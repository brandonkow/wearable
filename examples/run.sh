#!/usr/bin/env bash
# Compute usage and push a notification to the band. Point cron / a launchd
# job / a systemd timer at this script.
set -euo pipefail

# Resolve the repo root regardless of where this is invoked from.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Optionally keep secrets out of the JSON file:
# export NTFY_TOPIC="ai-usage-7f3k9"
# export NTFY_TOKEN="tk_..."

cd "$HERE"
python3 -m band_usage --config "$HERE/config.json" "$@"
