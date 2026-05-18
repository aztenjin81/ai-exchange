# Kalshi bot — rejection breakdown

**Generated:** 2026-05-18 16:07 MST
**Window:** 2026-05-18 09:54:00 to NOW()
**edge_cents unit interpretation:** **decimal cents** — stored as-is (0.1 = 0.1¢, 6.0 = 6¢). Buckets below use these values directly.

## Critical finding: the prod scanner was PAUSED

**`kalshi-crypto-prod` (job 2680ca72c1f8) has been PAUSED since 2026-05-17 18:55:39 MST.** It was paused when production trading was stopped yesterday afternoon and was never resumed. The 7 `crypto_intel_prod` rows in the window are from the manual verification run of the current session, not from autonomous scanning.

**The "zero trades" problem is not a threshold issue — the scanner wasn't running.**

The paper scanner (`kalshi-crypto-scanner`, active, runs every minute) is producing `crypto_intel` decisions normally and executing trades.

## Query 1 — scan volume by hour

| hour | strategy_name | scans |
| --- | --- | --- |
| 2026-05-18 09:00 | crypto_intel | 42 |
| 2026-05-18 10:00 | crypto_intel | 357 |
| 2026-05-18 11:00 | crypto_intel | 364 |
| 2026-05-18 12:00 | crypto_intel | 364 |
| 2026-05-18 13:00 | crypto_intel | 376 |
| 2026-05-18 14:00 | crypto_intel | 352 |
| 2026-05-18 15:00 | crypto_intel | 371 |
| 2026-05-18 16:00 | crypto_intel | 35 |
| 2026-05-18 16:00 | crypto_intel_prod | 7 |

**Interpretation:** `crypto_intel` (paper scanner) fires ~350 scans/hour consistently. `crypto_intel_prod` had 7 total — all from manual invocation in the current session.

## Query 2 — action distribution

| action | strategy_name | n | avg_edge | min_edge | max_edge | avg_conf | executed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| edge_too_small | crypto_intel | 1568 | 0.74 | -4.80 | 10.50 | 0.00 | 0 |
| too_close_to_expiry | crypto_intel | 278 | 0.00 | 0.00 | 0.00 | 0.00 | 0 |
| spread_too_wide | crypto_intel | 241 | 0.00 | 0.00 | 0.00 | 0.00 | 0 |
| positive_ev_direction_agreement_signal | crypto_intel | 43 | 6.78 | 4.30 | 11.40 | 0.43 | 43 |
| model_market_disagreement_too_large | crypto_intel | 42 | 0.00 | 0.00 | 0.00 | 0.00 | 0 |
| entry_too_expensive_for_ttl | crypto_intel | 29 | 5.90 | 4.00 | 11.90 | 0.00 | 0 |
| edge_ratio_too_small | crypto_intel | 25 | 5.17 | 4.00 | 7.40 | 0.00 | 0 |
| blocked_contrarian_cheap_no | crypto_intel | 15 | 7.53 | 4.30 | 13.90 | 0.00 | 0 |
| blocked_contrarian_cheap_yes | crypto_intel | 9 | 5.16 | 4.30 | 7.00 | 0.00 | 0 |
| yes_too_expensive_for_known_bias | crypto_intel | 7 | 5.37 | 4.20 | 6.10 | 0.00 | 0 |
| blocked_spot_strike_deadzone | crypto_intel | 4 | 8.25 | 6.30 | 11.00 | 0.00 | 0 |
| edge_too_small | crypto_intel_prod | 4 | 3.00 | 1.60 | 4.60 | 0.00 | 0 |
| entry_too_expensive_for_ttl | crypto_intel_prod | 2 | 8.40 | 6.20 | 10.60 | 0.00 | 0 |
| spread_too_wide | crypto_intel_prod | 1 | 0.00 | 0.00 | 0.00 | 0.00 | 0 |

