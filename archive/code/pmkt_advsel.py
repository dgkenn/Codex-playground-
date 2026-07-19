#!/usr/bin/env python3
"""
pmkt_advsel.py — TIE-BREAKER: Polymarket short-vol longshot edge under REALISTIC (YES-BUY-volume-weighted) fills.

Decisive question
-----------------
On zero-fee Polymarket you SELL far-OTM weekly "BTC/ETH above $X on <date>" longshots (entry YES mid in
[0.15,0.30], ~7-day horizon). As a resting SELLER of the longshot YES you fill against TAKER BUY orders on
the YES token. So the fills you actually get are concentrated on markets with high YES-BUY taker volume.

  Analysis A (per-TRADE weighting): adverse selection is FAVORABLE  -> weighted YES-print rate LOWER, edge holds.
  Analysis B (per-MARKET-total-volume weighting): adverse selection is ADVERSE -> weighted print rate HIGHER, edge collapses.

This script weights each settled longshot market by its ACTUAL first-half YES-BUY taker volume (what a resting
seller truly fills) and asks:
  (a) Is the YES-BUY-volume-weighted realized YES-print rate LOWER (favorable/A) or HIGHER (adverse/B) than the
      unweighted per-market rate?
  (b) Does seller PnL/contract = (entry_mid - outcome) - half_spread stay positive when weighted by real YES-buy
      volume, week-clustered by resolution week?
  (c) Tail: worst resolution-week PnL, % negative weeks.

Causality: entry mid comes from the FIRST HALF of market life only (CLOB price-history). YES-BUY volume is
aggregated only over the first half (the seller's entry window). Outcome only from UMA resolution.

Data sources (public, no auth):
  gamma-api.polymarket.com/events        -> universe + resolution (outcomePrices) + clobTokenIds
  clob.polymarket.com/prices-history     -> causal entry mid (YES token, first half)
  data-api.polymarket.com/trades         -> taker fills (side, asset=token id, size, price, timestamp)
"""
import os, sys, json, time, math, datetime as dt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

CACHE = "/home/user/Codex-playground-/scratchpad/advsel_cache"
os.makedirs(CACHE, exist_ok=True)
GAMMA="https://gamma-api.polymarket.com"
CLOB="https://clob.polymarket.com"
DATA="https://data-api.polymarket.com"

ENTRY_LO, ENTRY_HI = 0.15, 0.30
HORIZON_LO, HORIZON_HI = 4.0, 10.0     # days: isolate 7-day weeklies, drop intraday/4h variants
FIRST_HALF = 0.50                      # seller entry window = [start, start+0.5*life]
ENTRY_WIN_LO, ENTRY_WIN_HI = 0.10, 0.50  # causal price-history window for entry mid

S = requests.Session()
S.headers.update({"User-Agent":"research/1.0"})

def _get(url, params=None, tries=4, timeout=40):
    for i in range(tries):
        try:
            r=S.get(url, params=params, timeout=timeout)
            if r.status_code==200: return r.json()
            if r.status_code in (429,500,502,503,504): time.sleep(1.2*(i+1)); continue
            return None
        except Exception:
            time.sleep(1.0*(i+1))
    return None

def cache_get(key, fn):
    p=os.path.join(CACHE, key+".json")
    if os.path.exists(p):
        try:
            with open(p) as f: return json.load(f)
        except Exception: pass
    v=fn()
    if v is None: return None
    tmp=p+".tmp"
    with open(tmp,"w") as f: json.dump(v,f)
    os.replace(tmp,p)
    return v

def iso(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc)
def parse_dt(s):
    if not s: return None
    try: return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception: return None
def week_key(end_ts):
    d=iso(end_ts); y,w,_=d.isocalendar(); return f"{y}-W{w:02d}"

# --------------------------------------------------------------------------
# 1. Universe: settled weekly "above on <date>" multi-strike (BTC series 45, ETH series 42)
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

def resolved_outcome(m):
    """yes_win in {0.0,1.0} or None. outcomePrices ~['1','0']=YES won, ['0','1']=NO won."""
    op=m.get("outcomePrices"); oc=m.get("outcomes")
    try:
        op=json.loads(op) if isinstance(op,str) else op
        oc=json.loads(oc) if isinstance(oc,str) else oc
    except Exception: return None
    if not op or not oc: return None
    d={oc[i].lower():float(op[i]) for i in range(min(len(oc),len(op)))}
    y=d.get("yes")
    if y is None: return None
    if y>0.98: return 1.0
    if y<0.02: return 0.0
    return None

