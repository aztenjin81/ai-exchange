# Per-coin P&L — last 30 days

**Generated:** 2026-05-18T09:42:00-07:00
**Window:** NOW() - INTERVAL '30 days' to NOW()

## Query A — P&L by coin and strategy

| series_ticker | strategy_name | trades | closed | yes_trades | no_trades | wins | losses | total_pnl | avg_pnl | avg_entry | avg_edge_cents |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KXBNB15M | crypto_intel | 37 | 37 | 14 | 23 | 15 | 22 | -51.48 | -1.39 | 0.4259 | 26.83 |
| KXBNB15M | crypto_intel_prod | 2 | 2 | 1 | 1 | 0 | 2 | -1.29 | -0.65 | 0.3250 | 6.60 |
| KXBTC15M | crypto_intel | 49 | 49 | 16 | 33 | 19 | 30 | 13.89 | 0.28 | 0.3818 | 26.11 |
| KXBTC15M | crypto_intel_prod | 7 | 7 | 1 | 6 | 2 | 5 | 8.89 | 1.27 | 0.3203 | 21.00 |
| KXDOGE15M | crypto_intel | 53 | 53 | 19 | 34 | 24 | 29 | 391.32 | 7.38 | 0.3453 | 20.50 |
| KXDOGE15M | crypto_intel_prod | 6 | 6 | 4 | 2 | 1 | 5 | -1.22 | -0.20 | 0.2283 | 4.50 |
| KXETH15M | crypto_intel | 76 | 76 | 28 | 48 | 25 | 51 | 174.37 | 2.29 | 0.3078 | 16.68 |
| KXETH15M | crypto_intel_prod | 10 | 10 | 4 | 6 | 4 | 6 | 5.93 | 0.59 | 0.3020 | 8.34 |
| KXHYPE15M | crypto_intel | 35 | 35 | 18 | 17 | 16 | 19 | 83.46 | 2.38 | 0.4239 | 30.38 |
| KXHYPE15M | crypto_intel_prod | 2 | 2 | 0 | 2 | 0 | 2 | -1.70 | -0.85 | 0.2450 | 15.25 |
| KXSOL15M | crypto_intel | 68 | 68 | 32 | 36 | 24 | 44 | 8.19 | 0.12 | 0.3456 | 17.46 |
| KXSOL15M | crypto_intel_prod | 14 | 14 | 10 | 4 | 1 | 12 | -3.76 | -0.27 | 0.2507 | 8.18 |
| KXXRP15M | crypto_intel | 58 | 58 | 21 | 37 | 21 | 37 | 302.48 | 5.22 | 0.3219 | 18.66 |
| KXXRP15M | crypto_intel_prod | 5 | 5 | 2 | 3 | 1 | 4 | -0.31 | -0.06 | 0.2280 | 5.24 |

## Query B — Hit rate by coin and side

| series_ticker | side | n | wins | hit_rate | avg_entry | pnl | implied_minus_hit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| KXBNB15M | no | 17 | 6 | 0.353 | 0.421 | -56.66 | 0.068 |
| KXBNB15M | yes | 14 | 5 | 0.357 | 0.414 | -48.29 | 0.057 |
| KXBTC15M | no | 36 | 18 | 0.500 | 0.417 | 259.90 | -0.083 |
| KXBTC15M | yes | 16 | 3 | 0.188 | 0.342 | -192.69 | 0.154 |
| KXDOGE15M | no | 34 | 21 | 0.618 | 0.361 | 615.68 | -0.257 |
| KXDOGE15M | yes | 20 | 4 | 0.200 | 0.311 | -164.29 | 0.111 |
| KXETH15M | no | 46 | 19 | 0.413 | 0.296 | 264.00 | -0.117 |
| KXETH15M | yes | 31 | 5 | 0.161 | 0.301 | -251.36 | 0.140 |
| KXHYPE15M | no | 18 | 6 | 0.333 | 0.340 | 30.23 | 0.007 |
| KXHYPE15M | yes | 18 | 10 | 0.556 | 0.504 | 65.01 | -0.052 |
| KXSOL15M | no | 36 | 12 | 0.333 | 0.309 | 66.75 | -0.025 |
| KXSOL15M | yes | 40 | 9 | 0.225 | 0.332 | -199.85 | 0.107 |
| KXXRP15M | no | 39 | 14 | 0.359 | 0.272 | 291.94 | -0.087 |
| KXXRP15M | yes | 23 | 8 | 0.348 | 0.390 | 11.23 | 0.042 |

## Query C — Edge-cents bucket performance by coin

