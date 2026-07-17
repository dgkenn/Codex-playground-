#!/usr/bin/env python3
"""
Predictive model for STRANDED BOXES in the Kalshi 15-minute box-making strategy.

A "box" quotes two legs (up/down). A STRAND = one leg fills, the other doesn't,
leaving an unhedged directional position (a loss). We model P(strand | causal
features observed at the box decision instant) so we can veto quotes likely to
strand -- both to improve the (marginal, halted) box-maker and, more usefully,
as an execution risk-filter for a riskless multi-leg bucket-arb.

Data source: git branch origin/gha-data, read via `git show`.
  LABELS : gha_data/<day>/box_shadow_<asset>15m.jsonl  (plain jsonl)
           one row per (window, arm); we model the 'live' base arm (no veto),
           label = `stranded`.
  FEATURES: gha_data/<day>/ticks_kalshi_<asset>15m_*.jsonl.gz  (gzipped)
           each line: {ws, role, ticks:[[t,mid,spot,micro,bid,bidq,ask,askq],...]}
           A window's full tick stream is split across many run-files; we
           aggregate all run-files for a day+asset by ws, then build CAUSAL
           features using only ticks with t <= DECISION_T (720s).

No post-decision information is used. OOS split is by time (earliest days train,
recent days test). Small sample -> we report n, strand base rate, and a
bootstrap AUC CI, and stay honest about lift vs simple heuristics.
"""
import subprocess, gzip, json, math, collections, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

BRANCH = "origin/gha-data"
ASSETS = ["btc", "eth"]
DECISION_T = 720.0        # decision instant: last tick with t <= 720s of the 900s window
BASE_ARM = "live"         # most-populated non-veto arm -> raw strand behaviour
HEUR_ARMS = ["thickbook_veto", "volgate", "nsmove"]
RECENT_MOVE_WIN = 60.0    # seconds for "recent spot move" feature

def git_show(path):
    return subprocess.run(["git", "show", f"{BRANCH}:{path}"], capture_output=True).stdout

def list_day_files(day):
    out = subprocess.run(["git", "ls-tree", f"{BRANCH}:gha_data/{day}", "--name-only"],
                         capture_output=True, text=True).stdout
    return out.split()

def label_days():
    days = subprocess.run(["git", "ls-tree", f"{BRANCH}:gha_data", "--name-only"],
                          capture_output=True, text=True).stdout.split()
    days = [d for d in days if d.startswith("2026-")]
    out = []
    for d in days:
        fs = list_day_files(d)
        if any(f == "box_shadow_btc15m.jsonl" for f in fs):
            out.append(d)
    return sorted(out)

# ---------------------------------------------------------------- labels
def load_labels(day, asset):
    """Return dict ws -> {'live_stranded','live_locked_good', heur veto/strand flags}."""
    raw = git_show(f"gha_data/{day}/box_shadow_{asset}15m.jsonl")
    rows = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
    byws = collections.defaultdict(dict)
    for r in rows:
        byws[r["ws"]][r["arm"]] = r
    out = {}
    for ws, arms in byws.items():
        if BASE_ARM not in arms:
            continue
        live = arms[BASE_ARM]
        if not live.get("filled"):
            continue  # live arm quotes/fills essentially every window; require a fill
        d = {
            "stranded": bool(live.get("stranded")),
            "locked_good": bool(live.get("filled")) and not bool(live.get("stranded")),
        }
        for h in HEUR_ARMS:
            a = arms.get(h)
            if a is None:
                d[f"{h}_veto"] = None
                d[f"{h}_strand"] = None
            else:
                d[f"{h}_veto"] = (not a.get("filled"))      # heuristic skipped the window
                d[f"{h}_strand"] = bool(a.get("stranded"))  # stranded if it did quote
        out[ws] = d
    return out

# ---------------------------------------------------------------- ticks -> features
def load_ticks(day, asset):
    """Aggregate all run-files for day+asset -> dict ws -> sorted list of ticks."""
    fs = [f for f in list_day_files(day) if f.startswith(f"ticks_kalshi_{asset}15m_")]
    byws = collections.defaultdict(list)
    for f in fs:
        raw = git_show(f"gha_data/{day}/{f}")
        try:
            txt = gzip.decompress(raw).decode()
        except Exception:
            continue
        for l in txt.splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            byws[r["ws"]].extend(r["ticks"])
    for ws in byws:
        byws[ws].sort(key=lambda t: t[0])
    return byws

