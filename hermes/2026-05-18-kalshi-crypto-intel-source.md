# crypto_intel source dump

**Generated:** 2026-05-18T09:30:11.250756
**Repo path:** /root/.hermes/scripts/
**Files included:** crypto_intel.py, hermes_db.py, kalshi-crypto-prod, kalshi-crypto-scan, kalshi_client.py, path_tracker.py

## crypto_intel.py

```python
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

# Shared market snapshot cache — paper and prod both call fetch_crypto_markets()
# independently, getting different results due to timing. This cache ensures
# both see the same snapshot if called within MARKET_CACHE_TTL seconds.
_MARKET_CACHE = {"ts": 0, "data": None}
MARKET_CACHE_TTL = 15  # seconds

# Side-based sizing multiplier.
# NO bets historically 94% correct, YES bets 53% correct.
# Half-size on YES preserves learning; full-size on NO.
# As v2 data accumulates, adjust toward 1.0 if the asymmetry narrows.
SIZE_MULTIPLIER_BY_SIDE = {
    'no':  1.0,
    'yes': 0.5,
}

from path_tracker import get_window_path, compute_path_metrics

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
MIN_EDGE_CENTS = 8              # DEPRECATED — not referenced. Use MIN_EDGE_BY_COIN instead.
HARD_MAX_ENTRY_PRICE = 0.75
SPOT_STRIKE_DEADZONE_PCT = 0.02  # avoid treating RTI/noisy near-strike tick as direction

# Per-coin edge minimums (in dollars, e.g. 0.10 = 10c).
# Overrides the TTL-based dynamic edge for specific coins.
# Higher = tighter filter, lower = more trades.
#
# Based on v1 per-coin P&L:
#   BTC:  -$163 (worst — needs 10c min edge)
#   HYPE: -$41
#   BNB:  -$47
#   ETH:  +$253
#   SOL:  +$245
#   XRP:  +$359
#   DOGE: +$213
MIN_EDGE_BY_COIN = {
    'BTC':  0.10,
    'BNB':  0.08,
    'HYPE': 0.08,
    'ETH':  0.04,
    'SOL':  0.04,
    'XRP':  0.04,
    'DOGE': 0.04,
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
    # TTL-based dynamic minimum, relaxed to match MIN_EDGE_CENTS=3
    if ttl_min > 12:
        base = 0.04    # was 0.08
    elif ttl_min > 7:
        base = 0.03    # was 0.06
    elif ttl_min > 3:
        base = 0.03    # was 0.045
    else:
        base = 0.04    # was 0.08
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
                "Safety rule: do not buy cheap underdog NO 

... [OUTPUT TRUNCATED - 39411 chars omitted out of 89411 total] ...

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
                    # Also label all hold decisions for this market in the same window
                    cur.execute("""
                        UPDATE kalshi_decision_log
                        SET resolved_yes = %s, result = %s
                        WHERE market_ticker = %s
                          AND resolved_yes IS NULL
                          AND scan_time > NOW() - INTERVAL '30 minutes'
                    """, (result == 'yes', result, ticker))
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


def harvest_outcomes(client):
    """Resolve decision_log rows for markets that have settled, whether or not we
    traded them. The market's outcome is public — Kalshi's events API tells us
    the result regardless of whether the bot had an open position.

    Runs every scan cycle, prioritizes oldest unresolved markets first.
    """
    from hermes_db import query, execute
    import time

    rows = query("""
        SELECT DISTINCT market_ticker, event_ticker
        FROM kalshi_decision_log
        WHERE resolved_yes IS NULL
          AND market_ticker IS NOT NULL
          AND event_ticker IS NOT NULL
          AND scan_time < NOW() - INTERVAL '20 minutes'
        LIMIT 30
    """)

    resolved = 0
    for market_ticker, event_ticker in rows:
        try:
            event_data = client.get(f"/events/{event_ticker}")
            if not event_data or 'markets' not in event_data:
                continue
            for m in event_data['markets']:
                if m.get('ticker') != market_ticker:
                    continue
                status = m.get('status', '')
                result = m.get('result', '').lower()
                if status in ('finalized', 'settled', 'determined') and result in ('yes', 'no'):
                    result_bool = (result == 'yes')
                    execute("""
                        UPDATE kalshi_decision_log
                        SET resolved_yes = %s, result = %s
                        WHERE market_ticker = %s
                          AND resolved_yes IS NULL
                    """, (result_bool, result, market_ticker))
                    resolved += 1

                    # Also close any still-open trades for this market
                    open_trades = query("""
                        SELECT id, side, entry_price, quantity
                        FROM kalshi_trades
                        WHERE market_ticker = %s AND status = 'open'
                    """, (market_ticker,))
                    for t in open_trades:
                        tid, side, entry, qty = t
                        won = (side == 'yes' and result_bool) or (side == 'no' and not result_bool)
                        if won:
                            exit_price = 1.0
                            pnl = round((1.0 - float(entry)) * qty, 2)
                        else:
                            exit_price = 0.0
                            pnl = round(-float(entry) * qty, 2)
                        execute("""
                            UPDATE kalshi_trades SET status = 'closed',
                                exit_price = %s, pnl = %s,
                                exit_time = NOW(), exit_reason = 'settled'
                            WHERE id = %s
                        """, (exit_price, pnl, tid))
                        # Credit the portfolio if winning
                        if won:
                            proceed = exit_price * qty
                            execute("""
                                UPDATE kalshi_portfolio
                                SET current_balance = current_balance + %s
                                WHERE id = 1
                            """, (proceed,))
                        print(f"  Closed trade {tid}: {side} ${entry} x{qty} {'WON' if won else 'LOST'} ${pnl}")
                    if open_trades:
                        print(f"  Closed {len(open_trades)} trade(s) for {market_ticker}")

                    break
            time.sleep(0.1)
        except Exception as e:
            print(f"  Harvest error for {market_ticker}: {e}")

    if resolved:
        print(f"  Harvested outcomes: {resolved} markets")
    return resolved


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

    harvested = harvest_outcomes(client)

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
                # Path metrics for dashboard display (operational visibility, not predictive signal)
                "pct_above": sig.get("path_metrics", {}).get("pct_above") if sig.get("path_metrics") else None,
                "streak": sig.get("path_metrics", {}).get("streak") if sig.get("path_metrics") else None,
                "crossings": sig.get("path_metrics", {}).get("crossings") if sig.get("path_metrics") else None,
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
```

