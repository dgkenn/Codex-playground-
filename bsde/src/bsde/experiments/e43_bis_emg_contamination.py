#!/usr/bin/env python3
"""E43 — is BIS contaminated by muscle activity in a way a spectral slope is not?

WHY THIS IS CHALLENGE C's FIRST FAIR TEST, AND WHY OUR OWN THREE NEGATIVES DO NOT BEAR ON IT.

E26, E34 and E37 all measured candidates against **SEF95**, a computed spectral-edge proxy, and all three
scope themselves in their own headers as *"ahead of SEF95, never ahead of BIS"* — because BIS is not in the
DOSE-I deposit. The prior work's strongest Challenge C claim is against **real BIS**, on VitalDB, where BIS
is actually recorded. **Two different questions have been sharing a challenge number**, and this file asks
the one that has never been asked here.

It also tests a specific, falsifiable mechanism rather than a performance difference. The claim is that
discordant epochs carry 21x beta and 81x gamma power and cluster late in maintenance — consistent with
returning muscle tone as neuromuscular blockade wears off — and that **EMG drives the BIS number into the
40-60 "adequate" range while leaving a broadband spectral slope comparatively unaffected**. If true, that is
a fact about an instrument, not a disagreement between two imperfect ones.

THE CONFOUND THAT MAKES THE NAIVE TEST WORTHLESS, AND IT IS ALREADY VISIBLE IN THE DATA. Measured before
this file was written, on the 5,845 rows carrying all three monitor channels:

    BIS - monitor EMG   **+0.4479**
    BIS - monitor SQI   +0.1009
    BIS - whole_head_exponent  -0.3403
    monitor EMG - our `emg_index`  +0.3511

**That +0.4479 proves nothing.** Deeper anaesthesia lowers BIS *and* abolishes muscle tone, so BIS and EMG
would correlate strongly with no contamination whatever. The raw correlation is exactly what a shared
depth cause produces.

**THE TEST IS THEREFORE A PARTIAL, AND THE FINDING IS AN ASYMMETRY.** Condition on brain state — proxied by
the spectral measure — and ask what EMG still explains:

    partial( BIS,      EMG | state )   contaminated instrument -> POSITIVE
    partial( state,    EMG | BIS   )   robust instrument       -> approximately ZERO

**Neither number alone is the result. The asymmetry between them is**, because a single positive partial
could be residual confounding from an imperfect state proxy, while a difference in how two measures respond
to the same channel at the same conditioning cannot be explained that way.

REGISTERED BEFORE ANY PARTIAL IS COMPUTED. Failing branch first throughout.

  G1  COVERAGE. At least `MIN_CASES` cases and `MIN_ROWS` rows carrying BIS, EMG, SQI and the state measure.

  G2  **BOTH CHANNELS MUST VARY WITHIN CASE (rule 32).** A between-case comparison would answer "are these
      different patients?" rather than "does muscle move the number?", so every statistic here is
      case-clustered and the gate requires at least `MIN_VARYING` cases in which BIS and EMG both take at
      least 5 distinct values. Two whole ledger entries were once spent comparing a measure against a flag
      that was constant in the analysis cohort.

  P1  THE ASYMMETRY, and it is the primary. `partial(BIS, EMG | state)` minus `partial(state, EMG | BIS)`,
      with a case-clustered bootstrap CI. FAILS if the interval includes zero.

  P2  THE PLACEBO, gating (rule 34). The identical pair of partials with **SQI** substituted for EMG. SQI
      is a general signal-quality channel; if the asymmetry is about *muscle* rather than about *any
      artefact channel*, the EMG asymmetry must exceed the SQI asymmetry. A comparison, never a threshold.
      Reported NOT INFORMATIVE if P1's interval includes zero (rule 48).

  P3  THE INDEPENDENT-CHANNEL CHECK. The monitor's own EMG channel is one instrument's opinion. Repeat P1
      with **our** `emg_index`, computed from the waveform by code in this repository and correlating
      +0.3511 with the monitor's channel. Agreement across two independent EMG estimates is worth more
      than either alone (rule 23's spirit: validate against an independent implementation).

  P4  THE TEMPORAL CLAIM, reported not gating. The prior work reports discordance clustering **63 % in the
      final third of maintenance**. Test whether EMG rises across the maintenance fraction, and whether
      BIS rises with it while the state measure does not.

  P5  REPORTED CONTEXT: the raw correlations above, so a reader sees what the partials are correcting.

VERDICT RULE, written before the run and failing case first.

    NOT INTERPRETABLE   G1 or G2 failed.
    NO ASYMMETRY        P1's interval includes zero. BIS and the spectral measure respond to muscle alike,
                        and the mechanism claim is not supported here.
    NOT SPECIFIC        P1 excludes zero but the SQI placebo matches it — this is general artefact
                        sensitivity, not muscle, and must be described that way.
    CONTAMINATION       P1 excludes zero and exceeds its placebo. Permitted sentence: *"at matched
                        spectral state, muscle activity predicts BIS and does not predict the spectral
                        measure."* NOT permitted: any claim that the spectral measure is a better depth
                        monitor, which this design does not test and cannot.

SCOPE. VitalDB surgical cases, 250 with a decoded EEG grid; BIS is the Covidien/Medtronic implementation
only; `meta_emg` is that monitor's own EMG estimate. **Maintenance only** — the strip goes on after
induction, established earlier in this project (0 pre-induction windows of 6,439). No claim about induction
or emergence follows from this file.
"""

