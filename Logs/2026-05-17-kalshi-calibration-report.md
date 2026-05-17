# Kalshi Calibration Report — 2026-05-17

## Summary

Full model calibration analysis across v1 (edge_signal, 224 trades) and v2-on-paper (positive_ev_signal, 28 trades). Key finding: pure v1 was profitable at **+$820.47** (not +$978 — that was contaminated by 28 v2 trades), with systematic calibration issues the v2-on-paper data suggests may be worse in the new model.

---

## 1. v1 vs v2 P&L Split

The earlier +$978.80 number for crypto_intel was inflated by 28 trades that used v2 action labels. Pure v1:

| Group | Action | Trades | Wins | Losses | Win Rate | Net P&L | Avg/Trade |
|-------|--------|------:|----:|------:|:--------:|--------:|:---------:|
| **Pure v1** | edge_signal | 224 | 99 | 125 | 44.2% | **+$820.47** | +$3.66 |
| v2-on-paper | positive_ev_signal | 27 | 6 | 21 | 22.2% | +$65.62 | +$2.43 |
| v2-on-paper | positive_ev_direction_agreement_signal | 1 | 1 | 0 | 100% | +$35.89 | +$35.89 |

**Takeaway:** v1 is confirmed profitable with a sub-50% win rate. The wins were larger than losses — classic binary market asymmetry (buying at 30-40¢, winning at $1).

---

## 2. v1 Calibration — Systematic Overconfidence

Confidence buckets vs actual win rate (v1, edge_signal, N=224):

| Bucket | Predicted | Actual WR | N | Direction |
|:------:|:---------:|:---------:|:-:|:---------:|
| 4 | 0.35 | 0.75 | 4 | **OVER** (too pessimistic) |
| 5 | 0.43 | 0.53 | 17 | **OVER** (too pessimistic) |
| 6 | 0.53 | 0.41 | 106 | **UNDER** (too optimistic) |
| 7 | 0.63 | 0.43 | 93 | **UNDER** (too optimistic) |
| 8 | 0.70 | 0.25 | 4 | **UNDER** (too optimistic) |

The model is overconfident at **both ends** — too pessimistic near 0.35, too optimistic above 0.50. This is the signature of a model that underestimates variance (consistent with "jump risk not captured by realized vol" hypothesis).

**The 27-point gap in the highest-confidence bucket** (predicted 70%, actual 25%) is where real money is lost — the model was most confident about the predictions that were most wrong.

---

## 3. All Profit Came from NO Trades

| Side | Trades | Wins | Losses | Win Rate | Avg Win | Avg Loss | Total P&L |
|:----:|------:|----:|------:|:--------:|:-------:|:--------:|:---------:|
| **NO** | 135 | 69 | 66 | **51.1%** | +$57.82 | -$38.20 | **+$1,468.64** |
| YES | 89 | 30 | 59 | **33.7%** | +$23.26 | -$22.81 | -$648.17 |

v1 was **only profitable on NO trades**. YES trades lost money overall. This asymmetry is dramatic:
- NO avg win ($57.82) >> YES avg win ($23.26) — NO wins were 2.5x larger
- YES trades lost money despite the v1 model being supposedly calibrated for binary outcomes

Possible explanations:
- The v1 model's baseline (momentum-based) systematically favored fading high-probability YES markets (buying NO at cheap prices)
- When NO won, the payout was asymmetric (buying NO at 10-20¢, settling at $1)
- The NO-side win rate (51%) vs buy price explains the profitability

---

## 4. Per-Coin Breakdown

| Coin | Trades | Wins | Win Rate | Total P&L |
|:----:|:-----:|:---:|:--------:|:---------:|
| XRP | 32 | 16 | 50.0% | **+$359.58** |
| ETH | 32 | 15 | 46.9% | **+$253.55** |
| SOL | 31 | 17 | 54.8% | **+$245.00** |
| DOGE | 34 | 16 | 47.1% | **+$213.64** |
| HYPE | 30 | 12 | 40.0% | **-$41.40** |
| BNB | 30 | 12 | 40.0% | **-$46.73** |
| **BTC** | **35** | **11** | **31.4%** | **-$163.17** |

