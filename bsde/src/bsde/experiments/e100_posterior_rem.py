"""E100 -- Is the MEASURE wrong rather than the claim? Does posterior low-frequency power place REM with wake?

REGISTERED WHILE `sleep_edfx_channel_spectra.csv` IS EXTRACTING. What has been seen of it: three windows of
subject `SC4001E0` (stages W, N1, N2) from a smoke test -- rule 26 broken again, and **`SC4001E0` is
excluded below**, named in the code, as `sub-001` and `sub-02` were. The contrast under test, REM's
position on the wake-to-N3 axis, was not among what was printed.

=========================================================================================================
THE PROBLEM THIS EXISTS TO SETTLE
=========================================================================================================
Two orderings of sleep exist and they come apart at exactly one stage.

    AROUSAL / RESPONSIVENESS   W > N1 > N2 > N3, with REM behaviourally unresponsive (atonia)
    CONSCIOUS EXPERIENCE       REM ~ W > N1 > N2 > N3, from dream report on awakening

**REM is the diagnostic stage**: vivid experience, no behavioural output. Any coordinate claiming to track
consciousness rather than arousal has to place it near wake.

E95 measured, on the whole-head aperiodic coordinate with the best reference this project has:
W +0.2792, N1 -0.1840, **REM -0.2843**, N2 -0.5025, N3 -0.6168 -- **REM at 0.629 of the way from wake to
N3**, past N1, with an interval that does not overlap N1's. That matches arousal and contradicts
experience, which is the strongest evidence yet that the coordinate is an arousal axis.

**But the measure may be wrong rather than the claim, and the literature says exactly how.** Siclari et
al., *Nature Neuroscience* 2017 (PMID 28394322, verified through E-utilities): dreaming occurs in both REM
and NREM, and "reports of dream experience were associated with local decreases in low-frequency activity
in **posterior** cortical regions". A whole-head average cannot express a posterior-local effect. Every
sleep table in this repository medians across channels; none can test it.

*(That sentence is what the abstract says. The band is not named in it and the full text has not been read
here, so 1-4 Hz below is OUR operationalisation, not theirs -- rule 42.)*

=========================================================================================================
ESTIMAND
=========================================================================================================
For each subject and each measure M, REM's position on that subject's own wake-to-N3 axis:

    position(M) = ( M[REM] - M[W] ) / ( M[N3] - M[W] )

0 means REM sits at wake, 1 means it sits at deep sleep. Normalising by the subject's own W-to-N3 span
makes measures with different units and different directions directly comparable, and removes any
subject-specific gain (rule 57).

    P1  PRIMARY.  position(`posterior_rel_delta`) - position(`whole_head_exponent`), paired within
                  subject, Cohen's d_z with a subject bootstrap. **PREDICTED NEGATIVE**: posterior
                  low-frequency power places REM closer to wake than the whole-head coordinate does.
    P2  LOCALITY. position(`posterior_rel_delta`) - position(`frontal_rel_delta`), paired. **PREDICTED
                  NEGATIVE.** This is the actual test of Siclari's claim: the effect must be POSTERIOR. If
                  frontal does the same thing, the finding is about low-frequency power in general and the
                  locality that motivated the design is absent.

Primary band is **1-4 Hz** (`rel_delta`); **0.5-8 Hz** (`rel_low`) is the declared secondary, reported
whatever the primary does. Declaring which is primary before either is computed is the whole point of
emitting both.

VERDICT, wrong direction FIRST (rule 37):
    (a) P1's interval excludes 0 and is POSITIVE -> REVERSED. Posterior low-frequency places REM FURTHER
        from wake than the whole-head coordinate. Not a null: it would mean the posterior reduction makes
        the arousal reading stronger, and the Siclari-motivated design is refuted by its own measure.
    (b) P1's interval includes 0 -> NO IMPROVEMENT. **The measure is not the problem.** A posterior
        low-frequency reduction does not place REM more wake-like, so E95's arousal reading survives the
        best available challenge to it, and that strengthens rather than weakens the conclusion.
    (c) P1 negative -> IMPROVES, subject to P2 and to the muscle control below.

GATES (rule 40):
    G1  COVERAGE.  >= 50 subjects with all five stages present in both tables.
    G2  THE AXIS EXISTS.  Per subject and measure, |M[N3] - M[W]| must be non-zero; subjects failing it
        for any measure are dropped and counted. A position is undefined on a degenerate axis.
    G3  KNOWN EFFECT.  Delta power must INCREASE from W to N3 in a clear majority of subjects on both
        channels -- textbook, and if it does not hold the staging or the measure is broken and nothing
        below is interpretable. Compared against the same fraction for a per-subject Gaussian control
        rather than a fixed threshold (rule 63).
    G4  MUSCLE.  REM's defining feature is atonia, so muscle differs between REM and every NREM stage by
        construction, and E70 measured that a related REM placement was **58.7 % attributable to submental
        EMG** against a 27.6 % mechanical placebo. The submental channel's OWN position on the wake-to-N3
        axis is reported, and P1 is recomputed after residualising every measure on it within subject.
        **If P1 survives only before that adjustment it is muscle**, and the verdict says so.

SCOPE. Position on an axis is not experience. A measure placing REM near wake would be consistent with
tracking consciousness; it would not demonstrate it, because nothing here collects a dream report. This is
a test of whether the SPATIAL REDUCTION is what loses REM, not a test of consciousness.

    python -m bsde.experiments.e100_posterior_rem
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

OUT = os.path.join(RESULTS, "e100_posterior_rem.json")
BURNED = {"SC4001E0-PSG"}
STAGES = ("W", "N1", "N2", "N3", "REM")
PRIMARY_BAND, SECONDARY_BAND = "rel_delta", "rel_low"
MIN_SUBJECTS = 50
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    """subject -> stage -> {measure: value}, joined across the three tables on recording_id."""
    per = defaultdict(dict)
    spec = os.path.join(RESULTS, "sleep_edfx_channel_spectra.csv")
    if not os.path.exists(spec):
        return None
    for r in csv.DictReader(open(spec, newline="")):
        if r["subject"] in BURNED or r["label"] not in STAGES:
            continue
        per[r["subject"]].setdefault(r["label"], {}).update(
            {k: _f(r[k]) for k in r if k.startswith(("frontal_", "posterior_"))})
    for r in csv.DictReader(open(os.path.join(RESULTS, "sleep_edfx_five_stage.csv"), newline="")):
        rid = r.get("recording_id", "")
        if "@" not in rid:
            continue
        s, st = r.get("subject", ""), rid.rsplit("@", 1)[1]
        if s in per and st in per[s]:
            per[s][st]["whole_head_exponent"] = _f(r.get("whole_head_exponent", ""))
    emg = os.path.join(RESULTS, "sleep_edfx_emg.csv")
    if os.path.exists(emg):
        for r in csv.DictReader(open(emg, newline="")):
            s, st = r.get("subject", ""), r.get("label", "")
            if s in per and st in per[s]:
                per[s][st]["emg"] = _f(r.get("emg_mean", ""))
    return per


def position(vals, measure):
    w, n3, rem = vals["W"].get(measure), vals["N3"].get(measure), vals["REM"].get(measure)
    if not all(np.isfinite(x) for x in (w, n3, rem) if x is not None):
        return float("nan")
    if w is None or n3 is None or rem is None or abs(n3 - w) < 1e-12:
        return float("nan")
    return (rem - w) / (n3 - w)


def dz(v):
    v = v[np.isfinite(v)]
    if v.size < 5 or v.std(ddof=1) < 1e-12:
        return float("nan")
    return float(v.mean() / v.std(ddof=1))


def boot_dz(v, seed, reps=REPS):
    v = v[np.isfinite(v)]
    if v.size < 5:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    out = sorted(b.mean() / b.std(ddof=1) for b in
                 (v[rng.integers(0, v.size, v.size)] for _ in range(reps)) if b.std(ddof=1) > 1e-12)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    per = load()
    if per is None:
        print("ABSENT: sleep_edfx_channel_spectra.csv does not exist yet"); return 2
    subs = [s for s, d in per.items() if all(k in d for k in STAGES)]
    res = {"gates": {}, "excluded": sorted(BURNED), "positions": {}}
    print(f"{len(per)} subjects in the spectra table, {len(subs)} with all five stages "
          f"(excluding {sorted(BURNED)})")

    MEAS = {"posterior_delta": f"posterior_{PRIMARY_BAND}",
            "frontal_delta": f"frontal_{PRIMARY_BAND}",
            "posterior_low": f"posterior_{SECONDARY_BAND}",
            "frontal_low": f"frontal_{SECONDARY_BAND}",
            "whole_head_exponent": "whole_head_exponent",
            "emg": "emg"}
    pos = {k: [] for k in MEAS}
    keep = []
    for s in subs:
        p = {k: position(per[s], m) for k, m in MEAS.items()}
        core = ("posterior_delta", "frontal_delta", "whole_head_exponent")
        if all(np.isfinite(p[k]) for k in core):
            keep.append(s)
            for k in MEAS:
                pos[k].append(p[k])
    for k in MEAS:
        pos[k] = np.asarray(pos[k], float)
    res["gates"].update({"G1_subjects": len(keep), "G1_pass": bool(len(keep) >= MIN_SUBJECTS),
                         "G2_dropped": len(subs) - len(keep)})
    print(f"G1 coverage   {len(keep)} subjects usable, {len(subs) - len(keep)} dropped on a degenerate "
          f"axis   {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    rng = np.random.default_rng(SEED)
    inc = {}
    for ch in ("frontal", "posterior"):
        v = np.array([per[s]["N3"][f"{ch}_{PRIMARY_BAND}"] - per[s]["W"][f"{ch}_{PRIMARY_BAND}"]
                      for s in keep], float)
        inc[ch] = float(np.mean(v[np.isfinite(v)] > 0))
    ctrl = float(np.mean(rng.normal(size=len(keep)) > 0))
    g3 = bool(min(inc.values()) > ctrl)
    res["gates"].update({"G3_frac_delta_increases": inc, "G3_control": ctrl, "G3_pass": g3})
    print(f"G3 known effect  delta increases W->N3 in {inc['frontal']:.3f} of subjects frontally, "
          f"{inc['posterior']:.3f} posteriorly (Gaussian control {ctrl:.3f})   "
          f"{'PASS' if g3 else 'FAIL'}")

    print(f"\nREM position on each subject's own W->N3 axis (0 = at wake, 1 = at N3)")
    for k in MEAS:
        v = pos[k][np.isfinite(pos[k])]
        if v.size:
            lo, hi = np.percentile(v, [25, 75])
            res["positions"][k] = {"median": float(np.median(v)), "iqr": [float(lo), float(hi)],
                                   "n": int(v.size)}
            print(f"   {k:22s} median {np.median(v):+.3f}  IQR [{lo:+.3f}, {hi:+.3f}]  n={v.size}")

    if not (res["gates"]["G1_pass"] and g3):
        print("\nGATE FAILED -- no primary evaluated. ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    def arm(name, a, b, seed):
        d = pos[a] - pos[b]
        pt, (lo, hi) = dz(d), boot_dz(d, seed)
        res[name] = {"a": a, "b": b, "d_z": pt, "lo": lo, "hi": hi,
                     "median_diff": float(np.nanmedian(d))}
        print(f"{name:14s} position({a}) - position({b}): d_z {pt:+.3f} [{lo:+.3f}, {hi:+.3f}]  "
              f"median diff {np.nanmedian(d):+.3f}")
        return pt, lo, hi

    print()
    p1, p1lo, p1hi = arm("P1 primary", "posterior_delta", "whole_head_exponent", SEED + 1)
    p2, p2lo, p2hi = arm("P2 locality", "posterior_delta", "frontal_delta", SEED + 2)
    arm("S1 secondary", "posterior_low", "whole_head_exponent", SEED + 3)

    # G4 muscle: the submental channel's own position, and P1 after residualising on it
    if np.isfinite(pos["emg"]).sum() >= MIN_SUBJECTS:
        e = pos["emg"]
        print(f"\nG4 muscle     submental EMG's own REM position: median "
              f"{np.nanmedian(e):+.3f} over {int(np.isfinite(e).sum())} subjects")
        ok = np.isfinite(e) & np.isfinite(pos["posterior_delta"]) & np.isfinite(pos["whole_head_exponent"])
        def resid(y):
            A = np.column_stack([np.ones(ok.sum()), e[ok]])
            return y[ok] - A @ np.linalg.lstsq(A, y[ok], rcond=None)[0]
        d_adj = resid(pos["posterior_delta"]) - resid(pos["whole_head_exponent"])
        pa, (la, ha) = dz(d_adj), boot_dz(d_adj, SEED + 4)
        res["G4_muscle_adjusted_P1"] = {"d_z": pa, "lo": la, "hi": ha, "n": int(ok.sum())}
        print(f"              P1 after residualising on EMG: d_z {pa:+.3f} [{la:+.3f}, {ha:+.3f}]")
        survives = bool(np.isfinite(la) and ((la > 0 and ha > 0) or (la < 0 and ha < 0)))
    else:
        res["G4_muscle_adjusted_P1"] = None
        survives = None
        print("\nG4 muscle     submental EMG unavailable for enough subjects -- NOT TESTED, and a P1 "
              "result is therefore not muscle-controlled")

    if not np.isfinite(p1lo):
        v = "NOT-COMPUTABLE"
    elif p1lo > 0:
        v = ("REVERSED -- posterior low-frequency power places REM FURTHER from wake than the whole-head "
             "coordinate does. The posterior reduction makes the arousal reading stronger, and the "
             "Siclari-motivated design is refuted by its own measure.")
    elif p1hi < 0:
        loc = "and the effect is posterior-specific" if p2hi < 0 else \
              "but P2 does not show posterior specificity, so this is about low-frequency power in " \
              "general rather than about locality"
        mus = ("" if survives is None else
               "; it SURVIVES adjustment for submental EMG" if survives else
               "; **it does NOT survive adjustment for submental EMG and is therefore muscle**")
        v = f"IMPROVES -- posterior low-frequency places REM closer to wake, {loc}{mus}."
    else:
        v = ("NO IMPROVEMENT -- a posterior low-frequency reduction does NOT place REM more wake-like. "
             "**The measure is not the problem.** E95's reading that the coordinate tracks arousal rather "
             "than experience survives the best available challenge to it, which strengthens it.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
