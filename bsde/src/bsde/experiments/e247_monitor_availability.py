#!/usr/bin/env python3
"""E247 -- the conventional monitor is recording and declaring itself unusable through emergence.

PRE-REGISTRATION. Written and committed before any statistic in it has been computed. The extraction it
reads (`bsde/scripts/vitaldb_monitor_availability_probe2.py`) fetches only the monitor's two 1 Hz numeric
tracks, never an EEG waveform or a candidate feature, so nothing in the input can encode a result about a
measure.

------------------------------------------------------------------------------------------------------
WHAT THIS IS, AND WHAT IT IS NOT (rule 95 -- a challenge definition drifts unless it is anchored)

Challenge C, verbatim: **"seeing a transition before the conventional monitor."**

**This experiment does not propose a candidate that satisfies challenge C. It is a finding about the
INCUMBENT that challenge C names.** The claim is that the conventional monitor is unavailable for most of
the emergence period, which bears directly on the challenge -- it says the comparator against which any
candidate would be judged is largely absent exactly when the transition happens -- but it is not itself a
solution to it, and it must never be written up as one.

The lead-time half of challenge C was ABANDONED earlier the same day, on its own pre-committed condition,
because the PK/PD hysteresis literature already compares two indices' equilibration lag head-to-head
(PMID 32925339) and already shows that epoch length alone moves the estimated lag across BIS's own value
(PMID 33415524: 4.31 / 3.96 / 5.78 / 6.54 min for approximate entropy at 2 / 10 / 30 / 60 s epochs
against BIS's 5.09 min). See `bsde/docs/DESIGN_2026_08_02_CHALLENGE_C_EXPOSURE_LANDMARK.md`.

------------------------------------------------------------------------------------------------------
THE SENTENCE THIS WOULD LICENSE, WRITTEN FIRST

> *In routine anaesthesia the processed depth-of-anaesthesia index is unavailable for the great majority
> of the emergence period even though the same sensor is still recording, so any analysis conditioned on
> a valid index during emergence is conditioned on a minority of cases -- selected by the return of the
> muscle activity that defines emergence.*

WHY IT IS WORTH TESTING, checked against the literature before the run rather than after (records
retrieved via E-utilities and parsed, never WebFetch -- rules 25 and 39):

  * The MECHANISM is old news and is not claimed here. Frontalis EMG corrupting and invalidating BIS as
    muscle tone returns has been described since at least 2004 and re-demonstrated in 2024:
    PMID 15109199 ("Spurious bispectral index values due to electromyographic activity", Eur J
    Anaesthesiol 2004), PMID 16115989 ("Different conditions that could result in the bispectral index
    indicating an incorrect hypnotic state", Anesth Analg 2005), PMID 37756246 ("The Influence of
    Electromyographic on Electroencephalogram-Based Monitoring: Putting the Forearm on the Forehead",
    Anesth Analg 2024). All three verified against retrieved esummary records.
  * The MAGNITUDE has never been measured. No paper reports index availability as a function of time
    relative to the end of a case, on any deposit.
  * The SELECTION framing has never been stated. Conditioning on "a valid index is present" conditions
    on the index not having failed -- and it fails for a reason correlated with the state being studied.
    That is the contribution, and it applies to every study and every model that uses intraoperative BIS
    as a reference or a training target, including ones built on this very deposit (PMID 42351597 uses
    5,471 VitalDB cases with BIS as ground truth).

------------------------------------------------------------------------------------------------------
COHORT. Every public VitalDB case carrying `BIS/BIS`, `BIS/SQI` and `BIS/EEG1_WAV` with a sane `aneend`:
**5,866**. No waveform is fetched. Cases are clustered by `subjectid`, never by `caseid` -- 237 of 6,388
VitalDB cases share a patient with another case and one patient has eight (`vitaldb.py`).

WINDOWS, on a 60 s grid over +/-1800 s about a landmark:
    REFERENCE   [-1800, -1200)   deep anaesthesia, well before any transition
    PRE         [ -600,  -300)
    POST        [ +300,  +600)

TWO SERIES PER CASE, and the difference between them is the whole design:
    `emit`  a bin containing at least one BIS sample of any kind      -- the device is still recording
    `t0`    a bin containing at least one sample with SQI > 0         -- the index is usable

`BIS/BIS` emits a literal 0.0 while the index is unavailable and 0 is inside the index's valid range, so
validity is a POSITIVE test on SQI rather than a ban on the value 0 (`vitaldb.py`, defect 1). `SQI > 0`
is the LOOSEST possible test and therefore OVERSTATES availability; it is the conservative choice for a
claim that availability is low, and G2 measures what the stricter thresholds do.

------------------------------------------------------------------------------------------------------
PRIMARIES. Both are computed BEFORE any gate is read (rule 37: a gate can only invalidate a pass).

P1 -- IS THE INDEX UNAVAILABLE WHILE THE DEVICE STILL RECORDS, AND IS THAT SPECIFIC TO THE TRANSITION?

    silent(window) = fraction of cases that are EMITTING in that window but have NO valid reading in it
    P1 = silent(POST | real landmark) - silent(POST | placebo landmark)

  The placebo landmark is a deterministic mid-case time at least 1,800 s from either transition, drawn
  from a hash of the case id so it cannot be re-rolled. Same case, same track, same code path, no
  transition. Without it a monotone decline in signal quality across any long recording would produce
  the same curve with nothing to do with emergence -- rule 64's random-split control, in the form this
  design needs. Cluster bootstrap over `subjectid`, 4,000 draws.

P2 -- IS THE SURVIVING POPULATION SELECTED? Among cases EMITTING in POST, compare those with a valid
  index against those without, on variables recorded independently of the monitor: age, sex, ASA, BMI,
  emergency status, anaesthesia type and case duration. Reported as standardised mean differences with
  cluster-bootstrap intervals, and as the out-of-fold AUC of a logistic model predicting validity from
  those variables alone. **P2 is the methodological claim and P1 is its precondition**; a large drop that
  selects nobody is a nuisance, and a drop that selects systematically is a bias in a literature.

------------------------------------------------------------------------------------------------------
GATES.

G1  THE INSTRUMENT CAN SEE AVAILABILITY AT ALL. In REFERENCE, availability at SQI > 0 must exceed 0.80.
    If the index is already mostly unavailable in deep anaesthesia there is no drop to measure and the
    curve is about something else. This is the aliveness gate (rules 33, 53) applied to a coverage
    statistic, and it can fail: nothing in the pipeline forces deep-anaesthesia availability to be high.

G2  THE THRESHOLD IS NOT DOING THE WORK. P1 must have the same SIGN at SQI > 0, >= 50 and >= 80, and the
    three values are reported side by side. Rule 63: a threshold picked as a round number measures the
    round number. The prediction registered here is that the stricter thresholds make the drop LARGER,
    because they can only remove valid bins -- so a stricter threshold reversing the sign would mean the
    statistic is not measuring what it is supposed to.

G3  THE PLACEBO IS NOT ON A SELECTED SUBSET. At least 0.80 of analysable cases must admit a valid
    placebo landmark (a case shorter than ~3,600 s of anaesthesia cannot have one). If fewer do, the
    control is computed on long cases only and P1 becomes a comparison of two cohorts rather than two
    landmarks -- which is rule 32, and it would be a defect rather than a caveat.

G4  SUPPORT. >= 1,000 cases contribute to P1 and >= 200 cases fall in each arm of P2. Below that the
    standardised differences are not resolvable against their own bootstrap width.

------------------------------------------------------------------------------------------------------
VERDICT RULE. The wrong-direction case is enumerated FIRST and explicitly (rule 37, six prior
occurrences in this project's catalogue). An interval excluding zero answers "is this nonzero", never
"does this support the hypothesis".

  (a) REVERSED   -- P1's interval lies entirely BELOW zero: the index is MORE available after the
                    transition than at a random mid-case time. This refutes the claim outright and is
                    reported as a refutation.
  (b) ABSENT     -- P1's interval includes zero. The drop, whatever its size, is reproduced by a
                    landmark where nothing happens, so it is a property of the recording and not of
                    emergence. The claim fails and P2 is NOT EVALUATED -- selection within a population
                    that was not differentially selected is not a finding (rule 48's discipline: a
                    placebo cannot validate a null, and a downstream claim cannot rescue one).
  (c) PRESENT    -- P1's interval lies entirely above zero. Provisional; the gates are then read, and
                    any failure downgrades this to NOT INTERPRETABLE, never to (a) or (b).
  (d) PRESENT BUT UNSELECTED -- P1 holds and P2's variables show no systematic difference (every
                    standardised difference below 0.10 and the model's out-of-fold AUC interval
                    including 0.5). Named in advance because it is a real possible outcome and a much
                    weaker paper: the monitor is absent, but the cases where it survives are ordinary,
                    so the selection warning is not earned. It must be reported as (d), not as (c).

FALSIFICATION. If the drop at the real landmark is matched by the drop at the placebo landmark, the
line ends. There is no successor design that rescues it, because the placebo is the same case, the same
track and the same code, and the only difference is where the landmark sits.

    python -m bsde.experiments.e247_monitor_availability
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")

LO, STEP, NBIN = -1800.0, 60.0, 60
REFERENCE = (-1800.0, -1200.0)
PRE = (-600.0, -300.0)
POST = (300.0, 600.0)
MIN_CASES = 1000
MIN_ARM = 200
COVARS = ("age", "bmi", "asa", "opdur_s")


def _f(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _bins(lo, hi):
    return [i for i in range(NBIN) if lo <= LO + i * STEP < hi]


def _any(row, arm, kind, idx):
    got = False
    for i in idx:
        v = row.get(f"{arm}_{kind}_{i}", "")
        if v == "":
            continue
        if int(v) == 1:
            return True
        got = True
    return False if got else None          # None = no information in this window at all


def load(paths):
    rows, seen = [], set()
    for p in sorted(paths):
        with open(p) as fh:
            for r in csv.DictReader(fh):
                cid = r.get("caseid")
                if not cid or cid in seen or (r.get("error") or ""):
                    continue
                seen.add(cid)
                rows.append(r)
    return rows


def silent_flags(rows, arm, kind, window):
    """Per case: 1 if EMITTING in the window with NO valid reading, 0 if emitting and valid, None else."""
    idx = _bins(*window)
    out = {}
    for r in rows:
        emit = _any(r, arm, "emit", idx)
        if not emit:                        # not recording -> the case says nothing about this question
            continue
        val = _any(r, arm, kind, idx)
        out[r["caseid"]] = 0 if val else 1
    return out


def cluster_boot(stat, subj_of, ids, rng, reps=4000):
    by = {}
    for cid in ids:
        by.setdefault(subj_of.get(cid, cid), []).append(cid)
    keys = sorted(by)
    if len(keys) < 3:
        return float("nan"), float("nan")
    draws = []
    for _ in range(reps):
        drawn = []
        for _ in keys:
            drawn.extend(by[keys[rng.randrange(len(keys))]])
        v = stat(drawn)
        if math.isfinite(v):
            draws.append(v)
    if len(draws) < reps // 2:
        return float("nan"), float("nan")
    draws.sort()
    return draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]


def frac(d, ids):
    v = [d[c] for c in ids if c in d]
    return (sum(v) / len(v)) if v else float("nan")


def smd(a, b):
    """Standardised mean difference with a pooled SD; NaN when either arm is degenerate."""
    a = [x for x in a if math.isfinite(x)]
    b = [x for x in b if math.isfinite(x)]
    if len(a) < 5 or len(b) < 5:
        return float("nan")
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    s = math.sqrt(0.5 * (va + vb))
    return (ma - mb) / s if s > 0 else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--glob", default=os.path.join(RESULTS, "vitaldb_bis_curve.s*.csv"))
    ap.add_argument("--seed", type=int, default=247)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e247_monitor_availability.json"))
    ap.add_argument("--smoke", action="store_true",
                    help="Rule 26: overwrite the REAL arm with a second read of the PLACEBO arm, so every "
                         "code path runs on real availability distributions while the real landmark is "
                         "never looked at. P1 must come out at ~0 by construction. Writes no report.")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = load(sorted(glob.glob(a.glob)))
    if not rows:
        print("no input; run bsde/scripts/vitaldb_monitor_availability_probe2.py first")
        return 2
    if a.smoke:
        for r in rows:
            for kind in ("emit", "t0", "t50", "t80"):
                for i in range(NBIN):
                    r[f"real_{kind}_{i}"] = r.get(f"plac_{kind}_{i}", "")
        print("[SMOKE] the real arm has been replaced by the placebo arm; P1 must be ~0 and no report "
              "will be written (rule 26)")
    subj = {r["caseid"]: (r.get("subjectid") or r["caseid"]) for r in rows}
    print(f"[cohort] {len(rows)} cases, {len(set(subj.values()))} patients")
    rep = {"n_cases": len(rows), "n_patients": len(set(subj.values()))}

    # ---- P1, computed before any gate -----------------------------------------------------------
    p1 = {}
    for kind in ("t0", "t50", "t80"):
        real = silent_flags(rows, "real", kind, POST)
        plac = silent_flags(rows, "plac", kind, POST)
        both = sorted(set(real) & set(plac))

        def stat(ids, real=real, plac=plac):
            return frac(real, ids) - frac(plac, ids)

        lo, hi = cluster_boot(stat, subj, both, rng)
        p1[kind] = {"n": len(both), "silent_real": frac(real, both), "silent_placebo": frac(plac, both),
                    "diff": stat(both), "ci": [lo, hi]}
        print(f"[P1 {kind}] n={len(both)}  silent real {p1[kind]['silent_real']:.4f}  "
              f"placebo {p1[kind]['silent_placebo']:.4f}  diff {p1[kind]['diff']:+.4f} "
              f"[{lo:+.4f}, {hi:+.4f}]")
    rep["P1"] = p1
    prim = p1["t0"]

    if not math.isfinite(prim["diff"]) or prim["n"] < MIN_CASES:
        verdict = f"NOT INTERPRETABLE (support {prim['n']} < {MIN_CASES})"
    elif prim["ci"][1] < 0:
        verdict = "REVERSED -- the index is MORE available after the transition; the claim is REFUTED"
    elif prim["ci"][0] > 0:
        verdict = "PRESENT (provisional, pending gates)"
    else:
        verdict = "ABSENT -- a landmark where nothing happens reproduces the drop"

    # ---- descriptive availability curve, both arms ------------------------------------------------
    curve = {}
    for arm in ("real", "plac"):
        for kind in ("emit", "t0"):
            v = []
            for i in range(NBIN):
                col = [r.get(f"{arm}_{kind}_{i}", "") for r in rows]
                col = [int(x) for x in col if x != ""]
                v.append(sum(col) / len(col) if col else float("nan"))
            curve[f"{arm}_{kind}"] = v
    rep["curve_60s_bins_from_-1800s"] = curve

    # ---- GATES -------------------------------------------------------------------------------------
    gates = {}
    ridx = _bins(*REFERENCE)
    ref_ok = [1.0 if _any(r, "real", "t0", ridx) else 0.0 for r in rows if _any(r, "real", "emit", ridx)]
    g1 = (sum(ref_ok) / len(ref_ok)) if ref_ok else float("nan")
    gates["G1_instrument_can_see_availability"] = {"reference_availability": g1, "n": len(ref_ok),
                                                   "pass": bool(math.isfinite(g1) and g1 > 0.80)}

    signs = [1 if p1[k]["ci"][0] > 0 else (-1 if p1[k]["ci"][1] < 0 else 0) for k in ("t0", "t50", "t80")]
    gates["G2_threshold_not_doing_the_work"] = {
        "diffs": {k: p1[k]["diff"] for k in ("t0", "t50", "t80")},
        "signs": signs,
        "prediction_registered": "stricter thresholds make the drop LARGER, never smaller",
        "pass": bool(len(set(signs)) == 1 and signs[0] != 0)}

    n_pl = sum(1 for r in rows if (r.get("placebo_ok") or "0") == "1")
    gates["G3_placebo_support"] = {"frac_with_placebo": n_pl / len(rows),
                                  "pass": bool(n_pl / len(rows) >= 0.80)}
    gates["G4_support"] = {"n_P1": prim["n"], "pass": bool(prim["n"] >= MIN_CASES)}

    # ---- P2, the selection claim. NOT evaluated unless P1 is present (verdict rule (b)) -------------
    p2 = {"evaluated": False, "reason": "P1 did not establish a transition-specific drop"}
    if verdict.startswith("PRESENT"):
        idx = _bins(*POST)
        emit = [r for r in rows if _any(r, "real", "emit", idx)]
        valid = [r for r in emit if _any(r, "real", "t0", idx)]
        gone = [r for r in emit if not _any(r, "real", "t0", idx)]
        p2 = {"evaluated": True, "n_emitting": len(emit), "n_valid": len(valid), "n_silent": len(gone),
              "smd": {}, "categorical": {}}
        for c in COVARS:
            s = smd([_f(r.get(c)) for r in valid], [_f(r.get(c)) for r in gone])
            ids = [r["caseid"] for r in emit]
            vmap = {r["caseid"]: r for r in emit}
            vset = {r["caseid"] for r in valid}

            def st(sub, c=c, vmap=vmap, vset=vset):
                return smd([_f(vmap[i].get(c)) for i in sub if i in vset],
                           [_f(vmap[i].get(c)) for i in sub if i not in vset])

            lo, hi = cluster_boot(st, subj, ids, rng, reps=1500)
            p2["smd"][c] = {"smd": s, "ci": [lo, hi]}
        for c in ("sex", "ane_type", "emop"):
            tot = {}
            for r in emit:
                k = (r.get(c) or "?")
                tot.setdefault(k, [0, 0])
                tot[k][0] += 1
                tot[k][1] += 1 if _any(r, "real", "t0", idx) else 0
            p2["categorical"][c] = {k: {"n": v[0], "frac_valid": (v[1] / v[0]) if v[0] else None}
                                    for k, v in sorted(tot.items())}
        big = [c for c, d in p2["smd"].items()
               if math.isfinite(d["smd"]) and abs(d["smd"]) >= 0.10 and (d["ci"][0] > 0 or d["ci"][1] < 0)]
        p2["variables_with_smd_ge_0.10_excluding_zero"] = big
        if gates["G4_support"]["pass"] and min(len(valid), len(gone)) < MIN_ARM:
            gates["G4_support"]["pass"] = False
            gates["G4_support"]["note"] = f"P2 arms {len(valid)}/{len(gone)} < {MIN_ARM}"
    rep["P2"] = p2

    failed = [k for k, v in gates.items() if v.get("pass") is False]
    if verdict.startswith("PRESENT"):
        if failed:
            verdict = f"NOT INTERPRETABLE -- P1 present but gates failed: {failed}"
        elif p2.get("evaluated") and not p2.get("variables_with_smd_ge_0.10_excluding_zero"):
            verdict = ("PRESENT BUT UNSELECTED -- the monitor goes silent, but the surviving cases are "
                       "ordinary; the selection warning is NOT earned")
        else:
            verdict = "PRESENT AND SELECTED"
    rep["gates"] = gates
    rep["verdict"] = verdict

    print("\n[gates]", json.dumps(gates, indent=1, default=float))
    print("[P2]", json.dumps(p2, indent=1, default=float)[:2500])
    print("\nVERDICT:", verdict)
    if a.smoke:
        print("\n[SMOKE] complete; report NOT written and nothing above is a result.")
        return 0
    json.dump(rep, open(a.out, "w"), indent=1, default=float)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
