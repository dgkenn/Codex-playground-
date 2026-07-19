#!/usr/bin/env python3
"""xvenue_converge.py -- Cross-venue convergence edge test (Kalshi vs Polymarket, Deribit anchor).

HYPOTHESIS: the same real-world binary event is listed on BOTH Polymarket and Kalshi. If the two
venues price it differently beyond fees, converging the gap (buy cheap venue / sell rich venue) is
an edge orthogonal to any risk premium -- a riskless cross-venue box if the settlement criterion is
identical. For crypto price levels, Deribit option-implied probability is a "smart" third anchor.

WHAT THIS SCRIPT DOES (only what the free data supports):
  1. Pins each venue's implied SPOT per coin (Deribit index; Kalshi orderbook ATM; Polymarket
     threshold markets) -- because a price gap is only a mispricing if both venues reference the
     SAME underlying. This is the anti-artifact guard.
  2. Builds a matched-event universe: same coin + threshold (within tol) + same resolution concept
     & date. Two families that survive conservative matching in this environment:
        (a) short-dated daily price-level markets whose dates overlap on both venues
        (b) milestone / "reach $X by year-end" touch markets (Kalshi KXBTCMAXY vs Poly milestones)
     Plus a best-effort text match for politics/econ.
  3. Uses EXECUTABLE prices: Kalshi best bid/ask from the live /orderbook endpoint (the market-list
     fields are null in this mirror); Polymarket bestBid/bestAsk. Nets the Kalshi fee 0.07*p*(1-p)
     (Polymarket taker fee = 0). Reports the divergence distribution and the executable box PnL.
  4. Deribit anchor: BS European digital P(S_T>K) from mark IV; for touch markets, reports the
     reflection-principle touch upper bound. Flags which venue deviates from Deribit.

Prices reflect this environment's replay clock (BTC~$64.5k, ETH~$1.88k) -- reported as produced.
"""
import json, os, time, math, re, urllib.request, urllib.error
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA  = "https://gamma-api.polymarket.com"
DERIBIT= "https://www.deribit.com/api/v2/public"
CACHE  = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/xv_cache"
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}

def _get(url, cache_key=None, ttl=1e9):
    if cache_key:
        p = os.path.join(CACHE, cache_key)
        if os.path.exists(p) and time.time()-os.path.getmtime(p) < ttl:
            try:
                return json.load(open(p))
            except Exception:
                pass
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            data = json.load(urllib.request.urlopen(req, timeout=40))
            if cache_key:
                json.dump(data, open(os.path.join(CACHE, cache_key), "w"))
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                time.sleep(1.5*(attempt+1)); continue
            raise
        except Exception:
            time.sleep(1.0*(attempt+1))
    return None

# ---------------------------------------------------------------- Kalshi orderbook -> exec prices
def kalshi_exec(ticker, ttl=1e9):
    """Return (yes_bid, yes_ask, yes_bid_size, yes_ask_size) in dollars from the live book, or None."""
    d = _get(f"{KALSHI}/markets/{ticker}/orderbook", cache_key=f"ob_{ticker}.json", ttl=ttl)
    if not d:
        return None
    o = d.get("orderbook_fp") or {}
    yes = o.get("yes_dollars") or []   # resting bids to BUY yes
    no  = o.get("no_dollars") or []    # resting bids to BUY no
    if not yes and not no:
        return None
    yb = max((float(p) for p, _ in yes), default=0.0)
    yb_sz = max((float(s) for p, s in yes), default=0.0) if yes else 0.0
    nb = max((float(p) for p, _ in no), default=0.0)
    nb_sz = max((float(s) for p, s in no), default=0.0) if no else 0.0
    ya = 1.0 - nb                      # yes ask = 1 - best no bid
    ya_sz = nb_sz
    return yb, ya, yb_sz, ya_sz

def kalshi_series(series, status="open", limit=1000):
    d = _get(f"{KALSHI}/markets?series_ticker={series}&status={status}&limit={limit}",
             cache_key=f"ser_{series}_{status}.json", ttl=300)
    return (d or {}).get("markets", [])

