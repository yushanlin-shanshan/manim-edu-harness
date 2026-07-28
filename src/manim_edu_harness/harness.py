"""Core harness: isolated candidate → multi-agent produce → verify → review → promote."""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any

from .agents.pipeline import AgentPipeline
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
from .verify_manim import verify_candidate
from .zhipu_client import ZhipuClient


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

    def _client(self) -> ZhipuClient:
        z = self.config.get("zhipu", {})
        return ZhipuClient(
            model=z.get("model", "glm-4-plus"),
            temperature=float(z.get("temperature", 0.4)),
            max_tokens=int(z.get("max_tokens", 8192)),
        )

    def _execute(self, meta: dict[str, Any]) -> dict[str, Any]:
        run_dir = Path(meta["run_dir"])
        candidate = Path(meta["candidate"])
        request = meta["request"]
        client = self._client()
        pipe = AgentPipeline(client, candidate, request)

        meta["phase"] = "planner"
        self._persist(meta)
        plan = pipe.run_planner()

        meta["phase"] = "writer"
        self._persist(meta)
        script = pipe.run_writer(plan)

        meta["phase"] = "coder"
        self._persist(meta)
        scenes = pipe.run_coder(plan, script)

        episode = {
            "title": plan.get("title") or request.get("topic"),
            "topic": request.get("topic"),
            "major": request.get("major"),
            "learning_objectives": plan.get("learning_objectives", []),
            "scenes": scenes,
            "style": request.get("style") or self.config.get("pipeline", {}).get("short_drama", {}).get("style"),
        }
        write_json(candidate / "EPISODE.json", episode)

        while True:
            meta["phase"] = "verify"
            self._persist(meta)
            verification = verify_candidate(candidate, attempt_render=True)
            write_json(candidate / "VERIFICATION.json", verification)
            write_json(
                candidate / "WORKER_RESULT.json",
                {
                    "ok": verification.get("ok", False),
                    "claims": [
                        f"Generated short-drama episode for topic={request.get('topic')}",
                        f"Manim modules: {', '.join(scenes)}",
                    ],
                    "scenes": scenes,
                    "verification_ok": verification.get("ok", False),
                },
            )

            meta["phase"] = "review"
            meta["status"] = "REVIEWING"
            self._persist(meta)
            audit = pipe.run_reviewer(plan, script, scenes, verification)
            verdict = self._adjudicate(verification, audit)
            final = {
                "verdict": verdict,
                "verification_ok": verification.get("ok", False),
                "audit_verdict": audit.get("verdict"),
                "review_round": meta["review_round"],
            }
            write_json(candidate / "FINAL_REVIEW.json", final)
            round_dir = run_dir / "iterations" / f"{meta['review_round']:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            for name in (
                "VERIFICATION.json",
                "AUDIT.json",
                "FINAL_REVIEW.json",
                "WORKER_RESULT.json",
            ):
                src = candidate / name
                if src.is_file():
                    shutil.copy2(src, round_dir / name)

            if verdict == "PASS":
                return self._promote(meta)

            if verdict == "INCONCLUSIVE":
                meta["status"] = "PAUSED"
                meta["phase"] = "inconclusive"
                meta["pause_reason"] = "Missing blocking evidence or environment (e.g. manim)."
                self._persist(meta)
                return meta

            # FIX
            meta["review_round"] += 1
            if meta["review_round"] > meta["max_reviews"]:
                meta["status"] = "INCOMPLETE"
                meta["phase"] = "max_reviews"
                self._persist(meta)
                return meta
            meta["status"] = "FIXING"
            meta["phase"] = "fix"
            self._persist(meta)
            scenes = pipe.run_fix(audit, plan, script)
            episode["scenes"] = scenes
            write_json(candidate / "EPISODE.json", episode)

    def _adjudicate(self, verification: dict[str, Any], audit: dict[str, Any]) -> str:
        # Hard code/structure failures force FIX.
        if not verification.get("ok"):
            return "FIX"
        # Missing LaTeX/FFmpeg etc.: pause instead of burning repair rounds.
        if verification.get("env_blocked"):
            return "INCONCLUSIVE"
        audit_verdict = str(audit.get("verdict", "FIX")).upper()
        if audit.get("blockers"):
            return "FIX"
        if audit_verdict == "INCONCLUSIVE":
            return "INCONCLUSIVE"
        if audit_verdict == "PASS" and audit.get("math_ok", True):
            return "PASS"
        if audit_verdict == "FIX":
            return "FIX"
        return "FIX"

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
        promote(candidate, self.workspace, backup=backup)
        meta["status"] = "COMPLETE"
        meta["phase"] = "promoted"
        meta["workspace_fp_after"] = fingerprint(self.workspace)
        report = {
            "run_id": meta["run_id"],
            "status": "COMPLETE",
            "request": meta["request"],
            "episode": read_json(candidate / "EPISODE.json"),
            "final_review": read_json(candidate / "FINAL_REVIEW.json"),
        }
        write_json(run_dir / "REPORT.json", report)
        write_json(self.workspace / "LATEST_EPISODE.json", report["episode"])
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
            # Resume from verification/review on existing candidate
            return self._resume_review_loop(meta)
        if meta.get("status") in ACTIVE_STATES and meta.get("phase") not in ("promoted",):
            raise RuntimeError(
                f"Run {meta.get('run_id')} is {meta.get('status')}/{meta.get('phase')}; "
                "stop it first or wait for completion."
            )
        raise RuntimeError(f"Cannot continue status={meta.get('status')} phase={meta.get('phase')}")

    def _resume_review_loop(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Re-run verify+review on existing candidate after INCONCLUSIVE pause."""
        candidate = Path(meta["candidate"])
        request = meta["request"]
        plan = read_json(candidate / "PLAN.json")
        script = (candidate / "SCRIPT.md").read_text(encoding="utf-8")
        episode = read_json(candidate / "EPISODE.json")
        scenes = episode.get("scenes", [])
        client = self._client()
        pipe = AgentPipeline(client, candidate, request)

        verification = verify_candidate(candidate, attempt_render=True)
        write_json(candidate / "VERIFICATION.json", verification)
        audit = pipe.run_reviewer(plan, script, scenes, verification)
        verdict = self._adjudicate(verification, audit)
        write_json(
            candidate / "FINAL_REVIEW.json",
            {
                "verdict": verdict,
                "verification_ok": verification.get("ok", False),
                "audit_verdict": audit.get("verdict"),
                "review_round": meta["review_round"],
                "resumed": True,
            },
        )
        if verdict == "PASS":
            return self._promote(meta)
        if verdict == "INCONCLUSIVE":
            meta["status"] = "PAUSED"
            meta["phase"] = "inconclusive"
            self._persist(meta)
            return meta
        meta["status"] = "FIXING"
        meta["review_round"] += 1
        if meta["review_round"] > meta["max_reviews"]:
            meta["status"] = "INCOMPLETE"
            self._persist(meta)
            return meta
        self._persist(meta)
        scenes = pipe.run_fix(audit, plan, script)
        episode["scenes"] = scenes
        write_json(candidate / "EPISODE.json", episode)
        # Continue full loop from verify
        meta["status"] = "RUNNING"
        # Re-enter execute-like loop by recursive call pattern
        while True:
            verification = verify_candidate(candidate, attempt_render=True)
            write_json(candidate / "VERIFICATION.json", verification)
            audit = pipe.run_reviewer(plan, script, scenes, verification)
            verdict = self._adjudicate(verification, audit)
            write_json(
                candidate / "FINAL_REVIEW.json",
                {
                    "verdict": verdict,
                    "verification_ok": verification.get("ok", False),
                    "audit_verdict": audit.get("verdict"),
                    "review_round": meta["review_round"],
                },
            )
            if verdict == "PASS":
                return self._promote(meta)
            if verdict == "INCONCLUSIVE":
                meta["status"] = "PAUSED"
                meta["phase"] = "inconclusive"
                self._persist(meta)
                return meta
            meta["review_round"] += 1
            if meta["review_round"] > meta["max_reviews"]:
                meta["status"] = "INCOMPLETE"
                self._persist(meta)
                return meta
            scenes = pipe.run_fix(audit, plan, script)
            episode["scenes"] = scenes
            write_json(candidate / "EPISODE.json", episode)

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

    def batch(self, topics_file: Path | None = None, *, limit: int | None = None) -> list[dict[str, Any]]:
        topics_file = topics_file or (self.root / self.config.get("batch", {}).get("topics_file", "topics/seed_stem.json"))
        payload = read_json(topics_file)
        topics = payload.get("topics", payload if isinstance(payload, list) else [])
        if limit is not None:
            topics = topics[:limit]
        results = []
        for topic in topics:
            # Clear completed ACTIVE so next can start
            if self._state_path().is_file():
                prev = read_json(self._state_path())
                if prev.get("status") in ACTIVE_STATES:
                    raise RuntimeError("Cannot batch while a run is active/paused unfinished")
            req = topic if isinstance(topic, dict) else {"topic": str(topic)}
            if "topic" not in req:
                raise ValueError(f"topic entry missing 'topic': {req}")
            results.append(self.start(req))
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
