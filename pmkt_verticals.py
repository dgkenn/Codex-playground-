#!/usr/bin/env python3
"""
pmkt_verticals.py — WIDEN the multi-strategy book. We have TWO confirmed, uncorrelated longshot /
short-vol risk-premium sleeves on zero-fee Polymarket: CRYPTO (sell far-OTM weekly BTC/ETH longshots)
and ECON (sell far-from-consensus macro-release buckets), weekly-PnL corr ~ -0.01.

GOAL: find MORE INDEPENDENT domains where the SAME longshot premium exists AND whose weekly PnL is
UNCORRELATED with BOTH crypto and econ. Each such domain is a new stackable sleeve.

Verticals tested (gamma tag_ids discovered live):
  GEO       geopolitics/world (wars, ceasefires, foreign elections, sanctions)
  BUSINESS  companies (earnings beats, IPOs, M&A, exec moves)  [company-specific tags, NOT macro-Economy]
  TECHAI    tech/AI (model releases, product launches, milestones)
  WEATHER   weather/climate
  ENT       entertainment/culture/mentions (awards, box office, celebrity, tweet/"will X say Y")
  SPORTS_*  a few league sub-splits (NFL/NBA/SOCCER) — sports-aggregate already a one-week null

PROVEN methodology (identical anti-artifact discipline to the confirmed crypto/econ studies):
  * CAUSAL entry: time-weighted YES mid over the FIRST HALF of market life from CLOB price-history. No
    look-ahead. Outcome ONLY from resolution (outcomePrices), yes_win in {0,1}.
  * EXECUTABLE BID entry = entry_mid - half_spread (half_spread = median |YES-BUY taker fill - mid|,
    fallback vertical-median). Longshot SELL band = the BID in [0.10,0.35] AND full spread
    (2*half_spread) <= 0.06 (a near-zero bid is not the edge).
  * PnL/contract = entry_bid - yes_outcome, zero fee.
  * YES-BUY taker volume (first half) = the correct fill object for a resting YES seller. Total $-vol
    kept only for the naive/contrast weighting.
  * Cluster by RESOLUTION WEEK. Report equal / YES-BUY-vol / $-vol week-clustered means & t.
  * Adverse selection: YES-print-rate unweighted vs YES-BUY-vol-weighted (favorable if <=).
  * Tail: worst week, % neg weeks. Jackknife (leave-one-week-out) + one-week-driven (drop best week).
  * Calibration: realized YES vs entry by bin.
  * STACKABILITY (the key deliverable): weekly equal-weighted PnL series per vertical -> correlation to
    CRYPTO (advsel_rows.json) and ECON (cat_results ECON.weekly_eq), + full matrix.
  * Power flags: <20 weeks or <300 band markets = UNDERPOWERED.

A vertical is a NEW STACKABLE SLEEVE iff:
  (a) YES-BUY-vol t>=2 AND jackknife-stable AND not one-week-driven AND adverse-sel favorable/neutral
  (b) |corr| to BOTH crypto AND econ < ~0.30
"""
import os, sys, json, time, math, datetime as dt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

# Reuse the confirmed studies' price-history/trades cache (keyed by token/conditionId) for hits.
CACHE = "/home/user/Codex-playground-/scratchpad/cat_cache"
os.makedirs(CACHE, exist_ok=True)
GAMMA="https://gamma-api.polymarket.com"
CLOB="https://clob.polymarket.com"
DATA="https://data-api.polymarket.com"

# --- frozen parameters (same as confirmed studies) ---
ENTRY_LO, ENTRY_HI = 0.10, 0.35        # longshot SELL band, applied to the EXECUTABLE BID
MAX_FULL_SPREAD    = 0.06              # full bid-ask spread cap (= 2*half_spread)
MID_PREFILTER_LO, MID_PREFILTER_HI = 0.06, 0.46   # cut trade fetches before we know the bid
HORIZON_LO, HORIZON_HI = 2.0, 30.0
FIRST_HALF = 0.50
ENTRY_WIN_LO, ENTRY_WIN_HI = 0.10, 0.50
MAX_CAND_PER_VERT = 5000
EVENT_PAGE_CAP = 3000
POWER_WEEKS, POWER_MKTS = 20, 300

