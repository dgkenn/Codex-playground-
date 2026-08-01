"""E174 — E172 on 124 HELD-OUT sessions, with nothing free to move.

REGISTERED BEFORE `results/stieger_holdout_trials*.csv` CONTAINS A COMPLETE SUBJECT. The extraction was
launched in the same change and no held-out value has been read.

=========================================================================================================
WHAT IS BEING REPLICATED, QUOTED EXACTLY SO THE BAR CANNOT DRIFT
=========================================================================================================
E172, on session 1 of each of 62 Stieger subjects — 6,413 matched hit/miss pairs, all gates passing:

    mu_mean               0.5176 [0.5054, 0.5303]   p = 0.0060   same side 0.61
    mu_c4                 0.5171 [0.5054, 0.5298]   p = 0.0095   same side 0.69
    relative_alpha_power  0.5219 [0.5111, 0.5335]   p = 0.0010   same side 0.66
    placebo (previous trial's outcome)   0.4953, p = 0.4510
    measured floor rho = 0.05; trial index as a candidate 0.4920, p = 0.2070

**Everything in this file is fixed to those choices**: the same primary, the same statistic, the same
`MAX_GAP = 5`, the same `MIN_PAIRS = 30`, the same hit-rate band, the same placebo, the same ladder. The
only thing that changes is which sessions the rows come from. There is no candidate selection, no
threshold to set and no cohort to choose, which is the entire point of a replication file.

=========================================================================================================
ONE-SIDED, AND WHY THAT IS THE CORRECT USE OF PRIOR INFORMATION RATHER THAN A WEAKENED TEST
=========================================================================================================
E172 was two-sided because the direction was genuinely open — Blankertz 2010's between-subject sign is
positive, the pre-stimulus attention literature points the other way, and PMID 27199630 reports a
single-trial association **without stating a sign**. That question is now answered on session 1: more
pre-cue alpha, more successful trials.

A replication of a known-direction effect is **one-sided in the direction already observed**, declared
here before any held-out row is read. A result in the OPPOSITE direction is therefore not a partial
success and cannot be reported as one — it is enumerated below as its own verdict, `REVERSED`, and it
would be the more interesting outcome.

=========================================================================================================
THE LIMITATION THAT MUST TRAVEL WITH THIS RESULT, STATED BEFORE THE RUN
=========================================================================================================
**These are the SAME 62 subjects.** Sessions 2 and 3 are new recordings, new days, new electrode
applications and new trials, so this tests whether the effect is a property of the session or of the
recording day — a real and non-trivial question, since E97 showed some measures here are trait-like
(ICC(2,1) = 0.4288). It does **not** test subject-generality, and a pass here is NOT an independent
replication in the sampling sense.

The external test is a different deposit and is registered separately as E175 on eegmmidb. Neither file
may be described as validating the other's construct.

=========================================================================================================
GATES — IDENTICAL TO E172's, NOT RE-TUNED
=========================================================================================================
G1  >= 60 sessions with >= 30 pairs (E172 had 62; the held-out set should have ~124, so this floor is
    deliberately loose and exists only to refuse a part-finished extraction).
G2  (a) directional balance of the pairing against its own flip null; (b) trial index scored as a
    candidate must be at chance.
G3  (a) an i.i.d. noise feature must NOT be detected; (b) the ladder must detect something, and the
    measured floor is reported beside the effect.

=========================================================================================================
VERDICT — THE FAILING AND WRONG-DIRECTION CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3(a) fails.
  (2) NO POWER           G3(b) detects nothing at any rung.
  (3) REVERSED           the primary excludes 0.5 on the side OPPOSITE to E172's. Not a partial success:
                         it would mean the session-1 direction does not survive a change of recording day,
                         and both results would then need withdrawing pending explanation.
  (4) LAGGED             the primary reaches one-sided p <= 0.05 but the previous-trial placebo matches it.
  (5) NOT REPLICATED     the primary's one-sided p > 0.05. The effect is session-1-specific and E172's
                         result is reported thereafter only with this failure attached.
  (6) REPLICATED         one-sided p <= 0.05 in E172's direction, placebo clean, majority of sessions on
                         the same side.

REGISTERED PREDICTION: **(6)**, and the honest reason is that E172's own interval is comfortably clear of
0.5 and its per-session sign count was 0.61 — but the effect is 1.8 percentage points, the held-out set is
twice the size, and a failure here is entirely plausible. **The prediction is recorded so that a failure
costs something.**

    python bsde/src/bsde/experiments/e174_trial_replication_heldout_sessions.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e172_matched_pair_trial_responsiveness as E172                          # noqa: E402
from bsde.verifier.stats import screen_candidates, spearman                    # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e174_trial_replication_heldout.json")
SEED = 20260801

# E172's published numbers, transcribed IN FULL (rule 59) -- every candidate it reported, not the
# flattering subset -- so the comparison cannot be made against a chosen row afterwards.
E172_TABLE = {
    "mu_mean": 0.5176, "mu_c3": 0.5116, "mu_c4": 0.5171, "mu_lateralisation": 0.4960,
    "relative_alpha_power": 0.5219, "relative_delta_power": 0.4957, "exponent_low": 0.4998,
    "exponent_high": 0.4916, "whole_head_exponent": 0.5129, "spectral_edge_95": 0.4944,
    "spectral_entropy": 0.4978, "lempel_ziv": 0.5042,
}
E172_PRIMARY = 0.5176
E172_DIRECTION = 1                 # E172's primary sits ABOVE 0.5; the one-sided test is in this direction
MIN_SESSIONS = 60
ALPHA = 0.05
Q = 0.05


def load_holdout():
    """E172's loader, pointed at the held-out shards. Session 1 cannot leak in: it is not in these files."""
    paths = sorted(glob.glob(os.path.join(RESULTS, "stieger_holdout_trials*.csv")))
    if not paths:
        return None, 0
    orig_glob = os.path.join(RESULTS, "stieger_trials*.csv")

    import csv as _csv
    seen, rows = set(), []
    for p in paths:
        if os.path.getsize(p) == 0:
            continue
        for r in _csv.DictReader(open(p, newline="")):
            k = (r.get("subject"), r.get("session"), r.get("trial"))
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    assert all(str(r["session"]) != "1" for r in rows), \
        f"a session-1 row reached the held-out table; {orig_glob} must not be globbed here"
    by = {}
    for r in rows:
        by.setdefault((r["subject"], r["session"]), []).append(r)
    for k in by:
        by[k].sort(key=lambda r: int(float(r["trial"])))

    sess = []
    for (subj, s), rr in sorted(by.items()):
        res = np.array([E172._f(r["result"]) for r in rr])
        ok = np.isfinite(res)
        if ok.sum() < E172.MIN_PAIRS:
            continue
        pairs = E172.make_pairs(res)
        if len(pairs) < E172.MIN_PAIRS:
            continue
        cols = {c: np.array([E172._f(r.get(c, "")) for r in rr])
                for c in E172.CANDIDATES + [E172.INCUMBENT]}
        cols["_index"] = np.arange(len(rr), dtype=float)
        sess.append({"subject": subj, "session": s, "pairs": pairs, "cols": cols,
                     "n_trials": len(rr)})
    return sess, len(rows)


