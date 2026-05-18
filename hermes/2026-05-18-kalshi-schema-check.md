# Schema migration timing check

**Generated:** 2026-05-18T09:38:00-07:00

## Query A — kalshi_trades column population by day

| day | trades | has_confidence | has_fair_value | has_edge_cents | distinct_strategies |
| --- | --- | --- | --- | --- | --- |
| 2026-05-16 | 450 | 445 | 445 | 445 | 4 |
| 2026-05-17 | 106 | 104 | 104 | 104 | 2 |
| 2026-05-18 | 69 | 69 | 69 | 69 | 1 |

## Query B — kalshi_decision_log new-column population by day

| day | scans | has_model_fair_yes | has_blended_fair_yes | has_fair_no | has_side_fair_value | has_edge_ratio | has_volatility | has_path_metrics | distinct_strategies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-16 | 2616 | 1197 | 1197 | 1197 | 1177 | 1623 | 1197 | 0 | 3 |
| 2026-05-17 | 10570 | 8230 | 8230 | 8230 | 8008 | 10563 | 8230 | 3700 | 2 |
| 2026-05-18 | 3416 | 2716 | 2716 | 2716 | 2643 | 3416 | 2716 | 1898 | 1 |

## Query C — strategy split

| strategy_name | trades | last_24h | last_7d | earliest | latest |
| --- | --- | --- | --- | --- | --- |
| crypto_intel | 376 | 110 | 376 | 2026-05-16 15:22:33-07 | 2026-05-18 05:04:31-07 |
| sports_intel | 179 | 0 | 179 | 2026-05-16 13:35:29-07 | 2026-05-16 16:31:36-07 |
| crypto_intel_prod | 65 | 57 | 65 | 2026-05-16 16:55:39-07 | 2026-05-17 18:51:41-07 |
| spread_fishing | 5 | 0 | 5 | 2026-05-16 13:06:54-07 | 2026-05-16 13:06:54-07 |

## Notes

- **New columns appear on May 16** for decision_log rows (model_fair_yes, fair_yes, fair_no, side_fair_value, volatility all have non-NULL values starting day 1 of the window), but coverage is partial: only 1,197 of 2,616 scans (46%) on May 16. This rises to 78% on May 17 and 80% on May 18.

- **path_metrics first appears on May 17** — consistent with the Phase 1 path tracking deployment on 2026-05-17. Coverage: 35% of scans (3,700/10,570) on May 17, 56% on May 18.

- **kalshi_trades columns**: 5 trades on May 16 and 2 on May 17 have NULL confidence/predicted_fair_value/edge_cents. These are likely auto-reconciled trades (inserted from Kalshi order history, not from the analyzer pipeline) or legacy entries that predate the new columns.

- **edge_ratio** has the highest coverage: 1,623/2,616 (62%) on May 16, rising to near-100% (10,563/10,570) on May 17 and 100% on May 18. This suggests it was populated by an earlier version of the analyzer code that didn't yet write the probability-model fields.

- **sports_intel** and **spread_fishing** strategies are inactive — zero trades in the last 7 days. Only crypto_intel (paper) and crypto_intel_prod (production) are currently active.

- **crypto_intel_prod** has 65 trades in 14 days, with 57 (88%) in the last 24 hours — the production scanner trades are overwhelmingly recent, consistent with the filter relaxation deployed around May 17.

- **Column `path_metrics` is NULL for all rows on May 16** (pre-deployment). Column `has_path_metrics` goes from 0 on May 16 to 3,700 on May 17 — clean cutover.
