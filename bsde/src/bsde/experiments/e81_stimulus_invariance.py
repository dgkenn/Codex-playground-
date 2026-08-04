"""E81 -- Challenge A's second handle: at the SAME behavioural state, which measures ignore a noxious stimulus?

REGISTERED BEFORE `dosei_holdout_features.csv` EXISTS. It shares that table with E80 and asks a different
question of it; both were registered before the extraction was launched.

=========================================================================================================
THE HANDLE, AND WHY IT IS WORTH HAVING
=========================================================================================================
DOSE-I's pEEG tables carry a binary `Endoscopy` marker -- **1 in 65,565 of 93,225 seconds across the first
60 recordings, present in every one of them**, so the deposit contains a large, externally imposed,
within-recording stimulus contrast that nobody has used.

An endoscope in the airway is a strong noxious and mechanical stimulus. That gives a dissociation that
E80's hysteresis design cannot supply:

    at MATCHED MOAA/S, a measure of BRAIN STATE should read the same with the stimulus present or absent
    a measure contaminated by STIMULUS-DRIVEN MUSCLE AND MOVEMENT should not

**This matters most because DOSE-I ships no EMG channel.** Q35 could only partial out scalp proxies, and
E69/E71 established those cannot see REM atonia and correlate with a real submental channel at rho +0.20.
Here the artefact source is not estimated from the EEG at all -- it is an externally imposed clinical
event, which makes this a CAUSAL handle on artefact susceptibility rather than a correlational one.

`bis_rbr` is the reason to run it now. Q35 put it at rho +0.5258 against MOAA/S, E78 confirmed +0.4611 on
held-out data, and its numerator band is 30-47 Hz, which is where surface EMG lives. E77 removed the
muscle objection **in sleep**; its own scope limit says that does not transfer to anaesthesia. This is the
anaesthesia-side test that limit asked for.

=========================================================================================================
ESTIMAND
=========================================================================================================
Within each recording, for each MOAA/S level carrying >= 5 windows with the stimulus ON and >= 5 with it
OFF, and each feature:

    gap = ( mean(feature | stimulus on) - mean(feature | stimulus off) ) / sd(feature within recording)

standardised within recording (rule 57), aggregated by a RECORDING-level bootstrap.

**THE HYPOTHESIS OF INTEREST IS AN ABSENCE, so "the interval includes zero" is the wrong criterion** -- a
wide interval is no power, not invariance. Equivalence, at the same margin E80 declared:

    STIMULUS-SENSITIVE   interval excludes 0            -- the reading moves with the stimulus
    STIMULUS-INVARIANT   interval lies inside +-0.25    -- equivalent to no change, at a stated margin
    UNDETERMINED         neither                        -- named, and not reportable as either

PRE-DECLARED EXPECTATIONS, written now and able to be wrong. SENSITIVE: `emg_index`,
`emg_beta_gamma_fraction`, `emg_kurtosis`, and **`bis_rbr`**, whose numerator band overlaps surface EMG.
INVARIANT: `relative_delta_power`, `exponent_low`, `pac_slow_alpha` -- all below 20 Hz, where surface EMG
contributes least. **A `bis_rbr` that comes back INVARIANT is the outcome that would most strengthen
Q35's finding, and predicting the opposite is the point of writing it down.**

BH q = 0.05 across features for the SENSITIVE calls only. The INVARIANT calls are equivalence claims and
carry their intervals instead, because a multiplicity correction makes an equivalence test EASIER to pass
and would be backwards.

=========================================================================================================
GATES, before any feature (rule 40)
=========================================================================================================
    G1  HELD OUT   zero overlap with the 43 recordings already used.
    G2  COVERAGE   >= 15 recordings contributing >= 1 cell and >= 25 cells in total.
    G3  THE MARKER MARKS SOMETHING, and this is the gate that makes the whole design honest.
        **`ecg_hr` -- the deposit's own Intellivue heart rate, a NON-EEG channel -- must be
        STIMULUS-SENSITIVE.** Noxious stimulation raises heart rate; that is physiology, not a property of
        any candidate. If heart rate does not move, the `Endoscopy` column is not marking stimulation in
        the way the design assumes and no feature-level result is interpretable. Using a candidate as this
        control would beg the question, which is why a non-EEG channel was added to the extractor for it.
    G4  NEGATIVE CONTROL. A per-window Gaussian draw must NOT come back SENSITIVE. If it does, the
        standardisation or the cell weighting is manufacturing gaps.

PLACEBO (after the primaries, able only to remove). The stimulus label is permuted WITHIN each
(recording, MOAA/S level) cell, preserving both group sizes, 200 draws. Rule 55: the statistic is a
function of which windows carry the stimulus, and that is exactly what the permutation destroys, leaving
the MOAA/S structure and the recording standardisation intact. Any SENSITIVE feature inside the placebo's
central 95 % is withdrawn.

=========================================================================================================
WHAT NO OUTCOME LICENSES
=========================================================================================================
STIMULUS-INVARIANT is a NECESSARY condition, not a sufficient one, and a constant would pass it trivially
-- which is why G4 exists and why every invariance call is reported beside that feature's within-recording
SD. The stimulus is confounded with whatever else changes during endoscopy, including clinical titration:
this experiment therefore conditions on MOAA/S and claims nothing about periods where the state itself
changed. Nothing here is a claim about consciousness.

    python -m bsde.experiments.e81_stimulus_invariance
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

TABLE = os.path.join(RESULTS, "dosei_holdout_features.csv")
OUT = os.path.join(RESULTS, "e81_stimulus_invariance.json")
USED_TABLES = ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv")

META = {"recording", "t_s", "soc", "moaas", "propofol", "endoscopy", "n_finite"}
CTRL_POS, CTRL_NEG = "ecg_hr", "_CTRL_noise"
MIN_PER_SIDE = 5
MIN_RECORDINGS, MIN_CELLS = 15, 25
EQUIV = 0.25
N_BOOT = 10000
PLACEBO_DRAWS = 200
SEED = 20260731

EXPECT_SENSITIVE = ("emg_index", "emg_beta_gamma_fraction", "emg_kurtosis", "bis_rbr")
EXPECT_INVARIANT = ("relative_delta_power", "exponent_low", "pac_slow_alpha")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def used_recordings() -> set:
    out = set()
    for name in USED_TABLES:
        p = os.path.join(RESULTS, name)
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            rd = csv.DictReader(fh)
            key = "recording" if "recording" in (rd.fieldnames or []) else "recording_id"
            for r in rd:
                if r.get(key):
                    out.add(r[key].split("@")[0])
    return out


def cells(rows, feats, rng, permute=False):
    out = defaultdict(dict)
    for rec, rs in rows.items():
        mo = np.array([_f(r["moaas"]) for r in rs])
        st = np.array([_f(r["endoscopy"]) for r in rs])
        vals = {f: np.array([_f(r.get(f, "")) for r in rs]) for f in feats}
        vals[CTRL_POS] = np.array([_f(r.get("ecg_hr", "")) for r in rs])
        vals[CTRL_NEG] = rng.normal(size=len(rs))
        sd = {f: float(np.nanstd(v)) for f, v in vals.items()}
        for L in sorted(set(mo[np.isfinite(mo)].tolist())):
            at = np.isfinite(mo) & (mo == L) & np.isfinite(st)
            on, off = at & (st == 1), at & (st == 0)
            if on.sum() < MIN_PER_SIDE or off.sum() < MIN_PER_SIDE:
                continue
            idx = np.where(at)[0]
            if permute:
                lab = rng.permutation(np.concatenate([np.ones(on.sum()), np.zeros(off.sum())]))
                on_i, off_i = idx[lab == 1], idx[lab == 0]
            else:
                on_i, off_i = np.where(on)[0], np.where(off)[0]
            for f, v in vals.items():
                if not np.isfinite(sd[f]) or sd[f] < 1e-12:
                    continue
                g = (np.nanmean(v[on_i]) - np.nanmean(v[off_i])) / sd[f]
                if np.isfinite(g):
                    out[(rec, L)][f] = float(g)
    return out


def boot(cell_map, feat, seed, n_boot=N_BOOT):
    per_rec = defaultdict(list)
    for (rec, _), d in cell_map.items():
        if feat in d:
            per_rec[rec].append(d[feat])
    recs = sorted(per_rec)
    if len(recs) < 5:
        return (float("nan"),) * 3 + (0,)
    means = np.array([np.mean(per_rec[r]) for r in recs])
    rng = np.random.default_rng(seed)
    bs = means[rng.integers(0, means.size, size=(n_boot, means.size))].mean(axis=1)
    return float(means.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), len(recs)


def classify(pt, lo, hi):
    if not np.isfinite(pt):
        return "NOT-COMPUTABLE"
    if (lo > 0 and hi > 0) or (lo < 0 and hi < 0):
        return "STIMULUS-SENSITIVE"
    if lo > -EQUIV and hi < EQUIV:
        return "STIMULUS-INVARIANT"
    return "UNDETERMINED"


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} does not exist yet"); return 2
    rows = defaultdict(list)
    with open(TABLE, newline="") as fh:
        rd = csv.DictReader(fh)
        feats = [c for c in (rd.fieldnames or []) if c not in META and c != CTRL_POS]
        for r in rd:
            rows[r["recording"]].append(r)
    print(f"{len(rows)} recordings, {sum(len(v) for v in rows.values())} windows, {len(feats)} features")

    res = {"gates": {}, "controls": {}, "features": {}}
    overlap = sorted(set(rows) & used_recordings())
    res["gates"]["G1_overlap"], res["gates"]["G1_pass"] = overlap, not overlap
    print(f"G1 held out   {len(overlap)} overlapping   {'PASS' if not overlap else 'FAIL'}")

    rng = np.random.default_rng(SEED)
    cm = cells(rows, feats, rng)
    n_rec = len({k[0] for k in cm})
    res["gates"].update({"G2_recordings": n_rec, "G2_cells": len(cm),
                         "G2_pass": bool(n_rec >= MIN_RECORDINGS and len(cm) >= MIN_CELLS)})
    print(f"G2 coverage   {n_rec} recordings, {len(cm)} cells   "
          f"{'PASS' if res['gates']['G2_pass'] else 'FAIL'}")

    for c, label in ((CTRL_POS, "G3 heart rate"), (CTRL_NEG, "G4 noise")):
        pt, lo, hi, n = boot(cm, c, SEED + 1)
        cls = classify(pt, lo, hi)
        res["controls"][c] = {"gap": pt, "lo": lo, "hi": hi, "n_rec": n, "class": cls}
        print(f"{label:14s} {c:14s} gap {pt:+.3f} [{lo:+.3f}, {hi:+.3f}]  {cls}")
    res["gates"]["G3_pass"] = res["controls"][CTRL_POS]["class"] == "STIMULUS-SENSITIVE"
    res["gates"]["G4_pass"] = res["controls"][CTRL_NEG]["class"] != "STIMULUS-SENSITIVE"

    if not all(res["gates"][k] for k in ("G1_pass", "G2_pass", "G3_pass", "G4_pass")):
        print("\nGATE FAILED -- no feature is classified; the verdict is ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    plac = defaultdict(list)
    for d in range(PLACEBO_DRAWS):
        pcm = cells(rows, feats, np.random.default_rng(SEED + 500 + d), permute=True)
        for f in feats:
            v = [x[f] for x in pcm.values() if f in x]
            if v:
                plac[f].append(float(np.mean(v)))

    print(f"\n{'feature':<28s} {'gap':>8s} {'95% CI':>20s} {'n':>4s}  class                predicted")
    sens, inv, und = [], [], []
    for f in feats:
        pt, lo, hi, n = boot(cm, f, SEED + 2)
        cls = classify(pt, lo, hi)
        pv = np.asarray(plac.get(f, []), float)
        if cls == "STIMULUS-SENSITIVE" and pv.size and \
                np.percentile(pv, 2.5) <= pt <= np.percentile(pv, 97.5):
            cls = "WITHDRAWN-BY-PLACEBO"
        pred = ("sensitive" if f in EXPECT_SENSITIVE else
                "invariant" if f in EXPECT_INVARIANT else "-")
        res["features"][f] = {"gap": pt, "lo": lo, "hi": hi, "n_rec": n, "class": cls,
                              "predicted": pred}
        (sens if cls == "STIMULUS-SENSITIVE" else
         inv if cls == "STIMULUS-INVARIANT" else und).append(f)
        print(f"{f:<28s} {pt:+8.3f} [{lo:+8.3f}, {hi:+8.3f}] {n:>4d}  {cls:<20s} {pred}")

    hits = [f for f in EXPECT_SENSITIVE if res["features"].get(f, {}).get("class") == "STIMULUS-SENSITIVE"]
    miss = [f for f in EXPECT_INVARIANT
            if res["features"].get(f, {}).get("class") == "STIMULUS-SENSITIVE"]
    res["verdict"] = (f"SENSITIVE {sens}; INVARIANT {inv}; UNDETERMINED {len(und)}. "
                      f"Pre-declared sensitive that were: {hits} of {list(EXPECT_SENSITIVE)}. "
                      f"Pre-declared invariant that were NOT: {miss}. "
                      f"INVARIANT is a necessary condition passed at +-{EQUIV} SD, never a sufficient one.")
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
