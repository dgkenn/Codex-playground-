"""NEW informed-flow detectors for the Kalshi box-maker vs the VPIN incumbent.
Causal features from trades up to decision minute k=7; label = STRANDED window
(exactly one box leg fills in the k+1..k+2 fill window, front-of-queue q0=0).
Faithful to collect_fills / box_policy_ab conventions. Run synchronously; compact output."""
import numpy as np, pandas as pd, sys
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

K = 7                     # decision minute
ASSETS = ["btc", "eth", "sol", "xrp"]
ROUND_LOTS = {1, 5, 10, 25, 50, 100}   # raw-lot round sizes (sz*100)

# ---------- VPIN (reimplemented exactly from box_policy_ab) ----------
def vpin_buckets(t, sz, buy, n=20):
    if len(t) < n: return np.array([]), np.array([])
    V = float(sz.sum()) / n
    if V <= 0: return np.array([]), np.array([])
    bt, bi = [], []; vb = vs = 0.0
    for i in range(len(t)):
        if buy[i]: vb += sz[i]
        else: vs += sz[i]
        if vb + vs >= V:
            bt.append(t[i]); bi.append(abs(vb - vs) / (vb + vs)); vb = vs = 0.0
    return np.array(bt), np.array(bi)

def vpin_at(bt, bi, tt, smooth=5):
    if len(bt) == 0: return np.nan
    j = int(np.searchsorted(bt, tt))
    if j < 1: return np.nan
    return float(np.mean(bi[max(0, j - smooth):j]))

# ---------- NEW detectors (causal, trades with t < ws + 60*K) ----------
def detectors(ws, t, p, sz, buy):
    """Return dict of NEW detector features from causal pre-k trades. t,p,sz,buy already masked t<ws+60K."""
    n = len(t)
    out = dict(d1_maxrun=0.0, d1_signrun=0.0, d1_nruns=np.nan,
               d2_lambda=np.nan, d3_burst_cv=np.nan, d4_roundfrac=np.nan,
               d4_topsize_rep=np.nan, d5_sweep=np.nan, take_n=float(n))
    if n < 5:
        return out
    sgn = np.where(buy, 1, -1)
    # --- D1 aggressor runs / persistence ---
    runs = []  # signed run lengths
    cur = sgn[0]; ln = 1
    for i in range(1, n):
        if sgn[i] == cur: ln += 1
        else: runs.append(cur * ln); cur = sgn[i]; ln = 1
    runs.append(cur * ln)
    runs = np.array(runs)
    out["d1_maxrun"] = float(np.max(np.abs(runs)))
    # signed dominant run length (longest run with its direction sign)
    out["d1_signrun"] = float(runs[np.argmax(np.abs(runs))])
    out["d1_nruns"] = float(len(runs)) / n      # low = persistent (informed), high = alternating (retail)
    # --- D2 Kyle's lambda: |dp| ~ |signed vol| ; use slope of regression of dp on signed sz ---
    dp = np.diff(p)
    sv = (sgn * sz)[1:]                          # signed volume aligned to dp
    if np.std(sv) > 1e-9 and len(dp) >= 5:
        # lambda = cov(dp, sv)/var(sv) (price impact per signed contract)
        lam = np.cov(sv, dp)[0, 1] / np.var(sv)
        out["d2_lambda"] = float(abs(lam) * 1e3)    # scale to cents/k-contract-ish
    # --- D3 take burstiness: CV of inter-take times (clustered = informed reacting to signal) ---
    dt = np.diff(np.sort(t))
    dt = dt[dt >= 0]
    if len(dt) >= 4 and dt.mean() > 1e-9:
        out["d3_burst_cv"] = float(dt.std() / dt.mean())
    # --- D4 size roundness / repetition (algo footprint, the size-19 finding) ---
    lots = np.round(sz * 100).astype(int)        # raw lots
    valid = lots > 0
    if valid.sum() >= 5:
        lv = lots[valid]
        out["d4_roundfrac"] = float(np.mean([l in ROUND_LOTS for l in lv]))
        # top single-size repetition share (1 - roundness style: one odd size dominating = algo)
        vals, cnts = np.unique(lv, return_counts=True)
        top = vals[np.argmax(cnts)]
        topshare = cnts.max() / len(lv)
        # algo signal = a NON-round size repeating heavily
        out["d4_topsize_rep"] = float(topshare if top not in ROUND_LOTS else 0.0)
    # --- D5 sweep depth: consecutive same-dir takes at worsening prices (urgency) ---
    # for buys: price increasing; for sells: price decreasing, within same-dir runs
    sweep = 0
    i = 0
    while i < n - 1:
        d = sgn[i]; j = i + 1; worse = 0
        while j < n and sgn[j] == d:
            if (d > 0 and p[j] > p[j-1] + 1e-9) or (d < 0 and p[j] < p[j-1] - 1e-9):
                worse += 1
            j += 1
        sweep = max(sweep, worse)
        i = j if j > i else i + 1
    out["d5_sweep"] = float(sweep)
    return out

