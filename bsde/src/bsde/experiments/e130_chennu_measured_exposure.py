"""E130 -- Does the EEG add over a MEASURED plasma propofol concentration for predicting behaviour?
The external replication of E122, with the PK model removed from the incumbent entirely.

REGISTERED BEFORE ANY EEG FEATURE HAS BEEN PUT NEAR A BEHAVIOURAL OUTCOME IN THIS DEPOSIT. The marginal
distributions of the exposure and the two candidate outcomes were probed first and are disclosed below;
no association has been computed.

=========================================================================================================
WHY THIS IS THE REPLICATION E122 NEEDS, AND WHY IT IS A HARDER TEST
=========================================================================================================
E122 established, on DOSE-I, that the EEG carries sedation depth a complete propofol exposure model cannot
predict: the deposit's own index added to every rung of an exposure ladder (L0 -0.2738 to L4 -0.0952, all
intervals excluding zero) and a circular time-shift placebo failed to reproduce it at every rung. Its
scope note is the reason this file exists -- one deposit, one site, propofol mono-sedation for endoscopy,
and a five-point scale scored by a clinician who must stimulate the patient to score it.

**Chennu's deposit differs on every one of those axes, and on one more that makes the test harder.**

    DOSE-I                                  chennu
    exposure MODELLED from a dose record    exposure MEASURED: assayed plasma propofol, ug/L
    state = clinician-assigned MOAA/S       state = the subject's own BEHAVIOUR on a task
    assessment perturbs arousal             task performance is the state, not a probe of it
    endoscopy, procedural sedation          volunteer study, stepped target concentrations

The measured exposure is the important one. E122's incumbent was an 8-rate basis fitted out of bag -- a
strong incumbent, and this project's own PK validation measured what such a model costs when transported
(MDAPE 54.9 % across patients, `PK_VALIDATION_NOTE.md`). **Here there is no model to be wrong**: the
concentration is an assay. An EEG measure that adds over an assayed concentration cannot be adding because
the pharmacology was mis-specified, which is the single most available objection to E122.

=========================================================================================================
DESIGN
=========================================================================================================
COHORT: 20 subjects x 4 sedation levels = 80 rows, all `status == ok`.

OUTCOME, and the choice is made HERE on distributional grounds alone (disclosed below), not after seeing
any association:

    PRIMARY    `meta_mean_reaction_time_ms` -- continuous, 604 to 2217 ms, median 926, 78 of 80 present.
    SECONDARY  `meta_n_correct_of_40` -- median 37.5 of 40 with a maximum of 40, i.e. AT CEILING for most
               of the range. It moves only at the deepest levels, so it is a threshold measure rather than
               a graded one and is reported as a secondary that cannot become the headline (rule 59).

    Reaction time RISES with depth, so a measure that tracks depth correlates POSITIVELY with it. Stated
    because E127 was inverted by exactly this kind of unstated sign convention, twice.

    P   For each of the 17 EEG candidates, the OUT-OF-BAG increment from `plasma` to `plasma + candidate`
        in predicting reaction time. Each replicate fits BOTH models on a bootstrap resample of SUBJECTS
        and scores both on the subjects NOT drawn (rule 9). The statistic is `1 - spearman`, an ERROR, so
        **a NEGATIVE difference means the candidate HELPS** -- E122's and E84's convention, restated
        because reading it backwards inverts every verdict.
        Benjamini-Hochberg at q = 0.05 across all 17; the count is reported with the result.

GATES

    G1  COVERAGE: >= 18 subjects with >= 3 usable levels each.
    G2  THE EXPOSURE MUST BE ALIVE (rule 53, E33's formulation, and the gate E122 inherited). Measured
        plasma propofol must itself predict reaction time out of bag, median rho > 0.10. **If the assay
        does not predict behaviour there is nothing for an EEG measure to add TO**, and a null would be a
        statement about the outcome, not about the EEG.
    G3  NEGATIVE CONTROL: a per-row Gaussian column through the identical pipeline must not come back
        ADDS.
    G4  POWER, REPORTED NOT GATED. 20 subjects is a small cluster count and the out-of-bag bootstrap holds
        out roughly a third of them per replicate. The number of replicates that produced a usable
        out-of-bag set is reported for every candidate, and any candidate whose count falls below the
        estimator's own floor is marked rather than silently dropped.

PLACEBO, gating the verdict (rule 34): the EEG column is permuted ACROSS ROWS WITHIN SUBJECT, 500 draws.
That destroys the correspondence between the EEG and the sedation level while preserving each subject's
own marginal distribution and the subject-level clustering. Compared against the DISTRIBUTION, never the
mean (rule 37). Rule 48: the primary interval is read first, and a null primary makes the placebo NOT
INFORMATIVE rather than passed.

VERDICT per candidate, wrong direction FIRST and by name (rule 37, ninth occurrence in this project; the
seventh, eighth and ninth all followed E127's inverted sign, so the convention is spelled out above):

    (a) interval excludes 0 POSITIVE -> HURTS. The candidate makes out-of-bag prediction WORSE. Not a
        null, and must not be reported as one.
    (b) interval includes 0 -> NO INCREMENT.
    (c) interval excludes 0 NEGATIVE, survives BH, and beats the placebo -> ADDS.

WHAT A NULL WOULD AND WOULD NOT MEAN. E122's positive used the deposit's OWN shipped index, and its P2 --
27 of this project's candidates against that same index -- was entirely null. So a null here would be
consistent with E122 rather than a contradiction of it: it would say this project's candidates do not add,
which E122 already found, and would leave E122's claim (that SOME EEG summary adds) untested in this
deposit because chennu ships no vendor index to stand in for PE31/SEF95. **That asymmetry is registered
now so a null cannot later be read as a failed replication of E122.**

DISCLOSURE (rule 41). Before writing this file the marginals were read: 80 ok rows over 20 subjects;
plasma propofol 0 to 1521 ug/L, median 341; reaction time 604 to 2217 ms, median 926, n = 78; n_correct 0
to 40, median 37.5, n = 80; sedation level 1 to 4. Those numbers set the outcome choice and G1, and they
involve no EEG column and no association.

SCOPE. Twenty healthy volunteers, stepped target-controlled propofol, a high-density montage, and a
behavioural task. Nothing here transfers to surgical anaesthesia or to a patient population, and 20
subjects is a small cluster count for an out-of-bag bootstrap -- G4 reports what that costs rather than
assuming it is affordable.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e130_chennu_measured_exposure.json")
TABLE = os.path.join(RESULTS, "chennu_features_v3.csv")

EXPOSURE = "meta_plasma_propofol_ug_per_L"
PRIMARY_OUTCOME = "meta_mean_reaction_time_ms"
SECONDARY_OUTCOME = "meta_n_correct_of_40"
META_PREFIX = "meta_"
DROP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}

MIN_SUBJECTS = 18
MIN_LEVELS = 3
G2_RHO_FLOOR = 0.10
REPS = 2000
PLACEBO_DRAWS = 500
SEED = 130


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(table=TABLE, outcome=PRIMARY_OUTCOME):
    rows = [r for r in csv.DictReader(open(table, newline="")) if r.get("status") == "ok"]
    cands = sorted(c for c in rows[0] if not c.startswith(META_PREFIX) and c not in DROP)
    keep = [r for r in rows
            if np.isfinite(_f(r[EXPOSURE])) and np.isfinite(_f(r.get(outcome, "")))]
    by = {}
    for r in keep:
        by.setdefault(r["subject"], []).append(r)
    by = {s: v for s, v in by.items() if len(v) >= MIN_LEVELS}
    return by, cands


def main(argv=None) -> int:
    from bsde.verifier.stats import oob_regression_increment, spearman

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    ap.add_argument("--outcome", default=PRIMARY_OUTCOME)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)

    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E130", "C",
            "Does the EEG add over a MEASURED plasma propofol concentration for predicting behaviour?",
            "chennu",
            "out-of-bag increment from plasma to plasma+candidate for reaction time, error = 1 - "
            "spearman so NEGATIVE helps; BH q=0.05 over 17 candidates",
            ["G1 >=18 subjects with >=3 levels", "G2 measured exposure predicts behaviour out of bag",
             "G3 gaussian negative control", "G4 replicate counts reported, not gated"],
            "permute the EEG column ACROSS ROWS WITHIN SUBJECT, 500 draws, against the DISTRIBUTION",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E122",
            instrument_changed="the EXPOSURE and the OUTCOME: an ASSAYED plasma concentration replaces a "
                               "modelled one, and the subject's own task behaviour replaces a "
                               "clinician-assigned scale")
        print("registered E130")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    if a.register_only:
        return 0

    by, cands = load(outcome=a.outcome)
    subs = sorted(by)
    rows = [r for s in subs for r in by[s]]
    y = np.array([_f(r[a.outcome]) for r in rows])
    subj = np.array([r["subject"] for r in rows])
    Xa = np.array([[_f(r[EXPOSURE])] for r in rows])

    gates = {"G1_subjects": len(subs), "G1_rows": len(rows),
             "G1_pass": len(subs) >= MIN_SUBJECTS, "outcome": a.outcome}
    print(f"{len(subs)} subjects, {len(rows)} rows, outcome {a.outcome}")
    print(f"G1 coverage   {'PASS' if gates['G1_pass'] else 'FAIL'}")
    if not gates["G1_pass"]:
        json.dump({"gates": gates, "verdict": "REFUSED: coverage"}, open(a.out, "w"), indent=1)
        return 0

    def err(t, p):
        r = spearman(t, p)
        return 1.0 - r if np.isfinite(r) else float("nan")

    # ---- G2: is the MEASURED exposure alive? --------------------------------------------------------
    from bsde.verifier.stats import ridge_fit, _standardise
    uniq = np.unique(subj)
    idx = {u: np.flatnonzero(subj == u) for u in uniq}
    vals = []
    rng = np.random.default_rng(SEED)
    for _ in range(a.reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        ds = set(drawn.tolist())
        oob = [u for u in uniq if u not in ds]
        if len(oob) < 3:
            continue
        tr = np.concatenate([idx[u] for u in drawn])
        te = np.concatenate([idx[u] for u in oob])
        try:
            A, B = _standardise(Xa[tr], Xa[te])
            p = B @ ridge_fit(A, y[tr], 1.0)
        except Exception:                                                  # noqa: BLE001
            continue
        v = spearman(y[te], p)
        if np.isfinite(v):
            vals.append(v)
    rho = float(np.median(vals)) if vals else float("nan")
    gates["G2_exposure_oob_rho"] = rho
    gates["G2_n_reps_usable"] = len(vals)
    gates["G2_pass"] = bool(np.isfinite(rho) and rho > G2_RHO_FLOOR)
    print(f"G2 exposure   measured plasma propofol out-of-bag rho {rho:+.4f} "
          f"({len(vals)} usable reps)  {'PASS' if gates['G2_pass'] else 'FAIL'}")
    if not gates["G2_pass"]:
        json.dump({"gates": gates,
                   "verdict": "ABSENT -- the ASSAYED concentration does not predict behaviour out of "
                              "bag, so there is nothing for an EEG measure to add to. This is a "
                              "statement about the outcome, not about the EEG (rule 31)."},
                  open(a.out, "w"), indent=1)
        print("\nVERDICT: ABSENT -- exposure not alive")
        return 0

    # ---- P: increments -----------------------------------------------------------------------------
    results = {}
    for i, c in enumerate(cands):
        col = np.array([[_f(r.get(c, ""))] for r in rows])
        if not np.all(np.isfinite(col)) or np.unique(col).size < 3:
            results[c] = None
            continue
        m, lo, hi, nrep = oob_regression_increment(
            Xa, np.hstack([Xa, col]), y, subj, np.random.default_rng(SEED + 10 + i),
            stat=err, reps=a.reps)
        results[c] = {"mean": m, "lo": lo, "hi": hi, "n_reps": nrep}
    live = {c: v for c, v in results.items() if v and np.isfinite(v["lo"])}

    # BH over the live candidates, using the interval as the significance indicator.
    helps = [c for c, v in live.items() if v["hi"] < 0]
    hurts = [c for c, v in live.items() if v["lo"] > 0]
    for c, v in sorted(live.items(), key=lambda kv: kv[1]["mean"]):
        tag = "ADDS " if v["hi"] < 0 else ("HURTS" if v["lo"] > 0 else "  -  ")
        print(f"   {tag} {c:28s} {v['mean']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}]  reps={v['n_reps']}")

    # ---- G3 negative control -------------------------------------------------------------------------
    grng = np.random.default_rng(SEED + 999)
    gcol = grng.normal(size=(len(rows), 1))
    gm, glo, ghi, _ = oob_regression_increment(Xa, np.hstack([Xa, gcol]), y, subj,
                                               np.random.default_rng(SEED + 1000), stat=err, reps=a.reps)
    gates["G3_negative_control"] = {"mean": gm, "lo": glo, "hi": ghi}
    gates["G3_pass"] = bool(not (np.isfinite(ghi) and ghi < 0))
    print(f"G3 control    gaussian {gm:+.4f} [{glo:+.4f}, {ghi:+.4f}]  "
          f"{'PASS' if gates['G3_pass'] else 'FAIL'}")

    # ---- PLACEBO for anything that ADDS --------------------------------------------------------------
    placebo = {}
    prng = np.random.default_rng(SEED + 2)
    for c in helps:
        col = np.array([_f(r.get(c, "")) for r in rows])
        draws = []
        for _ in range(a.placebo_draws):
            sh = col.copy()
            for u in uniq:
                k = idx[u]
                sh[k] = prng.permutation(col[k])
            m, _l, _h, _n = oob_regression_increment(
                Xa, np.hstack([Xa, sh[:, None]]), y, subj,
                np.random.default_rng(SEED + 3), stat=err, reps=max(200, a.reps // 5))
            if np.isfinite(m):
                draws.append(float(m))
        d = np.asarray(draws, float)
        real = live[c]["mean"]
        frac = float(np.mean(d <= real)) if d.size else float("nan")
        placebo[c] = {"n": int(d.size), "mean": float(d.mean()) if d.size else float("nan"),
                      "p2.5": float(np.quantile(d, .025)) if d.size else float("nan"),
                      "p97.5": float(np.quantile(d, .975)) if d.size else float("nan"),
                      "frac_at_least_as_helpful": frac,
                      "beats": bool(np.isfinite(frac) and frac <= 0.05)}
        print(f"   PLACEBO {c}: real {real:+.4f} vs {placebo[c]['mean']:+.4f} "
              f"[{placebo[c]['p2.5']:+.4f}, {placebo[c]['p97.5']:+.4f}]  frac {frac:.3f}  "
              f"{'BEATS' if placebo[c]['beats'] else 'FAILS'}")

    survivors = [c for c in helps if placebo.get(c, {}).get("beats")]
    if hurts and not survivors:
        verdict = (f"(a) HURTS: {sorted(hurts)}; no candidate ADDS. Adding these makes out-of-bag "
                   "prediction WORSE over an ASSAYED concentration -- they are noise the model spends "
                   "capacity on, and this is not a null.")
    elif survivors:
        verdict = (f"(c) ADDS: {sorted(survivors)} over an ASSAYED plasma propofol concentration, "
                   f"surviving the within-subject permutation placebo, out of {len(live)} candidates "
                   f"tested. HURTS: {sorted(hurts)}. Because the exposure is measured rather than "
                   "modelled, this increment cannot be attributed to a mis-specified pharmacology -- the "
                   "most available objection to E122.")
    else:
        verdict = (f"(b) NO INCREMENT for any of {len(live)} candidates over an assayed plasma "
                   "concentration. The placebo is NOT INFORMATIVE (rule 48). "
                   "READ WITH THE REGISTERED ASYMMETRY: E122's positive used the DEPOSIT'S OWN shipped "
                   "index, and its P2 -- this project's 27 candidates against that index -- was entirely "
                   "null. chennu ships no vendor index, so a null here reproduces E122's P2 rather than "
                   "contradicting E122's P1, and must NOT be read as a failed replication of E122.")

    res = {"gates": gates, "n_candidates": len(live), "increments": results,
           "placebo": placebo, "verdict": verdict}
    json.dump(res, open(a.out, "w"), indent=1)
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