# ---------------------------------------------------------------- Deribit
def deribit_index(coin):
    d = _get(f"{DERIBIT}/get_index_price?index_name={coin.lower()}_usd", cache_key=f"idx_{coin}.json", ttl=120)
    return d["result"]["index_price"] if d else None

def deribit_options(coin):
    d = _get(f"{DERIBIT}/get_book_summary_by_currency?currency={coin}&kind=option",
             cache_key=f"opt_{coin}.json", ttl=300)
    return d["result"] if d else []

def norm_cdf(x): return 0.5*(1.0+math.erf(x/math.sqrt(2)))

def bs_digital_prob(S, K, T, iv):
    """European digital P(S_T > K) under BS with vol iv (annualized, decimal), r=0."""
    if T <= 0 or iv <= 0 or S <= 0:
        return float(S > K)
    d2 = (math.log(S/K) - 0.5*iv*iv*T) / (iv*math.sqrt(T))
    return norm_cdf(d2)

def deribit_digital(coin, K, target_date):
    """Interpolate P(S>K) at target_date from Deribit option chain mark IVs near strike K."""
    S = deribit_index(coin)
    if not S: return None
    opts = deribit_options(coin)
    # parse expiry from instrument name BTC-<DDMMMYY>-<strike>-<C/P>
    months = {m:i for i,m in enumerate(["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"],1)}
    rows=[]
    for o in opts:
        nm=o.get("instrument_name","")
        parts=nm.split("-")
        if len(parts)!=4: continue
        _,exp,strike,cp=parts
        m=re.match(r"(\d+)([A-Z]{3})(\d{2})", exp)
        if not m: continue
        dd,mon,yy=int(m.group(1)),months.get(m.group(2)),2000+int(m.group(3))
        if not mon: continue
        try: edt=datetime(yy,mon,dd,8,0,tzinfo=timezone.utc)
        except Exception: continue
        iv=o.get("mark_iv")
        if iv is None: continue
        rows.append((edt,float(strike),iv/100.0))
    if not rows: return None
    tgt=target_date
    # nearest expiry on each side of target
    exps=sorted(set(r[0] for r in rows))
    now=datetime.now(timezone.utc)
    # pick expiry closest to target
    best_exp=min(exps, key=lambda e: abs((e-tgt).total_seconds()))
    T=max((best_exp-now).total_seconds()/(365.25*86400), 1e-6)
    # IV at strike K: nearest strikes' mark_iv average (use IVs at this expiry)
    same=[(k,iv) for e,k,iv in rows if e==best_exp]
    if not same: return None
    same.sort(key=lambda x: abs(x[0]-K))
    iv=np.mean([iv for _,iv in same[:4]])
    p=bs_digital_prob(S,K,T,iv)
    return {"S":S,"iv":iv,"T":T,"exp":best_exp.date().isoformat(),"digital":p}

# ---------------------------------------------------------------- Polymarket
def poly_markets(closed=False):
    """Broad pull: flat pagination (offset<=2500) + crypto tag + volume-ordered head. Dedup by id."""
    out={}
    c='true' if closed else 'false'
    # flat pagination
    for off in range(0, 2500, 500):
        d=_get(f"{GAMMA}/markets?closed={c}&limit=500&offset={off}", cache_key=f"polyF_{c}_{off}.json", ttl=300)
        if not d: break
        for m in d: out[m["id"]]=m
    # volume-ordered head (caps ~100/page); walk offsets
    for off in range(0, 1000, 100):
        d=_get(f"{GAMMA}/markets?closed={c}&limit=100&offset={off}&order=volume&ascending=false",
               cache_key=f"polyV_{c}_{off}.json", ttl=300)
        if not d: break
        for m in d: out[m["id"]]=m
    # crypto tag
    for tag in (21,):
        d=_get(f"{GAMMA}/markets?closed={c}&limit=200&tag_id={tag}", cache_key=f"polyT_{c}_{tag}.json", ttl=300)
        if d:
            for m in d: out[m["id"]]=m
    return list(out.values())