## hermes_db.py

```python
"""
Hermes PostgreSQL helper — reusable connection for agent scripts.
Import and call get_conn() to get a psycopg2 connection to the hermes DB.

Usage:
    from hermes_db import get_conn, query, query_one

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM vm_metrics")
    print(cur.fetchone())

    # Convenience:
    rows = query("SELECT * FROM vm_metrics LIMIT 5")
    row  = query_one("SELECT max(checked_at) FROM vm_metrics")
"""

import os
import psycopg2

_URI = None


def _load_uri():
    """Load the PG URI from environment, trying ~/.hermes/env first."""
    global _URI
    if _URI:
        return _URI

    # Try to source the env file if HERMES_PG_URI isn't set
    if not os.environ.get("HERMES_PG_URI"):
        env_file = os.path.expanduser("~/.hermes/env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export HERMES_PG_URI="):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        os.environ["HERMES_PG_URI"] = val
                        break

    _URI = os.environ.get("HERMES_PG_URI")
    return _URI


def get_conn():
    """Return a psycopg2 connection to the hermes database."""
    uri = _load_uri()
    if not uri:
        raise RuntimeError("HERMES_PG_URI not set — check ~/.hermes/env")
    return psycopg2.connect(uri)


def query(sql, params=None):
    """Execute SELECT and return all rows as a list."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def query_one(sql, params=None):
    """Execute SELECT and return one row or None."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row
    finally:
        conn.close()


def execute(sql, params=None):
    """Execute INSERT/UPDATE/DELETE and commit. Returns rowcount."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        count = cur.rowcount
        cur.close()
        return count
    finally:
        conn.close()
```

## kalshi-crypto-prod

