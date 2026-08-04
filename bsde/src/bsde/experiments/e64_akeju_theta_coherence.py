#!/usr/bin/env python3
"""E64 -- Challenge A. Does Akeju's THETA coherence signature separate the drugs on a two-channel BIS strip?

REGISTERED AFTER A FEASIBILITY PROBE AND BEFORE ANY DRUG CONTRAST HAS BEEN COMPUTED ON THESE COLUMNS. The
probe (rule 41) read the eight new connectivity columns against BIS and against nothing else -- no agent
label was touched. What it found is recorded below and it KILLED the experiment this file was originally
going to be.

=========================================================================================================
WHAT THE PROBE KILLED, AND WHY THAT IS THE SYSTEM WORKING
=========================================================================================================
`CONSOLIDATION_2026_07_31.md` proposed testing E36's family split (inter-channel PHASE leaks little drug
identity) against Akeju et al. (PMID 25233374, the drug discriminator IS an inter-channel phase quantity)
on VitalDB's two BIS channels. Measured on 4,220 usable windows:

    measure            median      sd      IQR                 rho vs BIS
    coherence_delta    0.6299    0.1753    0.5095..0.7190        -0.1393
    coherence_theta    0.6445    0.1655    0.5396..0.7337        -0.0860
    coherence_alpha    0.6606    0.1612    0.5527..0.7481        -0.0633
    coherence_beta     0.5987    0.1582    0.5107..0.6760        -0.0816
    wpli_delta         0.0015    0.1371   -0.0172..0.0518        +0.0515
    wpli_theta         0.0106    0.1508   -0.0052..0.0549        -0.0166
    wpli_alpha         0.0235    0.1339   -0.0021..0.0913        -0.0364
    wpli_beta          0.0034    0.0974   -0.0024..0.0198        +0.0444

**wPLI is centred on zero with a symmetric spread in every band, and its rank correlation with the monitor
never exceeds 0.05 in magnitude. That is a noise distribution.** Two electrodes about two centimetres apart
on a shared reference have no consistent phase lag to detect, which is what wPLI exists to measure. So the
FAMILY COMPARISON IS NOT AVAILABLE HERE -- rule 53, applied before registration rather than discovered after
a confident null: a contrast between two families requires at least one of them to show the effect.

Coherence, by contrast, is alive: it varies (sd ~0.16) and moves weakly with depth. But it sits at 0.60-0.66
in EVERY band with no band-specific structure, which is the signature of a shared reference rather than of
frontal network coupling. **Akeju measured a full frontal montage; this is a two-electrode strip.**

=========================================================================================================
WHAT SURVIVES, AND WHY IT IS STILL WORTH RUNNING
=========================================================================================================
Akeju's claim is not "coherence is high". It is a DIFFERENTIAL between bands, and it is stated with an
internal control already built in:

    theta   sevoflurane shows a distinct coherence signature (peak 4.9 +/- 0.6 Hz, coherence 0.58 +/- 0.1)
            that propofol does not
    alpha   the two drugs are effectively the SAME (peak coherence 0.73 +/- 0.1 vs 0.71 +/- 0.1)

**A differential is exactly the statistic a reference-dominated coherence can still support**, because the
shared-reference contribution is common to both bands and cancels. That is the one design this montage
permits, and it is a genuine test of a published finding on an independent deposit.

COHORT. Single-agent cases, propofol vs sevoflurane, device BIS in [40,60) so identity is read at matched
depth, SQI >= 50. Identical to E61's cohort, deliberately: the only thing changing is the measure.

  M1 ALIVENESS GATE (rule 53)  `coherence_theta` must clear its OWN permutation null -- agent labels
                               shuffled across cases, same statistic. If theta coherence carries no agent
                               information at all, the differential is a difference of two nulls and means
                               nothing. **This gate is evaluated first and can end the experiment.**
  PRIMARY                      |AUC-0.5| for agent identity from `coherence_theta` MINUS the same from
                               `coherence_alpha`, out-of-fold with cases held out whole, case-clustered
                               bootstrap. **PREDICTED POSITIVE** -- Akeju says theta separates and alpha
                               does not.
  P1 PLACEBO                   agent permuted across cases, primary recomputed. |AUC-0.5| is biased upward
                               under the null (rule 46) so it appears only inside this difference, and the
                               placebo fixes the difference's own null level.
  S1 wPLI SENSITIVITY          the same differential on `wpli_theta` - `wpli_alpha`, REPORTED AND NOT
                               GATED. The probe says it should be null; printing it makes that visible
                               rather than assumed, and a surprise there would be worth more than the
                               primary.

VERDICT RULE, wrong direction first.

  (a) REVERSED       -- the primary's interval lies entirely BELOW zero: ALPHA separates the drugs more
                        than theta, which is the opposite of Akeju's report and would mean either the
                        finding does not transfer to this montage or the band assignment is inverted here.
  (b) NOT REPLICATED -- the interval includes zero. Akeju's theta signature does not produce a detectable
                        band differential on a two-channel BIS strip. **This is the expected outcome given
                        the montage** and it is not evidence against Akeju -- it is evidence about what
                        this deposit can resolve.
  (c) NOT INFORMATIVE-- M1 failed, or the placebo reaches the primary.
  (d) REPLICATED     -- the interval lies entirely above zero and the placebo does not reach it. Akeju's
                        band differential survives on an independent deposit with a far poorer montage,
                        which would make it robust in a way the original could not show.

WHAT NONE OF THESE LICENCE. Nothing here is a Challenge A pass. A1 is untouched: the agents are in disjoint
patients, so a leak through any correlate of the agent is still a leak and this design cannot attribute it
to pharmacology. And E36's family split remains untested on this deposit, permanently -- wPLI is dead here.

    python -m bsde.experiments.e64_akeju_theta_coherence
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import auc, cluster_bootstrap_ci, cv_predict_proba    # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
CONN = os.path.join(RESULTS, "vitaldb_conn.csv")
OUT = os.path.join(RESULTS, "e64_akeju_theta_coherence.json")

AGENTS = ("propofol", "sevoflurane")
DEPTH_BAND = (40.0, 60.0)
MIN_SQI = 50.0
N_PERM = 60
REPS = 200
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _abs_auc(x, y, case, rng):
    ok = np.isfinite(x)
    if ok.sum() < 50 or len(np.unique(y[ok])) < 2:
        return float("nan")
    a = auc(y[ok], cv_predict_proba(x[ok], y[ok], case[ok], rng))
    return abs(a - 0.5) if np.isfinite(a) else float("nan")


def main() -> int:
    if not os.path.exists(CONN):
        print(f"MISSING {CONN} -- run scripts/stream_vitaldb_conn.py first")
        return 2
    rows = [r for r in csv.DictReader(open(CONN, newline="")) if r["status"] == "ok"]
    bis = np.array([_f(r["meta_bis"]) for r in rows])
    sqi = np.array([_f(r["meta_sqi"]) for r in rows])
    ag = np.array([r.get("meta_agents_present", "") for r in rows])
    keep = (np.isfinite(bis) & (bis >= DEPTH_BAND[0]) & (bis < DEPTH_BAND[1])
            & (sqi >= MIN_SQI) & np.isin(ag, AGENTS)
            & (np.array([r.get("meta_sensor_off", "") for r in rows]) != "True"))
    idx = np.flatnonzero(keep)
    y = (ag[idx] == AGENTS[1]).astype(float)
    case = np.array([rows[i]["meta_caseid"] for i in idx])
    col = {k: np.array([_f(rows[i][k]) for i in idx])
           for k in ("coherence_theta", "coherence_alpha", "wpli_theta", "wpli_alpha")}
    print(f"analysis set: {len(idx)} windows, {len(np.unique(case))} cases "
          f"({int((y == 0).sum())} {AGENTS[0]} / {int((y == 1).sum())} {AGENTS[1]})")

    rng = np.random.default_rng(SEED)
    obs = {k: _abs_auc(v, y, case, np.random.default_rng(SEED)) for k, v in col.items()}
    for k, v in obs.items():
        print(f"   |AUC-0.5| {k:<18s} {v:.4f}")

    # M1 aliveness (rule 53), evaluated first: theta coherence must clear its own permutation null.
    uc = np.unique(case)
    lab = {c: y[case == c][0] for c in uc}
    rp = np.random.default_rng(SEED + 1)
    perms = []
    for _ in range(N_PERM):
        m = dict(zip(uc, rp.permutation([lab[c] for c in uc])))
        yp = np.array([m[c] for c in case])
        r = np.random.default_rng(SEED)
        perms.append({k: _abs_auc(v, yp, case, r) for k, v in col.items()})
    null_theta = np.array([p["coherence_theta"] for p in perms], float)
    p_theta = float(np.mean(null_theta >= obs["coherence_theta"]))
    m1 = p_theta < 0.05
    print(f"\nM1 aliveness: coherence_theta {obs['coherence_theta']:.4f} vs its own null "
          f"(mean {np.nanmean(null_theta):.4f}, p95 {np.nanquantile(null_theta, .95):.4f}), "
          f"p = {p_theta:.3f}   {'PASS' if m1 else 'FAIL'}")

    res = {"n_windows": int(len(idx)), "n_cases": int(len(uc)), "abs_auc": obs,
           "m1_theta_p": p_theta, "gate_m1": bool(m1)}
    if not m1:
        verdict = (f"NOT INFORMATIVE -- coherence_theta does not clear its own permutation null "
                   f"(p = {p_theta:.3f}), so it carries no agent information for the differential to be "
                   f"about. A theta-minus-alpha difference would be a difference of two nulls. Rule 53, "
                   f"and this is what a two-electrode strip on a shared reference can resolve.")
        print(f"\nVERDICT: {verdict}")
        res["verdict"] = verdict
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    def stat(i):
        yy, cc = y[i], case[i]
        if len(np.unique(yy)) < 2:
            return float("nan")
        r = np.random.default_rng(SEED)
        return _abs_auc(col["coherence_theta"][i], yy, cc, r) - _abs_auc(col["coherence_alpha"][i], yy, cc, r)

    point = obs["coherence_theta"] - obs["coherence_alpha"]
    lo, hi, nrep = cluster_bootstrap_ci(stat, case, rng, reps=REPS)
    plac = float(np.nanmean([p["coherence_theta"] - p["coherence_alpha"] for p in perms]))
    s1 = obs["wpli_theta"] - obs["wpli_alpha"]
    print(f"\nPRIMARY  |AUC-0.5| theta minus alpha (coherence) = {point:+.4f} [{lo:+.4f}, {hi:+.4f}] "
          f"({nrep} draws; positive = Akeju's direction)")
    print(f"PLACEBO  same differential, agent permuted        = {plac:+.4f}")
    print(f"S1       the same on wPLI (reported, not gated)   = {s1:+.4f}")

    if not np.isfinite(lo):
        verdict = "ABSENT -- the bootstrap could not form an interval."
    elif hi < 0:
        verdict = ("REVERSED -- ALPHA coherence separates the drugs more than theta, the opposite of "
                   "Akeju's report. Either the finding does not transfer to a two-electrode strip or the "
                   "band structure is different here.")
    elif lo <= 0:
        verdict = ("NOT REPLICATED -- the differential includes zero. Akeju's theta signature does not "
                   "produce a detectable band difference on a two-channel BIS strip. Given the montage "
                   "this is the expected outcome and it is NOT evidence against Akeju; it is evidence "
                   "about what this deposit can resolve.")
    elif plac >= point:
        verdict = ("NOT INFORMATIVE -- permuting the agent across cases reproduces the differential, so "
                   "the folded statistic's null level is doing the work.")
    else:
        verdict = ("REPLICATED -- Akeju's theta-over-alpha coherence differential survives on an "
                   "independent deposit with a far poorer montage, which makes it robust in a way the "
                   "original could not show. This is NOT a Challenge A pass: the agents sit in disjoint "
                   "patients, so the leak cannot be attributed to pharmacology.")
    print(f"\nVERDICT: {verdict}")
    res.update({"primary": {"point": point, "lo": lo, "hi": hi, "reps": nrep},
                "placebo": plac, "s1_wpli_differential": s1, "verdict": verdict})
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