**For crypto_intel (paper scanner):** `edge_too_small` dominates (69% — 1,568 of 2,261 decisions). But 43 trades did execute with avg edge 6.78c. The second-largest filter is `too_close_to_expiry` (278) and `spread_too_wide` (241). Multiple structural filters (contrarian blocks, spot-strike deadzone, model-market disagreement) each claim 4-42 decisions.

**For crypto_intel_prod:** Only 7 total decisions (all from manual invocation). 4 edge_too_small, 2 entry_too_expensive, 1 spread_too_wide. Zero trades executed.

## Query 3 — edge bucket of edge_too_small rejections

| edge_bucket | strategy_name | n | avg_conf |
| --- | --- | --- | --- |
| 0-1c | crypto_intel | 903 | 0.00 |
| 1-2c | crypto_intel | 240 | 0.00 |
| 2-3c | crypto_intel | 179 | 0.00 |
| 3-4c | crypto_intel | 137 | 0.00 |
| 4-5c | crypto_intel | 45 | 0.00 |
| 5-6c | crypto_intel | 28 | 0.00 |
| 6-7c | crypto_intel | 20 | 0.00 |
| 7-8c | crypto_intel | 12 | 0.00 |
| 8c+ | crypto_intel | 4 | 0.00 |
| 1-2c | crypto_intel_prod | 2 | 0.00 |
| 4-5c | crypto_intel_prod | 2 | 0.00 |

**Key observation:** 903 of 1,568 edge_too_small rejections (58%) are in the 0-1c bucket — the model produces a huge mass of negligible edges. At the other end, only 4 rejections are 8c+ and only 12 are 7-8c. The thresholds in the 4-8c range only catch 45+28+20+12 = 105 out of 1,568 (7%). The vast majority of rejections would not be helped by any threshold relaxation.

**For crypto_intel_prod:** All 4 edge_too_small rejections are at 4.6c or below — none would have passed the 6c threshold either.

## Query 4 — top 10 highest-edge near-misses (prod, key:value format)

### Row 1

scan_time: 2026-05-18 16:02:41.016929-07
market_ticker: KXBTC15M-26MAY181915-15
series_ticker: KXBTC15M
side: hold
entry_price: 0.81
fair_value: 0.8559783945772619
market_prob: 80.5
edge_cents: 4.6
confidence: 0
model_fair_yes: 0.8776221347433067
fair_yes: 0.8559783945772619
spot_price: 77097.925
strike_price: 77022.46
ttl_minutes: 12.326392449999998
spread: 0.010000000000000009
volatility: 0.1738511584784109
reasoning: Spot $77,097.93, strike $77,022.46, TTL 12.3m
Spot minus strike: 0.0980% (yes)
Annualized realized vol estimate: 0.17 (kraken)
Model fair YES: 0.878
Kalshi YES mid: 0.805, blend weight: 0.30
Final fair YES: 0.856, fair NO: 0.144
YES edge: 4.6c at ask 0.81
NO edge: -5.6c at ask 0.20
Signals: neutral (score=+0)
Best edge 4.6c < required 10.0c

---

### Row 2

scan_time: 2026-05-18 16:02:44.479358-07
market_ticker: KXHYPE15M-26MAY181915-15
series_ticker: KXHYPE15M
side: hold
entry_price: 0.65
fair_value: 0.6895521116604333
market_prob: 60.00000000000001
edge_cents: 4.0
confidence: 0
model_fair_yes: 0.727933946538484
fair_yes: 0.6895521116604333
spot_price: 47.3
strike_price: 47.1537
ttl_minutes: 12.272375333333335
spread: 0.09999999999999998
volatility: 1.056899256991029
reasoning: Spot $47.30, strike $47.15, TTL 12.3m
Spot minus strike: 0.3103% (yes)
Annualized realized vol estimate: 1.06 (hyperliquid)
Model fair YES: 0.728
Kalshi YES mid: 0.600, blend weight: 0.30
Final fair YES: 0.690, fair NO: 0.310
YES edge: 4.0c at ask 0.65
NO edge: -14.0c at ask 0.45
Signals: 1m trend=bullish, exchange=bearish (score=+0)
Best edge 4.0c < required 8.0c

