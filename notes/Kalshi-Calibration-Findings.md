---
type: reference
tags: [kalshi, calibration, model, sizing]
created: 2026-05-17
---

# Kalshi Model Calibration Findings

## Diagnosis (2026-05-17)

The `fair_yes_probability()` log-normal model was producing **directionally asymmetric** predictions on 15-min crypto data:

| Prediction | Accuracy |
|---|---|
| Model says NO (spot < strike) | 94.1% (16/17) |
| Model says YES (spot > strike) | 52.9% (9/17) |

This is a real market feature (downward persistence vs upward reversion in 15-min windows), not a fixable vol parameter.

## What Was Ruled Out

- **Symmetric vol multiplier** — rejected. A >1.0x multiplier shrinks all predictions toward 50/50, which hurts NO predictions (already reliable) while only mildly helping YES predictions (already unreliable). A <1.0x multiplier would unrealistically increase confidence.
- **Vol multiplier sweep** (0.5x–6.0x) confirmed: optimal Brier is at 0.6x, but this would inflate NO-side overconfidence, not fix the underlying asymmetry.

## What's In Place

- **Kalshi mid blend** — provides partial workaround (Brier 0.16 blended vs 0.17 raw model). The market mid is implicitly calibrated by money flow.
- **NO-side sizing preference** — deployed 2026-05-17:
  ```python
  SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}
  ```
  YES bets get half size to preserve learning while weighting toward the more reliable NO side.

## Next Steps

- Revisit after 50+ new resolved v2 trades with asymmetric sizing live
- If asymmetry narrows → move YES multiplier toward 1.0
- If asymmetry holds → NO bias is structural, sizing becomes permanent
- At 100–200 resolved trades → fit isotonic regression calibrator (per-direction or full)
- Sanity check script at `~/.hermes/scripts/calibration-sanity-check`

## Key Metrics

- v1 resolved trades with full model data: 34
- v2 resolved trades with full model data: 0 (as of 2026-05-17)
- Model-only Brier: 0.1745
- Blended Brier: 0.1600
