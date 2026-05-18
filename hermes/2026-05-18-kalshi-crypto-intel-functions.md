# crypto_intel.py — missing functions

**Generated:** 2026-05-18T09:37:10.267598
**Source:** /root/.hermes/scripts/crypto_intel.py

## analyze_crypto_market

```python
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
            "path_metrics": extra.get("path_metrics"),
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

    # Phase 1: Intra-window price path tracking (data collection only, no behavior change)
    ticker = m.get("market_ticker", "")
    history = get_window_path(ticker)
    path_metrics = compute_path_metrics(history, strike, spot, ttl_min)
    common["path_metrics"] = path_metrics

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

    # direction_block = require_direction_agreement(
    #     side=side,
    #     kalshi_yes_mid=kalshi_yes_mid,
    #     spot=spot,
    #     strike=strike,
    #     fair_yes=fair_yes,
    #     model_fair_yes=model_fair_yes,
    #     reasoning=reasoning,
    #     entry_price=entry_price,
    #     edge=edge,
    #     ttl_min=ttl_min,
    #     oi=oi,
    #     vol=vol,
    #     extra=common,
    # )
    # if direction_block:
    #     return direction_block

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
        "path_metrics": path_metrics,
    }

```

## evaluate_crypto_market

```python
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

```

## log_decision

```python
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
                 edge_ratio, volatility, exit_recommendation, hedge_evaluation,
                 path_metrics)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            json.dumps(signal.get("path_metrics")) if signal.get("path_metrics") is not None else None,
        ))
    except Exception as e:
        print(f"  [crypto_intel] Log error: {e}", file=__import__('sys').stderr)

```

## fetch_crypto_markets

```python
def fetch_crypto_markets(client=None):
    """Fetch current open crypto 15-min markets.

    Shares snapshot via file cache so paper and prod see the same data
    when running within MARKET_CACHE_TTL seconds of each other.
    """
    market_cache = Path.home() / '.hermes' / 'cache' / 'markets.json'
    if market_cache.exists():
        age = time.time() - market_cache.stat().st_mtime
        if age < MARKET_CACHE_TTL:
            try:
                with open(market_cache) as f:
                    return json.load(f)
            except Exception:
                pass

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
    # Write cache so prod can reuse this snapshot
    try:
        market_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(market_cache, "w") as f:
            json.dump(results, f)
    except Exception:
        pass
    return results

```

## already_have_open_market_position

```python
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
              AND strategy_name IN ('crypto_intel_prod', 'crypto_intel_microcap')
        """, (market_ticker,))
        return bool(rows and int(rows[0][0]) > 0)
    except Exception as e:
        print(f"  Duplicate position check error for {market_ticker}: {e}")
        return True

```

## print_trade_debug

```python
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

```
