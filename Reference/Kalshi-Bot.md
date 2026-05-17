---
type: reference
status: active
date: 2026-05-16
tags: [kalshi, paper-trading, bot, crypto-15m, strategy]
---

# Kalshi Paper Trading Bot

Automated prediction market bot for [[Kalshi]]. Paper portfolio ($10,000), runs on cron. Dashboard at `http://192.168.1.226:8890`.

## Architecture

```
Kalshi API → Scanner (crypto 60s / main 30min) → Strategy Pipeline → Postgres → Dashboard → Review
```

**Stack:** Python, Postgres, free APIs (Kalshi public, Coinbase spot, ESPN, Open-Meteo). No keys needed for reads.

## Strategy Pipeline (4-tier)

| # | Strategy | Frequency | Budget | What it does | Data Source |
|---|----------|-----------|--------|-------------|-------------|
| 0 | **Crypto 15-Min Intel** | Every 60s | $4,000 | Edge analysis on 7 crypto 15-min binary markets vs 50/50 baseline | Kalshi orderbook + Coinbase spot |
| 1 | Weather Intel | Every 30min | $1,500 | 30yr ERA5 climate + 16-day forecast → fair probability | Open-Meteo |
| 2 | Sports Intel | Every 30min | $3,000 | Team win%, player base rates, UFC log5 → MVE fair value | ESPN free APIs |
| 3 | Spread Fishing | Every 30min | $1,500 | Capture bid/ask spread on standard binaries | Kalshi orderbook |

All budgets sum to $10,000 (full portfolio). Crypto managed by separate scanner; main bot handles weather/sports/spread.

## Capital Allocation (vs old count-based caps)

Instead of position-count limits (MAX_OPEN_POSITIONS=50), the system now uses **capital budgets** per strategy:

```python
STRATEGY_BUDGETS = {
    'crypto_intel': 4000,    # $4k for crypto 15-min
    'sports_intel': 3000,    # $3k for sports parlays
    'weather_intel': 1500,   # $1.5k for weather
    'spread_fishing': 1500,  # $1.5k for spread capture
}
```

On each scan, the bot queries `SUM(entry_price * qty)` deployed per strategy and only enters if remaining budget > 0.

## Crypto 15-Min Intel — Detail

### Markets Tracked

7 coins via Kalshi `series_ticker` filter: BTC, ETH, SOL, XRP, DOGE, BNB, HYPE.

Each is a binary "will price be higher than 15 min ago?" market. Baseline probability is 50/50 (random walk). Edge = |market_prob - 0.50|.

### Per-Coin Limits

Max 3 concurrent positions per coin (prevents over-concentration when multiple 15-min windows overlap).

### Decision Log

Every scan cycle logs every market to `kalshi_decision_log`:
- Which coin, what we decided (enter_yes/enter_no/hold/skip)
- Edge in cents, confidence level, spread, OI
- Whether the trade was actually executed
- Trade ID link back to `kalshi_trades`

This is the data used for learning/review.

### Entry Logic

1. Skip expired or near-expiry (< 2 min) markets
2. Compute edge = |mid - 0.50| in cents
3. If edge < 3¢ → HOLD (edge_too_small)
4. If edge consumed by spread (net_edge < 1¢) → HOLD
5. Otherwise → trade YES or NO depending on direction
6. Confidence = base(0.25) + edge_bonus + liquidity_bonus + time_penalty (cap at 0.85)
7. Position size = `max(10, min(int(50 × confidence × 3), 200))` contracts
8. Check per-coin limit (max 3) and capital budget ($4k) before entering

## Dashboard

Live at `http://192.168.1.226:8890` — auto-refreshes every 30s.

**Sections:**
- Portfolio cards (balance, realized P&L, win rate, open position count, cost basis)
- Crypto live leans (all 7 coins with prob, bid/ask, lean signal, edge, confidence, spot price, OI)
- Open positions (all open crypto trades with entry, qty, cost, conf, edge)
- Decision log (last 30 decisions per cycle)
- Closed trades (settled trades with P&L)

Data flows: Scanner writes to PG + cache file → Dashboard reads cache + PG. Fast page loads (~16KB).

## Files

| File | Purpose |
|------|---------|
| `kalshi_bot.py` | Main bot: scan/status/history commands (sports, weather, spread) |
| `crypto_intel.py` | Crypto 15-min edge analysis + scanner + micro-cap mode |
| `kalshi_crypto_scanner.py` | Legacy crypto scanner (deprecated — use crypto_intel scan_and_log) |
| `kalshi_client.py` | Unified Kalshi API client (production read + demo auth) |
| `weather_intel.py` | Weather fair-value estimation |
| `sports_intel.py` | Sports fair-value estimation (ESPN data) |
| `kalshi_review.py` | After-action review module |
| `kalshi_eval.py` | On-the-fly market evaluator |
| `dashboard.py` | Python HTTP dashboard server on port 8890 |
| `kalshi-scan.sh` | Legacy main bot cron wrapper |

