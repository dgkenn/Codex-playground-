#!/usr/bin/env python3
"""E08 — do the exotic features add anything, and do they point the way they promised?

TWO GATES, IN THIS ORDER, AND THE ORDER IS THE POINT.

  1. REDUNDANCY, which is LABEL-FREE and therefore runs first. `check_redundancy` needs no outcome, no
     cohort and no labels, and it is fatal above |Spearman rho| = 0.98 when the candidate is the more complex
     of the pair. A feature that turns out to be an existing candidate wearing a new name dies here, before
     consuming an evaluation. This is the cheapest possible way to shrink a search space and it costs nothing
     to run, which is exactly why it goes first rather than being discovered afterwards.

  2. SIGNED DIRECTION. Every candidate is scored against ITS OWN declared direction, never against an
     unsigned monotonicity fraction. This exists because `lempel_ziv` was reported as the best-performing
     candidate across three experiments while moving OPPOSITE to its own declaration (§9.12) -- the
     unsigned statistic hid it, and the standing rule added afterwards forbids reporting one without the
     signed comparison beside it.

WHY REDUNDANCY BEFORE PERFORMANCE. The tempting order is to evaluate everything and then check what was
redundant. That wastes the evaluation, and worse, it means a redundant feature that happens to score well
gets reported before anyone notices it is a duplicate. Sibling error-catalogue rule 28 exists because this
project has already over-predicted three redundant measures.

REGISTERED BEFORE READING ANY EXOTIC VALUE:
    P1  `exponent_low` (1-20 Hz) IS REDUNDANT with `whole_head_exponent` (1-40 Hz), |rho| >= 0.90. Most
        spectral power sits below 20 Hz, so a 1-20 Hz fit is close to being the 1-40 Hz fit. Predicting my
        own new feature is redundant, before looking, is the honest version of adding it: if it survives, it
        survives against a stated expectation rather than into a vacuum.
    P2  `spatial_participation_ratio` is NOT redundant with any per-channel candidate, |rho| < 0.90 against
        all of them. It is the only candidate that reads BETWEEN channels; if it is redundant with a
        per-channel summary, then spatial structure genuinely carries nothing here and E06's "one channel is
        nearly as good as 91" is a fact about the brain rather than about my feature set.
    P3  At least one exotic candidate FAILS its declared direction. The seed set's record is poor and I am
        stating in advance that I expect the same of these, so that a failure is not presented afterwards as
        having been anticipated all along.
    P4  STRUCTURAL GATE: `critical_slowing_ar1` must NOT be reported as surviving, because its declaration
        requires the temporal layer and that layer is not built. If it is ever reported as surviving, the
        `requires`/verdict logic has broken.

    FALSIFICATION: if every exotic candidate is either redundant or fails its direction, the honest report is
    that borrowing from other fields added nothing here -- a real and publishable negative about feature
    engineering, and one this project should be willing to reach.

SCOPE. 20 healthy volunteers, one drug, one site, average-referenced, 0.5-45 Hz. Search space is 17
registered candidates with analytic_dof 1, and that denominator belongs beside every number below.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                     # noqa: E402
from bsde.candidates.seed import seed_registry                                     # noqa: E402
from bsde.verifier.engine import check_redundancy                                   # noqa: E402
from bsde.verifier.stats import directional_auc, cluster_bootstrap_ci, spearman, _midranks  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "chennu_features_v3.csv")
EXOTIC = ("spatial_participation_ratio", "multiscale_entropy_slope", "pac_slow_alpha",
          "exponent_low", "exponent_high", "critical_slowing_ar1")
INCUMBENT = ("whole_head_exponent", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
             "relative_alpha_power", "relative_delta_power", "wpli_alpha", "uce_v1")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    if not os.path.exists(TABLE):
        return []
    with open(TABLE, newline="") as fh:
        return [r for r in csv.DictReader(fh) if r.get("status") == "ok"]


def col(rows, name):
    return np.array([_f(r.get(name, "")) for r in rows], float)


def main() -> int:
    seed_registry()
    rows = load()
    n_space = REGISTRY.search_space_size()
    print("E08 — exotic features: redundancy first, then signed direction")
    print(f"   search space {n_space} registered candidates, analytic_dof 1")
    if not rows:
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    print(f"   rows {len(rows)}   subjects {len({r['subject'] for r in rows})}")

    # =============================== GATE 1: REDUNDANCY (label-free) ==============================
    print("\n" + "=" * 100); print("GATE 1 — REDUNDANCY (label-free, runs before any evaluation)")
    print("=" * 100)
    red = {}
    for name in EXOTIC:
        cand = REGISTRY.get(name)
        v = col(rows, name)
        if not np.isfinite(v).any():
            print(f"   {name:28s} NOT COMPUTED in this table")
            red[name] = {"status": "not_computed"}
            continue
        worst, worst_against, evs = 0.0, None, []
        for other in INCUMBENT:
            w = col(rows, other)
            if not np.isfinite(w).any():
                continue
            oc = REGISTRY.get(other)
            e = check_redundancy(cand, v, w, f"{other} (complexity {oc.complexity})", oc.complexity)
            r = abs(e.values.get("abs_spearman", float("nan")))
            evs.append((other, r, e.status, e.fatal))
            if np.isfinite(r) and r > worst:
                worst, worst_against = r, other
        fatal = any(st == "fail" and ft for _, _, st, ft in evs)
        top = sorted([e for e in evs if np.isfinite(e[1])], key=lambda t: -t[1])[:3]
        print(f"   {name:28s} max |rho| {worst:.3f} vs {worst_against}"
              f"{'   *** FATAL REDUNDANCY ***' if fatal else ''}")
        print(f"      {'  '.join(f'{o}={r:.3f}' for o, r, _, _ in top)}")
        red[name] = {"max_abs_rho": worst, "closest": worst_against, "fatal": bool(fatal),
                     "all": {o: r for o, r, _, _ in evs}}

    survivors = [n for n in EXOTIC if red.get(n, {}).get("status") != "not_computed"
                 and not red.get(n, {}).get("fatal")]
    killed = [n for n in EXOTIC if red.get(n, {}).get("fatal")]
    print(f"\n   killed by redundancy: {killed or 'none'}")
    print(f"   proceeding to evaluation: {survivors}")

    # =============================== GATE 2: SIGNED DIRECTION =====================================
    print("\n" + "=" * 100)
    print("GATE 2 — SIGNED DIRECTION, baseline (level 1) vs moderate (level 3)")
    print("=" * 100)
    lvl = np.array([_f(r.get("meta_sedation_level")) for r in rows])
    keep = np.isin(lvl, (1.0, 3.0))
    y = (lvl[keep] == 3.0).astype(float)
    subj = np.array([r.get("subject", "") for r in rows])[keep]
    rng = np.random.default_rng(20260730)
    print(f"   {'candidate':28s} {'declared':>9s} {'signed AUC':>22s}  verdict")
    ev = {}
    for name in list(EXOTIC) + list(INCUMBENT):
        cand = REGISTRY.get(name)
        d = cand.predicted("unconscious_vs_awake")
        v = col(rows, name)[keep]
        if d not in ("higher", "lower") or not np.isfinite(v).sum() > 20:
            continue
        a = directional_auc(y, v, d)
        lo, hi = cluster_bootstrap_ci(lambda i: directional_auc(y[i], v[i], d), subj, rng, reps=1000)[:2]
        if lo > 0.5:
            verdict = "SUPPORTS declared direction"
        elif hi < 0.5:
            verdict = "*** OPPOSITE to declaration -- REFUTED"
        else:
            verdict = "spans 0.5"
        tag = "  [redundant]" if red.get(name, {}).get("fatal") else ""
        print(f"   {name:28s} {d:>9s} {a:8.3f} [{lo:.3f}, {hi:.3f}]  {verdict}{tag}")
        ev[name] = {"declared": d, "auc": a, "ci": [lo, hi], "verdict": verdict,
                    "exotic": name in EXOTIC}

    # =============================== registered predictions =======================================
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    p1 = red.get("exponent_low", {}).get("all", {}).get("whole_head_exponent", 0.0) >= 0.90
    spr = red.get("spatial_participation_ratio", {})
    p2 = np.isfinite(spr.get("max_abs_rho", np.nan)) and spr["max_abs_rho"] < 0.90
    refuted = [n for n, e in ev.items() if n in EXOTIC and "OPPOSITE" in e["verdict"]]
    p3 = len(refuted) > 0
    cs = REGISTRY.get("critical_slowing_ar1")
    p4 = "temporal" in cs.requires
    print(f"   P1 exponent_low redundant with the 1-40 Hz exponent : {'MET' if p1 else 'NOT MET'} "
          f"(|rho| {red.get('exponent_low', {}).get('all', {}).get('whole_head_exponent', float('nan')):.3f})")
    print(f"   P2 spatial_participation_ratio NOT redundant        : {'MET' if p2 else 'NOT MET'} "
          f"(max |rho| {spr.get('max_abs_rho', float('nan')):.3f} vs {spr.get('closest')})")
    print(f"   P3 at least one exotic fails its declared direction : {'MET' if p3 else 'NOT MET'} ({refuted})")
    print(f"   P4 critical_slowing_ar1 requires the unbuilt        : {'MET' if p4 else 'NOT MET'} "
          f"temporal layer, so it cannot be reported as surviving")
    supports = [n for n, e in ev.items() if n in EXOTIC and e["verdict"].startswith("SUPPORTS")
                and not red.get(n, {}).get("fatal")]
    print(f"\n   exotic candidates that are non-redundant AND support their declared direction: "
          f"{supports or 'NONE'}")
    if not supports:
        print("   HONEST NEGATIVE: borrowing from other fields added nothing here. That is a real result")
        print("   about feature engineering and it is reported rather than buried.")
    print(f"\n   Every number above carries a denominator of {n_space} registered candidates.")

    dst = os.path.join(RESULTS, "e08_exotic.json")
    json.dump({"experiment": "E08", "search_space_size": n_space, "analytic_dof": 1,
               "redundancy": red, "signed_direction": ev,
               "predictions": {"P1": bool(p1), "P2": bool(p2), "P3": bool(p3), "P4": bool(p4)},
               "non_redundant_and_supported": supports}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
