---
type: analysis
tags: [kalshi, calibration, model, sizing]
shared-with: claude
created: 2026-05-17
---

# Kalshi Model Calibration — Current State

## The short version

The log-normal `fair_yes_probability()` model is **directionally asymmetric** on 15-min crypto:

- **NO predictions** (spot < strike): 94% correct (16/17)
- **YES predictions** (spot > strike): 53% correct (9/17)

## What we ruled out

- **Symmetric vol multiplier** → sweep confirmed it can't fix per-direction bias. A >1.0x multiplier shrinks all predictions toward 50/50, hurting reliable NO predictions while barely helping unreliable YES predictions. A <1.0x multiplier would unrealistically inflate confidence.
- **The math is correct**, the assumptions are wrong for 15-min crypto (jumps, fat tails, microstructure noise).

## What's in place

- **Kalshi mid blend** (Brier 0.16 blended vs 0.17 raw) — the market mid partially corrects the model's overconfidence by mixing in money-calibrated prices.
- **NO-side sizing** — deployed today: `SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}`. YES bets at half size preserves learning while weighting toward the more reliable NO side.

## Next steps

1. Once ~100-200 resolved v2 trades accumulate → fit **isotonic regression** calibrator (learns per-direction asymmetry naturally)
2. If asymmetry narrows over 50-100 trades → YES multiplier moves back toward 1.0
3. If asymmetry holds → NO bias is structural, sizing becomes permanent

## Raw data snapshot (34 resolved v1 trades)

| Prediction direction | Correct | Total | Accuracy |
|---|---|---|---|
| Model says NO | 16 | 17 | 94.1% |
| Model says YES | 9 | 17 | 52.9% |

Model-only Brier: 0.1745
Blended Brier: 0.1600

V2 resolved trades with full model data: 0 (as of 2026-05-17)

## Dashboard

Available at http://192.168.1.226:8890 (internal network, not externally accessible)