def realized_vol(spots):
    if len(spots) < 3:
        return None
    rets = []
    for i in range(1, len(spots)):
        p0, p1 = spots[i-1], spots[i]
        if p0 and p1 and p0 > 0 and p1 > 0:
            rets.append(math.log(p1/p0))
    if len(rets) < 2:
        return None
    return float(np.std(rets))

def build_features(ticks):
    """Causal features from ticks with t <= DECISION_T. Returns dict or None."""
    caus = [t for t in ticks if t[0] <= DECISION_T]
    if not caus:
        return None
    # decision tick = last tick <= 720
    t, mid, spot, micro, bid, bidq, ask, askq = caus[-1]
    depth = (bidq or 0) + (askq or 0)
    imb = ((bidq - askq) / depth) if depth > 0 else 0.0
    spread = (ask - bid) if (ask is not None and bid is not None) else np.nan
    mid_dist_05 = abs(mid - 0.5) if mid is not None else np.nan
    micro_skew = (micro - mid) if (micro is not None and mid is not None) else 0.0
    # strike proxy = open spot = earliest tick's spot
    open_spot = ticks[0][2]
    rel_strike = abs(spot - open_spot) / open_spot if open_spot else np.nan
    # causal realized vol of spot over ticks <= 720
    spots = [x[2] for x in caus if x[2]]
    rvol = realized_vol(spots)
    # recent spot move over ~last 60s before decision
    dec_time = t
    prior = [x for x in caus if x[0] <= dec_time - RECENT_MOVE_WIN]
    if prior:
        s_prev = prior[-1][2]
        recent_move = abs(spot - s_prev) / spot if (spot and s_prev) else 0.0
    else:
        recent_move = 0.0
    hour = (caus[-1] and 0)  # placeholder; hour set by caller from ws
    return {
        "spread": spread,
        "log_depth": math.log1p(depth),
        "imbalance": imb,
        "abs_imbalance": abs(imb),
        "mid_dist_05": mid_dist_05,
        "micro_skew": micro_skew,
        "rel_strike": rel_strike,
        "rvol": rvol,               # may be None -> imputed later
        "recent_move": recent_move,
        "n_ticks_causal": len(caus),
        "_depth": depth,            # raw, for heuristic replication / diagnostics
    }

FEATURES = ["spread", "log_depth", "imbalance", "abs_imbalance", "mid_dist_05",
            "micro_skew", "rel_strike", "rvol", "recent_move", "n_ticks_causal",
            "hour", "is_eth"]

# ---------------------------------------------------------------- assemble dataset
def assemble():
    days = label_days()
    print(f"[info] label days ({len(days)}): {days[0]}..{days[-1]}", file=sys.stderr)
    rows = []
    for day in days:
        for asset in ASSETS:
            labs = load_labels(day, asset)
            if not labs:
                continue
            ticks = load_ticks(day, asset)
            for ws, lab in labs.items():
                tk = ticks.get(ws)
                if not tk:
                    continue
                feat = build_features(tk)
                if feat is None:
                    continue
                feat["hour"] = (ws // 3600) % 24
                feat["is_eth"] = 1.0 if asset == "eth" else 0.0
                rec = {"day": day, "asset": asset, "ws": ws,
                       "y": 1 if lab["stranded"] else 0}
                rec.update({k: feat[k] for k in feat})
                rec.update({k: lab[k] for k in lab})
                rows.append(rec)
    return days, rows

def impute(rows):
    # median-impute rvol / spread NaN using TRAIN-visible medians would be ideal;
    # given tiny n we impute with global median but note it in the report.
    for col in ["rvol", "spread", "rel_strike", "mid_dist_05"]:
        vals = [r[col] for r in rows if r.get(col) is not None and not (isinstance(r[col], float) and math.isnan(r[col]))]
        med = float(np.median(vals)) if vals else 0.0
        for r in rows:
            v = r.get(col)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                r[col] = med
    return rows

def Xy(rows):
    X = np.array([[float(r[f]) for f in FEATURES] for r in rows], float)
    y = np.array([r["y"] for r in rows], int)
    return X, y

def boot_auc_ci(y, p, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y)); aucs = []
    for _ in range(n):
        s = rng.choice(idx, len(idx), replace=True)
        if len(np.unique(y[s])) < 2:
            continue
        aucs.append(roc_auc_score(y[s], p[s]))
    if not aucs:
        return (float("nan"), float("nan"))
    return (float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5)))