```python
#!/usr/bin/env python3
"""
Crypto 15-min Production Scanner — real-money trading.

Places actual orders on Kalshi via authenticated API.
Enforces hard limits: $1 max per coin exposure, $50 cash floor.
Every trade logged to DB with reasoning. Every position evaluated on closeout.
"""
import sys, json, time, os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path.home() / '.hermes' / 'scripts'))

def parse_market_ticker(market_ticker):
    """
    Parse a Kalshi market_ticker like 'KXSOL15M-26MAY171615-15'
    into (series_ticker, event_ticker).

    Format: SERIES-EVENT_DATETIME-STRIKE_SUFFIX
    Example: 'KXSOL15M-26MAY171615-15' → ('KXSOL15M', 'KXSOL15M-26MAY171615')

    Returns ('', '') if the ticker can't be parsed.
    """
    if not market_ticker or '-' not in market_ticker:
        return '', ''
    parts = market_ticker.split('-')
    if len(parts) < 2:
        return '', ''
    series_ticker = parts[0]
    event_ticker = f"{parts[0]}-{parts[1]}"
    return series_ticker, event_ticker

# ── Config ──────────────────────────────────────────────────────────
MAX_PER_COIN_DOLLARS = 1.00    # Hard cap: max $1 total exposure per coin
HALT_FLOOR = 30.00             # User lowered from $50 — take a loss, collect data
MIN_EDGE_CENTS = 3              # Was 8 — relaxed to get trades happening.
                                # $1/coin cap + $50 halt floor bounds downside.
                                # Real data beats speculation. Raise back after
                                # Phase 2 validates or 200 trades accumulated.
MIN_EDGE_RATIO = 0.15           # Edge / executable ask must clear this
MIN_CONFIDENCE = 0.15           # Was 0.30 — relaxed alongside MIN_EDGE_CENTS.
                                # $1/coin cap + $50 halt floor bounds downside.
HARD_MAX_ENTRY_PRICE = 0.75     # Emergency cap; TTL-specific cap lives in analyzer
ENABLE_AUTO_HEDGING = False
ENABLE_AUTO_EXITS = False
SCAN_INTERVAL_SEC = 90          # How often this runs (for logging context)
DRY_RUN = os.environ.get("KALSHI_DRY_RUN", "0") == "1"  # Analyze/log only; no orders

# ── Imports ─────────────────────────────────────────────────────────
from kalshi_client import create_prod_client
from crypto_intel import (
    fetch_crypto_markets, analyze_crypto_market, log_decision, write_cache,
    already_have_open_market_position, print_trade_debug, SIZE_MULTIPLIER_BY_SIDE,
    harvest_outcomes,
)
from hermes_db import query, get_conn, execute


def get_balance(client):
    """Get current portfolio balance in dollars.

    Kalshi's balance API returns cents as an integer (e.g. 7182 == $71.82).
    Keep scanner math and DB current_balance in dollars so HALT_FLOOR=50 means $50.
    """
    try:
        row = query("SELECT current_balance FROM kalshi_portfolio WHERE id = 1")
        db_bal = float(row[0][0]) if row else 0.0
        # Legacy prod syncs stored raw cents in this field; normalize for comparison/fallback.
        db_bal_dollars = db_bal / 100.0 if db_bal > 1000 else db_bal
    except Exception as e:
        print(f"  [prod] DB balance error: {e}")
        db_bal_dollars = 0.0

    # Sync from Kalshi API as the authoritative source
    try:
        api_resp = client.get_balance()
        if api_resp and not api_resp.get('_error'):
            api_bal_cents = float(api_resp.get('balance', 0))
            api_bal = api_bal_cents / 100.0
            if api_bal > 0 and abs(api_bal - db_bal_dollars) > 0.01:
                print(f"  Balance sync: API=${api_bal:.2f} vs DB=${db_bal_dollars:.2f} — updating DB")
                execute("UPDATE kalshi_portfolio SET current_balance = %s WHERE id = 1", (api_bal,))
                return api_bal
        return db_bal_dollars
    except Exception:
        return db_bal_dollars


def get_position_exposure():
    """Get per-coin exposure ($$) for open positions.
    Returns dict: {series_ticker: total_dollars_at_risk}
    """
    try:
        rows = query("""
            SELECT series_ticker, SUM(entry_price * quantity)
            FROM kalshi_trades
            WHERE strategy_name = 'crypto_intel_prod' AND status IN ('open','pending_settlement')
            GROUP BY series_ticker
        """)
        return {r[0]: float(r[1]) for r in rows} if rows else {}
    except Exception as e:
        print(f"  [prod] Position query error: {e}")
        return {}


def settle_expired(client):
    """Check and settle expired positions. Checks if orders actually filled first."""
    exited = 0
    try:
        open_pos = query("""
            SELECT id, market_ticker, side, entry_price, quantity, event_ticker, kalshi_order_id
            FROM kalshi_trades
            WHERE strategy_name = 'crypto_intel_prod' AND status IN ('open','pending_settlement')
        """)
        if not open_pos:
            return 0

        for pos in open_pos:
            tid, ticker, side, entry, qty, event, oid = pos
            entry = float(entry)

            # First check if the Kalshi order was actually filled
            if oid:
                order_resp = client.get(f"/portfolio/orders/{oid}")
                if order_resp and not order_resp.get('_error'):
                    od = order_resp.get('order', order_resp)
                    filled_fp = od.get('fill_count_fp', '0.00')
                    remaining_fp = od.get('remaining_count_fp', '0.00')
                    filled = float(filled_fp or '0.00')
                    remaining = float(remaining_fp or '0.00')
                    o_status = od.get('status', '')

                    # If order never filled, cancel the DB record with no P&L impact
                    if filled == 0 and o_status != 'open':
                        conn = get_conn()
                        try:
                            cur = conn.cursor()
                            cur.execute(
                                "UPDATE kalshi_trades SET status='cancelled', exit_price=entry_price, "
                                "pnl=0, exit_time=NOW(), exit_reason='order_unfilled' WHERE id=%s",
                                (tid,))
                            conn.commit()
                            print(f"  CANCEL [{tid}] {ticker[:20]}: order {oid[:16]} never filled")
                            exited += 1
                        except Exception as e:
                            conn.rollback()
                            print(f"  Cancel error [{tid}]: {e}")
                        finally:
                            cur.close()
                            conn.close()
                        continue

            event_data = client.get(f"/events/{event}")
            if not event_data or 'markets' not in event_data:
                continue
            m = None
            for sm in event_data['markets']:
                if sm.get('ticker') == ticker:
                    m = sm
                    break
            if not m:
                continue
            status = m.get('status', '')
            close_time = m.get('close_time', '')
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
                            print(f"  PENDING [{tid}] {ticker[:20]}: expired, awaiting result")
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
                    cur.execute(
                        "UPDATE kalshi_trades SET status='closed', exit_price=%s, pnl=%s, "
                        "exit_time=NOW(), exit_reason=%s WHERE id=%s",
                        (settle, pnl, reason, tid))
                    # Capture exit fee if we have an order_id
                    if oid:
                        try:
                            fill_resp = client.get(f"/portfolio/fills?order_id={oid}")
                            if fill_resp and 'fills' in fill_resp:
                                exit_fee = sum(float(f.get('fee_dollars', 0)) for f in fill_resp['fills'])
                                if exit_fee > 0:
                                    cur.execute("UPDATE kalshi_trades SET exit_fee = %s WHERE id = %s", (exit_fee, tid))
                        except Exception:
                            pass
                    cur.execute(
                        "UPDATE kalshi_portfolio SET current_balance = current_balance + %s, "
                        "total_realized_pnl = total_realized_pnl + %s WHERE id = 1",
                        (proceed, pnl))
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
                    # Also label all hold decisions for this market in the same window
                    # so Phase 2 validation has outcome data for path metrics analysis
                    cur.execute("""
                        UPDATE kalshi_decision_log
                        SET resolved_yes = %s, result = %s
                        WHERE market_ticker = %s
                          AND resolved_yes IS NULL
                          AND scan_time > NOW() - INTERVAL '30 minutes'
                    """, (result == 'yes', result, ticker))
                    conn.commit()
                    print(f"  SETTLE [{tid}] {ticker[:20]}: {reason} P&L=${pnl:+.2f}")
                    exited += 1
                except Exception as e:
                    conn.rollback()
                    print(f"  Settle error [{tid}]: {e}")
                finally:
                    cur.close()
                    conn.close()
    except Exception as e:
        print(f"  [prod] Settle scan error: {e}")
    return exited


def place_real_order(client, ticker, side, count, price):
    """Place a real buy order on Kalshi at the given price. Returns (order_id, error_string)."""
    try:
        if price <= 0:
            return None, "zero_price"
        if price > HARD_MAX_ENTRY_PRICE:
            return None, f"price_{price:.2f}_exceeds_max_{HARD_MAX_ENTRY_PRICE:.2f}"

        # Place limit order at the price we already determined
        resp = client.place_order(ticker, side, count, price, action="buy")
        if not resp:
            return None, "empty_response"
        if '_error' in resp:
            return None, resp['_error']

        order_id = resp.get('order', {}).get('order_id', resp.get('order_id', ''))
        if not order_id:
            order_id = json.dumps(resp)[:100]
        return order_id, None
    except Exception as e:
        return None, str(e)


def production_scan(client=None):
    """Full production scan cycle. Returns summary string."""

    # Heartbeat — dead man's switch (run before auth check so cron liveness is visible even when Kalshi is down)
    try:
        execute("""
            INSERT INTO kalshi_heartbeat (strategy_name, last_seen, status)
            VALUES ('crypto_intel_prod', NOW(), 'ok')
            ON CONFLICT (strategy_name)
            DO UPDATE SET last_seen = NOW(), status = 'ok'
        """)
    except Exception:
        pass  # never let heartbeat failures block the cycle

    if client is None:
        client = create_prod_client()
        if not client or not client.auth:
            # Retry: source ~/.hermes/env (cron scheduler doesn't always pass env vars)
            try:
                env_file = Path.home() / '.hermes' / 'env'
                if not env_file.exists():
                    env_file = Path.home() / '.hermes' / '.env'  # fallback to dotfile template
                if env_file.exists():
                    with open(env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('export '):
                                parts = line[7:].strip().split('=', 1)
                                if len(parts) == 2:
                                    k, v = parts
                                    v = v.strip("'\"")
                                    os.environ[k] = v
                    client = create_prod_client()
            except Exception:
                pass
        if not client or not client.auth:
            print("  [prod] FAILED: No production credentials configured")
            print("  Set KALSHI_PROD_KEY_ID and KALSHI_PROD_KEY_PATH in ~/.hermes/env")
            return "NO_AUTH"

    ts = datetime.now(timezone.utc)
    print(f"[{ts.strftime('%H:%M:%S')}] Prod Crypto Scan" + (" [DRY RUN]" if DRY_RUN else ""))

    # 1) Check balance
    balance = get_balance(client)
    print(f"  Balance: ${balance:.2f}")
    if balance < HALT_FLOOR:
        print(f"  ⛔ HALTED: Balance ${balance:.2f} < ${HALT_FLOOR:.2f} floor")
        # Still settle any expired positions before halting
        settled = settle_expired(client)
        if settled:
            print(f"  Settled {settled} positions during halt check")
        return "HALTED"

    # 2) Check per-coin exposure
    exposure = get_position_exposure()
    if exposure:
        for coin, dol in sorted(exposure.items()):
            print(f"  {coin}: ${dol:.2f} / ${MAX_PER_COIN_DOLLARS:.2f}")

    # 3) Settle expired positions
    settled = settle_expired(client)
    if settled:
        print(f"  Settled: {settled}")

    # 3b) Harvest outcomes for all unresolved markets (public data from Kalshi)
    harvested = harvest_outcomes(client)

    # Re-check balance after settlements
    balance = get_balance(client)
    print(f"  Balance after settle: ${balance:.2f}")

    # 4) Fetch and analyze markets
    markets = fetch_crypto_markets(client)

    if not markets:
        print("  No markets found")
        return "NO_MARKETS"

    # 5) Score and rank all tradeable markets
    candidates = []
    signals_by_name = {}
    for m in markets:
        if "error" in m:
            print(f"  {m.get('name','?')}: error ({m['error']})")
            log_decision(m, {"side": "hold", "reason": m["error"], "entry_price": 0,
                             "edge_cents": 0, "confidence": 0, "predicted_fair_value": 0.5,
                             "reasoning": [f"Market error: {m['error']}"],
                             "strategy": "crypto_intel_prod", "data_sources": {}},
                        was_executed=False)
            continue

        # Check per-coin cap
        series = m.get("series_ticker", "")
        current_exp = exposure.get(series, 0.0)
        if current_exp >= MAX_PER_COIN_DOLLARS:
            print(f"  {m['name']}: already at ${current_exp:.2f} exposure — skip")
            log_decision(m, {"side": "hold", "reason": "per_coin_cap_reached", "entry_price": 0,
                             "edge_cents": 0, "confidence": 0, "predicted_fair_value": 0.5,
                             "reasoning": [f"Exposure ${current_exp:.2f} >= ${MAX_PER_COIN_DOLLARS:.2f} max"],
                             "strategy": "crypto_intel_prod", "data_sources": {}},
                        was_executed=False)
            continue

        sig = analyze_crypto_market(m)
        sig["strategy"] = "crypto_intel_prod"
        signals_by_name[m.get("name", "?")] = sig
        if sig.get("side") not in ("yes", "no"):
            reason = sig.get("reason", "no_signal")
            print(f"  {m['name']}: {reason}")
            log_decision(m, sig, was_executed=False)
            continue

        edge = sig.get("edge_cents", 0)
        edge_ratio = sig.get("edge_ratio", 0) or 0
        conf = sig.get("confidence", 0)
        price = sig.get("entry_price", 0)

        if edge < MIN_EDGE_CENTS:
            print(f"  {m['name']}: edge {edge}c < {MIN_EDGE_CENTS}c min")
            log_decision(m, sig, was_executed=False)
            continue

        if edge_ratio < MIN_EDGE_RATIO:
            print(f"  {m['name']}: edge ratio {edge_ratio:.2f} < {MIN_EDGE_RATIO:.2f} min")
            log_decision(m, sig, was_executed=False)
            continue

        if conf < MIN_CONFIDENCE:
            print(f"  {m['name']}: conf {conf:.2f} < {MIN_CONFIDENCE:.2f} min")
            log_decision(m, sig, was_executed=False)
            continue

        if price > HARD_MAX_ENTRY_PRICE or price <= 0:
            print(f"  {m['name']}: price ${price:.4f} beyond hard cap ${HARD_MAX_ENTRY_PRICE:.2f}")
            log_decision(m, sig, was_executed=False)
            continue

        ticker = m.get("market_ticker", "")
        if already_have_open_market_position(ticker):
            print(f"  {ticker}: already have open position — skip duplicate")
            log_decision(m, {**sig, "reason": "duplicate_market_position", "side": "hold", "entry_price": 0}, was_executed=False)
            continue

        candidates.append((m, sig))

    try:
        write_cache(markets, precomputed_signals=signals_by_name)
        print(f"  Dashboard cache updated ({len(markets)} markets)")
    except Exception as e:
        print(f"  Cache write error: {e}")

    if not candidates:
        print("  No candidates pass all filters")
        return "NO_CANDIDATES"

    # 6) Pick top 3 candidates by score (edge * confidence)
    MAX_TRADES_PER_CYCLE = 3
    candidates.sort(key=lambda x: x[1]["edge_cents"] * x[1]["confidence"], reverse=True)
    to_execute = candidates[:MAX_TRADES_PER_CYCLE]
    candidate_str = ", ".join(f'{m["name"]} {sig["side"].upper()} ${sig["entry_price"]:.4f}' for m, sig in to_execute)
    print(f"  Top {len(to_execute)} candidates: {candidate_str}")

    entries = []
    for rank, (m, sig) in enumerate(to_execute):
        side = sig["side"]
        price = sig["entry_price"]
        edge = sig["edge_cents"]
        conf = sig["confidence"]
        series = m.get("series_ticker", "")

        # Size: cap at $1/coin minus existing exposure, adjusted by side multiplier
        current_exp = exposure.get(series, 0.0)
        side_mult = SIZE_MULTIPLIER_BY_SIDE.get(side, 1.0)
        available = (MAX_PER_COIN_DOLLARS - current_exp) * side_mult
        if available <= 0:
            print(f"  [{rank+1}] {m['name']}: already at ${current_exp:.2f} exposure — skip")
            log_decision(m, sig, was_executed=False)
            continue
        qty = max(1, int(available / price))
        cost = round(price * qty, 2)

        if qty == 0 or cost <= 0:
            print(f"  [{rank+1}] {m['name']}: zero-size (avail=${available:.2f})")
            log_decision(m, sig, was_executed=False)
            continue

        # Check balance
        if cost > balance:
            print(f"  [{rank+1}] {m['name']}: ${cost:.2f} > balance ${balance:.2f}")
            log_decision(m, sig, was_executed=False)
            break  # stop trying more trades if we're out of balance

        print(f"  [{rank+1}] {m['name']} {side.upper()} @ ${price:.4f} x {qty} = ${cost:.2f} (edge={edge}c, conf={conf:.2f})")
        print_trade_debug(m, sig)

        ticker = m.get("market_ticker", "")
        if already_have_open_market_position(ticker):
            print(f"    {ticker}: already have open position — skip duplicate before order")
            log_decision(m, {**sig, "reason": "duplicate_market_position", "side": "hold", "entry_price": 0}, was_executed=False)
            continue

        if DRY_RUN:
            print(f"    DRY RUN: would place order, logging only")
            sig["reasoning"] = sig.get("reasoning", []) + ["DRY RUN: order not placed"]
            log_decision(m, {**sig, "reason": "dryrun_positive_ev"}, was_executed=False)
            entries.append({"name": m['name'], "side": side, "cost": cost, "edge": edge})
            exposure[series] = current_exp + cost
            continue

        # Place real order
        ticker = m.get("market_ticker", "")
        order_id, error = place_real_order(client, ticker, side, qty, price)

        if error:
            print(f"    ❌ ORDER FAILED: {error}")
            sig["reasoning"] = sig.get("reasoning", []) + [f"ORDER FAILED: {error}"]
            log_decision(m, {**sig, "reason": "order_failed"}, was_executed=False)
            continue

        print(f"    ✅ ORDER PLACED: {order_id[:20]}")

        # Log trade to DB
        trade_id = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO kalshi_trades
                    (portfolio_id, market_ticker, event_ticker, series_ticker,
                     market_title, side, entry_price, quantity, strategy_name,
                     status, confidence, predicted_fair_value,
                     edge_cents, reasoning_json, data_sources,
                     kalshi_order_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                1, ticker, m.get("event_ticker",""), series,
                f"Crypto 15-min {m['name']}",
                side, f"{price:.4f}", qty,
                "crypto_intel_prod", "open",
                conf, sig.get("predicted_fair_value"),
                edge,
                json.dumps(sig.get("reasoning", [])),
                json.dumps(sig.get("data_sources", {})),
                order_id,
            ))
            trade_id = cur.fetchone()[0]
            cur.execute("UPDATE kalshi_portfolio SET current_balance = current_balance - %s WHERE id = 1", (cost,))
            conn.commit()

            # Fetch entry fee from Kalshi fills API (non-blocking on error)
            try:
                fill_resp = client.get(f"/portfolio/fills?order_id={order_id}")
                if fill_resp and 'fills' in fill_resp:
                    fills = fill_resp['fills']
                    total_fee = sum(float(f.get('fee_dollars', 0)) for f in fills)
                    if total_fee > 0:
                        fee_cur = conn.cursor()
                        fee_cur.execute("UPDATE kalshi_trades SET entry_fee = %s WHERE id = %s", (total_fee, trade_id))
                        conn.commit()
                        fee_cur.close()
                        print(f"    FEE: ${total_fee:.4f} entry fee for trade [{trade_id}]")
            except Exception as fee_e:
                print(f"    Fee fetch error [{trade_id}]: {fee_e}")

            # Capture spread_paid: entry_price relative to mid
            try:
                yes_bid = float(m.get("yes_bid", 0) or 0)
                yes_ask = float(m.get("yes_ask", 0) or 0)
                no_bid = float(m.get("no_bid", 0) or 0)
                no_ask = float(m.get("no_ask", 0) or 0)
                if side == 'yes' and yes_bid > 0 and yes_ask > 0:
                    mid = (yes_bid + yes_ask) / 2
                    spread_paid_v = price - mid
                elif side == 'no' and no_bid > 0 and no_ask > 0:
                    mid = (no_bid + no_ask) / 2
                    spread_paid_v = price - mid
                else:
                    spread_paid_v = 0
                if abs(spread_paid_v) > 0.001:
                    sp_cur = conn.cursor()
                    sp_cur.execute("UPDATE kalshi_trades SET spread_paid = %s WHERE id = %s", (round(spread_paid_v, 4), trade_id))
                    conn.commit()
                    sp_cur.close()
                    print(f"    SPREAD: ${spread_paid_v:.4f} paid for trade [{trade_id}]")
            except Exception as sp_e:
                print(f"    Spread capture error [{trade_id}]: {sp_e}")

            cur.close()
            conn.close()
            print(f"    DB LOG: trade [{trade_id}] linked to order {order_id[:20]}")
        except Exception as e:
            import traceback
            print(f"    DB LOG ERROR: {e}")
            traceback.print_exc()
            print(f"    ⚠ Kalshi order {order_id[:20]} in flight, DB entry failed")

        # Log decision
        log_decision(m, sig, was_executed=True, trade_id=trade_id)

        # Update running totals for next candidate
        balance -= cost
        exposure[series] = current_exp + cost
        entries.append({"name": m['name'], "side": side, "cost": cost, "edge": edge})

    # Final status
    total_exp = sum(get_position_exposure().values())
    if entries:
        for e in entries:
            print(f"  ENTERED {e['name']}: {e['side'].upper()} ${e['cost']:.2f} edge={e['edge']}c")
    print(f"  Balance: ${balance:.2f} | Total exposure: ${total_exp:.2f} | Trades: {len(entries)}")

    # Reconcile: check recent Kalshi orders for any not in our DB.
    # If found, INSERT a trade row with full metadata (not just the
    # bare minimum). The orphan-fix version populates series_ticker,
    # event_ticker, and entry_time from the order data.
    try:
        recent = client.get_orders(limit=10)
        if recent and 'orders' in recent:
            db_oids = set()
            for r_row in query("SELECT kalshi_order_id FROM kalshi_trades "
                              "WHERE strategy_name='crypto_intel_prod' "
                              "AND kalshi_order_id IS NOT NULL"):
                if r_row[0]:
                    db_oids.add(r_row[0])

            for o in recent['orders']:
                oid = o.get('order_id', '')
                if not oid or oid in db_oids:
                    continue
                if o.get('status') not in ('executed', 'filled'):
                    continue

                side = o.get('side', '')
                count = int(float(o.get('fill_count_fp',
                                       o.get('initial_count_fp', '0'))))
                price_str = o.get('yes_price_dollars' if side == 'yes'
                                  else 'no_price_dollars', '0')
                price = float(price_str) if price_str else 0

                if price <= 0 or count <= 0:
                    continue

                # Parse market ticker for series/event
                market_ticker = o.get('ticker', '')
                series_ticker, event_ticker = parse_market_ticker(market_ticker)

                # Use the order's created_time if available, else NOW
                created_str = o.get('created_time', '')
                if created_str:
                    try:
                        entry_time = datetime.fromisoformat(
                            created_str.replace('Z', '+00:00'))
                    except Exception:
                        entry_time = datetime.now(timezone.utc)
                else:
                    entry_time = datetime.now(timezone.utc)

                execute("""
                    INSERT INTO kalshi_trades
                        (portfolio_id, market_ticker, event_ticker,
                         series_ticker, side, entry_price, quantity,
                         strategy_name, status, kalshi_order_id,
                         entry_time, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                """, (1, market_ticker, event_ticker, series_ticker,
                      side, price, count, 'crypto_intel_prod', 'open',
                      oid, entry_time,
                      'auto_reconciled: no matching decision_log entry'))

                print(f"  RECONCILED: {market_ticker[:30]} "
                      f"{side} ${price:.4f} x {count} "
                      f"(series={series_ticker})")
    except Exception as e:
        print(f"  Reconciliation error: {e}")

    return f"OK:{len(entries)}trades:{','.join(e['name'] for e in entries)}"


if __name__ == "__main__":
    result = production_scan()
    print(f"RESULT:{result}")
```

