#!/usr/bin/env python3
"""
pmkt_horizon.py
================
Does Polymarket's LONGER-HORIZON (weekly/monthly) BTC/ETH price markets contain a
real, COST-SURVIVING, TRADE-WEIGHTED edge? Polymarket is zero-fee; only the CLOB
half-spread is a cost.

Anti-artifact discipline baked in (we have killed 4 prior "edges"):
  * Entry price strictly from the UNCERTAIN pre-resolution window (first half of
    market life), causal, never last/settlement price.  (no look-ahead)
  * Outcome only from UMA resolution.
  * Cluster by resolution WEEK (report distinct-week counts, flag underpower).
  * MARKET-weighted vs TRADE-weighted (actual adverse-selected fills) reported
    side by side; if they diverge, market-weighted is the artifact.
  * Report the FULL picture, not the best cell.

Data sources (public, no auth):
  gamma-api.polymarket.com/events        -> market universe + UMA resolution
  clob.polymarket.com/prices-history     -> causal entry mid (YES token)
  data-api.polymarket.com/trades         -> actual taker fills (trade-weighting, spread)
  www.deribit.com/api/v2                  -> smart options market: perp spot + DVOL history
"""
import os, sys, json, time, math, datetime as dt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

CACHE = "/home/user/Codex-playground-/scratchpad/pmkt_cache"
os.makedirs(CACHE, exist_ok=True)
GAMMA="https://gamma-api.polymarket.com"
CLOB="https://clob.polymarket.com"
DATA="https://data-api.polymarket.com"
DERI="https://www.deribit.com/api/v2/public/"

S = requests.Session()
S.headers.update({"User-Agent":"research/1.0"})

def _get(url, params=None, tries=4, timeout=40):
    for i in range(tries):
        try:
            r=S.get(url, params=params, timeout=timeout)
            if r.status_code==200: return r.json()
            if r.status_code in (429,500,502,503,504): time.sleep(1.5*(i+1)); continue
            return None
        except Exception:
            time.sleep(1.2*(i+1))
    return None

def cache_get(key, fn):
    p=os.path.join(CACHE, key+".json")
    if os.path.exists(p):
        try:
            with open(p) as f: return json.load(f)
        except Exception: pass
    v=fn()
    tmp=p+".tmp"
    with open(tmp,"w") as f: json.dump(v,f)
    os.replace(tmp,p)
    return v

def iso(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc)
def parse_dt(s):
    if not s: return None
    return dt.datetime.fromisoformat(s.replace("Z","+00:00"))

# --------------------------------------------------------------------------
# 1. ENUMERATE universe: weekly terminal "above on <date>" (series 45 BTC, 42 ETH)
#    + monthly one-touch ladders "what price will X hit in <month>"
# --------------------------------------------------------------------------
def enum_series(series_id):
    def fn():
        out=[]; off=0
        while True:
            d=_get(f"{GAMMA}/events", dict(series_id=series_id, closed="true", limit=100, offset=off))
            if not d: break
            out+=d; off+=100
            if len(d)<100: break
        return out
    return cache_get(f"events_series_{series_id}", fn)

def enum_search_events(q):
    d=_get(f"{GAMMA}/public-search", dict(q=q, limit_per_type=40))
    return (d or {}).get("events",[]) if d else []

def strike_from(m):
    g=m.get("groupItemTitle") or ""
    g=g.replace(",","").replace("$","").strip()
    try: return float(g)
    except:
        # fallback parse from question
        import re
        qq=m.get("question","").replace(",","")
        mt=re.search(r"\$?([0-9]+(?:\.[0-9]+)?)(k|K)?", qq)
        if mt:
            v=float(mt.group(1))
            if mt.group(2): v*=1000
            return v
        return None

