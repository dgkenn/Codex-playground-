#!/usr/bin/env python3
"""E141 -- E36's family split under an adjustment strong enough to be worth trusting, with probe gates.

REGISTERED BEFORE ANY ADJUSTED FEATURE AUC HAS BEEN COMPUTED. Successor to E140, which returned NO
VERDICT because all three of its adjustments failed GATE Q. What changed is the adjustment and the gates;
the question, the cohort, the families and the bar are E140's untouched.

=========================================================================================================
WHAT E140 ESTABLISHED, AND WHERE ITS GATE WENT WRONG
=========================================================================================================
The question is whether E36's headline -- amplitude features leak drug identity at 0.217-0.368 while phase
features leak 0.000-0.128 -- is a statement about drugs or about recording quality, given E139's finding
that `pctGoodSamples` alone identifies the agent at |AUC-0.5| = 0.2565 among the same 115 unresponsive
scalp blocks.

E140 tried three adjustments and none passed its own gate:

    A1 rank residual   quality legibility NaN  -- GATE Q is INAPPLICABLE to A1, not failed: residualising
                                                  rank(quality) on rank(quality) is degenerate by
                                                  construction. My gate, my defect (rule 30).
    A2 caliper 0.01    quality legibility +0.1660  -- genuinely too weak
    A3 quintiles       quality legibility +0.0661  -- genuinely too weak, and unstable: sweeping the
                                                  stratum count gives 0.0661, 0.0684, 0.0056, 0.0672,
                                                  0.0920 for k = 5, 8, 10, 15, 20, which is not an
                                                  estimator anyone should build a verdict on.

E140's one informative number was its rule-35 control: the quality-matched GAP of -0.0098 sat at the
**0.9 percent point** of the null formed by 1,000 subsamples matched on n but NOT on quality (median
+0.0905, [+0.0115, +0.1603]). So the collapse under matching is not sample-size loss. That is suggestive
and it is not claimed, because it came from an adjustment that failed its gate.

=========================================================================================================
THE ADJUSTMENT
=========================================================================================================
**OVERLAP WEIGHTING (Li, Morgan & Zaslavsky, JASA 2018).** Fit the propensity of arm on rank(quality);
weight each block by `1 - e` if dexmedetomidine and `e` if propofol. The weighted arms then have identical
quality distributions by construction, every block is retained, and the estimand is the contrast in the
region of common support -- which is exactly the population where a drug-identity question is answerable
at all. It is standard, it is citable, and unlike matching it discards nothing.

Two comparators, both reported, neither primary:
    A5  INVERSE PROBABILITY WEIGHTING, the same propensity, weights `1/e` and `1/(1-e)`.
    A2' CALIPER MATCHING at **0.003**, which the quality-only sweep below shows is the largest caliper
        that leaves quality illegible. Carries E140's rule-35 size-only control.

**PRE-CHECKED ON THE QUALITY COLUMN ALONE AND DISCLOSED (rule 41).** Before registration, and touching no
feature, quality's own legibility was measured under each: raw +0.2565, overlap-weighted **+0.0002**, IPW
**+0.0263**, caliper-0.003 **+0.0432** (27 pairs; the sweep gave 0.0175 / 0.0200 / 0.0266 / 0.0432 /
0.0945 / 0.1660 / 0.2641 at calipers 0.0005 / 0.001 / 0.002 / 0.003 / 0.005 / 0.01 / 0.02). The caliper was
chosen from that sweep, i.e. **from the placebo, never from the primary** -- the quality column and the arm
labels are the only inputs to the choice.

**Which means E140's GATE Q can no longer fail, and a gate that cannot fail is not a gate (rule 40).** It
is retained as a reported check and replaced, as the actual gates, by three synthetic probes that have NOT
been run.

=========================================================================================================
THE PROBE GATES -- and GATE P is the one that makes the design mean anything
=========================================================================================================
Synthetic columns are injected into the real rows and pushed through the identical code path as a feature.

GATE S  SUFFICIENCY. Probes built as `monotone(quality) + sigma * noise` for three monotone maps
        (identity, log, square) and sigma in {0.25, 0.5, 1.0}, i.e. features that are quality-driven at
        the magnitudes actually observed. **Every probe's adjusted legibility must fall below 0.05.** An
        adjustment that cannot kill a known quality signal cannot be used to argue a feature's is not one.

GATE N  NON-CREATION. A probe independent of both quality and arm must stay below 0.05 after adjustment.
        An adjustment that manufactures legibility is broken in the opposite direction.

GATE P  CAPABILITY, AND IT IS THE POINT. A probe built as `arm + sigma * noise`, orthogonal to quality by
        construction, must **RETAIN at least 70 % of its unadjusted legibility** after adjustment, at
        every sigma in {0.5, 1.0, 2.0}.

        Without GATE P a collapse is uninterpretable. Weighting on a covariate that differs between arms
        necessarily discards effective sample size, and an adjustment that flattens *everything* would
        produce a collapsed GAP whatever the truth is. GATE P is the only thing that distinguishes
        "quality was removed" from "information was removed". E36's own capability control had the same
        job for a different claim, and this project has twice reported a collapse it later had to reopen
        because nothing bounded the adjustment's cost.

G1  MANIFEST, unchanged from E140: >= 6 patients per arm (observed 8 propofol, 7 dexmedetomidine).
G2  VARIATION (rule 32), unchanged.

If GATE P fails, no verdict is issued and the honest report is that quality cannot be removed from this
deposit without removing the contrast as well -- which would itself close the question, negatively, for
the Krause table.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH FIRST (rule 37)
=========================================================================================================
    GAP  =  mean drug_leg(AMPLITUDE)  -  mean drug_leg(PHASE)     unadjusted +0.0913
    FAMILIES are E36's, fixed:
        PHASE      frontwPLI, backwPLI, longwPLI, allwPLI
        AMPLITUDE  EffDim, NmlzCmplx, allEnvCorr, AvgDelta, AvgAlpha, AvgGamma, frontalDelta, frontalAlpha

**IF THE GAP SURVIVES** -- overlap-weighted GAP retains >= 50 % of +0.0913 with a patient-clustered
interval excluding zero, and both comparators agree in sign -- then E36's split is not a quality artefact.
It would then be a result that has survived a multiplicity correction, a capability control, a partition
enumeration and now a confounder that was found after the fact, which is a strong position, and this file
will say so.

**IF THE GAP COLLAPSES** -- overlap-weighted GAP below 50 % retained -- then E36's family split is
substantially a data-quality-sensitivity split. wPLI's insensitivity to amplitude artefact is a design
property of wPLI, and it would be doing the work that was attributed to drug pharmacology. Every
downstream use of E36 must be re-derived rather than carried forward (rule 2), specifically its
recommendation of an amplitude+phase composite, whose entire rationale is that the families differ in what
they leak.

**REGISTERED PREDICTION: COLLAPSE.** Weaker as a bet than E140's was, and the weakening is stated rather
than hidden: E140's matched arm already pointed this way at the 0.9 percent point of its size-only null.
The prediction is repeated because the estimate it rests on failed its gate and this file is the one
entitled to make the claim.

SECONDARY, DESCRIPTION ONLY, NO VERDICT.
    S1  LAMBDA (E139's Challenge-A statistic) recomputed with the adjusted drug half.
    S2  rho(drug-free sleep transfer AUC, -adjusted drug legibility). E139 measured -0.2448 unadjusted --
        features leaking the MOST agent identity transferred BEST to natural sleep, opposite to its
        registration. If that survives adjustment it is an objection to Challenge A's acceptance condition
        rather than to any feature, and it will be written up as one in its own registration, not here.

    python bsde/src/bsde/experiments/e141_family_split_quality_audit_v2.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc, auc_abs, cluster_bootstrap_ci, spearman   # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "krause_dexprosleep_allData.csv")
E139 = os.path.join(RESULTS, "e139_challenge_a_single_statistic.json")
OUT = os.path.join(RESULTS, "e141_family_split_quality_audit_v2.json")

PHASE = ["frontwPLI", "backwPLI", "longwPLI", "allwPLI"]
AMPLITUDE = ["EffDim", "NmlzCmplx", "allEnvCorr", "AvgDelta", "AvgAlpha", "AvgGamma",
             "frontalDelta", "frontalAlpha"]
FEATURES = AMPLITUDE + PHASE
Q = "pctGoodSamples"
CALIPER = 0.003
BAR = 0.05
CAPABILITY_RETAIN = 0.70
UNADJ_GAP_REF = 0.0913          # E140's, recomputed here and asserted to match


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    out = []
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["Subdural"] != "0" or r["label"] not in ("U", "U_dex"):
            continue
        rec = {"pid": r["patientID"], "arm": 1 if r["label"] == "U_dex" else 0, "q": _f(r[Q])}
        rec[Q] = rec["q"]
        rec.update({c: _f(r.get(c, "")) for c in FEATURES})
        out.append(rec)
    return [r for r in out if math.isfinite(r["q"])]


def ranks(v):
    v = np.asarray(v, float)
    o = np.argsort(v, kind="mergesort")
    r = np.empty(len(v), float)
    r[o] = np.arange(1, len(v) + 1)
    for u in np.unique(v):
        m = v == u
        if m.sum() > 1:
            r[m] = r[m].mean()
    return r


def _logit(X, y, iters=200, lam=1e-3):
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-X @ b))
        W = p * (1 - p) + 1e-9
        H = X.T @ (X * W[:, None]) + lam * np.eye(X.shape[1])
        b = b + np.linalg.solve(H, X.T @ (y - p) - lam * b)
    return b


def propensity(rows):
    """P(dexmedetomidine | rank of recording quality). Rank scale so no functional form is assumed."""
    rq = ranks([r["q"] for r in rows])
    X = np.c_[np.ones(len(rq)), (rq - rq.mean()) / (rq.std() + 1e-12)]
    y = np.array([r["arm"] for r in rows], float)
    return 1.0 / (1.0 + np.exp(-X @ _logit(X, y)))


def wauc(y, x, w):
    """Weighted Mann-Whitney AUC. Ties get 0.5, as the unweighted implementation does."""
    a = [(x[i], w[i]) for i in range(len(y)) if y[i] == 1]
    b = [(x[i], w[i]) for i in range(len(y)) if y[i] == 0]
    if not a or not b:
        return float("nan")
    num = sum(wi * wj * (1.0 if xi > xj else 0.5 if xi == xj else 0.0) for xi, wi in a for xj, wj in b)
    den = sum(wi * wj for _, wi in a for _, wj in b)
    return num / den if den > 0 else float("nan")


def leg_raw(rows, col):
    y = [r["arm"] for r in rows if math.isfinite(r[col])]
    x = [r[col] for r in rows if math.isfinite(r[col])]
    if len(set(y)) < 2 or len(set(x)) < 2:
        return float("nan")
    return auc_abs(y, x) - 0.5


def _weighted_leg(rows, col, kind):
    ok = [r for r in rows if math.isfinite(r[col])]
    if len(ok) < 8 or len({r["arm"] for r in ok}) < 2 or len({r[col] for r in ok}) < 2:
        return float("nan")
    e = propensity(ok)
    y = [r["arm"] for r in ok]
    x = [r[col] for r in ok]
    if kind == "overlap":
        w = np.where(np.array(y) == 1, 1 - e, e)
    else:
        w = np.where(np.array(y) == 1, 1 / np.clip(e, 1e-3, 1), 1 / np.clip(1 - e, 1e-3, 1))
    v = wauc(y, x, w)
    return abs(v - 0.5) if math.isfinite(v) else float("nan")


def leg_overlap(rows, col):
    return _weighted_leg(rows, col, "overlap")


def leg_ipw(rows, col):
    return _weighted_leg(rows, col, "ipw")


def match(rows, caliper=CALIPER):
    dex = [r for r in rows if r["arm"] == 1]
    pool = [r for r in rows if r["arm"] == 0]
    out = []
    for d in sorted(dex, key=lambda r: r["q"]):
        cand = [p for p in pool if abs(p["q"] - d["q"]) <= caliper]
        if cand:
            p = min(cand, key=lambda p: abs(p["q"] - d["q"]))
            pool.remove(p)
            out += [d, p]
    return out


def gap(rows, fn):
    return float(np.nanmean([fn(rows, c) for c in AMPLITUDE]) -
                 np.nanmean([fn(rows, c) for c in PHASE]))


def main(argv=None) -> int:
    rng = np.random.default_rng(141)
    rows = load()
    matched = match(rows)
    out = {"experiment": "E141", "n_blocks": len(rows), "n_matched_pairs": len(matched) // 2}

    pats = {a: len({r["pid"] for r in rows if r["arm"] == a}) for a in (0, 1)}
    g1 = pats[0] >= 6 and pats[1] >= 6
    dropped = [c for c in FEATURES
               if any(len({r[c] for r in rows if r["arm"] == a and math.isfinite(r[c])}) < 2
                      for a in (0, 1))]
    print(f"G1 MANIFEST  blocks={len(rows)}  patients prop={pats[0]} dex={pats[1]}  "
          f"-> {'PASS' if g1 else 'FAIL'}")
    print(f"G2 VARIATION constant in an arm: {dropped or 'none'}")
    print(f"             caliper {CALIPER} -> {len(matched) // 2} pairs")
    out["G1"] = {"pass": bool(g1), "patients": pats}
    out["G2"] = {"dropped": dropped}

    ADJ = {"overlap": (rows, leg_overlap), "ipw": (rows, leg_ipw),
           "caliper0.003": (matched, leg_raw)}

    # ---- reported check, no longer a gate: quality's own legibility -----------------------------------
    print(f"\nCHECK (reported, pre-verified before registration, NOT a gate)  "
          f"quality's own legibility")
    print(f"   raw                {leg_raw(rows, Q):+.4f}")
    qown = {}
    for name, (rs, fn) in ADJ.items():
        qown[name] = fn(rs, Q)
        print(f"   {name:18s} {qown[name]:+.4f}")
    out["quality_own_legibility"] = {"raw": leg_raw(rows, Q), **qown}

    # ---- probe gates ---------------------------------------------------------------------------------
    def with_probe(rs, vals, name="_probe"):
        for r, v in zip(rs, vals):
            r[name] = float(v)
        return rs

    q = np.array([r["q"] for r in rows], float)
    arm = np.array([r["arm"] for r in rows], float)
    probes = {}
    for tag, fmap in (("identity", lambda v: v), ("log", np.log), ("square", lambda v: v ** 2)):
        b = fmap(q)
        b = (b - b.mean()) / (b.std() + 1e-12)
        for s in (0.25, 0.5, 1.0):
            probes[f"S:{tag}_sigma{s}"] = ("S", b + s * rng.standard_normal(len(q)))
    probes["N:pure_noise"] = ("N", rng.standard_normal(len(q)))
    for s in (0.5, 1.0, 2.0):
        probes[f"P:arm_sigma{s}"] = ("P", arm + s * rng.standard_normal(len(q)))

    print(f"\nPROBE GATES   S: quality-driven must fall below {BAR}   "
          f"N: null must stay below {BAR}   P: arm-driven must retain >= {CAPABILITY_RETAIN:.0%}")
    gate_rows = {}
    fails = {"S": [], "N": [], "P": []}
    for pname, (kind, vals) in probes.items():
        with_probe(rows, vals)
        mvals = {id(r): r["_probe"] for r in rows}
        for r in matched:
            r["_probe"] = mvals[id(r)]
        raw = leg_raw(rows, "_probe")
        rec = {"kind": kind, "raw": raw}
        for name, (rs, fn) in ADJ.items():
            v = fn(rs, "_probe")
            rec[name] = v
            if kind in ("S", "N"):
                if not (math.isfinite(v) and v < BAR):
                    fails[kind].append((pname, name, v))
            else:
                if not (math.isfinite(v) and raw > 0 and v / raw >= CAPABILITY_RETAIN):
                    fails[kind].append((pname, name, v / raw if raw else float("nan")))
        gate_rows[pname] = rec
        print(f"   {pname:22s} raw={raw:+.4f}  " +
              "  ".join(f"{n}={rec[n]:+.4f}" for n in ADJ))
    out["probe_gates"] = gate_rows
    for k in ("S", "N", "P"):
        print(f"   GATE {k}: {'PASS' if not fails[k] else 'FAIL -> ' + str(fails[k])}")
    out["probe_gate_fails"] = {k: [[a, b, float(c)] for a, b, c in v] for k, v in fails.items()}
    for r in rows:
        r.pop("_probe", None)

    # primary adjustments are those whose S and N probes all passed; P is a global gate
    ok_adj = [n for n in ADJ
              if not any(a == n for _, a, _ in fails["S"]) and not any(a == n for _, a, _ in fails["N"])]
    gate_p_ok = not fails["P"]

    # ---- primary --------------------------------------------------------------------------------------
    g0 = gap(rows, leg_raw)
    print(f"\nUNADJUSTED  mean AMPLITUDE={np.nanmean([leg_raw(rows, c) for c in AMPLITUDE]):+.4f}  "
          f"mean PHASE={np.nanmean([leg_raw(rows, c) for c in PHASE]):+.4f}  GAP={g0:+.4f} "
          f"(E140 reported {UNADJ_GAP_REF:+.4f})")
    assert abs(g0 - UNADJ_GAP_REF) < 5e-4, "unadjusted GAP does not reproduce E140's -- stop and diagnose"

    print(f"\n{'feature':16s} {'family':10s} {'raw':>8s} " + " ".join(f"{n:>13s}" for n in ADJ))
    per = {}
    for c in FEATURES:
        v = {"raw": leg_raw(rows, c), "family": "PHASE" if c in PHASE else "AMPLITUDE"}
        for name, (rs, fn) in ADJ.items():
            v[name] = fn(rs, c)
        per[c] = v
        print(f"{c:16s} {v['family']:10s} {v['raw']:+8.4f} " +
              " ".join(f"{v[n]:+13.4f}" for n in ADJ))
    out["per_feature"] = per
    out["unadjusted_gap"] = g0

    pids = np.array([r["pid"] for r in rows])
    mpids = np.array([r["pid"] for r in matched])
    res = {}
    print(f"\nPRIMARY  GAP after adjustment, patient-clustered bootstrap (1,000 reps)")
    for name, (rs, fn) in ADJ.items():
        g = gap(rs, fn)
        pp = mpids if name.startswith("caliper") else pids
        lo, hi, nok = cluster_bootstrap_ci(
            lambda ix, rs=rs, fn=fn: gap([rs[i] for i in ix], fn), pp, rng, reps=1000)
        res[name] = {"gap": g, "ci": [lo, hi], "retained": g / g0 if g0 else float("nan"),
                     "n_ok": nok, "probe_ok": name in ok_adj}
        print(f"   {name:18s} GAP={g:+.4f} [{lo:+.4f}, {hi:+.4f}]  retains {g / g0:6.1%}"
              f"{'' if name in ok_adj else '   [probe gates failed]'}")
    out["primary"] = res

    # ---- rule-35 size-only control for the matched arm ------------------------------------------------
    n_pairs = len(matched) // 2
    dex = [r for r in rows if r["arm"] == 1]
    prop = [r for r in rows if r["arm"] == 0]
    ctrl = []
    for _ in range(1000):
        s = ([dex[i] for i in rng.choice(len(dex), size=min(n_pairs, len(dex)), replace=False)] +
             [prop[i] for i in rng.choice(len(prop), size=min(n_pairs, len(prop)), replace=False)])
        v = gap(s, leg_raw)
        if math.isfinite(v):
            ctrl.append(v)
    ctrl = np.sort(np.asarray(ctrl))
    gm = res["caliper0.003"]["gap"]
    frac = float(np.mean(ctrl <= gm))
    print(f"\nRULE-35 CONTROL  {n_pairs} per arm, matched on n but NOT on quality: "
          f"null median {np.median(ctrl):+.4f} [{np.quantile(ctrl, .025):+.4f}, "
          f"{np.quantile(ctrl, .975):+.4f}]")
    print(f"   quality-matched GAP {gm:+.4f} at the {frac:.1%} point -> collapse is "
          f"{'NOT ' if frac >= 0.05 else ''}beyond sample-size loss")
    out["rule35_control"] = {"n_per_arm": n_pairs, "null_median": float(np.median(ctrl)),
                             "null_ci": [float(np.quantile(ctrl, .025)),
                                         float(np.quantile(ctrl, .975))],
                             "matched_gap": gm, "frac_null_below": frac}

    # ---- verdict ----------------------------------------------------------------------------------------
    prim = res.get("overlap")
    if not g1:
        verdict = "NO VERDICT -- G1 failed"
    elif not gate_p_ok:
        verdict = ("NO VERDICT -- GATE P failed: the adjustment destroys a signal that is orthogonal to "
                   "quality by construction, so a collapsed GAP could not be attributed to quality. The "
                   "honest reading is that quality cannot be removed from this deposit without removing "
                   "the contrast, which closes the question negatively for the Krause table.")
    elif "overlap" not in ok_adj:
        verdict = "NO VERDICT -- the primary adjustment failed a sufficiency or non-creation probe"
    elif prim["retained"] >= 0.5 and prim["ci"][0] > 0:
        verdict = ("SURVIVES -- E36's family split is not a data-quality artefact. The registered "
                   "prediction (COLLAPSE) is WRONG, and E36 leaves this audit stronger than it entered: "
                   "it has now cleared a confounder discovered after the fact.")
    elif prim["retained"] < 0.5:
        verdict = ("COLLAPSES -- E36's family split is substantially a data-quality-sensitivity split. "
                   "wPLI's insensitivity to amplitude artefact is a design property of wPLI and it was "
                   "doing work attributed to pharmacology. Every downstream use of E36 must be "
                   "re-derived, not carried forward (rule 2), starting with its amplitude+phase composite "
                   "recommendation.")
    else:
        verdict = (f"INDETERMINATE -- retained {prim['retained']:.1%} with interval "
                   f"[{prim['ci'][0]:+.4f}, {prim['ci'][1]:+.4f}] spanning zero at 15 patients.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict

    # ---- S1 / S2, description only ----------------------------------------------------------------------
    try:
        e139 = json.load(open(E139))
        s1 = {c: e139["P1_lambda"][c]["state_leg"] - leg_overlap(rows, c)
              for c in FEATURES if c in e139.get("P1_lambda", {})}
        tr = e139.get("P3", {}).get("transfer_auc", {})
        ok = [c for c in s1 if math.isfinite(tr.get(c, float("nan")))]
        r2 = spearman([tr[c] for c in ok], [-leg_overlap(rows, c) for c in ok])
        out["S1_lambda_overlap_adjusted"] = s1
        out["S2_transfer_rho_adjusted"] = {"rho": r2, "n": len(ok), "e139_unadjusted": -0.2448}
        print("\nS1 (description only) LAMBDA with the overlap-adjusted drug half:")
        for c in sorted(s1, key=lambda c: -s1[c]):
            print(f"   {c:16s} {s1[c]:+.4f}   ({per[c]['family']})")
        print(f"\nS2 (description only) rho(sleep transfer AUC, -adjusted drug_leg) over {len(ok)} "
              f"features = {r2:+.4f}   (E139 unadjusted -0.2448)")
    except Exception as e:                                                       # noqa: BLE001
        out["S1_S2_error"] = f"{type(e).__name__}: {e}"

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