## kalshi-crypto-scan

```python
#!/usr/bin/env python3
"""Crypto 15-min scanner — called by cron every 90s."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.hermes' / 'scripts'))
from crypto_intel import scan_and_log
result = scan_and_log()
print(f"{result['entries']} entries, {result['markets']} markets")
```

## kalshi_client.py

```python
#!/usr/bin/env python3
"""
Kalshi Client — unified interface for production and demo APIs.
- Production: read-only market data (no auth needed)
- Demo: authenticated trading with mock funds
- Also supports production trading with real keys (swap config)
"""
import json, time, os, base64, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

# --- Config ---
PROD_BASE = "https://external-api.kalshi.com/trade-api/v2"
DEMO_BASE = os.environ.get("KALSHI_DEMO_BASE", 
    "https://external-api.demo.kalshi.co/trade-api/v2")
DEMO_KEY_ID = os.environ.get("KALSHI_DEMO_KEY_ID", "")
DEMO_KEY_PATH = os.environ.get("KALSHI_DEMO_KEY_PATH", "")
PROD_KEY_ID = os.environ.get("KALSHI_PROD_KEY_ID", "")
PROD_KEY_PATH = os.environ.get("KALSHI_PROD_KEY_PATH", "")

# Crypto 15-min series to monitor
CRYPTO_SERIES = [
    {"name": "BTC", "ticker": "KXBTC15M", "color": "#f7931a", "icon": "₿"},
    {"name": "ETH", "ticker": "KXETH15M", "color": "#627eea", "icon": "⟠"},
    {"name": "SOL", "ticker": "KXSOL15M", "color": "#00d18c", "icon": "◎"},
    {"name": "XRP", "ticker": "KXXRP15M", "color": "#23292f", "icon": "✕"},
    {"name": "DOGE", "ticker": "KXDOGE15M", "color": "#c2a633", "icon": "Ð"},
    {"name": "BNB", "ticker": "KXBNB15M", "color": "#f0b90b", "icon": "◆"},
    {"name": "HYPE", "ticker": "KXHYPE15M", "color": "#5367ff", "icon": "◈"},
]

# --- Auth ---
class KalshiAuth:
    def __init__(self, key_id=None, key_path=None):
        self.key_id = key_id or DEMO_KEY_ID
        self.pk = None
        if key_path or DEMO_KEY_PATH:
            kp = key_path or DEMO_KEY_PATH
            if os.path.exists(kp):
                with open(kp, "rb") as f:
                    raw = f.read()
                # Kalshi key files are often combined format:
                #   line 1: key_id (UUID)
                #   line 2: (blank)
                #   line 3+: PEM private key body
                # Detect this by checking if line 1 is a UUID-style key ID.
                first = raw.split(b"\n")[0].strip().decode()
                if not self.key_id and len(first) == 36 and first.count("-") == 4:
                    self.key_id = first
                    # Skip first two lines to get clean PEM
                    pem_data = b"\n".join(raw.split(b"\n")[2:])
                else:
                    pem_data = raw
                self.pk = serialization.load_pem_private_key(pem_data, password=None)
    
    def sign(self, method, path):
        ts = str(int(time.time() * 1000))
        msg = ts + method + path.split("?")[0]
        sig = base64.b64encode(
            self.pk.sign(msg.encode(), padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ), hashes.SHA256())
        ).decode()
        return ts, sig


def create_prod_auth():
    """Create an authenticated KalshiAuth for production trading.

    Reads from os.environ directly (not module-level vars) so the retry
    sourcing path in the cron script actually takes effect after import.
    """
    key_id = os.environ.get("KALSHI_PROD_KEY_ID", "")
    key_path = os.environ.get("KALSHI_PROD_KEY_PATH", "")
    if not key_id or not key_path:
        return None
    return KalshiAuth(key_id=key_id, key_path=key_path)


def create_prod_client():
    """Create an authenticated KalshiClient for production trading."""
    auth = create_prod_auth()
    return KalshiClient(base_url=PROD_BASE, auth=auth)

# --- API Client ---
class KalshiClient:
    def __init__(self, base_url=PROD_BASE, auth=None):
        self.base = base_url.rstrip("/")
        self.auth = auth
        self.prefix = "/trade-api/v2"
    
    def request(self, method, endpoint, data=None, retries=1):
        path = endpoint
        headers = {"Content-Type": "application/json", "User-Agent": "hermes-agent/1.0"}
        
        if self.auth:
            ts, sig = self.auth.sign(method, self.prefix + endpoint)
            headers["KALSHI-ACCESS-KEY"] = self.auth.key_id
            headers["KALSHI-ACCESS-SIGNATURE"] = sig
            headers["KALSHI-ACCESS-TIMESTAMP"] = ts
        
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                body = e.read().decode()
                if e.code == 429 and attempt < retries - 1:
                    time.sleep(2)
                    continue
                return {"_error": f"HTTP {e.code}", "_detail": body[:200]}
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return {"_error": str(e)}
        return {"_error": "max_retries"}
    
    def get(self, endpoint):
        return self.request("GET", endpoint)
    
    def post(self, endpoint, data):
        return self.request("POST", endpoint, data)
    
    def delete(self, endpoint):
        return self.request("DELETE", endpoint)
    
    # --- Convenience methods ---
    
    def get_open_crypto_markets(self):
        """Fetch the current open market for each crypto 15-min series."""
        results = []
        for s in CRYPTO_SERIES:
            r = self.get(f"/markets?series_ticker={s['ticker']}&limit=1&status=open")
            markets = r.get("markets", [])
            if markets:
                m = markets[0]
                results.append({
                    **s,
                    "ticker": m.get("ticker", "?"),
                    "strike": m.get("floor_strike", 0),
                    "yes_bid": float(m.get("yes_bid_dollars", 0)),
                    "yes_ask": float(m.get("yes_ask_dollars", 0)),
                    "no_bid": float(m.get("no_bid_dollars", 0)),
                    "no_ask": float(m.get("no_ask_dollars", 0)),
                    "open_interest": float(m.get("open_interest_fp", 0)),
                    "close_time": m.get("close_time", ""),
                    "status": m.get("status", "unknown"),
                })
            else:
                results.append({**s, "error": "no_open_market"})
            time.sleep(0.25)
        return results
    
    def get_balance(self):
        return self.get("/portfolio/balance")
    
    def place_order(self, ticker, side, count, price, action="buy"):
        """Place a limit order.
        side: 'yes' or 'no'
        action: 'buy' or 'sell'
        price: in dollars (e.g. 0.56)
        """
        price_key = f"{side}_price_dollars"
        data = {
            "ticker": ticker,
            "action": action,
            "side": side,
            "type": "limit",
            "count_fp": f"{count:d}.00",
            price_key: f"{price:.4f}",
        }
        return self.post("/portfolio/orders", data)
    
    def cancel_order(self, order_id):
        return self.delete(f"/portfolio/orders/{order_id}")
    
    def get_orders(self, limit=20):
        return self.get(f"/portfolio/orders?limit={limit}")
    
    def get_fills(self, limit=20):
        return self.get(f"/portfolio/fills?limit={limit}")
    
    def get_positions(self):
        return self.get("/portfolio/positions")

# --- Analysis Engine ---
def analyze_market(m):
    """Analyze a single crypto 15-min market. Returns analysis + recommendation."""
    if "error" in m:
        return None
    
    mid = (m["yes_bid"] + m["yes_ask"]) / 2
    spread = m["yes_ask"] - m["yes_bid"]
    prob = mid * 100
    edge = mid - 0.50
    ec = abs(edge)
    oi = m["open_interest"]
    
    # Time remaining
    ttl_min = 0
    if m.get("close_time"):
        try:
            ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
            ttl_min = (ct - datetime.now(timezone.utc)).total_seconds() / 60
        except:
            pass
    
    # Liquidity grade
    if oi > 10000: liq, liq_note = "high", f"${oi/1000:.0f}K"
    elif oi > 1000: liq, liq_note = "medium", f"${oi:.0f}"
    else: liq, liq_note = "low", f"${oi:.0f}"
    
    # Decision logic
    if ttl_min < 3:
        rec, rc, conf = "EXPIRING", "rec-hold", "none"
        reason = f"Expiring in {ttl_min:.0f}m — prices are terminal. Wait for next window."
    elif spread > 0.15 and ec < 0.10:
        rec, rc, conf = "HOLD", "rec-hold", "low"
        reason = f"Spread ${spread:.2f} too wide. Edge meaningless without fills."
    elif ec < 0.03:
        rec, rc, conf = "HOLD", "rec-hold", "low"
        reason = f"Edge {ec*100:.0f}¢ vs 50/50 — market is fair within noise."
    elif edge > 0.05 and liq != "low":
        rec, rc, conf = "BUY YES", "rec-yes", "medium" if liq == "medium" else "high"
        reason = f"YES priced at {prob:.0f}% — {ec*100:.0f}¢ edge vs fair. Spread ${spread:.2f}. OI {oi:.0f}."
    elif edge < -0.05 and liq != "low":
        rec, rc, conf = "BUY NO", "rec-no", "medium" if liq == "medium" else "high"
        reason = f"Market too bullish. DOWN has {ec*100:.0f}¢ edge. Spread ${spread:.2f}. OI {oi:.0f}."
    else:
        rec, rc, conf = "HOLD", "rec-hold", "low"
        reason = f"Edge {ec*100:.1f}¢ — marginal. Spread ${spread:.2f}. Not actionable."
    
    return {
        "mid": round(mid, 3), "prob": round(prob, 1),
        "spread": round(spread, 3), "edge": round(edge, 3),
        "ttl": round(ttl_min, 1), "liq": liq, "liq_note": liq_note,
        "rec": rec, "rec_class": rc, "confidence": conf, "reasoning": reason,
    }
```

## path_tracker.py

```python
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
```