# vertical -> gamma tag_ids (related_tags on). Discovered live via public-search tag arrays.
# NOTE: BUSINESS deliberately EXCLUDES macro-Economy (100328) & the broad Business(107) tag that the
# existing ECON sleeve is built from — it uses company-event tags so it can be tested as INDEPENDENT.
VERT_TAGS = [
    ("GEO",      [100265, 101970]),                       # Geopolitics, World
    ("BUSINESS", [1013, 102599, 600, 100474, 538, 102676]),# Earnings, IPO, IPOs, merger, ceo, Equities
    ("TECHAI",   [439, 1401, 101999, 105579]),            # AI, Tech, Big Tech, AI Releases
    ("WEATHER",  [84, 87, 102023, 496]),                  # Weather, climate, hurricane, Natural Disasters
    ("ENT",      [596, 53, 18, 51, 972, 100343, 1535, 100]),# Culture, Movies, Awards, box office, Tweet Markets, Mentions, celebrity, Music
    ("SPORTS_NBA",   [745]),
    ("SPORTS_SOCCER",[100350]),
    ("SPORTS_NFL",   [450]),
]
VERT_ORDER = [v for v,_ in VERT_TAGS]

CONFIRMED_CRYPTO_ROWS = "/home/user/Codex-playground-/scratchpad/advsel_rows.json"
ECON_RESULTS          = "/home/user/Codex-playground-/scratchpad/cat_results.json"

S = requests.Session()
S.headers.update({"User-Agent":"research/1.0"})

def _get(url, params=None, tries=4, timeout=45):
    for i in range(tries):
        try:
            r=S.get(url, params=params, timeout=timeout)
            if r.status_code==200:
                try: return r.json()
                except Exception: return None
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

# ---------------- universe discovery ----------------
def enum_tag_events(tag_id):
    def fn():
        out=[]; off=0
        while off < EVENT_PAGE_CAP:
            d=_get(f"{GAMMA}/events", {"closed":"true","tag_id":tag_id,"related_tags":"true",
                                       "limit":100,"offset":off})
            if not isinstance(d,list) or not d or not isinstance(d[0],dict): break
            out+=d
            if len(d)<100: break
            off+=100
        return out
    return cache_get(f"evtag_{tag_id}", fn)

def resolved_outcome(m):
    op=m.get("outcomePrices"); oc=m.get("outcomes")
    try:
        op=json.loads(op) if isinstance(op,str) else op
        oc=json.loads(oc) if isinstance(oc,str) else oc
    except Exception: return None
    if not op or not oc: return None
    if len(oc)!=2 or set(str(x).lower() for x in oc)!={"yes","no"}: return None
    d={str(oc[i]).lower():float(op[i]) for i in range(2)}
    y=d.get("yes")
    if y is None: return None
    if y>0.98: return 1.0
    if y<0.02: return 0.0
    return None

def extract_markets(evs, vert):
    out=[]
    for e in (evs or []):
        for m in e.get("markets",[]):
            if not m.get("closed"): continue
            yw=resolved_outcome(m)
            if yw is None: continue
            start=parse_dt(m.get("startDate")); end=parse_dt(m.get("endDate"))
            if not start or not end: continue
            horizon=(end-start).total_seconds()/86400.0
            if not (HORIZON_LO<=horizon<=HORIZON_HI): continue
            cid=m.get("conditionId")
            if not cid: continue
            try: toks=json.loads(m["clobTokenIds"])
            except Exception: continue
            if not toks or len(toks)<2: continue
            out.append(dict(
                vert=vert, question=m.get("question"), conditionId=cid,
                yes_token=str(toks[0]), no_token=str(toks[1]),
                yes_win=yw, start=start.timestamp(), end=end.timestamp(),
                horizon_days=horizon, volume=float(m.get("volumeNum") or 0)))
    return out

def crypto_econ_exclusion(log):
    """conditionIds already owned by the existing CRYPTO & macro-ECON sleeves -> excluded from verticals
    so each vertical is tested as an INDEPENDENT universe (avoid re-measuring the existing sleeves)."""
    excl=set()
    # crypto confirmed rows
    try:
        for r in json.load(open(CONFIRMED_CRYPTO_ROWS)):
            if r.get("conditionId"): excl.add(r["conditionId"])
    except Exception: pass
    n_crypto=len(excl)
    # macro-ECON universe = tags used by the confirmed ECON sleeve (Economy 100328 + Business 107)
    for tid in (100328, 107, 21):   # +21 crypto tag catch-all
        for e in (enum_tag_events(tid) or []):
            for m in e.get("markets",[]):
                cid=m.get("conditionId")
                if cid: excl.add(cid)
    log(f"[excl] crypto rows={n_crypto}, total excluded conditionIds (crypto+macroEcon+cryptoTag)={len(excl)}")
    return excl

