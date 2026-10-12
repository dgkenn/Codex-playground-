"""E80 -- Challenge A, without a drug column: which measures give the SAME reading at the same behavioural
state on the way DOWN and the way UP?

REGISTERED BEFORE `dosei_holdout_features.csv` EXISTS. A feasibility probe was run first, as rule 41
requires, and it touched only MOAA/S and timestamps -- **no candidate column was read.** On the 39
already-scanned recordings, 27 (69 %) carry at least one MOAA/S level with >= 5 windows on both descent
and emergence, giving 43 (recording, level) cells. The test itself runs on the held-out partition.

=========================================================================================================
THE IDEA, AND WHY IT IS NOT ANOTHER SIGN COMPARISON
=========================================================================================================
Challenge A asks whether a measure tracks consciousness or pharmacology. Every attempt this project has
made compares ACROSS arms -- propofol against sleep (E67, E74, E75), propofol against dexmedetomidine
(E35, E36) -- and every one is limited by the arms being different people, montages and deposits. E75's
aggregate came back a null, and `MASTER_PLAN.md` §9.35 names the structural blocker: drug arm, electrode
type and data quality are nested inside patient identity.

**Anaesthetic hysteresis dissolves that.** Loss and recovery of responsiveness do not occur at the same
drug level: emergence happens at a lower concentration than induction required -- "neural inertia". So at
a MATCHED behavioural state, the drug level is systematically DIFFERENT between descent and emergence.
Turn that round and it becomes a within-subject discriminator that needs no drug data at all:

    a measure that reads DRUG must differ between descent and emergence at the same MOAA/S
    a measure that reads STATE must not

Same patient, same electrodes, same session, same behavioural label. No cross-deposit transport, no
pharmacokinetic model, and **no use of the deposit's `Propofol` column, which was inspected and is a
sparse bolus-event marker (0 in 1,583 of 1,590 seconds in the first recording) rather than a
concentration.** That inspection is why the design is built this way.

=========================================================================================================
THE ESTIMAND, AND THE ONE DESIGN DECISION THAT MATTERS
=========================================================================================================
Descent is every window at or before the recording's MOAA/S minimum; emergence is every window at or
after it. For each (recording, MOAA/S level) cell with >= 5 windows on each side, and each feature:

    gap = ( mean(feature | descent) - mean(feature | emergence) ) / sd(feature within that recording)

standardised within recording so features on different scales are commensurable and a subject-specific
gain cannot dominate (rule 57). Aggregated across cells by a RECORDING-level bootstrap.

**THE HYPOTHESIS IS AN ABSENCE, SO "THE INTERVAL INCLUDES ZERO" IS THE WRONG CRITERION.** A wide interval
around zero means no power, not state-tracking, and reporting it as the latter is the error rule 48 names
in its own domain. This experiment therefore uses EQUIVALENCE: a feature is called state-tracking only if
its whole 95 % interval lies inside |gap| < 0.25 within-recording SD -- a margin fixed here, before any
value exists, at the conventional boundary of a small effect. Three outcomes per feature, and the
uninformative one is named:

    DRUG-LIKE     interval excludes 0            -- the reading depends on direction of travel
    STATE-LIKE    interval lies inside +-0.25    -- equivalent to no gap, at a stated margin
    UNDETERMINED  neither                        -- the honest majority outcome if power is short, and it
                                                   must not be reported as either of the other two

Benjamini-Hochberg at q = 0.05 across the tested features for the DRUG-LIKE calls; the STATE-LIKE calls
are equivalence claims and are reported with their intervals rather than with a corrected p, because a
multiplicity correction on an equivalence test makes it EASIER to pass and would be backwards.

=========================================================================================================
MACHINERY CONTROLS, bracketing the method (the E72 pattern that worked), evaluated BEFORE any feature
=========================================================================================================
    C+  `_CTRL_time`   the window's own timestamp, standardised the same way. Descent windows are earlier
                       than emergence windows BY CONSTRUCTION, so this must return DRUG-LIKE with a large
                       gap. **It is a machinery control and is never evidence about anything** (rule 49:
                       a control that cannot fail proves nothing about the features) -- it exists only to
                       show the pipeline can detect a gap that is really there.
    C-  `_CTRL_noise`  a per-window Gaussian draw. Must return STATE-LIKE or UNDETERMINED. If NOISE comes
                       back DRUG-LIKE the standardisation or the cell weighting is manufacturing gaps and
                       nothing below is interpretable.

    G1  HELD OUT   zero overlap with the 43 recordings already used, asserted here and enforced by the
                   extractor's `--exclude-used`.
    G2  COVERAGE   >= 20 recordings contributing >= 1 cell, and >= 30 cells in total.
    G3  BRACKET    C+ DRUG-LIKE and C- not DRUG-LIKE. Either failing refuses the whole experiment.

PLACEBO (after the primaries, able only to remove). Each recording is re-split at a RANDOM window index
drawn to preserve the two group sizes, instead of at its MOAA/S minimum, and every gap recomputed, 200
draws. **The MOAA/S level structure is left intact**, so the placebo destroys exactly the thing the design
depends on -- the direction of travel -- and nothing else (rule 55: match the destruction to the
estimand). Any feature whose real gap is inside the placebo distribution's central 95 % is withdrawn.

=========================================================================================================
WHAT NO OUTCOME LICENSES
=========================================================================================================
A STATE-LIKE feature has passed a NECESSARY condition, not a sufficient one: a measure that is constant
would pass it trivially, which is why C- exists and why every STATE-LIKE call is reported beside that
feature's own within-recording SD. Nothing here is a claim about consciousness, and one deposit of
propofol sedation does not establish behaviour under any other agent.

    python -m bsde.experiments.e80_hysteresis_state_vs_drug
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
OUT = os.path.join(RESULTS, "e80_hysteresis_state_vs_drug.json")
USED_TABLES = ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv")

# `endoscopy` added 2026-07-31, BEFORE this file was run and before any value in its table existed.
# The DOSE-I pEEG tables carry a binary Endoscopy stimulus marker (1 in 65,565 of 93,225 seconds
# across the first 60 recordings) which the extractor did not previously emit. It is METADATA, not
# a candidate: excluding it here keeps it out of the feature list. No threshold, cohort, contrast,
# gate or margin of this registration changes. `ecg_hr` (the deposit's Intellivue heart rate)
# was added in the same edit and for the same reason: it is a non-EEG physiological channel,
# it is METADATA here, and it exists so E81 has a positive control that does not beg its own
# question. Neither column is a candidate in this experiment.
SKIP = {"recording", "t_s", "soc", "moaas", "propofol", "endoscopy", "ecg_hr", "n_finite"}
CTRL_POS, CTRL_NEG = "_CTRL_time", "_CTRL_noise"
MIN_PER_SIDE = 5
MIN_RECORDINGS, MIN_CELLS = 20, 30
EQUIV = 0.25
N_BOOT = 10000
PLACEBO_DRAWS = 200
SEED = 20260731


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


def cells(rows, feats, rng, split_at=None):
    """(recording, level) -> standardised descent-minus-emergence gap per feature.

    `split_at` overrides the MOAA/S-minimum split with a given index, which is how the placebo works.
    """
    out = defaultdict(dict)
    for rec, rs in rows.items():
        rs = sorted(rs, key=lambda r: _f(r["t_s"]))
        mo = np.array([_f(r["moaas"]) for r in rs])
        if not np.isfinite(mo).any():
            continue
        imin = int(np.nanargmin(mo)) if split_at is None else int(split_at[rec])
        desc = np.zeros(len(rs), bool)
        desc[:imin + 1] = True
        vals = {f: np.array([_f(r.get(f, "")) for r in rs]) for f in feats}
        vals[CTRL_POS] = np.array([_f(r["t_s"]) for r in rs])
        vals[CTRL_NEG] = rng.normal(size=len(rs))
        sd = {f: float(np.nanstd(v)) for f, v in vals.items()}
        for L in sorted(set(mo[np.isfinite(mo)].tolist())):
            a = desc & (mo == L)
            b = (~desc) & (mo == L)
            if a.sum() < MIN_PER_SIDE or b.sum() < MIN_PER_SIDE:
                continue
            for f, v in vals.items():
                if not np.isfinite(sd[f]) or sd[f] < 1e-12:
                    continue
                g = (np.nanmean(v[a]) - np.nanmean(v[b])) / sd[f]
                if np.isfinite(g):
                    out[(rec, L)][f] = float(g)
    return out


def boot(cell_map, feat, seed, n_boot=N_BOOT):
    recs = sorted({k[0] for k in cell_map})
    per_rec = defaultdict(list)
    for (rec, _), d in cell_map.items():
        if feat in d:
            per_rec[rec].append(d[feat])
    recs = [r for r in recs if per_rec.get(r)]
    if len(recs) < 5:
        return (float("nan"),) * 3 + (0,)
    means = np.array([np.mean(per_rec[r]) for r in recs])
    rng = np.random.default_rng(seed)
    bs = means[rng.integers(0, means.size, size=(n_boot, means.size))].mean(axis=1)
    return float(means.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), len(recs)


def classify(pt, lo, hi):
    """Wrong-direction-agnostic by design: DRUG-LIKE is either sign. The uninformative cell is NAMED."""
    if not np.isfinite(pt):
        return "NOT-COMPUTABLE"
    if (lo > 0 and hi > 0) or (lo < 0 and hi < 0):
        return "DRUG-LIKE"
    if lo > -EQUIV and hi < EQUIV:
        return "STATE-LIKE"
    return "UNDETERMINED"


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} does not exist yet"); return 2
    rows = defaultdict(list)
    with open(TABLE, newline="") as fh:
        rd = csv.DictReader(fh)
        feats = [c for c in (rd.fieldnames or []) if c not in SKIP]
        for r in rd:
            rows[r["recording"]].append(r)
    print(f"{len(rows)} recordings, {sum(len(v) for v in rows.values())} windows, {len(feats)} features")

    res = {"gates": {}, "features": {}, "controls": {}}
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

    for c in (CTRL_POS, CTRL_NEG):
        pt, lo, hi, n = boot(cm, c, SEED + 1)
        res["controls"][c] = {"gap": pt, "lo": lo, "hi": hi, "n_rec": n, "class": classify(pt, lo, hi)}
        print(f"   control {c:12s} gap {pt:+.3f} [{lo:+.3f}, {hi:+.3f}]  {res['controls'][c]['class']}")
    g3 = (res["controls"][CTRL_POS]["class"] == "DRUG-LIKE"
          and res["controls"][CTRL_NEG]["class"] != "DRUG-LIKE")
    res["gates"]["G3_pass"] = bool(g3)
    print(f"G3 bracket    {'PASS' if g3 else 'FAIL'}")

    if not all(res["gates"][k] for k in ("G1_pass", "G2_pass", "G3_pass")):
        print("\nGATE FAILED -- no feature is classified; the verdict is ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # placebo: re-split at a random index preserving each recording's group sizes
    plac = defaultdict(list)
    for d in range(PLACEBO_DRAWS):
        sp = {}
        for rec, rs in rows.items():
            n = len(rs)
            sp[rec] = int(rng.integers(MIN_PER_SIDE, max(MIN_PER_SIDE + 1, n - MIN_PER_SIDE)))
        pcm = cells(rows, feats, np.random.default_rng(SEED + 100 + d), split_at=sp)
        for f in feats:
            v = [x[f] for x in pcm.values() if f in x]
            if v:
                plac[f].append(float(np.mean(v)))

    print(f"\n{'feature':<28s} {'gap':>8s} {'95% CI':>20s} {'n':>4s}  class          placebo")
    tested = []
    for f in feats:
        pt, lo, hi, n = boot(cm, f, SEED + 2)
        cls = classify(pt, lo, hi)
        pv = np.asarray(plac.get(f, []), float)
        inside = bool(pv.size and np.percentile(pv, 2.5) <= pt <= np.percentile(pv, 97.5))
        if cls == "DRUG-LIKE" and inside:
            cls = "WITHDRAWN-BY-PLACEBO"
        res["features"][f] = {"gap": pt, "lo": lo, "hi": hi, "n_rec": n, "class": cls,
                              "placebo_lo": float(np.percentile(pv, 2.5)) if pv.size else None,
                              "placebo_hi": float(np.percentile(pv, 97.5)) if pv.size else None}
        tested.append((f, cls))
        print(f"{f:<28s} {pt:+8.3f} [{lo:+8.3f}, {hi:+8.3f}] {n:>4d}  {cls:<14s} "
              f"[{np.percentile(pv, 2.5):+.3f}, {np.percentile(pv, 97.5):+.3f}]" if pv.size else "")

    state = [f for f, c in tested if c == "STATE-LIKE"]
    drug = [f for f, c in tested if c == "DRUG-LIKE"]
    und = [f for f, c in tested if c == "UNDETERMINED"]
    res["verdict"] = (f"STATE-LIKE {state}; DRUG-LIKE {drug}; UNDETERMINED {len(und)} features. "
                      f"A STATE-LIKE call is a NECESSARY condition passed at an equivalence margin of "
                      f"+-{EQUIV} within-recording SD, not a sufficient one, and UNDETERMINED is not "
                      f"evidence of either.")
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
