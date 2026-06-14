"""kalshi_macro_snap.py -- point-in-time inventory + liquidity + implied-PDF snapshot for
Kalshi's US macro/economic event ladders, and the harness for a Kalshi-vs-reference lag test.

Kalshi macro markets are THRESHOLD LADDERS: for an event (e.g. June CPI YoY) a series of binary
markets "<metric> above X" share one close_time. strike_type='greater', floor_strike=X. The set of
"above X" yes-probabilities is a survival function S(X)=P(metric>X); the implied bracket pmf is
p(bracket k) = S(X_k) - S(X_{k+1}). The market's point estimate = sum X*p (or the median of S).

Book parsing: GET /markets/{t}/orderbook -> {'orderbook_fp':{'yes_dollars':[[px,qty]...],
'no_dollars':[[px,qty]...]}}. Best YES bid = max yes px; best YES ask = 1 - (max no px) because a
resting NO bid at q is an offer to sell YES at (1-q). Mid = (bid+ask)/2; spread = ask-bid. Depth in
contracts at touch = qty at those levels. Trade tape: GET /markets/trades?ticker=.. uses count_fp.

Fee (standard Economics category, fee_multiplier=1, quadratic): per-contract taker fee =
ceil(0.07*P*(1-P)*100)/100, max ~2c at P=0.5. Maker ~0. So a takeable edge must clear
spread/2 + ~1-2c. Economics is NOT the crypto-premium category (that was the 0.14 multiplier).

Usage:
  python kalshi_macro_snap.py inventory          # liquidity table across core US macro series
  python kalshi_macro_snap.py ladder KXCPIYOY    # implied survival/pmf for the nearest event
"""
from __future__ import annotations
import sys, math, time
import requests

B = "https://api.elections.kalshi.com/trade-api/v2"
S = requests.Session()

# core US macro series (current KX generation), with their sharp free reference
CORE = {
    "KXCPIYOY":     "Cleveland Fed Inflation Nowcast (CPI YoY)",
    "KXCPICOREYOY": "Cleveland Fed Nowcast (core CPI YoY)",
    "KXFED":        "CME FedWatch (FOMC upper bound)",
    "KXFEDDECISION":"CME FedWatch (FOMC move)",
    "KXPAYROLLS":   "Economist consensus / Bloomberg (NFP)",
    "KXU3":         "Economist consensus (unemployment U-3)",
    "KXGDP":        "Atlanta Fed GDPNow (real GDP QoQ)",
    "KXPCECORE":    "Cleveland Fed Nowcast (core PCE)",
    "KXEFFR":       "CME FedWatch / EFFR futures",
}

def get(path, **params):
    for a in range(4):
        try:
            return S.get(f"{B}{path}", params=params, timeout=20).json()
        except Exception:
            time.sleep(1.5 * (a + 1))
    return {}

def book(ticker):
    ob = get(f"/markets/{ticker}/orderbook", depth=30).get("orderbook_fp", {}) or {}
    yes = [(float(p), float(q)) for p, q in (ob.get("yes_dollars") or [])]
    no  = [(float(p), float(q)) for p, q in (ob.get("no_dollars") or [])]
    yb = max((p for p, _ in yes), default=None)
    nb = max((p for p, _ in no), default=None)
    ya = (1 - nb) if nb is not None else None
    yb_q = next((q for p, q in yes if p == yb), 0.0) if yb is not None else 0.0
    ya_q = next((q for p, q in no  if p == nb), 0.0) if nb is not None else 0.0
    return yb, ya, yb_q, ya_q

def fee(P):  # standard quadratic, multiplier 1
    return math.ceil(0.07 * P * (1 - P) * 100) / 100

def trade_vol(ticker, n=200):
    tr = get("/markets/trades", ticker=ticker, limit=n).get("trades", []) or []
    return sum(float(t.get("count_fp", 0) or 0) for t in tr), (tr[0]["created_time"][:16] if tr else "-")

def nearest_event(series):
    ms = get("/markets", series_ticker=series, status="open", limit=200).get("markets", []) or []
    ms = [m for m in ms if m.get("close_time")]
    if not ms:
        return None, []
    ms.sort(key=lambda m: m["close_time"])
    ct = ms[0]["close_time"]
    grp = [m for m in ms if m["close_time"] == ct]
    grp.sort(key=lambda m: (m.get("floor_strike") if m.get("floor_strike") is not None else -1e9))
    return ct, grp

def inventory():
    print(f"{'series':<14}{'next close':<12}{'brackets':<9}{'2sided':<7}{'mid_spr(c)':<11}{'touch_depth':<12}reference")
    for s, ref in CORE.items():
        ct, grp = nearest_event(s)
        if not grp:
            print(f"{s:<14}{'(none open)':<12}"); continue
        spreads, depths, two = [], [], 0
        for m in grp:
            yb, ya, ybq, yaq = book(m["ticker"])
            if yb is not None and ya is not None:
                two += 1; spreads.append(ya - yb); depths.append(min(ybq, yaq))
        msp = (sum(spreads) / len(spreads) * 100) if spreads else float("nan")
        mdp = (sum(depths) / len(depths)) if depths else 0
        print(f"{s:<14}{ct[:10]:<12}{len(grp):<9}{two:<7}{msp:<11.1f}{mdp:<12.0f}{ref}")

def ladder(series):
    ct, grp = nearest_event(series)
    print(f"=== {series} nearest event close {ct} : {len(grp)} 'above X' brackets ===")
    print(f"reference: {CORE.get(series,'?')}\n")
    print(f"{'above X':<10}{'yes_bid':<9}{'yes_ask':<9}{'mid=S(X)':<10}{'spr(c)':<8}{'fee@mid(c)':<11}{'depth':<8}{'lastTrade'}")
    rows = []
    for m in grp:
        yb, ya, ybq, yaq = book(m["ticker"])
        mid = (yb + ya) / 2 if (yb is not None and ya is not None) else (yb if yb is not None else ya)
        spr = (ya - yb) if (yb is not None and ya is not None) else float("nan")
        x = m.get("floor_strike")
        vol, lt = trade_vol(m["ticker"], 50)
        rows.append((x, mid))
        print(f"{str(x):<10}{str(yb):<9}{str(ya):<9}{(f'{mid:.3f}' if mid is not None else '-'):<10}"
              f"{(f'{spr*100:.1f}' if spr==spr else '-'):<8}"
              f"{(f'{fee(mid)*100:.0f}' if mid is not None else '-'):<11}{min(ybq,yaq):<8.0f}{lt}")
    # implied point estimate from the survival function
    pts = [(x, s) for x, s in rows if s is not None and x is not None]
    if len(pts) >= 2:
        pts.sort()
        ev = 0.0
        for i in range(len(pts) - 1):
            x0, s0 = pts[i]; x1, s1 = pts[i + 1]
            p = max(0.0, s0 - s1)               # P(metric in (x0,x1])
            ev += ((x0 + x1) / 2) * p
        print(f"\nimplied bracket-pmf point estimate ~ {ev:.3f} (sum of midpoint*P over brackets; "
              f"tails truncated -> approximate)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    if cmd == "inventory":
        inventory()
    elif cmd == "ladder":
        ladder(sys.argv[2])
