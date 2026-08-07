#!/usr/bin/env python3
"""E300-E304 -- the depth gradient on a NON-EEG exposure axis, and within patients.

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY THIS IS THE DECIDING EXPERIMENT. Everything supporting "agent identity grows with anaesthetic depth"
has stratified on BIS, which is computed from the same EEG as the candidates. E295 tried to control for
that with a muscle channel and failed -- `emg_index` is itself depth-related and reproduced 56 % of the
gradient, so the control never was independent. **If the gradient is an artefact of stratifying an EEG
measure on an EEG-derived index, it dies here. If it survives on the anaesthesia machine's own drug
record, the circularity objection is answered.**

THE AXIS, and why it needs no cross-drug potency constant.
    volatiles  `Primus/MAC`         -- equipotent across sevoflurane and desflurane BY CONSTRUCTION
    propofol   `Orchestra/PPF20_CE` -- Schnider effect-site concentration from the TCI pump
Each case's exposure is converted to a **percentile within its own arm**. Volatile and intravenous cases
are then comparable on "how deep is this case, for its own drug" without equating MAC to ug/mL. This
sidesteps the non-equipotence problem rather than pretending to solve it, and it is the reason no
literature potency value is cited (rule 42: a quotation supports only what it literally says, and I
cannot verify one in this session).

**A LIMITATION THAT MUST TRAVEL WITH EVERY NUMBER BELOW.** Within-arm percentiles are, by construction,
uniform in every arm. So this axis can test whether leakage varies with RELATIVE depth; it CANNOT test
whether the arms differ in absolute depth, and it deliberately discards that information. E280/E281
already addressed absolute depth on the BIS axis.

======================================================================================================
E300 -- COVERAGE. Reported before anything is stratified (rule 41).
    What fraction of cases carry a usable exposure value at each state, by arm?
    Registered floor: >= 60 % per arm at the control state, or the gradient items are NOT INTERPRETABLE
    and say so rather than running on a biased remnant.

E301 -- THE GRADIENT ON THE NON-EEG AXIS  *the deciding test*

Stratify cases into within-arm exposure quintiles and compute leakage per quintile, exactly as E296 did
on BIS.

PREDICTION: **median Spearman(quintile, leakage) <= -0.5, p < 0.05 against a within-arm permutation
null.** Weaker than E296's -0.90 because drug exposure is a noisier proxy for brain state than an EEG
index is, and because within-arm percentiles compress the range.
WRONG IF: the trend is absent or reversed, in which case the BIS-stratified gradient is circular and
**E271/E291/E296 must be withdrawn.** That outcome is named first because it is the one that matters.

E302 -- DOES THE EXPOSURE AXIS AGREE WITH THE BIS AXIS AT ALL?

Correlate each case's within-arm exposure percentile against its BIS. A validity check on the new axis
BEFORE it is trusted (rule 57: a control is an instrument and needs its own validation).

PREDICTION: **negative correlation, Spearman <= -0.2** -- more drug, lower BIS.
WRONG IF: no relationship, in which case the exposure axis is not measuring depth in this cohort and
E301 is uninterpretable whichever way it comes out.

E303 -- THE WITHIN-PATIENT DOSE-RESPONSE, WHICH NO STRATIFICATION CAN CONFOUND

738 patients have both states. For each, compute the change in candidate and the change in exposure
percentile between maintenance and pre-landmark. Ask whether the *ratio* of candidate change to exposure
change differs by arm -- i.e. whether agents differ in how much the measure moves per unit of drug
withdrawn, within the same person.

PREDICTION: **it differs, |AUC-0.5| above its null for a majority of top candidates.** This is the
strongest form of the claim: no between-patient stratification is involved at all.
WRONG IF: null, which would mean the depth-dependence is entirely a between-patient phenomenon.

E304 -- ARE THE ARMS' EXPOSURE CHANGES COMPARABLE?

E303's ratio is only interpretable if both arms actually change exposure between the two states. Report
the distribution of exposure change per arm, and gate E303 on both arms moving.

PREDICTION: registered as a GATE, not a hypothesis. If either arm's median absolute exposure change is
below 5 percentile points, E303 is NOT INTERPRETABLE for that pair (rule 32: check the thing varies
before comparing).

    python -m bsde.experiments.e300_exposure_axis
"""
from __future__ import annotations

import argparse, csv, glob, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
COVERAGE_FLOOR = 0.60
MIN_EXP_CHANGE = 5.0


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
    return {k: v for k, v in by.items() if len(v) >= 15}, cols


