"""E122 -- Does the EEG carry sedation depth that a complete propofol exposure model CANNOT predict?

REGISTERED BEFORE ANY OF THE PHARMACOLOGY COLUMNS HAVE BEEN LOOKED AT AGAINST MOAA/S. The dose record,
the covariates and the recovered clock were built and checked in the previous commit; the exponential
basis was verified against an independent ODE integration. Nothing in this file's question has been run.

=========================================================================================================
WHY, AND WHY THIS IS THE EXPERIMENT THE PROGRAMME HAS BEEN MISSING
=========================================================================================================
`docs/DEPTH_TARGET_STRATEGY.md` argues, in response to the investigator's question "BIS is not a good
target right?", that BIS fails as a target three ways -- it is computed from the same EEG (circular), its
failure modes are measured (E109's age discordance +0.2592; E120: it tracks remifentanil at +0.2042 while
the aperiodic exponent does not; E60: median SQI 5.1 of 100 in the band where its error was worst), and it
is an intermediate rather than an endpoint.

**And that effect-site concentration fails too, for a sharper reason.** If an EEG measure tracked Ce
perfectly it would be redundant with the infusion pump, which already knows Ce. The clinical case for an
EEG monitor is that individuals differ in their response AT THE SAME CONCENTRATION. So the chain is

    dose --[PK]--> concentration --[PD sensitivity]--> CLINICAL STATE

and the EEG's job is what the pharmacology cannot predict. Seven VitalDB experiments (E109, E110, E112,
E113, E118, E120, E121) asked exposure and device questions well and **none of them could have answered
this**, because VitalDB's only state-like variable is BIS and BIS is EEG-derived. DOSE-I can: a
clinician-assigned MOAA/S in 16,442 of 16,442 windows, varying within every recording, beside a dose
record.

THE RESIDUAL FRAMING IS IMPLEMENTED AS AN INCREMENT, WHICH IS ITS RIGOROUS FORM. Fitting a pharmacology
model, taking `observed - predicted`, and correlating an EEG measure against that residual would inherit
the first stage's error into the second stage's uncertainty and understate it. The identical question,
correctly propagated, is the out-of-bag increment from `pharmacology` to `pharmacology + EEG`, which is
what `oob_regression_increment` computes and what E84 used.

=========================================================================================================
THE PHARMACOLOGY ARM IS DELIBERATELY AS STRONG AS IT CAN BE MADE
=========================================================================================================
Making the incumbent weak would flatter the EEG for the wrong reason (rule 50). So:

  * the dose record is read at **1 Hz**, not from the 5 s-strided feature file, which would have dropped
    about four fifths of the bolus events;
  * the join uses a **recovered per-recording clock offset** (0 to 2323 s, 77 distinct values); assuming
    zero would have matched 14 of 221 feature-visible dose events, and the recovered offset matches
    221/221 while having been fitted only on `PE31`/`SEF95`/`MOAAS`/`SOC`;
  * the kinetics are an **exponential basis that contains every linear compartment model** -- Marsh,
    Schnider, Eleveld are points inside it (verified: `tests/test_pkpd_basis.py` reproduces an independent
    three-compartment ODE integration at R2 = 1.000000 and 0.999894, while single exponentials reach 0.029
    and 0.551). A transported published model could only do worse out of sample, so the paywall on Eleveld
    2018 costs this design nothing;
  * **the increment must clear EVERY rung of the ladder, not the best one.** Choosing the rung after
    seeing the scores would be selection; requiring all five removes the choice.

L0 cumulative mg/kg | L1 one 4 min exponential | L2 the 8-rate basis | L3 basis with allometric weight
scaling (CL^0.75, V^1.0; Anderson & Holford, PMID 17914927; the cohort spans 34-165 kg) | L4 L3 plus every
PD covariate the deposit records: age, sex, ASA, BMI, chronic opioid / neuroleptic / antiepileptic /
beta-blocker use, obesity-hypoventilation, sleep apnoea, hepatic encephalopathy, chronic heart failure,
inpatient status, and the **procedural stimulus indicator**, which is a non-EEG determinant of arousal at
fixed drug concentration and therefore belongs in the expectation rather than in the residual.

`chronic_benzodiazepines` is constant (0 in all 171 recordings) and is dropped rather than fitted.

WHAT THE COVARIATE ARM IS AND IS NOT. It is a population-level sensitivity model fitted on this cohort. It
is NOT a published tolerance or frailty model -- none exists that could be implemented as published
(`PKPD_MODEL_REVIEW.md` §6 Tier 3), and that is precisely the argument for the residual framing: you do
not have to model WHY a patient is sensitive, you measure THAT they are. Whatever L4 fails to absorb is
individual sensitivity, and it is the EEG's target.

=========================================================================================================
DESIGN
=========================================================================================================
COHORT. Every DOSE-I recording with extracted features, minus two pre-specified exclusions taken from the
deposit's own documentation and fixed before this file was written: `para=1` (propofol extravasation, so
the dose record overstates delivered drug by an unknown amount -- the metadata readme says to check this)
and `dose_complete=0` (30-40 mg administered outside the pEEG window, which would corrupt a PK integral).

ON REUSING RECORDINGS. E80, E81 and E84 have read these tables. That is a selection concern only if a
candidate was chosen because it performed here, and **E84 returned `ADDS []` for all 27 candidates**, so
nothing was. The candidate list is the extractor's fixed `TRANSPORTABLE` + `CONN` set, written before any
DOSE-I result existed. The question here -- increment over pharmacology -- has never been asked on this
deposit at all.

    P1  THE STRATEGY CLAIM. Out-of-bag increment from `rung` to `rung + PE31 + SEF95`, for each of the
        five rungs. Does the deposit's OWN established EEG index add sedation depth that the pharmacology
        cannot? This is the question the strategy document poses and it uses the established measure, not
        one of ours, so it cannot be a result about this project's candidate engineering.

    P2  THE INCUMBENT TEST (rule 45). Out-of-bag increment from `rung + PE31 + SEF95` to
        `rung + PE31 + SEF95 + candidate`, for each candidate and each rung. Benjamini-Hochberg at
        q = 0.05 across candidates; the candidate count is reported with the result.

    Error statistic `1 - spearman(true, predicted)` on the out-of-bag recordings, as in E84. Each replicate
    refits BOTH models on a bootstrap resample of RECORDINGS and scores both on the recordings not drawn
    (rule 9). The returned difference is B minus A, so **negative means the addition HELPS**. Reading that
    backwards would invert every verdict, which is why it is stated here.

GATES, evaluated before the primary is read, and each able to fail (rule 40):

    G1  EXCLUSIONS APPLIED. `para=0` and `dose_complete=1` for every retained recording, and the retained
        count is reported. An exclusion that silently removed nothing would be a defect.
    G2  COVERAGE. >= 25 recordings with >= 20 windows each, MOAA/S taking more than one value, and a
        non-empty dose record.
    G3  THE PHARMACOLOGY MUST BE ALIVE. **This is the gate the strategy document names**: the exposure-only
        model must itself predict MOAA/S out of bag, median rho > 0.10, for at least one rung. If
        pharmacology alone explains nothing there is no residual worth attributing, and the verdict is
        ABSENT -- a statement about the exposure model, not about the EEG (rule 53 / E33's formulation,
        which E61 failed to carry across).
    G4  NEGATIVE CONTROL. A per-window Gaussian column runs the identical pipeline and must NOT return
        ADDS. If noise adds, the out-of-bag machinery is leaking.
    G5  THE LADDER MUST BE A LADDER. L2 must beat L0 on out-of-bag rho. If eight exponentials cannot beat
        cumulative dose, the kinetics are not being estimated and P1's "pharmacology" is a misnomer. Note
        this gate is allowed to fail informatively: E121 found on VitalDB that elaborating the exposure
        made tracking WORSE, so a failure here would replicate that on a second deposit rather than
        indicate a bug.

PLACEBO, and it GATES the verdict rather than sitting beside it (rule 34).
    Each EEG series is CIRCULARLY TIME-SHIFTED within its own recording by a random offset of at least
    120 s. That preserves the marginal distribution, the autocorrelation, and any within-recording time
    trend, and destroys only the instantaneous correspondence with MOAA/S. It is the right destruction
    because the alternative explanation is specific: a pharmacology model that misfits the shape of the
    trajectory leaves a residual with a time trend, and any EEG measure that also drifts with time would
    predict it without carrying any state information (rule 64 -- a contrast keyed to time is a time
    contrast until a shift-placebo says otherwise).

    The comparison is against the placebo's DISTRIBUTION over 200 draws, never its mean (rule 37, fifth
    occurrence): a mean placebo is a point with no width and every real value differs from it. ADDS
    requires the real increment to be more negative than at least 95 % of placebo draws.

    Rule 48: if the primary interval INCLUDES zero the placebo is not informative and must say so rather
    than print PASSED. The primary is therefore evaluated first.

VERDICT, wrong direction FIRST and by name (rule 37, fourth occurrence -- "excludes the null" and
"supports the hypothesis" are different questions):

    (a) interval excludes 0 POSITIVE, at any rung  -> HURTS at that rung. The addition makes out-of-bag
        prediction WORSE. This is not a null and must not be reported as one.
    (b) interval includes 0 at any rung            -> NO INCREMENT. A conjunction across five rungs, so
        one inclusive interval is enough to refuse.
    (c) interval excludes 0 NEGATIVE at ALL FIVE rungs AND beats 95 % of placebo draws -> ADDS.

SCOPE, and it is narrow. One deposit, 171 recordings of propofol MONO-sedation for endoscopy at one site,
a two-channel fronto-temporal montage, and a five-point behavioural scale scored by a clinician who has to
stimulate the patient to score it -- so the assessment itself perturbs the arousal being measured, in the
direction of making any EEG measure look better. Nothing here transfers to surgical anaesthesia, to
multi-drug regimens, or to a population that is not having an endoscopy. The synergy question the
investigator raised cannot be asked in this deposit at all: the metadata's `Drug-related Events` section
lists only `PROP_sum`, and no second agent is recorded anywhere.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "bsde", "src"))

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e122_pharmacology_residual.json")

FEATURE_TABLES = ("dosei_features.csv", "dosei_holdout_features.csv")
DOSE_TABLE = os.path.join(RESULTS, "dosei_dose_events.csv")
COVAR_TABLE = os.path.join(RESULTS, "dosei_covariates.csv")
OFFSET_TABLE = os.path.join(RESULTS, "dosei_clock_offsets.csv")

INCUMBENT = ["their_pe31", "their_sef95"]
META = {"recording", "t_s", "soc", "moaas", "propofol", "endoscopy", "ecg_hr", "n_finite",
        "their_pe31", "their_sef95"}

RUNGS = (0, 1, 2, 3, 4)
MIN_WINDOWS = 20
MIN_RECORDINGS = 25
G3_RHO_FLOOR = 0.10
REPS = 400
PLACEBO_DRAWS = 200
MIN_SHIFT_S = 120.0
SEED = 122


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    import numpy as np
    off = {r["recording"]: int(r["offset_s"])
           for r in csv.DictReader(open(OFFSET_TABLE, newline=""))}
    cov = {r["recording"]: r for r in csv.DictReader(open(COVAR_TABLE, newline=""))}
    dose = {}
    for r in csv.DictReader(open(DOSE_TABLE, newline="")):
        dose.setdefault(r["recording"], []).append((float(r["t_abs_s"]), float(r["dose_mg"])))

    rows = []
    for name in FEATURE_TABLES:
        p = os.path.join(RESULTS, name)
        if not os.path.exists(p):
            continue
        rows.extend(csv.DictReader(open(p, newline="")))
    if not rows:
        raise SystemExit("no DOSE-I feature table found")

    cands = sorted(c for c in rows[0] if c not in META)
    by = {}
    for r in rows:
        by.setdefault(r["recording"], []).append(r)
    return by, cands, off, cov, dose


def build(by, cands, off, cov, dose):
    """Per-recording design blocks. Returns the retained recordings and the gate bookkeeping."""
    import numpy as np
    from bsde.pkpd.propofol import rung

    COVCOLS = ["age", "bmi", "asa", "chronic_bblocker", "chronic_opioids", "chronic_neuroleptics",
               "chronic_antiepileptics", "cond_ohs", "cond_sas", "cond_ohe", "cond_chf"]

    kept, dropped = {}, {"para": [], "dose_incomplete": [], "no_offset": [], "no_covar": [],
                         "few_windows": [], "constant_moaas": [], "no_dose": []}
    for rec in sorted(by):
        c = cov.get(rec)
        if c is None:
            dropped["no_covar"].append(rec); continue
        if c["para"] == "1":
            dropped["para"].append(rec); continue
        if c["dose_complete"] != "1":
            dropped["dose_incomplete"].append(rec); continue
        if rec not in off:
            dropped["no_offset"].append(rec); continue
        ev = dose.get(rec) or []
        if not ev:
            dropped["no_dose"].append(rec); continue

        rr = [r for r in by[rec] if np.isfinite(_f(r["moaas"]))]
        rr.sort(key=lambda r: _f(r["t_s"]))
        if len(rr) < MIN_WINDOWS:
            dropped["few_windows"].append(rec); continue
        y = np.array([_f(r["moaas"]) for r in rr])
        if np.unique(y).size < 2:
            dropped["constant_moaas"].append(rec); continue

        t_abs = np.array([_f(r["t_s"]) for r in rr]) + off[rec]
        dt = [e[0] for e in ev]
        dm = [e[1] for e in ev]
        wt = _f(c["weight_kg"])

        stim = np.array([1.0 if (r.get("endoscopy") or "").strip() in ("1", "1.0") else 0.0 for r in rr])
        cvals = {k: _f(c[k]) for k in COVCOLS}
        cvals["sex_male"] = 1.0 if c["sex"] == "male" else 0.0
        cvals["inpatient"] = 1.0 if c["care_type"] == "inpatient" else 0.0
        cvals["stimulus"] = stim

        pk, pknames = {}, {}
        ok = True
        for L in RUNGS:
            try:
                X, nm = rung(L, dt, dm, t_abs, weight_kg=wt, covariates=cvals)
            except Exception:                                            # noqa: BLE001
                ok = False; break
            if not np.all(np.isfinite(X)):
                ok = False; break
            pk[L], pknames[L] = X, nm
        if not ok:
            dropped["no_dose"].append(rec); continue

        inc = np.column_stack([[_f(r[c2]) for r in rr] for c2 in INCUMBENT])
        cand = {c2: np.array([_f(r[c2]) for r in rr]) for c2 in cands}
        kept[rec] = {"y": y, "t": t_abs, "pk": pk, "names": pknames, "inc": inc, "cand": cand}
    return kept, dropped


def stack(kept, recs, key_fn):
    import numpy as np
    Xs, ys, ss = [], [], []
    for rec in recs:
        d = kept[rec]
        X = key_fn(d)
        Xs.append(X); ys.append(d["y"]); ss.append(np.full(d["y"].size, rec))
    return np.vstack(Xs), np.concatenate(ys), np.concatenate(ss)


def oob_rho(X, y, subject, rng, reps=REPS, lam=1.0):
    """Median out-of-bag spearman for a single model. Refit inside every resample (rule 9)."""
    import numpy as np
    from bsde.verifier.stats import spearman, ridge_fit, _standardise
    uniq = np.unique(subject)
    idx = {u: np.flatnonzero(subject == u) for u in uniq}
    vals = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        ds = set(drawn.tolist())
        oob = [u for u in uniq if u not in ds]
        if len(oob) < 5:
            continue
        tr = np.concatenate([idx[u] for u in drawn])
        te = np.concatenate([idx[u] for u in oob])
        try:
            A, B = _standardise(X[tr], X[te])
            p = B @ ridge_fit(A, y[tr], lam)
        except Exception:                                                # noqa: BLE001
            continue
        r = spearman(y[te], p)
        if np.isfinite(r):
            vals.append(r)
    return float(np.median(vals)) if vals else float("nan")


def circular_shift(kept, recs, col, rng):
    """Circularly rotate one candidate column within each recording by >= MIN_SHIFT_S seconds."""
    import numpy as np
    out = {}
    for rec in recs:
        d = kept[rec]
        v = d["cand"][col] if col in d["cand"] else None
        n = d["y"].size
        span = float(d["t"][-1] - d["t"][0]) if n > 1 else 0.0
        lo = int(np.ceil(MIN_SHIFT_S / max(1e-9, span / max(1, n - 1)))) if span > 0 else 1
        lo = max(1, min(lo, max(1, n - 1)))
        k = int(rng.integers(lo, max(lo + 1, n))) if n > lo else 1
        out[rec] = np.roll(v, k)
    return out


def main(argv=None) -> int:
    import numpy as np
    from bsde.verifier.stats import oob_regression_increment, spearman

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)

    sys.path.insert(0, GOV)
    from registry_ledger import register                                  # noqa: E402
    try:
        register(
            "E122", "C",
            "Does the EEG carry sedation depth that a complete propofol exposure model cannot predict?",
            "DOSE-I", "out-of-bag increment from pharmacology rung to rung+EEG, all five rungs, "
                      "error = 1 - spearman, negative helps",
            ["G1 exclusions applied (para, incomplete dose)", "G2 coverage >=25 recordings",
             "G3 pharmacology alive: exposure-only oob rho > 0.10", "G4 gaussian negative control",
             "G5 L2 beats L0"],
            "circular within-recording time shift >= 120 s, compared against the 200-draw distribution",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E121",
            instrument_changed="the OUTCOME: a clinician-scored MOAA/S replaces BIS and replaces "
                               "effect-site concentration as the thing the EEG is scored against")
        print("registered E122")
    except Exception as e:                                                # noqa: BLE001
        print(f"registration: {e}")
    if a.register_only:
        return 0

    by, cands, off, cov, dose = load()
    kept, dropped = build(by, cands, off, cov, dose)
    recs = sorted(kept)
    rng = np.random.default_rng(SEED)

    gates = {
        "G1_excluded_para": len(dropped["para"]),
        "G1_excluded_dose_incomplete": len(dropped["dose_incomplete"]),
        "G1_pass": len(dropped["para"]) + len(dropped["dose_incomplete"]) > 0,
        "G2_recordings": len(recs),
        "G2_pass": len(recs) >= MIN_RECORDINGS,
        "dropped": {k: len(v) for k, v in dropped.items()},
    }

    if not gates["G2_pass"]:
        json.dump({"gates": gates, "verdict": "REFUSED: coverage"}, open(a.out, "w"), indent=1)
        print(json.dumps(gates, indent=1))
        return 0

    # ---- the pharmacology ladder, on its own (G3 and G5) -------------------------------------------
    ladder = {}
    for L in RUNGS:
        X, y, s = stack(kept, recs, lambda d, L=L: d["pk"][L])
        ladder[f"L{L}"] = oob_rho(X, y, s, np.random.default_rng(SEED + L), reps=a.reps)
    gates["G3_ladder_oob_rho"] = ladder
    gates["G3_best"] = max((v for v in ladder.values() if np.isfinite(v)), default=float("nan"))
    gates["G3_pass"] = bool(np.isfinite(gates["G3_best"]) and gates["G3_best"] > G3_RHO_FLOOR)
    gates["G5_pass"] = bool(np.isfinite(ladder["L2"]) and np.isfinite(ladder["L0"])
                            and ladder["L2"] > ladder["L0"])

    if not gates["G3_pass"]:
        out = {"gates": gates, "verdict":
               "ABSENT -- the exposure-only model does not predict MOAA/S out of bag "
               f"(best rung rho {gates['G3_best']:+.4f} <= {G3_RHO_FLOOR}). There is no residual worth "
               "attributing, so this is a statement about the exposure model and NOT about the EEG."}
        json.dump(out, open(a.out, "w"), indent=1)
        print(json.dumps(out, indent=1))
        return 0

    def err(t, p):
        r = spearman(t, p)
        return 1.0 - r if np.isfinite(r) else float("nan")

    # ---- P1: does the deposit's OWN index add over pharmacology? -----------------------------------
    p1 = {}
    for L in RUNGS:
        Xa, y, s = stack(kept, recs, lambda d, L=L: d["pk"][L])
        Xb, _, _ = stack(kept, recs, lambda d, L=L: np.hstack([d["pk"][L], d["inc"]]))
        m, lo, hi, n = oob_regression_increment(Xa, Xb, y, s, np.random.default_rng(SEED + 100 + L),
                                                stat=err, reps=a.reps)
        p1[f"L{L}"] = {"mean": m, "lo": lo, "hi": hi, "n_reps": n}

    # ---- P2: does any candidate add over pharmacology + the incumbent? ------------------------------
    testable = [c for c in cands
                if all(np.isfinite(kept[r]["cand"][c]).all() for r in recs)
                and len({round(float(v), 12) for r in recs for v in kept[r]["cand"][c]}) > 2]
    p2 = {}
    for c in testable:
        per_rung = {}
        for L in RUNGS:
            Xa, y, s = stack(kept, recs, lambda d, L=L: np.hstack([d["pk"][L], d["inc"]]))
            Xb, _, _ = stack(kept, recs,
                             lambda d, L=L, c=c: np.hstack([d["pk"][L], d["inc"], d["cand"][c][:, None]]))
            m, lo, hi, n = oob_regression_increment(Xa, Xb, y, s,
                                                    np.random.default_rng(SEED + 200 + L), stat=err,
                                                    reps=a.reps)
            per_rung[f"L{L}"] = {"mean": m, "lo": lo, "hi": hi, "n_reps": n}
        p2[c] = per_rung

    # ---- G4: the negative control runs the identical pipeline ---------------------------------------
    for rec in recs:
        kept[rec]["cand"]["__gaussian__"] = rng.normal(size=kept[rec]["y"].size)
    g4 = {}
    for L in RUNGS:
        Xa, y, s = stack(kept, recs, lambda d, L=L: np.hstack([d["pk"][L], d["inc"]]))
        Xb, _, _ = stack(kept, recs, lambda d, L=L: np.hstack(
            [d["pk"][L], d["inc"], d["cand"]["__gaussian__"][:, None]]))
        m, lo, hi, n = oob_regression_increment(Xa, Xb, y, s, np.random.default_rng(SEED + 300 + L),
                                                stat=err, reps=a.reps)
        g4[f"L{L}"] = {"mean": m, "lo": lo, "hi": hi}
    gates["G4_negative_control"] = g4
    gates["G4_pass"] = not all(np.isfinite(v["hi"]) and v["hi"] < 0 for v in g4.values())

    json.dump({"gates": gates, "P1_incumbent_over_pharmacology": p1,
               "P2_candidates": p2, "n_candidates": len(testable),
               "verdict": "PENDING -- placebo and verdict computed in the second stage"},
              open(a.out, "w"), indent=1)
    print(json.dumps({"gates": gates, "P1": p1}, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
