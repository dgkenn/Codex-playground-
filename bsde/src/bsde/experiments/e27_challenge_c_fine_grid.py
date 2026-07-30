#!/usr/bin/env python3
"""E27 — Challenge C again, at a 60 s grid: the retest E26 named for itself before it ran.

REGISTERED BEFORE `vitaldb_fine.csv` EXISTS, and before any candidate value from it has been read.

WHY THIS IS A RETEST AND NOT A SECOND BITE. E26 answered Challenge C in the negative and its scope note,
written before the run, named the binding limitation in advance:

    "**300 s grid.** The lead time is quantised to it, and a feature whose warning arrives 60 s ahead is
    indistinguishable here from one arriving 290 s ahead. A finer grid is a re-extraction."

Re-testing a limitation declared in advance is legitimate. Searching for a resolution at which the answer
flips is not, and the difference has to be visible in the code rather than asserted. **So this file is E26
with exactly two constants changed** — the input table and the horizon — and every prediction, gate,
statistic, threshold pair, placebo and primary is carried over unaltered. The horizon moves from 900 s to
`HORIZON_S` below for one reason: at a 300 s grid, 900 s was three windows, and at a 60 s grid the same
three-window horizon is 180 s. **Keeping 900 s would have changed the question from "three windows ahead"
to "fifteen windows ahead" while appearing to hold the design constant**, which is the subtler version of
the move this note exists to forbid. Both the 300 s / 900 s and the 60 s / 180 s pairs are three windows.

THE COHORT IS E26'S, NOT A NEW ONE. `vitaldb_fine_plan.json` names the same 81 cases E26 found eligible,
sampled every 60 s from 1,800 s before each case's first `BIS/SR > 0` window to 300 s after it. The plan
was built from the device's suppression score and the muscle filter, with no candidate column consulted.

IF THIS PASSES WHERE E26 FAILED, THE HONEST READING IS NARROW: the information exists but is short-lived,
arriving inside a window E26's sampling could not resolve. That is a finding about timescale, not a reversal
of E26 — E26's answer at 300 s stands, and both belong in any account of this work. **If it fails too, the
negative is substantially stronger**, because the pre-declared escape route will have been taken and found
empty.

Everything below — P1's muscle gate on the comparator, the two SR thresholds, the incumbent printed before
any candidate, the out-of-bag increment, the matched fake landmark, the lead time and the BIS + MAC
baseline — is E26's, unchanged. Its scope and limits apply here in full, with one removed: the grid is no
longer 300 s.
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
GRID = os.path.join(RESULTS, "vitaldb_fine.csv")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e27_challenge_c_fine_grid.json")

SR_THRESHOLDS = (0.0, 10.0)
"""Co-primary, both required. SR > 0 is the delirium literature's "any burst suppression"; SR >= 10 is the
common marker of substantial suppression. Requiring both removes a threshold choice rather than defending
one -- see P3's note on the ordering of what was known when."""
HORIZON_S = 180.0
"""Three windows, exactly as E26's 900 s was three of its 300 s windows. See the header: holding the
number constant instead of the window count would have silently changed the question."""
MIN_CLEAN_BEFORE = 2
MIN_PATIENTS = 25
BASE_RATE_BAND = (0.05, 0.95)
EMG_MAX = 35.0
PRIMARY = "exponent_high"
GATE_MIN_CASES = 75
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
    print("E27 — Challenge C at a 60 s grid: E26's pre-declared retest")
    print("   E26 answered NO at 300 s. This is the same design, same gates, same primary; only the")
    print("   sampling and the window-count-preserving horizon differ.")
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
    state = {"experiment": "E27", "horizon_s": HORIZON_S, "emg_max": EMG_MAX,
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
