# Orphan Trades (538, 539) — Full Context

## Full trade rows

```
id|portfolio_id|market_ticker|event_ticker|series_ticker|market_title|side|entry_price|exit_price|quantity|entry_time|exit_time|pnl|strategy_name|strategy_version|status|exit_reason|notes|fill_price|fill_time|confidence|reasoning_json|predicted_fair_value|edge_cents|data_sources|kalshi_order_id|entry_fee|exit_fee|spread_paid|net_pnl
538|1|KXSOL15M-26MAY171615-15|KXSOL15M-26MAY171615|||yes|0.2300|0.0000|2|2026-05-17 13:56:31-07|2026-05-17 14:50:16.947048-07|-0.46|crypto_intel_prod||closed|settled||||||||||||b959c5c1-cbd6-4ec5-ab48-fe48a7c6ce66|||||-0.46
539|1|KXDOGE15M-26MAY171615-15|KXDOGE15M-26MAY171615|||no|0.2400|0.0000|4|2026-05-17 13:56:31-07|2026-05-17 14:50:18.601409-07|-0.96|crypto_intel_prod||closed|settled||||||||||||df601830-7049-4ae2-8d7a-7a53f6229836|||||-0.96
```

Key observations:
- `series_ticker` is NULL for both
- `confidence` is NULL for both
- `predicted_fair_value` is NULL for both
- `edge_cents` is NULL for both
- `entry_fee`, `exit_fee`, `spread_paid` are all NULL
- Both have `kalshi_order_id` populated (they were real Kalshi orders)
- Both were auto-reconciled by the recovery script (same `entry_time` = `2026-05-17 13:56:31-07`)

## Decision log entries linked to these trades

No decision log rows have `trade_id IN (538, 539)`. The orphan trades have NO corresponding decision log entry — the `trade_id` column in `kalshi_decision_log` was never set for these.

## Trades in the same time window (13:50 - 14:10 MST)

```
id|strategy_name|series_ticker|side|entry_price|quantity|entry_time|exit_time|exit_reason|status|kalshi_order_id
534|crypto_intel|KXETH15M|no|0.2300|100|2026-05-17 13:56:13-07|||open|
535|crypto_intel|KXD OGE15M|no|0.2800|100|2026-05-17 13:56:16-07|||open|
536|crypto_intel_prod|KXDOGE15M|yes|0.1700|45|2026-05-17 13:56:30-07|2026-05-17 14:00:56-07|finalized(result=no)|closed|
537|crypto_intel_prod|KXDOGE15M|yes|0.1700|2|2026-05-17 13:56:31-07|2026-05-17 14:50:18.601409-07|settled|closed|b959c5c1-cbd6-4ec5-ab48-fe48a7c6ce66
538|crypto_intel_prod||yes|0.2300|2|2026-05-17 13:56:31-07|2026-05-17 14:50:16.947048-07|settled|closed|c74f99d2-25e5-4f86-a8e7-478e4187269a
539|crypto_intel_prod||no|0.2400|4|2026-05-17 13:56:31-07|2026-05-17 14:50:18.601409-07|settled|closed|df601830-7049-4ae2-8d7a-7a53f6229836
```

Note: trade 536 (same time, DOGE via crypto_intel_prod) has `series_ticker = 'KXDOGE15M'` and proper values. Trades 538/539 were inserted at the exact same second (13:56:31) but by a different code path.

## Decision log entries (13:50 - 14:10 MST)

Subset of the 136 decision log entries from this window. The key entries around the orphan trades:

```
    id|scan_time             |coin_name|action                          |side|entry_price|edge_cents|was_executed|trade_id
  9592|2026-05-17 13:56:30-07|DOGE    |positive_ev                     |yes |0.1700     |       5.0|t           |536
  9593|2026-05-17 13:56:33-07|DOGE    |already_have_open_market_position|hold|           |          |f           |
  9594|2026-05-17 13:56:34-07|SOL     |already_have_open_market_position|hold|           |          |f           |
  9595|2026-05-17 13:56:35-07|SOL     |already_have_open_market_position|hold|           |          |f           |
  9596|2026-05-17 13:56:36-07|ETH     |positive_ev                     |no  |0.2300     |       7.0|t           |534
  9597|2026-05-17 13:56:38-07|DOGE    |positive_ev                     |no  |0.2800     |       6.0|t           |535
  9598|2026-05-17 13:56:39-07|SOL     |positive_ev                     |no  |0.4900     |       3.2|t           |
  9599|2026-05-17 13:56:41-07|DOGE    |positive_ev                     |yes |0.1700     |       5.0|t           |
  ... (more entries)
```

Trade 536 (DOGE, series_ticker='KXDOGE15M') was logged correctly — it shows up in the decision_log with `trade_id=536` and `was_executed=t`.

Trade 538 and 539 do NOT appear in the decision log. The orphan path: these were inserted by the **auto-reconciliation** function at the end of `production_scan()`, not by the normal `log_decision()` → INSERT INTO `kalshi_trades` path. The `reconcile_missing_trades()` function in `kalshi-crypto-prod` fetches the last 10 Kalshi orders and inserts any not found in the DB. It uses a simple INSERT with only: `portfolio_id, market_ticker, side, entry_price, quantity, strategy_name, status, kalshi_order_id, entry_time`. It does NOT populate `series_ticker`, `confidence`, `predicted_fair_value`, `edge_cents`, or any of the decision-context fields.

## Root cause

The auto-reconciliation in `kalshi-crypto-prod` (`production_scan()` → end-of-cycle reconciliation) inserts a bare-bones trade row with only the fields that come from the Kalshi orders API response. Since the reconciliation bypasses `log_decision()`, none of the analytical fields (`series_ticker`, `confidence`, `edge_cents`, etc.) are populated. The decision_log is not updated either — no `trade_id` back-link exists.

The fix (already deployed in `harvest_outcomes()`) closes these orphan trades when their markets settle, but it doesn't retroactively populate the missing fields. To truly fix the root cause, the reconciliation code needs to either:
1. Reject orders that don't have a matching `decision_log` entry (these are orders placed outside the bot)
2. Look up the market metadata to populate `series_ticker`, `event_ticker`, etc.
3. Or skip reconciliation for orders that can't be linked to a decision (manual Kalshi trades)