# ---------- per-window label + features ----------
def build(asset):
    hist = pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
    tap = pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws")
    common = sorted(set(hist.index) & set(tap.index))
    rows = []
    for w in common:
        h = hist.loc[w]; t = tap.loc[w]
        bid = np.asarray(h.bid_path, float); ask = np.asarray(h.ask_path, float)
        mid = np.asarray(h.mid_path, float)
        b0, a0 = bid[K], ask[K]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
            continue
        t_arr = np.asarray(t.t, float); p_arr = np.asarray(t.p, float)
        sz_arr = np.asarray(t.sz, float); buy_arr = np.asarray(t.buy, bool)
        # --- fill sim: minutes K+1..K+2, front-of-queue (q0=0) ---
        lo, hi = w + 60 * (K + 1), w + 60 * (K + 2)
        i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
        done_b = done_a = False
        for i in range(i0, i1):
            if done_b and done_a: break
            p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
            if not done_b and not buy and p <= b0 + 1e-9: done_b = True
            if not done_a and buy and p >= a0 - 1e-9: done_a = True
        stranded = int(done_b != done_a)          # XOR: exactly one leg filled
        any_fill = int(done_b or done_a)
        if not any_fill:                           # no trading at our quotes => not a box opportunity
            continue
        # --- VPIN at decision (clock = end of minute K) ---
        bt, bi = vpin_buckets(t_arr, sz_arr, buy_arr)
        vp = vpin_at(bt, bi, w + 60 * K)
        # --- NEW detectors: causal trades t < ws + 60*K ---
        msk = t_arr < (w + 60 * K)
        d = detectors(w, t_arr[msk], p_arr[msk], sz_arr[msk], buy_arr[msk])
        rec = dict(ws=w, asset=asset, stranded=stranded, vpin=vp, **d)
        rows.append(rec)
    return pd.DataFrame(rows)

def safe_auc(y, x):
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 30 or len(np.unique(y[m])) < 2: return np.nan, int(m.sum())
    xx = x[m].copy()
    # auc is invariant to direction; report max(auc, 1-auc) with sign note handled by caller
    return float(roc_auc_score(y[m], xx)), int(m.sum())

