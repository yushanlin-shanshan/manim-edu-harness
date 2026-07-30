"""Tests for batch quota / budget."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.batch_quota import BatchQuota


class BatchQuotaTests(unittest.TestCase):
    def test_max_errors_stops(self) -> None:
        q = BatchQuota(max_errors=2)
        q.record({"status": "ERROR", "attempts": 1}, elapsed_seconds=1)
        self.assertFalse(q.should_stop())
        q.record({"status": "INCONCLUSIVE", "attempts": 1}, elapsed_seconds=2)
        self.assertTrue(q.should_stop())
        self.assertIn("max_errors", q.stop_reason or "")

    def test_max_attempts_total(self) -> None:
        q = BatchQuota(max_attempts_total=3)
        q.record({"status": "FIX_UNRESOLVED", "attempts": 2}, elapsed_seconds=1)
        self.assertFalse(q.should_stop())
        q.record({"status": "PASS", "attempts": 1}, elapsed_seconds=2)
        self.assertTrue(q.should_stop())

    def test_max_episodes_remaining(self) -> None:
        q = BatchQuota(max_episodes=1)
        self.assertEqual(q.remaining(), 1)
        q.record({"status": "PASS", "attempts": 1}, elapsed_seconds=1)
        self.assertEqual(q.remaining(), 0)
        self.assertTrue(q.should_stop())

    def test_from_config(self) -> None:
        q = BatchQuota.from_config(
            {"batch": {"quota": {"max_errors": 5, "max_elapsed_seconds": 100}}},
            max_errors=2,
        )
        self.assertEqual(q.max_errors, 2)
        self.assertEqual(q.max_elapsed_seconds, 100.0)

    def test_mark_skipped(self) -> None:
        q = BatchQuota(max_errors=1)
        q.record({"status": "ERROR", "attempts": 0}, elapsed_seconds=1)
        row = q.mark_skipped(title="x", index=2, total=3)
        self.assertEqual(row["status"], "QUOTA_SKIPPED")
        self.assertEqual(q.snapshot()["skipped_count"], 1)


if __name__ == "__main__":
    unittest.main()
