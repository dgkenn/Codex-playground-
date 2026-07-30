#!/usr/bin/env python3
"""E15 — is the 20-40 Hz effect a beta hump? The band above it answers, on a second propofol deposit.

REGISTERED BEFORE ANY ds005620 FEATURE VALUE FOR THIS CANDIDATE SET EXISTS. `exponent_gamma` has never been
computed on any deposit; `exponent_high` has never been computed on ds005620 (the previously committed
ds005620 table carries eight features and neither of these is among them). The only ds005620 columns
inspected while writing this were `meta_task` and `meta_acq`, to establish the confound structure below.

THE QUESTION. E08 found `exponent_high` (20-40 Hz) at AUC 0.863 on Chennu. E10 raised the alternative that it
tracks propofol's beta hump rather than a broadband aperiodic change, and the synthetic ground truth in
`tests/test_exponent_gamma.py` shows that mechanism is REAL AND SUFFICIENT: on 1/f^2 noise whose true
exponent is exactly 2.0, planting a 20 Hz peak drives the 20-40 Hz fit from 1.983 to 9.872 while the 50-90 Hz
fit does not move past 2.060. Sufficient is not actual. This experiment asks whether it is actual.

    H_hump        the effect lives in a spectral peak near the low edge of the 20-40 Hz window
                  -> `exponent_high` responds, `exponent_gamma` (50-90 Hz) does NOT
    H_broadband   the effect is a genuine change in the aperiodic slope across the spectrum
                  -> BOTH respond

WHY ds005620 AND NOT CHENNU. The 50-90 Hz band does not exist on Chennu (filtered 0.5-45 Hz) or on Sleep-EDF
(100 Hz, Nyquist 50). ds005620 is propofol at 5 kHz. E12 would have answered the same question by moving the
fit window off the hump on Chennu, and the Cambridge host that serves Chennu is currently unreachable (§9.17),
so this is the reachable route.

THE CONFOUND, MEASURED RATHER THAN ASSUMED, AND IT SHAPES THE WHOLE DESIGN.
Cross-tabulating `meta_task` against `meta_acq` on ds005620's committed table:

              EC    EO   rest   tms
    awake     21    21      0    17
    sed        0     0     54    38
    sed2       0     0     51     0

**`awake` never occurs at `rest`, and `sed` never occurs at `EC` or `EO`.** Task and acquisition are perfectly
collinear across most of the deposit, so a naive awake-vs-sed contrast measures the acquisition condition as
much as the drug. Exactly one stratum contains both classes: **`acq=tms`, 17 awake against 38 sed.** That is
the acquisition-matched contrast, and it is the primary. Its own cost is stated up front: TMS recordings
contain stimulation artefacts, which is a different problem from the one being avoided.

**THE COMPARISON THAT MATTERS IS BETWEEN TWO CANDIDATES ON THE SAME ROWS, AND THAT IS WHAT RESCUES THIS.**
Whatever the acquisition condition does to the EEG, it does to `exponent_high` and `exponent_gamma` alike,
because both are computed from the same window of the same recording. A DIFFERENCE between them is therefore
far better protected against the confound than either one's absolute AUC. P2 is confounded and is reported as
such; P3 is the question this experiment exists to answer.

REGISTERED PREDICTIONS:
    P1  MACHINERY GATE. `exponent_gamma` must be finite in at least 80 % of usable rows. It is NaN by
        construction wherever the band is absent, and if ds005620 also fails to supply it — an unexpected
        filter, a decimated upload — the candidate is untestable anywhere reachable and nothing else is
        reported (rule 31: absent, not negative).
    P2  REPLICATION, AND IT IS CONFOUNDED. `exponent_high`'s signed AUC for awake vs sed excludes 0.5 in its
        declared `higher` direction, in the acquisition-matched `tms` stratum. This is the first time E08's
        finding has been tested on a second propofol deposit at all. Not met -> the 0.863 is Chennu-specific
        and the lead is withdrawn regardless of what P3 says.
    P3  THE DISCRIMINATOR. Given P2, `exponent_gamma`'s |AUC-0.5| is at least 0.15 BELOW `exponent_high`'s.
        Met -> H_hump: the effect is confined to the band containing the beta peak, and E08's result is a
        peak artefact rather than an aperiodic finding. Not met -> H_broadband: the two bands agree, the
        effect spans the spectrum, and the beta-hump explanation is refuted for the first time by data
        rather than by argument.
    P4  EMG GATE, EVALUATED BEFORE P3 BECAUSE IT CAN INVALIDATE IT. 50-90 Hz is squarely where surface
        motor-unit activity lives, and `exponent_gamma` declares that an EMG result there makes it an EMG
        measure. Unlike Chennu, ds005620 retains the frequencies where muscle actually lives, so its EMG
        proxies are GOOD instruments here rather than degraded ones (§9.11). The gate FAILS if an EMG proxy
        tracks the contrast at least as well as `exponent_gamma` AND `exponent_gamma`'s association does not
        survive residualising on it. A failed gate makes P3 uninterpretable in the H_hump direction
        specifically: a null for `exponent_gamma` could then be muscle cancelling a real signal rather than
        the absence of one.

    FALSIFICATION OF THE E08 LEAD: P2 not met.
    FALSIFICATION OF THE BETA-HUMP EXPLANATION: P3 not met with P4 passing.

SCOPE. 21 subjects, one drug, one site, BrainVision at 5 kHz. Denominators: 18 registered candidates,
analytic_dof >= 72 for the exponent family. Nothing here speaks to consciousness — ds005620 carries no
experience reports (§9.5) and, like Chennu, its sedation depth is not established to reach unconsciousness
(§9.16); `sed` and `sed2` are the deposit's own labels and are taken at face value as "sedated", no more.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                        # noqa: E402
from bsde.candidates.seed import seed_registry                                        # noqa: E402
from bsde.verifier.engine import residual_auc                                          # noqa: E402
from bsde.verifier.stats import directional_auc, cluster_bootstrap_ci                   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "ds005620_features_v2.csv")

PRIMARY, DISCRIMINATOR = "exponent_high", "exponent_gamma"
EMG_PROXIES = ("emg_beta_gamma_fraction", "emg_kurtosis", "emg_index")
MATCHED_ACQ = "tms"
AWAKE, SEDATED = {"awake"}, {"sed"}
GATE_MIN_FINITE = 0.80
DISCRIMINATOR_GAP = 0.15
ALSO = ("exponent_low", "whole_head_exponent", "relative_delta_power", "relative_alpha_power",
        "lempel_ziv", "spectral_entropy", "spectral_edge_95", "uce_v1", "wpli_alpha")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def score(rows, name, y, subj, rng):
    cand = REGISTRY.get(name)
    d = cand.predicted("unconscious_vs_awake")
    if d not in ("higher", "lower"):
        d = "higher"
    x = np.array([_f(r.get(name, "")) for r in rows], float)
    if np.isfinite(x).sum() < 12 or len(np.unique(y)) < 2:
        return None
    a = directional_auc(y, x, d)
    lo, hi = cluster_bootstrap_ci(lambda i: directional_auc(y[i], x[i], d), subj, rng, reps=2000)[:2]
    return {"declared": d, "auc": float(a), "ci": [float(lo), float(hi)],
            "abs": float(abs(a - 0.5)), "n_finite": int(np.isfinite(x).sum()), "_x": x}


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    print("E15 — is the 20-40 Hz effect a beta hump? Testing the band above it on ds005620")
    print(f"   search space {n_space} registered candidates; analytic dof >= 72")
    if not os.path.exists(TABLE):
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    with open(TABLE, newline="") as fh:
        allrows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]
    print(f"   usable rows in table {len(allrows)}   subjects {len({r['subject'] for r in allrows})}")

    # ------------------------------- P1 gate --------------------------------------------------------
    g = np.array([_f(r.get(DISCRIMINATOR, "")) for r in allrows], float)
    frac = float(np.isfinite(g).mean()) if g.size else 0.0
    p1 = frac >= GATE_MIN_FINITE
    print("\n" + "=" * 100)
    print(f"P1 — MACHINERY GATE: {DISCRIMINATOR} finite in >= {GATE_MIN_FINITE:.0%} of rows")
    print("=" * 100)
    print(f"   finite in {np.isfinite(g).sum()}/{g.size} rows ({frac:.1%})   "
          f"{'GATE PASSED' if p1 else '*** GATE FAILED'}")
    if not p1:
        print("   The 50-90 Hz band is unavailable even here. The candidate is untestable on any reachable")
        print("   deposit and nothing else is reported.")
        json.dump({"experiment": "E15", "gate_passed": False, "finite_frac": frac},
                  open(os.path.join(RESULTS, "e15_beta_hump.json"), "w"), indent=2)
        return 1

    # ------------------------------- the two contrasts ----------------------------------------------
    rng = np.random.default_rng(20260730)
    out = {}
    for label, sel in (("acq-MATCHED (tms only)", lambda r: r.get("meta_acq") == MATCHED_ACQ),
                       ("FULL (task and acq collinear)", lambda r: True)):
        rows = [r for r in allrows
                if (r.get("meta_task") in AWAKE or r.get("meta_task") in SEDATED) and sel(r)]
        if len(rows) < 12:
            print(f"\n   {label}: only {len(rows)} rows — not reported")
            out[label] = {"n": len(rows), "scores": {}}
            continue
        y = np.array([1.0 if r["meta_task"] in SEDATED else 0.0 for r in rows])
        subj = np.array([r["subject"] for r in rows])
        print("\n" + "=" * 100)
        print(f"{label}   rows {len(rows)}  subjects {len(set(subj))}  "
              f"awake {int((y == 0).sum())} / sed {int((y == 1).sum())}")
        print("=" * 100)
        print(f"   {'candidate':26s} {'declared':>9s} {'signed AUC':>24s} {'|AUC-.5|':>9s}")
        sc = {}
        for name in (PRIMARY, DISCRIMINATOR) + EMG_PROXIES + ALSO:
            s = score(rows, name, y, subj, rng)
            if s is None:
                continue
            sc[name] = s
            mark = "   <-- primary" if name == PRIMARY else ("   <-- discriminator" if name == DISCRIMINATOR
                                                             else "")
            print(f"   {name:26s} {s['declared']:>9s} {s['auc']:8.3f} [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}] "
                  f"{s['abs']:9.3f}{mark}")
        out[label] = {"n": len(rows), "n_subjects": len(set(subj)),
                      "scores": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                                 for k, v in sc.items()},
                      "_sc": sc, "_y": y, "_subj": subj}

    matched = out.get("acq-MATCHED (tms only)", {})
    sc = matched.get("_sc", {})
    if PRIMARY not in sc or DISCRIMINATOR not in sc:
        print("\n   *** the matched stratum did not yield both candidates. Nothing decisive is reported.")
        json.dump({"experiment": "E15", "gate_passed": True, "finite_frac": frac,
                   "contrasts": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                                 for k, v in out.items()},
                   "verdict": "MATCHED_STRATUM_INSUFFICIENT"},
                  open(os.path.join(RESULTS, "e15_beta_hump.json"), "w"), indent=2, default=str)
        return 1

    # ------------------------------- P4 EMG gate, BEFORE P3 -----------------------------------------
    print("\n" + "=" * 100)
    print(f"P4 — EMG GATE on {DISCRIMINATOR} (evaluated before P3, because it can invalidate it)")
    print("=" * 100)
    y, subj = matched["_y"], matched["_subj"]
    gx = sc[DISCRIMINATOR]["_x"]
    emg_fires = []
    for nm in EMG_PROXIES:
        if nm not in sc:
            continue
        v = sc[nm]["_x"]
        r = residual_auc(y, gx, v)
        tracks = sc[nm]["abs"] >= sc[DISCRIMINATOR]["abs"]
        killed = np.isfinite(r) and abs(r - 0.5) < 0.5 * sc[DISCRIMINATOR]["abs"]
        print(f"   {nm:26s} |AUC-.5| {sc[nm]['abs']:.3f} vs gamma {sc[DISCRIMINATOR]['abs']:.3f}   "
              f"gamma residualised -> {r:.3f}   "
              f"{'*** BOTH CLAUSES FIRE' if (tracks and killed) else ''}")
        if tracks and killed:
            emg_fires.append(nm)
    p4 = not emg_fires
    print(f"\n   EMG gate: {'PASSED' if p4 else '*** FAILED on ' + str(emg_fires)}")
    if not p4:
        print("   ds005620 retains the frequencies where muscle lives, so these are good instruments here.")
        print("   A null for exponent_gamma could now be muscle cancelling a real signal rather than the")
        print("   absence of one, which makes P3 uninterpretable in the H_hump direction specifically.")

    # ------------------------------- P2, P3 ---------------------------------------------------------
    p2 = sc[PRIMARY]["ci"][0] > 0.5
    gap = sc[PRIMARY]["abs"] - sc[DISCRIMINATOR]["abs"]
    p3 = gap >= DISCRIMINATOR_GAP

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 {DISCRIMINATOR} computable here                     : MET ({frac:.1%} finite)")
    print(f"   P2 {PRIMARY} replicates (CI excludes 0.5), matched  : {'MET' if p2 else 'NOT MET'} "
          f"({sc[PRIMARY]['auc']:.3f} [{sc[PRIMARY]['ci'][0]:.3f}, {sc[PRIMARY]['ci'][1]:.3f}])")
    print(f"   P3 gamma weaker than high by >= {DISCRIMINATOR_GAP}                  : "
          f"{'MET' if p3 else 'NOT MET'} (gap {gap:+.3f})")
    print(f"   P4 EMG gate on the discriminator                       : {'MET' if p4 else 'NOT MET'}")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p2:
        verdict = "NO_REPLICATION"
        print("   exponent_high does NOT replicate on a second propofol deposit in the acquisition-matched")
        print("   stratum. E08's 0.863 is Chennu-specific and the lead is WITHDRAWN, whatever P3 says.")
    elif not p4:
        verdict = "EMG_GATE_FAILED"
        print("   The primary replicates, but the discriminator is an EMG measure here, so the comparison")
        print("   that this experiment exists to make cannot be made. Rule 31: absent, not negative.")
    elif p3:
        verdict = "BETA_HUMP_SUPPORTED"
        print(f"   The effect is confined to the band containing the beta peak: exponent_high "
              f"|AUC-0.5| {sc[PRIMARY]['abs']:.3f} against exponent_gamma's {sc[DISCRIMINATOR]['abs']:.3f}.")
        print("   Combined with the synthetic ground truth showing a 20 Hz peak inflates a 20-40 Hz fit")
        print("   fivefold with no change in the aperiodic component, E08's result is best read as a")
        print("   SPECTRAL PEAK artefact, not an aperiodic finding. It should be reported as a measure of")
        print("   propofol beta, which is a real drug effect and not a consciousness marker.")
    else:
        verdict = "BROADBAND_BETA_HUMP_REFUTED"
        print("   Both bands respond and the gap is below the registered threshold. The effect spans the")
        print("   spectrum rather than sitting in the beta peak, so the beta-hump explanation is REFUTED")
        print("   by data rather than by argument — the first time it has been tested at all. exponent_high")
        print("   survives as an aperiodic finding, still on the sedation-depth reading of §9.16.")
    print(f"\n   verdict: {verdict}")
    print("\n   The absolute AUCs in the FULL contrast are confounded with acquisition condition and are")
    print("   printed for completeness only. P2 and P3 are computed in the matched stratum.")

    dst = os.path.join(RESULTS, "e15_beta_hump.json")
    json.dump({"experiment": "E15", "gate_passed": True, "search_space_size": n_space,
               "finite_frac_gamma": frac, "matched_acq": MATCHED_ACQ,
               "contrasts": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                             for k, v in out.items()},
               "emg_gate_failures": emg_fires, "gap": float(gap),
               "predictions": {"P1": True, "P2": bool(p2), "P3": bool(p3), "P4": bool(p4)},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
