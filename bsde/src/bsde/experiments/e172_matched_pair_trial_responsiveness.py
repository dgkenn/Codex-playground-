"""E172 — E167's question with the clock removed BY CONSTRUCTION instead of by regression.

REGISTERED BEFORE ANY PAIR HAS BEEN FORMED.

=========================================================================================================
WHY THIS FILE EXISTS AND WHAT IT MAY NOT DO
=========================================================================================================
E167 asked whether the 2 s of spontaneous EEG before a cue predicts whether THAT trial's command is
followed. It failed its own gate, twice, and the failure is recorded rather than repaired further: the
registered polynomial adjustment left a rank correlation of **+0.2184** between trial index and the
residualised outcome against a measured null of [-0.0790, +0.0789], and the one repair rule 58 allows —
centring inside 10 blocks of consecutive trials — still left position predicting the outcome at
**mean r = -0.0416, p = 0.0000** when scored as a candidate by the primary's own statistic. Later trials
inside a block are less successful, so any feature with a within-block time trend inherits an association.

**The instrument change is the design, not the adjustment.** Regression cannot be trusted to remove a
trend whose shape is unknown; a paired design does not have to. Each HIT trial is matched to the nearest
MISS trial in the same session within `MAX_GAP` trials, each trial used at most once. The two members of a
pair are neighbours in time, so drift, impedance, gel, fatigue and practice are all differenced out
**by construction rather than by model**, and no position term appears anywhere in the statistic.

This is a legitimate successor because it changes the instrument and keeps the question, the cohort, the
candidate list and the two-sidedness fixed (rule 58). What it may NOT do is re-open E167's gates or read
E167's unlicensed numbers as support: they are recorded in that ledger row as unlicensed and they stay
that way whatever this file finds.

=========================================================================================================
ESTIMAND AND STATISTIC
=========================================================================================================
    pairing     within session, each hit matched to the nearest unused miss with |delta trial| <= MAX_GAP,
                taken in order of increasing gap so the closest pairs are formed first
    per session the FRACTION of its pairs in which the feature is larger on the hit trial
    reported    the mean of that fraction over sessions; 0.5 is no effect
    interval    cluster bootstrap over SUBJECTS (sessions are nested in subjects, rule 69)
    null        the exact paired permutation: flip the hit/miss assignment WITHIN each pair,
                independently, which is precisely the randomisation this estimand assumes and leaves
                every other structure -- session, pair membership, time, feature values -- untouched
                (rule 55: the destruction matches the estimand)

TWO-SIDED, and for E167's reason unchanged: Blankertz 2010's between-subject predictor says more resting
sensorimotor rhythm goes with better control, PMID 27199630 reports central mu at cue presentation
"correlated with the success on the subsequent imagery task" without stating a sign, and the pre-stimulus
attention literature points the other way. This project has no basis to choose (rule 42).

PRIMARY    `mu_mean` — relative alpha over C3 and C4, the variable PMID 27199630 names.
SECONDARY  `mu_c3`, `mu_c4`, `mu_lateralisation` and the eight-feature spectral panel, BH at q = 0.05.
INCUMBENT  `artifact`, the deposit's own per-trial flag, scored identically. Reported as the bar, not used
           as a gate, because G3 establishes the instrument's aliveness synthetically.

=========================================================================================================
GATES
=========================================================================================================
G1  PAIRING YIELD: >= 40 sessions with >= 30 pairs each.
G2  **THE CLOCK IS ACTUALLY GONE, AND THIS CAN FAIL.** Two checks, both against measured nulls rather than
    round numbers (rule 63). (a) The mean SIGNED gap (hit index minus miss index) must sit inside its own
    within-pair flip null — greedy nearest matching could systematically place the miss earlier or later,
    which would reintroduce direction. (b) **Trial index scored as a candidate by the identical
    statistic** must be at chance. Under this design (b) is not degenerate and is the direct test that
    pairing did what regression could not.
G3  CALIBRATION AND FLOOR, both halves, either can fail. (a) An i.i.d. synthetic feature must NOT be
    detected. (b) A ladder of injected within-pair effects gives the **measured detection floor**; no
    detected rung means every null here is ABSENT rather than negative (rule 31).

=========================================================================================================
PLACEBO, AND IT GATES THE VERDICT (rule 34)
=========================================================================================================
Unchanged in intent from E167: **the outcome is replaced by the PREVIOUS trial's outcome**, pairs re-formed
on that basis. If the pre-cue window explains the trial just finished as well as the one about to start,
the association is a lagged consequence of the last trial and the forward claim is refused. It is a
comparison against the placebo's own null, never a threshold.

=========================================================================================================
VERDICT — UNINFORMATIVE AND WRONG-DIRECTION CASES FIRST (rules 31, 37, 48)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1 or either half of G2 or G3(a) fails.
  (2) NO POWER           G3(b) detects nothing: every candidate null is ABSENT, not negative.
  (3) LAGGED             the primary reaches p <= 0.05 and the placebo matches it against its own null.
  (4) NOT CLAIMED        the primary reaches p <= 0.05 but fewer than half the sessions share the sign.
  (5) PRESENT            the primary survives all of the above; the direction is REPORTED against the
                         between-subject sign, never predicted.
  (6) ABSENT ABOVE FLOOR p > 0.05 with a floor established.

REGISTERED EXPECTATION. E167's unlicensed run pointed at (5) with a positive sign, and that is exactly why
it is not being treated as a prediction: a number produced under a failed gate is not evidence about what
the repaired design will find, and writing it down as an expectation would launder it. **No prediction is
registered.**

    python bsde/src/bsde/experiments/e172_matched_pair_trial_responsiveness.py
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

from bsde.verifier.stats import screen_candidates, spearman                    # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e172_matched_pair_trial_responsiveness.json")
SEED = 20260801

PRIMARY = "mu_mean"
CANDIDATES = ["mu_mean", "mu_c3", "mu_c4", "mu_lateralisation",
              "relative_alpha_power", "relative_delta_power", "exponent_low", "exponent_high",
              "whole_head_exponent", "spectral_edge_95", "spectral_entropy", "lempel_ziv"]
INCUMBENT = "artifact"

MAX_GAP = 5
MIN_PAIRS = 30
MIN_SESSIONS = 40
REPS = 2000
RUNGS = (0.02, 0.05, 0.10, 0.20)
ALPHA = 0.05
Q = 0.05


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load_rows():
    seen, rows = set(), []
    for p in sorted(glob.glob(os.path.join(RESULTS, "stieger_trials*.csv"))):
        if os.path.getsize(p) == 0:
            continue
        for r in csv.DictReader(open(p, newline="")):
            k = (r.get("subject"), r.get("session"), r.get("trial"))
            if k in seen:                       # rule 56: de-duplicate on the key when loading
                continue
            seen.add(k)
            rows.append(r)
    by = {}
    for r in rows:
        by.setdefault((r["subject"], r["session"]), []).append(r)
    for k in by:
        by[k].sort(key=lambda r: int(float(r["trial"])))
    return by, len(rows)


def make_pairs(res, max_gap=MAX_GAP):
    """Nearest-neighbour hit/miss pairs inside one session, closest gaps formed first."""
    hits = [i for i, v in enumerate(res) if np.isfinite(v) and v > 0.5]
    miss = [i for i, v in enumerate(res) if np.isfinite(v) and v <= 0.5]
    cand = []
    for h in hits:
        for m in miss:
            g = abs(h - m)
            if g <= max_gap:
                cand.append((g, h, m))
    cand.sort()
    used_h, used_m, pairs = set(), set(), []
    for g, h, m in cand:
        if h in used_h or m in used_m:
            continue
        used_h.add(h)
        used_m.add(m)
        pairs.append((h, m))
    return pairs


def build(outcome="result"):
    by, n_rows = load_rows()
    sess = []
    for (subj, s), rr in sorted(by.items()):
        res = np.array([_f(r[outcome]) if outcome in r else np.nan for r in rr]) \
            if outcome == "result" else \
            np.concatenate([[np.nan], np.array([_f(r["result"]) for r in rr])[:-1]])
        pairs = make_pairs(res)
        if len(pairs) < MIN_PAIRS:
            continue
        cols = {c: np.array([_f(r.get(c, "")) for r in rr]) for c in CANDIDATES + [INCUMBENT]}
        cols["_index"] = np.arange(len(rr), dtype=float)
        sess.append({"subject": subj, "session": s, "pairs": pairs, "cols": cols,
                     "n_trials": len(rr)})
    return sess, n_rows


def frac_stat(sess, name, flips=None, override=None):
    """Mean over sessions of the fraction of pairs where the feature is larger on the HIT trial."""
    vals, subs = [], []
    for si, s in enumerate(sess):
        x = s["cols"][name] if override is None else override[(s["subject"], s["session"])]
        f = None if flips is None else flips[si]
        hi = []
        for pi, (h, m) in enumerate(s["pairs"]):
            a, b = (h, m) if (f is None or not f[pi]) else (m, h)
            xa, xb = x[a], x[b]
            if np.isfinite(xa) and np.isfinite(xb) and xa != xb:
                hi.append(1.0 if xa > xb else 0.0)
        if len(hi) >= MIN_PAIRS // 2:
            vals.append(float(np.mean(hi)))
            subs.append(s["subject"])
    if not vals:
        return {"mean": float("nan"), "median": float("nan"), "n_sessions": 0,
                "frac_same_side": float("nan"), "vals": [], "subjects": []}
    v = np.asarray(vals)
    mu = float(v.mean())
    return {"mean": mu, "median": float(np.median(v)), "n_sessions": int(v.size),
            "frac_same_side": float(np.mean(np.sign(v - 0.5) == np.sign(mu - 0.5))),
            "vals": v.tolist(), "subjects": subs}


def flip_null(sess, name, rng, reps=REPS, override=None):
    """Exact paired permutation: flip hit/miss WITHIN each pair, independently."""
    obs = frac_stat(sess, name, override=override)["mean"]
    if not np.isfinite(obs):
        return obs, float("nan"), float("nan"), 0
    nulls = []
    for _ in range(reps):
        flips = [rng.integers(0, 2, len(s["pairs"])).astype(bool) for s in sess]
        v = frac_stat(sess, name, flips=flips, override=override)["mean"]
        if np.isfinite(v):
            nulls.append(v)
    if len(nulls) < 30:
        return obs, float("nan"), float("nan"), len(nulls)
    n = np.asarray(nulls)
    p = float((np.abs(n - n.mean()) >= abs(obs - n.mean())).mean())
    return obs, p, float(n.mean()), len(n)


def cluster_ci(stat, rng, reps=2000):
    v, subs = np.asarray(stat["vals"]), np.asarray(stat["subjects"])
    if v.size == 0:
        return float("nan"), float("nan")
    uniq = np.unique(subs)
    draws = []
    for _ in range(reps):
        pick = rng.choice(uniq, size=uniq.size, replace=True)
        vals = np.concatenate([v[subs == u] for u in pick])
        if vals.size:
            draws.append(vals.mean())
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def synthetic(sess, rho, rng):
    """A feature carrying a KNOWN within-pair effect of size `rho` on the hit member."""
    out = {}
    for s in sess:
        x = rng.normal(size=s["n_trials"])
        for (h, m) in s["pairs"]:
            x[h] += rho
        out[(s["subject"], s["session"])] = x
    return out


def bh(pvals, q=Q):
    idx = [i for i, p in enumerate(pvals) if np.isfinite(p)]
    if not idx:
        return set()
    order = sorted(idx, key=lambda i: pvals[i])
    keep, m = set(), len(order)
    for rank, i in enumerate(order, 1):
        if pvals[i] <= q * rank / m:
            keep = set(order[:rank])
    return keep


def main() -> int:
    print("E172 — matched-pair trial responsiveness: the clock removed by construction")
    sess, n_rows = build("result")
    res = {"experiment": "E172", "n_trial_rows": n_rows, "max_gap": MAX_GAP}
    if not sess:
        print("   ABSENT: no session yields enough pairs.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2
    npairs = [len(s["pairs"]) for s in sess]
    subs = sorted({s["subject"] for s in sess})
    res.update({"n_sessions": len(sess), "n_subjects": len(subs), "total_pairs": int(sum(npairs)),
                "median_pairs_per_session": float(np.median(npairs))})
    res["G1_pass"] = bool(len(sess) >= MIN_SESSIONS)
    print(f"   {n_rows} trial rows -> {len(sess)} sessions from {len(subs)} subjects, "
          f"{sum(npairs)} pairs (median {np.median(npairs):.0f} per session)")
    print(f"   G1 {'PASS' if res['G1_pass'] else '*** FAIL'} (floor {MIN_SESSIONS} sessions, "
          f"{MIN_PAIRS} pairs each)")
    if not res["G1_pass"]:
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)

    # G2(a) -- is the matching directionally balanced?
    gaps = np.concatenate([[h - m for (h, m) in s["pairs"]] for s in sess]).astype(float)
    signed = float(gaps.mean())
    gnull = np.asarray([float((gaps * np.where(rng.integers(0, 2, gaps.size) > 0, -1, 1)).mean())
                        for _ in range(2000)])
    lo, hi = float(np.quantile(gnull, 0.025)), float(np.quantile(gnull, 0.975))
    g2a = lo <= signed <= hi
    res["G2a"] = {"mean_signed_gap": signed, "null_lo": lo, "null_hi": hi,
                  "mean_abs_gap": float(np.abs(gaps).mean()), "pass": bool(g2a)}
    print(f"   G2(a) mean signed gap (hit - miss) {signed:+.4f} vs flip null [{lo:+.4f}, {hi:+.4f}]; "
          f"mean |gap| {np.abs(gaps).mean():.2f} trials   {'PASS' if g2a else '*** FAIL'}")

    # G2(b) -- trial index scored as a candidate by the identical statistic
    idx_over = {(s["subject"], s["session"]): s["cols"]["_index"] for s in sess}
    io_obs, io_p, _, _ = flip_null(sess, PRIMARY, np.random.default_rng(SEED + 2), reps=1000,
                                   override=idx_over)
    g2b = np.isfinite(io_p) and io_p > ALPHA
    res["G2b"] = {"mean": float(io_obs), "p": float(io_p), "pass": bool(g2b)}
    print(f"   G2(b) trial index as a candidate: {io_obs:.4f}, p = {io_p:.4f}   "
          f"{'PASS -- the clock is gone' if g2b else '*** FAIL -- the clock survives'}")
    if not (g2a and g2b):
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the pairing did not remove position; nothing is readable"
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # G3 -- calibration and floor
    print("\n   G3 calibration and floor")
    _, p0, _, _ = flip_null(sess, PRIMARY, np.random.default_rng(SEED + 3), reps=1000,
                            override=synthetic(sess, 0.0, rng))
    res["G3a"] = {"p": float(p0), "pass": bool(np.isfinite(p0) and p0 > ALPHA)}
    print(f"      (a) i.i.d. noise: p = {p0:.4f}   "
          f"{'PASS' if res['G3a']['pass'] else '*** FAIL -- noise detected'}")
    floor, ladder = None, []
    for rho in RUNGS:
        _, p, _, _ = flip_null(sess, PRIMARY, np.random.default_rng(SEED + 4), reps=1000,
                               override=synthetic(sess, rho, rng))
        ladder.append({"rho": rho, "p": float(p)})
        det = np.isfinite(p) and p <= ALPHA
        print(f"      (b) rho = {rho:.2f}: p = {p:.4f}   {'DETECTED' if det else 'not detected'}")
        if det:
            floor = rho
            break
    res["G3b_ladder"], res["floor"] = ladder, floor
    print(f"      FLOOR: {'none up to %.2f' % max(RUNGS) if floor is None else '%.2f' % floor}")
    if not res["G3a"]["pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "an i.i.d. noise feature is detected; the paired null is anti-conservative"
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # candidate table
    pool = {c: np.concatenate([s["cols"][c] for s in sess]) for c in CANDIDATES}
    usable, dropped = screen_candidates(pool)
    for c, why in dropped.items():
        print(f"   dropped: {c} ({why})")
    names = [c for c in CANDIDATES if c in usable] + [INCUMBENT]
    print(f"\n   {'candidate':<24s} {'frac hit>miss':>13s} {'[95% CI]':>20s} {'same side':>10s} {'p':>8s}")
    table, ps = {}, []
    for c in names:
        st = frac_stat(sess, c)
        obs, p, nm, k = flip_null(sess, c, np.random.default_rng(SEED + 11))
        lo_, hi_ = cluster_ci(st, np.random.default_rng(SEED + 12))
        table[c] = {"mean": st["mean"], "median": st["median"], "n_sessions": st["n_sessions"],
                    "frac_same_side": st["frac_same_side"], "ci": [lo_, hi_], "p": float(p),
                    "null_mean": float(nm), "n_null": int(k)}
        if c != INCUMBENT:
            ps.append(p)
        print(f"   {c:<24s} {st['mean']:>13.4f} [{lo_:>8.4f},{hi_:>8.4f}] "
              f"{st['frac_same_side']:>10.2f} {p:>8.4f}"
              + ("   <- INCUMBENT" if c == INCUMBENT else ""))
    keep = bh(ps)
    cn = [c for c in names if c != INCUMBENT]
    res["table"], res["survivors_bh"] = table, [cn[i] for i in sorted(keep)]
    print(f"   BH q={Q}: {res['survivors_bh'] or 'none'}")

    # placebo -- the PREVIOUS trial's outcome, pairs re-formed on it
    print("\n   PLACEBO — pairs re-formed on the PREVIOUS trial's outcome")
    psess, _ = build("prev")
    if len(psess) < MIN_SESSIONS:
        res["placebo"] = {"status": "NOT-ESTIMABLE", "n_sessions": len(psess)}
        print(f"      only {len(psess)} sessions yield pairs — the placebo is ABSENT, and by rule 31 the "
              "primary is reported WITHOUT it rather than as though it had passed")
        pp = float("nan")
        pobs = float("nan")
    else:
        pobs, pp, _, _ = flip_null(psess, PRIMARY, np.random.default_rng(SEED + 21))
        res["placebo"] = {"mean": float(pobs), "p": float(pp), "n_sessions": len(psess)}
        print(f"      {PRIMARY}: {pobs:.4f}, p = {pp:.4f}")

    prim = table[PRIMARY]
    if floor is None:
        v, why = "NO-POWER", (f"no injected within-pair effect up to rho = {max(RUNGS):.2f} is detectable; "
                              "every candidate null here is ABSENT, not negative")
    elif not (np.isfinite(prim["p"]) and prim["p"] <= ALPHA):
        v, why = "ABSENT-ABOVE-FLOOR", f"the primary is null with nothing above rho = {floor:.2f}"
    elif (np.isfinite(pp) and pp <= ALPHA
          and abs(pobs - 0.5) >= abs(prim["mean"] - 0.5)):
        v, why = "LAGGED", ("the previous trial's outcome is explained at least as well, so this is a "
                            "consequence and not a prediction")
    elif np.isfinite(prim["frac_same_side"]) and prim["frac_same_side"] < 0.5:
        v, why = "NOT-CLAIMED", "fewer than half the sessions fall on the mean's side of 0.5"
    else:
        d = "MORE pre-cue mu on SUCCESSFUL trials" if prim["mean"] > 0.5 else \
            "LESS pre-cue mu on SUCCESSFUL trials"
        v, why = "PRESENT", (f"{d}; PMID 27199630 reports a single-trial association without a sign and "
                             "Blankertz 2010's between-subject sign is positive, so agreement is stated "
                             "rather than predicted")
    res["verdict"], res["why"] = v, why
    print(f"\n   VERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
