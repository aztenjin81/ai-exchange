#!/usr/bin/env python3
"""
Crypto 15-Min Market Intelligence Module.
Edge analysis for Kalshi crypto 15-min binary markets.
Logs every decision (enter/hold/skip) to kalshi_decision_log.

The baseline for these 'price up/down in next 15 min' markets is 50/50 —
a random walk has equal odds of going up or down in any window.
Edge = |market_prob - 0.50| minus friction (spread).
"""

import time, json, os, math
from math import log, sqrt
from statistics import NormalDist
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

CACHE_FILE = Path.home() / '.hermes' / 'cache' / 'kalshi_live.json'

# Side-based sizing multiplier.
# NO bets historically 94% correct, YES bets 53% correct.
# Half-size on YES preserves learning; full-size on NO.
# As v2 data accumulates, adjust toward 1.0 if the asymmetry narrows.
SIZE_MULTIPLIER_BY_SIDE = {
    'no':  1.0,
    'yes': 0.5,
}

SERIES = [
    ("BTC", "KXBTC15M", "#f7931a", "₿"),
    ("ETH", "KXETH15M", "#627eea", "⟠"),
    ("SOL", "KXSOL15M", "#00d18c", "◎"),
    ("XRP", "KXXRP15M", "#23292f", "✕"),
    ("DOGE", "KXDOGE15M", "#c2a633", "Ð"),
    ("BNB", "KXBNB15M", "#f0b90b", "◆"),
    ("HYPE", "KXHYPE15M", "#5367ff", "◈"),
]

# ── Emergency anti-contrarian safety defaults ───────────────────────
ENABLE_CONTRARIAN_ENTRIES = False
MAX_MODEL_MARKET_DISAGREEMENT = 0.20
MIN_EDGE_RATIO = 0.15
UNDERDOG_BLOCK_THRESHOLD = 0.50
ENABLE_AUTO_HEDGING = False
ENABLE_AUTO_EXITS = False
MIN_EDGE_CENTS = 8
HARD_MAX_ENTRY_PRICE = 0.75
SPOT_STRIKE_DEADZONE_PCT = 0.02  # avoid treating RTI/noisy near-strike tick as direction

# Per-coin edge minimums (in dollars, e.g. 0.10 = 10c).
# Overrides the TTL-based dynamic edge for specific coins.
# Higher = tighter filter, lower = more trades.
MIN_EDGE_BY_COIN = {
    'BTC':  0.10,   # v1 lost -$163 — highest bar
    'BNB':  0.08,   # v1 lost -$47
    'HYPE': 0.08,   # v1 lost -$41
    'ETH':  0.04,   # v1 made +$253 — lower bar
    'SOL':  0.04,   # v1 made +$245
    'XRP':  0.04,   # v1 made +$359
    'DOGE': 0.04,   # v1 made +$213
}

# Per-coin contrarian limits: (lower_bound, upper_bound)
# Contrarian YES is blocked when kalshi_yes_mid < lower_bound
# Contrarian NO is blocked when kalshi_yes_mid > upper_bound
# Inside the bounds, contrarian trading is allowed.
# Tighter bounds = more protection on coins where the model historically loses.
CONTRARIAN_LIMITS = {
    'BTC':  (0.25, 0.75),   # tightest — v1 lost -$163 on BTC
    'BNB':  (0.20, 0.80),   # v1 lost -$47
    'HYPE': (0.20, 0.80),   # v1 lost -$41
    'ETH':  (0.10, 0.90),   # looser — v1 made +$253
    'SOL':  (0.10, 0.90),   # v1 made +$245
    'XRP':  (0.10, 0.90),   # v1 made +$359
    'DOGE': (0.10, 0.90),   # v1 made +$213
}

_cycle_counter = 0


def _next_cycle():
    global _cycle_counter
    _cycle_counter += 1
    return _cycle_counter

def fetch_spot_price(coin_name):
    """Fetch current spot price from Coinbase. Returns float or None."""
    asset_api = {
        "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
        "XRP": "XRP-USD", "DOGE": "DOGE-USD", "BNB": "BNB-USD",
        "HYPE": "HYPE-USD",
    }.get(coin_name)
    if not asset_api:
        return None
    try:
        req = Request(f'https://api.coinbase.com/v2/prices/{asset_api}/spot',
                      headers={'Accept': 'application/json'})
        data = json.loads(urlopen(req, timeout=8).read().decode())
        return float(data['data']['amount'])
    except Exception:
        return None


def get_ttl_minutes(close_time):
    """Return minutes until market close. Returns 0 if missing/invalid."""
    if not close_time:
        return 0.0
    try:
        ct = datetime.fromisoformat(str(close_time).replace("Z", "+00:00"))
        return max(0.0, (ct - datetime.now(timezone.utc)).total_seconds() / 60.0)
    except Exception:
        return 0.0


def fair_yes_probability(spot, strike, annualized_vol, minutes_left):
    """P(final price > strike) using short-horizon log-normal movement."""
    if not spot or not strike or strike <= 0:
        return 0.5
    if minutes_left <= 0:
        return 1.0 if spot > strike else 0.0
    if not annualized_vol or annualized_vol <= 0:
        return 1.0 if spot > strike else 0.0
    t_years = minutes_left / (365.0 * 24.0 * 60.0)
    sigma_t = annualized_vol * sqrt(t_years)
    if sigma_t <= 0:
        return 1.0 if spot > strike else 0.0
    z = log(spot / strike) / sigma_t
    fair = NormalDist().cdf(z)
    return max(0.01, min(0.99, fair))


def realized_vol_from_closes(closes, candle_minutes=1):
    """Annualized realized volatility from close prices."""
    if not closes or len(closes) < 6:
        return None
    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            returns.append(math.log(closes[i] / closes[i - 1]))
    if len(returns) < 5:
        return None
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / max(1, len(returns) - 1)
    candles_per_year = 365.0 * 24.0 * 60.0 / candle_minutes
    return math.sqrt(variance * candles_per_year)


def conservative_vol_blend(vol_5m=None, vol_15m=None, vol_60m=None):
    """Conservative volatility estimate; intentionally avoids underestimation."""
    candidates = []
    if vol_5m:
        candidates.append(vol_5m)
    if vol_15m:
        candidates.append(vol_15m * 0.90)
    if vol_60m:
        candidates.append(vol_60m * 0.75)
    return max(candidates) if candidates else None


KRAKEN_PAIRS = {
    "BTC": "XXBTZUSD", "ETH": "XETHZUSD", "SOL": "SOLUSD",
    "XRP": "XRPUSD", "DOGE": "DOGEUSD", "BNB": "BNBUSD",
}

FALLBACK_VOL = {
    "BTC": 0.60,
    "ETH": 0.70,
    "SOL": 1.10,
    "XRP": 0.85,
    "DOGE": 1.20,
    "BNB": 0.65,
    "HYPE": 1.40,
}

_vol_cache = {}  # {coin_name: (vol, timestamp, source)}
_VOL_CACHE_TTL = 120
_last_vol_source = {}


def fetch_recent_closes_kraken(coin_name, lookback_minutes=90):
    """Fetch recent 1-minute close prices from Kraken. Never throws."""
    pair = KRAKEN_PAIRS.get(coin_name)
    if not pair:
        return []
    try:
        url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1"
        req = Request(url, headers={"Accept": "application/json"})
        data = json.loads(urlopen(req, timeout=8).read().decode())
        if data.get("error"):
            return []
        for key, candles in data.get("result", {}).items():
            if key == "last" or not isinstance(candles, list):
                continue
            closes = []
            for candle in candles:
                try:
                    if len(candle) > 4:
                        closes.append(float(candle[4]))
                except Exception:
                    pass
            return closes[-lookback_minutes:] if len(closes) > lookback_minutes else closes
    except Exception:
        return []
    return []


