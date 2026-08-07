#!/usr/bin/env python3
"""E311 -- is BIS's agent-invariance at depth real invariance, or is it compression?

PRE-REGISTRATION. Committed before any statistic in it exists.

THE QUESTION AND WHY IT HAS CLINICAL BITE. E292 found that as patients go deeper every candidate's
agent-identifiability RISES while BIS's FALLS (deep 0.0884 -> light 0.1286). Read one way that is a point
in the incumbent's favour: the commercial index is the one measure whose drug-dependence does not worsen
with depth. Read another way it is an artefact of the index having stopped resolving anything at the deep
end -- a measure with no variance cannot identify a drug, and it cannot identify a brain state either.
Those two readings have opposite clinical implications for titrating to a fixed index value.

**THE CIRCULARITY THAT KILLS THE OBVIOUS DESIGN, AND IT IS NAMED HERE RATHER THAN DISCOVERED LATER.**
The natural test -- stratify by BIS quintile and measure BIS's spread within each -- is worthless:
conditioning on BIS forces its within-stratum variance to be small by construction. Any "compression"
found that way is arithmetic. This file therefore uses two designs that do not condition on the level of
the variable being assessed.

P1 -- WITHIN-CASE DYNAMIC RANGE AGAINST DEPTH, COMPARED BETWEEN MEASURES.
    For each case, compute the within-case interquartile range of a measure across its 21 maintenance
    windows, normalised by that measure's cohort-wide IQR so measures are on a common scale. Then
    correlate that normalised range against the case's mean BIS, separately for BIS and for each
    candidate, and COMPARE THE SLOPES.
    A mean and a spread of the same variable are not independent, so BIS's own slope is not
    interpretable alone. **The comparison against the candidates' slopes on the same cases is the
    estimand**, because whatever mean-variance coupling the design induces applies to every measure.

    PREDICTION: **BIS's normalised range falls more steeply toward deep BIS than the candidates' do**
    -- Spearman(mean BIS, normalised range) more positive for BIS than the median candidate, by at least
    0.15. That is compression.
    WRONG IF: BIS's slope is comparable to or shallower than the candidates'. Then BIS retains its
    resolution at depth and its falling leakage is genuine invariance, which is a real and reportable
    point in the incumbent's favour.

P2 -- DOES BIS STILL TRACK THE STATE TRANSITION AT DEPTH?
    On the peri-landmark cohort, compute BIS's within-patient state-tracking AUC and the candidates', in
    terciles of pre-landmark depth. Stratifying by pre-landmark BIS conditions on BIS, so **the estimand
    is again the DIFFERENCE between BIS and the candidates within the same stratum**, not BIS's level.

    PREDICTION: **BIS's state tracking degrades toward the deep tercile relative to the candidates'** --
    the BIS-minus-candidate gap is more negative in the deepest tercile than in the lightest.
    WRONG IF: BIS tracks state as well at depth as the candidates do.

GATE. G1: both measures must be present on the same cases in every stratum, >= 100 cases per stratum.

**WHAT THIS CAN AND CANNOT ESTABLISH.** Both designs compare measures on the same cases, which controls
the shared conditioning. Neither escapes the fact that depth here is indexed by BIS itself; a result that
BIS compresses relative to candidates is suggestive, not decisive, and the decisive version needs a depth
axis external to both. This limitation is registered, not appended afterwards.

    python -m bsde.experiments.e311_bis_compression
"""
from __future__ import annotations

import argparse, csv, glob, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
ARMS = ("sevo", "des", "ppf")
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
TOP = ["whole_head_exponent", "multiscale_entropy_slope", "critical_slowing_ar1",
       "exponent_low", "spectral_edge_95", "alpha_peak_hz"]


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


def pear(x, y):
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 5:
        return float("nan")
    n = len(q); mx = sum(t[0] for t in q) / n; my = sum(t[1] for t in q) / n
    sxy = sum((t[0] - mx) * (t[1] - my) for t in q)
    sxx = sum((t[0] - mx) ** 2 for t in q); syy = sum((t[1] - my) ** 2 for t in q)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def spear(x, y):
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 5:
        return float("nan")
    return pear(midranks([t[0] for t in q]), midranks([t[1] for t in q]))


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def iqr(v):
    v = sorted(x for x in v if math.isfinite(x))
    if len(v) < 4:
        return float("nan")
    return v[int(0.75 * len(v))] - v[int(0.25 * len(v))]


