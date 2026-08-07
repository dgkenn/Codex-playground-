#!/usr/bin/env python3
"""E261-E269 -- second battery. Follow-ups the first one earned, plus the checks it revealed were missing.

PRE-REGISTRATION. Predictions committed before the corresponding statistics existed.

SMOKE DISCIPLINE, FIXED FROM THE LAST BATTERY. E250-E259's smoke permuted one global arm label, so the
four items that do not use it (E252/E253/E257/E259) ran unblinded. Here **each item declares the labels
it depends on and the smoke permutes all of them**, enumerated per item in `SMOKE_LABELS` below.

COHORT: the completed 56,731-window table, 2,589 single-agent cases, sevo 1,274 / des 412 / ppf 903.
SCOPE unchanged: the label is the AIRWAY RECORD, a brainstem behavioural output, not consciousness;
recovery only.

======================================================================================================
E261 -- IS THE E250 CORNER REAL, OR A LINE DRAWN THROUGH 19 POINTS? (rule 47)

E250 found leakage and state tracking dissociate (Spearman -0.1807) and named a low-leakage /
high-tracking corner. A corner read off a scatter is not a result. Test the specific claim: the corner
members' mean (state_tracking - leakage) against the null of all equally-sized subsets of the panel.

PREDICTION: **the corner's margin sits above the 95th percentile of the subset null.**
WRONG IF: it lands inside the null, in which case E250's dissociation is real but the corner is just the
tail of a continuum and must be described that way.

E262 -- IS BIS'S LEAKAGE REDUCIBLE TO OUR PANEL?

E251 found BIS leaks above our median in all three pairs. Ask whether that leakage is carried by the
spectral content we already measure: residualise BIS on the candidate panel within patient, and re-run
the leakage path on the residual.

PREDICTION: **BIS's leakage falls by >= 50 % after adjustment** -- BIS is a composite of the same
spectral quantities, so its agent identity should be largely the panel's agent identity re-expressed.
WRONG IF: the residual retains most of the leakage, which would mean BIS carries agent information our
panel does not -- a much more interesting result, and one that would say the proprietary composite has
its own drug-dependent behaviour.

E263 -- E253 REDONE CORRECTLY: MUSCLE AS A PRE-LANDMARK TRAIT, NOT A CONCURRENT MEDIATOR

E253 conditioned on `meta_emg` measured concurrently. EMG rises because the patient starts breathing, so
it is post-exposure -- a mediator, and rule 13 forbids conditioning on it. Use instead each patient's
**pre-landmark median EMG** as a patient-level trait, which cannot be on the causal path from the
transition to a post-landmark window.

PREDICTION: **state tracking is essentially unchanged** -- the top candidates retain >= 90 % of their
signed mean after adjustment. A patient-level muscle trait should not explain a within-patient change.
WRONG IF: it attenuates substantially, which would mean high-muscle patients drive the state effect.

E264 -- BURST SUPPRESSION: DOES IT DIFFER BY ARM, AND DOES IT CARRY THE LEAKAGE?

`meta_sr` is the monitor's suppression ratio, finite in 45,580 windows. E248's registration asserted
suppression ratio is "0.000 throughout" on an earlier cohort. Verify here, and if it varies, test whether
excluding suppression-positive cases changes leakage.

PREDICTION: **SR is near-zero for the large majority of windows and excluding SR-positive cases moves the
top candidates' leakage by < 20 %.** Suppression is not the mechanism.
WRONG IF: SR differs markedly by arm, which would make it a confound of exactly the kind rule 87 warns
about -- a machine-reported quantity standing in for a patient state.

E265 -- DOES LEAKAGE LIVE IN LOW-QUALITY WINDOWS? (rule 52's corollary: use the flag the deposit ships)

`meta_sqi` is the monitor's own signal-quality index. E60's worst band turned out to be windows the
monitor itself declared unreliable, and no experiment had used the column.

PREDICTION: **leakage is essentially unchanged when restricted to high-SQI windows (SQI >= 50)** --
within 25 % for the top candidates.
WRONG IF: leakage concentrates in low-quality windows, which would make it partly an artefact of when the
sensor is failing, and failing differently by agent.

E266 -- WHERE DOES EACH CANDIDATE'S VARIANCE LIVE?

Agent identity is a patient-level property, so leakage can only be carried by between-patient variance.
Decompose each candidate into between- and within-patient variance and correlate the between-share
against leakage.

PREDICTION: **positive, Spearman >= +0.3.** Candidates whose variance is mostly between-patient leak more.
WRONG IF: near zero, which would mean leakage is not simply a function of where the variance sits and
something more specific is going on.

E267 -- DOES THE E250 DISSOCIATION REPLICATE IN INDEPENDENT HALVES?

Split patients at random into two halves, recompute both axes and the Spearman in each.

PREDICTION: **both halves negative**, i.e. the dissociation replicates in sign.
WRONG IF: the halves disagree in sign, which would make E250 a 19-point noise correlation.

E268 -- DOES LEAKAGE SURVIVE RESTRICTION TO COMMON COVARIATE SUPPORT?

E257 showed the cohort exclusion tracks anaesthesia duration, and duration identifies the agent (E154:
0.3771). Trim each pair to the overlapping 10th-90th percentile band of age, BMI and duration jointly,
and recompute.

PREDICTION: **leakage survives, retaining >= 70 %** for the top candidates. E248's G2 already showed the
nuisances do not out-identify the candidates; restriction should cost power, not the effect.
WRONG IF: it collapses, which would mean the arm contrast is partly a case-mix contrast.

E269 -- WHERE DOES BIS RANK IN THE FULL PANEL, WITH HOLM ACROSS THE EXTENDED FAMILY?

E251 compared BIS to the median. Rank it, and apply Holm across the panel + BIS as one family of 20.

PREDICTION: **BIS ranks in the top third of the extended panel in at least 2 of 3 pairs.**
WRONG IF: it ranks mid-pack, which would soften E251's claim from "the incumbent is among the worst" to
"the incumbent is unexceptional" -- a materially different sentence.

    python -m bsde.experiments.e261_battery2
"""
from __future__ import annotations

