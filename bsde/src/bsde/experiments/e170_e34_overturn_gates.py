#!/usr/bin/env python3
"""E170 — E34's overturn, with the gates that decided it re-derived by the same calibrated test.

REGISTERED BEFORE ANY CANDIDATE OTHER THAN E34'S OWN PRIMARY HAS BEEN RE-SCORED.

=========================================================================================================
WHY THIS EXISTS, AND WHY IT IS NOT OPTIONAL
=========================================================================================================
E166 re-derived e34 with `permutation_increment` and the verdict MOVED. On e34's own cohort, rebuilt to
the row (79,429 windows, 129 recordings, GATE R exact), `PE31` added to `SEF95` for predicting loss of
consciousness within 60 s at an increment of **-0.02147 with p = 0.0000** against a 500-draw
recording-level permutation null, with a measured detection floor of rho = 0.05 and a rho = 0 calibration
rung that did not fire. The recorded verdict was **PLAIN NULL** (+0.0178 [-0.0226, +0.0474] in the
old estimator's POSITIVE-adds convention).

**An overturned primary whose gates were computed by the SAME blind instrument is half a result.** E34's
placebo (+0.0244 [-0.0440, +0.0935]) and its whole candidate table came from `oob_auc_increment`, whose
tail fraction E146 measured detecting in 0 % of draws where a proper test detected in 88 %. So the placebo
that would have withdrawn the primary is exactly as blind as the primary was, and it cannot be used to
certify an overturn it was never able to see.

Three things are re-derived here, all with the calibrated test, and each of them can kill the overturn:

  **(1) THE PLACEBO, AS A DISTRIBUTION.** E34 drew ONE fake landmark per recording and compared a single
  placebo increment against the real one. A placebo comparison is against the placebo's DISTRIBUTION, not
  a single draw or its mean — this project has now made that error five times (rule 37's fifth entry). So
  `N_FAKE` independent fake-landmark label sets are drawn, each at a matched relative position, each
  scored by the identical increment, and the real increment is placed in that distribution.

  **(2) THE MUSCLE COMPARATOR, AND IT IS THE MOST LIKELY WAY THIS DIES.** E34's own record says: *"Muscle
  unexcludable: rel_gamma 0.632 > primary 0.623 and no muscle channel exists."* DOSE-I has no EMG channel,
  so the only available control is whether a broadly muscle-sensitive band beats the candidate at the same
  task. `rel_gamma` is scored by the identical statistic and **the claim is refused if its increment is at
  least as large as `PE31`'s.** Written here, before the number is known.

  **(3) THE WHOLE CANDIDATE TABLE.** All fifteen of E34's `REPORT` features, BH at q = 0.05, because a
  single cell of fifteen is exactly the look E34's own multiplicity note exists to refuse.

=========================================================================================================
WHAT IS NOT RE-OPENED
=========================================================================================================
The cohort, the horizon, the grid, the incumbent and the label are E34's, unchanged, and GATE R requires
the rebuild to reproduce 129 recordings before anything is scored. This is a re-derivation of E34's gates
with a better test, not a new experiment on a chosen cohort — nothing here is free to move in response to
a result (rule 58).

=========================================================================================================
GATES
=========================================================================================================
G1  REBUILD: 129 recordings, or nothing is reported (rule 31).
G2  BASELINE ALIVE: SEF95 alone must beat its own cluster-permutation null. E166 measured -0.2123 for the
    E37 sub-cohort and -0.1404 here; it is re-checked rather than carried across (rule 59).
G3  CALIBRATION: a rho = 0 synthetic column must NOT be detected, and a ladder must detect SOMETHING, so
    that a null in the table is readable as measured-absent rather than as no power. Either half can fail.

=========================================================================================================
VERDICT — WRONG-DIRECTION AND WITHDRAWAL CASES FIRST (rules 34, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, or either half of G3, fails.
  (2) WITHDRAWN-BY-PLACEBO  the real `PE31` increment sits inside the fake-landmark distribution
                          (one-sided fraction > 0.05). The overturn is an artefact of the label's shape,
                          not of the transition, and E34's recorded null stands.
  (3) MUSCLE              `rel_gamma`'s increment is at least as large as `PE31`'s. DOSE-I cannot separate
                          a muscle explanation from a cortical one, and the claim is refused.
  (4) HURTS               the increment is positive with p >= 0.95 — the addition makes the model worse.
  (5) CONFIRMED           `PE31` survives the placebo distribution, exceeds `rel_gamma`, and clears BH.
                          Then E34's ledger row is corrected from `negative` to `positive` and this
                          becomes the project's first surviving Challenge C increment.

REGISTERED EXPECTATION: I do not have one that is worth writing down as a prediction, and saying so is
more honest than inventing one. The placebo and the muscle comparator are both live, E34's own single-draw
placebo was numerically LARGER than its primary, and a 60 s horizon on a 1 Hz grid gives the fake landmark
a great deal of room. **What I will not do is treat a survival as confirmation and a failure as a reason
to look again** — whichever of (2), (3), (5) comes out is the result.

    python bsde/src/bsde/experiments/e170_e34_overturn_gates.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import auc, permutation_increment, screen_candidates   # noqa: E402
from e34_challenge_c_dosei_allwindows import (HORIZON_S, INCUMBENT, PRIMARY,    # noqa: E402
                                              REPORT, _load, _stack)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "e170_e34_overturn_gates.json")
SEED = 20260801

MUSCLE = "rel_gamma"
N_RECORDINGS = 129
N_FAKE = 200
REPS = 500
RUNGS = (0.02, 0.05, 0.10, 0.20)
ALPHA = 0.05
Q = 0.05


def neg_auc(t, p):
    a = auc(np.asarray(t, int), np.asarray(p, float))
    return -a if np.isfinite(a) else float("nan")


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


def fake_labels(recs, rng):
    """One fake landmark per recording at a matched relative position -- E34's own construction."""
    out = []
    for r in recs:
        n = len(r["y"])
        cut = int(n * float(rng.uniform(0.2, 0.9)))
        fy = np.zeros(n)
        fy[max(0, cut - HORIZON_S):cut] = 1.0
        out.append(fy)
    return np.concatenate(out)


