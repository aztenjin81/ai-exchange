---
date: 2026-05-19
project: kalshi-crypto-15min-bot
status: shipped
---

# Kalshi Bot — 2026-05-19 session: filter tuning, calibration, depth ingestion

Day 3 of active work on the paper scanner. Today moved from "triaging
old issues" to "actively tuning behavior from data." Six commits, one
schema migration, two doc updates. Paper equity went from −$108
overnight to **+$85** between calibration deploy and end of session.

## Headline numbers

- **Overnight (5/18 18:00 → 5/19 07:00 MST):** 89 trades, 23.6% WR, **−$107.98**
- **Today after deploys (5/19 ~14:00 → ~16:00 UTC):** 18 trades, 5 wins, **+$85.18**
- **Paper equity:** $10,844.91 (starting_balance $10k + total_realized_pnl $844.91)
- **Trade count drop:** counterfactual replay shows new filter set
  would have cut overnight to 48 trades (89 → 48) at **+$69 vs −$108**

## What shipped (commit chain)

| Commit | Title | Effect |
|---|---|---|
| `6b55eb8` | tighten BTC/SOL NO floors, flat-block YES on 5 coins | Asymmetric per-side per-coin filter overrides |
| `557c163` | block NO entry ≥ 0.50 due to model calibration error | Hard guard mirroring `YES_MAX_ENTRY_PRICE` |
| `94277d9` | empirical calibration of fair_yes against realized outcomes | Maps predicted → realized via 20-bin LUT |
| `0f0d7c5` | kalshi_client adds exchange status + batch orderbook endpoints | New REST methods (pure additions) |
| `b7d1c9a` | fetch orderbook depth + exchange-status pre-flight per scan | Scanner integration + `orderbook_jsonb` logging |

## Findings that drove the changes

### 1. Counterfactual projection systematically overshoots realized

When 32ed036 (asymmetric NO floor, deployed 5/18 PM) was evaluated on
the next overnight window, realized win rates undershot the projection
by 35-50 points:

| Coin × Side | Projected WR | Realized WR | Realized P&L |
|---|---|---|---|
| ETH NO | 64% | 47% | +$241 |
| XRP NO | 74% | 22% | +$14 |
| BTC NO | 72% | **29%** | **−$139** |
| SOL NO | 64% | **17%** | **−$118** |

Survivorship-bias hypothesis: the counterfactual was built from the
*rejected* signal pool, which was filtered for everything *except* the
loosened floor. Once we loosened the floor, the marginal signals that
came through weren't represented in the reject sample.

### 2. Model has systematic calibration bias against YES at high fair_yes

Audit on 16,099 decision_log rows with `resolved_yes` populated:

| Raw `fair_yes` bucket | n | Predicted | Realized | Shift |
|---|---|---|---|---|
| 0.30 | 1511 | 0.351 | 0.338 | −0.013 |
| 0.50 | 1907 | 0.549 | 0.582 | +0.033 |
| 0.65 | 828 | 0.626 | 0.691 | **+0.065** |
| 0.72 | 651 | 0.725 | 0.800 | **+0.075** |
| 0.85 | 1248 | 0.851 | 0.884 | +0.033 |

Mild overpredict at low fair_yes (−1 to −2pts in 0.10-0.40), strong
underpredict at high fair_yes (+4 to +7.5pts in 0.45-0.95). This bias
explains the historical −$1,642 NO-entry-≥0.50 leak: model sees its
largest "edge" precisely where it is most miscalibrated.

### 3. Entry-price bucket is a clean predictor over full history

NO trades sort cleanly by entry price (full history, all coins):

| Entry | n | WR | Σ P&L |
|---|---|---|---|
| <30c | 179 | 37% | +$2,657 |
| 30-40c | 36 | **64%** | +$843 |
| 40-50c | 29 | 41% | −$52 |
| **≥50c** | 59 | **36%** | **−$1,642** |

Pattern holds in *every coin individually* — BTC, ETH, SOL, XRP, BNB,
DOGE, HYPE all show NO ≥50c as a money pit. Even small samples (HYPE
n=4) show 0% WR at this bucket.

## Calibration mechanism

`_FAIR_YES_CALIBRATION` lives in `crypto_intel.py` after
`fair_yes_probability`. 20 control points `(predicted, realized)`
fit on full historical data. Strictly monotonic in y, so plain
piecewise-linear interpolation suffices — no Pool Adjacent
Violators step needed.

Application: in `analyze_crypto_market`, between the Kalshi blend
and downstream filters. `fair_yes_blend` is computed as before
(`model_fair_yes` + `kalshi_yes_mid`), then `fair_yes = calibrate_fair_yes(fair_yes_blend)`,
re-clamped to [0.01, 0.99]. `fair_no = 1 - fair_yes`. Edges propagate
through unchanged callers.

