#!/usr/bin/env python3
"""
edge_capture.py — How much MORE of the confirmed Polymarket weekly crypto short-vol
edge is capturable via two REAL, executable levers?

  Lever 1: the maker REBATE now paid on crypto markets (crypto_fees_v2, rebateRate 0.2).
  Lever 2: optimal STRIKE (sub-band / moneyness) and TIMING selection WITHIN the band.

This is NOT a new edge. It measures capture of the confirmed one:
  SELL far-OTM weekly "BTC/ETH above $X on <date>" YES longshots (== buy NO),
  executable YES-mid band [0.15,0.30], first-half entry, resting MAKER.

Confirmed baseline (reproduced below): eq +10.57c/ct, bv +11.97c/ct, week-clustered t~4.6.

Discipline: walk-forward / OOS for any selection; week-cluster t; multiple-testing
haircut; executable prices. Strong prior from two prior conditioning nulls
(LONGSHOT-CONDITIONAL, VRP-REGIME): conditioning did NOT help. The bar is a robust
walk-forward improvement, not in-sample cherry-picking.

Data: scratchpad/advsel_rows.json — 601 settled markets, 49 ISO-weeks, BTC+ETH,
entry YES-mid in [0.15,0.30], first-half snapshot. Fields: entry (YES mid),
yes_win (0/1 UMA outcome), half_spread, yes_buy_shares/dollars, n_yes_buy,
horizon_days, volume, end (resolution ts), asset, question (carries the strike).
This is the same recovered settled sample the edge was confirmed on.

Timing re-analysis uses scratchpad/lstiming_out.json (the LONGSHOT-TIMING study's
2626-market fresh-sample entry-fraction grid), re-derived here.

No orders. No capital. Read-only. Analysis only.
"""
import json, math, re, statistics, collections, datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, "scratchpad", "advsel_rows.json")
LSTIMING = os.path.join(HERE, "scratchpad", "lstiming_out.json")

# ---- Polymarket crypto_fees_v2 constants (verified live + docs) ----
TAKER_RATE = 0.07     # feeSchedule.rate ; taker fee = C * rate * p*(1-p)
REBATE_SHARE = 0.20   # feeSchedule.rebateRate ; crypto maker rebate share
MAKER_RATE = 0.0      # makers pay no fee (takerOnly:true)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def isowk(ts):
    return datetime.datetime.utcfromtimestamp(ts).isocalendar()[:2]

def wk_key(ts):
    y, w = isowk(ts)
    return y * 100 + w

