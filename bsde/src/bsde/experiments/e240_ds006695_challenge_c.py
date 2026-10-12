#!/usr/bin/env python3
"""E240 -- Challenge C on ds006695, the one deposit whose columns have never met its label.

PRE-REGISTRATION. Written and committed before the numbers below this line exist, and before any
statistic involving the `stage` column has been computed on this deposit by anyone.

WHY THIS DEPOSIT AND WHY IT MATTERS THAT IT IS CLEAN. Every other deposit in this project has been swept:
its candidate columns have been correlated against its labels, often repeatedly, in the course of finding
the effects that are now being replicated. ds006695 has not. It was located, its hypnograms pulled by HTTP
byte range, its epochs extracted and its panel computed WITHOUT any statistic touching the stage column --
the design document `DESIGN_2026_08_02_DS006695_CHALLENGE_C.md` states which inspections were made and
which were refused. That makes this the only genuinely confirmatory test available, and a single
exploratory correlation would spend it.

THE CLAIM BEING REPLICATED. E222 found, on Sleep-EDFx, that two measures add to a spectral-edge incumbent
in discriminating sleep depth after muscle adjustment: `whole_head_exponent` +0.0542 [+0.030, +0.082] and
`multiscale_entropy_slope` +0.0280 [+0.011, +0.049].

COHORT. 19 subjects, 12 epochs per stage per subject, stages W/N1/N2/N3/REM, 3 frontal derivations
(FP1-AFz, FP2-AFz, FF) at 500 Hz. The primary ladder is W=0, N1=1, N2=2, N3=3 with REM EXCLUDED -- REM is
not a depth on this ladder and E222 treats it the same way -- giving 19 x 4 x 12 = 912 rows.

PRIMARY. Out-of-fold Spearman between a ridge prediction and the ladder, incremented by each candidate over
the incumbent, computed by `increment()` IMPORTED FROM E222 rather than reimplemented (rule 20), with
SUBJECTS held out whole. The effective n is 19 subjects, not 912 epochs -- rule 69 records that a row-level
null once inflated significance here by 178x.

  base = [spectral_edge_95]                      -> the "plain" increment
  base = [spectral_edge_95, emg_index]           -> the MUSCLE-ADJUSTED increment, on which the verdict rests

FOLDS = 19 (leave-one-subject-out), a registered deviation from E222's default 5, because with 19 subjects
LOSO maximises training data per held-out subject and every fold still exceeds `grouped_cv_predict`'s
`X.shape[1] + 2` requirement by three orders of magnitude. The bound is derived from the machinery, not
chosen (rule 63).

WHAT `emg_index` CAN AND CANNOT SUPPORT, stated here because it must be repeated wherever the number is
quoted (rule 3). ds006695 has NO true EMG channel -- three EEG derivations, not a PSG montage with chin
EMG. E69 showed `emg_index` fails to detect REM atonia and E71 measured it against a real submental
channel at rho = 0.20 pooled. Surviving adjustment with it supports "not driven by the muscle
contamination this weak proxy can see" and NOTHING stronger. It cannot support "cortical".

CANDIDATES. Only measures this montage can carry. `icoh_alpha` and `wpli_alpha` need 8 channels,
`spatial_participation_ratio` needs 4, `uce_v1` needs a posterior region this forehead montage does not
have, and `lrtc_alpha` needs a DFA scale range a 30 s epoch cannot supply -- all five are structurally
unavailable and are excluded by declaration, not by a filter that might silently pass (rule 74). The panel
is E222's four: `multiscale_entropy_slope`, `whole_head_exponent`, `relative_alpha_power`,
`pac_slow_alpha`.

GATES, each able to go either way (rules 40 and 81).

  G1  COVERAGE. All 19 subjects present with all 4 ladder stages and 12 epochs each; the feature table must
      have reached its full 1140 rows. A partial table would make the result a statement about which
      subjects finished extracting first.
  G2  THE INCUMBENT MUST BE ALIVE ON THIS COHORT (rule 53), re-derived here and not inherited from E222.
      `spectral_edge_95` alone must reach an out-of-fold |Spearman| against the ladder that clears a
      subject-level label-permutation null. A null increment over a dead incumbent is uninformative.
  G3  THE NOISE CONTROL MUST NOT ADD. A Gaussian column drawn independently of everything must give an
      increment whose interval includes zero. This is the input that SHOULD fail an "adds" verdict, and if
      it passes, the increment estimator is broken and nothing else is readable.
  G4  CANDIDATES MUST VARY. Any all-NaN or constant column is EXCLUDED and REPORTED with the reason and
      the count (rule 74), never scored -- `verifier.stats.screen_candidates` exists for exactly this.

PLACEBO. A WITHIN-SUBJECT label permutation: each subject's 48 ladder labels are shuffled among that
subject's own epochs, preserving every subject's stage composition, the panel, the folds and the code path,
and destroying only the epoch-to-stage correspondence. That is the destruction matching this estimand
(rule 55); a covariate permutation could not touch it, which is the mistake rule 88 records from E230 and
E231. Compared against the placebo's DISTRIBUTION over draws, never its mean (rule 37).

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37, five recorded occurrences).

  (a) A candidate's muscle-adjusted increment interval lies entirely BELOW zero -> WRONG DIRECTION for that
      candidate: it makes the incumbent WORSE out of fold, which refutes rather than fails to support, and
      is reported with the sign.
  (b) No candidate's interval excludes zero above -> ABSENT. E222's result does not replicate on this
      montage. Reported with the power caveat below, because absence at n = 19 against a strong incumbent
      is weak evidence of absence.
  (c) A candidate's interval excludes zero above AND exceeds the placebo distribution's 95th percentile ->
      REPLICATES, and it is named. This is a third deposit and the first clean one.
  (d) An interval excludes zero above but does NOT beat the placebo -> PLACEBO-INDISTINGUISHABLE, a branch
      kept separate from ABSENT because the two mean different things and only one of them is about the
      brain.

  Gating applied AFTER the primary because a gate can only invalidate a pass and never rescue a null
  (rule 37): G1, G2, G3 or G4 failing -> NOT INTERPRETABLE.

POWER IS DECLARED IN ADVANCE AND IT IS POOR. n = 19 subjects. E223 already established that a strong
incumbent squeezes increments toward zero, and this deposit's 3 forehead derivations make
`whole_head_exponent` a different measurement from the one E222 computed on a full montage -- the project's
own `PROBE_2026_08_02_DEPOSITS.md` says so. **Neither a positive nor a null here should be read as a clean
third replication**, and the write-up must carry that sentence wherever the number goes.

INCUMBENT (rule 45): `spectral_edge_95`, re-derived on this cohort.

    python bsde/src/bsde/experiments/e240_ds006695_challenge_c.py
"""
from __future__ import annotations