def build_universe(log):
    excl=crypto_econ_exclusion(log)
    per_vert=defaultdict(list); raw_counts={}; seen_per_vert=defaultdict(set)
    for vert, tags in VERT_TAGS:
        evs=[]
        for tid in tags:
            evs += (enum_tag_events(tid) or [])
        cand=extract_markets(evs, vert)
        raw=0
        for m in cand:
            cid=m["conditionId"]
            if cid in excl: continue                 # belongs to an existing sleeve
            if cid in seen_per_vert[vert]: continue   # dedup within vertical
            seen_per_vert[vert].add(cid)
            per_vert[vert].append(m); raw+=1
        raw_counts[vert]=raw
    for vert in per_vert:
        per_vert[vert].sort(key=lambda x:-x["end"])
        if len(per_vert[vert])>MAX_CAND_PER_VERT:
            per_vert[vert]=per_vert[vert][:MAX_CAND_PER_VERT]
    return per_vert, raw_counts

# ---------------- causal entry + fills ----------------
def price_history(token, start, end):
    key="ph_"+str(token)+"_"+str(int(start))+"_"+str(int(end))
    def fn():
        d=_get(f"{CLOB}/prices-history", dict(market=token, startTs=int(start), endTs=int(end), fidelity=60))
        return (d or {}).get("history",[])
    return cache_get(key, fn)

def causal_entry(mk):
    st,en=mk["start"],mk["end"]; life=en-st
    if life<=0: return None
    lo=st+ENTRY_WIN_LO*life; hi=st+ENTRY_WIN_HI*life
    h=price_history(mk["yes_token"], st, en)
    if not h: return None
    pts=[(p["t"],p["p"]) for p in h if lo<=p["t"]<=hi]
    if len(pts)<2:
        allp=[(p["t"],p["p"]) for p in h if st<=p["t"]<=hi]
        if not allp: return None
        allp.sort(); return float(allp[-1][1])
    pts.sort()
    tot=0.0; wsum=0.0
    for i in range(len(pts)-1):
        dtw=pts[i+1][0]-pts[i][0]
        tot+=pts[i][1]*dtw; wsum+=dtw
    return float(tot/wsum) if wsum>0 else float(np.mean([p for _,p in pts]))

def mid_interp(h):
    if not h: return None
    ts=np.array([p["t"] for p in h],float); ps=np.array([p["p"] for p in h],float)
    o=np.argsort(ts); ts=ts[o]; ps=ps[o]
    return lambda t: float(np.interp(t, ts, ps))

def trades_for(conditionId, max_pages=12, page=500):
    key="tr_"+conditionId
    def fn():
        out=[]; off=0
        for _ in range(max_pages):
            d=_get(f"{DATA}/trades", dict(market=conditionId, limit=page, offset=off))
            if not isinstance(d,list) or not d: break
            out+=d
            if len(d)<page: break
            off+=page
        return out
    return cache_get(key, fn)

def analyze_fills(mk):
    st,en=mk["start"],mk["end"]; life=en-st
    half_ts=st+FIRST_HALF*life
    yt=mk["yes_token"]
    h=price_history(yt, st, en); f=mid_interp(h)
    trades=trades_for(mk["conditionId"]) or []
    yes_buy_shares=0.0; yes_buy_dollars=0.0; n_yes_buy=0; costs=[]
    for t in trades:
        side=(t.get("side") or "").upper()
        asset=str(t.get("asset") or "")
        try:
            price=float(t.get("price") or 0); size=float(t.get("size") or 0); ts=int(t.get("timestamp") or 0)
        except Exception: continue
        if size<=0 or ts<st or ts>en: continue
        if asset==yt and side=="BUY":
            if f is not None:
                c=abs(price - f(ts))
                if 0<=c<0.5: costs.append(c)
            if ts<=half_ts:
                yes_buy_shares+=size; yes_buy_dollars+=size*price; n_yes_buy+=1
    mk["yes_buy_shares"]=yes_buy_shares
    mk["yes_buy_dollars"]=yes_buy_dollars
    mk["n_yes_buy"]=n_yes_buy
    mk["half_spread"]= float(np.median(costs)) if len(costs)>=5 else None
    return mk

