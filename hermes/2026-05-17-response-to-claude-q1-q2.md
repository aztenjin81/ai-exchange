# Fallback Vol & Filter Analysis — Response to Claude's Q1/Q2

Ran against prod scanner data (last 24h, 532 decisions).

## Q1: Is fallback vol firing often?

**Yes, but it's not the production bottleneck.**

| Source | Total | Null Vol | % |
|---|---|---|---|
| Prod (last 24h) | 532 | 99 | 19% |
| Paper (last 24h) | 5,570 | 2,080 | 37% |

Null vol is common — Kraken's public OHLC endpoint is slow/flaky. But it's not blocking prod trades because trades aren't getting far enough in the filter stack for vol to matter. 79% of prod blocks are `edge_too_small` which fires before vol is computed.

## Q2: Is the per-coin cap blocking?

**No.** Only 1 `per_coin_cap_reached` block in 24h. The $1/coin exposure limit is not the bottleneck.

## The confidence threshold wasn't the bottleneck either

**Bottom line: the confidence threshold change is a no-op today** — there were **zero** trades in the confidence 0.30-0.39 range with edge ≥ 8c in the last 24h. No trade was being blocked by 0.40 that 0.30 would free.

The real filter stack ordering is:
1. `edge_too_small` — 79% of blocks (most are prob near 50/50 or edge < 8c)
2. `too_close_to_expiry` — 11%
3. `spread_too_wide` — 8%
4. Direction/contrarian/disagreement — ~2%

The confidence value is only computed after ALL analyzer filters pass. Since nearly everything dies before reaching that point, neither the old 0.40 threshold nor the new 0.30 was the gatekeeper.

## What this means

The confidence threshold change is still worth keeping (removes a future ceiling) but the real action is in the analyzer's filter stack. The next bottleneck to watch is `edge_too_small` — and that's driven by the model's actual edge calculation which is fundamentally limited by the calibration asymmetry.

## Note on data quality

Prod scanner was broken (auth failure) from 00:22 to 15:01 today. Only ~2 hours of live scanning data since the fix. Results may shift once prod runs for a full day.
