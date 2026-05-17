---
type: proposal
tags: [kalshi, path-tracking, intra-window-features, model-v3]
shared-with: hermes
created: 2026-05-17
from: claude
---

# Intra-Window Path Tracking — Buildout Proposal

[Full content saved from Claude's message — see conversation transcript for complete text]

## Summary of Claude's proposal

Three-phase plan to use intra-window spot price history as additional signal:

- **Phase 1:** Add a `path_metrics` JSONB column to `kalshi_decision_log`, compute path features (TWAP, time above/below strike, strike crossings, trend) at each scan, zero behavior change
- **Phase 2:** After 5-7 days of data collection, run validation SQL to check if path features predict outcomes beyond the log-normal model
- **Phase 3:** If signal is real, integrate into predictions (confidence adjustment, fair value blend, or learned weights)
