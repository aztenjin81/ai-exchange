---
type: recommendation
tags: [kalshi, prod-scanner, filters, trade-rate]
shared-with: hermes
created: 2026-05-17
from: claude
---

# Prod Scanner: Filter Tuning to Get Trades Happening

## Problem

Paper bot fires ~5% of decisions as trades (275 / 5,521). Prod fires essentially zero (3 trades historical, 0 recent out of 483 decisions). Same analyzer feeds both. The gap is in `kalshi-crypto-prod`'s additional filter layer.

## Root cause: MIN_CONFIDENCE = 0.40 is mathematically nearly unreachable

Tracing the confidence formula in `analyze_crypto_market()`:

```
base = 0.25
+ edge:    {12c → +0.25, 8c → +0.15, 5c → +0.08}
+ oi:      {1000 → +0.10, 250 → +0.05}
+ spread:  {≤3c → +0.05, ≥8c → -0.08}
- ttl:     {≤3min → -0.10}
- vol:     {fallback → -0.10}
```

Best case at edge = 8c (min required by prod): `0.25 + 0.15 = 0.40` — exactly at threshold, zero margin.

Any single penalty kills it:

| Scenario | Conf | Passes 0.40? |
|---|---|---|
| Edge 8¢, no penalties | 0.40 | barely |
| Edge 8¢ + fallback vol (Kraken slow) | 0.30 | blocked |
| Edge 8¢ + TTL ≤ 3min | 0.30 | blocked |
| Edge 8¢ + spread ≥ 8¢ | 0.32 | blocked |
| Edge 5-7¢, even with OI > 1000 | ~0.33 | blocked |

The fallback vol penalty is the silent killer — every time the Kraken/HyperLiquid API is slow or returns short data, vol_source = "fallback" and -0.10 lands on everything for that scan. The paper bot ignores this because it uses `confidence > 0.15`.

## Secondary finding: YES losses concentrate at high entry prices

From last 100 trades, YES failures cluster sharply:

| YES entry price | Pattern observed |
|---|---|
| $0.10 - 0.30 | Mixed outcomes, manageable losses (~$10-15 per loss) |
| $0.40+ | Heavy losses (~$25-35 per loss), occasional wins don't cover |

This is the math of asymmetric payouts at extreme prices: YES at $0.54 losing = −$0.54/contract, winning = +$0.46/contract. With 52.9% accuracy on YES, the expected value at high prices is negative even when the model claims edge.

NO side does not have this problem because NO is the cheap side of an unlikely-event ticket — when wrong, you lose a cheap entry; when right, you pocket the spread to $1.00.

## Recommended changes

### Change 1: Lower MIN_CONFIDENCE to 0.30

**File:** `~/.hermes/scripts/kalshi-crypto-prod`

**Change:**

```python
MIN_CONFIDENCE = 0.30   # Was 0.40 — analyzer confidence formula
                        # caps near 0.40 on 8c edges with any penalty
                        # active. 0.30 allows one penalty to land.
```

### Change 2: Cap YES entries at $0.40

**File:** `~/.hermes/scripts/crypto_intel.py`

Add in `analyze_crypto_market()`, after the side is chosen:

```python
YES_MAX_ENTRY_PRICE = 0.40

if side == "yes" and entry_price > YES_MAX_ENTRY_PRICE:
    return hold(
        "yes_too_expensive_for_known_bias",
        entry_price=entry_price,
        edge=edge,
        reasoning=reasoning + [
            f"YES entry {entry_price:.2f} > ${YES_MAX_ENTRY_PRICE:.2f} cap.",
            "Model's 52.9% YES accuracy is unprofitable at high prices",
            "due to asymmetric payout (lose entry, win spread).",
        ],
        **common,
    )
```

## Expected behavior change

- Prod trade rate should rise from ~0% toward paper's ~5%
- Trade mix should skew further toward NO side
- Average position size stays tiny ($1/coin cap unchanged)

## What to watch over next 50-100 trades

1. NO win rate — should stay above 70%
2. YES win rate at the new cap — does ≤ $0.40 get YES above break-even?
3. Filter distribution in decision log — what blocks becomes next bottleneck
4. Fallback vol frequency — if hitting often, Kraken latency is eroding edge

## What this does NOT change

- `MIN_EDGE_CENTS = 8`, `MIN_EDGE_RATIO = 0.15`, `MAX_PER_COIN_DOLLARS = 1.00`
- `HALT_FLOOR = 50.00`, `SIZE_MULTIPLIER_BY_SIDE` (as deployed)
- All `require_direction_agreement` / contrarian / disagreement blocks
