"""E119 -- Is E116's second axis just ALPHA POWER? An audit of this project's own positive.

REGISTERED BEFORE ANY DECOMPOSITION IS COMPUTED. Existing tables only. Machinery imported from E118 rather
than reimplemented (rule 20).

=========================================================================================================
THE ALTERNATIVE EXPLANATION I OWE THIS RESULT
=========================================================================================================
E116 found a second state-carrying axis and E118 showed its predicted inverted U transfers to anaesthetic
depth in VitalDB (TIVA c(comp2) -3.1437 [-3.7112, -2.5893]; contrast against comp1 -5.0472 [-6.0561,
-4.0270]; comp1 curving the OPPOSITE way at +1.9035). Two deposits, two state variables, a shape fixed in
advance.

**And there is a boring explanation that has not been tested.** comp2 is

    +exponent_high  +relative_alpha_power  -pac_slow_alpha  -relative_delta_power

and its behaviour -- absent when awake, present at intermediate depth, gone again when deep -- is the
**textbook description of anaesthetic and sleep spindle-alpha oscillations**. Frontal alpha appears at
moderate propofol and disappears into burst suppression; sleep spindles appear in N2 and vanish in deep
N3. An inverted U in depth that loads on alpha is exactly what that produces.

If comp2 is alpha power wearing a four-measure name, then E116 and E118 are a careful re-derivation of a
phenomenon known since the 1930s, and must be described as one. **This is rule 60 applied to my own
result, and it is the check E116's G1 did not make**: E116 validated that the COUNTER could count, not
that the axis it counted was new.

=========================================================================================================
PRIMARY
=========================================================================================================
Two deposits, because a redundancy that appears in only one is a fact about that deposit.

VITALDB, per case, same construction and same quadratic fit as E118:

    P1  c(comp2 residualised on relative_alpha_power within case), mean over cases, case bootstrap.
        **If the inverted U survives removing alpha, comp2 is not alpha.**
    P2  c(relative_alpha_power alone). Does alpha by itself reproduce the U?
    P3  c(exponent_high alone) -- the other strong loader, reported so the decomposition is not selective
        (rule 59).

SLEEP-EDFx, on E116's own data:

    P4  spearman between comp2's per-feature rank profile and `relative_alpha_power`'s rank profile
        across the five stages. A value near +-1 means the axis and the single measure order the stages
        identically and the axis is that measure.

VERDICT, wrong direction FIRST (rule 37) -- and the wrong direction here costs this project its only
Challenge A positive, which is why it is named first:

    (a) P1's interval INCLUDES 0 while P2's excludes it -> **comp2 IS ALPHA POWER.** E116 and E118 are a
        re-derivation of anaesthetic/spindle alpha. The finding is not withdrawn -- the shape is real --
        but "second axis" becomes "the alpha oscillation", and every claim of novelty goes.
    (b) BOTH include 0 -> ABSENT. The decomposition removed the effect from both parts, which means the
        residualisation destroyed the signal rather than partitioning it; nothing is learned.
    (c) BOTH exclude 0 -> comp2 carries an inverted U beyond alpha, AND alpha carries one of its own.
        The axis is not reducible to alpha but alpha is part of it.
    (d) P1 excludes 0 and P2 does not -> comp2's U is NOT alpha at all, and the alternative explanation
        is refuted outright.

PREDICTED: (a) at ~45 %, (c) at ~35 %, (d) at ~15 %, (b) at ~5 %. **(a) leads because it is the
parsimonious reading and because I want it not to be true**, which is the condition under which a
pre-registered prediction is worth writing down.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE, inherited from E118: >= 60 cases with >= 15 windows and within-case BIS range >= 30.
    G2  THE RESIDUAL MUST EXIST. After removing alpha within case, comp2's residual must retain
        non-trivial variance -- if alpha explains essentially all of comp2 the residual is noise and P1
        cannot be interpreted either way. Reported as the median within-case R^2 of alpha on comp2.
    G3  TRANSFER, inherited from E118: comp1 must rise with BIS in an arm for that arm to be
        interpretable (E117 found this construction inverts against propofol concentration).

PLACEBO: BIS permuted across windows within case, 500 draws, applied to P1. Primary read FIRST (rule 48).

SCOPE. Unchanged from E118. A negative here does not withdraw the measured shape; it renames what carries
it. Nothing in either outcome concerns consciousness.
"""
from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict

import numpy as np

from bsde.experiments import e118_second_axis_inverted_u as e118

