# Kalshi Crypto 15-Min Bot — Full System Architecture

## Overview

This bot trades Kalshi's crypto 15-minute binary options ("will the price of [coin] be above the strike price at expiry?"). It's been built iteratively over several sessions, progressing through v0 (spread arb), v1 (basic mid-based edge), and v2 (model-driven fair probability + filters).

Runs on a headless Ubuntu server in a homelab environment. Postgres database, cron-driven scanners, Python scripts, and a web dashboard.

---

## Directory Layout

All scripts live at `~/.hermes/scripts/` (git repo: `github.com/aztenjin81/homelab-scripts`).

```
~/.hermes/
├── scripts/
│   ├── crypto_intel.py           # Core intelligence (~2,015 lines)
│   ├── kalshi-crypto-prod        # Production scanner — places real orders (661 lines)
│   ├── kalshi-crypto-scan        # Paper scanner — wrapper, calls scan_and_log() (8 lines)
│   ├── kalshi_client.py          # Kalshi REST API client (244 lines)
│   ├── hermes_db.py              # PostgreSQL helper (91 lines)
│   ├── dashboard.py              # Web UI server (851 lines, port 8890)
│   ├── kalshi_review.py          # After-action review script
│   ├── calibration-sanity-check  # Calibration validation script
│   ├── kalshi-scan.sh            # Paper bot shell wrapper (older, less frequent)
│   └── ... (other scripts)
├── secrets/
│   └── kalshi-production.key     # Prod API key (combined UUID + PEM format)
├── .env                          # Prod credentials (sourced by cron)
├── cron/
│   ├── jobs.json                 # Cron job definitions (Hermes-managed)
│   └── postmortem_enabled        # Toggle for closeout postmortem
└── cache/
    └── kalshi_live.json          # Dashboard cache (updated every scan)
```

Vault: `~/hermes-vault/` — shared via Obsidian Sync + git push to `github.com/aztenjin81/ai-exchange`.

---

## File-by-File Breakdown

### 1. `crypto_intel.py` — Core Intelligence Module (~2,015 lines)

The brain. Imported by both the paper and production scanners. Contains:

**Market data fetching:**
- `fetch_crypto_markets(client)` — hits Kalshi API for all 7 series (BTC, ETH, SOL, XRP, DOGE, BNB, HYPE), returns orderbook data (bid/ask/open interest/close_time)
- `fetch_recent_closes_kraken()` / `fetch_recent_closes_hyperliquid()` — gets 1-min OHLC for vol calculation
- `fetch_spot_price(coin)` — live Coinbase spot price

**Volatility estimation:**
- `realized_vol_from_closes()` — annualized RV from 1-min candle closes
- `conservative_vol_blend()` — takes `max(vol_5m, vol_15m*0.90, vol_60m*0.75)` — intentionally biased high
- `get_model_volatility(coin)` — fetches + caches vol (90s TTL), falls back to hardcoded `FALLBACK_VOL` dict if live data unavailable

**Probability model:**
- `fair_yes_probability(spot, strike, annualized_vol, minutes_left)` — log-normal: `Φ(ln(spot/strike) / (σ√t))`
- Clamped to [0.01, 0.99]
- Blended with Kalshi mid via `kalshi_blend_weight(ttl_min)` — weights shift from 80/20 (model/market) at 15min to 25/75 at expiry

**Trade analysis & filtering (in `analyze_crypto_market()`):**
1. Check TTL > 1.5 min
2. Check ask prices exist
3. `spread_too_wide()` — YES spread > 8% or NO spread > 8%
4. Compute model fair_yes (log-normal)
5. Blend with Kalshi mid
6. `block_large_model_market_disagreement()` — if model differs from market by >20 points, block
7. Compute yes_edge and no_edge: `fair_yes - yes_ask` and `fair_no - no_ask`
8. Pick max edge side
9. Check per-coin edge minimum (`MIN_EDGE_BY_COIN`) — **this is the tightest filter for most coins**
10. Check `max_entry_for_ttl()` — cap on entry price
11. `edge_ratio_too_small` — edge must be at least 15% of entry price
12. `spot_strike_deadzone` — block if spot too close to strike (<0.02%)
13. `block_contrarian_entry_if_needed()` — prevents betting against strong market consensus
14. `require_direction_agreement()` — Kalshi orderbook, spot price, and model must agree
15. Compute confidence score (0.10-0.85) from edge size, OI, spread, TTL, volatility source

