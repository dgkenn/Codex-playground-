#!/usr/bin/env python3
"""E345 -- does any EEG measure track GRADED behaviour beyond what drug concentration explains?

PRE-REGISTRATION. Committed before the data is on disk, let alone before any statistic exists.

DEPOSIT. PhysioNet `eeg-power-anesthesia` 1.0.0 -- "Multitaper spectra recorded during GABAergic
anesthetic unconsciousness", DOI 10.13026/m792-h077, Restricted Health Data License 1.5.0. Fetch with
`bsde/scripts/physionet_fetch.sh eeg-power-anesthesia 1.0.0 <dest>` once `PHYSIONET_USER` and
`PHYSIONET_PASSWORD` are set in the environment.

------------------------------------------------------------------------------------------------------
WHAT THIS PROJECT ALREADY KNOWS ABOUT THIS DEPOSIT, read before the design was written (rule 96 -- the
constraint that kills a design is usually already recorded by whoever met the data first).
`docs/DEPOSIT_ACCESS_STATUS.md` records a full extraction on 2026-08-01 (E148-E158), since lost with the
container. Four constraints from it bind this design:

  * **The volunteer arm hosts behavioural-landmark designs; the OR arm cannot.** Each of the 10
    volunteers has exactly one behavioural LOC and one behavioural ROC, defined by response probability
    to click and verbal cues crossing 5 %, with 18-67 min of drug-free baseline.
  * **In the OR arm, 0 of 44 cases have a conscious epoch adjacent to an unconscious one** -- median gap
    286 epochs (10 min), range 31-1051, because the deposit labels induction-to-surgery `NaN` on the
    stated grounds that the true LOC is unknowable retrospectively. **So the OR arm is excluded here by
    construction, not by a result.**
  * **The OR arm's agent contrast is confounded by case length**: `pure_propofol` 27, `mixed` 16,
    `pure_sevo` **1**, with sevoflurane cases nearly twice as long, and E154 measured case duration
    identifying the agent at |AUC-0.5| = 0.3771. A third arm of one is not an arm.
  * **n = 10 is the whole cohort for this question anywhere this project can reach.** That is small, and
    the design is built around it rather than pretending otherwise -- see THE EXACT NULL below.

WHY THIS QUESTION AND NOT ANOTHER DISSOCIATION HUNT. **E344/T8 measured that the criterion this
programme has been using is broken.** "Measure X separates consciousness but does NOT separate drug" tests
its second half by ACCEPTING a null, so a measure too imprecise to reject anything satisfies it for free:
on synthetics with a known drug response the false-dissociation rate reaches 11 % at intermediate noise,
and by noise 2.0 the criterion returns 0.110 for a drug-responsive measure against 0.212 for a true
dissociator -- nearly uninformative. **E344/T9** then showed the resulting set is unstable at n = 18.
Repeating that design at n = 10 would be worse on both counts.

**This deposit permits a design with neither defect, because its behavioural axis is CONTINUOUS.**
Response probability is graded, measured repeatedly within each subject, and moves in both directions
(down through induction, up through emergence). A correlation against a graded outcome is POSITIVE
evidence, so nothing here rests on accepting a null; and the drug half is tested by an EQUIVALENCE test
with a margin stated below, which is the fix T8 prescribes.

------------------------------------------------------------------------------------------------------
THE INCUMBENT (rule 45), and why it is the right kind (rule 86). The incumbent is the **drug exposure** --
the deposit's own concentration or dose series -- not another observation of the patient. Rule 86 was paid
for by E204, where RASS and GCS-motor turned out to be two readings of one bedside act; an EXPOSURE cannot
share a measurement act with a behavioural outcome, so a null against it means something.

PRIMARIES. All within subject; the unit of inference is the SUBJECT throughout (rule 69).

P1  BEHAVIOURAL TRACKING. Per subject, Spearman rho between each candidate measure and response
    probability across that subject's epochs, aggregated across the 10 subjects.
    A measure TRACKS BEHAVIOUR if its subject-level MEAN excludes zero on the exact null below.
    The aggregate is the mean rather than the median because the median is degenerate under sign-flipping
    at small n -- see the docstring of `exact_signflip`, where a unit test written before registration
    showed ten identical +0.5 correlations returning p = 1.0000 under the median.

P2  INCREMENT OVER THE DRUG. Per subject, the partial Spearman of measure against response probability
    GIVEN the drug exposure series, by rank-residualising both on the exposure within subject.
    A measure ADDS if its subject-level mean partial excludes zero on the same exact null.
    **This is the primary that matters**: P1 alone is satisfied by anything that tracks the drug, since
    the drug is what moves behaviour.

P3  DRUG-IDENTIFICATION EQUIVALENCE (the T8 fix, and Challenge A's minimisation half). Challenge A asks
    for a measure that predicts loss and recovery *while MINIMISING drug-identification information*
    (rule 95 -- the verbatim statement, echoed at registration). Instead of accepting a null, this is an
    EQUIVALENCE test with a margin fixed here, before any data:
        MARGIN = 0.20 on |Spearman(measure, exposure)| at the subject level.
    A measure is DRUG-MINIMAL if the upper bound of its 90 % subject-level interval on
    |rho(measure, exposure)| lies BELOW 0.20 (two one-sided tests at 5 %).
    **0.20 is not a round number chosen for comfort**: it is the value at which the drug series explains
    under 4 % of a measure's rank variance, i.e. the point past which "this measure is a drug proxy"
    stops being a live reading. It is stated here so it cannot move afterwards, and a measure that fails
    equivalence is reported as NOT SHOWN TO BE DRUG-MINIMAL, never as drug-driven -- the two are
    different claims and only one is tested.

P4  DIRECTION SYMMETRY -- does a measure track behaviour on the way DOWN and on the way UP?
    P1 recomputed separately on the induction side and the emergence side of each subject's record.
    A measure is SYMMETRIC if both sides exclude zero with the same sign. **Registered because Challenge
    A says "loss AND recovery"**, and because a measure that only works on induction is a dose proxy.

THE EXACT NULL, and why n = 10 is a feature here. Subject-level inference over 10 subjects admits
**complete enumeration**: all 2^10 = 1,024 sign assignments are computed, so every p-value in this file
is EXACT with no Monte Carlo error and no seed dependence (rules 46 and 85 cannot apply). The smallest
attainable two-sided p is 2/1024 = 0.00195, which is stated in advance as the resolution floor.

PREDICTION. At least one measure passes P1 and P2. **NO measure passes all of P1, P2, P3 and P4** -- the
drug-minimal requirement is expected to be where everything dies, because a measure that tracks behaviour
through a drug-induced transition is tracking something the drug causes.
WRONG IF a measure passes all four. **That is named first because it would be the strongest single result
this programme has produced**, and because a surprising pass demands the harder scrutiny.

GATES. Each guards one claim and is named for it (rule 97).
  G0  FEASIBILITY PROBE, RUN FIRST AND BEFORE ANY PRIMARY IS COMPUTED (rule 41). The probe reports the
      deposit's actual shape -- files found, volunteer count, epochs per subject, which column carries
      response probability, which carries drug exposure, and the coverage of each -- and the file
      REFUSES to compute a primary unless it can identify the response-probability and exposure series
      **unambiguously**. It never guesses a column. If G0 fails, E345 is not run, the probe's output is
      reported, and the design is revised as a successor with that output in hand. **This is the honest
      form of rule 41 under an access constraint: the probe cannot precede the registration, so it is
      registered AS the first gate and given the power to stop the run.**
  G1  BEHAVIOURAL AXIS ALIVE (rule 53): response probability must actually vary within subject -- at
      least 8 of 10 subjects showing both a high (> 0.8) and a low (< 0.2) epoch. Otherwise "tracking
      behaviour" has nothing to track and every primary is uninterpretable.
  G2  INCUMBENT ALIVE (rule 53 / E33): the drug exposure must itself correlate with response probability
      at |median rho| >= 0.3. If the exposure does not move behaviour in this cohort, P2's increment is
      not an increment over anything.
  G3  EQUIVALENCE HAS POWER: a planted measure equal to the exposure plus small noise must FAIL
      equivalence, and a planted measure independent of the exposure (verified, rule 77/84, and printed)
      must PASS it. An equivalence test at n = 10 can be underpowered to the point of rejecting
      everything, and if the independent plant cannot pass, P3 is reported NOT INTERPRETABLE rather than
      as evidence that nothing is drug-minimal (rule 40 in its "cannot pass" form, rule 81).
  G4  DIRECTION COVERAGE: P4 requires >= 8 subjects with usable epochs on BOTH sides; otherwise P4 alone
      reports INSUFFICIENT and P1-P3 stand (rule 97 -- one gate per claim, so a P4 failure must not
      refuse P1).

SCOPE AND LIMITS, stated before any result.
  * **10 subjects.** Every interval here is wide and the resolution floor is p = 0.00195. This is a
    small-n study and is reported as one; T9 has already shown what a 18-subject cohort does to set
    membership, and 10 is worse.
  * The OR arm is excluded by construction (see above), so nothing here speaks to surgical patients.
  * Response probability is a behavioural measurement, not a measurement of experience. A measure that
    tracks it tracks responsiveness (rule 42 -- the inference to consciousness is an inference and is
    labelled one).
  * This is a **replication in spirit** of the volunteer-arm work in the deposit's own publications and
    of PMID 31326088's drug-independent state tracking; the unclaimed part is P2 and P3 jointly -- an
    increment over the exposure combined with an equivalence-tested minimisation of it.

    python -m bsde.experiments.e345_mgh_graded_behaviour --probe        # G0 only, no primaries
    python -m bsde.experiments.e345_mgh_graded_behaviour
"""
from __future__ import annotations

