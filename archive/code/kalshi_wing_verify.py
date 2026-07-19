#!/usr/bin/env python3
"""
Independent from-scratch verification of the Kalshi hourly BTC ladder (KXBTCD)
deep-OTM WING overpricing / variance-risk-premium claim.

Written WITHOUT reading kalshi_wing_vrp.py. All logic is my own.

Claim under test:
  Selling YES on deep-OTM wing strikes is +1.3-1.6c/contract net of fees at
  VWAP entry, but collapses to ~0 once a 1c half-spread is charged.

I test:
  (1) Does overpricing replicate across THREE independent entry-price defs?
  (2) THE executable-sell-price question: split by taker_side, estimate the
      real bid you could sell into, recompute PnL. Does anything survive?
  (3) Selection: are traded wings more overpriced than base rate; does edge
      correlate with tradeable size?
  (4) Day-cluster everything (cluster by close date).
"""
import json, os, sys, time, math, statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/wing_cache"
os.makedirs(CACHE, exist_ok=True)

TARGET_EVENTS = 1400         # ~58 days of hourly events -> >=40 distinct close dates
WING_MAX = 0.15              # wing = early YES price in (0, 0.15]
MIN_EARLY_TRADES = 2         # >=2 early trades filter (as in claim)
BINS = [(0.00,0.02),(0.02,0.04),(0.04,0.06),(0.06,0.10),(0.10,0.15)]

S = requests.Session()
S.headers.update({"Accept":"application/json"})

def get(path, params=None, tries=5):
    for i in range(tries):
        try:
            r = S.get(BASE+path, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429,500,502,503,504):
                time.sleep(1.0*(i+1)); continue
            r.raise_for_status()
        except requests.RequestException:
            time.sleep(1.0*(i+1))
    return None