**Per-coin edge minimums (in crypto_intel.py, applies to BOTH paper and prod):**
```python
MIN_EDGE_BY_COIN = {
    'BTC':  0.10,   # 10¢ — tightest, BTC has been the worst performer
    'BNB':  0.99,   # disabled — soft-disabled via absurdly high threshold
    'HYPE': 0.08,   # 8¢
    'ETH':  0.04,   # 4¢
    'SOL':  0.04,   # 4¢
    'XRP':  0.04,   # 4¢
    'DOGE': 0.04,   # 4¢
}
```
These are **dollar values** (0.10 = 10¢). They're checked inside `analyze_crypto_market()` before the caller's global threshold. This means even if the prod script's `MIN_EDGE_CENTS=6`, BTC still requires 10¢ edge from the analyzer.

**Sizing (shared by paper + prod):**
- `SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}` — deployed 2026-05-17 based on calibration showing NO-side predictions are far more reliable (94% vs 53%)
- `_crypto_intel_qty(signal)` — scales by confidence and side multiplier

**Paper trade execution (`_execute_trade()`):**
- Inserts into `kalshi_trades` with `strategy_name='crypto_intel'`
- Deducts cost from shared portfolio balance in DB
- No Kalshi API calls — purely simulated paper trading
- This is how paper trades flow into `kalshi_trades` (see Paper vs Prod section below)

**Scan & log (`scan_and_log()` — called by paper scanner):**
- Runs `_check_exits()` to settle expired paper positions
- Runs `harvest_outcomes()` to label resolved markets
- Analyzes all 7 markets, filters through the full analyzer stack
- Places paper trades via `_execute_trade()`
- Writes every decision to `kalshi_decision_log`
- Writes `kalshi_live.json` cache
- Checks budget ($4k max, 3 concurrent per coin)
- Logs heartbeat `strategy_name='crypto_intel'`

**Cache:**
- `write_cache()` — writes `kalshi_live.json` for dashboard consumption
- `log_decision()` — writes to `kalshi_decision_log` table

### 2. `kalshi-crypto-prod` — Production Scanner (661 lines)

Cron runner for real-money trading. Called every minute by cron (no_agent mode). **Currently PAUSED** (see Current State below).

**Flow:**
1. Write heartbeat (`kalshi_heartbeat`, strategy=`crypto_intel_prod`) — dead man's switch
2. Authenticate (`create_prod_client()` → RSA-signed requests to Kalshi production API)
3. Fetch and sync balance from Kalshi API (real money)
4. Check halt floor ($30 minimum)
5. Get per-coin exposure from `kalshi_trades` (open positions)
6. Settle any expired positions
7. Fetch and analyze all 7 markets (calls `crypto_intel.analyze_crypto_market()`)
8. Apply ADDITIONAL filter: `MIN_EDGE_CENTS = 6` (prod's own global threshold, on top of analyzer's per-coin minimums)
9. Apply ADDITIONAL filter: `MIN_CONFIDENCE = 0.30`
10. Score candidates by `edge * confidence`
11. Pick top 3, apply per-coin sizing with side multiplier from crypto_intel
12. Check DRY_RUN flag: if set, log only (no real orders)
13. Place real limit orders via Kalshi production API
14. Log trades and decisions to DB with `strategy_name='crypto_intel_prod'`
15. Reconcile open orders against DB (catch orphan fills)

**Config:**
```python
MAX_PER_COIN_DOLLARS = 1.00    # Hard cap: max $1 total exposure per coin
HALT_FLOOR = 30.00             # Halt trading when balance drops below this
MIN_EDGE_CENTS = 6             # Global min edge (loosened from 8 on 2026-05-18)
MIN_EDGE_RATIO = 0.15          # Edge / executable ask must clear this
MIN_CONFIDENCE = 0.30          # Min model confidence (reverted from 0.15 on 2026-05-18)
HARD_MAX_ENTRY_PRICE = 0.75    # Emergency cap; TTL-specific cap lives in analyzer
DRY_RUN = env("KALSHI_DRY_RUN", "0") == "1"  # Analyze/log only; no orders
```

### 3. `kalshi-crypto-scan` — Paper Scanner (8 lines)

