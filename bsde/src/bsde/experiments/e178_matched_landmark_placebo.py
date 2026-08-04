#!/usr/bin/env python3
"""E178 — the landmark placebo, matched on the two things E170's was not.

REGISTERED BEFORE ANY MATCHED PLACEBO DRAW HAS BEEN SCORED.

=========================================================================================================
WHY, AND WHAT THIS FILE IS NOT ALLOWED TO DO
=========================================================================================================
**E170's verdict is final and is not re-opened here.** Its placebo fired — 200 fake landmarks gave a mean
increment of -0.04844 against the real -0.02180, with 0.8300 reaching or beating it — and e34's overturn is
withdrawn. A gate is not re-tuned after it fires (rule 58). Nothing in this file can restore e34's claim.

What this file exists for is that **the same placebo was never run on e37 at all**, and that E170's own
placebo was measured afterwards to be UNMATCHED in two ways that make it harder than the real test:

    baseline SEF95 out-of-fold AUC, REAL label : 0.6088    base rate 0.312
    baseline SEF95 out-of-fold AUC, FAKE labels: 0.4652    base rate 0.097

An added column has more room to help when the baseline is weaker and the positive class rarer, and
neither has anything to do with where the landmark sits. So the honest question — for e37, which has no
verdict yet, and descriptively for e34, which has one — is what a placebo says when those two are held
fixed.

**The asymmetry is deliberate and is written here so it cannot be quietly dropped:** a matched placebo can
only REFUSE e37, never rescue e34. e34 is reported in this file as a descriptive re-measurement whose
verdict was already recorded, and its row in the ledger does not change whatever this returns.

=========================================================================================================
THE MATCHED PLACEBO
=========================================================================================================
Fake landmarks are drawn exactly as E34 and E170 drew them — one per recording, at a relative position
uniform on [0.2, 0.9], with the `HORIZON_S` seconds before it labelled positive — and then **kept only if
both of the following fall inside a band around the real label's values**:

    base rate                     within +-0.05 of the real label's
    incumbent out-of-fold AUC     within +-0.03 of the real label's

Both bands are set from what the machinery can achieve rather than from habit (rule 63): the fake labels'
own baseline AUC has an sd of 0.0188 across draws, so +-0.03 is about 1.6 sd and is the tightest band that
can be filled at a workable acceptance rate; +-0.05 on a base rate of ~0.31 is ~16 % relative.

**GATE M — THE MATCH MUST BE ACHIEVABLE, AND IF IT IS NOT THAT IS THE RESULT.** At least `MIN_MATCHED`
accepted draws are required from `MAX_TRIES` attempts. If the band cannot be filled, the file reports
**NOT MATCHABLE** and says what that means: *no arbitrary landmark in these recordings reproduces the real
landmark's baseline predictability*. That is evidence about the landmark and it is **not** a pass for the
candidate — it is a limitation of the placebo, and it is written down here in advance so it cannot be read
the other way later.

=========================================================================================================
ARMS
=========================================================================================================
    A  **e37, unmatched** — the like-for-like test e37 has never had, identical to the one e34 failed.
       `ar1_sef95` over `SEF95`, 70 recordings, 60 s horizon. This arm alone decides e37.
    B  **e37, matched** — the same, with the rejection-sampled placebo.
    C  **e34, matched** — descriptive only. e34's verdict is recorded and does not move.

Every arm reports the real increment, the placebo distribution, the fraction of placebo draws at or below
the real increment, and the baseline AUC and base rate actually achieved.

=========================================================================================================
VERDICT FOR e37 — THE WITHDRAWING CASES FIRST (rules 31, 34, 37)
=========================================================================================================
  (1) NOT MATCHABLE       GATE M fails on arm B. Then arm A alone decides, and if arm A also withdraws,
                          e37 is withdrawn; if arm A survives, e37 is reported as SURVIVES-UNMATCHED-ONLY,
                          which is weaker than a pass and says so.
  (2) WITHDRAWN           arm A fires (fraction at or below the real increment > 0.05). e37's overturn is
                          withdrawn exactly as e34's was, and the two DOSE-I landmark rows fall together.
  (3) WITHDRAWN-MATCHED   arm A survives but arm B fires. The unmatched placebo was too lenient rather
                          than too harsh — the opposite of E170's diagnosis, and it would mean the
                          diagnosis was wrong.
  (4) SURVIVES            arm A and arm B both fail to reproduce the real increment. e37's overturn stands
                          with a matched placebo behind it, and it becomes the only surviving Challenge C
                          landmark result in this ledger.

REGISTERED PREDICTION: **(2) WITHDRAWN.** e37 is the same deposit, the same horizon, the same landmark
construction and a subset of the same recordings as e34, and its increment (-0.00737) is a third the size
of the one that just died (-0.02147). Predicting otherwise would be predicting that a smaller effect
survives a test a larger one failed.

    python bsde/src/bsde/experiments/e178_matched_landmark_placebo.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import auc, grouped_cv_predict                        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "e178_matched_landmark_placebo.json")
SEED = 20260801

BASE_RATE_TOL = 0.05
BASE_AUC_TOL = 0.03
MIN_MATCHED = 50
MAX_TRIES = 4000
UNMATCHED_DRAWS = 200
ALPHA = 0.05


def neg_auc(t, p):
    a = auc(np.asarray(t, int), np.asarray(p, float))
    return -a if np.isfinite(a) else float("nan")


def build(which):
    if which == "e34":
        from e34_challenge_c_dosei_allwindows import _load, _stack, INCUMBENT, PRIMARY, HORIZON_S
        recs = _load(ZIP)
        xi, y, grp, _ = _stack(recs, INCUMBENT)
        xp, _, _, _ = _stack(recs, PRIMARY)
    else:
        from e37_challenge_c_critical_slowing import _load, _stack, INCUMBENT, PRIMARY, HORIZON_S
        recs, _ = _load(ZIP)
        xi, y, grp = _stack(recs, INCUMBENT)
        xp, _, _ = _stack(recs, PRIMARY)
    m = np.isfinite(xi) & np.isfinite(xp) & np.isfinite(y)
    return recs, xi[m], xp[m], y[m], grp[m], HORIZON_S, INCUMBENT, PRIMARY, m


def _n_blocks(v):
    """How many separate positive runs the real label has in this recording."""
    v = np.asarray(v, float) > 0.5
    return int(np.sum(v[1:] & ~v[:-1]) + (1 if v.size and v[0] else 0))


def fake_label(recs, horizon, rng, mask, match_count=False):
    """One fake landmark per recording (E34's and E170's construction), or `match_count` of them.

    **WHY `match_count` EXISTS, AND IT IS ARITHMETIC RATHER THAN A REACTION TO A RESULT.** A single fake
    landmark labels `horizon` samples positive out of a recording's ~550 conscious windows, so its base
    rate is structurally ~0.11. E37's real label -- "time to the NEXT loss <= 60 s", which a recording with
    several losses satisfies several times -- has a base rate of 0.217. **A one-landmark placebo therefore
    CANNOT reach the real base rate, and the matched arm was unbuildable as first written**, before any
    draw was scored and independent of what the numbers turned out to be. Placing as many fake landmarks
    as the recording has real transitions matches the base rate by construction and is the more faithful
    destruction anyway: it preserves how many transitions there are and destroys only where they sit.

    ARM A IS NOT AFFECTED. It keeps the single-landmark construction, because it is the like-for-like test
    e34 failed and that comparison is the one that decides e37.
    """
    out = []
    for r in recs:
        n = len(r["y"])
        fy = np.zeros(n)
        k = max(1, _n_blocks(r["y"])) if match_count else 1
        for _ in range(k):
            cut = int(n * float(rng.uniform(0.2, 0.9)))
            fy[max(0, cut - horizon):cut] = 1.0
        out.append(fy)
    return np.concatenate(out)[mask]


def increment_and_base(xi, xp, target, grp, seed):
    """Returns (increment in the lower-is-better convention, baseline AUC, base rate)."""
    Xa, Xb = xi.reshape(-1, 1), np.column_stack([xi, xp])
    g = np.random.default_rng(seed)
    pa = grouped_cv_predict(Xa, target, grp, g)
    pb = grouped_cv_predict(Xb, target, grp, np.random.default_rng(seed))
    ok = np.isfinite(pa) & np.isfinite(pb)
    if ok.sum() < 100 or len(np.unique(target[ok])) < 2:
        return float("nan"), float("nan"), float(np.mean(target))
    base = float(auc(target[ok].astype(int), pa[ok]))
    return float(neg_auc(target[ok], pb[ok]) - neg_auc(target[ok], pa[ok])), base, float(target[ok].mean())


def run_arm(name, which, matched):
    recs, xi, xp, y, grp, horizon, inc_name, pri_name, mask = build(which)
    real_inc, real_base, real_rate = increment_and_base(xi, xp, y, grp, SEED + 1)
    print(f"\n{'=' * 100}\n{name}  ({which}, {len(recs)} recordings, {len(y)} windows, "
          f"{pri_name} over {inc_name})")
    print(f"   real increment {real_inc:+.5f}   baseline AUC {real_base:.4f}   base rate {real_rate:.3f}")
    rng = np.random.default_rng(SEED + 2)
    draws, tries, kept_base, kept_rate = [], 0, [], []
    target_n = MIN_MATCHED if matched else UNMATCHED_DRAWS
    cap = MAX_TRIES if matched else UNMATCHED_DRAWS
    while len(draws) < target_n and tries < cap:
        tries += 1
        fy = fake_label(recs, horizon, rng, mask, match_count=matched)
        if len(np.unique(fy)) < 2:
            continue
        # base rate is free to compute; screening on it BEFORE the cross-fit is pure efficiency and
        # changes no threshold
        if matched and abs(float(fy.mean()) - real_rate) > BASE_RATE_TOL:
            continue
        inc, base, rate = increment_and_base(xi, xp, fy, grp, SEED + 3000 + tries)
        if not np.isfinite(inc):
            continue
        if matched and (abs(rate - real_rate) > BASE_RATE_TOL or abs(base - real_base) > BASE_AUC_TOL):
            continue
        draws.append(inc)
        kept_base.append(base)
        kept_rate.append(rate)
    d = np.asarray(draws)
    out = {"which": which, "matched": bool(matched), "real_increment": real_inc,
           "real_baseline_auc": real_base, "real_base_rate": real_rate,
           "n_draws": int(d.size), "n_tries": int(tries)}
    if d.size < (MIN_MATCHED if matched else 30):
        out["status"] = "NOT-MATCHABLE" if matched else "TOO-FEW-DRAWS"
        print(f"   *** {out['status']}: {d.size} usable draws from {tries} attempts")
        return out
    frac = float((d <= real_inc).mean())
    out.update({"placebo_mean": float(d.mean()), "placebo_p05": float(np.quantile(d, 0.05)),
                "fraction_at_or_below_real": frac,
                "placebo_baseline_auc_mean": float(np.mean(kept_base)),
                "placebo_base_rate_mean": float(np.mean(kept_rate)),
                "fires": bool(frac > ALPHA), "status": "OK"})
    print(f"   placebo: {d.size} draws from {tries} attempts, mean {d.mean():+.5f}, "
          f"5th pct {np.quantile(d, 0.05):+.5f}")
    print(f"            achieved baseline AUC {np.mean(kept_base):.4f} (real {real_base:.4f}), "
          f"base rate {np.mean(kept_rate):.3f} (real {real_rate:.3f})")
    print(f"   fraction of placebo draws at or below the real increment: {frac:.4f}   "
          f"{'*** PLACEBO FIRES' if frac > ALPHA else 'placebo does not reproduce it'}")
    return out


def main() -> int:
    print("E178 — the landmark placebo, matched on baseline headroom and base rate")
    print("   e34's verdict is RECORDED and is not re-opened; arm C is descriptive only.")
    if not os.path.exists(ZIP):
        print(f"ABSENT: {ZIP}")
        return 2
    res = {"experiment": "E178", "base_rate_tol": BASE_RATE_TOL, "base_auc_tol": BASE_AUC_TOL,
           "arms": {}}
    res["arms"]["A_e37_unmatched"] = run_arm("ARM A — e37, UNMATCHED (decides e37)", "e37", False)
    res["arms"]["B_e37_matched"] = run_arm("ARM B — e37, MATCHED", "e37", True)
    res["arms"]["C_e34_matched"] = run_arm("ARM C — e34, MATCHED (descriptive; verdict already recorded)",
                                           "e34", True)

    A, B = res["arms"]["A_e37_unmatched"], res["arms"]["B_e37_matched"]
    if A.get("status") != "OK":
        v, why = "NOT-INTERPRETABLE", "arm A could not be computed"
    elif B.get("status") == "NOT-MATCHABLE":
        if A["fires"]:
            v, why = "WITHDRAWN", ("the unmatched placebo fires and no matched placebo can be built, so "
                                   "e37 falls with e34; and the failure to match is itself a statement "
                                   "that no arbitrary landmark reproduces the real one's baseline")
        else:
            v, why = "SURVIVES-UNMATCHED-ONLY", ("the unmatched placebo does not reproduce the real "
                                                 "increment, but the band could not be filled, so this is "
                                                 "weaker than a pass and must be described as such")
    elif A["fires"]:
        v, why = "WITHDRAWN", (f"{A['fraction_at_or_below_real']:.4f} of unmatched fake landmarks reach "
                               "the real increment; e37's overturn is withdrawn exactly as e34's was")
    elif B["fires"]:
        v, why = "WITHDRAWN-MATCHED", (f"the unmatched placebo did not fire but the MATCHED one does "
                                       f"({B['fraction_at_or_below_real']:.4f}), so the unmatched placebo "
                                       "was too lenient rather than too harsh -- the opposite of E170's "
                                       "diagnosis, which would then be wrong")
    else:
        v, why = "SURVIVES", ("neither the unmatched nor the matched placebo reproduces the real "
                              "increment; e37's overturn stands with a matched placebo behind it")
    res["verdict_e37"], res["why"] = v, why
    print(f"\n{'=' * 100}\nVERDICT for e37: {v} — {why}")
    C = res["arms"]["C_e34_matched"]
    if C.get("status") == "OK":
        print(f"\nARM C, descriptive: e34's matched placebo puts {C['fraction_at_or_below_real']:.4f} of "
              f"draws at or below the real increment "
              f"({'still fires' if C['fires'] else 'does NOT fire'}). "
              "E170's recorded verdict does not change either way (rule 58).")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
