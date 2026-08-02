#!/usr/bin/env python3
"""E222 — do Challenge C's survivors replicate on sleep_edfx, where MUSCLE TRACKS THE LABEL?

REGISTERED AFTER A RULE-41 PROBE AND BEFORE ANY CANDIDATE TOUCHED THE LABEL. The probe correlated only the
declared incumbent and the artefact channel; `bsde/docs/PROBE_2026_08_02_SLEEP_EDFX_C.md` records it.

=========================================================================================================
WHY THIS DEPOSIT, AND WHY IT IS NOT CLEAN
=========================================================================================================
Challenge C has lost three cohorts to dead incumbents — chennu twice, on two different estimands, and
ds004541 refused before anything was spent — and found capslpdb's candidates REDUNDANT with an incumbent
rather than absent. `sleep_edfx` has never been used for Challenge C. It has been this programme's
Challenge D evaluation ladder (E198, E211), a different question and estimand, and its candidate columns
have never been correlated with a Challenge C label.

    incumbent `spectral_edge_95` vs the ordered ladder:  rho = **-0.8461**
    within-subject permutation null, 95th percentile:           **0.0890**

Alive by a factor of 9.5 — the strongest incumbent this programme has measured on any deposit. All 142
subjects carry all four ordered stages, and **`multiscale_entropy_slope` is present**, which capslpdb's
extraction had to omit for cost, so this deposit can test the one survivor capslpdb could not.

**AND MUSCLE TONE TRACKS THE LABEL ALMOST AS WELL AS THE INCUMBENT DOES:**

    `emg_index` vs the ordered ladder:  rho = **-0.6542**, same direction.

That is physiologically unsurprising — muscle tone falls with sleep depth, which is why submental EMG is
part of standard sleep scoring — and it is exactly why a caveat would not do. Rule 54: a confound named in
a registration is not thereby controlled; point at the line of code. There are two, below.

    **P1  Do the survivors add to the incumbent — AND do they still add once muscle is in the baseline?**

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE: all four ordered stages per subject, >= 100 subjects, every tested candidate finite. `uce_v1`
    is 0 % finite in this table and is named here rather than allowed to reach a p-value (rules 6, 74).
G2  THE INCUMBENT MUST BE ALIVE, recomputed here rather than taken from the probe (rule 53).
G3  NEGATIVE CONTROL: an i.i.d. noise column must not add.
G4  **THE MUSCLE GATE, PART ONE — CODE, NOT CAVEAT.** Every increment is computed TWICE: over a baseline of
    `[incumbent]` and over `[incumbent, emg_index]`. A candidate that adds to the first and not the second
    was carrying muscle, and is reported as MUSCLE-DEPENDENT rather than as a replication. The muscle-
    adjusted increment is the one that decides the verdict.
G5  **THE MUSCLE GATE, PART TWO — REM AS A PLACEBO, WHICH IS WHY REM IS NOT DISCARDED.** REM has the lowest
    muscle tone of any stage and sits in the MIDDLE of the depth ordering. Those two facts dissociate, and
    nothing else in this deposit dissociates them. So for every column the median REM value is located
    against that column's own W-to-N3 ladder, giving a "REM rung" in ladder units. A muscle-driven column
    places REM near the DEEP end, where `emg_index` places it; a cortical one need not. Each candidate's
    REM rung is reported beside `emg_index`'s and the incumbent's, and a candidate landing within
    `REM_TOL` of the EMG channel's rung is flagged.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails.
  (2) REVERSED            a candidate's muscle-adjusted interval excludes zero on the NEGATIVE side. Not
                          support in any form.
  (3) MUSCLE-DEPENDENT    a candidate adds over the incumbent alone but NOT once `emg_index` is in the
                          baseline. Reported as its own outcome, never as a weak replication.
  (4) ABSENT              no candidate's muscle-adjusted interval excludes zero on the positive side.
  (5) REPLICATES          at least one candidate adds with muscle already in the baseline.

**REGISTERED PREDICTION: (3) or (4), and I expect at least one MUSCLE-DEPENDENT.** With `emg_index`
tracking the label at -0.65 and the deposit carrying two channels at 100 Hz, there is no spatial handle to
separate cortex from muscle, and `lempel_ziv` and the high-frequency exponent are the measures most exposed.
**(5) for `whole_head_exponent` would be the most valuable outcome**, because it replicated on ds005620,
was redundant on capslpdb, and a muscle-adjusted positive here would be the first clean cross-deposit
survival it has had.

**SCOPE.** `wpli_theta` is absent from this panel as it is from every other. The label is a sleep ladder,
not sedation, so this replicates the CANDIDATES rather than the exact DOSE-I estimand — the same caveat
E209 and E219 carry. And `emg_index` is a WEAK proxy: E69 showed it fails to detect REM atonia, so
adjusting for it is a partial control and a candidate surviving G4 is not thereby proven cortical.

    python bsde/src/bsde/experiments/e222_sleep_edfx_replication.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import spearman, read_rows, grouped_cv_predict        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e222_sleep_edfx_replication.json")
TABLE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")

SEED = 20260802
LADDER = {"W": 0, "N1": 1, "N2": 2, "N3": 3}
INCUMBENT = "spectral_edge_95"
ARTEFACT = "emg_index"
CANDIDATES = ("multiscale_entropy_slope", "whole_head_exponent", "relative_alpha_power", "pac_slow_alpha")
MIN_SUBJECTS = 100
N_BOOT = 1500
N_PERM = 2000
REM_TOL = 0.35


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def load():
    rows, dropped = read_rows(TABLE)
    rows = [r for r in rows if r.get("status", "ok") == "ok" and "@" in r.get("recording_id", "")]
    ladder, rem = [], []
    for r in rows:
        st = r["recording_id"].rsplit("@", 1)[1]
        (ladder if st in LADDER else (rem if st == "REM" else [])).append((r, st))
    return ladder, rem, dropped


def increment(X, y, sub, base, add, seed):
    r0 = np.random.default_rng(seed)
    a = spearman(list(grouped_cv_predict(X[:, base], y, sub, r0)), list(y))
    r1 = np.random.default_rng(seed)
    b = spearman(list(grouped_cv_predict(X[:, base + add], y, sub, r1)), list(y))
    return b - a


def main() -> int:
    print("E222 — do Challenge C's survivors replicate where MUSCLE TRACKS THE LABEL?")
    ladder, rem, dropped = load()
    subs = sorted({r["subject"] for r, _ in ladder})
    cols = [INCUMBENT, ARTEFACT, *CANDIDATES]
    X = np.array([[_f(r.get(c, "")) for c in cols] for r, _ in ladder], float)
    y = np.array([float(LADDER[s]) for _, s in ladder])
    sub = np.array([r["subject"] for r, _ in ladder])
    print(f"   {len(ladder)} ordered-ladder points over {len(subs)} subjects; {len(rem)} REM points; "
          f"{dropped} header-artefact rows dropped")
    g1 = bool(len(subs) >= MIN_SUBJECTS and np.isfinite(X).all())
    print(f"G1 COVERAGE >= {MIN_SUBJECTS} subjects, all candidates finite   {'PASS' if g1 else '*** FAIL'}")

    rng = np.random.default_rng(SEED)
    rho = spearman(list(X[:, 0]), list(y))
    nul = []
    for _ in range(N_PERM):
        p = y.copy()
        for s in subs:
            m = sub == s
            p[m] = rng.permutation(p[m])
        nul.append(abs(spearman(list(X[:, 0]), list(p))))
    p95 = float(np.quantile(nul, 0.95))
    g2 = bool(abs(rho) > p95)
    print(f"G2 INCUMBENT ALIVE  rho {rho:+.4f} vs within-subject permutation p95 {p95:.4f}   "
          f"{'PASS' if g2 else '*** FAIL'}")
    print(f"   ARTEFACT for reference: rho({ARTEFACT}, stage) = "
          f"{spearman(list(X[:, 1]), list(y)):+.4f}")

    Xn = np.column_stack([X, rng.normal(size=len(y))])
    noise_i = Xn.shape[1] - 1
    res = {}
    print(f"\n   {'candidate':<26s} {'over incumbent':>16s} {'+ muscle in baseline':>22s}  call")
    for k, name in enumerate([*CANDIDATES, "NOISE_CONTROL"]):
        add = [noise_i] if name == "NOISE_CONTROL" else [2 + k]
        out = {}
        for tag, base in (("plain", [0]), ("muscle_adjusted", [0, 1])):
            d = increment(Xn, y, sub, base, add, SEED + 1)
            boot = []
            for b in range(N_BOOT):
                g = np.random.default_rng(SEED + 500 + b)
                pick = np.concatenate([np.flatnonzero(sub == s)
                                       for s in g.choice(subs, size=len(subs), replace=True)])
                try:
                    boot.append(increment(Xn[pick], y[pick], sub[pick], base, add, SEED + 1))
                except Exception:
                    pass
            boot = np.array([x for x in boot if np.isfinite(x)])
            out[tag] = {"increment": d, "ci": [float(np.quantile(boot, 0.025)),
                                               float(np.quantile(boot, 0.975))]}
        pl, ma = out["plain"], out["muscle_adjusted"]
        if ma["ci"][1] < 0:
            call = "REVERSED"
        elif ma["ci"][0] > 0:
            call = "REPLICATES"
        elif pl["ci"][0] > 0:
            call = "MUSCLE-DEPENDENT"
        else:
            call = "absent"
        res[name] = {**out, "call": call}
        print(f"   {name:<26s} {pl['increment']:>+8.4f} [{pl['ci'][0]:>+6.3f},{pl['ci'][1]:>+6.3f}] "
              f"{ma['increment']:>+9.4f} [{ma['ci'][0]:>+6.3f},{ma['ci'][1]:>+6.3f}]  {call}")

    g3 = bool(res["NOISE_CONTROL"]["call"] == "absent")
    print(f"G3 NEGATIVE CONTROL does not add   {'PASS' if g3 else '*** FAIL'}")

    # G5 -- REM placebo. Where does each column place REM on its OWN W..N3 ladder?
    print(f"\nG5 REM PLACEBO  (REM has the LOWEST muscle tone and sits MID-depth; those dissociate)")
    Xr = np.array([[_f(r.get(c, "")) for c in cols] for r, _ in rem], float)
    rung = {}
    print(f"   {'column':<26s} {'REM rung (0=W .. 3=N3)':>24s}")
    for i, c in enumerate(cols):
        lad = [float(np.median(X[y == v, i])) for v in (0, 1, 2, 3)]
        rv = float(np.median(Xr[:, i][np.isfinite(Xr[:, i])]))
        order = np.argsort(lad)
        pos = float(np.interp(rv, np.array(lad)[order], np.arange(4.0)[order]))
        rung[c] = pos
        print(f"   {c:<26s} {pos:>24.3f}")
    flagged = [c for c in CANDIDATES if abs(rung[c] - rung[ARTEFACT]) <= REM_TOL]
    print(f"   candidates within {REM_TOL} of the artefact channel's REM rung: "
          f"{flagged if flagged else 'none'}")

    out = {"experiment": "E222", "n_points": len(ladder), "n_subjects": len(subs), "n_rem": len(rem),
           "incumbent_rho": rho, "incumbent_floor": p95,
           "artefact_rho": spearman(list(X[:, 1]), list(y)),
           "results": res, "rem_rung": rung, "rem_flagged": flagged,
           "g1": g1, "g2": g2, "g3": g3}
    tested = {k: v for k, v in res.items() if k in CANDIDATES}
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3):
        out["verdict"] = "NOT INTERPRETABLE"
        out["why"] = "a gate failed: " + ", ".join(
            n for n, ok in (("G1", g1), ("G2 incumbent alive", g2), ("G3 negative control", g3)) if not ok)
    elif any(v["call"] == "REVERSED" for v in tested.values()):
        w = [k for k, v in tested.items() if v["call"] == "REVERSED"]
        out["verdict"], out["why"] = "REVERSED", f"{w} clear on the NEGATIVE side; never support"
    elif any(v["call"] == "REPLICATES" for v in tested.values()):
        w = [k for k, v in tested.items() if v["call"] == "REPLICATES"]
        out["verdict"], out["why"] = "REPLICATES", (
            f"{w} add to the incumbent WITH muscle already in the baseline")
    elif any(v["call"] == "MUSCLE-DEPENDENT" for v in tested.values()):
        w = [k for k, v in tested.items() if v["call"] == "MUSCLE-DEPENDENT"]
        out["verdict"], out["why"] = "MUSCLE-DEPENDENT", (
            f"{w} add over the incumbent alone but NOT once emg_index is in the baseline")
    else:
        out["verdict"], out["why"] = "ABSENT", "no candidate adds, with or without muscle in the baseline"
    print(f"VERDICT: {out['verdict']}\n  {out['why']}")
    print("=" * 100)
    print("SCOPE: wpli_theta is absent from this panel. The label is a SLEEP ladder, not sedation, so this\n"
          "  replicates the CANDIDATES rather than the exact estimand. And emg_index is a WEAK proxy --\n"
          "  E69 showed it fails to detect REM atonia -- so G4 is a PARTIAL control and surviving it does\n"
          "  not prove a candidate cortical.")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