def build_universe():
    out=[]
    for sid,asset in [(45,"BTC"),(42,"ETH")]:
        evs=enum_series(sid) or []
        for e in evs:
            if not e.get("closed"): continue
            slug=e.get("slug","")
            if "above" not in slug: continue
            start=parse_dt(e.get("startDate")); end=parse_dt(e.get("endDate"))
            if not start or not end: continue
            horizon=(end-start).total_seconds()/86400.0
            if not (HORIZON_LO<=horizon<=HORIZON_HI): continue   # 7-day weeklies only
            mks=e.get("markets",[])
            if len(mks)<3: continue
            for m in mks:
                q=(m.get("question") or "").lower()
                if "above" not in q: continue
                yw=resolved_outcome(m)
                if yw is None: continue
                try: toks=json.loads(m["clobTokenIds"])
                except Exception: continue
                if not toks or len(toks)<2: continue
                out.append(dict(
                    asset=asset, slug=slug, question=m.get("question"),
                    conditionId=m.get("conditionId"),
                    yes_token=str(toks[0]), no_token=str(toks[1]),
                    yes_win=yw, start=start.timestamp(), end=end.timestamp(),
                    horizon_days=horizon, volume=float(m.get("volumeNum") or 0)))
    return out

# --------------------------------------------------------------------------
# 2. Causal entry mid: time-weighted YES price over first-half window
# --------------------------------------------------------------------------
def price_history(token, start, end):
    key="ph_"+str(token)+"_"+str(int(start))+"_"+str(int(end))
    def fn():
        d=_get(f"{CLOB}/prices-history", dict(market=token, startTs=int(start), endTs=int(end), fidelity=60))
        return (d or {}).get("history",[])
    return cache_get(key, fn)

def causal_entry(mk):
    st,en=mk["start"],mk["end"]; life=en-st
    lo=st+ENTRY_WIN_LO*life; hi=st+ENTRY_WIN_HI*life
    h=price_history(mk["yes_token"], st, en)
    if not h: return None,0
    pts=[(p["t"],p["p"]) for p in h if lo<=p["t"]<=hi]
    if len(pts)<2:
        allp=[(p["t"],p["p"]) for p in h if st<=p["t"]<=hi]
        if not allp: return None,0
        allp.sort(); return float(allp[-1][1]), len(allp)
    pts.sort()
    tot=0.0; wsum=0.0
    for i in range(len(pts)-1):
        dtw=pts[i+1][0]-pts[i][0]
        tot+=pts[i][1]*dtw; wsum+=dtw
    val=tot/wsum if wsum>0 else float(np.mean([p for _,p in pts]))
    return float(val), len(pts)

def mid_interp(h):
    if not h: return None
    ts=np.array([p["t"] for p in h],float); ps=np.array([p["p"] for p in h],float)
    o=np.argsort(ts); ts=ts[o]; ps=ps[o]
    return lambda t: float(np.interp(t, ts, ps))

# --------------------------------------------------------------------------
# 3. Trades: aggregate FIRST-HALF YES-BUY taker volume + estimate half-spread
# --------------------------------------------------------------------------
def trades_for(conditionId, max_pages=12, page=500):
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

