#!/usr/bin/env python3
"""E290-E299 -- fifth battery. Hardening the one claim that might matter outside this repo.

PRE-REGISTRATION. Committed before any statistic in it exists.

THE CLAIM UNDER TEST, stated plainly so it can be attacked: **anaesthetic-agent identity in frontal EEG
is strongly state-dependent -- large at maintenance, small at emergence, graded with depth -- and the
RANKING of which measures leak most barely transports between states.** If true, a "drug-invariant EEG"
claim is uninterpretable without the depth at which invariance was measured, and measuring at emergence
flatters a representation by roughly a factor of five.

Evidence so far: E260 (0.35-0.38 at maintenance vs 0.06-0.07 peri-landmark), E271 (monotone across BIS
terciles), E274 (rank Spearman +0.29 to +0.37), E281 (survives BIS matching, rule 17).

KNOWN WEAKNESSES THIS BATTERY ATTACKS, and the ones it cannot:
  * one deposit, two frontal channels, ventilation label -- NOT attacked here, not attackable here;
  * BIS is the only depth axis available and it is EEG-derived, so stratifying leakage of an EEG measure
    by an EEG index risks circularity -- E295;
  * the maintenance/emergence gap could be depth OR could be the transition itself -- E298;
  * "monotone in 6 of 6" was a weak statistic against a null whose 95th is 4 -- E296;
  * the two states come from different-sized cohorts -- E297;
  * it could be one arm's doing -- E299.

COHORTS. PERI = 2,589 cases peri-landmark (2,573 with recovery). CTRL = 740 at maintenance.

======================================================================================================
E290 -- NOVELTY. Recorded as PARTIAL/BLOCKED before the run and not upgraded afterwards.

PubMed returned 7 records for "anesthetic agent classification EEG depends on depth of anesthesia"
(PMIDs 40638527, 40113116, 35404821, 34517477, 20051218, 15816591, 12885180) and **zero** for the
narrower phrasings tried. **The metadata tool requires interactive approval unavailable in this session,
so no record could be verified from MEDLINE.** Rules 25 and 39: no citation is made, no novelty is
claimed, and this item is reported as unresolved. A session that can fetch them owes this check before
any external claim.

E291 -- DOES THE DEPTH GRADIENT REPLICATE IN THE PERI COHORT, AT 3.5x THE n?

E271 used CTRL (740 cases). PERI has 2,573, each with a pre-landmark median BIS. Stratify PERI cases by
that and recompute PERI leakage per tercile.

PREDICTION: **the gradient reproduces -- deepest tercile highest for a majority of top candidates.**
WRONG IF: flat in PERI, which would confine the gradient to the control extraction and make it a property
of that particular window rather than of depth.

E292 -- DOES BIS'S OWN LEAKAGE GROW WITH DEPTH?

PREDICTION: **yes, same direction as the candidates.** BIS is a spectral composite; if depth amplifies the
drug signature it should amplify BIS's too.
WRONG IF: BIS is flat across depth while candidates are not -- which would be a strong point in the
incumbent's favour and would need saying.

E293 -- WHAT IS THE EFFECT IN UNITS ANYONE CAN READ?

|AUC-0.5| is not interpretable to a clinician. Report, per top candidate and pair, the arm medians and
their difference in native units, plus Cliff's delta.

PREDICTION: descriptive, no threshold. Registered so the numbers are reported rather than only the AUCs.

E294 -- THE WITHIN-PATIENT DEPTH CONTRAST, WHICH REMOVES BETWEEN-PATIENT CONFOUNDING ENTIRELY

738 patients appear in BOTH cohorts. For each, compute the candidate at maintenance and at pre-landmark.
The maintenance-minus-preland difference is a within-patient depth change. Ask whether that DIFFERENCE
identifies the agent.

PREDICTION: **it does, |AUC-0.5| above its null for a majority of top candidates.** Agents differ in how
far the measure moves between depths, not only in where it sits.
WRONG IF: the within-patient difference carries no agent identity, which would mean the whole effect is a
between-patient level offset and the "state-dependence" is really "the offset is bigger when deeper".
BOTH OUTCOMES ARE INFORMATIVE and the second is the more deflationary; it is named first on purpose.

E295 -- IS THE GRADIENT AN ARTEFACT OF STRATIFYING AN EEG MEASURE BY AN EEG INDEX?

Repeat E271 stratifying by a measure that is NOT BIS and NOT the candidate being tested -- for each
candidate, stratify by `emg_index` (a muscle channel, not a spectral depth index) and separately re-run
with BIS. A gradient present under BIS and absent under an unrelated stratifier is suspect.

PREDICTION: **the gradient is much weaker or absent under the muscle stratifier**, confirming it is depth
and not an artefact of stratifying on any correlated variable.
WRONG IF: an equally strong gradient appears under a muscle stratifier, which would mean stratification
itself manufactures gradients here and E271 means little.

E296 -- REPLACE THE MONOTONE COUNT WITH A TREND TEST (E282's registered prediction failed)

E282's null had a 95th percentile of 4 of 6, so "monotone in 6 of 6" is weaker than it reads. Use
quintiles and a Spearman of leakage against quintile index per candidate, with the same within-arm
BIS permutation null.

PREDICTION: **median Spearman across top candidates <= -0.8 (leakage falls as BIS rises), p < 0.05
against the permutation null.**
WRONG IF: the trend is weak once measured continuously rather than as a monotone flag.

E297 -- IS THE PERI/CTRL GAP AN ARTEFACT OF COHORT SIZE?

|AUC-0.5| is not mechanically n-dependent but its sampling error is. Subsample PERI to 740 cases,
250 per arm, 200 times, and compare the distribution of PERI leakage against the CTRL point estimate.

PREDICTION: **the CTRL value lies far above the subsampled PERI distribution** (above its 99th percentile
for the top candidates).
WRONG IF: CTRL sits inside the PERI subsample spread, meaning the gap is noise.

E298 -- DEPTH, OR THE TRANSITION ITSELF?  *the sharpest available test*

Restrict PERI to its DEEPEST pre-landmark BIS windows and CTRL to its LIGHTEST, so the two cohorts
overlap in BIS, then compare leakage at matched BIS.

PREDICTION: **leakage is similar at matched BIS**, i.e. the whole PERI/CTRL gap is depth and the landmark
adds nothing.
WRONG IF: PERI remains lower at matched BIS, which would mean proximity to the transition suppresses the
drug signature independently of depth -- a different and more interesting claim, and one that would
change what the successor should measure.

E299 -- IS THE GRADIENT ONE ARM'S DOING?

Recompute the depth gradient using only the two pairs that exclude each arm in turn.

PREDICTION: **the gradient survives the removal of any single arm.**
WRONG IF: it depends on propofol (or on desflurane, the smallest arm), which would make it a statement
about one drug rather than about depth.

    python -m bsde.experiments.e290_battery5
"""
from __future__ import annotations

