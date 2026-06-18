"""Tests for parsing, aggregation, pricing, and formatting.

Run with:  python -m unittest discover -s tests
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from band_usage.aggregate import window_start
from band_usage.claude_usage import parse_claude
from band_usage.codex_usage import parse_codex
from band_usage.format import build_message, human_tokens, progress_bar
from band_usage.models import Totals
from band_usage.pricing import price_for

NOW = datetime.now(timezone.utc)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class ClaudeParsingTest(unittest.TestCase):
    def test_parses_and_dedupes_and_windows(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            recent = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            old = (NOW - timedelta(hours=10)).isoformat().replace("+00:00", "Z")
            rows = [
                {"type": "summary"},  # ignored
                {
                    "type": "assistant",
                    "timestamp": recent,
                    "requestId": "r1",
                    "message": {
                        "id": "m1",
                        "model": "claude-sonnet-4-6",
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "cache_creation_input_tokens": 10,
                            "cache_read_input_tokens": 200,
                        },
                    },
                },
                {  # duplicate of m1/r1 -> de-duped
                    "type": "assistant",
                    "timestamp": recent,
                    "requestId": "r1",
                    "message": {
                        "id": "m1",
                        "model": "claude-sonnet-4-6",
                        "usage": {"input_tokens": 100, "output_tokens": 50},
                    },
                },
                {  # too old -> filtered by window
                    "type": "assistant",
                    "timestamp": old,
                    "requestId": "r2",
                    "message": {
                        "id": "m2",
                        "model": "claude-opus-4-8",
                        "usage": {"input_tokens": 999, "output_tokens": 999},
                    },
                },
            ]
            _write_jsonl(base / "proj" / "session.jsonl", rows)

            since = NOW - timedelta(hours=5)
            records = parse_claude(str(base), since)
            self.assertEqual(len(records), 1)
            r = records[0]
            self.assertEqual(r.input_tokens, 100)
            self.assertEqual(r.cache_read_tokens, 200)

            totals = Totals.of(records)
            self.assertEqual(totals.total_tokens, 100 + 50 + 10 + 200)
            self.assertGreater(totals.cost, 0)

    def test_missing_dir_returns_empty(self):
        self.assertEqual(parse_claude("/no/such/dir"), [])


class CodexParsingTest(unittest.TestCase):
    def test_sums_last_token_usage_deltas(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            t1 = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            t2 = (NOW - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
            rows = [
                {"type": "session_meta", "payload": {"turn_context": {"model": "gpt-5-codex"}}},
                {
                    "type": "event_msg",
                    "timestamp": t1,
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"input_tokens": 100, "output_tokens": 20},
                            "last_token_usage": {
                                "input_tokens": 100,
                                "cached_input_tokens": 40,
                                "output_tokens": 20,
                            },
                        },
                    },
                },
                {
                    "type": "event_msg",
                    "timestamp": t2,
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"input_tokens": 250, "output_tokens": 60},
                            "last_token_usage": {
                                "input_tokens": 150,
                                "cached_input_tokens": 0,
                                "output_tokens": 40,
                            },
                        },
                    },
                },
            ]
            _write_jsonl(base / "2026" / "06" / "18" / "rollout-x.jsonl", rows)

            records = parse_codex(str(base), NOW - timedelta(hours=5))
            self.assertEqual(len(records), 2)
            totals = Totals.of(records)
            # fresh input: (100-40) + (150-0) = 210; output 60; cached 40
            self.assertEqual(totals.input_tokens, 210)
            self.assertEqual(totals.output_tokens, 60)
            self.assertEqual(totals.cache_read_tokens, 40)
            self.assertTrue(all(r.model == "gpt-5-codex" for r in records))

    def test_falls_back_to_total_when_no_deltas(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            rows = [
                {"type": "event_msg", "payload": {"info": {
                    "total_token_usage": {"input_tokens": 500, "output_tokens": 100}}}},
            ]
            _write_jsonl(base / "rollout-y.jsonl", rows)
            records = parse_codex(str(base), since=None)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].input_tokens, 500)


class PricingTest(unittest.TestCase):
    def test_longest_substring_match(self):
        codex = price_for("gpt-5-codex")
        plain = price_for("gpt-5")
        # gpt-5-codex defines cache_read; both share input price here.
        self.assertEqual(codex.input, plain.input)
        self.assertNotEqual(codex.cache_read, 0)

    def test_unknown_model_uses_default(self):
        self.assertGreater(price_for("totally-unknown").input, 0)


class FormatTest(unittest.TestCase):
    def test_human_tokens(self):
        self.assertEqual(human_tokens(1_500_000), "1.5M")
        self.assertEqual(human_tokens(2500), "2.5k")
        self.assertEqual(human_tokens(42), "42")

    def test_progress_bar_clamps(self):
        self.assertEqual(progress_bar(50, width=10), "█████░░░░░")
        self.assertEqual(progress_bar(150, width=4), "████")
        self.assertEqual(progress_bar(-5, width=4), "░░░░")

    def test_build_message_with_budget(self):
        claude = Totals(cost=10.0)
        codex = Totals(cost=2.0)
        title, body = build_message(
            claude, codex, "last 5h", {"claude_usd": 20, "codex_usd": 10}
        )
        self.assertIn("AI usage - last 5h", title)
        self.assertIn("Claude $10.00/$20.00 50%", body)
        self.assertIn("Total $12.00", body)

    def test_build_message_without_budget(self):
        claude = Totals(input_tokens=1_000_000, cost=3.0)
        codex = Totals(output_tokens=500_000, cost=1.0)
        _, body = build_message(claude, codex, "today", {})
        self.assertIn("tok", body)
        self.assertIn("Total $4.00", body)


class WindowTest(unittest.TestCase):
    def test_window_specs(self):
        self.assertEqual(window_start("all")[0], None)
        start, label = window_start("5h", now=NOW)
        self.assertEqual(label, "last 5h")
        self.assertAlmostEqual((NOW - start).total_seconds(), 5 * 3600, delta=2)
        _, label7 = window_start("7d", now=NOW)
        self.assertEqual(label7, "last 7d")


if __name__ == "__main__":
    unittest.main()
