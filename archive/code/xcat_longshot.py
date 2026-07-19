#!/usr/bin/env python3
"""
xcat_longshot.py — DIVERSIFICATION scan: does the confirmed Polymarket longshot short-vol premium
(SELL far-OTM YES priced in [0.10,0.35], harvest lottery/favorite-longshot overpricing) exist in
NON-CRYPTO categories, and are those PnLs UNCORRELATED with the crypto edge (and each other)?

The confirmed crypto edge is a CRYPTO-BETA bet (SOL/XRP came back 0.6-0.8 corr with BTC, so adding
crypto tickers does not diversify). To RAISE the diversified frontier we need the SAME overpricing
mechanism in categories whose longshots resolve on events UNCORRELATED with crypto. The decisive
deliverable is the cross-category + vs-crypto weekly-PnL correlation matrix.

This is an INDEPENDENT re-implementation (my own code) of the cross-category test. It goes FINER than
the earlier 5-bucket study: it isolates ENTERTAINMENT, SCI/TECH, WEATHER, GEOPOLITICS, ELECTIONS and
splits ECON from BUSINESS, so a premium that was hidden inside a catch-all "OTHER" bucket is exposed
category-by-category, and the multiple-testing count is stated honestly (9 non-crypto categories).

METHOD (same anti-artifact discipline that killed 14+ prior candidates):
  * Universe: settled binary Yes/No Polymarket markets, discovered per category via gamma tag_id
    (related_tags on). Each conditionId assigned to exactly ONE category by priority (specific buckets
    first; crypto stripped out entirely) -> mutually exclusive categories.
  * CAUSAL entry: time-weighted YES mid over the FIRST HALF of market life from CLOB prices-history.
    No look-ahead. Longshot SELL band = entry mid in [0.10,0.35] (the TRADEABLE band; excludes the
    2-8c "taker-dead deep wing" that cannot be filled).
  * Executable price, not mid: entry_exec = entry_mid - half_spread, where half_spread = median
    |YES-BUY taker fill price - mid| over the first half (falls back to category-global median).
    Markets with ZERO first-half YES-BUY taker volume are FLAGGED (no fill object) and reported
    separately; the headline uses only markets that actually had takers.
  * Outcome ONLY from resolution (outcomePrices). yes_win in {0,1}. PnL/ct = entry_exec - yes_win.
  * PERIOD-CLUSTERED t: cluster by RESOLUTION WEEK (mean of per-week means / (sd/sqrt(K))). NOT
    per-contract (that inflates t massively). Also report event-day-clustered t as a robustness check.
  * Calibration: realized YES rate vs priced entry, by bin (the overpricing the seller harvests).
  * CORRELATION: per-week equal-weight PnL series per category -> cross-category corr matrix AND each
    category's corr with the CONFIRMED crypto short-vol PnL (advsel_rows.json). Low corr + real premium
    = raises the diversified frontier.
  * CAPACITY: first-half YES-BUY taker $ (the fillable size for a resting YES seller) per category,
    total and per-week. Thin niche premium with no size is flagged.
  * Multiple testing: 9 non-crypto categories tested -> Bonferroni |t|>=2.77 for family-wise 0.05.

Data (public, no auth): gamma-api events (universe+resolution), clob prices-history (causal mid),
data-api trades (YES-BUY taker fills). Reuses the shared cache (scratchpad/cat_cache) key scheme.
"""
import os, sys, json, time, math, datetime as dt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

ROOT = "/home/user/Codex-playground-"
CACHE = os.path.join(ROOT, "scratchpad/cat_cache")   # shared cache (same key scheme as prior study)
os.makedirs(CACHE, exist_ok=True)
GAMMA = "https://gamma-api.polymarket.com"
CLOB  = "https://clob.polymarket.com"
DATA  = "https://data-api.polymarket.com"
CONFIRMED_CRYPTO_ROWS = os.path.join(ROOT, "scratchpad/advsel_rows.json")

