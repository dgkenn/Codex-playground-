#!/usr/bin/env python3
"""E185 — E161's conclusion is about the AMPLITUDE family by construction. Does anything else leak less?

REGISTERED BEFORE ANY AGENT LEGIBILITY OF A NON-AMPLITUDE MEASURE HAS BEEN COMPUTED ON THIS COHORT.

=========================================================================================================
THE GAP, AND WHY IT IS STRUCTURAL RATHER THAN AN OVERSIGHT
=========================================================================================================
Every Challenge A screen this project has run on VitalDB used the same ten measures — relative band
powers, aperiodic exponents, spectral edge, spectral entropy, Lempel-Ziv, alpha peak frequency. E161's
headline is that **seven of ten separate the anaesthetics against a cluster-level null**, and E176 measured
non-parametric agent legibility over that whole set at **+0.4593 against a floor of +0.1444**.

**That is a statement about the amplitude family, and it is a statement about the only family that was
looked at.** E168 and E169's constructive tests, and E182's matched-strength control, are all built on the
same ten columns. If the leakage is a property of amplitude summaries specifically, a different family
might carry depth without carrying the drug — and the constructive programme has never checked.

`vitaldb_agentprobe.s*.csv` ships columns from three other families. **Four of eight are dead** and are
named rather than silently dropped (rules 14, 74): `lrtc_alpha`, `icoh_alpha`,
`spatial_participation_ratio` and `uce_v1` are each 0-of-3,043 finite. What survives is three measures that
are not amplitude summaries — a temporal-autocorrelation measure, a complexity measure and a
phase-amplitude coupling measure — plus one that is.

=========================================================================================================
THE TWO FAMILIES, AND THE AMBIGUOUS MEMBER IS ASSIGNED AGAINST THE FAVOURED STORY (rule 47)
=========================================================================================================
    AMPLITUDE          the ten E161/E169 measures, PLUS `exponent_gamma`. An aperiodic slope in the gamma
                       band is a spectral summary, so it belongs here — and it is the one column whose
                       assignment could be argued either way. **It is assigned to the family this file
                       hopes will look worse**, which is what rule 47 requires of a partition drawn by the
                       person testing it.
    PHASE/COMPLEXITY   `critical_slowing_ar1`, `multiscale_entropy_slope`, `pac_slow_alpha`.

Three members is thin and is stated as the scope limit it is. It is what the deposit supplies.

=========================================================================================================
RULE 60, RUN BEFORE THE PRIMARY AND ABLE TO VOID IT
=========================================================================================================
A measure chosen for belonging to a different family must be SHOWN to differ from that family. E73 named
`wpli_alpha_global_efficiency` a network measure and it correlated **+0.9962** with mean degree, so the
"network" test was a re-run of the connectivity test.

**G3 correlates each PHASE/COMPLEXITY measure against every AMPLITUDE measure, on the same case summaries
the primary uses.** Any member whose maximum absolute correlation exceeds `FAMILY_MAX_CORR` is **not a
member of a different family** and is excluded from the primary with its correlation printed. If fewer
than `MIN_PER_FAMILY` survive, the file reports NOT A DIFFERENT FAMILY and no comparison is made.

=========================================================================================================
GATES
=========================================================================================================
G1  E169's cohort: >= 40 cases per agent arm.
G2  **ALIVENESS PER FEATURE.** A measure that does not track depth is not a Challenge A candidate, and its
    low agent legibility would be meaningless (rule 53, and E182's whole lesson). Each feature's
    deep-versus-light legibility is measured against a within-case flip floor, and only ALIVE features
    enter the primary. At least `MIN_PER_FAMILY` alive per family or the comparison is NOT COMPARABLE.
G3  rule 60's escape check above.
G4  **THE NULL IS CLUSTER-LEVEL.** Every p comes from permuting the agent label across CASES, which is the
    unit the exposure varies at (rule 69, and E142's 178x inflation).

=========================================================================================================
PRIMARY, AND THE WRONG-DIRECTION BRANCH IS FIRST (rule 37)
=========================================================================================================
The **family gap**: mean agent legibility of the alive PHASE/COMPLEXITY members minus that of the alive
AMPLITUDE members, against the null distribution of the same gap under case-level agent-label permutation.

  (1) NOT INTERPRETABLE   G1, G2 or G3 fails.
  (2) NOT A DIFFERENT FAMILY  G3 leaves fewer than `MIN_PER_FAMILY` members that escape the amplitude
                          family. The question cannot be asked with these columns.
  (3) LEAKS MORE          the gap is positive and beyond the null's 95th percentile. The non-amplitude
                          family leaks MORE, which would be the opposite of this file's hypothesis and
                          would be reported as the finding.
  (4) NO DIFFERENCE       the gap sits inside its null. **Leakage is not a property of the amplitude
                          family in particular**, and Challenge A's problem is the deposit rather than the
                          feature choice — which is the registered prediction.
  (5) LEAKS LESS          the gap is negative and below the null's 5th percentile, with both families
                          alive for depth. Then a Challenge A representation should be built from
                          PHASE/COMPLEXITY measures and the constructive files should be re-run on them.

**REGISTERED PREDICTION: (4) NO DIFFERENCE.** The anaesthetics differ in what they do to the spectrum, and
a complexity or coupling measure computed from the same signal inherits that. E176 also showed the agent
information is spread through the feature space rather than concentrated on one direction. **The
prediction is against the hope that motivates the file**, which is the correct way round; and (5) would
redirect the whole constructive programme, so it is worth one run to find out.

SCOPE. One deposit, 115 cases, two agents, three non-amplitude measures, depth within anaesthesia. A null
bounds these three columns and says nothing about families the deposit does not ship — which, given four
of eight non-amplitude columns are entirely empty here, is most of them.

    python bsde/src/bsde/experiments/e185_non_amplitude_family_leakage.py
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import screen_candidates, spearman                      # noqa: E402
from e165_adversarial_challenge_a import legibility, ranks                       # noqa: E402
from e161_vitaldb_replication_repaired import SHARDS, _f                         # noqa: E402
from e169_constructive_challenge_a_vitaldb import (FEATURES as AMPLITUDE_BASE,   # noqa: E402
                                                   MIN_PER_ARM, MIN_WINDOWS)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e185_non_amplitude_family_leakage.json")
SEED = 20260801

AMPLITUDE = list(AMPLITUDE_BASE) + ["exponent_gamma"]     # the ambiguous member, assigned against us
PHASE_COMPLEXITY = ["critical_slowing_ar1", "multiscale_entropy_slope", "pac_slow_alpha"]
KNOWN_DEAD = ["lrtc_alpha", "icoh_alpha", "spatial_participation_ratio", "uce_v1"]
FAMILY_MAX_CORR = 0.90
MIN_PER_FAMILY = 3
PERMS = 5000


def load():
    """E169's cohort construction, extended to the extra columns."""
    dose = {r["recording_id"]: r for r in csv.DictReader(open(AGENTS, newline=""))}
    want = AMPLITUDE + PHASE_COMPLEXITY + KNOWN_DEAD
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

    pool = {c: [] for c in want}
    for rs in rows.values():
        for r in rs:
            for c in want:
                pool[c].append(_f(r.get(c, "")))
    usable, dropped = screen_candidates(pool)
    for c, why in sorted(dropped.items()):
        print(f"   dropped column: {c} ({why})")
    live = [c for c in want if c in usable]

    cases = {}
    for cid, rs in rows.items():
        rs.sort(key=lambda r: _f(r["meta_t_s"]))
        keep = [r for r in rs if math.isfinite(r["_exposure"])]
        if len(keep) < MIN_WINDOWS:
            continue
        order = sorted(keep, key=lambda r: r["_exposure"])
        k = max(3, len(keep) // 3)
        light, deep = order[:k], order[-k:]
        d = {"arm": 1 if rs[0]["meta_agents_present"] == "sevoflurane" else 0}
        ok = True
        for c in live:
            for tag, grp in (("deep", deep), ("light", light)):
                v = [_f(r.get(c, "")) for r in grp]
                v = [x for x in v if math.isfinite(x)]
                d[f"{tag}_{c}"] = float(np.median(v)) if v else float("nan")
                ok = ok and bool(v)
        if ok:
            cases[cid] = d
    return cases, live


def main() -> int:
    print("E185 — is the anaesthetic leakage a property of the AMPLITUDE family in particular?")
    cases, live = load()
    ids = sorted(cases)
    if not ids:
        print("ABSENT — no clean-arm cases.")
        return 2
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n = len(ids)
    amp = [c for c in AMPLITUDE if c in live]
    pc = [c for c in PHASE_COMPLEXITY if c in live]
    res = {"experiment": "E185", "n_cases": n, "n_sevoflurane": int(arm.sum()),
           "n_propofol": int(n - arm.sum()), "amplitude": amp, "phase_complexity": pc,
           "dead_columns": [c for c in KNOWN_DEAD if c not in live]}
    g1 = arm.sum() >= MIN_PER_ARM and (n - arm.sum()) >= MIN_PER_ARM
    print(f"G1 {n} cases: {int(n - arm.sum())} propofol alone, {int(arm.sum())} sevoflurane alone   "
          f"{'PASS' if g1 else '*** FAIL'}")
    print(f"   AMPLITUDE ({len(amp)}): {amp}")
    print(f"   PHASE/COMPLEXITY ({len(pc)}): {pc}")
    res["G1_pass"] = bool(g1)
    if not g1 or len(pc) < MIN_PER_FAMILY:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "cohort too small, or fewer than three non-amplitude columns survive the screen"
        print(f"\nVERDICT NOT INTERPRETABLE — {res['why']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # rank-standardise deep and light JOINTLY then split -- ranking the blocks separately annihilates the
    # contrast, which is the factor-77 bug E165's capability gate caught
    cols = amp + pc
    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in cols])
    D, L = both[:n], both[n:]
    state_lab = np.concatenate([np.ones(n), np.zeros(n)])
    rng = np.random.default_rng(SEED)

    # ---- G2 aliveness for depth, per feature
    print("\nG2 ALIVENESS FOR DEPTH (a measure that does not track depth is not a candidate)")
    flips = [rng.integers(0, 2, n).astype(float) for _ in range(2000)]
    alive, per = {}, {}
    for j, c in enumerate(cols):
        st = legibility(np.concatenate([D[:, j], L[:, j]]), state_lab)
        nul = [legibility(np.concatenate([D[:, j], L[:, j]]), np.concatenate([f, 1.0 - f]))
               for f in flips]
        nul = np.asarray([v for v in nul if math.isfinite(v)])
        p95 = float(np.quantile(nul, 0.95))
        ag = legibility(D[:, j], arm)
        alive[c] = bool(np.isfinite(st) and st > p95)
        per[c] = {"depth": float(st), "depth_floor_p95": p95, "agent": float(ag),
                  "alive": alive[c], "family": "amplitude" if c in amp else "phase_complexity"}
        print(f"   {c:<26s} depth {st:+.4f} (floor {p95:+.4f})  agent {ag:+.4f}   "
              f"{'ALIVE' if alive[c] else 'not alive'}")
    res["per_feature"] = per
    amp_alive = [c for c in amp if alive[c]]
    pc_alive = [c for c in pc if alive[c]]
    res["amplitude_alive"], res["phase_complexity_alive"] = amp_alive, pc_alive
    print(f"   alive: {len(amp_alive)} amplitude, {len(pc_alive)} phase/complexity")

    # ---- G3 rule 60: do the non-amplitude measures actually escape the amplitude family?
    print(f"\nG3 RULE 60 ESCAPE CHECK (max |rho| against the amplitude family, on the deep-block ranks)")
    escaped = []
    for c in pc:
        j = cols.index(c)
        best, who = 0.0, ""
        for c2 in amp:
            j2 = cols.index(c2)
            r = spearman(list(D[:, j]), list(D[:, j2]))
            if np.isfinite(r) and abs(r) > best:
                best, who = abs(r), c2
        per[c]["max_corr_with_amplitude"] = float(best)
        per[c]["max_corr_partner"] = who
        ok = best < FAMILY_MAX_CORR
        if ok:
            escaped.append(c)
        print(f"   {c:<26s} max |rho| {best:.4f} with {who:<24s} "
              f"{'escapes' if ok else '*** IS the amplitude family restated'}")
    res["escaped"] = escaped
    pc_use = [c for c in pc_alive if c in escaped]
    res["phase_complexity_used"] = pc_use
    if len(pc_use) < MIN_PER_FAMILY or len(amp_alive) < MIN_PER_FAMILY:
        res["verdict"] = "NOT-A-DIFFERENT-FAMILY" if len(pc_use) < MIN_PER_FAMILY else "NOT-COMPARABLE"
        res["why"] = (f"{len(pc_use)} non-amplitude measures are both alive for depth and escape the "
                      f"amplitude family, and {len(amp_alive)} amplitude measures are alive; "
                      f"at least {MIN_PER_FAMILY} of each are required")
        print(f"\nVERDICT {res['verdict']} — {res['why']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    # ---- primary: the family gap against a case-level agent-label permutation null
    def gap(a):
        ga = np.mean([legibility(D[:, cols.index(c)], a) for c in pc_use])
        gb = np.mean([legibility(D[:, cols.index(c)], a) for c in amp_alive])
        return float(ga - gb), float(ga), float(gb)

    obs, pc_mean, amp_mean = gap(arm)
    nulls = []
    for _ in range(PERMS):
        v, _, _ = gap(rng.permutation(arm))
        if math.isfinite(v):
            nulls.append(v)
    nl = np.asarray(nulls)
    lo, hi = float(np.quantile(nl, 0.05)), float(np.quantile(nl, 0.95))
    res["primary"] = {"gap": obs, "phase_complexity_mean_agent": pc_mean,
                      "amplitude_mean_agent": amp_mean, "null_p05": lo, "null_p95": hi,
                      "null_mean": float(nl.mean()), "n_null": int(nl.size),
                      "p_two_sided": float((np.abs(nl - nl.mean()) >= abs(obs - nl.mean())).mean())}
    print(f"\nPRIMARY  mean agent legibility: phase/complexity {pc_mean:+.4f}, amplitude {amp_mean:+.4f}")
    print(f"   family gap {obs:+.4f} against a case-permutation null of [{lo:+.4f}, {hi:+.4f}] "
          f"(mean {nl.mean():+.4f}, {nl.size} draws), two-sided p "
          f"{res['primary']['p_two_sided']:.4f}")

    if obs > hi:
        v, why = "LEAKS-MORE", ("the non-amplitude family leaks MORE than the amplitude family, which is "
                                "the opposite of this file's hypothesis and is the finding")
    elif obs < lo:
        v, why = "LEAKS-LESS", (f"{pc_use} leak less than {amp_alive} beyond the case-permutation null, "
                                "and both families track depth. A Challenge A representation should be "
                                "built from these and the constructive files re-run on them")
    else:
        v, why = "NO-DIFFERENCE", ("the family gap sits inside its own case-level permutation null: "
                                   "anaesthetic leakage is NOT a property of amplitude summaries in "
                                   "particular, so Challenge A's obstacle here is the deposit rather than "
                                   "the feature choice")
    res["verdict"], res["why"] = v, why
    print(f"\nVERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
