#!/usr/bin/env python3
"""E36 — is E35's measure-family split real, or a post-hoc line drawn through 13 noisy numbers?

WHAT THIS EXPERIMENT CAN AND CANNOT DO, STATED FIRST BECAUSE IT GOVERNS EVERYTHING BELOW.

E36 runs on **the same rows E35 ran on** — the Krause dexmedetomidine/propofol/sleep deposit
(10.5281/zenodo.15497531). It therefore **cannot confirm E35's observation**, and no outcome of this file
may be written up as confirmation. It exists to *kill* the observation, using three machineries E35 did not
have. A pass here means only "the observation survived an attempt to kill it on its own data"; the claim
stays unclaimed until an independent two-agent cohort exists, and none does — no public deposit located
across PubMed, OpenNeuro, Dryad, Zenodo, OSF, Figshare and PhysioNet pairs raw EEG with two mechanistically
distinct anaesthetics in the same patients. That search is recorded in QUEUE.md Q8.

WHAT E35 LEFT BEHIND. Its P4 asked, per feature, whether drug identity is more legible than behavioural
state. Twelve features passed as registered; five failed under the stricter bar, and every one of those five
was a power or complexity measure. Read off the point estimates, the phase-coupling features sit at drug
legibility |AUC-0.5| of 0.000-0.066 on the matched-unresponsiveness contrast while everything else sits at
0.217-0.368. E35 declined to claim that, for three stated reasons: thirteen features, no multiplicity
correction, and no test of the family contrast itself. This file supplies all three.

THE FAMILIES, FIXED HERE AND NOT REVISABLE AFTER THE RUN.

    PHASE      frontwPLI, backwPLI, longwPLI, allwPLI                          (4)
    AMPLITUDE  EffDim, NmlzCmplx, allEnvCorr, AvgDelta, AvgAlpha, AvgGamma,
               frontalDelta, frontalAlpha                                      (8)

Two assignment decisions, both made before any statistic was computed and both defensible on the column
definitions alone:

  * `allEnvCorr` is an amplitude-ENVELOPE correlation. It is a connectivity measure, and it is assigned to
    AMPLITUDE anyway, because the sharpened reading of E35 is that the split runs between phase-based and
    amplitude-based quantities rather than between connectivity and non-connectivity. Assigning the one
    measure that discriminates the two readings *against* the connectivity story is the conservative choice:
    if the split is really "connectivity vs the rest", putting allEnvCorr in AMPLITUDE works against the
    primary statistic. This assignment is the reason the primary can fail on a distinction the data itself
    suggested, which is the only way that suggestion can be tested at all.
  * `frontBias` is **excluded from both families and from the primary**. Checked numerically before the run:
    it equals `frontwPLI - backwPLI` to 9.2e-16, i.e. it is an exact deterministic function of two features
    already in PHASE. Including it would count the same information twice and inflate PHASE's weight in a
    mean. It is reported in P5 and enters nothing.

THE STATISTIC, AND WHY IT IS A DIFFERENCE OF DIFFERENCES.

Per feature f, both computed as direction-free |AUC - 0.5| with a patient-clustered bootstrap:

    drug_f   = legibility of DRUG IDENTITY at matched unresponsiveness      (U vs U_dex)
    state_f  = legibility of BEHAVIOURAL STATE pooled over both agents      (WA + WA_dex  vs  U + U_dex)

    D = mean_AMPLITUDE(drug)  - mean_PHASE(drug)
    S = mean_AMPLITUDE(state) - mean_PHASE(state)
    Delta = D - S                                                            <- THE PRIMARY

D alone is not enough, and this is the alternative explanation the whole file is built around: **a family
that leaks less drug may simply be a weaker measure.** A feature that separates nothing leaks nothing, and
would pass any drug probe by being useless (error-catalogue rule 32). S measures exactly that — the family
gap in raw capability — and subtracting it leaves the part of the drug gap that capability does not explain.
If PHASE is merely insensitive, D and S move together and Delta collapses to zero. Delta is the statistic
that can distinguish agent-invariance from insensitivity; D cannot.

One statistical detail that has to be said out loud, because |AUC - 0.5| is a folded statistic and folded
statistics are biased upward under the null: E[|AUC - 0.5|] > 0 when nothing is there, and how much depends
on sample size. That bias is why D and S are each computed as a difference **within one contrast** — the two
families are measured on the identical rows with the identical n, so the folding bias is common to them and
subtracts out of D, out of S, and hence out of Delta. It does *not* subtract out of a single feature's
legibility, which is another reason no per-feature claim is made here.

State is pooled across agents rather than taken per agent on purpose. E35 reported state per drug and then
had to choose between `max` and `min` of the two as a bar — a choice that turned out to decide the verdict
for five features, and a choice this file must not inherit. One pooled contrast has no such knob.

THE NUISANCE FLOOR, WHICH THE FEASIBILITY PROBE FOUND AND E35 DID NOT CHECK.

`governance/feasibility.py` was run on the U/U_dex rows before this file was written (label = drug arm,
artefact = pctGoodSamples, then Subdural). It returned two confounds:

    pctGoodSamples   fraction of dex rows falls 0.40 -> 0.10 from the worst to the best quality decile,
                     spread 0.536. Data quality differs systematically between the arms.
    Subdural         0.49 vs 0.12 across the two deciles where it varies. Electrode type differs too.

So the arms are separable from nuisance channels alone, and every feature's drug legibility has a floor it
did not earn. P0 measures that floor by running the identical drug contrast on `pctGoodSamples` and
`Subdural` themselves. The floor is reported, and it is the reference a per-feature drug leak must clear
before it means anything. It does not gate the primary — Delta is a *difference between families* measured
on the same rows, so a floor common to both families cancels out of it. What the floor would break is a
per-feature claim, and this file makes none.

REGISTERED BEFORE THE DATA WAS READ. Evaluated in this order; the failing branch is written first in each.

  G1  MACHINERY GATE, evaluated before anything else. Both families must be CAPABLE, or the primary is a
      comparison between a measure and a non-measure. Requirement: each family contains at least 3 features
      with pooled state legibility >= 0.15. If either family fails, nothing downstream is reported and the
      outcome is ABSENT, not negative (rule 31).

  P0  THE NUISANCE FLOOR. Drug legibility of pctGoodSamples and Subdural. Reported, not gating; see above.

  P1  THE PRIMARY. Delta, with a 95 % patient-clustered bootstrap CI. **The same patient resample is used
      for both contrasts within a replicate**, so D and S are coupled exactly as they are in the data and
      their difference carries the right variance. FAILS if the CI includes 0. A CI that spans zero is not a
      direction, and must not be reported as one (rule 37).

  P2  THE PLACEBO GATE, evaluated after the primary and gating the verdict (rule 34). The families are
      shuffled: **all 495 ways of splitting the 12 primary features into a group of 4 and a group of 8 are
      enumerated exhaustively** — not sampled — and Delta is recomputed for each. With 12 features some
      split always looks clean, and this is the test of whether the real one is special. FAILS unless the
      real Delta sits at or above the 97.5th percentile of that distribution, i.e. in the top ~12 of 495.
      This gate is the entire reason the file exists, because "I drew a line through 13 numbers after
      seeing them" is precisely what E35 was accused of by its own write-up.

  P3  MULTIPLICITY, reported not gating. Westfall-Young step-down max-T across the 12 per-feature drug-leak
      statistics, with the null built by permuting arm assignment **at the patient level** — drug is a
      patient attribute, so permuting rows would manufacture power that does not exist. Reports adjusted
      p-values and `effective_tests`; E01 measured rho = 0.9952 between two candidates in this project, so
      the Bonferroni-equivalent count is expected to be far below 12 and that is the number worth reading.
      NOTE the limitation: this permutation breaks the arm-nuisance association too, so P3 tests "carries
      drug information beyond chance", NOT "carries drug information beyond quality and electrode type".
      P0 is what speaks to the second question and it speaks to it only descriptively.

  P4  ROBUSTNESS, reported not gating. Delta recomputed on the quality band where the two arms actually
      overlap (deciles 2-7 of pctGoodSamples, pooled). Registered as a robustness arm before the run, so it
      cannot become an escape hatch if the primary fails — a failed primary is a failed primary, and
      DISCOVERY_LOOP.md §2 forbids a successor that changes the cohort rather than the instrument.

  P5  REPORTED CONTEXT, no verdict attached. frontBias, held out of the primary as an exact function of two
      PHASE features; and the per-feature table that P1 aggregates over.

VERDICT RULE, written before the run.

    NOT INTERPRETABLE   G1 failed.
    NOT MET             Delta's CI includes 0, or the shuffled-family placebo puts the real Delta below its
                        97.5th percentile.
    SURVIVES            both hold. The permitted sentence is: *"within this deposit, the measure-family
                        split is not explained by post-hoc partitioning, and is not explained by
                        phase-coupling measures being weaker instruments."* The forbidden sentences are
                        anything of the form "phase coupling is agent-invariant" or "connectivity tracks
                        consciousness" — one deposit, 10 dexmedetomidine patients, intracranial electrodes
                        in epilepsy-surgery patients, and the same rows E35 used.

INCUMBENT (rule 45). There is no incumbent measure for this question, because the question is about a
partition of measures rather than about prediction. The incumbent *explanation* is the one P1 is built to
beat: "phase-coupling features leak less drug because they measure less". S is that incumbent, quantified,
and Delta is the margin over it.

SCOPE LIMIT. Intracranial recordings from epilepsy-surgery patients; block-level features at ~6-7 min
resolution; 19 propofol and 10 dexmedetomidine patients; features as shipped by the depositors, not
recomputed here. Nothing in this file transfers to scalp EEG without being re-measured there.
"""

