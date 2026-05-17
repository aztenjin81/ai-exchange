---
type: reference
status: active
date: 2026-05-16
tags: [kalshi, paper-trading, bot, cron, dashboard]
---

# Kalshi Paper Trading Bot — Operations

Dashboard: `http://192.168.1.226:8890` (auto-refresh 30s)

## Current State

Portfolio: ~$9,224 (from $10k). Running fully autonomous since May 16.

## Cron Jobs

| Job ID | Name | Schedule | Script | Type | Status |
|--------|------|----------|--------|------|--------|
| 9c49efa4fb7e | kalshi-crypto-scanner | `* * * * *` (every 60s) | `kalshi-crypto-scan` | no_agent, deliver=local | Active |
| eb0a98aeafd0 | kalshi-paper-bot | `*/30 5-22 * * *` (every 30min) | `kalshi-scan.sh` | no_agent, deliver=origin | Active |
| 9a7833953380 | kalshi-after-action-review | `0 21 * * *` (daily 9pm) | `kalshi_review.py` | LLM-driven, deliver=origin | Active |

### Crypto Scanner (`kalshi-crypto-scan`)

```python
# Wrapper at ~/.hermes/scripts/kalshi-crypto-scan
from crypto_intel import scan_and_log
scan_and_log()
```

Scans all 7 crypto 15-min markets, logs decisions, enters paper trades where edge exists, settles expired positions, writes cache for dashboard.

## Key Files

All in `~/.hermes/scripts/`:

| File | Role |
|------|------|
| `kalshi_bot.py` | Main bot: sports, weather, spread strategies (30min cycle) |
| `crypto_intel.py` | Crypto 15-min edge analysis, scanner, micro-cap mode |
| `kalshi_client.py` | API client — production read (no auth) + demo auth |
| `dashboard.py` | HTTP server on port 8890 |
| `kalshi_review.py` | After-action review (daily 9pm) |
| `kalshi-crypto-scan` | Cron wrapper for crypto scanner |

## Switching to Micro-Cap Mode (Real Money)

When going live with $10-20:

1. Replace the crypto scanner cron's script or create a new cron calling `scan_micro_cap()` instead of `scan_and_log()`
2. Strategy config is at `kalshi_strategy_params` where `strategy_name='crypto_intel_microcap'`
3. Full strategy documented in `kalshi-micro-cap` skill

## Dashboard

Static HTML served from Python `http.server`. Page rebuilds on each request from:
- Cache file (`~/.hermes/cache/kalshi_live.json`) — written by scanner every 60s
- Postgres queries (portfolio, positions, decisions, closed trades)

No dependencies beyond stdlib + psycopg2. Runs as background process.

## Migration Log

| Date | Change |
|------|--------|
| May 16 | Initial bot: sports, weather, spread fishing |
| May 16 | Added crypto 15-min Strategy 0 |
| May 16 | Replaced count-based caps with capital budgets |
| May 16 | Added `kalshi_decision_log` for per-cycle tracking |
| May 16 | Fixed exit checker (events endpoint + finalized status) |
| May 16 | Built dashboard on port 8890 |
| May 16 | Added micro-cap mode for $10-20 real-money trading |

## Related

- [[Kalshi-Bot]]
- [[Kalshi-API]]
