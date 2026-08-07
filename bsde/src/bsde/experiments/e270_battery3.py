#!/usr/bin/env python3
"""E270-E279 -- third battery. Everything E260 forced, run where the drug is actually acting.

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY THIS BATTERY EXISTS. E260 showed agent identity is 5-6x LARGER at maintenance than peri-landmark
(`whole_head_exponent` 0.3525/0.3788 against 0.0668/0.0635), which withdrew E250's dissociation and
E261's corner -- both were computed from leakage measured exactly where the agent is washing out. Every
item here re-asks a peri-landmark question at the control centre, or asks something only the two states
together can answer.

COHORTS. **PERI** = the 56,731-window table, 2,589 cases. **CTRL** = the 15,747-window control table,
740 cases with >= 15 windows, centred 2,400 s before recovery, >= 900 s clear of both landmarks. The
control arms are ~247 each, so the analytic leakage null 95th is ~0.051 -- roughly double PERI's, and
every threshold below accounts for it.

SCOPE unchanged: the label is the AIRWAY RECORD, a brainstem behavioural output, not consciousness.

======================================================================================================
E270 -- THE DISSOCIATION, RE-ASKED WITH LEAKAGE MEASURED WHERE THE DRUG IS ACTING

E250 got Spearman -0.1807 and E261's corner p = 0.0003, both from peri-landmark leakage. Redo with
CTRL leakage against PERI state tracking.

PREDICTION: **the correlation goes POSITIVE (Spearman >= +0.2) and the E261 corner no longer beats its
subset null.** E260 already showed the corner's headline member is among the leakiest at maintenance.
WRONG IF: the corner survives, in which case E260's reversal is specific to `whole_head_exponent` and the
family claim stands after all.

E271 -- THE LEAKAGE-VERSUS-DEPTH CURVE, WHICH NOBODY HAS

E260's reusable claim is that a leakage value is meaningless without the state it was measured in. Test
it *within* CTRL by stratifying cases on their own control-window median BIS into terciles and computing
leakage in each.

PREDICTION: **leakage rises monotonically as BIS falls** (deepest tercile highest) for a majority of the
top candidates.
WRONG IF: flat or non-monotone, which would mean the PERI/CTRL gap is about the transition specifically
rather than about depth, and E260's mechanism would need rewriting.

E272 -- IS THE ARM DIFFERENCE A LOCATION SHIFT OR A DISTRIBUTIONAL ONE?

If leakage is a per-drug offset (E254), aligning the two arms' medians should remove nearly all of it.
Recompute CTRL leakage after subtracting each arm's own median.

PREDICTION: **median alignment removes >= 80 % of leakage** for the top candidates.
WRONG IF: much survives, meaning the arms differ in spread or shape, which no centring or per-drug
calibration could fix and which is a harder problem for any invariance method.

E273 -- BIS AT MAINTENANCE: DOES E251 REPLICATE WHERE THE DRUG IS ACTING?

PREDICTION: **BIS still leaks at or above the median candidate in all three pairs at CTRL.**
WRONG IF: BIS falls below the median at maintenance, which would mean E251's finding was itself a
peri-landmark artefact -- the same error E260 caught in the corner, in the other direction.

E274 -- DOES THE LEAKAGE RANKING EVEN AGREE BETWEEN THE TWO STATES?

Spearman between each candidate's PERI leakage and its CTRL leakage, per pair.

PREDICTION: **weak agreement, Spearman < +0.5 in at least 2 of 3 pairs.** If E260 is right that state
determines leakage, the rank order should not transport either.
WRONG IF: strong agreement, which would mean the level changes but the ordering is stable -- and a stable
ordering is all a candidate-selection procedure actually needs, which would considerably soften E260.

E275 -- WITHIN-PATIENT STABILITY BETWEEN THE TWO STATES

For patients in both cohorts, correlate each candidate's CTRL median against its PERI pre-landmark
median. This is a test-retest coefficient across a ~40-minute gap and a depth change, and reliability has
been this programme's binding constraint before (E38, E68).

PREDICTION: **the aperiodic and complexity measures are the most stable (r >= 0.5) and the muscle
measures the least.**
WRONG IF: everything is unstable, in which case the leakage differences between states are partly just
noise and E260's contrast is weaker than it looks.

E277 -- IS CTRL LEAKAGE ROBUST TO SIGNAL QUALITY?  (E265 re-asked at maintenance)

PREDICTION: **restricting to `meta_sqi >= 50` leaves CTRL leakage within 25 %**, as it did at PERI.
WRONG IF: it moves a lot, which would make the maintenance leakage partly a sensor artefact.

E278 -- IS CTRL LEAKAGE ROBUST TO CASE MIX?  (E268 re-asked at maintenance)

PREDICTION: **trimming to the joint 10-90th percentile overlap of age, BMI and duration retains >= 70 %.**
WRONG IF: it collapses. Note in advance the control arms are ~247, so trimming leaves ~120 per arm and
the null floor rises to ~0.073 -- this item is powered only for large effects and says so.

E279 -- THE ACTUAL CHALLENGE A SCREEN: LOW LEAKAGE AT **BOTH** STATES, HIGH TRACKING

The screen no experiment here has run. Require: state tracking above the panel median, AND leakage below
the panel median at PERI, AND below the panel median at CTRL.

PREDICTION: **the set is EMPTY or has at most one member.** E260 suggests the peri-landmark winners are
maintenance losers.
WRONG IF: a stable set exists, which would be the most valuable result this deposit could produce and
would name Challenge A's candidate shortlist directly.

    python -m bsde.experiments.e270_battery3
"""
from __future__ import annotations