import argparse, itertools, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
DEFAULT_DATA = "/tmp/eeg_probe/physionet/eeg-power-anesthesia/1.0.0"

MARGIN = 0.20            # P3's equivalence margin, fixed at registration
MIN_SUBJ = 8             # G1/G4 coverage floor
INCUMBENT_FLOOR = 0.30   # G2
RESP_PAT = re.compile(r"(resp.*prob|prob.*resp|p_?response|resp_?p\b|pdetect|p_detect)", re.I)
EXPO_PAT = re.compile(r"(conc|ce\b|cp\b|effect_?site|dose|mac|propofol|sevo|infusion)", re.I)


def spearman(x, y):
    pr = [(a, b) for a, b in zip(x, y)
          if a is not None and b is not None and math.isfinite(a) and math.isfinite(b)]
    if len(pr) < 10:
        return float("nan")
    return _pearson(_rank([a for a, _ in pr]), _rank([b for _, b in pr]))


def _rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        av = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[o[k]] = av
        i = j + 1
    return r


def _pearson(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def partial_spearman(x, y, z):
    """rank-residualise x and y on z, then correlate the residuals."""
    pr = [(a, b, c) for a, b, c in zip(x, y, z)
          if all(v is not None and math.isfinite(v) for v in (a, b, c))]
    if len(pr) < 12:
        return float("nan")
    rx, ry, rz = (_rank([p[i] for p in pr]) for i in range(3))

    def resid(v):
        mz, mv = sum(rz) / len(rz), sum(v) / len(v)
        szz = sum((c - mz) ** 2 for c in rz)
        b = (sum((c - mz) * (w - mv) for c, w in zip(rz, v)) / szz) if szz > 0 else 0.0
        return [w - b * (c - mz) for c, w in zip(rz, v)]
    return _pearson(resid(rx), resid(ry))


def med(v):
    v = sorted(x for x in v if x is not None and math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def exact_signflip(vals):
    """EXACT two-sided p for the MEAN of `vals` under all 2^n sign assignments.

    THE STATISTIC IS THE MEAN, NOT THE MEDIAN, AND THAT IS A DELIBERATE DEPARTURE from the median-based
    `signflip` used elsewhere in this project. A unit test on synthetic input, written before this file
    was registered, showed the median version is DEGENERATE under sign-flipping: for ten subject-level
    correlations all equal to +0.5 -- as unambiguous a positive as the design can produce -- flipping any
    subset leaves |median| unchanged at 0.5, so `|median(flipped)| >= |median(obs)|` holds for every one
    of the 1,024 assignments and the test returns **p = 1.0000**. The degeneracy is worst exactly where
    the effect is cleanest, and it bites hardest at small n where magnitudes cannot spread out. With the
    mean the same input returns p = 2/1024 = 0.00195, the resolution floor, which is correct.

    n = 10 gives 1,024 assignments, so there is no Monte Carlo error and no seed: rules 46 and 85, which
    exist for verdicts that move with the RNG, cannot apply to any p-value in this file. Returns
    (observed_mean, p_two_sided, n_assignments, resolution_floor).
    """
    v = [x for x in vals if x is not None and math.isfinite(x)]
    n = len(v)
    if n < 4:
        return float("nan"), float("nan"), 0, float("nan")
    if n > 20:                       # enumeration would be 10^6+; refuse rather than silently sample
        raise RuntimeError(f"exact enumeration refused at n={n}; this design is registered for n <= 20")
    obs = sum(v) / n
    hits = 0
    total = 1 << n
    for mask in range(total):
        m = sum((-x if (mask >> i) & 1 else x) for i, x in enumerate(v)) / n
        if abs(m) >= abs(obs):
            hits += 1
    return obs, hits / total, total, 2.0 / total


def tost_upper(vals, margin):
    """Upper bound of the 90 % subject-level interval on the median of |rho|, by exact enumeration
    of the same 2^n sign assignments applied to (|rho| - margin). Equivalence PASSES when that upper
    bound lies below `margin`."""
    v = [abs(x) for x in vals if x is not None and math.isfinite(x)]
    n = len(v)
    if n < 4:
        return float("nan"), False
    # percentile bootstrap is not available without an RNG; use the exact distribution-free
    # binomial upper confidence bound on the median, which needs no resampling at all.
    # P(at least k of n above the true median) -> the (n - k + 1)-th order statistic bounds it.
    v.sort()
    k = None
    for i in range(n):
        # one-sided 95 % upper bound on the median: smallest order statistic j with
        # P(Binom(n, 0.5) >= j) <= 0.05
        tail = sum(math.comb(n, t) for t in range(i, n + 1)) / (2 ** n)
        if tail <= 0.05:
            k = i
            break
    upper = v[k - 1] if k is not None and 0 < k <= n else float("nan")
    return upper, bool(math.isfinite(upper) and upper < margin)


# ------------------------------------------------------------------------------ G0 feasibility probe
def probe(data_dir):
    """Report the deposit's actual shape. Never guesses a column; returns what it found."""
    out = {"data_dir": data_dir, "exists": os.path.isdir(data_dir)}
    if not out["exists"]:
        out["error"] = ("deposit not on disk. Fetch it with "
                        "bsde/scripts/physionet_fetch.sh eeg-power-anesthesia 1.0.0 " + data_dir)
        return out
    files = []
    for dp, _, fns in os.walk(data_dir):
        for fn in fns:
            p = os.path.join(dp, fn)
            files.append((os.path.relpath(p, data_dir), os.path.getsize(p)))
    files.sort(key=lambda t: -t[1])
    out["n_files"] = len(files)
    out["total_bytes"] = sum(s for _, s in files)
    out["largest"] = files[:25]
    out["by_ext"] = {}
    for rel, s in files:
        e = os.path.splitext(rel)[1].lower() or "(none)"
        d = out["by_ext"].setdefault(e, {"n": 0, "bytes": 0})
        d["n"] += 1
        d["bytes"] += s
    # column discovery, csv only without pandas; other formats are REPORTED, not parsed blindly
    cands = {}
    for rel, s in files:
        if not rel.lower().endswith((".csv", ".tsv", ".txt")) or s > 400_000_000:
            continue
        try:
            with open(os.path.join(data_dir, rel), errors="replace") as fh:
                head = fh.readline().strip()
        except OSError:
            continue
        sep = "\t" if rel.lower().endswith(".tsv") or "\t" in head else ","
        cols = [c.strip().strip('"') for c in head.split(sep)]
        if len(cols) < 2:
            continue
        resp = [c for c in cols if RESP_PAT.search(c)]
        expo = [c for c in cols if EXPO_PAT.search(c)]
        if resp or expo:
            cands[rel] = {"n_cols": len(cols), "response_like": resp, "exposure_like": expo,
                          "columns": cols[:60]}
    out["column_candidates"] = cands
    resolvable = [k for k, v in cands.items() if v["response_like"] and v["exposure_like"]]
    out["tables_with_both"] = resolvable
    out["G0"] = bool(resolvable)
    out["G0_reason"] = ("found >= 1 table carrying both a response-probability-like and an "
                        "exposure-like column" if resolvable else
                        "NO table carries both a response-probability-like and an exposure-like "
                        "column that this probe can identify without guessing. E345 does not run. "
                        "Report this output and revise the design as a successor (rule 41).")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("EEGPOWER_DIR", DEFAULT_DATA))
    ap.add_argument("--probe", action="store_true", help="run G0 only and stop")
    ap.add_argument("--out", default=os.path.join(RESULTS, "e345_mgh_graded_behaviour.json"))
    a = ap.parse_args(argv)

    print("=" * 96)
    print("E345 -- G0 FEASIBILITY PROBE (rule 41: this runs before any primary and can stop the run)")
    p = probe(a.data)
    if not p.get("exists"):
        print(f"  {p['error']}")
        json.dump({"G0": False, "probe": p}, open(a.out, "w"), indent=1)
        print(f"\nwrote {a.out}")
        print("\nE345 NOT RUN -- the deposit is not on disk. This is a BLOCKED outcome, not a negative.")
        return 0
    print(f"  {p['n_files']} files, {p['total_bytes']/1e6:.1f} MB")
    print("  by extension: " + ", ".join(f"{k} x{v['n']} ({v['bytes']/1e6:.0f} MB)"
                                         for k, v in sorted(p["by_ext"].items(),
                                                            key=lambda t: -t[1]["bytes"])[:8]))
    print("  largest files:")
    for rel, s in p["largest"][:12]:
        print(f"    {s/1e6:>9.1f} MB  {rel}")
    print(f"  tables carrying BOTH a response-like and an exposure-like column: "
          f"{p['tables_with_both'] or 'NONE'}")
    for rel, v in list(p["column_candidates"].items())[:10]:
        print(f"    {rel}: response_like={v['response_like']} exposure_like={v['exposure_like']}")
    print(f"  [G0] -> {'PASS' if p['G0'] else 'FAIL'} -- {p['G0_reason']}")
    if a.probe or not p["G0"]:
        json.dump({"G0": p["G0"], "probe": p}, open(a.out, "w"), indent=1)
        print(f"\nwrote {a.out}")
        if not p["G0"]:
            print("\nE345 NOT RUN. The probe's output above is the deliverable; the design is revised "
                  "as a successor with it in hand, which is rule 41 under an access constraint.")
        return 0

    print("\nG0 passed. The primaries require the per-subject loader, which is written against the "
          "probe's actual output rather than against a guess -- see the note in the registration. "
          "Re-run without --probe once the loader is committed.")
    json.dump({"G0": True, "probe": p}, open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