# ---- frozen parameters (task-specified band; same discipline as confirmed study) ----
ENTRY_LO, ENTRY_HI = 0.10, 0.35        # TRADEABLE longshot SELL band
HORIZON_LO, HORIZON_HI = 2.0, 30.0     # days; life must support a first-half entry window
ENTRY_WIN_LO, ENTRY_WIN_HI = 0.10, 0.50  # causal first-half price-history window for the entry mid
FIRST_HALF = 0.50                      # taker-fill aggregation window = [start, start+0.5*life]
MAX_CAND_PER_CAT = 4500                # cap price-history calls per category (coverage reported)
EVENT_PAGE_CAP = 2600                  # gamma offset window per tag query
POWER_WEEKS, POWER_MKTS = 15, 150      # underpowered thresholds (blunt about small n)

# non-crypto categories -> gamma tag_ids. Order = dedup priority (specific buckets first so the
# large catch-alls POLITICS/SPORTS don't swallow them). CRYPTO is stripped out first via advsel set.
CAT_TAGS = [
    ("WEATHER",       [84, 87]),                       # weather + climate
    ("SCITECH",       [74, 1401, 22, 439]),            # science + tech + technology + AI
    ("ENTERTAINMENT", [315, 100338, 53, 100, 18, 596]),# entertainment+TV+movies+music+awards+culture
    ("ECON",          [100328]),                       # macro econ data releases
    ("BUSINESS",      [107]),                          # company/business events
    ("ELECTIONS",     [144]),                          # election outcomes
    ("GEOPOL",        [100265]),                       # geopolitics / war / foreign affairs
    ("SPORTS",        [1]),                             # sports (de-vig caveat, see report)
    ("POLITICS",      [2]),                             # general politics (catch-all last)
]
NONCRYPTO = [c for c, _ in CAT_TAGS]
CAT_ORDER = ["CRYPTO"] + NONCRYPTO
N_TESTS = len(NONCRYPTO)               # multiple-testing family size
BONF_T = 2.77                          # ~ two-sided 0.05/9 critical |t|

S = requests.Session(); S.headers.update({"User-Agent": "research/1.0"})

def _get(url, params=None, tries=4, timeout=45):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                try: return r.json()
                except Exception: return None
            if r.status_code in (429,500,502,503,504): time.sleep(1.2*(i+1)); continue
            return None
        except Exception:
            time.sleep(1.0*(i+1))
    return None

def cache_get(key, fn):
    p = os.path.join(CACHE, key + ".json")
    if os.path.exists(p):
        try:
            with open(p) as f: return json.load(f)
        except Exception: pass
    v = fn()
    if v is None: return None
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(v, f)
    os.replace(tmp, p)
    return v

def iso(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc)
def parse_dt(s):
    if not s: return None
    try: return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception: return None
def week_key(end_ts):
    d = iso(end_ts); y,w,_ = d.isocalendar(); return f"{y}-W{w:02d}"
def day_key(end_ts):
    return iso(end_ts).strftime("%Y-%m-%d")

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

def extract_markets(evs, cat):
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
            out.append(dict(cat=cat, question=m.get("question"), conditionId=cid,
                            yes_token=str(toks[0]), no_token=str(toks[1]),
                            yes_win=yw, start=start.timestamp(), end=end.timestamp(),
                            horizon_days=horizon, volume=float(m.get("volumeNum") or 0)))
    return out

def crypto_condition_ids():
    """conditionIds of the confirmed crypto edge, to strip crypto out of every non-crypto bucket."""
    ids=set()
    if os.path.exists(CONFIRMED_CRYPTO_ROWS):
        for r in json.load(open(CONFIRMED_CRYPTO_ROWS)):
            if r.get("conditionId"): ids.add(r["conditionId"])
    # also strip anything under the crypto tag (21) to be safe
    evs=enum_tag_events(21) or []
    for m in extract_markets(evs, "CRYPTO"):
        ids.add(m["conditionId"])
    return ids

