#!/usr/bin/env python3
"""E26 — Discovery Challenge C: does the EEG see burst suppression coming before the monitor scores it?

REGISTERED BEFORE ANY CANDIDATE VALUE FROM `vitaldb_grid.csv` HAS BEEN READ. What has been read of that
table is BIS, SQI, SR, EMG and the window timings — the machinery columns, while closing E22 and while
checking this design's coverage. No candidate column has been read at any point, in this file or any other.

WHY CHALLENGE C NEEDED A NEW TRANSITION. E24 registered emergence as the transition and is BLOCKED, not
failed: its landmark was the first BIS >= 80 window, and every such window in this deposit is a facial-EMG
artefact (`scripts/diagnose_bis_high_windows.py`). Four windows in 250 cases sit after `aneend`. **VitalDB
captures maintenance and only maintenance**, so a transition for Challenge C has to be one that happens
*inside* maintenance.

Burst suppression is that transition, and it is a better one than emergence in three ways.

  1. **The comparator is the device's own score, not ours.** `BIS/SR` is the monitor's suppression ratio.
     Challenge C asks for a feature that is ahead of a conventional monitor; here the monitor's own output
     is the thing to be ahead of, and it is also the label, so there is no proxy step.
  2. **IT IS NOT THE ARTEFACT THAT KILLED E22, AND THAT WAS CHECKED BEFORE THIS FILE WAS WRITTEN.** Split by
     EMG decile, P(SR > 0) runs 41.0 %, 25.2 %, 15.0 %, 15.4 %, 15.7 %, 11.1 %, 11.4 %, 16.9 %, 10.9 %,
     6.0 % — **falling** with muscle activity, where P(BIS >= 80) rose from 0 % to 27.6 %. That is the
     physiologically correct direction: deep anaesthesia produces both suppression and low muscle tone. The
     comparator is clean in exactly the way the last one was not.
  3. **It is the clinically actionable one.** Intraoperative burst suppression is associated with
     postoperative delirium, and the response to seeing it coming — reduce the agent — is available to the
     anaesthetist in the moment. Emergence timing is a scheduling question; suppression is a harm question.

REGISTERED PREDICTIONS, evaluated in this order. A failed gate makes the downstream verdict ABSENT, not
negative (rule 31).

    P1  MACHINERY GATE, three parts, using no candidate.
        (a) **THE COMPARATOR MUST NOT BE MUSCLE.** P(SR > 0) must not RISE across EMG deciles — formally,
            the Spearman correlation between EMG and SR across eligible windows must not be positive. This
            re-runs, as a gate, the check that E22 lacked and died without. It is first because everything
            downstream is meaningless if it fails.
        (b) COVERAGE — at least `MIN_PATIENTS` patients must have a suppression onset preceded by at least
            `MIN_CLEAN_BEFORE` suppression-free windows, at EACH threshold below.
        (c) The base rate must sit inside `BASE_RATE_BAND`; outside it an AUC is uninterpretable.

    P2  THE BAR: what the monitor already knows. BIS alone predicting imminent suppression, out-of-fold with
        subject-level folds, **printed before any candidate** so that no candidate's absolute AUC can be
        presented without the incumbent's beside it.

    P3  THE PRIMARY, AT TWO THRESHOLDS, BOTH REQUIRED. `exponent_high` added to BIS must improve the
        out-of-bag AUC with a subject-clustered interval excluding zero, at **SR > 0** and at **SR >= 10**.
        Both, not either.
            **Why two, and the honest account of the ordering.** The perioperative-delirium literature
        conventionally scores "any burst suppression" as SR > 0, which makes it the defensible primary; 10 %
        is the commonly used marker of substantial suppression. Coverage at SR > 5 was measured before this
        file was written — 52 patients with an onset preceded by two clean windows — so a single threshold
        chosen now could be suspected of being chosen for coverage. Requiring BOTH removes the choice
        instead of defending it, and is strictly harder than either alone.

    P4  THE PLACEBO, AND IT GATES THE VERDICT (rule 34). A matched fake landmark: each patient's onset time
        replaced by another patient's relative onset position within their own eligible window span, so the
        label keeps the real one's time-in-case structure and loses its relation to suppression. Its
        increment must be SMALLER than the real one — a comparison against the real effect, never an
        absolute threshold (rule 37).

    P5  THE LEAD TIME, reported only if P3 and P4 both hold. Median time from a top-decile window to the
        actual onset. **An increment with no lead time is a statistical result and not a clinical one**, and
        at a 300 s grid the answer is quantised — this can distinguish "one window ahead" from "three", and
        nothing finer.

    P6  THE HARDER BASELINE, reported and not gating. BIS + MAC versus BIS + MAC + candidate, on the cases
        where `vitaldb_agents.csv` supplies MAC. The monitor and the vaporiser setting together are what an
        anaesthetist actually has, so an increment over BIS alone that vanishes once dose is included is a
        weaker result and should be visible as one.

    NOTE ON THE OTHER CANDIDATES IN THE TABLE. The primary is one pre-declared candidate, so the headline is
    one test. The rest are context with UNADJUSTED intervals and would have to pass
    `verifier/multiplicity.py` before becoming a claim. None is made here.

    FALSIFICATION: P3's interval includes zero at either threshold, or P4 fails. Either is a negative answer
    to Challenge C on this deposit, and a negative answer is a result.

SCOPE AND LIMITS, none of which a larger n repairs.
  * **`BIS/SR` is a proprietary algorithm's opinion, not ground truth suppression.** It is computed on the
    same two frontal electrodes as the candidates, so a candidate that predicts SR may be predicting the
    algorithm's behaviour rather than the brain's. The direction of that error is toward making the task
    EASIER, so a positive result here is weaker than it looks and a negative one is strong.
  * **300 s grid.** The lead time is quantised to it, and a feature whose warning arrives 60 s ahead is
    indistinguishable here from one arriving 290 s ahead. A finer grid is a re-extraction.
  * **Suppression-free windows are not evenly distributed.** Patients who suppress early contribute few
    eligible windows and patients who never suppress contribute none to the positive class, so the eligible
    set is selected on the outcome's timing. Reported, and it is why the base rate is gated rather than
    assumed.
  * **The muscle filter is applied, not merely reported** (`EMG <= 35`), carried forward from E25 for the
    same reason: the comparator is clean but a CANDIDATE can still be muscle-driven.
  * One site, one monitor, two frontal channels, 128 Hz; `exponent_gamma` is above Nyquist and `uce_v1`
    needs a posterior region this montage lacks.
  * Cases are taken in ascending case id, never selected by result.

--------------------------------------------------------------------------------------------------------
OUTCOME, ADDED AFTER THE RUN. **Challenge C is NOT MET on this deposit. P3 failed at both thresholds and
this is a genuine negative, not a blocked or absent one** — every gate passed and every section executed.

    P1  PASSED. Spearman EMG vs SR = **-0.197** over 5,798 live windows, with P(SR > 0) by EMG decile at
        41 % 25 % 15 % 15 % 16 % 11 % 11 % 17 % 11 % 6 %. The comparator falls with muscle where BIS rose,
        so the artefact that closed E22 is absent here. Coverage: 81 patients with an onset at SR > 0 (597
        eligible windows, base rate 26.1 %) and 33 at SR >= 10 (213 windows, 14.6 %).
    P2  The incumbent's bar: BIS alone reaches **AUC 0.583 [0.519, 0.645]** at SR > 0 and **0.449
        [0.321, 0.577]** at SR >= 10. Note the second interval spans 0.5 — over a 15-minute horizon the
        monitor's own index barely predicts substantial suppression either.
    P3  **FAILED.** `exponent_high` increments **-0.0021 [-0.1069, +0.0431]** at SR > 0 and **-0.0387
        [-0.3057, +0.1656]** at SR >= 10. Both intervals span zero and both point estimates are negative.
    P4  PASSED — the placebo incremented -0.0331 against the real -0.0021, so the machinery discriminates
        as designed. It is reported even though P3 failed, because a placebo that had FAILED here would
        have meant the harness was broken rather than the candidate silent.
    P6  The harder baseline agrees: over BIS + MAC the increment is -0.0069 [-0.0632, +0.0238] and
        -0.0187 [-0.2050, +0.1058].

**THE RESULT IS NOT ABOUT ONE CANDIDATE.** All ten reported candidates have negative point estimates at both
thresholds, and every interval spans zero. The one positive point estimate anywhere in the table is
`lempel_ziv` at +0.0278 [-0.0780, +0.1026] at SR > 0, which spans zero, does not survive at SR >= 10, and is
one cell of twenty — exactly the kind of look the header's multiplicity note exists to refuse. No claim is
made from it.

WHAT THIS DOES AND DOES NOT SAY.
  * It says that on 250 VitalDB cases, over a 15-minute horizon and a 300 s grid, **none of these
    representations sees burst suppression coming before the BIS monitor does.** For the anaesthesia wedge
    that is the commercially relevant question and the answer is no, on this deposit, at this resolution.
  * It does NOT say the information is absent from the EEG. A 300 s grid cannot express a warning that
    arrives 60 s ahead, and the horizon, the grid and the 30 s window were all fixed before the run rather
    than searched. **A finer grid is the obvious next test and it is a re-extraction, not a re-analysis.**
  * It does NOT generalise past this deposit. One site, one monitor, two frontal channels, and the label is
    a proprietary algorithm's own scoring.
  * The negative is the STRONG direction here, as the scope note said in advance: because the label is
    computed from the same electrodes as the candidates, the task is easier than the real one, and a
    candidate that cannot beat the monitor on the monitor's own definition is unlikely to beat it on
    ground truth.
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
                                 oob_auc_increment, spearman)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e26_challenge_c_suppression.json")

SR_THRESHOLDS = (0.0, 10.0)
"""Co-primary, both required. SR > 0 is the delirium literature's "any burst suppression"; SR >= 10 is the
common marker of substantial suppression. Requiring both removes a threshold choice rather than defending
one -- see P3's note on the ordering of what was known when."""
HORIZON_S = 900.0
MIN_CLEAN_BEFORE = 2
MIN_PATIENTS = 25
BASE_RATE_BAND = (0.05, 0.95)
EMG_MAX = 35.0
PRIMARY = "exponent_high"
GATE_MIN_CASES = 240
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
    print("     P1 GATE  the comparator must not be muscle (EMG-SR correlation not positive), plus")
    print(f"              >= {MIN_PATIENTS} patients with an onset at EACH threshold, base rate in "
          f"{BASE_RATE_BAND}")
    print("     P2       BIS ALONE predicting imminent suppression — the bar, printed before any candidate")
    print(f"     P3       {PRIMARY} added to BIS must increment at SR > 0 AND at SR >= 10, both intervals")
    print("              excluding zero")
    print("     P4 GATE  a matched fake landmark must increment LESS than the real one")
    print("     P5       lead time; P6 the harder BIS + MAC baseline, reported not gating")


