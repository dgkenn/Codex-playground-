"""E184 — gating on pre-cue alpha for SPEED, which is the one thing it could actually buy.

REGISTERED BEFORE ANY GATED SIMULATION ON THE SPEED OUTCOME HAS BEEN RUN.

=========================================================================================================
WHY THIS IS A DIFFERENT QUESTION FROM E179, AND WHY E179's ANSWER IS NOW UNUSABLE
=========================================================================================================
**E179 gated on `mu_mean` to raise the HIT RATE and returned USABLE** (+0.0347 [+0.0048, +0.0645] at a
20-attempt budget). **E174 then killed the effect it was built on**: `mu_mean` does not predict hit/miss on
held-out sessions (0.4991, one-sided p = 0.5700, BH keeps nothing). E179's verdict is recorded as
inheriting that and is not claimed.

**E181 found what does replicate.** On the same held-out sessions, and confirmed on session 1 one-sided,
pre-cue alpha predicts **how fast** a followed command is executed: `mu_mean` 0.4803 (p = 0.0000) in
discovery and 0.4799 (one-sided p = 0.0255) in confirmation, with `relative_alpha_power` at 0.4841 and
0.4739. **More pre-cue alpha, slower trial.** The collider gate passed (`mu_mean` against hit/miss in the
same cohort: 0.4993, p = 0.8890), so this is not the binary effect in disguise.

So the decision rule that follows from the surviving finding is not "wait for a good moment to be
CORRECT" — it is "wait for a good moment to be FAST", and the gate must select LOW alpha, not high.

=========================================================================================================
AND SPEED IS THE ONE OUTCOME WHERE THE PUBLISHED INCUMBENT COULD BE BEATEN
=========================================================================================================
Geronimo, Kamrunnahar & Schiff 2016, PMID 27199630, verbatim: *"an offline gating simulation was limited
in its ability to produce an increase in device throughput."* E179 reproduced that cleanly — **throughput
fell at every one of its six cells**, by 0.014 to 0.078 — because gating for accuracy discards trials and
discarded trials cost time.

**Gating for SPEED does not have that problem in the same way.** If skipping a bad moment shortens the
trials you do run by more than the skipped ones cost, throughput goes UP. That is the only mechanism by
which any of this could beat the published negative in the published unit, and it is what this file tests.

    PRIMARY     seconds of elapsed recording per DELIVERED trial, gated minus ungated, at a fixed budget
                of `N` delivered trials. Skipped trials are charged at their own duration, because the
                subject performs them regardless — this is Geronimo's throughput, computed his way.
    SECONDARY   mean trial length among delivered trials (the direct translation of E181's effect).

=========================================================================================================
DISCOVERY AND CONFIRMATION, DECLARED BEFORE EITHER RUNS
=========================================================================================================
    DISCOVERY     sessions 2 and 3 — the cohort E181 discovered on.
    CONFIRMATION  session 1 — run ONLY if discovery is positive, one-sided in the discovered direction.

**The gate selects LOW alpha**, declared here from E181's direction and not chosen afterwards. Its rule is
causally implementable: a running quantile over trials already seen, never the whole session, with
`WARMUP` trials observed before any delivery.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 60 discovery sessions reaching the budget.
G2  LOOK-AHEAD: the causal running-quantile gate must differ from a whole-session oracle, or the quantile
    is not running (E179's gate, unchanged, and it can fail).
G3  THE COHORT IS E181's: `mu_mean`'s fast/slow matched-pair statistic recomputed here must reproduce
    E181's discovery value to within 0.01, or nothing here is about E181 (rule 59).
G4  THE PLACEBO: the identical gate driven by a RANDOM score at matched selection rate, 300 draws, giving
    the null distribution of the gain from selecting fewer trials at all. It GATES the verdict (rule 34)
    and the comparison is against its DISTRIBUTION, never a threshold.

=========================================================================================================
VERDICT — THE FAILING AND WRONG-DIRECTION CASES FIRST (rules 31, 34, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails.
  (2) SLOWER             the gated arm's seconds-per-delivered-trial is HIGHER and the interval excludes
                         zero — gating on low alpha makes throughput WORSE. Enumerated because a rule that
                         discards trials can do exactly that, and "excludes zero" is not "supports the
                         hypothesis" (rule 37).
  (3) NO GAIN            the interval includes zero at every budget, or the gain does not beat the
                         random-score placebo. **Geronimo's negative then stands in his own unit even for
                         the outcome most likely to beat it**, and E181's effect is real and inert.
  (4) FASTER-NOT-THROUGHPUT  the SECONDARY improves (delivered trials are shorter) while the PRIMARY does
                         not. Then the effect is real and the waiting eats it, which is precisely
                         Geronimo's finding arrived at from the other direction.
  (5) THROUGHPUT GAIN    the primary improves, beats the placebo, and the confirmation arm agrees. Stated
                         in **seconds saved per ten delivered trials**, because that is the unit the claim
                         would have to be made in.

**REGISTERED PREDICTION: (4) FASTER-NOT-THROUGHPUT.** E181's effect is about two percentage points on a
pairwise statistic; a gate that skips a third of trials must recover that cost in shortened trials, and a
2 % shift is very unlikely to pay for a 50 % increase in elapsed trials. **The prediction is against this
file's own hypothesis**, and (4) would still be a real result: it would show the effect is genuine and
quantify exactly how far short of usable it falls.

    python bsde/src/bsde/experiments/e184_gating_for_speed.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e172_matched_pair_trial_responsiveness as E172                          # noqa: E402
import e181_trial_length_graded_outcome as E181                                # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e184_gating_for_speed.json")
SEED = 20260801

PREDICTOR = "mu_mean"
BUDGETS = (10, 20, 40)
QUANTILES = (0.33, 0.50)        # deliver when the predictor is BELOW this running quantile
WARMUP = 20
PLACEBO_DRAWS = 300
E181_DISCOVERY = 0.4803
E181_TOL = 0.01
MIN_SESSIONS = 60
ALPHA = 0.05


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load_sessions(pattern):
    by, _ = E181.load(pattern)
    out = []
    for (subj, s), rr in sorted(by.items()):
        x = np.array([_f(r[PREDICTOR]) for r in rr])
        tl = np.array([_f(r["triallength"]) for r in rr])
        res = np.array([_f(r["result"]) for r in rr])
        ok = np.isfinite(x) & np.isfinite(tl) & (tl > 0) & np.isfinite(res)
        if ok.sum() < 120:
            continue
        out.append({"subject": subj, "session": s, "x": x[ok], "tl": tl[ok], "res": res[ok]})
    return out


def simulate(x, tl, n_budget, q, causal=True, warmup=WARMUP):
    """Deliver when the predictor is BELOW the running quantile. Skipped trials still cost their duration.

    Returns (seconds elapsed, delivered count, summed delivered trial length).
    """
    thr_all = float(np.quantile(x, q)) if x.size else np.nan
    seen, delivered, elapsed, dur = [], 0, 0.0, 0.0
    for i in range(x.size):
        seen.append(x[i])
        elapsed += tl[i]                       # the subject performs the trial whether or not it counts
        if len(seen) <= warmup:
            continue
        thr = thr_all if not causal else float(np.quantile(seen[:-1], q))
        if not np.isfinite(thr) or x[i] > thr:
            continue
        delivered += 1
        dur += tl[i]
        if delivered >= n_budget:
            return elapsed, delivered, dur
    return elapsed, delivered, dur


def control(tl, n_budget, warmup=WARMUP):
    seen, delivered, elapsed, dur = 0, 0, 0.0, 0.0
    for i in range(tl.size):
        seen += 1
        elapsed += tl[i]
        if seen <= warmup:
            continue
        delivered += 1
        dur += tl[i]
        if delivered >= n_budget:
            return elapsed, delivered, dur
    return elapsed, delivered, dur


def arm(sess, n_budget, q, causal=True, override=None):
    rows = []
    for s in sess:
        x = s["x"] if override is None else override[(s["subject"], s["session"])]
        ge, gd, gdur = simulate(x, s["tl"], n_budget, q, causal=causal)
        ce, cd, cdur = control(s["tl"], n_budget)
        if gd < n_budget or cd < n_budget:
            continue
        rows.append({"subject": s["subject"],
                     "gated_spt": ge / gd, "control_spt": ce / cd,
                     "gated_len": gdur / gd, "control_len": cdur / cd})
    return rows


def ci(vals, subs, rng, reps=2000):
    v, sarr = np.asarray(vals, float), np.asarray(subs)
    if v.size == 0:
        return float("nan"), float("nan")
    uniq = np.unique(sarr)
    draws = []
    for _ in range(reps):
        pick = rng.choice(uniq, size=uniq.size, replace=True)
        d = np.concatenate([v[sarr == u] for u in pick])
        if d.size:
            draws.append(d.mean())
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def run(sess, tag):
    print(f"\n=== {tag}: {len(sess)} sessions")
    out = {"tag": tag, "n_sessions": len(sess), "cells": {}}
    print(f"   {'N':>3s} {'q':>5s} {'sec/trial gated':>16s} {'ctrl':>8s} {'gain(-=better)':>15s} "
          f"{'[95% CI]':>22s} {'len gain':>9s} {'placebo p':>10s}")
    for n_budget in BUDGETS:
        for q in QUANTILES:
            rows = arm(sess, n_budget, q)
            if len(rows) < MIN_SESSIONS // 2:
                print(f"   {n_budget:>3d} {q:>5.2f}   only {len(rows)} sessions reach the budget — skipped")
                continue
            spt = np.asarray([r["gated_spt"] - r["control_spt"] for r in rows])
            lng = np.asarray([r["gated_len"] - r["control_len"] for r in rows])
            subs = [r["subject"] for r in rows]
            lo, hi = ci(spt, subs, np.random.default_rng(SEED + 1))
            prng = np.random.default_rng(SEED + 2)
            pg = []
            for _ in range(PLACEBO_DRAWS):
                ov = {(s["subject"], s["session"]): prng.normal(size=s["x"].size) for s in sess}
                pr = arm(sess, n_budget, q, override=ov)
                if len(pr) >= MIN_SESSIONS // 2:
                    pg.append(float(np.mean([r["gated_spt"] - r["control_spt"] for r in pr])))
            pv = np.asarray(pg)
            p_pl = float((pv <= spt.mean()).mean()) if pv.size >= 30 else float("nan")
            cell = {"n": n_budget, "q": q, "n_sessions": len(rows),
                    "gated_spt": float(np.mean([r["gated_spt"] for r in rows])),
                    "control_spt": float(np.mean([r["control_spt"] for r in rows])),
                    "spt_gain": float(spt.mean()), "ci": [lo, hi],
                    "len_gain": float(lng.mean()),
                    "placebo_mean": float(pv.mean()) if pv.size else float("nan"),
                    "placebo_p": p_pl,
                    "seconds_saved_per_10": float(-10 * spt.mean())}
            out["cells"][f"N{n_budget}_q{q}"] = cell
            print(f"   {n_budget:>3d} {q:>5.2f} {cell['gated_spt']:>16.3f} {cell['control_spt']:>8.3f} "
                  f"{cell['spt_gain']:>+15.4f} [{lo:>+9.4f},{hi:>+9.4f}] {cell['len_gain']:>+9.4f} "
                  f"{p_pl:>10.4f}")
    return out


def main() -> int:
    print("E184 — gating on LOW pre-cue alpha for SPEED; primary is Geronimo's own throughput unit")
    sess = load_sessions(E181.DISCOVERY_GLOB)
    res = {"experiment": "E184", "predictor": PREDICTOR, "budgets": list(BUDGETS),
           "quantiles": list(QUANTILES), "incumbent": "Geronimo 2016, PMID 27199630"}
    if not sess:
        print("   ABSENT: no discovery sessions.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2
    res["G1_pass"] = bool(len(sess) >= MIN_SESSIONS)
    print(f"   {len(sess)} discovery sessions   {'G1 PASS' if res['G1_pass'] else '*** G1 FAIL'}")

    gs, _, _ = E181.build_graded(E181.DISCOVERY_GLOB)
    st = E172.frac_stat(gs, PREDICTOR)
    ok3 = abs(st["mean"] - E181_DISCOVERY) <= E181_TOL
    res["G3"] = {"recomputed": st["mean"], "e181": E181_DISCOVERY, "pass": bool(ok3)}
    print(f"   G3 E181's discovery statistic recomputed: {st['mean']:.4f} vs {E181_DISCOVERY:.4f}   "
          f"{'PASS' if ok3 else '*** FAIL'}")
    if not (res["G1_pass"] and ok3):
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    res["discovery"] = run(sess, "discovery (sessions 2-3)")
    c_rows = arm(sess, 20, 0.33, causal=True)
    o_rows = arm(sess, 20, 0.33, causal=False)
    cg = float(np.mean([r["gated_spt"] - r["control_spt"] for r in c_rows])) if c_rows else float("nan")
    og = float(np.mean([r["gated_spt"] - r["control_spt"] for r in o_rows])) if o_rows else float("nan")
    g2 = np.isfinite(cg) and np.isfinite(og) and abs(cg - og) > 1e-4
    res["G2"] = {"causal": cg, "oracle": og, "pass": bool(g2)}
    print(f"\n   G2 look-ahead: causal {cg:+.4f} vs whole-session oracle {og:+.4f}   "
          f"{'PASS' if g2 else '*** FAIL -- identical, the quantile is not running'}")

    cells = res["discovery"]["cells"]
    best = min(cells.values(), key=lambda c: c["spt_gain"]) if cells else None
    worse = [c for c in cells.values() if c["ci"][0] > 0]
    good = [c for c in cells.values()
            if c["ci"][1] < 0 and np.isfinite(c["placebo_p"]) and c["placebo_p"] <= ALPHA]
    len_better = [c for c in cells.values() if c["len_gain"] < 0]

    if not g2:
        res["verdict"], res["why"] = "NOT-INTERPRETABLE", "the causal and oracle gates are identical"
    elif worse and not good:
        res["verdict"] = "SLOWER"
        res["why"] = (f"gating on low alpha makes throughput WORSE at "
                      f"{[(c['n'], c['q']) for c in worse]} — the registered wrong-direction branch")
    elif not good:
        res["verdict"] = "FASTER-NOT-THROUGHPUT" if len(len_better) >= len(cells) / 2 else "NO-GAIN"
        res["why"] = (("delivered trials are shorter under the gate in "
                       f"{len(len_better)} of {len(cells)} cells (best {best['len_gain']:+.4f} s) but no "
                       "cell improves seconds-per-delivered-trial against the random-score placebo: the "
                       "effect is real and the waiting eats it, which is Geronimo's finding reached from "
                       "the other side")
                      if len(len_better) >= len(cells) / 2 else
                      ("no cell improves throughput or trial length beyond the placebo; Geronimo's "
                       "negative stands in his own unit even for the outcome most likely to beat it"))
    else:
        b = min(good, key=lambda c: c["spt_gain"])
        print(f"\n   DISCOVERY POSITIVE at N = {b['n']}, q = {b['q']:.2f} "
              f"({b['seconds_saved_per_10']:+.2f} s saved per ten delivered trials) — "
              "running CONFIRMATION on session 1")
        csess = load_sessions(E181.CONFIRM_GLOB)
        if len(csess) < 40:
            res["verdict"] = "DISCOVERED-UNCONFIRMED"
            res["why"] = f"only {len(csess)} confirmation sessions; the confirmation arm is ABSENT"
        else:
            res["confirmation"] = run(csess, "confirmation (session 1)")
            key = f"N{b['n']}_q{b['q']}"
            cc = res["confirmation"]["cells"].get(key)
            if cc and cc["ci"][1] < 0:
                res["verdict"] = "THROUGHPUT-GAIN"
                res["why"] = (f"discovery saves {b['seconds_saved_per_10']:+.2f} s per ten delivered "
                              f"trials at N = {b['n']}, q = {b['q']:.2f} and confirmation saves "
                              f"{cc['seconds_saved_per_10']:+.2f} s -- beating a published negative in "
                              "its own unit")
            else:
                res["verdict"] = "DISCOVERED-NOT-CONFIRMED"
                res["why"] = (f"the discovery cell {key} does not confirm on session 1 "
                              f"({cc['spt_gain']:+.4f} [{cc['ci'][0]:+.4f}, {cc['ci'][1]:+.4f}])"
                              if cc else "the discovery cell is not estimable on session 1")
    print(f"\nVERDICT {res['verdict']} — {res['why']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