import collections
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

FEATURES = "bsde/results/ds006695_features.csv"
OUT = "bsde/results/e240_ds006695_challenge_c.json"
INCUMBENT = "spectral_edge_95"
MUSCLE = "emg_index"
CANDIDATES = ("multiscale_entropy_slope", "whole_head_exponent", "relative_alpha_power", "pac_slow_alpha")
LADDER = {"W": 0, "N1": 1, "N2": 2, "N3": 3}
EXPECTED_ROWS = 1140
N_BOOT = 2000
N_PLACEBO = 300
SEED = 20260802


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import read_rows, spearman, screen_candidates
    from bsde.experiments.e222_sleep_edfx_replication import increment
    rng = np.random.default_rng(SEED)

    rows, dropped = read_rows(FEATURES)
    print(f"feature table: {len(rows)} rows ({dropped} shard-header rows dropped), "
          f"expected {EXPECTED_ROWS}")
    g1_full = len(rows) >= EXPECTED_ROWS
    lad = [r for r in rows if r.get("stage") in LADDER]
    subs = sorted({r["subject"] for r in lad})
    cells = collections.Counter((r["subject"], r["stage"]) for r in lad)
    complete = [s for s in subs if all(cells.get((s, st), 0) == 12 for st in LADDER)]
    print(f"ladder rows {len(lad)}; subjects {len(subs)}; with all 4 stages x 12 epochs: {len(complete)}")
    g1 = g1_full and len(complete) == 19
    print(f"G1 coverage (full table and 19 complete subjects): {'PASS' if g1 else 'FAIL'}")

    use = [r for r in lad if r["subject"] in complete]
    assert use, "no complete subjects"
    y = np.asarray([LADDER[r["stage"]] for r in use], float)
    sub = [r["subject"] for r in use]

    cols = [INCUMBENT, MUSCLE] + list(CANDIDATES)
    raw = {c: [_f(r.get(c)) for r in use] for c in cols}
    kept, excluded = screen_candidates(raw)
    print(f"G4 screening: kept {sorted(kept)}; EXCLUDED {excluded}")
    g4 = INCUMBENT in kept and MUSCLE in kept and any(c in kept for c in CANDIDATES)
    cands = [c for c in CANDIDATES if c in kept]

    noise = rng.normal(size=len(y))
    names = [INCUMBENT, MUSCLE] + cands + ["__noise__"]
    X = np.column_stack([np.asarray(raw[c], float) if c != "__noise__" else noise for c in names])
    for j in range(X.shape[1]):
        col = X[:, j]
        m = np.isfinite(col)
        col[~m] = np.nanmedian(col[m]) if m.any() else 0.0
    idx = {n: i for i, n in enumerate(names)}
    folds = len(complete)
    print(f"rows used {len(y)}; folds = {folds} (leave-one-subject-out)")

    # ---- G2 incumbent aliveness ---------------------------------------------------------------------
    from bsde.verifier.stats import grouped_cv_predict
    base_pred = grouped_cv_predict(X[:, [idx[INCUMBENT]]], y, sub, np.random.default_rng(SEED), folds=folds)
    a = float(spearman(list(base_pred), list(y)))
    null = []
    for _ in range(N_PLACEBO):
        yp = y.copy()
        for s in complete:
            m = np.asarray([x == s for x in sub])
            yp[m] = rng.permutation(yp[m])
        p = grouped_cv_predict(X[:, [idx[INCUMBENT]]], yp, sub, np.random.default_rng(SEED), folds=folds)
        null.append(abs(float(spearman(list(p), list(yp)))))
    null = np.asarray(null, float)
    g2 = abs(a) > float(np.percentile(null, 95))
    headroom = 1.0 - abs(a)
    print(f"G2 incumbent alive: out-of-fold |rho| {abs(a):.4f} against a within-subject permutation "
          f"95th percentile of {np.percentile(null, 95):.4f} -> {'PASS' if g2 else 'FAIL'}; "
          f"headroom {headroom:.4f}")

    # ---- primary ------------------------------------------------------------------------------------
    def boot(base, add):
        vals = []
        for _ in range(N_BOOT):
            take = rng.choice(complete, len(complete), replace=True)
            sel = np.concatenate([np.flatnonzero([x == s for x in sub]) for s in take])
            sb = [f"{s}#{i}" for i, s in enumerate(take) for _ in range(int(np.sum([x == s for x in sub])))]
            try:
                vals.append(increment(X[sel], y[sel], sb, base, add, SEED))
            except Exception:
                continue
        v = np.asarray([x for x in vals if np.isfinite(x)], float)
        return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if len(v) > 50 else (np.nan, np.nan)

    res = {}
    print()
    print(f"{'candidate':28s}{'plain':>10}{'adjusted':>11}{'CI (adjusted)':>26}{'% headroom':>12}")
    for c in cands + ["__noise__"]:
        pl = increment(X, y, sub, [idx[INCUMBENT]], [idx[c]], SEED)
        ad = increment(X, y, sub, [idx[INCUMBENT], idx[MUSCLE]], [idx[c]], SEED)
        lo, hi = boot([idx[INCUMBENT], idx[MUSCLE]], [idx[c]])
        res[c] = {"plain": pl, "adjusted": ad, "lo": lo, "hi": hi,
                  "pct_headroom": 100.0 * ad / headroom if headroom > 0 else float("nan")}
        print(f"{c:28s}{pl:+10.4f}{ad:+11.4f}   [{lo:+.4f}, {hi:+.4f}]{res[c]['pct_headroom']:12.1f}")

    g3 = not (np.isfinite(res["__noise__"]["lo"]) and res["__noise__"]["lo"] > 0)
    print(f"G3 noise control does not add: {'PASS' if g3 else 'FAIL'}")

    # ---- placebo: within-subject label permutation ----------------------------------------------------
    plac = {c: [] for c in cands}
    for _ in range(N_PLACEBO):
        yp = y.copy()
        for s in complete:
            m = np.asarray([x == s for x in sub])
            yp[m] = rng.permutation(yp[m])
        for c in cands:
            try:
                plac[c].append(increment(X, yp, sub, [idx[INCUMBENT], idx[MUSCLE]], [idx[c]], SEED))
            except Exception:
                continue
    pl95 = {c: float(np.nanpercentile(plac[c], 95)) if plac[c] else float("nan") for c in cands}
    print()
    for c in cands:
        print(f"placebo {c:28s} 95th pct {pl95[c]:+.4f}  against observed {res[c]['adjusted']:+.4f}")

    wrong = [c for c in cands if np.isfinite(res[c]["hi"]) and res[c]["hi"] < 0]
    adds = [c for c in cands if np.isfinite(res[c]["lo"]) and res[c]["lo"] > 0]
    beats = [c for c in adds if np.isfinite(pl95[c]) and res[c]["adjusted"] > pl95[c]]
    if wrong:
        verdict = (f"WRONG DIRECTION for {', '.join(wrong)} -- the muscle-adjusted increment interval lies "
                   "entirely below zero, so adding the candidate makes the incumbent WORSE out of fold; "
                   "that refutes rather than fails to support")
    elif not adds:
        verdict = ("ABSENT -- no candidate's muscle-adjusted interval excludes zero above. At n = 19 "
                   "subjects against a strong incumbent this is weak evidence of absence and must not be "
                   "read as a clean failure to replicate")
    elif beats:
        verdict = (f"REPLICATES on a clean deposit: {', '.join(beats)} add over the incumbent after muscle "
                   "adjustment and beat the within-subject permutation placebo")
    else:
        verdict = (f"PLACEBO-INDISTINGUISHABLE -- {', '.join(adds)} exclude zero but do not beat the "
                   "permutation placebo; kept separate from ABSENT because only one of the two is about "
                   "the brain")
    if not g1:
        verdict = "NOT INTERPRETABLE -- G1 coverage failed; the feature table is incomplete"
    elif not g2:
        verdict = "NOT INTERPRETABLE -- G2 failed; the incumbent is not alive on this cohort"
    elif not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; the noise control adds, so the increment estimator is broken"
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 failed; too few usable candidates"
    print()
    print("VERDICT:", verdict)
    print("POWER CAVEAT (registered): n = 19 subjects, 3 forehead derivations, and a strong incumbent. "
          "Neither a positive nor a null here is a clean third replication.")

    with open(OUT, "w") as fh:
        json.dump({"n_rows": len(y), "n_subjects": len(complete), "folds": folds,
                   "incumbent_rho": a, "headroom": headroom,
                   "incumbent_null_p95": float(np.percentile(null, 95)),
                   "increments": res, "placebo_p95": pl95, "excluded": excluded,
                   "gates": {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