def _onsets(subj, t_s, sr, eligible_base, thr):
    """Per patient: the first window at SR > thr, and the suppression-free windows that precede it.

    A patient qualifies only if that onset has at least MIN_CLEAN_BEFORE earlier windows at SR == 0, so
    there is a suppression-free run to predict from. Returns (onset_time_by_subject, eligible_mask).
    """
    onset, elig = {}, np.zeros(len(sr), bool)
    for s in np.unique(subj):
        k = np.flatnonzero((subj == s) & eligible_base)
        if k.size == 0:
            continue
        k = k[np.argsort(t_s[k])]
        hit = k[sr[k] > thr]
        if hit.size == 0:
            continue
        t0 = t_s[hit[0]]
        clean = k[(sr[k] == 0.0) & (t_s[k] < t0)]
        if clean.size < MIN_CLEAN_BEFORE:
            continue
        onset[s] = float(t0)
        elig[clean] = True
    return onset, elig


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    grid = os.path.abspath(args[args.index("--grid") + 1]) if "--grid" in args else GRID
    agents = os.path.abspath(args[args.index("--agents") + 1]) if "--agents" in args else AGENTS
    seed_registry()
    print("E26 — Challenge C: is the EEG ahead of the monitor at burst-suppression onset?")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    if not os.path.exists(grid):
        print(f"\n   *** {os.path.basename(grid)} absent.")
        _registered_order()
        return 2

    rows = [r for r in csv.DictReader(open(grid, newline="")) if r.get("status") == "ok"]
    n_cases = len({r.get("meta_caseid", "") for r in rows})
    if n_cases < GATE_MIN_CASES:
        print(f"\n   *** {n_cases} cases, below the registered floor of {GATE_MIN_CASES}. "
              "Nothing is reported.")
        _registered_order()
        return 2

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)          # noqa: E731
    subj = np.array([r.get("subject", "") for r in rows])
    t_s, bis, sr, emg = col("meta_t_s"), col("meta_bis"), col("meta_sr"), col("meta_emg")
    sensor_off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    live = ~sensor_off & np.isfinite(sr) & np.isfinite(bis) & np.isfinite(emg) & np.isfinite(t_s)
    base_mask = live & (emg <= EMG_MAX)
    rng = np.random.default_rng(20260730)

    print(f"\n   {len(rows)} decoded windows over {n_cases} cases, {len(set(subj))} patients")
    print(f"   with the monitor live and EMG <= {EMG_MAX:.0f}: {int(base_mask.sum())} windows, "
          f"{len(set(subj[base_mask]))} patients")

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (no candidate). (a) is the check E22 lacked, run first and as a GATE.")
    print("=" * 100)
    rho_emg = spearman(emg[live], sr[live])
    a_ok = np.isfinite(rho_emg) and rho_emg <= 0.0
    print(f"   (a) Spearman EMG vs SR over {int(live.sum())} live windows: {rho_emg:+.3f}   "
          f"{'PASSED — not muscle' if a_ok else '*** FAILED — the comparator rises with muscle, as BIS did'}")
    q = np.quantile(emg[live], np.linspace(0, 1, 11))
    cells = []
    for i in range(10):
        m = live & (emg >= q[i]) & ((emg <= q[i + 1]) if i == 9 else (emg < q[i + 1]))
        cells.append(float(np.mean(sr[m] > 0)) if m.any() else float("nan"))
    print("       P(SR>0) by EMG decile: " + " ".join(f"{c:.0%}" for c in cells))

    per_thr, cov_ok = {}, []
    for thr in SR_THRESHOLDS:
        onset, elig = _onsets(subj, t_s, sr, base_mask, thr)
        ttl = np.full(len(rows), np.nan)
        for i in np.flatnonzero(elig):
            ttl[i] = onset[subj[i]] - t_s[i]
        y = (ttl <= HORIZON_S).astype(float)
        base = float(y[elig].mean()) if elig.any() else float("nan")
        ok = (len(onset) >= MIN_PATIENTS and np.isfinite(base)
              and BASE_RATE_BAND[0] <= base <= BASE_RATE_BAND[1])
        cov_ok.append(ok)
        per_thr[thr] = {"onset": onset, "elig": elig, "ttl": ttl, "y": y, "base": base,
                        "n_patients": len(onset)}
        print(f"   (b,c) SR > {thr:4.1f}: {len(onset):4d} patients with an onset, "
              f"{int(elig.sum()):5d} eligible windows, base rate {base:6.1%}   "
              f"{'PASSED' if ok else '*** FAILED'}")
    p1 = bool(a_ok and all(cov_ok))
    print(f"\n   P1 {'PASSED' if p1 else '*** FAILED'}")
    state = {"experiment": "E26", "horizon_s": HORIZON_S, "emg_max": EMG_MAX,
             "p1": {"emg_sr_spearman": float(rho_emg), "p_sr_by_emg_decile": cells,
                    "per_threshold": {str(t): {"n_patients": d["n_patients"], "base_rate": d["base"]}
                                      for t, d in per_thr.items()},
                    "passed": p1}}
    if not p1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    # ------------------------------------------------------------------ P2
    print("\n" + "=" * 100)
    print("P2 — THE BAR: BIS ALONE predicting imminent suppression (out-of-fold, subject-level folds)")
    print("=" * 100)
    bars = {}
    for thr, d in per_thr.items():
        m = d["elig"] & np.isfinite(bis)
        p = cv_predict_proba(bis[m], d["y"][m], subj[m], rng)
        ok = np.isfinite(p)
        a = auc(d["y"][m][ok], p[ok])
        lo, hi, _ = cluster_bootstrap_ci(lambda i: auc(d["y"][m][ok][i], p[ok][i]),
                                         subj[m][ok], rng, reps=2000)
        bars[thr] = {"auc": float(a), "ci": [float(lo), float(hi)]}
        print(f"   SR > {thr:4.1f}: BIS alone AUC {a:.3f} [{lo:.3f}, {hi:.3f}] over {int(ok.sum())} "
              f"windows, {len(set(subj[m][ok]))} patients")
    print("   This is the incumbent's score, printed before any candidate.")
    state["p2"] = {str(t): v for t, v in bars.items()}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print(f"P3 — PRIMARY: does {PRIMARY} add to BIS? Required at BOTH thresholds (rule 9 out-of-bag)")
    print("=" * 100)
    incs, prim_ok = {}, []
    for thr, d in per_thr.items():
        print(f"\n   SR > {thr:4.1f}")
        print(f"   {'candidate':26s} {'rows':>6s} {'pats':>5s} {'increment':>10s} "
              f"{'95% OOB interval':>22s} {'reps':>5s}")
        for cname in (PRIMARY,) + tuple(c for c in REPORT if c != PRIMARY):
            xc = col(cname)
            m = d["elig"] & np.isfinite(bis) & np.isfinite(xc)
            if len(np.unique(d["y"][m])) < 2 or len(set(subj[m])) < MIN_PATIENTS:
                continue
            one = np.ones(int(m.sum()))
            inc, lo, hi, nrep = oob_auc_increment(
                np.column_stack([one, bis[m]]), np.column_stack([one, bis[m], xc[m]]),
                d["y"][m], subj[m], rng, reps=400)
            incs.setdefault(str(thr), {})[cname] = {"increment": inc, "ci": [lo, hi], "n_reps": nrep,
                                                    "n_rows": int(m.sum()),
                                                    "n_patients": len(set(subj[m]))}
            print(f"   {cname:26s} {int(m.sum()):6d} {len(set(subj[m])):5d} {inc:10.4f} "
                  f"{f'[{lo:+.4f}, {hi:+.4f}]':>22s} {nrep:5d}")
        p = incs.get(str(thr), {}).get(PRIMARY)
        prim_ok.append(bool(p and np.isfinite(p["ci"][0]) and p["ci"][0] > 0.0))
    p3 = bool(prim_ok and all(prim_ok))
    print(f"\n   P3 {'PASSED at BOTH thresholds' if p3 else '*** FAILED — it must hold at both, and does not'}")
    state["p3"] = {"increments": incs, "passed": p3}

    # ------------------------------------------------------------------ P4
    print("\n" + "=" * 100)
    print("P4 — PLACEBO GATE: a matched fake landmark must increment LESS than the real one")
    print("=" * 100)
    thr0 = SR_THRESHOLDS[0]
    d = per_thr[thr0]
    fracs, frac_by = [], {}
    for s, t0 in d["onset"].items():
        k = np.flatnonzero((subj == s) & d["elig"])
        if k.size:
            span = t_s[k].max() - t_s[k].min()
            frac_by[s] = (t0 - t_s[k].min()) / span if span > 0 else 1.0
    fracs = np.array(list(frac_by.values()), float)
    shuffled = rng.permutation(fracs)
    fake_y = np.zeros(len(rows))
    for j, s in enumerate(sorted(frac_by)):
        k = np.flatnonzero((subj == s) & d["elig"])
        if not k.size:
            continue
        lo_t, hi_t = t_s[k].min(), t_s[k].max()
        span = hi_t - lo_t if hi_t > lo_t else 1.0
        fake_t = lo_t + shuffled[j % len(shuffled)] * span
        fake_y[k] = ((fake_t - t_s[k]) <= HORIZON_S) & ((fake_t - t_s[k]) >= 0)
    xc = col(PRIMARY)
    m = d["elig"] & np.isfinite(bis) & np.isfinite(xc)
    real = incs.get(str(thr0), {}).get(PRIMARY, {})
    print(f"   fake-landmark base rate {float(fake_y[d['elig']].mean()):.1%} against the real "
          f"{d['base']:.1%}")
    if len(np.unique(fake_y[m])) < 2 or not real:
        print("   the fake label is degenerate — P4 is ABSENT, so P3 is UNGATED and provisional (rule 31)")
        p4 = None
        state["p4"] = {"passed": None, "reason": "degenerate fake label"}
    else:
        one = np.ones(int(m.sum()))
        f_inc, f_lo, f_hi, f_n = oob_auc_increment(
            np.column_stack([one, bis[m]]), np.column_stack([one, bis[m], xc[m]]),
            fake_y[m], subj[m], rng, reps=400)
        print(f"   placebo increment {f_inc:+.4f} [{f_lo:+.4f}, {f_hi:+.4f}] over {f_n} reps")
        print(f"   real    increment {real['increment']:+.4f} "
              f"[{real['ci'][0]:+.4f}, {real['ci'][1]:+.4f}]")
        p4 = bool(np.isfinite(f_inc) and np.isfinite(real["increment"])
                  and f_inc < real["increment"])
        print(f"\n   P4 {'PASSED' if p4 else '*** FAILED — P3 is WITHDRAWN: the increment is time-in-case'}")
        state["p4"] = {"placebo_increment": float(f_inc), "real_increment": float(real["increment"]),
                       "passed": p4}

    # ------------------------------------------------------------------ P5
    print("\n" + "=" * 100)
    print("P5 — LEAD TIME (reported only if P3 passed and P4 did not withdraw it)")
    print("=" * 100)
    if not (p3 and p4):
        print("   Not reported: an increment that failed or was withdrawn has no lead time to describe.")
        state["p5"] = {"reported": False}
    else:
        p_c = cv_predict_proba(xc[m], d["y"][m], subj[m], rng)
        okc = np.isfinite(p_c)
        top = okc & (p_c >= np.quantile(p_c[okc], 0.90))
        lead = d["ttl"][m][top]
        lead = lead[np.isfinite(lead)]
        med = float(np.median(lead)) if lead.size else float("nan")
        print(f"   top-decile windows {int(top.sum())}; median time to actual onset {med:.0f} s "
              f"({med / 60:.1f} min), quantised to the 300 s grid")
        state["p5"] = {"reported": True, "median_lead_s": med, "n_top_decile": int(top.sum())}

    # ------------------------------------------------------------------ P6
    print("\n" + "=" * 100)
    print("P6 — HARDER BASELINE: BIS + MAC vs BIS + MAC + candidate (reported, not gating)")
    print("=" * 100)
    if not os.path.exists(agents):
        print(f"   {os.path.basename(agents)} absent — the dose join has not produced it. ABSENT, not a")
        print("   negative result: this says nothing about whether the increment survives dose adjustment.")
        state["p6"] = {"reported": False, "reason": "agents table absent"}
    else:
        dose_by = {r["recording_id"]: r for r in csv.DictReader(open(agents, newline=""))}
        mac = np.array([_f(dose_by.get(r["recording_id"], {}).get("mac", "")) for r in rows], float)
        out6 = {}
        for thr, dd in per_thr.items():
            mm = dd["elig"] & np.isfinite(bis) & np.isfinite(xc) & np.isfinite(mac)
            if len(np.unique(dd["y"][mm])) < 2 or len(set(subj[mm])) < MIN_PATIENTS:
                print(f"   SR > {thr:4.1f}: too few patients with MAC; not reported")
                continue
            one = np.ones(int(mm.sum()))
            inc, lo, hi, nrep = oob_auc_increment(
                np.column_stack([one, bis[mm], mac[mm]]),
                np.column_stack([one, bis[mm], mac[mm], xc[mm]]),
                dd["y"][mm], subj[mm], rng, reps=400)
            out6[str(thr)] = {"increment": inc, "ci": [lo, hi], "n_patients": len(set(subj[mm]))}
            print(f"   SR > {thr:4.1f}: increment over BIS+MAC {inc:+.4f} [{lo:+.4f}, {hi:+.4f}] "
                  f"({len(set(subj[mm]))} patients)")
        state["p6"] = {"reported": True, "per_threshold": out6}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p4 is False:
        print("   Challenge C is NOT met: the increment survives a fake landmark, so it reads time-in-case.")
        verdict = "withdrawn_by_placebo"
    elif p4 is None:
        print("   UNGATED — the placebo could not be evaluated, so P3 is provisional (rule 31).")
        verdict = "ungated"
    elif p3:
        print("   Challenge C is MET on this deposit: before the monitor scores any suppression, the EEG")
        print("   carries information about imminent suppression that the monitor's own index does not,")
        print("   at both thresholds and against a matched fake landmark. One site, one monitor, the")
        print("   device's own scoring as the label, and a 300 s grid — a first pass, not a settled answer.")
        verdict = "met"
    else:
        print("   Challenge C is NOT met: the candidate adds nothing to BIS at both thresholds. That is a")
        print("   result, and it says the index on the screen already uses what is there.")
        verdict = "no_increment"
    state["verdict"] = verdict
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