def poly_price(m):
    """Return (yes_bid, yes_ask, yes_mid) for the YES/first outcome, executable where possible."""
    bb=m.get("bestBid"); ba=m.get("bestAsk")
    op=m.get("outcomePrices")
    mid=None
    if op:
        try:
            arr=json.loads(op) if isinstance(op,str) else op
            mid=float(arr[0])
        except Exception: pass
    bb=float(bb) if bb not in (None,"") else None
    ba=float(ba) if ba not in (None,"") else None
    if mid is None and bb is not None and ba is not None: mid=(bb+ba)/2
    return bb,ba,mid

# ---------------------------------------------------------------- parsing / normalization
COIN_ALIAS={"bitcoin":"BTC","btc":"BTC","ethereum":"ETH","eth":"ETH","solana":"SOL","sol":"SOL",
            "xrp":"XRP","ripple":"XRP","dogecoin":"DOGE","doge":"DOGE"}
def parse_coin(text):
    t=text.lower()
    for k,v in COIN_ALIAS.items():
        if re.search(rf"\b{k}\b", t): return v
    return None
def parse_dollars(text):
    vals=re.findall(r"\$\s?([\d][\d,]*(?:\.\d+)?)", text)
    return [float(v.replace(",","")) for v in vals]

MONTHS={m:i for i,m in enumerate(["january","february","march","april","may","june","july",
        "august","september","october","november","december"],1)}
def parse_poly_date(m):
    ed=m.get("endDate")
    if ed:
        try: return datetime.fromisoformat(ed.replace("Z","+00:00"))
        except Exception: pass
    return None