BTC has the most trades and the worst results — 31.4% actual YES rate vs 63% average predicted confidence. The model was most overconfident on BTC, which is ironic given BTC should have the most liquid and reliable data.

---

## 5. v2-on-Paper Calibration (N=28 — Small Sample Warning)

| Bucket | Predicted | Actual WR | N | Direction |
|:------:|:---------:|:---------:|:-:|:---------:|
| 4 | 0.38 | 1.00 | 1 | noise |
| 5 | 0.46 | 0.17 | 18 | **UNDER** (overconfident) |
| 6 | 0.54 | 0.29 | 7 | **UNDER** (overconfident) |
| 7 | 0.65 | 0.00 | 1 | noise |

**Brier score: 0.1654** (some skill — category: between coin flip and good)

v2 looks **worse** than v1 at the same confidence ranges (22.2% WR vs v1's 44.2% at similar confidences). But N=28 is tiny for calibration buckets. The Brier of 0.1654 says the model has directional skill but overstates its confidence.

**The fair_yes column is NULL for all v1 trades** (the old model didn't populate it), so Brier can only be computed for v2-on-paper.

---

## 6. v1 Calibration by TTL Bucket

| TTL | N | Actual WR | Avg Conf | Avg Edge(c) |
|:---:|:-:|:---------:|:--------:|:-----------:|
| >10m | 88 | 36.4% | 0.54 | 24.9¢ |
| 5-10m | 108 | 40.7% | 0.58 | 31.8¢ |
| <5m | 28 | **71.4%** | 0.57 | 38.6¢ |

The v1 model was **most accurate near expiry** (71.4% WR at <5m TTL). This is counterintuitive but makes sense given the blend weight was highest near expiry — the market knows more, and v1's momentum baseline aligned with market direction in late windows.

---

## 7. Calibration by Edge Tier

| Edge Tier | N | Actual WR | Avg Conf | Total P&L |
|:---------:|:-:|:---------:|:--------:|:---------:|
| 15c+ | 189 | 40.2% | 0.58 | +$1,002.60 |
| 10-15c | 18 | 50.0% | 0.55 | -$381.46 |
| 8-10c | 2 | 50.0% | 0.45 | +$10.65 |
| <8c | 15 | 66.7% | 0.44 | +$188.68 |

**Suspicious:** The 10-15c edge tier has 50% WR but **lost $381**. That suggests the losses were pathologically large in that bucket — a few big losing trades wiped out many small wins. Worth investigating which trades those were.

---

## 8. Overconfidence Hypotheses — Data Assessment

| Hypothesis | Supported? | Evidence |
|:-----------|:----------:|:---------|
| Vol estimates too low | **Likely** | Calibration shows overconfidence at both ends (buckets 4 AND 6-8), consistent with underestimating variance. Short-window realized vol systematically misses crypto's fat-tail jump risk. |
| Blend weight (now 20/75) swung too far | **Inconclusive** | v1 calibration predates the blend change — v1 used 80/97 blend, not 20/75. We have no calibration data for the new blend. |
| Selection bias | **Likely contributing** | The trades that fire are the ones where model and market disagree most — which are precisely the trades where the model is most likely wrong. The 10-15c edge tier losing $381 despite 50% WR is consistent with this. |

---

## Strategic Implications

1. **v1 was profitable on pure NO-side bets** (+$1,468 on 135 NO trades). If v1 logic were running in prod with $1/coin sizing, the risk/reward is known.
2. **v2 has worse calibration** than v1 on limited data (22.2% WR vs 44.2%). The blend-weight fix (20/75 from 80/97) may help, but needs time to accumulate trades.
3. **BTC is the worst-performing coin** — the model is systematically overconfident on BTC. Consider tighter thresholds or higher vol floor for BTC specifically.
4. **The model is most accurate near expiry** — the blend-heavy late-window behavior (trusting the market when it knows more) was actually helping v1's accuracy. The new 20/75 blend reduces that late-window market trust, which could make late-window calibration worse.

**Next step:** Continue accumulating v2 paper trades with the 20/75 blend. Every 50 resolved trades, re-run this calibration report. The critical threshold is ~100-150 v2 trades where the calibration curve becomes statistically meaningful.

---

*Generated from kalshi_decision_log + kalshi_trades join on 2026-05-17. Raw queries available in session history.*
