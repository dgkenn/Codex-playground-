"""E113 -- Is E109's age effect actually an AGENT effect? An audit of a result already reported.

REGISTERED BEFORE THE CONFOUND IS MEASURED. Existing tables only. This experiment exists because E110 and
E112 produced a fact that E109 could not have known and that threatens it directly.

=========================================================================================================
WHY THIS HAD TO BE RUN
=========================================================================================================
E109 reported a positive: within-case agreement between BIS and the aperiodic exponent DEGRADES with age,
+0.2592 [+0.1367, +0.3761] over 240 cases, surviving both attenuation routes, not paediatric, outside its
placebo. It was checked against range restriction, sample size, SQI, EMG and paediatric composition.

**It was not checked against anaesthetic agent, because at the time nobody knew agent mattered.** Two
experiments later it manifestly does:

    E110  the exponent's fidelity to the drug is +0.2837 under volatile agents and **-0.0382 under
          propofol** -- on the same deposit, same pipeline, same statistic.
    E112  the blindness is largely a FIT-RANGE artefact: a 20-40 Hz slope recovers propofol sensitivity
          (+0.0865, interaction +0.4025) while the 1-40 Hz version does not.

So the exponent behaves like a different measure depending on the agent. **If older patients receive a
different agent mix -- which is clinically plausible in either direction, since frailty pushes toward TIVA
in some practices and away from it in others -- then E109's "age" gradient could be an agent gradient
wearing an age label.** Nothing in E109 excludes it, and a confound discovered after a result is still a
confound (error catalogue A1: a correction propagates to everything downstream).

=========================================================================================================
ESTIMAND
=========================================================================================================
Per case, exactly as E109 computed it: `agree_c = spearman(meta_bis, whole_head_exponent)` within case
across windows, negative when the two track each other.

    P1  THE CONFOUND'S PRECONDITION. spearman(agent class, age) across cases, where agent class is
        1 for TIVA-dominant and 0 for volatile-dominant. **If this is null, no agent effect can explain
        E109 and the audit ends there with E109 intact.** Reported first because it is the cheapest way
        the audit can conclude.

    P2  THE ADJUSTED ESTIMATE. E109's primary re-run as a partial correlation given agent class, on the
        SAME cases E109 used, plus E109's own three attenuation covariates so the comparison is like for
        like. **If E109's +0.2592 survives adjustment, it is not an agent effect.**

    P3  THE WITHIN-AGENT ESTIMATE, which is the stronger form. E109's primary re-run SEPARATELY inside the
        volatile cases and inside the TIVA cases. An effect present in both, at similar size, cannot be
        agent composition -- there is no composition left to vary. Rule 29: a contrast between A and
        not-A must be decomposed INSIDE not-A.

VERDICT, wrong direction FIRST (rule 37) -- and here the wrong direction is the one that costs us a
reported result, which is exactly why it is named first:

    (a) P2's interval INCLUDES 0 while P1 shows a real age-agent association -> **E109 IS AN AGENT
        EFFECT.** The reported positive must be withdrawn and re-described as agent composition.
    (b) P2 survives but P3 splits -- present in one agent class and absent in the other -> PARTIAL. The
        effect is real within one class and the pooled estimate overstates its generality.
    (c) P1 null -> NOT CONFOUNDED BY AGENT. The precondition for the confound does not hold.
    (d) P2 survives and P3 holds in BOTH classes -> E109 SURVIVES, and more strongly than before, because
        an agent-composition explanation has been excluded by two independent routes.

PREDICTED: (d) at ~45 %, (c) at ~30 %, (b) at ~20 %, (a) at ~5 %.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 40 cases in EACH agent class with >= 10 windows, else P3 is not computable and the
        audit rests on P2 alone -- which is weaker and must be said.
    G2  AGENT CLASS MUST BE ASSIGNABLE AND MUST NOT BE A THIRD THING. A case is TIVA-dominant if it
        carries propofol effect-site concentration and no meaningful volatile exposure, volatile-dominant
        if the reverse, and is DROPPED if both or neither. The dropped count is reported: if most cases
        are mixed, "agent class" is not a variable and the audit cannot proceed as designed.
    G3  E109 MUST REPRODUCE ON THIS CASE SET. The unadjusted primary is recomputed here on whatever
        subset survives G2, and must reproduce E109's +0.2592 with an interval excluding zero. **If it
        does not, the audit is comparing against a different result and reports ABSENT** (rule 31) --
        a partial that "kills" an effect which was not there on this subset proves nothing.

PLACEBO: age shuffled across cases, 2000 draws, applied to P2. Primary read FIRST (rule 48).

SCOPE. VitalDB, single-channel BIS-module EEG. Agent class here is an EXPOSURE label derived from recorded
concentrations, not a randomised assignment; patients are not assigned to agents at random and any residual
difference between the classes travels with this analysis. Nothing here concerns consciousness.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e113_is_e109_an_agent_effect.json")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
TABLES = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))

MIN_WINDOWS, MIN_PER_CLASS = 10, 40
E109_POINT = 0.2592
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rank(x):
    return np.argsort(np.argsort(np.asarray(x, float))).astype(float)


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 0 or np.ptp(y[ok]) <= 0:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def partial_spearman(x, y, Z):
    x, y, Z = np.asarray(x, float), np.asarray(y, float), np.asarray(Z, float)
    ok = np.isfinite(x) & np.isfinite(y) & np.all(np.isfinite(Z), axis=1)
    if ok.sum() < Z.shape[1] + 6:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    RZ = np.column_stack([np.ones(ok.sum())] + [_rank(Z[ok, j]) for j in range(Z.shape[1])])
    bx, *_ = np.linalg.lstsq(RZ, rx, rcond=None)
    by, *_ = np.linalg.lstsq(RZ, ry, rcond=None)
    ex, ey = rx - RZ @ bx, ry - RZ @ by
    d = float(np.sqrt((ex ** 2).sum() * (ey ** 2).sum()))
    return float((ex * ey).sum() / d) if d > 1e-12 else float("nan")


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def main() -> int:
    if not os.path.exists(AGENTS) or not any(os.path.exists(t) for t in TABLES):
        print("ABSENT: missing input tables")
        return 2

    # agent exposure per case, from the recorded tracks only
    expo = defaultdict(lambda: {"ppf": 0, "vol": 0, "n": 0})
    for r in csv.DictReader(open(AGENTS, newline="")):
        c = r.get("caseid")
        if not c:
            continue
        p, m = _f(r.get("ppf_ce")), _f(r.get("mac"))
        expo[c]["n"] += 1
        if math.isfinite(p) and p > 0:
            expo[c]["ppf"] += 1
        if math.isfinite(m) and m > 0:
            expo[c]["vol"] += 1

    per = defaultdict(list)
    seen = set()
    for tb in TABLES:
        if not os.path.exists(tb):
            continue
        for r in csv.DictReader(open(tb, newline="")):
            c, t = r.get("meta_caseid"), _f(r.get("meta_t_s"))
            b, e, a = _f(r.get("meta_bis")), _f(r.get("whole_head_exponent")), _f(r.get("meta_age"))
            if not c or not (math.isfinite(b) and b > 0 and math.isfinite(e) and math.isfinite(a)):
                continue
            key = (c, round(t, 1) if math.isfinite(t) else len(per[c]))
            if key in seen:
                continue
            seen.add(key)
            per[c].append((b, e, a))

    cases, agree, age, cls, sd_b, sd_e, nwin = [], [], [], [], [], [], []
    dropped_mixed = 0
    for c, v in per.items():
        b = np.array([x[0] for x in v], float)
        e = np.array([x[1] for x in v], float)
        if b.size < MIN_WINDOWS or np.ptp(b) <= 0 or np.ptp(e) <= 0:
            continue
        rho = spearman(b, e)
        if not np.isfinite(rho):
            continue
        ex = expo.get(c)
        if not ex or ex["n"] == 0:
            dropped_mixed += 1
            continue
        fp, fv = ex["ppf"] / ex["n"], ex["vol"] / ex["n"]
        # G2: dominant means present in a clear majority of that case's agent rows and the other absent
        if fp >= 0.5 and fv < 0.1:
            k = 1
        elif fv >= 0.5 and fp < 0.1:
            k = 0
        else:
            dropped_mixed += 1
            continue
        cases.append(c); agree.append(rho); age.append(v[0][2]); cls.append(k)
        sd_b.append(float(b.std())); sd_e.append(float(e.std())); nwin.append(int(b.size))

    agree = np.array(agree); age = np.array(age); cls = np.array(cls, float)
    Zatt = np.column_stack([sd_b, sd_e, np.log(np.asarray(nwin, float))]) if cases else None
    res = {"n_cases": len(cases), "n_dropped_mixed_or_unassignable": dropped_mixed,
           "n_tiva": int((cls == 1).sum()), "n_volatile": int((cls == 0).sum()), "gates": {}}
    print(f"{len(per)} cases in the grid; {len(cases)} assignable to a single agent class "
          f"({int((cls==1).sum())} TIVA, {int((cls==0).sum())} volatile); "
          f"{dropped_mixed} dropped as mixed or unassignable")
    res["gates"]["G1_pass"] = bool((cls == 1).sum() >= MIN_PER_CLASS
                                   and (cls == 0).sum() >= MIN_PER_CLASS)
    res["gates"]["G2_pass"] = bool(len(cases) >= 2 * MIN_PER_CLASS)
    print(f"G1 per-class  {'PASS' if res['gates']['G1_pass'] else 'FAIL -- P3 not computable'}")

    rng = np.random.default_rng(SEED)
    n = len(cases)
    if n < 20:
        res["verdict"] = "ABSENT -- too few assignable cases to audit anything."
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # G3 -- E109 must reproduce on this subset
    unadj = spearman(agree, age)
    u_lo, u_hi = ci([spearman(agree[i], age[i])
                     for i in (rng.integers(0, n, n) for _ in range(REPS))])
    g3 = bool(np.isfinite(u_lo) and u_lo > 0)
    res["gates"]["G3"] = {"unadjusted": unadj, "lo": u_lo, "hi": u_hi, "e109": E109_POINT, "pass": g3}
    print(f"G3 reproduce  E109's primary on THIS subset: {unadj:+.4f} [{u_lo:+.4f}, {u_hi:+.4f}]  "
          f"(E109 reported {E109_POINT:+.4f})  {'PASS' if g3 else 'FAIL'}")
    if not g3:
        res["verdict"] = ("ABSENT -- E109's effect does not reproduce on the agent-assignable subset, so "
                          "any adjustment here would be adjusting something that is not there (rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # P1 -- the confound's precondition
    p1 = spearman(cls, age)
    p1_lo, p1_hi = ci([spearman(cls[i], age[i])
                       for i in (rng.integers(0, n, n) for _ in range(REPS))])
    p1_real = bool(np.isfinite(p1_lo) and not (p1_lo <= 0.0 <= p1_hi))
    res["P1"] = {"rho_agentclass_age": p1, "lo": p1_lo, "hi": p1_hi, "association_present": p1_real}
    print(f"\nP1 precondition  spearman(TIVA-dominant, age) = {p1:+.4f} [{p1_lo:+.4f}, {p1_hi:+.4f}]  "
          f"{'agent mix DOES vary with age' if p1_real else 'no age-agent association'}")

    # P2 -- adjusted
    Z = np.column_stack([cls, Zatt])
    p2 = partial_spearman(agree, age, Z)
    p2_lo, p2_hi = ci([partial_spearman(agree[i], age[i], Z[i])
                       for i in (rng.integers(0, n, n) for _ in range(REPS))])
    pl = [partial_spearman(agree, age[rng.permutation(n)], Z) for _ in range(PLACEBO_DRAWS)]
    pl_lo, pl_hi = ci(pl)
    p2_inside = bool(np.isfinite(pl_lo) and pl_lo <= p2 <= pl_hi)
    p2_survives = bool(np.isfinite(p2_lo) and p2_lo > 0 and not p2_inside)
    res["P2"] = {"partial": p2, "lo": p2_lo, "hi": p2_hi, "placebo": [pl_lo, pl_hi],
                 "inside_placebo": p2_inside, "survives": p2_survives}
    print(f"P2 adjusted      partial given agent class + E109's 3 attenuation covariates: "
          f"{p2:+.4f} [{p2_lo:+.4f}, {p2_hi:+.4f}]")
    print(f"                 placebo (age shuffled) [{pl_lo:+.4f}, {pl_hi:+.4f}]  "
          f"{'INSIDE' if p2_inside else 'outside'}")

    # P3 -- within agent class
    res["P3"] = {}
    holds = {}
    for k, nm in ((0, "volatile"), (1, "tiva")):
        m = cls == k
        if m.sum() < 15:
            print(f"P3 {nm:<9s} only {int(m.sum())} cases -- not computable")
            res["P3"][nm] = {"n": int(m.sum())}
            holds[nm] = None
            continue
        v = spearman(agree[m], age[m])
        lo, hi = ci([spearman(agree[m][i], age[m][i])
                     for i in (rng.integers(0, int(m.sum()), int(m.sum())) for _ in range(REPS))])
        res["P3"][nm] = {"rho": v, "lo": lo, "hi": hi, "n": int(m.sum())}
        holds[nm] = bool(np.isfinite(lo) and lo > 0)
        print(f"P3 {nm:<9s} {v:+.4f} [{lo:+.4f}, {hi:+.4f}]  over {int(m.sum())} cases  "
              f"{'holds' if holds[nm] else 'does not hold'}")

    both = [v for v in holds.values() if v is not None]
    if not p1_real:
        v = (f"NOT CONFOUNDED BY AGENT -- the precondition fails. Agent class and age are not associated "
             f"({p1:+.4f} [{p1_lo:+.4f}, {p1_hi:+.4f}]), so no agent-composition difference can generate "
             f"an age gradient. E109 stands as reported, and the cheapest branch of the audit is the one "
             f"that settled it.")
    elif not p2_survives:
        v = (f"**E109 IS AN AGENT EFFECT -- the reported positive is WITHDRAWN.** Agent class varies with "
             f"age ({p1:+.4f}) and E109's gradient does not survive adjustment for it "
             f"({p2:+.4f} [{p2_lo:+.4f}, {p2_hi:+.4f}]). What was described as a discordance growing with "
             f"age is agent composition: the exponent is nearly blind to propofol (E110, E112) and the "
             f"age groups differ in how much propofol they receive.")
    elif len(both) == 2 and all(both):
        v = (f"E109 SURVIVES, AND MORE STRONGLY THAN BEFORE. Agent class does vary with age ({p1:+.4f}), "
             f"so the confound was real to check -- and the gradient survives adjustment for it "
             f"({p2:+.4f} [{p2_lo:+.4f}, {p2_hi:+.4f}]) AND appears separately inside both agent classes, "
             f"where there is no composition left to vary (rule 29). Two independent routes exclude the "
             f"agent-composition explanation.")
    elif len(both) == 2 and any(both):
        present = [k for k, val in holds.items() if val]
        v = (f"PARTIAL -- E109's gradient survives pooled adjustment ({p2:+.4f} [{p2_lo:+.4f}, "
             f"{p2_hi:+.4f}]) but appears only in the {present} arm within class. The pooled estimate "
             f"overstates its generality and E109 must be re-described as agent-specific.")
    else:
        v = (f"E109 SURVIVES ADJUSTMENT ({p2:+.4f} [{p2_lo:+.4f}, {p2_hi:+.4f}]) but the within-class "
             f"decomposition was not computable in both arms, so the stronger form of the audit is "
             f"unavailable and the pooled adjustment carries the claim alone.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