def build_universe(log):
    crypto_ids=crypto_condition_ids()
    log(f"crypto conditionIds to strip: {len(crypto_ids)}")
    seen={}; per_cat=defaultdict(list); raw_counts={}
    for cat, tags in CAT_TAGS:
        evs=[]
        for tid in tags: evs += (enum_tag_events(tid) or [])
        cand=extract_markets(evs, cat)
        raw_counts[cat]=len(cand)
        for m in cand:
            cid=m["conditionId"]
            if cid in crypto_ids: continue      # never let crypto contaminate a non-crypto bucket
            if cid in seen: continue            # first (highest-priority) category claims it
            seen[cid]=cat; per_cat[cat].append(m)
    for cat in per_cat:
        per_cat[cat].sort(key=lambda x:-x["end"])
        if len(per_cat[cat])>MAX_CAND_PER_CAT: per_cat[cat]=per_cat[cat][:MAX_CAND_PER_CAT]
    return per_cat, raw_counts

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
        dtw=pts[i+1][0]-pts[i][0]; tot+=pts[i][1]*dtw; wsum+=dtw
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
    st,en=mk["start"],mk["end"]; life=en-st; half_ts=st+FIRST_HALF*life
    yt=mk["yes_token"]
    h=price_history(yt, st, en); f=mid_interp(h)
    trades=trades_for(mk["conditionId"]) or []
    yes_buy_shares=0.0; yes_buy_dollars=0.0; n_yes_buy=0; costs=[]
    for t in trades:
        side=(t.get("side") or "").upper(); asset=str(t.get("asset") or "")
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
    mk["yes_buy_shares"]=yes_buy_shares; mk["yes_buy_dollars"]=yes_buy_dollars
    mk["n_yes_buy"]=n_yes_buy
    mk["half_spread"]= float(np.median(costs)) if len(costs)>=5 else None
    return mk

# ---------------- stats ----------------
def pnl_fn(m): return (m["entry"] - m["half_spread"]) - m["yes_win"]

def keyed_series(rows, keyfn, weightfn=None):
    grp=defaultdict(list); wt=defaultdict(list)
    for m in rows:
        k=keyfn(m["end"]); grp[k].append(pnl_fn(m))
        wt[k].append(1.0 if weightfn is None else max(0.0,weightfn(m)))
    out={}
    for k in grp:
        v=np.array(grp[k],float); w=np.array(wt[k],float)
        if w.sum()<=0: continue
        out[k]=float(np.average(v, weights=w))
    return out

def cluster_t(means):
    vals=np.array(list(means.values()),float); K=len(vals)
    if K<2: return (float(vals.mean()) if K else float('nan'), float('nan'), K)
    m=vals.mean(); sd=vals.std(ddof=1); se=sd/math.sqrt(K) if K>0 else float('nan')
    return (float(m), float(m/se) if se>0 else float('nan'), K)

def flat_t(vals):
    v=np.array(vals,float); N=len(v)
    if N<2: return (float(v.mean()) if N else float('nan'), float('nan'), N)
    m=v.mean(); se=v.std(ddof=1)/math.sqrt(N)
    return (float(m), float(m/se) if se>0 else float('nan'), N)

def build_filled(cat, cands, log):
    log(f"[{cat}] candidates (capped): {len(cands)}")
    if not cands: return 0, [], 0.01, 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs={ex.submit(causal_entry, mk):mk for mk in cands}
        for f in as_completed(futs): futs[f]["entry"]=f.result()
    band=[m for m in cands if m.get("entry") is not None and ENTRY_LO<=m["entry"]<=ENTRY_HI]
    n_band=len(band)
    log(f"[{cat}] band [{ENTRY_LO},{ENTRY_HI}]: {n_band}")
    if not band: return 0, [], 0.01, 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs=[ex.submit(analyze_fills, mk) for mk in band]
        for _ in as_completed(futs): pass
    hs_all=[m["half_spread"] for m in band if m["half_spread"] is not None]
    HS=float(np.median(hs_all)) if hs_all else 0.02
    for m in band:
        if m["half_spread"] is None: m["half_spread"]=HS
    filled=[m for m in band if m["yes_buy_shares"]>0]   # require an actual taker fill object
    n_notaker=n_band-len(filled)
    log(f"[{cat}] filled (>0 first-half YES-buy taker vol): {len(filled)}  no-taker(flagged): {n_notaker}  HS={HS:.4f}")
    return n_band, filled, HS, n_notaker