def resolved_outcome(m):
    """return yes_win in {0.0,1.0} or None if not cleanly resolved."""
    if (m.get("umaResolutionStatus") or "").lower()!="resolved" and not m.get("closed"):
        return None
    op=m.get("outcomePrices")
    oc=m.get("outcomes")
    try:
        op=json.loads(op) if isinstance(op,str) else op
        oc=json.loads(oc) if isinstance(oc,str) else oc
    except: return None
    if not op or not oc: return None
    d={oc[i].lower():float(op[i]) for i in range(len(oc))}
    y=d.get("yes")
    if y is None: return None
    if y>0.98: return 1.0
    if y<0.02: return 0.0
    return None  # ambiguous / not settled to 0/1

def build_universe():
    markets=[]
    # ---- weekly terminal above (BTC 45, ETH 42) ----
    for sid,asset in [(45,"BTC"),(42,"ETH")]:
        for e in enum_series(sid):
            if not e.get("closed"): continue
            slug=e.get("slug","")
            # keep the multi-strike "above on" terminal family; drop intraday time-suffixed
            if "above-on" not in slug:
                # some titled differently; require question 'above' below
                pass
            start=parse_dt(e.get("startDate")); end=parse_dt(e.get("endDate"))
            if not start or not end: continue
            horizon=(end-start).total_seconds()/86400.0
            # weekly bucket: horizon >= 2 days (drops intraday 9am/10am variants ~fraction of day)
            if horizon < 2.0: continue
            mks=e.get("markets",[])
            if len(mks)<5: continue
            for m in mks:
                q=(m.get("question") or "").lower()
                if "above" not in q: continue
                yw=resolved_outcome(m)
                if yw is None: continue
                K=strike_from(m)
                if not K: continue
                try: toks=json.loads(m["clobTokenIds"])
                except: continue
                if len(toks)<2: continue
                markets.append(dict(
                    asset=asset, family="weekly_terminal", slug=slug,
                    question=m.get("question"), conditionId=m.get("conditionId"),
                    yes_token=toks[0], no_token=toks[1], strike=K, yes_win=yw,
                    start=start.timestamp(), end=end.timestamp(), horizon_days=horizon,
                    volume=float(m.get("volumeNum") or 0)))
    # ---- monthly one-touch ladders ----
    seen=set()
    for asset,qs in [("BTC","what price will bitcoin hit"),("ETH","what price will ethereum hit")]:
        for e in enum_search_events(qs):
            slug=e.get("slug","")
            if slug in seen: continue
            if not e.get("closed"): continue
            # monthly: 'in-<month>' style, horizon ~2-5 weeks; weekly-range 'july-13-19' too
            start=parse_dt(e.get("startDate")); end=parse_dt(e.get("endDate"))
            if not start or not end: continue
            horizon=(end-start).total_seconds()/86400.0
            if horizon < 6: continue  # monthly/multiweek one-touch
            seen.add(slug)
            fam="monthly_touch" if horizon>=20 else "week_touch"
            for m in e.get("markets",[]):
                yw=resolved_outcome(m)
                if yw is None: continue
                K=strike_from(m)
                if not K: continue
                try: toks=json.loads(m["clobTokenIds"])
                except: continue
                if len(toks)<2: continue
                markets.append(dict(
                    asset=asset, family=fam, slug=slug,
                    question=m.get("question"), conditionId=m.get("conditionId"),
                    yes_token=toks[0], no_token=toks[1], strike=K, yes_win=yw,
                    start=start.timestamp(), end=end.timestamp(), horizon_days=horizon,
                    volume=float(m.get("volumeNum") or 0)))
    return markets

# --------------------------------------------------------------------------
# 2. CAUSAL ENTRY: YES price-history, time-weighted mid over first-half window
# --------------------------------------------------------------------------
def price_history(token, start, end):
    key="ph_"+str(token)+"_"+str(int(start))+"_"+str(int(end))
    def fn():
        d=_get(f"{CLOB}/prices-history", dict(market=token, startTs=int(start), endTs=int(end), fidelity=60))
        return (d or {}).get("history",[])
    return cache_get(key, fn)

