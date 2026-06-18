# AI usage limits on a Samsung Galaxy Fit 3

Show how much of your **Claude Code** and **Codex** subscription limits you've
used — as a glanceable card on a Samsung Galaxy Fit 3 smart band. Percentages
and reset times, the same numbers `/usage` shows. No tokens, no dollars.

```
┌──────────────────────┐
│ AI limits            │
│ Claude .2h           │
│ 5h ██░░░░░░ 24%      │
│ wk ███░░░░░ 41%      │
│ Codex .46m           │
│ 5h █████░░░ 62%      │
│ wk ███░░░░░ 38%      │
└──────────────────────┘
```

`.2h` / `.46m` is when the soonest (5-hour) window resets. `5h` is the 5-hour
rolling window, `wk` the weekly cap.

## Important: why this works the way it does

The Galaxy Fit 3 does **not** run Wear OS or Tizen. It runs Samsung's
proprietary FreeRTOS firmware with **no public SDK**, so you cannot install a
custom app or even a custom watch face on it
([Samsung Developer Forum](https://forum.developer.samsung.com/t/samsung-galaxy-fit-3-custom-watchface-support/29728),
[XDA Forums](https://xdaforums.com/t/sideloading-apps-or-adding-custom-watchfaces.4659565/)).

What the band *can* do is **mirror notifications** from the paired phone. So
this project pushes a compact notification via [**ntfy**](https://ntfy.sh) that
mirrors to the band. There are **no Python dependencies** (standard library
only).

## Where the limit percentages come from

The two tools expose their subscription limits very differently:

- **Codex** writes the real plan limits straight into its session logs. Each
  `token_count` event carries a `rate_limits` block with `primary` (5-hour) and
  `secondary` (weekly) windows, each with `used_percent` + reset time. We read
  the freshest one. **No setup needed.**
  ([SessionWatcher](https://www.sessionwatcher.com/guides/how-to-check-codex-usage))

- **Claude Code** does **not** persist its limit percentages to disk — they're
  only handed to a [statusline script](https://code.claude.com/docs/en/statusline)
  at runtime (fields `rate_limits.five_hour` / `seven_day`, Pro/Max only, after
  the first API response in a session). So we ship a tiny statusline hook that
  captures those numbers into a cache file the moment Claude Code reports them.

That means **Claude's number is as fresh as your last active Claude Code
session** — the card shows a `(3h old)` marker when the data is stale, and a
"set up the statusline hook" hint until the cache exists.

## Setup

### 1. Get the code

```bash
git clone <this repo>
cd wearable
cp config.example.json config.json
```

### 2. Set up ntfy (free, no account)

1. Install the **ntfy** app on the phone paired with your Fit 3
   ([Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
2. Pick a hard-to-guess topic name (it's effectively a password), e.g.
   `ai-limits-7f3k9`. In the app, tap **+** and subscribe to it.
3. Put the same topic in `config.json` under `ntfy.topic`.

> Anyone who knows a public ntfy topic can read/post to it. Use a random name,
> or self-host ntfy / use [reserved topics + a token](https://docs.ntfy.sh/config/#access-control)
> and set `ntfy.token`.

### 3. Capture Claude Code's limits (statusline hook)

Add the bundled statusline script to `~/.claude/settings.json` (use the
**absolute** path to your clone):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /ABSOLUTE/PATH/TO/wearable/statusline/band_statusline.py"
  }
}
```

Now whenever Claude Code is running, your status line shows
`Opus 4.8 | 5h 24% · wk 41%` **and** the numbers are cached to
`~/.claude/usage-cache.json` for the band. (Already have a custom statusline?
Merge the `rate_limits`-capturing logic from `band_statusline.py` into it.)

> Codex needs no equivalent step — it logs its limits automatically.

### 4. Let notifications reach the band

In **Galaxy Wearable → Notifications**, enable notifications for the ntfy app
(and turn off "only while wearing" if you want them anytime).

### 5. Try it

```bash
# Print the card without sending (sanity check):
python3 -m band_usage --config config.json --dry-run

# Send it for real:
python3 -m band_usage --config config.json
```

If Claude shows "set up the statusline hook", run a Claude Code session first
so the cache gets written. If Codex shows "no limit data in sessions", run a
Codex turn so it logs a `rate_limits` event.

## Keep it updated automatically

Run it as a loop:

```bash
python3 -m band_usage --config config.json --loop 600   # every 10 min
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
| `bar_width` | Width of the progress bar in characters (default 8). |
| `claude.usage_cache` | Cache file written by the statusline hook. Default `~/.claude/usage-cache.json`. Set `enabled: false` to skip Claude. |
| `codex.sessions_dir` | Default `~/.codex/sessions`. Set `enabled: false` to skip Codex. |

`NTFY_SERVER`, `NTFY_TOPIC`, and `NTFY_TOKEN` environment variables override the
file — handy for keeping secrets out of `config.json` in cron jobs. The
statusline hook honors `BAND_USAGE_CLAUDE_CACHE` to relocate the cache.

## CLI reference

```
python3 -m band_usage [options]
  -c, --config PATH    config JSON file
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
  claude_usage.py  read ~/.claude/usage-cache.json (from the statusline hook)
  codex_usage.py   read rate_limits from ~/.codex/sessions/**/*.jsonl
  models.py        LimitWindow / ToolUsage + window parsing
  format.py        compact band-friendly card + progress bars
  notify.py        ntfy push
statusline/
  band_statusline.py  Claude Code statusline hook that caches limit %
examples/             run.sh + crontab sample
tests/                unit tests
```

## Limitations & notes

- **Claude freshness:** the percentage is only as current as your last active
  Claude Code session (see above). Anthropic has no official API for live
  subscription quotas yet ([feature request](https://github.com/anthropics/claude-code/issues/21943)).
- **Codex schema drift:** the `rate_limits` location is found with a tolerant
  search, but field names have changed across Codex versions. If Codex shows
  no data, run `--dry-run` and open an issue with a sample log line.
- Everything is read **locally** — no scraping, no credentials handled.
```