# ---------- 1. events ----------
def pull_events():
    cf = os.path.join(CACHE,"events.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out=[]; cursor=None
    while len(out) < TARGET_EVENTS:
        p={"series_ticker":"KXBTCD","status":"settled","limit":200}
        if cursor: p["cursor"]=cursor
        j=get("/events",p)
        if not j: break
        evs=j.get("events",[])
        out.extend(evs)
        cursor=j.get("cursor")
        if not cursor or not evs: break
    json.dump(out,open(cf,"w"))
    return out

# ---------- 2. markets ----------
def pull_markets(et):
    cf=os.path.join(CACHE,f"mk_{et}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out=[]; cursor=None
    while True:
        p={"event_ticker":et,"limit":400}
        if cursor:p["cursor"]=cursor
        j=get("/markets",p)
        if not j:break
        mk=j.get("markets",[])
        out.extend(mk)
        cursor=j.get("cursor")
        if not cursor or not mk:break
    json.dump(out,open(cf,"w"))
    return out

# ---------- 3. trades (FIRST-HALF window only; unbiased & cheap for wings) ----------
def pull_trades_window(ticker, min_ts, max_ts, maxpages=3):
    cf=os.path.join(CACHE,f"trw_{ticker}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out=[]; cursor=None; pages=0
    while pages<maxpages:
        p={"ticker":ticker,"limit":1000,"min_ts":int(min_ts),"max_ts":int(max_ts)}
        if cursor:p["cursor"]=cursor
        j=get("/markets/trades",p)
        if not j:break
        tr=j.get("trades",[])
        out.extend(tr)
        cursor=j.get("cursor")
        pages+=1
        if not cursor or not tr or len(tr)<1000:break
    json.dump(out,open(cf,"w"))
    return out

def parse_ts(s):
    # ISO8601 -> epoch seconds
    if s is None: return None
    s=s.replace("Z","+00:00")
    try:
        import datetime as dt
        return dt.datetime.fromisoformat(s).timestamp()
    except Exception:
        return None

def price_dollars(t, side="yes"):
    # prefer *_dollars fields; fall back to integer cents
    k=f"{side}_price_dollars"
    if k in t and t[k] is not None:
        try: return float(t[k])
        except: pass
    k2=f"{side}_price"
    if k2 in t and t[k2] is not None:
        try: return float(t[k2])/100.0
        except: pass
    return None

def count_of(t):
    for k in ("count_fp","count"):
        if k in t and t[k] is not None:
            try: return float(t[k])
            except: pass
    return 1.0

def kalshi_fee(price, contracts=1):
    # Kalshi trading fee: ceil(0.07 * C * P * (1-P)) in cents; taker only.
    raw = 0.07*contracts*price*(1.0-price)
    cents = math.ceil(raw*100.0)/100.0
    return cents  # dollars

def main():
    events=pull_events()
    print(f"pulled {len(events)} settled events", file=sys.stderr)

    # collect (event, market) pairs; fetch markets
    ev_tickers=[e["event_ticker"] for e in events]
    markets_by_ev={}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs={ex.submit(pull_markets,et):et for et in ev_tickers}
        for f in as_completed(futs):
            et=futs[f]
            try: markets_by_ev[et]=f.result()
            except Exception: markets_by_ev[et]=[]

    # Build candidate market list. We need trades to know entry price.
    # To limit fetches, fetch trades for ALL markets that have any volume.
    cand=[]
    for et,mks in markets_by_ev.items():
        for m in mks:
            res=m.get("result")
            if res not in ("yes","no"): continue
            vol = m.get("volume") or m.get("volume_fp") or 0
            try: vol=float(vol)
            except: vol=0
            if vol<=0: continue
            cand.append(m)
    print(f"{len(cand)} settled markets with volume>0", file=sys.stderr)

    # fetch FIRST-HALF trades (window = [open, open+life/2]) for each candidate
    def job(m):
        ot=parse_ts(m.get("open_time")); ct=parse_ts(m.get("close_time"))
        if ot is None or ct is None or ct<=ot: return (m["ticker"],[])
        half=ot+(ct-ot)*0.5
        return (m["ticker"], pull_trades_window(m["ticker"], ot, half))
    trades_by_tk={}
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs={ex.submit(job,m):m for m in cand}
        done=0
        for f in as_completed(futs):
            try:
                tk,tr=f.result(); trades_by_tk[tk]=tr
            except Exception: pass
            done+=1
            if done%1000==0: print(f"  trades {done}/{len(cand)}",file=sys.stderr)

    # ---- build per-market records with 3 entry defs ----
    recs=[]
    for m in cand:
        tk=m["ticker"]; et=m["event_ticker"]
        ot=parse_ts(m.get("open_time")); ct=parse_ts(m.get("close_time"))
        if ot is None or ct is None or ct<=ot: continue
        life=ct-ot
        res=1.0 if m.get("result")=="yes" else 0.0
        trs=trades_by_tk.get(tk,[])
        # normalize trades: (ts, yes_price, taker_side, count)
        T=[]
        for t in trs:
            ts=parse_ts(t.get("created_time"))
            yp=price_dollars(t,"yes")
            if ts is None or yp is None: continue
            if ts<ot-2 or ts>ct+2: continue
            T.append((ts,yp,t.get("taker_side"),count_of(t)))
        if len(T)<MIN_EARLY_TRADES: continue
        T.sort(key=lambda x:x[0])
        # first-half trades
        halfmark=ot+life*0.5
        first=[x for x in T if x[0]<=halfmark]
        if len(first)<MIN_EARLY_TRADES: continue
        # (a) count-weighted VWAP over first half
        wsum=sum(x[1]*x[3] for x in first); csum=sum(x[3] for x in first)
        vwap = wsum/csum if csum>0 else None
        # (b) single trade nearest 1/3-life mark
        thirdmark=ot+life/3.0
        near=min(T,key=lambda x:abs(x[0]-thirdmark))
        near_p=near[1]
        # (c) median early-trade price (first half, count-unweighted)
        med=statistics.median([x[1] for x in first])
        # taker side split among first-half trades
        buy_cnt=sum(x[3] for x in first if x[2]=="yes")   # aggressive YES buyers (lift ask)
        sell_cnt=sum(x[3] for x in first if x[2]=="no")   # aggressive NO buyers = YES sellers (hit bid)
        buy_px=[x[1] for x in first if x[2]=="yes"]
        sell_px=[x[1] for x in first if x[2]=="no"]
        vol = m.get("volume") or m.get("volume_fp") or 0
        try: vol=float(vol)
        except: vol=0
        close_date=(m.get("close_time") or "")[:10]
        recs.append(dict(ticker=tk,event=et,close_date=close_date,result=res,
                         vwap=vwap,near=near_p,med=med,
                         n_first=len(first),n_all=len(T),
                         buy_cnt=buy_cnt,sell_cnt=sell_cnt,
                         buy_px=buy_px,sell_px=sell_px,volume=vol,
                         first_buy_px=[x[1] for x in first if x[2]=="yes"],
                         first_sell_px=[x[1] for x in first if x[2]=="no"]))
    print(f"{len(recs)} markets with >=2 first-half trades", file=sys.stderr)
    json.dump(recs, open(os.path.join(CACHE,"recs.json"),"w"))
    return recs

def cluster_t(pairs):
    """pairs: list of (value, cluster_key) -> (mean, day-clustered t, N, G)."""
    from collections import defaultdict
    vals=[p[0] for p in pairs]; N=len(vals)
    if N<2: return (float('nan'),float('nan'),N,0)
    mean=sum(vals)/N; cs=defaultdict(float)
    for v,g in pairs: cs[g]+=(v-mean)
    G=len(cs)
    if G<2: return (mean,float('nan'),N,G)
    meat=sum(s*s for s in cs.values())
    var=(G/(G-1.0))*meat/(N*N)   # K=1 -> (N-1)/(N-K)=1
    se=math.sqrt(var) if var>0 else float('nan')
    return (mean, mean/se if se and se>0 else float('nan'), N, G)

def analyze(recs, fee=kalshi_fee):
    """Full adversarial analysis. See kalshi_wing_verify_report.md for interpretation."""
    print("="*90)
    print(f"TOTAL first-half-traded settled markets: {len(recs)}")
    ad=sorted(set(r['close_date'] for r in recs))
    print(f"distinct close-dates: {len(ad)} ({ad[0]}..{ad[-1]})")

    print("\n(1) CALIBRATION under 3 entry defs  (edge_buy=realized-entry; sellNet=(entry-result)-fee)")
    for d in ["vwap","near","med"]:
        print(f"\n-- entry def: {d} --")
        print(f"{'bin':>10}{'N':>6}{'dates':>6}{'entry':>8}{'realiz':>8}{'edgeBuy':>8}{'sellNet¢':>9}{'tClust':>8}")
        for lo,hi in BINS+[(0.0,WING_MAX)]:
            sub=[r for r in recs if r[d] is not None and lo<r[d]<=hi] if (lo,hi)!=(0.0,WING_MAX) else [r for r in recs if r[d] is not None and 0<r[d]<=WING_MAX]
            if not sub: print(f"{lo:.2f}-{hi:.2f}     0"); continue
            e=statistics.mean(r[d] for r in sub); rz=statistics.mean(r['result'] for r in sub)
            m,t,N,G=cluster_t([((r[d]-r['result'])-fee(r[d]),r['close_date']) for r in sub])
            lab=f"{lo:.2f}-{hi:.2f}" if (lo,hi)!=(0.0,WING_MAX) else "ALL<=.15"
            print(f"{lab:>10}{N:>6}{G:>6}{e:>8.3f}{rz:>8.3f}{rz-e:>8.3f}{m*100:>9.2f}{t:>8.2f}")

    wings=[r for r in recs if r['vwap'] is not None and 0<r['vwap']<=WING_MAX]
    tb=sum(r['buy_cnt'] for r in wings); ts=sum(r['sell_cnt'] for r in wings)
    print("\n(2) EXECUTABLE SELL PRICE")
    print(f"  fraction of early wing volume = aggressive BUYERS: {tb/(tb+ts):.3f}")
    nw=sum(1 for r in wings if r['sell_cnt']>0)
    print(f"  wings with a real taker-SELL (observed bid): {nw}/{len(wings)} = {nw/len(wings):.3f}")
    hs={}
    for lo,hi in BINS:
        h=[(statistics.mean(r['first_buy_px'])-statistics.mean(r['first_sell_px']))/2
           for r in wings if lo<r['vwap']<=hi and r['first_buy_px'] and r['first_sell_px']]
        if h: hs[(lo,hi)]=statistics.median(h)
    print("  within-mkt half-spread by bin (¢):", {f"{lo:.2f}-{hi:.2f}":round(v*100,2) for (lo,hi),v in hs.items()})
    print(f"\n  SELLER net ¢: A=sell@VWAP  B=sell@real-bid  C=VWAP-halfspread  D=VWAP-1c")
    print(f"{'bin':>10}{'N':>6}{'A':>7}{'tA':>6}{'B':>7}{'tB':>6}{'nB':>6}{'C':>7}{'tC':>6}{'D':>7}{'tD':>6}")
    for lo,hi in BINS+[(0.0,WING_MAX)]:
        sub=[r for r in wings if lo<r['vwap']<=hi] if (lo,hi)!=(0.0,WING_MAX) else wings
        if not sub: continue
        h=hs.get((lo,hi), statistics.median(list(hs.values())) if hs else .005)
        A=cluster_t([((r['vwap']-r['result'])-fee(r['vwap']),r['close_date']) for r in sub])
        B=cluster_t([((statistics.mean(r['first_sell_px'])-r['result'])-fee(max(statistics.mean(r['first_sell_px']),.001)),r['close_date']) for r in sub if r['first_sell_px']])
        C=cluster_t([((r['vwap']-h-r['result'])-fee(max(r['vwap']-h,.001)),r['close_date']) for r in sub])
        D=cluster_t([((r['vwap']-.01-r['result'])-fee(max(r['vwap']-.01,.001)),r['close_date']) for r in sub])
        lab=f"{lo:.2f}-{hi:.2f}" if (lo,hi)!=(0.0,WING_MAX) else "ALL<=.15"
        print(f"{lab:>10}{A[2]:>6}{A[0]*100:>7.2f}{A[1]:>6.2f}{B[0]*100:>7.2f}{B[1]:>6.2f}{B[2]:>6}{C[0]*100:>7.2f}{C[1]:>6.2f}{D[0]*100:>7.2f}{D[1]:>6.2f}")

    print("\n(3) SELECTION: wing volume distribution & edge-vs-size")
    vols=sorted(r['volume'] for r in wings)
    q=lambda p:vols[min(len(vols)-1,int(p/100*len(vols)))]
    print(f"  volume_fp pctiles p10={q(10):.0f} p50={q(50):.0f} p90={q(90):.0f} max={vols[-1]:.0f}")
    ws=sorted(wings,key=lambda r:r['volume']); n=len(ws)
    for nm,g in [("low",ws[:n//3]),("mid",ws[n//3:2*n//3]),("high",ws[2*n//3:])]:
        A=cluster_t([((r['vwap']-r['result'])-fee(r['vwap']),r['close_date']) for r in g])
        B=cluster_t([((statistics.mean(r['first_sell_px'])-r['result'])-fee(max(statistics.mean(r['first_sell_px']),.001)),r['close_date']) for r in g if r['first_sell_px']])
        print(f"  {nm:>4} vol[{g[0]['volume']:.0f}-{g[-1]['volume']:.0f}] sellVWAP={A[0]*100:.2f}c t={A[1]:.2f} | sellRealBid={B[0]*100:.2f}c t={B[1]:.2f}")

if __name__=="__main__":
    recs=main()
    analyze(recs)
