"""E79 -- Is our permutation entropy's edge over the deposit's PE31 a property of the MEASURE, or of the WINDOW?

REGISTERED BEFORE `dosei_window_control.csv` EXISTS. The extractor is committed in the same commit and had
not been run when this was written.

--------------------------------------------------------------------------------------------------------
THE NUMBER THIS EXISTS TO ATTACK
--------------------------------------------------------------------------------------------------------
E78, on 62 held-out DOSE-I recordings and 19,299 windows, measured

    mean_rec[ rho(pe_declared, MOAA/S) - rho(their_PE31, MOAA/S) ] = +0.0500 [+0.0177, +0.0849]

an interval excluding zero, and E78 **deliberately refused to claim it**. QUEUE.md Q37 names the reason:
the deposit's `pEEG_parameter_description.txt` gives an explicit window for every spectral measure --
`T=8 s` for columns 26-29 and 36, `T=16 s` for 37-41 -- and **none for any of its three permutation-entropy
columns**. Ours is 30 s. A longer window is a smoother estimate, and a smoother estimate tracks a
slowly-varying behavioural scale better for reasons that have nothing to do with the measure.

Rule 50: **before attributing a difference to X, measure the difference when X is held constant, and match
the baseline's statistical structure to the effect's.** Rule 54: a confound named in a registration is not
thereby controlled -- point at the line of code. This experiment is that line of code, and it holds the
window constant in BOTH directions, because each direction alone has a hole.

--------------------------------------------------------------------------------------------------------
CO-PRIMARIES. Both are reported whatever either does.
--------------------------------------------------------------------------------------------------------
    P1  SHORTEN OURS.   A8 = mean_rec[ rho(pe_8,  MOAA/S) - rho(their_PE31, MOAA/S) ]
                        Our PE recomputed over 8 s -- the window the deposit declares for its own spectral
                        measures -- with the declared band and tie threshold otherwise unchanged.

    P2  SMOOTH THEIRS.  B  = mean_rec[ rho(pe_30, MOAA/S) - rho(PE31_smooth30, MOAA/S) ]
                        Their column given the same ~30 s support ours has, by a causal 30-sample trailing
                        mean of its own 1 Hz series.

**Why both.** P1 alone is confounded the other way: shortening our window also makes our estimator noisier
in absolute terms, so a null there could be our loss rather than their gain. P2 alone assumes a trailing
mean is the right model of whatever smoothing their pipeline does, which is an assumption about an
undeclared parameter. **The two fail in opposite directions, so agreement between them is informative and
disagreement localises the problem.**

Recording-level bootstrap, 20,000 resamples, three seeds, the fraction of resamples on the wrong side of
zero reported beside every interval (rule 46).

PREDICTION WRITTEN NOW: **both A8 and B include zero** -- i.e. E78's +0.0500 is window length. This
predicts against a number this project measured and chose not to claim, which is the only reason the
number was left unclaimed.

--------------------------------------------------------------------------------------------------------
VERDICT RULE, per co-primary, wrong-direction branch FIRST and by name (rule 37)
--------------------------------------------------------------------------------------------------------
    (a) CI excludes 0 and NEGATIVE
            -> WORSE-AT-MATCHED-WINDOW. At equal support our PE tracks the clinician LESS well than the
               deposit's. E78's +0.0500 was not merely explained by window length, it was masking a deficit.
               This is not a null and must not print as one.
    (b) CI includes 0
            -> WINDOW-EXPLAINED. The edge does not survive matching, so it is a property of the window and
               not of the implementation. E78's descriptive interval must not be quoted as superiority.
    (c) CI excludes 0 and POSITIVE
            -> SURVIVES. The edge is a property of the implementation at matched support.

OVERALL: the two co-primaries are combined by the CONSERVATIVE rule, declared now: **`SURVIVES` overall
requires (c) on BOTH.** One (c) and one (b) is `PARTIAL` and is reported as not established, because the
whole design exists to stop a single framing carrying the claim.

--------------------------------------------------------------------------------------------------------
GATES, before the primaries (rule 40)
--------------------------------------------------------------------------------------------------------
    G1  HELD OUT    zero overlap with the 43 recordings this project used before E78, asserted here and
                    refused in the extractor. A window control run on scanned data controls nothing.
    G2  COVERAGE    >= 30 recordings with >= 10 windows carrying finite pe_8, pe_30, PE31, PE31_smooth30
                    and a MOAA/S taking more than one value.
    G3  THE ARMS DIFFER. `pe_8` must actually differ from `pe_30` (median within-recording rho between
                    them < 0.99) and `PE31_smooth30` from `PE31` (same test). If either pair is
                    effectively identical the corresponding control is a no-op and is reported
                    INAPPLICABLE rather than as evidence of anything (rule 40, and rule 55's requirement
                    that a control be able to change the statistic it controls for).
    G4  MONOTONE SUPPORT, descriptive and not gating: rho(pe_8), rho(pe_16), rho(pe_30) against MOAA/S are
                    all reported. **If tracking rises monotonically with window length, that IS the
                    smoothing explanation quantified**, and it is the single most legible number here.

SCOPE. This is about two implementations of one measure on one deposit against one behavioural scale. It
says nothing about consciousness, and a WINDOW-EXPLAINED verdict does not make either implementation wrong
-- it makes the comparison between them uninformative until support is matched.

    python -m bsde.experiments.e79_pe_window_control
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

TABLE = os.path.join(RESULTS, "dosei_window_control.csv")
OUT = os.path.join(RESULTS, "e79_pe_window_control.json")
USED_TABLES = ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv")

ARMS = ("pe_8", "pe_16", "pe_30", "their_pe31", "their_pe31_smooth30")
MIN_WINDOWS = 10
MIN_RECORDINGS = 30
N_BOOT = 20000
SEEDS = (31, 32, 33)
IDENTICAL_RHO = 0.99


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < MIN_WINDOWS:
        return float("nan")
    x, y = a[ok], b[ok]
    if len(set(x.tolist())) < 2 or len(set(y.tolist())) < 2:
        return float("nan")
    from scipy.stats import spearmanr
    return float(spearmanr(x, y).statistic)


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


def boot_mean(vals, seed, n_boot=N_BOOT):
    v = np.asarray([x for x in vals if np.isfinite(x)], float)
    if v.size < 3:
        return float("nan"), float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, v.size, size=(n_boot, v.size))].mean(axis=1)
    point = float(v.mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    wrong = float(np.mean(means <= 0.0)) if point > 0 else float(np.mean(means >= 0.0))
    return point, float(lo), float(hi), wrong


def verdict(point, lo, hi):
    if not np.isfinite(point):
        return "NOT-COMPUTABLE"
    if lo < 0 and hi < 0:
        return "WORSE-AT-MATCHED-WINDOW"
    if lo > 0 and hi > 0:
        return "SURVIVES"
    return "WINDOW-EXPLAINED"


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} does not exist yet"); return 2
    res = {"gates": {}, "primaries": {}, "descriptive": {}}
    rows = defaultdict(list)
    with open(TABLE, newline="") as fh:
        for r in csv.DictReader(fh):
            rows[r["recording"]].append(r)
    print(f"{len(rows)} recordings, {sum(len(v) for v in rows.values())} windows")

    overlap = sorted(set(rows) & used_recordings())
    res["gates"]["G1_overlap"] = overlap
    res["gates"]["G1_pass"] = not overlap
    print(f"G1 held out   {len(overlap)} overlapping   {'PASS' if not overlap else 'FAIL'}")

    rho = {a: [] for a in ARMS}
    within = {"pe_8_vs_pe_30": [], "pe31_vs_smooth30": []}
    kept = []
    for rec, rs in sorted(rows.items()):
        mo = np.array([_f(r["moaas"]) for r in rs])
        if np.isfinite(mo).sum() < MIN_WINDOWS or len(set(mo[np.isfinite(mo)].tolist())) < 2:
            continue
        col = {a: np.array([_f(r[a]) for r in rs]) for a in ARMS}
        if any(np.isfinite(col[a]).sum() < MIN_WINDOWS for a in ARMS):
            continue
        kept.append(rec)
        for a in ARMS:
            rho[a].append(spearman(col[a], mo))
        within["pe_8_vs_pe_30"].append(spearman(col["pe_8"], col["pe_30"]))
        within["pe31_vs_smooth30"].append(spearman(col["their_pe31"], col["their_pe31_smooth30"]))

    res["gates"]["G2_recordings"] = len(kept)
    res["gates"]["G2_pass"] = bool(len(kept) >= MIN_RECORDINGS)
    print(f"G2 coverage   {len(kept)} recordings   {'PASS' if len(kept) >= MIN_RECORDINGS else 'FAIL'}")

    g3 = {}
    for k, v in within.items():
        m = float(np.nanmedian(v))
        g3[k] = {"median_rho": m, "differ": bool(m < IDENTICAL_RHO)}
        print(f"G3 arms differ  {k:20s} median rho {m:+.4f}   "
              f"{'differ' if m < IDENTICAL_RHO else 'INAPPLICABLE (effectively identical)'}")
    res["gates"]["G3"] = g3

    print("\nG4 median within-recording rho vs MOAA/S (DESCRIPTIVE, gating nothing)")
    for a in ARMS:
        res["descriptive"][f"median_rho_{a}"] = float(np.nanmedian(rho[a]))
        print(f"    {a:22s} {np.nanmedian(rho[a]):+.4f}")
    trend = [float(np.nanmedian(rho[a])) for a in ("pe_8", "pe_16", "pe_30")]
    mono = trend[0] < trend[1] < trend[2]
    res["descriptive"]["monotone_in_window"] = bool(mono)
    print(f"    tracking {'RISES MONOTONICALLY' if mono else 'is not monotone'} with window length "
          f"({trend[0]:+.4f} -> {trend[1]:+.4f} -> {trend[2]:+.4f})")

    if not (res["gates"]["G1_pass"] and res["gates"]["G2_pass"]):
        print("\nGATE FAILED -- no primary is evaluated; the verdict is ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    verdicts = {}
    for name, a, b, label in (("P1", "pe_8", "their_pe31", "shorten ours to 8 s"),
                              ("P2", "pe_30", "their_pe31_smooth30", "smooth theirs to 30 s")):
        applicable = (g3["pe_8_vs_pe_30"]["differ"] if name == "P1"
                      else g3["pe31_vs_smooth30"]["differ"])
        d = [x - y for x, y in zip(rho[a], rho[b])]
        per_seed = {}
        for s in SEEDS:
            pt, lo, hi, wrong = boot_mean(d, s)
            per_seed[s] = {"D": pt, "lo": lo, "hi": hi, "frac_wrong_side": wrong,
                           "verdict": verdict(pt, lo, hi)}
        vs = {p["verdict"] for p in per_seed.values()}
        v = per_seed[SEEDS[0]]["verdict"] if len(vs) == 1 else "SEED-UNSTABLE"
        if not applicable:
            v = "INAPPLICABLE"
        verdicts[name] = v
        res["primaries"][name] = {"contrast": label, "per_seed": per_seed, "verdict": v}
        p0 = per_seed[SEEDS[0]]
        print(f"\n{name}  {label}:  D = {p0['D']:+.4f} [{p0['lo']:+.4f}, {p0['hi']:+.4f}]  "
              f"frac wrong side {p0['frac_wrong_side']:.4f}")
        print(f"    VERDICT {v}" + ("" if len(vs) == 1 else f"  (seeds disagree: {sorted(vs)})"))

    if verdicts["P1"] == verdicts["P2"] == "SURVIVES":
        overall = "SURVIVES"
    elif "WORSE-AT-MATCHED-WINDOW" in verdicts.values():
        overall = "WORSE-AT-MATCHED-WINDOW"
    elif "SURVIVES" in verdicts.values():
        overall = "PARTIAL -- not established; the conservative rule requires both co-primaries"
    else:
        overall = "WINDOW-EXPLAINED"
    res["verdict"] = overall
    print(f"\nOVERALL: {overall}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
