#!/usr/bin/env python3
"""E24 — Discovery Challenge C: does the EEG know emergence is coming while the monitor still says deep?

REGISTERED BEFORE ANY CANDIDATE VALUE FROM `vitaldb_grid.csv` HAS BEEN READ, and before E22 or E23 has been
run on real labels. Only E22's permuted smoke run has executed and it reports nothing about the association.

CHALLENGE C, in Brief 03's words: *a trajectory feature that predicts a transition AHEAD of a conventional
monitor.* §5 and §9.22 recorded it as blocked since the plan was written, for want of a deposit carrying
both raw EEG and a monitor to be ahead of. VitalDB carries `BIS/EEG1_WAV` and `BIS/BIS` on the same strip,
so the challenge becomes answerable without new extraction: the table E22 reads already has everything.

THE QUESTION, MADE PRECISE. Restrict to windows where the monitor says the patient is deep (BIS <= 60).
Among those, ask whether emergence — the first window at BIS >= 80 — arrives within the next `HORIZON_S`
seconds. The monitor's own current reading is the thing to beat, and it is given every advantage: it enters
the comparison as a covariate, not as a straw man.

    A candidate is "ahead of the monitor" if adding it to a model containing BIS improves out-of-bag
    discrimination of imminent emergence.

WHY THIS IS THE COMMERCIALLY MEANINGFUL FORM OF THE CHALLENGE, stated once and not repeated: an
anaesthetist's operational question at the end of a case is *when will this patient wake*, and the index on
the screen answers *how deep is this patient now*. Those are different questions and only the first has
theatre-turnover value. That is the wedge, and this experiment is the first test of whether the wedge exists.

REGISTERED PREDICTIONS, evaluated in this order. A failed gate makes the downstream verdict ABSENT, not
negative (rule 31).

    P1  MACHINERY GATE, using the clinical record only — no EEG, no candidate.
        (a) At least `MIN_PATIENTS` patients have an identifiable emergence: a first BIS >= 80 window that
            is preceded by at least two BIS <= 60 windows, so there is something to predict from.
        (b) The outcome must not be degenerate: between 10 % and 90 % of eligible deep windows must be
            within the horizon. A base rate outside that makes an AUC uninterpretable and is a coverage
            failure, not a result.

    P2  THE MONITOR'S OWN PERFORMANCE, reported first and deliberately so. BIS alone predicting imminent
        emergence, out-of-bag with subject-level folds. **This number is the bar.** Reporting it before any
        candidate makes it impossible to present a candidate's absolute AUC as impressive without saying
        what the incumbent scores.

    P3  THE PRIMARY. `exponent_high` added to BIS must improve the out-of-bag AUC, with a subject-clustered
        out-of-bag interval excluding zero. The increment is computed by resampling SUBJECTS, refitting both
        models on the drawn subjects, and evaluating both on the subjects NOT drawn — error-catalogue rule 9,
        which was paid for twice in the sibling project by bootstrapping fixed out-of-fold predictions
        (too narrow) and by refitting and evaluating on the same resample (too optimistic).

    P4  THE PLACEBO, AND IT GATES THE VERDICT (rule 34). The identical pipeline with the horizon label
        replaced by a **matched fake landmark**: for each patient, a time drawn to have the same distribution
        of position-within-the-deep-phase as the real emergence, but unrelated to BIS crossing 80. Its
        increment must be smaller than P3's. **If the placebo increments as much, the model is reading
        time-in-case and P3 is withdrawn.** R410 is why this gates rather than sits beside: a primary that
        passed every pairwise comparison was meaningless because the same statistic fired at an arbitrary
        day where no guideline acts.

    P5  THE LEAD TIME, reported only if P3 passes. Among windows the candidate-augmented model ranks in its
        top decile, the median time to actual emergence. **An increment with no lead time is a statistical
        result and not a clinical one**, and rule 15's sibling applies: discrimination without a usable
        horizon is half a result, and the missing half is the half an anaesthetist would use.

    NOTE ON THE OTHER CANDIDATES IN THE TABLES BELOW, added at registration and before any value
    was read. The primary is ONE pre-declared candidate, so the headline is one test. Every other
    candidate is printed for CONTEXT and its interval is UNADJUSTED — reading a claim out of the
    best of them is a look at the whole family, and `verifier/multiplicity.py` (layer 2's
    correction: Holm, Benjamini-Hochberg, and a Westfall-Young max-T that uses the observed
    correlation between candidates rather than assuming independence) is what such a claim would
    have to go through first. None is made here.

    FALSIFICATION: P3's interval includes zero, or P4 fails. Either is a negative answer to Challenge C on
    this deposit, and a negative answer is a result.

SCOPE AND LIMITS, none of which a larger n repairs.
  * **`BIS >= 80` is a proxy for emergence, not emergence.** VitalDB marks no return of consciousness. The
    proxy is applied identically in every arm and to the placebo, so it costs power rather than validity —
    but a patient whose strip came off before they woke contributes no landmark at all, and that exclusion
    is reported and is NOT random (see below).
  * **A 300 s grid bounds the resolution.** Nothing here can distinguish a 60 s lead from a 200 s one, and
    the reported lead time is quantised to the grid. A finer grid is a re-extraction, not a re-analysis.
  * **The landmark exclusion is outcome-related.** Decode failures cluster at the end of the case, and so do
    detached sensors, so patients with a clean emergence landmark are those whose monitoring continued
    through it. That correlates with case length and with practice. Reported per drug group.
  * **BIS is not a neutral incumbent.** It is a proprietary index on the same electrodes, tuned for depth
    rather than for prediction, so beating it at prediction is a weaker claim than beating a purpose-built
    forecaster. It is nonetheless the thing on the screen, which is what the challenge names.
  * One site, one monitor, two frontal channels, 128 Hz — `exponent_gamma` is above Nyquist and `uce_v1`
    needs a posterior region this montage does not have.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                          # noqa: E402
from bsde.candidates.seed import seed_registry                                          # noqa: E402
from bsde.verifier.stats import (auc, cluster_bootstrap_ci, cv_predict_proba,           # noqa: E402
                                 oob_auc_increment)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e24_challenge_c.json")

BIS_DEEP_MAX = 60.0
BIS_EMERGED_MIN = 80.0
HORIZON_S = 900.0
"""Three grid steps. Chosen as the shortest horizon the 300 s grid can express with more than one step of
resolution, and fixed before any result — a horizon tuned afterwards would be a free parameter."""
MIN_DEEP_BEFORE = 2
MIN_PATIENTS = 20
BASE_RATE_BAND = (0.10, 0.90)
PRIMARY = "exponent_high"
GATE_MIN_ROWS = 1500
REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "multiscale_entropy_slope", "critical_slowing_ar1")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _registered_order() -> None:
    print("   Registered order of evaluation, fixed here and not re-openable:")
    print(f"     P1 GATE  >= {MIN_PATIENTS} patients with an identifiable emergence, and a base rate "
          f"inside {BASE_RATE_BAND}")
    print("     P2       BIS ALONE predicting imminent emergence — the bar, reported before any candidate")
    print(f"     P3       {PRIMARY} added to BIS must improve out-of-bag AUC, interval excluding zero")
    print("     P4 GATE  matched fake landmark must increment LESS than the real one")
    print("     P5       lead time in the top decile — an increment with no lead time is not clinical")


def _landmarks(rows, subj, t_s, bis, sensor_off):
    """Per patient: the time of the first BIS >= 80 window, and the deep windows that precede it.

    A patient qualifies only if that window has at least MIN_DEEP_BEFORE earlier BIS <= 60 windows, so there
    is a deep phase to predict from. Returns (landmark_time_by_subject, eligible_row_mask).
    """
    land, elig = {}, np.zeros(len(rows), bool)
    for s in np.unique(subj):
        k = np.flatnonzero((subj == s) & ~sensor_off & np.isfinite(bis) & np.isfinite(t_s))
        if k.size == 0:
            continue
        k = k[np.argsort(t_s[k])]
        emerged = k[bis[k] >= BIS_EMERGED_MIN]
        if emerged.size == 0:
            continue
        t0 = t_s[emerged[0]]
        deep = k[(bis[k] <= BIS_DEEP_MAX) & (t_s[k] < t0)]
        if deep.size < MIN_DEEP_BEFORE:
            continue
        land[s] = float(t0)
        elig[deep] = True
    return land, elig


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    table = os.path.abspath(args[args.index("--table") + 1]) if "--table" in args else TABLE
    seed_registry()
    print("E24 — Challenge C: is the EEG ahead of the monitor at emergence?")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    if not os.path.exists(table):
        print(f"\n   *** {os.path.basename(table)} absent — the VitalDB grid stream has not produced it.")
        _registered_order()
        return 2

    rows = [r for r in csv.DictReader(open(table, newline="")) if r.get("status") == "ok"]
    if len(rows) < GATE_MIN_ROWS:
        print(f"\n   *** {os.path.basename(table)} holds {len(rows)} usable rows, below the registered "
              f"floor of {GATE_MIN_ROWS}. Nothing is reported.")
        _registered_order()
        return 2

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)          # noqa: E731
    subj = np.array([r.get("subject", "") for r in rows])
    agents = np.array([r.get("meta_agents_present", "") for r in rows])
    t_s, bis = col("meta_t_s"), col("meta_bis")
    sensor_off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    rng = np.random.default_rng(20260730)

    land, elig = _landmarks(rows, subj, t_s, bis, sensor_off)
    ttl = np.full(len(rows), np.nan)
    for i in np.flatnonzero(elig):
        ttl[i] = land[subj[i]] - t_s[i]
    y = (ttl <= HORIZON_S).astype(float)

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (clinical record only: no EEG, no candidate)")
    print("=" * 100)
    n_pat_total = len(set(subj))
    n_pat = len(land)
    base = float(y[elig].mean()) if elig.any() else float("nan")
    print(f"   patients in the table                          : {n_pat_total}")
    print(f"   with an identifiable emergence landmark        : {n_pat}  "
          f"({n_pat / max(1, n_pat_total):.0%})")
    print(f"   eligible deep windows                          : {int(elig.sum())}")
    print(f"   base rate (within {HORIZON_S:.0f} s of emergence)        : {base:.1%}")
    for a in ("propofol", "sevoflurane", "desflurane"):
        tot = len({s for s, g in zip(subj, agents) if a in g})
        got = len({s for s in land if a in set(agents[subj == s])})
        print(f"      {a:12s} landmark in {got:4d} of {tot:4d} patients "
              f"({got / tot if tot else float('nan'):6.1%})")
    print("   (the landmark exclusion is outcome-related — sensors come off around emergence — so a")
    print("    difference between groups here is a confound for any cross-drug reading, rule 14)")
    p1 = bool(n_pat >= MIN_PATIENTS and np.isfinite(base)
              and BASE_RATE_BAND[0] <= base <= BASE_RATE_BAND[1])
    print(f"\n   P1 {'PASSED' if p1 else '*** FAILED'}")
    state = {"experiment": "E24", "table": os.path.basename(table), "horizon_s": HORIZON_S,
             "p1": {"n_patients_total": n_pat_total, "n_with_landmark": n_pat,
                    "n_eligible_windows": int(elig.sum()), "base_rate": base, "passed": p1}}
    if not p1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    # ------------------------------------------------------------------ P2
    print("\n" + "=" * 100)
    print("P2 — THE BAR: BIS ALONE predicting imminent emergence (out-of-fold, subject-level folds)")
    print("=" * 100)
    m = elig & np.isfinite(bis)
    p_bis = cv_predict_proba(bis[m], y[m], subj[m], rng)
    ok = np.isfinite(p_bis)
    bis_auc = auc(y[m][ok], p_bis[ok])
    lo, hi, _ = cluster_bootstrap_ci(lambda i: auc(y[m][ok][i], p_bis[ok][i]), subj[m][ok], rng, reps=2000)
    print(f"   BIS alone: AUC {bis_auc:.3f}  [{lo:.3f}, {hi:.3f}]  over {int(ok.sum())} windows, "
          f"{len(set(subj[m][ok]))} patients")
    print("   This is the incumbent's score and it is printed before any candidate, so no candidate's")
    print("   absolute AUC can be presented as impressive without it.")
    state["p2"] = {"bis_auc": float(bis_auc), "ci": [float(lo), float(hi)]}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print(f"P3 — PRIMARY: does {PRIMARY} add to BIS, out-of-bag? (rule 9: refit per resample, score OOB)")
    print("=" * 100)
    print(f"   {'candidate':26s} {'rows':>6s} {'pats':>5s} {'increment':>10s} {'95% OOB interval':>22s} "
          f"{'reps':>5s}")
    incs = {}
    for cname in (PRIMARY,) + tuple(c for c in REPORT if c != PRIMARY):
        xc = col(cname)
        mm = elig & np.isfinite(bis) & np.isfinite(xc)
        if len(np.unique(y[mm])) < 2 or len(set(subj[mm])) < MIN_PATIENTS:
            continue
        one = np.ones(int(mm.sum()))
        Xa = np.column_stack([one, bis[mm]])
        Xb = np.column_stack([one, bis[mm], xc[mm]])
        inc, ilo, ihi, nrep = oob_auc_increment(Xa, Xb, y[mm], subj[mm], rng, reps=400)
        incs[cname] = {"increment": inc, "ci": [ilo, ihi], "n_reps": nrep,
                       "n_rows": int(mm.sum()), "n_patients": len(set(subj[mm]))}
        print(f"   {cname:26s} {int(mm.sum()):6d} {len(set(subj[mm])):5d} {inc:10.4f} "
              f"{f'[{ilo:+.4f}, {ihi:+.4f}]':>22s} {nrep:5d}")
    prim = incs.get(PRIMARY)
    p3 = bool(prim and np.isfinite(prim["ci"][0]) and prim["ci"][0] > 0.0)
    print(f"\n   P3 {'PASSED' if p3 else '*** FAILED'}"
          + ("" if prim else " — the primary was not evaluable"))
    state["p3"] = {"increments": incs, "passed": p3}

    # ------------------------------------------------------------------ P4
    print("\n" + "=" * 100)
    print("P4 — PLACEBO GATE: a matched fake landmark must increment LESS than the real one")
    print("=" * 100)
    print("   Each patient's fake landmark sits at the same RELATIVE position within their deep phase as")
    print("   some other patient's real one, so the label keeps the real one's time-in-case structure and")
    print("   loses its relation to BIS crossing 80. If the increment survives that, the model is reading")
    print("   time-in-case rather than approaching emergence.")
    frac_by_subj = {}
    for s, t0 in land.items():
        k = np.flatnonzero((subj == s) & elig)
        if k.size:
            span = t_s[k].max() - t_s[k].min()
            frac_by_subj[s] = (t0 - t_s[k].min()) / span if span > 0 else 1.0
    fracs = np.array(list(frac_by_subj.values()), float)
    fake_y = np.zeros(len(rows))
    shuffled = rng.permutation(fracs)
    for j, s in enumerate(sorted(frac_by_subj)):
        k = np.flatnonzero((subj == s) & elig)
        if not k.size:
            continue
        lo_t, hi_t = t_s[k].min(), t_s[k].max()
        span = hi_t - lo_t
        fake_t = lo_t + shuffled[j % len(shuffled)] * (span if span > 0 else 1.0)
        fake_y[k] = ((fake_t - t_s[k]) <= HORIZON_S) & ((fake_t - t_s[k]) >= 0)
    fake_base = float(fake_y[elig].mean())
    print(f"\n   fake-landmark base rate {fake_base:.1%} against the real {base:.1%}")
    xc = col(PRIMARY)
    mm = elig & np.isfinite(bis) & np.isfinite(xc)
    if len(np.unique(fake_y[mm])) < 2:
        print("   the fake label is degenerate — P4 is ABSENT, so P3 is UNGATED and provisional (rule 31)")
        p4 = None
    else:
        one = np.ones(int(mm.sum()))
        f_inc, f_lo, f_hi, f_n = oob_auc_increment(
            np.column_stack([one, bis[mm]]), np.column_stack([one, bis[mm], xc[mm]]),
            fake_y[mm], subj[mm], rng, reps=400)
        print(f"   placebo increment {f_inc:+.4f} [{f_lo:+.4f}, {f_hi:+.4f}] over {f_n} reps")
        print(f"   real    increment {prim['increment']:+.4f} "
              f"[{prim['ci'][0]:+.4f}, {prim['ci'][1]:+.4f}]")
        # A COMPARISON against the real effect, never an absolute threshold -- rule 37, which was paid for
        # by a placebo check that asked whether the placebo attenuated "a lot" instead of "more than the
        # variable of interest".
        p4 = bool(np.isfinite(f_inc) and np.isfinite(prim["increment"]) and f_inc < prim["increment"])
        print(f"\n   P4 {'PASSED' if p4 else '*** FAILED — P3 is WITHDRAWN: the increment is time-in-case'}")
    state["p4"] = {"fake_base_rate": fake_base,
                   "placebo_increment": None if p4 is None else float(f_inc), "passed": p4}

    # ------------------------------------------------------------------ P5
    print("\n" + "=" * 100)
    print("P5 — LEAD TIME (reported only if P3 passed and P4 did not withdraw it)")
    print("=" * 100)
    if not (p3 and p4):
        print("   Not reported: an increment that failed or was withdrawn has no lead time to describe.")
        state["p5"] = {"reported": False}
    else:
        p_full = cv_predict_proba(xc[mm], y[mm], subj[mm], rng)   # candidate alone, for the ranking
        okf = np.isfinite(p_full)
        thr = np.quantile(p_full[okf], 0.90)
        top = okf & (p_full >= thr)
        lead = ttl[mm][top]
        lead = lead[np.isfinite(lead)]
        med = float(np.median(lead)) if lead.size else float("nan")
        print(f"   top-decile windows {int(top.sum())}; median time to actual emergence {med:.0f} s "
              f"({med / 60:.1f} min)")
        print(f"   NOTE: quantised to the {300:.0f} s grid — this cannot distinguish a 60 s lead from 200 s.")
        state["p5"] = {"reported": True, "median_lead_s": med, "n_top_decile": int(top.sum())}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p4 is False:
        print("   Challenge C is NOT met: the increment survives a fake landmark, so it reads time-in-case.")
        state["verdict"] = "withdrawn_by_placebo"
    elif p4 is None:
        print("   UNGATED — the placebo could not be evaluated, so P3 is provisional (rule 31).")
        state["verdict"] = "ungated"
    elif p3:
        print("   Challenge C is MET on this deposit: while the monitor still reads deep, the EEG carries")
        print("   information about imminent emergence that the monitor does not. One site, one monitor,")
        print("   a proxy landmark and a 300 s grid — a first pass, not a settled answer.")
        state["verdict"] = "met"
    else:
        print("   Challenge C is NOT met: the candidate adds nothing to BIS. That is a result, and it is")
        print("   the one that says the index on the screen is already using what is there.")
        state["verdict"] = "no_increment"
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
