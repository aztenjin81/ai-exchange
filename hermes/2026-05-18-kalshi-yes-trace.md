# Kalshi YES Trade Trace — Worst Loss

**Generated:** 2026-05-18T09:26:00-07:00

## 1. Target trade row

Full `kalshi_trades` row for the worst-loss closed YES trade.

```
id: 209
portfolio_id: 1
market_ticker: KXBNB15M-26MAY161915-15
event_ticker: KXBNB15M-26MAY161915
series_ticker: KXBNB15M
market_title: Crypto 15-min BNB
side: yes
entry_price: 0.5100
exit_price: 0.0000
quantity: 82
entry_time: 2026-05-16 16:05:11.025394-07
exit_time: 2026-05-16 16:15:13.417192-07
pnl: -41.82
strategy_name: crypto_intel
strategy_version: 
status: closed
exit_reason: finalized(result=no)
notes: 
fill_price: 
fill_time: 
confidence: 0.55
reasoning_json: ["Momentum: 5/8 recent windows resolved YES → baseline 60%", "Uptrend — momentum favors YES", "Market pricing YES at 41.5% — edge=18.5¢ vs baseline", "Spread: 19.0¢ | OI: 160 | TTL: 10m", "Spot: $656.26 (-0.08% from strike)"]
predicted_fair_value: 0.6
edge_cents: 18.5
data_sources: {"spot": "coinbase", "kalshi": "orderbook"}
kalshi_order_id: 
entry_fee: 0
exit_fee: 0
spread_paid: 
net_pnl: -41.82
```

## 2. Originating decision log row

Full `kalshi_decision_log` row linked by `trade_id=209`.

```
id: 272
scan_time: 2026-05-16 16:05:11.038386-07
strategy_name: crypto_intel
market_ticker: KXBNB15M-26MAY161915-15
event_ticker: KXBNB15M-26MAY161915
series_ticker: KXBNB15M
coin_name: BNB
market_title: BNB price up in next 15 mins?
action: edge_signal
side: yes
entry_price: 0.51
fair_value: 0.6
market_prob: 41.5
edge_cents: 18.5
confidence: 0.55
spread: 
open_interest: 159.63
ttl_minutes: 9.817126616666666
strike_price: 656.76
reasoning: Momentum: 5/8 recent windows resolved YES → baseline 60%
Uptrend — momentum favors YES
Market pricing YES at 41.5% — edge=18.5¢ vs baseline
Spread: 19.0¢ | OI: 160 | TTL: 10m
Spot: $656.26 (-0.08% from strike)
spot_price: 656.265
was_executed: t
trade_id: 209
cycle_number: 6
model_fair_yes: 
fair_yes: 
fair_no: 
side_fair_value: 
edge_ratio: 
volatility: 
exit_recommendation: 
hedge_evaluation: 
result: no
resolved_yes: f
path_metrics: 
```

## 3. Pre-entry context

Every other `kalshi_decision_log` row for `KXBNB15M-26MAY161915-15` in the 30 minutes before the target trade's `entry_time` (16:05:11 MST), in chronological order.

---

### Row id=251 — scan_time=2026-05-16 16:00:07 MST (5m 4s before entry)

```
id: 251
scan_time: 2026-05-16 16:00:07.850063-07
strategy_name: crypto_intel
market_ticker: KXBNB15M-26MAY161915-15
event_ticker: KXBNB15M-26MAY161915
series_ticker: KXBNB15M
coin_name: BNB
market_title: BNB price up in next 15 mins?
action: edge_consumed_by_spread
side: hold
entry_price: 0
fair_value: 0.5
market_prob: 50.0
edge_cents: 10.0
confidence: 0
spread: 0.78
open_interest: 0.0
ttl_minutes: 14.870290083333334
strike_price: 0
reasoning: Momentum: 5/8 recent windows resolved YES → baseline 60%
Uptrend — momentum favors YES
Market pricing YES at 50.0% — edge=10.0¢ vs baseline
Spread: 78.0¢ | OI: 0 | TTL: 15m
Gross edge 10.0¢ but spread 78.0¢ consumes it
spot_price: 
was_executed: f
trade_id: 
cycle_number: 6
model_fair_yes: 
fair_yes: 
fair_no: 
side_fair_value: 
edge_ratio: 
volatility: 
exit_recommendation: 
hedge_evaluation: 
result: no
resolved_yes: f
path_metrics: 
```

---

### Row id=258 — scan_time=2026-05-16 16:02:37 MST (2m 34s before entry)

