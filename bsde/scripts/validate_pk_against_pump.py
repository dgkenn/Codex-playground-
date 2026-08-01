"""RIGOROUS VALIDATION of this project's propofol kinetics against a reference that is not the EEG.

WHY THIS AND NOT SOMETHING ELSE. `PKPD_MODEL_REVIEW.md` §6.2 forbids validating the exposure model against
BIS, because BIS is computed from the EEG under test and the whole programme rests on the EEG and the
pharmacology being independent. `DEPTH_TARGET_STRATEGY.md` extends that: an EEG scored against
concentration is rewarded for being redundant with the pump. **But the pump's own effect-site
concentration is a perfectly good target for the KINETICS**, because reproducing it tests only whether we
turn an infusion record into a concentration the way a TCI device does -- a question with no EEG in it
anywhere.

VitalDB publishes, per case, `Orchestra/PPF20_RATE` (the infusion rate the pump delivered),
`Orchestra/PPF20_VOL` (its own cumulative volume) and `Orchestra/PPF20_CE` (its own modelled effect-site
concentration). 145 of the 250 cases with EEG features carry all three. The rate is the INPUT, the volume
is a free end-to-end check on the integration, and Ce is the target.

WHAT MAKES THIS A VALIDATION RATHER THAN A CURVE FIT. The basis weights are fitted on TRAINING CASES and
scored on cases never seen (grouped, so a case is wholly in one side). Fitting weights on the same case
they are scored on would reproduce anything, and the exponential basis is expressive enough that it
certainly would. Out-of-sample is the only version of this that means something.

THE METRICS ARE VARVEL'S, because they are the standard for exactly this comparison and because each
answers a different question that a single R^2 hides (Varvel et al., J Pharmacokinet Biopharm
1992;20:63-94, PMID 1588504 -- verified from the MEDLINE record, not from a summary, per rule 25):

    PE_ij   = 100 * (reference_ij - predicted_ij) / predicted_ij     performance error
    MDPE_i  = median_j PE_ij                                          BIAS within case i
    MDAPE_i = median_j |PE_ij|                                        INACCURACY within case i
    wobble_i= median_j |PE_ij - MDPE_i|                               intra-case variability
    divergence_i = slope of |PE_ij| against time, %/h                 drift: does it get worse?

and the reported figures are the medians across cases, which is what Varvel specifies and what the TCI
literature reports.

TWO HONEST LIMITS, stated here so they cannot become excuses afterwards (rule 47).

  1. **The pump's model is not stated in the deposit.** So this measures agreement with WHICHEVER model
     the Orchestra implements, not agreement with truth. A disagreement is therefore ambiguous, but an
     AGREEMENT is not: reproducing an unknown three-compartment model out of sample from its input alone
     is exactly the claim the exponential-basis argument makes (`bsde/src/bsde/pkpd/propofol.py`), and
     failing to would refute it.
  2. **The pump's Ce is itself a model output, not a measured blood concentration.** No deposit this
     project can reach has assayed propofol concentrations. This validates the kinetics against a
     reference implementation, which is a weaker claim than validating against blood, and it is the
     strongest available here.

    python bsde/scripts/validate_pk_against_pump.py --folds 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.pkpd.propofol import (HALF_LIVES_MIN, infusion_basis,             # noqa: E402
                                rate_track_to_segments)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
PK_INPUTS = os.path.join(RESULTS, "vitaldb_pk_inputs.jsonl")
OUT = os.path.join(RESULTS, "pk_pump_validation.json")

RATE = "Orchestra/PPF20_RATE"
CE = "Orchestra/PPF20_CE"
VOL = "Orchestra/PPF20_VOL"
MG_PER_ML = 20.0                      # named in the track: PPF20 is a 20 mg/mL preparation
STRIDE_S = 10                         # evaluate every 10th second; the pump reports at ~1 Hz
MIN_CE_SAMPLES = 60
SEED = 1992


def load_cases(path, limit=0):
    out = []
    for line in open(path):
        d = json.loads(line)
        t = d.get("tracks") or {}
        if not (RATE in t and CE in t):
            continue
        out.append(d)
        if limit and len(out) >= limit:
            break
    return out


def prepare(d):
    """One case -> (design, target, volume check). Returns None if the case cannot be used."""
    t = d["tracks"]
    rt, rv = np.asarray(t[RATE]["t"], float), np.asarray(t[RATE]["v"], float)
    ct, cv = np.asarray(t[CE]["t"], float), np.asarray(t[CE]["v"], float)
    ok = np.isfinite(ct) & np.isfinite(cv)
    ct, cv = ct[ok], cv[ok]
    if ct.size < MIN_CE_SAMPLES or not np.any(cv > 0):
        return None
    s0, s1, rate_mg_s = rate_track_to_segments(rt, rv, mg_per_ml=MG_PER_ML, t_end_s=float(ct[-1]))
    if s0.size == 0:
        return None

    # Evaluate where the pump reports a concentration, strided. Only AFTER the first infusion has begun:
    # before that both series are identically zero and would inflate every agreement statistic for free.
    keep = (ct >= s0.min()) & (np.arange(ct.size) % STRIDE_S == 0)
    ev, tgt = ct[keep], cv[keep]
    if ev.size < 20:
        return None

    X = infusion_basis(s0, s1, rate_mg_s, ev)
    wt = float(d.get("demog", {}).get("weight") or "nan")
    if np.isfinite(wt) and wt > 0:
        X = X / wt                                     # per-kg, so weights transfer between cases
    if not np.all(np.isfinite(X)):
        return None

    # FREE END-TO-END CHECK: the pump publishes its own cumulative volume. Integrating the rate segments
    # must reproduce it. A mismatch means the zero-order-hold reading of the rate track is wrong, and it
    # would corrupt every concentration silently.
    vol_ok = None
    if VOL in t:
        vt, vv = np.asarray(t[VOL]["t"], float), np.asarray(t[VOL]["v"], float)
        m = np.isfinite(vt) & np.isfinite(vv)
        if m.any() and vv[m].max() > 0:
            mine_ml = float(((s1 - s0) * rate_mg_s).sum() / MG_PER_ML)
            theirs = float(vv[m].max())
            vol_ok = abs(mine_ml - theirs) / theirs
    return {"caseid": d["caseid"], "X": X, "y": tgt, "t": ev, "vol_rel_err": vol_ok}


def varvel(reference, predicted, times_s):
    """Varvel's four metrics for one case. `predicted` is ours, `reference` is the pump's."""
    p = np.asarray(predicted, float)
    r = np.asarray(reference, float)
    m = np.isfinite(p) & np.isfinite(r) & (p > 1e-6)
    if m.sum() < 10:
        return None
    pe = 100.0 * (r[m] - p[m]) / p[m]
    mdpe = float(np.median(pe))
    mdape = float(np.median(np.abs(pe)))
    wobble = float(np.median(np.abs(pe - mdpe)))
    tt = np.asarray(times_s, float)[m] / 3600.0
    div = float(np.polyfit(tt, np.abs(pe), 1)[0]) if np.ptp(tt) > 1e-6 else float("nan")
    return {"MDPE": mdpe, "MDAPE": mdape, "wobble": wobble, "divergence_pct_per_h": div, "n": int(m.sum())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inputs", default=PK_INPUTS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    raw = load_cases(a.inputs, a.limit)
    print(f"{len(raw)} cases carry both {RATE} and {CE}", flush=True)
    cases = [c for c in (prepare(d) for d in raw) if c is not None]
    print(f"{len(cases)} usable after preparation", flush=True)
    if len(cases) < 2 * a.folds:
        print("too few cases")
        return 1

    vols = [c["vol_rel_err"] for c in cases if c["vol_rel_err"] is not None]
    if vols:
        vols = np.asarray(vols)
        print(f"volume reproduction: median relative error {np.median(vols):.4%}, "
              f"90th pct {np.quantile(vols, 0.9):.4%}, {int((vols < 0.02).sum())}/{vols.size} within 2 %",
              flush=True)

    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(cases))
    fold_of = {int(i): int(k % a.folds) for k, i in enumerate(order)}

    per_case, per_case_ref = [], []
    for f in range(a.folds):
        tr = [cases[i] for i in range(len(cases)) if fold_of[i] != f]
        te = [cases[i] for i in range(len(cases)) if fold_of[i] == f]
        Xtr = np.vstack([c["X"] for c in tr])
        ytr = np.concatenate([c["y"] for c in tr])
        A = np.hstack([Xtr, np.ones((Xtr.shape[0], 1))])
        w, *_ = np.linalg.lstsq(A, ytr, rcond=None)
        for c in te:
            pred = np.hstack([c["X"], np.ones((c["X"].shape[0], 1))]) @ w
            v = varvel(c["y"], pred, c["t"])
            if v:
                v["caseid"] = c["caseid"]
                per_case.append(v)
            # REFERENCE ARM (rule 40: a metric with nothing to compare against cannot fail). The naive
            # exposure this project used before -- cumulative dose, no kinetics -- scored identically.
            cum = np.cumsum(np.gradient(np.arange(c["X"].shape[0], dtype=float)))  # placeholder, replaced
            naive = c["X"][:, -1:]                     # the SLOWEST kernel alone ~ cumulative dose
            An = np.hstack([naive, np.ones((naive.shape[0], 1))])
            wn, *_ = np.linalg.lstsq(
                np.hstack([np.vstack([t2["X"][:, -1:] for t2 in tr]),
                           np.ones((Xtr.shape[0], 1))]), ytr, rcond=None)
            vr = varvel(c["y"], An @ wn, c["t"])
            if vr:
                per_case_ref.append(vr)

    def agg(rows, key):
        v = np.asarray([r[key] for r in rows if np.isfinite(r[key])], float)
        return {"median": float(np.median(v)), "p25": float(np.quantile(v, .25)),
                "p75": float(np.quantile(v, .75)), "n_cases": int(v.size)}

    res = {"n_cases": len(cases), "folds": a.folds,
           "half_lives_min": list(HALF_LIVES_MIN),
           "volume_reproduction_median_rel_err": float(np.median(vols)) if len(vols) else None,
           "full_basis": {k: agg(per_case, k) for k in
                          ("MDPE", "MDAPE", "wobble", "divergence_pct_per_h")},
           "reference_slowest_kernel_only": {k: agg(per_case_ref, k) for k in
                                             ("MDPE", "MDAPE", "wobble", "divergence_pct_per_h")}}
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
