#!/usr/bin/env python3
"""E160 -- Challenge D: does the DOSE-I pharmacology model transport to the ICU?

THE PREDICTION WAS COMMITTED ON 2026-08-03 IN `docs/CHALLENGE_D_PREREGISTRATION.md`, WHILE THE EXTRACTION
WAS STILL STREAMING AND BEFORE ANY EXPOSURE MODEL HAD BEEN FITTED AGAINST RASS. That file exists because
"once the transport result is visible the prediction cannot honestly be made." This file implements it and
changes none of it.

=========================================================================================================
THE RULE UNDER TEST
=========================================================================================================
`PROGRAMME_ROADMAP.md` states the pattern four observations produced -- **transport succeeds when the
construct matches and fails when it does not, and construct match is specifiable in advance** -- and
immediately flags that it is a RETRODICTION over E131, E123, the PK validation and E129. Challenge D's
first job is to make it predict something.

E122 measured what there is to transport: on DOSE-I, an exposure model reaches **out-of-bag rho 0.4595**
against MOAA/S, climbing from **0.1755** for cumulative dose alone to **0.4263** once the kinetic basis is
used -- a gain of **+0.2508**.

Six axes, five of which do not match:

    axis          DOSE-I                        MIMIC-IV                        matched?
    dosing        intermittent BOLUS            INFUSION                        no
    drugs         propofol alone                propofol + midazolam + ketamine
                                                + dexmedetomidine + fentanyl    no
    state scale   MOAA/S 1-5, observer-rated    RASS -5..+4, observer-rated     partial
    cadence       every few minutes             a few times a day               no
    horizon       ~20 minutes                   days                            no
    population    elective endoscopy day-case   critically ill ICU              no

=========================================================================================================
THE COMMITTED PREDICTIONS, QUOTED
=========================================================================================================
**PRIMARY: "the DOSE-I-shaped exposure model will reach out-of-bag rho BELOW +0.25 against RASS in
MIMIC-IV"** -- losing more than half of E122's 0.4595 and landing closer to its kinetics-free rung.

Three outcomes, and the costly one is listed first exactly as the pre-registration lists it:

1. **rho >= 0.40** -- transport is essentially intact despite five mismatched axes. **The construct-match
   rule is then wrong**, or "construct" means something narrower than these six axes, and Challenge D's
   central claim collapses.
2. **0.25 <= rho < 0.40** -- partial. The rule is directionally right and its binary framing too coarse;
   what would be needed is a graded notion of construct distance, which the table above does not supply.
3. **rho < 0.25** -- as predicted.

**SECONDARY, and the pre-registration calls it the sharper test because it predicts a MECHANISM rather
than a magnitude: "the L0 -> L2 gain in MIMIC will be under half the DOSE-I gain of +0.2508."** Bolus
dosing makes concentration non-monotone in cumulative dose, which is why the kinetic basis more than
doubled the correlation on DOSE-I. Under infusion at ICU timescales, cumulative dose and concentration
order the observations almost identically, so the elaboration should buy little. E121 already found this
pattern on VitalDB maintenance data, which is the closest existing analogue.

=========================================================================================================
GATES, AS REGISTERED
=========================================================================================================
G1  >= 500 ICU stays with >= 3 RASS observations and a non-empty sedative record.
G2  **THE OUTCOME MUST BE ALIVE.** RASS must vary within stays. A cohort of uniformly alert-and-calm
    patients has nothing for any exposure model to predict and a null would be about the cohort.
G3  **NEGATIVE CONTROL.** A Gaussian exposure column must not predict RASS.
G4  **PARSING**, already discharged by the cohort builder and re-asserted here from its manifest:
    **10 distinct RASS strings, 0 unparsed** over 1,656,001 observations.

=========================================================================================================
WHAT IS FITTED
=========================================================================================================
    L0  cumulative mg per drug, five columns                       -- E122's kinetics-free rung
    L2  the exponential basis per drug, thirty columns             -- E122's kinetic rung
    statistic   out-of-bag rho, clustering on STAY: each replicate fits on stays drawn with replacement
                and scores Spearman on the rows of stays NOT drawn (rule 9). This is E122's statistic, so
                the two numbers are comparable, which is the entire point of a transport test.

**The half-life span is (2, 8, 32, 128, 512, 2048) minutes and it was widened from the originally declared
(2, 8, 32, 128) after a smoke run showed the median observation sits 152 hours into the stay**, where the
short terms are numerically zero. That change is recorded in the cohort builder with its reason: a basis
with no dynamic range would have confirmed the primary prediction for the wrong reason, and confirming my
own prediction by crippling the incumbent is the one direction I am not entitled to move in.

SECONDARY, NO VERDICT ATTACHED -- **the E127 repair.** `Goal Richmond-RAS Scale` is charted for 98 % of
these observations. E127 destroyed E126 by showing the residual LEADS the concentration direction, because
clinicians withhold drug from a patient who already looks deeper than intended; DOSE-I records no target
so the confound could be detected and never removed. Here the model is re-fitted with the most recent
goal added, and the change in rho is reported. **If the goal alone predicts RASS better than the
pharmacology does, the honest reading is that this cohort measures clinical intent rather than drug
effect**, and that would bound every ICU transport claim, not just this one.

WHAT WAS ALREADY SEEN (rule 41). The cohort manifest: 83,575 stays with a RASS row, 30,132 with a
sedative record and >= 3 observations, 4,000 sampled at seed 160 giving 123,728 rows; the RASS value
distribution over the full 1.66 M (modal ' 0  Alert and calm' at 787,684, full -5..+4 scale represented);
the per-drug unit combinations; and, on a 30-stay smoke run, that cumulative propofol is monotone within
every stay and goal RASS is present in 98 % of rows. **No exposure column has been correlated with RASS.**

    python bsde/src/bsde/experiments/e160_mimic_transport.py
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

from bsde.verifier.stats import ridge_fit, spearman, _standardise              # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "mimic_cohort.csv")
OUT = os.path.join(RESULTS, "e160_mimic_transport.json")

DRUGS = ("propofol", "midazolam", "ketamine", "dexmedetomidine", "fentanyl")
HALF_LIVES = (2, 8, 32, 128, 512, 2048)
DOSEI_FULL, DOSEI_L0, DOSEI_L2 = 0.4595, 0.1755, 0.4263
DOSEI_GAIN = DOSEI_L2 - DOSEI_L0
REPS = 300
MIN_STAYS = 500


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def oob_rho(X, y, stay, rng, reps=REPS, lam=1.0):
    """Out-of-bag Spearman, clustering on stay. E122's statistic, so the two numbers compare."""
    uniq = np.unique(stay)
    idx = {u: np.flatnonzero(stay == u) for u in uniq}
    out = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        ds = set(drawn.tolist())
        oob = [u for u in uniq if u not in ds]
        if len(oob) < 20:
            continue
        tr = np.concatenate([idx[u] for u in drawn])
        te = np.concatenate([idx[u] for u in oob])
        try:
            Ztr, Zte = _standardise(X[tr], X[te])
            p = Zte @ ridge_fit(Ztr, y[tr], lam)
        except Exception:                                                      # noqa: BLE001
            continue
        r = spearman(list(y[te]), list(p))
        if math.isfinite(r):
            out.append(r)
    if len(out) < 30:
        return float("nan"), float("nan"), float("nan"), len(out)
    v = np.sort(np.asarray(out, float))
    return float(v.mean()), float(np.quantile(v, .025)), float(np.quantile(v, .975)), len(v)


