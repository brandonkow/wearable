"""Tests for limit parsing and card formatting.

Run with:  python -m unittest discover -s tests
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from band_usage.claude_usage import read_claude_usage
from band_usage.codex_usage import read_codex_usage
from band_usage.format import bar, build_card, fmt_age, fmt_pct, fmt_reset
from band_usage.models import ToolUsage, limit_window

NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class ClaudeCacheTest(unittest.TestCase):
    def test_reads_both_windows(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "usage-cache.json"
            resets = int((NOW + timedelta(hours=2)).timestamp())
            _write_json(
                cache,
                {
                    "five_hour": {"used_percent": 24.0, "resets_at": resets},
                    "seven_day": {"used_percent": 41.0, "resets_at": resets},
                    "updated_at": NOW.isoformat().replace("+00:00", "Z"),
                },
            )
            usage = read_claude_usage(str(cache))
            self.assertTrue(usage.available)
            self.assertEqual(len(usage.windows), 2)
            self.assertEqual(usage.windows[0].label, "5h")
            self.assertEqual(usage.windows[0].used_percent, 24.0)
            self.assertIsNotNone(usage.windows[0].resets_at)

    def test_missing_cache_is_unavailable(self):
        usage = read_claude_usage("/no/such/cache.json")
        self.assertFalse(usage.available)
        self.assertIn("statusline", usage.note)


class CodexSessionTest(unittest.TestCase):
    def test_reads_latest_rate_limits(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            t1 = (NOW - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
            t2 = (NOW - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
            rows = [
                {"type": "session_meta", "payload": {}},
                {
                    "type": "event_msg",
                    "timestamp": t1,
                    "payload": {"type": "token_count", "info": {"rate_limits": {
                        "primary": {"used_percent": 10.0, "window_minutes": 300},
                        "secondary": {"used_percent": 20.0, "window_minutes": 10080},
                    }}},
                },
                {  # later event -> this one wins
                    "type": "event_msg",
                    "timestamp": t2,
                    "payload": {"type": "token_count", "info": {"rate_limits": {
                        "primary": {"used_percent": 62.0, "resets_in_seconds": 3600},
                        "secondary": {"used_percent": 38.0, "resets_in_seconds": 86400},
                    }}},
                },
            ]
            _write_jsonl(base / "2026" / "06" / "18" / "rollout-x.jsonl", rows)

            usage = read_codex_usage(str(base))
            self.assertTrue(usage.available)
            self.assertEqual(usage.windows[0].label, "5h")
            self.assertEqual(usage.windows[0].used_percent, 62.0)
            self.assertEqual(usage.windows[1].used_percent, 38.0)
            # resets_in_seconds resolved relative to the event timestamp
            self.assertIsNotNone(usage.windows[0].resets_at)

    def test_no_dir(self):
        self.assertFalse(read_codex_usage("/no/such/dir").available)

    def test_no_rate_limits(self):
        with tempfile.TemporaryDirectory() as d:
            _write_jsonl(Path(d) / "r.jsonl", [{"type": "event_msg", "payload": {}}])
            self.assertFalse(read_codex_usage(d).available)


class WindowHelperTest(unittest.TestCase):
    def test_resets_at_epoch(self):
        epoch = int((NOW + timedelta(hours=3)).timestamp())
        w = limit_window({"used_percent": 5, "resets_at": epoch}, "5h", NOW)
        self.assertEqual(w.used_percent, 5.0)
        self.assertAlmostEqual((w.resets_at - NOW).total_seconds(), 3 * 3600, delta=2)

    def test_resets_in_seconds(self):
        w = limit_window({"used_percentage": 7, "resets_in_seconds": 1800}, "wk", NOW)
        self.assertEqual(w.used_percent, 7.0)
        self.assertAlmostEqual((w.resets_at - NOW).total_seconds(), 1800, delta=2)


class FormatTest(unittest.TestCase):
    def test_bar(self):
        self.assertEqual(bar(50, width=8), "████░░░░")
        self.assertEqual(bar(0, width=4), "░░░░")
        self.assertEqual(bar(150, width=4), "████")
        self.assertEqual(bar(None, width=4), "····")

    def test_fmt_pct_and_reset(self):
        self.assertEqual(fmt_pct(24.0), "24%")
        self.assertEqual(fmt_pct(None), "?")
        self.assertEqual(fmt_reset(NOW + timedelta(minutes=47), NOW), "47m")
        self.assertEqual(fmt_reset(NOW + timedelta(hours=2), NOW), "2h")
        self.assertEqual(fmt_reset(NOW - timedelta(minutes=1), NOW), "now")
        self.assertEqual(fmt_reset(None, NOW), "")

    def test_fmt_age_only_when_stale(self):
        self.assertEqual(fmt_age(NOW - timedelta(minutes=2), NOW), "")
        self.assertEqual(fmt_age(NOW - timedelta(hours=3), NOW), "3h old")

    def test_build_card(self):
        claude = ToolUsage(
            "Claude",
            windows=[
                limit_window({"used_percent": 24, "resets_at": int((NOW + timedelta(hours=2)).timestamp())}, "5h", NOW),
                limit_window({"used_percent": 41}, "wk", NOW),
            ],
            updated_at=NOW,
        )
        codex_unavail = ToolUsage("Codex", available=False, note="no recent session")
        title, body = build_card([claude, codex_unavail], bar_width=8, now=NOW)
        self.assertEqual(title, "AI limits")
        self.assertIn("Claude .2h", body)
        self.assertIn("5h ██░░░░░░ 24%", body)
        self.assertIn("wk ", body)
        self.assertIn("Codex: no recent session", body)


if __name__ == "__main__":
    unittest.main()