def fetch_recent_closes_hyperliquid(lookback_minutes=90):
    """Fetch recent 1-minute closes for HYPE from HyperLiquid public API."""
    try:
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - (lookback_minutes * 60 * 1000)
        payload = json.dumps({
            "type": "candleSnapshot",
            "req": {
                "coin": "HYPE",
                "interval": "1m",
                "startTime": start_ms,
                "endTime": now_ms,
            },
        }).encode()
        req = Request(
            "https://api.hyperliquid.xyz/info",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        data = json.loads(urlopen(req, timeout=8).read().decode())
        if not isinstance(data, list):
            return []
        closes = []
        for candle in data:
            try:
                if "c" in candle:
                    closes.append(float(candle["c"]))
            except Exception:
                pass
        return closes[-lookback_minutes:] if len(closes) > lookback_minutes else closes
    except Exception:
        return []


def fetch_recent_closes(coin_name, lookback_minutes=90):
    if coin_name == "HYPE":
        return fetch_recent_closes_hyperliquid(lookback_minutes)
    return fetch_recent_closes_kraken(coin_name, lookback_minutes)


def get_model_volatility(coin_name):
    """Build annualized volatility estimate from recent 1-minute closes with cache/fallback."""
    now = time.time()
    cached = _vol_cache.get(coin_name)
    if cached and (now - cached[1]) < _VOL_CACHE_TTL:
        _last_vol_source[coin_name] = cached[2]
        return cached[0]

    closes = fetch_recent_closes(coin_name, lookback_minutes=90)
    source = "hyperliquid" if coin_name == "HYPE" and len(closes) >= 10 else "kraken"
    vol = None
    if len(closes) >= 10:
        vol_5m = realized_vol_from_closes(closes[-6:], candle_minutes=1) if len(closes) >= 6 else None
        vol_15m = realized_vol_from_closes(closes[-16:], candle_minutes=1) if len(closes) >= 16 else None
        vol_60m = realized_vol_from_closes(closes[-61:], candle_minutes=1) if len(closes) >= 61 else None
        vol = conservative_vol_blend(vol_5m, vol_15m, vol_60m)

    if vol is None:
        vol = FALLBACK_VOL.get(coin_name)
        source = "fallback" if vol is not None else "missing"
        if vol is not None:
            print(f"  [vol] {coin_name}: using fallback vol {vol:.2f} (live candle data unavailable)")

    _vol_cache[coin_name] = (vol, now, source)
    _last_vol_source[coin_name] = source
    return vol


def get_last_vol_source(coin_name):
    return _last_vol_source.get(coin_name, "missing")

def orderbook_pressure_from_top_level(bids, asks):
    """Top-level size imbalance: +1 bullish, 0 neutral, -1 bearish."""
    try:
        if not bids or not asks:
            return 0
        bid_size = float(bids[0][1])
        ask_size = float(asks[0][1])
        total = bid_size + ask_size
        if total <= 0:
            return 0
        imbalance = bid_size / total
        if imbalance >= 0.65:
            return 1
        if imbalance <= 0.35:
            return -1
        return 0
    except Exception:
        return 0


def orderbook_pressure_from_depth(bids, asks, levels=10):
    """Depth size imbalance: +1 bullish, 0 neutral, -1 bearish."""
    try:
        bid_size = sum(float(row[1]) for row in bids[:levels])
        ask_size = sum(float(row[1]) for row in asks[:levels])
        total = bid_size + ask_size
        if total <= 0:
            return 0
        imbalance = bid_size / total
        if imbalance >= 0.62:
            return 1
        if imbalance <= 0.38:
            return -1
        return 0
    except Exception:
        return 0


def min_edge_for_ttl(ttl_min, coin_name=None):
    # TTL-based dynamic minimum
    if ttl_min > 12:
        base = 0.08
    elif ttl_min > 7:
        base = 0.06
    elif ttl_min > 3:
        base = 0.045
    else:
        base = 0.08
    # Per-coin minimum overrides TTL-based if larger
    coin_min = MIN_EDGE_BY_COIN.get(coin_name) if coin_name else None
    if coin_min is not None and coin_min > base:
        return coin_min
    return base


def max_entry_for_ttl(ttl_min):
    if ttl_min > 12:
        return 0.55
    if ttl_min > 7:
        return 0.65
    if ttl_min > 3:
        return 0.75
    return 0.35


def kalshi_blend_weight(ttl_min):
    """
    Blend model fair probability with Kalshi midpoint.

    Early in the window, trust the model more.
    Later in the window, trust Kalshi more because the market incorporates
    real-time information and the outcome may be nearly determined.
    """
    progress = max(0.0, min(1.0, 1.0 - ttl_min / 15.0))
    return min(0.75, 0.20 + progress * 0.55)


def spread_too_wide(yes_bid, yes_ask, no_bid, no_ask):
    yes_spread = max(0.0, yes_ask - yes_bid)
    no_spread = max(0.0, no_ask - no_bid)
    return min(yes_spread, no_spread) > 0.10


def hold_signal(
    reason,
    reasoning=None,
    entry_price=0,
    edge_cents=0,
    confidence=0,
    fair_yes=0.5,
    ttl_min=None,
    oi=None,
    strike=None,
    spot=None,
    kalshi_yes_mid=None,
    model_fair_yes=None,
    vol=None,
    extra=None,
):
    signal = {
        "side": "hold",
        "reason": reason,
        "entry_price": round(float(entry_price or 0), 4),
        "edge_cents": round(float(edge_cents or 0), 1),
        "edge_ratio": 0,
        "confidence": confidence,
        "predicted_fair_value": round(float(fair_yes if fair_yes is not None else 0.5), 4),
        "reasoning": reasoning or [],
        "strategy": "crypto_intel",
        "ttl_min": ttl_min,
        "open_interest": oi,
        "strike": strike,
        "spot_price": spot,
        "market_prob": kalshi_yes_mid * 100 if kalshi_yes_mid is not None else None,
        "model_fair_yes": model_fair_yes,
        "fair_yes": fair_yes,
        "fair_no": 1.0 - fair_yes if fair_yes is not None else None,
        "side_fair_value": None,
        "volatility": vol,
    }
    if extra:
        signal.update(extra)
    return signal


def block_large_model_market_disagreement(
    model_fair_yes, kalshi_yes_mid, fair_yes, reasoning, ttl_min, oi, strike, spot, vol, extra=None
):
    diff = abs(model_fair_yes - kalshi_yes_mid)
    if diff <= MAX_MODEL_MARKET_DISAGREEMENT:
        return None
    return hold_signal(
        reason="model_market_disagreement_too_large",
        reasoning=reasoning + [
            f"Raw model fair YES {model_fair_yes:.3f} disagrees with Kalshi YES mid {kalshi_yes_mid:.3f}.",
            f"Difference {diff:.3f} exceeds limit {MAX_MODEL_MARKET_DISAGREEMENT:.3f}.",
            "Blocking because the model is not calibrated enough to fade Kalshi this hard.",
        ],
        fair_yes=fair_yes,
        ttl_min=ttl_min,
        oi=oi,
        strike=strike,
        spot=spot,
        kalshi_yes_mid=kalshi_yes_mid,
        model_fair_yes=model_fair_yes,
        vol=vol,
        extra=extra,
    )


def _spot_direction(spot, strike):
    if not spot or not strike:
        return None, 0.0
    dist_pct = ((spot - strike) / strike) * 100.0
    if abs(dist_pct) < SPOT_STRIKE_DEADZONE_PCT:
        return "deadzone", dist_pct
    return ("yes" if dist_pct > 0 else "no"), dist_pct


def block_contrarian_entry_if_needed(
    side, kalshi_yes_mid, spot, strike, fair_yes, model_fair_yes,
    reasoning, entry_price, edge, ttl_min, oi, vol, extra=None, coin_name=None
):
    if ENABLE_CONTRARIAN_ENTRIES:
        return None
    # Look up per-coin limits; fall back to global UNDERDOG_BLOCK_THRESHOLD
    limits = CONTRARIAN_LIMITS.get(coin_name) if coin_name else None
    if limits:
        lower, upper = limits
    else:
        lower = upper = UNDERDOG_BLOCK_THRESHOLD
    if side == "yes" and kalshi_yes_mid < lower:
        return hold_signal(
            reason="blocked_contrarian_cheap_yes",
            reasoning=reasoning + [
                f"Blocked YES because Kalshi YES mid is {kalshi_yes_mid:.3f} < {lower:.2f} (coin limit for {coin_name or 'default'}).",
                "Safety rule: do not buy cheap underdog YES against Kalshi direction.",
                f"spot={spot}, strike={strike}, model_fair_yes={model_fair_yes:.3f}, fair_yes={fair_yes:.3f}.",
            ],
            entry_price=entry_price,
            edge_cents=edge * 100,
            confidence=0,
            fair_yes=fair_yes,
            ttl_min=ttl_min,
            oi=oi,
            strike=strike,
            spot=spot,
            kalshi_yes_mid=kalshi_yes_mid,
            model_fair_yes=model_fair_yes,
            vol=vol,
            extra=extra,
        )
    if side == "no" and kalshi_yes_mid >= upper:
        return hold_signal(
            reason="blocked_contrarian_cheap_no",
            reasoning=reasoning + [
                f"Blocked NO because Kalshi YES mid is {kalshi_yes_mid:.3f} >= {upper:.2f} (coin limit for {coin_name or 'default'}).",
                "Safety rule: do not buy cheap underdog NO against Kalshi direction.",
                f"spot={spot}, strike={strike}, model_fair_yes={model_fair_yes:.3f}, fair_yes={fair_yes:.3f}.",
            ],
            entry_price=entry_price,
            edge_cents=edge * 100,
            confidence=0,
            fair_yes=fair_yes,
            ttl_min=ttl_min,
            oi=oi,
            strike=strike,
            spot=spot,
            kalshi_yes_mid=kalshi_yes_mid,
            model_fair_yes=model_fair_yes,
            vol=vol,
            extra=extra,
        )
    return None


def require_direction_agreement(
    side, kalshi_yes_mid, spot, strike, fair_yes, model_fair_yes,
    reasoning, entry_price, edge, ttl_min, oi, vol, extra=None
):
    spot_dir, dist_pct = _spot_direction(spot, strike)
    kalshi_says_yes = kalshi_yes_mid >= 0.50
    spot_says_yes = spot_dir == "yes"
    model_says_yes = fair_yes >= 0.50

    if spot_dir == "deadzone":
        return hold_signal(
            reason="blocked_spot_strike_deadzone",
            reasoning=reasoning + [
                f"Blocked: spot/strike distance {dist_pct:.4f}% is inside dead zone {SPOT_STRIKE_DEADZONE_PCT:.4f}%.",
                "RTI settlement uses averaging; near-strike tick direction is not reliable enough for emergency mode.",
            ],
            entry_price=entry_price,
            edge_cents=edge * 100,
            confidence=0,
            fair_yes=fair_yes,
            ttl_min=ttl_min,
            oi=oi,
            strike=strike,
            spot=spot,
            kalshi_yes_mid=kalshi_yes_mid,
            model_fair_yes=model_fair_yes,
            vol=vol,
            extra=extra,
        )

    if side == "yes" and not (kalshi_says_yes and spot_says_yes and model_says_yes):
        return hold_signal(
            reason="blocked_direction_disagreement_yes",
            reasoning=reasoning + [
                "Blocked YES because Kalshi, spot, and model do not all agree on YES.",
                f"kalshi_says_yes={kalshi_says_yes}",
                f"spot_says_yes={spot_says_yes}",
                f"model_says_yes={model_says_yes}",
                f"kalshi_yes_mid={kalshi_yes_mid:.3f}",
                f"spot={spot}",
                f"strike={strike}",
                f"spot_minus_strike_pct={dist_pct:.4f}",
                f"model_fair_yes={model_fair_yes:.3f}",
                f"fair_yes={fair_yes:.3f}",
            ],
            entry_price=entry_price,
            edge_cents=edge * 100,
            confidence=0,
            fair_yes=fair_yes,
            ttl_min=ttl_min,
            oi=oi,
            strike=strike,
            spot=spot,
            kalshi_yes_mid=kalshi_yes_mid,
            model_fair_yes=model_fair_yes,
            vol=vol,
            extra=extra,
        )

    if side == "no" and (kalshi_says_yes or spot_says_yes or model_says_yes):
        return hold_signal(
            reason="blocked_direction_disagreement_no",
            reasoning=reasoning + [
                "Blocked NO because Kalshi, spot, and model do not all agree on NO.",
                f"kalshi_says_no={not kalshi_says_yes}",
                f"spot_says_no={spot_dir == 'no'}",
                f"model_says_no={not model_says_yes}",
                f"kalshi_yes_mid={kalshi_yes_mid:.3f}",
                f"spot={spot}",
                f"strike={strike}",
                f"spot_minus_strike_pct={dist_pct:.4f}",
                f"model_fair_yes={model_fair_yes:.3f}",
                f"fair_yes={fair_yes:.3f}",
            ],
            entry_price=entry_price,
            edge_cents=edge * 100,
            confidence=0,
            fair_yes=fair_yes,
            ttl_min=ttl_min,
            oi=oi,
            strike=strike,
            spot=spot,
            kalshi_yes_mid=kalshi_yes_mid,
            model_fair_yes=model_fair_yes,
            vol=vol,
            extra=extra,
        )
    return None


def already_have_open_market_position(market_ticker):
    """Prevent duplicate open positions in the same crypto market across paper/prod/microcap."""
    if not market_ticker:
        return True
    try:
        from hermes_db import query
        rows = query("""
            SELECT COUNT(*)
            FROM kalshi_trades
            WHERE market_ticker = %s
              AND status = 'open'
              AND strategy_name IN ('crypto_intel', 'crypto_intel_prod', 'crypto_intel_microcap')
        """, (market_ticker,))
        return bool(rows and int(rows[0][0]) > 0)
    except Exception as e:
        print(f"  Duplicate position check error for {market_ticker}: {e}")
        return True


def trade_debug_payload(market, signal):
    return {
        "ticker": market.get("market_ticker"),
        "title": market.get("title"),
        "side": signal.get("side"),
        "spot": signal.get("spot_price"),
        "strike": signal.get("strike"),
        "spot_minus_strike_pct": signal.get("spot_minus_strike_pct"),
        "ttl_min": signal.get("ttl_min"),
        "yes_bid": signal.get("yes_bid"),
        "yes_ask": signal.get("yes_ask"),
        "no_bid": signal.get("no_bid"),
        "no_ask": signal.get("no_ask"),
        "kalshi_yes_mid": signal.get("kalshi_yes_mid") or ((market.get("yes_bid", 0) + market.get("yes_ask", 0)) / 2.0 if market.get("yes_bid") is not None and market.get("yes_ask") is not None else None),
        "model_fair_yes": signal.get("model_fair_yes"),
        "fair_yes": signal.get("fair_yes"),
        "fair_no": signal.get("fair_no"),
        "yes_edge": signal.get("yes_edge"),
        "no_edge": signal.get("no_edge"),
        "chosen_side": signal.get("side"),
        "entry_price": signal.get("entry_price"),
        "edge_cents": signal.get("edge_cents"),
        "edge_ratio": signal.get("edge_ratio"),
        "vol": signal.get("volatility"),
        "vol_source": signal.get("vol_source"),
        "reason": signal.get("reason"),
    }


def print_trade_debug(market, signal):
    print("TRADE DEBUG", json.dumps(trade_debug_payload(market, signal), sort_keys=True))


def suggested_position_dollars(bankroll, entry_price, side_fair_value, max_fraction=0.02):
    """Fractional Kelly-style sizing, capped heavily. Not used to increase prod cap yet."""
    p = side_fair_value
    q = 1.0 - p
    if entry_price <= 0 or entry_price >= 1:
        return 0.0
    b = (1.0 - entry_price) / entry_price
    kelly = (b * p - q) / b
    if kelly <= 0:
        return 0.0
    fractional = kelly * 0.25
    return bankroll * min(fractional, max_fraction)


ENABLE_AUTO_EXITS = False
ENABLE_AUTO_HEDGING = False
EXIT_EDGE_TOLERANCE = 0.03


def evaluate_open_position_exit(position, market, fair_yes):
    """Logging-only exit recommendation. Does not trade unless auto exits enabled elsewhere."""
    side = position["side"]
    entry = float(position["entry_price"])
    qty = int(float(position["quantity"]))
    yes_bid = float(market.get("yes_bid", 0) or 0)
    no_bid = float(market.get("no_bid", 0) or 0)
    if side == "yes":
        current_exit_bid = yes_bid
        fair_hold_value = fair_yes
    else:
        current_exit_bid = no_bid
        fair_hold_value = 1.0 - fair_yes
    mark_pnl = (current_exit_bid - entry) * qty
    should_exit = current_exit_bid >= fair_hold_value - EXIT_EDGE_TOLERANCE
    return {
        "should_exit": should_exit,
        "side": side,
        "entry_price": entry,
        "current_exit_bid": current_exit_bid,
        "fair_hold_value": fair_hold_value,
        "quantity": qty,
        "mark_pnl": round(mark_pnl, 2),
        "reason": "exit_bid_near_or_above_fair_value" if should_exit else "hold_value_better_than_exit",
        "auto_exits_enabled": ENABLE_AUTO_EXITS,
    }


def evaluate_emergency_hedge(position, market, fair_yes):
    """Logging-only hedge evaluation. Never places hedge here."""
    side = position["side"]
    entry = float(position["entry_price"])
    qty = int(float(position["quantity"]))
    yes_ask = float(market.get("yes_ask", 0) or 0)
    no_ask = float(market.get("no_ask", 0) or 0)
    if side == "yes":
        opposite_ask = no_ask
        fair_hold_value = fair_yes
    else:
        opposite_ask = yes_ask
        fair_hold_value = 1.0 - fair_yes
    original_cost = entry * qty
    hedge_cost = opposite_ask * qty
    guaranteed_payout = 1.0 * qty
    locked_pnl = guaranteed_payout - original_cost - hedge_cost
    expected_hold_pnl = (fair_hold_value - entry) * qty
    return {
        "recommend_hedge": False,
        "side": side,
        "opposite_ask": opposite_ask,
        "locked_pnl": round(locked_pnl, 2),
        "expected_hold_pnl": round(expected_hold_pnl, 2),
        "hedge_better_by": round(locked_pnl - expected_hold_pnl, 2),
        "reason": "logging_only_auto_hedging_disabled",
        "auto_hedging_enabled": ENABLE_AUTO_HEDGING,
    }


def _get_market_signals(coin_name):
    """Fetch extra signals to build conviction: micro-trend, exchange divergence, orderbook pressure.
    
    Returns a dict with signal scores: +1 (bullish), 0 (neutral), -1 (bearish).
    """
    signals = {"micro_trend": 0, "exchange_div": 0, "orderbook": 0}
    
    asset_map = {
        "BTC": ("BTC-USD", "btcusd", "XXBTZUSD"),
        "ETH": ("ETH-USD", "ethusd", "XETHZUSD"),
        "SOL": ("SOL-USD", "solusd", "SOLUSD"),
        "XRP": ("XRP-USD", "xrpusd", "XRPUSD"),
        "DOGE": ("DOGE-USD", "dogeusd", "DOGEUSD"),
        "BNB": ("BNB-USD", "bnbusd", "BNBUSD"),
        "HYPE": ("HYPE-USD", "hypeusd", "HYPEUSD"),
    }.get(coin_name)
    if not asset_map:
        return signals

    cb_pair, gemini_pair, kraken_pair = asset_map
    
    # 1) Exchange divergence: Coinbase vs Gemini
    gemini_price = None
    try:
        req = Request(f'https://api.gemini.com/v1/pubticker/{gemini_pair}',
                      headers={'Accept': 'application/json'})
        data = json.loads(urlopen(req, timeout=6).read().decode())
        gemini_price = float(data['last'])
    except Exception:
        pass

    spot = fetch_spot_price(coin_name)
    if spot and gemini_price:
        diff_pct = ((spot - gemini_price) / gemini_price) * 100
        if diff_pct > 0.1:
            signals["exchange_div"] = 1   # Coinbase higher → bullish
        elif diff_pct < -0.1:
            signals["exchange_div"] = -1  # Coinbase lower → bearish
        # else neutral

    # 2) Micro-trend from Kraken 1-min candles
    try:
        req = Request(f'https://api.kraken.com/0/public/OHLC?pair={kraken_pair}&interval=1',
                      headers={'Accept': 'application/json'})
        data = json.loads(urlopen(req, timeout=8).read().decode())
        for pair_name, ohlc_data in data.get('result', {}).items():
            if isinstance(ohlc_data, list) and len(ohlc_data) >= 3:
                # Last 2 candles
                c2 = ohlc_data[-2]  # 1 min ago
                c1 = ohlc_data[-1]  # current candle
                prev_close = float(c2[4])
                curr_close = float(c1[4])
                if curr_close > prev_close * 1.0002:  # ≥ 0.02% up
                    signals["micro_trend"] = 1
                elif curr_close < prev_close * 0.9998:  # ≥ 0.02% down
                    signals["micro_trend"] = -1
                # else neutral
                break
    except Exception:
        pass

    # 3) Coinbase orderbook pressure (size imbalance, depth preferred)
    try:
        req = Request(f'https://api.exchange.coinbase.com/products/{cb_pair}/book?level=2',
                      headers={'Accept': 'application/json'})
        data = json.loads(urlopen(req, timeout=6).read().decode())
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        signals["orderbook"] = orderbook_pressure_from_depth(bids, asks, levels=10)
        if signals["orderbook"] == 0:
            signals["orderbook"] = orderbook_pressure_from_top_level(bids, asks)
    except Exception:
        pass

    return signals


def _get_momentum_baseline(series_ticker):
    """Neutral baseline for 15-min crypto markets.
    
    15-min binary options are essentially random walk — past window outcomes
    do NOT predict future windows. Momentum baselines introduce false signal.
    Always return 50/50 neutral baseline.
    
    Returns (baseline_prob, lookback_count, yes_count)
    """
    return 0.50, 0, 0


def fetch_crypto_markets(client=None):
    """Fetch current open crypto 15-min markets."""
    if client is None:
        from kalshi_client import KalshiClient
        client = KalshiClient()
    results = []
    for name, ticker, color, icon in SERIES:
        r = client.get(f"/markets?series_ticker={ticker}&limit=1&status=open")
        markets = r.get("markets", [])
        if markets:
            m = markets[0]
            yes_ask = float(m.get("yes_ask_dollars", 0))
            yes_bid = float(m.get("yes_bid_dollars", 0))
            no_ask = float(m.get("no_ask_dollars", 0))
            no_bid = float(m.get("no_bid_dollars", 0))
            results.append({
                "name": name, "color": color, "icon": icon,
                "market_ticker": m.get("ticker", ""),
                "event_ticker": m.get("event_ticker", ""),
                "series_ticker": ticker,
                "strike": m.get("floor_strike", 0),
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "no_bid": no_bid,
                "no_ask": no_ask,
                "open_interest": float(m.get("open_interest_fp", 0)),
                "volume_24h": float(m.get("volume_24h_fp", 0)),
                "close_time": m.get("close_time", ""),
                "status": m.get("status", "unknown"),
                "title": m.get("title", ""),
            })
        else:
            results.append({"name": name, "series_ticker": ticker, "error": "no_open_market"})
        time.sleep(0.2)
    return results


def evaluate_crypto_market(m):
    """Evaluate a crypto 15-min market for dashboard display (non-trading signal)."""
    if "error" in m:
        return m

    mid = (m["yes_bid"] + m["yes_ask"]) / 2
    spread = m["yes_ask"] - m["yes_bid"]
    prob = mid * 100
    edge = mid - 0.50
    ec = abs(edge)

    ttl_min = 0
    if m.get("close_time"):
        try:
            ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
            ttl_min = (ct - datetime.now(timezone.utc)).total_seconds() / 60
        except:
            pass

    if ttl_min < 0:
        conf = "expired"
    elif ec < 0.03:
        conf = "no_edge"
    elif ec < 0.05:
        conf = "small_edge"
    elif ec >= 0.10 and m["open_interest"] > 5000:
        conf = "strong"
    elif ec >= 0.07 and m["open_interest"] > 500:
        conf = "good"
    elif ec >= 0.05:
        conf = "weak"
    else:
        conf = "no_edge"

    return {
        "name": m["name"],
        "market_ticker": m.get("market_ticker", ""),
        "strike": m.get("strike", 0),
        "prob": round(prob, 1),
        "edge_cents": round(ec * 100, 1),
        "edge_dir": "up" if edge > 0 else "down",
        "spread": round(spread, 3),
        "oi": round(m["open_interest"], 0),
        "ttl": round(ttl_min, 1),
        "confidence": conf,
    }


def analyze_crypto_market(m):
    """Expected-value analyzer for crypto 15-min markets.

    Core rule: trade only when independent/blended fair probability exceeds
    executable ask by enough edge after spread, TTL, and uncertainty filters.
    """
    def hold(reason, entry_price=0, edge=0, confidence=0, reasoning=None, **extra):
        base = {
            "side": "hold",
            "reason": reason,
            "entry_price": round(float(entry_price or 0), 4),
            "edge_cents": round(float(edge or 0) * 100, 1),
            "edge_ratio": 0,
            "confidence": confidence,
            "predicted_fair_value": extra.get("fair_yes", 0.5),
            "spread": extra.get("spread", 0),
            "reasoning": reasoning or [],
            "strategy": "crypto_intel",
            "data_sources": extra.get("data_sources", {}),
            "ttl_min": extra.get("ttl_min", 0),
            "open_interest": extra.get("open_interest", 0),
            "strike": extra.get("strike", 0),
            "spot_price": extra.get("spot_price"),
            "market_prob": extra.get("market_prob"),
            "model_fair_yes": extra.get("model_fair_yes"),
            "fair_yes": extra.get("fair_yes"),
            "fair_no": extra.get("fair_no"),
            "side_fair_value": extra.get("side_fair_value"),
            "volatility": extra.get("volatility"),
            "vol_source": extra.get("vol_source"),
        }
        return base

    if "error" in m:
        return hold(m["error"], reasoning=[f"Market error: {m['error']}"])

    yes_bid = float(m.get("yes_bid", 0) or 0)
    yes_ask = float(m.get("yes_ask", 0) or 0)
    no_bid = float(m.get("no_bid", 0) or 0)
    no_ask = float(m.get("no_ask", 0) or 0)
    ttl_min = get_ttl_minutes(m.get("close_time", ""))
    strike = float(m.get("strike", 0) or 0)
    oi = float(m.get("open_interest", 0) or 0)
    coin = m.get("name", "")
    kalshi_yes_mid = (yes_bid + yes_ask) / 2.0 if yes_ask or yes_bid else 0.5
    market_prob = kalshi_yes_mid * 100
    yes_spread = max(0.0, yes_ask - yes_bid)
    no_spread = max(0.0, no_ask - no_bid)
    reasoning = []
    common = {
        "ttl_min": ttl_min,
        "open_interest": oi,
        "strike": strike,
        "market_prob": market_prob,
        "data_sources": {"kalshi": "orderbook"},
    }

    if ttl_min <= 1.5:
        return hold("too_close_to_expiry", reasoning=[f"Only {ttl_min:.1f}m left"], **common)

    if yes_ask <= 0 or no_ask <= 0:
        return hold("missing_ask", reasoning=["Missing executable ask price"], **common)

    if spread_too_wide(yes_bid, yes_ask, no_bid, no_ask):
        return hold(
            "spread_too_wide",
            reasoning=[f"Spread too wide: YES {yes_spread:.2f}, NO {no_spread:.2f}"],
            spread=min(yes_spread, no_spread),
            **common,
        )

    spot = fetch_spot_price(coin)
    vol = get_model_volatility(coin)
    vol_source = get_last_vol_source(coin)
    common["spot_price"] = spot
    common["volatility"] = vol
    common["vol_source"] = vol_source
    common["data_sources"] = {
        "kalshi": "orderbook",
        "spot": "coinbase" if spot else "missing",
        "volatility": vol_source,
    }

    if not spot or not strike or not vol:
        return hold(
            "missing_model_inputs",
            reasoning=[f"Missing model inputs: spot={spot}, strike={strike}, vol={vol}"],
            **common,
        )

    model_fair_yes = fair_yes_probability(
        spot=spot,
        strike=strike,
        annualized_vol=vol,
        minutes_left=ttl_min,
    )
    blend_weight = kalshi_blend_weight(ttl_min)
    fair_yes = model_fair_yes * (1.0 - blend_weight) + kalshi_yes_mid * blend_weight
    fair_yes = max(0.01, min(0.99, fair_yes))
    fair_no = 1.0 - fair_yes

    yes_edge = fair_yes - yes_ask
    no_edge = fair_no - no_ask

    spot_dir, dist_pct = _spot_direction(spot, strike)
    debug_fields = {
        "model_fair_yes": model_fair_yes,
        "fair_yes": fair_yes,
        "fair_no": fair_no,
        "spot_minus_strike_pct": dist_pct,
        "yes_edge": yes_edge,
        "no_edge": no_edge,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "vol_source": vol_source,
        "data_sources": common["data_sources"],
        "market_prob": market_prob,
    }
    common.update(debug_fields)

    reasoning.append(f"Spot ${spot:,.2f}, strike ${strike:,.2f}, TTL {ttl_min:.1f}m")
    reasoning.append(f"Spot minus strike: {dist_pct:.4f}% ({spot_dir or 'unknown'})")
    reasoning.append(f"Annualized realized vol estimate: {vol:.2f} ({vol_source})")
    if vol_source == "fallback":
        reasoning.append(f"Fallback vol used ({vol:.2f}) — live candle data unavailable")
    reasoning.append(f"Model fair YES: {model_fair_yes:.3f}")
    reasoning.append(f"Kalshi YES mid: {kalshi_yes_mid:.3f}, blend weight: {blend_weight:.2f}")
    reasoning.append(f"Final fair YES: {fair_yes:.3f}, fair NO: {fair_no:.3f}")

    market_disagreement_block = block_large_model_market_disagreement(
        model_fair_yes=model_fair_yes,
        kalshi_yes_mid=kalshi_yes_mid,
        fair_yes=fair_yes,
        reasoning=reasoning,
        ttl_min=ttl_min,
        oi=oi,
        strike=strike,
        spot=spot,
        vol=vol,
        extra=common,
    )
    if market_disagreement_block:
        return market_disagreement_block

    reasoning.append(f"YES edge: {yes_edge * 100:.1f}c at ask {yes_ask:.2f}")
    reasoning.append(f"NO edge: {no_edge * 100:.1f}c at ask {no_ask:.2f}")

    # Extra signals are no longer the source of truth, but remain useful for logging/confidence.
    extra_signals = _get_market_signals(coin)
    signal_score = sum(extra_signals.values())
    sig_labels = {"micro_trend": "1m trend", "exchange_div": "exchange", "orderbook": "orderbook"}
    sig_texts = []
    for k, v in extra_signals.items():
        if v == 1:
            sig_texts.append(f"{sig_labels[k]}=bullish")
        elif v == -1:
            sig_texts.append(f"{sig_labels[k]}=bearish")
    reasoning.append(f"Signals: {', '.join(sig_texts) if sig_texts else 'neutral'} (score={signal_score:+d})")

    if yes_edge >= no_edge:
        side = "yes"
        entry_price = yes_ask
        edge = yes_edge
        side_fair = fair_yes
        spread = yes_spread
    else:
        side = "no"
        entry_price = no_ask
        edge = no_edge
        side_fair = fair_no
        spread = no_spread

    required_edge = min_edge_for_ttl(ttl_min, coin_name=coin)
    max_entry = max_entry_for_ttl(ttl_min)
    edge_ratio = edge / max(entry_price, 0.01)

    common.update({
        "side_fair_value": side_fair,
        "spread": spread,
        "edge_ratio": round(edge_ratio, 3),
    })

    if edge < required_edge:
        return hold(
            "edge_too_small",
            entry_price=entry_price,
            edge=edge,
            reasoning=reasoning + [f"Best edge {edge * 100:.1f}c < required {required_edge * 100:.1f}c"],
            **common,
        )

    if entry_price > max_entry:
        return hold(
            "entry_too_expensive_for_ttl",
            entry_price=entry_price,
            edge=edge,
            reasoning=reasoning + [f"Entry {entry_price:.2f} > max {max_entry:.2f} for TTL bucket"],
            **common,
        )

    # YES asymmetry guard: 52.9% accuracy means YES at high prices
    # loses more than it wins because of asymmetric payout (lose entry,
    # win spread). NO doesn't have this problem. Drop this cap once
    # isotonic calibration is fit and YES accuracy improves.
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
                "NO side has no equivalent block — only YES is restricted.",
            ],
            **common,
        )

    if edge_ratio < MIN_EDGE_RATIO:
        h = hold(
            "edge_ratio_too_small",
            entry_price=entry_price,
            edge=edge,
            reasoning=reasoning + [f"Edge ratio {edge_ratio:.2f} < {MIN_EDGE_RATIO:.2f}"],
            **common,
        )
        h["edge_ratio"] = round(edge_ratio, 3)
        return h

    if spot_dir == "deadzone":
        return hold_signal(
            reason="blocked_spot_strike_deadzone",
            reasoning=reasoning + [
                f"Blocked: spot/strike distance {dist_pct:.4f}% is inside dead zone {SPOT_STRIKE_DEADZONE_PCT:.4f}%.",
                "RTI settlement uses averaging; near-strike tick direction is not reliable enough for emergency mode.",
            ],
            entry_price=entry_price,
            edge_cents=edge * 100,
            confidence=0,
            fair_yes=fair_yes,
            ttl_min=ttl_min,
            oi=oi,
            strike=strike,
            spot=spot,
            kalshi_yes_mid=kalshi_yes_mid,
            model_fair_yes=model_fair_yes,
            vol=vol,
            extra=common,
        )

    contrarian_block = block_contrarian_entry_if_needed(
        side=side,
        kalshi_yes_mid=kalshi_yes_mid,
        spot=spot,
        strike=strike,
        fair_yes=fair_yes,
        model_fair_yes=model_fair_yes,
        reasoning=reasoning,
        entry_price=entry_price,
        edge=edge,
        ttl_min=ttl_min,
        oi=oi,
        vol=vol,
        extra=common,
        coin_name=coin,
    )
    if contrarian_block:
        return contrarian_block

    direction_block = require_direction_agreement(
        side=side,
        kalshi_yes_mid=kalshi_yes_mid,
        spot=spot,
        strike=strike,
        fair_yes=fair_yes,
        model_fair_yes=model_fair_yes,
        reasoning=reasoning,
        entry_price=entry_price,
        edge=edge,
        ttl_min=ttl_min,
        oi=oi,
        vol=vol,
        extra=common,
    )
    if direction_block:
        return direction_block

    # Conservative ranking/sizing confidence, not a calibrated probability.
    confidence = 0.25
    if edge >= 0.12:
        confidence += 0.25
    elif edge >= 0.08:
        confidence += 0.15
    elif edge >= 0.05:
        confidence += 0.08

    if oi >= 1000:
        confidence += 0.10
    elif oi >= 250:
        confidence += 0.05

    if spread <= 0.03:
        confidence += 0.05
    elif spread >= 0.08:
        confidence -= 0.08

    if ttl_min <= 3:
        confidence -= 0.10
    if vol_source == "fallback":
        confidence -= 0.10

    expected_direction = 1 if side == "yes" else -1
    signal_agreement = signal_score * expected_direction
    if signal_agreement >= 2:
        confidence += 0.08
    elif signal_agreement <= -2:
        confidence -= 0.08

    confidence = max(0.10, min(0.85, confidence))

    return {
        "side": side,
        "reason": "positive_ev_direction_agreement_signal",
        "entry_price": round(entry_price, 4),
        "expected_profit": round(edge, 4),
        "edge_cents": round(edge * 100, 1),
        "edge_ratio": round(edge_ratio, 3),
        "confidence": round(confidence, 3),
        "predicted_fair_value": round(fair_yes, 4),
        "side_fair_value": round(side_fair, 4),
        "spread": round(spread, 4),
        "spread_cents": round(spread * 100, 1),
        "reasoning": reasoning + [
            f"TRADE {side.upper()}: fair {side_fair:.3f} vs ask {entry_price:.2f}, edge {edge * 100:.1f}c",
            "Trade allowed because Kalshi, spot, and model direction agree.",
        ],
        "strategy": "crypto_intel",
        "data_sources": common["data_sources"],
        "ttl_min": ttl_min,
        "open_interest": oi,
        "strike": strike,
        "spot_price": spot,
        "market_prob": market_prob,
        "model_fair_yes": model_fair_yes,
        "fair_yes": fair_yes,
        "fair_no": fair_no,
        "volatility": vol,
        "vol_source": vol_source,
        "signal_score": signal_score,
        "extra_signals": extra_signals,
        "spot_minus_strike_pct": dist_pct,
        "kalshi_yes_mid": kalshi_yes_mid,
        "yes_edge": yes_edge,
        "no_edge": no_edge,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": no_bid,
        "no_ask": no_ask,
    }