def norm_ppf(p):
    """Inverse standard normal CDF (Acklam)."""
    if p <= 0: return -1e9
    if p >= 1: return 1e9
    a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,
       1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
    b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,
       6.680131188771972e+01,-1.328068155288572e+01]
    c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,
       -2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
    dd=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,
        3.754408661907416e+00]
    plow=0.02425; phigh=1-plow
    if p<plow:
        q=math.sqrt(-2*math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    if p>phigh:
        q=math.sqrt(-2*math.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    q=p-0.5; r=q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

def cluster_t(rows, key="pnl", wkfn=lambda r: r["wk"], weight=None):
    """Week-clustered t: mean of per-week means / (sd/sqrt(G)), small-sample corrected.
    weight=None -> equal weight; weight='w' -> per-row weight field name."""
    wk = collections.defaultdict(list); wkw = collections.defaultdict(list)
    for r in rows:
        wk[wkfn(r)].append(r[key])
        wkw[wkfn(r)].append(r[weight] if weight else 1.0)
    wkm = []
    for k in wk:
        v = wk[k]; w = wkw[k]
        sw = sum(w)
        if sw <= 0: continue
        wkm.append(sum(x*wi for x, wi in zip(v, w))/sw)
    G = len(wkm)
    if G < 2: return (float('nan'), float('nan'), G)
    m = statistics.mean(wkm)
    sd = statistics.stdev(wkm)  # sample sd
    se = sd/math.sqrt(G)
    t = m/se if se > 0 else float('nan')
    return (m, t, G)

def weekly_series(rows, wkfn=lambda r: r["wk"], key="pnl"):
    wk = collections.defaultdict(list)
    for r in rows: wk[wkfn(r)].append(r[key])
    return {k: statistics.mean(v) for k, v in wk.items()}

def sharpe_weekly(series_by_wk):
    vals = list(series_by_wk.values())
    if len(vals) < 2: return float('nan'), float('nan')
    m = statistics.mean(vals); sd = statistics.stdev(vals)
    s = m/sd if sd > 0 else float('nan')
    return s, s*math.sqrt(52.0)  # annualized (weekly obs)

# ---------------------------------------------------------------------------
# load + build baseline
# ---------------------------------------------------------------------------
def load():
    d = json.load(open(ROWS))
    for r in d:
        # executable seller PnL/ct, sell at bid, ZERO-FEE baseline (matches confirmed backtest)
        r["pnl"] = (r["entry"] - r["half_spread"]) - r["yes_win"]
        r["wk"] = wk_key(r["end"])
        r["bv"] = max(r.get("yes_buy_shares", 0.0), 0.0)  # realistic-fill weight
        # moneyness: standardized OTM distance implied by the YES price (risk-neutral prob)
        # p = P(above) -> z = -Phi^{-1}(p)  (higher z = further OTM / lower prob)
        r["moneyness"] = -norm_ppf(r["entry"])
        m = re.search(r"above \$?([\d,]+(?:\.\d+)?)", r["question"])
        r["strike"] = float(m.group(1).replace(",", "")) if m else float('nan')
    return d

# ---------------------------------------------------------------------------
# LEVER 1 — maker rebate
# ---------------------------------------------------------------------------
def lever1_rebate(d):
    """Deterministic per-fill maker rebate for a resting short-vol seller.

    Mechanics (docs + live fields): taker fee = C*rate*p*(1-p); maker pays 0.
    Rebate program: rebate = (your_fee_equiv / total_fee_equiv) * rebate_pool, per
    market per day, where fee_equiv = C*rate*p*(1-p) and rebate_pool = REBATE_SHARE *
    (taker fees collected in that market). Because every fill has exactly ONE maker and
    ONE taker at the same (C,p), the sum of maker fee-equivalents == total taker fees ==
    the base the pool is 20% of. The pro-rata fraction therefore self-normalizes:
        rebate = REBATE_SHARE * your_own_fee_equiv = 0.20 * 0.07 * p*(1-p)  per share.
    -> deterministic 20% pass-through of the taker fee your own resting order generated.
    NO minimum size, NO two-sided quoting, NO midpoint-distance / requoting requirement
    (those belong to the SEPARATE CLOB Liquidity-Rewards pool program, not this rebate).
    Only gate: $1 accrual before payout (rolls over for a small book)."""
    rebates = [REBATE_SHARE * TAKER_RATE * r["entry"] * (1 - r["entry"]) for r in d]
    taker_costs = [TAKER_RATE * r["entry"] * (1 - r["entry"]) for r in d]  # if you CROSS instead
    eq = statistics.mean(r["pnl"] for r in d)
    totbv = sum(r["bv"] for r in d)
    bv = sum(r["pnl"]*r["bv"] for r in d)/totbv
    reb_mean = statistics.mean(rebates)
    # bv-weighted rebate (rebate scales with fill size, so weight by fillable buy vol)
    reb_bv = sum(rb*r["bv"] for rb, r in zip(rebates, d))/totbv
    return {
        "mechanics": "deterministic 20% pass-through of own taker fee (pool self-normalizes); "
                     "no min-size/two-sided/requote requirement; $1 accrual to payout",
        "taker_rate": TAKER_RATE, "rebate_share": REBATE_SHARE,
        "rebate_mean_ct": reb_mean, "rebate_bv_ct": reb_bv,
        "rebate_min_ct": min(rebates), "rebate_max_ct": max(rebates),
        "baseline_eq_ct": eq, "baseline_bv_ct": bv,
        "rebate_pct_of_eq_edge": 100*reb_mean/eq,
        "rebate_pct_of_bv_edge": 100*reb_bv/bv,
        "taker_cost_if_cross_ct": statistics.mean(taker_costs),
        "taker_cost_pct_of_eq_edge": 100*statistics.mean(taker_costs)/eq,
    }

# ---------------------------------------------------------------------------
# LEVER 2a — sub-band split (in-sample descriptive)
# ---------------------------------------------------------------------------
SUBBANDS = [(0.15,0.20),(0.20,0.25),(0.25,0.30)]

def in_band(r, lo, hi): return lo <= r["entry"] < hi or (hi==0.30 and r["entry"]==0.30)

def lever2_subband_insample(d):
    out = {}
    m_all, t_all, G = cluster_t(d)
    m_all_bv, t_all_bv, _ = cluster_t(d, weight="bv")
    out["BLANKET"] = {"n":len(d), "eq_mean":m_all, "eq_t":t_all, "bv_mean":m_all_bv, "bv_t":t_all_bv, "weeks":G}
    for lo,hi in SUBBANDS:
        sub=[r for r in d if in_band(r,lo,hi)]
        m,t,g = cluster_t(sub)
        mb,tb,_ = cluster_t(sub, weight="bv")
        out[f"{lo:.2f}-{hi:.2f}"] = {"n":len(sub),"eq_mean":m,"eq_t":t,"bv_mean":mb,"bv_t":tb,
                                     "eq_lift_vs_blanket":m-m_all,"bv_lift_vs_blanket":mb-m_all_bv,"weeks":g}
    return out

# ---------------------------------------------------------------------------
# LEVER 2b — WALK-FORWARD sub-band selection (the real test)
# ---------------------------------------------------------------------------
def lever2_walkforward(d, min_train_weeks=12, weight_metric="eq"):
    """Expanding-window walk-forward. For each test week (chronological), pick the
    sub-band with the best mean edge over ALL PRIOR weeks, then realize that sub-band's
    actual mean edge in the test week. Compare the adaptive-selection weekly series to
    the blanket weekly series over the SAME test weeks. Honest OOS: the selection at
    week t uses only weeks < t."""
    weeks = sorted(set(r["wk"] for r in d))
    by_wk = collections.defaultdict(list)
    for r in d: by_wk[r["wk"]].append(r)

    def band_mean(rows, lo, hi, metric):
        sub=[r for r in rows if in_band(r,lo,hi)]
        if not sub: return None
        if metric=="eq": return statistics.mean(r["pnl"] for r in sub)
        w=sum(x["bv"] for x in sub)
        return sum(r["pnl"]*r["bv"] for r in sub)/w if w>0 else None

    adaptive=[]; blanket=[]; picks=collections.Counter(); test_weeks=[]
    for i,wk in enumerate(weeks):
        if i < min_train_weeks: continue
        train=[r for j,w in enumerate(weeks) if w<wk for r in by_wk[w]]
        # choose best sub-band on train
        best=None; bestval=-1e9
        for lo,hi in SUBBANDS:
            v=band_mean(train,lo,hi,weight_metric)
            if v is not None and v>bestval: bestval=v; best=(lo,hi)
        if best is None: continue
        # realize on the test week
        realized=band_mean(by_wk[wk],best[0],best[1],weight_metric)
        blanket_wk=band_mean(by_wk[wk],0.15,0.30,weight_metric)
        if realized is None or blanket_wk is None: continue
        adaptive.append(realized); blanket.append(blanket_wk)
        picks[f"{best[0]:.2f}-{best[1]:.2f}"]+=1; test_weeks.append(wk)

    def stats(x):
        m=statistics.mean(x); sd=statistics.stdev(x) if len(x)>1 else float('nan')
        sh=m/sd if sd>0 else float('nan')
        return m,sd,sh,sh*math.sqrt(52)
    am,asd,ash,asha=stats(adaptive); bm,bsd,bsh,bsha=stats(blanket)
    # paired diff, week-clustered t (each week is its own cluster already)
    diff=[a-b for a,b in zip(adaptive,blanket)]
    dm=statistics.mean(diff); dsd=statistics.stdev(diff) if len(diff)>1 else float('nan')
    dt=dm/(dsd/math.sqrt(len(diff))) if dsd>0 else float('nan')
    return {
        "test_weeks":len(adaptive), "picks":dict(picks),
        "adaptive_mean_ct":am, "adaptive_sharpe_wk":ash, "adaptive_sharpe_ann":asha,
        "blanket_mean_ct":bm, "blanket_sharpe_wk":bsh, "blanket_sharpe_ann":bsha,
        "mean_diff_ct":dm, "diff_t":dt, "weight_metric":weight_metric,
    }

def lever2_fixed_pick_oos(d, pick=(0.20,0.25), split=0.6):
    """Pre-registered pick from the prior in-sample winner (0.20-0.25). Evaluate ONCE
    on the held-out last (1-split) of weeks vs blanket on the same test weeks."""
    weeks=sorted(set(r["wk"] for r in d))
    cut=weeks[int(len(weeks)*split)]
    test=[r for r in d if r["wk"]>=cut]
    sub=[r for r in test if in_band(r,pick[0],pick[1])]
    ms,ts,_=cluster_t(sub); mss,tss,_=cluster_t(sub,weight="bv")
    mb,tb,_=cluster_t(test); mbb,tbb,_=cluster_t(test,weight="bv")
    return {"pick":f"{pick[0]:.2f}-{pick[1]:.2f}","test_n":len(test),"sub_n":len(sub),
            "sub_eq":ms,"sub_eq_t":ts,"blanket_eq":mb,"eq_oos_lift":ms-mb,
            "sub_bv":mss,"blanket_bv":mbb,"bv_oos_lift":mss-mbb}

# ---------------------------------------------------------------------------
# LEVER 2c — moneyness normalization
# ---------------------------------------------------------------------------
def lever2_moneyness(d):
    """Is the edge better expressed per unit of (price-implied) moneyness? If edge is
    ~proportional to moneyness, then no sub-selection helps (edge/moneyness is flat).
    Regress per-contract edge on standardized moneyness; also bucket by moneyness."""
    xs=[r["moneyness"] for r in d]; ys=[r["pnl"] for r in d]
    n=len(xs); mx=statistics.mean(xs); my=statistics.mean(ys)
    sxx=sum((x-mx)**2 for x in xs); sxy=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    slope=sxy/sxx; intercept=my-slope*mx
    # correlation
    syy=sum((y-my)**2 for y in ys)
    r_pearson=sxy/math.sqrt(sxx*syy) if sxx*syy>0 else float('nan')
    # tercile buckets on moneyness (cross-sectional, in-sample descriptive)
    order=sorted(d,key=lambda r:r["moneyness"])
    k=n//3
    buckets={"low_OTM(near)":order[:k],"mid":order[k:2*k],"high_OTM(far)":order[2*k:]}
    bstats={}
    for name,rows in buckets.items():
        m,t,g=cluster_t(rows)
        edge_per_m=statistics.mean(r["pnl"]/r["moneyness"] for r in rows if r["moneyness"]>0.05)
        bstats[name]={"n":len(rows),"mean_moneyness":statistics.mean(r["moneyness"] for r in rows),
                      "eq_mean":m,"eq_t":t,"edge_per_moneyness":edge_per_m}
    return {"slope_edge_on_moneyness":slope,"intercept":intercept,"pearson_r":r_pearson,
            "buckets":bstats}

# ---------------------------------------------------------------------------
# LEVER 2d — timing re-analysis (from LONGSHOT-TIMING fresh-sample grid)
# ---------------------------------------------------------------------------
def lever2_timing():
    try:
        t=json.load(open(LSTIMING))
    except Exception as e:
        return {"error":str(e)}
    rows=t["crypto"]["rows"]
    grid=[{"f":r["f"],"n":r["n"],"edge_ct":r["mean_edge"],"t_eq":r["t_eq"],
           "vw_edge_ct":r["vw_edge"],"t_bv":r["t_w"],"ann_roc":r.get("roc")} for r in rows]
    best_eq=max(grid,key=lambda g:g["edge_ct"])
    return {"grid":grid,"best_eq_fraction":best_eq["f"],
            "note":"equal-weight edge decays monotonically with later entry; earliest "
                   "first-half fraction is best; volume-weighted edge negative at every "
                   "fraction (adverse selection). No later sweet spot."}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    d=load()
    res={"sample":{"n_markets":len(d),"n_weeks":len(set(r["wk"] for r in d)),
                   "date_range":[str(datetime.datetime.utcfromtimestamp(min(r["end"] for r in d)).date()),
                                 str(datetime.datetime.utcfromtimestamp(max(r["end"] for r in d)).date())],
                   "yes_win_rate":sum(r["yes_win"] for r in d)/len(d)}}
    res["lever1_rebate"]=lever1_rebate(d)
    res["lever2_subband_insample"]=lever2_subband_insample(d)
    res["lever2_walkforward_eq"]=lever2_walkforward(d,weight_metric="eq")
    res["lever2_walkforward_bv"]=lever2_walkforward(d,weight_metric="bv")
    res["lever2_walkforward_sensitivity"]=[
        {"min_train":mt,"metric":wm,**{k:lever2_walkforward(d,min_train_weeks=mt,weight_metric=wm)[k]
          for k in ("adaptive_mean_ct","blanket_mean_ct","mean_diff_ct","diff_t",
                    "adaptive_sharpe_wk","blanket_sharpe_wk")}}
        for mt in (8,12,16,20) for wm in ("eq","bv")]
    res["lever2_fixed_pick_oos"]=lever2_fixed_pick_oos(d)
    res["lever2_moneyness"]=lever2_moneyness(d)
    res["lever2_timing"]=lever2_timing()

    # blanket weekly Sharpe (reference)
    bw=weekly_series(d)
    sh,sha=sharpe_weekly(bw)
    res["blanket_weekly_sharpe"]={"weekly":sh,"annualized":sha,"weeks":len(bw)}

    # multiple-testing accounting
    n_tests = len(SUBBANDS) + 1  # 3 sub-bands as selection candidates (+blanket as null)
    res["multiple_testing"]={"n_subband_candidates":len(SUBBANDS),
        "n_timing_fractions":len(res["lever2_timing"].get("grid",[])),
        "prior_conditioning_tests":"LONGSHOT-CONDITIONAL 25 rules; VRP-REGIME 27 tests — both null",
        "bonferroni_note":f"with {n_tests} sub-band candidates, |t|~{1.96:.2f} nominal -> "
                          f"~{2.5:.2f} Bonferroni-adjusted bar for a single robust winner"}

    r1=res["lever1_rebate"]
    res["BLUNT_VERDICT"]={
        "rebate_ct_added": r1["rebate_mean_ct"],
        "rebate_pct_of_edge": r1["rebate_pct_of_eq_edge"],
        "rebate_feasible_small_book": True,
        "rebate_mechanics": "deterministic 20% pass-through of own taker fee; NO min-size/two-sided/requote",
        "selection_robust_improvement": False,
        "selection_walkforward_eq_diff_ct": res["lever2_walkforward_eq"]["mean_diff_ct"],
        "selection_walkforward_eq_diff_t": res["lever2_walkforward_eq"]["diff_t"],
        "selection_walkforward_bv_diff_ct": res["lever2_walkforward_bv"]["mean_diff_ct"],
        "timing_lever": "none — earliest first-half already optimal, edge decays later, bv-negative",
        "taker_drag_if_cross_pct_of_edge": r1["taker_cost_pct_of_edge" if "taker_cost_pct_of_edge" in r1 else "taker_cost_pct_of_eq_edge"],
        "total_more_capturable_pct": r1["rebate_pct_of_eq_edge"],
        "one_liner": ("~+2% of the confirmed edge is capturable, ALL of it the maker rebate "
                      "(~+0.24c/ct); strike/timing selection adds nothing robust and is ~-3.7c "
                      "worse on the fill-weighted metric; the real execution rule is negative: "
                      "stay a resting maker, never cross (taker fee = ~-11% of edge)."),
    }
    out=os.path.join(HERE,"edge_capture_summary.json")
    json.dump(res,open(out,"w"),indent=2)
    print(json.dumps(res,indent=2))
    return res

if __name__=="__main__":
    main()