# ---------------- stats helpers ----------------
def weekly_series(rows, valfn, weightfn=None):
    wk=defaultdict(list); wt=defaultdict(list)
    for m in rows:
        k=week_key(m["end"]); wk[k].append(valfn(m))
        wt[k].append(1.0 if weightfn is None else max(0.0,weightfn(m)))
    out={}
    for k in wk:
        v=np.array(wk[k],float); w=np.array(wt[k],float)
        if w.sum()<=0: continue
        out[k]=float(np.average(v, weights=w))
    return out

def week_t_from_means(weekmeans):
    vals=np.array(list(weekmeans.values()),float); K=len(vals)
    if K<2: return (float(vals.mean()) if K else float('nan'), float('nan'), K)
    m=vals.mean(); sd=vals.std(ddof=1); se=sd/math.sqrt(K) if K>0 else float('nan')
    return (float(m), float(m/se) if se>0 else float('nan'), K)

def flat_t(vals):
    v=np.array(vals,float); N=len(v)
    if N<2: return (float(v.mean()) if N else float('nan'), float('nan'), N)
    m=v.mean(); se=v.std(ddof=1)/math.sqrt(N)
    return (float(m), float(m/se) if se>0 else float('nan'), N)

def pnl_fn(m):   # PnL/contract = executable_bid - yes_outcome = (entry_mid - half_spread) - yes_win
    return (m["entry"] - m["half_spread"]) - m["yes_win"]

def jackknife_week(weekmeans):
    """Leave-one-week-out t on the weekly-mean series. Returns (min_t, max_t)."""
    ks=list(weekmeans.keys())
    if len(ks)<3: return (float('nan'), float('nan'))
    ts=[]
    for drop in ks:
        sub={k:v for k,v in weekmeans.items() if k!=drop}
        _,t,_=week_t_from_means(sub); ts.append(t)
    return (float(np.nanmin(ts)), float(np.nanmax(ts)))

def drop_best_week(weekmeans):
    """t after removing the single most-positive week (one-week-driven check)."""
    if len(weekmeans)<3: return float('nan')
    kbest=max(weekmeans.items(), key=lambda kv:kv[1])[0]
    sub={k:v for k,v in weekmeans.items() if k!=kbest}
    _,t,_=week_t_from_means(sub); return t

# ---------------- per-vertical build & stats ----------------
def build_filled(vert, cands, log):
    log(f"[{vert}] candidates (capped): {len(cands)}")
    if not cands: return 0, [], 0.01, 0
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs={ex.submit(causal_entry, mk):mk for mk in cands}
        for f in as_completed(futs):
            futs[f]["entry_mid"]=f.result()
    pre=[m for m in cands if m.get("entry_mid") is not None and MID_PREFILTER_LO<=m["entry_mid"]<=MID_PREFILTER_HI]
    log(f"[{vert}] mid-prefilter [{MID_PREFILTER_LO},{MID_PREFILTER_HI}]: {len(pre)}")
    if not pre: return 0, [], 0.01, 0
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs=[ex.submit(analyze_fills, mk) for mk in pre]
        for _ in as_completed(futs): pass
    hs_all=[m["half_spread"] for m in pre if m["half_spread"] is not None]
    HS=float(np.median(hs_all)) if hs_all else 0.01
    for m in pre:
        if m["half_spread"] is None: m["half_spread"]=HS
        m["entry"]=m["entry_mid"]                      # entry_mid retained; bid = entry - half_spread
        m["entry_bid"]=m["entry_mid"]-m["half_spread"]
    # longshot SELL band on the EXECUTABLE BID + full-spread cap
    band=[m for m in pre if ENTRY_LO<=m["entry_bid"]<=ENTRY_HI and (2.0*m["half_spread"])<=MAX_FULL_SPREAD]
    log(f"[{vert}] BID-band [{ENTRY_LO},{ENTRY_HI}] & spread<= {MAX_FULL_SPREAD}: {len(band)}  half_spread(med)={HS:.4f}")
    filled=[m for m in band if m["yes_buy_shares"]>0]
    log(f"[{vert}] band w/ >0 first-half YES-buy vol: {len(filled)}")
    return len(band), filled, HS, len(pre)

