#!/usr/bin/env python3
"""E161 -- E157's replication with the two defects fixed, and nothing else changed.

REGISTERED BEFORE THE REPAIRED RUN. Successor to E157. Cohort, arms, window, weighting, candidates,
predictions and every threshold are E157's, untouched. **Two mechanical defects are fixed and that is the
whole diff**, which is what rule 58 permits: one repair, with the reason written down.

=========================================================================================================
WHAT E157 PRODUCED AND WHY IT COULD NOT ISSUE A VERDICT
=========================================================================================================
On 112 clean-arm VitalDB cases -- **43 propofol alone against 69 sevoflurane alone**, a real agent
contrast where the MGH cohort had exactly one sevoflurane case -- with age, sex, ASA and BMI overlap-
weighted out (each covariate losing >= 99.8 % of its legibility) and case summaries taken over a fixed
eight-window intra-operative block so length cannot enter:

    relative_theta_power   weighted 0.3263   null p95 0.1013   p 0.0000   **signed AUC(sevo) 0.8022**
    alpha_peak_hz          weighted 0.2990   null p95 0.1078   p 0.0000   **signed AUC(sevo) 0.1935**

Predicted HIGHER, observed higher. Predicted LOWER, observed lower. **Both registered directions hold**,
which is the form of confirmation rule 37's fourth-occurrence entry demands and which a magnitude alone
cannot give.

**No verdict was issued, and the gate that blocked it is one I had already diagnosed in E156's ledger row
and then carried forward into E157 unchanged.** That is the fault, and it is mine:

  * **GATE P failed only on `P:arm_sigma2.0`**, whose RAW legibility is **0.0221** -- far below the
    cluster-level null floor of ~0.11. It is not a detectable signal at all, so a retention ratio on it
    divides by noise and returned 216.9 %. The two probes that ARE alive passed cleanly at 99.7 % and
    103.5 %.
  * **`wpli_alpha` is all-NaN in this table and was scored at p = 0.0000**, because
    `nanmean(null >= nan)` evaluates every comparison False and returns 0.0. A column with no data must be
    dropped and named, never scored.

=========================================================================================================
THE TWO FIXES, AND NOTHING ELSE
=========================================================================================================
**1. A CAPABILITY PROBE MUST BE ALIVE BEFORE IT CAN TEST PRESERVATION.** GATE P now evaluates only probes
whose raw legibility exceeds the measured cluster-level null's 95th percentile, and reports the excluded
ones by name with their raw values. This is rule 53 applied to a control rather than to an incumbent: a
comparison against something undetectable is a comparison against noise, in either direction.

**2. AN ALL-NaN COLUMN IS DROPPED AND NAMED.** Any candidate with fewer than 20 finite case-level values
is excluded before the null is built, so it cannot reach a p-value at all.

Neither fix touches a threshold, a cohort, a horizon or a prediction. The bar for GATE P stays
[0.70, 1.50]; the primary stays the signed direction; the null stays 20,000 cluster-level permutations.

=========================================================================================================
PRIMARY -- UNCHANGED, AND THE WRONG-DIRECTION BRANCH STILL COMES FIRST (rule 37)
=========================================================================================================
    PREDICTED   `relative_theta_power` HIGHER under sevoflurane (signed AUC > 0.5)
                `alpha_peak_hz` LOWER under sevoflurane (signed AUC < 0.5)

**A magnitude that clears the null with the WRONG sign is a REFUTATION, not a partial confirmation.**

**IF BOTH REPLICATE**, the MGH signature stands as a real agent effect measured twice, on two continents
and two monitors, with covariate adjustment in one. **For Challenge A that is UNFAVOURABLE news about the
features**: a candidate that identifies the agent at matched depth carries exactly the drug-identification
information the brief penalises, and `alpha_peak_hz` is also E153's only behavioural-threshold survivor.
A feature that does both is a good state marker and a bad Challenge A candidate, and that is the claim
this pair of results would support.

**WHAT WAS ALREADY SEEN, AND IT IS EVERYTHING (rule 41).** E157's complete output, quoted above and in its
ledger row: all eleven candidates' raw, weighted, null and signed values, all six gate lines. This run
cannot be blind and is not presented as such. Its only legitimate claim is that the two mechanical faults
above did not manufacture E157's numbers -- which is exactly what a repair run is for, and why the
verdict it issues is about the machinery's validity rather than about a fresh look at the data.

    python bsde/src/bsde/experiments/e161_vitaldb_replication_repaired.py
"""