def log_decision(market, signal, was_executed=False, trade_id=None):
    """Log a single decision to kalshi_decision_log. Safe to call any time."""
    try:
        from hermes_db import execute
        execute("""
            INSERT INTO kalshi_decision_log
                (strategy_name, market_ticker, event_ticker, series_ticker,
                 coin_name, market_title, action, side, entry_price,
                 fair_value, market_prob, edge_cents, confidence, spread,
                 open_interest, ttl_minutes, strike_price, reasoning,
                 spot_price, was_executed, trade_id, cycle_number,
                 model_fair_yes, fair_yes, fair_no, side_fair_value,
                 edge_ratio, volatility, exit_recommendation, hedge_evaluation)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            signal.get("strategy", "crypto_intel"),
            market.get("market_ticker", ""),
            market.get("event_ticker", ""),
            market.get("series_ticker", ""),
            market.get("name", ""),
            market.get("title", "")[:200],
            signal.get("reason", "unknown"),
            signal.get("side", "hold"),
            signal.get("entry_price"),
            signal.get("predicted_fair_value"),
            signal.get("market_prob"),
            signal.get("edge_cents"),
            signal.get("confidence"),
            signal.get("spread"),
            signal.get("open_interest"),
            signal.get("ttl_min"),
            signal.get("strike"),
            "\n".join(signal.get("reasoning", []))[:1000],
            signal.get("spot_price"),
            was_executed,
            trade_id,
            _next_cycle(),
            signal.get("model_fair_yes"),
            signal.get("fair_yes"),
            signal.get("fair_no"),
            signal.get("side_fair_value"),
            signal.get("edge_ratio"),
            signal.get("volatility"),
            json.dumps(signal.get("exit_recommendation")) if signal.get("exit_recommendation") is not None else None,
            json.dumps(signal.get("hedge_evaluation")) if signal.get("hedge_evaluation") is not None else None,
        ))
    except Exception as e:
        print(f"  [crypto_intel] Log error: {e}", file=__import__('sys').stderr)


def _check_exits(client):
    """Check open crypto positions, settle expired markets. Returns count."""
    from hermes_db import query, get_conn
    exited = 0
    try:
        open_positions = query("""
            SELECT id, market_ticker, side, entry_price, quantity, event_ticker
            FROM kalshi_trades
            WHERE strategy_name = 'crypto_intel' AND status IN ('open','pending_settlement')
        """)
        if not open_positions:
            return 0

        for pos in open_positions:
            tid, ticker, side, entry, qty, event = pos
            entry = float(entry)
            # Use events endpoint — markets endpoint doesn't return status/result
            event_data = client.get(f"/events/{event}")
            if not event_data or 'markets' not in event_data:
                continue
            # Find our specific market within the event
            m = None
            for sm in event_data['markets']:
                if sm.get('ticker') == ticker:
                    m = sm
                    break
            if not m:
                continue
            close_time = m.get('close_time', '')
            status = m.get('status', '')

            should_settle = False
            settle = 0.0
            reason = ""

            result = m.get('result', '').lower()
            if status in ('finalized', 'settled', 'determined') and result in ('yes', 'no'):
                settle = 1.0 if result == side else 0.0
                should_settle = True
                reason = f"finalized(result={result})"
            elif close_time:
                try:
                    ct = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                    if ct < datetime.now(timezone.utc):
                        conn = get_conn()
                        try:
                            cur = conn.cursor()
                            cur.execute("UPDATE kalshi_trades SET status='pending_settlement', exit_reason='expired_awaiting_result' WHERE id=%s AND status <> 'pending_settlement'", (tid,))
                            conn.commit()
                            print(f"  PENDING [{tid}] {ticker[:25]}: expired, awaiting result")
                        except Exception as e:
                            conn.rollback()
                            print(f"  Pending-settlement error [{tid}]: {e}")
                        finally:
                            cur.close()
                            conn.close()
                except Exception:
                    pass

            if should_settle:
                pnl = round((settle - entry) * qty, 2)
                proceed = round(settle * qty, 2)
                conn = get_conn()
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE kalshi_trades SET status='closed', exit_price=%s, pnl=%s, exit_time=NOW(), exit_reason=%s WHERE id=%s",
                               (settle, pnl, reason, tid))
                    cur.execute("UPDATE kalshi_portfolio SET current_balance = current_balance + %s, "
                               "total_realized_pnl = total_realized_pnl + %s "
                               "WHERE id = 1", (proceed, pnl))
                    if pnl >= 0:
                        cur.execute("UPDATE kalshi_portfolio SET win_count = win_count + 1 WHERE id = 1")
                    else:
                        cur.execute("UPDATE kalshi_portfolio SET loss_count = loss_count + 1 WHERE id = 1")
                    cur.execute("""
                        UPDATE kalshi_decision_log
                        SET resolved_yes = %s, result = %s
                        WHERE trade_id = %s
                          AND resolved_yes IS NULL
                    """, (result == 'yes', result, tid))
                    conn.commit()
                    print(f"  SETTLE [{tid}] {ticker[:25]}: {reason} P&L=${pnl:+.2f}")
                    exited += 1
                except Exception as e:
                    conn.rollback()
                    print(f"  Settle error [{tid}]: {e}")
                finally:
                    cur.close()
                    conn.close()
    except Exception as e:
        print(f"  Exit check error: {e}", file=__import__('sys').stderr)
    return exited


def scan_and_log(client=None):
    """
    Full cycle: fetch all markets, analyze each, log every decision,
    execute trades where there's edge.
    Returns summary dict.
    """
    from kalshi_client import KalshiClient
    if client is None:
        client = KalshiClient()

    # Heartbeat — dead man's switch
    try:
        from hermes_db import execute
        execute("""
            INSERT INTO kalshi_heartbeat (strategy_name, last_seen, status)
            VALUES ('crypto_intel', NOW(), 'ok')
            ON CONFLICT (strategy_name)
            DO UPDATE SET last_seen = NOW(), status = 'ok'
        """)
    except Exception:
        pass  # never let heartbeat failures block the cycle

    ts = datetime.now(timezone.utc)
    print(f"\n[{ts.strftime('%H:%M:%S')}] Crypto scan cycle")

    markets = fetch_crypto_markets(client)
    results = []
    entries = []
    signals_by_name = {}

    # Step 1: Check and settle expired positions
    exited = _check_exits(client)
    if exited:
        print(f"  Settled: {exited} positions")

    # Step 2: Check capital deployed by strategy
    CRYPTO_BUDGET = 4000      # $4k max capital at risk for crypto 15-min
    MAX_PER_COIN = 3           # max concurrent positions per coin
    try:
        from hermes_db import query
        crypt_used_q = query("SELECT COALESCE(SUM(entry_price * quantity), 0) FROM kalshi_trades WHERE strategy_name='crypto_intel' AND status='open'")
        crypt_used = float(crypt_used_q[0][0])

        # Per-coin open counts (fetch once)
        positions = query("SELECT series_ticker, count(*) FROM kalshi_trades WHERE strategy_name='crypto_intel' AND status='open' GROUP BY series_ticker")
        coin_counts = {r[0]: r[1] for r in positions}
    except Exception:
        crypt_used = 0
        coin_counts = {}

    # Step 3: Analyze markets and enter trades
    for m in markets:
        signal = analyze_crypto_market(m)
        signals_by_name[m.get("name", "?")] = signal
        is_trade = signal["side"] in ("yes", "no") and signal.get("confidence", 0) > 0.15

        if is_trade:
            ticker = m.get("market_ticker", "")
            if already_have_open_market_position(ticker):
                print(f"  [{m['name']}] {ticker}: already have open position — skip duplicate")
                signal = {**signal, "side": "hold", "reason": "duplicate_market_position", "entry_price": 0}
                signals_by_name[m.get("name", "?")] = signal
                is_trade = False

        if is_trade:
            price = signal["entry_price"]
            conf = signal.get("confidence", 0.5)
            qty = max(10, min(int(50 * conf * 3), 200))
            cost = round(price * qty, 2)

            # Capital budget check
            if crypt_used + cost > CRYPTO_BUDGET:
                is_trade = False
                print(f"  [{m['name']}] Budget ${crypt_used:.0f}+${cost:.0f} > ${CRYPTO_BUDGET} — skip")

            # Per-coin limit
            series = m.get("series_ticker", "")
            coin_count = coin_counts.get(series, 0)
            if is_trade and coin_count >= MAX_PER_COIN:
                is_trade = False
                print(f"  [{m['name']}] {coin_count} >= {MAX_PER_COIN} per-coin limit — skip")

            if is_trade:
                crypt_used += cost  # reserve for next iterations in same cycle

        trade_id = None
        if is_trade:
            print_trade_debug(m, signal)
            tid, cost = _execute_trade(m, signal)
            if tid:
                trade_id = tid
                entries.append({"name": m.get("name", "?"), "side": signal["side"],
                                "entry": signal["entry_price"], "cost": cost,
                                "conf": signal["confidence"], "edge": signal["edge_cents"]})

        log_decision(m, signal, was_executed=is_trade, trade_id=trade_id)
        results.append({"market": m.get("name", "?"), "signal": signal["side"],
                        "confidence": signal.get("confidence", 0), "edge": signal.get("edge_cents", 0)})

    # Portfolio status
    try:
        from hermes_db import query
        port = query("SELECT current_balance, total_realized_pnl, win_count, loss_count FROM kalshi_portfolio WHERE id = 1")
        if port:
            b, p, w, l = port[0]
            print(f"  Portfolio: ${float(b):.2f} (P&L: ${float(p or 0):+.2f}) W:{w} L:{l}")
    except Exception as e:
        print(f"  Portfolio query error: {e}")

    if entries:
        for e in entries:
            print(f"  ENTER {e['name']}: {e['side'].upper()} @ ${e['entry']:.4f} cost=${e['cost']:.2f} edge={e['edge']}c conf={e['conf']:.2f}")
    else:
        print("  No entries this cycle")

    # Write cache for dashboard
    write_cache(markets, precomputed_signals=signals_by_name)

    return {"timestamp": ts, "markets": len(markets), "entries": len(entries), "details": results}


def _execute_trade(market, signal):
    """Execute a paper trade — log to kalshi_trades and update portfolio."""
    try:
        from hermes_db import get_conn
        import psycopg2.extras
        conn = get_conn()
        try:
            cur = conn.cursor()
            ticker = market.get("market_ticker", "")
            if already_have_open_market_position(ticker):
                print(f"    Duplicate open position for {ticker}; refusing trade insert")
                conn.close()
                return None, None
            event = market.get("event_ticker", "")
            series = market.get("series_ticker", "")
            price = signal["entry_price"]

            # Scale position by confidence
            base_qty = 50
            conf = signal.get("confidence", 0.5)
            qty = max(10, min(int(base_qty * conf * 3), 200))
            cost = round(price * qty, 2)

            # Check balance
            cur.execute("SELECT current_balance FROM kalshi_portfolio WHERE id = 1")
            bal = cur.fetchone()
            if not bal or float(bal[0]) < cost:
                print(f"    Insufficient balance (${float(bal[0]):.2f} < ${cost:.2f})" if bal else "    No portfolio found")
                conn.close()
                return None, None

            # Insert trade
            cur.execute("""
                INSERT INTO kalshi_trades
                    (portfolio_id, market_ticker, event_ticker, series_ticker,
                     market_title, side, entry_price, quantity, strategy_name,
                     status, confidence, predicted_fair_value,
                     edge_cents, reasoning_json, data_sources)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                1, ticker, event, series,
                f"Crypto 15-min {market.get('name', '')}",
                signal["side"], f"{price:.4f}", qty,
                "crypto_intel", "open",
                signal.get("confidence"), signal.get("predicted_fair_value"),
                signal.get("edge_cents"),
                json.dumps(signal.get("reasoning", [])),
                json.dumps(signal.get("data_sources", {})),
            ))
            trade_id = cur.fetchone()[0]

            # Deduct from portfolio
            cur.execute("UPDATE kalshi_portfolio SET current_balance = current_balance - %s WHERE id = 1", (cost,))

            conn.commit()
            cur.close()
            conn.close()
            return trade_id, cost
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"    Trade execution error: {e}")
            return None, None

    except Exception as e:
        print(f"    Trade connection error: {e}")
        return None, None