def main():
    dfs = [build(a) for a in ASSETS]
    df = pd.concat(dfs, ignore_index=True)
    print(f"=== POOLED windows n={len(df)} | strand rate={df.stranded.mean():.3f} | "
          f"vpin-present={df.vpin.notna().mean():.2f} ===")
    for a in ASSETS:
        s = df[df.asset == a]
        print(f"  {a}: n={len(s)} strand={s.stranded.mean():.3f}")

    # IS/OOS split 60/40 by ws (time-ordered)
    df = df.sort_values("ws").reset_index(drop=True)
    cut = int(len(df) * 0.6)
    IS, OOS = df.iloc[:cut], df.iloc[cut:]
    yI, yO = IS.stranded.values.astype(float), OOS.stranded.values.astype(float)
    print(f"\nsplit: IS n={len(IS)} (strand {yI.mean():.3f}) | OOS n={len(OOS)} (strand {yO.mean():.3f})")

    DET = ["vpin", "d1_maxrun", "d1_signrun", "d1_nruns", "d2_lambda",
           "d3_burst_cv", "d4_roundfrac", "d4_topsize_rep", "d5_sweep", "take_n"]
    # --- univariate OOS AUC ranking (direction-agnostic: report signed) ---
    print("\n=== UNIVARIATE OOS AUC (single-feature logistic, fit IS) ===")
    rank = []
    for c in DET:
        mI = IS[c].notna().values; mO = OOS[c].notna().values
        if mI.sum() < 50 or mO.sum() < 50:
            print(f"  {c:14s} skip (n too small)"); continue
        sc = StandardScaler()
        XI = sc.fit_transform(IS.loc[mI, [c]].values)
        XO = sc.transform(OOS.loc[mO, [c]].values)
        lr = LogisticRegression(max_iter=500).fit(XI, yI[mI])
        pr = lr.predict_proba(XO)[:, 1]
        auc = roc_auc_score(yO[mO], pr) if len(np.unique(yO[mO])) > 1 else np.nan
        rank.append((c, auc, int(mO.sum())))
    for c, auc, n in sorted(rank, key=lambda x: -(x[1] if not np.isnan(x[1]) else 0)):
        tag = " <-- VPIN" if c == "vpin" else ""
        print(f"  {c:14s} AUC={auc:.3f}  n={n}{tag}")
    vpin_auc = dict((c, a) for c, a, _ in rank).get("vpin", np.nan)

    # --- correlation with VPIN (independence) ---
    print("\n=== corr with VPIN (Pearson, |low|=independent) ===")
    base = df.dropna(subset=["vpin"])
    for c in DET:
        if c == "vpin": continue
        bb = base.dropna(subset=[c])
        if len(bb) < 50: continue
        r = np.corrcoef(bb["vpin"], bb[c])[0, 1]
        print(f"  {c:14s} r={r:+.3f}  (n={len(bb)})")

    # --- incremental: VPIN+detector vs VPIN-alone OOS AUC ---
    print("\n=== INCREMENTAL: OOS AUC of [VPIN + detector] vs VPIN-alone ===")
    def fit_auc(cols):
        mI = IS[cols].notna().all(axis=1).values & ~np.isnan(yI)
        mO = OOS[cols].notna().all(axis=1).values & ~np.isnan(yO)
        if mI.sum() < 50 or mO.sum() < 50 or len(np.unique(yI[mI])) < 2: return np.nan, 0
        sc = StandardScaler()
        XI = sc.fit_transform(IS.loc[mI, cols].values); XO = sc.transform(OOS.loc[mO, cols].values)
        lr = LogisticRegression(max_iter=500).fit(XI, yI[mI])
        pr = lr.predict_proba(XO)[:, 1]
        if len(np.unique(yO[mO])) < 2: return np.nan, int(mO.sum())
        return float(roc_auc_score(yO[mO], pr)), int(mO.sum())
    va, vn = fit_auc(["vpin"])
    print(f"  VPIN-alone OOS AUC={va:.3f} (n={vn})")
    addtbl = []
    for c in DET:
        if c == "vpin": continue
        auc2, n2 = fit_auc(["vpin", c])
        if np.isnan(auc2): continue
        addtbl.append((c, auc2, auc2 - va, n2))
    for c, auc2, delta, n2 in sorted(addtbl, key=lambda x: -x[2]):
        flag = "ADDS" if delta > 0.005 else ("~flat" if delta > -0.005 else "redundant/worse")
        print(f"  +{c:14s} AUC={auc2:.3f}  d={delta:+.3f}  n={n2}  {flag}")

    # --- best combined: VPIN + additive detectors ---
    additive = [c for c, _, d, _ in addtbl if d > 0.005]
    print(f"\n=== BEST COMBINED: VPIN + {additive} ===")
    combo = ["vpin"] + additive if additive else ["vpin"]
    ca, cn = fit_auc(combo)
    print(f"  combined OOS AUC={ca:.3f} (n={cn})  vs VPIN-alone {va:.3f}  gain={ca-va:+.3f}")

    # --- economic gate test: strand rate at equal volume kept ---
    print("\n=== ECONOMIC GATE (OOS): strand rate among KEPT windows at equal keep-fraction ===")
    def gate_eval(score_oos, keep_frac):
        m = ~np.isnan(score_oos)
        s = score_oos[m]; yy = yO[m]
        thr = np.quantile(s, keep_frac)          # keep LOW-toxicity windows (below threshold)
        kept = s <= thr
        return yy[kept].mean(), kept.mean(), int(m.sum())
    # build OOS scores for vpin-alone and combined using fitted models
    def model_scores(cols):
        mI = IS[cols].notna().all(axis=1).values & ~np.isnan(yI)
        sc = StandardScaler(); XI = sc.fit_transform(IS.loc[mI, cols].values)
        lr = LogisticRegression(max_iter=500).fit(XI, yI[mI])
        out = np.full(len(OOS), np.nan)
        mO = OOS[cols].notna().all(axis=1).values
        out[mO] = lr.predict_proba(sc.transform(OOS.loc[mO, cols].values))[:, 1]
        return out
    sv_ = model_scores(["vpin"]); sc_ = model_scores(combo)
    base_strand = yO[~np.isnan(sv_)].mean()
    print(f"  OOS baseline strand (all kept) = {base_strand:.3f}")
    for kf in [0.5, 0.7, 0.85]:
        vr, vk, vn2 = gate_eval(sv_, kf)
        cr, ck, cn2 = gate_eval(sc_, kf)
        print(f"  keep~{kf:.0%}: VPIN strand={vr:.3f}(kept {vk:.0%}) | COMBO strand={cr:.3f}(kept {ck:.0%})  n={vn2}")

if __name__ == "__main__":
    main()