RESULTS = e118.RESULTS
OUT = os.path.join(RESULTS, "e119_is_comp2_just_alpha.json")
ALPHA = "relative_alpha_power"
OTHER = "exponent_high"
SLEEP = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")
STAGES = ("W", "N1", "N2", "N3", "REM")
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def residualise(y, x):
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < 8 or np.ptp(x[ok]) <= 0:
        return None, float("nan")
    b, a = np.polyfit(x[ok], y[ok], 1)
    r = np.full_like(y, np.nan)
    r[ok] = y[ok] - (a + b * x[ok])
    ss = float(np.var(y[ok]))
    r2 = float(1.0 - np.var(r[ok]) / ss) if ss > 0 else float("nan")
    return r, r2


def main() -> int:
    per, expo = e118.build()
    rng = np.random.default_rng(SEED)
    ia = e118.FEATS.index(ALPHA)
    io = e118.FEATS.index(OTHER)

    arms = defaultdict(list)
    for c, rows in per.items():
        if len(rows) < e118.MIN_WINDOWS:
            continue
        bis, s1, s2 = e118.scores_for(rows)
        if bis is None or np.ptp(bis) < e118.MIN_BIS_RANGE:
            continue
        ex = expo.get(c)
        if not ex or ex["n"] == 0:
            continue
        fp, fv = ex["ppf"] / ex["n"], ex["vol"] / ex["n"]
        arm = "tiva" if (fp >= 0.5 and fv < 0.1) else ("volatile" if (fv >= 0.5 and fp < 0.1) else None)
        if arm is None:
            continue
        M = np.array(rows, float)[:, 1:]
        sd = M.std(axis=0)
        if np.any(sd <= 0):
            continue
        Z = (M - M.mean(axis=0)) / sd
        alpha, other = Z[:, ia], Z[:, io]
        resid, r2 = residualise(s2, alpha)
        if resid is None:
            continue
        c_res, _ = e118.quad(bis, resid)
        c_alpha, _ = e118.quad(bis, alpha)
        c_other, _ = e118.quad(bis, other)
        c_raw, b1 = e118.quad(bis, s2)
        _, b_c1 = e118.quad(bis, s1)
        if not all(np.isfinite(v) for v in (c_res, c_alpha, c_other, c_raw, b_c1)):
            continue
        arms[arm].append({"c_res": c_res, "c_alpha": c_alpha, "c_other": c_other, "c_raw": c_raw,
                          "r2": r2, "b_c1": b_c1, "bis": bis, "resid": resid})

    res = {"arms": {}, "gates": {}}
    total = sum(len(v) for v in arms.values())
    print(f"{total} cases contribute ({len(arms.get('volatile', []))} volatile, "
          f"{len(arms.get('tiva', []))} TIVA)")
    res["gates"]["G1_pass"] = bool(total >= e118.MIN_CASES)
    print(f"G1 coverage   {total} >= {e118.MIN_CASES}  "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    outcome = {}
    for arm in ("volatile", "tiva"):
        rows = arms.get(arm, [])
        if len(rows) < 15:
            continue
        n = len(rows)
        cr = np.array([r["c_res"] for r in rows])
        ca = np.array([r["c_alpha"] for r in rows])
        co = np.array([r["c_other"] for r in rows])
        craw = np.array([r["c_raw"] for r in rows])
        r2 = np.array([r["r2"] for r in rows])
        b1 = np.array([r["b_c1"] for r in rows])
        print(f"\n=== ARM {arm} ({n} cases) ===")
        g3 = bool(np.mean(b1) > 0)
        print(f"G3 transfer   comp1 slope on BIS {np.mean(b1):+.4f}  {'PASS' if g3 else 'FAIL'}")
        g2 = bool(np.nanmedian(r2) < 0.90)
        print(f"G2 residual   median within-case R^2 of alpha on comp2 = {np.nanmedian(r2):.4f}  "
              f"{'PASS -- a residual exists' if g2 else 'FAIL -- alpha explains comp2 outright'}")

        def boot(v):
            return e118.ci([float(np.mean(v[i]))
                            for i in (rng.integers(0, n, n) for _ in range(REPS))])

        lo_r, hi_r = boot(cr)
        lo_a, hi_a = boot(ca)
        lo_o, hi_o = boot(co)
        print(f"P1 comp2 | alpha removed   c = {np.mean(cr):+.4f} [{lo_r:+.4f}, {hi_r:+.4f}]   "
              f"(raw comp2 was {np.mean(craw):+.4f})")
        print(f"P2 {ALPHA:<24s} c = {np.mean(ca):+.4f} [{lo_a:+.4f}, {hi_a:+.4f}]")
        print(f"P3 {OTHER:<24s} c = {np.mean(co):+.4f} [{lo_o:+.4f}, {hi_o:+.4f}]")

        pl = []
        for _ in range(PLACEBO_DRAWS):
            vals = []
            for r in rows:
                bp = r["bis"][rng.permutation(r["bis"].size)]
                v, _ = e118.quad(bp, r["resid"])
                if np.isfinite(v):
                    vals.append(v)
            if len(vals) >= 15:
                pl.append(float(np.mean(vals)))
        q_lo, q_hi = e118.ci(pl)
        inside = bool(np.isfinite(q_lo) and q_lo <= np.mean(cr) <= q_hi)
        print(f"PLACEBO on P1: [{q_lo:+.4f}, {q_hi:+.4f}]  real {'INSIDE' if inside else 'outside'}")

        res["arms"][arm] = {"n": n, "P1": [float(np.mean(cr)), lo_r, hi_r],
                            "P2_alpha": [float(np.mean(ca)), lo_a, hi_a],
                            "P3_other": [float(np.mean(co)), lo_o, hi_o],
                            "raw_comp2": float(np.mean(craw)), "median_r2": float(np.nanmedian(r2)),
                            "G2_pass": g2, "G3_pass": g3, "placebo_inside": inside}
        outcome[arm] = {"p1": bool(np.isfinite(hi_r) and hi_r < 0 and not inside),
                        "p2": bool(np.isfinite(hi_a) and hi_a < 0),
                        "g2": g2, "g3": g3}

    # ---- P4: the sleep-side check on E116's own data ----------------------------------------------
    p4 = float("nan")
    if os.path.exists(SLEEP):
        pers = defaultdict(dict)
        for r in csv.DictReader(open(SLEEP, newline="")):
            rid, sb = r.get("recording_id", ""), r.get("subject", "")
            if "@" not in rid or "SC4001E0" in sb:
                continue
            st = rid.rsplit("@", 1)[1]
            if st in STAGES:
                pers[sb][st] = r
        prof_c2, prof_a = [], []
        for sb, d in pers.items():
            if not all(k in d for k in STAGES):
                continue
            vals = {}
            ok = True
            for f in e118.FEATS:
                v = np.array([e118._f(d[k].get(f, "")) for k in STAGES], float)
                if not np.isfinite(v).all() or np.ptp(v) <= 0:
                    ok = False
                    break
                vals[f] = np.argsort(np.argsort(v)).astype(float)
            if not ok:
                continue
            w2 = np.array([e118.COMP2.get(f, 0.0) for f in e118.FEATS])
            prof_c2.append(np.sum([w2[i] * vals[f] for i, f in enumerate(e118.FEATS)], axis=0))
            prof_a.append(vals[ALPHA])
        if prof_c2:
            m2 = np.mean(prof_c2, axis=0)
            ma = np.mean(prof_a, axis=0)
            p4 = e118.spearman(m2 - m2.mean(), ma - ma.mean())
    res["P4_sleep_profile_rho"] = p4
    print(f"\nP4 SLEEP: spearman(comp2 stage profile, {ALPHA} stage profile) over 5 stages = {p4:+.4f}")

    interp = [a for a, v in outcome.items() if v["g3"] and v["g2"]]
    if not interp:
        v = ("ABSENT -- no arm is interpretable: either comp1 does not transfer or alpha explains comp2 "
             "outright, leaving no residual to test (rule 31).")
    else:
        p1s = [a for a in interp if outcome[a]["p1"]]
        p2s = [a for a in interp if outcome[a]["p2"]]
        if not p1s and p2s:
            v = (f"**comp2 IS ALPHA POWER.** The inverted U does NOT survive removing "
                 f"`{ALPHA}` within case, while alpha alone reproduces it. E116 and E118 measured a real "
                 f"shape and it is the anaesthetic/sleep alpha oscillation -- known since the 1930s. The "
                 f"shape stands; the claim of a NEW second axis does not, and every description of it "
                 f"must be rewritten as 'the alpha oscillation'.")
        elif not p1s and not p2s:
            v = ("ABSENT -- neither the residual nor alpha alone shows the U, so the decomposition "
                 "destroyed the signal rather than partitioning it and nothing is learned (rule 31).")
        elif p1s and p2s:
            v = (f"**NOT REDUCIBLE TO ALPHA, BUT ALPHA IS PART OF IT.** comp2's inverted U survives "
                 f"removing `{ALPHA}` in {p1s}, and alpha alone also carries one. The second axis is not "
                 f"a rename of the alpha oscillation, but alpha is one of its constituents and any "
                 f"description must say so.")
        else:
            v = (f"**THE ALTERNATIVE IS REFUTED.** comp2's inverted U survives removing `{ALPHA}` in "
                 f"{p1s}, and alpha ALONE does not produce one. Whatever the second axis is, it is not "
                 f"the alpha oscillation.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
