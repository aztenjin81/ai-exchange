# Session: 2026-05-17 — Major Calibration & Infrastructure Work

## What was accomplished

This was the most significant work session on the Kalshi crypto bot to date.
Multiple rounds of analysis, implementation, and cross-agent reasoning (Hermes + Claude via GitHub repo exchange).

---

## Model Calibration Investigation

### Starting premise
The log-normal `fair_yes_probability()` was thought to be systematically overconfident. A vol multiplier was proposed as a fix.

### What the data actually showed

**Finding 1: Directional asymmetry, not uniform overconfidence**
- Model says NO (spot < strike): 94% correct in v2 sample (16/17)
- Model says YES (spot > strike): 53% correct in v2 sample (9/17)
- A symmetric vol multiplier sweep (0.5x–6.0x) confirmed it can't fix per-direction bias

**Finding 2: The 94% NO thesis doesn't scale**
- Across ALL 264 resolved trades (v1+v2 combined):
  - NO side: **49.4% win rate** (77W/79L out of 156)
  - YES side: **30.6% win rate** (33W/75L out of 108)
- Neither side is profitable at scale. The small v2 sample (17 trades) showed 94% but that's selection bias from the tiny sample.

**Finding 3: Blend weight is already at intended spec**
- The emergency 80/97 blend fix (implemented after v1 momentum baseline blew up) has already been REVERTED.
- Current blend: original 20/75 spec (model voice 25-80%).

**Finding 4: The bottleneck is edge, not blend**
- 92% of `edge_too_small` blocks are at <4c edge
- The blended fair value sits inside the bid-ask spread
- The fundamental constraint: 15-min crypto binaries have limited signal after spread

### What was ruled out / rejected
- **Symmetric vol multiplier** — rejected after sweep confirmed it can't fix per-direction bias
- **Path B (asymmetric blend weights)** — rejected because the "94% NO accuracy" load-bearing assumption doesn't hold at scale. NO was actually 49.4%.
- **Confidence 0.40 → 0.30** — implemented as structural fix but confirmed no-op today (zero trades in 0.30-0.39 range with >=8c edge)

### What was deployed
- **NO-side sizing** — `SIZE_MULTIPLIER_BY_SIDE = {'no': 1.0, 'yes': 0.5}` — YES bets at half size
- **YES cap at $0.40** — addresses asymmetric payout problem (30.6% YES win rate)
- **MIN_CONFIDENCE = 0.30** — structural fix, no-op today
- **Phase 1 path tracking** — ALTER TABLE + path_tracker.py, data collection only

---

## Infrastructure Fixes

### Prod auth from cron (long-standing bug, finally fixed)
**Root cause:** Two compounding bugs:
1. `create_prod_auth()` in `kalshi_client.py` read module-level `PROD_KEY_ID`/`PROD_KEY_PATH` frozen at import time. Setting `os.environ` in the retry block never propagated.
2. Retry env sourcing in `kalshi-crypto-prod` sourced `~/.hermes/.env` (template, no KALSHI_PROD vars) instead of `~/.hermes/env` (actual creds).

**Fix:** Both addressed — auth reads os.environ directly at call time, env sourcing checks `env` before `.env`.

### Dashboard bid/ask display
Added NO bid/ask alongside YES bid/ask in the cache pipeline.

---

## AI Exchange Infrastructure

Set up `github.com/aztenjin81/ai-exchange` as a shared workspace between Hermes and Claude:
- `hermes/` — analysis from Hermes
- `claude/` — recommendations from Claude (via copy-paste from user)
- `shared/` — mutual workspace
- `hermes/references/` — full script copies + DB export

Auto-syncs every 15 min via cron (git push + Obsidian Sync).

---

## Cross-Agent Exchange (Hermes ↔ Claude via GitHub)

Claude contributed three recommendation rounds this session:

| Round | Proposal | Verdict |
|---|---|---|
| 1 | Prod filter tuning (conf 0.40→0.30, YES cap) | Partially implemented. Conf change was no-op (correct analysis, wrong bottleneck). YES cap was independently valuable. |
| 2 | Path B asymmetric blend weights | Rejected. The 94% NO accuracy thesis doesn't hold at scale (NO was actually 49.4%). |
| 3 | Intra-window path tracking | Phase 1 implemented. Data collection starts now, Phase 2 validation in ~7 days. |

---

## Path Tracking Phase 1 — Summary

**Schema:** `ALTER TABLE kalshi_decision_log ADD COLUMN path_metrics JSONB`
**Index:** `idx_decision_log_market_scan` on (market_ticker, scan_time DESC)
**Module:** `path_tracker.py` — `get_window_path()` queries history, `compute_path_metrics()` computes features
**Features collected per scan:** observations_count, window_elapsed_minutes, twap, twap_vs_strike_pct, pct_time_above_strike, pct_time_below_strike, max_excursion_above, max_excursion_below, recent_trend_per_min, intra_window_vol, strike_crossings, current_streak
**Status:** Live, writing, fresh data only (no backfill)

---

## Key Numbers to Return To

| Metric | Value | Date |
|---|---|---|
| Resolved trades with full v2 model data | 0 | 2026-05-17 |
| V1+v2 resolved trades (all) | 264 | 2026-05-17 |
| NO win rate (all resolved) | 49.4% | 2026-05-17 |
| YES win rate (all resolved) | 30.6% | 2026-05-17 |
| Model-only Brier | 0.1745 | 2026-05-17 |
| Blended Brier | 0.1600 | 2026-05-17 |
| Prod balance (synced) | $68.05 | 2026-05-17 |
| % edge_too_small blocks <4c | 92.0% | 2026-05-17 |
| Fallback vol frequency (prod) | 19% | 2026-05-17 |
| Fallback vol frequency (paper) | 37% | 2026-05-17 |

---

## Next Actions (checkpoint in ~7 days)

1. **Phase 2 validation** — run `path-analysis` script to check if path features predict outcomes
2. **Check v2 resolved trade count** — if 50-100+ have accumulated, start evaluating isotonic regression
3. **Review filter distribution** — has edge_too_small dropped from 79%? Did conf 0.30 or YES cap change anything?
4. **Fallback vol investigation** — 19-37% null vol is the largest unaddressed issue. Kraken fetch reliability.