def analyze_fills(mk):
    """First-half YES-BUY taker volume (shares & $), plus half-spread estimate from all trades vs mid."""
    st,en=mk["start"],mk["end"]; life=en-st
    half_ts=st+FIRST_HALF*life
    yt=mk["yes_token"]; nt=mk["no_token"]
    h=price_history(yt, st, en); f=mid_interp(h)
    trades=trades_for(mk["conditionId"]) or []
    yes_buy_shares=0.0; yes_buy_dollars=0.0
    n_yes_buy=0
    costs=[]
    for t in trades:
        side=(t.get("side") or "").upper()
        asset=str(t.get("asset") or "")
        price=float(t.get("price") or 0); size=float(t.get("size") or 0); ts=int(t.get("timestamp") or 0)
        if size<=0 or ts<st or ts>en: continue
        # YES-BUY taker fill = what a resting YES seller fills into
        if asset==yt and side=="BUY":
            # half-spread proxy: |fill price - mid| (taker paid above mid)
            if f is not None:
                c=abs(price - f(ts))
                if 0<=c<0.5: costs.append(c)
            if ts<=half_ts:
                yes_buy_shares+=size
                yes_buy_dollars+=size*price
                n_yes_buy+=1
        elif asset==nt and side=="SELL":
            # sell NO = also lifts a resting YES seller? No: sell-No hits a resting No-bid.
            # We keep the strict definition (taker BUY on YES token). Just gather half-spread signal.
            if f is not None:
                c=abs((1-price) - f(ts))
                if 0<=c<0.5: costs.append(c)
    mk["yes_buy_shares"]=yes_buy_shares
    mk["yes_buy_dollars"]=yes_buy_dollars
    mk["n_yes_buy"]=n_yes_buy
    mk["half_spread"]= float(np.median(costs)) if len(costs)>=5 else None
    return mk

# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------
def weekly_series(rows, valfn, weightfn=None):
    """Return dict week-> (weighted or equal) mean of valfn over rows in that week."""
    wk=defaultdict(list); wt=defaultdict(list)
    for m in rows:
        k=week_key(m["end"]); wk[k].append(valfn(m))
        wt[k].append(1.0 if weightfn is None else max(0.0,weightfn(m)))
    out={}
    for k in wk:
        v=np.array(wk[k],float); w=np.array(wt[k],float)
        if w.sum()<=0:  # no volume in that week under weighting -> skip
            continue
        out[k]=float(np.average(v, weights=w))
    return out

def week_t(weekmeans):
    vals=np.array(list(weekmeans.values()),float)
    K=len(vals)
    if K<2: return (float(vals.mean()) if K else float('nan'), float('nan'), K)
    m=vals.mean(); sd=vals.std(ddof=1)
    se=sd/math.sqrt(K) if K>0 else float('nan')
    t=m/se if se>0 else float('nan')
    return (float(m), float(t), K)

def flat_t(vals):
    v=np.array(vals,float); N=len(v)
    if N<2: return (float(v.mean()) if N else float('nan'), float('nan'), N)
    m=v.mean(); se=v.std(ddof=1)/math.sqrt(N)
    return (float(m), float(m/se) if se>0 else float('nan'), N)

