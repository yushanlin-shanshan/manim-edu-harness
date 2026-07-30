"""Batch quota / budget (OpenMAIC ``lib/agent/runtime/quota`` pattern).

Deterministic stop conditions for long batch runs so operators can cap
episodes, total FIX attempts, consecutive/total errors, or wall time
without wiping in-flight work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _positive_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


@dataclass
class BatchQuota:
    """Mutable quota tracker for a single batch invocation."""

    max_episodes: int | None = None
    max_attempts_total: int | None = None
    max_errors: int | None = None
    max_elapsed_seconds: float | None = None

    episodes_done: int = 0
    attempts_spent: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    stop_reason: str | None = None
    skipped: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any] | None = None,
        *,
        max_episodes: int | None = None,
        max_errors: int | None = None,
        max_elapsed_seconds: float | None = None,
        max_attempts_total: int | None = None,
    ) -> "BatchQuota":
        batch = dict((config or {}).get("batch") or {})
        quota = dict(batch.get("quota") or {})
        return cls(
            max_episodes=_positive_int(
                max_episodes if max_episodes is not None else quota.get("max_episodes")
            ),
            max_attempts_total=_positive_int(
                max_attempts_total
                if max_attempts_total is not None
                else quota.get("max_attempts_total")
            ),
            max_errors=_positive_int(
                max_errors if max_errors is not None else quota.get("max_errors")
            ),
            max_elapsed_seconds=_positive_float(
                max_elapsed_seconds
                if max_elapsed_seconds is not None
                else quota.get("max_elapsed_seconds")
            ),
        )

    def remaining(self) -> int:
        """Episodes still allowed (OpenMAIC ``QuotaSource.remaining``).

        Returns a large sentinel when uncapped so callers can use ``<= 0``.
        """
        if self.stop_reason:
            return 0
        if self.max_episodes is None:
            return 10**9
        return max(0, self.max_episodes - self.episodes_done)

    def should_stop(self) -> bool:
        return self._evaluate_stop() is not None

    def _evaluate_stop(self) -> str | None:
        if self.stop_reason:
            return self.stop_reason
        if self.max_episodes is not None and self.episodes_done >= self.max_episodes:
            return f"max_episodes={self.max_episodes}"
        if (
            self.max_attempts_total is not None
            and self.attempts_spent >= self.max_attempts_total
        ):
            return f"max_attempts_total={self.max_attempts_total}"
        if self.max_errors is not None and self.errors >= self.max_errors:
            return f"max_errors={self.max_errors}"
        if (
            self.max_elapsed_seconds is not None
            and self.elapsed_seconds >= self.max_elapsed_seconds
        ):
            return f"max_elapsed_seconds={self.max_elapsed_seconds}"
        return None

    def record(self, result: dict[str, Any], *, elapsed_seconds: float) -> None:
        """Consume one episode result and refresh stop_reason."""
        self.episodes_done += 1
        self.attempts_spent += int(result.get("attempts") or 0)
        self.elapsed_seconds = float(elapsed_seconds)
        status = str(result.get("status") or "")
        if status in {"ERROR", "INCONCLUSIVE"}:
            self.errors += 1
        reason = self._evaluate_stop()
        if reason:
            self.stop_reason = reason

    def mark_skipped(self, *, title: str, index: int, total: int) -> dict[str, Any]:
        row = {
            "title": title,
            "slug": None,
            "status": "QUOTA_SKIPPED",
            "verdict": "QUOTA_SKIPPED",
            "attempts": 0,
            "run_dir": None,
            "delivered": None,
            "reason": self.stop_reason or "quota exhausted",
            "index": index,
            "total": total,
        }
        self.skipped.append(row)
        return row

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_episodes": self.max_episodes,
            "max_attempts_total": self.max_attempts_total,
            "max_errors": self.max_errors,
            "max_elapsed_seconds": self.max_elapsed_seconds,
            "episodes_done": self.episodes_done,
            "attempts_spent": self.attempts_spent,
            "errors": self.errors,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "remaining_episodes": self.remaining() if self.max_episodes else None,
            "stop_reason": self.stop_reason,
            "skipped_count": len(self.skipped),
        }