def main(argv=None) -> int:
    rng = np.random.default_rng(160)
    rows = list(csv.DictReader(open(TABLE, newline="")))
    stay = np.array([r["stay_id"] for r in rows])
    y = np.array([_f(r["rass"]) for r in rows], float)
    goal = np.array([_f(r["goal_rass"]) for r in rows], float)
    L0 = np.column_stack([[_f(r[f"cum_{d}"]) for r in rows] for d in DRUGS]).astype(float)
    L2 = np.column_stack([[_f(r[f"k{h}_{d}"]) for r in rows] for d in DRUGS for h in HALF_LIVES]
                         ).astype(float)
    ok = np.isfinite(y) & np.isfinite(L0).all(1) & np.isfinite(L2).all(1)
    rows_n, stays_n = int(ok.sum()), int(len(set(stay[ok].tolist())))
    out = {"experiment": "E160", "n_rows": rows_n, "n_stays": stays_n, "reps": REPS,
           "dosei": {"full": DOSEI_FULL, "L0": DOSEI_L0, "L2": DOSEI_L2, "gain": DOSEI_GAIN}}

    g1 = stays_n >= MIN_STAYS
    print(f"G1 COVERAGE  {rows_n:,} observations from {stays_n:,} stays (floor {MIN_STAYS}) -> "
          f"{'PASS' if g1 else 'FAIL'}")

    # ---- G2 the outcome must be alive ----------------------------------------------------------------
    per = {}
    for s, v in zip(stay[ok], y[ok]):
        per.setdefault(s, set()).add(v)
    varying = sum(1 for v in per.values() if len(v) > 1)
    frac = varying / max(len(per), 1)
    g2 = frac >= 0.5
    print(f"G2 OUTCOME ALIVE  {varying:,} of {len(per):,} stays have RASS varying within them "
          f"({frac:.1%}) -> {'PASS' if g2 else 'FAIL'}")
    print(f"   RASS overall sd {y[ok].std():.3f}, range {y[ok].min():.0f} to {y[ok].max():.0f}")

    # ---- G4 parsing, re-asserted from the builder's manifest -------------------------------------------
    try:
        man = json.load(open(TABLE + ".manifest.json"))
        g4 = man.get("unparsed_rass", 1) == 0
        print(f"G4 PARSING  {man['distinct_rass_strings']} distinct strings, "
              f"{man['unparsed_rass']:,} unparsed -> {'PASS' if g4 else 'FAIL'}")
    except Exception:                                                          # noqa: BLE001
        g4 = False
        print("G4 PARSING  manifest unreadable -> FAIL")

    X0, X2, yy, ss = L0[ok], L2[ok], y[ok], stay[ok]

    # ---- G3 negative control ---------------------------------------------------------------------------
    gaus = rng.standard_normal((len(yy), 1))
    m, lo, hi, n = oob_rho(gaus, yy, ss, rng)
    g3 = abs(m) < 0.05
    print(f"G3 NEGATIVE CONTROL  a Gaussian exposure column reaches out-of-bag rho {m:+.4f} "
          f"[{lo:+.4f}, {hi:+.4f}] -> {'PASS' if g3 else 'FAIL'}")
    out["G1"], out["G2"] = bool(g1), {"pass": bool(g2), "frac_varying": frac}
    out["G3"] = {"pass": bool(g3), "rho": m}
    out["G4"] = bool(g4)

    gates = g1 and g2 and g3 and g4
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    # ---- the ladder --------------------------------------------------------------------------------------
    r0 = oob_rho(X0, yy, ss, rng)
    r2 = oob_rho(np.c_[X0, X2], yy, ss, rng)
    gain = r2[0] - r0[0]
    print(f"THE LADDER, out-of-bag rho against RASS, clustering on stay")
    print(f"   L0 cumulative dose only      {r0[0]:+.4f} [{r0[1]:+.4f}, {r0[2]:+.4f}]   "
          f"(DOSE-I: {DOSEI_L0:+.4f})")
    print(f"   L2 + kinetic basis           {r2[0]:+.4f} [{r2[1]:+.4f}, {r2[2]:+.4f}]   "
          f"(DOSE-I: {DOSEI_L2:+.4f})")
    print(f"   L0 -> L2 gain                {gain:+.4f}                     "
          f"(DOSE-I: {DOSEI_GAIN:+.4f})")
    out["ladder"] = {"L0": {"rho": r0[0], "ci": [r0[1], r0[2]]},
                     "L2": {"rho": r2[0], "ci": [r2[1], r2[2]]}, "gain": gain}

    # ---- secondary: the E127 repair ---------------------------------------------------------------------
    gk = np.isfinite(goal[ok])
    rg = oob_rho(goal[ok][gk].reshape(-1, 1), yy[gk], ss[gk], rng)
    rgp = oob_rho(np.c_[X0[gk], X2[gk], goal[ok][gk]], yy[gk], ss[gk], rng)
    print(f"\nSECONDARY (no verdict) -- the E127 repair, on the {int(gk.sum()):,} rows with a charted goal")
    print(f"   goal RASS alone              {rg[0]:+.4f} [{rg[1]:+.4f}, {rg[2]:+.4f}]")
    print(f"   pharmacology + goal          {rgp[0]:+.4f} [{rgp[1]:+.4f}, {rgp[2]:+.4f}]")
    out["goal"] = {"alone": {"rho": rg[0], "ci": [rg[1], rg[2]]},
                   "with_pharmacology": {"rho": rgp[0], "ci": [rgp[1], rgp[2]]},
                   "n_rows": int(gk.sum())}

    # ---- verdict -----------------------------------------------------------------------------------------
    rho = r2[0]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif rho >= 0.40:
        verdict = (f"THE RULE IS WRONG -- out-of-bag rho {rho:+.4f} against RASS, essentially intact "
                   f"transport across five mismatched axes. The construct-match rule this programme has "
                   f"been building on does not predict, and Challenge D's central claim collapses. This "
                   f"is outcome 1 of the pre-registration, the one listed first because it costs most.")
    elif rho >= 0.25:
        verdict = (f"PARTIAL TRANSPORT -- rho {rho:+.4f}, between the pre-registered thresholds. The rule "
                   f"is directionally right and its binary framing is too coarse; what is needed is a "
                   f"GRADED notion of construct distance, which the six-axis table does not supply. "
                   f"Outcome 2 of three.")
    else:
        verdict = (f"AS PREDICTED -- rho {rho:+.4f} < 0.25, losing "
                   f"{100 * (1 - rho / DOSEI_FULL):.0f} % of DOSE-I's {DOSEI_FULL:+.4f}. The "
                   f"construct-match rule made a forward prediction and it held. Outcome 3.")
    sharp = ("CONFIRMED" if gain < DOSEI_GAIN / 2 else "REFUTED")
    print(f"\nVERDICT: {verdict}")
    print(f"SECONDARY PREDICTION (the sharper one): L0->L2 gain {gain:+.4f} against half of DOSE-I's "
          f"{DOSEI_GAIN:+.4f} = {DOSEI_GAIN / 2:+.4f} -> {sharp}")
    out["verdict"] = verdict
    out["secondary_prediction"] = sharp
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