def compute_stats(vert, n_band, filled, HS):
    if not filled:
        return dict(vert=vert, n_band=n_band, n_filled=0, weeks=0, weekly_eq={}, empty=True, half_spread=HS)
    for m in filled: m["pnl"]=pnl_fn(m)
    yw=np.array([m["yes_win"] for m in filled],float)
    vshare=np.array([m["yes_buy_shares"] for m in filled],float)
    vtot=np.array([max(0.0,m["volume"]) for m in filled],float)
    unw_rate=float(yw.mean())
    w_rate_share=float(np.average(yw, weights=vshare)) if vshare.sum()>0 else float('nan')

    wm_eq=weekly_series(filled, pnl_fn, None);                          m_eq,t_eq,K_eq=week_t_from_means(wm_eq)
    wm_sh=weekly_series(filled, pnl_fn, lambda m:m["yes_buy_shares"]);  m_sh,t_sh,K_sh=week_t_from_means(wm_sh)
    wm_dv=weekly_series(filled, pnl_fn, lambda m:max(0.0,m["volume"])); m_dv,t_dv,K_dv=week_t_from_means(wm_dv)
    m_flat,t_flat,N_flat=flat_t([m["pnl"] for m in filled])

    jk_min_sh, jk_max_sh = jackknife_week(wm_sh)
    dropbest_t_sh = drop_best_week(wm_sh)
    jk_min_eq, jk_max_eq = jackknife_week(wm_eq)

    worst_eq=min(wm_eq.items(), key=lambda kv:kv[1]) if wm_eq else ("-",float('nan'))
    negw_eq=100.0*sum(1 for v in wm_eq.values() if v<0)/max(1,len(wm_eq))

    bins=[(0.10,0.175),(0.175,0.25),(0.25,0.325),(0.325,0.35)]
    calib=[]
    for lo,hi in bins:
        sub=[m for m in filled if lo<=m["entry_bid"]<hi]
        if sub:
            calib.append((lo,hi,len(sub), float(np.mean([m["entry_bid"] for m in sub])),
                          float(np.mean([m["yes_win"] for m in sub]))))
    weeks=sorted(set(week_key(m["end"]) for m in filled))
    return dict(vert=vert, n_band=n_band, n_filled=len(filled), weeks=len(weeks), half_spread=HS,
                mean_entry=float(np.mean([m["entry_bid"] for m in filled])),
                unw_rate=unw_rate, w_rate_share=w_rate_share,
                m_eq=m_eq,t_eq=t_eq, m_sh=m_sh,t_sh=t_sh, m_dv=m_dv,t_dv=t_dv, m_flat=m_flat,t_flat=t_flat,
                jk_min_sh=jk_min_sh, jk_max_sh=jk_max_sh, dropbest_t_sh=dropbest_t_sh,
                jk_min_eq=jk_min_eq, jk_max_eq=jk_max_eq,
                worst_week=worst_eq, negw_eq=negw_eq, calib=calib, weekly_eq=wm_eq, empty=False)

# ---------------- existing sleeves ----------------
def load_crypto_weekly():
    rows=json.load(open(CONFIRMED_CRYPTO_ROWS))
    wk=defaultdict(list)
    for r in rows:
        if r.get("entry") is None: continue
        if r.get("yes_buy_shares",0)<=0: continue
        pnl=(float(r["entry"])-float(r["half_spread"]))-float(r["yes_win"])
        wk[week_key(float(r["end"]))].append(pnl)
    return {k:float(np.mean(v)) for k,v in wk.items()}

def load_econ_weekly():
    d=json.load(open(ECON_RESULTS))
    return dict(d["ECON"]["weekly_eq"])

def corr(a,b,minc=8):
    common=sorted(set(a)&set(b))
    if len(common)<minc: return (float('nan'), len(common))
    x=np.array([a[k] for k in common]); y=np.array([b[k] for k in common])
    if x.std()==0 or y.std()==0: return (float('nan'), len(common))
    return (float(np.corrcoef(x,y)[0,1]), len(common))

