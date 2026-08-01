#!/usr/bin/env python3
"""E155 -- were E154's two agent-identification hits the drug, or the length of the operation?

REGISTERED BEFORE ANY DURATION-ADJUSTED LEGIBILITY HAS BEEN COMPUTED. Successor to E154, which was VOID
by its own gate. Cohort, candidates, state definition and null construction are E154's, unchanged.

=========================================================================================================
WHAT E154's GATE CAUGHT
=========================================================================================================
E154 pushed three case-level nuisance variables through the identical drug-legibility path. Two of them
failed catastrophically:

    recording duration   |AUC-0.5| = **0.3771**   p = 0.0000 against 20,000 cluster permutations
    epoch count          0.3771  (the same variable)
    quality fraction     0.0686  p = 0.4197  -- fine, unlike Krause's 0.2565

**Sevoflurane cases are longer.** Median good-quality unconscious epochs: mixed **1,740** (58 min) against
pure propofol **900** (30 min). Without the gate, E154 would have reported `rel_theta` (0.4771) and
`alpha_peak_hz` (0.3943) as agent-identification positives clearing a correct cluster-level null at Holm
p = 0.0000 -- with duration sitting at 0.3771 right beside them. Third time in this project a nuisance
variable out-identified the features.

E154's other number stands and is independent of the failure: the cluster-level null's mean 95th
percentile is **0.1904** at 39 clusters against **0.2791** at Krause's 15, a ratio of 0.68 where pure
sample size predicts sqrt(15/39) = 0.62.

=========================================================================================================
TWO CHANGES, AND BOTH ARE NECESSARY
=========================================================================================================
**1. THE SUMMARY NO LONGER AVERAGES OVER DIFFERENT AMOUNTS OF TIME.** Each case's value is the median over
its **first 300 good-quality unconscious epochs** -- exactly 10 minutes after the labelled loss, identical
for every case. Checked before registration: **all 43 cases have at least 300**, so nothing is excluded
and no selection is introduced (rule 14). A 20-minute window would have dropped 6 of 27 propofol cases and
a 30-minute window 13 of 27, which is why 10 minutes is the choice.

**2. DURATION IS ADJUSTED FOR, NOT MERELY MATCHED.** Case length remains a property of the case even when
the summary is fixed-length, and it is associated with the agent at 0.3771. So drug legibility is computed
under **overlap weighting** on the propensity of arm given rank(duration) -- the machinery that took
quality legibility from 0.2565 to 0.0002 in E141. Raw legibility is reported beside it, never instead.

=========================================================================================================
GATES -- thresholds DERIVED, not chosen (rule 63)
=========================================================================================================
E141's gates failed because a 0.05 bar sat below the statistic's own chance floor. That floor is now
measured for this cohort: E154's cluster-level null puts the 95th percentile at **0.1904**. Every gate
below is stated against **the null's own 95th percentile recomputed under the weighting**, not against a
round number.

G1  MANIFEST. >= 12 cases per arm, all with >= 300 good-quality unconscious epochs.
G2  **GATE Q.** After weighting, duration's own drug legibility must fall **below the weighted null's 95th
    percentile**. An adjustment that leaves duration legible cannot be used to argue a feature's is not
    duration.
G3  **GATE P, CAPABILITY.** A synthetic case-level feature built as `arm + sigma * noise`, orthogonal to
    duration by construction, must retain **>= 70 %** of its unweighted legibility after weighting, at
    sigma in {0.5, 1.0, 2.0}. Without this, a collapse is uninterpretable: weighting on a covariate that
    differs between arms discards effective sample size, and an adjustment that flattens everything would
    look identical to a confound being removed.
G4  **GATE S, SUFFICIENCY.** Synthetic probes built as `monotone(duration) + noise` must fall below the
    weighted null's 95th percentile. An adjustment that cannot kill a known duration signal cannot
    certify that a feature's signal is not one.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF `rel_theta` OR `alpha_peak_hz` SURVIVES** the fixed window and the weighting, still clearing the
weighted cluster-level null after Holm, then the frontal spectrum genuinely identifies whether
sevoflurane was co-administered at matched unresponsiveness on 39 independent cases. That is a real
positive for the drug-identification half of Challenge A, a real problem for any candidate built from
those features, and it must be reported as a finding rather than filed as a caveat. **This is the branch
that costs and it is written first.**

**REGISTERED PREDICTION: NEITHER SURVIVES, AND NOTHING ELSE CLEARS.** Reasoning, stated so it can be
wrong: duration's legibility (0.3771) is of the same magnitude as theirs (0.4771, 0.3943), a 58-minute
case sits at a different point of the depth trajectory than a 30-minute one even 10 minutes in, and theta
power and alpha peak frequency are both known to drift with time under maintenance anaesthesia.

**SECONDARY, NO VERDICT: the weighted null's 95th percentile.** Weighting costs effective sample size, so
the floor will rise above E154's 0.1904. Reporting how far is what tells a successor whether the
adjustment is affordable at this n or whether the cohort must grow first.

WHAT WAS ALREADY SEEN (rule 41). All of E154's output, quoted above. The per-arm distribution of
unconscious epoch counts and the retention of every case at each of five candidate window widths -- which
is how the 300-epoch window was chosen, from the exposure and the manifest, with no feature touched.

    python bsde/src/bsde/experiments/e155_duration_adjusted_drug_legibility.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import auc_abs                                        # noqa: E402

sys.path.insert(0, HERE)
from e141_family_split_quality_audit_v2 import _logit, ranks, wauc             # noqa: E402
from e154_lambda_on_mgh_or import FEATURES, MIN_EPOCHS, _f                     # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "mgh_power_windows.csv")
OUT = os.path.join(RESULTS, "e155_duration_adjusted.json")

WINDOW = 300            # epochs of unconsciousness summarised, identical for every case
PERMS = 5000
MIN_PER_ARM = 12
CAPABILITY_RETAIN = 0.70


def load():
    per = defaultdict(list)
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["cohort"] == "OR":
            per[r["case"]].append(r)
    cases = {}
    for c, rows in per.items():
        if rows[0]["arm"] == "pure_sevo":
            continue
        rows.sort(key=lambda r: _f(r["t"]))
        good = [r for r in rows if r["quality"] == "1"]
        con = [r for r in good if r["label"] == "1"]
        unc = [r for r in good if r["label"] == "0"]
        if len(con) < MIN_EPOCHS or len(unc) < WINDOW:
            continue
        seg = unc[:WINDOW]
        t = np.array([_f(r["t"]) for r in rows], float)
        cases[c] = {"arm": 1 if rows[0]["arm"] == "mixed" else 0,
                    "duration_s": float(np.nanmax(t) - np.nanmin(t)),
                    "n_unc": float(len(unc)),
                    **{f: float(np.nanmedian([_f(r[f]) for r in seg])) for f in FEATURES}}
    return cases


def main(argv=None) -> int:
    rng = np.random.default_rng(155)
    cases = load()
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids])
    dur = np.array([cases[c]["duration_s"] for c in ids], float)
    n_mix, n_pro = int(arm.sum()), int((1 - arm).sum())
    out = {"experiment": "E155", "window_epochs": WINDOW, "n_cases": len(ids),
           "n_mixed": n_mix, "n_propofol": n_pro, "perms": PERMS}

    g1 = n_mix >= MIN_PER_ARM and n_pro >= MIN_PER_ARM
    print(f"G1 MANIFEST  {len(ids)} cases with >= {WINDOW} good unconscious epochs: "
          f"{n_pro} pure propofol, {n_mix} mixed -> {'PASS' if g1 else 'FAIL'}")

    rd = ranks(dur)
    X = np.c_[np.ones(len(rd)), (rd - rd.mean()) / (rd.std() + 1e-12)]
    e = 1.0 / (1.0 + np.exp(-X @ _logit(X, arm.astype(float))))
    w_ovl = np.where(arm == 1, 1 - e, e)
    print(f"   propensity(arm | rank duration) range {e.min():.3f}-{e.max():.3f}")

    def raw(v, lab):
        m = np.isfinite(v)
        if len(set(lab[m].tolist())) < 2 or len(set(v[m].tolist())) < 2:
            return float("nan")
        return auc_abs(list(lab[m]), list(v[m])) - 0.5

    def wtd(v, lab, w):
        m = np.isfinite(v)
        if len(set(lab[m].tolist())) < 2 or len(set(v[m].tolist())) < 2:
            return float("nan")
        a = wauc(list(lab[m]), list(v[m]), w[m])
        return abs(a - 0.5) if math.isfinite(a) else float("nan")

    # ---- the weighted null, recomputing the propensity inside every permutation ------------------------
    cols = {f: np.array([cases[c][f] for c in ids], float) for f in FEATURES}
    cols["duration_s"] = dur
    probes = {}
    for tag, base in (("dur", dur), ("logdur", np.log(np.maximum(dur, 1.0)))):
        b = (base - base.mean()) / (base.std() + 1e-12)
        for s in (0.25, 0.5, 1.0):
            probes[f"S:{tag}_sigma{s}"] = b + s * rng.standard_normal(len(ids))
    for s in (0.5, 1.0, 2.0):
        probes[f"P:arm_sigma{s}"] = arm + s * rng.standard_normal(len(ids))
    cols.update(probes)

    null = {k: np.empty(PERMS) for k in cols}
    for i in range(PERMS):
        p = rng.permutation(arm)
        Xp = np.c_[np.ones(len(rd)), (rd - rd.mean()) / (rd.std() + 1e-12)]
        ep = 1.0 / (1.0 + np.exp(-Xp @ _logit(Xp, p.astype(float))))
        wp = np.where(p == 1, 1 - ep, ep)
        for k, v in cols.items():
            null[k][i] = wtd(v, p, wp)
    q95 = {k: float(np.nanquantile(null[k], 0.95)) for k in cols}
    obs_w = {k: wtd(v, arm, w_ovl) for k, v in cols.items()}
    obs_r = {k: raw(v, arm) for k, v in cols.items()}
    pval = {k: float(np.nanmean(null[k] >= obs_w[k])) for k in cols}
    mean_q95 = float(np.nanmean([q95[f] for f in FEATURES]))
    print(f"   weighted cluster-level null: mean 95th percentile {mean_q95:.4f} "
          f"(E154 unweighted: 0.1904, Krause 15 clusters: 0.2791)")

    # ---- G2 / G3 / G4 -----------------------------------------------------------------------------------
    g2 = math.isfinite(obs_w["duration_s"]) and obs_w["duration_s"] < q95["duration_s"]
    print(f"\nG2 GATE Q  duration legibility raw {obs_r['duration_s']:+.4f} -> weighted "
          f"{obs_w['duration_s']:+.4f}  (null p95 {q95['duration_s']:.4f})  -> "
          f"{'PASS' if g2 else 'FAIL'}")

    print(f"G4 GATE S  duration-driven probes must fall below their null p95")
    g4 = True
    for k in sorted(p for p in probes if p.startswith("S:")):
        ok = math.isfinite(obs_w[k]) and obs_w[k] < q95[k]
        g4 &= ok
        print(f"   {k:22s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  (p95 {q95[k]:.4f})  "
              f"{'ok' if ok else 'FAIL'}")
    print(f"   -> {'PASS' if g4 else 'FAIL'}")

    print(f"G3 GATE P  arm-driven probes orthogonal to duration must retain >= "
          f"{CAPABILITY_RETAIN:.0%}")
    g3 = True
    for k in sorted(p for p in probes if p.startswith("P:")):
        ret = obs_w[k] / obs_r[k] if obs_r[k] else float("nan")
        ok = math.isfinite(ret) and ret >= CAPABILITY_RETAIN
        g3 &= ok
        print(f"   {k:22s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  retains {ret:6.1%}  "
              f"{'ok' if ok else 'FAIL'}")
    print(f"   -> {'PASS' if g3 else 'FAIL'}")
    out["G1"] = bool(g1)
    out["G2"] = {"pass": bool(g2), "raw": obs_r["duration_s"], "weighted": obs_w["duration_s"],
                 "null_p95": q95["duration_s"]}
    out["G3"] = {"pass": bool(g3), "probes": {k: {"raw": obs_r[k], "weighted": obs_w[k]}
                                              for k in probes if k.startswith("P:")}}
    out["G4"] = {"pass": bool(g4), "probes": {k: {"raw": obs_r[k], "weighted": obs_w[k],
                                                  "null_p95": q95[k]}
                                              for k in probes if k.startswith("S:")}}
    out["weighted_null_mean_q95"] = mean_q95

    gates = g1 and g2 and g3 and g4
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    hp = holm([pval[f] for f in FEATURES], FEATURES)
    print(f"{'candidate':18s} {'raw':>8s} {'weighted':>9s} {'null p95':>9s} {'p':>8s} {'p_holm':>8s} "
          f"{'E154 raw':>9s}")
    e154 = {}
    try:
        e154 = {k: v["drug_leg"] for k, v in
                json.load(open(os.path.join(RESULTS, "e154_lambda_mgh_or.json")))["per_feature"].items()}
    except Exception:                                                          # noqa: BLE001
        pass
    res = {}
    for f in sorted(FEATURES, key=lambda x: -obs_w[x]):
        res[f] = {"raw": obs_r[f], "weighted": obs_w[f], "null_p95": q95[f], "p": pval[f],
                  "p_holm": hp[f], "e154_raw": e154.get(f, float("nan")),
                  "clears": bool(hp[f] < 0.05 and obs_w[f] > q95[f])}
        print(f"{f:18s} {obs_r[f]:8.4f} {obs_w[f]:9.4f} {q95[f]:9.4f} {pval[f]:8.4f} {hp[f]:8.4f} "
              f"{e154.get(f, float('nan')):9.4f}")
    out["per_feature"] = res

    clears = [f for f in FEATURES if res[f]["clears"]]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif clears:
        verdict = (f"POSITIVE -- {', '.join(clears)} identify whether sevoflurane was co-administered at "
                   f"matched unresponsiveness, on a fixed 10-minute window and after overlap weighting "
                   f"on duration, against a weighted cluster-level null. The registered prediction is "
                   f"WRONG. Any Challenge A candidate built from these features carries agent identity, "
                   f"and that is a finding rather than a caveat.")
    else:
        verdict = (f"NEGATIVE, AND E154's TWO HITS WERE DURATION -- nothing clears once the summary is "
                   f"taken over a fixed 10-minute window and duration is weighted out. rel_theta went "
                   f"{e154.get('rel_theta', float('nan')):.4f} -> {obs_w['rel_theta']:.4f} and "
                   f"alpha_peak_hz {e154.get('alpha_peak_hz', float('nan')):.4f} -> "
                   f"{obs_w['alpha_peak_hz']:.4f}. On 39 independent cases the frontal amplitude family "
                   f"does not identify the agent at matched unresponsiveness, with the weighted null's "
                   f"floor at {mean_q95:.4f}.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
