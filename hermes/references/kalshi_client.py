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