def calibration_table(y, p, bins=5):
    order = np.argsort(p)
    y, p = y[order], p[order]
    out = []
    for b in np.array_split(np.arange(len(y)), bins):
        if len(b) == 0:
            continue
        out.append((float(p[b].mean()), float(y[b].mean()), len(b)))
    return out

def main():
    days, rows = assemble()
    rows = impute(rows)
    n = len(rows); npos = sum(r["y"] for r in rows)
    print(f"[info] joined windows n={n}, strands={npos}, base rate={npos/n:.3%}", file=sys.stderr)

    # ---- time-OOS split: earliest ~70% of days train, recent ~30% test
    ndays = len(days)
    cut = max(1, int(round(ndays * 0.70)))
    train_days, test_days = set(days[:cut]), set(days[cut:])
    tr = [r for r in rows if r["day"] in train_days]
    te = [r for r in rows if r["day"] in test_days]
    Xtr, ytr = Xy(tr); Xte, yte = Xy(te)

    scaler = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = scaler.transform(Xtr), scaler.transform(Xte)

    # ---- logistic regression (L2, class-balanced)
    logit = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    logit.fit(Xtr_s, ytr)
    p_lr = logit.predict_proba(Xte_s)[:, 1]
    auc_lr = roc_auc_score(yte, p_lr)
    ci_lr = boot_auc_ci(yte, p_lr)

    # ---- gradient-boosted trees
    gbt = HistGradientBoostingClassifier(max_depth=3, max_iter=200,
                                         learning_rate=0.05, l2_regularization=1.0,
                                         min_samples_leaf=20, random_state=0)
    gbt.fit(Xtr, ytr)
    p_gbt = gbt.predict_proba(Xte)[:, 1]
    auc_gbt = roc_auc_score(yte, p_gbt)
    ci_gbt = boot_auc_ci(yte, p_gbt)

    # ---- permutation importance for GBT (OOS)
    from sklearn.inspection import permutation_importance
    perm = permutation_importance(gbt, Xte, yte, n_repeats=30, random_state=0,
                                  scoring="roc_auc")
    gbt_imp = sorted(zip(FEATURES, perm.importances_mean, perm.importances_std),
                     key=lambda z: -z[1])

    coefs = sorted(zip(FEATURES, logit.coef_[0]), key=lambda z: -abs(z[1]))

    # ---- univariate AUC (single-feature discriminative power, OOS)
    uni = []
    for j, f in enumerate(FEATURES):
        col = Xte[:, j]
        if len(np.unique(col)) < 2 or len(np.unique(yte)) < 2:
            uni.append((f, float("nan"))); continue
        a = roc_auc_score(yte, col)
        uni.append((f, max(a, 1 - a)))  # direction-agnostic
    uni.sort(key=lambda z: -(z[1] if not math.isnan(z[1]) else 0))

    # ---------------------------------------------------------------- veto tradeoff
    # Evaluate on the TEST set (OOS). For each policy compute over live-arm windows:
    #   veto_rate    = fraction of windows skipped
    #   strand_rate  = strands among KEPT windows (lower is better)
    #   good_retained= (# good locked fills kept) / (# good locked fills no-veto)
    # Heuristics use their realized arm labels; the model vetoes highest-P windows
    # at the matched veto rate.
    def policy_stats(keep_mask, rows_):
        kept = [r for r, k in zip(rows_, keep_mask) if k]
        n_all = len(rows_)
        n_keep = len(kept)
        strands_kept = sum(r["y"] for r in kept)
        good_kept = sum(1 for r in kept if r["y"] == 0)
        good_total = sum(1 for r in rows_ if r["y"] == 0)
        return {
            "veto_rate": 1 - n_keep / n_all,
            "kept": n_keep,
            "strand_rate": (strands_kept / n_keep) if n_keep else float("nan"),
            "strands_kept": strands_kept,
            "good_retained": (good_kept / good_total) if good_total else float("nan"),
        }

    table = {}
    # no-veto (live)
    table["no-veto"] = policy_stats([True] * len(te), te)
    # heuristics: kept when NOT vetoed by that arm
    heur_veto_rate = {}
    for h in HEUR_ARMS:
        keep = [not bool(r.get(f"{h}_veto")) for r in te]
        table[h] = policy_stats(keep, te)
        heur_veto_rate[h] = table[h]["veto_rate"]
    # score vector for a simple 1-feature rule = |mid - 0.5| (rel_strike is nearly
    # identical); veto the windows most lopsided (highest |mid-0.5|).
    j_mid = FEATURES.index("mid_dist_05")
    simple_score = Xte[:, j_mid]

    # model @ matched veto rate to thickbook_veto (primary heuristic) and to volgate
    for h in ["thickbook_veto", "volgate"]:
        vr = heur_veto_rate[h]
        k = int(round(vr * len(te)))
        def veto_by(score):
            vset = set(np.argsort(-score)[:k].tolist())
            return [i not in vset for i in range(len(te))]
        table[f"model@{h}_rate(GBT)"] = policy_stats(veto_by(p_gbt), te)
        table[f"model@{h}_rate(LR)"] = policy_stats(veto_by(p_lr), te)
        table[f"simple|mid-.5|@{h}_rate"] = policy_stats(veto_by(simple_score), te)

    # ---------------------------------------------------------------- output
    R = {
        "days": days, "train_days": sorted(train_days), "test_days": sorted(test_days),
        "n_total": n, "n_strand": npos, "base_rate": npos / n,
        "n_train": len(tr), "n_train_strand": int(sum(ytr)),
        "n_test": len(te), "n_test_strand": int(sum(yte)),
        "auc_lr": auc_lr, "ci_lr": ci_lr,
        "auc_gbt": auc_gbt, "ci_gbt": ci_gbt,
        "logit_coefs": coefs,
        "gbt_perm_importance": gbt_imp,
        "univariate_auc": uni,
        "calib_lr": calibration_table(yte, p_lr),
        "calib_gbt": calibration_table(yte, p_gbt),
        "veto_table": table,
        "heur_veto_rate": heur_veto_rate,
    }
    import pprint
    print("\n================ STRAND MODEL RESULTS ================")
    print(f"label days: {days[0]}..{days[-1]}  (train {sorted(train_days)} | test {sorted(test_days)})")
    print(f"n_total={n}  strands={npos}  base_rate={npos/n:.3%}")
    print(f"train n={len(tr)} strands={int(sum(ytr))} | test n={len(te)} strands={int(sum(yte))}")
    print(f"\nOOS AUC  logistic = {auc_lr:.3f}  95%CI [{ci_lr[0]:.3f},{ci_lr[1]:.3f}]")
    print(f"OOS AUC  GBT      = {auc_gbt:.3f}  95%CI [{ci_gbt[0]:.3f},{ci_gbt[1]:.3f}]")
    print("\nLogistic coefficients (standardized, |.| desc):")
    for f, c in coefs:
        print(f"   {f:16s} {c:+.3f}")
    print("\nGBT permutation importance (OOS AUC drop):")
    for f, m, s in gbt_imp:
        print(f"   {f:16s} {m:+.4f} +/- {s:.4f}")
    print("\nUnivariate OOS AUC (direction-agnostic):")
    for f, a in uni:
        print(f"   {f:16s} {a:.3f}")
    print("\nCalibration GBT (mean_pred, obs_rate, n):")
    for mp, ob, cnt in R["calib_gbt"]:
        print(f"   pred={mp:.3f}  obs={ob:.3f}  n={cnt}")
    print("\nVeto tradeoff table (OOS test set):")
    hdr = f"{'policy':26s} {'veto%':>7s} {'kept':>5s} {'strand%kept':>11s} {'strands':>7s} {'good_retain%':>12s}"
    print(hdr); print("-" * len(hdr))
    order = ["no-veto", "thickbook_veto", "model@thickbook_veto_rate(GBT)",
             "model@thickbook_veto_rate(LR)", "simple|mid-.5|@thickbook_veto_rate",
             "volgate", "model@volgate_rate(GBT)", "model@volgate_rate(LR)",
             "simple|mid-.5|@volgate_rate", "nsmove"]
    for k in order:
        if k not in table: continue
        s = table[k]
        print(f"{k:26s} {s['veto_rate']*100:6.1f}% {s['kept']:5d} "
              f"{s['strand_rate']*100:10.1f}% {s['strands_kept']:7d} {s['good_retained']*100:11.1f}%")

    # persist json for the report writer
    import os
    outp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strand_model_results.json")
    with open(outp, "w") as fh:
        json.dump(R, fh, indent=2, default=float)
    print(f"\n[info] wrote {outp}")
    return R

if __name__ == "__main__":
    main()