All scripts live in `~/.hermes/scripts/`.

## Database (Postgres, schema `public`)

| Table | Purpose |
|-------|---------|
| `kalshi_portfolio` | Balance, realized P&L, win/loss count |
| `kalshi_trades` | Every trade with entry/exit, confidence, reasoning, data sources |
| `kalshi_market_snapshots` | Market snapshots at each scan cycle |
| `kalshi_decision_log` | Per-cycle decision for every market (including HOLDs) |
| `kalshi_trade_reviews` | Post-settlement prediction vs outcome analysis |
| `kalshi_strategy_params` | Strategy versioning, parameter overrides, micro-cap config |

Every trade logs: `confidence` (0-1), `reasoning_json` (why we bought), `predicted_fair_value`, `edge_cents`, `data_sources`.

## Cron Jobs

| Job | Schedule | Type | Script | Deliver |
|-----|----------|------|--------|---------|
| kalshi-crypto-scanner | Every 60s | no_agent | `kalshi-crypto-scan` | local |
| kalshi-paper-bot | Every 30 min, 5am-10pm | no_agent | `kalshi-scan.sh` | origin |
| kalshi-after-action-review | Daily 9pm | no_agent | `kalshi_review.py` | origin |

## Commands

```bash
# Main bot
python3 kalshi_bot.py scan     # snapshot + evaluate (sports/weather/spread)
python3 kalshi_bot.py status   # portfolio + mark-to-market
python3 kalshi_bot.py history  # last 20 closed trades

# Crypto scanner
python3 -c "from crypto_intel import scan_and_log; scan_and_log()"

# Micro-cap mode (for $10-20 real-money trading)
python3 -c "from crypto_intel import scan_micro_cap; scan_micro_cap()"

# Review
python3 kalshi_review.py       # review settled trades
```

## Micro-Cap Mode (for $10-20 Real Money)

Saved as skill `kalshi-micro-cap`. Config in `kalshi_strategy_params` as `crypto_intel_microcap`:

| Parameter | Value |
|-----------|-------|
| min_edge_cents | 15 |
| min_confidence | 0.60 |
| min_oi | 500 |
| max_risk_pct | 0.50 (50% of bankroll per trade) |
| halt_below_dollars | 5 |

Strategy: **Pick the single best signal** across all 7 coins by `edge × confidence` score. Skip all others. One concentrated bet per 15-min window. If no market meets thresholds, sit out.

The goal is asymmetric ROI: buying at $0.10→$1.00 gives 900% return. At $20 bankroll, hitting 3 of these in a row compounds to $200+.

## After-Action Review

Runs daily at 9pm. For each settled trade:
1. Compare predicted fair value vs actual outcome
2. Flag calibration issues (overconfident / underconfident)
3. Generate improvement recommendations
4. Save to `kalshi_trade_reviews`

## Current Results (First Batch, May 16 2026)

System entered 21 crypto 15-min trades. All resolved YES. P&L: **+$202.37** (21-0, 100% win rate).

| Coin | Trades | P&L |
|------|--------|-----|
| ETH | 3 | +$49.34 |
| BNB | 3 | +$40.50 |
| BTC | 3 | +$38.67 |
| DOGE | 3 | +$26.34 |
| XRP | 3 | +$24.48 |
| SOL | 3 | +$17.22 |
| HYPE | 3 | +$5.82 |

## Known Issues

- **Weekend markets:** Only MVE sports markets available. No economic/political markets until Monday
- **Sports MVE liquidity:** YES-side bid is often $0 after entry — can't flip, must hold to settlement
- **Exit detection:** Must use `/events/{event_ticker}` endpoint (not `/markets?ticker=`) to get `status=finalized` and `result`
- **Crypto 15-min liquidity:** Smaller coins (DOGE, BNB, HYPE, XRP) often have OI < 500 and wide spreads — low conf, high spread risk

## Changelog

| Date | Change |
|------|--------|
| May 16 — Initial | Sports, weather, spread fishing deployed |
| May 16 — v2 | Added crypto 15-min Strategy 0 |
| May 16 — v3 | Replaced count-based caps with capital budgets ($10k split across 4 strategies) |
| May 16 — v4 | Added `kalshi_decision_log` for per-cycle decision tracking |
| May 16 — v5 | Fixed exit checker: events endpoint + finalized status |
| May 16 — v6 | Built dashboard at `http://192.168.1.226:8890` |
| May 16 — v7 | Added micro-cap mode for $10-20 real-money trading (skill: `kalshi-micro-cap`) |
| May 16 — v8 | **Momentum-adjusted baseline.** Replaced hard 50/50 baseline with trend-aware baseline from last 8 settled windows. Prevents betting against clear trends (which caused -$1,087 loss in batch 2). XRP/HYPE now correctly trigger YES signals at 88% trend baseline instead of false NO signals. |

## Links

- [[Kalshi-API]]
- [[Crexendo-CXDO]]
- [[Cron-Jobs]]
- Skill: `kalshi-micro-cap` (micro-cap strategy playbook)
