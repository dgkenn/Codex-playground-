#!/usr/bin/env python3
"""E342 -- is E321's dissociation reducible to a measure in its own inventory? Successor to E341.

PRE-REGISTRATION. Committed before any statistic in it exists.

WHAT WAS SEEN BEFORE THIS WAS WRITTEN, stated in full because a successor that hides its predecessor's
numbers is not a successor (rule 59). **E341 returned NOT INTERPRETABLE on G1** -- its planted reducible
column reached a measured pooled-z correlation of 0.7542 with `AvgDelta` against its own 0.90 bar, so the
detector was never shown able to detect a planted reduction and could not license a null. Its primaries
had already printed, so under rule 58 it was not repaired and re-run. The numbers seen, all UNLICENSED
and recorded in `results/e341_result_note.md`:

    P1 pooled-z co-linearity   NmlzCmplx / allEnvCorr  -0.8723      EffDim / allEnvCorr  -0.7921
                               NmlzCmplx / EffDim      +0.9588
    P2 state-profile match     three unrelated pairs at exactly 1.0000
    P3 after residualising on allEnvCorr, both dissociators kept (a) and (b) at p <= 0.0028,
       and criterion (c) was vacuous at n = 9

**Three things change, all of them instruments or defects, none of them a threshold, cohort or horizon
(rule 58).**

------------------------------------------------------------------------------------------------------
CHANGE 1 -- THE PROFILE INSTRUMENT IS RETIRED, NOT RECALIBRATED.

`scripts/krause_profile_calibration.py` measured what that statistic can reach before this file was
written (rule 63). Two facts kill it:

  * Only **6 of 8** profile states are finite for every measure, and a Spearman over k points is
    QUANTISED with resolution 6*2/(k(k^2-1)). At k = 6 the largest attainable value below 1.0000 is
    **0.9429**. There is nothing between 0.9429 and 1.0000, so **a bar of 0.95 is not a threshold, it is
    a synonym for "identical ordering"** -- E341 could not have set a bar that meant anything else.
  * Identical ordering is not rare here. It occurs in **6 of 136 pairs (4.4 %)** overall and in
    **2 of 105 (1.9 %)** among pairs whose pooled-z correlation is under 0.5 -- including
    `NmlzCmplx / frontalAlpha` at profile 1.0000 with pooled correlation only **-0.3861**. Two measures
    that agree observation-by-observation about a third of the time are not the same measure, and the
    instrument cannot tell that from identity.

An instrument whose only meaningful setting fires on 4.4 % of arbitrary pairs is measuring "both track
depth", which is true of nearly everything in a depth inventory. It is dropped rather than tuned, and the
calibration is reported so the drop is auditable.

**This also revises how one of this project's own results should be read**, and the revision is stated
here rather than left for a reader to find (rule 3): **E119** identified E116/E118's second axis as
`relative_alpha_power` on a stage-rank profile correlation of +1.0000 over **5** stages, where the
resolution is 0.1000 and +1.0000 likewise means only "identical ordering of five states". E119's
CONCLUSION is not withdrawn -- it rested independently on the VitalDB residualisation, where the inverted
U retained 20 % and 6.6 % of itself -- but its headline statistic is weaker than +1.0000 reads, and rule
68's prescription should name the residualisation, not the profile correlation.

CHANGE 2 -- P2 IS REPLACED BY A BEHAVIOURAL SUBSTITUTION TEST, WHICH NEEDS NO BAR AT ALL.

The decision E321 supports is "use a complexity measure to separate arousal from processing". The
question that matches that decision (rule 94: match the test to the decision, not to the parameter) is
not "how correlated are two columns" but **"does a power or connectivity measure already do the job?"**
So E342 simply runs E321's three criteria on EVERY measure in the inventory and reports who dissociates.
No threshold is chosen, because none is needed: either a competitor satisfies (a), (b) and (c) or it does
not, on the same nulls E321 used.

CHANGE 3 -- CRITERION (c) CAN NO LONGER BE SATISFIED BY MISSING DATA.

E341 scored (c) as passing whenever its p was NaN, which a 9-patient drug arm produced. That is rule 48:
a criterion a missing measurement satisfies. Here (c) has three states -- EXCLUDES ZERO / DOES NOT EXCLUDE
ZERO / **INSUFFICIENT** -- and a measure with INSUFFICIENT (c) is reported as `AROUSAL+REM ONLY`, never as
dissociating. Separately, the residualisation slope is fitted IN THE Z SPACE over the SLEEP states -- the
space the primary is computed in, so the residual is orthogonal to the competitor by construction -- and
APPLIED to every state including the drug blocks, so removing a competitor no longer costs drug-state
patients. On the drug blocks the removal is an EXTRAPOLATION of a slope fitted elsewhere, which is stated
here and reported beside G3 rather than assumed. (This mechanism is the one repair spent on E342, made
during `--smoke` before any real statistic existed; the first draft fitted the slope on raw row-level
values to buy the drug-state patients back and thereby reintroduced the aggregation mismatch E341's own
smoke had exposed, leaving |rho| = 0.35 and 0.22 with the column it was removing.)

------------------------------------------------------------------------------------------------------
FAMILY PARTITION -- carried over from E341 UNCHANGED, including the assignment made against the favoured
story (rule 47): `allEnvCorr` stays in CONNECTIVITY, where it is the measure most likely to overturn the
claim, and E341's unlicensed numbers confirm it is the near-miss for both dissociators.

  COMPLEXITY   NmlzCmplx, EffDim
  POWER        AvgDelta, AvgAlpha, AvgGamma, frontalDelta, frontalAlpha, temporalDelta, parietalDelta,
               limbicDelta, frontBias
  CONNECTIVITY allwPLI, frontwPLI, backwPLI, longwPLI, InsAwPLI, allEnvCorr

PRIMARIES.

P1  CO-LINEARITY. For each dissociator D, Pearson rho against every other measure over the pooled
    (patient, state) within-patient z. REDUCIBLE-BY-COLINEARITY if the maximum over POWER and
    CONNECTIVITY reaches 0.90. Bar carried over from E341 unchanged.

P2  BEHAVIOURAL SUBSTITUTION. E321's criteria (a) z(wake)-z(N3) excludes zero; (b) z(REM)-z(N3) excludes
    zero with the same sign; (c) z(drug-U)-z(N3) does NOT exclude zero -- run on all 17 measures with
    5,000-draw paired sign-flip nulls. REDUCIBLE-IN-EFFECT if any POWER or CONNECTIVITY measure
    dissociates on all three.

P3  RESIDUAL DISSOCIATION. Residualise each D on its strongest POWER/CONNECTIVITY competitor from P1,
    within patient, fitting on sleep blocks and applying everywhere, and re-run (a), (b), (c).
    SURVIVES if all three still hold, with (c) required to be DOES-NOT-EXCLUDE and not INSUFFICIENT.

PREDICTION: not reducible on any of the three -- P1's power/connectivity maximum stays under 0.90, no
power or connectivity measure dissociates, and P3 survives for at least one dissociator.

WRONG IF any of the three fires. **Named first because it costs the most**: E321's headline and E340's
graded result would both have to be rewritten to name the competitor, exactly as E119 forced on E116/E118.
E341's unlicensed numbers point toward the prediction, which is a reason for more suspicion of this run,
not less.

THE THIRD BRANCH, carried over from E341 and unchanged: if no rival family reaches any bar but each
dissociator's strongest competitor of ANY family is the other dissociator, the correct report is that the
two are ONE instrument (rule 28) and E321 must not be read as two measures corroborating each other.
E341's +0.9588 says this branch is live.

GATES.
  G1  CAPABILITY BOTH WAYS (rule 40) with the constructed property MEASURED BEFORE USE (rules 77, 84).
      **The construction is fixed by SEARCH rather than by a guessed constant**, which is what E341 got
      wrong: `_planted_reducible` is `AvgDelta` plus Gaussian noise whose scale is a multiple of
      `AvgDelta`'s ACROSS-BLOCK WITHIN-PATIENT spread -- the quantity the statistic actually sees -- and
      the multiplier is stepped down until the MEASURED pooled-z correlation lands in [0.90, 0.98].
      Landing above 0.98 is also a failure: a plant that is a near-copy tests nothing that a bar of 0.90
      needs tested. `_planted_free` is an independent draw with the same within-patient block structure
      and must NOT be flagged. Both measured values printed; the search trace printed.
  G2  SUPPORT: >= 10 POWER+CONNECTIVITY competitors, and >= 12 patients on (a) and (b) for both
      dissociators in P3.
  G3  THE ADJUSTMENT MUST ADJUST (rule 55): after P3, residual-vs-competitor |rho| < 0.10 against the
      within-patient-centred competitor, over the SLEEP states the slope was fitted on, printed. The same
      quantity over ALL states -- where the drug blocks are an extrapolation of the removal -- is printed
      beside it and is descriptive, not gated, because no within-patient fit ever claimed to remove a
      competitor from blocks it was not fitted on. Carried over from E341, where it passed at 0.0077/0.0097.
  G4  SMOKE MUST BITE: under `--smoke` every measure's values are shuffled independently across rows and
      the file prints the resulting maximum competitor |rho| and the count of dissociating measures, both
      of which must fall.

SCOPE. Unchanged from E321 and E341: intracranial epilepsy-surgery patients, depositor-computed features,
block-level staging, 18 patients. A null is "not reducible to anything the depositor computed" and must
be worded that way -- this design cannot speak to measures absent from the inventory.

    python -m bsde.experiments.e342_reducibility2
"""
from __future__ import annotations