def causal_entry(mk, frac_lo=0.10, frac_hi=0.50):
    """time-weighted mean YES price over [start+lo*life, start+hi*life] (pre-resolution)."""
    st,en=mk["start"],mk["end"]; life=en-st
    lo=st+frac_lo*life; hi=st+frac_hi*life
    h=price_history(mk["yes_token"], st, en)
    pts=[(p["t"],p["p"]) for p in h if lo<=p["t"]<=hi]
    if len(pts)<2:
        # fallback: nearest single point to mid of window
        allp=[(p["t"],p["p"]) for p in h if p["t"]<=hi and p["t"]>=st]
        if not allp: return None,0
        allp.sort(); return allp[-1][1], len(allp)
    pts.sort()
    tot=0.0; wsum=0.0
    for i in range(len(pts)-1):
        dtw=pts[i+1][0]-pts[i][0]
        tot+=pts[i][1]*dtw; wsum+=dtw
    return (tot/wsum if wsum>0 else np.mean([p for _,p in pts])), len(pts)

def mid_interp(h):
    """return function t->interpolated YES mid from history list."""
    if not h: return None
    ts=np.array([p["t"] for p in h],float); ps=np.array([p["p"] for p in h],float)
    order=np.argsort(ts); ts=ts[order]; ps=ps[order]
    def f(t):
        return float(np.interp(t, ts, ps))
    return f

# --------------------------------------------------------------------------
# 3. TRADES: actual taker fills -> effective YES direction/price; spread; adverse sel
# --------------------------------------------------------------------------
def trades_for(conditionId, max_pages=4, page=500):
    key="tr_"+conditionId
    def fn():
        out=[]; off=0
        for _ in range(max_pages):
            d=_get(f"{DATA}/trades", dict(market=conditionId, limit=page, offset=off))
            if not d: break
            out+=d
            if len(d)<page: break
            off+=page
        return out
    return cache_get(key, fn)

def norm_trade(t):
    """-> (dir, yes_price, size, ts). dir=+1 taker net-bought YES, -1 sold YES."""
    side=(t.get("side") or "").upper(); oc=(t.get("outcome") or "").lower()
    p=float(t.get("price") or 0); sz=float(t.get("size") or 0); ts=int(t.get("timestamp") or 0)
    if oc=="yes":
        if side=="BUY": return (+1, p, sz, ts)
        else: return (-1, p, sz, ts)
    elif oc=="no":
        if side=="BUY": return (-1, 1-p, sz, ts)   # buy No = short Yes at (1-p)
        else: return (+1, 1-p, sz, ts)             # sell No = long Yes at (1-p)
    return (0,p,sz,ts)

