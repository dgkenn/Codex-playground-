#!/usr/bin/env python3
"""E31 — is E30's cross-deposit sign reversal a DEPTH-RANGE effect, or a deposit artefact?

REGISTERED AFTER E30, whose result it exists to explain, and that is stated first. E30 found
`exponent_high` correlating with dose at **+0.710** in Chennu (sedation, no opioid) and **-0.126** in
VitalDB (surgical maintenance), with **six of seven comparable candidates flipping sign** between the two.
A reversal that near-universal is a property of the deposits, not of any feature, and E30 named three
possible causes: dose range, montage, sampling rate. **This file tests the first and only the first**,
because it is the one with a published shape behind it and the only one testable without re-extraction.

THE PUBLISHED SHAPE, verified through NCBI E-utilities and not WebFetch (rules 25, 39):

    Gugino LD, Chabot RJ, Prichep LS, John ER, Formanek V, Aglio LS. "Quantitative EEG changes associated
    with loss and return of consciousness in healthy adult volunteers anaesthetized with propofol or
    sevoflurane." Br J Anaesth 2001 Sep;87(3):421-8. PMID 11517126.

Its abstract states, verbatim: *"Light sedation was accompanied by decreased posterior alpha and increased
frontal/central beta power... With loss of consciousness, delta and theta power increased further in
anterior regions and also spread to posterior regions."* **So the EEG's response to a hypnotic is not
monotone in dose** — the fast end rises through light sedation and is overtaken by slowing at and beyond
loss of consciousness. Chennu sits entirely in the first regime (§9.16: the median subject still got 35 of
40 targets right at the deepest level) and VitalDB entirely in the second.

**AND THAT SAME PAPER IS THE MOST IMPORTANT PIECE OF PRIOR ART THIS PROGRAMME HAS FOUND.** Its stated goal
was *"to identify those changes that were sensitive to alterations in the state of consciousness but
independent of anaesthetic protocol"* — which is Challenge A, published in 2001, in volunteers, with two
drugs given in graded steps under a common protocol. Any claim this project makes about Challenge A has to
be positioned against it. That belongs in the plan, and is recorded there.

THE PREDICTION, AND ITS DIRECTION IS FIXED HERE BEFORE THE RUN. If depth range explains the reversal, then
**within the VitalDB arm alone** the association must move toward Chennu's positive value as the windows get
lighter. Depth is stratified by `BIS/SR`, the device's own suppression score, which is not a candidate, is
not the exposure, and was shown in E26 to be free of the EMG artefact that closed E22 (P(SR > 0) falls
across EMG deciles, Spearman -0.197).

    P1  MACHINERY GATE, no candidate. Both SR strata must contain at least `MIN_PATIENTS` patients with
        varying MAC (rule 32, fifth occurrence), and the strata must differ in depth by an independent
        measure — median BIS must be lower in the SR > 0 stratum, or the stratification is not a depth
        stratification and nothing below means anything.

    P2  THE PRIMARY, DIRECTIONAL. rho(exponent_high, MAC) computed within-subject in the SR == 0 stratum
        must be **greater than** in the SR > 0 stratum. Directional and pre-stated: a difference in the
        other direction refutes the depth-range explanation rather than supporting it in absolute value.

    P3  THE MAGNITUDE OF THE MOVE. How much of the gap between the two deposits (+0.710 against -0.126,
        a gap of 0.836) does the within-VitalDB stratification recover? Reported, not gated — an
        explanation that accounts for a tenth of the gap is a different claim from one that accounts for
        most of it, and the number should be stated rather than the direction alone.

    P4  THE PLACEBO, GATING (rule 34). The identical stratified comparison for rho(exponent_high,
        REMIFENTANIL). Remifentanil is not a hypnotic and has no reason to show a depth-range reversal, so
        if it moves as much as MAC does across the strata, the pattern is about the strata rather than
        about the drug and P2 is withdrawn.

    P5  THE OTHER CANDIDATES, reported. If depth range is the cause, the SAME stratified move should appear
        in the other five candidates that flipped in E30 — a shared cause should have a shared signature.
        Reported and not gated, because "most of them move the same way" is evidence and not a threshold.

    FALSIFICATION: P2's difference is zero or negative, or P4 fails. Either leaves montage and sampling
    rate as the surviving explanations, and both need re-extraction that the Cambridge TLS failure blocks
    for Chennu.

SCOPE AND LIMITS.
  * **This tests one of three explanations and cannot rank the other two.** A pass says depth range is
    sufficient to move the association; it does not say montage and Nyquist contribute nothing.
  * **VitalDB's whole MAC range is surgical.** Its "light" stratum is light *for an anaesthetised patient*,
    nowhere near Chennu's sedation. So the strongest possible result here is a move in the right direction
    over a fraction of the gap, never a full reconciliation.
  * **SR > 0 selects deeper windows and also older, sicker patients** who suppress more readily. The
    comparison is not within-patient across strata unless a patient supplies both, and the count that do is
    reported.
  * Dose is not consciousness; carried over from E25, E29 and E30.
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
from bsde.verifier.stats import (cluster_bootstrap_ci, n_evaluable_spearman,            # noqa: E402
                                 within_subject_spearman)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e31_depth_range_reversal.json")

PRIMARY = "exponent_high"
EMG_MAX = 35.0
MIN_POINTS = 4
MIN_DISTINCT = 3
MIN_PATIENTS = 20
CHENNU_RHO = 0.710          # E30, recorded so P3's gap is computed and not eyeballed
VITALDB_RHO = -0.126        # E30
FLIPPED = ("exponent_high", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
           "relative_delta_power", "whole_head_exponent", "relative_alpha_power")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main(argv=None) -> int:
    seed_registry()
    print("E31 — is E30's cross-deposit sign reversal a DEPTH-RANGE effect?")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    print("   Prior art fixing the predicted shape: Gugino 2001, Br J Anaesth, PMID 11517126.")
    if not (os.path.exists(GRID) and os.path.exists(AGENTS)):
        print("   *** inputs absent")
        return 2
    dose_by = {r["recording_id"]: r for r in csv.DictReader(open(AGENTS, newline=""))}
    rows = [r for r in csv.DictReader(open(GRID, newline=""))
            if r.get("status") == "ok" and r["recording_id"] in dose_by]
    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)                   # noqa: E731
    subj = np.array([r.get("subject", "") for r in rows])
    ap = np.array([r.get("meta_agents_present", "") for r in rows])
    off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    emg, sr, bis = col("meta_emg"), col("meta_sr"), col("meta_bis")
    mac = np.array([_f(dose_by[r["recording_id"]].get("mac", "")) for r in rows], float)
    rftn = np.array([_f(dose_by[r["recording_id"]].get("rftn_ce", "")) for r in rows], float)
    vol = np.array(["sevoflurane" in g or "desflurane" in g for g in ap])
    base = vol & ~off & np.isfinite(emg) & (emg <= EMG_MAX) & np.isfinite(mac) & np.isfinite(sr)
    strata = {"light (SR == 0)": base & (sr == 0.0), "deep (SR > 0)": base & (sr > 0.0)}
    rng = np.random.default_rng(20260730)

    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE: are these two strata, and are they strata of DEPTH?")
    print("=" * 100)
    x = col(PRIMARY)
    counts, med_bis = {}, {}
    for name, m in strata.items():
        mm = m & np.isfinite(x)
        counts[name] = n_evaluable_spearman(x[mm], mac[mm], subj[mm], MIN_POINTS, MIN_DISTINCT)
        med_bis[name] = float(np.nanmedian(bis[m])) if m.any() else float("nan")
        print(f"   {name:18s} rows {int(m.sum()):5d}   patients with varying MAC {counts[name]:4d}   "
              f"median BIS {med_bis[name]:5.1f}")
    both = len({s for s in subj[strata['light (SR == 0)']]} & {s for s in subj[strata['deep (SR > 0)']]})
    print(f"   patients contributing to BOTH strata: {both}")
    depth_ok = med_bis["deep (SR > 0)"] < med_bis["light (SR == 0)"]
    cov_ok = all(v >= MIN_PATIENTS for v in counts.values())
    p1 = bool(depth_ok and cov_ok)
    print(f"   BIS lower in the suppressed stratum: {depth_ok}   coverage: {cov_ok}   "
          f"-> P1 {'PASSED' if p1 else '*** FAILED'}")
    state = {"experiment": "E31", "p1": {"counts": counts, "median_bis": med_bis,
                                         "n_both": both, "passed": p1}}
    if not p1:
        print("\n   ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    def rho_in(mask, xx, zz):
        m = mask & np.isfinite(xx) & np.isfinite(zz)
        if n_evaluable_spearman(xx[m], zz[m], subj[m], MIN_POINTS, MIN_DISTINCT) < MIN_PATIENTS:
            return float("nan"), (float("nan"), float("nan"))
        r = within_subject_spearman(xx[m], zz[m], subj[m], MIN_POINTS, MIN_DISTINCT)
        lo, hi, _ = cluster_bootstrap_ci(
            lambda i: within_subject_spearman(xx[m][i], zz[m][i], subj[m][i], MIN_POINTS, MIN_DISTINCT),
            subj[m], rng, reps=2000)
        return r, (float(lo), float(hi))

    print("\n" + "=" * 100)
    print(f"P2 — PRIMARY, DIRECTIONAL: rho({PRIMARY}, MAC) must be GREATER in the light stratum")
    print("=" * 100)
    res = {}
    for name, m in strata.items():
        r, ci = rho_in(m, x, mac)
        res[name] = {"rho": r, "ci": list(ci)}
        print(f"   {name:18s} rho {r:+.3f}  [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    diff = res["light (SR == 0)"]["rho"] - res["deep (SR > 0)"]["rho"]
    p2 = bool(np.isfinite(diff) and diff > 0)
    print(f"\n   light - deep = {diff:+.3f}   P2 {'PASSED' if p2 else '*** FAILED'}")
    print("   Directional and pre-stated: a move the other way refutes the depth-range explanation.")
    state["p2"] = {"strata": res, "difference": float(diff), "passed": p2}

    print("\n" + "=" * 100)
    print("P3 — HOW MUCH OF THE CROSS-DEPOSIT GAP DOES THIS RECOVER? (reported, not gated)")
    print("=" * 100)
    gap = CHENNU_RHO - VITALDB_RHO
    frac = diff / gap if gap else float("nan")
    print(f"   E30's gap: Chennu {CHENNU_RHO:+.3f} - VitalDB {VITALDB_RHO:+.3f} = {gap:.3f}")
    print(f"   recovered within VitalDB by depth stratification: {diff:+.3f} = {frac:.1%} of it")
    print("   VitalDB's 'light' is light for an anaesthetised patient and nowhere near Chennu's sedation,")
    print("   so a fraction is the most this design can show, never a full reconciliation.")
    state["p3"] = {"gap": float(gap), "recovered": float(diff), "fraction": float(frac)}

    print("\n" + "=" * 100)
    print("P4 — PLACEBO GATE: remifentanil has no reason to show a depth-range reversal")
    print("=" * 100)
    rres = {}
    for name, m in strata.items():
        r, ci = rho_in(m, x, rftn)
        rres[name] = {"rho": r, "ci": list(ci)}
        print(f"   {name:18s} rho(exponent_high, remifentanil) {r:+.3f}  [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    rdiff = rres["light (SR == 0)"]["rho"] - rres["deep (SR > 0)"]["rho"]
    p4 = bool(np.isfinite(rdiff) and abs(rdiff) < abs(diff))
    print(f"\n   remifentanil light - deep = {rdiff:+.3f} against MAC's {diff:+.3f}")
    print(f"   P4 {'PASSED' if p4 else '*** FAILED — the pattern is about the strata, not the drug; P2 is WITHDRAWN'}")
    state["p4"] = {"strata": rres, "difference": float(rdiff), "passed": p4}

    print("\n" + "=" * 100)
    print("P5 — DO THE OTHER FLIPPED CANDIDATES MOVE THE SAME WAY? (reported, not gated)")
    print("=" * 100)
    print(f"   {'candidate':26s} {'light':>9s} {'deep':>9s} {'light-deep':>12s}")
    out5, moved = {}, 0
    for cname in FLIPPED:
        xc = col(cname)
        rl, _ = rho_in(strata["light (SR == 0)"], xc, mac)
        rd, _ = rho_in(strata["deep (SR > 0)"], xc, mac)
        if not (np.isfinite(rl) and np.isfinite(rd)):
            print(f"   {cname:26s} {'—':>9s} {'—':>9s} {'—':>12s}")
            continue
        out5[cname] = {"light": float(rl), "deep": float(rd), "diff": float(rl - rd)}
        moved += int((rl - rd) > 0)
        print(f"   {cname:26s} {rl:+9.3f} {rd:+9.3f} {rl - rd:+12.3f}")
    print(f"\n   {moved} of {len(out5)} move in the predicted direction. A shared cause should have a")
    print("   shared signature; this is evidence, not a threshold, and is not gated.")
    state["p5"] = {"per_candidate": out5, "n_moved": moved, "n_total": len(out5)}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not p4:
        print("   WITHDRAWN by the placebo: the stratified move is a property of the strata, not the drug.")
        verdict = "withdrawn_by_placebo"
    elif p2:
        print(f"   DEPTH RANGE IS PART OF THE ANSWER. Within VitalDB alone, moving from suppressed to")
        print(f"   unsuppressed windows shifts the dose association by {diff:+.3f}, {frac:.0%} of the gap")
        print("   to Chennu, in the direction Gugino 2001 predicts and not shown by remifentanil.")
        print("   It does NOT rule out montage or sampling rate, which need a re-extraction Chennu's TLS")
        print("   failure blocks.")
        verdict = "depth_range_supported"
    else:
        print("   REFUTED: the association does not move toward Chennu's value as the windows get lighter.")
        print("   Depth range is not the explanation, and montage and sampling rate survive as the two")
        print("   remaining candidates — neither testable without re-extraction.")
        verdict = "depth_range_refuted"
    state["verdict"] = verdict
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
