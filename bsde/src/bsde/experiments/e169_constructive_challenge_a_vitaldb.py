#!/usr/bin/env python3
"""E169 — the constructive Challenge A test on a cohort where the problem actually exists.

REGISTERED BEFORE ANY WEIGHT VECTOR HAS BEEN FITTED ON THIS COHORT.

=========================================================================================================
WHY THIS COHORT AND NOT E165/E168'S
=========================================================================================================
E165 asked the constructive question — is there a linear combination of the amplitude family that keeps
the state axis while giving up the anaesthetic? — on the MGH OR cases, and E168 supplied the null its
verdict needed. On that cohort the **lam = 0 state axis's agent legibility is already at its permutation
floor**, so no adversarial pressure was ever required and the design could not speak to whether pressure
works. E168 enumerated that outcome in advance as VACUOUS and named the reason: the MGH agent contrast is
**27 pure-propofol against 16 MIXED-agent cases**, not one drug against another.

**VitalDB has the contrast MGH lacks and E161 measured the leakage there directly**: 115 clean single-agent
cases (44 propofol alone, 71 sevoflurane alone) with seven of ten features separating the agents against a
cluster-level null — `lempel_ziv` 0.3266, `relative_theta_power` 0.3263, `alpha_peak_hz` 0.2990,
`exponent_low` 0.2559, `whole_head_exponent` 0.2265, `relative_alpha_power` 0.1994, `spectral_edge_95`
0.1690. So the nuisance is alive here, which is the precondition E168's cohort failed.

This is a cohort change, not a threshold change, and it is the move E168's registered VACUOUS branch
prescribes in writing — not a re-run of a failed test with a friendlier setting (rule 58).

=========================================================================================================
WHAT VITALDB CANNOT SUPPLY, AND WHAT REPLACES IT
=========================================================================================================
**VitalDB has no awake baseline.** Measured, not assumed: across 6,437 windows from 250 cases, ZERO fall
before `anestart`; the earliest is +0.0 min, the median +100.3 min, and 0 of 250 cases contribute a
pre-anaesthesia window. So the conscious-versus-unconscious contrast E165 used does not exist here, and
BIS cannot substitute because it is computed from the same EEG.

The state axis is therefore **DEPTH WITHIN THE ANAESTHETISED RANGE, anchored on administered exposure and
nothing else**: per case, the median feature vector over that case's own DEEPEST exposure tercile against
its own LIGHTEST. Exposure is `mac` for sevoflurane cases and `ppf_ce` for propofol cases, **ranked within
case**, so the two agents' incommensurable units are never compared to each other — only each case's
windows to that case's other windows. `vitaldb_agents.csv` joins to the probe table on `recording_id` at
6,437 of 6,437 rows, so no window is lost to the join.

This is a weaker state axis than consciousness and it is the RIGHT one for the anaesthesia wedge: a depth
monitor's job is to track depth within anaesthesia, which is where BIS is used and where E60 found its
target band.

=========================================================================================================
THE CONFOUND THAT MUST HAVE A LINE OF CODE, NOT A CAVEAT (rule 54)
=========================================================================================================
Within a case, deep windows and light windows are not distributed evenly in time — induction and emergence
sit at the ends. A projection that tracks the CLOCK would score as a state axis for free. This is rule 64's
before/after-an-extremum failure in another guise.

Two things are done about it, both in code:
  * the mean within-case time position of the DEEP set and the LIGHT set is reported, and
  * **PLACEBO: the identical pipeline is run with each case split by TIME instead of by exposure**, first
    tercile against last, group sizes and every other choice preserved. If the time split reproduces the
    state axis, the exposure split is a clock and the state axis is withdrawn. This GATES the verdict.

=========================================================================================================
GATES
=========================================================================================================
G1  MANIFEST >= 40 cases per agent arm with >= 9 usable windows (three per tercile).
G2  **THE TWO NULLS AGREE AT lam = 0** — the full-pipeline agent permutation must reproduce the exactly
    computable lam = 0 null, where the fit never sees the label. Can fail; nothing is reported if it does.
G3  **THE FLOOR, per lambda**, as the 95th percentile of the case-level agent-label permutation pushed
    through fit and score, with its Monte Carlo error printed beside it (rule 46).
G4  **THE STATE AXIS IS ALIVE** against a within-case deep/light flip — the destruction matched to a
    paired estimand (rule 55).
G5  **THE NUISANCE IS ALIVE, AND THIS IS THE GATE E168 DID NOT HAVE.** The lam = 0 agent legibility must
    EXCEED its own permutation floor. If the state axis does not leak the agent to begin with, there is
    nothing for an adversarial term to remove and the experiment cannot answer its own question. Rule 53
    applied to the nuisance rather than to the signal.

=========================================================================================================
VERDICT — UNINFORMATIVE AND WRONG-DIRECTION CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G2 or G4 fails.
  (2) VACUOUS            G5 fails: no leakage to remove, same outcome as E168 and the constructive
                         programme has no reachable cohort at all.
  (3) CLOCK              the time-split placebo reproduces the state axis (>= 80 % of it). The state axis
                         is position in the case, the exposure anchor did no work, and nothing is claimed.
  (4) ENTANGLED          no lambda gives BOTH state legibility >= 80 % of the lam = 0 axis AND agent
                         legibility at or below that lambda's floor.
  (5) SEPARABLE          some lambda gives both — the first constructed Challenge A candidate.

REGISTERED PREDICTION: **(4) ENTANGLED**, for E161's reason — the features that leak the agent most
(`lempel_ziv`, `relative_theta_power`) are also strong depth discriminators, which is the signature of one
axis serving both rather than a nuisance direction that can be projected away. The prediction is against
the hope that motivates the file, which is the correct way round.

SCOPE. Linear combinations, one deposit, spectra plus one connectivity column, two agents, depth within
anaesthesia rather than consciousness. A negative bounds the linear case in this family; it says nothing
about non-linear representations or about families this deposit lacks.

POST-REGISTRATION NOTE, ADDED BEFORE THE FIRST RUN AND BEFORE ANY VALUE WAS READ. The scope line above
says "spectra plus one connectivity column". **There is no connectivity column.** `wpli_alpha` is
0-of-3,043 finite in the agentprobe shards -- the same all-NaN column E157 scored at p = 0.0000 before
`screen_candidates` existed -- so the feature list is screened at import and the run works on TEN spectral
measures. The first version required every feature finite in both the deep and light blocks WITHOUT
screening, which emptied the cohort to zero cases and read as "no eligible cases" rather than as a dead
column (rules 5, 14, 74). The scope sentence is left as registered and corrected here rather than
rewritten.

    python bsde/src/bsde/experiments/e169_constructive_challenge_a_vitaldb.py [--perm N]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from e165_adversarial_challenge_a import fit_w, legibility, ranks                    # noqa: E402
from e161_vitaldb_replication_repaired import CANDIDATES, SHARDS, _f                 # noqa: E402
from e168_adversarial_with_permutation_floor import mc_error_p95                     # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e169_constructive_challenge_a_vitaldb.json")
SEED = 20260801

def _live_features():
    """E161's candidate list with dead columns dropped and NAMED (rules 14, 74).

    `wpli_alpha` is 0-of-3043 finite in the agentprobe shards -- the same all-NaN column that E157 scored
    at p = 0.0000 before `screen_candidates` existed. Requiring every feature finite in both the deep and
    light blocks without screening first emptied the cohort to ZERO cases, which is exactly the silent
    failure rule 5 warns about: the filter looked like an absence of eligible cases and was a dead column.
    """
    import csv as _csv
    import glob as _glob
    from bsde.verifier.stats import screen_candidates as _screen
    cols = {c: [] for c in CANDIDATES}
    for p_ in sorted(_glob.glob(SHARDS)):
        for r in _csv.DictReader(open(p_, newline="")):
            if r.get("status") != "ok":
                continue
            if (r.get("meta_agents_present") or "").strip() not in ("propofol", "sevoflurane"):
                continue
            for c in CANDIDATES:
                cols[c].append(_f(r.get(c, "")))
    usable, dropped = _screen(cols)
    for c, why in dropped.items():
        print(f"   dropped feature: {c} ({why})")
    return [c for c in CANDIDATES if c in usable]


FEATURES = _live_features()
LAMBDAS = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0)
MIN_PER_ARM = 40
MIN_WINDOWS = 9
STATE_TOL = 0.80
CLOCK_TOL = 0.80
N_PERM = 100
EXACT_DRAWS = 5000


def load(split="exposure"):
    """Per case: median feature vectors over the DEEP and LIGHT terciles, and the agent label.

    `split="time"` is the placebo: the same terciles taken on within-case TIME instead of exposure.
    """
    dose = {r["recording_id"]: r for r in csv.DictReader(open(AGENTS, newline=""))}
    rows = defaultdict(list)
    for p in sorted(glob.glob(SHARDS)):
        for r in csv.DictReader(open(p, newline="")):
            if r.get("status") != "ok":
                continue
            ag = (r.get("meta_agents_present") or "").strip()
            if ag not in ("propofol", "sevoflurane"):
                continue
            d = dose.get(r["recording_id"])
            if d is None:
                continue
            r["_exposure"] = _f(d["mac"]) if ag == "sevoflurane" else _f(d["ppf_ce"])
            rows[r["meta_caseid"]].append(r)

    cases = {}
    for c, rs in rows.items():
        rs.sort(key=lambda r: _f(r["meta_t_s"]))
        keep = [r for r in rs if math.isfinite(r["_exposure"])]
        if len(keep) < MIN_WINDOWS:
            continue
        n = len(keep)
        pos = {id(r): i / (n - 1.0) for i, r in enumerate(keep)}
        key = (lambda r: r["_exposure"]) if split == "exposure" else (lambda r: pos[id(r)])
        order = sorted(keep, key=key)
        k = max(3, n // 3)
        light, deep = order[:k], order[-k:]
        d = {"arm": 1 if rs[0]["meta_agents_present"] == "sevoflurane" else 0,
             "pos_deep": float(np.mean([pos[id(r)] for r in deep])),
             "pos_light": float(np.mean([pos[id(r)] for r in light])),
             "n_windows": n}
        ok = True
        for f in FEATURES:
            for tag, grp in (("deep", deep), ("light", light)):
                v = [_f(r.get(f, "")) for r in grp]
                v = [x for x in v if math.isfinite(x)]
                d[f"{tag}_{f}"] = float(np.median(v)) if v else float("nan")
                ok = ok and bool(v)
        if ok:
            cases[c] = d
    return cases


def evaluate(cases, ids, lam, arm_override, seed=0):
    """Leave-one-CASE-out held-out state (deep vs light) and agent legibility.

    Ranking is over the STACKED deep+light values and only then split, because ranking the two blocks
    separately standardises each to mean zero and annihilates the contrast the file is about -- the bug
    E165's capability gate caught (factor 77).
    """
    arm = np.asarray(arm_override, float)
    n = len(ids)
    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in FEATURES])
    D, L = both[:n], both[n:]
    Xs = np.vstack([D, L])
    ys = np.concatenate([np.full(n, 1.0), np.full(n, -1.0)])
    ya = (arm - arm.mean()) / (arm.std() + 1e-12)
    st, ag = np.full(2 * n, np.nan), np.full(n, np.nan)
    for i in range(n):
        tr = np.array([j for j in range(n) if j != i])
        trs = np.concatenate([tr, tr + n])
        # the agent is read off the DEEP block, matching E165: one summary per case, not two
        w = fit_w(Xs[trs], ys[trs], D[tr], ya[tr], lam, seed=seed)
        st[i], st[i + n] = D[i] @ w, L[i] @ w
        ag[i] = D[i] @ w
    state_lab = np.concatenate([np.ones(n), np.zeros(n)])
    return legibility(st, state_lab), legibility(ag, arm), st, ag


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perm", type=int, default=N_PERM)
    a = ap.parse_args(argv)
    rng = np.random.default_rng(SEED)

    cases = load("exposure")
    ids = sorted(cases)
    if not ids:
        print("ABSENT — no clean-arm cases with a dose join.")
        return 2
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n_sevo, n_prop = int(arm.sum()), int((1 - arm).sum())
    res = {"experiment": "E169", "n_cases": len(ids), "n_sevoflurane": n_sevo,
           "n_propofol": n_prop, "lambdas": list(LAMBDAS), "n_perm": a.perm,
           "features": FEATURES}
    g1 = n_sevo >= MIN_PER_ARM and n_prop >= MIN_PER_ARM
    res["G1_pass"] = bool(g1)
    print("E169 — constructive Challenge A on VitalDB: depth within anaesthesia versus agent identity")
    print(f"G1 MANIFEST  {len(ids)} clean-arm cases: {n_prop} propofol alone, {n_sevo} sevoflurane alone "
          f"(floor {MIN_PER_ARM} each)   {'PASS' if g1 else '*** FAIL'}")
    pd_, pl_ = np.mean([cases[c]["pos_deep"] for c in ids]), np.mean([cases[c]["pos_light"] for c in ids])
    res["time_position"] = {"deep": float(pd_), "light": float(pl_)}
    print(f"   mean within-case time position: DEEP {pd_:.3f}, LIGHT {pl_:.3f} "
          f"(0 = first window, 1 = last) — the placebo below is what actually tests this")
    if not g1:
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    print("\nOBSERVED")
    obs = {}
    for lam in LAMBDAS:
        t0 = time.time()
        s, g, st, ag = evaluate(cases, ids, lam, arm, seed=0)
        obs[lam] = {"state": float(s), "agent": float(g), "st": st, "ag": ag}
        print(f"   lam={lam:<4.1f} state {s:+.4f}   agent {g:+.4f}   ({time.time() - t0:.1f} s)")
    res["observed"] = {str(k): {"state": v["state"], "agent": v["agent"]} for k, v in obs.items()}

    # ---- G2 exact vs pipeline null at lam = 0
    ag0 = obs[0.0]["ag"]
    exact = np.asarray([legibility(ag0, rng.permutation(arm)) for _ in range(EXACT_DRAWS)])
    exact = exact[np.isfinite(exact)]
    ex_p95 = float(np.quantile(exact, 0.95))
    pipe0 = []
    for _ in range(a.perm):
        _, g, _, _ = evaluate(cases, ids, 0.0, rng.permutation(arm), seed=0)
        if math.isfinite(g):
            pipe0.append(g)
    pipe0 = np.asarray(pipe0)
    pi_p95, mc0 = float(np.quantile(pipe0, 0.95)), mc_error_p95(pipe0, rng=rng)
    agree = abs(pi_p95 - ex_p95) <= 3 * max(mc0, 1e-9)
    res["G2"] = {"exact_p95": ex_p95, "exact_mean": float(exact.mean()), "pipeline_p95": pi_p95,
                 "pipeline_mean": float(pipe0.mean()), "mc_sd": mc0, "pass": bool(agree)}
    print(f"\nG2 exact lam=0 null p95 {ex_p95:+.4f} (mean {exact.mean():+.4f}); "
          f"pipeline p95 {pi_p95:+.4f} (MC sd {mc0:.4f})   "
          f"{'PASS' if agree else '*** FAIL — the pipeline permutation is broken'}")

    # ---- G4 state axis alive
    st0 = obs[0.0]["st"]
    snull = []
    for _ in range(EXACT_DRAWS):
        flip = rng.integers(0, 2, len(ids)).astype(float)
        snull.append(legibility(st0, np.concatenate([flip, 1.0 - flip])))
    snull = np.asarray([s for s in snull if math.isfinite(s)])
    s_p95 = float(np.quantile(snull, 0.95))
    g4 = obs[0.0]["state"] > s_p95
    res["G4"] = {"state_lam0": obs[0.0]["state"], "floor_p95": s_p95, "pass": bool(g4)}
    print(f"G4 state axis alive: {obs[0.0]['state']:+.4f} vs within-case flip floor {s_p95:+.4f}   "
          f"{'PASS' if g4 else '*** FAIL'}")

    # ---- G5 the NUISANCE must be alive: this is the gate E168 did not have
    g5 = obs[0.0]["agent"] > pi_p95
    res["G5"] = {"agent_lam0": obs[0.0]["agent"], "floor_p95": pi_p95, "pass": bool(g5)}
    print(f"G5 nuisance alive:  agent {obs[0.0]['agent']:+.4f} vs its floor {pi_p95:+.4f}   "
          f"{'PASS — there is leakage to remove' if g5 else '*** FAIL — nothing to remove (VACUOUS)'}")

    if not (agree and g4):
        res["verdict"], res["why"] = "NOT-INTERPRETABLE", "G2 or G4 failed"
        print("\nVERDICT NOT INTERPRETABLE — G2 or G4 failed")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1
    if not g5:
        res["verdict"] = "VACUOUS"
        res["why"] = ("the lam = 0 axis does not leak the agent above its own floor, so there is nothing "
                      "for an adversarial term to remove — the same outcome as E168 and, on the only two "
                      "reachable cohorts, the constructive question cannot be posed at all")
        print("\nVERDICT VACUOUS — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    # ---- PLACEBO: split by TIME instead of exposure, and it gates the verdict
    print("\nPLACEBO — the identical pipeline with each case split by TIME instead of exposure")
    tcases = load("time")
    tids = [c for c in ids if c in tcases]
    ts, tg, _, _ = evaluate(tcases, tids, 0.0, np.array([tcases[c]["arm"] for c in tids], float), seed=0)
    clock = np.isfinite(ts) and ts >= CLOCK_TOL * obs[0.0]["state"]
    res["placebo_time_split"] = {"state": float(ts), "agent": float(tg), "n_cases": len(tids),
                                 "reproduces": bool(clock)}
    print(f"   time-split state {ts:+.4f} against exposure-split {obs[0.0]['state']:+.4f} "
          f"({len(tids)} cases)   {'*** REPRODUCES — the axis is a clock' if clock else 'does not reproduce'}")
    if clock:
        res["verdict"] = "CLOCK"
        res["why"] = ("splitting each case by time reproduces at least 80 % of the state axis, so the "
                      "exposure anchor did no work and the axis is position in the case")
        print("\nVERDICT CLOCK — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    # ---- G3 floor per lambda, then the verdict
    print(f"\nG3 FLOOR per lambda, {a.perm} case-level permutations through fit AND score")
    floors = {0.0: {"p95": pi_p95, "mean": float(pipe0.mean()), "mc_sd": mc0, "n": int(pipe0.size)}}
    for lam in LAMBDAS:
        if lam == 0.0:
            continue
        draws = []
        for _ in range(a.perm):
            _, g, _, _ = evaluate(cases, ids, lam, rng.permutation(arm), seed=0)
            if math.isfinite(g):
                draws.append(g)
        d = np.asarray(draws)
        floors[lam] = {"p95": float(np.quantile(d, 0.95)), "mean": float(d.mean()),
                       "mc_sd": mc_error_p95(d, rng=rng), "n": int(d.size)}
        print(f"   lam={lam:<4.1f} floor p95 {floors[lam]['p95']:+.4f} "
              f"(mean {floors[lam]['mean']:+.4f}, MC sd {floors[lam]['mc_sd']:.4f}, {d.size} draws)")
    res["floors"] = {str(k): v for k, v in floors.items()}

    s0, sep, rows_out = obs[0.0]["state"], [], []
    print(f"\n{'lam':>5s} {'state':>9s} {'>=80% lam0':>11s} {'agent':>9s} {'floor':>9s} {'at floor':>9s}")
    for lam in LAMBDAS:
        st_ok = obs[lam]["state"] >= STATE_TOL * s0
        ag_ok = obs[lam]["agent"] <= floors[lam]["p95"]
        rows_out.append({"lam": lam, "state": obs[lam]["state"], "state_ok": bool(st_ok),
                         "agent": obs[lam]["agent"], "floor": floors[lam]["p95"],
                         "agent_ok": bool(ag_ok)})
        if st_ok and ag_ok:
            sep.append(lam)
        print(f"{lam:>5.1f} {obs[lam]['state']:>+9.4f} {str(st_ok):>11s} {obs[lam]['agent']:>+9.4f} "
              f"{floors[lam]['p95']:>+9.4f} {str(ag_ok):>9s}")
    res["rows"] = rows_out
    if sep:
        res["verdict"] = "SEPARABLE"
        res["why"] = (f"lambda in {sep} keeps >= {STATE_TOL:.0%} of the depth axis with agent legibility "
                      "at its own permutation floor; the first constructed Challenge A candidate, and it "
                      "must now be tested for depth tracking against BIS before it is called anything")
    else:
        res["verdict"] = "ENTANGLED"
        res["why"] = ("no lambda keeps 80 % of the depth axis while reaching its own floor: depth and "
                      "agent identity are entangled in the linear span of this feature family")
    res["separable_lambdas"] = sep
    print(f"\nVERDICT {res['verdict']} — {res['why']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
