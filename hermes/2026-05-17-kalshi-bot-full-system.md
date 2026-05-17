# Kalshi Crypto 15-Min Bot — Full System Architecture

## Overview

This bot trades Kalshi's crypto 15-minute binary options ("will the price of [coin] be above the strike price at expiry?"). It's been built iteratively over several sessions, progressing through v0 (spread arb), v1 (basic mid-based edge), and v2 (model-driven fair probability + filters).

Runs on a headless Ubuntu server (DevServer, 192.168.1.226) in a homelab environment. Postgres database, cron-driven scanners, Python scripts, and a web dashboard.

---

## Directory Layout

All scripts live at `~/.hermes/scripts/` (git repo: `github.com/aztenjin81/homelab-scripts`).

```
~/.hermes/
├── scripts/
│   ├── crypto_intel.py           # Core intelligence (1,831 lines)
│   ├── kalshi-crypto-prod        # Production scanner (cron, 551 lines)
│   ├── kalshi-crypto-scan        # Paper scanner (cron, 8 lines)
│   ├── kalshi_client.py          # Kalshi REST API client (244 lines)
│   ├── hermes_db.py              # PostgreSQL helper (91 lines)
│   ├── dashboard.py              # Web UI server (851 lines, port 8890)
│   ├── kalshi_review.py          # After-action review script
│   ├── calibration-sanity-check  # Calibration validation script
│   ├── kalshi-scan.sh            # Paper bot shell wrapper
│   └── ... (other scripts)
├── secrets/
│   └── kalshi-production.key     # Prod API key (combined format)
├── .env                          # Prod credentials (sourced by cron)
├── cron/
│   ├── jobs.json                 # Cron job definitions
│   └── postmortem_enabled        # Toggle for closeout postmortem
└── cache/
    └── kalshi_live.json          # Dashboard cache (updated every scan)
```

Vault: `~/.hermes-vault/` — shared via Obsidian Sync + git push to `github.com/aztenjin81/ai-exchange`.

---

## File-by-File Breakdown

### 1. `crypto_intel.py` — Core Intelligence Module (1,831 lines)

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
9. Check `min_edge_for_ttl()` — higher edge required closer to expiry
10. Check `max_entry_for_ttl()` — cap on entry price
11. `edge_ratio_too_small` — edge must be at least 15% of entry price
12. `spot_strike_deadzone` — block if spot too close to strike (<0.02%)
13. `block_contrarian_entry_if_needed()` — prevents betting against strong market consensus
14. `require_direction_agreement()` — Kalshi orderbook, spot price, and model must agree
15. Compute confidence score (0.10-0.85) from edge size, OI, spread, TTL, volatility source

**Sizing:**
- `SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}` — deployed 2026-05-17
- `scan_and_log()` — runs analyze on all markets, logs decisions
- `scan_micro_cap()` — picks single best signal, sizes at up to 50% of bankroll

**Cache & logging:**
- `write_cache()` — writes `kalshi_live.json` for dashboard consumption
- `log_decision()` — writes to `kalshi_decision_log` table

### 2. `kalshi-crypto-prod` — Production Scanner (551 lines)

Cron runner for real-money trading. Called every minute by cron (no_agent mode).

**Flow:**
1. Write heartbeat (`kalshi_heartbeat` table) — dead man's switch
2. Authenticate (create_prod_client → RSA-signed requests to Kalshi API)
3. Fetch and sync balance from Kalshi API
4. Check halt floor ($50 minimum)
5. Get per-coin exposure from `kalshi_trades` (open positions)
6. Settle any expired positions
7. Fetch and analyze all 7 markets (calls crypto_intel)
8. Score candidates by `edge * confidence`
9. Pick top 3, apply per-coin sizing with side multiplier
10. Place limit orders via Kalshi API
11. Log trades and decisions to DB

**Config:**
```
MAX_PER_COIN_DOLLARS = 1.00
HALT_FLOOR = 50.00
MIN_EDGE_CENTS = 8
MIN_CONFIDENCE = 0.40
HARD_MAX_ENTRY_PRICE = 0.75
DRY_RUN = env("KALSHI_DRY_RUN", False)
```

