# Paper 24h Status Report

Generated: 2026-05-18 19:20 MST
Reporting window: since paper resume (2026-05-17 19:20:00-07)
~24 hours of paper trading under tiered MIN_EDGE_BY_COIN thresholds.

## Trades by side

```
no|74|21|88.98
yes|28|3|-160.55
```

## Action distribution (top 15)

```
edge_too_small|6052
too_close_to_expiry|1061
spread_too_wide|762
positive_ev_direction_agreement_signal|190
model_market_disagreement_too_large|154
entry_too_expensive_for_ttl|101
edge_ratio_too_small|93
blocked_contrarian_cheap_yes|45
blocked_contrarian_cheap_no|38
blocked_spot_strike_deadzone|28
yes_too_expensive_for_known_bias|22
duplicate_market_position|6
missing_ask|1
blocked_direction_disagreement_no|1
```

## Edge-too-small breakdown by coin

```
BNB|0.90|-4.80|10.50|731
BTC|2.37|-1.50|9.70|1031
DOGE|-0.27|-4.80|5.00|887
ETH|0.72|-4.30|5.90|811
HYPE|0.02|-4.90|7.90|763
SOL|0.75|-3.00|5.30|887
XRP|0.41|-4.70|4.80|942
```

## Interpretation

- If trades > 0: bot is finding edges under tiered thresholds. Check win rate and P&L.
- If trades == 0: bot is not trading under current thresholds. This is a finding to report.
- If edge_too_small dominates all coins equally, thresholds may be too aggressive for current market conditions.
- If certain coins have zero opportunity (all too_close_to_expiry or spread_too_wide), those coins may be structurally unsuitable.