from __future__ import annotations

import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import auc, auc_abs, spearman                         # noqa: E402

sys.path.insert(0, HERE)
from e141_family_split_quality_audit_v2 import _logit, ranks, wauc             # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e161_vitaldb_replication_repaired.json")
SHARDS = os.path.join(RESULTS, "vitaldb_agentprobe.s*.csv")

PRIMARY = {"relative_theta_power": "higher", "alpha_peak_hz": "lower"}
CANDIDATES = ["relative_theta_power", "alpha_peak_hz", "relative_alpha_power", "relative_delta_power",
              "spectral_edge_95", "spectral_entropy", "whole_head_exponent", "exponent_low",
              "exponent_high", "lempel_ziv", "wpli_alpha"]
COVARS = ["meta_age", "meta_sex", "meta_asa", "meta_bmi"]
NUISANCE = ["duration_s", "n_windows"] + COVARS
N_WINDOWS = 8
MIN_PER_ARM = 40
PERMS = 20000
RETAIN_LO, RETAIN_HI = 0.70, 1.50
REMOVAL = 0.80


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    rows = defaultdict(list)
    for p in sorted(glob.glob(SHARDS)):
        for r in csv.DictReader(open(p, newline="")):
            if r.get("status") != "ok":
                continue
            ag = (r.get("meta_agents_present") or "").strip()
            if ag not in ("propofol", "sevoflurane"):
                continue
            rows[r["meta_caseid"]].append(r)
    cases = {}
    for c, rs in rows.items():
        rs.sort(key=lambda r: _f(r["meta_t_s"]))
        keep = []
        for r in rs:
            t, o, a = _f(r["meta_t_s"]), _f(r["meta_opstart_s"]), _f(r["meta_aneend_s"])
            if math.isfinite(t) and math.isfinite(o) and math.isfinite(a) and o <= t <= a:
                keep.append(r)
        if len(keep) < N_WINDOWS:
            continue
        seg = keep[:N_WINDOWS]
        d = {"arm": 1 if rs[0]["meta_agents_present"] == "sevoflurane" else 0,
             "duration_s": _f(rs[-1]["meta_t_s"]) - _f(rs[0]["meta_t_s"]),
             "n_windows": float(len(keep))}
        for cv in COVARS:
            v = seg[0].get(cv, "")
            d[cv] = _f(v) if cv != "meta_sex" else (1.0 if str(v).upper().startswith("M") else 0.0)
        for f in CANDIDATES:
            vals = [_f(r.get(f, "")) for r in seg]
            vals = [v for v in vals if math.isfinite(v)]
            d[f] = float(np.median(vals)) if vals else float("nan")
        cases[c] = d
    return cases


