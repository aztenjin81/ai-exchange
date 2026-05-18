# Recent Paper Status

## When paper was last running

Paper trading was paused on **2026-05-17 14:50:02 MST** along with both paper scanner cron jobs (`kalshi-crypto-scanner` every 60s, `kalshi-paper-bot` every 30min). Before that, paper had been running continuously with the current codebase since the v2 upgrade.

## Code parity

Paper and prod share the same core analysis engine (`crypto_intel.py`). Both call the same `fetch_crypto_markets()`, `analyze_crypto_market()`, and `log_decision()` functions. The paper scanner (`03_scanner_paper.py`) is a thin 8-line wrapper that calls `scan_and_log()` which is a function inside `crypto_intel.py` — it's not a separate script. Prod has its own scanner (`02_scanner_prod.py`) that calls `production_scan()` which is also in `crypto_intel.py`.

Both use the same functions for:
- Probability modeling (`fair_yes_probability()`)
- Blend weights (`kalshi_blend_weight()`)
- Asymmetric sizing (`SIZE_MULTIPLIER_BY_SIDE`)
- Coin-aware contrarian filters (`CONTRARIAN_LIMITS`)
- `spot_strike_deadzone`
- Outcome harvesting (`harvest_outcomes()`)

The only differences are config-level:
- `MIN_EDGE_CENTS`: paper = 0, prod = 3
- `MIN_CONFIDENCE`: paper > 0.15, prod >= 0.15
- `MAX_PER_COIN`: paper = 3 positions, prod = $1 dollar cap
- `HALT_FLOOR`: paper = $4,000 budget, prod = $30
- Trade execution: paper calls `hold()` (synthetic), prod calls Kalshi API

## Market cache dependency

The market cache (`markets.json` at `~/.hermes/cache/`) was introduced to keep paper and prod on the same snapshot. Both call `fetch_crypto_markets()` which has a 15-second TTL cache. **Paper wrote the cache, prod consumed it.** But since paper was paused, prod's last test run (before being paused) was fetching its own snapshots independently.

When prod is paused, the cache file still exists — it just gets stale. The dashboard reads from this cache for the live market table. The cache age is displayed on the dashboard.

## `resolved_yes` back-fill

`harvest_outcomes()` queries `kalshi_decision_log` for unresolved markets, regardless of strategy. It updates ALL rows for a given `market_ticker` where `resolved_yes IS NULL`. This means:

- **Prod executed trades**: yes, back-filled via their decision_log entries
- **Paper executed trades**: yes, same function, same path
- **Hold decisions (no trade)**: yes, the harvesting resolves those too
- **Orphan trades (538/539)**: no — they have no decision_log entry, so `harvest_outcomes()` never fires for them specifically. They were closed by the trade-closing logic added to `harvest_outcomes()` at the end of the settlement check.

## Resume readiness

Paper can resume at any time. The code is identical to what was running before pause. The prod floor is at $30 (lowered from $50), but since paper doesn't use real money, floor doesn't affect it. Prod would need manual unpause and confirm floor is acceptable.
