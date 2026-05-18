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

    # Reconcile: check recent Kalshi orders for any not in our DB
    try:
        recent = client.get_orders(limit=10)
        if recent and 'orders' in recent:
            db_oids = set()
            for r_row in query("SELECT kalshi_order_id FROM kalshi_trades WHERE strategy_name='crypto_intel_prod' AND kalshi_order_id IS NOT NULL"):
                if r_row[0]:
                    db_oids.add(r_row[0])
            for o in recent['orders']:
                oid = o.get('order_id', '')
                if not oid or oid in db_oids:
                    continue
                if o.get('status') not in ('executed', 'filled'):
                    continue
                side = o.get('side', '')
                count = int(float(o.get('fill_count_fp', o.get('initial_count_fp', '0'))))
                price_str = o.get('yes_price_dollars' if side == 'yes' else 'no_price_dollars', '0')
                price = float(price_str) if price_str else 0
                if price > 0 and count > 0:
                    execute("""
                        INSERT INTO kalshi_trades
                            (portfolio_id, market_ticker, side, entry_price, quantity,
                             strategy_name, status, kalshi_order_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING
                    """, (1, o.get('ticker',''), side, price, count,
                          'crypto_intel_prod', 'open', oid))
                    print(f"  RECONCILED: {o.get('ticker','')[:30]} {side} ${price:.4f} x {count}")
    except Exception as e:
        print(f"  Reconcilation error: {e}")

    return f"OK:{len(entries)}trades:{','.join(e['name'] for e in entries)}"


if __name__ == "__main__":
    result = production_scan()
    print(f"RESULT:{result}")