def load_confirmed_crypto(log):
    if not os.path.exists(CONFIRMED_CRYPTO_ROWS):
        log("[CRYPTO] confirmed rows missing"); return 0, [], 0.01, 0
    rows=json.load(open(CONFIRMED_CRYPTO_ROWS)); filled=[]
    for r in rows:
        if r.get("entry") is None or r.get("yes_buy_shares",0)<=0: continue
        filled.append(dict(cat="CRYPTO", entry=float(r["entry"]), yes_win=float(r["yes_win"]),
                           half_spread=float(r["half_spread"]), yes_buy_shares=float(r["yes_buy_shares"]),
                           yes_buy_dollars=float(r["yes_buy_dollars"]), volume=float(r.get("volume") or 0),
                           end=float(r["end"]), conditionId=r.get("conditionId")))
    HS=float(np.median([m["half_spread"] for m in filled])) if filled else 0.01
    log(f"[CRYPTO] confirmed edge rows w/ YES-buy vol: {len(filled)}  HS={HS:.4f}")
    return len(filled), filled, HS, 0

def compute_stats(cat, n_band, filled, HS, n_notaker):
    if not filled:
        return dict(cat=cat, n_band=n_band, n_filled=0, weeks=0, weekly_eq={}, empty=True,
                    half_spread=HS, n_notaker=n_notaker)
    yw=np.array([m["yes_win"] for m in filled],float)
    vshare=np.array([m["yes_buy_shares"] for m in filled],float)
    # PnL, three weightings, week-clustered
    wm_eq=keyed_series(filled, week_key, None);                          m_eq,t_eq,K_eq=cluster_t(wm_eq)
    wm_sh=keyed_series(filled, week_key, lambda m:m["yes_buy_shares"]);  m_sh,t_sh,K_sh=cluster_t(wm_sh)
    dm_eq=keyed_series(filled, day_key, None);                           m_d,t_d,K_d=cluster_t(dm_eq)
    m_flat,t_flat,N_flat=flat_t([pnl_fn(m) for m in filled])
    worst=min(wm_eq.items(), key=lambda kv:kv[1]) if wm_eq else ("-",float('nan'))
    negw=100.0*sum(1 for v in wm_eq.values() if v<0)/max(1,len(wm_eq))
    winr=100.0*float((yw<0.5).mean())   # a SELL wins when it settles NO
    bins=[(0.10,0.175),(0.175,0.25),(0.25,0.325),(0.325,0.35)]
    calib=[]
    for lo,hi in bins:
        sub=[m for m in filled if lo<=m["entry"]<hi]
        if sub:
            calib.append((lo,hi,len(sub), float(np.mean([m["entry"] for m in sub])),
                          float(np.mean([m["yes_win"] for m in sub]))))
    weeks=sorted(set(week_key(m["end"]) for m in filled))
    cap_total=float(np.sum([m["yes_buy_dollars"] for m in filled]))
    return dict(cat=cat, n_band=n_band, n_filled=len(filled), n_notaker=n_notaker,
                weeks=len(weeks), days=len(dm_eq), half_spread=HS,
                mean_entry=float(np.mean([m["entry"] for m in filled])),
                unw_yes=float(yw.mean()), w_yes_share=(float(np.average(yw,weights=vshare)) if vshare.sum()>0 else float('nan')),
                m_eq=m_eq,t_eq=t_eq,K_eq=K_eq, m_sh=m_sh,t_sh=t_sh,K_sh=K_sh,
                m_day=m_d,t_day=t_d,K_day=K_d, m_flat=m_flat,t_flat=t_flat,N_flat=N_flat,
                worst_week=worst, negw=negw, winrate=winr, calib=calib,
                cap_total_yesbuy_usd=cap_total, cap_per_week=cap_total/max(1,len(weeks)),
                weekly_eq=wm_eq, empty=False)

def corr_overlap(a, b, min_common=8):
    ks=sorted(set(a) & set(b))
    if len(ks)<min_common: return (float('nan'), len(ks))
    x=np.array([a[k] for k in ks]); y=np.array([b[k] for k in ks])
    if x.std()==0 or y.std()==0: return (float('nan'), len(ks))
    return (float(np.corrcoef(x,y)[0,1]), len(ks))

# ---------------- main ----------------
def fmt(x, d=4):
    try:
        if x is None or (isinstance(x,float) and math.isnan(x)): return "—"
        return f"{x:+.{d}f}"
    except Exception: return str(x)

