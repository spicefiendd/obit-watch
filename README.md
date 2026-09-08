# obit-watch

Check free public obituary / funeral / death-notice sources for Northern Indiana.
Python 3 **stdlib only** — no paid APIs, no Facebook.

## HOWTO (run)

```bash
cd /workspace/obit-watch
python3 -m obit_watch \
  --name "Jane Marie Example" \
  --name-variant "Jane Example" \
  --town Plymouth \
  --town Culver \
  --county Marshall \
  --state IN
```

Exit codes: `0` any hit · `1` clean miss · `2` every source error/blocked (or none runnable).

## Options

| Flag | Meaning |
|------|---------|
| `--name` | Primary name (repeatable) |
| `--name-variant` | Alternate form (repeatable) |
| `--town` | Town context (repeatable) |
| `--county` | County context (repeatable) |
| `--state` | State abbrev (default `IN`) |
| `--timeout` | HTTP timeout seconds (default `15`) |
| `--extra-url` | Extra page to scan (repeatable) |
| `--format` | `json` (default) or `md` |

## Default sources

1. Google News RSS (names + obituary/funeral + towns/counties + state)
2. Echovita (Plymouth / Culver IN listing + search)
3. Legacy.com public search
4. Find A Grave public search
5. InkFree / Marshall County news obituaries pages
6. Funeral homes: Johnson-Danielson (Plymouth), Palmer, Odom (Marshall Co) — `403` → `blocked`
7. Each `--extra-url` as a generic HTML name scan

A **hit** means the page/RSS contains a plausible match for any name variant (prefer near words like obituary, funeral, died, passing, services). Excerpts ≤ 200 chars.

## Output (JSON)

```json
{
  "query": {"names": [...], "towns": [...], "counties": [...], "state": "IN"},
  "checked_at": "ISO-UTC",
  "sources": [
    {"id": "...", "name": "...", "url": "...", "status": "hit|miss|error|blocked",
     "http_code": 200, "excerpt": "...or null", "checked_at": "ISO-UTC"}
  ],
  "summary": {"hits": 0, "misses": 0, "errors": 0, "blocked": 0}
}
```

## Layout

```
obit-watch/
  README.md
  obit_watch/
    __init__.py
    __main__.py
    cli.py
    httputil.py
    match.py
    sources.py
```

## Requirements

- Python 3.8+
- Network access for live fetches (offline otherwise except no results)
- No third-party packages
