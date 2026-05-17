# Database Schema & State

Auto-exported 2026-05-17.

---


## kalshi_trades

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | NO | nextval('kalshi_trades_id_seq'::regclass) |
| portfolio_id | integer | YES |  |
| market_ticker | text | NO |  |
| event_ticker | text | YES |  |
| series_ticker | text | YES |  |
| market_title | text | YES |  |
| side | text | YES |  |
| entry_price | numeric | NO |  |
| exit_price | numeric | YES |  |
| quantity | integer | NO |  |
| entry_time | timestamp with time zone | YES | now() |
| exit_time | timestamp with time zone | YES |  |
| pnl | numeric | YES |  |
| strategy_name | text | YES |  |
| strategy_version | integer | YES |  |
| status | text | YES | 'open'::text |
| exit_reason | text | YES |  |
| notes | text | YES |  |
| fill_price | numeric | YES |  |
| fill_time | timestamp with time zone | YES |  |
| confidence | numeric | YES |  |
| reasoning_json | jsonb | YES |  |
| predicted_fair_value | numeric | YES |  |
| edge_cents | numeric | YES |  |
| data_sources | jsonb | YES |  |
| kalshi_order_id | text | YES |  |
| entry_fee | numeric | YES | 0 |
| exit_fee | numeric | YES | 0 |
| spread_paid | numeric | YES |  |
| net_pnl | numeric | YES |  |

**Rows:** 458


## kalshi_decision_log

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | NO | nextval('kalshi_decision_log_id_seq'::regclass) |
| scan_time | timestamp with time zone | YES | now() |
| strategy_name | text | NO | 'crypto_intel'::text |
| market_ticker | text | YES |  |
| event_ticker | text | YES |  |
| series_ticker | text | YES |  |
| coin_name | text | YES |  |
| market_title | text | YES |  |
| action | text | NO |  |
| side | text | YES |  |
| entry_price | numeric | YES |  |
| fair_value | numeric | YES |  |
| market_prob | numeric | YES |  |
| edge_cents | numeric | YES |  |
| confidence | numeric | YES |  |
| spread | numeric | YES |  |
| open_interest | numeric | YES |  |
| ttl_minutes | numeric | YES |  |
| strike_price | numeric | YES |  |
| reasoning | text | YES |  |
| spot_price | numeric | YES |  |
| was_executed | boolean | YES | false |
| trade_id | integer | YES |  |
| cycle_number | integer | YES |  |
| model_fair_yes | numeric | YES |  |
| fair_yes | numeric | YES |  |
| fair_no | numeric | YES |  |
| side_fair_value | numeric | YES |  |
| edge_ratio | numeric | YES |  |
| volatility | numeric | YES |  |
| exit_recommendation | jsonb | YES |  |
| hedge_evaluation | jsonb | YES |  |
| result | text | YES |  |
| resolved_yes | boolean | YES |  |

**Rows:** 6011


## kalshi_portfolio

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | NO | nextval('kalshi_portfolio_id_seq'::regclass) |
| created_at | timestamp with time zone | YES | now() |
| starting_balance | numeric | NO |  |
| current_balance | numeric | NO |  |
| total_realized_pnl | numeric | YES | 0 |
| total_unrealized_pnl | numeric | YES | 0 |
| win_count | integer | YES | 0 |
| loss_count | integer | YES | 0 |
| active | boolean | YES | true |

**Rows:** 1


## kalshi_strategy_params

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | NO | nextval('kalshi_strategy_params_id_seq'::regclass) |
| strategy_name | text | NO |  |
| version | integer | NO |  |
| params | jsonb | YES |  |
| notes | text | YES |  |
| created_at | timestamp with time zone | YES | now() |

**Rows:** 4


## kalshi_heartbeat

| Column | Type | Nullable | Default |
|---|---|---|---|
| strategy_name | text | NO |  |
| last_seen | timestamp with time zone | NO |  |
| status | text | NO | 'ok'::text |

**Rows:** 2


---
## Strategy Summary

| Strategy | Total Decisions | Executed Trades |
|---|---|---|
| crypto_intel | 5521 | 275 |
| crypto_intel_prod | 483 | 0 |
| crypto_intel_dryrun | 7 | 0 |

## Heartbeat

| Strategy | Last Seen | Status |
|---|---|---|
| crypto_intel_prod | 2026-05-17 08:54:44.829737-07:00 | ok |
| crypto_intel | 2026-05-17 08:54:44.827779-07:00 | ok |

## Portfolio

- Starting balance: $10000.00
- Current balance: $68.05
- Realized P&L: $1100.74
- Wins: 121, Losses: 150