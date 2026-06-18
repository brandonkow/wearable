# AI usage on a Samsung Galaxy Fit 3

Show your **Claude Code** and **Codex CLI** usage as a glanceable card on a
Samsung Galaxy Fit 3 smart band.

```
┌──────────────────────┐
│ AI usage - last 5h   │
│ Claude $1.47/$20  7% │
│ █░░░░░░░░░            │
│ Codex  $0.08/$10  1% │
│ ░░░░░░░░░░            │
│ Total  $1.55         │
└──────────────────────┘
```

## Important: why this works the way it does

The Galaxy Fit 3 does **not** run Wear OS or Tizen. It runs Samsung's
proprietary FreeRTOS firmware with **no public SDK**, so you cannot install a
custom app or even a custom watch face on it
([Samsung Developer Forum](https://forum.developer.samsung.com/t/samsung-galaxy-fit-3-custom-watchface-support/29728),
[XDA Forums](https://xdaforums.com/t/sideloading-apps-or-adding-custom-watchfaces.4659565/)).

What the band *can* do is **mirror notifications** from the paired phone. So
this project doesn't build a native band app (impossible) — instead it:

1. Reads your local Claude Code logs (`~/.claude/projects`) and Codex CLI logs
   (`~/.codex/sessions`) on your computer.
2. Adds up tokens used and estimates cost over a time window (default: a
   rolling 5 hours, matching Claude's rate-limit reset cadence).
3. Pushes a compact notification via [**ntfy**](https://ntfy.sh) to your phone,
   which mirrors it to the band.

Everything is read **locally** — no scraping, no account credentials. There are
**no Python dependencies** (standard library only).

## Setup

### 1. Get the code

```bash
git clone <this repo>
cd wearable
cp config.example.json config.json
```

### 2. Set up ntfy (free, no account)

1. Install the **ntfy** app on the phone that's paired with your Fit 3
   ([Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
2. Pick a hard-to-guess topic name (it's effectively your password), e.g.
   `ai-usage-7f3k9`. In the app, tap **+** and subscribe to that topic.
3. Put the same topic in `config.json` under `ntfy.topic`.

> Anyone who knows a public ntfy topic can read/post to it. Use a random name,
> or self-host ntfy / use [reserved topics + a token](https://docs.ntfy.sh/config/#access-control)
> and set `ntfy.token`.

### 3. Let notifications reach the band

In **Galaxy Wearable → Notifications**, enable notifications for the ntfy app
(and turn off "only while wearing" if you want them anytime). The next pushed
card will appear on the band.

### 4. Try it

```bash
# Print the notification without sending (sanity check):
python3 -m band_usage --config config.json --dry-run

# Send it for real:
python3 -m band_usage --config config.json
```

If you see realistic numbers in `--dry-run`, you're good. If totals are 0,
check that `claude.logs_dir` / `codex.logs_dir` point at your real log folders.

## Keep it updated automatically

Have it refresh on a schedule. Either run it as a long-lived loop:

```bash
python3 -m band_usage --config config.json --loop 900   # every 15 min
```

…or use cron (see [`examples/crontab.example`](examples/crontab.example) and
[`examples/run.sh`](examples/run.sh)):

```bash
crontab examples/crontab.example   # edit the path first
```

## Configuration

`config.json` (see [`config.example.json`](config.example.json)):

| Key | Meaning |
| --- | --- |
| `ntfy.server` | ntfy server URL (default `https://ntfy.sh`). |
| `ntfy.topic` | Your private topic name. **Required.** |
| `ntfy.token` | Optional bearer token for protected topics. |
| `ntfy.priority` | `min`/`low`/`default`/`high`/`urgent`. `low` avoids buzzing. |
| `window` | `5h`, `today`, `7d`/`week`, `<N>h`, `<N>d`, or `all`. |
| `claude.logs_dir` | Default `~/.claude/projects`. Set `enabled: false` to skip. |
| `codex.logs_dir` | Default `~/.codex/sessions`. Set `enabled: false` to skip. |
| `budgets.claude_usd` / `budgets.codex_usd` | Optional. When set, the card shows a **progress bar** toward that spend (your "usage limit"). When unset, it shows raw token totals instead. |
| `pricing_overrides` | Per-model price overrides (per **million** tokens). |

`NTFY_SERVER`, `NTFY_TOPIC`, and `NTFY_TOKEN` environment variables override the
file — handy for keeping secrets out of `config.json` in cron jobs.

### About the "limit"

The local logs record what you *used*, not your plan's hard rate limit (that
isn't written to disk). So `band_usage` treats the optional `budgets` values as
your limit and draws the bar against them. Set them to whatever ceiling you
care about (e.g. your daily spend target).

### About cost estimates

Costs are computed from a built-in price table in
[`band_usage/pricing.py`](band_usage/pricing.py). LLM prices change often —
adjust that table or use `pricing_overrides` if you want exact figures.

## CLI reference

```
python3 -m band_usage [options]
  -c, --config PATH    config JSON file
  -w, --window SPEC    override window (5h, today, 7d, all, ...)
      --topic NAME     override ntfy topic
      --server URL     override ntfy server
      --dry-run        print instead of send
      --loop SECONDS   run forever, sending on an interval
```

## Development

```bash
python3 -m unittest discover -s tests -v
```

## Project layout

```
band_usage/
  cli.py           argparse entry point + orchestration
  config.py        defaults + JSON file + env overrides
  claude_usage.py  parse ~/.claude/projects/**/*.jsonl
  codex_usage.py   parse ~/.codex/sessions/**/*.jsonl
  aggregate.py     time-window resolution
  models.py        UsageRecord / Totals
  pricing.py       per-model price table + cost math
  format.py        compact band-friendly message + progress bar
  notify.py        ntfy push
examples/          run.sh + crontab sample
tests/             unit tests
```
