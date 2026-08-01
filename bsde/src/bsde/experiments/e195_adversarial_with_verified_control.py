#!/usr/bin/env python3
"""E195 — E193 with a negative control whose inseparability is CONSTRUCTED AND MEASURED, not asserted.

REGISTERED BEFORE ANY PERMUTATION DRAW HAS BEEN COMPUTED WITH THE CORRECTED CONTROL.

=========================================================================================================
WHY THIS EXISTS: E193's GATE FIRED AND THE FAULT WAS IN THE GATE
=========================================================================================================
E193 added the negative capability gate E165 lacked — a synthetic system where state and agent are
"driven by the same latent, so no axis can separate them", which must therefore yield no succeeding
lambda. **It fired**: at lambda 0.5 and 1.0 the method kept 90 % and 83 % of the lambda = 0 state
legibility while putting agent legibility below the permutation floor, on a system where that was supposed
to be impossible. E193's verdict is NOT INTERPRETABLE and is recorded as such.

**The system was not inseparable.** Reading the construction rather than its name: the state-carrying
direction `ws` and the agent-carrying direction `wa` were two INDEPENDENT Gaussian draws in eleven
dimensions, so they are very nearly orthogonal — and the state contrast contained a term
`-1.2 * ws` that does not involve the latent at all. A projection onto `ws` therefore reads a constant
state offset and almost nothing of the agent. Separation was not merely possible, it was easy, and the
method finding it is **correct behaviour**. Calling that a failure of the method would have been the
error; calling it a failure of the control is the diagnosis.

This is rule 77 in its exact shape — *a control built to have a property must be MEASURED for that
property, because a shared latent (or here, the lack of one) is invisible in the code that constructs it*
— and it is the second time in this programme that a control's construction, rather than the thing under
test, produced the verdict.

=========================================================================================================
THE CORRECTION, AND WHY IT IS NOT A LOOSENED GATE
=========================================================================================================
The repair is one line of construction and one line of verification:

    entangled system:  ws IS wa. The state contrast and the agent signal lie on the SAME direction, so
                       any projection that reads the state offset necessarily orders cases by the latent
                       and therefore by arm. Inseparable by construction rather than by description.
    separable system:  ws and wa independent, as before. Unchanged.

**And the property is now measured rather than named.** `|cos(ws, wa)|` is printed for both systems and
GATED: the entangled system must have it at 1.0 and the separable system below 0.5. A control that does
not have the property it exists to have is refused before it is used.

Note the direction this cuts. E193's gate failed and this file makes the control **correct**, which
happens to make the gate passable — so it must be said plainly that a gate is not being loosened after a
failure. The registered success rule, the floors, the tolerance, the cohort, the features and the null are
**identical to E193's**; nothing about the real-data test moves. What changes is that the synthetic system
labelled "inseparable" now is one. If that repair is rejected, the correct reading is E193's: NOT
INTERPRETABLE, and Challenge A has no constructive answer on this cohort.

Everything else is E193, which is E165 with the null repaired: MGH OR cases with a **behavioural**
loss-of-consciousness label, case summaries over a fixed epoch count, leave-one-case-out fitting, and an
agent floor that is the 95th percentile of a cluster-level permutation over case arm labels recomputed
per lambda through the entire pipeline.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) CONTROL REFUSED     the constructed systems do not have their intended separability (the new
                          measurement gate). Nothing is run.
  (2) NOT INTERPRETABLE   G1, G2a, G2b or G4 fails.
  (3) VACUOUS             the success rule fires at lambda = 0, with no adversarial term.
  (4) NOT CONSTRUCTED     no lambda > 0 keeps >= 80 % of the lambda = 0 state legibility while putting
                          agent legibility below the cluster-permutation floor.
  (5) CONSTRUCTED         some lambda > 0 does both.

**REGISTERED PREDICTION: (4) NOT CONSTRUCTED**, unchanged from E193 and for the same reasons — E161 found
two spectral features each identifying the agent far above a cluster null on VitalDB, and E186 finds the
agent legible in every pre-specified subset of the same family. **The prediction is recorded again here
rather than quietly inherited, because a successor that does not restate its prediction can absorb its
predecessor's result as a success.**

    python bsde/src/bsde/experiments/e195_adversarial_with_verified_control.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from e154_lambda_on_mgh_or import FEATURES                                     # noqa: E402
from e165_adversarial_challenge_a import build, ranks                          # noqa: E402
from e193_adversarial_against_cluster_null import (CORR_MAX, LAMBDAS, MIN_PER_ARM,   # noqa: E402
                                                   PERMS, STATE_TOL, add_duration,
                                                   blocks, evaluate)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e195_adversarial_verified_control.json")
SEED = 20260801

COS_ENTANGLED_MIN = 0.999   # the entangled system's two directions must BE the same direction
COS_SEPARABLE_MAX = 0.50    # the separable system's must not be
NULL_DRAWS_CONTROL = 40


def synthetic(n, entangled, rng):
    """A system whose separability is known BY CONSTRUCTION and returned so it can be CHECKED.

    entangled=True   ws IS wa: the state contrast and the agent signal lie on ONE direction, so a
                     projection that reads the state offset necessarily orders cases by the latent and
                     therefore by arm. No axis can keep one and drop the other.
    entangled=False  ws and wa are independent draws, so a separating axis exists.
    """
    p = len(FEATURES)
    lat_s = rng.normal(size=n)
    lat_a = lat_s.copy() if entangled else rng.normal(size=n)
    arm = (lat_a > np.median(lat_a)).astype(float)
    wa = rng.normal(size=p)
    ws = wa.copy() if entangled else rng.normal(size=p)
    U = 0.9 * np.outer(lat_a, wa) + rng.normal(size=(n, p))
    S = U - 1.2 * np.outer(np.ones(n), ws) - 0.9 * np.outer(lat_s, ws) \
        + rng.normal(size=(n, p)) * 0.3
    st = np.column_stack([ranks(np.concatenate([S[:, j], U[:, j]])) for j in range(p)])
    cos = float(abs(np.dot(ws, wa) / (np.linalg.norm(ws) * np.linalg.norm(wa))))
    return st[:n], st[n:], arm, cos


def sweep(S, U, arm, tag, perms, seed=SEED):
    """Run every lambda and return the table plus whether any lambda > 0 satisfies the success rule."""
    s0, a0, _ = evaluate(S, U, arm, 0.0, seed=seed)
    tab = {}
    for lam in LAMBDAS:
        s, a, ax = evaluate(S, U, arm, lam, seed=seed)
        nul = []
        for k in range(perms):
            pa = np.random.default_rng(seed + 9000 + k).permutation(arm)
            _s2, a2, _ = evaluate(S, U, pa, lam, seed=seed)
            if np.isfinite(a2):
                nul.append(abs(a2))
        f95 = float(np.quantile(nul, 0.95)) if nul else float("nan")
        keeps = bool(np.isfinite(s) and np.isfinite(s0) and s >= STATE_TOL * abs(s0))
        hides = bool(np.isfinite(a) and np.isfinite(f95) and abs(a) < f95)
        tab[str(lam)] = {"state": float(s), "agent": float(a), "floor": f95,
                         "keeps_state": keeps, "hides_agent": hides,
                         "succeeds": bool(keeps and hides), "n_null": len(nul),
                         "axis": ax.tolist() if lam == 0.0 else None}
        print(f"   [{tag}] lam {lam:>4.1f}: state {s:+.4f} ({'keeps' if keeps else ' no  '}) "
              f"agent {a:+.4f} floor {f95:+.4f} ({len(nul)})  "
              f"{'SUCCEEDS' if keeps and hides else ''}", flush=True)
    pos = [float(k) for k, v in tab.items() if v["succeeds"] and float(k) > 0]
    zero = bool(tab["0.0"]["succeeds"])
    return tab, pos, zero, float(s0)


def main() -> int:
    print("E195 — Challenge A constructively, with a negative control whose property is MEASURED")
    res = {"experiment": "E195", "lambdas": list(LAMBDAS), "perms": PERMS,
           "state_tol": STATE_TOL, "features": FEATURES}

    cases, miss = add_duration(build())
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n_mix, n_pro = int(arm.sum()), int(len(arm) - arm.sum())
    g1 = bool(min(n_mix, n_pro) >= MIN_PER_ARM)
    print(f"G1 COHORT  {len(ids)} OR cases: {n_pro} propofol alone, {n_mix} mixed   "
          f"{'PASS' if g1 else '*** FAIL'}")
    res.update({"n_cases": len(ids), "n_mixed": n_mix, "n_propofol": n_pro, "g1": g1})

    print("\nG0 CONTROL VERIFICATION — the constructed systems must HAVE their intended separability")
    Sp, Up, ap, cos_sep = synthetic(len(ids), False, np.random.default_rng(SEED + 1))
    Se, Ue, ae, cos_ent = synthetic(len(ids), True, np.random.default_rng(SEED + 2))
    print(f"   |cos(ws, wa)|  separable system {cos_sep:.4f} (must be < {COS_SEPARABLE_MAX});  "
          f"entangled system {cos_ent:.4f} (must be >= {COS_ENTANGLED_MIN})")
    g0 = bool(cos_sep < COS_SEPARABLE_MAX and cos_ent >= COS_ENTANGLED_MIN)
    print(f"   {'PASS' if g0 else '*** FAIL — a control without its property is not a control'}")
    res["g0"] = {"cos_separable": cos_sep, "cos_entangled": cos_ent, "pass": g0}
    if not g0:
        res["verdict"], res["why"] = "CONTROL REFUSED", (
            "the synthetic systems do not have the separability they are built to have, so neither "
            "capability gate means anything and nothing is run (rule 77)")
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"\nVERDICT: {res['verdict']}\n  {res['why']}")
        return 1

    print("\nG2a POSITIVE capability — independent directions, a separating axis EXISTS")
    tp, pos_p, _z, s0p = sweep(Sp, Up, ap, "sep", NULL_DRAWS_CONTROL, SEED)
    g2a = bool(np.isfinite(s0p) and s0p > 0.20)
    print(f"   lam=0 state legibility {s0p:+.4f}   {'PASS' if g2a else '*** FAIL'}"
          f"   (separating lambdas found: {pos_p or 'none'})")

    print("\nG2b NEGATIVE capability — ONE direction carries both, so NO axis can separate them")
    te, pos_e, _z2, s0e = sweep(Se, Ue, ae, "ent", NULL_DRAWS_CONTROL, SEED)
    g2b = not pos_e
    print(f"   {'PASS — the success rule can FAIL' if g2b else '*** FAIL — unfalsifiable: ' + str(pos_e)}")
    res.update({"g2a": g2a, "g2b": g2b, "separable_control": tp, "entangled_control": te,
                "separable_state_lam0": s0p, "entangled_state_lam0": s0e})

    print("\nREAL DATA — MGH OR, behavioural loss-of-consciousness label")
    S, U = blocks(cases, ids)
    dur = np.array([cases[c]["n_epochs"] for c in ids], float)
    print(f"   recording length {np.nanmin(dur):.0f}-{np.nanmax(dur):.0f} epochs, "
          f"{int(np.isfinite(dur).sum())} of {len(ids)} populated")
    tab, pos, zero, s0 = sweep(S, U, arm, "real", PERMS, SEED)
    res.update({"table": tab, "state_lam0": s0})

    lam_g4 = pos[0] if pos else 0.0
    _s, _a, ax = evaluate(S, U, arm, lam_g4, seed=SEED)
    m = np.isfinite(dur) & np.isfinite(ax)
    rho = (float(np.corrcoef(np.argsort(np.argsort(dur[m])), np.argsort(np.argsort(ax[m])))[0, 1])
           if m.sum() > 10 else float("nan"))
    g4 = bool(not np.isfinite(rho) or abs(rho) < CORR_MAX)
    res["g4_axis_vs_duration_rho"], res["g4"] = rho, g4
    print(f"\nG4 axis vs recording length: rho = {rho:+.4f}   {'PASS' if g4 else '*** FAIL'} "
          "(E154 measured duration identifying the agent at 0.3771 on this cohort)")

    print("\n" + "=" * 100)
    if not (g1 and g2a and g2b and g4):
        v, why = "NOT INTERPRETABLE", (
            "a gate failed: " + ", ".join(n for n, ok in (("G1 cohort", g1),
                                                          ("G2a positive capability", g2a),
                                                          ("G2b negative capability", g2b),
                                                          ("G4 duration", g4)) if not ok))
    elif zero and not pos:
        v, why = "VACUOUS", ("the success rule fires only at lambda = 0, with no adversarial term in "
                             "the objective. That is E165's failure mode and it is not a result")
    elif pos:
        v, why = "CONSTRUCTED", (
            f"lambda {pos} keeps >= {STATE_TOL:.0%} of the lambda=0 state legibility ({s0:+.4f}) while "
            "putting agent legibility below the cluster-permutation 95th percentile. This would be a "
            "surprise against E161 and E186 and needs replication on VitalDB before it is believed")
    else:
        v, why = "NOT CONSTRUCTED", (
            f"no lambda keeps >= {STATE_TOL:.0%} of the lambda=0 state legibility ({s0:+.4f}) while "
            "dropping agent legibility below the cluster-permutation floor; on this cohort, with a "
            "BEHAVIOURAL state label, depth and agent identity are not linearly separable in the "
            "spectral family")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