from __future__ import annotations

import csv
import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc_abs                                                 # noqa: E402
from bsde.verifier.multiplicity import westfall_young_maxt                              # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "krause_dexprosleep_allData.csv")
OUT = os.path.join(RESULTS, "e36_family_split_probe.json")

PHASE = ("frontwPLI", "backwPLI", "longwPLI", "allwPLI")
AMPLITUDE = ("EffDim", "NmlzCmplx", "allEnvCorr", "AvgDelta", "AvgAlpha", "AvgGamma",
             "frontalDelta", "frontalAlpha")
PRIMARY = PHASE + AMPLITUDE
HELD_OUT = ("frontBias",)
NUISANCE = ("pctGoodSamples", "Subdural")

WAKE = ("WA", "WA_dex")
UNRESP = ("U", "U_dex")

MIN_CAPABLE_STATE = 0.15
MIN_CAPABLE_PER_FAMILY = 3
PLACEBO_PERCENTILE = 97.5
REPS = 2000
PERMS = 2000
SEED = 20260730


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load():
    rows = list(csv.DictReader(open(TABLE, newline="")))
    lab = np.array([r["label"] for r in rows])
    pid = np.array([r["patientID"] for r in rows])
    keep = np.isin(lab, WAKE + UNRESP)
    cols = {c: np.array([_f(r.get(c, "")) for r in rows], float)[keep]
            for c in PRIMARY + HELD_OUT + NUISANCE}
    return lab[keep], pid[keep], cols


