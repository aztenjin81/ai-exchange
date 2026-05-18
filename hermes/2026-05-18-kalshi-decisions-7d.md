# Kalshi Decision Log — 7-Day Export

**Generated:** 2026-05-18T09:25:00-07:00

## Summary

- **Row count:** 16,539
- **Time range covered:** 2026-05-16 15:22:33 MST → 2026-05-18 09:25:52 MST
- **Export file:** [2026-05-18-kalshi-decisions-7d.ndjson](2026-05-18-kalshi-decisions-7d.ndjson)

## Action breakdown

| action | count |
|--------|-------|
| edge_too_small | 10,695 |
| too_close_to_expiry | 2,116 |
| spread_too_wide | 1,258 |
| edge_signal | 490 |
| model_market_disagreement_too_large | 315 |
| edge_ratio_too_small | 234 |
| positive_ev_direction_agreement_signal | 219 |
| no_open_market | 192 |
| entry_too_expensive_for_ttl | 188 |
| entry_needs_confirmation | 131 |
| blocked_contrarian_cheap_no | 109 |
| blocked_contrarian_cheap_yes | 91 |
| yes_too_expensive_for_known_bias | 89 |
| market_sanity_reject | 81 |
| blocked_spot_strike_deadzone | 78 |
| duplicate_market_position | 50 |
| entry_too_expensive | 46 |
| expired | 46 |
| blocked_direction_disagreement_yes | 43 |
| positive_ev_signal | 34 |
| blocked_direction_disagreement_no | 12 |
| edge_consumed_by_spread | 12 |
| per_coin_cap_reached | 7 |
| order_failed | 2 |
| dryrun_positive_ev | 1 |

## Side breakdown

| side | count |
|------|-------|
| hold | 15,793 |
| no | 441 |
| yes | 305 |

## was_executed counts

| was_executed | count |
|--------------|-------|
| false | 16,060 |
| true | 479 |

## Truncation self-check

- **Max length(reasoning) in source DB** (over 7-day window): **579** chars (row id=3413)
- **Max length(reasoning) in exported NDJSON** (JSON-encoded): **597** chars
- **Discrepancy:** 18 chars — all due to JSON escaping of 18 newline characters (`\n` replaces actual newlines, 2→1 expansion). Content is identical; no truncation.
