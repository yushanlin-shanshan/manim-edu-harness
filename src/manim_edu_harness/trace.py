"""Append-only TRACE.jsonl for harness observability (no secrets)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_trace(candidate: Path, event: str, **fields: Any) -> None:
    """Append one JSON line to candidate/TRACE.jsonl."""
    candidate = Path(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    path = candidate / "TRACE.jsonl"
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{k: v for k, v in fields.items() if k not in {"api_key", "token", "password"}},
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class TraceSpan:
    """Context manager for latency_ms."""

    def __init__(self, candidate: Path, event: str, **fields: Any) -> None:
        self.candidate = Path(candidate)
        self.event = event
        self.fields = fields
        self._t0 = 0.0
        self.ok = True
        self.error: str | None = None

    def __enter__(self) -> "TraceSpan":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        latency_ms = int((time.perf_counter() - self._t0) * 1000)
        ok = exc is None and self.ok
        err = self.error
        if exc is not None:
            err = f"{type(exc).__name__}: {exc}"
            ok = False
        append_trace(
            self.candidate,
            self.event,
            ok=ok,
            latency_ms=latency_ms,
            error=err,
            **self.fields,
        )
        return False
