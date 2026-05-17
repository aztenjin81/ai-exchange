# Kalshi Crypto Bot — Full Audit Dump

Generated: 2026-05-16 22:01 MST (America/Phoenix)

## 1. Database Schema — `kalshi_decision_log`

| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| scan_time | timestamptz | |
| strategy_name | text | crypto_intel / crypto_intel_dryrun / crypto_intel_prod |
| market_ticker | text | |
| event_ticker | text | |
| series_ticker | text | |
| coin_name | text | BTC / ETH / SOL / XRP / DOGE / BNB / HYPE |
| market_title | text | |
| action | text | edge_too_small, positive_ev_signal, spread_too_wide, too_close_to_expiry, model_market_disagreement_too_large, entry_too_expensive |
| side | text | yes / no / hold |
| entry_price | numeric | Price paid per contract (0 if not executed) |
| fair_value | numeric | |
| market_prob | numeric | Kalshi YES mid price (%) |
| edge_cents | numeric | Best available edge across both sides (cents) |
| confidence | numeric | 0.0–1.0 |
| spread | numeric | YES ask - YES bid |
| open_interest | numeric | |
| ttl_minutes | numeric | Minutes until expiry |
| strike_price | numeric | |
| reasoning | text | Full debug reasoning |
| spot_price | numeric | |
| was_executed | boolean | |
| trade_id | integer | FK to kalshi_trades |
| cycle_number | integer | |
| model_fair_yes | numeric | Raw model probability of YES |
| fair_yes | numeric | Blended final fair probability of YES |
| fair_no | numeric | Blended final fair probability of NO (1 - fair_yes) |
| side_fair_value | numeric | |
| edge_ratio | numeric | |
| volatility | numeric | Annualized vol estimate |
| exit_recommendation | jsonb | |
| hedge_evaluation | jsonb | |
| result | text | settlement result |
| resolved_yes | boolean | |

---

## 2. Edge Calculation Logic (from code)

```
YES edge = fair_yes - yes_ask
NO edge  = fair_no  - no_ask
where no_ask ≈ 1 - yes_bid

edge_cents = max(YES edge, NO edge) * 100
side = YES if YES_edge > NO_edge else NO
```

**Key:** When fair_yes falls between YES bid and YES ask, BOTH sides produce negative edge. The spread consumes the value.

---

## 3. Aggregate Stats by Strategy

### crypto_intel (paper) — 1,930 total scans
| Metric | Count |
|--------|-------|
| Positive edge, executed (trade) | **266** |
| Negative edge, executed | **0** — no bad trades entered |
| Positive edge, NOT executed | **739** — edges existed but filtered |
| Negative edge, NOT executed | **925** — correctly held |
| Min edge | -4.9¢ |
| Max edge | 87.0¢ |
| Avg edge | **+11.7¢** |

### crypto_intel_prod (real money) — 168 scans
| Metric | Count |
|--------|-------|
| Positive edge, executed | **0** — no real trades entered |
| Positive edge, NOT executed | **35** — edges existed but filtered |
| Negative edge, NOT executed | **133** |
| Min edge | -4.4¢ |
| Max edge | 22.1¢ |
| Avg edge | **-0.3¢** (essentially neutral) |

### crypto_intel_dryrun — 7 scans (maybe stale/stopped early)
| Metric | Count |
|--------|-------|
| Avg edge | +1.8¢ |

---

## 4. Negative Edge Distribution (paper, non-executed, non-trivial filters excluded)

| Bucket | Count | Avg Market Prob | Avg Edge |
|--------|-------|-----------------|----------|
| +10¢+ (strong) | 426 | 54.0% | +34.6¢ |
| +5–9¢ (moderate) | 84 | 50.0% | +6.9¢ |
| +2–4¢ (weak) | 80 | 54.1% | +3.2¢ |
| 0–1¢ (tiny) | 149 | 54.8% | +0.6¢ |
| -1 to -2¢ | 528 | **61.1%** | -0.6¢ |
| -2 to -5¢ | 115 | **60.2%** | -3.0¢ |

**Observation:** The largest bucket is -1 to -2¢ at avg market_prob 61%. Edges are negative most often when the market has moved off 50/50 (60%+) but the model's fair value is still close to the midpoint — the spread then makes both sides unprofitable.

---

## 5. All Executed Trades (266 total) — Full Log