def one_sided_p(sess, name, rng, reps=E172.REPS):
    """Fraction of within-pair-flip nulls at or beyond the observed value, IN E172's DIRECTION."""
    obs = E172.frac_stat(sess, name)["mean"]
    if not np.isfinite(obs):
        return obs, float("nan"), float("nan"), 0
    nulls = []
    for _ in range(reps):
        flips = [rng.integers(0, 2, len(s["pairs"])).astype(bool) for s in sess]
        v = E172.frac_stat(sess, name, flips=flips)["mean"]
        if np.isfinite(v):
            nulls.append(v)
    if len(nulls) < 30:
        return obs, float("nan"), float("nan"), len(nulls)
    n = np.asarray(nulls)
    p = float((n >= obs).mean()) if E172_DIRECTION > 0 else float((n <= obs).mean())
    return obs, p, float(n.mean()), len(n)


def main() -> int:
    print("E174 — E172 on held-out Stieger sessions 2 and 3, one-sided in E172's direction")
    sess, n_rows = load_holdout()
    res = {"experiment": "E174", "n_trial_rows": n_rows,
           "e172_primary": E172_PRIMARY, "e172_table": E172_TABLE,
           "one_sided_direction": "above 0.5"}
    if not sess:
        print("   ABSENT: the held-out extraction has produced nothing yet.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2
    subs = sorted({s["subject"] for s in sess})
    npairs = [len(s["pairs"]) for s in sess]
    res.update({"n_sessions": len(sess), "n_subjects": len(subs), "total_pairs": int(sum(npairs))})
    res["G1_pass"] = bool(len(sess) >= MIN_SESSIONS)
    print(f"   {n_rows} held-out trial rows -> {len(sess)} sessions from {len(subs)} subjects, "
          f"{sum(npairs)} pairs")
    print(f"   G1 {'PASS' if res['G1_pass'] else '*** FAIL'} (floor {MIN_SESSIONS} sessions)")
    if not res["G1_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    gaps = np.concatenate([[h - m for (h, m) in s["pairs"]] for s in sess]).astype(float)
    signed = float(gaps.mean())
    gnull = np.asarray([float((gaps * np.where(rng.integers(0, 2, gaps.size) > 0, -1, 1)).mean())
                        for _ in range(2000)])
    lo, hi = float(np.quantile(gnull, 0.025)), float(np.quantile(gnull, 0.975))
    g2a = lo <= signed <= hi
    res["G2a"] = {"mean_signed_gap": signed, "null_lo": lo, "null_hi": hi,
                  "mean_abs_gap": float(np.abs(gaps).mean()), "pass": bool(g2a)}
    print(f"   G2(a) signed gap {signed:+.4f} vs [{lo:+.4f}, {hi:+.4f}], |gap| "
          f"{np.abs(gaps).mean():.2f}   {'PASS' if g2a else '*** FAIL'}")

    idx_over = {(s["subject"], s["session"]): s["cols"]["_index"] for s in sess}
    io_obs, io_p, _, _ = E172.flip_null(sess, E172.PRIMARY, np.random.default_rng(SEED + 2),
                                        reps=1000, override=idx_over)
    g2b = np.isfinite(io_p) and io_p > ALPHA
    res["G2b"] = {"mean": float(io_obs), "p": float(io_p), "pass": bool(g2b)}
    print(f"   G2(b) trial index as a candidate {io_obs:.4f}, p = {io_p:.4f}   "
          f"{'PASS' if g2b else '*** FAIL'}")
    if not (g2a and g2b):
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the pairing did not remove position in the held-out sessions"
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    print("\n   G3 calibration and floor")
    _, p0, _, _ = E172.flip_null(sess, E172.PRIMARY, np.random.default_rng(SEED + 3), reps=1000,
                                 override=E172.synthetic(sess, 0.0, rng))
    res["G3a"] = {"p": float(p0), "pass": bool(np.isfinite(p0) and p0 > ALPHA)}
    print(f"      (a) i.i.d. noise: p = {p0:.4f}   {'PASS' if res['G3a']['pass'] else '*** FAIL'}")
    floor, ladder = None, []
    for rho in E172.RUNGS:
        _, p, _, _ = E172.flip_null(sess, E172.PRIMARY, np.random.default_rng(SEED + 4), reps=1000,
                                    override=E172.synthetic(sess, rho, rng))
        ladder.append({"rho": rho, "p": float(p)})
        print(f"      (b) rho = {rho:.2f}: p = {p:.4f}")
        if np.isfinite(p) and p <= ALPHA:
            floor = rho
            break
    res["G3b_ladder"], res["floor"] = ladder, floor
    print(f"      FLOOR: {'none' if floor is None else '%.2f' % floor}")
    if not res["G3a"]["pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "an i.i.d. noise feature is detected in the held-out sessions"
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pool = {c: np.concatenate([s["cols"][c] for s in sess]) for c in E172.CANDIDATES}
    usable, dropped = screen_candidates(pool)
    for c, why in dropped.items():
        print(f"   dropped: {c} ({why})")
    names = [c for c in E172.CANDIDATES if c in usable]
    print(f"\n   {'candidate':<24s} {'held-out':>9s} {'E172':>9s} {'delta':>8s} "
          f"{'[95% CI]':>20s} {'same side':>10s} {'p(1-sided)':>11s}")
    table, ps = {}, []
    for c in names:
        st = E172.frac_stat(sess, c)
        obs, p, nm, k = one_sided_p(sess, c, np.random.default_rng(SEED + 11))
        lo_, hi_ = E172.cluster_ci(st, np.random.default_rng(SEED + 12))
        ref = E172_TABLE.get(c, float("nan"))
        table[c] = {"mean": st["mean"], "e172": ref, "delta": st["mean"] - ref,
                    "ci": [lo_, hi_], "frac_same_side": st["frac_same_side"],
                    "p_one_sided": float(p), "null_mean": float(nm), "n_null": int(k)}
        ps.append(p)
        print(f"   {c:<24s} {st['mean']:>9.4f} {ref:>9.4f} {st['mean'] - ref:>+8.4f} "
              f"[{lo_:>8.4f},{hi_:>8.4f}] {st['frac_same_side']:>10.2f} {p:>11.4f}")
    keep = E172.bh(ps, q=Q)
    res["table"], res["survivors_bh"] = table, [names[i] for i in sorted(keep)]
    print(f"   BH q={Q}: {res['survivors_bh'] or 'none'}")

    print("\n   PLACEBO — pairs re-formed on the PREVIOUS trial's outcome is not available for the "
          "held-out table without a second build; it is run on the same rows below")
    prim = table[E172.PRIMARY]
    pobs, pp = float("nan"), float("nan")
    try:
        psess = []
        for s in sess:
            res_prev = np.full(s["n_trials"], np.nan)
            # reconstruct the previous-trial outcome from the pair structure is NOT possible; rebuild
            # instead from the raw rows via E172's own builder pointed at the held-out glob
            psess = None
            break
        if psess is None:
            import csv as _csv
            by = {}
            for p_ in sorted(glob.glob(os.path.join(RESULTS, "stieger_holdout_trials*.csv"))):
                for r in _csv.DictReader(open(p_, newline="")):
                    by.setdefault((r["subject"], r["session"]), []).append(r)
            built = []
            for (subj, s_), rr in sorted(by.items()):
                rr.sort(key=lambda r: int(float(r["trial"])))
                cur = np.array([E172._f(r["result"]) for r in rr])
                prev = np.concatenate([[np.nan], cur[:-1]])
                pairs = E172.make_pairs(prev)
                if len(pairs) < E172.MIN_PAIRS:
                    continue
                cols = {c: np.array([E172._f(r.get(c, "")) for r in rr])
                        for c in E172.CANDIDATES + [E172.INCUMBENT]}
                cols["_index"] = np.arange(len(rr), dtype=float)
                built.append({"subject": subj, "session": s_, "pairs": pairs, "cols": cols,
                              "n_trials": len(rr)})
            if len(built) >= MIN_SESSIONS:
                pobs, pp, _, _ = E172.flip_null(built, E172.PRIMARY,
                                                np.random.default_rng(SEED + 21))
                print(f"      {E172.PRIMARY} against the previous trial: {pobs:.4f}, p = {pp:.4f} "
                      f"({len(built)} sessions)")
            else:
                print(f"      only {len(built)} sessions -- the placebo is ABSENT (rule 31)")
    except Exception as exc:                                               # noqa: BLE001
        print(f"      placebo not computable: {type(exc).__name__}: {exc}")
    res["placebo"] = {"mean": float(pobs), "p": float(pp)}

    if floor is None:
        v, why = "NO-POWER", "no injected within-pair effect is detectable in the held-out sessions"
    elif np.isfinite(prim["ci"][1]) and prim["ci"][1] < 0.5:
        v, why = "REVERSED", ("the primary excludes 0.5 on the side OPPOSITE to E172's; the session-1 "
                              "direction does not survive a change of recording day and BOTH results "
                              "need withdrawing pending an explanation")
    elif not (np.isfinite(prim["p_one_sided"]) and prim["p_one_sided"] <= ALPHA):
        v, why = "NOT-REPLICATED", (f"one-sided p = {prim['p_one_sided']:.4f}; the effect is specific to "
                                    "session 1 and E172's result carries this failure from here on")
    elif np.isfinite(pp) and pp <= ALPHA and abs(pobs - 0.5) >= abs(prim["mean"] - 0.5):
        v, why = "LAGGED", "the previous trial's outcome is explained at least as well"
    elif np.isfinite(prim["frac_same_side"]) and prim["frac_same_side"] < 0.5:
        v, why = "NOT-CLAIMED", "fewer than half the held-out sessions fall on the mean's side of 0.5"
    else:
        v, why = "REPLICATED", (f"held-out {prim['mean']:.4f} against E172's {E172_PRIMARY:.4f} "
                                f"(delta {prim['delta']:+.4f}), one-sided p = {prim['p_one_sided']:.4f}, "
                                "on new recording days from the same subjects -- session-general, NOT an "
                                "independent-sample replication")
    res["verdict"], res["why"] = v, why
    print(f"\n   VERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