from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import cluster_bootstrap_ci, spearman                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e43_bis_emg_contamination.json")

STATE = "whole_head_exponent"
BIS, EMG, SQI = "meta_bis", "meta_emg", "meta_sqi"
OUR_EMG = "emg_index"
MIN_CASES = 100
MIN_ROWS = 2000
MIN_VARYING = 50
REPS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load():
    rows = [r for r in csv.DictReader(open(GRID, newline="")) if r.get("status") == "ok"]
    cols = {c: np.array([_f(r.get(c, "")) for r in rows], float)
            for c in (BIS, EMG, SQI, STATE, OUR_EMG, "meta_rel_anestart_s", "meta_rel_aneend_s")}
    case = np.array([r.get("meta_caseid", "") for r in rows])
    return cols, case


def _partial(x, y, z):
    """Partial Spearman of x and y given z, via residualised ranks."""
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if ok.sum() < 50:
        return float("nan")
    def rank(v):
        o = np.argsort(np.argsort(v))
        return o.astype(float)
    rx, ry, rz = rank(x[ok]), rank(y[ok]), rank(z[ok])
    Z = np.column_stack([np.ones(rz.size), rz])
    def resid(v):
        b, *_ = np.linalg.lstsq(Z, v, rcond=None)
        return v - Z @ b
    ex, ey = resid(rx), resid(ry)
    if ex.std() < 1e-12 or ey.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(ex, ey)[0, 1])


def _asymmetry(cols, idx, art):
    """partial(BIS, art | state) - partial(state, art | BIS)."""
    b, s, a = cols[BIS][idx], cols[STATE][idx], cols[art][idx]
    p1 = _partial(b, a, s)
    p2 = _partial(s, a, b)
    if not (np.isfinite(p1) and np.isfinite(p2)):
        return float("nan")
    return abs(p1) - abs(p2)


