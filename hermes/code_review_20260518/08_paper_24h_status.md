# Paper 24h Status — Initial

Generated: 2026-05-17 19:24 MST

## Status

Paper scanner (`kalshi-crypto-scanner`) resumed at **19:20 MST** on 2026-05-17.
All 5 priorities from the fix brief are complete:

1. **P1 — fair_yes_probability**: 0 mismatches across 30 sampled rows. Function correct.
2. **P2 — MIN_EDGE_BY_COIN**: Restored tiered values (BTC=10c, BNB/HYPE=8c, ETH/SOL/XRP/DOGE=4c). Deprecated `MIN_EDGE_CENTS` constant.
3. **P3 — Orphan reconciliation**: `parse_market_ticker()` helper added. INSERT now populates 12 fields instead of 8. Trades 538/539 backfilled.
4. **P4 — resolved_yes**: 3 random trades verified against Kalshi API — all consistent.
5. **P5 — Paper resumed**: Scanner running every 60s.

## Premilinary data (24h window, pre-pause + post-resume)

Paper trades in last 24h (includes old relaxed filters, pre-tiered MIN_EDGE):
- NO: 14 trades, 6 wins, -$8.41
- YES: 14 trades, 4 wins, -$3.18
- Total: -$11.59 on 28 trades

Decision actions (last 24h, paper):
- edge_too_small: 4,363 — dominating filter
- too_close_to_expiry: 894
- spread_too_wide: 507
- positive_ev trades executed: 30

## Scanner verification

Fresh scan cycle confirmed at 19:22 MST — all 7 coins analyzed. All decisions are `edge_too_small` under the new tiered thresholds, which is expected per the fix brief ("do not lower thresholds to get trades going").

## Code changes deployed

All changes committed and pushed to both repos:
- `~/.hermes/scripts/crypto_intel.py` — MIN_EDGE_BY_COIN tiered values
- `~/.hermes/scripts/kalshi-crypto-prod` — parse_market_ticker + reconciliation fix
- `~/hermes-vault/hermes/code_review_20260518/` — code review data package

## 24h report pending

Paper needs to run for 24 hours under the new thresholds to generate meaningful
post-fix data. The full 24h status report with trade counts by side and action
distribution will be committed here after 19:20 MST on 2026-05-18.