# ---------------- main ----------------
def main():
    t0=time.time(); R=[]
    def w(s=""): R.append(s); print(s, flush=True)
    log=lambda s: print("   "+s, flush=True)

    print("[1/3] Enumerating vertical universes (gamma tag_id, crypto/econ-excluded) ...", flush=True)
    per_vert, raw_counts = build_universe(log)
    for v in VERT_ORDER:
        print(f"    {v}: independent_candidates={len(per_vert.get(v,[]))} (raw {raw_counts.get(v,0)})", flush=True)

    print("[2/3] Per-vertical causal entry + fills + stats ...", flush=True)
    results={}
    for v in VERT_ORDER:
        nb, filled, HS, npre = build_filled(v, per_vert.get(v,[]), log)
        results[v]=compute_stats(v, nb, filled, HS)

    print("[3/3] Correlation to existing sleeves ...", flush=True)
    crypto_wk=load_crypto_weekly(); econ_wk=load_econ_weekly()

    # ---------------- report ----------------
    w("# Widening the book — new longshot-premium sleeves across Polymarket verticals\n")
    w(f"_Generated {dt.datetime.now(dt.timezone.utc).isoformat()} | runtime {time.time()-t0:.0f}s_\n")
    w("SELL the far-OTM longshot: causal first-half YES entry mid, **executable BID** = entry_mid − "
      f"half_spread banded in [{ENTRY_LO},{ENTRY_HI}] with full spread ≤ {MAX_FULL_SPREAD}. "
      "PnL/contract = entry_bid − yes_outcome, zero fee. Cluster by resolution week. Verticals are "
      "independent tag universes with the existing CRYPTO & macro-ECON conditionIds EXCLUDED (so we are "
      "not re-measuring the two live sleeves). Existing sleeves: CRYPTO (advsel_rows.json), ECON "
      "(cat_results ECON.weekly_eq).\n")

    w("## Per-vertical longshot-SELL edge (week-clustered)\n")
    w("| vertical | n_band | n_filled | weeks | mean bid | equal mean / t | YES-BUY-vol mean / t | $-vol mean / t | flat mean / t | power |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|:--|")
    for v in VERT_ORDER:
        r=results[v]
        if r.get("empty"):
            w(f"| {v} | {r.get('n_band',0)} | 0 | 0 | — | — | — | — | — | EMPTY |"); continue
        flag=[]
        if r["weeks"]<POWER_WEEKS: flag.append("<20wk")
        if r["n_filled"]<POWER_MKTS: flag.append("<300mkt")
        pw="OK" if not flag else ",".join(flag)
        w(f"| {v} | {r['n_band']} | {r['n_filled']} | {r['weeks']} | {r['mean_entry']:.3f} "
          f"| {r['m_eq']:+.4f} / {r['t_eq']:.2f} | {r['m_sh']:+.4f} / {r['t_sh']:.2f} "
          f"| {r['m_dv']:+.4f} / {r['t_dv']:.2f} | {r['m_flat']:+.4f} / {r['t_flat']:.2f} | {pw} |")
    w("")
    w("Weightings: **equal** = per-market; **YES-BUY-vol** = first-half YES-BUY taker shares (realistic "
      "fill object for a resting YES seller); **$-vol** = total market dollar volume (naive/contrast). "
      "`flat` = pooled iid SE (ignores week clustering; optimistic).\n")

    w("## Adverse selection, tail & robustness (per vertical)\n")
    w("| vertical | YES-print unw | YES-print vol-wtd | Δ | adv-sel | worst week | %neg wk | JK-min t (vol) | drop-best t (vol) |")
    w("|---|---:|---:|---:|:--|---:|---:|---:|---:|")
    for v in VERT_ORDER:
        r=results[v]
        if r.get("empty"): w(f"| {v} | — | — | — | — | — | — | — | — |"); continue
        d=r["w_rate_share"]-r["unw_rate"]
        direction="FAVORABLE" if d<=0.0 else ("neutral" if d<=0.01 else "adverse")
        ww=r["worst_week"]
        w(f"| {v} | {r['unw_rate']:.4f} | {r['w_rate_share']:.4f} | {d:+.4f} | {direction} "
          f"| {ww[1]:+.4f} ({ww[0]}) | {r['negw_eq']:.1f}% | {r['jk_min_sh']:.2f} | {r['dropbest_t_sh']:.2f} |")
    w("")

    w("## Calibration — realized YES vs executable bid, by bin\n")
    for v in VERT_ORDER:
        r=results[v]
        if r.get("empty") or not r.get("calib"): continue
        w(f"**{v}** (mean bid {r['mean_entry']:.3f}, unweighted realized YES {r['unw_rate']:.3f}):\n")
        w("| bid bin | n | mean bid | realized YES | overprice (bid−realized) |")
        w("|---|---:|---:|---:|---:|")
        for lo,hi,n,pe,ry in r["calib"]:
            w(f"| [{lo:.3f},{hi:.3f}) | {n} | {pe:.3f} | {ry:.3f} | {pe-ry:+.3f} |")
        w("")

    # ---------- sleeve gating ----------
    def real_edge(r):
        return (not r.get("empty")) and r["t_sh"]>=2.0 and r["n_filled"]>=POWER_MKTS and r["weeks"]>=POWER_WEEKS
    def robust(r):
        # jackknife-stable (drop-one-week keeps t>=1.5) AND not one-week-driven (drop-best keeps t>=1.5)
        return real_edge(r) and (r["jk_min_sh"]>=1.5) and (r["dropbest_t_sh"]>=1.5)
    def advsel_ok(r):
        return (r["w_rate_share"]-r["unw_rate"])<=0.01   # favorable or neutral

    # ---------- correlations ----------
    w("## CORRELATION TO EXISTING SLEEVES (the key deliverable)\n")
    w("Weekly series = equal-weighted mean PnL/contract per resolution week. Correlation on the weeks "
      "both series trade (>=8 common weeks required, else n/a).\n")
    w("| vertical | corr vs CRYPTO (n) | corr vs ECON (n) | real edge? | robust? | adv-sel | |corr|<0.3 both? |")
    w("|---|---:|---:|:--|:--|:--|:--|")
    corr_rows={}
    for v in VERT_ORDER:
        r=results[v]
        if r.get("empty"):
            w(f"| {v} | — | — | no | no | — | — |"); continue
        cc,nc=corr(r["weekly_eq"], crypto_wk)
        ce,ne=corr(r["weekly_eq"], econ_wk)
        corr_rows[v]=(cc,nc,ce,ne)
        re_=real_edge(r); rb=robust(r); av=advsel_ok(r)
        both_low = (not math.isnan(cc)) and (not math.isnan(ce)) and abs(cc)<0.30 and abs(ce)<0.30
        w(f"| {v} | {('n/a' if math.isnan(cc) else f'{cc:+.2f}')} ({nc}) "
          f"| {('n/a' if math.isnan(ce) else f'{ce:+.2f}')} ({ne}) "
          f"| {'YES' if re_ else 'no'} | {'YES' if rb else 'no'} | {'ok' if av else 'ADVERSE'} "
          f"| {'YES' if both_low else 'no'} |")
    w("")

    # full matrix over {crypto, econ, + verticals with a real edge}
    real_verts=[v for v in VERT_ORDER if real_edge(results[v])]
    series={"CRYPTO":crypto_wk, "ECON":econ_wk}
    for v in real_verts: series[v]=results[v]["weekly_eq"]
    mat_order=["CRYPTO","ECON"]+real_verts
    w("## FULL weekly-PnL correlation matrix  {crypto, econ, + verticals showing a real edge}\n")
    if len(mat_order)>2:
        w("| corr | " + " | ".join(mat_order) + " |")
        w("|---|" + "---:|"*len(mat_order))
        for a in mat_order:
            cells=[]
            for b in mat_order:
                if a==b: cells.append("1.00")
                else:
                    c,n=corr(series[a],series[b]); cells.append("n/a" if math.isnan(c) else f"{c:+.2f}")
            w(f"| **{a}** | " + " | ".join(cells) + " |")
        w("")
        w("Overlapping-week counts:\n")
        w("| n | " + " | ".join(mat_order) + " |")
        w("|---|" + "---:|"*len(mat_order))
        for a in mat_order:
            cells=[]
            for b in mat_order:
                if a==b: cells.append(f"{len(series[a])}")
                else:
                    _,n=corr(series[a],series[b]); cells.append(f"{n}")
            w(f"| **{a}** | " + " | ".join(cells) + " |")
        w("")
    else:
        w("_No vertical cleared the real-edge gate (YES-BUY-vol t>=2, powered); matrix reduces to the two "
          "existing sleeves. CRYPTO×ECON shown for reference:_\n")
        c,n=corr(crypto_wk,econ_wk)
        w(f"- CRYPTO × ECON: {('n/a' if math.isnan(c) else f'{c:+.2f}')} (n={n} common weeks)\n")

    # ---------- verdict ----------
    w("## VERDICT\n")
    stackable=[]; redundant=[]; nullv=[]
    for v in VERT_ORDER:
        r=results[v]
        if r.get("empty"): nullv.append((v,"no band markets")); continue
        re_=real_edge(r); rb=robust(r); av=advsel_ok(r)
        cc,nc,ce,ne=corr_rows.get(v,(float('nan'),0,float('nan'),0))
        both_low = (not math.isnan(cc)) and (not math.isnan(ce)) and abs(cc)<0.30 and abs(ce)<0.30
        pw=[]
        if r["weeks"]<POWER_WEEKS: pw.append(f"{r['weeks']}wk")
        if r["n_filled"]<POWER_MKTS: pw.append(f"{r['n_filled']}mkt")
        pwtxt=(" UNDERPOWERED["+",".join(pw)+"]") if pw else ""
        if re_ and rb and av and both_low:
            stackable.append(v)
            w(f"- **{v} — NEW STACKABLE SLEEVE.** YES-BUY-vol mean {r['m_sh']:+.4f} (t={r['t_sh']:.2f}), "
              f"JK-min t {r['jk_min_sh']:.2f}, drop-best t {r['dropbest_t_sh']:.2f}, adv-sel "
              f"{r['w_rate_share']-r['unw_rate']:+.4f}; corr crypto {cc:+.2f}, econ {ce:+.2f} — both |<0.3|.{pwtxt}")
        elif re_ and rb and av and (not both_low):
            redundant.append(v)
            w(f"- **{v} — REAL but CORRELATED (redundant).** t={r['t_sh']:.2f}, robust; but corr "
              f"crypto {cc:+.2f} / econ {ce:+.2f} — not both <0.3.{pwtxt}")
        elif re_ and not (rb and av):
            nullv.append((v, f"t={r['t_sh']:.2f} but "
                             + ("adverse-selection " if not av else "")
                             + ("fragile (JK-min {:.2f}/drop-best {:.2f})".format(r['jk_min_sh'],r['dropbest_t_sh']) if not rb else "")))
            w(f"- **{v} — REAL-t but FAILS robustness/adv-sel** (not a clean sleeve). t={r['t_sh']:.2f}, "
              f"JK-min {r['jk_min_sh']:.2f}, drop-best {r['dropbest_t_sh']:.2f}, adv-sel "
              f"{r['w_rate_share']-r['unw_rate']:+.4f}.{pwtxt}")
        else:
            nullv.append((v, f"t_sh={r['t_sh']:.2f}"))
            w(f"- **{v} — NULL** at realistic fills. YES-BUY-vol mean {r['m_sh']:+.4f} (t={r['t_sh']:.2f}), "
              f"equal {r['m_eq']:+.4f} (t={r['t_eq']:.2f}).{pwtxt}")
    w("")
    w(f"**NEW STACKABLE sleeves (real + robust + uncorrelated to BOTH crypto & econ):** "
      f"{', '.join(stackable) if stackable else 'NONE'}.")
    w(f"**Real-but-correlated (redundant with an existing sleeve):** {', '.join(redundant) if redundant else 'none'}.")
    w(f"**Null / fragile / adverse:** {', '.join(v for v,_ in nullv) if nullv else 'none'}.")
    w("")

    with open("/home/user/Codex-playground-/pmkt_verticals_report.md","w") as fp:
        fp.write("\n".join(R)+"\n")
    dump={v:{k:results[v].get(k) for k in ("n_band","n_filled","weeks","half_spread","unw_rate",
             "w_rate_share","m_eq","t_eq","m_sh","t_sh","m_dv","t_dv","jk_min_sh","dropbest_t_sh",
             "weekly_eq")} for v in VERT_ORDER}
    dump["_corr"]={v:corr_rows.get(v) for v in VERT_ORDER}
    with open("/home/user/Codex-playground-/scratchpad/vert_results.json","w") as fp:
        json.dump(dump,fp)
    print(f"\nDONE in {time.time()-t0:.0f}s -> pmkt_verticals_report.md", flush=True)

if __name__=="__main__":
    main()
