# Kalshi bot — 24h follow-up after threshold patches

**Generated:** 2026-05-19 09:31 PDT
**Window:** 2026-05-18 09:31 to 2026-05-19 09:31 PDT
**Patches in effect:** MIN_EDGE_CENTS=8, MIN_CONFIDENCE=0.30, BNB disabled, paper YES half-sized

## Patch verification summary

- **MIN_EDGE_CENTS=8:** edge bucket 1 (3-6c) trade count: **29 trades** (all closed, 7W/22L, PnL +$54.95). Bucket 2 (6-9c): **50 trades**. ⚠️ Trades with edge < 8c are still entering the book — 79 trades in buckets 1-2. See Notes below.
- **BNB disable:** BNB trade count: **0** ✅ — no BNB trades in the 24h window.
- **Paper YES half-sizing:** Overall YES avg qty / NO avg qty across crypto_intel = **0.53** ✅ (target ~0.5, acceptable range 0.4-0.6). Per-coin ratios: DOGE 0.65, ETH 0.54, SOL 0.56, XRP 0.58 (BTC has 0 YES trades). DOGE is slightly above 0.6 — flagged in Notes.

## Query 1 — Edge bucket distribution

| edge_bucket | trades | closed | wins | losses | pnl | strategies |
| --- | --- | --- | --- | --- | --- | --- |
| 1 (3-6c) | 29 | 29 | 7 | 22 | $54.95 | 1 |
| 2 (6-9c) | 50 | 50 | 12 | 38 | -$53.97 | 1 |
| 3 (9-12c) | 20 | 20 | 6 | 14 | -$47.22 | 1 |
| 4 (12-15c) | 1 | 1 | 0 | 1 | -$3.63 | 1 |

**Notable:** Bucket 1 (sub-6c edge) is the only bucket with positive PnL. All buckets use only 1 strategy (crypto_intel).

## Query 2 — Per-coin activity

| series_ticker | strategy_name | trades | yes_trades | no_trades | closed | wins | losses | pnl | avg_entry | avg_edge_cents | avg_qty |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KXBTC15M | crypto_intel | 15 | 0 | 15 | 15 | 4 | 11 | -$176.69 | 0.4193 | 7.84 | 76.1 |
| KXDOGE15M | crypto_intel | 14 | 5 | 9 | 14 | 2 | 12 | -$38.48 | 0.1864 | 7.54 | 44.5 |
| KXETH15M | crypto_intel | 27 | 3 | 24 | 27 | 12 | 15 | +$326.21 | 0.2752 | 6.95 | 62.4 |
| KXSOL15M | crypto_intel | 28 | 7 | 21 | 28 | 5 | 23 | -$123.53 | 0.2646 | 6.51 | 49.4 |
| KXXRP15M | crypto_intel | 16 | 6 | 10 | 16 | 2 | 14 | -$37.38 | 0.2044 | 7.06 | 47.4 |

**YES vs NO avg_qty breakdown (half-sizing check):**

| series_ticker | side | trades | avg_qty | pnl |
| --- | --- | --- | --- | --- |
| KXBTC15M | no | 15 | 76.1 | -$176.69 |
| KXDOGE15M | no | 9 | 50.9 | -$49.40 |
| KXDOGE15M | yes | 5 | 33.0 | +$10.92 |
| KXETH15M | no | 24 | 65.8 | +$343.15 |
| KXETH15M | yes | 3 | 35.7 | -$16.94 |
| KXSOL15M | no | 21 | 55.4 | -$109.36 |
| KXSOL15M | yes | 7 | 31.3 | -$14.17 |
| KXXRP15M | no | 10 | 56.3 | +$4.04 |
| KXXRP15M | yes | 6 | 32.5 | -$41.42 |

## Query 3 — Hourly aggregate

| hour | trades | closed | wins | losses | pnl | avg_edge | min_edge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-18 16:00 | 3 | 3 | 0 | 3 | -$40.04 | 4.97 | **4.70** |
| 2026-05-18 17:00 | 3 | 3 | 1 | 2 | +$20.77 | 5.73 | **4.10** |
| 2026-05-18 18:00 | 4 | 4 | 0 | 4 | -$30.00 | 7.00 | **4.70** |
| 2026-05-18 19:00 | 6 | 6 | 3 | 3 | +$75.58 | 6.05 | **3.90** |
| 2026-05-18 20:00 | 8 | 8 | 1 | 7 | -$48.02 | 6.41 | **5.10** |
| 2026-05-18 21:00 | 3 | 3 | 0 | 3 | -$36.24 | 4.70 | **3.90** |
| 2026-05-18 22:00 | 7 | 7 | 0 | 7 | -$86.90 | 7.41 | **5.50** |
| 2026-05-18 23:00 | 2 | 2 | 1 | 1 | +$20.27 | 8.70 | 8.50 |
| 2026-05-19 00:00 | 7 | 7 | 2 | 5 | +$40.98 | 6.97 | **4.40** |
| 2026-05-19 01:00 | 8 | 8 | 4 | 4 | +$56.73 | 8.30 | **6.30** |
| 2026-05-19 02:00 | 5 | 5 | 1 | 4 | -$27.03 | 8.12 | **5.90** |
| 2026-05-19 03:00 | 7 | 7 | 2 | 5 | -$58.32 | 8.40 | **4.30** |
| 2026-05-19 04:00 | 10 | 10 | 3 | 7 | +$51.05 | 6.67 | **3.40** |
| 2026-05-19 05:00 | 6 | 6 | 0 | 6 | -$113.30 | 6.03 | **3.80** |
| 2026-05-19 06:00 | 11 | 11 | 1 | 10 | -$51.94 | 7.66 | **4.00** |
| 2026-05-19 07:00 | 6 | 6 | 4 | 2 | +$137.12 | 7.12 | **4.10** |
| 2026-05-19 08:00 | 3 | 3 | 1 | 2 | -$2.40 | 6.90 | **3.70** |
| 2026-05-19 09:00 | 1 | 1 | 1 | 0 | +$41.82 | 9.80 | 9.80 |

## Notes

### ⚠️ Min edge below 8c in 16 out of 18 hours
Almost every hour in the window has at least one trade with edge_cents < 8. The MIN_EDGE_CENTS=8 filter does not appear to be actively blocking sub-8c entries — trades as low as 3.40c edge appear as recently as 2026-05-19 04:00. Only two hours (23:00 and 09:00) have min_edge ≥ 8. This could mean:
1. The patch was deployed mid-window and earlier trades predate it, OR
2. The filter isn't wired into the entry path for all strategies.

If the patch was deployed prior to this window, the filter needs investigation.

### ✅ BNB disable — confirmed working
Zero BNB trades in the 24h window.

### ~✅ YES half-sizing — mostly on target
Overall YES/NO qty ratio = **0.53** (target ~0.5, acceptable 0.4-0.6). Per-coin:
- DOGE: **0.65** — slightly above range. Only 5 YES trades, small sample.
- ETH: 0.54 ✅
- SOL: 0.56 ✅
- XRP: 0.58 ✅
- BTC: no YES trades (100% NO bias)

The DOGE ratio is marginal and may normalize with more YES trade volume.

### ℹ️ Bucket 1 (3-6c edge) positive PnL paradox
The lowest-edge bucket is the only one with positive PnL (+$54.95). This could be survivor bias (small sample of 29 trades with favorable settlement outcomes) or suggest that edge filtering alone doesn't predict PnL in this market regime.

### 📊 Overall 24h PnL: -$49.87
Total: 100 trades, all closed, 25W/75L. ETH is the only profitable coin (+$326.21), carrying BTC's heavy loss (-$176.69).