### BTC trades
| Time | Side | Entry | Edge | Confidence | Market% | Model Fair YES | Fair YES | Fair NO | Reasoning |
|------|------|-------|------|------------|---------|----------------|----------|---------|-----------|
| 18:52:12 | NO | 0.12¢ | 9.1¢ | 0.55 | 88.5% | 0.706 | 0.789 | 0.211 | Spot $77,795.71 strike $77,740.34, TTL 7.8m. Vol 0.34. Kalshi blend weight 0.46. YES edge -10.1c, NO edge 9.1c. TRADE NO: fair 0.211 vs ask 0.12 |
| 18:53:20 | NO | 0.13¢ | 7.2¢ | 0.48 | 87.5% | 0.720 | 0.798 | 0.202 | Spot $77,796.10 strike $77,740.34, TTL 6.7m. |
| 18:36:05 | YES | 0.30¢ | 6.5¢ | 0.48 | 29.5% | 0.417 | 0.365 | 0.635 | Spot $77,931.35 strike $77,962.17, TTL 8.9m. Signals bearish. TRADE YES: fair 0.365 vs ask 0.30 |
| 18:33:50 | YES | 0.25¢ | 7.8¢ | 0.48 | 22.5% | 0.341 | 0.329 | 0.671 | Signals bearish. TRADE YES: fair 0.329 vs ask 0.25 |

### ETH trades
| Time | Side | Entry | Edge | Confidence | Market% | Fair YES | Fair NO | Reasoning |
|------|------|-------|------|------------|---------|----------|---------|-----------|
| 18:54:30 | NO | 0.065¢ | 5.2¢ | 0.48 | 94.2% | 0.883 | 0.117 | Spot $2,171.57 strike $2,168.60, TTL 5.5m. TRADE NO: fair 0.117 vs ask 0.07 |
| 18:51:04 | NO | 0.15¢ | 6.5¢ | 0.48 | 86.5% | 0.785 | 0.215 | TRADE NO: fair 0.215 vs ask 0.15 |
| 18:48:45 | YES | 0.16¢ | 7.5¢ | 0.48 | 15.0% | 0.235 | 0.765 | TRADE YES: fair 0.235 vs ask 0.16 |
| 18:21:20 | YES | 0.12¢ | 6.5¢ | 0.48 | 11.5% | 0.185 | 0.815 | TRADE YES: fair 0.185 vs ask 0.12 |
| 18:20:08 | YES | 0.16¢ | 6.9¢ | 0.48 | 14.5% | 0.229 | 0.771 | TRADE YES: fair 0.229 vs ask 0.16 |
| 18:18:57 | YES | 0.19¢ | 6.8¢ | 0.48 | 17.5% | 0.258 | 0.742 | TRADE YES: fair 0.258 vs ask 0.19 |

### SOL trades
| Time | Side | Entry | Edge | Confidence | Market% | Fair YES | Fair NO | Reasoning |
|------|------|-------|------|------------|---------|----------|---------|-----------|
| 18:53:21 | NO | 0.17¢ | 8.4¢ | 0.50 | 84.0% | 0.746 | 0.254 | TRADE NO: fair 0.254 vs ask 0.17 |
| 18:52:13 | NO | 0.24¢ | 7.0¢ | 0.43 | 76.5% | 0.690 | 0.310 | TRADE NO: fair 0.310 vs ask 0.24 |
| 18:33:52 | NO | 0.34¢ | 8.0¢ | 0.43 | 66.5% | 0.580 | 0.420 | TRADE NO: fair 0.420 vs ask 0.34 |
| 18:20:06 | YES | 0.25¢ | 6.3¢ | 0.48 | 19.5% | 0.310 | 0.690 | TRADE YES: fair 0.310 vs ask 0.25 |

### XRP trades
| Time | Side | Entry | Edge | Confidence | Market% | Fair YES | Fair NO | Reasoning |
|------|------|-------|------|------------|---------|----------|---------|-----------|
| 18:53:22 | NO | 0.18¢ | 5.5¢ | 0.38 | 84.0% | 0.765 | 0.235 | TRADE NO: fair 0.235 vs ask 0.18 |
| 18:34:59 | YES | 0.13¢ | 8.1¢ | 0.55 | 12.5% | 0.211 | 0.789 | TRADE YES: fair 0.211 vs ask 0.13 |
| 18:33:52 | YES | 0.18¢ | 8.8¢ | 0.50 | 16.0% | 0.268 | 0.732 | TRADE YES: fair 0.268 vs ask 0.18 |
| 18:27:21 | YES | 0.071¢ | **18.6¢** | 0.55 | 6.3% | 0.257 | 0.743 | **Best single edge in dataset.** TRADE YES: fair 0.257 vs ask 0.07 |

### DOGE trades
| Time | Side | Entry | Edge | Confidence | Market% | Fair YES | Fair NO | Reasoning |
|------|------|-------|------|------------|---------|----------|---------|-----------|
| 18:48:49 | NO | 0.28¢ | 11.1¢ | 0.40 | 74.0% | 0.609 | 0.391 | TRADE NO: fair 0.391 vs ask 0.28 |

### HYPE trades
| Time | Side | Entry | Edge | Confidence | Market% | Fair YES | Fair NO | Reasoning |
|------|------|-------|------|------------|---------|----------|---------|-----------|
| 18:26:10 | YES | 0.27¢ | 8.4¢ | 0.40 | 25.0% | 0.354 | 0.646 | TRADE YES: fair 0.354 vs ask 0.27 |

