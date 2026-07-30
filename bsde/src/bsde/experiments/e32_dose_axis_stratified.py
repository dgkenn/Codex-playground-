#!/usr/bin/env python3
"""E32 - the same question as E31, with the standard instrument: stratify on the DOSE AXIS itself.

REGISTERED AFTER E31 FAILED ITS COVERAGE GATE, and the ordering is stated because it matters. E31 asked
whether E30's cross-deposit sign reversal is a depth-range effect, stratifying depth by the device's
suppression score. Its depth check passed - median BIS 35.8 in the suppressed stratum against 43.3 - but
only **19 of 110** volatile patients both suppress and have a varying MAC, one short of the floor, which was
not lowered.

**The instrument here is not a weaker version of E31's; it is the standard one for the question.** The claim
under test is that the dose-response is NON-LINEAR - rising through light sedation, falling past loss of
consciousness (Gugino 2001, Br J Anaesth, PMID 11517126, verified via NCBI E-utilities). The textbook test
for a non-linear dose-response is to stratify **on the dose axis** and ask whether the slope depends on
where along it you are. That needs no second variable, uses every patient, and asks the question directly
rather than through a proxy. That it also has better coverage than E31 is a consequence and not the motive,
and E31 records the same ordering so a reader can judge it.

THE PREDICTION, FIXED BEFORE THE RUN. Within the VitalDB volatile arm, split windows at the cohort's MAC
terciles. If the Gugino shape explains E30, the within-subject rho between `exponent_high` and MAC must be
**more positive in the LOW-MAC tercile than in the HIGH-MAC tercile** - moving toward Chennu's +0.710 as the
anaesthetic lightens. A move in the other direction refutes it.

    P1  MACHINERY GATE, no candidate: at least `MIN_PATIENTS` patients with varying MAC in the low and high
        terciles, and the terciles separated in MAC by at least `MIN_TERCILE_GAP`, so they are different
        doses and not three slices of one value (rule 32, fifth occurrence in this project).
    P2  PRIMARY, DIRECTIONAL: rho(low tercile) > rho(high tercile).
    P3  How much of E30's cross-deposit gap does this recover? Reported, not gated.
    P4  PLACEBO, GATING: the identical stratified comparison for remifentanil, which is not a hypnotic and
        has no reason to show a dose-range reversal. A comparison against the real effect (rule 37).
    P5  Do the other candidates that flipped in E30 move the same way? Reported, not gated. A shared cause
        should have a shared signature.

    FALSIFICATION: P2's difference is zero or negative, or P4 fails.

SCOPE. Every limit from E31 applies. Two are specific to this instrument. **Stratifying on the exposure
narrows the dose range inside each stratum**, which attenuates every within-stratum correlation toward zero
and makes this a conservative test of a DIFFERENCE between strata. And VitalDB's whole MAC range is
surgical, so its "low" tercile is light for an anaesthetised patient and nowhere near Chennu's sedation - a
fraction of the gap is the most this can show.

--------------------------------------------------------------------------------------------------------
OUTCOME: P1 FAILED, AND IT FAILED BY EXPOSING A DEFECT IN THREE EARLIER EXPERIMENTS.

    low MAC tercile    2,194 rows   **0** patients with varying MAC   median MAC **0.00**
    high MAC tercile   1,689 rows   89 patients with varying MAC      median MAC 1.00

The tercile split is degenerate because **the bottom third of the volatile arm is MAC = 0** — windows where
the vaporiser was not delivering anything. `meta_agents_present` records which agent TRACKS a case carries,
not whether the agent was flowing at that moment, and a volatile is off for long stretches of a case that
nonetheless has a sevoflurane track.

**MEASURED: 2,199 of the 4,379 volatile-arm windows used by E25, E29 and E30 have MAC = 0. Half the arm.**
The MAC quartiles across that arm are 0.00 / 0.00 / 0.00 / 0.92 / 2.68.

**THIS PROPAGATES BACKWARD AND IS RECORDED AS A CORRECTION, NOT A CURIOSITY** (rule 1: a correction reaches
everything downstream of the definition, not only the number that exposed it).

  * **E30's volatile arm** was a contrast spanning "no volatile" to "full volatile", inside cases where
    propofol was frequently also running. It is not a clean volatile-dose axis. Recomputed on MAC > 0
    windows only, its rho moves from **-0.126 to -0.167** over 98 patients instead of 110 — the same sign
    and slightly stronger, so **E30's P3 sign disagreement is unaffected** and its conclusion stands.
  * **E30's propofol arm is untouched.** Chennu's dose column is a measured plasma concentration in a
    volunteer protocol; there is no vaporiser and no off-state. **The +0.710 result, which is the one E30
    actually rests on, does not depend on this at all.**
  * **E25 and E29** used the same arm definition. E25's primary was already withdrawn by its placebo and
    E29 never reported a candidate value, so neither conclusion changes — but both were computed on an arm
    that was half vaporiser-off, and that belongs in the record.

**WHY THE GATE CAUGHT IT AND FOUR PREVIOUS EXPERIMENTS DID NOT.** E25, E29 and E30 all asked for a
correlation across a dose range, and a correlation is perfectly happy to span an off-state. Only a design
that SPLITS the dose axis had to look at where the axis actually sits, and the first thing it printed was a
median of zero. **A stratified analysis is a machinery check on the exposure that a correlation never
performs**, which is a general lesson and not a fact about MAC.

**WHAT HAPPENS NEXT IS A NEW REGISTRATION, NOT AN EDIT.** Re-running this file with `MAC > 0` would be
changing the cohort after seeing the gate fail. The correct move is a fresh registration whose arm
definition requires an agent to actually be flowing — and it should be written knowing that the volatile
arm then loses half its windows and 12 of 110 patients.
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
OUT = os.path.join(RESULTS, "e32_dose_axis_stratified.json")

PRIMARY = "exponent_high"
EMG_MAX = 35.0
MIN_POINTS = 4
MIN_DISTINCT = 3
MIN_PATIENTS = 20
MIN_TERCILE_GAP = 0.15
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
    print("E31 — dose-axis stratified, does the slope depend on where along the dose you are?")
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
    q = np.nanquantile(mac[base], [1 / 3, 2 / 3])
    strata = {"low MAC tercile": base & (mac <= q[0]),
              "high MAC tercile": base & (mac >= q[1])}
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
    both = len({s for s in subj[strata['low MAC tercile']]}
               & {s for s in subj[strata['high MAC tercile']]})
    print(f"   patients contributing to BOTH strata: {both}")
    tgap = float(np.nanmedian(mac[strata["high MAC tercile"]])
                 - np.nanmedian(mac[strata["low MAC tercile"]]))
    print(f"   median MAC: low {np.nanmedian(mac[strata['low MAC tercile']]):.2f}, "
          f"high {np.nanmedian(mac[strata['high MAC tercile']]):.2f}, gap {tgap:.2f} "
          f"(floor {MIN_TERCILE_GAP})")
    depth_ok = tgap >= MIN_TERCILE_GAP
    cov_ok = all(v >= MIN_PATIENTS for v in counts.values())
    p1 = bool(depth_ok and cov_ok)
    print(f"   terciles separated in MAC: {depth_ok}   coverage: {cov_ok}   "
          f"-> P1 {'PASSED' if p1 else '*** FAILED'}")
    state = {"experiment": "E32", "p1": {"counts": counts, "median_bis": med_bis,
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
    print(f"P2 — PRIMARY, DIRECTIONAL: rho({PRIMARY}, MAC) must be GREATER in the LOW-MAC tercile")
    print("=" * 100)
    res = {}
    for name, m in strata.items():
        r, ci = rho_in(m, x, mac)
        res[name] = {"rho": r, "ci": list(ci)}
        print(f"   {name:18s} rho {r:+.3f}  [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    diff = res["low MAC tercile"]["rho"] - res["high MAC tercile"]["rho"]
    p2 = bool(np.isfinite(diff) and diff > 0)
    print(f"\n   low - high = {diff:+.3f}   P2 {'PASSED' if p2 else '*** FAILED'}")
    print("   Directional and pre-stated: a move the other way refutes the depth-range explanation.")
    state["p2"] = {"strata": res, "difference": float(diff), "passed": p2}

    print("\n" + "=" * 100)
    print("P3 — HOW MUCH OF THE CROSS-DEPOSIT GAP DOES THIS RECOVER? (reported, not gated)")
    print("=" * 100)
    gap = CHENNU_RHO - VITALDB_RHO
    frac = diff / gap if gap else float("nan")
    print(f"   E30's gap: Chennu {CHENNU_RHO:+.3f} - VitalDB {VITALDB_RHO:+.3f} = {gap:.3f}")
    print(f"   recovered within VitalDB by depth stratification: {diff:+.3f} = {frac:.1%} of it")
    print("   Stratifying on the exposure narrows the range inside each stratum, attenuating both rhos")
    print("   toward zero, so this is a conservative test of the DIFFERENCE between them.")
    state["p3"] = {"gap": float(gap), "recovered": float(diff), "fraction": float(frac)}

    print("\n" + "=" * 100)
    print("P4 — PLACEBO GATE: remifentanil has no reason to show a depth-range reversal")
    print("=" * 100)
    rres = {}
    for name, m in strata.items():
        r, ci = rho_in(m, x, rftn)
        rres[name] = {"rho": r, "ci": list(ci)}
        print(f"   {name:18s} rho(exponent_high, remifentanil) {r:+.3f}  [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    rdiff = rres["low MAC tercile"]["rho"] - rres["high MAC tercile"]["rho"]
    p4 = bool(np.isfinite(rdiff) and abs(rdiff) < abs(diff))
    print(f"\n   remifentanil low - high = {rdiff:+.3f} against MAC's {diff:+.3f}")
    print(f"   P4 {'PASSED' if p4 else '*** FAILED — the pattern is about the strata, not the drug; P2 is WITHDRAWN'}")
    state["p4"] = {"strata": rres, "difference": float(rdiff), "passed": p4}

    print("\n" + "=" * 100)
    print("P5 — DO THE OTHER FLIPPED CANDIDATES MOVE THE SAME WAY? (reported, not gated)")
    print("=" * 100)
    print(f"   {'candidate':26s} {'light':>9s} {'deep':>9s} {'light-deep':>12s}")
    out5, moved = {}, 0
    for cname in FLIPPED:
        xc = col(cname)
        rl, _ = rho_in(strata["low MAC tercile"], xc, mac)
        rd, _ = rho_in(strata["high MAC tercile"], xc, mac)
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
