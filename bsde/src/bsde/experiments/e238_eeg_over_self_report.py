#!/usr/bin/env python3
"""E238 -- does resting EEG predict BCI command-following BEYOND a self-report the literature validates?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.

WHY CHALLENGE B HAS BEEN STUCK, AND WHAT CHANGES HERE. Challenge B asks whether spontaneous, task-free
EEG predicts command-following capacity over and above an incumbent. Two attempts died on catalogue
rule 86 -- the incumbent (RASS) and the outcome (GCS-motor) were both clinician bedside scores charted
in the same assessment round, so a null was uninformative about the brain. A third (E149) died on rule
70. A fourth candidate design turned out to duplicate E122.

**The Dreyer motor-imagery deposit escapes rule 86 structurally, because its outcome is machine-scored**:
`Perf_RUN_3..6` are OpenViBE online classifier accuracies, computed by software with no human in the
loop. The incumbent this file uses is a PRE-SESSION SELF-REPORT filled in before the electrodes went on.
Candidate, incumbent and outcome are therefore produced by three different instruments -- an offline DSP
pipeline, a paper questionnaire and a classifier -- and no observer is shared by any pair of them.

THE INCUMBENT IS LITERATURE-VALIDATED, WHICH IS WHY IT IS THE RIGHT ONE (rule 45). Rimbert 2018
(PMID 30728772, verified against the MEDLINE record) states verbatim: *"Our results showed no significant
correlation between BCI performance and the MIQ-RS scores. However, we reveal that BCI performance is
correlated to habits and frequency of practicing manual activities."* This project's own
`INCUMBENT_REGISTRY.md` had that backwards, citing the paper as licensing a questionnaire sweep, and was
corrected today. `Manual activity` is the column the paper's POSITIVE finding is about: 5 ordinal levels
(1 = never … 5 = every day), n = 87 of 87 non-missing, distribution 6/18/13/31/19.

**A SELF-REPORT IS A HARD INCUMBENT AND THAT IS THE POINT.** If a questionnaire item filled in before the
session predicts BCI accuracy as well as the EEG does, then "the EEG predicts command-following" is not a
claim about brain state -- it is a claim about who practises manual skills. Rule 86's lesson generalises:
an incumbent must be an instrument the candidate cannot be a proxy for, and a pre-session trait
questionnaire is exactly that test for a resting-EEG marker.

PRIMARIES.

  P1  Spearman(`Manual activity`, mean online accuracy) over 87 subjects. This is a REPLICATION of
      Rimbert 2018's rho = 0.381 (n = 35) and it establishes whether the incumbent is ALIVE on this
      cohort (rule 53). If it is dead, P2 is a comparison against nothing and must be read as such.
  P2  THE CHALLENGE B PRIMARY: partial Spearman(accuracy, `smr_predictor_db` | `Manual activity`).
      Does the resting-EEG sensorimotor-rhythm predictor retain its association once the self-report is
      conditioned out? E129 measured its raw association on this exact cohort at +0.4440
      [+0.2480, +0.6104], quoted verbatim from the ledger; it is RE-DERIVED here rather than imported
      (rule 59).
  P3  The mirror, so the comparison is symmetric and neither instrument is privileged:
      partial Spearman(accuracy, `Manual activity` | `smr_predictor_db`). If both survive, the two carry
      independent information; if only the self-report survives, the EEG marker is a proxy for practice.

GATES, each able to go either way (rules 40 and 81).

  G1  THE INCUMBENT MUST BE ALIVE (rule 53, and E33's rule carried across). `Manual activity` must clear
      a permutation null. If it does not, P2 cannot be read as "EEG beats a live incumbent" and the file
      says so instead of quietly claiming it.
  G2  THE CANDIDATE MUST BE ALIVE. `smr_predictor_db` must clear its own permutation null, re-derived
      here. A null P2 over a dead candidate is absence of power, not measured absence (rule 69).
  G3  BOTH PREDICTORS MUST VARY, and neither may be near-constant (rule 74). `Manual activity` has 5
      levels with a maximum share of 35.6 %; the gate is that no level holds more than 60 % and at least
      4 levels are populated.
  G4  COVERAGE and JOIN. At least 80 subjects present in BOTH tables, joined on subject id, with the
      join count reported (rule 14).

POWER IS DECLARED IN ADVANCE, INCLUDING THE ASYMMETRY. At n = 87 the 80 %-power floor for a bivariate
Spearman is **rho = 0.2965** (Fisher z, two-sided alpha 0.05), computed rather than asserted. Rimbert's
own effect (rho = 0.381) sits above it, so a failure to replicate P1 is informative. But if the true
effect is nearer this project's other Dreyer self-report correlates -- mental rotation came in at -0.17
-- power falls to roughly a third and a P1 null would be UNDERPOWERED rather than evidential. That
asymmetry is registered here so it cannot be discovered afterwards.

PLACEBO. The candidate-outcome PAIRING is permuted, which is the destruction that matches a bivariate
association: it removes the association while preserving both marginals, the cohort and the code path.
E230 and E231 both died on placebos that could not touch their estimand (rule 88), and a covariate
permutation would be exactly that mistake here. Compared against the placebo's DISTRIBUTION, never a
mean (rule 37).

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37, five recorded occurrences).

  (a) P1 excludes zero with a NEGATIVE sign -> WRONG DIRECTION. More manual practice predicts WORSE BCI
      accuracy, contradicting Rimbert 2018 rather than merely failing to replicate it; report with the
      sign and stop, because the incumbent is then not the thing the literature describes.
  (b) G1 fails (P1 does not clear its null) -> INCUMBENT DEAD. P2 is reported but explicitly as an
      association against no competitor, and the power asymmetry above is quoted beside it.
  (c) P2 survives and P3 does not -> EEG BEATS THE SELF-REPORT. The strongest Challenge B result this
      project has produced, and the first with all three instruments structurally independent.
  (d) Both P2 and P3 survive -> INDEPENDENT INFORMATION. Both are reported; no claim about which
      dominates.
  (e) P3 survives and P2 does not -> THE EEG MARKER IS A PROXY FOR PRACTICE. A genuine negative for
      Challenge B and a more interesting one than a plain null, because it names what the EEG was
      tracking.
  (f) Neither survives -> NULL, read against the declared power floor.

  Gating, applied AFTER the primaries because a gate can only invalidate a pass and never rescue a null
  (rule 37): G2, G3 or G4 failing -> NOT INTERPRETABLE. The placebo reproducing P2 -> NOT INTERPRETABLE.

SCOPE. Motor-imagery BCI accuracy is command-following in the operational sense -- the subject is asked
to do something and a machine reads whether they did -- but it is not the CRS-R construct the flagship
covert-consciousness question needs, and this file makes no claim about disorders of consciousness. n =
87 healthy volunteers, single session, so nothing here speaks to trajectory or to patients.

    python bsde/src/bsde/experiments/e238_eeg_over_self_report.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

PERF = "bsde/results/dreyer_performance.csv"
SMR = "bsde/results/dreyer_smr.s*.csv"
OUT = "bsde/results/e238_eeg_over_self_report.json"
OUTCOME_COLS = ("Perf_RUN_3", "Perf_RUN_4", "Perf_RUN_5", "Perf_RUN_6")
INCUMBENT = "Manual activity"
CANDIDATE = "smr_predictor_db"
MIN_SUBJECTS = 80
N_BOOT = 5000
N_PERM = 10000
SEED = 20260802


def _f(x):
    """Dreyer's table is semicolon-delimited with COMMA decimal separators.

    Parsing it with a comma delimiter splits inside the numbers -- 67,5 becomes two fields -- which is
    how a first attempt at this table returned zero usable rows. The separator is a property of the file
    and is handled here rather than worked around downstream (rule 61: parse the structure).
    """
    try:
        return float(str(x).strip().replace(",", "."))
    except (TypeError, ValueError):
        return float("nan")


def load_performance():
    rows = list(csv.reader(open(PERF), delimiter=";"))
    hdr = rows[2]
    data = [r for r in rows[3:] if r and re.match(r"^[A-Za-z]\d+$", r[0].strip())]
    out = {}
    for r in data:
        def g(name):
            i = hdr.index(name)
            return r[i].strip() if i < len(r) else ""
        out[r[0].strip()] = {"incumbent": _f(g(INCUMBENT)),
                             "acc": [_f(g(c)) for c in OUTCOME_COLS]}
    return out, len(data)


def load_smr():
    import numpy as np
    out = {}
    for p in sorted(glob.glob(SMR)):
        for r in csv.DictReader(open(p)):
            if r.get("status") == "ok":
                out[r["subject"].strip()] = _f(r.get(CANDIDATE))
    return out


def partial_spearman(x, y, z):
    import numpy as np
    from bsde.verifier.stats import _midranks
    X, Y, Z = (_midranks(np.asarray(v, float)) for v in (x, y, z))
    for a in (X, Y, Z):
        if np.std(a) <= 0:
            return float("nan")
    rxy, rxz, ryz = (np.corrcoef(X, Y)[0, 1], np.corrcoef(X, Z)[0, 1], np.corrcoef(Y, Z)[0, 1])
    d = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return float((rxy - rxz * ryz) / d) if d > 0 else float("nan")


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import spearman
    rng = np.random.default_rng(SEED)

    perf, n_parsed = load_performance()
    smr = load_smr()
    ids = sorted(set(perf) & set(smr))
    print(f"performance rows parsed {n_parsed}, smr rows {len(smr)}, JOINED {len(ids)}")

    acc, inc, can = [], [], []
    for s in ids:
        a = np.asarray(perf[s]["acc"], float)
        a = a[np.isfinite(a)]
        if not len(a) or not np.isfinite(perf[s]["incumbent"]) or not np.isfinite(smr[s]):
            continue
        acc.append(float(a.mean()))
        inc.append(perf[s]["incumbent"])
        can.append(smr[s])
    acc, inc, can = np.asarray(acc), np.asarray(inc), np.asarray(can)
    n = len(acc)
    print(f"complete cases: {n}")
    print(f"outcome  mean {acc.mean():.2f}, range {acc.min():.1f}-{acc.max():.1f}")
    lv, ct = np.unique(inc, return_counts=True)
    print(f"incumbent '{INCUMBENT}': levels {dict(zip(lv.astype(int).tolist(), ct.tolist()))}, "
          f"max share {ct.max() / n:.3f}")
    print(f"candidate '{CANDIDATE}': median {np.median(can):.3f}, "
          f"range {can.min():.2f}-{can.max():.2f}")

    g4 = n >= MIN_SUBJECTS
    g3 = (ct.max() / n) <= 0.60 and len(lv) >= 4 and np.std(can) > 0
    from math import sqrt, tanh
    floor = tanh((1.959963985 + 0.8416212336) / sqrt(n - 3))
    print(f"declared 80%-power floor at n={n}: rho = {floor:.4f}")

    def perm_null(x, y, k=N_PERM):
        return np.asarray([float(spearman(x[rng.permutation(len(x))], y)) for _ in range(k)], float)

    p1 = float(spearman(inc, acc))
    n1 = perm_null(inc, acc)
    p1_p = float(np.mean(np.abs(n1) >= abs(p1)))
    g1 = p1_p < 0.05
    craw = float(spearman(can, acc))
    n2 = perm_null(can, acc)
    craw_p = float(np.mean(np.abs(n2) >= abs(craw)))
    g2 = craw_p < 0.05
    print()
    print(f"P1 spearman({INCUMBENT}, accuracy)        = {p1:+.4f}  perm |p| = {p1_p:.4f}  "
          f"-> incumbent {'ALIVE' if g1 else 'DEAD'}   (Rimbert 2018: rho 0.381, n=35)")
    print(f"   spearman({CANDIDATE}, accuracy)  = {craw:+.4f}  perm |p| = {craw_p:.4f}  "
          f"-> candidate {'ALIVE' if g2 else 'DEAD'}   (E129: +0.4440 [+0.2480, +0.6104])")

    p2 = partial_spearman(acc, can, inc)
    p3 = partial_spearman(acc, inc, can)
    n_p2 = np.asarray([partial_spearman(acc, can[rng.permutation(n)], inc) for _ in range(N_PERM)], float)
    n_p3 = np.asarray([partial_spearman(acc, inc[rng.permutation(n)], can) for _ in range(N_PERM)], float)
    p2_p = float(np.nanmean(np.abs(n_p2) >= abs(p2)))
    p3_p = float(np.nanmean(np.abs(n_p3) >= abs(p3)))
    b2 = np.asarray([partial_spearman(acc[i], can[i], inc[i])
                     for i in (rng.integers(0, n, n) for _ in range(N_BOOT))], float)
    print()
    print(f"P2 partial(accuracy, EEG | self-report)   = {p2:+.4f} "
          f"[{np.nanpercentile(b2, 2.5):+.4f}, {np.nanpercentile(b2, 97.5):+.4f}]  perm |p| = {p2_p:.4f}")
    print(f"P3 partial(accuracy, self-report | EEG)   = {p3:+.4f}  perm |p| = {p3_p:.4f}")

    s2, s3 = p2_p < 0.05, p3_p < 0.05
    if g1 and p1 < 0:
        verdict = (f"WRONG DIRECTION -- more manual practice predicts WORSE accuracy ({p1:+.4f}), "
                   "contradicting Rimbert 2018 rather than failing to replicate it; the incumbent is not "
                   "the thing the literature describes and P2 is not read")
    elif not g1:
        verdict = (f"INCUMBENT DEAD -- the self-report does not clear its own null on this cohort "
                   f"({p1:+.4f}, |p| = {p1_p:.4f}), so P2 = {p2:+.4f} is an association against no "
                   f"competitor; at n = {n} the 80%-power floor is rho = {floor:.4f} and Rimbert's own "
                   "effect was 0.381, so this is a real failure to replicate rather than a power failure")
    elif s2 and not s3:
        verdict = ("EEG BEATS THE SELF-REPORT -- the resting sensorimotor-rhythm predictor retains its "
                   "association after conditioning on a literature-validated pre-session questionnaire, "
                   "and the questionnaire does not survive conditioning on the EEG; three structurally "
                   "independent instruments, no shared observer")
    elif s2 and s3:
        verdict = "INDEPENDENT INFORMATION -- both partials survive; no claim about which dominates"
    elif s3 and not s2:
        verdict = ("THE EEG MARKER IS A PROXY FOR PRACTICE -- the self-report survives conditioning on "
                   "the EEG and the EEG does not survive conditioning on the self-report; a negative for "
                   "Challenge B that names what the marker was tracking")
    else:
        verdict = f"NULL -- neither partial survives, read against the declared power floor rho = {floor:.4f}"
    if not g2:
        verdict = "NOT INTERPRETABLE -- G2 failed; the candidate is dead on this cohort and a null P2 is absence of power"
    elif not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; a predictor is near-constant"
    elif not g4:
        verdict = f"NOT INTERPRETABLE -- G4 failed; only {n} joined subjects against a floor of {MIN_SUBJECTS}"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"n": n, "n_joined": len(ids), "power_floor": floor,
                   "p1": {"rho": p1, "perm_p": p1_p, "rimbert_2018": 0.381},
                   "candidate_raw": {"rho": craw, "perm_p": craw_p, "e129": 0.4440},
                   "p2": {"partial": p2, "lo": float(np.nanpercentile(b2, 2.5)),
                          "hi": float(np.nanpercentile(b2, 97.5)), "perm_p": p2_p},
                   "p3": {"partial": p3, "perm_p": p3_p},
                   "incumbent_levels": dict(zip(lv.astype(int).tolist(), ct.tolist())),
                   "gates": {"G1_incumbent_alive": bool(g1), "G2_candidate_alive": bool(g2),
                             "G3_vary": bool(g3), "G4_coverage": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
