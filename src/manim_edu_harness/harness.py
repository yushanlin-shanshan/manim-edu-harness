"""Core harness: interactive ACTIVE.json lifecycle over the shared EpisodeLoop."""

from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from .batch_quota import BatchQuota
from .control_plane import EpisodeLoop, make_llm_client, run_batch_item
from .fsutil import (
    copy_tree,
    fingerprint,
    load_config,
    load_dotenv,
    now_id,
    project_root,
    promote,
    read_json,
    write_json,
)
from .textutil import sanitize_text


ACTIVE_STATES = {"RUNNING", "PAUSED", "REVIEWING", "FIXING"}


class Harness:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or project_root()
        load_dotenv(self.root)
        self.config = load_config(self.root)
        self.workspace = self.root / self.config.get("workspace", "workspace")
        self.runs_dir = self.root / self.config.get("runs_dir", "runs")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        (self.workspace / ".gitkeep").touch(exist_ok=True)
        (self.runs_dir / ".gitkeep").touch(exist_ok=True)

    def _state_path(self) -> Path:
        return self.runs_dir / "ACTIVE.json"

    def active_run(self) -> dict[str, Any] | None:
        path = self._state_path()
        if not path.is_file():
            return None
        data = read_json(path)
        if data.get("status") in ("COMPLETE", "INCOMPLETE", "FAILED"):
            return None
        return data

    def status(self) -> dict[str, Any]:
        active = None
        path = self._state_path()
        if path.is_file():
            active = read_json(path)
        return {
            "workspace": str(self.workspace),
            "runs_dir": str(self.runs_dir),
            "active": active,
            "workspace_fingerprint": fingerprint(self.workspace) if any(self.workspace.iterdir()) else None,
        }

    def _reject_if_busy(self) -> None:
        active = self.active_run()
        if active and active.get("status") in ACTIVE_STATES:
            raise RuntimeError(
                f"Unfinished run {active.get('run_id')} status={active.get('status')}. "
                "Use continue/status/stop; do not start a duplicate."
            )

    def start(self, request: dict[str, Any], *, run_id: str | None = None) -> dict[str, Any]:
        self._reject_if_busy()
        run_id = run_id or now_id("edu")
        run_dir = self.runs_dir / run_id
        if run_dir.exists():
            raise RuntimeError(f"run dir already exists: {run_dir}")
        run_dir.mkdir(parents=True)
        candidate = run_dir / "candidate"
        candidate.mkdir()
        # Seed candidate from formal workspace snapshot
        copy_tree(self.workspace, candidate)
        meta = {
            "run_id": run_id,
            "status": "RUNNING",
            "request": request,
            "run_dir": str(run_dir),
            "candidate": str(candidate),
            "workspace_fp_at_start": fingerprint(self.workspace),
            "review_round": 0,
            "max_reviews": int(self.config.get("max_reviews", 3)),
            "phase": "init",
        }
        write_json(run_dir / "REQUEST.json", request)
        write_json(self._state_path(), meta)
        write_json(run_dir / "STATUS.json", meta)
        try:
            result = self._execute(meta)
            return result
        except Exception as exc:
            meta["status"] = "FAILED"
            meta["error"] = str(exc)
            meta["traceback"] = traceback.format_exc()
            write_json(self._state_path(), meta)
            write_json(run_dir / "STATUS.json", meta)
            raise

    def _client(self, *, dry_run: bool = False):
        return make_llm_client(self.config, dry_run=dry_run)

    def _snapshot_iteration(self, run_dir: Path, candidate: Path, attempt: int) -> None:
        round_dir = run_dir / "iterations" / f"{attempt:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "VERIFICATION.json",
            "AUDIT.json",
            "FINAL_REVIEW.json",
            "WORKER_RESULT.json",
            "HANDOFF.json",
            "RULE_GATE.json",
            "RENDER_RESULT.json",
            "TTS_RESULT.json",
        ):
            src = candidate / name
            if src.is_file():
                shutil.copy2(src, round_dir / name)

    def _execute(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Interactive adapter: seed candidate, then shared EpisodeLoop topology."""
        run_dir = Path(meta["run_dir"])
        candidate = Path(meta["candidate"])
        request = meta["request"]
        dry_run = bool(meta.get("dry_run") or request.get("dry_run"))
        client = self._client(dry_run=dry_run)
        loop = EpisodeLoop(self.config, client)

        def on_attempt(outcome) -> None:
            meta["review_round"] = outcome.attempt
            if outcome.verdict == "PASS":
                meta["phase"] = "review"
                meta["status"] = "REVIEWING"
            elif outcome.verdict == "INCONCLUSIVE":
                meta["phase"] = "inconclusive"
                meta["status"] = "REVIEWING"
            elif outcome.verdict == "ERROR":
                meta["phase"] = "failed"
                meta["status"] = "FAILED"
            else:
                meta["phase"] = "fix"
                meta["status"] = "FIXING"
            self._persist(meta)
            self._snapshot_iteration(run_dir, candidate, outcome.attempt)

        meta["phase"] = "episode_loop"
        meta["status"] = "RUNNING"
        self._persist(meta)

        outcome = loop.run_until_done(
            request,
            candidate,
            max_reviews=int(meta.get("max_reviews") or self.config.get("max_reviews", 3)),
            dry_run=dry_run,
            on_attempt=on_attempt,
        )
        meta["review_round"] = outcome.attempts
        meta["loop_status"] = outcome.status
        meta["loop_reason"] = outcome.reason

        if outcome.verdict == "PASS":
            return self._promote(meta)
        if outcome.verdict == "INCONCLUSIVE":
            meta["status"] = "PAUSED"
            meta["phase"] = "inconclusive"
            meta["pause_reason"] = (
                outcome.reason or "Missing blocking evidence or environment (e.g. manim)."
            )
            self._persist(meta)
            return meta
        if outcome.verdict == "ERROR":
            meta["status"] = "FAILED"
            meta["phase"] = "error"
            meta["error"] = outcome.reason
            self._persist(meta)
            return meta

        meta["status"] = "INCOMPLETE"
        meta["phase"] = "max_reviews"
        self._persist(meta)
        return meta

    def _promote(self, meta: dict[str, Any]) -> dict[str, Any]:
        run_dir = Path(meta["run_dir"])
        candidate = Path(meta["candidate"])
        backup = run_dir / "workspace_backup"
        # Fingerprint check: formal workspace unchanged since start (simple equality)
        current_fp = fingerprint(self.workspace)
        if meta.get("workspace_fp_at_start") and current_fp != meta["workspace_fp_at_start"]:
            meta["status"] = "PAUSED"
            meta["pause_reason"] = "Formal workspace changed during run; refuse blind promote."
            self._persist(meta)
            return meta
        # Promote latest episode to workspace root; keep library/ intact.
        promote(candidate, self.workspace, backup=backup)
        library_dir = self.workspace / "library" / meta["run_id"]
        library_dir.mkdir(parents=True, exist_ok=True)
        copy_tree(candidate, library_dir)
        # Prefer rendered mp4 into library/videos when present under candidate media/
        videos_dir = library_dir / "videos"
        videos_dir.mkdir(exist_ok=True)
        for mp4 in candidate.rglob("EpisodeScene.mp4"):
            if "partial_movie_files" in mp4.parts:
                continue
            target = videos_dir / "EpisodeScene.mp4"
            target.write_bytes(mp4.read_bytes())
            break
        meta["status"] = "COMPLETE"
        meta["phase"] = "promoted"
        meta["library_path"] = str(library_dir)
        meta["workspace_fp_after"] = fingerprint(self.workspace)
        report = {
            "run_id": meta["run_id"],
            "status": "COMPLETE",
            "request": meta["request"],
            "episode": read_json(candidate / "EPISODE.json"),
            "final_review": read_json(candidate / "FINAL_REVIEW.json"),
            "library_path": str(library_dir),
        }
        write_json(run_dir / "REPORT.json", report)
        write_json(self.workspace / "LATEST_EPISODE.json", report["episode"])
        write_json(library_dir / "REPORT.json", report)
        catalog_path = self.workspace / "library" / "catalog.json"
        catalog = {"episodes": []}
        if catalog_path.is_file():
            try:
                catalog = read_json(catalog_path)
            except Exception:
                catalog = {"episodes": []}
        episodes = [e for e in catalog.get("episodes", []) if e.get("run_id") != meta["run_id"]]
        video_rel = None
        if (library_dir / "videos" / "EpisodeScene.mp4").is_file():
            video_rel = f"library/{meta['run_id']}/videos/EpisodeScene.mp4"
        episodes.append(
            {
                "run_id": meta["run_id"],
                "topic": meta["request"].get("topic"),
                "title": report["episode"].get("title"),
                "path": f"library/{meta['run_id']}",
                "video": video_rel,
            }
        )
        catalog["episodes"] = episodes
        write_json(catalog_path, catalog)
        self._persist(meta)
        return meta

    def _persist(self, meta: dict[str, Any]) -> None:
        write_json(self._state_path(), meta)
        write_json(Path(meta["run_dir"]) / "STATUS.json", meta)

    def continue_run(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.is_file():
            raise RuntimeError("No ACTIVE.json to continue")
        meta = read_json(path)
        if meta.get("status") == "PAUSED" and meta.get("phase") == "inconclusive":
            meta["status"] = "RUNNING"
            return self._resume_review_loop(meta)
        if meta.get("status") in ACTIVE_STATES and meta.get("phase") not in ("promoted",):
            raise RuntimeError(
                f"Run {meta.get('run_id')} is {meta.get('status')}/{meta.get('phase')}; "
                "stop it first or wait for completion."
            )
        raise RuntimeError(f"Cannot continue status={meta.get('status')} phase={meta.get('phase')}")

    def _resume_review_loop(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Resume after INCONCLUSIVE via the same EpisodeLoop topology."""
        run_dir = Path(meta["run_dir"])
        candidate = Path(meta["candidate"])
        request = meta["request"]
        dry_run = bool(meta.get("dry_run") or request.get("dry_run"))
        client = self._client(dry_run=dry_run)
        loop = EpisodeLoop(self.config, client)

        start_attempt = int(meta.get("review_round") or 0) + 1
        max_reviews = int(meta.get("max_reviews") or self.config.get("max_reviews", 3))
        if start_attempt > max_reviews:
            meta["status"] = "INCOMPLETE"
            meta["phase"] = "max_reviews"
            self._persist(meta)
            return meta

        fix_feedback = None
        fix_path = candidate / "FIX_FEEDBACK.md"
        if fix_path.is_file():
            fix_feedback = fix_path.read_text(encoding="utf-8").strip() or None

        def on_attempt(outcome) -> None:
            meta["review_round"] = outcome.attempt
            meta["status"] = "FIXING" if outcome.verdict == "FIX" else "REVIEWING"
            self._persist(meta)
            self._snapshot_iteration(run_dir, candidate, outcome.attempt)

        outcome = loop.run_until_done(
            request,
            candidate,
            max_reviews=max_reviews,
            dry_run=dry_run,
            on_attempt=on_attempt,
            start_attempt=start_attempt,
            initial_fix_feedback=fix_feedback,
        )
        meta["review_round"] = outcome.attempts
        meta["loop_status"] = outcome.status
        meta["loop_reason"] = outcome.reason

        if outcome.verdict == "PASS":
            return self._promote(meta)
        if outcome.verdict == "INCONCLUSIVE":
            meta["status"] = "PAUSED"
            meta["phase"] = "inconclusive"
            meta["pause_reason"] = outcome.reason or meta.get("pause_reason")
            self._persist(meta)
            return meta
        if outcome.verdict == "ERROR":
            meta["status"] = "FAILED"
            meta["error"] = outcome.reason
            self._persist(meta)
            return meta
        meta["status"] = "INCOMPLETE"
        meta["phase"] = "max_reviews"
        self._persist(meta)
        return meta

    def stop(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.is_file():
            return {"ok": True, "message": "no active run"}
        meta = read_json(path)
        if meta.get("status") in ("COMPLETE", "INCOMPLETE", "FAILED"):
            return meta
        meta["status"] = "PAUSED"
        meta["pause_reason"] = meta.get("pause_reason") or "stopped by operator"
        self._persist(meta)
        return meta

    def batch(
        self,
        topics_file: Path | None = None,
        *,
        limit: int | None = None,
        start: int = 0,
        dry_run: bool = False,
        delivered_root: Path | None = None,
    ) -> list[dict[str, Any]]:
        """Production batch via shared EpisodeLoop → workspace/delivered/.

        Prefer this over per-topic Harness.start() so TTS/renderer/reviewer match
        ``batch_harness.py``.
        """
        topics_file = topics_file or (
            self.root / self.config.get("batch", {}).get("topics_file", "topics/seed_stem.json")
        )
        payload = read_json(topics_file)
        if isinstance(payload, list):
            topics = payload
        else:
            topics = (
                payload.get("topics")
                or payload.get("knowledge_points")
                or payload.get("items")
                or []
            )
        topics = topics[max(0, int(start)) :]
        if limit is not None:
            topics = topics[:limit]

        client = self._client(dry_run=dry_run)
        delivered = delivered_root or (self.workspace / "delivered")
        delivered.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, Any]] = []
        quota = BatchQuota.from_config(self.config)
        t0 = time.time()
        total = len(topics)
        for i, topic in enumerate(topics, 1):
            req = topic if isinstance(topic, dict) else {"topic": str(topic)}
            if "topic" not in req and "title" not in req:
                raise ValueError(f"topic entry missing 'topic'/'title': {req}")
            title = str(req.get("title") or req.get("topic") or f"item-{i}")
            if quota.should_stop() or quota.remaining() <= 0:
                results.append(
                    quota.mark_skipped(title=sanitize_text(title), index=i, total=total)
                )
                for j in range(i + 1, total + 1):
                    rest = topics[j - 1]
                    rest_req = rest if isinstance(rest, dict) else {"topic": str(rest)}
                    rest_title = str(
                        rest_req.get("title") or rest_req.get("topic") or f"item-{j}"
                    )
                    results.append(
                        quota.mark_skipped(
                            title=sanitize_text(rest_title), index=j, total=total
                        )
                    )
                break
            row = run_batch_item(
                req,
                self.config,
                client,
                self.runs_dir,
                delivered,
                dry_run=dry_run,
            )
            results.append(row)
            quota.record(row, elapsed_seconds=time.time() - t0)
        return results


def build_request_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    return {
        "topic": text,
        "format": "理科知识点短剧",
        "audience": "高中/大学低年级",
        "language": "zh-CN",
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m manim_edu_harness.harness start|status|stop|continue|batch [...]")
        return 2
    cmd = argv[0]
    h = Harness()
    if cmd == "status":
        print(json.dumps(h.status(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "stop":
        print(json.dumps(h.stop(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "continue":
        print(json.dumps(h.continue_run(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "start":
        if len(argv) < 2:
            print("usage: ... start '<topic or json>'")
            return 2
        req = build_request_from_text(" ".join(argv[1:]))
        print(json.dumps(h.start(req), ensure_ascii=False, indent=2))
        return 0
    if cmd == "batch":
        limit = None
        topics = None
        args = argv[1:]
        i = 0
        while i < len(args):
            if args[i] == "--limit":
                limit = int(args[i + 1])
                i += 2
            elif args[i] == "--topics":
                topics = Path(args[i + 1])
                i += 2
            else:
                i += 1
        results = h.batch(topics, limit=limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
