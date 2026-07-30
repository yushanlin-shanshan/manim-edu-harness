"""Structured generation retry — ported from OpenMAIC lib/generation/generation-retry.ts.

Distinguishes retryable (network / 429 / 5xx) from non-retryable (4xx auth / validation).
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY_MS = 1000
DEFAULT_MAX_DELAY_MS = 16000

RETRYABLE_STATUS_CODES = {408, 409, 425, 429}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}

_RETRYABLE_MSG = re.compile(
    r"rate limit|too many requests|timeout|timed out|fetch failed|network|"
    r"ECONNRESET|ECONNREFUSED|ECONNABORTED|ETIMEDOUT|ENOTFOUND|EPIPE|"
    r"socket hang up|RemoteDisconnected|Connection reset|SSL|temporarily unavailable",
    re.I,
)


@dataclass
class GenerationRetryEvent:
    label: str
    attempt: int
    max_attempts: int
    next_delay_ms: int
    reason: str


def _status_code(error: BaseException) -> int | None:
    for attr in ("status_code", "status", "code"):
        raw = getattr(error, attr, None)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    return None


def is_retryable_generation_error(error: BaseException) -> bool:
    if getattr(error, "is_retryable", None) is False:
        return False
    if getattr(error, "is_retryable", None) is True:
        return True
    status = _status_code(error)
    if status is not None:
        if status in RETRYABLE_STATUS_CODES or status >= 500:
            return True
        if status in NON_RETRYABLE_STATUS_CODES or 400 <= status < 500:
            return False
    name = type(error).__name__
    if name in {"TimeoutError", "ConnectionError", "BrokenPipeError"}:
        return True
    return bool(_RETRYABLE_MSG.search(str(error) or ""))


def _delay_ms(attempt: int, base_ms: int, max_ms: int) -> int:
    exponential = min(max_ms, base_ms * (2 ** max(0, attempt - 1)))
    jitter = int(exponential * random.random() * 0.2)
    return min(max_ms, exponential + jitter)


def with_generation_retry(
    operation: Callable[[int], T],
    *,
    label: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay_ms: int = DEFAULT_BASE_DELAY_MS,
    max_delay_ms: int = DEFAULT_MAX_DELAY_MS,
    on_retry: Callable[[GenerationRetryEvent], None] | None = None,
    should_retry_result: Callable[[T], bool] | None = None,
) -> T:
    """Run operation(attempt) with exponential backoff on retryable errors."""
    max_attempts = max_retries + 1
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = operation(attempt)
            if should_retry_result and should_retry_result(result) and attempt < max_attempts:
                delay = _delay_ms(attempt, base_delay_ms, max_delay_ms)
                if on_retry:
                    on_retry(
                        GenerationRetryEvent(
                            label=label,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            next_delay_ms=delay,
                            reason="retryable result",
                        )
                    )
                time.sleep(delay / 1000.0)
                continue
            return result
        except BaseException as exc:  # noqa: BLE001 — classify then re-raise
            last_error = exc
            if not is_retryable_generation_error(exc) or attempt >= max_attempts:
                raise
            delay = _delay_ms(attempt, base_delay_ms, max_delay_ms)
            if on_retry:
                on_retry(
                    GenerationRetryEvent(
                        label=label,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        next_delay_ms=delay,
                        reason=str(exc) or type(exc).__name__,
                    )
                )
            time.sleep(delay / 1000.0)
    assert last_error is not None
    raise last_error