```
id: 258
scan_time: 2026-05-16 16:02:37.384903-07
strategy_name: crypto_intel
market_ticker: KXBNB15M-26MAY161915-15
event_ticker: KXBNB15M-26MAY161915
series_ticker: KXBNB15M
coin_name: BNB
market_title: BNB price up in next 15 mins?
action: edge_signal
side: yes
entry_price: 0.49
fair_value: 0.6
market_prob: 43.5
edge_cents: 16.5
confidence: 0.55
spread: 
open_interest: 120.63
ttl_minutes: 12.37928445
strike_price: 656.76
reasoning: Momentum: 5/8 recent windows resolved YES → baseline 60%
Uptrend — momentum favors YES
Market pricing YES at 43.5% — edge=16.5¢ vs baseline
Spread: 11.0¢ | OI: 121 | TTL: 12m
Spot: $656.42 (-0.05% from strike)
spot_price: 656.425
was_executed: t
trade_id: 197
cycle_number: 6
model_fair_yes: 
fair_yes: 
fair_no: 
side_fair_value: 
edge_ratio: 
volatility: 
exit_recommendation: 
hedge_evaluation: 
result: no
resolved_yes: f
path_metrics: 
```

---

### Row id=265 — scan_time=2026-05-16 16:04:04 MST (1m 7s before entry)

```
id: 265
scan_time: 2026-05-16 16:04:04.948604-07
strategy_name: crypto_intel
market_ticker: KXBNB15M-26MAY161915-15
event_ticker: KXBNB15M-26MAY161915
series_ticker: KXBNB15M
coin_name: BNB
market_title: BNB price up in next 15 mins?
action: edge_signal
side: yes
entry_price: 0.47
fair_value: 0.6
market_prob: 44.5
edge_cents: 15.5
confidence: 0.55
spread: 
open_interest: 120.63
ttl_minutes: 10.9186197
strike_price: 656.76
reasoning: Momentum: 5/8 recent windows resolved YES → baseline 60%
Uptrend — momentum favors YES
Market pricing YES at 44.5% — edge=15.5¢ vs baseline
Spread: 5.0¢ | OI: 121 | TTL: 11m
Spot: $656.30 (-0.07% from strike)
spot_price: 656.305
was_executed: t
trade_id: 203
cycle_number: 6
model_fair_yes: 
fair_yes: 
fair_no: 
side_fair_value: 
edge_ratio: 
volatility: 
exit_recommendation: 
hedge_evaluation: 
result: no
resolved_yes: f
path_metrics: 
```

## 4. Schema notes

Numeric field interpretation based on actual values in the rows above.

### kalshi_trades numeric fields

| Field | Storage format | Evidence |
|-------|---------------|----------|
| id | integer (count) | value 209 |
| portfolio_id | integer (count) | value 1 |
| entry_price | dollars (0–1) | value 0.5100 = $0.51 |
| exit_price | dollars (0–1) | value 0.0000 |
| quantity | integer (count) | value 82 = 82 contracts |
| pnl | dollars | value -41.82 = -$41.82 |
| strategy_version | integer (nullable count) | value null |
| confidence | decimal (0–1) | value 0.55 = 55% |
| predicted_fair_value | decimal (0–1) | value 0.6 = 60% |
| edge_cents | cents | value 18.5 = 18.5¢ |
| entry_fee | dollars | value 0 = $0.00 |
| exit_fee | dollars | value 0 = $0.00 |
| spread_paid | dollars (nullable) | value null/empty |
| net_pnl | dollars | value -41.82 = -$41.82 |

### kalshi_decision_log numeric fields

| Field | Storage format | Evidence |
|-------|---------------|----------|
| id | integer (count) | value 272 |
| entry_price | dollars (0–1) | value 0.51 = $0.51 |
| fair_value | decimal (0–1) | value 0.6 = 60% probability |
| market_prob | percent (0–100) | value 41.5 = 41.5% |
| edge_cents | cents | value 18.5 = 18.5¢ (also 10.0, 16.5, 15.5 in pre-context) |
| confidence | decimal (0–1) | value 0.55 = 55% |
| spread | dollars (0–1) | value 0.78 = $0.78 (from row id=251) |
| open_interest | dollars (contract face value) | value 159.63 = $159.63 OI (also 120.63, 0.0) |
| ttl_minutes | minutes (float) | value 9.82 minutes (also 14.87, 12.38, 10.92 in pre-context) |
| strike_price | dollars | value 656.76 = $656.76 (0 in row 251 where spread consumed edge) |
| spot_price | dollars (nullable) | value 656.265 = $656.265 (null in row 251) |
| cycle_number | integer (count) | value 6 |
| model_fair_yes | decimal (0–1) (nullable) | all null in this trace (v1-era rows lack this field) |
| fair_yes | decimal (0–1) (nullable) | all null in this trace |
| fair_no | decimal (0–1) (nullable) | all null in this trace |
| side_fair_value | decimal (0–1) (nullable) | all null in this trace |
| edge_ratio | decimal (0–1) (nullable) | all null in this trace |
| volatility | decimal (annualized) (nullable) | all null in this trace |