import argparse, csv, glob, itertools, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def midranks(vals):
    o = sorted(range(len(vals)), key=lambda i: vals[i]); r = [0.0] * len(vals); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and vals[o[j + 1]] == vals[o[i]]:
            j += 1
        av = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[o[k]] = av
        i = j + 1
    return r


def auc(p, n):
    p = [x for x in p if math.isfinite(x)]; n = [x for x in n if math.isfinite(x)]
    if not p or not n:
        return float("nan")
    r = midranks(p + n)
    return (sum(r[:len(p)]) - len(p) * (len(p) + 1) / 2.0) / (len(p) * len(n))


def lk(a_, b_):
    a_ = [x for x in a_ if math.isfinite(x)]; b_ = [x for x in b_ if math.isfinite(x)]
    if len(a_) < 8 or len(b_) < 8:
        return float("nan")
    return abs(auc(a_, b_) - 0.5)


def null95(n1, n2):
    return 1.959964 * math.sqrt((n1 + n2 + 1) / (12.0 * n1 * n2))


def pau(vals, aft):
    k = [(v, a) for v, a in zip(vals, aft) if math.isfinite(v)]
    if len(k) < 4:
        return float("nan")
    v = [x[0] for x in k]; a = [x[1] for x in k]
    n1 = sum(1 for x in a if x); n2 = len(a) - n1
    if not n1 or not n2:
        return float("nan")
    r = midranks(v)
    return (sum(rr for rr, aa in zip(r, a) if aa) - n1 * (n1 + 1) / 2.0) / (n1 * n2)


def pear(x, y):
    p = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(p) < 3:
        return float("nan")
    n = len(p); mx = sum(q[0] for q in p) / n; my = sum(q[1] for q in p) / n
    sxy = sum((q[0] - mx) * (q[1] - my) for q in p)
    sxx = sum((q[0] - mx) ** 2 for q in p); syy = sum((q[1] - my) ** 2 for q in p)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def spear(x, y):
    p = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(p) < 4:
        return float("nan")
    return pear(midranks([q[0] for q in p]), midranks([q[1] for q in p]))


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def pct(v, q):
    v = sorted(x for x in v if math.isfinite(x))
    return v[min(len(v) - 1, int(q * len(v)))] if v else float("nan")


