#!/usr/bin/env python3
"""E183 — the MOAA/S label placebo that E180's own outcome specifies, plus the one it could not build.

REGISTERED BEFORE ANY DRAW FROM EITHER NEW PLACEBO HAS BEEN SCORED.

=========================================================================================================
WHAT E180 SETTLED AND WHAT IT COULD NOT
=========================================================================================================
E180 gave E150's eleven MOAA/S increments the label placebo they were missing and **eight of eleven
withdrew**, including E150's largest EEG adder `relative_alpha_power` (fraction 0.1900) and
`whole_head_exponent` (0.1650). Three survived and are not muscle: `multiscale_entropy_slope` (0.0000),
`bis_rbr` (0.0250), `wpli_theta` (0.0150).

**But E180's GATE 4 failed and the direction of the failure makes those three survivors weak, not strong.**
Not one of 200 circular shifts in 3,000 attempts landed within 0.03 of the real baseline: the PE31 + SEF95
incumbent's out-of-fold rho falls from **+0.3987 under the real MOAA/S to +0.0324 under a shifted one**. A
shifted label is essentially unpredictable, every model's error sits at its ceiling, and an added column
has nothing to exploit — so **an unmatched placebo that does NOT fire is too lenient**, which is the
direction here. E180 recorded that and did not adjust its verdict (rule 58).

E180's own recorded successor is this file, and it was written down before this file existed: *"a placebo
that preserves the trajectory and breaks only the moment-to-moment link would shift by a SMALL lag just
past the half-life, or swap MOAA/S series between recordings matched on trajectory shape."*

=========================================================================================================
TWO ARMS, BOTH DECLARED HERE, TESTING TWO DIFFERENT ALTERNATIVES
=========================================================================================================
    ARM S — SMALL-LAG SHIFT. The lag is drawn uniformly on **[halflife, LAG_MULT x halflife]** instead of
        E180's [halflife, n - halflife]. E180's lag distribution was dominated by shifts of a hundred
        windows or more, which destroy the slow sedation trajectory along with the fine alignment. A lag
        just past the autocorrelation half-life keeps the trajectory and breaks the correspondence, so the
        incumbent should stay predictive and GATE 4 should become fillable. **The change is to the lag
        DISTRIBUTION and to nothing else** — the rejection band, the statistic, the cohort, the candidate
        list and the 0.05 bar are E180's, unchanged.
        *Alternative under test:* the increment is about this window's depth rather than about where in
        the recording we are.

    ARM T — TRAJECTORY SWAP. Each recording's MOAA/S series is replaced by **another recording's series**,
        resampled to the same length, chosen among recordings whose own trajectory correlates with it above
        `TRAJ_MIN`. That preserves the marginal distribution AND a realistic sedation trajectory but
        destroys the patient-specific correspondence entirely.
        *Alternative under test:* the increment is about THIS patient's depth rather than about the typical
        shape of a sedation procedure.

The two arms can disagree, and if they do that is the finding rather than a problem: a candidate that
survives S and fails T tracks the generic trajectory; one that survives both tracks this patient at this
moment.

=========================================================================================================
GATES
=========================================================================================================
G1  REBUILD against E150's own stored cohort size, loaded from its JSON rather than transcribed (rule 59).
G2  THE INCUMBENT IS ALIVE under the real label.
G3  THE HALF-LIFE IS MEASURED, as in E180, and the small-lag range is set from it.
G4  **THE MATCH MUST NOW SUCCEED, AND IF IT DOES NOT THAT IS THE RESULT.** At least `MIN_MATCHED` draws
    per arm must land within `BASE_TOL` of the real baseline. **If arm S still cannot be matched, then no
    time shift of any size preserves MOAA/S's predictability**, which means the label's predictability
    lives entirely in the fine alignment — a real finding about the deposit, reported as a limitation of
    every placebo of this family and NOT as a pass for any candidate.
G5  **THE PLACEBO MUST STILL BE A DESTRUCTION.** A small lag that changes nothing would make every
    candidate withdraw trivially. So the correlation between the real and shifted label is measured and
    printed; if it exceeds `MAX_LABEL_CORR` the shift is not a destruction and the arm is void. This is
    the rule-55 check: confirm the placebo alters what it claims to alter, in the units that matter.

=========================================================================================================
VERDICT, PER CANDIDATE — THE WITHDRAWING AND UNINFORMATIVE CASES FIRST (rules 31, 34, 37, 78)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G5 fails on that arm.
  (2) NOT MATCHABLE       G4 fails on that arm; no verdict from it, and the limitation is stated.
  (3) WITHDRAWN           the placebo reaches the real increment in more than 5 % of draws.
  (4) TRAJECTORY-ONLY     survives arm S and fails arm T: the increment tracks the generic shape of a
                          sedation procedure, not this patient.
  (5) SURVIVES BOTH       the increment exceeds both placebo distributions. **Only then is E150's entry
                          for that candidate supported**, and only then does Challenge C have a live
                          incremental result on DOSE-I.

**REGISTERED PREDICTION: (3) or (4) for all three of E180's survivors.** E180's placebo was too lenient by
its own measurement, so a harder one should cull rather than confirm; and MOAA/S's trajectory through a
procedural sedation is stereotyped, so arm T is the harder of the two. **The prediction is against the
last live Challenge C claim this project has**, which is the correct way round.

    python bsde/src/bsde/experiments/e183_moaas_matched_label_placebo.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import grouped_cv_predict, permutation_increment, spearman  # noqa: E402
import e84_increment_over_validated_incumbent as E84                                 # noqa: E402
from e150_challenge_c_negatives_rederived import build                               # noqa: E402
from e180_moaas_label_placebo import (E150_ADDS, MUSCLE, autocorr_halflife,          # noqa: E402
                                      baseline_perf)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
E150_JSON = os.path.join(RESULTS, "e150_challenge_c_rederived.json")
OUT = os.path.join(RESULTS, "e183_moaas_matched_label_placebo.json")
SEED = 20260801

LAG_MULT = 4              # arm S draws the lag from [halflife, LAG_MULT * halflife]
TRAJ_MIN = 0.30           # arm T donates only from recordings whose trajectory correlates above this
BASE_TOL = 0.03           # E180's band, unchanged
MAX_LABEL_CORR = 0.90     # G5: a shift that leaves the label this similar is not a destruction
MIN_MATCHED = 50
N_DRAWS = 200
MAX_TRIES = 6000
PERMS = 300
ALPHA = 0.05

try:
    _e150 = json.load(open(E150_JSON))
    N_RECORDINGS, N_WINDOWS = int(_e150["n_recordings"]), int(_e150["n_windows"])
except Exception:                                                              # noqa: BLE001
    N_RECORDINGS, N_WINDOWS = -1, -1


def small_shift(y, subj, hl, rng):
    out = np.empty_like(y)
    for u in np.unique(subj):
        m = subj == u
        v = y[m]
        n = v.size
        hi = min(LAG_MULT * hl, max(hl + 1, n - hl))
        if n <= 2 * hl + 2 or hi <= hl:
            out[m] = v
            continue
        out[m] = np.roll(v, int(rng.integers(hl, hi)))
    return out


def traj_swap(y, subj, donors, rng):
    """Replace each recording's MOAA/S with a trajectory-matched donor's, resampled to the same length."""
    out = np.empty_like(y)
    for u in np.unique(subj):
        m = subj == u
        v = y[m]
        pool = donors.get(u, [])
        if not pool:
            out[m] = v
            continue
        d = pool[int(rng.integers(0, len(pool)))]
        src = y[subj == d]
        idx = np.clip((np.linspace(0, 1, v.size) * (src.size - 1)).round().astype(int), 0, src.size - 1)
        out[m] = src[idx]
    return out


def build_donors(y, subj):
    """For each recording, the recordings whose length-normalised trajectory correlates above TRAJ_MIN."""
    uniq = list(np.unique(subj))
    norm = {}
    for u in uniq:
        v = y[subj == u]
        idx = np.clip((np.linspace(0, 1, 50) * (v.size - 1)).round().astype(int), 0, v.size - 1)
        norm[u] = v[idx]
    donors = {}
    for u in uniq:
        ds = []
        for d in uniq:
            if d == u:
                continue
            r = spearman(list(norm[u]), list(norm[d]))
            if np.isfinite(r) and r >= TRAJ_MIN:
                ds.append(d)
        donors[u] = ds
    return donors


def make_pool(kind, y, subj, base, real_base, hl, donors, rng):
    pool, tries, kept_base, kept_corr = [], 0, [], []
    while len(pool) < N_DRAWS and tries < MAX_TRIES:
        tries += 1
        ys = small_shift(y, subj, hl, rng) if kind == "S" else traj_swap(y, subj, donors, rng)
        if len(np.unique(ys)) < 2:
            continue
        c = spearman(list(y), list(ys))
        b = baseline_perf(base, ys, subj, SEED + 3000 + tries)
        if not np.isfinite(b):
            continue
        if abs(b - real_base) > BASE_TOL:
            continue
        pool.append(ys)
        kept_base.append(b)
        kept_corr.append(c if np.isfinite(c) else 0.0)
    return pool, tries, kept_base, kept_corr


def run_arm(kind, name, y, subj, base, cand, real_base, hl, donors):
    rng = np.random.default_rng(SEED + (1 if kind == "S" else 2))
    pool, tries, kb, kc = make_pool(kind, y, subj, base, real_base, hl, donors, rng)
    out = {"arm": kind, "name": name, "n_draws": len(pool), "n_tries": int(tries),
           "real_baseline": real_base,
           "pool_baseline_mean": float(np.mean(kb)) if kb else float("nan"),
           "label_corr_mean": float(np.mean(kc)) if kc else float("nan")}
    print(f"\n=== ARM {kind} — {name}")
    print(f"   {len(pool)} matched draws from {tries} attempts; incumbent rho real {real_base:+.4f} vs "
          f"pool {out['pool_baseline_mean']:+.4f}; mean rho(real label, placebo label) "
          f"{out['label_corr_mean']:+.4f}")
    if len(pool) < MIN_MATCHED:
        out["status"] = "NOT-MATCHABLE"
        print(f"   *** NOT MATCHABLE ({len(pool)} < {MIN_MATCHED}) — no verdict from this arm")
        return out
    if np.isfinite(out["label_corr_mean"]) and out["label_corr_mean"] > MAX_LABEL_CORR:
        out["status"] = "NOT-A-DESTRUCTION"
        print(f"   *** NOT A DESTRUCTION (label correlation {out['label_corr_mean']:.4f} > "
              f"{MAX_LABEL_CORR}) — the placebo barely changes the label (rule 55)")
        return out
    out["status"] = "OK"
    print(f"   {'candidate':<26s} {'real':>10s} {'pool mean':>11s} {'frac>=real':>11s}  verdict")
    tab = {}
    for c in E150_ADDS:
        x = cand.get(c)
        if x is None:
            continue
        ok = np.isfinite(x)
        if ok.sum() < 0.5 * len(y):
            continue
        yy, ss, bb, xx = y[ok], subj[ok], base[ok], x[ok]
        real, p_real, _, _ = permutation_increment(bb, np.c_[bb, xx], yy, ss,
                                                   np.random.default_rng(SEED + 5),
                                                   stat=E84.err, reps=PERMS)
        vals = []
        for i, ys in enumerate(pool):
            pa = grouped_cv_predict(bb, ys[ok], ss, np.random.default_rng(SEED + 7000 + i))
            pb = grouped_cv_predict(np.c_[bb, xx], ys[ok], ss, np.random.default_rng(SEED + 7000 + i))
            m2 = np.isfinite(pa) & np.isfinite(pb)
            if m2.sum() < 100:
                continue
            vals.append(E84.err(ys[ok][m2], pb[m2]) - E84.err(ys[ok][m2], pa[m2]))
        v = np.asarray([q for q in vals if np.isfinite(q)])
        frac = float((v <= real).mean()) if v.size >= 30 else float("nan")
        fires = bool(np.isfinite(frac) and frac > ALPHA)
        tab[c] = {"real": float(real), "p_real": float(p_real),
                  "pool_mean": float(v.mean()) if v.size else float("nan"),
                  "fraction_at_or_below_real": frac, "n": int(v.size),
                  "muscle": c in MUSCLE, "withdrawn": fires}
        print(f"   {c:<26s} {real:>+10.5f} {tab[c]['pool_mean']:>+11.5f} {frac:>11.4f}  "
              f"{'WITHDRAWN' if fires else 'survives'}" + ("   MUSCLE" if c in MUSCLE else ""))
    out["table"] = tab
    return out


def main() -> int:
    print("E183 — the matched MOAA/S label placebo, and a trajectory-swap placebo beside it")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E183", "n_recordings": int(n_rec), "n_windows": int(len(y)),
           "lag_mult": LAG_MULT, "traj_min": TRAJ_MIN, "base_tol": BASE_TOL}
    g1 = (n_rec == N_RECORDINGS) and (len(y) == N_WINDOWS)
    print(f"G1 REBUILD  {n_rec} recordings, {len(y)} windows vs E150's stored {N_RECORDINGS} / "
          f"{N_WINDOWS}   {'PASS' if g1 else '*** FAIL'}")
    res["G1_pass"] = bool(g1)
    if not g1:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    real_base = baseline_perf(base, y, subj, SEED)
    res["G2_baseline_rho"] = real_base
    res["G2_pass"] = bool(np.isfinite(real_base) and real_base > 0.1)
    print(f"G2 INCUMBENT ALIVE  PE31+SEF95 out-of-fold rho = {real_base:+.4f}   "
          f"{'PASS' if res['G2_pass'] else '*** FAIL'}")
    hl, n_hl = autocorr_halflife(y, subj)
    res["G3"] = {"halflife": hl, "n": n_hl, "lag_range": [hl, LAG_MULT * hl], "pass": bool(hl > 0)}
    print(f"G3 HALF-LIFE  {hl} windows over {n_hl} recordings; arm S draws lags from "
          f"[{hl}, {LAG_MULT * hl}]")
    if not (res["G2_pass"] and hl > 0):
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    donors = build_donors(y, subj)
    n_don = float(np.mean([len(v) for v in donors.values()]))
    res["donors_per_recording"] = n_don
    print(f"   arm T donor pool: {n_don:.1f} trajectory-matched donors per recording "
          f"(rho >= {TRAJ_MIN})")

    res["arm_S"] = run_arm("S", f"small-lag shift, lags in [{hl}, {LAG_MULT * hl}]",
                           y, subj, base, cand, real_base, hl, donors)
    res["arm_T"] = run_arm("T", "trajectory swap between matched recordings",
                           y, subj, base, cand, real_base, hl, donors)

    S, T = res["arm_S"], res["arm_T"]
    verdicts = {}
    for c in E150_ADDS:
        s_ok = S.get("status") == "OK" and c in S.get("table", {}) and not S["table"][c]["withdrawn"]
        t_ok = T.get("status") == "OK" and c in T.get("table", {}) and not T["table"][c]["withdrawn"]
        if S.get("status") != "OK" and T.get("status") != "OK":
            verdicts[c] = "NO-VERDICT"
        elif S.get("status") == "OK" and not s_ok:
            verdicts[c] = "WITHDRAWN"
        elif T.get("status") == "OK" and not t_ok:
            verdicts[c] = "TRAJECTORY-ONLY" if s_ok else "WITHDRAWN"
        else:
            verdicts[c] = "SURVIVES-BOTH"
    res["per_candidate"] = verdicts
    both = [c for c, v in verdicts.items() if v == "SURVIVES-BOTH"]
    both_nm = [c for c in both if c not in MUSCLE]
    res["survives_both"], res["survives_both_non_muscle"] = both, both_nm
    print(f"\n{'candidate':<26s} verdict")
    for c, v in verdicts.items():
        print(f"{c:<26s} {v}" + ("   MUSCLE" if c in MUSCLE else ""))

    if S.get("status") != "OK" and T.get("status") != "OK":
        res["verdict"] = "NOT-MATCHABLE"
        res["why"] = ("neither placebo could be built to match the incumbent's predictability. With "
                      "E180's large-lag failure that means NO time shift and NO trajectory swap preserves "
                      "MOAA/S's predictability -- its predictability lives entirely in the fine alignment. "
                      "That is a finding about the deposit and it is NOT a pass for any candidate")
    elif not both_nm:
        res["verdict"] = "WITHDRAWN"
        res["why"] = (f"no non-muscle candidate survives both placebos (survives both: {both or 'none'}). "
                      "E150's eleven do not survive a label placebo that keeps the incumbent predictive, "
                      "and Challenge C has no live incremental result on DOSE-I")
    else:
        res["verdict"] = "SURVIVES"
        res["why"] = (f"{both_nm} survive both a small-lag shift and a trajectory swap while the incumbent "
                      "stays predictive under each. This is the first Challenge C increment in the ledger "
                      "with a label placebo behind it")
    print(f"\nVERDICT {res['verdict']} — {res['why']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