def main():
    t0=time.time(); R=[]
    def w(s=""): R.append(s); print(s, flush=True)
    log=lambda s: print("   "+s, flush=True)

    print("[1/3] Enumerating category universes (finer granularity, priority-deduped, crypto stripped) ...", flush=True)
    per_cat, raw_counts = build_universe(log)
    for cat in NONCRYPTO:
        print(f"    {cat}: raw_binary_resolved={raw_counts.get(cat,0)}  exclusive={len(per_cat.get(cat,[]))}", flush=True)

    print("[2/3] Per-category causal entry + taker fills + week-clustered stats ...", flush=True)
    results={}
    nb,filled,HS,nt=load_confirmed_crypto(log); results["CRYPTO"]=compute_stats("CRYPTO",nb,filled,HS,nt)
    for cat in NONCRYPTO:
        nb,filled,HS,nt=build_filled(cat, per_cat.get(cat,[]), log)
        results[cat]=compute_stats(cat, nb, filled, HS, nt)

    print("[3/3] Cross-category + vs-crypto weekly-PnL correlation matrix ...", flush=True)
    series={c:results[c]["weekly_eq"] for c in CAT_ORDER if not results[c].get("empty")}
    cats_ok=[c for c in CAT_ORDER if c in series]
    cmat={}; nmat={}
    for a in cats_ok:
        for b in cats_ok:
            cval,ncom=corr_overlap(series[a], series[b])
            cmat[(a,b)]=1.0 if a==b else cval; nmat[(a,b)]=len(set(series[a])) if a==b else ncom

    # ---------------- REPORT ----------------
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    w(f"# Cross-category longshot short-vol premium — DIVERSIFICATION scan\n")
    w(f"_Generated {now} | runtime {time.time()-t0:.0f}s_\n")
    w("Test: SELL the far-OTM longshot (causal first-half YES entry mid in [0.10,0.35]), hold to UMA "
      "resolution, PnL/ct = (entry_mid − half_spread) − yes_outcome, zero fee. Non-crypto categories "
      "are mutually-exclusive Polymarket markets discovered by gamma tag_id, priority-deduped, with all "
      "crypto conditionIds stripped out. Horizon [2,30] days; band = TRADEABLE [0.10,0.35] (excludes the "
      "2-8c taker-dead deep wing). Half-spread haircut = median |YES-BUY taker fill − mid| over the first "
      "half; markets with no first-half YES-buy taker are flagged (no fill object) and excluded from the "
      "headline. **t is PERIOD-CLUSTERED by resolution week** (not per-contract).\n")
    w(f"**CRYPTO row = the CONFIRMED edge** (BTC/ETH weekly 'above on' longshots, band [0.15,0.30], from "
      f"`advsel_rows.json`) — carried in as the diversification anchor, not a re-scan.\n")
    w(f"**Multiple testing:** {N_TESTS} non-crypto categories tested. Family-wise 0.05 ⇒ Bonferroni "
      f"critical |t| ≈ {BONF_T}. A category clears the bar only if its week-clustered |t| exceeds it.\n")

    w("## Per-category longshot-SELL edge (week-clustered)\n")
    w("| category | n_band | n_filled | no-taker | weeks | mean entry | equal PnL/ct / t_wk | YES-buy-vol PnL/ct / t_wk | day-clust t | winrate | powered |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--|")
    for cat in CAT_ORDER:
        r=results[cat]
        if r.get("empty"):
            w(f"| {cat} | {r['n_band']} | 0 | {r.get('n_notaker',0)} | 0 | — | — | — | — | — | EMPTY |"); continue
        powered = "OK" if (r["weeks"]>=POWER_WEEKS and r["n_filled"]>=POWER_MKTS) else "UNDERPOWERED"
        w(f"| {cat} | {r['n_band']} | {r['n_filled']} | {r['n_notaker']} | {r['weeks']} | {r['mean_entry']:.3f} "
          f"| {fmt(r['m_eq'])} / {r['t_eq']:.2f} | {fmt(r['m_sh'])} / {r['t_sh']:.2f} "
          f"| {r['t_day']:.2f} | {r['winrate']:.1f}% | {powered} |")
    w("\nWeightings: **equal** = per-market; **YES-buy-vol** = first-half YES-BUY taker shares (the "
      "realistic fill object for a resting YES seller). day-clust t clusters by resolution DAY (robustness).\n")

    w("## Tail & adverse-selection (per category)\n")
    w("| category | worst week | % neg weeks | YES-print unwtd | YES-print YES-buy-wtd | Δ | direction |")
    w("|---|---:|---:|---:|---:|---:|:--|")
    for cat in CAT_ORDER:
        r=results[cat]
        if r.get("empty"): continue
        d=r["w_yes_share"]-r["unw_yes"]
        direction="FAVORABLE (≤)" if d<=0 else "adverse (>)"
        ww=r["worst_week"]
        w(f"| {cat} | {ww[1]:+.4f} ({ww[0]}) | {r['negw']:.1f}% | {r['unw_yes']:.4f} | {r['w_yes_share']:.4f} | {d:+.4f} | {direction} |")

    w("\n## Calibration — realized YES vs priced entry, by bin (the overpricing the seller harvests)\n")
    for cat in CAT_ORDER:
        r=results[cat]
        if r.get("empty") or not r.get("calib"): continue
        w(f"**{cat}** (mean entry {r['mean_entry']:.3f}, realized YES {r['unw_yes']:.3f}):\n")
        w("| entry bin | n | priced | realized YES | overprice (priced−realized) |")
        w("|---|---:|---:|---:|---:|")
        for lo,hi,n,pe,ry in r["calib"]:
            w(f"| [{lo:.3f},{hi:.3f}) | {n} | {pe:.3f} | {ry:.3f} | {pe-ry:+.3f} |")
        w("")

    w("## CROSS-CATEGORY + vs-CRYPTO weekly-PnL CORRELATION MATRIX (the diversification deliverable)\n")
    w("Weekly series = equal-weighted mean PnL/ct per resolution week. Correlation on the weeks two "
      "categories BOTH trade (pairwise overlap). Low/zero corr with CRYPTO + real premium = raises the "
      "diversified frontier. `—` = <8 common weeks (not estimable).\n")
    head="| corr | " + " | ".join(cats_ok) + " |"
    w(head); w("|---|" + "|".join(["---:"]*len(cats_ok)) + "|")
    for a in cats_ok:
        row=[f"**{a}**"]
        for b in cats_ok:
            row.append("1.00" if a==b else fmt(cmat[(a,b)],2))
        w("| " + " | ".join(row) + " |")
    w("\nPairwise overlapping-week counts:\n")
    w(head.replace("corr","n_com")); w("|---|" + "|".join(["---:"]*len(cats_ok)) + "|")
    for a in cats_ok:
        row=[f"**{a}**"]+[str(nmat[(a,b)]) for b in cats_ok]
        w("| " + " | ".join(row) + " |")

    w("\n## Capacity (first-half YES-BUY taker $ — the fillable size for a resting YES seller)\n")
    w("| category | total YES-buy $ | per resolution-week $ | n_filled |")
    w("|---|---:|---:|---:|")
    for cat in CAT_ORDER:
        r=results[cat]
        if r.get("empty"): continue
        w(f"| {cat} | ${r['cap_total_yesbuy_usd']:,.0f} | ${r['cap_per_week']:,.0f} | {r['n_filled']} |")

    # ---------------- verdict ----------------
    w("\n## VERDICT — non-crypto uncorrelated longshot-premium sleeves?\n")
    def classify(r):
        if r.get("empty"): return "EMPTY"
        powered = r["weeks"]>=POWER_WEEKS and r["n_filled"]>=POWER_MKTS
        t=r["t_sh"] if not math.isnan(r["t_sh"]) else r["t_eq"]
        m=r["m_sh"] if not math.isnan(r["m_sh"]) else r["m_eq"]
        if not powered: return "UNDERPOWERED"
        if m>0 and t>=BONF_T: return "REAL (survives multiple-testing)"
        if m>0 and t>=2.0: return "REAL-nominal (t≥2 but < Bonferroni)"
        if m>0 and t>0: return "MARGINAL (positive, t<2)"
        return "NULL/negative"
    verdict={}
    for cat in NONCRYPTO:
        r=results[cat]; verdict[cat]=classify(r)
        if r.get("empty"):
            w(f"- **{cat}**: EMPTY (no band markets)."); continue
        t=r["t_sh"] if not math.isnan(r["t_sh"]) else r["t_eq"]
        m=r["m_sh"] if not math.isnan(r["m_sh"]) else r["m_eq"]
        cc,ncc=corr_overlap(r["weekly_eq"], results["CRYPTO"]["weekly_eq"])
        ccs = f"{cc:+.2f} (n={ncc})" if not math.isnan(cc) else f"— (n={ncc}, insufficient)"
        w(f"- **{cat}** [{verdict[cat]}]: realistic-fill PnL/ct {fmt(m)} (t_wk={t:.2f}), equal {fmt(r['m_eq'])} "
          f"(t_wk={r['t_eq']:.2f}); vs-CRYPTO corr {ccs}; cap ${r['cap_per_week']:,.0f}/wk; worst week {r['worst_week'][1]:+.3f}.")

    real=[c for c in NONCRYPTO if verdict[c].startswith("REAL")]
    marg=[c for c in NONCRYPTO if verdict[c].startswith("MARGINAL")]
    # which are BOTH real AND crypto-uncorrelated?
    prize=[]
    for c in real:
        cc,ncc=corr_overlap(results[c]["weekly_eq"], results["CRYPTO"]["weekly_eq"])
        if ncc>=8 and (math.isnan(cc) or abs(cc)<0.3): prize.append((c,cc,ncc))
        elif ncc<8: prize.append((c,cc,ncc))  # uncorrelated-by-construction (no overlap)
    w("")
    w(f"**Categories with a real premium surviving realistic fills:** {', '.join(real) if real else 'NONE'} "
      f"(REAL = week-clustered t≥{BONF_T} Bonferroni, or ≥2 nominal). Marginal: {', '.join(marg) if marg else 'none'}.")
    if prize:
        w(f"**BOTH profitable AND crypto-uncorrelated (the frontier-raising prize):** " +
          ", ".join(f"{c} (corr {fmt(cc,2)}, n={n})" for c,cc,n in prize) + ".")
    else:
        w("**BOTH profitable AND crypto-uncorrelated:** NONE cleared the bar.")

    # summary json
    summ=dict(generated=now, n_tests=N_TESTS, bonferroni_t=BONF_T,
              categories={}, verdict=verdict,
              corr_vs_crypto={}, corr_matrix={f"{a}|{b}":cmat[(a,b)] for a in cats_ok for b in cats_ok},
              corr_overlap_n={f"{a}|{b}":nmat[(a,b)] for a in cats_ok for b in cats_ok})
    for cat in CAT_ORDER:
        r=results[cat]
        if r.get("empty"):
            summ["categories"][cat]=dict(empty=True, n_band=r["n_band"]); continue
        cc,ncc=corr_overlap(r["weekly_eq"], results["CRYPTO"]["weekly_eq"])
        summ["corr_vs_crypto"][cat]=dict(corr=None if math.isnan(cc) else cc, n_common=ncc)
        summ["categories"][cat]=dict(
            n_band=r["n_band"], n_filled=r["n_filled"], n_notaker=r["n_notaker"], weeks=r["weeks"],
            mean_entry=r["mean_entry"], m_eq=r["m_eq"], t_eq=r["t_eq"], m_yesbuyvol=r["m_sh"], t_yesbuyvol=r["t_sh"],
            t_day=r["t_day"], winrate=r["winrate"], worst_week=list(r["worst_week"]), pct_neg_weeks=r["negw"],
            unw_yes=r["unw_yes"], w_yes_share=r["w_yes_share"],
            cap_total_yesbuy_usd=r["cap_total_yesbuy_usd"], cap_per_week=r["cap_per_week"],
            calib=[list(c) for c in r["calib"]])
    with open(os.path.join(ROOT,"xcat_longshot_summary.json"),"w") as f: json.dump(summ,f,indent=2)
    with open(os.path.join(ROOT,"xcat_longshot_report.md"),"w") as f: f.write("\n".join(R)+"\n")
    print(f"\nWROTE xcat_longshot_report.md and xcat_longshot_summary.json  ({time.time()-t0:.0f}s)", flush=True)

if __name__=="__main__":
    main()