def pct(v, q):
    v = sorted(x for x in v if math.isfinite(x))
    return v[min(len(v) - 1, int(q * len(v)))] if v else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=311)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e311_bis_compression.json"))
    a = ap.parse_args(argv)

    lm = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_vent_landmarks.s?.csv"))):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r

    def load(pats):
        rows, cols = [], None
        for pat in pats:
            for p in sorted(glob.glob(os.path.join(RESULTS, pat))):
                rd = csv.DictReader(open(p))
                if cols is None:
                    cols = [c for c in (rd.fieldnames or [])
                            if not c.startswith("meta_") and c not in SKIP]
                for r in rd:
                    if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                        rows.append(r)
        by = {}
        for r in rows:
            by.setdefault(r["meta_caseid"], []).append(r)
        return {k: v for k, v in by.items() if len(v) >= 15}, cols

    ctrl, cols = load(["vitaldb_ctrlwin.s?.csv", "vitaldb_ctrlwin2.s?.csv"])
    peri, _ = load(["vitaldb_ventwin.s?.csv"])
    top = [c for c in TOP if c in cols]
    MEAS = ["meta_bis"] + top
    print(f"[cohort] maintenance {len(ctrl)} cases, peri-landmark {len(peri)} cases")

    # ---------------------------------------------------------------- P1
    print("\n" + "=" * 92 + "\nP1 -- within-case dynamic range against depth, compared between measures")
    per = {m: {} for m in MEAS}
    mean_bis = {}
    for cid, rs in ctrl.items():
        b = [f(r.get("meta_bis")) for r in rs]
        mb = med(b)
        if not math.isfinite(mb):
            continue
        mean_bis[cid] = mb
        for m in MEAS:
            per[m][cid] = iqr([f(r.get(m)) for r in rs])
    ids = [i for i in mean_bis if all(math.isfinite(per[m].get(i, float("nan"))) for m in MEAS)]
    print(f"  {len(ids)} cases with all measures")
    coh = {m: med([per[m][i] for i in ids]) for m in MEAS}
    slopes = {}
    for m in MEAS:
        norm = [per[m][i] / coh[m] if coh[m] else float("nan") for i in ids]
        slopes[m] = spear([mean_bis[i] for i in ids], norm)
        print(f"  {m:28s} Spearman(mean BIS, normalised within-case range) = {slopes[m]:+.4f}")
    cand_med = med([slopes[c] for c in top])
    gap = slopes["meta_bis"] - cand_med
    print(f"  BIS {slopes['meta_bis']:+.4f} vs median candidate {cand_med:+.4f}   gap = {gap:+.4f}")
    met1 = math.isfinite(gap) and gap >= 0.15
    print(f"  PREDICTED BIS more positive by >= 0.15 (compression)  ->  "
          f"{'MET' if met1 else 'NOT MET'}")

    # ---------------------------------------------------------------- P2
    print("\n" + "=" * 92 + "\nP2 -- does BIS still track the state transition at depth?")
    pbis, track = {}, {m: {} for m in MEAS}
    for cid, rs in peri.items():
        if lm[cid].get("rec_ok") != "1":
            continue
        t0 = f(lm[cid]["t_rec_s"])
        offs = [f(r.get("meta_t_s")) - t0 for r in rs]
        pre = [f(r.get("meta_bis")) for r, o in zip(rs, offs) if o < 0]
        mb = med(pre)
        if not math.isfinite(mb):
            continue
        pbis[cid] = mb
        for m in MEAS:
            aft = [f(r.get(m)) for r, o in zip(rs, offs) if o > 0]
            bef = [f(r.get(m)) for r, o in zip(rs, offs) if o < 0]
            A = auc(aft, bef)
            track[m][cid] = abs(A - 0.5) if math.isfinite(A) else float("nan")
    ok = [i for i in pbis if all(math.isfinite(track[m].get(i, float("nan"))) for m in MEAS)]
    q1, q2 = pct([pbis[i] for i in ok], 0.333), pct([pbis[i] for i in ok], 0.667)
    terc = {"deep": [i for i in ok if pbis[i] <= q1],
            "mid": [i for i in ok if q1 < pbis[i] <= q2],
            "light": [i for i in ok if pbis[i] > q2]}
    G1 = all(len(v) >= 100 for v in terc.values())
    print(f"  terciles n = { {k: len(v) for k, v in terc.items()} } -> G1 "
          f"{'PASS' if G1 else 'FAIL'}")
    p2 = {}
    for nm, idl in terc.items():
        row = {m: med([track[m][i] for i in idl]) for m in MEAS}
        cm = med([row[c] for c in top])
        row["_candidate_median"] = cm
        row["_bis_minus_candidate"] = row["meta_bis"] - cm
        p2[nm] = row
        print(f"  {nm:6s} BIS {row['meta_bis']:.4f}   candidate median {cm:.4f}   "
              f"gap {row['_bis_minus_candidate']:+.4f}")
    gd = p2["deep"]["_bis_minus_candidate"]; gl = p2["light"]["_bis_minus_candidate"]
    met2 = math.isfinite(gd) and math.isfinite(gl) and gd < gl
    print(f"  gap deep {gd:+.4f} vs light {gl:+.4f}  ->  PREDICTED deep more negative  "
          f"{'MET' if met2 else 'NOT MET'}")

    if not G1:
        verdict = "NOT INTERPRETABLE (G1)"
    elif met1 and met2:
        verdict = ("COMPRESSION -- BIS's falling agent-identifiability at depth is accompanied by a "
                   "loss of both dynamic range and state resolution relative to the candidates")
    elif met1 or met2:
        verdict = "MIXED -- one of the two compression signatures is present, the other is not"
    else:
        verdict = ("GENUINE INVARIANCE -- BIS keeps its range and its state resolution at depth, so its "
                   "falling agent-identifiability is a real point in the incumbent's favour")
    print(f"\nVERDICT: {verdict}")
    print("\nLIMIT, registered in advance: depth here is indexed by BIS itself. Comparing measures on the "
          "same cases controls the shared conditioning, but a decisive test needs a depth axis external "
          "to both. Suggestive, not decisive.")

    rep = {"verdict": verdict, "P1_slopes": slopes, "P1_candidate_median": cand_med,
           "P1_gap": gap, "P1_met": met1, "P1_n": len(ids),
           "P2": p2, "P2_met": met2, "P2_terciles": {k: len(v) for k, v in terc.items()},
           "G1": G1}
    json.dump(rep, open(a.out, "w"), indent=1, default=float)
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