```python
#!/usr/bin/env python3
"""Crypto 15-min scanner — called by cron every 60s."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.hermes' / 'scripts'))
from crypto_intel import scan_and_log
result = scan_and_log()
print(f"{result['entries']} entries, {result['markets']} markets")
```

Thin wrapper that calls `crypto_intel.scan_and_log()`. Runs every minute via cron, logs decisions to `kalshi_decision_log` with `strategy_name='crypto_intel'`. Places simulated paper trades into `kalshi_trades` (deducts from shared portfolio balance in DB — no real Kalshi API calls).

### 4. `kalshi_client.py` — API Client (244 lines)

Uniform interface for both demo and production Kalshi APIs.

**Key classes:**
- `KalshiAuth` — RSA key signing (PSS padding, SHA256). Auto-detects combined key format (UUID on line 1 + PEM body)
- `KalshiClient` — HTTP client with request signing, retry (1 attempt default), 10s timeout

**Key methods:**
- `get_open_crypto_markets()` — fetches all 7 series from `/markets?series_ticker=...&status=open`
- `get_balance()` — `/portfolio/balance`
- `place_order(ticker, side, count, price)` — limit orders
- `cancel_order(order_id)`, `get_orders()`, `get_fills()` — order management
- `get_positions()` — `/portfolio/positions`

**API format:** Kalshi returns balances in cents (integer), prices in dollars (decimal). `yes_bid_dollars`, `yes_ask_dollars` are the orderbook top-of-book.

**Auth separation:**
- Paper (demo): Uses `KalshiClient()` constructor — reads env vars for demo credentials
- Prod (live): Uses `create_prod_client()` — reads production RSA key + UUID from `~/.hermes/secrets/kalshi-production.key`, signs every request

### 5. `hermes_db.py` — PostgreSQL Helper (91 lines)

Database connection helper for all scripts.

Provides: `get_conn()`, `query(sql)` (returns list of tuples), `query_one(sql)`, `execute(sql)`.

Connects to `HERMES_PG_URI` from environment or sourced from `~/.hermes/env`.

**Important pitfall:** `execute()` auto-commits and returns rowcount. `query()` does NOT commit. This means calling `query()` followed by `get_conn().close()` inside the same function will roll back uncommitted writes (caused 3 consecutive test failures before discovery).

### 6. `dashboard.py` — Web Dashboard (~851 lines)

Self-contained HTTP server on port 8890. Renders a dark-themed HTML dashboard showing:
- Portfolio cards (LIVE/PAPER equity, P&L, win rate, open positions)
- Performance summary (Brier score, calibration table, per-coin breakdown)
- Operational health (heartbeat age, decisions/hour, filter distribution)
- Live crypto market leans (bid/ask, edge, confidence, open interest by coin)
- Open positions, decision log, closed trades

Refreshes every 30 seconds via `<meta refresh>`.

---

## Paper Trading vs Production: How They Operate

This is the most important architectural distinction — the two scanners share the same intelligence layer but are completely separate at the execution level.

### Shared Layer (crypto_intel.py)

Both scanners import `crypto_intel` and call the same functions:
- `analyze_crypto_market()` — same model, same filters, same MIN_EDGE_BY_COIN
- `log_decision()` — write to the same `kalshi_decision_log` table
- `write_cache()` — update the same `kalshi_live.json` for the dashboard
- `SIZE_MULTIPLIER_BY_SIDE` — same side-biased sizing

Every decision from both scanners goes to `kalshi_decision_log` differentiated only by `strategy_name`:
- `'crypto_intel'` = paper scanner decisions
- `'crypto_intel_prod'` = prod scanner decisions

### Paper Scanner (kalshi-crypto-scan → scan_and_log())

| Aspect | Detail |
|---|---|
| **Cron** | `kalshi-crypto-scanner` — every 60s, **active** |
| **Auth** | Demo KalshiClient (env var credentials) |
| **Execution** | DB-only simulated trades — no Kalshi API calls |
| **Trade table** | `kalshi_trades` with `strategy_name='crypto_intel'` |
| **Portfolio** | Shared DB portfolio (paper balance, separate from real money) |
| **Budget** | $4k max capital, 3 concurrent positions per coin |
| **Sizing** | `_crypto_intel_qty()` — confidence × side multiplier |
| **Settlement** | `_check_exits()` checks DB timestamps, `harvest_outcomes()` labels resolution |
| **Heartbeat** | `kalshi_heartbeat` strategy_name='crypto_intel' |
| **Trade flow** | 1. analyze → 2. size → 3. deduct from DB portfolio → 4. insert kalshi_trades → 5. log decision |