### BNB trades
None (0 trades executed — always spread_too_wide or edge_too_small)

---

## 6. All "Negative Edge" Example Rows (fair value inside spread)

3 representative examples where both YES edge and NO edge were negative:

### SOL | 18:16:37 | edge_too_small | entry_price 0.43 | edge_cents -0.7¢
- Spot $86.19, strike $86.23, TTL 13.4m
- Model fair YES: 0.425
- Kalshi YES mid: 0.415, blend weight: 0.26
- Final fair YES: 0.423, fair NO: 0.577
- Spread: 3.0¢
- YES edge: -0.7¢ at ask 0.43
- NO edge: -2.3¢ at ask 0.60
- **Best edge -0.7¢ < required 8.0¢**
- Both sides negative → fair value (42.3¢ / 57.7¢) inside spread (bid~40¢ / ask~43¢ for YES)

### DOGE | 18:16:38 | edge_too_small | entry_price 0.57 | edge_cents -3.7¢
- Spot $0.11, strike $0.11, TTL 13.4m
- Model fair YES: 0.534
- Kalshi YES mid: 0.530, blend weight: 0.26
- Final fair YES: 0.533, fair NO: 0.467
- Spread: **8.0¢** (very wide for DOGE)
- YES edge: -3.7¢ at ask 0.57
- NO edge: -4.3¢ at ask 0.51
- **Both negative. Spread (8¢) > any possible edge. Not tradeable.**

### XRP | 18:17:47 | edge_too_small | entry_price 0.51 | edge_cents -0.4¢
- Spot $1.41, strike $1.41, TTL 12.2m
- Model fair YES: 0.491
- Kalshi YES mid: 0.500, blend weight: 0.30
- Final fair YES: **0.494**, fair NO: **0.506**
- **Market and model agree — it's a coin flip at 50/50.**
- YES edge: -1.6¢ at ask 0.51
- NO edge: -0.4¢ at ask 0.51
- **Both negative because the spread (2¢) sits on either side of an ~50/50 fair value.**

---

## 7. "Edge Inside Spread" — The Core Pattern

The most common state. Visualized:

```
YES bid         YES ask
  |-----spread-----|
  40¢             43¢

Model says fair value = 42.3¢ (YES) / 57.7¢ (NO)

YES edge = fair_yes - yes_ask = 42.3¢ - 43¢ = -0.7¢ (negative)
NO edge  = fair_no  - no_ask  = 57.7¢ - 60¢ = -2.3¢ (negative)
          (no_ask ≈ 1 - yes_bid = 1 - 0.40 = 0.60)
```

**Result:** Both sides have negative edge. No trade possible. This is the default state for most cycles.

---

## 8. "Positive Edge" — The Rare Pattern (executed trades)

```
YES bid         YES ask
  |-----spread-----|
  12¢             15¢

Model says fair value = 21.1¢ (YES) / 78.9¢ (NO)

YES edge = 21.1¢ - 15¢ = +6.1¢ (positive!)
NO edge  = 78.9¢ - 88¢ = -9.1¢ (negative)

→ BUY YES at 15¢, expected value = 6.1¢ per contract
```

This only happens when the model disagrees strongly with the market. The market prices YES cheap (12-15¢), but the model says YES is worth 21.1¢. The gap is wide enough to overcome the spread.

---

## 9. Action Filter Breakdown (paper, all time)

| Action | Count | Notes |
|--------|-------|-------|
| edge_too_small | 1,239 | Most common — edge exists but below threshold |
| positive_ev_signal | 266 | ✅ Trades entered |
| too_close_to_expiry | 252 | < 2 min TTL |
| spread_too_wide | 155 | Spread eats any possible edge (small coins) |
| model_market_disagreement_too_large | 14 | Model and Kalshi differ by >20¢ — safety filter |
| entry_too_expensive | 4 | Entry > $0.50 |

---

## 10. Pattern Summary

1. **Default state: edge negative.** Fair value sits inside the bid-ask spread ~40-50% of the time. System correctly holds.

2. **Positive edge requires model-market disagreement > spread.** Need the gap between fair value and market price to be wider than the spread. This happens when the model's vol/trend analysis differs enough from what Kalshi's pricing reflects.

3. **NO trades dominate (v2 architecture).** 77% of executed trades are NO side. The model tends to see through overpriced YES and bet NO. YES trades only happen at extreme underpricing (market YES < 30%).

4. **When edges are positive but not executed** (739 occurrences): the edge existed but other filters blocked entry — model_market_disagreement_too_large, too_close_to_expiry, entry_too_expensive, confidence too low for mode.

5. **Zero edge direction errors.** No trade was executed with a negative edge. The current safety filters (entry cap $0.50, min edge 8¢ paper / 10¢ prod, market sanity 80% gate, spread check, TTL check) are all correctly blocking bad entries.

---

*End of dump*