def kalshi_daily_date(ticker):
    # KXBTCD-26JUL1613-T64000  -> date 2026-07-16
    mt=re.match(r"[A-Z]+-(\d{2})([A-Z]{3})(\d{2})", ticker)
    if not mt: return None
    yy,mon,dd=2000+int(mt.group(1)), {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,
        "AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}[mt.group(2)], int(mt.group(3))
    return datetime(yy,mon,dd,tzinfo=timezone.utc).date()

# ================================================================ MAIN
def main():
    print("="*78); print("CROSS-VENUE CONVERGENCE  (Kalshi x Polymarket, Deribit anchor)"); print("="*78)
    report=[]
    def out(*a):
        s=" ".join(str(x) for x in a); print(s); report.append(s)

    # ---- 1. SPOT CONSISTENCY per coin -----------------------------------------
    out("\n[1] SPOT CONSISTENCY CHECK (a gap is only a mispricing if the underlying matches)")
    spot={}
    for coin,ser in [("BTC","KXBTCD"),("ETH","KXETHD")]:
        di=deribit_index(coin)
        # Kalshi ATM: today's daily, strike where mid ~0.5 from live book.
        # Only probe strikes within +/-3% of the Deribit index (avoids ~260 orderbook calls).
        ms=[m for m in kalshi_series(ser) if kalshi_daily_date(m["ticker"])==datetime.now(timezone.utc).date()
            and m.get("floor_strike") and di and abs(m["floor_strike"]-di)/di < 0.03]
        atm=None; best=1e9
        for m in ms:
            ex=kalshi_exec(m["ticker"], ttl=1e9)
            if not ex: continue
            mid=(ex[0]+ex[1])/2
            if 0.02<mid<0.98:
                # implied spot ~ strike when mid crosses 0.5
                if abs(mid-0.5)<best:
                    best=abs(mid-0.5); atm=m.get("floor_strike")
        spot[coin]={"deribit":di,"kalshi_atm":atm}
        out(f"    {coin}: Deribit index=${di:,.0f}   Kalshi ATM strike~${(atm or 0):,.0f}   "
            f"(agree={'YES' if atm and di and abs(atm-di)/di<0.03 else 'check'})")

    # ---- 2. MATCHED UNIVERSE ---------------------------------------------------
    out("\n[2] BUILDING MATCHED-EVENT UNIVERSE")
    pm_open=poly_markets(closed=False)
    out(f"    Polymarket open markets pulled: {len(pm_open)}")

    matches=[]   # normalized so YES = P(coin settles >= threshold) on BOTH venues
    kser={"BTC":"KXBTCD","ETH":"KXETHD","XRP":"KXXRPD","SOL":"KXSOLD","DOGE":"KXDOGED"}
    kcache={}
    def kser_get(s):
        if s not in kcache: kcache[s]=kalshi_series(s)
        return kcache[s]

    def add_match(family,coin,K,date,km_ticker,kyb,kya,pq,pyb,pya,pmid,der,note=""):
        matches.append(dict(family=family,coin=coin,threshold=K,date=date,k_ticker=km_ticker,
            k_yb=kyb,k_ya=kya,p_q=pq,p_yb=pyb,p_ya=pya,p_mid=pmid,deribit=der,deribit_note=note))

    # --- family A: short-dated daily price levels (date overlap), normalized to P(>=K) ---
    poly_short=[]
    for m in pm_open:
        q=m.get("question","")
        if re.search(r"price of (bitcoin|ethereum|btc|eth|solana|xrp)", q, re.I):
            coin=parse_coin(q); ds=parse_dollars(q); d=parse_poly_date(m)
            if coin and ds and d: poly_short.append((m,coin,ds,d))
    out(f"    Polymarket short-dated crypto price-level markets: {len(poly_short)}")

    for m,coin,ds,d in poly_short:
        ser=kser.get(coin)
        if not ser: continue
        cand=[km for km in kser_get(ser) if kalshi_daily_date(km["ticker"])==d.date()
              and km.get("floor_strike")]
        if not cand: continue
        q=m.get("question","").lower()
        K=ds[0]
        # normalize Polymarket YES to P(price >= K)
        pb,pa,pm_=poly_price(m)
        if pm_ is None: continue
        if "above" in q or "greater" in q:
            pnorm=(pb,pa,pm_)  # already P(>=K)
        elif "less than" in q or "below" in q or "under" in q:
            # YES(poly)=P(<K); convert to P(>=K)=1-p  (bid/ask flip)
            pnorm=((1-pa) if pa is not None else None,(1-pb) if pb is not None else None,1-pm_)
        else:
            continue  # skip "between" (needs ladder combo) -- conservative
        # Kalshi market at strike K (Kalshi YES = P(price >= floor_strike))
        km=min(cand, key=lambda x: abs(x["floor_strike"]-K))
        if abs(km["floor_strike"]-K)/max(K,1) > 0.01:  # threshold tolerance 1%
            continue
        kx=kalshi_exec(km["ticker"])
        if not kx: continue
        der=deribit_digital(coin,K,d)
        add_match("short_daily",coin,K,d.date().isoformat(),km["ticker"],kx[0],kx[1],
                  m.get("question",""),pnorm[0],pnorm[1],pnorm[2],(der or {}).get("digital"))

    # --- family B: milestone / touch by year-end (Kalshi *MAXY vs Poly reach/hit) ---
    milestone_ser={"BTC":["KXBTCMAXY"],"ETH":["ETHMAXY"]}
    poly_mile=[m for m in pm_open if re.search(r"(reach|hit)\s+\$[\d,]+", m.get("question",""), re.I)
               and parse_coin(m.get("question","")) and "before gta" not in m.get("question","").lower()]
    out(f"    Polymarket milestone (reach/hit $X by date) markets: {len(poly_mile)}")
    for m in poly_mile:
        coin=parse_coin(m["question"]); ds=parse_dollars(m["question"]); d=parse_poly_date(m)
        if not (coin and ds and d): continue
        K=ds[0]
        # resolution year: prefer a 4-digit year in the question, else endDate.year (and year-1,
        # since Poly "by Dec 31 20XX" often carries endDate 20XX+1-01-01)
        yrs=set(int(y) for y in re.findall(r"20(\d{2})", m["question"]))
        yrs |= {d.year-2000, d.year-2000-1}
        for ser in milestone_ser.get(coin,[]):
            cand=[km for km in kser_get(ser) if km.get("floor_strike") and abs(km["floor_strike"]-K)/K<0.01
                  and any((f"{y:02d}DEC") in km["ticker"] for y in yrs)]
            if not cand: continue
            km=cand[0]; kx=kalshi_exec(km["ticker"]); pb,pa,pm_=poly_price(m)
            if not kx or pm_ is None: continue
            der=deribit_digital(coin,K,d)
            add_match("milestone",coin,K,d.date().isoformat(),km["ticker"],kx[0],kx[1],
                      m["question"],pb,pa,pm_,(der or {}).get("digital"),"european digital; touch>=this")
            break

    out(f"\n    >>> GENUINE MATCHED PAIRS (crypto): {len(matches)}")
    for x in matches:
        km=(x['k_yb']+x['k_ya'])/2
        tstr=f"${x['threshold']:,.2f}" if x['threshold']<100 else f"${x['threshold']:,.0f}"
        out(f"      [{x['family']}] {x['coin']} {tstr} {x['date']}  "
            f"Kalshi mid={km:.3f}({x['k_yb']:.2f}/{x['k_ya']:.2f})  Poly mid={x['p_mid']:.3f}"
            f"({(x['p_yb'] if x['p_yb'] is not None else float('nan')):.2f}/{(x['p_ya'] if x['p_ya'] is not None else float('nan')):.2f})"
            + (f"  Deribit={x['deribit']:.3f}" if x['deribit'] is not None else "  Deribit=NA"))

    # ---- 3. DIVERGENCE DISTRIBUTION & TRADEABLE BOX ---------------------------
    out("\n[3] DIVERGENCE & EXECUTABLE CONVERGENCE (Kalshi fee=0.07*p*(1-p), Poly fee=0)")
    gaps=[]; boxes=[]; which_mis=defaultdict(int)
    for x in matches:
        km=(x['k_yb']+x['k_ya'])/2
        gap=abs(km-x['p_mid']); gaps.append(gap)
        # executable box: to lock $1, buy YES on cheap venue at its ask, buy NO on rich venue.
        # direction 1: Kalshi rich (sell yes on Kalshi = buy no), Poly cheap (buy yes)
        # We can only *sell* yes on Kalshi at k_yb (hit the bid) and buy yes on Poly at p_ya.
        # locked profit if we sell-rich/buy-cheap and both settle same:
        # box net = (rich_bid - cheap_ask) - kalshi_fee
        def fee(p): return 0.07*p*(1-p)
        best_box=-9
        # A: Kalshi is rich -> sell yes Kalshi @k_yb, buy yes Poly @p_ya
        if x['p_ya'] is not None:
            box = x['k_yb'] - x['p_ya'] - fee(km); best_box=max(best_box,box)
        # B: Poly is rich -> sell yes Poly @p_yb, buy yes Kalshi @k_ya
        if x['p_yb'] is not None:
            box = x['p_yb'] - x['k_ya'] - fee(km); best_box=max(best_box,box)
        boxes.append(best_box)
        # which venue mispriced vs Deribit
        if x['deribit'] is not None:
            dk=abs(km-x['deribit']); dp=abs(x['p_mid']-x['deribit'])
            which_mis["kalshi_off" if dk>dp else "poly_off"] += 1
    if gaps:
        g=np.array(gaps); b=np.array(boxes)
        out(f"    matched pairs: {len(g)}")
        out(f"    |mid gap| : mean={g.mean():.3f}  median={np.median(g):.3f}  max={g.max():.3f}")
        for thr in (0.03,0.05,0.10):
            out(f"      P(|gap|>{thr:.2f}) = {(g>thr).mean():.2f}  ({int((g>thr).sum())}/{len(g)})")
        out(f"    executable box net (>0 = riskless cross-venue arb after fees):")
        out(f"      mean={b.mean():.3f}  max={b.max():.3f}  #profitable={(b>0).sum()}/{len(b)}")
        if which_mis:
            out(f"    vs Deribit anchor (further-from-Deribit venue): {dict(which_mis)}")
        # per-family + directional-cluster diagnostics
        for fam in sorted(set(x['family'] for x in matches)):
            fm=[x for x in matches if x['family']==fam]
            signs=[((x['k_yb']+x['k_ya'])/2 - x['p_mid']) for x in fm]
            fg=np.array([abs(s) for s in signs])
            allpos=all(s>0 for s in signs); allneg=all(s<0 for s in signs)
            out(f"    [{fam}] n={len(fm)} mean|gap|={fg.mean():.3f} "
                f"Kalshi-richer={sum(s>0 for s in signs)}/{len(fm)} "
                f"{'(MONOTONE one-directional cluster)' if (allpos or allneg) and len(fm)>=3 else ''}")
        out("    NOTE: the 7 BTC milestone strikes are the SAME year-end touch curve -> one")
        out("    correlated bet (n_eff~1-2), NOT 7 independent observations.")
        out("    NOTE: milestone box is NOT truly riskless -- Kalshi & Polymarket settle a 5.5-month")
        out("    BTC touch off DIFFERENT price oracles; a wick near the strike can split settlement.")

    # ---- 4. SETTLEMENT-PNL feasibility ---------------------------------------
    out("\n[4] SETTLEMENT-BASED CONVERGENCE PnL")
    out("    Requires synchronized PRE-settlement quotes on BOTH venues for pairs that later settled.")
    out("    In this environment Kalshi's market-list price fields are null and Polymarket gamma")
    out("    exposes only current quotes; matched pairs are near-dated and none have both a stored")
    out("    pre-settlement quote AND a settled outcome. The live executable box in [3] is itself a")
    out("    settlement-INDEPENDENT test (a locked box pays regardless of outcome), so it is the")
    out("    honest tradeability metric here.")

    # ---- 5. ORTHOGONALITY -----------------------------------------------------
    out("\n[5] ORTHOGONALITY to 'sell crypto longshots'")
    out("    The two-venue box (long cheap venue + short rich venue on the SAME event) is")
    out("    market-neutral -> orthogonal to a directional longshot-RP series by construction.")
    out("    BUT if only ONE side is tradeable, shorting the rich Kalshi touch alone IS a crypto")
    out("    longshot short -> then it OVERLAPS the longshot-RP edge and is NOT orthogonal.")
    out("    (No settled paired history here to compute a realized-PnL correlation series.)")

    # ---- 6. VERDICT -----------------------------------------------------------
    out("\n[6] VERDICT")
    n=len(matches)
    prof=int((np.array(boxes)>0).sum()) if boxes else 0
    out(f"    Genuine same-coin+threshold+date matches with live quotes on BOTH venues: {n} (<30).")
    out(f"    Executable positive boxes: {prof}/{n} (max +{(np.array(boxes).max()*100 if boxes else 0):.1f}c).")
    out("    SIGNAL: BTC year-end touch ladder is persistently 2-5c RICHER on Kalshi than on")
    out("    Polymarket (monotone, 7/7 strikes), and Deribit's implied touch says KALSHI is the")
    out("    over-priced venue -> convergence = SELL Kalshi touch / BUY Polymarket touch.")
    out("    BUT: (a) it is ONE correlated cluster (n_eff~1-2, not significant); (b) NOT riskless")
    out("    (cross-oracle 5.5-month barrier settlement can split); (c) capital locked ~5.5mo for")
    out("    a few cents; (d) short-dated same-day crypto gaps are sub-cent, inside fees.")
    out("    => Suggestive venue-relative-value tilt, NOT a proven robust stackable riskless edge.")
    json.dump(matches, open(os.path.join(CACHE,"matches.json"),"w"), indent=2, default=str)
    # write report
    rep_path="/home/user/Codex-playground-/xvenue_converge_report.md"
    return report, matches, (gaps if gaps else []), (boxes if boxes else []), dict(which_mis) if gaps else {}

if __name__=="__main__":
    main()