def write_cache(markets, precomputed_signals=None):
    """Write current crypto market data + analysis to cache file for dashboard."""
    precomputed_signals = precomputed_signals or {}
    try:
        cache = {"_ts": time.time(), "_markets": []}
        for m in markets:
            if "error" in m:
                cache["_markets"].append({"name": m["name"], "error": m["error"]})
                continue
            sig = precomputed_signals.get(m.get("name")) or analyze_crypto_market(m)
            ev = evaluate_crypto_market(m)
            cache["_markets"].append({
                "name": m["name"], "icon": m.get("icon", "?"),
                "color": m.get("color", "#888"),
                "yes_bid": m.get("yes_bid", 0), "yes_ask": m.get("yes_ask", 0),
                "prob": ev.get("prob", 0),
                "signal": sig.get("side", "hold"),
                "edge": sig.get("edge_cents", 0),
                "conf": sig.get("confidence", 0),
                "spot": sig.get("spot_price"),
                "oi": m.get("open_interest", 0),
                "baseline": round(sig.get("momentum_baseline", 0.5) * 100, 0) if sig.get("lookback", 0) >= 2 else None,
            })
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"  Cache write error: {e}", file=__import__('sys').stderr)


def scan_micro_cap(client=None):
    """Micro-cap mode for $10-20 real-money trading.

    Picks the single best signal across all 7 coins and enters ONE
    concentrated trade per cycle. Skips all others.
    """
    from hermes_db import query, get_conn
    from kalshi_client import KalshiClient
    if client is None:
        client = KalshiClient()

    # Load micro-cap params
    try:
        row = query("SELECT params FROM kalshi_strategy_params WHERE strategy_name='crypto_intel_microcap' ORDER BY version DESC LIMIT 1")
        cfg = row[0][0] if row else {}
    except Exception:
        cfg = {}

    min_edge = cfg.get("min_edge_cents", 15)
    min_conf = cfg.get("min_confidence", 0.60)
    min_oi = cfg.get("min_oi", 500)
    max_risk = cfg.get("max_risk_pct", 0.50)
    halt_floor = cfg.get("halt_below_dollars", 5)
    max_entry = cfg.get("max_entry_price", 0.25)  # Tighter for micro-cap: max 25¢

    ts = datetime.now(timezone.utc)
    print(f"\n[{ts.strftime('%H:%M:%S')}] Micro-Cap Scan")

    # Get bankroll (current_balance = all available cash)
    port = query("SELECT current_balance FROM kalshi_portfolio WHERE id = 1")
    if not port:
        print("  No portfolio found")
        return
    bankroll = float(port[0][0])
    print(f"  Bankroll: ${bankroll:.2f}")

    if bankroll < halt_floor:
        print(f"  BANKROLL < ${halt_floor} — HALTED")
        return

    # Fetch all markets
    markets = fetch_crypto_markets(client)

    # Score each market
    best = None
    best_score = 0
    for m in markets:
        if "error" in m:
            continue
        if m.get("open_interest", 0) < min_oi:
            continue
        sig = analyze_crypto_market(m)
        if sig.get("side") not in ("yes", "no"):
            continue
        edge = sig.get("edge_cents", 0)
        conf = sig.get("confidence", 0)
        if edge < min_edge or conf < min_conf:
            continue
        score = edge * conf
        if score > best_score:
            best_score = score
            best = (m, sig)

    if not best:
        print("  No market meets micro-cap thresholds — HOLD")
        write_cache(markets)
        return

    m, sig = best
    ticker = m.get("market_ticker", "")
    if already_have_open_market_position(ticker):
        print(f"  {ticker}: already have open position — skip duplicate")
        log_decision(m, {**sig, "side": "hold", "reason": "duplicate_market_position", "entry_price": 0, "strategy": "crypto_intel_microcap"}, was_executed=False)
        write_cache(markets)
        return

    price = sig["entry_price"]
    # Position: up to 50% of bankroll in one trade, adjusted by side multiplier
    side_mult = SIZE_MULTIPLIER_BY_SIDE.get(sig.get("side", ""), 1.0)
    pos_dollars = min(bankroll * max_risk, bankroll * 0.50) * side_mult
    qty = max(1, int(pos_dollars / price))
    cost = round(price * qty, 2)

    print(f"  BEST: {m['name']} | edge={sig['edge_cents']}c conf={sig['confidence']:.2f} score={best_score:.1f}")
    print_trade_debug(m, sig)
    print(f"  Enter: {sig['side'].upper()} @ ${price:.4f} x {qty} = ${cost:.2f} ({cost/bankroll*100:.0f}% of bankroll)")

    # Execute
    trade_id = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kalshi_trades
                (portfolio_id, market_ticker, event_ticker, series_ticker,
                 market_title, side, entry_price, quantity, strategy_name,
                 status, confidence, predicted_fair_value,
                 edge_cents, reasoning_json, data_sources)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            1, m.get("market_ticker",""), m.get("event_ticker",""), m.get("series_ticker",""),
            f"Crypto 15-min {m['name']}",
            sig["side"], f"{price:.4f}", qty,
            "crypto_intel_microcap", "open",
            sig.get("confidence"), sig.get("predicted_fair_value"),
            sig.get("edge_cents"),
            json.dumps(sig.get("reasoning", [])),
            json.dumps(sig.get("data_sources", {})),
        ))
        trade_id = cur.fetchone()[0]
        cur.execute("UPDATE kalshi_portfolio SET current_balance = current_balance - %s WHERE id = 1", (cost,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"  Trade [{trade_id}] entered")
    except Exception as e:
        print(f"  Trade error: {e}")

    # Log decision
    try:
        from hermes_db import execute
        execute("""
            INSERT INTO kalshi_decision_log
                (strategy_name, market_ticker, event_ticker, series_ticker,
                 coin_name, action, side, entry_price, fair_value, market_prob,
                 edge_cents, confidence, spread, open_interest, ttl_minutes,
                 strike_price, reasoning, was_executed, trade_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            "crypto_intel_microcap",
            m.get("market_ticker",""), m.get("event_ticker",""), m.get("series_ticker",""),
            m.get("name",""), "microcap_entry", sig["side"],
            price, sig.get("predicted_fair_value"), sig.get("market_prob"),
            sig.get("edge_cents"), sig.get("confidence"), sig.get("spread"),
            m.get("open_interest",0), sig.get("ttl_min"),
            sig.get("strike"),
            "\n".join(sig.get("reasoning",[]))[:500],
            True, trade_id,
        ))
    except Exception as e:
        print(f"  Log error: {e}")

    # Check exits on any existing micro-cap positions too
    try:
        open_pos = query("""
            SELECT id, market_ticker, side, entry_price, quantity, event_ticker
            FROM kalshi_trades
            WHERE strategy_name='crypto_intel_microcap' AND status IN ('open','pending_settlement')
        """)
        if open_pos:
            for p in open_pos:
                _settle_one_trade(client, p[0], p[1], p[2], float(p[3]), p[4], p[5])
    except Exception as e:
        print(f"  Exit check error: {e}")

    write_cache(markets)
    print(f"  Bankroll after: ${float(query('SELECT current_balance FROM kalshi_portfolio WHERE id=1')[0][0]):.2f}")


def _settle_one_trade(client, tid, ticker, side, entry, qty, event):
    """Settle a single expired/determined trade. Shared by scan_and_log and micro_cap."""
    from hermes_db import get_conn
    try:
        event_data = client.get(f"/events/{event}")
        if not event_data or 'markets' not in event_data:
            return
        m = None
        for sm in event_data['markets']:
            if sm.get('ticker') == ticker:
                m = sm
                break
        if not m:
            return
        status = m.get('status', '')
        close_time = m.get('close_time', '')
        should_settle = False
        settle = 0.0
        reason = ""
        result = m.get('result', '').lower()
        if status in ('finalized', 'settled', 'determined') and result in ('yes', 'no'):
            settle = 1.0 if result == side else 0.0
            should_settle = True
            reason = f"finalized({result})"
        elif close_time:
            try:
                ct = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                if ct < datetime.now(timezone.utc):
                    conn = get_conn()
                    try:
                        cur = conn.cursor()
                        cur.execute("UPDATE kalshi_trades SET status='pending_settlement', exit_reason='expired_awaiting_result' WHERE id=%s AND status <> 'pending_settlement'", (tid,))
                        conn.commit()
                        print(f"    PENDING [{tid}] {ticker[:25]}: expired, awaiting result")
                    except Exception as e:
                        conn.rollback()
                        print(f"    Pending-settlement error [{tid}]: {e}")
                    finally:
                        cur.close()
                        conn.close()
            except Exception:
                pass
        if should_settle:
            pnl = round((settle - entry) * qty, 2)
            proceed = round(settle * qty, 2)
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE kalshi_trades SET status='closed', exit_price=%s, pnl=%s, exit_time=NOW(), exit_reason=%s WHERE id=%s",
                           (settle, pnl, reason, tid))
                cur.execute("UPDATE kalshi_portfolio SET current_balance = current_balance + %s, "
                           "total_realized_pnl = total_realized_pnl + %s "
                           "WHERE id = 1", (proceed, pnl))
                if pnl >= 0:
                    cur.execute("UPDATE kalshi_portfolio SET win_count = win_count + 1 WHERE id = 1")
                else:
                    cur.execute("UPDATE kalshi_portfolio SET loss_count = loss_count + 1 WHERE id = 1")
                cur.execute("""
                    UPDATE kalshi_decision_log
                    SET resolved_yes = %s, result = %s
                    WHERE market_ticker = %s
                      AND was_executed = TRUE
                      AND resolved_yes IS NULL
                """, (result == 'yes', result, ticker))
                conn.commit()
                print(f"    SETTLE [{tid}] {ticker[:25]}: {reason} P&L=${pnl:+.2f}")
            except Exception as e:
                conn.rollback()
                print(f"    Settle error [{tid}]: {e}")
            finally:
                cur.close()
                conn.close()
    except Exception:
        pass
