# Response to Claude's Asymmetric Blend Proposal — Data Check

## Q1: Model distribution (good news)

The model produces a reasonable spread of predictions. Path B would have material to work with.

| Bucket | Share |
|---|---|
| Strong NO (<0.30) | 25.3% |
| Mild NO (0.30-0.50) | 21.2% |
| Mild YES (0.50-0.70) | 22.2% |
| Strong YES (>0.70) | 31.3% |

Among trades that passed all filters (side=yes/no), the split is roughly even (~30%/23%/27%/21%). So the model IS sending strong NO signals — they're just dying at edge_too_small.

## Q2: Side-based win rate (mixed news)

This is across ALL resolved v1+v2 trades with execution and resolution data:

| Side | Trades | Win Rate |
|---|---|---|
| NO | 156 | **49.4%** |
| YES | 108 | **30.6%** |

**Neither side is profitable.** The 94% NO accuracy from the earlier 17-row v2 sample does NOT generalize to the full v1 trade set — v1 NO trades were roughly breakeven. This is a critical caveat for Path B: the "94% NO accuracy" thesis may be v2-specific (small sample, better model) and may not hold at scale.

## Q3: Edge distribution among edge_too_small blocks (the real story)

**3,813 decisions blocked by `edge_too_small` in 48 hours.**

| Range | Count | % |
|---|---|---|
| **< 4c (far)** | 3,509 | **92.0%** |
| 4-7.9c (reachable) | 299 | 7.8% |
| 6-7.9c (near-reachable) | 54 | 1.4% |

Even in the best-case scenario Claude modeled (model_fair_yes=0.20, kalshi_mid=0.35), Path B improves edge from 6.7c → 10.3c — a gain of ~3.6c. Applied to the 299 reachable cases (4-7.9c), that might free up some trades. But **92% of blocks are at < 4c edge where even a 3.6c boost won't clear 8c.**

## Assessment of Path B

**Path B would help at the margins but won't be the throughput unlock.** The improvement is real — maybe ~50-150 extra trades per day if we're generous — but 92% of blocks are too far from the threshold for any blend tweak to reach.

The fundamental constraint: the blended fair value sits inside the bid-ask spread for most markets most of the time. The edge is genuinely small because 15-min crypto binaries are effectively random walks over short windows, leaving very little signal to extract after accounting for spread.

## What I'd recommend instead

1. **Still implement Path B** — worth adding, safely tunable, addresses the root cause even if the throughput impact is modest. But with gentler starting multipliers: ×0.7 for NO, ×1.2 for YES.

2. **Focus on the fallback vol problem instead** — 19-37% null vol is eroding confidence on the trades that DO have edge. Fixing Kraken reliability (wider lookback, retry with backoff) is a higher-leverage change than blend tinkering.

3. **Accept that the crypto 15-min market has limited exploitable edge.** The per-coin $1 cap and $68 current balance mean we're at low risk regardless. The bot is learning — every edge_too_small decision IS a data point for the isotonic calibrator later.

4. **Revisit after 200+ resolved v2 trades.** That's when we can actually fit the isotonic regression and see whether the v2 data confirms or contradicts the 94% NO thesis. Until then, the blend tweaks are marginal improvements on a fundamentally noisy signal.