### Production Scanner (kalshi-crypto-prod)

| Aspect | Detail |
|---|---|
| **Cron** | `kalshi-crypto-prod` — every 60s, **currently PAUSED** |
| **Auth** | Prod KalshiClient — RSA-signed requests with UUID + PEM key from `~/.hermes/secrets/kalshi-production.key` |
| **Execution** | Real limit orders on Kalshi production exchange |
| **Trade table** | `kalshi_trades` with `strategy_name='crypto_intel_prod'` |
| **Portfolio** | Real Kalshi API balance — deducts real money |
| **Budget** | $1 per coin max, $30 halt floor |
| **Sizing** | `(MAX_PER_COIN_DOLLARS - current_exposure) × side_multiplier` |
| **Additional filters** | `MIN_EDGE_CENTS=6`, `MIN_CONFIDENCE=0.30` (on top of analyzer's per-coin mins) |
| **Settlement** | Fetches Kalshi API positions, reconciles filled/cancelled orders |
| **Heartbeat** | `kalshi_heartbeat` strategy_name='crypto_intel_prod' |
| **Trade flow** | 1. analyze → 2. check halt floor → 3. check exposure → 4. apply extra filters → 5. pick top 3 → 6. DRY_RUN check → 7. place limit order on Kalshi → 8. log decision + trade |
| **DRY_RUN** | Env toggle: logs decisions as `positive_ev` without placing real orders |

### Key Architectural Differences

1. **Dual filter stack**: The analyzer (`crypto_intel.py`) has its own per-coin minimums (`MIN_EDGE_BY_COIN`). The prod script adds `MIN_EDGE_CENTS` and `MIN_CONFIDENCE` on top. The paper scanner does NOT apply these extra filters — it trusts the analyzer's output directly. This means prod can reject a trade that paper would take.

2. **Auth isolation**: Paper never touches real money. Even if `crypto_intel.py` had a bug, it can only affect simulated capital in the DB. Prod has a separate auth path with its own key file and RSA signing.

3. **Execution path**: Paper writes trades to the DB and deducts from the DB portfolio. Prod negotiates with the Kalshi API, handles order fill/cancel reconciliation, and writes to the DB as a record of real activity.

4. **Independence**: Each scanner has its own heartbeat, its own cron schedule, its own entry in `kalshi_trades`. One can be paused while the other runs. They do not share state at runtime beyond reading the same config and writing to the same tables.

---

## Database Schema

### `kalshi_trades` — All trades (open + closed)

| Column | Type | Role |
|---|---|---|
| `id` | SERIAL PK | Unique trade ID |
| `portfolio_id` | int | Portfolio reference |
| `market_ticker` | text | Kalshi ticker (e.g. "KXBTCM1Y...") |
| `event_ticker` | text | Event grouping |
| `series_ticker` | text | Series (KXBTC15M, KXETH15M...) |
| `market_title` | text | Human-readable title |
| `side` | text | "yes" or "no" |
| `entry_price` | numeric | Price paid per contract ($) |
| `exit_price` | numeric | Price received at close ($) |
| `quantity` | int | Number of contracts |
| `entry_time` | timestamptz | When trade opened |
| `exit_time` | timestamptz | When trade closed |
| `pnl` | numeric | Gross P&L |
| `net_pnl` | numeric | Net P&L (after fees) |
| `strategy_name` | text | "crypto_intel" (paper), "crypto_intel_prod" (live) |
| `status` | text | "open", "closed", "pending_settlement" |
| `exit_reason` | text | Why the trade was exited |
| `confidence` | numeric | Model confidence at entry (0-1) |
| `edge_cents` | numeric | Edge in cents at entry |
| `predicted_fair_value` | numeric | Blended fair_yes at entry |
| `reasoning_json` | jsonb | Full reasoning chain |
| `kalshi_order_id` | text | Kalshi order reference (prod only; null for paper) |
| `entry_fee`, `exit_fee` | numeric | Fees paid |
| `spread_paid` | numeric | Spread cost |
| `fill_price` | numeric | Actual fill price |
| `data_sources` | jsonb | What data fed the decision |

### `kalshi_decision_log` — Every scan decision (tracking + calibration)

| Column | Type | Role |
|---|---|---|
| `id` | SERIAL PK | Unique decision ID |
| `scan_time` | timestamptz | When the scan ran |
| `strategy_name` | text | Which strategy made this decision |
| `market_ticker`, `event_ticker`, `series_ticker` | text | Market identifiers |
| `coin_name` | text | BTC, ETH, SOL... |
| `action` | text | Reason for decision (edge_too_small, spread_too_wide, positive_ev...) |
| `side` | text | "yes", "no", or "hold" |
| `entry_price` | numeric | Price that would have been paid |
| `edge_cents` | numeric | Edge in cents (decimal — 0.1 = 0.1¢, 6.0 = 6¢) |
| `confidence` | numeric | Model confidence |
| `model_fair_yes` | numeric | Raw log-normal probability BEFORE blending |
| `fair_yes` | numeric | Blended fair_yes (after Kalshi mid blend) |
| `fair_no` | numeric | 1.0 - fair_yes |
| `side_fair_value` | numeric | Fair value of the chosen side |
| `edge_ratio` | numeric | Edge / entry_price |
| `volatility` | numeric | Annualized vol used |
| `spot_price` | numeric | Coinbase spot at scan time |
| `strike_price` | numeric | Kalshi strike |
| `ttl_minutes` | numeric | Time to expiry |
| `spread` | numeric | Orderbook spread |
| `open_interest` | numeric | Kalshi OI |
| `resolved_yes` | boolean | True = YES won, False = NO won (filled after market close) |
| `was_executed` | boolean | True = trade was placed |
| `trade_id` | int | FK to kalshi_trades if executed |
| `reasoning` | text | Full human-readable analysis chain |
| `data_sources` | jsonb | Input provenance |

### `kalshi_portfolio` — Balance tracking

| Column | Type | Role |
|---|---|---|
| `id` | SERIAL PK | 1 = shared portfolio across strategies |
| `starting_balance` | numeric | Initial deposit |
| `current_balance` | numeric | Current cash balance |
| `total_realized_pnl` | numeric | Running P&L total |
| `win_count`, `loss_count` | int | Trade counters |
| `active` | boolean | Portfolio enabled |

Note: Prod uses Kalshi API balance (real money) and DB portfolio for paper. They share the same `kalshi_portfolio` row via `id=1`, but prod syncs its balance from Kalshi API directly (line 326-335 of kalshi-crypto-prod) and writes the API balance value, while paper deducts from the DB-only balance.

### `kalshi_heartbeat` — Dead man's switch

| Column | Type | Role |
|---|---|---|
| `strategy_name` | text PK | "crypto_intel_prod", "crypto_intel" |
| `last_seen` | timestamptz | Last successful scan |
| `status` | text | "ok" or error state |

### `kalshi_strategy_params` — Versioned config

| Column | Type | Role |
|---|---|---|
| `strategy_name` | text | Strategy identifier |
| `version` | int | Config version |
| `params` | jsonb | Full config blob |
| `notes` | text | What changed |
| `created_at` | timestamptz | When deployed |

### Key SQL patterns

```sql
-- Per-coin exposure for open trades
SELECT series_ticker, SUM(entry_price * quantity)
FROM kalshi_trades
WHERE strategy_name='crypto_intel_prod' AND status='open'
GROUP BY series_ticker;

-- Calibration: model prediction vs actual outcome
SELECT width_bucket(fair_yes, 0, 1, 10) AS bucket,
       COUNT(*) AS n,
       AVG(CASE WHEN resolved_yes THEN 1 ELSE 0 END) AS actual_win_rate,
       AVG(fair_yes) AS avg_predicted
FROM kalshi_decision_log
WHERE was_executed = TRUE AND resolved_yes IS NOT NULL
GROUP BY bucket ORDER BY bucket;

-- Brier score
SELECT AVG(POWER(fair_yes - CASE WHEN resolved_yes THEN 1 ELSE 0 END, 2))
FROM kalshi_decision_log
WHERE was_executed = TRUE AND resolved_yes IS NOT NULL;

-- Heartbeat health check
SELECT strategy_name, last_seen,
       EXTRACT(EPOCH FROM (NOW() - last_seen)) AS seconds_since_heartbeat
FROM kalshi_heartbeat;

-- Filter distribution (diagnose why no trades)
SELECT action, strategy_name, COUNT(*) AS n
FROM kalshi_decision_log
WHERE scan_time > NOW() - INTERVAL '1 day'
GROUP BY action, strategy_name
ORDER BY strategy_name, n DESC;
```

---

## Analysis Pipeline (per market, per scan)

```
Kalshi API ──── GET /markets?series_ticker=X&status=open
                   │
                   ▼
            yes_bid, yes_ask, no_bid, no_ask
            strike, open_interest, close_time
                   │
                   ▼
Coinbase API ── spot price ($)
                   │
                   ▼
Kraken API ──── 1-min OHLC closes → realized vol (5m/15m/60m)
                   │
                   ▼
            fair_yes_probability(spot, strike, vol, ttl)
                   │
                   ▼
            blended = model * (1-w) + kalshi_mid * w
                w = kalshi_blend_weight(ttl)
                   │
                   ▼
            yes_edge = fair_yes - yes_ask
            no_edge  = fair_no - no_ask
            edge = max(yes_edge, no_edge)
                   │
                   ▼
         [Filter stack: TTL, spread, disagreement,
          per-coin edge min (MIN_EDGE_BY_COIN),
          entry_price, edge_ratio,
          deadzone, contrarian, direction_agreement]
                   │
                   ▼
         side, entry_price, confidence, reasoning
                   │
                   ▼
         log_decision() ──→ kalshi_decision_log
         write_cache()  ──→ kalshi_live.json → dashboard.py
```

---

## Cron Jobs

| Name | Schedule | Script | Type | Status | Purpose |
|---|---|---|---|---|---|
| `kalshi-crypto-prod` | every 1 min | `kalshi-crypto-prod` | no_agent | **PAUSED** (since May 17) | Production scanner — places real orders on Kalshi |
| `kalshi-crypto-scanner` | every 1 min | `kalshi-crypto-scan` | no_agent | **ACTIVE** | Paper scanner — logs decisions + simulated trades |
| `kalshi-paper-bot` | every 30 min (5-22) | `kalshi-scan.sh` | no_agent | PAUSED | Older paper bot (superseded by per-minute scanner) |
| `kalshi-after-action-review` | daily 21:00 | `kalshi_review.py` | agent | ACTIVE | Summarizes day's P&L, decisions, calibration |
| `kalshi-crypto-closeout` | every 15 min | `kalshi-crypto-closeout` | agent | PAUSED | Postmortem analysis of expired markets |

All no_agent scripts produce stdout verbatim; empty stdout = silent. Agent-driven cron jobs use the LLM to interpret script output and summarize findings.

---

## Current State (as of 2026-05-18)

### Portfolio
- **Paper balance (DB):** $1,000,000.00 (set manually — paper is actively trading)
- **Production balance (Kalshi API):** $45.92 (synced from exchange)
- **Production exposure cap:** $1.00 per coin, $30 HALT floor
- **Paper budget:** $4k max, 3 concurrent positions per coin

### Scanner Status
- **Paper scanner:** ACTIVE — runs every minute, logging decisions and placing simulated trades. 43 trades executed since 2026-05-18 09:54.
- **Production scanner:** PAUSED since 2026-05-17 18:55 MST (production trading was halted). The cron job `kalshi-crypto-prod` is disabled in the Hermes scheduler. Re-enable when ready to trade live again.

### Model Calibration Findings
The log-normal `fair_yes_probability()` is directionally asymmetric on 15-min crypto:

| Prediction | Correct | Total | Accuracy |
|---|---|---|---|
| Model says NO | 16 | 17 | 94.1% |
| Model says YES | 9 | 17 | 52.9% |

- Model-only Brier: **0.1745**
- Blended Brier: **0.1600** (Kalshi mid blend partially corrects overconfidence)
- V2 resolved trades with model data: **0** (v1: 34) — insufficient resolved v2 trades for calibration
- Target: 100-200 resolved v2 trades before training isotonic regression

### Active Deployments
- **Side-biased sizing:** `SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}` deployed 2026-05-17
- **Global MIN_EDGE_CENTS:** 6 (loosened from 8 on 2026-05-18 to capture 6-9¢ bucket)
- **MIN_CONFIDENCE:** 0.30 (reverted from 0.15 on 2026-05-18)
- **MIN_EDGE_BY_COIN (analyzer):** BTC=10¢, HYPE=8¢, ETH/SOL/XRP/DOGE=4¢, BNB=disabled
- **HALT_FLOOR:** $30 (lowered from $50 on 2026-05-17)
- **Symmetric vol multiplier:** rejected — 2.5x sweep couldn't fix per-direction bias

### Known Issues (Resolved)
1. ~~Prod auth failing from cron (5 recurrences)~~ — Fixed 2026-05-17: stale module-level vars in `kalshi_client.py` changed to read `os.environ` directly at call time. The final fix was commit `b86eeef` which also set up the heartbeat.
2. ~~Wrong env file priority~~ — Fixed 2026-05-17: cron retry now sources `~/.hermes/env` before `~/.hermes/.env`.
3. ~~Dashboard bid/ask only showing one side~~ — Fixed.
4. ~~8¢ threshold killed all trades~~ — MIN_EDGE_CENTS loosened to 6 on 2026-05-18. Assessment: even at 6¢, the analyzer's per-coin minimums (BTC=10¢, HYPE=8¢) are the tighter constraint for those coins. Zero-trade window was primarily caused by the prod scanner being paused, not the threshold.

### Known Issues (Open)
- **Prod scanner is paused** — needs manual re-enable via Hermes cron when ready to trade live again
- **Insufficient resolved v2 trades** for calibration modeling — need 100-200 resolved trades before isotonic regression is viable
- **Vault path in old docs says `~/.hermes-vault/`** — actual path is `~/hermes-vault/` (no dot prefix)

---

## Dashboard

Runs on port **8890** at internal network address (internal network only).

Shows:
- REAL-TIME crypto market leans (bid/ask, prob, edge, signal, OI for all 7 coins)
- LIVE + PAPER portfolio cards (equity, P&L, win rate, positions)
- Performance summary (net P&L, ROI, avg win/loss, 24h sparkline)
- Model honesty metrics (calibration table by bucket, Brier score, per-coin P&L)
- Operational health (heartbeat monitor, decisions/hour, filter distribution)
- Spread cost analysis
- Open positions, decision log, closed trades

Updated every scan cycle via `kalshi_live.json` cache file.

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                     CRON SCHEDULER                           │
│  every 60s                                                  │
│  ├── kalshi-crypto-prod ───→ places REAL orders on Kalshi   │
│  │   [PAUSED since 2026-05-17]                              │
│  │                          writes to kalshi_trades          │
│  │                          writes to kalshi_decision_log    │
│  │                          updates kalshi_heartbeat          │
│  │                          writes kalshi_live.json cache    │
│  │                                                           │
│  └── kalshi-crypto-scan ──→ paper trades (DB only)          │
│      [ACTIVE]               writes to kalshi_trades          │
│                              writes to kalshi_decision_log    │
│                              writes kalshi_live.json cache    │
│                                                              │
│  every 15 min                                                │
│  └── obsidian-sync.sh ────→ git commit + push to GitHub      │
│                             (syncs vault notes)              │
│                                                              │
│  daily 21:00                                                 │
│  └── kalshi-after-action-review → agent reviews day's data   │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     POSTGRES DATABASE                         │
│  kalshi_trades, kalshi_decision_log, kalshi_portfolio,       │
│  kalshi_heartbeat, kalshi_strategy_params                     │
│                                                              │
│  strategy_name='crypto_intel'           → paper             │
│  strategy_name='crypto_intel_prod'      → prod/live         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     DASHBOARD (port 8890)                     │
│  Reads from DB + cache file, renders HTML                    │
│  Auto-refreshes every 30s                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Script Locations

```
Repo:   https://github.com/aztenjin81/homelab-scripts
Server: /root/.hermes/scripts/

Vault:   https://github.com/aztenjin81/ai-exchange
Server:  /root/hermes-vault/
```

The AI exchange repo mirrors the Obsidian vault and auto-syncs every 15 min via cron. Drop files in `claude/` to communicate back to Hermes, check `hermes/` for analysis from Hermes.