import argparse, csv, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
SKIP = {"label", "refTime", "patientID", "Subdural", "timeOfDay",
        "timeOfDay_envCorrTimeData", "timeOfDay_bandPowerTimeData",
        "pctGoodSamples", "pctGoodSamples_envCorrTimeData", "pctGoodSamples_bandPowerTimeData"}

WAKE, REM, DEEP = "WS", "R", "N3"
SLEEP = (WAKE, "N1", "N2", DEEP, REM)
DRUG_U = ("U", "U_dex")
ALL_STATES = (WAKE, "N1", "N2", DEEP, REM, "WA", "S", "U", "U_dex")
MIN_PATIENTS = 12

DISSOCIATORS = ("NmlzCmplx", "EffDim")
COMPLEXITY = {"NmlzCmplx", "EffDim"}
POWER = {"AvgDelta", "AvgAlpha", "AvgGamma", "frontalDelta", "frontalAlpha",
         "temporalDelta", "parietalDelta", "limbicDelta", "frontBias"}
CONNECTIVITY = {"allwPLI", "frontwPLI", "backwPLI", "longwPLI", "InsAwPLI", "allEnvCorr"}

COLINEAR_BAR = 0.90
PLANT_LO, PLANT_HI = 0.90, 0.98
ADJUST_BAR = 0.10


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def iqr(v):
    v = sorted(x for x in v if math.isfinite(x))
    if len(v) < 4:
        return float("nan")
    return v[int(0.75 * len(v))] - v[int(0.25 * len(v))]


