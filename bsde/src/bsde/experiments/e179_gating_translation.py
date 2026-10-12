"""E179 — is E172's effect USABLE? Gating trials on the pre-cue state, at a fixed attempt budget.

REGISTERED BEFORE ANY GATED SELECTION HAS BEEN SIMULATED.

=========================================================================================================
THE OBLIGATION THIS FILE DISCHARGES
=========================================================================================================
E172 found that pre-cue alpha amplitude is higher on the successful member of a matched adjacent hit/miss
pair — 0.5176 [0.5054, 0.5303], p = 0.0060, placebo clean, above a measured floor. **51.8 % against
50 %.** A finding that small has an obligation attached: say whether it can do anything.

**And there is a published answer to exactly this question, which must be the incumbent (rule 45).**
Geronimo, Kamrunnahar & Schiff, *Front Neurosci* 2016, PMID 27199630 — the same paper whose single-trial
association E172 replicates — went on to test gating and reported, verbatim:

> "Despite the potential for gating trials using these features, **an offline gating simulation was
>  limited in its ability to produce an increase in device throughput.** This discrepancy highlights a
>  distinction between the identification of predictive features, and the use of this knowledge in an
>  online BCI. Using such a system, we cannot assume that the user will respond similarly when faced with
>  a scenario where feedback is altered by trials that are gated on a regular basis."

So the registered incumbent claim is a **published negative**, and the first thing this file does is try to
reproduce it on roughly ten times the trials.

=========================================================================================================
THE ONE THING THEIR CAVEAT DOES NOT COVER, AND IT IS THE APPLICATION THAT MATTERS HERE
=========================================================================================================
Their objection is about an online BCI: gating alters the feedback the user receives, so an offline
simulation may not transfer. **That objection does not apply to a bedside assessment of an unresponsive
patient.** There is no device, no throughput to maximise and no feedback loop to perturb — there is a
clinician with a limited number of usable attempts, asking when to make them. Throughput is the wrong
figure of merit for that use; **hits per attempt DELIVERED at a fixed attempt budget** is the right one.

Both are therefore computed and reported side by side:
    THROUGHPUT      hits per trial ELAPSED, counting skipped trials against you — Geronimo's figure
    ASSESSMENT      hits per trial DELIVERED at a fixed budget of N delivered trials — the DoC figure

=========================================================================================================
THE GATING RULE, AND WHY IT IS CAUSALLY IMPLEMENTABLE
=========================================================================================================
The predictor is the 2 s BEFORE the cue, so a real system can compute it and then decide whether to
deliver the cue. The simulation must respect that and is written to:

    walk the session in order; maintain a running quantile of `mu_mean` over trials ALREADY SEEN;
    deliver the cue when the current trial's value is above that running quantile; stop at N delivered.

**No statistic is ever computed from a trial that has not happened yet.** `WARMUP` trials are observed
without delivering, to have a quantile at all.

G2 — LOOK-AHEAD CHECK, AND IT CAN FAIL. The same simulation is run with an ORACLE gate that uses the
whole session's quantile. If the causal and oracle gates give the same answer to four decimal places, the
running quantile is not actually running and the implementation is broken; if the oracle is enormously
better, the causal rule is the one that gets reported and the gap is stated.

=========================================================================================================
ARMS AND STATISTIC
=========================================================================================================
    budgets      N in {5, 10, 20} delivered trials — a bedside assessment's realistic range
    gated        the causal rule above, at selection quantiles q in {0.50, 0.67}
    control      N trials taken in order from the same starting point, no gating
    placebo      the identical gate driven by a RANDOM score, matched selection rate, 500 draws — this
                 gives the null distribution of "gain from selecting fewer trials at all" and it GATES
                 the verdict (rule 34)
    statistic    mean over sessions of (hit rate under gating − hit rate under the control) at each N,
                 with a cluster bootstrap over SUBJECTS

=========================================================================================================
GATES
=========================================================================================================
G1  >= 40 sessions with >= 100 scored trials and a hit rate inside [0.15, 0.85] — E172's cohort rule.
G2  the look-ahead check above.
G3  **THE PREDICTOR MUST BE THE ONE E172 FOUND.** `mu_mean`'s matched-pair statistic is recomputed here on
    the same rows and must reproduce E172's 0.5176 to within 0.01, or the cohort is not E172's and nothing
    downstream is about E172's finding (rule 59).

=========================================================================================================
VERDICT — THE NEGATIVE AND UNINFORMATIVE CASES FIRST (rules 31, 34, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails.
  (2) NO USABLE GAIN      the assessment gain's interval includes zero at every budget, or it does not
                          exceed the random-score placebo. **This replicates Geronimo 2016 and is the
                          registered prediction.** It would mean E172's finding is real and clinically
                          inert at this effect size, and that is what would be reported.
  (3) HURTS               the gain is negative and excludes zero — gating on pre-cue alpha makes
                          assessment WORSE. Enumerated because a selection rule that discards trials can
                          do that, and "excludes zero" is not "supports the hypothesis" (rule 37).
  (4) USABLE              the assessment gain excludes zero, exceeds the placebo, and is large enough at
                          N = 10 to change a bedside decision. **The file states the size in extra
                          detected responses per ten attempts, not as a percentage**, because that is the
                          unit the claim would have to be made in.

**REGISTERED PREDICTION: (2) NO USABLE GAIN.** E172's effect is 1.8 percentage points on a pairwise
statistic; a selection rule cannot extract more than the feature carries, and at N = 10 a shift of that
order is a fraction of one extra hit. Geronimo reached the same conclusion with a different design. **The
prediction is against this project's own positive result**, which is the correct way round, and a file
that predicted otherwise would be arguing for its own finding.

    python bsde/src/bsde/experiments/e179_gating_translation.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e172_matched_pair_trial_responsiveness as E172                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e179_gating_translation.json")
SEED = 20260801

PREDICTOR = "mu_mean"
BUDGETS = (5, 10, 20)
QUANTILES = (0.50, 0.67)
WARMUP = 20
PLACEBO_DRAWS = 500
E172_PRIMARY = 0.5176
E172_TOL = 0.01
MIN_SESSIONS = 40
ALPHA = 0.05


def simulate(x, res, n_budget, q, causal=True, warmup=WARMUP):
    """Walk the session in order and deliver a cue when `x` is above the running quantile.

    Returns (hits, delivered, elapsed). No value from a future trial is ever used when `causal` is True.
    """
    n = len(x)
    thr_all = np.nanquantile(x[np.isfinite(x)], q) if np.isfinite(x).any() else np.nan
    hits = delivered = 0
    seen = []
    for i in range(n):
        xi, yi = x[i], res[i]
        if not (np.isfinite(xi) and np.isfinite(yi)):
            continue
        seen.append(xi)
        if len(seen) <= warmup:
            continue
        thr = thr_all if not causal else float(np.quantile(seen[:-1], q))
        if not np.isfinite(thr) or xi < thr:
            continue
        delivered += 1
        hits += int(yi > 0.5)
        if delivered >= n_budget:
            return hits, delivered, i + 1
    return hits, delivered, n


def control(res, n_budget, warmup=WARMUP):
    """The same budget, taken in order from the same starting point, with no gating."""
    hits = delivered = 0
    seen = 0
    for i, yi in enumerate(res):
        if not np.isfinite(yi):
            continue
        seen += 1
        if seen <= warmup:
            continue
        delivered += 1
        hits += int(yi > 0.5)
        if delivered >= n_budget:
            return hits, delivered, i + 1
    return hits, delivered, len(res)


def arm(sess, n_budget, q, key=PREDICTOR, causal=True, override=None):
    """Per-session (gated hit rate, control hit rate, gated throughput, control throughput)."""
    out = []
    for s in sess:
        x = s["cols"][key] if override is None else override[(s["subject"], s["session"])]
        res = s["cols"]["_result"]
        gh, gd, ge = simulate(x, res, n_budget, q, causal=causal)
        ch, cd, ce = control(res, n_budget)
        if gd < n_budget or cd < n_budget:
            continue
        out.append({"subject": s["subject"],
                    "gated_rate": gh / gd, "control_rate": ch / cd,
                    "gated_throughput": gh / ge, "control_throughput": ch / ce})
    return out


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


def main() -> int:
    print("E179 — can E172's effect be used? Gating at a fixed attempt budget")
    print("   incumbent claim: Geronimo 2016 (PMID 27199630) reports offline gating 'limited in its "
          "ability to produce an increase in device throughput'")
    sess, n_rows = E172.build("result")
    res = {"experiment": "E179", "n_trial_rows": n_rows, "budgets": list(BUDGETS),
           "quantiles": list(QUANTILES), "incumbent": "Geronimo 2016, PMID 27199630"}
    if not sess:
        print("   ABSENT: no trial table.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2

    # attach the per-trial outcome to each session in the shape the simulator wants
    import csv as _csv
    import glob as _glob
    by = {}
    for p in sorted(_glob.glob(os.path.join(RESULTS, "stieger_trials*.csv"))):
        for r in _csv.DictReader(open(p, newline="")):
            by.setdefault((r["subject"], r["session"]), []).append(r)
    for k in by:
        by[k].sort(key=lambda r: int(float(r["trial"])))
    for s in sess:
        rr = by[(s["subject"], s["session"])]
        s["cols"]["_result"] = np.array([E172._f(r["result"]) for r in rr])

    subs = sorted({s["subject"] for s in sess})
    res["n_sessions"], res["n_subjects"] = len(sess), len(subs)
    res["G1_pass"] = bool(len(sess) >= MIN_SESSIONS)
    print(f"   {len(sess)} sessions from {len(subs)} subjects   "
          f"{'G1 PASS' if res['G1_pass'] else '*** G1 FAIL'}")
    if not res["G1_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # G3 -- is this E172's cohort and E172's effect?
    st = E172.frac_stat(sess, PREDICTOR)
    ok3 = abs(st["mean"] - E172_PRIMARY) <= E172_TOL
    res["G3"] = {"recomputed": st["mean"], "e172": E172_PRIMARY, "pass": bool(ok3)}
    print(f"   G3 E172's statistic recomputed here: {st['mean']:.4f} vs published {E172_PRIMARY:.4f}   "
          f"{'PASS' if ok3 else '*** FAIL'}")
    if not ok3:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the cohort does not reproduce E172's statistic, so nothing here is about E172"
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    res["arms"] = {}
    print(f"\n   {'N':>3s} {'q':>5s} {'gated':>7s} {'ctrl':>7s} {'gain':>8s} {'[95% CI]':>20s} "
          f"{'thru gain':>10s} {'placebo p':>10s}")
    any_usable, any_hurts = [], []
    for n_budget in BUDGETS:
        for q in QUANTILES:
            rows = arm(sess, n_budget, q)
            if len(rows) < MIN_SESSIONS:
                print(f"   {n_budget:>3d} {q:>5.2f}   only {len(rows)} sessions reach the budget — skipped")
                continue
            gain = np.asarray([r["gated_rate"] - r["control_rate"] for r in rows])
            thru = np.asarray([r["gated_throughput"] - r["control_throughput"] for r in rows])
            subs_r = [r["subject"] for r in rows]
            lo, hi = ci(gain, subs_r, np.random.default_rng(SEED + 1))

            # placebo: the same gate driven by a random score
            prng = np.random.default_rng(SEED + 2)
            pg = []
            for _ in range(PLACEBO_DRAWS):
                ov = {(s["subject"], s["session"]): prng.normal(size=s["n_trials"]) for s in sess}
                pr = arm(sess, n_budget, q, override=ov)
                if len(pr) >= MIN_SESSIONS:
                    pg.append(float(np.mean([r["gated_rate"] - r["control_rate"] for r in pr])))
            pgv = np.asarray(pg)
            p_pl = float((pgv >= gain.mean()).mean()) if pgv.size >= 30 else float("nan")

            cell = {"n": n_budget, "q": q, "n_sessions": len(rows),
                    "gated_rate": float(np.mean([r["gated_rate"] for r in rows])),
                    "control_rate": float(np.mean([r["control_rate"] for r in rows])),
                    "gain": float(gain.mean()), "ci": [lo, hi],
                    "throughput_gain": float(thru.mean()),
                    "placebo_mean": float(pgv.mean()) if pgv.size else float("nan"),
                    "placebo_p": p_pl,
                    "extra_hits_per_10": float(10 * gain.mean())}
            res["arms"][f"N{n_budget}_q{q}"] = cell
            print(f"   {n_budget:>3d} {q:>5.2f} {cell['gated_rate']:>7.4f} {cell['control_rate']:>7.4f} "
                  f"{cell['gain']:>+8.4f} [{lo:>+8.4f},{hi:>+8.4f}] {cell['throughput_gain']:>+10.4f} "
                  f"{p_pl:>10.4f}")
            if lo > 0 and np.isfinite(p_pl) and p_pl <= ALPHA:
                any_usable.append(cell)
            if hi < 0:
                any_hurts.append(cell)

    # G2 -- look-ahead check
    c_rows = arm(sess, 10, 0.67, causal=True)
    o_rows = arm(sess, 10, 0.67, causal=False)
    c_gain = float(np.mean([r["gated_rate"] - r["control_rate"] for r in c_rows])) if c_rows else float("nan")
    o_gain = float(np.mean([r["gated_rate"] - r["control_rate"] for r in o_rows])) if o_rows else float("nan")
    g2 = np.isfinite(c_gain) and np.isfinite(o_gain) and abs(c_gain - o_gain) > 1e-4
    res["G2"] = {"causal_gain": c_gain, "oracle_gain": o_gain, "pass": bool(g2)}
    print(f"\n   G2 look-ahead: causal gate {c_gain:+.4f} vs whole-session oracle {o_gain:+.4f}   "
          f"{'PASS -- they differ, so the quantile really is running' if g2 else '*** FAIL -- identical'}")

    if not g2:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the causal and oracle gates are identical, so the running quantile is not running"
    elif any_hurts:
        res["verdict"] = "HURTS"
        res["why"] = ("gating on pre-cue alpha makes assessment WORSE at "
                      f"{[(c['n'], c['q']) for c in any_hurts]}")
    elif not any_usable:
        best = max((c for c in res["arms"].values()), key=lambda c: c["gain"], default=None)
        res["verdict"] = "NO-USABLE-GAIN"
        res["why"] = ("no budget and quantile gives a gain that both excludes zero and beats the "
                      "random-score placebo. **This replicates Geronimo 2016 on ~10x the trials.** "
                      + (f"The best cell is N = {best['n']}, q = {best['q']:.2f} at "
                         f"{best['extra_hits_per_10']:+.2f} extra detected responses per ten attempts."
                         if best else ""))
    else:
        b = max(any_usable, key=lambda c: c["gain"])
        res["verdict"] = "USABLE"
        res["why"] = (f"gating gives {b['extra_hits_per_10']:+.2f} extra detected responses per ten "
                      f"attempts at N = {b['n']}, q = {b['q']:.2f}, above the random-score placebo "
                      f"(p = {b['placebo_p']:.4f}) -- stated in attempts rather than percentages because "
                      "that is the unit the claim has to be made in")
    print(f"\n   VERDICT {res['verdict']} — {res['why']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
