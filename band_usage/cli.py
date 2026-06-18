"""Command-line entry point.

Examples::

    python -m band_usage --config config.json --dry-run
    python -m band_usage --config config.json            # send once
    python -m band_usage --config config.json --loop 600 # send every 10 min
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import List, Optional

from .claude_usage import read_claude_usage
from .codex_usage import read_codex_usage
from .config import Config, load_config
from .format import build_card
from .models import ToolUsage
from .notify import send_ntfy


def collect(cfg: Config) -> List[ToolUsage]:
    tools: List[ToolUsage] = []
    if cfg.claude_enabled:
        tools.append(read_claude_usage(cfg.claude_usage_cache))
    if cfg.codex_enabled:
        tools.append(read_codex_usage(cfg.codex_sessions_dir))
    return tools


def run_once(cfg: Config, dry_run: bool) -> int:
    tools = collect(cfg)
    title, body = build_card(tools, bar_width=cfg.bar_width)

    if dry_run:
        print(f"[{title}]")
        print(body)
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
        description="Push Claude Code & Codex subscription limits to a Galaxy Fit 3 via ntfy.",
    )
    parser.add_argument("--config", "-c", help="Path to config JSON file.")
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

    if args.loop:
        print(f"Looping every {args.loop}s. Ctrl-C to stop.")
        try:
            while True:
                try:
                    run_once(cfg, args.dry_run)
                except Exception as exc:  # keep the loop alive on transient errors
                    print(f"error: {exc}", file=sys.stderr)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            return 0

    try:
        return run_once(cfg, args.dry_run)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