def _leg(x, y):
    """Direction-free |AUC-0.5| for one feature vector against one binary label."""
    m = np.isfinite(x)
    if m.sum() < 20:
        return float("nan")
    yy, xx = y[m], x[m]
    if np.unique(yy).size < 2:
        return float("nan")
    return abs(auc_abs(yy, xx) - 0.5)


def _both(cols, lab, names, idx):
    """(drug legibility, state legibility) per feature over the row subset `idx`."""
    l_ = lab[idx]
    drug_rows = np.isin(l_, UNRESP)
    y_drug = (l_[drug_rows] == "U_dex").astype(float)
    y_state = np.isin(l_, UNRESP).astype(float)
    d, s = {}, {}
    for n in names:
        v = cols[n][idx]
        d[n] = _leg(v[drug_rows], y_drug)
        s[n] = _leg(v, y_state)
    return d, s


def _delta(d, s, phase, amp):
    def mu(dd, keys):
        vals = [dd[k] for k in keys if np.isfinite(dd[k])]
        return float(np.mean(vals)) if vals else float("nan")
    D = mu(d, amp) - mu(d, phase)
    S = mu(s, amp) - mu(s, phase)
    return D - S, D, S


def _patient_index(pid, patients):
    """Row index built by concatenating every row belonging to each patient in `patients`."""
    by = {}
    for i, p in enumerate(pid):
        by.setdefault(p, []).append(i)
    return np.concatenate([np.asarray(by[p], int) for p in patients])


