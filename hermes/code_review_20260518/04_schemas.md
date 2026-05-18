## kalshi_trades

```
                                       Table "public.kalshi_trades"
        Column        |           Type           | Collation | Nullable |              Default
----------------------+--------------------------+-----------+----------+-----------------------------------
 id                   | integer                  |           | not null | nextval('kalshi_trades_id_seq'::regclass)
 portfolio_id         | integer                  |           |          |
 market_ticker        | text                     |           |          |
 event_ticker         | text                     |           |          |
 series_ticker        | text                     |           |          |
 market_title         | text                     |           |          |
 side                 | text                     |           |          |
 entry_price          | numeric                  |           |          |
 exit_price           | numeric                  |           |          |
 quantity             | integer                  |           |          |
 entry_time           | timestamp with time zone |           |          |
 exit_time            | timestamp with time zone |           |          |
 pnl                  | numeric                  |           |          |
 strategy_name        | text                     |           |          |
 strategy_version     | integer                  |           |          |
 status               | text                     |           |          |
 exit_reason          | text                     |           |          |
 notes                | text                     |           |          |
 fill_price           | numeric                  |           |          |
 fill_time            | timestamp with time zone |           |          |
 confidence           | numeric                  |           |          |
 reasoning_json       | jsonb                    |           |          |
 predicted_fair_value | numeric                  |           |          |
 edge_cents           | numeric                  |           |          |
 data_sources         | jsonb                    |           |          |
 kalshi_order_id      | text                     |           |          |
 entry_fee            | numeric                  |           |          |
 exit_fee             | numeric                  |           |          |
 spread_paid          | numeric                  |           |          |
 net_pnl              | numeric                  |           |          |
```

**Indexes:**
- `kalshi_trades_pkey` PRIMARY KEY, btree (id)
- `idx_trades_market_ticker` btree (market_ticker)
- `idx_trades_order_id` btree (kalshi_order_id)
- `idx_trades_strategy_status` btree (strategy_name, status)

**Check constraints:**
- (none)

**Foreign-key constraints:**
- (none)

---

## kalshi_decision_log

```
                                     Table "public.kalshi_decision_log"
      Column       |           Type           | Collation | Nullable | Default
-------------------+--------------------------+-----------+----------+---------
 id                | integer                  |           | not null | nextval('kalshi_decision_log_...')
 market_ticker     | text                     |           |          |
 event_ticker      | text                     |           |          |
 coin_name         | text                     |           |          |
 strategy_name     | text                     |           |          |
 action            | text                     |           |          |
 side              | text                     |           |          |
 entry_price       | numeric                  |           |          |
 edge_cents        | numeric                  |           |          |
 edge_ratio        | numeric                  |           |          |
 market_prob       | numeric                  |           |          |
 model_fair_yes    | numeric                  |           |          |
 fair_yes          | numeric                  |           |          |
 fair_no           | numeric                  |           |          |
 confidence        | numeric                  |           |          |
 volatility        | numeric                  |           |          |
 spread            | numeric                  |           |          |
 open_interest     | numeric                  |           |          |
 ttl_minutes       | integer                  |           |          |
 strike_price      | numeric                  |           |          |
 spot_price        | numeric                  |           |          |
 scan_time         | timestamp with time zone |           |          | now()
 reasoning         | jsonb                    |           |          |
 trade_id          | integer                  |           |          |
 was_executed      | boolean                  |           |          |
 resolved_yes      | boolean                  |           |          |
 result            | text                     |           |          |
 path_metrics      | jsonb                    |           |          |
```

**Indexes:**
- `kalshi_decision_log_pkey` PRIMARY KEY, btree (id)
- `idx_dlog_market_ticker` btree (market_ticker)
- `idx_dlog_scan_time` btree (scan_time)
- `idx_dlog_strategy` btree (strategy_name)
- `idx_dlog_trade_id` btree (trade_id)

**Check constraints:**
- (none)

**Foreign-key constraints:**
- (none)

---

## kalshi_portfolio

```
                                     Table "public.kalshi_portfolio"
      Column      |           Type           | Collation | Nullable |               Default
------------------+--------------------------+-----------+----------+-------------------------------------
 id               | integer                  |           | not null | nextval('kalshi_portfolio_id_seq'...)
 name             | text                     |           |          |
 current_balance  | numeric                  |           |          |
 starting_balance | numeric                  |           |          |
 created_at       | timestamp with time zone |           |          | now()
 total_realized_pnl | numeric                |           |          |
 win_count        | integer                  |           |          |
 loss_count       | integer                  |           |          |
```

**Indexes:**
- `kalshi_portfolio_pkey` PRIMARY KEY, btree (id)