| series_ticker | edge_bucket | n | wins | hit_rate | pnl |
| --- | --- | --- | --- | --- | --- |
| KXBNB15M | 1 (3-6c) | 1 | 0 | 0.000 | -12.25 |
| KXBNB15M | 2 (6-9c) | 5 | 3 | 0.600 | 85.73 |
| KXBNB15M | 3 (9-12c) | 2 | 0 | 0.000 | -48.60 |
| KXBNB15M | 4 (12-15c) | 2 | 0 | 0.000 | -73.79 |
| KXBNB15M | 5 (15-18c) | 1 | 0 | 0.000 | -41.82 |
| KXBNB15M | 6 (18c+) | 20 | 8 | 0.400 | -14.22 |
| KXBTC15M | 1 (3-6c) | 4 | 0 | 0.000 | -21.39 |
| KXBTC15M | 2 (6-9c) | 12 | 6 | 0.500 | 117.95 |
| KXBTC15M | 3 (9-12c) | 6 | 2 | 0.333 | -77.44 |
| KXBTC15M | 4 (12-15c) | 2 | 1 | 0.500 | -21.34 |
| KXBTC15M | 5 (15-18c) | 1 | 1 | 1.000 | 62.10 |
| KXBTC15M | 6 (18c+) | 27 | 11 | 0.407 | 7.33 |
| KXDOGE15M | 1 (3-6c) | 16 | 1 | 0.063 | -127.88 |
| KXDOGE15M | 2 (6-9c) | 7 | 5 | 0.714 | 163.26 |
| KXDOGE15M | 3 (9-12c) | 6 | 3 | 0.500 | 31.18 |
| KXDOGE15M | 4 (12-15c) | 2 | 0 | 0.000 | -68.06 |
| KXDOGE15M | 6 (18c+) | 23 | 16 | 0.696 | 452.89 |
| KXETH15M | 1 (3-6c) | 28 | 7 | 0.250 | 21.20 |
| KXETH15M | 2 (6-9c) | 14 | 4 | 0.286 | 54.07 |
| KXETH15M | 3 (9-12c) | 10 | 2 | 0.200 | -139.58 |
| KXETH15M | 4 (12-15c) | 1 | 0 | 0.000 | -9.51 |
| KXETH15M | 5 (15-18c) | 2 | 0 | 0.000 | -71.78 |
| KXETH15M | 6 (18c+) | 22 | 11 | 0.500 | 158.24 |
| KXHYPE15M | 1 (3-6c) | 1 | 0 | 0.000 | -0.92 |
| KXHYPE15M | 2 (6-9c) | 4 | 3 | 0.750 | 151.54 |
| KXHYPE15M | 3 (9-12c) | 3 | 1 | 0.333 | -40.35 |
| KXHYPE15M | 4 (12-15c) | 3 | 0 | 0.000 | -118.27 |
| KXHYPE15M | 6 (18c+) | 25 | 12 | 0.480 | 103.24 |
| KXSOL15M | 1 (3-6c) | 22 | 3 | 0.136 | -90.10 |
| KXSOL15M | 2 (6-9c) | 25 | 6 | 0.240 | -62.87 |
| KXSOL15M | 3 (9-12c) | 4 | 1 | 0.250 | -3.62 |
| KXSOL15M | 5 (15-18c) | 3 | 1 | 0.333 | 15.40 |
| KXSOL15M | 6 (18c+) | 22 | 10 | 0.455 | 8.09 |
| KXXRP15M | 1 (3-6c) | 21 | 3 | 0.143 | -30.02 |
| KXXRP15M | 2 (6-9c) | 7 | 2 | 0.286 | -22.24 |
| KXXRP15M | 3 (9-12c) | 5 | 0 | 0.000 | -180.59 |
| KXXRP15M | 4 (12-15c) | 3 | 2 | 0.667 | 26.90 |
| KXXRP15M | 5 (15-18c) | 1 | 0 | 0.000 | -5.82 |
| KXXRP15M | 6 (18c+) | 25 | 15 | 0.600 | 514.94 |

## Notes

- The `implied_minus_hit` column in Query B is `avg_entry - hit_rate`. Positive means the coin/side is unprofitable on average (the market priced your side higher than it actually wins). Near-zero means break-even after fees. Negative means real edge.
- Query C uses edge_cents bins: bucket 1 = 3–6c, 2 = 6–9c, 3 = 9–12c, 4 = 12–15c, 5 = 15–18c, 6 = 18c+.
- Only crypto_intel and crypto_intel_prod have data in the 30-day window.
