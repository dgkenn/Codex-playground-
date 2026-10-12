#!/usr/bin/env python3
"""E65 -- Challenge C. Does the BIS-like index track a CLINICIAN's sedation score on another deposit?

REGISTERED BEFORE ANY DOSE-I FEATURE HAS BEEN RELATED TO MOAA/S OR SOC. What has been read from the DOSE-I
feature table is a 200-window, two-recording pilot, inspected for column coverage and for the
cross-deposit distribution check reported below. **No label was touched in that pilot beyond counting how
many windows carried each MOAA/S value.**

=========================================================================================================
WHY THIS IS THE TEST THE INDEX HAS NOT HAD
=========================================================================================================
Q22 leaves the BIS-like index validated against ONE reference on ONE deposit: device BIS, on VitalDB, in
surgical maintenance, median \\|err\\| 3.47 in [40,60). Every number it has is agreement with a machine that
was itself measured, on the same recordings it was fitted to, from the same monitor.

**DOSE-I carries per-second clinician-scored MOAA/S and SOC, with raw EEG and no branded index.** Different
device, different population (procedural sedation for endoscopy, not surgery), and a reference that is a
person. If the index is measuring anaesthetic depth rather than one manufacturer's algorithm, it should
track a human's ordinal judgement on a deposit it never saw.

=========================================================================================================
A CROSS-DEPOSIT PROBLEM FOUND BEFORE THE FIT, AND IT IS A RESULT IN ITS OWN RIGHT
=========================================================================================================
Comparing feature medians across the two deposits, on features only -- no label:

    feature               VitalDB (128 Hz)      DOSE-I (125 Hz)
    exponent_gamma            -2.675               +29.651
    exponent_high             +4.804                +0.004
    whole_head_exponent       +2.196                +0.820
    exponent_low              +1.387                +1.435

**`exponent_gamma` is a device artefact on both deposits and cannot be transported.** It fits 50-90 Hz;
Nyquist is 64 Hz on VitalDB and 62.5 Hz on DOSE-I, so on both it is fitting the anti-alias rolloff rather
than the brain, and the two devices roll off differently. Neither value is a physiological exponent, and no
biology produces +29.7 against -2.7. **It is excluded by a rule fixed from the INSTRUMENT and not from the
data: any feature whose fit band extends above the lower deposit's Nyquist is excluded.** That rule names
`exponent_gamma` and nothing else, and it would have named it without any of the numbers above.

`exponent_high` and `whole_head_exponent` disagree substantially too. **They are NOT excluded**, because
excluding features for disagreeing would be selecting the feature set to make the transport look good. They
are instead handled by a gate that uses no label:

  M1 TRANSPORT GATE   for each surviving feature, the standardised difference between deposit medians,
                      `|med_v - med_d| / pooled IQR`. Features above `MAX_SHIFT` are REPORTED as
                      non-transporting and the primary is run BOTH with them (arm FULL) and without them
                      (arm SAFE). **Computed on features alone, before any MOAA/S is read**, so it selects
                      on distribution overlap and never on the answer. A model asked to score inputs far
                      outside its training range is extrapolating, and that is a broken application rather
                      than a finding.

=========================================================================================================
DESIGN
=========================================================================================================
FIT. Ridge on VitalDB windows with device BIS present, SQI >= 50, BIS in [20,60) -- the band
`BIS_FAITHFUL_OR_BRAIN_FAITHFUL.md` licenses -- using the transportable feature set. Case-grouped folds are
irrelevant to the transport (the test set is a different deposit entirely) but are kept so the reported
VitalDB fidelity remains comparable to E58's.

APPLY. Predict on DOSE-I windows. **Predictions outside [20,60) are REFUSED, not clipped** -- the refusal is
the deliverable's stated licence and applying it here is the point. The refused fraction is reported.

  M2 COVERAGE GATE    at least `MIN_KEPT` windows across `MIN_RECORDINGS` recordings must survive the
                      refusal, with at least `MIN_LEVELS` distinct MOAA/S values among them. A procedural
                      sedation cohort spends much of its time outside surgical maintenance depth, so this
                      gate can genuinely fail and that failure would be informative: it would mean the
                      validated band does not cover the states a human is scoring.

  PRIMARY             median across recordings of within-recording Spearman(predicted index, MOAA/S).
                      **PREDICTED POSITIVE** -- MOAA/S rises with alertness and so should a depth index
                      whose scale runs the way BIS's does. Recording-clustered bootstrap.
  P1 INCUMBENT        the same statistic for DOSE-I's own shipped `SEF95` and `PE31` (rule 45 -- a marker
                      reported without the thing it must beat is not a result). These are the published
                      measures E26/E34/E37 were scoped against, computed by the depositors, not by us.
  P2 PLACEBO          predictions shuffled ACROSS recordings, preserving each recording's own value
                      distribution and destroying its alignment with that recording's MOAA/S trajectory.

VERDICT RULE, wrong direction first.

  (a) INVERTED        -- the primary's interval lies entirely BELOW zero: the index runs backwards against
                         a human judgement, which would mean it is tracking something other than depth and
                         its agreement with device BIS is not evidence that it tracks depth either.
  (b) NO TRACKING     -- the interval includes zero.
  (c) NOT INFORMATIVE -- M1 or M2 failed, or the placebo reaches the primary.
  (d) TRACKS          -- the interval excludes zero on the positive side and the placebo does not reach it.
                         Report against the incumbent WITHOUT claiming to beat it unless the incumbent's
                         own interval is separated -- "above chance" and "above the incumbent" are
                         different claims and this project has conflated them before (E26, E34).

WHAT NO OUTCOME LICENCES. This is not a Challenge C pass. Challenge C asks for a measure that sees a
transition BEFORE the monitor; this asks only whether a computed index agrees with a human at all. A pass
would make the index usable as a comparator on monitor-free deposits, which is what Q22 was for; it would
not put anything ahead of anything.

    python -m bsde.experiments.e65_index_vs_human_label
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import _standardise, ridge_fit, spearman            # noqa: E402
from bsde.experiments.e58_bis_like_index import SUBPARAMS, _f, load          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
DOSEI = os.path.join(RESULTS, "dosei_features.csv")
OUT = os.path.join(RESULTS, "e65_index_vs_human_label.json")

# Excluded by the instrument rule: fit band 50-90 Hz, above the lower Nyquist (62.5 Hz) on both deposits.
NYQUIST_EXCLUDED = ["exponent_gamma"]
TRANSPORTABLE = [c for c in
                 ["critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_index", "emg_kurtosis",
                  "exponent_gamma", "exponent_high", "exponent_low", "lempel_ziv",
                  "multiscale_entropy_slope", "pac_slow_alpha", "relative_alpha_power",
                  "relative_delta_power", "spectral_edge_95", "spectral_entropy",
                  "whole_head_exponent", "bis_rbr", "bis_bsr", "bis_quazi", "bis_sfs"]
                 if c not in NYQUIST_EXCLUDED]

FIT_BAND = (20.0, 60.0)
MIN_SQI = 50.0
MAX_SHIFT = 1.0
MIN_KEPT = 300
MIN_RECORDINGS = 10
MIN_LEVELS = 3
REPS = 2000
SEED = 20260731


def _boot_median(vals, rng, reps=REPS):
    v = np.asarray([x for x in vals if np.isfinite(x)], float)
    if v.size < 3:
        return float("nan"), float("nan")
    d = np.sort([np.median(rng.choice(v, size=v.size, replace=True)) for _ in range(reps)])
    return float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))


def main() -> int:
    if not os.path.exists(DOSEI):
        print(f"MISSING {DOSEI} -- run scripts/extract_dosei_features.py first")
        return 2
    grid, sub, _ = load()
    vr = [r for r in sorted(grid)
          if grid[r].get("status") == "ok" and r in sub and sub[r].get("status") == "ok"
          and str(grid[r].get("meta_sensor_off", "")).strip().lower() not in ("true", "1")
          and np.isfinite(_f(grid[r].get("meta_bis"))) and _f(grid[r].get("meta_sqi")) >= MIN_SQI
          and FIT_BAND[0] <= _f(grid[r]["meta_bis"]) < FIT_BAND[1]]
    yv = np.array([_f(grid[r]["meta_bis"]) for r in vr])

    def vcol(c):
        src = sub if c in SUBPARAMS else grid
        return np.array([_f(src[r].get(c, "")) for r in vr], float)

    drows = [r for r in csv.DictReader(open(DOSEI, newline=""))]
    print(f"VitalDB fit set: {len(vr)} windows in BIS [{FIT_BAND[0]:.0f},{FIT_BAND[1]:.0f}), SQI >= "
          f"{MIN_SQI:.0f}\nDOSE-I: {len(drows)} windows, "
          f"{len(set(r['recording'] for r in drows))} recordings")
    print(f"excluded by the Nyquist rule: {NYQUIST_EXCLUDED}")

    # ---- M1 transport gate, features only, no label read
    shift = {}
    for c in TRANSPORTABLE:
        a, b = vcol(c), np.array([_f(r.get(c, "")) for r in drows], float)
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if a.size < 50 or b.size < 50:
            shift[c] = float("nan")
            continue
        iqr = 0.5 * ((np.quantile(a, .75) - np.quantile(a, .25))
                     + (np.quantile(b, .75) - np.quantile(b, .25)))
        shift[c] = abs(np.median(a) - np.median(b)) / iqr if iqr > 1e-12 else float("inf")
    safe = [c for c in TRANSPORTABLE if np.isfinite(shift[c]) and shift[c] <= MAX_SHIFT]
    drift = [c for c in TRANSPORTABLE if c not in safe]
    print(f"\nM1 transport gate (|median shift| / pooled IQR, threshold {MAX_SHIFT})")
    for c in sorted(TRANSPORTABLE, key=lambda k: -(shift[k] if np.isfinite(shift[k]) else 1e9)):
        print(f"   {c:<26s} {shift[c]:7.3f}  {'DRIFT' if c in drift else 'ok'}")
    print(f"   {len(safe)} of {len(TRANSPORTABLE)} transport; arm SAFE uses those, arm FULL uses all")

    res = {"n_vitaldb": len(vr), "n_dosei": len(drows), "nyquist_excluded": NYQUIST_EXCLUDED,
           "transport_shift": shift, "safe_features": safe, "drift_features": drift, "arms": {}}
    mo = np.array([_f(r.get("moaas", "")) for r in drows])
    rec = np.array([r["recording"] for r in drows])
    inc = {"their_sef95": np.array([_f(r.get("their_sef95", "")) for r in drows]),
           "their_pe31": np.array([_f(r.get("their_pe31", "")) for r in drows])}

    rng = np.random.default_rng(SEED)
    for arm, feats in (("FULL", TRANSPORTABLE), ("SAFE", safe)):
        if len(feats) < 3:
            print(f"\narm {arm}: fewer than 3 features, skipped")
            continue
        Xv = np.column_stack([vcol(c) for c in feats])
        Xd = np.column_stack([np.array([_f(r.get(c, "")) for r in drows], float) for c in feats])
        Ztr, Zte = _standardise(Xv, Xd)
        pred = Zte @ ridge_fit(Ztr, yv, 1.0)
        keep = np.isfinite(pred) & (pred >= FIT_BAND[0]) & (pred < FIT_BAND[1]) & np.isfinite(mo)
        n_rec = len(np.unique(rec[keep]))
        lev = len(np.unique(mo[keep])) if keep.any() else 0
        m2 = bool(keep.sum() >= MIN_KEPT and n_rec >= MIN_RECORDINGS and lev >= MIN_LEVELS)
        print(f"\narm {arm} ({len(feats)} features): {int(keep.sum())} of {len(drows)} windows inside "
              f"[{FIT_BAND[0]:.0f},{FIT_BAND[1]:.0f}) ({100 * keep.mean():.1f}%), {n_rec} recordings, "
              f"{lev} MOAA/S levels   M2 {'PASS' if m2 else 'FAIL'}")
        entry = {"n_features": len(feats), "n_kept": int(keep.sum()), "frac_kept": float(keep.mean()),
                 "n_recordings": n_rec, "n_moaas_levels": lev, "gate_m2": m2}
        if not m2:
            entry["verdict"] = ("NOT INFORMATIVE -- coverage gate failed: the validated band does not "
                                "cover enough of what a clinician was scoring on this deposit.")
            print(f"   {entry['verdict']}")
            res["arms"][arm] = entry
            continue

        def per_rec(vals):
            out = []
            for r in np.unique(rec[keep]):
                m = keep & (rec == r)
                if m.sum() >= 20 and np.unique(mo[m]).size >= 2 and np.isfinite(vals[m]).sum() >= 20:
                    out.append(spearman(vals[m], mo[m]))
            return [v for v in out if np.isfinite(v)]

        prim = per_rec(pred)
        p_med = float(np.median(prim))
        p_lo, p_hi = _boot_median(prim, rng)
        entry["primary"] = {"median_rho": p_med, "lo": p_lo, "hi": p_hi, "n_recordings": len(prim)}
        print(f"   PRIMARY  median within-recording rho(index, MOAA/S) = {p_med:+.4f} "
              f"[{p_lo:+.4f}, {p_hi:+.4f}]  ({len(prim)} recordings)")
        for k, v in inc.items():
            iv = per_rec(v)
            i_med = float(np.median(iv)) if iv else float("nan")
            i_lo, i_hi = _boot_median(iv, np.random.default_rng(SEED + 3))
            entry[k] = {"median_rho": i_med, "lo": i_lo, "hi": i_hi, "n_recordings": len(iv)}
            print(f"   P1 INCUMBENT {k:<12s} = {i_med:+.4f} [{i_lo:+.4f}, {i_hi:+.4f}]")

        rp = np.random.default_rng(SEED + 1)
        sh = pred.copy()
        for r in np.unique(rec[keep]):
            m = np.flatnonzero(keep & (rec == r))
            sh[m] = pred[rp.permutation(m)]
        plac = per_rec(sh)
        q_med = float(np.median(plac)) if plac else float("nan")
        entry["placebo"] = q_med
        print(f"   P2 PLACEBO  predictions shuffled within recording = {q_med:+.4f}")

        if not np.isfinite(p_lo):
            v = "ABSENT -- the bootstrap could not form an interval."
        elif p_hi < 0:
            v = ("INVERTED -- the index runs BACKWARDS against a clinician's judgement. Its agreement "
                 "with device BIS is then not evidence that it tracks depth.")
        elif p_lo <= 0:
            v = "NO TRACKING -- the interval includes zero."
        elif np.isfinite(q_med) and q_med >= p_med:
            v = "NOT INFORMATIVE -- a within-recording shuffle reproduces the association."
        else:
            beats = [k for k, e in entry.items()
                     if k.startswith("their_") and np.isfinite(e.get("hi", np.nan)) and e["hi"] < p_lo]
            v = ("TRACKS -- the index agrees with a clinician's ordinal sedation score on a deposit it "
                 "never saw, with a different device and population. "
                 + (f"It also separates from {beats} on non-overlapping intervals."
                    if beats else "It does NOT separate from the shipped incumbents; 'above chance' and "
                                  "'above the incumbent' are different claims."))
        entry["verdict"] = v
        print(f"   VERDICT: {v}")
        res["arms"][arm] = entry

    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