# ==========================================================================
def main():
    t0=time.time()
    print("[1/4] Enumerating settled weekly 'above on' universe (BTC s45, ETH s42) ...", flush=True)
    uni=build_universe()
    print(f"    resolved 7d weekly markets: {len(uni)}", flush=True)

    print("[2/4] Causal entry mid (CLOB first-half price-history) ...", flush=True)
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs=[ex.submit(lambda mk: (mk.__setitem__('entry', causal_entry(mk)[0]) or mk), mk) for mk in uni]
        for i,f in enumerate(as_completed(futs)):
            if (i+1)%500==0: print(f"    entry {i+1}/{len(uni)}", flush=True)
    band=[m for m in uni if m.get("entry") is not None and ENTRY_LO<=m["entry"]<=ENTRY_HI]
    print(f"    longshot band [{ENTRY_LO},{ENTRY_HI}] markets: {len(band)}", flush=True)

    print("[3/4] Fetching trades, aggregating FIRST-HALF YES-BUY taker volume ...", flush=True)
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs=[ex.submit(analyze_fills, mk) for mk in band]
        for i,f in enumerate(as_completed(futs)):
            if (i+1)%200==0: print(f"    fills {i+1}/{len(band)}", flush=True)

    # rows that actually have YES-buy fills (a real seller could fill something)
    filled=[m for m in band if m["yes_buy_shares"]>0]
    hs_all=[m["half_spread"] for m in band if m["half_spread"] is not None]
    HS_GLOBAL=float(np.median(hs_all)) if hs_all else 0.01
    for m in band:
        if m["half_spread"] is None: m["half_spread"]=HS_GLOBAL

    print(f"    band markets with >0 first-half YES-buy volume: {len(filled)}", flush=True)
    print(f"    global median half-spread: {HS_GLOBAL:.4f} (n={len(hs_all)})", flush=True)

    print("[4/4] Computing tie-breaker + PnL weightings ...", flush=True)

    # ---------- (a) PRINT-RATE tie-breaker ----------
    yw=np.array([m["yes_win"] for m in filled],float)
    vshare=np.array([m["yes_buy_shares"] for m in filled],float)
    vdol=np.array([m["yes_buy_dollars"] for m in filled],float)
    unw_rate=float(yw.mean())
    w_rate_share=float(np.average(yw, weights=vshare))
    w_rate_dol=float(np.average(yw, weights=vdol))

    # ---------- (b) seller PnL/contract ----------
    def pnl(m): return (m["entry"] - m["yes_win"]) - m["half_spread"]
    for m in filled: m["pnl"]=pnl(m)

    # equal-weight, week-clustered
    wm_eq=weekly_series(filled, pnl, None)
    m_eq,t_eq,K_eq=week_t(wm_eq)
    # YES-buy-volume weighted (shares), week-clustered
    wm_vw=weekly_series(filled, pnl, lambda m:m["yes_buy_shares"])
    m_vw,t_vw,K_vw=week_t(wm_vw)
    # YES-buy $ weighted, week-clustered (secondary)
    wm_vwd=weekly_series(filled, pnl, lambda m:m["yes_buy_dollars"])
    m_vwd,t_vwd,K_vwd=week_t(wm_vwd)
    # flat pooled mean (iid SE)
    m_flat,t_flat,N_flat=flat_t([m["pnl"] for m in filled])

    # ---------- (c) tail ----------
    weekvals_eq=sorted(wm_eq.items(), key=lambda kv:kv[1])
    weekvals_vw=sorted(wm_vw.items(), key=lambda kv:kv[1])
    worst_eq=weekvals_eq[0] if weekvals_eq else ("-",float('nan'))
    worst_vw=weekvals_vw[0] if weekvals_vw else ("-",float('nan'))
    negw_eq=100.0*sum(1 for _,v in wm_eq.items() if v<0)/max(1,len(wm_eq))
    negw_vw=100.0*sum(1 for _,v in wm_vw.items() if v<0)/max(1,len(wm_vw))

    weeks=sorted(set(week_key(m["end"]) for m in filled))
    mean_entry=float(np.mean([m["entry"] for m in filled]))

    R=[]
    def w(s=""): R.append(s); print(s, flush=True)

    w("# Polymarket short-vol longshot — ADVERSE-SELECTION tie-breaker\n")
    w(f"_Generated {dt.datetime.now(dt.timezone.utc).isoformat()} | runtime {time.time()-t0:.0f}s_\n")
    w("## Sample")
    w(f"- Resolved 7d weekly 'above on' markets enumerated: **{len(uni)}**")
    w(f"- In longshot entry band YES mid [{ENTRY_LO},{ENTRY_HI}] (causal first-half mid): **{len(band)}**")
    w(f"- With >0 first-half YES-BUY taker volume (a resting seller could fill): **{len(filled)}**")
    w(f"- Distinct resolution weeks: **{len(weeks)}**")
    w(f"- Mean causal entry mid in band: **{mean_entry:.4f}**")
    w(f"- Global median half-spread (subtracted from PnL): **{HS_GLOBAL:.4f}**")
    tot_share=float(vshare.sum()); tot_dol=float(vdol.sum())
    w(f"- Total first-half YES-BUY volume: **{tot_share:,.0f} shares / ${tot_dol:,.0f}**\n")

    w("## (a) TIE-BREAKER — YES-print rate: unweighted vs YES-BUY-volume-weighted\n")
    w("| weighting | realized YES-print rate |")
    w("|---|---:|")
    w(f"| UNWEIGHTED (per-market) | {unw_rate:.4f} |")
    w(f"| YES-BUY-volume weighted (shares) | {w_rate_share:.4f} |")
    w(f"| YES-BUY-volume weighted ($) | {w_rate_dol:.4f} |")
    delta_share=w_rate_share-unw_rate; delta_dol=w_rate_dol-unw_rate
    w("")
    w(f"- Share-weighted minus unweighted = **{delta_share:+.4f}**")
    w(f"- $-weighted minus unweighted = **{delta_dol:+.4f}**")
    verdict_advsel = "ADVERSE (weighted print rate HIGHER → Analysis B)" if delta_share>0 else "FAVORABLE (weighted print rate LOWER → Analysis A)"
    w(f"- **Adverse-selection direction: {verdict_advsel}**\n")

    w("## (b) Seller PnL/contract = (entry_mid − outcome) − half_spread\n")
    w("| weighting | mean PnL/contract | week-clustered t | k weeks / n |")
    w("|---|---:|---:|---:|")
    w(f"| per-market EQUAL, week-clustered | {m_eq:+.4f} | {t_eq:.2f} | {K_eq} |")
    w(f"| YES-BUY-VOLUME weighted (shares), week-clustered | {m_vw:+.4f} | {t_vw:.2f} | {K_vw} |")
    w(f"| YES-BUY-VOLUME weighted ($), week-clustered | {m_vwd:+.4f} | {t_vwd:.2f} | {K_vwd} |")
    w(f"| FLAT pooled mean (iid SE) | {m_flat:+.4f} | {t_flat:.2f} | n={N_flat} |")
    w("")

    w("## (c) Tail\n")
    w(f"- Worst resolution-week PnL (equal-weight): **{worst_eq[1]:+.4f}** ({worst_eq[0]})")
    w(f"- Worst resolution-week PnL (YES-buy-vol weight): **{worst_vw[1]:+.4f}** ({worst_vw[0]})")
    w(f"- % negative weeks (equal-weight): **{negw_eq:.1f}%** of {len(wm_eq)}")
    w(f"- % negative weeks (YES-buy-vol weight): **{negw_vw:.1f}%** of {len(wm_vw)}\n")

    # ---------- VERDICT ----------
    w("## VERDICT\n")
    edge_survives = (m_vw>0) and (t_vw>=2.0)
    edge_marginal = (m_vw>0) and (1.0<=t_vw<2.0)
    if delta_share<=0 and edge_survives:
        v=("**REAL & cost-surviving at realistic fills.** YES-BUY-volume weighting LOWERS the print rate "
           "(favorable adverse selection) and the seller PnL stays positive with week-clustered t≥2 net of "
           "half-spread. The data supports **ANALYSIS A** (favorable/real).")
    elif delta_share>0 and not edge_survives:
        v=("**ADVERSE-SELECTION ARTIFACT.** YES-BUY-volume weighting RAISES the realized print rate — the seller "
           "disproportionately fills exactly the longshots that DO print — and the PnL collapses to "
           f"{'marginal' if edge_marginal else 'non-'}significant (week-clustered t={t_vw:.2f}) net of half-spread. "
           "The data supports **ANALYSIS B** (adverse/marginal), like the earlier wing edge.")
    else:
        v=(f"**MIXED.** Print-rate delta {delta_share:+.4f} and volume-weighted week-clustered t={t_vw:.2f} "
           f"(mean {m_vw:+.4f}). ")
        if delta_share>0:
            v+="Weighting raises the print rate (adverse direction), leaning **Analysis B**, "
        else:
            v+="Weighting lowers the print rate (favorable direction), leaning **Analysis A**, "
        v+="but the significance verdict is not clean — read the numbers above."
    w(v)

    with open("/home/user/Codex-playground-/pmkt_advsel_report.md","w") as fp:
        fp.write("\n".join(R)+"\n")

    # audit dump
    dump=[{k:m[k] for k in ("asset","slug","question","conditionId","entry","yes_win",
            "half_spread","yes_buy_shares","yes_buy_dollars","n_yes_buy","horizon_days","volume","end")}
          for m in filled]
    with open("/home/user/Codex-playground-/scratchpad/advsel_rows.json","w") as fp:
        json.dump(dump,fp)

    print(f"\nDONE in {time.time()-t0:.0f}s. Report -> pmkt_advsel_report.md")
    # machine-readable one-liner for the caller
    print(json.dumps(dict(n_band=len(band), n_filled=len(filled), weeks=len(weeks),
        unw_print=unw_rate, w_print_share=w_rate_share, w_print_dol=w_rate_dol,
        pnl_equal=m_eq, t_equal=t_eq, pnl_volw=m_vw, t_volw=t_vw, pnl_flat=m_flat, t_flat=t_flat,
        worst_week_eq=worst_eq[1], worst_week_vw=worst_vw[1], negw_eq=negw_eq, negw_vw=negw_vw,
        half_spread=HS_GLOBAL)))

if __name__=="__main__":
    main()
