#!/usr/bin/env python3
"""E05 — does a candidate track the DRUG or the STATE? The Chennu recovery dissociation.

WHY THIS IS THE MOST INFORMATIVE EXPERIMENT THE PROJECT CAN CURRENTLY RUN.

Every labelled contrast reached so far confounds drug level with behavioural state, or is circular, or has no
labels at all:

    Figshare          no labels whatsoever                                        (MASTER_PLAN §1 row 2)
    Sleep-EDF         labels scored FROM the EEG -- definitionally circular        (§9.6)
    ds005620          awake vs sedated: drug and state move together; no reports   (§1 row 6)
    I-CARE            CPC outcome: prognosis, so a negative control only           (§9.1)

Chennu breaks the confound, and it does so *within subject*. Its four levels are baseline, mild, moderate and
recovery, and at **recovery the measured plasma propofol is 276.5 µg/L -- not zero, and above baseline --
while behaviour is nearly restored (38/40 correct against baseline's 39/40)**. So recovery is a state where the
DRUG IS PRESENT AND RESPONSIVENESS IS BACK. Compare a candidate's recovery value against two references
measured in the same people:

    if recovery resembles BASELINE          -> the candidate follows behavioural state
    if recovery resembles MILD SEDATION     -> the candidate follows the drug
                                               (mild's plasma, 438, is the closest level to recovery's 276)

This is Discovery Challenge A -- "the simplest representation that predicts loss and recovery of
responsiveness across anaesthetics while minimising drug-identification information" -- in the form the
available data can actually test. It also attacks §9.2's mediator problem directly: drug level and behaviour
are separately MEASURED here, so arousal does not have to be blindly adjusted away.

THE STATISTIC. For each candidate and each subject, take the four level values and compute

    d_state = |v(recovery) - v(baseline)|
    d_drug  = |v(recovery) - v(mild)|
    S       = (d_drug - d_state) / (d_drug + d_state)          in [-1, +1]

S > 0 means recovery sits closer to baseline, i.e. the candidate follows STATE. S < 0 means it sits closer to
mild sedation, i.e. it follows the DRUG. S is scale-free, so it is comparable across candidates measured in
different units, and it is computed WITHIN subject so between-subject variation cannot produce it. The
subject-level mean of S is tested against 0 by a subject bootstrap, and against a null built by permuting the
three level labels within each subject.

REGISTERED BEFORE ANY CHENNU EEG IS READ:
    P1  MANIFEST CHECK, evaluated first. The cohort must contain 20 subjects with all four levels present.
        A subject missing a level cannot contribute S and is dropped and counted; if fewer than 15 subjects
        remain, the run is reported as underpowered and NO verdict is issued.
    P2  The aperiodic exponent (`whole_head_exponent`) is a MONOTONE function of plasma concentration across
        levels 1-3 (baseline < mild < moderate), i.e. Spearman r(exponent, plasma) > 0 within subject over
        those three levels. If this fails, the marker does not track this drug at all and P3 is not
        interpretable.
    P3  DIRECTION -- the substantive prediction. The aperiodic exponent has **S < 0**: it follows the DRUG
        rather than the state. Rationale: Colombo (PMID 30639334) reports the exponent tracking *reported
        experience* rather than responsiveness, but the exponent is also a direct read-out of cortical
        excitation/inhibition balance (Gao 2017, PMID 28676297), which is what a GABAergic agent acts on
        pharmacologically. With drug still on board at recovery, an E/I read-out should still see it.
        **This prediction is deliberately against the project's own interest**: S > 0 would be the better
        news for a consciousness marker, and predicting S < 0 means a state-tracking result cannot be claimed
        as confirmation of something expected.
    P4  PLACEBO / GATE. The same statistic computed with `mild` replaced by `moderate` -- comparing recovery
        against a level whose plasma (803) is FURTHER from recovery's than mild's is -- must show S at least
        as positive as the primary. If recovery looks closer to moderate than to mild, the plasma ordering
        is not driving anything and the whole design is void. **This gate is evaluated BEFORE the primary is
        interpreted** (error-catalogue rules 34 and 37).

    FALSIFICATION: if the subject-level mean S has an interval spanning 0 for every candidate, the honest
    report is that this design cannot separate drug from state at this n -- a real negative for Challenge A
    on public data, reported as such and not reframed.

WHAT THIS CANNOT SHOW. n = 20 healthy volunteers, one drug, one site, and "responsiveness" is a two-choice
reaction task, not consciousness. Nothing here speaks to covert awareness. Reaction time is additionally
confounded by practice order (§9.8), so correct-response count is the behavioural label of record.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                    # noqa: E402
from bsde.candidates.seed import seed_registry                                    # noqa: E402
from bsde.governance.search_log import append                                      # noqa: E402
from bsde.verifier.stats import spearman                                           # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
NOW = os.environ.get("BSDE_NOW", "2026-07-30T00:00:00Z")
LEVELS = {1: "baseline", 2: "mild", 3: "moderate", 4: "recovery"}
MIN_SUBJECTS = 15


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load_features(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as fh:
        return [r for r in csv.DictReader(fh) if r.get("status") == "ok"]


def by_subject_level(rows, cand):
    """{subject: {level: value}} using only finite values."""
    out = defaultdict(dict)
    for r in rows:
        lvl = _f(r.get("meta_sedation_level"))
        v = _f(r.get(cand))
        if not np.isfinite(lvl) or not np.isfinite(v):
            continue
        out[r.get("subject", r["recording_id"])][int(lvl)] = v
    return out


def s_index(per, ref_level):
    """Subject-wise S for recovery vs baseline against recovery vs `ref_level`. Returns (S array, subjects)."""
    ss, subs = [], []
    for s, d in sorted(per.items()):
        if not {1, 4, ref_level} <= set(d):
            continue
        d_state = abs(d[4] - d[1])
        d_drug = abs(d[4] - d[ref_level])
        tot = d_drug + d_state
        if tot <= 0:
            continue
        ss.append((d_drug - d_state) / tot)
        subs.append(s)
    return np.asarray(ss, float), subs


def boot_ci(x, rng, reps=2000):
    if len(x) < 3:
        return float("nan"), float("nan")
    m = np.array([np.mean(rng.choice(x, size=len(x), replace=True)) for _ in range(reps)])
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def perm_null(per, ref_level, rng, reps=2000):
    """Permute the THREE level labels within each subject; recompute mean S. Tests whether the observed
    asymmetry could arise from arbitrary relabelling of a subject's own conditions."""
    keys = [1, ref_level, 4]
    subs = [d for d in per.values() if set(keys) <= set(d)]
    if len(subs) < 3:
        return {"mean": float("nan"), "q025": float("nan"), "q975": float("nan"), "n": 0}
    vals = []
    for _ in range(reps):
        ss = []
        for d in subs:
            v = [d[k] for k in keys]
            p = rng.permutation(v)
            ds, dd = abs(p[2] - p[0]), abs(p[2] - p[1])
            if ds + dd > 0:
                ss.append((dd - ds) / (dd + ds))
        if ss:
            vals.append(float(np.mean(ss)))
    if not vals:
        return {"mean": float("nan"), "q025": float("nan"), "q975": float("nan"), "n": 0}
    a = np.asarray(vals)
    return {"mean": float(a.mean()), "q025": float(np.quantile(a, .025)),
            "q975": float(np.quantile(a, .975)), "n": len(a)}