def read(pattern, lm):
    rows, cols = [], None
    for p in sorted(glob.glob(pattern)):
        rd = csv.DictReader(open(p))
        if cols is None:
            cols = [c for c in (rd.fieldnames or []) if not c.startswith("meta_") and c not in SKIP]
        for r in rd:
            if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                rows.append(r)
    by = {}
    for r in rows:
        by.setdefault(r["meta_caseid"], []).append(r)
    return {k: v for k, v in by.items() if len(v) >= 15}, cols, rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=270)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e270_battery3.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {}

    lm = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_vent_landmarks.s?.csv"))):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r
    peri, cols, prows = read(os.path.join(RESULTS, "vitaldb_ventwin.s?.csv"), lm)
    ctrl, _, crows = read(os.path.join(RESULTS, "vitaldb_ctrlwin.s?.csv"), lm)
    fin = {c: sum(1 for r in prows if math.isfinite(f(r.get(c)))) for c in cols}
    cols = [c for c in cols if fin[c] >= 0.20 * len(prows)]
    arm = {k: lm[k]["arm"] for k in set(peri) | set(ctrl)}
    if a.smoke:
        ks = sorted(arm); vs = [arm[k] for k in ks]; rng.shuffle(vs); arm = dict(zip(ks, vs))
        print("[SMOKE] arm labels permuted; every leakage below is recomputed under it")
    rec = [k for k in peri if lm[k].get("rec_ok") == "1"]
    t0 = {k: f(lm[k]["t_rec_s"]) for k in rec}
    print(f"[cohorts] PERI {len(peri)} cases / CTRL {len(ctrl)} cases / {len(cols)} candidates")

    EXTRA = ["meta_bis", "meta_sqi"]
    cmed, chi, pre, ST = {}, {}, {}, {}
    for cid, rs in ctrl.items():
        for c in cols + EXTRA:
            cmed.setdefault(c, {})[cid] = med([f(r.get(c)) for r in rs])
            chi.setdefault(c, {})[cid] = med([f(r.get(c)) for r in rs if f(r.get("meta_sqi")) >= 50])
    for cid in rec:
        rs = peri[cid]; offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
        aft = [o > 0 for o in offs]
        for c in cols + EXTRA:
            pre.setdefault(c, {})[cid] = med([f(r.get(c)) for r, o in zip(rs, offs) if o < 0])
            ST.setdefault(c, {})[cid] = pau([f(r.get(c)) for r in rs], aft)

    p1 = json.load(open(os.path.join(RESULTS, "e248_agent_leakage.json")))["pairs"]
    p2 = json.load(open(os.path.join(RESULTS, "e249_gate_completion.json")))["p2"]
    PERI_LK = {c: max(p1[n]["features"][c]["obs"] for n in p1 if c in p1[n]["features"]) for c in cols}
    CTRL_LK = {c: max(lk([cmed[c][i] for i in ctrl if arm.get(i) == x],
                         [cmed[c][i] for i in ctrl if arm.get(i) == y]) for x, y in PAIRS)
               for c in cols}
    STATE = {c: abs(p2[c]["obs"]) for c in cols if c in p2}
    n_arm = {x: sum(1 for i in ctrl if arm.get(i) == x) for x in ARMS}
    print(f"[ctrl arms] {n_arm}  analytic null95 ~ "
          f"{null95(n_arm['des'], n_arm['ppf']):.4f}")

    # ------------------------------------------------------------------ E270
    print("\n" + "=" * 92 + "\nE270 -- the dissociation with leakage measured at maintenance")
    names = [c for c in cols if c in STATE and math.isfinite(CTRL_LK[c])]
    rho_ctrl = spear([CTRL_LK[c] for c in names], [STATE[c] for c in names])
    rho_peri = spear([PERI_LK[c] for c in names], [STATE[c] for c in names])
    print(f"  Spearman(PERI leakage, state) = {rho_peri:+.4f}   (E250 reported -0.1807)")
    print(f"  Spearman(CTRL leakage, state) = {rho_ctrl:+.4f}")
    CORNER = ["whole_head_exponent", "multiscale_entropy_slope", "spectral_edge_95",
              "emg_index", "emg_beta_gamma_fraction"]
    corner = [c for c in CORNER if c in names]
    marg = {c: STATE[c] - CTRL_LK[c] for c in names}
    obs = sum(marg[c] for c in corner) / len(corner)
    null = sorted(sum(marg[c] for c in s) / len(s)
                  for s in itertools.combinations(sorted(marg), len(corner)))
    p95 = null[int(0.95 * len(null))]
    pv = sum(1 for v in null if v >= obs) / len(null)
    print(f"  E261 corner at CTRL: {obs:+.4f} vs subset null 95th {p95:+.4f}, p = {pv:.4f}")
    met = rho_ctrl >= 0.20 and obs <= p95
    print(f"  PREDICTED rho>=+0.20 AND corner no longer beats its null  ->  "
          f"{'MET' if met else 'NOT MET'}")
    R["E270"] = {"rho_ctrl": rho_ctrl, "rho_peri": rho_peri, "corner_obs": obs,
                 "corner_null_p95": p95, "corner_p": pv, "prediction_met": met}

    # ------------------------------------------------------------------ E271
    print("\n" + "=" * 92 + "\nE271 -- the leakage-versus-depth curve")
    bis = {i: cmed["meta_bis"][i] for i in ctrl if math.isfinite(cmed["meta_bis"][i])}
    q1, q2 = pct(list(bis.values()), 0.333), pct(list(bis.values()), 0.667)
    terc = {"deep": [i for i in bis if bis[i] <= q1],
            "mid": [i for i in bis if q1 < bis[i] <= q2],
            "light": [i for i in bis if bis[i] > q2]}
    print(f"  BIS terciles at <= {q1:.1f} / <= {q2:.1f}; "
          f"n = {({k: len(v) for k, v in terc.items()})}")
    e271, mono = {}, 0
    TOP = sorted(cols, key=lambda c: -CTRL_LK.get(c, 0))[:6]
    for c in TOP:
        d = {}
        for nm, ids in terc.items():
            d[nm] = max(lk([cmed[c][i] for i in ids if arm.get(i) == x],
                           [cmed[c][i] for i in ids if arm.get(i) == y]) for x, y in PAIRS)
        e271[c] = d
        if all(math.isfinite(v) for v in d.values()) and d["deep"] >= d["mid"] >= d["light"]:
            mono += 1
        print(f"  {c:28s} deep {d['deep']:.4f}  mid {d['mid']:.4f}  light {d['light']:.4f}")
    met = mono > len(TOP) / 2
    print(f"  monotone deep>=mid>=light in {mono} of {len(TOP)}  ->  "
          f"PREDICTION {'MET' if met else 'NOT MET'}")
    R["E271"] = {"terciles": {k: len(v) for k, v in terc.items()}, "detail": e271,
                 "n_monotone": mono, "prediction_met": met}

    # ------------------------------------------------------------------ E272
    print("\n" + "=" * 92 + "\nE272 -- location shift or distributional difference?")
    e272, removed = {}, []
    for c in TOP:
        d = {}
        for x, y in PAIRS:
            va = [cmed[c][i] for i in ctrl if arm.get(i) == x]
            vb = [cmed[c][i] for i in ctrl if arm.get(i) == y]
            raw = lk(va, vb)
            ma, mb = med(va), med(vb)
            al = lk([v - ma for v in va], [v - mb for v in vb])
            d[f"{x}_vs_{y}"] = {"raw": raw, "aligned": al,
                                "removed": 1 - al / raw if raw > 0 else float("nan")}
            if math.isfinite(d[f"{x}_vs_{y}"]["removed"]):
                removed.append(d[f"{x}_vs_{y}"]["removed"])
        e272[c] = d
        print(f"  {c:26s} " + "  ".join(f"{k[:9]} {v['raw']:.3f}->{v['aligned']:.3f}"
                                        f"({v['removed']:+.0%})" for k, v in d.items()))
    met = sum(1 for r in removed if r >= 0.80) / len(removed) > 0.5 if removed else False
    print(f"  PREDICTED median alignment removes >= 80%  ->  {'MET' if met else 'NOT MET'}")
    R["E272"] = {"detail": e272, "median_removed": med(removed), "prediction_met": met}

    # ------------------------------------------------------------------ E273
    print("\n" + "=" * 92 + "\nE273 -- BIS at maintenance")
    e273 = {}
    for x, y in PAIRS:
        b = lk([cmed["meta_bis"][i] for i in ctrl if arm.get(i) == x],
               [cmed["meta_bis"][i] for i in ctrl if arm.get(i) == y])
        mc = med([lk([cmed[c][i] for i in ctrl if arm.get(i) == x],
                     [cmed[c][i] for i in ctrl if arm.get(i) == y]) for c in cols])
        e273[f"{x}_vs_{y}"] = {"bis": b, "median_candidate": mc, "above": b >= mc}
        print(f"  {x}_vs_{y:5s} BIS {b:.4f}  median candidate {mc:.4f}  "
              f"-> BIS {'>=' if b >= mc else '<'} median")
    met = all(v["above"] for v in e273.values())
    print(f"  PREDICTED BIS >= median in all three  ->  {'MET' if met else 'NOT MET'}")
    R["E273"] = {"detail": e273, "prediction_met": met}

    # ------------------------------------------------------------------ E274
    print("\n" + "=" * 92 + "\nE274 -- does the leakage RANKING transport between states?")
    e274 = {}
    for x, y in PAIRS:
        nm = f"{x}_vs_{y}"
        pv_ = [p1[nm]["features"][c]["obs"] for c in cols if c in p1[nm]["features"]]
        cv = [lk([cmed[c][i] for i in ctrl if arm.get(i) == x],
                 [cmed[c][i] for i in ctrl if arm.get(i) == y])
              for c in cols if c in p1[nm]["features"]]
        r = spear(pv_, cv)
        e274[nm] = {"spearman": r, "n": len(pv_)}
        print(f"  {nm:14s} Spearman(PERI rank, CTRL rank) = {r:+.4f} over {len(pv_)} candidates")
    weak = sum(1 for v in e274.values() if math.isfinite(v["spearman"]) and v["spearman"] < 0.5)
    met = weak >= 2
    print(f"  PREDICTED < +0.5 in >= 2 of 3  ->  {'MET' if met else 'NOT MET'}")
    R["E274"] = {"detail": e274, "prediction_met": met}

    # ------------------------------------------------------------------ E275
    print("\n" + "=" * 92 + "\nE275 -- within-patient stability across the two states")
    both = [i for i in ctrl if i in pre.get(cols[0], {})]
    e275 = {}
    for c in cols:
        r = pear([cmed[c][i] for i in both], [pre[c][i] for i in both])
        e275[c] = r
    for c in sorted(e275, key=lambda k: -(e275[k] if math.isfinite(e275[k]) else -9))[:8]:
        print(f"  {c:30s} r = {e275[c]:+.4f}")
    ap_ = [e275.get(c, float("nan")) for c in
           ("whole_head_exponent", "exponent_high", "exponent_low", "multiscale_entropy_slope",
            "lempel_ziv") if c in e275]
    mus = [e275.get(c, float("nan")) for c in
           ("emg_index", "emg_kurtosis", "emg_beta_gamma_fraction") if c in e275]
    met = (med(ap_) >= 0.5) and (med(ap_) > med(mus))
    print(f"  n={len(both)} patients in both; aperiodic/complexity median r = {med(ap_):+.4f}, "
          f"muscle median r = {med(mus):+.4f}  ->  {'MET' if met else 'NOT MET'}")
    R["E275"] = {"n": len(both), "detail": e275, "aperiodic_median": med(ap_),
                 "muscle_median": med(mus), "prediction_met": met}

    # ------------------------------------------------------------------ E277
    print("\n" + "=" * 92 + "\nE277 -- is CTRL leakage robust to signal quality?")
    e277, rr = {}, []
    for c in TOP:
        d = {}
        for x, y in PAIRS:
            full = lk([cmed[c][i] for i in ctrl if arm.get(i) == x],
                      [cmed[c][i] for i in ctrl if arm.get(i) == y])
            hi = lk([chi[c][i] for i in ctrl if arm.get(i) == x],
                    [chi[c][i] for i in ctrl if arm.get(i) == y])
            d[f"{x}_vs_{y}"] = {"all": full, "sqi_hi": hi,
                                "ratio": hi / full if full > 0 else float("nan")}
            if math.isfinite(d[f"{x}_vs_{y}"]["ratio"]):
                rr.append(d[f"{x}_vs_{y}"]["ratio"])
        e277[c] = d
        print(f"  {c:26s} " + "  ".join(f"{k[:9]}:{v['all']:.3f}->{v['sqi_hi']:.3f}"
                                        for k, v in d.items()))
    met = sum(1 for r in rr if abs(r - 1) <= 0.25) / len(rr) > 0.5 if rr else False
    print(f"  PREDICTED most within 25%  ->  {'MET' if met else 'NOT MET'}")
    R["E277"] = {"detail": e277, "prediction_met": met}

    # ------------------------------------------------------------------ E278
    print("\n" + "=" * 92 + "\nE278 -- is CTRL leakage robust to case mix?")
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
    e278, rets = {}, []
    for x, y in PAIRS:
        ax = [i for i in ctrl if arm.get(i) == x]; ay = [i for i in ctrl if arm.get(i) == y]
        keep = set()
        for k in ("age", "bmi", "dur"):
            va = [clin.get(i, {}).get(k, float("nan")) for i in ax]
            vb = [clin.get(i, {}).get(k, float("nan")) for i in ay]
            lo = max(pct(va, 0.10), pct(vb, 0.10)); hi = min(pct(va, 0.90), pct(vb, 0.90))
            ok = {i for i in ax + ay if lo <= clin.get(i, {}).get(k, float("nan")) <= hi}
            keep = ok if not keep else (keep & ok)
        d = {}
        for c in TOP[:4]:
            full = lk([cmed[c][i] for i in ax], [cmed[c][i] for i in ay])
            tr = lk([cmed[c][i] for i in ax if i in keep], [cmed[c][i] for i in ay if i in keep])
            d[c] = {"full": full, "trimmed": tr,
                    "retained": tr / full if full > 0 else float("nan")}
            if math.isfinite(d[c]["retained"]):
                rets.append(d[c]["retained"])
        e278[f"{x}_vs_{y}"] = {"n_kept": len(keep), "n_full": len(ax) + len(ay), "features": d}
        print(f"  {x}_vs_{y:5s} kept {len(keep)} of {len(ax)+len(ay)}  "
              + ", ".join(f"{c[:16]} {d[c]['full']:.3f}->{d[c]['trimmed']:.3f}" for c in list(d)[:3]))
    met = sum(1 for r in rets if r >= 0.70) / len(rets) > 0.5 if rets else False
    print(f"  PREDICTED most retain >= 70%  ->  {'MET' if met else 'NOT MET'}")
    R["E278"] = {"detail": e278, "prediction_met": met}

    # ------------------------------------------------------------------ E279
    print("\n" + "=" * 92 + "\nE279 -- the actual Challenge A screen: low leakage at BOTH states")
    mp, mc, ms = med(list(PERI_LK.values())), med(list(CTRL_LK.values())), med(list(STATE.values()))
    survivors = [c for c in names
                 if STATE[c] > ms and PERI_LK[c] < mp and CTRL_LK[c] < mc]
    print(f"  medians: state {ms:.4f}, PERI leakage {mp:.4f}, CTRL leakage {mc:.4f}")
    for c in sorted(names, key=lambda k: -STATE[k])[:10]:
        flag = "  <== SURVIVES" if c in survivors else ""
        print(f"  {c:28s} state {STATE[c]:.4f}  PERI {PERI_LK[c]:.4f}  CTRL {CTRL_LK[c]:.4f}{flag}")
    print(f"  SURVIVORS: {survivors if survivors else 'NONE'}")
    met = len(survivors) <= 1
    print(f"  PREDICTED empty or at most one  ->  {'MET' if met else 'NOT MET'}")
    R["E279"] = {"survivors": survivors, "median_state": ms, "median_peri": mp,
                 "median_ctrl": mc, "prediction_met": met}

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
