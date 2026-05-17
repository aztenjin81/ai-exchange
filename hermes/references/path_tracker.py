#!/usr/bin/env python3
"""
Intra-window price path tracking for Kalshi crypto 15-min markets.

Phase 1 of Claude's proposal: collect path metrics (TWAP, time above/below
strike, strike crossings, trend) at each scan with zero behavior change.
Phase 2 will validate whether these features carry predictive signal.
"""
import json, math
from datetime import datetime, timezone

def get_window_path(market_ticker):
    """Return list of (scan_time, spot_price) for all observations of this
    market in the current 15-minute window.

    Queries the decision_log which already records spot_price per scan.
    Returns empty list if no history or market_ticker is empty.
    """
    if not market_ticker:
        return []
    from hermes_db import query
    rows = query("""
        SELECT scan_time, spot_price
        FROM kalshi_decision_log
        WHERE market_ticker = %s
          AND spot_price IS NOT NULL
          AND scan_time > NOW() - INTERVAL '16 minutes'
        ORDER BY scan_time ASC
    """, (market_ticker,))
    return [(r[0], float(r[1])) for r in rows if r[1] is not None]


def compute_path_metrics(history, strike, current_spot, ttl_min):
    """Compute path features from spot observation history.

    Args:
        history: list of (timestamp, spot_price) tuples from get_window_path()
        strike: floor_strike from the Kalshi market
        current_spot: current Coinbase spot price
        ttl_min: minutes remaining in this window

    Returns dict of path metrics, or None if history is too short.
    """
    if not history or strike <= 0 or len(history) < 3:
        return None

    prices = [p for _, p in history]
    n = len(prices)

    above_count = sum(1 for p in prices if p > strike)
    below_count = sum(1 for p in prices if p < strike)

    twap = sum(prices) / n
    twap_vs_strike_pct = ((twap - strike) / strike) * 100

    max_excursion_above = max(prices) - strike
    max_excursion_below = min(prices) - strike

    # Recent trend: linear slope over last 3-5 obs, in $ per minute
    recent_trend = 0.0
    if n >= 3:
        recent = prices[-5:] if n >= 5 else prices
        x = list(range(len(recent)))
        x_mean = sum(x) / len(x)
        y_mean = sum(recent) / len(recent)
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, recent))
        den = sum((xi - x_mean) ** 2 for xi in x)
        recent_trend = num / den if den > 0 else 0.0

    # Strike crossings (above→below or below→above transitions)
    crossings = 0
    for i in range(1, n):
        prev_above = prices[i-1] > strike
        curr_above = prices[i] > strike
        if prev_above != curr_above:
            crossings += 1

    # Current streak (consecutive observations on current side of strike)
    current_above = current_spot > strike
    streak = 0
    for p in reversed(prices):
        if (p > strike) == current_above:
            streak += 1
        else:
            break

    # Intra-window volatility (std of log returns)
    intra_vol = 0.0
    if n >= 3:
        returns = [
            math.log(prices[i] / prices[i-1])
            for i in range(1, n)
            if prices[i-1] > 0 and prices[i] > 0
        ]
        if len(returns) >= 2:
            mean_r = sum(returns) / len(returns)
            var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            intra_vol = math.sqrt(var)

    window_elapsed = round(15.0 - ttl_min, 1)

    return {
        "n":                n,
        "window_elapsed":   window_elapsed,
        "twap":             round(twap, 4),
        "twap_vs_strike":   round(twap_vs_strike_pct, 4),
        "pct_above":        round(above_count / n, 3),
        "pct_below":        round(below_count / n, 3),
        "max_exc_above":    round(max_excursion_above, 4),
        "max_exc_below":    round(max_excursion_below, 4),
        "trend_per_min":    round(recent_trend, 6),
        "intra_vol":        round(intra_vol, 6),
        "crossings":        crossings,
        "streak":           streak,
    }