def main(argv=None) -> int:
    print("E36 — is E35's measure-family split real, or a post-hoc line through 13 noisy numbers?")
    print("   SAME ROWS AS E35. This file can only KILL the observation; it cannot confirm it.")
    if not os.path.exists(TABLE):
        print(f"\n   *** {os.path.basename(TABLE)} absent.")
        return 2

    lab, pid, cols = _load()
    rng = np.random.default_rng(SEED)
    all_idx = np.arange(len(lab))
    patients = np.array(sorted(set(pid)))
    st = {"experiment": "E36", "n_rows": int(len(lab)), "n_patients": int(patients.size),
          "phase": list(PHASE), "amplitude": list(AMPLITUDE), "held_out": list(HELD_OUT)}

    d_obs, s_obs = _both(cols, lab, PRIMARY + HELD_OUT + NUISANCE, all_idx)

    print("\n" + "=" * 100)
    print("G1 — MACHINERY GATE: both families must be capable measures")
    print("=" * 100)
    cap = {fam: [n for n in names if np.isfinite(s_obs[n]) and s_obs[n] >= MIN_CAPABLE_STATE]
           for fam, names in (("PHASE", PHASE), ("AMPLITUDE", AMPLITUDE))}
    for fam in ("PHASE", "AMPLITUDE"):
        print(f"   {fam:10s} features with pooled state legibility >= {MIN_CAPABLE_STATE}: "
              f"{len(cap[fam])}  (floor {MIN_CAPABLE_PER_FAMILY})   {cap[fam]}")
    g1 = all(len(cap[f]) >= MIN_CAPABLE_PER_FAMILY for f in cap)
    print(f"\n   G1 {'PASSED' if g1 else '*** FAILED'}")
    st["g1"] = {"capable": cap, "passed": bool(g1)}
    if not g1:
        print("   A family that cannot track state at all cannot be compared on what it leaks.")
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P0 — THE NUISANCE FLOOR (reported, not gating)")
    print("=" * 100)
    print("   Drug legibility of channels that are not brain activity at all.")
    for n in NUISANCE:
        print(f"   {n:20s} drug legibility {d_obs[n]:.3f}")
    floor = float(np.nanmax([d_obs[n] for n in NUISANCE]))
    print(f"\n   floor = {floor:.3f}. A per-feature drug leak below this is not evidence the feature")
    print("   carries the agent; it is consistent with carrying data quality or electrode type.")
    print("   Delta is a between-family difference on the same rows, so a floor common to both")
    print("   families cancels out of it — the floor constrains per-feature claims, and this file")
    print("   makes none.")
    st["p0"] = {"nuisance": {n: d_obs[n] for n in NUISANCE}, "floor": floor}

    print("\n" + "=" * 100)
    print("P5 — the per-feature table P1 aggregates over (reported, no verdict)")
    print("=" * 100)
    print(f"   {'feature':14s} {'family':10s} {'drug':>7s} {'state':>7s}   above floor?")
    for n in PRIMARY + HELD_OUT:
        fam = "PHASE" if n in PHASE else ("AMPLITUDE" if n in AMPLITUDE else "held out")
        print(f"   {n:14s} {fam:10s} {d_obs[n]:7.3f} {s_obs[n]:7.3f}   {d_obs[n] > floor}")
    st["p5"] = {"drug": {n: d_obs[n] for n in PRIMARY + HELD_OUT},
                "state": {n: s_obs[n] for n in PRIMARY + HELD_OUT}}

    print("\n" + "=" * 100)
    print("P1 — THE PRIMARY: Delta = (drug gap) - (state gap)")
    print("=" * 100)
    delta, D, S = _delta(d_obs, s_obs, PHASE, AMPLITUDE)
    boot = []
    for _ in range(REPS):
        drawn = rng.choice(patients, size=patients.size, replace=True)
        idx = _patient_index(pid, drawn)
        db, sb = _both(cols, lab, PRIMARY, idx)
        v, _, _ = _delta(db, sb, PHASE, AMPLITUDE)
        if np.isfinite(v):
            boot.append(v)
    lo, hi = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))) if boot else (np.nan,) * 2
    print(f"   D  (drug gap,  AMPLITUDE - PHASE) : {D:+.4f}")
    print(f"   S  (state gap, AMPLITUDE - PHASE) : {S:+.4f}     <- the incumbent explanation")
    print(f"   Delta = D - S                     : {delta:+.4f}  [{lo:+.4f}, {hi:+.4f}]"
          f"   ({len(boot)} patient resamples)")
    p1 = bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0))
    if not p1:
        print("\n   P1 *** FAILED — the interval includes 0. That is not a direction (rule 37).")
    else:
        print(f"\n   P1 PASSED — the drug gap exceeds what the capability gap explains.")
    st["p1"] = {"delta": float(delta), "D": float(D), "S": float(S), "ci": [lo, hi],
                "n_resamples": len(boot), "passed": p1}

    print("\n" + "=" * 100)
    print("P2 — PLACEBO GATE: all 495 ways of splitting 12 features into 4 and 8")
    print("=" * 100)
    null = []
    for combo in itertools.combinations(PRIMARY, len(PHASE)):
        other = tuple(n for n in PRIMARY if n not in combo)
        v, _, _ = _delta(d_obs, s_obs, combo, other)
        if np.isfinite(v):
            null.append(v)
    null = np.asarray(null, float)
    thresh = float(np.percentile(null, PLACEBO_PERCENTILE))
    pct = float(100.0 * np.mean(null <= delta))
    rank = int(np.sum(null >= delta))
    print(f"   enumerated splits                : {null.size}  (exhaustive, not sampled)")
    print(f"   real Delta                       : {delta:+.4f}")
    print(f"   {PLACEBO_PERCENTILE}th percentile of shuffled splits : {thresh:+.4f}")
    print(f"   real Delta sits at the {pct:.1f}th percentile — {rank} of {null.size} splits reach it")
    p2 = bool(delta >= thresh)
    print(f"\n   P2 {'PASSED' if p2 else '*** FAILED — the real split is not special'}")
    st["p2"] = {"n_splits": int(null.size), "threshold": thresh, "percentile": pct,
                "n_at_or_above": rank, "passed": p2}

    print("\n" + "=" * 100)
    print("P3 — MULTIPLICITY across the 12 per-feature drug-leak statistics (reported)")
    print("=" * 100)
    arm = {}
    for p, l in zip(pid, lab):
        if l in UNRESP:
            arm[p] = 1.0 if l == "U_dex" else 0.0
    pats = np.array(sorted(arm))
    labels = np.array([arm[p] for p in pats])
    drug_rows = np.isin(lab, UNRESP)
    row_pat = pid[drug_rows]
    nullm = np.empty((PERMS, len(PRIMARY)), float)
    for k in range(PERMS):
        perm = rng.permutation(labels)
        mp = dict(zip(pats, perm))
        y = np.array([mp[p] for p in row_pat], float)
        for j, n in enumerate(PRIMARY):
            nullm[k, j] = _leg(cols[n][drug_rows], y)
    obs = [d_obs[n] for n in PRIMARY]
    wy = westfall_young_maxt(obs, np.nan_to_num(nullm, nan=0.0), names=list(PRIMARY))
    print(f"   permutations                     : {PERMS} (arm permuted at the PATIENT level)")
    print(f"   effective_tests                  : {wy['effective_tests']:.2f} of {wy['n_candidates']}")
    surv = [n for n in PRIMARY if wy["adjusted"][n] <= 0.05]
    print(f"   features with adjusted p <= 0.05 : {len(surv)}   {surv}")
    for n in PRIMARY:
        fam = "PHASE" if n in PHASE else "AMPLITUDE"
        print(f"      {n:14s} {fam:10s} drug {d_obs[n]:6.3f}   raw p {wy['raw'][n]:.4f}   "
              f"adj p {wy['adjusted'][n]:.4f}")
    print("   Tests 'beyond chance', NOT 'beyond quality and electrode type' — see P0.")
    st["p3"] = {"effective_tests": wy["effective_tests"], "adjusted": wy["adjusted"],
                "raw": wy["raw"], "survivors": surv}

    print("\n" + "=" * 100)
    print("P4 — ROBUSTNESS: the quality band where the arms overlap (reported, not gating)")
    print("=" * 100)
    q = cols["pctGoodSamples"]
    ok = np.isfinite(q)
    lo_q, hi_q = np.percentile(q[ok], [20, 80])
    band = ok & (q >= lo_q) & (q <= hi_q)
    print(f"   pctGoodSamples band [{lo_q:.4f}, {hi_q:.4f}] keeps {int(band.sum())} of {int(len(lab))} rows")
    db, sb = _both(cols, lab, PRIMARY, np.where(band)[0])
    vb, Db, Sb = _delta(db, sb, PHASE, AMPLITUDE)
    print(f"   Delta in band                    : {vb:+.4f}   (D {Db:+.4f}, S {Sb:+.4f})")
    print(f"   Delta on all rows                : {delta:+.4f}")
    st["p4"] = {"band": [float(lo_q), float(hi_q)], "n_rows": int(band.sum()),
                "delta": float(vb), "D": float(Db), "S": float(Sb)}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not p1:
        verdict = "not_met_primary"
        print("   NOT MET: Delta's interval includes 0 — the capability gap explains the drug gap.")
    elif not p2:
        verdict = "not_met_placebo"
        print("   NOT MET: a shuffled family split reaches the real one. The line was post hoc.")
    else:
        verdict = "survives"
        print("   SURVIVES — within this deposit, the family split is explained neither by post-hoc")
        print("   partitioning nor by phase-coupling measures being weaker instruments.")
        print("   NOT a claim that phase coupling is agent-invariant. Same rows as E35, one deposit,")
        print("   10 dexmedetomidine patients, intracranial, epilepsy-surgery cohort.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