def main() -> int:
    seed_registry()
    # v3 is the CURRENT extraction; v1 has 21 columns and lacks exponent_high, pac_slow_alpha,
    # critical_slowing_ar1 and others, which is why those candidates returned n=0 subjects rather than a
    # null. Rule 2: numbers inherited from a superseded extraction must be re-derived, not carried forward.
    rows = load_features(os.path.join(RESULTS, "chennu_features_v3.csv"))
    print("E05 — drug vs state: the Chennu recovery dissociation")
    if not rows:
        print("   *** no results/chennu_features.csv yet. Nothing is reported.")
        return 2

    # ---- P1 MANIFEST GATE, evaluated first -------------------------------------------------------
    ref = by_subject_level(rows, "whole_head_exponent")
    complete = [s for s, d in ref.items() if {1, 2, 3, 4} <= set(d)]
    print(f"   rows {len(rows)}   subjects {len(ref)}   with all four levels: {len(complete)}")
    print("\n" + "=" * 100); print("P1  MANIFEST GATE"); print("=" * 100)
    if len(complete) < MIN_SUBJECTS:
        print(f"   FAIL: only {len(complete)} subjects have all four levels (minimum {MIN_SUBJECTS}).")
        print("   NO VERDICT IS ISSUED. The design needs four levels per subject and this cohort lacks them;")
        print("   that is a data-availability statement, not a result about any candidate.")
        return 1
    print(f"   PASS: {len(complete)} subjects carry all four levels.")

    rng = np.random.default_rng(20260730)
    summary = {}
    for cand in REGISTRY.all():
        per = by_subject_level(rows, cand.name)
        S, subs = s_index(per, 2)                 # primary: recovery vs mild
        Sp, _ = s_index(per, 3)                   # placebo: recovery vs moderate
        if len(S) < MIN_SUBJECTS:
            print(f"\n-- {cand.name}: NOT EVALUABLE (n={len(S)} subjects with levels 1,2,4)")
            summary[cand.name] = {"verdict": "NOT_EVALUABLE", "n_subjects": len(S)}
            continue
        m, (lo, hi) = float(S.mean()), boot_ci(S, rng)
        null = perm_null(per, 2, rng)
        mp = float(Sp.mean()) if len(Sp) else float("nan")

        # P2: monotone in plasma across levels 1-3, within subject
        mono = []
        for s, d in sorted(per.items()):
            if not {1, 2, 3} <= set(d):
                continue
            pl = [0.0, 438.0, 803.0]              # level medians; ordering is what matters, not the values
            mono.append(spearman([d[1], d[2], d[3]], pl))
        mono_frac = float(np.mean([x > 0 for x in mono if np.isfinite(x)])) if mono else float("nan")

        # P4 GATE FIRST, then the primary (rules 34 and 37)
        gate_ok = np.isfinite(mp) and mp >= m - 1e-9
        follows = "STATE" if lo > 0 else ("DRUG" if hi < 0 else "undetermined")
        print(f"\n-- {cand.name}")
        print(f"   P4 placebo gate (recovery vs moderate S={mp:+.3f} must be >= primary S={m:+.3f}): "
              f"{'PASS' if gate_ok else 'FAIL -- primary NOT interpretable'}")
        print(f"   P2 monotone in plasma over levels 1-3: {100*mono_frac:.0f}% of subjects "
              f"(n={len(mono)})" if np.isfinite(mono_frac) else "   P2 not evaluable")
        print(f"   PRIMARY S = {m:+.3f} [{lo:+.3f}, {hi:+.3f}]  over {len(S)} subjects   "
              f"null mean {null['mean']:+.3f} [{null['q025']:+.3f}, {null['q975']:+.3f}]")
        print(f"   -> follows {follows}" + ("" if gate_ok else "   (WITHHELD: placebo gate failed)"))
        summary[cand.name] = {"S": m, "ci": [lo, hi], "n_subjects": len(S), "follows": follows,
                              "placebo_S": mp, "placebo_gate": bool(gate_ok),
                              "null": null, "monotone_fraction_levels_1_3": mono_frac,
                              "verdict": (follows if gate_ok else "INDETERMINATE")}

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    b = summary.get("whole_head_exponent", {})
    p2 = np.isfinite(b.get("monotone_fraction_levels_1_3", np.nan)) and \
        b.get("monotone_fraction_levels_1_3", 0) > 0.5
    p3 = b.get("follows") == "DRUG" and b.get("placebo_gate")
    p4 = all(v.get("placebo_gate") for v in summary.values() if "placebo_gate" in v)
    print(f"   P1 manifest gate                            : PASS ({len(complete)} subjects)")
    print(f"   P2 exponent monotone in plasma (levels 1-3) : {'MET' if p2 else 'NOT MET'} "
          f"({100*b.get('monotone_fraction_levels_1_3', float('nan')):.0f}% of subjects)")
    print(f"   P3 exponent follows the DRUG (S < 0)        : {'MET' if p3 else 'NOT MET'} "
          f"(S={b.get('S', float('nan')):+.3f}, follows {b.get('follows')})")
    print(f"   P4 placebo gate holds for every candidate   : {'MET' if p4 else 'NOT MET'}")
    det = {k: v["follows"] for k, v in summary.items() if v.get("follows") in ("STATE", "DRUG")}
    print(f"\n   candidates with a determined direction: {det or 'none'}")
    if not det:
        print("   HONEST NEGATIVE: no candidate separates drug from state at n=20. That is a real result")
        print("   for Discovery Challenge A on public data.")
    print("\n   SCOPE: 20 healthy volunteers, one drug, one site. 'Responsiveness' is a two-choice reaction")
    print("   task, not consciousness. Nothing here speaks to covert awareness.")

    dst = os.path.join(RESULTS, "e05_drug_vs_state.json")
    json.dump({"experiment": "E05", "n_subjects_complete": len(complete),
               "search_space_size": REGISTRY.search_space_size(), "analytic_dof": 1,
               "summary": summary}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