### 3. `kalshi-crypto-scan` — Paper Scanner (8 lines)

Simple wrapper that calls `crypto_intel.scan_and_log()`. Runs every minute via cron, logs decisions to `kalshi_decision_log` with `strategy_name='crypto_intel'`. No real orders placed.

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

### 5. `hermes_db.py` — PostgreSQL Helper (91 lines)

Database connection helper for all scripts.

Provides: `get_conn()`, `query(sql)` (returns list of tuples), `query_one(sql)`, `execute(sql)`.

Connects to `HERMES_PG_URI` from environment or sourced from `~/.hermes/env`.

### 6. `dashboard.py` — Web Dashboard (851 lines)

Self-contained HTTP server on port 8890. Renders a dark-themed HTML dashboard showing:
- Portfolio cards (LIVE/PAPER equity, P&L, win rate, open positions)
- Performance summary (Brier score, calibration table, per-coin breakdown)
- Operational health (heartbeat age, decisions/hour, filter distribution)
- Live crypto market leans (bid/ask, edge, confidence, open interest by coin)
- Open positions, decision log, closed trades

Refreshes every 30 seconds via `<meta refresh>`.

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
| `kalshi_order_id` | text | Kalshi order reference |
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
| `edge_cents` | numeric | Edge in cents |
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
          min_edge, entry_price, edge_ratio,
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

| Name | Schedule | Script | Type | Purpose |
|---|---|---|---|---|
| `kalshi-crypto-prod` | every 1 min | `kalshi-crypto-prod` | no_agent | Production scanner — places real orders |
| `kalshi-crypto-scanner` | every 1 min | `kalshi-crypto-scan` | no_agent | Paper scanner — logs decisions only |
| `kalshi-paper-bot` | every 30 min (5-22) | `kalshi-scan.sh` | no_agent | Paper bot (older, less frequent) |
| `kalshi-after-action-review` | daily 21:00 | `kalshi_review.py` | agent | Summarizes day's P&L, decisions, calibration |
| `kalshi-crypto-closeout` | every 15 min | (paused) | agent | Postmortem analysis of expired markets |

All no_agent scripts produce stdout verbatim; empty stdout = silent. Agent-driven cron jobs use the LLM to interpret script output and summarize findings.

---

## Current State (as of 2026-05-17)

### Portfolio
- **Production balance:** $68.05 (just synced from Kalshi API)
- **Production exposure cap:** $1.00 per coin, $50 HALT floor
- **Paper:** Separate demo portfolio

### Model Calibration Findings
The log-normal `fair_yes_probability()` is directionally asymmetric on 15-min crypto:

| Prediction | Correct | Total | Accuracy |
|---|---|---|---|
| Model says NO | 16 | 17 | 94.1% |
| Model says YES | 9 | 17 | 52.9% |

- Model-only Brier: **0.1745**
- Blended Brier: **0.1600** (Kalshi mid blend partially corrects overconfidence)
- V2 resolved trades with model data: **0** (v1: 34)

### Active Deployments
- **Symmetric vol multiplier** — rejected (2.5x sweep confirmed it can't fix per-direction bias)
- **NO-side sizing** — `SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}` deployed 2026-05-17
- **Isotonic regression** — deferred until 100-200 resolved v2 trades accumulate

### Known Issues (Resolved 2026-05-17)
1. ~~Prod auth failing from cron~~ — Fixed: stale module-level vars in `kalshi_client.py` changed to read `os.environ` directly at call time
2. ~~Wrong env file priority~~ — Fixed: cron retry now sources `~/.hermes/env` (credentials) before `~/.hermes/.env` (template)
3. Dashboard bid/ask now shows both sides' books

---

## Dashboard

Runs on port **8890** at http://192.168.1.226:8890 (internal network only).

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
│  ├── kalshi-crypto-prod ───→ places REAL orders on Kalshi    │
│  │                          writes to kalshi_trades          │
│  │                          writes to kalshi_decision_log    │
│  │                          updates kalshi_heartbeat          │
│  │                          writes kalshi_live.json cache    │
│  └── kalshi-crypto-scan ──→ logs paper decisions only        │
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
