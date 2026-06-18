"""Command-line entry point.

Examples::

    python -m band_usage --config config.json --dry-run
    python -m band_usage --config config.json            # send once
    python -m band_usage --config config.json --loop 300 # send every 5 min
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

from .aggregate import window_start
from .claude_usage import parse_claude
from .codex_usage import parse_codex
from .config import Config, load_config
from .format import build_message
from .models import Totals
from .notify import send_ntfy


def collect(cfg: Config, window: str):
    since, label = window_start(window)
    claude_records = (
        parse_claude(cfg.claude_logs_dir, since) if cfg.claude_enabled else []
    )
    codex_records = (
        parse_codex(cfg.codex_logs_dir, since, cfg.codex_default_model)
        if cfg.codex_enabled
        else []
    )
    claude_totals = Totals.of(claude_records, cfg.pricing_overrides)
    codex_totals = Totals.of(codex_records, cfg.pricing_overrides)
    return claude_totals, codex_totals, label


def run_once(cfg: Config, window: str, dry_run: bool) -> int:
    claude_totals, codex_totals, label = collect(cfg, window)
    title, body = build_message(claude_totals, codex_totals, label, cfg.budgets)

    if dry_run:
        print(f"[{title}]")
        print(body)
        print(
            f"\n(claude: {claude_totals.count} msgs, "
            f"codex: {codex_totals.count} turns)"
        )
        return 0

    status = send_ntfy(
        server=cfg.ntfy_server,
        topic=cfg.ntfy_topic,
        title=title,
        message=body,
        token=cfg.ntfy_token,
        priority=cfg.ntfy_priority,
        tags=["robot"],
    )
    print(f"Sent to {cfg.ntfy_server}/{cfg.ntfy_topic} (HTTP {status})")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="band_usage",
        description="Push Claude Code & Codex usage to a Samsung Galaxy Fit 3 via ntfy.",
    )
    parser.add_argument("--config", "-c", help="Path to config JSON file.")
    parser.add_argument("--window", "-w", help="Override window (e.g. 5h, today, 7d, all).")
    parser.add_argument("--topic", help="Override ntfy topic.")
    parser.add_argument("--server", help="Override ntfy server URL.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the notification instead of sending it.",
    )
    parser.add_argument(
        "--loop",
        type=int,
        metavar="SECONDS",
        help="Run forever, sending every SECONDS seconds.",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.topic:
        cfg.ntfy_topic = args.topic
    if args.server:
        cfg.ntfy_server = args.server
    window = args.window or cfg.window

    if args.loop:
        print(f"Looping every {args.loop}s. Ctrl-C to stop.")
        try:
            while True:
                try:
                    run_once(cfg, window, args.dry_run)
                except Exception as exc:  # keep the loop alive on transient errors
                    print(f"error: {exc}", file=sys.stderr)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            return 0

    try:
        return run_once(cfg, window, args.dry_run)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