def main(argv=None) -> int:
    print("E43 — is BIS contaminated by muscle in a way a spectral slope is not?")
    print("   Challenge C's first test against the comparator our own three negatives never used.")
    print("   The primary is an ASYMMETRY, because a single partial could be residual confounding.")
    if not os.path.exists(GRID):
        print(f"\n   *** {os.path.basename(GRID)} absent.")
        return 2
    cols, case = _load()
    rng = np.random.default_rng(SEED)
    base = (np.isfinite(cols[BIS]) & np.isfinite(cols[EMG]) & np.isfinite(cols[SQI])
            & np.isfinite(cols[STATE]))
    idx = np.flatnonzero(base)
    st = {"experiment": "E43", "n_rows": int(idx.size), "n_cases": int(np.unique(case[idx]).size)}

    print("\n" + "=" * 100)
    print("G1 / G2 — COVERAGE AND WITHIN-CASE VARIATION")
    print("=" * 100)
    print(f"   rows with BIS, EMG, SQI and {STATE} : {idx.size}   (floor {MIN_ROWS})")
    print(f"   cases                               : {np.unique(case[idx]).size}   (floor {MIN_CASES})")
    varying = 0
    for c in np.unique(case[idx]):
        m = idx[case[idx] == c]
        if np.unique(cols[BIS][m]).size >= 5 and np.unique(cols[EMG][m]).size >= 5:
            varying += 1
    print(f"   cases where BIS and EMG both vary   : {varying}   (floor {MIN_VARYING})")
    g = bool(idx.size >= MIN_ROWS and np.unique(case[idx]).size >= MIN_CASES and varying >= MIN_VARYING)
    print(f"\n   G1/G2 {'PASSED' if g else '*** FAILED'}")
    st["gates"] = {"n_rows": int(idx.size), "n_cases": int(np.unique(case[idx]).size),
                   "n_varying": varying, "passed": g}
    if not g:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P5 — RAW CORRELATIONS (reported, so a reader sees what the partials correct)")
    print("=" * 100)
    for a, b, na, nb in ((BIS, EMG, "BIS", "monitor EMG"), (BIS, SQI, "BIS", "SQI"),
                         (BIS, STATE, "BIS", STATE), (EMG, OUR_EMG, "monitor EMG", "our emg_index")):
        m = idx[np.isfinite(cols[a][idx]) & np.isfinite(cols[b][idx])]
        print(f"   {na:12s} - {nb:18s} {spearman(cols[a][m], cols[b][m]):+.4f}   n={m.size}")
    print("   The BIS-EMG number proves nothing on its own: depth lowers both.")

    print("\n" + "=" * 100)
    print("P1 — THE PRIMARY: the asymmetry, using the MONITOR's EMG channel")
    print("=" * 100)
    p_bis = _partial(cols[BIS][idx], cols[EMG][idx], cols[STATE][idx])
    p_state = _partial(cols[STATE][idx], cols[EMG][idx], cols[BIS][idx])
    asym = abs(p_bis) - abs(p_state)
    lo, hi, _ = cluster_bootstrap_ci(lambda i: _asymmetry(cols, idx[i], EMG), case[idx], rng, reps=REPS)
    print(f"   partial(BIS,   EMG | {STATE}) = {p_bis:+.4f}")
    print(f"   partial({STATE}, EMG | BIS)  = {p_state:+.4f}")
    print(f"   ASYMMETRY |a| - |b|          = {asym:+.4f}  [{lo:+.4f}, {hi:+.4f}]")
    p1 = bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0))
    print(f"   P1 {'PASSED' if p1 else '*** FAILED — the interval includes zero'}")
    st["p1"] = {"partial_bis": p_bis, "partial_state": p_state, "asymmetry": asym,
                "ci": [float(lo), float(hi)], "passed": p1}

    print("\n" + "=" * 100)
    print("P2 — PLACEBO: the same asymmetry with SQI, a general signal-quality channel")
    print("=" * 100)
    if not p1:
        print("   NOT INFORMATIVE: the primary's interval includes zero (rule 48).")
        st["p2"] = {"status": "not_informative"}
        p2 = None
    else:
        q_bis = _partial(cols[BIS][idx], cols[SQI][idx], cols[STATE][idx])
        q_state = _partial(cols[STATE][idx], cols[SQI][idx], cols[BIS][idx])
        q = abs(q_bis) - abs(q_state)
        print(f"   partial(BIS, SQI | state) = {q_bis:+.4f}   partial(state, SQI | BIS) = {q_state:+.4f}")
        print(f"   SQI asymmetry {q:+.4f}   vs EMG asymmetry {asym:+.4f}")
        p2 = bool(asym > q)
        print(f"   P2 {'PASSED — the effect is muscle-specific' if p2 else '*** FAILED — general artefact'}")
        st["p2"] = {"sqi_asymmetry": q, "passed": p2}

    print("\n" + "=" * 100)
    print("P3 — INDEPENDENT EMG ESTIMATE: our own emg_index from the waveform")
    print("=" * 100)
    o_bis = _partial(cols[BIS][idx], cols[OUR_EMG][idx], cols[STATE][idx])
    o_state = _partial(cols[STATE][idx], cols[OUR_EMG][idx], cols[BIS][idx])
    o = abs(o_bis) - abs(o_state)
    olo, ohi, _ = cluster_bootstrap_ci(lambda i: _asymmetry(cols, idx[i], OUR_EMG), case[idx],
                                       rng, reps=REPS)
    print(f"   partial(BIS, our_emg | state) = {o_bis:+.4f}   partial(state, our_emg | BIS) = {o_state:+.4f}")
    print(f"   asymmetry {o:+.4f}  [{olo:+.4f}, {ohi:+.4f}]   monitor's channel gave {asym:+.4f}")
    agree = bool(np.sign(o) == np.sign(asym) and np.isfinite(olo) and (olo > 0 or ohi < 0))
    print(f"   two independent EMG estimates agree in sign and both exclude zero: {agree}")
    st["p3"] = {"asymmetry": o, "ci": [float(olo), float(ohi)], "agrees": agree}

    print("\n" + "=" * 100)
    print("P4 — THE TEMPORAL CLAIM (reported, not gating)")
    print("=" * 100)
    t0, t1 = cols["meta_rel_anestart_s"][idx], cols["meta_rel_aneend_s"][idx]
    frac = np.full(idx.size, np.nan)
    m = np.isfinite(t0) & np.isfinite(t1) & ((t0 - t1) != 0)
    frac[m] = t0[m] / (t0[m] - t1[m])
    good = np.isfinite(frac) & (frac >= 0) & (frac <= 1)
    if good.sum() > 500:
        print(f"   maintenance-fraction available on {int(good.sum())} rows")
        for name, v in ((EMG, cols[EMG][idx]), (BIS, cols[BIS][idx]), (STATE, cols[STATE][idx])):
            print(f"      Spearman(fraction, {name:22s}) = {spearman(frac[good], v[good]):+.4f}")
        thirds = np.digitize(frac[good], [1 / 3, 2 / 3])
        for k, lab in enumerate(("first", "middle", "final")):
            s = thirds == k
            if s.sum():
                print(f"      {lab:7s} third: n={int(s.sum()):5d}  median EMG "
                      f"{np.nanmedian(cols[EMG][idx][good][s]):6.2f}  median BIS "
                      f"{np.nanmedian(cols[BIS][idx][good][s]):6.2f}")
        st["p4"] = {"spearman_frac_emg": spearman(frac[good], cols[EMG][idx][good]),
                    "spearman_frac_bis": spearman(frac[good], cols[BIS][idx][good]),
                    "spearman_frac_state": spearman(frac[good], cols[STATE][idx][good])}
    else:
        print("   maintenance fraction not derivable on enough rows — reported as absent.")
        st["p4"] = {"status": "absent"}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not p1:
        verdict = "no_asymmetry"
        print("   NO ASYMMETRY: BIS and the spectral measure respond to muscle alike here.")
    elif p2 is False:
        verdict = "not_specific"
        print("   NOT SPECIFIC: the SQI placebo matches, so this is general artefact sensitivity")
        print("   rather than muscle, and must be described that way.")
    else:
        verdict = "contamination"
        print("   CONTAMINATION: at matched spectral state, muscle activity predicts BIS and does not")
        print("   predict the spectral measure. NOT a claim that the spectral measure is a better")
        print("   depth monitor — this design does not test that and cannot.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
