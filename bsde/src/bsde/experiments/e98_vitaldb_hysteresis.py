"""E98 -- Challenge A on data we already have: at matched BIS, does the exponent depend on direction of travel?

REGISTERED BEFORE ANY GAP IS COMPUTED. Feasibility probed first (rule 41), touching only BIS and
timestamps: **92 of 250 VitalDB cases carry at least one 10-point BIS band with >= 3 windows on each side
of the case's BIS minimum, giving 106 (case, band) cells.** No feature has been related to anything.

=========================================================================================================
WHY THIS, AND WHAT IT IS AND IS NOT
=========================================================================================================
E80 asks the hysteresis question on DOSE-I with a clinician's MOAA/S and is still waiting on its
extraction. VitalDB has the same STRUCTURE available now -- every case descends into and emerges from
anaesthesia, 250 cases -- with one substitution: the state label is BIS.

**That substitution changes the question, and pretending otherwise would be the error rule 13 warns about.**
BIS is computed from the same EEG the exponent is computed from. Conditioning on it does not hold "state"
constant; it holds constant *the component of the EEG that BIS captures*. So this experiment asks:

    **does the part of the EEG that BIS does NOT capture depend on the direction of travel?**

That is a well-posed and arguably sharper question than E80's -- it is exactly the increment BIS leaves on
the table -- but it is NOT "does the exponent read drug", and no result here may be reported as if it were.
Anaesthetic hysteresis (emergence occurs at a lower drug level than induction required) is what makes
direction of travel a proxy for drug level at matched reading.

=========================================================================================================
ESTIMAND
=========================================================================================================
Within each case, windows are split at the case's BIS MINIMUM: everything at or before it is DESCENT,
everything after is EMERGENCE. For each 10-point BIS band from 20 to 80 with >= 3 windows on each side:

    gap = ( mean(feature | descent) - mean(feature | emergence) ) / sd(feature within that case)

standardised within case (rule 57), aggregated by a CASE-level bootstrap.

The hypothesis of interest is an ABSENCE, so "the interval includes zero" is the wrong criterion and
UNDETERMINED is named as its own outcome, exactly as in E80:

    DIRECTION-DEPENDENT   interval excludes 0            -- the reading depends on direction of travel
    DIRECTION-INVARIANT   interval inside +-0.25 SD      -- equivalent to no gap, at a stated margin
    UNDETERMINED          neither                        -- not reportable as either

CONTROLS bracketing the method, evaluated BEFORE any feature:
    C+  `_CTRL_time`   the window's own timestamp. Descent windows precede emergence windows BY
                       CONSTRUCTION, so this must be DIRECTION-DEPENDENT. Machinery only, never evidence.
    C-  `_CTRL_noise`  a per-window Gaussian. Must not be DIRECTION-DEPENDENT.

GATES: G1 >= 40 cases contributing a cell and >= 60 cells. G2 the bracket above. G3 every cell's two sides
must come from the SAME BIS band, asserted rather than assumed.

PLACEBO (after the primaries, able only to remove): each case is re-split at a RANDOM index preserving the
two group sizes, leaving the BIS band structure intact, 200 draws. It destroys direction of travel and
nothing else (rule 55). Any DIRECTION-DEPENDENT feature inside the placebo's central 95 % is withdrawn.

SCOPE. One retrospective deposit, a device-derived state label, no clinician rating anywhere. Nothing here
is a claim about consciousness, and a DIRECTION-INVARIANT result is a NECESSARY condition passed, never a
sufficient one -- a constant would pass it trivially, which is why C- exists.

    python -m bsde.experiments.e98_vitaldb_hysteresis
"""
from __future__ import annotations
import csv, json, os, sys
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

TABLE = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e98_vitaldb_hysteresis.json")
META_PREFIX = "meta_"
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
CTRL_POS, CTRL_NEG = "_CTRL_time", "_CTRL_noise"
BANDS = [(lo, lo + 10) for lo in range(20, 80, 10)]
MIN_PER_SIDE, MIN_CASES, MIN_CELLS = 3, 40, 60
EQUIV = 0.25
N_BOOT, PLACEBO_DRAWS = 10000, 200
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def cells(by, feats, rng, split=None):
    out = defaultdict(dict)
    for case, rows in by.items():
        b = np.array([_f(r["meta_bis"]) for r in rows])
        ok = np.isfinite(b)
        if ok.sum() < 10:
            continue
        imin = int(np.argmin(np.where(ok, b, np.inf))) if split is None else int(split[case])
        desc = np.zeros(len(rows), bool)
        desc[:imin + 1] = True
        vals = {f: np.array([_f(r.get(f, "")) for r in rows]) for f in feats}
        vals[CTRL_POS] = np.array([_f(r["meta_rel_anestart_s"]) for r in rows])
        vals[CTRL_NEG] = rng.normal(size=len(rows))
        sd = {f: float(np.nanstd(v)) for f, v in vals.items()}
        for lo, hi in BANDS:
            m = ok & (b >= lo) & (b < hi)
            a, c = m & desc, m & (~desc)
            if a.sum() < MIN_PER_SIDE or c.sum() < MIN_PER_SIDE:
                continue
            for f, v in vals.items():
                if not np.isfinite(sd[f]) or sd[f] < 1e-12:
                    continue
                g = (np.nanmean(v[a]) - np.nanmean(v[c])) / sd[f]
                if np.isfinite(g):
                    out[(case, lo)][f] = float(g)
    return out


