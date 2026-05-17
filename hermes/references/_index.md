# References — Source of Truth for Claude

This directory contains the actual source code and database state that the Hermes Agent uses to trade Kalshi crypto 15-min markets.

## Files

| File | What it is |
|---|---|
| `crypto_intel.py` | Core intelligence — analysis, model, filters (1,831 lines) |
| `kalshi-crypto-prod` | Real-money production scanner (551 lines) |
| `kalshi-crypto-scan` | Paper scanner wrapper (8 lines) |
| `kalshi_client.py` | Kalshi REST API client with RSA auth (244 lines) |
| `hermes_db.py` | PostgreSQL helper (91 lines) |
| `dashboard.py` | Web dashboard server on port 8890 (851 lines) |
| `calibration-sanity-check` | Calibration validation script |
| `db-export.md` | Full database schema + row counts + portfolio state |
| `trades-export.md` | Last 100 trades with P&L |

## Architecture Summary

- **Kalshi API** → `kalshi_client.py` → `crypto_intel.py` (analysis) → `kalshi-crypto-prod` (execution) → **Postgres DB** → `dashboard.py` (UI)
- Cron jobs run the scanners every 60 seconds
- Every decision is logged to `kalshi_decision_log` for calibration tracking
- See `2026-05-17-kalshi-bot-full-system.md` for the full architecture doc

## Current Calibration State

- Model is directionally asymmetric (94% NO correct, 53% YES correct)
- NO-side sizing multiplier active: `{'no': 1.0, 'yes': 0.5}`
- Isotonic regression deferred until 100-200 v2 resolved trades
- See `2026-05-17-kalshi-calibration.md` for details