---

### Row 3

scan_time: 2026-05-18 16:02:41.605025-07
market_ticker: KXETH15M-26MAY181915-15
series_ticker: KXETH15M
side: hold
entry_price: 0.19
fair_value: 0.7920789227785229
market_prob: 82.0
edge_cents: 1.8
confidence: 0
model_fair_yes: 0.780203679819903
fair_yes: 0.7920789227785229
spot_price: 2136.775
strike_price: 2134.62
ttl_minutes: 12.316349233333334
spread: 0.01999999999999999
volatility: 0.26970031927016125
reasoning: Spot $2,136.78, strike $2,134.62, TTL 12.3m
Spot minus strike: 0.1010% (yes)
Annualized realized vol estimate: 0.27 (kraken)
Model fair YES: 0.780
Kalshi YES mid: 0.820, blend weight: 0.30
Final fair YES: 0.792, fair NO: 0.208
YES edge: -3.8c at ask 0.83
NO edge: 1.8c at ask 0.19
Signals: 1m trend=bullish (score=+1)
Best edge 1.8c < required 4.0c

---

### Row 4

scan_time: 2026-05-18 16:02:43.639929-07
market_ticker: KXDOGE15M-26MAY181915-15
series_ticker: KXDOGE15M
side: hold
entry_price: 0.84
fair_value: 0.8555724668121115
market_prob: 82.0
edge_cents: 1.6
confidence: 0
model_fair_yes: 0.8707823260125334
fair_yes: 0.8555724668121115
spot_price: 0.10513
strike_price: 0.104922
ttl_minutes: 12.286066883333332
spread: 0.039999999999999925
volatility: 0.3624700810887352
reasoning: Spot $0.11, strike $0.10, TTL 12.3m
Spot minus strike: 0.1982% (yes)
Annualized realized vol estimate: 0.36 (kraken)
Model fair YES: 0.871
Kalshi YES mid: 0.820, blend weight: 0.30
Final fair YES: 0.856, fair NO: 0.144
YES edge: 1.6c at ask 0.84
NO edge: -5.6c at ask 0.20
Signals: 1m trend=bullish, exchange=bullish (score=+2)
Best edge 1.6c < required 4.0c

---

## Notes

1. **Prod scanner is paused.** `kalshi-crypto-prod` (job `2680ca72c1f8`) was paused at `2026-05-17T18:55:39 MST` and never resumed after production trading was stopped. The entire "zero trades" window is explained by the bot not running. The 7 prod rows in the log are from the verification execution in this session, not from autonomous operation.

2. **The global `MIN_EDGE_CENTS` is not the primary bottleneck.** Even for the paper scanner, which runs freely, `edge_too_small` blocks 69% of decisions. But 58% of those (903/1,568) are in the 0-1c edge bucket — no threshold relaxation helps there. The model simply produces very small edges for most scans.

3. **The analyzer's per-coin minimums are a harder constraint.** In `crypto_intel.py`, `MIN_EDGE_BY_COIN` sets BTC=10c, HYPE=8c, ETH/SOL/XRP/DOGE=4c. These are checked inside the analyzer before the prod script's global `MIN_EDGE_CENTS=6` is even consulted. Even at `MIN_EDGE_CENTS=6`, BTC requires 10c and HYPE requires 8c from the analyzer layer. The two near-miss BTC scans at 4.6c were blocked by the analyzer's 10c requirement.

4. **The paper scanner IS executing trades.** 43 trades executed since the 8c revert with avg edge 6.78c and avg confidence 0.43. The system works for paper — the bottleneck was that prod wasn't running.