import argparse, csv, glob, json, math, os, random

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


def lk(a_, b_, minn=8):
    a_ = [x for x in a_ if math.isfinite(x)]; b_ = [x for x in b_ if math.isfinite(x)]
    if len(a_) < minn or len(b_) < minn:
        return float("nan")
    return abs(auc(a_, b_) - 0.5)


def null95(n1, n2):
    return 1.959964 * math.sqrt((n1 + n2 + 1) / (12.0 * n1 * n2))


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
    if len(p) < 3:
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


def grad(cmap, bmap, arm, cols, nq=3, exclude=None):
    """Leakage per depth quantile. Returns {candidate: [q0..qn-1]} ordered deep -> light."""
    pairs = [(x, y) for x, y in PAIRS if exclude not in (x, y)]
    cuts = [pct(list(bmap.values()), (i + 1) / nq) for i in range(nq - 1)]
    buckets = [[] for _ in range(nq)]
    for i, b in bmap.items():
        k = 0
        while k < nq - 1 and b > cuts[k]:
            k += 1
        buckets[k].append(i)
    out = {}
    for c in cols:
        vs = []
        for ids in buckets:
            vals = [lk([cmap[c][i] for i in ids if arm.get(i) == x],
                       [cmap[c][i] for i in ids if arm.get(i) == y]) for x, y in pairs]
            vals = [v for v in vals if math.isfinite(v)]
            vs.append(max(vals) if vals else float("nan"))
        out[c] = vs
    return out, [len(b) for b in buckets]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=290)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e290_battery5.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {"E290": {"status": "PARTIAL/BLOCKED", "pmids_found":
                  ["40638527", "40113116", "35404821", "34517477", "20051218", "15816591", "12885180"],
                  "note": "metadata tool requires interactive approval; no record verified from "
                          "MEDLINE; rules 25/39 -- no citation, no novelty claim"}}
    print("E290 -- NOVELTY: PARTIAL/BLOCKED. 7 candidate PMIDs found, none verifiable in this session. "
          "No citation made, no novelty claimed.")

    lm = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_vent_landmarks.s?.csv"))):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r
    peri, cols, prows = read(os.path.join(RESULTS, "vitaldb_ventwin.s?.csv"), lm)
    ctrl, _, _ = read(os.path.join(RESULTS, "vitaldb_ctrlwin.s?.csv"), lm)
    fin = {c: sum(1 for r in prows if math.isfinite(f(r.get(c)))) for c in cols}
    cols = [c for c in cols if fin[c] >= 0.20 * len(prows)]
    arm = {k: lm[k]["arm"] for k in set(peri) | set(ctrl)}
    if a.smoke:
        ks = sorted(arm); vs = [arm[k] for k in ks]; rng.shuffle(vs); arm = dict(zip(ks, vs))
        print("[SMOKE] arm labels permuted; every leakage recomputed under it")
    rec = [k for k in peri if lm[k].get("rec_ok") == "1"]
    t0 = {k: f(lm[k]["t_rec_s"]) for k in rec}

    cmed, pmed, pbis, cbis, cemg = {}, {}, {}, {}, {}
    for cid, rs in ctrl.items():
        for c in cols + ["meta_bis", "emg_index"]:
            cmed.setdefault(c, {})[cid] = med([f(r.get(c)) for r in rs])
        cbis[cid] = cmed["meta_bis"][cid]; cemg[cid] = cmed.get("emg_index", {}).get(cid, float("nan"))
    for cid in rec:
        rs = peri[cid]; offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
        for c in cols + ["meta_bis"]:
            pmed.setdefault(c, {})[cid] = med([f(r.get(c)) for r, o in zip(rs, offs) if o < 0])
        pbis[cid] = pmed["meta_bis"][cid]
    cbis = {k: v for k, v in cbis.items() if math.isfinite(v)}
    pbis = {k: v for k, v in pbis.items() if math.isfinite(v)}
    CTRL_LK = {c: max([v for v in (lk([cmed[c][i] for i in ctrl if arm.get(i) == x],
                                      [cmed[c][i] for i in ctrl if arm.get(i) == y])
                                   for x, y in PAIRS) if math.isfinite(v)] or [float("nan")])
               for c in cols}
    TOP = sorted(cols, key=lambda c: -(CTRL_LK[c] if math.isfinite(CTRL_LK[c]) else -9))[:6]
    print(f"[cohorts] PERI {len(peri)} ({len(pbis)} with BIS) / CTRL {len(ctrl)} ({len(cbis)} with BIS)")

    # ---------------------------------------------------------------- E291
    print("\n" + "=" * 92 + "\nE291 -- does the depth gradient replicate in PERI, at 3.5x the n?")
    g, nb = grad(pmed, pbis, arm, TOP, 3)
    print(f"  PERI tercile n = {nb}")
    down = 0
    for c in TOP:
        v = g[c]
        ok = all(math.isfinite(x) for x in v) and v[0] >= v[2]
        down += 1 if ok else 0
        print(f"  {c:28s} deep {v[0]:.4f}  mid {v[1]:.4f}  light {v[2]:.4f}{'  v' if ok else ''}")
    met = down > len(TOP) / 2
    print(f"  deep >= light in {down} of {len(TOP)}  ->  PREDICTION {'MET' if met else 'NOT MET'}")
    R["E291"] = {"gradient": g, "n": nb, "n_down": down, "prediction_met": met}

    # ---------------------------------------------------------------- E292
    print("\n" + "=" * 92 + "\nE292 -- does BIS's own leakage grow with depth?")
    gb, _ = grad(cmed, cbis, arm, ["meta_bis"], 3)
    v = gb["meta_bis"]
    print(f"  CTRL: deep {v[0]:.4f}  mid {v[1]:.4f}  light {v[2]:.4f}")
    met = math.isfinite(v[0]) and math.isfinite(v[2]) and v[0] >= v[2]
    print(f"  PREDICTED deep >= light  ->  {'MET' if met else 'NOT MET'}")
    R["E292"] = {"gradient": v, "prediction_met": met}

    # ---------------------------------------------------------------- E293
    print("\n" + "=" * 92 + "\nE293 -- the effect in readable units (descriptive)")
    e293 = {}
    for c in TOP[:4]:
        d = {}
        for x, y in PAIRS:
            va = [cmed[c][i] for i in ctrl if arm.get(i) == x]
            vb = [cmed[c][i] for i in ctrl if arm.get(i) == y]
            A = auc(va, vb)
            d[f"{x}_vs_{y}"] = {"median_a": med(va), "median_b": med(vb),
                                "diff": med(va) - med(vb), "cliffs_delta": 2 * A - 1 if
                                math.isfinite(A) else float("nan")}
        e293[c] = d
        print(f"  {c}")
        for k, v2 in d.items():
            print(f"     {k:14s} {v2['median_a']:+9.4f} vs {v2['median_b']:+9.4f}  "
                  f"diff {v2['diff']:+8.4f}   Cliff's delta {v2['cliffs_delta']:+.3f}")
    R["E293"] = e293

    # ---------------------------------------------------------------- E294
    print("\n" + "=" * 92 + "\nE294 -- the within-patient depth contrast")
    both = [i for i in ctrl if i in pmed.get(TOP[0], {})]
    e294, above = {}, 0
    for c in TOP:
        dif = {i: cmed[c][i] - pmed[c][i] for i in both
               if math.isfinite(cmed[c][i]) and math.isfinite(pmed[c][i])}
        d = {}
        for x, y in PAIRS:
            va = [dif[i] for i in dif if arm.get(i) == x]; vb = [dif[i] for i in dif if arm.get(i) == y]
            v = lk(va, vb); n95 = null95(len(va), len(vb)) if va and vb else float("nan")
            d[f"{x}_vs_{y}"] = {"leak": v, "null95": n95, "above": math.isfinite(v) and v > n95}
            if d[f"{x}_vs_{y}"]["above"]:
                above += 1
        e294[c] = d
        print(f"  {c:26s} " + "  ".join(f"{k[:9]} {v2['leak']:.3f}"
              f"{'*' if v2['above'] else ''}" for k, v2 in d.items()))
    tot = sum(len(v) for v in e294.values())
    met = above / tot > 0.5
    print(f"  above null in {above} of {tot} (n={len(both)} patients)  ->  "
          f"PREDICTION {'MET' if met else 'NOT MET'}")
    R["E294"] = {"detail": e294, "n_above": above, "n_total": tot, "n_patients": len(both),
                 "prediction_met": met}

    # ---------------------------------------------------------------- E295
    print("\n" + "=" * 92 + "\nE295 -- gradient under BIS vs under an unrelated (muscle) stratifier")
    emgmap = {i: cemg[i] for i in ctrl if math.isfinite(cemg.get(i, float("nan")))}
    gB, _ = grad(cmed, cbis, arm, TOP, 3)
    gE, nE = grad(cmed, emgmap, arm, TOP, 3)
    sB = med([gB[c][0] - gB[c][2] for c in TOP if all(math.isfinite(v) for v in gB[c])])
    sE = med([gE[c][0] - gE[c][2] for c in TOP if all(math.isfinite(v) for v in gE[c])])
    for c in TOP:
        print(f"  {c:26s} BIS {gB[c][0]:.3f}->{gB[c][2]:.3f} (drop {gB[c][0]-gB[c][2]:+.3f}) | "
              f"EMG {gE[c][0]:.3f}->{gE[c][2]:.3f} (drop {gE[c][0]-gE[c][2]:+.3f})")
    met = math.isfinite(sB) and math.isfinite(sE) and abs(sE) < 0.5 * abs(sB)
    print(f"  median deep-light drop: BIS {sB:+.4f}   muscle {sE:+.4f}  ->  "
          f"PREDICTION {'MET' if met else 'NOT MET'}")
    R["E295"] = {"bis_drop": sB, "emg_drop": sE, "prediction_met": met}

    # ---------------------------------------------------------------- E296
    print("\n" + "=" * 92 + "\nE296 -- trend test on quintiles, replacing the monotone count")
    gq, nq_ = grad(cmed, cbis, arm, TOP, 5)
    rhos = {c: spear(list(range(5)), gq[c]) for c in TOP}
    obs = med(list(rhos.values()))
    null = []
    for _ in range(200):
        perm = {}
        for x in ARMS:
            ids = [i for i in cbis if arm.get(i) == x]
            vals = [cbis[i] for i in ids]; rng.shuffle(vals)
            perm.update(dict(zip(ids, vals)))
        gp, _ = grad(cmed, perm, arm, TOP, 5)
        null.append(med([spear(list(range(5)), gp[c]) for c in TOP]))
    null.sort()
    p = sum(1 for v in null if v <= obs) / len(null)
    print(f"  quintile n = {nq_}")
    for c in TOP:
        print(f"  {c:28s} rho(quintile, leakage) = {rhos[c]:+.4f}   "
              + " ".join(f"{v:.3f}" for v in gq[c]))
    print(f"  median rho = {obs:+.4f}; permutation null 5th = {null[int(0.05*len(null))]:+.4f}, "
          f"p = {p:.4f}")
    met = obs <= -0.8 and p < 0.05
    print(f"  PREDICTED median rho <= -0.8 AND p < 0.05  ->  {'MET' if met else 'NOT MET'}")
    R["E296"] = {"rhos": rhos, "median_rho": obs, "p": p, "prediction_met": met}

    # ---------------------------------------------------------------- E297
    print("\n" + "=" * 92 + "\nE297 -- is the PERI/CTRL gap an artefact of cohort size?")
    e297 = {}
    for c in TOP[:4]:
        dist = []
        for _ in range(200):
            sub = {}
            for x in ARMS:
                ids = [i for i in rec if arm.get(i) == x]
                rng.shuffle(ids); sub[x] = ids[:250]
            dist.append(max([v for v in (lk([pmed[c][i] for i in sub[x]],
                                            [pmed[c][i] for i in sub[y]])
                                         for x, y in PAIRS) if math.isfinite(v)] or [float("nan")]))
        dist = sorted(v for v in dist if math.isfinite(v))
        p99 = dist[int(0.99 * len(dist))] if dist else float("nan")
        e297[c] = {"ctrl": CTRL_LK[c], "peri_sub_median": med(dist), "peri_sub_p99": p99,
                   "above": CTRL_LK[c] > p99}
        print(f"  {c:26s} CTRL {CTRL_LK[c]:.4f}   PERI-subsampled median {med(dist):.4f}, "
              f"99th {p99:.4f}  {'ABOVE' if CTRL_LK[c] > p99 else 'inside'}")
    met = all(v["above"] for v in e297.values())
    print(f"  PREDICTED CTRL above the PERI 99th for all  ->  {'MET' if met else 'NOT MET'}")
    R["E297"] = {"detail": e297, "prediction_met": met}

    # ---------------------------------------------------------------- E298
    print("\n" + "=" * 92 + "\nE298 -- depth, or the transition itself?")
    lo = max(pct(list(pbis.values()), 0.0), pct(list(cbis.values()), 0.60))
    hi = min(pct(list(pbis.values()), 0.40), pct(list(cbis.values()), 1.0))
    pk = [i for i in pbis if lo <= pbis[i] <= hi]
    ck = [i for i in cbis if lo <= cbis[i] <= hi]
    print(f"  matched BIS band [{lo:.1f}, {hi:.1f}]: PERI {len(pk)} cases, CTRL {len(ck)} cases")
    e298 = {}
    for c in TOP:
        pv = max([v for v in (lk([pmed[c][i] for i in pk if arm.get(i) == x],
                                 [pmed[c][i] for i in pk if arm.get(i) == y])
                              for x, y in PAIRS) if math.isfinite(v)] or [float("nan")])
        cv = max([v for v in (lk([cmed[c][i] for i in ck if arm.get(i) == x],
                                 [cmed[c][i] for i in ck if arm.get(i) == y])
                              for x, y in PAIRS) if math.isfinite(v)] or [float("nan")])
        e298[c] = {"peri_matched": pv, "ctrl_matched": cv,
                   "ratio": pv / cv if cv and math.isfinite(cv) and cv > 0 else float("nan")}
        print(f"  {c:28s} PERI@matchedBIS {pv:.4f}   CTRL@matchedBIS {cv:.4f}   "
              f"ratio {e298[c]['ratio']:.3f}")
    rr = [v["ratio"] for v in e298.values() if math.isfinite(v["ratio"])]
    met = med(rr) >= 0.70
    print(f"  median ratio {med(rr):.3f}  ->  PREDICTED >= 0.70 (gap is depth)  "
          f"{'MET' if met else 'NOT MET'}")
    R["E298"] = {"detail": e298, "median_ratio": med(rr), "band": [lo, hi],
                 "n": [len(pk), len(ck)], "prediction_met": met}

    # ---------------------------------------------------------------- E299
    print("\n" + "=" * 92 + "\nE299 -- is the gradient one arm's doing?")
    e299 = {}
    for ex in ARMS:
        ge, _ = grad(cmed, cbis, arm, TOP, 3, exclude=ex)
        drop = med([ge[c][0] - ge[c][2] for c in TOP if all(math.isfinite(v) for v in ge[c])])
        e299[f"without_{ex}"] = drop
        print(f"  without {ex:5s}: median deep-light drop {drop:+.4f}")
    met = all(v > 0 for v in e299.values() if math.isfinite(v))
    print(f"  PREDICTED gradient survives removing any single arm  ->  "
          f"{'MET' if met else 'NOT MET'}")
    R["E299"] = {"detail": e299, "prediction_met": met}

    print("\n" + "=" * 92)
    for k in sorted(R):
        v = R[k].get("prediction_met")
        print(f"  {k}: {'MET' if v else 'NOT MET' if v is False else 'descriptive/blocked'}")
    if not a.smoke:
        json.dump(R, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print("\n[SMOKE] complete; nothing above is a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
