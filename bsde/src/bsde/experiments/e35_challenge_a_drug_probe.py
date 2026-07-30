#!/usr/bin/env python3
"""E35 — Challenge A's acceptance condition, run adversarially: propofol against dexmedetomidine.

REGISTERED BEFORE ANY FEATURE HAS BEEN RELATED TO DRUG OR STATE in this deposit. What has been read is the
structure — labels, patient counts, column names — which is the feasibility probe (loop step 2.5) and
carries no feature-outcome relationship. Committed before it does.

**THIS EXPERIMENT IS INVERTED, AND THE INVERSION IS THE POINT.** Challenge A's acceptance condition is that
a drug-identity probe must NOT out-predict the state model. So a probe that succeeds is a **failure** for
the challenge. This file is written to give the probe every chance — the adversary is the hypothesis here,
and a null result from it is the good outcome. Stating that up front is what stops a weak probe being
mistaken for a clean bill.

WHY THIS DEPOSIT MAKES THE CONDITION TESTABLE FOR THE FIRST TIME. E25 ran the probe and it PASSED — drug
|AUC-0.5| of 0.006 against a depth legibility of 0.063 — but it compared **sevoflurane against
desflurane**, two halogenated volatiles acting on the same GABA-A target. That is not an adversarial test;
it is the same case twice. Krause/Banks (PMID 41203472; Zenodo 10.5281/zenodo.15497531, CC-BY-SA 4.0) gives
**propofol against dexmedetomidine**, an alpha-2 agonist rather than a GABAergic agent, with documented
**opposite-signed** EEG effects at matched sedation depth (Akeju 2014, PMID 25187999: dexmedetomidine
spindles peak near 13 Hz against propofol's ~11 Hz frontal alpha, *"these drugs place patients into
different brain states"*; Xi 2018, PMID 29920532). **If a representation is going to leak drug identity,
this is where it leaks.**

THE STRUCTURE, parsed from `allData.csv` rather than taken from the paper: 34 patients, block-level OAA/S.
Propofol `WA`/`S`/`U` at 119/77/129 rows over 19 patients; dexmedetomidine `WA_dex`/`S_dex`/`U_dex` at
49/111/66 over 10; natural sleep `WS`/`N1`/`N2`/`N3`/`R` over 24. Nineteen patients have both a drug arm
and staged sleep.

REGISTERED PREDICTIONS. A failed gate makes the downstream verdict ABSENT (rule 31).

    P1  MACHINERY GATE, no drug-vs-state comparison yet.
        (a) COVERAGE — at least `MIN_PATIENTS` patients per drug arm contributing both `WA` and `U`.
        (b) **THE STATE CONTRAST MUST WORK FIRST.** For a feature to be worth probing, it must separate
            wake from unresponsive *within* a drug. **Comparing the drug-legibility of a feature that
            cannot track state at all is meaningless** — it would compare a real drug effect against
            nothing and declare the drug effect smaller only when both are noise. This is the same failure
            E33's "incumbent must be alive" gate was reaching for, applied to the right quantity.

    P2  STATE LEGIBILITY, the bar. For each feature, |AUC-0.5| separating `WA` from `U` within propofol,
        and `WA_dex` from `U_dex` within dexmedetomidine. Patient-clustered intervals.

    P3  DRUG LEGIBILITY AT MATCHED STATE, the probe. |AUC-0.5| separating `U` from `U_dex` — both
        unresponsive, different drug — and separately `S` from `S_dex`. Direction-free (`auc_abs`), because
        which drug scores "higher" is meaningless.

    P4  **THE ACCEPTANCE CONDITION.** For each feature, drug legibility must be BELOW state legibility.
        A feature failing this is a pharmacology detector wearing a consciousness label, and **Challenge A
        is failed for that feature however well it separates states.**

    P5  THE SLEEP CONTROL, which this deposit uniquely allows. Nineteen patients have both a drug arm and
        staged sleep. For each feature, |AUC-0.5| separating drug-unresponsive from `N2` sleep, **within
        patient**. A feature that tracks state rather than pharmacology should find drug-unresponsiveness
        and N2 relatively *similar*; one that separates them sharply is responding to the drug, to the
        intracranial recording condition, or to time of day. Reported, not gating — sleep is an arousal
        analogue and not a graded elicited responsiveness score, and no published work licenses treating it
        as one (checked; the nearest is Lendner 2020, PMID 32720644, which argues generality of a marker
        across arousal states and NOT absence of drug information).

    FALSIFICATION, inverted as everything here is: **P4 failing for the features that pass P2** is the
    finding. It would mean the measures that best track state are also the ones that best encode which drug
    produced it.

SCOPE AND LIMITS.
  * **Intracranial, epilepsy-surgery patients**, patient-specific electrode coverage, possible network
    abnormality. Nothing here transfers to scalp EEG without saying so.
  * **10 dexmedetomidine patients.** A real test and a thin one; the intervals will say which.
  * **Block-level OAA/S** (~6-7 min), not a per-second ladder.
  * **These are the depositors' features**, not this project's candidates, and cannot be audited from the
    CSV. `exponent_high` is not among them.
  * **Between-subject by construction** — a patient receives one drug — so the probe cannot be run within
    subject and every drug comparison carries the full weight of between-patient variation.
  * **CC-BY-SA 4.0**: ShareAlike propagates to derived artefacts (Invention Notebook entry 12).
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc_abs, cluster_bootstrap_ci                           # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "krause_dexprosleep_allData.csv")
OUT = os.path.join(RESULTS, "e35_challenge_a_drug_probe.json")

FEATURES = ("EffDim", "NmlzCmplx", "allEnvCorr", "AvgDelta", "AvgAlpha", "AvgGamma",
            "frontalDelta", "frontalAlpha", "frontwPLI", "backwPLI", "longwPLI", "allwPLI",
            "frontBias")
MIN_PATIENTS = 8
MIN_STATE_LEGIBILITY = 0.05
"""A feature must separate wake from unresponsive by at least this |AUC-0.5| within a drug before its
drug-legibility is worth comparing. Declared before the run; see P1(b) for why comparing a drug effect
against nothing would otherwise pass automatically."""


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load():
    rows = list(csv.DictReader(open(TABLE, newline="")))
    lab = np.array([r["label"] for r in rows])
    pid = np.array([r["patientID"] for r in rows])
    cols = {c: np.array([_f(r.get(c, "")) for r in rows], float) for c in FEATURES}
    return lab, pid, cols


def _contrast(cols, lab, pid, a, b, name, rng, reps=2000):
    """Direction-free |AUC-0.5| between two label groups, clustered on patient."""
    m = np.isin(lab, (a, b)) & np.isfinite(cols[name])
    if m.sum() < 20:
        return None
    y = (lab[m] == b).astype(float)
    x, g = cols[name][m], pid[m]
    if len(np.unique(y)) < 2 or len(np.unique(g)) < MIN_PATIENTS:
        return None
    a_ = auc_abs(y, x)
    lo, hi, _ = cluster_bootstrap_ci(lambda i: auc_abs(y[i], x[i]), g, rng, reps=reps)
    return {"auc_abs": float(a_), "legibility": float(abs(a_ - 0.5)),
            "ci": [float(lo), float(hi)], "n_rows": int(m.sum()),
            "n_patients": int(len(np.unique(g)))}


def main(argv=None) -> int:
    print("E35 — Challenge A's acceptance condition, adversarially: propofol vs dexmedetomidine")
    print("   INVERTED: a probe that SUCCEEDS is a FAILURE for Challenge A. The adversary is the hypothesis.")
    if not os.path.exists(TABLE):
        print(f"\n   *** {os.path.basename(TABLE)} absent.")
        return 2
    lab, pid, cols = _load()
    rng = np.random.default_rng(20260730)

    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE")
    print("=" * 100)
    n_prop = len({p for p, l in zip(pid, lab) if l in ("WA", "U")})
    n_dex = len({p for p, l in zip(pid, lab) if l in ("WA_dex", "U_dex")})
    print(f"   propofol patients with WA and/or U     : {n_prop}   (floor {MIN_PATIENTS})")
    print(f"   dexmedetomidine patients with WA/U_dex : {n_dex}   (floor {MIN_PATIENTS})")
    cov = n_prop >= MIN_PATIENTS and n_dex >= MIN_PATIENTS

    state = {}
    for f in FEATURES:
        p = _contrast(cols, lab, pid, "WA", "U", f, rng)
        d = _contrast(cols, lab, pid, "WA_dex", "U_dex", f, rng)
        state[f] = {"propofol": p, "dex": d}
    usable = [f for f, v in state.items()
              if v["propofol"] and v["propofol"]["legibility"] >= MIN_STATE_LEGIBILITY]
    print(f"   features separating WA from U within propofol by >= {MIN_STATE_LEGIBILITY}: "
          f"{len(usable)} of {len(FEATURES)}")
    print("      (a feature that cannot track state at all is not worth probing for drug identity —")
    print("       comparing a real drug effect against nothing would pass automatically)")
    p1 = bool(cov and usable)
    print(f"\n   P1 {'PASSED' if p1 else '*** FAILED'}")
    st = {"experiment": "E35", "n_propofol": n_prop, "n_dex": n_dex,
          "p1": {"usable_features": usable, "passed": p1}}
    if not p1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P2/P3/P4 — STATE legibility (the bar) against DRUG legibility at matched state (the probe)")
    print("=" * 100)
    print(f"   {'feature':14s} {'state|prop':>11s} {'state|dex':>10s} {'DRUG U vs U_dex':>16s} "
          f"{'DRUG S vs S_dex':>16s} {'verdict':>22s}")
    verdicts, rows_out = [], {}
    for f in FEATURES:
        sp = state[f]["propofol"]
        sd = state[f]["dex"]
        du = _contrast(cols, lab, pid, "U", "U_dex", f, rng)
        ds = _contrast(cols, lab, pid, "S", "S_dex", f, rng)
        if not (sp and du):
            continue
        bar = max(sp["legibility"], sd["legibility"] if sd else 0.0)
        worst_drug = max([x["legibility"] for x in (du, ds) if x] or [float("nan")])
        ok = bool(np.isfinite(worst_drug) and worst_drug < bar)
        if f in usable:
            verdicts.append(ok)
        rows_out[f] = {"state_propofol": sp, "state_dex": sd, "drug_U": du, "drug_S": ds,
                       "bar": float(bar), "worst_drug": float(worst_drug), "passes_p4": ok}
        mark = ("ok" if ok else "*** LEAKS DRUG") if f in usable else "(state too weak)"
        print(f"   {f:14s} {sp['legibility']:11.3f} "
              f"{(sd['legibility'] if sd else float('nan')):10.3f} "
              f"{du['legibility']:16.3f} {(ds['legibility'] if ds else float('nan')):16.3f} "
              f"{mark:>22s}")
    p4 = bool(verdicts) and all(verdicts)
    n_leak = sum(1 for v in verdicts if not v)
    print(f"\n   P4 {'PASSED — no state-tracking feature leaks drug identity' if p4 else f'*** FAILED — {n_leak} of {len(verdicts)} state-tracking features are MORE legible by drug than by state'}")
    st["p234"] = {"per_feature": rows_out, "p4_passed": p4, "n_leaking": n_leak}

    print("\n" + "=" * 100)
    print("P5 — SLEEP CONTROL (reported, not gating): drug-unresponsive vs N2 sleep")
    print("=" * 100)
    print("   A feature tracking STATE should find these relatively similar; one separating them sharply is")
    print("   responding to the drug, the recording condition, or the time of day. Sleep is an arousal")
    print("   analogue, not a graded elicited responsiveness score, and nothing licenses treating it as one.")
    sl = {}
    for f in usable:
        u_n2 = _contrast(cols, lab, pid, "U", "N2", f, rng)
        d_n2 = _contrast(cols, lab, pid, "U_dex", "N2", f, rng)
        sl[f] = {"propofolU_vs_N2": u_n2, "dexU_vs_N2": d_n2}
        print(f"   {f:14s} propofol-U vs N2 {(u_n2['legibility'] if u_n2 else float('nan')):.3f}   "
              f"dex-U vs N2 {(d_n2['legibility'] if d_n2 else float('nan')):.3f}")
    st["p5"] = sl

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p4:
        print("   The acceptance condition HOLDS against the adversarial drug pair: among features that")
        print("   track state, none is more legible by drug than by state. This is the first time it has")
        print("   been tested against a non-GABAergic agent — E25 compared two volatiles.")
        v = "acceptance_condition_holds"
    else:
        print(f"   The acceptance condition FAILS: {n_leak} of {len(verdicts)} state-tracking features carry")
        print("   MORE drug information than state information at matched unresponsiveness. Those features")
        print("   are pharmacology detectors wearing a consciousness label, and Challenge A is failed for")
        print("   them however well they separate states.")
        v = "acceptance_condition_fails"
    st["verdict"] = v
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