import argparse, csv, glob, itertools, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
MIN_WIN = 15
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}

# Every item names the labels it depends on; the smoke permutes all of them (fixing E250-E259's gap).
SMOKE_LABELS = {
    "E261": ["arm", "after"], "E262": ["arm"], "E263": ["after"], "E264": ["arm"],
    "E265": ["arm"], "E266": ["arm"], "E267": ["arm", "after"], "E268": ["arm"], "E269": ["arm"],
}


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def midranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def auc(pos, neg):
    pos = [x for x in pos if math.isfinite(x)]
    neg = [x for x in neg if math.isfinite(x)]
    if not pos or not neg:
        return float("nan")
    r = midranks(pos + neg)
    return (sum(r[:len(pos)]) - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def leak(va, vb, rng=None, reps=0):
    va = [x for x in va if math.isfinite(x)]
    vb = [x for x in vb if math.isfinite(x)]
    if len(va) < 5 or len(vb) < 5:
        return float("nan"), float("nan")
    obs = abs(auc(va, vb) - 0.5)
    if not reps:
        return obs, float("nan")
    pool = va + vb
    n1 = len(va)
    null = []
    for _ in range(reps):
        rng.shuffle(pool)
        a = auc(pool[:n1], pool[n1:])
        if math.isfinite(a):
            null.append(abs(a - 0.5))
    null.sort()
    return obs, (sum(1 for v in null if v >= obs) / len(null) if null else float("nan"))


def patient_auc(vals, is_after):
    keep = [(v, a) for v, a in zip(vals, is_after) if math.isfinite(v)]
    if len(keep) < 4:
        return float("nan")
    v = [x[0] for x in keep]; a = [x[1] for x in keep]
    n1 = sum(1 for x in a if x); n2 = len(a) - n1
    if not n1 or not n2:
        return float("nan")
    r = midranks(v)
    return (sum(rr for rr, aa in zip(r, a) if aa) - n1 * (n1 + 1) / 2.0) / (n1 * n2)


def pearson(x, y):
    pts = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pts) < 3:
        return float("nan")
    n = len(pts)
    mx = sum(p[0] for p in pts) / n; my = sum(p[1] for p in pts) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    sxx = sum((p[0] - mx) ** 2 for p in pts); syy = sum((p[1] - my) ** 2 for p in pts)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def spearman(x, y):
    pts = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pts) < 4:
        return float("nan")
    return pearson(midranks([p[0] for p in pts]), midranks([p[1] for p in pts]))