def pear(x, y):
    pr = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pr) < 6:
        return float("nan")
    n = len(pr)
    mx = sum(a for a, _ in pr) / n
    my = sum(b for _, b in pr) / n
    sxx = sum((a - mx) ** 2 for a, _ in pr)
    syy = sum((b - my) ** 2 for _, b in pr)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in pr) / math.sqrt(sxx * syy)


def signflip(diffs, rng, reps):
    d = [x for x in diffs if math.isfinite(x)]
    if len(d) < 4:
        return float("nan"), float("nan")
    obs = med(d)
    hits = 0
    for _ in range(reps):
        if abs(med([x if rng.random() < 0.5 else -x for x in d])) >= abs(obs):
            hits += 1
    return obs, hits / reps


def criteria(Z, col, pats, rng, reps):
    """E321's (a)(b)(c) with an explicit INSUFFICIENT state for (c) (rule 48)."""
    g = lambda p, st: Z[(p, col)].get(st, float("nan")) if (p, col) in Z else float("nan")
    d1 = [g(p, WAKE) - g(p, DEEP) for p in pats]
    d2 = [g(p, REM) - g(p, DEEP) for p in pats]
    d3 = []
    for p in pats:
        for u in DRUG_U:
            v = g(p, u) - g(p, DEEP)
            if math.isfinite(v):
                d3.append(v); break
    d1 = [v for v in d1 if math.isfinite(v)]
    d2 = [v for v in d2 if math.isfinite(v)]
    o1, q1 = signflip(d1, rng, reps) if len(d1) >= MIN_PATIENTS else (float("nan"), float("nan"))
    o2, q2 = signflip(d2, rng, reps) if len(d2) >= MIN_PATIENTS else (float("nan"), float("nan"))
    if len(d3) >= MIN_PATIENTS:
        o3, q3 = signflip(d3, rng, reps)
        c_state = "EXCLUDES" if (math.isfinite(q3) and q3 < 0.05) else "DOES NOT EXCLUDE"
    else:
        o3, q3, c_state = float("nan"), float("nan"), "INSUFFICIENT"
    a_ok = math.isfinite(q1) and q1 < 0.05
    b_ok = (math.isfinite(q2) and q2 < 0.05 and math.isfinite(o1) and math.isfinite(o2)
            and o1 * o2 > 0)
    return {"a": o1, "pa": q1, "b": o2, "pb": q2, "c": o3, "pc": q3, "c_state": c_state,
            "n": [len(d1), len(d2), len(d3)],
            "dissociates": bool(a_ok and b_ok and c_state == "DOES NOT EXCLUDE"),
            "arousal_rem_only": bool(a_ok and b_ok and c_state == "INSUFFICIENT"),
            "ambiguous": bool(a_ok and b_ok and c_state == "EXCLUDES")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=342)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e342_reducibility2.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = list(csv.DictReader(open(a.data)))
    cols = [c for c in rows[0] if c not in SKIP]
    by = {}
    for r in rows:
        by.setdefault((r["patientID"], r["label"]), []).append(r)
    pats = sorted({p for p, l in by if l == WAKE} & {p for p, l in by if l == REM}
                  & {p for p, l in by if l == DEEP})
    print(f"[cohort] {len(pats)} patients with wake-sleep, REM and N3 within patient; "
          f"{len(cols)} depositor measures")

    plant_r, plant_f = "_planted_reducible", "_planted_free"

    def zbuild(rowset, extra_cols=()):
        """within-patient z per (patient, state), median-centred and IQR-scaled over sleep blocks."""
        use = list(cols) + list(extra_cols)
        Z = {}
        for p in pats:
            blocks = {st: rowset.get((p, st), []) for st in ALL_STATES if (p, st) in rowset}
            for c in use:
                raw = {st: [f(x.get(c)) for x in rs] for st, rs in blocks.items()}
                pool = [v for st in SLEEP for v in raw.get(st, []) if math.isfinite(v)]
                m0, s0 = med(pool), iqr(pool)
                if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                    continue
                Z[(p, c)] = {st: (med(v) - m0) / s0 for st, v in raw.items() if med(v) == med(v)}
        return Z

    def residualise(Z, target, comp):
        """ONE REPAIR, found by --smoke before any real statistic existed (rules 26, 58).

        E341's fix residualised in the z space and was orthogonal by construction, but required
        >= 4 shared states per patient, which cost drug-state patients and left criterion (c)
        vacuous at n = 9. The first draft of E342 tried to buy those patients back by fitting the
        slope on RAW row-level values -- and reintroduced exactly the aggregation mismatch E341's
        smoke had exposed, leaving |rho| = 0.35 and 0.22 with the very column being removed.

        Both goals are available at once: fit the slope IN THE Z SPACE over the SLEEP states, where
        every patient has data, and APPLY it to every state including the drug blocks. Orthogonality
        holds by construction over the states the slope was fitted on -- which is what "removed the
        competitor" means -- and the drug states are an explicit extrapolation of that removal,
        reported as such rather than silently assumed.
        """
        out = {k: dict(v) for k, v in Z.items()}
        for p in pats:
            if (p, target) not in Z or (p, comp) not in Z:
                continue
            sts = [st for st in SLEEP
                   if st in Z[(p, target)] and st in Z[(p, comp)]
                   and math.isfinite(Z[(p, target)][st]) and math.isfinite(Z[(p, comp)][st])]
            if len(sts) < 3:
                out.pop((p, target), None)
                continue
            xs = [Z[(p, comp)][st] for st in sts]
            ys = [Z[(p, target)][st] for st in sts]
            mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
            sxx = sum((v - mx) ** 2 for v in xs)
            b = sum((v - mx) * (w - my) for v, w in zip(xs, ys)) / sxx if sxx > 0 else 0.0
            out[(p, target)] = {st: Z[(p, target)][st] - b * (Z[(p, comp)][st] - mx)
                                for st in Z[(p, target)]
                                if st in Z[(p, comp)] and math.isfinite(Z[(p, comp)][st])
                                and math.isfinite(Z[(p, target)][st])}
        return out

    # -------------------------------------------------------------- G1: plants, built by SEARCH
    print("\n" + "=" * 96)
    print("G1 -- planted controls. Noise scaled to AvgDelta's ACROSS-BLOCK spread and the multiplier")
    print("     SEARCHED until the MEASURED correlation lands in [%.2f, %.2f] (rules 77, 84)."
          % (PLANT_LO, PLANT_HI))
    # AvgDelta's within-patient across-block spread, the quantity the statistic actually sees
    spreads = []
    for p in pats:
        bl = [med([f(x.get("AvgDelta")) for x in by[(p, st)]])
              for st in SLEEP if (p, st) in by]
        bl = [v for v in bl if math.isfinite(v)]
        if len(bl) >= 3:
            spreads.append((max(bl) - min(bl)) or 0.0)
    base = med(spreads)
    print(f"  AvgDelta median within-patient across-block range = {base:.6g}")
    pshift = {p: rng.gauss(0, 1.0) for p in pats}
    chosen, r_plant = None, float("nan")
    for mult in (1.20, 1.00, 0.85, 0.70, 0.60, 0.50, 0.42, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10):
        sd = mult * base
        trial = {}
        for i, r in enumerate(rows):
            d = f(r.get("AvgDelta"))
            trial[i] = "" if not math.isfinite(d) else repr(d + rng.gauss(0, sd))
        for i, r in enumerate(rows):
            r[plant_r] = trial[i]
            r[plant_f] = repr(pshift.get(r["patientID"], 0.0) + rng.gauss(0, 1.0))
        Zt = zbuild(by, extra_cols=(plant_r, plant_f))
        keys = [(p, st) for p in pats for st in ALL_STATES]
        gv = lambda c: [Zt[(p, c)].get(st, float("nan")) if (p, c) in Zt else float("nan")
                        for p, st in keys]
        rr = pear(gv(plant_r), gv("AvgDelta"))
        print(f"    mult {mult:5.2f} (sd {sd:.4g})  measured corr with AvgDelta = {rr:+.4f}")
        if math.isfinite(rr) and PLANT_LO <= abs(rr) <= PLANT_HI:
            chosen, r_plant = mult, rr
            break
    if chosen is None:
        print("  [G1] the search never landed in the window -- plant construction FAILED")

    Z = zbuild(by, extra_cols=(plant_r, plant_f))
    allcols = list(cols) + [plant_r, plant_f]

    src = by
    if a.smoke:
        vals = {c: [r.get(c) for r in rows] for c in allcols}
        for c in allcols:
            rng.shuffle(vals[c])
        sh = [dict(r) for r in rows]
        for i, r in enumerate(sh):
            for c in allcols:
                r[c] = vals[c][i]
        src = {}
        for r in sh:
            src.setdefault((r["patientID"], r["label"]), []).append(r)
        Z = zbuild(src, extra_cols=(plant_r, plant_f))
        print("\n[SMOKE] every measure's values shuffled independently across rows")

    keys = [(p, st) for p in pats for st in ALL_STATES]
    vec = {c: [Z[(p, c)].get(st, float("nan")) if (p, c) in Z else float("nan") for p, st in keys]
           for c in allcols}

    def maxcorr(name, exclude=()):
        best = float("nan")
        for c in allcols:
            if c == name or c in exclude:
                continue
            v = pear(vec[name], vec[c])
            if math.isfinite(v) and (not math.isfinite(best) or abs(v) > abs(best)):
                best = v
        return best

    r_free = maxcorr(plant_f, exclude=(plant_r,))
    pos_ok = math.isfinite(r_plant) and PLANT_LO <= abs(r_plant) <= PLANT_HI
    det_pos = math.isfinite(maxcorr(plant_r, exclude=(plant_f,))) and \
        abs(maxcorr(plant_r, exclude=(plant_f,))) >= COLINEAR_BAR
    det_neg = math.isfinite(r_free) and abs(r_free) < COLINEAR_BAR
    G1 = bool(pos_ok and det_pos and det_neg)
    print(f"\n  {plant_r:22s} constructed corr with AvgDelta = {r_plant:+.4f}  "
          f"(window [{PLANT_LO:.2f}, {PLANT_HI:.2f}]) -> {'ok' if pos_ok else 'FAIL'}")
    print(f"  {plant_f:22s} largest |corr| with any measure = {r_free:+.4f}  "
          f"(must be < {COLINEAR_BAR:.2f}) -> {'ok' if det_neg else 'FAIL'}")
    print(f"  detector flags the reducible plant = {det_pos}; flags the free plant = "
          f"{not det_neg}")
    print(f"  [G1] -> {'PASS' if G1 else 'FAIL'}")

    competitors = sorted((POWER | CONNECTIVITY) & set(cols))
    G2_comp = len(competitors) >= 10
    print(f"\n[G2a] {len(competitors)} POWER+CONNECTIVITY competitors -> "
          f"{'PASS' if G2_comp else 'FAIL'}")

    # -------------------------------------------------------------------------------- P1
    report, worst = {}, {}
    for D in DISSOCIATORS:
        print("\n" + "=" * 96)
        print(f"P1 -- pooled-z co-linearity for {D}   (bar {COLINEAR_BAR:.2f})")
        tab = []
        for c in cols:
            if c == D:
                continue
            fam = ("COMPLEXITY" if c in COMPLEXITY else "POWER" if c in POWER else
                   "CONNECTIVITY" if c in CONNECTIVITY else "unassigned")
            tab.append((pear(vec[D], vec[c]), c, fam))
        tab.sort(key=lambda t: -(abs(t[0]) if math.isfinite(t[0]) else -1))
        for rr, c, fam in tab:
            print(f"  {c:<18}{fam:<14}{rr:>+10.4f}")
        rival = [t for t in tab if t[2] in ("POWER", "CONNECTIVITY")]
        best = max(rival, key=lambda t: abs(t[0]) if math.isfinite(t[0]) else -1)
        print(f"  [P1] strongest POWER/CONNECTIVITY rival: {best[1]} rho = {best[0]:+.4f}")
        print(f"  [ctx] strongest rival of ANY family    : {tab[0][1]} ({tab[0][2]}) "
              f"rho = {tab[0][0]:+.4f}")
        report[D] = {"table": [{"measure": c, "family": fam, "rho": rr} for rr, c, fam in tab],
                     "P1_best": {"measure": best[1], "rho": best[0]},
                     "overall_best": {"measure": tab[0][1], "family": tab[0][2], "rho": tab[0][0]},
                     "reducible_colinearity": bool(math.isfinite(best[0])
                                                   and abs(best[0]) >= COLINEAR_BAR)}
        worst[D] = best[1]

    # -------------------------------------------------------------------------------- P2
    print("\n" + "=" * 96)
    print("P2 -- BEHAVIOURAL SUBSTITUTION: run E321's (a)(b)(c) on every measure. No bar is chosen.")
    print(f"  {'measure':<18}{'family':<14}{'(a) wake-N3':>14}{'(b) REM-N3':>13}"
          f"{'(c) drugU-N3':>15}   status")
    sub = {}
    for c in cols:
        fam = ("COMPLEXITY" if c in COMPLEXITY else "POWER" if c in POWER else
               "CONNECTIVITY" if c in CONNECTIVITY else "unassigned")
        r = criteria(Z, c, pats, rng, a.reps)
        sub[c] = dict(r, family=fam)
        st = ("DISSOCIATES" if r["dissociates"] else
              "arousal+REM only (c INSUFFICIENT)" if r["arousal_rem_only"] else
              "ambiguous (c excludes)" if r["ambiguous"] else "-")
        ca = f"{r['a']:+.3f}/{r['pa']:.3f}" if math.isfinite(r["pa"]) else "n/a"
        cb = f"{r['b']:+.3f}/{r['pb']:.3f}" if math.isfinite(r["pb"]) else "n/a"
        cc = f"{r['c']:+.3f}/{r['pc']:.3f}" if math.isfinite(r["pc"]) else r["c_state"]
        print(f"  {c:<18}{fam:<14}{ca:>14}{cb:>13}{cc:>15}   {st}")
    rival_diss = [c for c, r in sub.items()
                  if r["dissociates"] and r["family"] in ("POWER", "CONNECTIVITY")]
    print(f"\n  [P2] POWER/CONNECTIVITY measures that dissociate: "
          f"{rival_diss if rival_diss else 'none'}")

    # -------------------------------------------------------------------------------- P3
    print("\n" + "=" * 96)
    print("P3 -- does the dissociation survive removing its strongest power/connectivity competitor?")
    p3, G3, G2_n = {}, True, True
    for D in DISSOCIATORS:
        comp = worst[D]
        Za = residualise(Z, D, comp)
        # verified against the WITHIN-PATIENT CENTRED competitor -- the component a within-patient
        # regression can remove -- over the SLEEP states the slope was fitted on. The same quantity
        # over all states, where the removal is an extrapolation, is reported beside it.
        cm = {}
        for p in pats:
            if (p, comp) in Z:
                fv = [Z[(p, comp)][st] for st in SLEEP
                      if st in Z[(p, comp)] and math.isfinite(Z[(p, comp)][st])]
                cm[p] = sum(fv) / len(fv) if fv else 0.0
        skeys = [(p, st) for p in pats for st in SLEEP]
        gD = lambda ks: [Za[(p, D)].get(st, float("nan")) if (p, D) in Za else float("nan")
                         for p, st in ks]
        gC = lambda ks: [Z[(p, comp)].get(st, float("nan")) - cm.get(p, 0.0) if (p, comp) in Z
                         else float("nan") for p, st in ks]
        rres = pear(gD(skeys), gC(skeys))
        rres_all = pear(gD(keys), gC(keys))
        ok_adj = math.isfinite(rres) and abs(rres) < ADJUST_BAR
        G3 = G3 and ok_adj
        r = criteria(Za, D, pats, rng, a.reps)
        n_ok = r["n"][0] >= MIN_PATIENTS and r["n"][1] >= MIN_PATIENTS
        G2_n = G2_n and n_ok
        print(f"\n  {D} residualised on {comp}  (slope fitted in z space on sleep blocks, "
              f"applied to every block)")
        print(f"    [G3] residual-vs-{comp} |rho| over the fitted sleep states = {abs(rres):.4f} "
              f"(bar {ADJUST_BAR:.2f}) -> "
              f"{'PASS' if ok_adj else 'FAIL -- the adjustment did not adjust'}")
        print(f"         same quantity over ALL states (drug blocks are an extrapolation of the "
              f"removal) = {abs(rres_all):.4f}")
        print(f"    (a) wake-N3  {r['a']:+.4f} p={r['pa']:.4f}  n={r['n'][0]}")
        print(f"    (b) REM -N3  {r['b']:+.4f} p={r['pb']:.4f}  n={r['n'][1]}")
        print(f"    (c) drugU-N3 {r['c']:+.4f} p={r['pc']:.4f}  n={r['n'][2]}   [{r['c_state']}]")
        print(f"    -> {'SURVIVES' if r['dissociates'] else 'does NOT survive'}")
        p3[D] = dict(r, competitor=comp, residual_rho=rres, residual_rho_all=rres_all,
                     adjust_ok=ok_adj, n_ok=n_ok)

    G2 = G2_comp and G2_n
    print(f"\n[G2] support -> {'PASS' if G2 else 'FAIL'}")
    print(f"[G3] every residualisation removed its competitor -> {'PASS' if G3 else 'FAIL'}")

    # ---------------------------------------------------------------------------- verdict
    print("\n" + "=" * 96)
    red_col = any(report[D]["reducible_colinearity"] for D in DISSOCIATORS)
    red_eff = bool(rival_diss)
    surv = any(p3[D]["dissociates"] for D in DISSOCIATORS)
    twin = all(report[D]["overall_best"]["family"] == "COMPLEXITY" for D in DISSOCIATORS)

    if not (G1 and G2):
        verdict = "NOT INTERPRETABLE"
        why = ("gate failed: " + ", ".join(g for g, ok in (("G1", G1), ("G2", G2)) if not ok)
               + " -- rule 31: the downstream verdict is absent, not negative.")
    elif red_col or red_eff:
        bits = []
        if red_col:
            bits.append("co-linearity: " + ", ".join(
                f"{D} ~ {report[D]['P1_best']['measure']} ({report[D]['P1_best']['rho']:+.4f})"
                for D in DISSOCIATORS if report[D]["reducible_colinearity"]))
        if red_eff:
            bits.append("behavioural substitution: " + ", ".join(rival_diss) + " dissociate too")
        verdict = "REDUCIBLE -- E321 AND E340 MUST BE REWRITTEN"
        why = ("a power or connectivity measure already in the inventory reproduces the dissociation. "
               + "; ".join(bits) + ". The behaviour is real and the NAME is wrong.")
    elif not G3:
        verdict = "PARTIAL -- P1 and P2 stand, P3 NOT INTERPRETABLE"
        why = (f"no rival reaches the co-linearity bar and none dissociates, but a residualisation left "
               f"|rho| >= {ADJUST_BAR:.2f} with its competitor, so the survival test says nothing "
               f"(rule 55).")
    elif not surv:
        verdict = "NOT REDUCIBLE BY EITHER TEST, BUT DOES NOT SURVIVE ADJUSTMENT"
        why = ("no rival is co-linear at the bar and no rival dissociates, yet removing the strongest "
               "rival destroys the dissociation for both. A shared component is doing the work even "
               "though no single competitor reproduces it; the claim must be stated jointly.")
    elif twin:
        verdict = "NOT REDUCIBLE -- but the two dissociators are ONE instrument"
        why = ("no power or connectivity measure is co-linear at the bar or dissociates, and the "
               "dissociation survives adjustment, so E321's claim stands. But each dissociator's "
               "strongest rival of any family is the other dissociator, so they do not independently "
               "corroborate each other (rule 28).")
    else:
        verdict = "NOT REDUCIBLE"
        why = ("no power or connectivity measure in this inventory is co-linear at the bar, none "
               "reproduces the dissociation behaviourally, and the dissociation survives residualising "
               "on the strongest rival. Bounded by the inventory.")
    print(f"VERDICT: {verdict}\n  {why}")

    if a.smoke:
        mx = max(abs(t["rho"]) for D in DISSOCIATORS for t in report[D]["table"]
                 if math.isfinite(t["rho"]))
        nd = sum(1 for r in sub.values() if r["dissociates"])
        print(f"\n[G4 SMOKE] largest |rho| to any rival = {mx:.4f}; measures dissociating = {nd}. "
              f"Both must fall against the real run.")
        return 0

    out = {"verdict": verdict, "why": why, "n_patients": len(pats),
           "gates": {"G1": G1, "G2": G2, "G3": G3, "plant_mult": chosen,
                     "plant_corr": r_plant, "plant_free_max": r_free},
           "bars": {"colinearity": COLINEAR_BAR, "plant_window": [PLANT_LO, PLANT_HI],
                    "adjust": ADJUST_BAR},
           "P1": report, "P2": sub, "P2_rival_dissociators": rival_diss, "P3": p3,
           "families": {"COMPLEXITY": sorted(COMPLEXITY), "POWER": sorted(POWER),
                        "CONNECTIVITY": sorted(CONNECTIVITY)}}
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
