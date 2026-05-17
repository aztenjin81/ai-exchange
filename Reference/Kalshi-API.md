---
type: reference
status: active
date: 2026-05-16
tags: [api, finance, kalshi, prediction-markets, crypto-15m]
---

# Kalshi API

US-regulated event contract exchange (CFTC). No API key needed for market data reads.

## API Base

```
https://external-api.kalshi.com/trade-api/v2
```

## Auth (for orders)

Demo: `https://external-api.demo.kalshi.co/trade-api/v2`
Production orders: same base URL, RSA key from `kalshi.com/account/profile`.

Stored in `~/.hermes/env/kalshi.env`. Demp key ID + private key path in env vars.

## Key Endpoints (No Auth Required)

| Endpoint | Description |
|----------|-------------|
| `GET /markets?series_ticker={ticker}&limit=N&status=open` | Active markets for a series (use for crypto 15-min) |
| `GET /events/{event_ticker}` | Event details with all sub-markets + status + result |
| `GET /markets/{market_ticker}` | Single market detail (DOES NOT return status/result) |
| `GET /series/{series_ticker}` | Series info |

**Important:** For checking settlement (status=finalized, result=yes/no), use the **events endpoint** (`/events/{event_ticker}`). The `/markets` endpoint does not return `status` or `result` fields.

## Crypto 15-Min Series

7 crypto series tracked by the bot:

| Coin | Series Ticker | Event Pattern | Spot API |
|------|--------------|---------------|----------|
| BTC | `KXBTC15M` | `KXBTC15M-26MAY161815` (date+time UTC) | Coinbase BTC-USD |
| ETH | `KXETH15M` | `KXETH15M-...` | Coinbase ETH-USD |
| SOL | `KXSOL15M` | `KXSOL15M-...` | Coinbase SOL-USD |
| XRP | `KXXRP15M` | `KXXRP15M-...` | Coinbase XRP-USD |
| DOGE | `KXDOGE15M` | `KXDOGE15M-...` | Coinbase DOGE-USD |
| BNB | `KXBNB15M` | `KXBNB15M-...` | Coinbase BNB-USD |
| HYPE | `KXHYPE15M` | `KXHYPE15M-...` | Coinbase HYPE-USD |

Each 15-min window produces a market ticker like `KXBTC15M-26MAY161815-15` (series-event-seq). Floor strike is the reference price 15 min ago. The question: "Will the average of BRTI prices at close be ≥ the average 15 min earlier?"

## Rate Limits

- No rate limit documented, but 0.2s delay between coin fetches (7 call burst every 60s) works fine
- Events endpoint has ~5 calls per open position per cycle

## Relevant Event Categories

| Category | Examples |
|----------|----------|
| Crypto 15-Min | BTC, ETH, SOL, XRP, DOGE, BNB, HYPE price up/down every 15 min |
| Economics | CPI, Fed rate decisions, employment, durable goods, gas prices |
| Companies | Company-specific KPIs (FedEx, etc.) |
| Politics | Corporate tax rate, regulation |

## Usage

```bash
# List open markets for a series
curl -s "https://external-api.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&limit=1&status=open"

# Get event details (includes status + result for settlement)
curl -s "https://external-api.kalshi.com/trade-api/v2/events/KXBTC15M-26MAY161815"

# Demo authenticated order
curl -s -X POST "https://external-api.demo.kalshi.co/trade-api/v2/orders" \
  -H "Content-Type: application/json" \
  -H "KALSHI-ACCESS-KEY: $KALSHI_DEMO_KEY_ID" \
  -H "KALSHI-ACCESS-SIGNATURE: ..." \
  -H "KALSHI-ACCESS-TIMESTAMP: ..." \
  -d '{...}'
```

## Notes

- Kalshi cannot replace stock price tracking (no individual equity markets)
- Best used for economic indicator probabilities + crypto 15-min markets
- Complements CXDO tracking with macro context
- `floor_strike` = reference price at start of 15-min window
- Settlement uses CF Benchmarks BRTI 60-sec average (not live spot)
- Markets settle at `close_time`, finalization is immediate

## Related

- [[Kalshi-Bot]]
- [[Crexendo-CXDO]]
- [[Cron-Jobs]]