Side effects on edges in the dangerous region:
- raw `fair_yes` = 0.50 → calibrated 0.529 → NO edge tightens 3c
- raw `fair_yes` = 0.65 → calibrated 0.706 → NO edge tightens 6c
- raw `fair_yes` = 0.75 → calibrated 0.809 → NO edge tightens 6c

Decision log carries both raw and calibrated; the existing `fair_yes`
column captures the calibrated value (what the strategy sees), and the
`reasoning` text now includes the shift explicitly.

## Per-side asymmetric filters

`MIN_EDGE_BY_COIN_SIDE` now contains:
```python
('BTC',  'no'):  0.07,   # raised after BTC NO 29% WR overnight
('HYPE', 'no'):  0.03,
('SOL',  'no'):  0.07,   # raised after SOL NO 17% WR overnight
('ETH',  'no'):  0.03,   # confirmed winner, 47% WR overnight
('XRP',  'no'):  0.03,
('BTC',  'yes'): 0.99,   # flat-block — YES uniformly losing
('HYPE', 'yes'): 0.99,
('SOL',  'yes'): 0.99,
('ETH',  'yes'): 0.99,
('XRP',  'yes'): 0.99,
```

DOGE YES is preserved (was the only YES with positive P&L; small
sample). BNB is otherwise soft-disabled via `MIN_EDGE_BY_COIN['BNB'] = 0.99`.

`NO_MAX_ENTRY_PRICE = 0.50` cap added as defense-in-depth (commit `557c163`),
mirroring the existing `YES_MAX_ENTRY_PRICE = 0.40`. Both can be relaxed
once a few days of post-calibration data confirm the bias is genuinely
addressed at the source.

## Orderbook ingestion

Two new endpoints wired into the scanner:

- **`/exchange/status` pre-flight** at start of `scan_and_log`. If
  `trading_active=false`, writes a heartbeat with `status='exchange_paused'`
  and returns early — no decision-log rows generated during maintenance.

- **Batch `/markets/orderbooks`** call per cycle. Returns top-10
  levels per side per market. Folded into each market dict as
  `orderbook = {"yes_dollars": [[price, qty], ...], "no_dollars": [...]}`
  with best bid (highest price) at index 0 after client-side reversal.

New column `kalshi_decision_log.orderbook_jsonb` (JSONB) captures the
snapshot per evaluation. ~450 bytes/row, ~4.5 MB/day.

**Important caveat noted:** `/markets` quote and `/orderbook` best-bid
disagree by several cents at the moment (e.g. BTC: `/markets` yes_bid=0.26
vs `/orderbook` best yes_bid=0.31). Almost certainly an API-cache
freshness gap. Scanner still uses `/markets` quote for trading logic
in this commit; switching the source-of-truth is a separate decision
once the divergence pattern is characterized.

## Schema additions

```sql
ALTER TABLE kalshi_decision_log
  ADD COLUMN orderbook_jsonb JSONB;
```

This complements earlier additions in the day's chain (already deployed
across yesterday-today): `intended_side`, `yes_edge`, `no_edge`,
`code_version`, `path_pct_above`, `path_streak`, `path_crossings`,
`path_intra_vol`, `path_trend_per_min`, `path_twap_vs_strike`,
`btc_spot_at_decision`, `orderbook_jsonb`.

## Open work

- **Verify calibration impact** — first few days of post-94277d9
  data. If ETH NO holds at >40% WR with calibrated edges, calibration
  is doing its job and we can relax the `NO_MAX_ENTRY_PRICE` guard.

- **Per-coin calibration LUT** — global LUT shows HYPE has REVERSED
  bias (overpredicts YES). Worth investigating per-coin LUTs once
  there's another week of data.

- **`/markets` vs `/orderbook` quote divergence** — characterize the
  freshness gap, then decide whether to switch trading logic to
  orderbook-derived prices.

- **DOGE NO** — still bleeding overnight (13% WR, −$44). Not in the
  asymmetric override; falls through to `MIN_EDGE_BY_COIN['DOGE']=0.06`.
  Tighten to 0.07 if pattern persists tomorrow.

- **Sizing per coin × side** — once cohort EV is confirmed, the natural
  next lever is `SIZE_MULTIPLIER_BY_COIN_SIDE` to concentrate capital
  on confirmed-positive cohorts (ETH NO primarily). Not yet built.

- **Trade tape via WS** — `/markets/trades` exists as a REST endpoint
  too. Would give us flow direction signal we are entirely blind to.
  Separate worker, append-only table. Deferred to a later session.

## What I avoided

- Sizing up before EV is confirmed (user asked about it; answered "no").
- Implementing model-disagreement exits (acknowledged as "harder to
  paper trade" — would require synthesizing mid-window exit prices).
- Path-metric filters — sample size too small (24h, 31% coverage) to
  fit clean splits yet.
