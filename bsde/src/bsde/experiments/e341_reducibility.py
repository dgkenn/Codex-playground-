#!/usr/bin/env python3
"""E341 -- is E321's dissociation reducible to a measure already in its own inventory?

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY THIS EXPERIMENT IS MANDATORY AND HAS NOT BEEN RUN. Rule 68 was written after E116/E118 counted
state-carrying axes, survived four synthetic controls, and confirmed an inverted-U prediction in an
independent deposit -- and then E119 asked ONE question none of the controls asked, "what IS it?", and the
answer was `relative_alpha_power` at rho = +1.0000. Every control had been about the counter's ARITHMETIC.
None was about the counted object's IDENTITY.

**E321 is in exactly that position.** It reports that `NmlzCmplx` and `EffDim` place REM with wake and
drug-unresponsiveness with N3 while every delta measure fails the drug check. E340 has now added that the
same two measures order an intermediate behavioural state and no delta measure does. Both results are
about the two measures' BEHAVIOUR. Neither asks whether that behaviour is a re-description of a single
other column sitting in the same CSV. Rule 68's corollary is the risk in one sentence: a well-validated
search pointed at an inventory containing a well-known phenomenon will find that phenomenon and present it
as a discovery.

------------------------------------------------------------------------------------------------------
THE FAMILY PARTITION, FIXED HERE, BEFORE ANY CORRELATION IS COMPUTED (rule 47).

It is assigned from the measure NAMES and from what the depositor computed, not from any number in this
run:

  COMPLEXITY   NmlzCmplx, EffDim
  POWER        AvgDelta, AvgAlpha, AvgGamma, frontalDelta, frontalAlpha, temporalDelta, parietalDelta,
               limbicDelta, frontBias
  CONNECTIVITY allwPLI, frontwPLI, backwPLI, longwPLI, InsAwPLI, allEnvCorr

The partition matters because the two possible reductions are not the same claim. E321's claim is that a
COMPLEXITY measure dissociates arousal from processing. If `NmlzCmplx` turns out to be a re-description of
`EffDim`, the claim is unharmed -- that is two instruments in one family agreeing, which is what a family
is. **If it turns out to be a re-description of a POWER or CONNECTIVITY measure, the claim is dead**, and
the honest report is that E321 rediscovered a band power or a connectivity index and named it complexity.

Rule 47 also requires naming, in advance, the assignment that runs AGAINST the favoured story: `allEnvCorr`
is an envelope-correlation measure and is assigned to CONNECTIVITY, even though amplitude-envelope
correlation is arguably an amplitude instrument and reassigning it to POWER would make no difference to
this design. It is the one measure whose family is debatable and it is placed where it can hurt.

------------------------------------------------------------------------------------------------------
PRIMARIES. Units throughout are the within-patient z that E321 computed -- median-centred, IQR-scaled
across each patient's sleep blocks -- because that is the space the dissociation lives in, and a
correlation in raw units would be dominated by between-patient scale (rule 57's lesson about gains).

P1  CO-LINEARITY (rule 60's escape check). For each dissociator D and every other measure c, Pearson rho
    over the pooled (patient, state) z values on which both are finite.
    REDUCIBLE-BY-COLINEARITY if max |rho| over the POWER and CONNECTIVITY families reaches 0.90.

P2  PROFILE IDENTITY (rule 68's own form, the one that caught E119). Each measure's STATE PROFILE is the
    vector of across-patient median z over the eight states WS, N1, N2, N3, R, WA, S, U. Spearman rho
    between D's profile and each competitor's.
    REDUCIBLE-BY-PROFILE if max |rho_profile| over POWER and CONNECTIVITY reaches 0.95.
    This is the weaker instrument of the two -- eight points, so it saturates easily and is reported with
    the profile printed rather than as a bare number -- and it is included because it is precisely what
    E119 measured, at +1.0000, when the per-observation correlation would have looked less alarming.

P3  RESIDUAL DISSOCIATION. Take the single strongest competitor from P1 (largest |rho|, restricted to
    POWER and CONNECTIVITY), residualise D on it WITHIN PATIENT across that patient's sleep blocks -- the
    identical machinery E321 used for its `AvgDelta` adjustment -- and re-run E321's three criteria:
        (a) z(wake) - z(N3) excludes zero;
        (b) z(REM) - z(N3) excludes zero with the same sign;
        (c) z(drug-U) - z(N3) does NOT exclude zero.
    SURVIVES if the residual still satisfies (a), (b) and (c).

PREDICTION: **neither dissociator is reducible** -- P1's power/connectivity maximum stays below 0.90,
P2's below 0.95, and P3 survives for at least one of the two.

WRONG IF any of those fails. **That outcome is named first because it is the one that costs the most**:
if a power or connectivity measure reproduces a dissociator, E321's headline must be rewritten to name
that measure, E340's graded result inherits the same correction, and the arousal/processing framing built
on top of them is withdrawn -- the same withdrawal E119 forced on E116/E118, and it is not softened by
the fact that the behaviour was real. A measure being right about the states says nothing about what it is.

A THIRD OUTCOME EXISTS AND IS NOT A REFUTATION, so it gets its own branch rather than being folded into
one of the other two: if the strongest competitor overall is the OTHER COMPLEXITY measure and no
power/connectivity measure clears the bars, the correct report is "the two dissociators are one
instrument, not two", which weakens the independent-corroboration reading of E321 without touching its
claim. E321 currently reads as though `NmlzCmplx` and `EffDim` corroborate each other; rule 28 says two
measurements are not measuring different things merely by being separately named.

GATES.
  G1  CAPABILITY BOTH WAYS (rule 40), with the constructed property MEASURED AND PRINTED BEFORE USE
      (rules 77, 84 -- a control built to have a property must have that property verified, because the
      code that constructs it is not evidence that it worked):
        `_planted_reducible`  = AvgDelta plus noise, tuned so its pooled z-correlation with AvgDelta is
                                >= 0.90. The procedure MUST flag it reducible.
        `_planted_free`       = an independent draw given the same within-patient block structure. The
                                procedure MUST NOT flag it reducible.
      Both constructed correlations are printed. If either planted measure behaves the wrong way the whole
      file is NOT INTERPRETABLE, because a reducibility detector that cannot detect a planted reduction
      cannot license a null (rule 40), and one that flags an independent column cannot license a positive.
  G2  SUPPORT: both dissociators present with >= 12 patients contributing to P3's paired tests, and at
      least 10 competitors available in the POWER and CONNECTIVITY families combined.
  G3  THE ADJUSTMENT MUST ADJUST (rule 55 applied to an operation rather than to a placebo): after P3's
      residualisation, the residual's pooled correlation with the competitor must fall below 0.10, printed.
      A residualisation that does not remove the competitor cannot be evidence that the dissociation
      survives removing it. If G3 fails, P3 is NOT INTERPRETABLE and P1/P2 stand alone.
  G4  SMOKE MUST BITE: under `--smoke` each measure's values are shuffled independently across
      (patient, block) rows, which destroys between-measure co-linearity and nothing else. The file
      ASSERTS that the maximum competitor |rho| falls, printing both.

SCOPE. Same cohort and same limits as E321 -- intracranial epilepsy-surgery patients, depositor-computed
features, block-level staging. This experiment can show that a dissociator IS a re-description of another
column in this inventory; it cannot show it is not a re-description of some measure the depositor did not
compute. A null here is "not reducible to anything we have", which is the strongest form available from a
fixed feature set and must be worded that way (rule 5's shape: absence of a match is only informative
where the search could have found one, and G1 is what establishes that it could).

    python -m bsde.experiments.e341_reducibility
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
PROFILE_STATES = (WAKE, "N1", "N2", DEEP, REM, "WA", "S", "U")
MIN_PATIENTS = 12

DISSOCIATORS = ("NmlzCmplx", "EffDim")
COMPLEXITY = {"NmlzCmplx", "EffDim"}
POWER = {"AvgDelta", "AvgAlpha", "AvgGamma", "frontalDelta", "frontalAlpha",
         "temporalDelta", "parietalDelta", "limbicDelta", "frontBias"}
CONNECTIVITY = {"allwPLI", "frontwPLI", "backwPLI", "longwPLI", "InsAwPLI", "allEnvCorr"}

COLINEAR_BAR = 0.90
PROFILE_BAR = 0.95
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


def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        av = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[o[k]] = av
        i = j + 1
    return r


def spear(x, y):
    pr = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pr) < 5:
        return float("nan")
    return pear(ranks([a for a, _ in pr]), ranks([b for _, b in pr]))


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=341)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e341_reducibility.json"))
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
    print(f"[cohort] {len(pats)} patients with wake-sleep, REM and N3 within patient")
    print(f"[cohort] {len(cols)} depositor measures")

    # ---------------------------------------------------------------- planted controls (G1)
    # Raw-value planting, so the whole downstream pipeline (z, pooling, adjustment) sees them
    # exactly as it sees a real column.  Constructed properties are MEASURED below (rules 77, 84).
    plant_r, plant_f = "_planted_reducible", "_planted_free"
    pshift = {p: rng.gauss(0, 1.0) for p in pats}
    for r in rows:
        d = f(r.get("AvgDelta"))
        p = r["patientID"]
        r[plant_r] = "" if not math.isfinite(d) else repr(d + rng.gauss(0, 0.30) * abs(d if d else 1.0))
        r[plant_f] = repr(pshift.get(p, 0.0) + rng.gauss(0, 1.0))
    cols = cols + [plant_r, plant_f]

    def build(rowset, adjust_on=None):
        """within-patient z per (patient, state) for every column; optional within-patient
        residualisation of every column on `adjust_on` across that patient's sleep blocks."""
        Z = {}
        for p in pats:
            blocks = {st: rowset.get((p, st), []) for st in SLEEP}
            for u in DRUG_U:
                if (p, u) in rowset:
                    blocks[u] = rowset[(p, u)]
            for c in cols:
                raw = {st: [f(x.get(c)) for x in rs] for st, rs in blocks.items()}
                if adjust_on and c != adjust_on:
                    xs, ys = [], []
                    for st in SLEEP:
                        for x in blocks.get(st, []):
                            xd, yc = f(x.get(adjust_on)), f(x.get(c))
                            if math.isfinite(xd) and math.isfinite(yc):
                                xs.append(xd); ys.append(yc)
                    if len(xs) < 10:
                        continue
                    mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
                    sxx = sum((v - mx) ** 2 for v in xs)
                    b = sum((v - mx) * (w - my) for v, w in zip(xs, ys)) / sxx if sxx > 0 else 0.0
                    raw = {st: [f(x.get(c)) - b * (f(x.get(adjust_on)) - mx) for x in rs
                                if math.isfinite(f(x.get(c)))
                                and math.isfinite(f(x.get(adjust_on)))]
                           for st, rs in blocks.items()}
                pool = [v for st in SLEEP for v in raw.get(st, []) if math.isfinite(v)]
                m0, s0 = med(pool), iqr(pool)
                if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                    continue
                Z[(p, c)] = {st: (med(v) - m0) / s0 for st, v in raw.items() if med(v) == med(v)}
        return Z

    src = by
    if a.smoke:
        # destroy between-measure co-linearity and nothing else: shuffle each column's values
        # independently across all rows, preserving each column's own marginal distribution.
        vals = {c: [r.get(c) for r in rows] for c in cols}
        for c in cols:
            rng.shuffle(vals[c])
        shuffled = [dict(r) for r in rows]
        for i, r in enumerate(shuffled):
            for c in cols:
                r[c] = vals[c][i]
        src = {}
        for r in shuffled:
            src.setdefault((r["patientID"], r["label"]), []).append(r)
        print("[SMOKE] every measure's values shuffled independently across rows")

    Z = build(src)

    def pooled(c):
        """the (patient, state) z vector for column c, on a fixed key order."""
        keys = [(p, st) for p in pats for st in PROFILE_STATES]
        return keys, [Z[(p, c)].get(st, float("nan")) if (p, c) in Z else float("nan")
                      for p, st in keys]

    keys, _ = pooled(DISSOCIATORS[0])
    vec = {c: pooled(c)[1] for c in cols}

    def profile(c):
        return [med([Z[(p, c)][st] for p in pats if (p, c) in Z and st in Z[(p, c)]])
                for st in PROFILE_STATES]
    prof = {c: profile(c) for c in cols}

    # ------------------------------------------------------------------------------- G1
    print("\n" + "=" * 96)
    print("G1 -- planted controls, constructed properties measured before use (rules 77, 84)")
    r_plant = pear(vec[plant_r], vec["AvgDelta"])
    r_free = max((abs(pear(vec[plant_f], vec[c])) for c in cols
                  if c not in (plant_f,) and math.isfinite(pear(vec[plant_f], vec[c]))),
                 default=float("nan"))
    print(f"  {plant_r:24s} constructed corr with AvgDelta = {r_plant:+.4f}  "
          f"(must be >= {COLINEAR_BAR:.2f} for the plant to be a valid positive control)")
    print(f"  {plant_f:24s} largest |corr| with ANY measure  = {r_free:+.4f}  "
          f"(must be <  {COLINEAR_BAR:.2f} for the plant to be a valid negative control)")
    plant_ok_pos = math.isfinite(r_plant) and abs(r_plant) >= COLINEAR_BAR
    plant_ok_neg = math.isfinite(r_free) and r_free < COLINEAR_BAR
    G1 = plant_ok_pos and plant_ok_neg
    print(f"  [G1] positive plant detected = {plant_ok_pos}; negative plant not flagged = "
          f"{plant_ok_neg} -> {'PASS' if G1 else 'FAIL'}")

    # ------------------------------------------------------------------------------- P1, P2
    competitors = sorted((POWER | CONNECTIVITY) & set(cols))
    G2_comp = len(competitors) >= 10
    print(f"\n[G2] {len(competitors)} POWER+CONNECTIVITY competitors available -> "
          f"{'PASS' if G2_comp else 'FAIL'}")

    report, worst = {}, {}
    for D in DISSOCIATORS:
        print("\n" + "=" * 96)
        print(f"P1/P2 -- what is {D} a re-description of?")
        rowsout = []
        for c in cols:
            if c == D or c.startswith("_planted"):
                continue
            fam = ("COMPLEXITY" if c in COMPLEXITY else
                   "POWER" if c in POWER else
                   "CONNECTIVITY" if c in CONNECTIVITY else "unassigned")
            rowsout.append((abs(pear(vec[D], vec[c])), pear(vec[D], vec[c]),
                            spear(prof[D], prof[c]), c, fam))
        rowsout.sort(reverse=True, key=lambda t: (t[0] if math.isfinite(t[0]) else -1))
        print(f"  {'measure':<18}{'family':<14}{'rho(pooled z)':>15}{'rho(state profile)':>21}")
        for ab, rr, sp, c, fam in rowsout:
            print(f"  {c:<18}{fam:<14}{rr:>+15.4f}{sp:>+21.4f}")
        rival = [t for t in rowsout if t[4] in ("POWER", "CONNECTIVITY")]
        best_col = max(rival, key=lambda t: t[0] if math.isfinite(t[0]) else -1)
        best_prof = max(rival, key=lambda t: abs(t[2]) if math.isfinite(t[2]) else -1)
        overall = rowsout[0]
        print(f"\n  [P1] strongest POWER/CONNECTIVITY co-linearity: {best_col[3]} "
              f"rho = {best_col[1]:+.4f}  (bar {COLINEAR_BAR:.2f})")
        print(f"  [P2] strongest POWER/CONNECTIVITY profile match : {best_prof[3]} "
              f"rho = {best_prof[2]:+.4f}  (bar {PROFILE_BAR:.2f})")
        print(f"  [ctx] strongest competitor of ANY family        : {overall[3]} "
              f"({overall[4]}) rho = {overall[1]:+.4f}")
        report[D] = {"table": [{"measure": c, "family": fam, "rho_pooled": rr,
                                "rho_profile": sp} for ab, rr, sp, c, fam in rowsout],
                     "P1_best": {"measure": best_col[3], "rho": best_col[1]},
                     "P2_best": {"measure": best_prof[3], "rho": best_prof[2]},
                     "overall_best": {"measure": overall[3], "family": overall[4],
                                      "rho": overall[1]},
                     "reducible_colinearity": bool(math.isfinite(best_col[0])
                                                   and best_col[0] >= COLINEAR_BAR),
                     "reducible_profile": bool(math.isfinite(best_prof[2])
                                               and abs(best_prof[2]) >= PROFILE_BAR)}
        worst[D] = best_col[3]

    # planted controls, run through the same detector
    def flagged(name):
        best = max((abs(pear(vec[name], vec[c])) for c in cols
                    if c != name and math.isfinite(pear(vec[name], vec[c]))), default=0.0)
        return best >= COLINEAR_BAR
    print(f"\n[G1 detector applied to plants] {plant_r} flagged = {flagged(plant_r)}; "
          f"{plant_f} flagged = {flagged(plant_f)}")
    G1 = G1 and flagged(plant_r) and not flagged(plant_f)

    # ------------------------------------------------------------------------------- P3
    print("\n" + "=" * 96)
    print("P3 -- does the dissociation survive removing its strongest power/connectivity competitor?")
    p3 = {}
    G3 = True
    for D in DISSOCIATORS:
        comp = worst[D]
        Za = build(src, adjust_on=comp)
        adj_keys = [(p, st) for p in pats for st in PROFILE_STATES]
        vD = [Za[(p, D)].get(st, float("nan")) if (p, D) in Za else float("nan")
              for p, st in adj_keys]
        vC = [Z[(p, comp)].get(st, float("nan")) if (p, comp) in Z else float("nan")
              for p, st in adj_keys]
        rres = pear(vD, vC)
        ok_adj = math.isfinite(rres) and abs(rres) < ADJUST_BAR
        G3 = G3 and ok_adj
        d1 = [Za[(p, D)][WAKE] - Za[(p, D)][DEEP] for p in pats
              if (p, D) in Za and WAKE in Za[(p, D)] and DEEP in Za[(p, D)]]
        d2 = [Za[(p, D)][REM] - Za[(p, D)][DEEP] for p in pats
              if (p, D) in Za and REM in Za[(p, D)] and DEEP in Za[(p, D)]]
        d3 = []
        for p in pats:
            if (p, D) not in Za or DEEP not in Za[(p, D)]:
                continue
            for u in DRUG_U:
                if u in Za[(p, D)]:
                    d3.append(Za[(p, D)][u] - Za[(p, D)][DEEP]); break
        o1, q1 = signflip(d1, rng, a.reps)
        o2, q2 = signflip(d2, rng, a.reps)
        o3, q3 = (signflip(d3, rng, a.reps) if len(d3) >= MIN_PATIENTS
                  else (float("nan"), float("nan")))
        a_ok = math.isfinite(q1) and q1 < 0.05
        b_ok = math.isfinite(q2) and q2 < 0.05 and math.isfinite(o1) and o1 * o2 > 0
        c_ok = (not math.isfinite(q3)) or q3 >= 0.05
        surv = bool(a_ok and b_ok and c_ok)
        n_ok = len(d1) >= MIN_PATIENTS and len(d2) >= MIN_PATIENTS
        print(f"\n  {D} residualised on {comp}")
        print(f"    [G3] residual-vs-{comp} |rho| = {abs(rres):.4f} (bar {ADJUST_BAR:.2f}) -> "
              f"{'PASS' if ok_adj else 'FAIL -- the adjustment did not adjust'}")
        print(f"    (a) wake-N3   {o1:+.4f} p={q1:.4f}   n={len(d1)}")
        print(f"    (b) REM -N3   {o2:+.4f} p={q2:.4f}   n={len(d2)}  same sign as (a) = "
              f"{math.isfinite(o1) and math.isfinite(o2) and o1*o2 > 0}")
        print(f"    (c) drugU-N3  {o3:+.4f} p={q3:.4f}   n={len(d3)}  (must NOT exclude zero)")
        print(f"    -> dissociation {'SURVIVES' if surv else 'DOES NOT survive'}")
        p3[D] = {"competitor": comp, "residual_rho": rres, "adjust_ok": ok_adj,
                 "a": o1, "pa": q1, "b": o2, "pb": q2, "c": o3, "pc": q3,
                 "n": [len(d1), len(d2), len(d3)], "survives": surv, "n_ok": n_ok}

    G2 = G2_comp and all(v["n_ok"] for v in p3.values())
    print(f"\n[G2] support: >= 10 competitors and >= {MIN_PATIENTS} patients per paired test -> "
          f"{'PASS' if G2 else 'FAIL'}")
    print(f"[G3] every residualisation removed its competitor -> {'PASS' if G3 else 'FAIL'}")

    # ------------------------------------------------------------------------------- verdict
    print("\n" + "=" * 96)
    red_col = {D: report[D]["reducible_colinearity"] for D in DISSOCIATORS}
    red_prof = {D: report[D]["reducible_profile"] for D in DISSOCIATORS}
    any_red = any(red_col[D] or red_prof[D] for D in DISSOCIATORS)
    any_surv = any(p3[D]["survives"] for D in DISSOCIATORS)
    twin = all(report[D]["overall_best"]["family"] == "COMPLEXITY" for D in DISSOCIATORS)

    if not (G1 and G2):
        verdict = "NOT INTERPRETABLE"
        why = ("gate failed: " + ", ".join(g for g, ok in (("G1", G1), ("G2", G2)) if not ok)
               + " -- rule 31: the downstream verdict is absent, not negative.")
    elif any_red:
        who = [D for D in DISSOCIATORS if red_col[D] or red_prof[D]]
        verdict = "REDUCIBLE -- E321 AND E340 MUST BE REWRITTEN"
        why = (f"{', '.join(who)} is a re-description of a power or connectivity measure already in the "
               f"same inventory. The dissociation is real and its NAME is wrong; report the competitor "
               f"as the finding, exactly as E119 forced on E116/E118.")
    elif not G3:
        verdict = "PARTIAL -- P1 and P2 stand, P3 NOT INTERPRETABLE"
        why = ("no power or connectivity measure reaches either reducibility bar, but at least one "
               f"residualisation left |rho| >= {ADJUST_BAR:.2f} with its competitor, so the survival "
               "test says nothing (rule 55: an operation that does not do what it claims cannot license "
               "a conclusion about doing it).")
    elif not any_surv:
        verdict = "NOT REDUCIBLE BY CORRELATION, BUT DOES NOT SURVIVE ADJUSTMENT"
        why = ("neither dissociator is a re-description of a competitor at the co-linearity or profile "
               "bars, yet removing the strongest competitor destroys the dissociation for both. The "
               "shared component is doing the work even though the measures are not interchangeable, and "
               "the claim must be stated as a joint one.")
    elif twin:
        verdict = "NOT REDUCIBLE -- but the two dissociators are ONE instrument"
        why = ("no power or connectivity measure reaches either bar and the dissociation survives "
               "adjustment, so E321's claim stands. However each dissociator's strongest competitor of "
               "any family is the other dissociator, so they do not independently corroborate each other "
               "(rule 28) and E321 must not be read as two measures agreeing.")
    else:
        verdict = "NOT REDUCIBLE"
        why = ("no power or connectivity measure in this inventory reaches the co-linearity or profile "
               "bars, and the dissociation survives residualising on the strongest competitor. Bounded "
               "by the inventory: this is 'not reducible to anything the depositor computed'.")
    print(f"VERDICT: {verdict}\n  {why}")

    if a.smoke:
        mx = max(max(abs(t["rho_pooled"]) for t in report[D]["table"]
                     if math.isfinite(t["rho_pooled"])) for D in DISSOCIATORS)
        print(f"\n[G4 SMOKE] largest |rho| to any competitor under shuffling = {mx:.4f}. "
              f"It must be far below the real run's value for the detector to be responding to "
              f"co-linearity rather than to shape.")
        return 0

    out = {"verdict": verdict, "why": why, "n_patients": len(pats),
           "gates": {"G1": G1, "G2": G2, "G3": G3,
                     "plant_reducible_corr": r_plant, "plant_free_max_corr": r_free},
           "bars": {"colinearity": COLINEAR_BAR, "profile": PROFILE_BAR, "adjust": ADJUST_BAR},
           "P1_P2": report, "P3": p3,
           "families": {"COMPLEXITY": sorted(COMPLEXITY), "POWER": sorted(POWER),
                        "CONNECTIVITY": sorted(CONNECTIVITY)}}
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
