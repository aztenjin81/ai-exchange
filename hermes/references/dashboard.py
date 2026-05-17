#!/usr/bin/env python3
"""
Kalshi Dashboard — reads from Postgres + cache file.
Shows both Paper and Live (production) trading.
Includes performance metrics, calibration, and operational health.
"""
import json, sys, os, time, math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, str(Path.home() / '.hermes' / 'scripts'))
from hermes_db import query as pg_query

PORT = 8890
CACHE_FILE = Path.home() / '.hermes' / 'cache' / 'kalshi_live.json'


def load_cache():
    """Load live crypto data from cache file (updated by scanner cron)."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                data = json.load(f)
                age = time.time() - data.get("_ts", 0)
                data["_age"] = f"{age:.0f}s"
                return data
    except Exception:
        pass
    return {"_age": "stale", "_markets": []}


# ── Existing portfolio helpers ─────────────────────────────────────

def fetch_paper_portfolio():
    """Paper portfolio: computed from starting_balance + paper trade P&L."""
    try:
        row = pg_query("SELECT starting_balance, total_realized_pnl, win_count, loss_count FROM kalshi_portfolio WHERE id = 1")
        if not row:
            return None
        starting = float(row[0][0])
        paper_pnl = float(row[0][1] or 0)
        wins = row[0][2] or 0
        losses = row[0][3] or 0
        paper_equity = starting + paper_pnl
        return {"equity": round(paper_equity, 2), "pnl": round(paper_pnl, 2),
                "wins": wins, "losses": losses}
    except Exception:
        return None


def fetch_prod_portfolio():
    """Production portfolio: current_balance (synced from Kalshi API)."""
    try:
        row = pg_query("SELECT current_balance FROM kalshi_portfolio WHERE id = 1")
        prod_balance = float(row[0][0]) if row else 0.0
        r = pg_query("SELECT COALESCE(SUM(net_pnl),0), COUNT(*) FILTER (WHERE net_pnl > 0), COUNT(*) FILTER (WHERE net_pnl < 0) FROM kalshi_trades WHERE strategy_name = 'crypto_intel_prod' AND status = 'closed'")
        prod_pnl = float(r[0][0]) if r else 0.0
        prod_wins = r[0][1] if r else 0
        prod_losses = r[0][2] if r else 0
        return {"equity": round(prod_balance, 2), "pnl": round(prod_pnl, 2),
                "wins": prod_wins, "losses": prod_losses}
    except Exception:
        return None


def fetch_positions(strategy=None):
    """Fetch open positions."""
    if strategy:
        where = "strategy_name = %s AND status IN ('open','pending_settlement')"
        params = (strategy,)
    else:
        where = "status IN ('open','pending_settlement')"
        params = ()
    rows = pg_query(f"""
        SELECT id, market_ticker, market_title, side, entry_price, quantity,
               confidence, edge_cents, predicted_fair_value, entry_time, strategy_name, kalshi_order_id
        FROM kalshi_trades
        WHERE {where}
        ORDER BY entry_time DESC
    """, params)
    total_cost = 0
    positions = []
    for r in rows:
        cost = float(r[4]) * r[5]
        total_cost += cost
        positions.append({"id": r[0], "ticker": (r[1] or "")[:30],
            "title": (r[2] or "")[:40], "side": r[3], "entry": float(r[4]),
            "qty": r[5], "cost": round(cost, 2), "conf": float(r[6] or 0),
            "edge": float(r[7] or 0), "fair": float(r[8] or 0),
            "time": r[9].strftime("%H:%M") if r[9] else "",
            "strategy": r[10], "order_id": r[11] or ""})
    return positions, round(total_cost, 2)


def fetch_closed_trades(strategy=None):
    if strategy:
        where = "status = 'closed' AND strategy_name = %s"
        params = (strategy,)
    else:
        where = "status = 'closed'"
        params = ()
    rows = pg_query(f"""
        SELECT id, LEFT(market_ticker, 25), side, entry_price, exit_price, net_pnl,
               strategy_name, entry_time, exit_time, exit_reason, kalshi_order_id
        FROM kalshi_trades
        WHERE {where}
        ORDER BY exit_time DESC LIMIT 20
    """, params)
    trades = []
    for r in rows:
        pnl = float(r[5]) if r[5] else 0
        trades.append({"id": r[0], "ticker": r[1], "side": r[2],
            "entry": float(r[3]), "exit": float(r[4] or 0),
            "pnl": pnl, "strat": r[6], "entry_t": r[7].strftime("%H:%M") if r[7] else "",
            "exit_t": r[8].strftime("%m/%d %H:%M") if r[8] else "",
            "reason": r[9] or "", "order_id": r[10] or ""})
    return trades


def fetch_decision_history(limit=50):
    rows = pg_query("""
        SELECT coin_name, action, side, edge_cents, confidence, market_prob,
               scan_time, spread, open_interest, trade_id, strategy_name,
               resolved_yes, result
        FROM kalshi_decision_log
        ORDER BY id DESC LIMIT %s
    """, (limit,))
    return [{"coin": r[0], "action": r[1], "side": r[2],
             "edge": float(r[3] or 0), "conf": float(r[4] or 0),
             "prob": float(r[5] or 0),
             "time": r[6].strftime("%H:%M:%S") if r[6] else "",
             "spread": float(r[7] or 0), "oi": float(r[8] or 0), "trade": r[9],
             "strategy": r[10], "resolved": r[11], "result": r[12]}
            for r in rows]


# ── New performance query functions (Tiers 1-4) ─────────────────────

def fetch_perf(strategy):
    """Tier 1: Overall P&L stats using net_pnl."""
    try:
        r = pg_query("""
            SELECT
                COUNT(*) AS n,
                COUNT(*) FILTER (WHERE net_pnl > 0) AS wins,
                COUNT(*) FILTER (WHERE net_pnl < 0) AS losses,
                COALESCE(SUM(net_pnl), 0) AS total_pnl,
                COALESCE(SUM(entry_price * quantity), 0) AS total_at_risk,
                COALESCE(AVG(net_pnl) FILTER (WHERE net_pnl > 0), 0) AS avg_win,
                COALESCE(AVG(net_pnl) FILTER (WHERE net_pnl < 0), 0) AS avg_loss
            FROM kalshi_trades
            WHERE strategy_name = %s AND status = 'closed'
        """, (strategy,))
        if not r or r[0][0] == 0:
            return None
        row = r[0]
        n = row[0]
        wins = row[1]
        losses = row[2]
        total_pnl = float(row[3])
        at_risk = float(row[4])
        return {
            "trades": n, "wins": wins, "losses": losses,
            "win_rate": round(wins / n, 4) if n else 0,
            "total_pnl": round(total_pnl, 2),
            "roi_pct": round(total_pnl / at_risk * 100, 2) if at_risk else 0,
            "avg_win": round(float(row[5]), 2),
            "avg_loss": round(float(row[6]), 2),
            "total_at_risk": round(at_risk, 2),
        }
    except Exception:
        return None


def fetch_rolling_24h(strategy):
    """Hourly P&L for sparkline."""
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        rows = pg_query("""
            SELECT date_trunc('hour', exit_time) AS hour, SUM(net_pnl) AS pnl
            FROM kalshi_trades
            WHERE strategy_name = %s AND status = 'closed' AND exit_time >= %s
            GROUP BY 1 ORDER BY 1
        """, (strategy, since))
        return [{"hour": r[0].strftime("%H:%M") if r[0] else "?", "pnl": round(float(r[1] or 0), 2)} for r in rows]
    except Exception:
        return []


def fetch_calibration(strategy):
    """Tier 2: Predicted vs actual outcomes by bucket."""
    try:
        rows = pg_query("""
            SELECT
                width_bucket(fair_yes, 0, 1, 10) AS bucket,
                COUNT(*) AS n,
                AVG(CASE WHEN resolved_yes AND side = 'yes' THEN 1
                         WHEN NOT resolved_yes AND side = 'no' THEN 1
                         ELSE 0 END) AS actual_win_rate,
                AVG(fair_yes) AS avg_predicted
            FROM kalshi_decision_log
            WHERE strategy_name = %s AND was_executed = TRUE
              AND resolved_yes IS NOT NULL AND fair_yes IS NOT NULL
            GROUP BY bucket ORDER BY bucket
        """, (strategy,))
        return [{"bucket": r[0], "n": r[1],
                 "actual": round(float(r[2] or 0), 3),
                 "predicted": round(float(r[3] or 0), 3)} for r in rows]
    except Exception:
        return []


def fetch_brier(strategy):
    """Tier 2: Brier score."""
    try:
        r = pg_query("""
            SELECT AVG(POWER(fair_yes - CASE WHEN resolved_yes THEN 1 ELSE 0 END, 2)),
                   COUNT(*)
            FROM kalshi_decision_log
            WHERE strategy_name = %s AND was_executed = TRUE
              AND resolved_yes IS NOT NULL AND fair_yes IS NOT NULL
        """, (strategy,))
        if not r or r[0][1] == 0 or r[0][0] is None:
            return None
        score = float(r[0][0])
        return {
            "score": round(score, 4), "n": r[0][1],
            "label": "good" if score < 0.15 else ("some_skill" if score < 0.20 else "no_skill"),
        }
    except Exception:
        return None


def fetch_coin_pnl(strategy):
    """Per-coin breakdown."""
    try:
        rows = pg_query("""
            SELECT series_ticker, COUNT(*),
                   COUNT(*) FILTER (WHERE net_pnl > 0) AS wins,
                   SUM(net_pnl) AS total_pnl
            FROM kalshi_trades
            WHERE strategy_name = %s AND status = 'closed'
            GROUP BY series_ticker ORDER BY total_pnl DESC
        """, (strategy,))
        return [{"coin": r[0].replace("KX", "").replace("15M", ""),
                 "trades": r[1], "wins": r[2],
                 "win_rate": round(r[2] / r[1], 3) if r[1] else 0,
                 "total_pnl": round(float(r[3] or 0), 2)} for r in rows]
    except Exception:
        return []


def fetch_heartbeat():
    """Tier 3: Heartbeat age."""
    try:
        rows = pg_query("SELECT strategy_name, last_seen, status FROM kalshi_heartbeat ORDER BY strategy_name")
        now = datetime.now(timezone.utc)
        result = []
        for r in rows:
            age_sec = (now - r[1]).total_seconds() if r[1] else 999
            age_color = "green" if age_sec < 90 else ("yellow" if age_sec < 180 else "red")
            result.append({"name": r[0], "age_sec": int(age_sec),
                           "age_label": f"{age_sec:.0f}s" if age_sec < 120 else f"{age_sec/60:.0f}m",
                           "color": age_color, "status": r[2]})
        return result
    except Exception:
        return []


def fetch_harvest_stats():
    """Outcome harvesting stats for operational health card."""
    try:
        r = pg_query("""
            SELECT
                COUNT(*) AS path_resolved,
                (SELECT COUNT(*) FROM kalshi_decision_log
                 WHERE path_metrics IS NOT NULL AND resolved_yes IS NULL) AS path_pending
            FROM kalshi_decision_log
            WHERE path_metrics IS NOT NULL AND resolved_yes IS NOT NULL
        """)
        total = pg_query("SELECT COUNT(*) FROM kalshi_decision_log WHERE resolved_yes IS NOT NULL")
        resolved_total = total[0][0] if total else 0
        pr = r[0] if r else (0, 0)
        return {"with_path": pr[0], "pending": pr[1], "total_resolved": resolved_total}
    except Exception:
        return None


def fetch_operational(strategy, hours=24):
    """Tier 3: Decisions per hour."""
    try:
        r = pg_query("""
            SELECT COUNT(*) AS decisions, COUNT(DISTINCT cycle_number) AS cycles,
                   MIN(scan_time) AS earliest, MAX(scan_time) AS latest
            FROM kalshi_decision_log
            WHERE strategy_name = %s AND scan_time > NOW() - %s::interval
        """, (strategy, f"{hours} hours"))
        if not r or r[0][0] == 0:
            return None
        row = r[0]
        duration_h = (row[3] - row[2]).total_seconds() / 3600 if row[2] and row[3] else 1
        return {"decisions": row[0], "cycles": row[1],
                "per_hour": round(row[0] / max(duration_h, 0.01), 1)}
    except Exception:
        return None


def fetch_filter_distribution(strategy, hours=24):
    """Tier 3: Action type distribution."""
    try:
        rows = pg_query("""
            SELECT action, COUNT(*) AS n, AVG(edge_cents) AS avg_edge
            FROM kalshi_decision_log
            WHERE strategy_name = %s AND scan_time > NOW() - %s::interval
            GROUP BY action ORDER BY n DESC LIMIT 10
        """, (strategy, f"{hours} hours"))
        return [{"action": r[0], "count": r[1], "avg_edge": round(float(r[2] or 0), 1)} for r in rows]
    except Exception:
        return []


def fetch_spread_cost(strategy):
    """Tier 4: Spread cost analysis."""
    try:
        r = pg_query("""
            SELECT COUNT(*) AS n, AVG(spread) AS avg_spread,
                   AVG(edge_cents / 100.0) AS avg_predicted_edge,
                   AVG(spread / 2) AS avg_spread_cost
            FROM kalshi_decision_log
            WHERE strategy_name = %s AND was_executed = TRUE
        """, (strategy,))
        if not r or r[0][0] == 0 or r[0][1] is None:
            return None
        row = r[0]
        return {
            "n": row[0],
            "avg_spread_cents": round(float(row[1]) * 100, 2),
            "avg_edge_cents": round(float(row[2] or 0) * 100, 2),
            "avg_spread_cost_cents": round(float(row[3] or 0) * 100, 2),
            "avg_net_edge_cents": round((float(row[2] or 0) - float(row[3] or 0)) * 100, 2),
        }
    except Exception:
        return None


def fetch_fees(strategy):
    """Total fees paid."""
    try:
        r = pg_query("""
            SELECT COALESCE(SUM(entry_fee), 0) AS entry_fees,
                   COALESCE(SUM(exit_fee), 0) AS exit_fees,
                   COALESCE(SUM(net_pnl), 0) AS net_pnl,
                   COALESCE(SUM(pnl), 0) AS gross_pnl
            FROM kalshi_trades
            WHERE strategy_name = %s AND status = 'closed'
        """, (strategy,))
        if not r:
            return None
        row = r[0]
        total_fees = float(row[0]) + float(row[1])
        gross = float(row[3])
        return {
            "entry_fees": round(float(row[0]), 4),
            "exit_fees": round(float(row[1]), 4),
            "total_fees": round(total_fees, 4),
            "fee_pct_of_gross": round(total_fees / gross * 100, 2) if gross else 0,
        }
    except Exception:
        return None


def fetch_model_health():
    """Vol estimates per coin."""
    try:
        rows = pg_query("""
            SELECT coin_name, AVG(volatility) AS avg_vol,
                   MAX(scan_time) AS last_scan, COUNT(*) AS n
            FROM kalshi_decision_log
            WHERE scan_time > NOW() - INTERVAL '2 hours' AND fair_yes IS NOT NULL
            GROUP BY coin_name ORDER BY coin_name
        """)
        return [{"coin": r[0], "vol": round(float(r[1] or 0), 3),
                 "last": r[2].strftime("%H:%M") if r[2] else "?",
                 "n": r[3]} for r in rows]
    except Exception:
        return []


# ── HTML rendering ─────────────────────────────────────────────────

def _pnl_color(v):
    return "#3fb950" if v >= 0 else "#f85149"


def _bar(v, max_v, color="#58a6ff"):
    w = min(100, max(2, v / max_v * 100)) if max_v else 0
    return f'<div style="display:inline-block;width:{w:.0f}%;min-width:2px;height:14px;background:{color};border-radius:2px"></div>'


def _sparkline(data):
    """Tiny inline bar chart for 24h P&L."""
    if not data:
        return "<span style='color:#484f58'>no data</span>"
    vals = [d["pnl"] for d in data]
    mx = max(abs(v) for v in vals) or 1
    bars = ""
    for d in data:
        p = d["pnl"]
        h = max(2, abs(p) / mx * 24)
        c = "#3fb950" if p >= 0 else "#f85149"
        bars += f'<div style="display:inline-block;width:8px;height:24px;margin:0 1px;vertical-align:bottom;position:relative">'
        if p >= 0:
            bars += f'<div style="position:absolute;bottom:0;left:0;right:0;height:{h:.0f}px;background:{c};border-radius:1px" title="{d["hour"]} ${p:+.2f}"></div>'
        else:
            bars += f'<div style="position:absolute;top:{24-h:.0f}px;left:0;right:0;height:{h:.0f}px;background:{c};border-radius:1px" title="{d["hour"]} ${p:+.2f}"></div>'
        bars += "</div>"
    return bars


def _build_tier1_html():
    """Tier 1: Net P&L, win rate, ROI, avg win/loss — for both strategies."""
    html = '<h2>📊 Performance Summary</h2>'
    html += '<div class="grid">'
    for label, strat, badge_cls in [
        ("PAPER", "crypto_intel", "badge-paper"),
        ("LIVE", "crypto_intel_prod", "badge-live"),
    ]:
        p = fetch_perf(strat)
        if not p:
            html += f'<div class="card" style="grid-column:span 2"><div class="label"><span class="{badge_cls}">{label}</span> No closed trades yet</div></div>'
            continue
        wr_color = "#3fb950" if p["win_rate"] >= 0.50 else ("#d29922" if p["win_rate"] >= 0.40 else "#f85149")
        html += f'''
        <div class="card" style="border-color:#30363d;grid-column:span 2">
          <div class="label"><span class="{badge_cls}">{label}</span> {strat}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-top:8px">
            <div><span class="label">Net P&L</span><div class="value" style="color:{_pnl_color(p['total_pnl'])};font-size:1.3em">${p["total_pnl"]:+,.2f}</div></div>
            <div><span class="label">Win Rate</span><div class="value" style="color:{wr_color}">{p["win_rate"]*100:.1f}%</div></div>
            <div><span class="label">ROI</span><div class="value" style="color:{_pnl_color(p['roi_pct'])}">{p["roi_pct"]:+.1f}%</div></div>
            <div><span class="label">Trades</span><div class="value">{p["trades"]} ({p["wins"]}W/{p["losses"]}L)</div></div>
            <div><span class="label">Avg Win</span><div class="value" style="color:#3fb950">${p["avg_win"]:+.2f}</div></div>
            <div><span class="label">Avg Loss</span><div class="value" style="color:#f85149">${p["avg_loss"]:+.2f}</div></div>
            <div><span class="label">At Risk</span><div class="value">${p["total_at_risk"]:,.2f}</div></div>
            <div><span class="label">Avg P&L/Trade</span><div class="value" style="color:{_pnl_color(p['total_pnl']/p['trades'])}">${p["total_pnl"]/p["trades"]:+.2f}</div></div>
          </div>
        </div>'''
    html += '</div>'

    # 24h rolling P&L
    for label, strat in [("LIVE", "crypto_intel_prod"), ("PAPER", "crypto_intel")]:
        r24 = fetch_rolling_24h(strat)
        if r24:
            total_24h = sum(d["pnl"] for d in r24)
            html += f'''
            <div class="card" style="margin-bottom:12px">
              <div class="label">{label} 24h P&L • Total: <span style="color:{_pnl_color(total_24h)};font-weight:600">${total_24h:+.2f}</span></div>
              <div style="margin-top:6px">{_sparkline(r24)}</div>
            </div>'''
    return html


def _build_tier2_html():
    """Tier 2: Calibration + Brier + per-coin P&L."""
    html = '<h2>📐 Model Honesty</h2><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">'

    # Calibration table
    for label, strat in [("PAPER", "crypto_intel"), ("LIVE", "crypto_intel_prod")]:
        cal = fetch_calibration(strat)
        brier = fetch_brier(strat)
        side_html = f'<div class="card"><div class="label">{label} Calibration</div>'
        if not cal:
            side_html += '<div style="color:#484f58;margin-top:8px;font-size:0.85em">Not enough data yet (need executed trades with fair_yes + resolved_yes)</div>'
        else:
            side_html += '<table class="tbl"><thead><tr><th>Bucket</th><th>N</th><th>Predicted</th><th>Actual</th><th>Bar</th></tr></thead><tbody>'
            for c in cal:
                diff = abs(c["predicted"] - c["actual"])
                bar_c = "#3fb950" if diff < 0.1 else ("#d29922" if diff < 0.2 else "#f85149")
                bar_w = max(2, c["actual"] * 100)
                side_html += f'<tr><td>{c["bucket"]}</td><td>{c["n"]}</td><td>{c["predicted"]:.3f}</td><td style="color:{bar_c}">{c["actual"]:.3f}</td><td>{_bar(c["actual"], 1, bar_c)}</td></tr>'
            side_html += '</tbody></table>'
        if brier:
            b_c = "#3fb950" if brier["label"] == "good" else ("#d29922" if brier["label"] == "some_skill" else "#f85149")
            side_html += f'<div style="margin-top:8px;font-size:0.85em">Brier: <b style="color:{b_c}">{brier["score"]}</b> (<span style="color:{b_c}">{brier["label"]}</span>) · {brier["n"]} outcomes</div>'
        side_html += '</div>'
        html += side_html

    html += '</div>'

    # Per-coin P&L
    for label, strat in [("LIVE", "crypto_intel_prod"), ("PAPER", "crypto_intel")]:
        coins = fetch_coin_pnl(strat)
        if coins:
            html += f'<div class="card" style="margin-bottom:12px"><div class="label">{label} Per-Coin P&L</div><table class="tbl"><thead><tr><th>Coin</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>P&L</th><th>Bar</th></tr></thead><tbody>'
            mx = max(abs(c["total_pnl"]) for c in coins) or 1
            for c in coins:
                bar_w = abs(c["total_pnl"]) / mx * 100
                bar_c = "#3fb950" if c["total_pnl"] >= 0 else "#f85149"
                pnl_s = f'<span style="color:{bar_c}">${c["total_pnl"]:+.2f}</span>'
                html += f'<tr><td><b>{c["coin"]}</b></td><td>{c["trades"]}</td><td>{c["wins"]}</td><td>{c["win_rate"]*100:.0f}%</td><td>{pnl_s}</td><td>{_bar(abs(c["total_pnl"]), mx, bar_c)}</td></tr>'
            html += '</tbody></table></div>'

    return html


def _build_tier3_html():
    """Tier 3: Heartbeat + operational stats."""
    html = '<h2>❤️‍🩹 Operational Health</h2><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">'

    # Heartbeat
    hb = fetch_heartbeat()
    hb_html = '<div class="card"><div class="label">Heartbeat</div>'
    if hb:
        for h in hb:
            dot_c = {"green": "#3fb950", "yellow": "#d29922", "red": "#f85149"}.get(h["color"], "#484f58")
            hb_html += f'<div style="margin-top:6px;font-size:0.9em"><span style="color:{dot_c};font-size:1.3em">●</span> {h["name"]}: {h["age_label"]} ago</div>'
            if h["color"] == "red":
                hb_html += f'<div style="color:#f85149;font-size:0.8em">⚠ Heartbeat stale — scanner may be down</div>'
    else:
        hb_html += '<div style="color:#484f58;margin-top:8px">No heartbeat data</div>'
    hb_html += '</div>'

    # Operational stats
    for label, strat in [("PAPER", "crypto_intel"), ("LIVE", "crypto_intel_prod")]:
        op = fetch_operational(strat)
        filt = fetch_filter_distribution(strat)
        op_html = f'<div class="card"><div class="label">{label} Scan Activity</div>'
        if op:
            ok = "✅" if abs(op["per_hour"] - 280) < 200 else "⚠️"
            op_html += f'<div style="margin-top:6px;font-size:0.9em">{ok} {op["decisions"]} decisions, {op["cycles"]} cycles → {op["per_hour"]}/hr (target: 280)</div>'
        if filt:
            mx_c = max(f["count"] for f in filt) or 1
            op_html += '<table class="tbl"><thead><tr><th>Action</th><th>Count</th><th>Avg Edge</th><th>Dist</th></tr></thead><tbody>'
            for f in filt:
                op_html += f'<tr><td>{f["action"][:22]}</td><td>{f["count"]}</td><td>{f["avg_edge"]}c</td><td>{_bar(f["count"], mx_c, "#8b949e")}</td></tr>'
            op_html += '</tbody></table>'
        op_html += '</div>'
        # Combine heartbeat + ops side by side
        if 'hb_closed' not in locals():
            hb_closed = hb_html + op_html
        else:
            hb_closed += op_html

    html += hb_html

    # Model health (vol per coin)
    mh = fetch_model_health()
    if mh:
        mh_html = '<div class="card"><div class="label">Volatility Estimates (2h)</div><table class="tbl"><thead><tr><th>Coin</th><th>Vol</th><th>Last</th><th>Decisions</th></tr></thead><tbody>'
        for c in mh:
            vol_ok = "✅" if c["vol"] < 2.0 else "⚠️"
            mh_html += f'<tr><td><b>{c["coin"]}</b></td><td>{vol_ok} {c["vol"]:.3f}</td><td>{c["last"]}</td><td>{c["n"]}</td></tr>'
        mh_html += '</tbody></table></div>'
        html += mh_html
    else:
        html += '<div class="card"><div class="label">Model Health</div><div style="color:#484f58;margin-top:8px">No recent data</div></div>'

    html += '</div>'
    return html


def _build_tier4_html():
    """Tier 4: Cost analysis — spread + fees."""
    html = '<h2>💰 Cost Analysis</h2><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">'
    for label, strat in [("PAPER", "crypto_intel"), ("LIVE", "crypto_intel_prod")]:
        sc = fetch_spread_cost(strat)
        fees = fetch_fees(strat)
        card = f'<div class="card"><div class="label">{label}</div>'
        if sc:
            net_ok = "✅" if sc["avg_net_edge_cents"] > 2 else "⚠️"
            card += f'''
            <div style="margin-top:8px;font-size:0.85em">
              <table style="width:100%">
                <tr><td>Avg spread (cents)</td><td style="text-align:right"><b>{sc["avg_spread_cents"]:.2f}c</b></td></tr>
                <tr><td>Avg predicted edge</td><td style="text-align:right"><b>{sc["avg_edge_cents"]:.2f}c</b></td></tr>
                <tr><td>Avg spread cost paid</td><td style="text-align:right"><b style="color:#f85149">−{sc["avg_spread_cost_cents"]:.2f}c</b></td></tr>
                <tr><td>Avg net edge {net_ok}</td><td style="text-align:right"><b style="color:{_pnl_color(sc['avg_net_edge_cents'])}">{sc["avg_net_edge_cents"]:+.2f}c</b></td></tr>
                <tr><td colspan="2" style="font-size:0.8em;color:#8b949e;padding-top:4px">Based on {sc["n"]} executed trades</td></tr>
              </table>
            </div>'''
        else:
            card += '<div style="color:#484f58;margin-top:8px;font-size:0.85em">No spread data</div>'
        if fees and fees["total_fees"] > 0:
            card += f'''
            <div style="margin-top:8px;border-top:1px solid #30363d;padding-top:6px;font-size:0.85em">
              <div>Total entry fees: <b>${fees["entry_fees"]:.4f}</b></div>
              <div>Total exit fees: <b>${fees["exit_fees"]:.4f}</b></div>
              <div>Fees as % of gross P&L: <b style="color:{_pnl_color(-fees['fee_pct_of_gross'])}">{fees["fee_pct_of_gross"]:.2f}%</b></div>
            </div>'''
        card += '</div>'
        html += card
    html += '</div>'
    return html


# ── Main HTML builder ──────────────────────────────────────────────

def build_html(mode='all'):
    cache = load_cache()
    markets = cache.get("_markets", [])
    cache_age = cache.get("_age", "?")
    show_paper = mode in ('paper', 'all')
    show_live = mode in ('live', 'all')

    paper = fetch_paper_portfolio() if show_paper else None
    prod = fetch_prod_portfolio() if show_live else None
    positions_all, _ = fetch_positions()
    positions_paper, cost_paper = fetch_positions("crypto_intel") if show_paper else ([], 0)
    positions_live, cost_live = fetch_positions("crypto_intel_prod") if show_live else ([], 0)
    closed = fetch_closed_trades()
    decisions = fetch_decision_history()
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    def card_value(port, key, fmt="dollar"):
        if not port:
            return "N/A"
        val = port.get(key, 0)
        if fmt == "dollar":
            return f"${val:,.2f}"
        elif fmt == "pct":
            return f"{val:.0f}%"
        return str(val)

    # Paper portfolio card values
    if paper:
        paper_wr = (paper["wins"] / (paper["wins"] + paper["losses"]) * 100
                    if (paper["wins"] + paper["losses"]) > 0 else 0)
    else:
        paper_wr = 0

    # Prod portfolio card values
    if prod:
        prod_wr = (prod["wins"] / (prod["wins"] + prod["losses"]) * 100
                   if (prod["wins"] + prod["losses"]) > 0 else 0)
    else:
        prod_wr = 0

    # Crypto market rows
    crypto_rows = ""
    for c in markets:
        if c.get("error"):
            crypto_rows += f'<tr class="skip"><td>{c.get("icon","?")} {c["name"]}</td><td colspan="12">{c["error"]}</td></tr>\n'
            continue
        sig = c.get("signal", "hold")
        if sig == "yes":
            sig_html = '<span class="sig-yes">⬆ BUY YES</span>'
        elif sig == "no":
            sig_html = '<span class="sig-no">⬇ BUY NO</span>'
        else:
            sig_html = '<span class="sig-hold">— HOLD</span>'
        conf_pct = int(c.get("conf", 0) * 100)
        spot = c.get("spot")
        spot_str = f'${spot:,.0f}' if spot else '—'
        crypto_rows += f"""
        <tr>
            <td><b style="color:{c.get('color','#888')}">{c.get('icon','?')} {c['name']}</b></td>
            <td>{c.get('prob',0):.1f}%</td>
            <td>{c.get('yes_bid',0):.4f} / {c.get('yes_ask',0):.4f}</td>
            <td>{sig_html}</td>
            <td>{c.get('edge',0)}c</td>
            <td><div class="conf-bar"><div class="conf-fill" style="width:{conf_pct}%"></div></div>{conf_pct}%</td>
            <td>{c.get('pct_above','—') or '—'}</td>
            <td>{c.get('streak','—') or '—'}</td>
            <td>{c.get('crossings','—') or '—'}</td>
            <td>{c.get('baseline','—') or '—'}{'%' if c.get('baseline') else ''}</td>
            <td>{spot_str}</td>
            <td>{c.get('oi',0):,.0f}</td>
        </tr>"""

    def pos_rows(positions, live=False):
        if not positions:
            return '<tr><td colspan="8" style="color:#484f58;text-align:center">None</td></tr>'
        rows = ""
        for p in positions:
            sig_c = "sig-yes" if p["side"] == "yes" else "sig-no"
            badge = '<span class="badge-live">LIVE</span>' if live else '<span class="badge-paper">PAPER</span>'
            oid = f' <span class="order-id" title="{p["order_id"]}">#{p["order_id"][:10]}…</span>' if p.get("order_id") else ""
            rows += f"""
            <tr><td>{badge}</td><td>{p['ticker'][:25]}</td>
            <td><span class="{sig_c}">{p['side'].upper()}</span></td>
            <td>${p['entry']:.4f}</td><td>{p['qty']}</td>
            <td>${p['cost']:.2f}</td><td>{p['conf']:.0%}</td>
            <td>{p['edge']}c{oid}</td></tr>"""
        return rows

    # Decision rows with strategy badges — filtered by mode
    dec_rows = ""
    for d in decisions:
        strat = d.get('strategy', '')
        # Filter by mode
        if mode == 'live' and 'prod' not in strat:
            continue
        if mode == 'paper' and ('prod' in strat or 'intel' not in strat):
            continue
        sig_c = f"sig-{d['side']}" if d['side'] in ('yes','no') else ""
        tb = f' <span class="trade-badge">T{d["trade"]}</span>' if d['trade'] else ""
        badge = '<span class="badge-live-sm">L</span>' if 'prod' in strat else ('<span class="badge-paper-sm">P</span>' if 'intel' in strat else '')
        dec_rows += f"""
        <tr><td>{d['time']}</td><td><b>{d['coin']}</b>{badge}</td>
        <td>{d['action'][:20]}</td><td><span class="{sig_c}">{d['side']}</span>{tb}</td>
        <td>{d['prob']:.1f}%</td><td>{d['edge']}c</td>
        <td>{d['conf']:.0%}</td><td>{d['oi']:,.0f}</td><td>{'—' if d.get('resolved') is None else '✅ YES' if d['resolved'] else '❌ NO'}</td></tr>"""

    def closed_rows(trades):
        if not trades:
            return '<tr><td colspan="7" style="color:#484f58;text-align:center">No closed trades</td></tr>'
        rows = ""
        for t in trades:
            strat = t.get('strat', '')
            # Filter by mode
            if mode == 'live' and 'prod' not in strat:
                continue
            if mode == 'paper' and ('prod' in strat or 'intel' not in strat):
                continue
            sc = "sig-yes" if t["side"] == "yes" else "sig-no"
            pc = "pnl-pos" if t["pnl"] >= 0 else "pnl-neg"
            badge = '<span class="badge-live-sm">L</span>' if 'prod' in strat else ('<span class="badge-paper-sm">P</span>' if 'intel' in strat else '')
            oid = f' <span class="order-id" title="{t["order_id"]}">#{t["order_id"][:10]}</span>' if t.get('order_id') else ""
            rows += f"""
            <tr><td>{badge}</td><td>{t['ticker']}</td><td><span class="{sc}">{t['side'].upper()}</span></td>
            <td>${t['entry']:.4f} → ${t['exit']:.4f}</td>
            <td class="{pc}">${t['pnl']:+.2f}</td>
            <td>{t['reason']}</td><td>{oid}</td></tr>"""
        return rows

    # Build all tier sections — filter by mode
    tier1_html = _build_tier1_html()
    tier2_html = _build_tier2_html()
    tier3_html = _build_tier3_html()
    tier4_html = _build_tier4_html()

    # Mode indicator
    mode_label = {'all': 'All', 'live': 'LIVE Only', 'paper': 'PAPER Only'}.get(mode, 'All')
    mode_links = []
    for m, label in [('all', 'All'), ('live', 'LIVE'), ('paper', 'PAPER')]:
        active = 'font-weight:700;color:#f0f6fc' if m == mode else ''
        mode_links.append(f'<a href=\"/?mode={m}\" style=\"color:#58a6ff;{active};text-decoration:none;margin:0 6px\">{label}</a>')

    # Build portfolio cards section outside f-string to avoid nesting issues
    paper_cards = ""
    if show_paper and paper:
        paper_cards = ('<div class="grid">'
            '<div class="card" style="border-color:#1f6feb"><div class="label"><span class="badge-paper">PAPER</span> Equity</div><div class="value" style="color:#58a6ff">' + card_value(paper,"equity") + '</div></div>'
            '<div class="card" style="border-color:#1f6feb"><div class="label"><span class="badge-paper">PAPER</span> Realized P&amp;L</div><div class="value" style="color:' + _pnl_color(paper["pnl"]) + '">' + card_value(paper,"pnl") + '</div></div>'
            '<div class="card" style="border-color:#1f6feb"><div class="label"><span class="badge-paper">PAPER</span> Win Rate</div><div class="value">' + str(paper_wr) + '%</div></div>'
            '<div class="card" style="border-color:#1f6feb"><div class="label"><span class="badge-paper">PAPER</span> Trades</div><div class="value">' + str(paper["wins"]+paper["losses"]) + '</div></div>'
            '</div>')

    live_cards = ""
    if show_live and prod:
        live_cards = ('<div class="grid">'
            '<div class="card" style="border-color:#f85149"><div class="label"><span class="badge-live">LIVE</span> Equity</div><div class="value" style="color:#f85149">' + card_value(prod,"equity") + '</div></div>'
            '<div class="card" style="border-color:#f85149"><div class="label"><span class="badge-live">LIVE</span> Realized P&amp;L</div><div class="value" style="color:' + _pnl_color(prod["pnl"]) + '">' + card_value(prod,"pnl") + '</div></div>'
            '<div class="card" style="border-color:#f85149"><div class="label"><span class="badge-live">LIVE</span> Win Rate</div><div class="value">' + str(prod_wr) + '%</div></div>'
            '<div class="card" style="border-color:#f85149"><div class="label"><span class="badge-live">LIVE</span> Trades</div><div class="value">' + str(prod["wins"]+prod["losses"]) + '</div></div>'
            '<div class="card" style="border-color:#f85149"><div class="label"><span class="badge-live">LIVE</span> Positions</div><div class="value" style="color:#f85149">' + str(len(positions_live)) + '</div></div>'
            '<div class="card" style="border-color:#f85149"><div class="label"><span class="badge-live">LIVE</span> Cost at Risk</div><div class="value" style="color:#f85149">$' + f"{cost_live:,.2f}" + '</div></div>'
            '</div>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kalshi Dashboard</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px}}
h1{{color:#f0f6fc;font-size:1.5em;margin-bottom:4px}}
h2{{color:#58a6ff;font-size:1.1em;margin:20px 0 8px;border-bottom:1px solid #30363d;padding-bottom:4px}}
.subtitle{{color:#8b949e;font-size:0.85em;margin-bottom:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}}
.card .label{{font-size:0.75em;color:#8b949e;text-transform:uppercase}}
.card .value{{font-size:1.3em;font-weight:600;margin-top:4px}}
.tbl{{width:100%;border-collapse:collapse;font-size:0.85em;margin-top:8px}}
.tbl th{{text-align:left;padding:6px 8px;border-bottom:2px solid #30363d;color:#8b949e;font-weight:500}}
.tbl td{{padding:6px 8px;border-bottom:1px solid #21262d}}
.tbl tr:hover{{background:#1c2128}}
.sig-yes{{color:#3fb950;font-weight:600}}
.sig-no{{color:#f85149;font-weight:600}}
.sig-hold{{color:#8b949e}}
.skip td{{color:#484f58;font-style:italic}}
.conf-bar{{display:inline-block;width:40px;height:6px;background:#21262d;border-radius:3px;vertical-align:middle;margin-right:4px}}
.conf-fill{{height:100%;background:#58a6ff;border-radius:3px}}
.trade-badge{{font-size:0.75em;background:#1f6feb;color:#fff;padding:1px 5px;border-radius:4px}}
.order-id{{font-size:0.75em;color:#8b949e;cursor:help}}
.pnl-pos{{color:#3fb950}}
.pnl-neg{{color:#f85149}}
.badge-live{{font-size:0.7em;background:#f85149;color:#fff;padding:1px 6px;border-radius:4px;font-weight:700}}
.badge-paper{{font-size:0.7em;background:#1f6feb;color:#fff;padding:1px 6px;border-radius:4px;font-weight:700}}
.badge-live-sm{{font-size:0.65em;background:#f85149;color:#fff;padding:0 4px;border-radius:3px;margin-left:3px;font-weight:700}}
.badge-paper-sm{{font-size:0.65em;background:#1f6feb;color:#fff;padding:0 4px;border-radius:3px;margin-left:3px;font-weight:700}}
</style>
<meta http-equiv="refresh" content="30">
</head>
<body>
<h1>📊 Kalshi Trading Dashboard</h1>
<div class="subtitle">Updated: {ts} · Cache: {cache_age} ago · <a href="/" style="color:#58a6ff">↻ refresh</a> · Mode: {" | ".join(mode_links)}</div>

{paper_cards}
{live_cards}

{tier1_html}
{tier2_html}
{tier3_html}
{tier4_html}

<h2>🪙 Crypto 15-Min — Live Leans</h2>
<table class="tbl"><thead><tr><th>Coin</th><th>Prob</th><th>Bid/Ask</th><th>Lean</th><th>Edge</th><th>Conf</th><th>Above</th><th>Strk</th><th>Xings</th><th>Base</th><th>Spot</th><th>OI</th></tr></thead>
<tbody>{crypto_rows}</tbody></table>

{"".join((
  '<h2>🔴 LIVE Positions (' + str(len(positions_live)) + ')</h2>'
  '<table class="tbl"><thead><tr><th>Mode</th><th>Market</th><th>Side</th><th>Entry</th><th>Qty</th><th>Cost</th><th>Conf</th><th>Edge/Order</th></tr></thead>'
  '<tbody>' + pos_rows(positions_live, live=True) + '</tbody></table>'
) if show_live else "")}

{"".join((
  '<h2>🔵 Paper Positions (' + str(len(positions_paper)) + ')</h2>'
  '<table class="tbl"><thead><tr><th>Mode</th><th>Market</th><th>Side</th><th>Entry</th><th>Qty</th><th>Cost</th><th>Conf</th><th>Edge</th></tr></thead>'
  '<tbody>' + pos_rows(positions_paper, live=False) + '</tbody></table>'
) if show_paper else "")}

<h2>🧠 Decision Log (last {len(decisions)})</h2>
<table class="tbl"><thead><tr><th>Time</th><th>Coin</th><th>Action</th><th>Side</th><th>Prob</th><th>Edge</th><th>Conf</th><th>OI</th><th>Outcome</th></tr></thead>
<tbody>{dec_rows if dec_rows else '<tr><td colspan="9" style="color:#484f58;text-align:center">No decisions logged yet</td></tr>'}</tbody></table>

<h2>📈 Closed Trades ({len(closed)})</h2>
<table class="tbl"><thead><tr><th>M</th><th>Ticker</th><th>Side</th><th>Entry→Exit</th><th>P&L</th><th>Reason</th><th>Order</th></tr></thead>
<tbody>{closed_rows(closed)}</tbody></table>
</body></html>"""
    return html


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        # Parse mode filter from query string: ?mode=live|paper|all (default: all)
        qs = parsed.query
        params = {}
        if qs:
            for pair in qs.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    params[k] = v
        mode = params.get('mode', 'all')
        if mode not in ('live', 'paper', 'all'):
            mode = 'all'

        if parsed.path == "/":
            try:
                html = build_html(mode)
            except Exception as e:
                import traceback
                html = f"<html><body><h1>Error</h1><pre>{traceback.format_exc()}</pre></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Kalshi Dashboard @ http://0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