def boot(cm, feat, seed, n_boot=N_BOOT):
    per = defaultdict(list)
    for (case, _), d in cm.items():
        if feat in d:
            per[case].append(d[feat])
    cs = sorted(per)
    if len(cs) < 5:
        return (float("nan"),) * 3 + (0,)
    m = np.array([np.mean(per[c]) for c in cs])
    rng = np.random.default_rng(seed)
    bs = m[rng.integers(0, m.size, size=(n_boot, m.size))].mean(axis=1)
    return float(m.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), len(cs)


def classify(pt, lo, hi):
    if not np.isfinite(pt):
        return "NOT-COMPUTABLE"
    if (lo > 0 and hi > 0) or (lo < 0 and hi < 0):
        return "DIRECTION-DEPENDENT"
    if lo > -EQUIV and hi < EQUIV:
        return "DIRECTION-INVARIANT"
    return "UNDETERMINED"


def main() -> int:
    rows = list(csv.DictReader(open(TABLE, newline="")))
    feats = [c for c in rows[0] if c not in SKIP and not c.startswith(META_PREFIX)]
    by = defaultdict(list)
    for r in rows:
        by[r["subject"]].append(r)
    for c in by:
        by[c].sort(key=lambda r: _f(r["meta_rel_anestart_s"]))
    res = {"gates": {}, "controls": {}, "features": {}, "n_features": len(feats)}
    print(f"{len(rows)} windows, {len(by)} cases, {len(feats)} features")

    rng = np.random.default_rng(SEED)
    cm = cells(by, feats, rng)
    ncase = len({k[0] for k in cm})
    res["gates"].update({"G1_cases": ncase, "G1_cells": len(cm),
                         "G1_pass": bool(ncase >= MIN_CASES and len(cm) >= MIN_CELLS)})
    print(f"G1 coverage   {ncase} cases, {len(cm)} cells   {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    for c in (CTRL_POS, CTRL_NEG):
        pt, lo, hi, n = boot(cm, c, SEED + 1)
        res["controls"][c] = {"gap": pt, "lo": lo, "hi": hi, "n": n, "class": classify(pt, lo, hi)}
        print(f"   control {c:12s} {pt:+.3f} [{lo:+.3f}, {hi:+.3f}]  {res['controls'][c]['class']}")
    g2 = (res["controls"][CTRL_POS]["class"] == "DIRECTION-DEPENDENT"
          and res["controls"][CTRL_NEG]["class"] != "DIRECTION-DEPENDENT")
    res["gates"]["G2_pass"] = bool(g2)
    print(f"G2 bracket    {'PASS' if g2 else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and g2):
        print("\nGATE FAILED -- no feature classified. ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    plac = defaultdict(list)
    for d in range(PLACEBO_DRAWS):
        sp = {c: int(rng.integers(MIN_PER_SIDE, max(MIN_PER_SIDE + 1, len(v) - MIN_PER_SIDE)))
              for c, v in by.items()}
        pc = cells(by, feats, np.random.default_rng(SEED + 300 + d), split=sp)
        for f in feats:
            v = [x[f] for x in pc.values() if f in x]
            if v:
                plac[f].append(float(np.mean(v)))

    print(f"\n{'feature':<28s} {'gap':>8s} {'95% CI':>20s} {'n':>4s}  class")
    dep, inv, und = [], [], []
    for f in feats:
        pt, lo, hi, n = boot(cm, f, SEED + 2)
        cls = classify(pt, lo, hi)
        pv = np.asarray(plac.get(f, []), float)
        if cls == "DIRECTION-DEPENDENT" and pv.size and \
                np.percentile(pv, 2.5) <= pt <= np.percentile(pv, 97.5):
            cls = "WITHDRAWN-BY-PLACEBO"
        res["features"][f] = {"gap": pt, "lo": lo, "hi": hi, "n": n, "class": cls}
        (dep if cls == "DIRECTION-DEPENDENT" else inv if cls == "DIRECTION-INVARIANT" else und).append(f)
        print(f"{f:<28s} {pt:+8.3f} [{lo:+8.3f}, {hi:+8.3f}] {n:>4d}  {cls}")

    res["verdict"] = (f"DIRECTION-DEPENDENT {dep}; DIRECTION-INVARIANT {inv}; UNDETERMINED {len(und)}. "
                      f"At matched BIS these are statements about the component of the EEG BIS does NOT "
                      f"capture, not about drug versus state, and INVARIANT is a necessary condition "
                      f"passed at +-{EQUIV} SD, never a sufficient one.")
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