def main() -> int:
    print("E170 — E34's overturn, with its gates re-derived by the calibrated test")
    if not os.path.exists(ZIP):
        print(f"ABSENT: {ZIP}")
        return 2
    recs = _load(ZIP)
    xi, y, grp, _ = _stack(recs, INCUMBENT)
    res = {"experiment": "E170", "n_recordings": len(recs), "n_rows": int(len(y)),
           "horizon_s": HORIZON_S, "incumbent": INCUMBENT}
    g1 = len(recs) == N_RECORDINGS
    print(f"G1 REBUILD  {len(recs)} recordings, {len(y)} windows, base rate {y.mean():.1%}   "
          f"{'PASS' if g1 else '*** FAIL (expected %d)' % N_RECORDINGS}")
    res["G1_pass"] = bool(g1)
    if not g1:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    cols = {c: _stack(recs, c)[0] for c in REPORT}
    usable, dropped = screen_candidates(cols)
    for c, why in dropped.items():
        print(f"   dropped: {c} ({why})")
    names = [c for c in REPORT if c in usable and c != INCUMBENT]
    base = np.isfinite(xi) & np.isfinite(y)

    def arm(x, yy=None, reps=REPS, seed=SEED + 1):
        m = base & np.isfinite(x)
        Xa = xi[m].reshape(-1, 1)
        Xb = np.column_stack([xi[m], x[m]])
        target = (y if yy is None else yy)[m]
        return permutation_increment(Xa, Xb, target, grp[m], np.random.default_rng(seed),
                                     stat=neg_auc, reps=reps)

    # G2 -- baseline alive
    n = int(base.sum())
    o, p, nm, k = permutation_increment(np.zeros((n, 1)), xi[base].reshape(-1, 1), y[base], grp[base],
                                        np.random.default_rng(SEED + 2), stat=neg_auc, reps=200)
    res["G2"] = {"increment": float(o), "p": float(p), "pass": bool(np.isfinite(p) and p <= ALPHA)}
    print(f"G2 BASELINE ALIVE  {INCUMBENT} alone: {o:+.4f}, p = {p:.4f}   "
          f"{'PASS' if res['G2']['pass'] else '*** FAIL'}")

    # G3 -- calibration and floor
    print("G3 CALIBRATION AND FLOOR")
    rng = np.random.default_rng(SEED + 3)
    A = np.column_stack([np.ones(n), xi[base]])
    coef, *_ = np.linalg.lstsq(A, y[base].astype(float), rcond=None)
    r = y[base] - A @ coef
    u = (r - r.mean()) / (r.std() if r.std() > 1e-12 else 1.0)
    floor, ladder = None, []
    for rho in (0.0,) + RUNGS:
        ps = []
        for d in range(3):
            g = np.random.default_rng(SEED + 500 + int(rho * 1000) + d)
            z = rho * u + np.sqrt(max(0.0, 1 - rho ** 2)) * g.normal(size=n)
            full = np.full(len(y), np.nan)
            full[base] = z
            ps.append(arm(full, reps=300, seed=SEED + 900 + d)[1])
        hits = sum(1 for q in ps if np.isfinite(q) and q <= ALPHA)
        ladder.append({"rho": rho, "p": [float(q) for q in ps], "hits": hits})
        print(f"   rho={rho:.2f}  p = " + ", ".join(f"{q:.4f}" for q in ps) + f"   {hits}/3")
        if rho == 0.0 and hits >= 2:
            res.update({"G3_ladder": ladder, "verdict": "NOT-INTERPRETABLE",
                        "why": "the rho = 0 rung fired; the null is anti-conservative here"})
            print("\nVERDICT NOT INTERPRETABLE — the rho = 0 rung fired")
            json.dump(res, open(OUT, "w"), indent=2)
            return 1
        if rho > 0 and hits >= 2 and floor is None:
            floor = rho
            break
    res["G3_ladder"], res["floor"] = ladder, floor
    print(f"   FLOOR: {'none up to %.2f' % max(RUNGS) if floor is None else '%.2f' % floor}")
    if floor is None:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "no injected effect is detectable; nothing in the table can be read either way"
        print("\nVERDICT NOT INTERPRETABLE — no power")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # the candidate table
    print(f"\n{'candidate':<14s} {'increment':>11s} {'p':>8s} {'null mean':>11s}")
    table, ps = {}, []
    for c in names:
        o, p, nm, k = arm(cols[c])
        table[c] = {"increment": float(o), "p": float(p), "null_mean": float(nm), "n_null": int(k)}
        ps.append(p)
        print(f"{c:<14s} {o:>+11.5f} {p:>8.4f} {nm:>+11.5f}"
              + ("   <- PRIMARY" if c == PRIMARY else "")
              + ("   <- MUSCLE COMPARATOR" if c == MUSCLE else ""))
    keep = bh(ps)
    res["table"], res["survivors_bh"] = table, [names[i] for i in sorted(keep)]
    print(f"BH q={Q}: {res['survivors_bh'] or 'none'}")

    # the placebo, as a DISTRIBUTION
    print(f"\nPLACEBO — {N_FAKE} independent fake landmarks at matched relative positions")
    frng = np.random.default_rng(SEED + 4)
    real = table[PRIMARY]["increment"]
    fake_inc = []
    for i in range(N_FAKE):
        fy = fake_labels(recs, frng)
        m = base & np.isfinite(cols[PRIMARY])
        if len(np.unique(fy[m])) < 2:
            continue
        Xa, Xb = xi[m].reshape(-1, 1), np.column_stack([xi[m], cols[PRIMARY][m]])
        # one cross-fit per fake label; no inner null is needed because the FAKE DRAWS are the null
        from bsde.verifier.stats import grouped_cv_predict
        g = np.random.default_rng(SEED + 4000 + i)
        pa = grouped_cv_predict(Xa, fy[m], grp[m], g)
        pb = grouped_cv_predict(Xb, fy[m], grp[m], g)
        ok = np.isfinite(pa) & np.isfinite(pb)
        if ok.sum() < 100 or len(np.unique(fy[m][ok])) < 2:
            continue
        fake_inc.append(neg_auc(fy[m][ok], pb[ok]) - neg_auc(fy[m][ok], pa[ok]))
    fake_inc = np.asarray([v for v in fake_inc if np.isfinite(v)])
    p_placebo = float((fake_inc <= real).mean()) if fake_inc.size else float("nan")
    res["placebo"] = {"real": real, "n_fake": int(fake_inc.size),
                      "fake_mean": float(fake_inc.mean()) if fake_inc.size else float("nan"),
                      "fake_p05": float(np.quantile(fake_inc, 0.05)) if fake_inc.size else float("nan"),
                      "fraction_at_or_below_real": p_placebo}
    print(f"   real {real:+.5f}; fake landmarks: mean {res['placebo']['fake_mean']:+.5f}, "
          f"5th pct {res['placebo']['fake_p05']:+.5f}, {fake_inc.size} draws")
    print(f"   fraction of fake landmarks at or below the real increment: {p_placebo:.4f}")

    # verdict
    muscle = table.get(MUSCLE, {}).get("increment", float("nan"))
    if not (np.isfinite(p_placebo) and p_placebo <= ALPHA):
        v = "WITHDRAWN-BY-PLACEBO"
        why = (f"{p_placebo:.4f} of fake landmarks reach the real increment, so the label's shape rather "
               "than the transition explains it; E34's recorded null stands")
    elif np.isfinite(muscle) and muscle <= real:
        v = "MUSCLE"
        why = (f"{MUSCLE} increments {muscle:+.5f} against the primary's {real:+.5f}, at least as large; "
               "DOSE-I has no muscle channel and cannot separate the explanations, so the claim is refused")
    elif real > 0 and table[PRIMARY]["p"] >= 1 - ALPHA:
        v = "HURTS"
        why = "the addition significantly worsens the model"
    elif PRIMARY not in res["survivors_bh"]:
        v = "NOT-CLAIMED"
        why = f"{PRIMARY} does not clear BH at q = {Q} across the fifteen reported candidates"
    else:
        v = "CONFIRMED"
        why = (f"{PRIMARY} increments {real:+.5f}, survives {fake_inc.size} fake landmarks, exceeds the "
               f"muscle comparator ({muscle:+.5f}) and clears BH; E34's ledger row must be corrected from "
               "negative to positive")
    res["verdict"], res["why"] = v, why
    print(f"\nVERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