def main(argv=None) -> int:
    rng = np.random.default_rng(157)
    cases = load()
    ids = sorted(cases)
    if not ids:
        print("ABSENT -- no clean-arm cases yet; the extraction is still running.")
        return 2
    arm = np.array([cases[c]["arm"] for c in ids])
    n_sevo, n_prop = int(arm.sum()), int((1 - arm).sum())
    out = {"experiment": "E161", "n_cases": len(ids), "n_sevoflurane": n_sevo,
           "n_propofol": n_prop, "n_windows": N_WINDOWS, "perms": PERMS}

    g1 = n_sevo >= MIN_PER_ARM and n_prop >= MIN_PER_ARM
    print(f"G1 MANIFEST  {len(ids)} clean-arm cases: {n_prop} propofol alone, {n_sevo} sevoflurane "
          f"alone (floor {MIN_PER_ARM} each) -> {'PASS' if g1 else 'FAIL'}")

    cols = {k: np.array([cases[c].get(k, float("nan")) for c in ids], float)
            for k in CANDIDATES + NUISANCE}
    # FIX 2 -- a column with almost no data must be dropped and NAMED, never scored. E157 gave all-NaN
    # `wpli_alpha` a p of 0.0000 because nanmean(null >= nan) counts every comparison False.
    dead = [c for c in CANDIDATES if int(np.isfinite(cols[c]).sum()) < 20]
    for c in dead:
        cols.pop(c, None)
    live_candidates = [c for c in CANDIDATES if c not in dead]
    print(f"   dropped for having < 20 finite case values: {dead or 'none'}")
    for s in (0.5, 1.0, 2.0):
        cols[f"P:arm_sigma{s}"] = arm + s * rng.standard_normal(len(ids))

    # ---- G2 rule 60 escape check ----------------------------------------------------------------------
    m = np.isfinite(cols["alpha_peak_hz"]) & np.isfinite(cols["relative_alpha_power"])
    rho60 = spearman(list(cols["alpha_peak_hz"][m]), list(cols["relative_alpha_power"][m]))
    g2 = abs(rho60) < 0.9
    print(f"G2 RULE-60 ESCAPE  rho(alpha_peak_hz, relative_alpha_power) = {rho60:+.4f} "
          f"(bar |rho| < 0.9) -> {'PASS' if g2 else 'FAIL -- it is an amplitude measure renamed'}")

    # ---- overlap weighting on the covariates -----------------------------------------------------------
    C = np.column_stack([ranks(cols[c]) if np.isfinite(cols[c]).all() else
                         ranks(np.nan_to_num(cols[c], nan=np.nanmedian(cols[c]))) for c in COVARS])
    C = (C - C.mean(0)) / (C.std(0) + 1e-12)
    X = np.c_[np.ones(len(ids)), C]
    e = 1.0 / (1.0 + np.exp(-X @ _logit(X, arm.astype(float))))
    w = np.where(arm == 1, 1 - e, e)
    print(f"   propensity(arm | age, sex, ASA, BMI) range {e.min():.3f}-{e.max():.3f}")

    def raw(v, lab):
        k = np.isfinite(v)
        if len(set(lab[k].tolist())) < 2 or len(set(v[k].tolist())) < 2:
            return float("nan")
        return auc_abs(list(lab[k]), list(v[k])) - 0.5

    def wtd(v, lab, ww):
        k = np.isfinite(v)
        if len(set(lab[k].tolist())) < 2 or len(set(v[k].tolist())) < 2:
            return float("nan")
        a = wauc(list(lab[k]), list(v[k]), ww[k])
        return abs(a - 0.5) if math.isfinite(a) else float("nan")

    obs_r = {k: raw(v, arm) for k, v in cols.items()}
    obs_w = {k: wtd(v, arm, w) for k, v in cols.items()}
    null = {k: np.empty(PERMS) for k in cols}
    for i in range(PERMS):
        p = rng.permutation(arm)
        ep = 1.0 / (1.0 + np.exp(-X @ _logit(X, p.astype(float))))
        wp = np.where(p == 1, 1 - ep, ep)
        for k, v in cols.items():
            null[k][i] = wtd(v, p, wp)
    q95 = {k: float(np.nanquantile(null[k], 0.95)) for k in cols}
    pval = {k: float(np.nanmean(null[k] >= obs_w[k])) for k in cols}
    med_cand = float(np.nanmedian([obs_r[c] for c in live_candidates]))

    print(f"\nG3 NUISANCE PLACEBOS  median candidate raw legibility {med_cand:+.4f}")
    for k in NUISANCE:
        print(f"   {k:16s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  null p95 {q95[k]:.4f}  "
              f"p={pval[k]:.4f}  {'ABOVE the median candidate (raw)' if obs_r[k] >= med_cand else 'ok'}")
    print(f"G4 GATE Q  each covariate must lose >= {REMOVAL:.0%} of its raw legibility")
    g4 = True
    for k in COVARS:
        rem = 1.0 - (obs_w[k] / obs_r[k]) if obs_r[k] else float("nan")
        ok = math.isfinite(rem) and rem >= REMOVAL
        g4 &= ok
        print(f"   {k:16s} removed {rem:6.1%}  {'ok' if ok else 'FAIL'}")
    print(f"G5 GATE P  arm probes orthogonal to the covariates must retain within "
          f"[{RETAIN_LO:.0%}, {RETAIN_HI:.0%}]")
    # FIX 1 -- a capability probe must be ALIVE before it can test preservation (rule 53 applied to a
    # control). A probe whose raw legibility sits below the measured null floor is not a detectable signal,
    # so a retention ratio on it divides by noise; E157's sigma=2.0 probe had raw 0.0221 against a floor of
    # ~0.11 and returned 216.9 %. Excluded probes are reported by name with their raw values.
    g5 = True
    n_alive_probes = 0
    for k in [c for c in cols if c.startswith("P:")]:
        if not (math.isfinite(obs_r[k]) and obs_r[k] > q95[k]):
            print(f"   {k:16s} raw {obs_r[k]:+.4f} is below its null p95 {q95[k]:.4f} -- NOT ALIVE, "
                  f"excluded from the gate")
            continue
        n_alive_probes += 1
        ret = obs_w[k] / obs_r[k] if obs_r[k] else float("nan")
        ok = math.isfinite(ret) and RETAIN_LO <= ret <= RETAIN_HI
        g5 &= ok
        print(f"   {k:16s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  retains {ret:6.1%}  "
              f"{'ok' if ok else 'FAIL'}")
    if n_alive_probes < 2:
        g5 = False
        print(f"   only {n_alive_probes} alive probe(s) -- GATE P cannot be evaluated, so it FAILS")
    out.update({"G1": bool(g1), "G2": {"pass": bool(g2), "rho": rho60},
                "G4": bool(g4), "G5": bool(g5),
                "nuisance": {k: {"raw": obs_r[k], "weighted": obs_w[k], "p": pval[k]} for k in NUISANCE}})

    gates = g1 and g2 and g4 and g5
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    hp = holm([pval[c] for c in live_candidates], live_candidates)
    print(f"{'candidate':22s} {'raw':>8s} {'weighted':>9s} {'null p95':>9s} {'p':>8s} {'p_holm':>8s} "
          f"{'signed AUC(sevo)':>17s}")
    res = {}
    for c in sorted(live_candidates, key=lambda x: -obs_w[x]):
        k = np.isfinite(cols[c])
        sa = auc(list(arm[k]), list(cols[c][k])) if len(set(arm[k].tolist())) > 1 else float("nan")
        note = ""
        if c in PRIMARY:
            got = "higher" if sa > 0.5 else "lower"
            note = f"  predicted {PRIMARY[c]}, observed {got}"
        res[c] = {"raw": obs_r[c], "weighted": obs_w[c], "null_p95": q95[c], "p": pval[c],
                  "p_holm": hp[c], "signed_auc_sevo": sa,
                  "clears": bool(hp[c] < 0.05 and obs_w[c] > q95[c]),
                  "direction_ok": (None if c not in PRIMARY else
                                   bool((sa < 0.5) == (PRIMARY[c] == "lower")))}
        print(f"{c:22s} {obs_r[c]:8.4f} {obs_w[c]:9.4f} {q95[c]:9.4f} {pval[c]:8.4f} {hp[c]:8.4f} "
              f"{sa:17.4f}{note}")
    out["per_candidate"] = res
    out["dropped_candidates"] = dead

    rep = [c for c in PRIMARY if res[c]["clears"] and res[c]["direction_ok"]]
    wrong = [c for c in PRIMARY if res[c]["clears"] and not res[c]["direction_ok"]]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif wrong:
        verdict = (f"REFUTED BY SIGN -- {', '.join(wrong)} clear the null with the WRONG direction "
                   f"(signed AUC(sevo) "
                   f"{ {c: round(res[c]['signed_auc_sevo'], 4) for c in wrong} }). Something separates "
                   f"these arms and it is not the pharmacology the MGH result was attributed to. Not a "
                   f"partial confirmation.")
    elif len(rep) == len(PRIMARY):
        verdict = (f"REPLICATED -- {', '.join(rep)} separate propofol from sevoflurane at matched "
                   f"intra-operative state, in the predicted directions, on {len(ids)} cases with age, "
                   f"sex, ASA and BMI weighted out. The MGH signature stands. For Challenge A this is "
                   f"UNFAVOURABLE news about the features: they carry exactly the drug-identification "
                   f"information the brief penalises, and alpha_peak_hz is also E153's only "
                   f"behavioural-threshold survivor.")
    elif rep:
        verdict = (f"HALF-REPLICATED -- {', '.join(rep)} replicates; "
                   f"{', '.join(c for c in PRIMARY if c not in rep)} does not and is withdrawn. No "
                   f"composite claim is made from a half-replication.")
    else:
        verdict = (f"NOT REPLICATED -- neither primary clears the cluster-level null on {len(ids)} cases "
                   f"with real separate agents and covariate adjustment. The MGH finding was a property "
                   f"of that cohort, most plausibly its care-pathway contrast, and is WITHDRAWN rather "
                   f"than qualified.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