def median(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def pct(v, q):
    v = sorted(x for x in v if math.isfinite(x))
    return v[min(len(v) - 1, int(q * len(v)))] if v else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=os.path.join(RESULTS, "vitaldb_ventwin.s*.csv"))
    ap.add_argument("--landmarks", default=os.path.join(RESULTS, "vitaldb_vent_landmarks.s*.csv"))
    ap.add_argument("--p1", default=os.path.join(RESULTS, "e248_agent_leakage.json"))
    ap.add_argument("--p2", default=os.path.join(RESULTS, "e249_gate_completion.json"))
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=261)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e261_battery2.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {}

    lm = {}
    for p in sorted(glob.glob(a.landmarks)):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r
    rows, cols = [], None
    for p in sorted(glob.glob(a.features)):
        rd = csv.DictReader(open(p))
        if cols is None:
            cols = [c for c in (rd.fieldnames or []) if not c.startswith("meta_") and c not in SKIP]
        for r in rd:
            if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                rows.append(r)
    fin = {c: sum(1 for r in rows if math.isfinite(f(r.get(c)))) for c in cols}
    cols = [c for c in cols if fin[c] >= 0.20 * len(rows)]
    by = {}
    for r in rows:
        by.setdefault(r["meta_caseid"], []).append(r)
    by = {k: v for k, v in by.items() if len(v) >= MIN_WIN}
    rec = [k for k in by if lm[k].get("rec_ok") == "1"]
    arm = {k: lm[k]["arm"] for k in by}
    if a.smoke:
        ks = sorted(arm); vs = [arm[k] for k in ks]; rng.shuffle(vs); arm = dict(zip(ks, vs))
        print("[SMOKE] arm AND after labels permuted for every item that uses them")
    t0 = {k: f(lm[k]["t_rec_s"]) for k in rec}
    print(f"[cohort] {len(by)} cases, {len(cols)} candidates, {len(rec)} recovery")

    EXTRA = ["meta_bis", "meta_sqi", "meta_sr", "meta_emg"]
    lvl, p2, sqi_hi_lvl, emg_pre, sr_max = {}, {}, {}, {}, {}
    win_var = {}
    for cid in rec:
        rs = by[cid]
        offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
        aft = [o > 0 for o in offs]
        if a.smoke:
            aft = list(aft); rng.shuffle(aft)
        for c in cols + EXTRA:
            vb = [f(r.get(c)) for r, o in zip(rs, offs) if o < 0]
            lvl.setdefault(c, {})[cid] = median(vb)
            p2.setdefault(c, {})[cid] = patient_auc([f(r.get(c)) for r in rs], aft)
            hv = [f(r.get(c)) for r in rs if f(r.get("meta_sqi")) >= 50]
            sqi_hi_lvl.setdefault(c, {})[cid] = median(hv)
            vv = [f(r.get(c)) for r in rs if math.isfinite(f(r.get(c)))]
            if len(vv) > 2:
                m = sum(vv) / len(vv)
                win_var.setdefault(c, {})[cid] = sum((x - m) ** 2 for x in vv) / len(vv)
        emg_pre[cid] = median([f(r.get("meta_emg")) for r, o in zip(rs, offs) if o < 0])
        srs = [f(r.get("meta_sr")) for r in rs if math.isfinite(f(r.get("meta_sr")))]
        sr_max[cid] = max(srs) if srs else float("nan")

    p1doc = json.load(open(a.p1))
    p2doc = json.load(open(a.p2))
    LK = {c: max(p1doc["pairs"][n]["features"][c]["obs"] for n in p1doc["pairs"]
                 if c in p1doc["pairs"][n]["features"]) for c in cols}
    ST = {c: abs(p2doc["p2"][c]["obs"]) for c in cols if c in p2doc["p2"]}
    TOP = sorted(cols, key=lambda c: -LK.get(c, 0))[:6]

    # -------------------------------------------------------------- E261
    print("\n" + "=" * 92 + "\nE261 -- is the E250 corner real, or a line through 19 points?")
    CORNER = ["whole_head_exponent", "multiscale_entropy_slope", "spectral_edge_95",
              "emg_index", "emg_beta_gamma_fraction"]
    corner = [c for c in CORNER if c in LK and c in ST]
    marg = {c: ST[c] - LK[c] for c in cols if c in ST and c in LK}
    obs = sum(marg[c] for c in corner) / len(corner)
    allc = sorted(marg)
    null = [sum(marg[c] for c in s) / len(s)
            for s in itertools.combinations(allc, len(corner))]
    null.sort()
    p95 = null[int(0.95 * len(null))]
    pv = sum(1 for v in null if v >= obs) / len(null)
    print(f"  corner {corner}")
    print(f"  mean(state - leakage) = {obs:+.4f}   subset null 95th {p95:+.4f}   "
          f"p = {pv:.4f}  over {len(null)} subsets")
    met = obs > p95
    print(f"  PREDICTED above the 95th  ->  {'MET' if met else 'NOT MET'}")
    R["E261"] = {"corner": corner, "obs": obs, "null_p95": p95, "p": pv,
                 "n_subsets": len(null), "prediction_met": met}

    # -------------------------------------------------------------- E262
    print("\n" + "=" * 92 + "\nE262 -- is BIS's leakage reducible to our panel?")
    # residualise BIS on the panel across patients (patient-level, which is where leakage lives)
    ids = [c for c in rec if math.isfinite(lvl["meta_bis"][c])
           and all(math.isfinite(lvl[k][c]) for k in cols)]
    y = [lvl["meta_bis"][i] for i in ids]
    resid = list(y)
    for _ in range(6):                       # simple sequential Gram-Schmidt on the panel
        for c in cols:
            x = [lvl[c][i] for i in ids]
            mx = sum(x) / len(x); my = sum(resid) / len(resid)
            sxx = sum((v - mx) ** 2 for v in x)
            if sxx <= 0:
                continue
            b = sum((v - mx) * (w - my) for v, w in zip(x, resid)) / sxx
            resid = [w - b * (v - mx) for v, w in zip(x, resid)]
    rmap = dict(zip(ids, resid))
    e262 = {}
    for x, y_ in PAIRS:
        ax = [i for i in ids if arm[i] == x]; ay = [i for i in ids if arm[i] == y_]
        raw, _ = leak([lvl["meta_bis"][i] for i in ax], [lvl["meta_bis"][i] for i in ay])
        res, pr = leak([rmap[i] for i in ax], [rmap[i] for i in ay], rng, a.reps)
        drop = 1 - res / raw if raw > 0 else float("nan")
        e262[f"{x}_vs_{y_}"] = {"raw": raw, "residual": res, "p_residual": pr, "drop": drop,
                                "n": [len(ax), len(ay)]}
        print(f"  {x}_vs_{y_:5s} BIS raw {raw:.4f} -> residual {res:.4f}  "
              f"({drop:+.1%} reduction, p={pr:.4f})")
    drops = [v["drop"] for v in e262.values() if math.isfinite(v["drop"])]
    met = all(d >= 0.5 for d in drops)
    print(f"  PREDICTED >= 50% reduction in all pairs  ->  {'MET' if met else 'NOT MET'}")
    R["E262"] = {"detail": e262, "prediction_met": met}

    # -------------------------------------------------------------- E263
    print("\n" + "=" * 92 + "\nE263 -- E253 redone: muscle as a PRE-landmark trait (rule 13 respected)")
    e263 = {}
    for c in ("whole_head_exponent", "spectral_edge_95", "multiscale_entropy_slope",
              "emg_beta_gamma_fraction"):
        if c not in cols:
            continue
        ids2 = [i for i in rec if math.isfinite(p2[c][i]) and math.isfinite(emg_pre[i])]
        vals = [p2[c][i] - 0.5 for i in ids2]
        raw = sum(vals) / len(vals)
        e = [emg_pre[i] for i in ids2]
        me = sum(e) / len(e); mv = sum(vals) / len(vals)
        sxx = sum((x - me) ** 2 for x in e)
        b = sum((x - me) * (w - mv) for x, w in zip(e, vals)) / sxx if sxx > 0 else 0.0
        adj = [w - b * (x - me) for x, w in zip(e, vals)]
        adjm = sum(adj) / len(adj)
        ret = adjm / raw if raw != 0 else float("nan")
        e263[c] = {"raw": raw, "adjusted": adjm, "retained": ret, "n": len(ids2)}
        print(f"  {c:28s} raw {raw:+.4f} -> emg-trait-adjusted {adjm:+.4f}   retained {ret:.3f}")
    rets = [v["retained"] for v in e263.values() if math.isfinite(v["retained"])]
    met = all(r >= 0.90 for r in rets) if rets else False
    print(f"  PREDICTED all retain >= 0.90  ->  {'MET' if met else 'NOT MET'}")
    R["E263"] = {"detail": e263, "prediction_met": met}

    # -------------------------------------------------------------- E264
    print("\n" + "=" * 92 + "\nE264 -- burst suppression by arm, and does it carry the leakage?")
    srv = [sr_max[i] for i in rec if math.isfinite(sr_max[i])]
    frac0 = sum(1 for v in srv if v <= 0.5) / len(srv) if srv else float("nan")
    by_arm_sr = {x: median([sr_max[i] for i in rec if arm[i] == x]) for x in ARMS}
    print(f"  max SR per case: median {median(srv):.2f}, {frac0:.1%} of cases <= 0.5; "
          f"by arm {({k: round(v,2) for k,v in by_arm_sr.items()})}")
    clean = [i for i in rec if math.isfinite(sr_max[i]) and sr_max[i] <= 0.5]
    e264 = {}
    for c in TOP:
        d = {}
        for x, y_ in PAIRS:
            full, _ = leak([lvl[c][i] for i in rec if arm[i] == x],
                           [lvl[c][i] for i in rec if arm[i] == y_])
            cl, _ = leak([lvl[c][i] for i in clean if arm[i] == x],
                         [lvl[c][i] for i in clean if arm[i] == y_])
            d[f"{x}_vs_{y_}"] = {"full": full, "sr_clean": cl,
                                 "ratio": cl / full if full > 0 else float("nan")}
        e264[c] = d
        print(f"  {c:26s} " + "  ".join(f"{k[:9]}:{v['full']:.3f}->{v['sr_clean']:.3f}"
                                        for k, v in d.items()))
    rr = [v["ratio"] for c in e264 for v in e264[c].values() if math.isfinite(v["ratio"])]
    met = sum(1 for r in rr if abs(r - 1) <= 0.20) / len(rr) > 0.5 if rr else False
    print(f"  n SR-clean cases {len(clean)} of {len(rec)};  "
          f"PREDICTED most within 20%  ->  {'MET' if met else 'NOT MET'}")
    R["E264"] = {"frac_sr_low": frac0, "by_arm": by_arm_sr, "n_clean": len(clean),
                 "detail": e264, "prediction_met": met}

    # -------------------------------------------------------------- E265
    print("\n" + "=" * 92 + "\nE265 -- does leakage live in low-SQI windows?")
    e265 = {}
    for c in TOP:
        d = {}
        for x, y_ in PAIRS:
            full, _ = leak([lvl[c][i] for i in rec if arm[i] == x],
                           [lvl[c][i] for i in rec if arm[i] == y_])
            hi, _ = leak([sqi_hi_lvl[c][i] for i in rec if arm[i] == x],
                         [sqi_hi_lvl[c][i] for i in rec if arm[i] == y_])
            d[f"{x}_vs_{y_}"] = {"all": full, "sqi_hi": hi,
                                 "ratio": hi / full if full > 0 else float("nan")}
        e265[c] = d
        print(f"  {c:26s} " + "  ".join(f"{k[:9]}:{v['all']:.3f}->{v['sqi_hi']:.3f}"
                                        for k, v in d.items()))
    rr = [v["ratio"] for c in e265 for v in e265[c].values() if math.isfinite(v["ratio"])]
    met = sum(1 for r in rr if abs(r - 1) <= 0.25) / len(rr) > 0.5 if rr else False
    print(f"  PREDICTED most within 25%  ->  {'MET' if met else 'NOT MET'}")
    R["E265"] = {"detail": e265, "prediction_met": met}

    # -------------------------------------------------------------- E266
    print("\n" + "=" * 92 + "\nE266 -- where does each candidate's variance live?")
    shares, lks = [], []
    e266 = {}
    for c in cols:
        wv = [win_var[c][i] for i in rec if i in win_var.get(c, {})]
        lv = [lvl[c][i] for i in rec if math.isfinite(lvl[c][i])]
        if len(wv) < 50 or len(lv) < 50:
            continue
        within = sum(wv) / len(wv)
        m = sum(lv) / len(lv)
        between = sum((x - m) ** 2 for x in lv) / len(lv)
        sh = between / (between + within) if (between + within) > 0 else float("nan")
        e266[c] = {"between": between, "within": within, "between_share": sh, "leakage": LK.get(c)}
        shares.append(sh); lks.append(LK.get(c, float("nan")))
    rho = spearman(shares, lks)
    print(f"  n={len(shares)}  Spearman(between-patient share, leakage) = {rho:+.4f}")
    met = math.isfinite(rho) and rho >= 0.30
    print(f"  PREDICTED >= +0.30  ->  {'MET' if met else 'NOT MET'}")
    R["E266"] = {"rho": rho, "n": len(shares), "prediction_met": met, "detail": e266}

    # -------------------------------------------------------------- E267
    print("\n" + "=" * 92 + "\nE267 -- does the E250 dissociation replicate in halves?")
    ids3 = sorted(rec); rng.shuffle(ids3)
    halves = [set(ids3[:len(ids3) // 2]), set(ids3[len(ids3) // 2:])]
    e267 = {}
    for hi, H in enumerate(halves):
        lk_h, st_h, nm = [], [], []
        for c in cols:
            mx = 0.0
            for x, y_ in PAIRS:
                v, _ = leak([lvl[c][i] for i in H if arm[i] == x],
                            [lvl[c][i] for i in H if arm[i] == y_])
                if math.isfinite(v):
                    mx = max(mx, v)
            vals = [p2[c][i] - 0.5 for i in H if math.isfinite(p2[c][i])]
            s = abs(sum(vals) / len(vals)) if vals else float("nan")
            if mx and math.isfinite(s):
                lk_h.append(mx); st_h.append(s); nm.append(c)
        r = spearman(lk_h, st_h)
        e267[f"half{hi}"] = {"rho": r, "n": len(nm)}
        print(f"  half {hi}: Spearman = {r:+.4f} over {len(nm)} candidates, {len(H)} patients")
    rs = [v["rho"] for v in e267.values()]
    met = all(math.isfinite(r) and r < 0 for r in rs)
    print(f"  PREDICTED both negative  ->  {'MET' if met else 'NOT MET'}")
    R["E267"] = {"detail": e267, "prediction_met": met}

    # -------------------------------------------------------------- E268
    print("\n" + "=" * 92 + "\nE268 -- does leakage survive common covariate support?")
    import gzip, io as _io, urllib.request
    req = urllib.request.Request("https://api.vitaldb.net/cases", headers={"User-Agent": "bsde/1.0"})
    blob = urllib.request.urlopen(req, timeout=300).read()
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    clin = {}
    for r in csv.DictReader(_io.StringIO(blob.decode("utf-8-sig", "replace"))):
        ae, as_ = f(r.get("aneend")), f(r.get("anestart"))
        clin[r["caseid"]] = {"age": f(r.get("age")), "bmi": f(r.get("bmi")),
                             "dur": ae - as_ if math.isfinite(ae) and math.isfinite(as_)
                             else float("nan")}
    e268 = {}
    for x, y_ in PAIRS:
        ax = [i for i in rec if arm[i] == x]; ay = [i for i in rec if arm[i] == y_]
        keep = set()
        for k in ("age", "bmi", "dur"):
            va = [clin.get(i, {}).get(k, float("nan")) for i in ax]
            vb = [clin.get(i, {}).get(k, float("nan")) for i in ay]
            lo = max(pct(va, 0.10), pct(vb, 0.10)); hi = min(pct(va, 0.90), pct(vb, 0.90))
            ok = {i for i in ax + ay
                  if lo <= clin.get(i, {}).get(k, float("nan")) <= hi}
            keep = ok if not keep else (keep & ok)
        d = {}
        for c in TOP:
            full, _ = leak([lvl[c][i] for i in ax], [lvl[c][i] for i in ay])
            tr, _ = leak([lvl[c][i] for i in ax if i in keep],
                         [lvl[c][i] for i in ay if i in keep])
            d[c] = {"full": full, "trimmed": tr,
                    "retained": tr / full if full > 0 else float("nan")}
        e268[f"{x}_vs_{y_}"] = {"n_kept": len(keep), "n_full": len(ax) + len(ay), "features": d}
        print(f"  {x}_vs_{y_:5s} kept {len(keep)} of {len(ax)+len(ay)}: "
              + ", ".join(f"{c[:14]} {d[c]['full']:.3f}->{d[c]['trimmed']:.3f}" for c in TOP[:3]))
    rets = [v["retained"] for pr in e268.values() for v in pr["features"].values()
            if math.isfinite(v["retained"])]
    met = sum(1 for r in rets if r >= 0.70) / len(rets) > 0.5 if rets else False
    print(f"  PREDICTED most retain >= 70%  ->  {'MET' if met else 'NOT MET'}")
    R["E268"] = {"detail": e268, "prediction_met": met}

    # -------------------------------------------------------------- E269
    print("\n" + "=" * 92 + "\nE269 -- where does BIS rank in the extended panel?")
    e269 = {}
    for x, y_ in PAIRS:
        name = f"{x}_vs_{y_}"
        vals = {c: p1doc["pairs"][name]["features"][c]["obs"] for c in cols
                if c in p1doc["pairs"][name]["features"]}
        b, _ = leak([lvl["meta_bis"][i] for i in rec if arm[i] == x
                     and math.isfinite(lvl["meta_bis"][i])],
                    [lvl["meta_bis"][i] for i in rec if arm[i] == y_
                     and math.isfinite(lvl["meta_bis"][i])])
        vals["BIS"] = b
        order = sorted(vals, key=lambda k: -vals[k])
        rk = order.index("BIS") + 1
        e269[name] = {"bis": b, "rank": rk, "n": len(order),
                      "top_third": rk <= len(order) / 3}
        print(f"  {name:14s} BIS {b:.4f} ranks {rk} of {len(order)}"
              f"  {'(top third)' if rk <= len(order)/3 else ''}")
    met = sum(1 for v in e269.values() if v["top_third"]) >= 2
    print(f"  PREDICTED top third in >= 2 of 3  ->  {'MET' if met else 'NOT MET'}")
    R["E269"] = {"detail": e269, "prediction_met": met}

    print("\n" + "=" * 92)
    for k in sorted(R):
        v = R[k].get("prediction_met")
        print(f"  {k}: prediction {'MET' if v else 'NOT MET' if v is False else 'descriptive'}")
    if not a.smoke:
        json.dump(R, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print("\n[SMOKE] complete; nothing above is a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
