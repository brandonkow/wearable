"""Configuration loading: defaults, JSON file, and environment overrides."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from .pricing import ModelPrice, per_million

DEFAULT_CONFIG = {
    "ntfy": {
        "server": "https://ntfy.sh",
        "topic": "",
        "token": None,
        "priority": "default",
    },
    "window": "5h",
    "claude": {"enabled": True, "logs_dir": "~/.claude/projects"},
    "codex": {"enabled": True, "logs_dir": "~/.codex/sessions", "default_model": "gpt-5-codex"},
    "budgets": {"claude_usd": None, "codex_usd": None},
    "pricing_overrides": {},
}


@dataclass
class Config:
    ntfy_server: str
    ntfy_topic: str
    ntfy_token: Optional[str]
    ntfy_priority: str
    window: str
    claude_enabled: bool
    claude_logs_dir: str
    codex_enabled: bool
    codex_logs_dir: str
    codex_default_model: str
    budgets: Dict[str, Optional[float]]
    pricing_overrides: Dict[str, ModelPrice] = field(default_factory=dict)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _build_pricing_overrides(raw: dict) -> Dict[str, ModelPrice]:
    out: Dict[str, ModelPrice] = {}
    for key, vals in (raw or {}).items():
        if not isinstance(vals, dict):
            continue
        out[key] = per_million(
            float(vals.get("input", 0)),
            float(vals.get("output", 0)),
            vals.get("cache_write"),
            vals.get("cache_read"),
        )
    return out


def load_config(path: Optional[str] = None) -> Config:
    data = dict(DEFAULT_CONFIG)
    if path and os.path.exists(os.path.expanduser(path)):
        with open(os.path.expanduser(path), "r", encoding="utf-8") as fh:
            data = _deep_merge(data, json.load(fh))

    # Environment overrides (handy for cron / secrets).
    ntfy = data["ntfy"]
    if os.environ.get("NTFY_SERVER"):
        ntfy["server"] = os.environ["NTFY_SERVER"]
    if os.environ.get("NTFY_TOPIC"):
        ntfy["topic"] = os.environ["NTFY_TOPIC"]
    if os.environ.get("NTFY_TOKEN"):
        ntfy["token"] = os.environ["NTFY_TOKEN"]

    return Config(
        ntfy_server=ntfy["server"],
        ntfy_topic=ntfy.get("topic", ""),
        ntfy_token=ntfy.get("token"),
        ntfy_priority=ntfy.get("priority", "default"),
        window=data.get("window", "5h"),
        claude_enabled=bool(data["claude"].get("enabled", True)),
        claude_logs_dir=data["claude"].get("logs_dir", "~/.claude/projects"),
        codex_enabled=bool(data["codex"].get("enabled", True)),
        codex_logs_dir=data["codex"].get("logs_dir", "~/.codex/sessions"),
        codex_default_model=data["codex"].get("default_model", "gpt-5-codex"),
        budgets=data.get("budgets", {}) or {},
        pricing_overrides=_build_pricing_overrides(data.get("pricing_overrides", {})),
    )