# --------------------------------------------------------------------------
# 4. DERIBIT smart-market implied P(S_T>K) via perp spot + DVOL (30d CM vol)
# --------------------------------------------------------------------------
def deribit_series(currency, start_ms, end_ms, res_sec=3600):
    key=f"deri_{currency}_{start_ms}_{end_ms}"
    def fn():
        px=_get(DERI+"get_tradingview_chart_data",
                dict(instrument_name=f"{currency}-PERPETUAL", start_timestamp=start_ms,
                     end_timestamp=end_ms, resolution=str(res_sec//60)))
        dv=_get(DERI+"get_volatility_index_data",
                dict(currency=currency, start_timestamp=start_ms, end_timestamp=end_ms, resolution=res_sec))
        return {"px":px, "dv":dv}
    return cache_get(key, fn)

_DERI_CACHE={}
def deribit_lookup(currency):
    if currency in _DERI_CACHE: return _DERI_CACHE[currency]
    # one big pull 2023-06 .. 2026-07 hourly
    start_ms=int(dt.datetime(2023,6,1,tzinfo=dt.timezone.utc).timestamp()*1000)
    end_ms  =int(dt.datetime(2026,7,16,tzinfo=dt.timezone.utc).timestamp()*1000)
    # deribit caps ~ many pts; chunk monthly
    spot_t=[]; spot_v=[]; vol_t=[]; vol_v=[]
    cur=start_ms
    month=30*86400*1000
    while cur<end_ms:
        nxt=min(cur+month, end_ms)
        d=deribit_series(currency, cur, nxt)
        px=(d.get("px") or {}).get("result",{})
        if px and px.get("ticks"):
            spot_t+=px["ticks"]; spot_v+=px["close"]
        dv=(d.get("dv") or {}).get("result",{}).get("data",[])
        for row in dv:
            vol_t.append(row[0]); vol_v.append(row[4])  # close DVOL
        cur=nxt
    st=np.array(spot_t,float); sv=np.array(spot_v,float)
    o=np.argsort(st); st,sv=st[o],sv[o]
    vt=np.array(vol_t,float); vv=np.array(vol_v,float)
    o=np.argsort(vt); vt,vv=vt[o],vv[o]
    _DERI_CACHE[currency]=(st,sv,vt,vv)
    return _DERI_CACHE[currency]

def norm_cdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def deribit_digital(currency, entry_ts, end_ts, strike):
    st,sv,vt,vv=deribit_lookup(currency)
    if len(st)==0 or len(vt)==0: return None
    tms=entry_ts*1000
    if tms<st[0] or tms>st[-1]: return None
    Sspot=float(np.interp(tms, st, sv))
    sigma=float(np.interp(tms, vt, vv))/100.0
    T=(end_ts-entry_ts)/ (365*86400.0)
    if T<=0 or sigma<=0 or Sspot<=0: return None
    d2=(math.log(Sspot/strike) - 0.5*sigma*sigma*T)/(sigma*math.sqrt(T))
    return norm_cdf(d2)

# --------------------------------------------------------------------------
# STATS: clustered t-stat (cluster by resolution ISO-week)
# --------------------------------------------------------------------------
def week_key(end_ts):
    d=iso(end_ts); y,w,_=d.isocalendar(); return f"{y}-W{w:02d}"

def cluster_t(values, clusters):
    """mean and clustered-SE t-stat of `values`, clustered by `clusters` label."""
    v=np.array(values,float);
    if len(v)<3: return (np.mean(v) if len(v) else float('nan'), float('nan'), len(v), 0)
    m=v.mean()
    groups=defaultdict(list)
    for x,c in zip(v,clusters): groups[c].append(x)
    G=len(groups); N=len(v)
    # cluster-robust SE of the mean: sum over clusters of (sum resid)^2 / N^2, adj
    ss=0.0
    for c,xs in groups.items():
        r=sum(x-m for x in xs); ss+=r*r
    if G<2 or N<2: return (m,float('nan'),N,G)
    var=ss*(G/(G-1.0))/(N*N)
    se=math.sqrt(var) if var>0 else float('nan')
    t=m/se if se and se>0 else float('nan')
    return (m,t,N,G)

# ==========================================================================
def main():
    t0=time.time()
    print("[1/5] Enumerating universe ...", flush=True)
    universe=build_universe()
    print(f"    raw resolved markets: {len(universe)}", flush=True)

    # ---- fetch causal entry for all (threaded) ----
    print("[2/5] Fetching causal entry prices (CLOB history) ...", flush=True)
    def fill_entry(mk):
        e,n=causal_entry(mk)
        mk["entry"]=e; mk["entry_npts"]=n
        return mk
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs=[ex.submit(fill_entry,mk) for mk in universe]
        done=0
        for f in as_completed(futs):
            done+=1
            if done%400==0: print(f"    entry {done}/{len(universe)}", flush=True)
    rows=[m for m in universe if m.get("entry") is not None and 0.0<=m["entry"]<=1.0]
    print(f"    markets with entry: {len(rows)}", flush=True)

    # ---- fetch trades (threaded) for economics ----
    print("[3/5] Fetching taker trades ...", flush=True)
    def fill_tr(mk):
        tr=trades_for(mk["conditionId"])
        mk["_trades"]=tr; return mk
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs=[ex.submit(fill_tr,mk) for mk in rows]
        done=0
        for f in as_completed(futs):
            done+=1
            if done%400==0: print(f"    trades {done}/{len(rows)}", flush=True)

    # ---- per-market: half-spread, trade-weighted fills, entry mid interp ----
    print("[4/5] Deriving spread + fills + Deribit ...", flush=True)
    for mk in rows:
        st,en=mk["start"],mk["end"]; life=en-st
        h=price_history(mk["yes_token"], st, en)
        f=mid_interp(h)
        costs=[]; fills=[]
        for t in mk.get("_trades",[]):
            dirn,yp,sz,ts=norm_trade(t)
            if dirn==0 or sz<=0: continue
            if ts< st or ts> en: continue
            fills.append((dirn,yp,sz,ts))
            if f is not None and st<=ts<=en:
                mid=f(ts)
                # effective taker cost = signed distance paid beyond mid
                c=(yp-mid) if dirn>0 else (mid-yp)
                if -0.5<c<0.5: costs.append(c)
        mk["_fills"]=fills
        mk["half_spread"]= float(np.median([abs(c) for c in costs])) if len(costs)>=5 else None
        # deribit digital at entry (weekly terminal only; one-touch not vanilla)
        mk["deribit_p"]=None
        if mk["family"]=="weekly_terminal":
            entry_ts=int(st+0.30*life)  # mid of causal window
            mk["deribit_p"]=deribit_digital(mk["asset"], entry_ts, en, mk["strike"])

    # global half-spread estimate (fallback)
    hs_all=[mk["half_spread"] for mk in rows if mk["half_spread"] is not None]
    HS_GLOBAL=float(np.median(hs_all)) if hs_all else 0.01
    print(f"    global median half-spread est: {HS_GLOBAL:.4f}  (n={len(hs_all)})", flush=True)

    print("[5/5] Analysis ...", flush=True)
    report=[]
    def w(s=""):
        report.append(s); print(s, flush=True)

    # save row-level dump for auditability
    dump=[{k:mk[k] for k in ("asset","family","slug","strike","yes_win","entry",
            "entry_npts","horizon_days","volume","half_spread","deribit_p","end")}
          for mk in rows]
    with open("/home/user/Codex-playground-/scratchpad/pmkt_rows.json","w") as fp:
        json.dump(dump,fp)

    # ================= universe summary =================
    w("# Polymarket Longer-Horizon BTC/ETH Edge — Results\n")
    w(f"_Generated {dt.datetime.now(dt.timezone.utc).isoformat()} | runtime {time.time()-t0:.0f}s_\n")
    w("## Universe discovered\n")
    w("| family | asset | n markets | distinct weeks | median horizon (d) | total volume $ |")
    w("|---|---|---:|---:|---:|---:|")
    fam_order=["weekly_terminal","week_touch","monthly_touch"]
    for fam in fam_order:
        for asset in ("BTC","ETH"):
            sub=[m for m in rows if m["family"]==fam and m["asset"]==asset]
            if not sub: continue
            wks=len(set(week_key(m["end"]) for m in sub))
            hz=np.median([m["horizon_days"] for m in sub])
            vol=sum(m["volume"] for m in sub)
            w(f"| {fam} | {asset} | {len(sub)} | {wks} | {hz:.1f} | {vol:,.0f} |")
    w("")

    # ================= TEST 1: CALIBRATION / favorite-longshot =================
    def calibration(sub, label):
        w(f"### Calibration — {label}  (n={len(sub)}, weeks={len(set(week_key(m['end']) for m in sub))})\n")
        if len(sub)<30:
            w(f"_underpowered (n<30), reported for completeness_\n")
        bins=[(0.0,0.05),(0.05,0.15),(0.15,0.30),(0.30,0.45),(0.45,0.55),
              (0.55,0.70),(0.70,0.85),(0.85,0.95),(0.95,1.001)]
        w("| entry bin | n | wks | mean entry | realized YES | diff(real-entry) | clustered t | net½sprd diff |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|")
        for lo,hi in bins:
            b=[m for m in sub if lo<=m["entry"]<hi]
            if len(b)<8:
                if b:
                    w(f"| [{lo:.2f},{hi:.2f}) | {len(b)} | - | - | - | underpowered | - |")
                continue
            me=np.mean([m["entry"] for m in b])
            ry=np.mean([m["yes_win"] for m in b])
            diffs=[m["yes_win"]-m["entry"] for m in b]
            mean,t,N,G=cluster_t(diffs,[week_key(m["end"]) for m in b])
            # net half-spread: to CAPTURE this diff you must trade; subtract a half-spread of edge
            hs=np.median([m["half_spread"] for m in b if m["half_spread"] is not None] or [HS_GLOBAL])
            net=abs(mean)-hs
            nets=f"{net:+.3f}"
            w(f"| [{lo:.2f},{hi:.2f}) | {N} | {G} | {me:.3f} | {ry:.3f} | {mean:+.3f} | {t:+.2f} | {nets} |")
        # overall directional FLB test: is (yes_win-entry) correlated with entry?
        # slope of realized-entry vs (0.5-entry): >0 means longshots overpriced (FLB)
        e=np.array([m["entry"] for m in sub]); yw=np.array([m["yes_win"] for m in sub])
        resid=yw-e
        # FLB signal magnitude: mean resid for entry<0.5 minus mean resid for entry>0.5
        lo_m=resid[e<0.5]; hi_m=resid[e>=0.5]
        w("")
        if len(lo_m)>5 and len(hi_m)>5:
            w(f"- longshot side (entry<0.5): mean(real-entry) = {lo_m.mean():+.4f}  (n={len(lo_m)})")
            w(f"- favorite side (entry>=0.5): mean(real-entry) = {hi_m.mean():+.4f}  (n={len(hi_m)})")
        w("")

    w("## TEST 1 — Calibration / Favorite-Longshot (zero-fee AND net half-spread)\n")
    w(f"Entry = time-weighted YES mid over first 10-50% of market life (causal). "
      f"Cluster = resolution ISO-week. Half-spread subtracted = realized taker cost from fills.\n")
    for fam in fam_order:
        sub=[m for m in rows if m["family"]==fam]
        if len(sub)>=20:
            calibration(sub, fam)

    # ================= TEST 2: CROSS-MARKET vs DERIBIT =================
    w("## TEST 2 — Cross-market vs Deribit (weekly terminal BTC/ETH)\n")
    dsub=[m for m in rows if m["family"]=="weekly_terminal" and m.get("deribit_p") is not None
          and 0.02<=m["entry"]<=0.98]
    w(f"Deribit implied P(S_T>K) = N(d2) from perp spot + DVOL(30d) at entry time. n={len(dsub)}, "
      f"weeks={len(set(week_key(m['end']) for m in dsub))}\n")
    if len(dsub)>=30:
        gap=np.array([m["entry"]-m["deribit_p"] for m in dsub])
        yw=np.array([m["yes_win"] for m in dsub])
        dp=np.array([m["deribit_p"] for m in dsub])
        # 2a: does (pmkt - deribit) predict (outcome - deribit)? i.e. is pmkt's deviation informative or noise/mispricing
        # If pmkt mispriced vs smart market: trading TOWARD deribit profits =>
        #   signal = deribit - pmkt ; PnL(buy YES when deribit>pmkt) = yw - entry
        # Test corr of gap with realized (yw - deribit): if gap is pure mispricing, gap and (yw-deribit) uncorrelated,
        #   and (yw-entry) has sign of -gap.
        # Strategy: trade toward Deribit. per market pnl = -sign(gap)*(yw-entry) ... use signed:
        pnl_toward = -(np.sign(gap))*(yw-np.array([m["entry"] for m in dsub]))
        m1,t1,N1,G1=cluster_t(list(pnl_toward),[week_key(m["end"]) for m in dsub])
        # net of half-spread
        hs=np.median([m["half_spread"] for m in dsub if m["half_spread"] is not None] or [HS_GLOBAL])
        w("**2a. Trade Polymarket TOWARD Deribit fair value** (buy the side Deribit says is cheap):\n")
        w("| metric | value |")
        w("|---|---|")
        w(f"| mean |gap| = |pmkt-deribit| | {np.mean(np.abs(gap)):.4f} |")
        w(f"| mean PnL/market (mid, zero-fee) | {m1:+.4f} |")
        w(f"| clustered t | {t1:+.2f}  (N={N1}, weeks={G1}) |")
        w(f"| median half-spread cost | {hs:.4f} |")
        w(f"| net PnL after half-spread | {m1-hs:+.4f} |")
        w("")
        # 2b: calibration of Deribit vs Polymarket (who is better?)
        # Brier scores
        brier_pm=np.mean((np.array([m["entry"] for m in dsub])-yw)**2)
        brier_dv=np.mean((dp-yw)**2)
        w("**2b. Who predicts better? (Brier, lower=better)**\n")
        w("| predictor | Brier | mean pred | realized |")
        w("|---|---:|---:|---:|")
        w(f"| Polymarket entry mid | {brier_pm:.4f} | {np.mean([m['entry'] for m in dsub]):.3f} | {yw.mean():.3f} |")
        w(f"| Deribit digital | {brier_dv:.4f} | {dp.mean():.3f} | {yw.mean():.3f} |")
        w("")
        # OOS split by time
        order=sorted(range(len(dsub)), key=lambda i: dsub[i]["end"])
        half=len(order)//2
        for name,idx in [("in-sample (older half)",order[:half]),("OOS (newer half)",order[half:])]:
            g=gap[idx]; yv=yw[idx]; ev=np.array([dsub[i]["entry"] for i in idx])
            pn=-(np.sign(g))*(yv-ev)
            mm,tt,NN,GG=cluster_t(list(pn),[week_key(dsub[i]["end"]) for i in idx])
            w(f"- {name}: mean toward-Deribit PnL {mm:+.4f}, t={tt:+.2f} (weeks={GG})")
        w("")
    else:
        w("_underpowered / insufficient Deribit-matched markets_\n")

    # ================= TEST 3: MARKET- vs TRADE-WEIGHTED economics =================
    w("## TEST 3 — MARKET-weighted vs TRADE-weighted (the discipline that killed the wing edge)\n")
    w("The favorite-longshot 'edge' says extreme longshots are overpriced. A tradeable version FADES "
      "longshots: SELL YES (buy NO) on low-entry markets, BUY YES on high-entry markets. We compare a "
      "MARKET-weighted backtest (1 obs/market at entry mid) to a TRADE-weighted backtest (actual taker "
      "fills at executed prices, weighted by size) — plus an adverse-selection check.\n")

    def flb_signed(entry):
        # signal: fade toward the mean-reverting favorite-longshot direction
        # longshot (entry<0.5): expected realized < entry -> we SELL YES (dir -1)
        # favorite (entry>0.5): expected realized > entry -> we BUY YES (dir +1)
        if entry<0.45: return -1
        if entry>0.55: return +1
        return 0

    for fam in fam_order:
        sub=[m for m in rows if m["family"]==fam]
        if len(sub)<30: continue
        w(f"### {fam}\n")
        # --- market-weighted: per market, PnL of taking signal side at ENTRY MID ---
        mw=[]; mw_wk=[]
        for m in sub:
            s=flb_signed(m["entry"])
            if s==0: continue
            # buy YES at entry mid: pnl = yw-entry ; sell YES: pnl = entry-yw ; minus half spread
            hs=m["half_spread"] if m["half_spread"] is not None else HS_GLOBAL
            pnl = s*(m["yes_win"]-m["entry"]) - hs
            mw.append(pnl); mw_wk.append(week_key(m["end"]))
        m_mw,t_mw,N_mw,G_mw=cluster_t(mw,mw_wk)

        # --- trade-weighted: actual taker fills that took OUR signal side, at exec prices ---
        tw=[]; tw_wk=[]; tw_wt=[]
        # adverse selection: outcome rate weighted by trade volume vs by market
        vol_yes_num=0.0; vol_den=0.0
        for m in sub:
            s=flb_signed(m["entry"])
            if s==0: continue
            hs=m["half_spread"] if m["half_spread"] is not None else HS_GLOBAL
            for dirn,yp,sz,ts in m.get("_fills",[]):
                # a taker who took OUR side: dir matches s
                if dirn!=s: continue
                # our realized pnl per share if WE were this taker (already crossed spread in yp)
                pnl = s*(m["yes_win"]-yp)
                tw.append(pnl); tw_wk.append(week_key(m["end"])); tw_wt.append(sz)
                vol_yes_num+=sz*m["yes_win"]; vol_den+=sz
        # size-weighted mean pnl with clustered t (approx: weight residuals)
        if tw:
            wtarr=np.array(tw_wt); pnlarr=np.array(tw)
            m_tw=float(np.average(pnlarr, weights=wtarr))
            # clustered t on unweighted fills (conservative)
            _,t_tw,N_tw,G_tw=cluster_t(tw,tw_wk)
            m_tw_unw,_,_,_=cluster_t(tw,tw_wk)
        else:
            m_tw=float('nan'); t_tw=float('nan'); N_tw=0; G_tw=0; m_tw_unw=float('nan')

        w("| weighting | mean PnL/unit (net ½sprd) | clustered t | N | weeks |")
        w("|---|---:|---:|---:|---:|")
        w(f"| MARKET-weighted (entry mid) | {m_mw:+.4f} | {t_mw:+.2f} | {N_mw} | {G_mw} |")
        w(f"| TRADE-weighted, size-wtd (exec fills) | {m_tw:+.4f} | {t_tw:+.2f} | {N_tw} | {G_tw} |")
        w(f"| TRADE-weighted, unweighted fills | {m_tw_unw:+.4f} | {t_tw:+.2f} | {N_tw} | {G_tw} |")
        # adverse selection
        base_yes=np.mean([m["yes_win"] for m in sub if flb_signed(m["entry"])!=0])
        vw_yes=vol_yes_num/vol_den if vol_den>0 else float('nan')
        w("")
        w(f"- Adverse selection: signal-side outcome rate — MARKET-weighted YES={base_yes:.3f} "
          f"vs FILL-volume-weighted YES={vw_yes:.3f} "
          f"(fills cluster where the taker side WINS/LOSES more than the market average)")
        # divergence flag
        if not math.isnan(m_tw):
            div = m_mw - m_tw
            w(f"- MARKET minus TRADE weighted PnL = {div:+.4f}  "
              f"({'MARKET-weighted is the ARTIFACT (trade-weighted worse)' if div>0.005 else 'consistent' })")
        w("")

    # ================= write report =================
    with open("/home/user/Codex-playground-/pmkt_horizon_report.md","w") as fp:
        fp.write("\n".join(report)+"\n")
    print("\nWROTE /home/user/Codex-playground-/pmkt_horizon_report.md", flush=True)

if __name__=="__main__":
    main()
