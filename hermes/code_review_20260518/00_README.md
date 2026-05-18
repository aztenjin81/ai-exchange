# Code Review 2026-05-18

## What's here

| File | Contents |
|------|----------|
| `01_crypto_intel.py` | Core analysis engine — probability model, blend weights, sizing, filters, outcome harvesting, paper scanner (`scan_and_log()`) |
| `02_scanner_prod.py` | Production scanner — Kalshi API calls, order placement, settlement, auto-reconciliation, prod-specific config |
| `03_scanner_paper.py` | Paper scanner wrapper — 8-line script calling `scan_and_log()` from `01_crypto_intel.py` |
| `04_schemas.md` | `\d+` output for `kalshi_trades`, `kalshi_decision_log`, `kalshi_portfolio` |
| `05_orphan_trades.md` | Trades 538/539 with full context: trade rows, surrounding window, decision log, root cause analysis |
| `06_eth_no_trades.md` | ETH NO vs SOL losing trades: full query output with parameter comparison table |
| `07_recent_paper_status.md` | Status note: when paper was paused, code parity, cache dependency, resume readiness |

## Caveats

### `01_crypto_intel.py` is the single source

Paper (`scan_and_log()`) and prod (`production_scan()`) both live in this file as functions. The paper scanner (`03_scanner_paper.py`) is just `import; scan_and_log()` — literally 8 lines. Prod's scanner (`02_scanner_prod.py`) is a separate script but imports core functions from this module.

### `02_scanner_prod.py` contains the production config

MIN_EDGE_CENTS=3, HALT_FLOOR=30.00, MAX_PER_COIN=1.00, etc. Paper defaults are hardcoded inside `crypto_intel.py` in `scan_and_log()`. Both use the same `SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}`.

### No credentials in any file

All secrets (`HERMES_PG_URI`, Kalshi API keys) come from `~/.hermes/env` sourced at runtime. The `kalshi_client.py` (not included — it's the thin API wrapper) reads env vars. No API keys, DB passwords, or connection strings are hardcoded anywhere in these files.

### Settlement code

Is split between `02_scanner_prod.py` (`settle_expired()`) and `01_crypto_intel.py` (`harvest_outcomes()`). `settle_expired()` checks Kalshi order fill status for open positions. `harvest_outcomes()` labels decision_log rows with market results. Both close trades.

### Auto-reconciliation (the orphan bug)

At the end of `production_scan()` in `02_scanner_prod.py`, a function fetches the last 10 Kalshi orders and inserts any missing ones. This is the path that created trades 538/539 without `series_ticker` or decision context. See `05_orphan_trades.md` for the full analysis.

## What's NOT here

- `kalshi_client.py` — the HTTP API wrapper. Not included because it only handles auth + HTTP calls, no trading logic.
- `hermes_db.py` — the DB helper. Just `psycopg2.connect(uri)` wrapper, no logic.
- `dashboard.py` — the HTML dashboard. Not relevant to code review.
- `path_tracker.py` — intra-window path metrics. Not relevant to code review.
- `kalshi-performance-report` — the JSON report generator. Used for the sizing checkpoint export.
- Any historical data or database dumps beyond the targeted queries in `05_orphan_trades.md` and `06_eth_no_trades.md`.

## Start here for the orphan bug

Read in this order:
1. `05_orphan_trades.md` — see the NULL fields and the reconciliation path
2. `02_scanner_prod.py` — search for `reconcile` or the end-of-cycle order check in `production_scan()` (around line 550+)
3. `04_schemas.md` — confirm `series_ticker` is nullable (it is)

## Start here for the ETH NO diagnostic

1. `06_eth_no_trades.md` — the comparison table tells the story
2. `01_crypto_intel.py` — the `fair_yes_probability()` function (around line 200) and `analyze_crypto_market()` (around line 800) to understand what parameters drive the edge calculation