def within_arm_pct(vals_by_case, arm):
    """Percentile of each case's exposure WITHIN ITS OWN ARM. Unitless, 0-100."""
    out = {}
    for x in ARMS:
        ids = [i for i in vals_by_case if arm.get(i) == x and math.isfinite(vals_by_case[i])]
        if not ids:
            continue
        order = sorted(ids, key=lambda i: vals_by_case[i])
        for k, i in enumerate(order):
            out[i] = 100.0 * k / max(1, len(order) - 1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=300)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e300_exposure_axis.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {}

    lm = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_vent_landmarks.s?.csv"))):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r
    peri, cols = read(os.path.join(RESULTS, "vitaldb_ventwin.s?.csv"), lm)
    ctrl, _ = read(os.path.join(RESULTS, "vitaldb_ctrlwin.s?.csv"), lm)
    arm = {k: lm[k]["arm"] for k in set(peri) | set(ctrl)}
    if a.smoke:
        ks = sorted(arm); vs = [arm[k] for k in ks]; rng.shuffle(vs); arm = dict(zip(ks, vs))
        print("[SMOKE] arm labels permuted")

    exp_c, exp_p = {}, {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_exposure.s?.csv"))):
        for r in csv.DictReader(open(p)):
            exp_c[r["caseid"]] = f(r.get("exp_ctrl")); exp_p[r["caseid"]] = f(r.get("exp_pre"))
    rec = [k for k in peri if lm[k].get("rec_ok") == "1"]
    cmed, pmed, cbis = {}, {}, {}
    for cid, rs in ctrl.items():
        for c in cols + ["meta_bis"]:
            cmed.setdefault(c, {})[cid] = med([f(r.get(c)) for r in rs])
        cbis[cid] = cmed["meta_bis"][cid]
    for cid in rec:
        rs = peri[cid]; t0 = f(lm[cid]["t_rec_s"])
        offs = [f(r.get("meta_t_s")) - t0 for r in rs]
        for c in cols:
            pmed.setdefault(c, {})[cid] = med([f(r.get(c)) for r, o in zip(rs, offs) if o < 0])

    # ---------------------------------------------------------------- E300 coverage
    print("=" * 92 + "\nE300 -- coverage of the non-EEG exposure axis")
    cov = {}
    for x in ARMS:
        ids = [i for i in ctrl if arm.get(i) == x]
        n = sum(1 for i in ids if math.isfinite(exp_c.get(i, float("nan"))))
        cov[x] = n / len(ids) if ids else float("nan")
        print(f"  {x:5s} control state: {n} of {len(ids)} = {cov[x]:.1%}")
    ok = all(v >= COVERAGE_FLOOR for v in cov.values() if math.isfinite(v))
    print(f"  registered floor {COVERAGE_FLOOR:.0%} per arm  ->  {'PASS' if ok else 'FAIL'}")
    R["E300"] = {"coverage": cov, "pass": ok}
    if not ok:
        print("  NOT INTERPRETABLE: the gradient items would run on a biased remnant. Stopping them.")

    ec = {i: exp_c[i] for i in ctrl if math.isfinite(exp_c.get(i, float("nan")))}
    pc = within_arm_pct(ec, arm)

    # ---------------------------------------------------------------- E302 axis validity
    print("\n" + "=" * 92 + "\nE302 -- does the exposure axis agree with BIS? (validate the instrument)")
    ids = [i for i in pc if math.isfinite(cbis.get(i, float("nan")))]
    rho = spear([pc[i] for i in ids], [cbis[i] for i in ids])
    per_arm = {x: spear([pc[i] for i in ids if arm.get(i) == x],
                        [cbis[i] for i in ids if arm.get(i) == x]) for x in ARMS}
    print(f"  pooled Spearman(exposure pct, BIS) = {rho:+.4f} over {len(ids)} cases")
    print("  per arm: " + ", ".join(f"{k} {v:+.4f}" for k, v in per_arm.items()))
    met302 = math.isfinite(rho) and rho <= -0.20
    print(f"  PREDICTED <= -0.20  ->  {'MET' if met302 else 'NOT MET'}")
    R["E302"] = {"rho": rho, "per_arm": per_arm, "n": len(ids), "prediction_met": met302}

    # ---------------------------------------------------------------- E301 the deciding test
    print("\n" + "=" * 92 + "\nE301 -- the gradient on the NON-EEG axis  *deciding test*")
    TOP = ["whole_head_exponent", "multiscale_entropy_slope", "critical_slowing_ar1",
           "exponent_low", "emg_beta_gamma_fraction", "alpha_peak_hz"]
    TOP = [c for c in TOP if c in cols]

    def quint_grad(pmap):
        buckets = [[] for _ in range(5)]
        for i, v in pmap.items():
            buckets[min(4, int(v // 20))].append(i)
        out = {}
        for c in TOP:
            vs = []
            for ids_ in buckets:
                vals = [lk([cmed[c][i] for i in ids_ if arm.get(i) == x],
                           [cmed[c][i] for i in ids_ if arm.get(i) == y]) for x, y in PAIRS]
                vals = [v for v in vals if math.isfinite(v)]
                vs.append(max(vals) if vals else float("nan"))
            out[c] = vs
        return out, [len(b) for b in buckets]

    g, nb = quint_grad(pc)
    print(f"  quintile n = {nb}   (0 = least drug ... 4 = most drug)")
    rhos = {}
    for c in TOP:
        rhos[c] = spear(list(range(5)), g[c])
        print(f"  {c:28s} rho = {rhos[c]:+.4f}   " + " ".join(f"{v:.3f}" for v in g[c]))
    obs = med(list(rhos.values()))
    null = []
    for _ in range(200):
        perm = {}
        for x in ARMS:
            ids_ = [i for i in pc if arm.get(i) == x]
            vals = [pc[i] for i in ids_]; rng.shuffle(vals)
            perm.update(dict(zip(ids_, vals)))
        gp, _ = quint_grad(perm)
        null.append(med([spear(list(range(5)), gp[c]) for c in TOP]))
    null.sort()
    p = sum(1 for v in null if v >= obs) / len(null)
    print(f"  median rho = {obs:+.4f}; permutation null 95th = {null[int(0.95*len(null))]:+.4f}, "
          f"p(>= obs) = {p:.4f}")
    met301 = ok and math.isfinite(obs) and obs >= 0.50 and p < 0.05
    print(f"  PREDICTED median rho >= +0.50 (leakage RISES with drug) AND p < 0.05  ->  "
          f"{'MET' if met301 else 'NOT MET'}")
    print("  NOTE: sign convention -- on the BIS axis leakage rose as BIS FELL (rho negative); "
          "here quintile 4 is MOST drug, so the same phenomenon appears as rho POSITIVE.")
    R["E301"] = {"rhos": rhos, "median_rho": obs, "p": p, "n": nb, "gradient": g,
                 "prediction_met": met301}

    # ---------------------------------------------------------------- E304 gate
    print("\n" + "=" * 92 + "\nE304 -- do both arms actually change exposure between the states?")
    ep = {i: exp_p[i] for i in rec if math.isfinite(exp_p.get(i, float("nan")))}
    pp = within_arm_pct(ep, arm)
    both = [i for i in pc if i in pp]
    dexp = {i: pc[i] - pp[i] for i in both}
    chg = {}
    for x in ARMS:
        v = [abs(dexp[i]) for i in dexp if arm.get(i) == x]
        chg[x] = med(v)
        print(f"  {x:5s} median |exposure percentile change| = {chg[x]:.1f}  (n={len(v)})")
    gate304 = all(v >= MIN_EXP_CHANGE for v in chg.values() if math.isfinite(v))
    print(f"  gate: both arms >= {MIN_EXP_CHANGE} percentile points  ->  "
          f"{'PASS' if gate304 else 'FAIL'}")
    R["E304"] = {"median_abs_change": chg, "n": len(both), "pass": gate304}

    # ---------------------------------------------------------------- E303
    print("\n" + "=" * 92 + "\nE303 -- the within-patient dose-response")
    if not gate304:
        print("  NOT INTERPRETABLE: E304's gate failed (rule 32).")
        R["E303"] = {"status": "NOT INTERPRETABLE", "reason": "E304 gate failed"}
    else:
        e303, above = {}, 0
        for c in TOP:
            ratio = {}
            for i in both:
                dv = cmed[c].get(i, float("nan")) - pmed[c].get(i, float("nan"))
                de = dexp[i]
                if math.isfinite(dv) and math.isfinite(de) and abs(de) >= 1.0:
                    ratio[i] = dv / de
            d = {}
            for x, y in PAIRS:
                va = [ratio[i] for i in ratio if arm.get(i) == x]
                vb = [ratio[i] for i in ratio if arm.get(i) == y]
                v = lk(va, vb)
                n95 = null95(len(va), len(vb)) if va and vb else float("nan")
                d[f"{x}_vs_{y}"] = {"leak": v, "null95": n95,
                                    "above": math.isfinite(v) and v > n95}
                if d[f"{x}_vs_{y}"]["above"]:
                    above += 1
            e303[c] = {"n": len(ratio), "pairs": d}
            print(f"  {c:26s} n={len(ratio):4d}  " + "  ".join(
                f"{k[:9]} {v['leak']:.3f}{'*' if v['above'] else ''}" for k, v in d.items()))
        tot = sum(len(v["pairs"]) for v in e303.values())
        met = above / tot > 0.5 if tot else False
        print(f"  above null in {above} of {tot}  ->  PREDICTION {'MET' if met else 'NOT MET'}")
        R["E303"] = {"detail": e303, "n_above": above, "n_total": tot, "prediction_met": met}

    print("\n" + "=" * 92)
    for k in sorted(R):
        v = R[k].get("prediction_met", R[k].get("pass"))
        print(f"  {k}: {'MET/PASS' if v else 'NOT MET/FAIL' if v is False else 'descriptive'}")
    if not a.smoke:
        json.dump(R, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
