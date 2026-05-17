# Calibration Analysis — Full Findings (2026-05-17)

## Q1: Model prediction distribution

The model produces a reasonable spread of `model_fair_yes` values. No single-bucket saturation problem.

| Bucket | Decisions | % |
|---|---|---|
| Strong NO (<0.30) | 1,019 | 25.3% |
| Mild NO (0.30-0.50) | 851 | 21.2% |
| Mild YES (0.50-0.70) | 894 | 22.2% |
| Strong YES (>0.70) | 1,259 | 31.3% |

## Q2: Win rate by side (the critical finding)

Across 264 resolved executed trades (all v1 + v2 combined):

| Side | Trades | Won | Lost | Win Rate |
|---|---|---|---|---|
| **NO** | 156 | 77 | 79 | **49.4%** |
| **YES** | 108 | 33 | 75 | **30.6%** |

**Neither side is profitable at scale.** The 94% NO accuracy observed in the 17-row v2 calibration sample does NOT generalize to the full trade set. NO was essentially breakeven in v1. This is a critical reality check for any "trust the NO side" strategy.

YES side is structurally unprofitable (30.6% win rate), confirming the asymmetric payout problem Claude identified: losing \$0.54/contract on YES but only gaining \$0.46 makes even 50% accuracy unprofitable.

## Q3: edge_too_small bottleneck

3,813 decisions blocked by `edge_too_small` in the last 48 hours:

| Edge Range | Count | % |
|---|---|---|
| < 4c (far from actionable) | 3,509 | **92.0%** |
| 4-7.9c (potentially reachable) | 299 | 7.8% |
| 6-7.9c (near-reachable) | 54 | 1.4% |

Only 7.8% of blocks are close enough to the 8c threshold that any blend adjustment could help. 92% are at edge < 4c — the blended fair value sits inside the bid-ask spread. The fundamental constraint is that 15-min crypto binaries are near-random walks over short windows, leaving minimal signal after accounting for spread.

## Blend weight verification

Confirmed live deployment is the **original 20/75 spec** (`min(0.75, 0.20 + progress * 0.55)`). The emergency 80/97 fix referenced in memory has already been reverted. The model has 25-80% voice in the blend by design (higher early, lower near expiry). The blend weight is not the bottleneck — it's already giving the model significant weight.

## Path B (asymmetric blend) assessment

Claude proposed asymmetric blend weights (×0.5 for NO, ×1.3 for YES) to trust the model more on NO predictions.

**Verdict: Would help at the margins but won't materially change throughput.**

The analysis assumes the model's NO signal is 94% accurate. Q2 shows it's actually 49.4% accurate at scale across all resolved trades. The small v2 sample (17 trades) may genuinely reflect better v2 model performance, but we can't bet on that with 0 v2 resolved trades to confirm.

Even if the v2 NO accuracy is genuinely higher, the blend isn't suppressing enough edge to matter — 92% of edge_too_small blocks are at < 4c, and the blend only contributes ±3-4c of drag in the most extreme cases.

## Where the emergency 80/97 blend came from

Memory context reveals the original 20/75 spec was overridden after "v1 momentum baseline blew up — the model proved dangerous by buying NO at 96¢ against a 95% market." The emergency fix clamped the blend to 80/97 (model voice reduced to 3-20%).

That emergency fix has since been reverted. The current 20/75 is the intended design. This means there's no hidden blend override to undo — the blend is already at its neutral design point.

## What I'd recommend

1. **Don't implement Path B as a major initiative.** The data doesn't support the "94% NO accuracy" thesis it depends on. The blend is already at 20/75, not the emergency 80/97.

2. **Keep the YES cap at \$0.40** — the asymmetric payout math (30.6% win rate on YES) independently justifies this, regardless of blend logic.

3. **Keep the confidence threshold at 0.30** — removes a future ceiling, even if no-op today.

4. **Wait for v2 resolved trades before any more blend or model changes.** The v2 model may genuinely be better than v1's breakeven NO accuracy. We need resolved outcomes to know.

5. **If throughput matters now:** focus on the fallback vol problem (19-37% null vol) and consider a lower `MIN_EDGE_CENTS` for NO trades only (Claude's Path A, as a last resort).
