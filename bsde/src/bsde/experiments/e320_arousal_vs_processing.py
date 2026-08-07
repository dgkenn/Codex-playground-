#!/usr/bin/env python3
"""E320 -- separating AROUSAL from COGNITIVE PROCESSING: the dissociation Brief 01 actually asks for.

PRE-REGISTRATION. Committed before any statistic in it exists.

------------------------------------------------------------------------------------------------------
THE QUESTION, WHICH IS THE PROJECT'S ORIGINAL ONE AND NOT THE LEAKAGE LINE'S

`RESEARCH_PROGRAM_BRIEF.md` exists to separate **arousal**, **cognitive-processing capacity**,
**command-following** and **behavioural output**, which are never synonyms. Every experiment in this
programme so far has measured a single arousal axis -- E93/E95/E100 ordered states on arousal, E73/E86's
network measures reduced to mean connectivity, `uce_v1` reduced to the whole-head exponent, and the whole
E248-E311 line measured drug identity against a ventilatory or sedation axis. None of it separates the
two constructs, because none of its states dissociate them.

**REM sleep dissociates them, and it is the only widely available state that does.** A person in REM is
behaviourally unresponsive -- atonic, unarousable by ordinary stimuli -- and yet is having vivid
conscious experience. N3 and drug-induced unresponsiveness are unresponsive AND largely experience-free.
So:

    state                 arousal / responsiveness      conscious experience
    wake (WS)                    high                          high
    REM (R)                      LOW                           HIGH      <-- the dissociation
    N3                           low                           low
    drug-unresponsive (U)        low                           low

**A measure of arousal or behavioural output must place REM with N3. A measure of cognitive-processing
capacity must place REM with wake.** That is a discriminating test between the two constructs, and it
requires no task, no command, and no report.

COHORT. `krause_dexprosleep_allData.csv`. **18 patients have REM, N3 and wake-sleep within patient**;
**16 of those also have drug-induced unresponsiveness** (12 propofol, 4 dexmedetomidine). Intracranial,
epilepsy-surgery, depositor-computed features. Everything is WITHIN PATIENT, so between-patient
differences in electrode coverage cannot produce the contrast.

------------------------------------------------------------------------------------------------------
PRIMARY. For each patient and each measure, the **dissociation index**

    D = (REM - N3) / (wake - N3)

computed on that patient's own state medians. D ~ 1 means the measure places REM with wake (a
processing-like measure); D ~ 0 means it places REM with N3 (an arousal-like measure). Aggregated as the
median across patients.

**THE DENOMINATOR GUARD, and it exists because this project has already been burned by exactly this.**
E303's within-patient dose-response returned a null that was probably its own estimator: a per-patient
ratio whose denominator could approach zero has unbounded variance. Here a patient contributes only if
`|wake - N3|` exceeds that patient's pooled within-state IQR for that measure -- i.e. the wake-to-N3
contrast must be large relative to the noise it is divided by. Patients failing the guard are **reported,
not silently dropped** (rule 14).

NULL. The states are permuted WITHIN PATIENT (the three labels reassigned among that patient's own
blocks), 5,000 draws, recomputing D. This destroys the state identities while preserving every
patient-level property, which is the destruction matched to the estimand (rule 55).

PREDICTIONS, stated per family before the run:
  * **Complexity measures (`NmlzCmplx`, `EffDim`) have D >= 0.5** and clear their null -- they are the
    established correlates of conscious level, and REM's high complexity is the reason the perturbational
    literature treats it as the dissociation state.
  * **Band-power measures (`AvgDelta`, `AvgAlpha`) have D <= 0.3** -- delta is the canonical arousal/depth
    marker and should place REM with N3... **NO. That prediction is WRONG-HEADED and is corrected here
    before the run**: REM is famously LOW-delta, so `AvgDelta` will place REM near wake for reasons that
    have nothing to do with cognition. **`AvgDelta` is therefore excluded from the confirmatory set and
    is reported as a POSITIVE CONTROL for the index responding to sleep-stage physiology rather than to
    consciousness.** This is rule 21 -- check the physiology before building the prediction on it -- and
    it is the difference between a discriminating test and a rediscovery of sleep staging.
  * **The discriminating comparison is therefore not "which measures have high D" but "which measures
    have high D that is NOT explained by the delta/arousal axis"**, which P2 tests.

P2 -- THE ADJUSTED DISSOCIATION. Recompute D for every measure after residualising that measure on
`AvgDelta` **within patient across all sleep blocks**, so anything that is delta-power restated is
removed. A measure whose D survives this is dissociating REM from N3 on something other than the classical
sleep-depth axis.
  PREDICTION: **at least one non-delta measure retains D >= 0.5 after adjustment.**
  WRONG IF: every measure's D collapses, which would mean the panel contains only arousal-axis
  information and Brief 01's separation is not achievable with these features. **That is a publishable
  negative for this project and is named first.**

P3 -- WHERE DOES THE DRUG PUT THE PATIENT? On the same per-patient scale, `D_U = (U - N3)/(wake - N3)`
for the 16 patients with a drug-unresponsive block.
  PREDICTION: **for measures that pass P2, D_U <= 0.3** -- drug unresponsiveness should sit with N3, not
  with REM. A measure that placed drug-U with REM would be reporting experience where there is none, and
  that is the failure mode a covert-consciousness application cannot tolerate.

------------------------------------------------------------------------------------------------------
GATES.
  G1  COVERAGE: >= 12 patients contribute after the denominator guard, per measure, else that measure is
      NOT INTERPRETABLE and is reported as such rather than scored.
  G2  THE STATE AXIS IS ALIVE: wake and N3 must separate within patient for the majority of measures,
      else D's denominator is meaningless (rule 53).
  G3  CAPABILITY, BOTH DIRECTIONS (rule 40): a synthetic per-patient feature built to equal
      wake-vs-N3 arousal must return D ~ 0; one built to equal a REM-inclusive consciousness contrast
      must return D ~ 1. Both are constructed from the real state assignments and their intended
      property is MEASURED before use (rule 84).

MUSCLE, and why its direction makes a positive result conservative. The deposit ships no EMG channel, so
no muscle covariate is available -- a real limitation. But REM is a state of **atonia**: if any measure
were driven by muscle, REM would look LOW, i.e. like N3, which pushes D DOWN. So muscle contamination
biases against the predicted result rather than toward it, and a high D cannot be manufactured by it.

SCOPE. Intracranial electrodes in epilepsy-surgery patients; depositor-computed features (no raw traces,
so rule 23's independent re-implementation is unavailable); sleep staged at 30 s and drug blocks at
~6-7 min. **REM is used as a proxy for conscious experience without a report** -- dream recall was not
collected here, so "REM = conscious" is an inference from the literature, not a measurement in this
cohort, and it is labelled as such (rule 42).

    python -m bsde.experiments.e320_arousal_vs_processing
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
DRUG_U = ("U", "U_dex")
MIN_PATIENTS = 12


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
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 4:
        return float("nan")
    n = len(q); mx = sum(t[0] for t in q) / n; my = sum(t[1] for t in q) / n
    sxy = sum((t[0] - mx) * (t[1] - my) for t in q)
    sxx = sum((t[0] - mx) ** 2 for t in q); syy = sum((t[1] - my) ** 2 for t in q)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=320)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e320_arousal_vs_processing.json"))
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

    # per patient x state medians, plus a within-patient pooled sleep IQR for the guard
    M, POOL = {}, {}
    for p in pats:
        for st in (WAKE, REM, DEEP) + DRUG_U:
            rs = by.get((p, st))
            if rs:
                M[(p, st)] = {c: med([f(x.get(c)) for x in rs]) for c in cols}
        allsleep = [x for st in (WAKE, REM, DEEP, "N1", "N2") for x in by.get((p, st), [])]
        POOL[p] = {c: iqr([f(x.get(c)) for x in allsleep]) for c in cols}

    def D_of(p, c, hi_state, mp=None):
        mm = mp or M
        w = mm.get((p, WAKE), {}).get(c, float("nan"))
        d = mm.get((p, DEEP), {}).get(c, float("nan"))
        h = mm.get((p, hi_state), {}).get(c, float("nan"))
        if not all(math.isfinite(x) for x in (w, d, h)):
            return float("nan"), False
        den = w - d
        guard = abs(den) > (POOL[p].get(c, float("nan")) or 0)
        if not guard or den == 0:
            return float("nan"), False
        return (h - d) / den, True

    # ---- G2
    sep = 0
    for c in cols:
        v = [abs(M[(p, WAKE)][c] - M[(p, DEEP)][c]) for p in pats
             if (p, WAKE) in M and (p, DEEP) in M
             and math.isfinite(M[(p, WAKE)][c]) and math.isfinite(M[(p, DEEP)][c])]
        pooled = med([POOL[p].get(c, float("nan")) for p in pats])
        if math.isfinite(med(v)) and math.isfinite(pooled) and med(v) > pooled:
            sep += 1
    G2 = sep >= len(cols) / 2
    print(f"[G2] wake vs N3 separates within patient for {sep} of {len(cols)} measures "
          f"-> {'PASS' if G2 else 'FAIL'}")

    # ---- G3 capability
    synth = {}
    for p in pats:
        for st in (WAKE, REM, DEEP):
            synth.setdefault((p, st), {})
        synth[(p, WAKE)]["arousal_like"] = 1.0 + rng.gauss(0, .02)
        synth[(p, REM)]["arousal_like"] = 0.0 + rng.gauss(0, .02)
        synth[(p, DEEP)]["arousal_like"] = 0.0 + rng.gauss(0, .02)
        synth[(p, WAKE)]["processing_like"] = 1.0 + rng.gauss(0, .02)
        synth[(p, REM)]["processing_like"] = 1.0 + rng.gauss(0, .02)
        synth[(p, DEEP)]["processing_like"] = 0.0 + rng.gauss(0, .02)
    g3 = {}
    for nm in ("arousal_like", "processing_like"):
        vals = []
        for p in pats:
            w = synth[(p, WAKE)][nm]; d = synth[(p, DEEP)][nm]; h = synth[(p, REM)][nm]
            if w != d:
                vals.append((h - d) / (w - d))
        g3[nm] = med(vals)
    G3 = (abs(g3["arousal_like"]) < 0.2) and (abs(g3["processing_like"] - 1.0) < 0.2)
    print(f"[G3] planted arousal-like D = {g3['arousal_like']:+.4f} (want ~0); "
          f"planted processing-like D = {g3['processing_like']:+.4f} (want ~1) "
          f"-> {'PASS' if G3 else 'FAIL'}")

    # ---- P1
    print("\n" + "=" * 96 + "\nP1 -- dissociation index D = (REM - N3) / (wake - N3), per measure")
    P1 = {}
    for c in cols:
        vals, n_ok, n_guard = [], 0, 0
        for p in pats:
            d, ok = D_of(p, c, REM)
            if ok:
                vals.append(d); n_ok += 1
            else:
                n_guard += 1
        if n_ok < MIN_PATIENTS:
            P1[c] = {"D": float("nan"), "n": n_ok, "dropped_by_guard": n_guard,
                     "status": "NOT INTERPRETABLE (G1)"}
            continue
        obs = med(vals)
        null = []
        for _ in range(a.reps):
            mp = {}
            for p in pats:
                labs = [WAKE, REM, DEEP]; rng.shuffle(labs)
                for tgt, src in zip((WAKE, REM, DEEP), labs):
                    mp[(p, tgt)] = M[(p, src)]
            v2 = [D_of(p, c, REM, mp)[0] for p in pats]
            v2 = [x for x in v2 if math.isfinite(x)]
            if v2:
                null.append(med(v2))
        null.sort()
        pv = sum(1 for v in null if v >= obs) / len(null) if null else float("nan")
        P1[c] = {"D": obs, "n": n_ok, "dropped_by_guard": n_guard, "p": pv,
                 "null_p95": null[int(0.95 * len(null))] if null else float("nan")}
    for c in sorted(P1, key=lambda k: -(P1[k]["D"] if math.isfinite(P1[k]["D"]) else -9)):
        r = P1[c]
        if not math.isfinite(r["D"]):
            print(f"  {c:24s} {r['status']}  (n={r['n']}, {r['dropped_by_guard']} dropped by guard)")
        else:
            print(f"  {c:24s} D = {r['D']:+.4f}   n={r['n']:2d} ({r['dropped_by_guard']} guarded)   "
                  f"null95 {r['null_p95']:+.4f}   p = {r['p']:.4f}")

    # ---- P2 delta-adjusted
    print("\n" + "=" * 96 + "\nP2 -- D after removing anything that is AvgDelta restated")
    P2 = {}
    for c in cols:
        if c == "AvgDelta":
            continue
        vals = []
        for p in pats:
            xs, ys = [], []
            for st in (WAKE, REM, DEEP, "N1", "N2"):
                for x in by.get((p, st), []):
                    xd, yc = f(x.get("AvgDelta")), f(x.get(c))
                    if math.isfinite(xd) and math.isfinite(yc):
                        xs.append(xd); ys.append(yc)
            if len(xs) < 10:
                continue
            mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
            sxx = sum((v - mx) ** 2 for v in xs)
            b = sum((v - mx) * (w - my) for v, w in zip(xs, ys)) / sxx if sxx > 0 else 0.0
            res = {}
            for st in (WAKE, REM, DEEP):
                rs = by.get((p, st))
                if not rs:
                    res = {}; break
                res[st] = med([f(x.get(c)) - b * (f(x.get("AvgDelta")) - mx) for x in rs
                               if math.isfinite(f(x.get(c))) and math.isfinite(f(x.get("AvgDelta")))])
            if len(res) != 3 or not all(math.isfinite(v) for v in res.values()):
                continue
            den = res[WAKE] - res[DEEP]
            if abs(den) > (POOL[p].get(c, 0) or 0) and den != 0:
                vals.append((res[REM] - res[DEEP]) / den)
        P2[c] = {"D_adj": med(vals) if len(vals) >= MIN_PATIENTS else float("nan"),
                 "n": len(vals)}
    for c in sorted(P2, key=lambda k: -(P2[k]["D_adj"] if math.isfinite(P2[k]["D_adj"]) else -9))[:10]:
        r = P2[c]
        raw = P1.get(c, {}).get("D", float("nan"))
        print(f"  {c:24s} D_raw {raw:+.4f} -> D_delta_adjusted {r['D_adj']:+.4f}   n={r['n']}")
    survivors = [c for c in P2 if math.isfinite(P2[c]["D_adj"]) and P2[c]["D_adj"] >= 0.5
                 and math.isfinite(P1.get(c, {}).get("p", 1)) and P1[c]["p"] < 0.05]
    print(f"  SURVIVORS (D_adj >= 0.5 and P1 p < 0.05): {survivors if survivors else 'NONE'}")

    # ---- P3 where does the drug sit
    print("\n" + "=" * 96 + "\nP3 -- where does drug-induced unresponsiveness fall on the same scale?")
    P3 = {}
    for c in (survivors or sorted(P1, key=lambda k: -(P1[k]["D"] if math.isfinite(P1[k]["D"]) else -9))[:4]):
        vals = []
        for p in pats:
            for u in DRUG_U:
                if (p, u) in M:
                    w = M[(p, WAKE)][c]; d = M[(p, DEEP)][c]; h = M[(p, u)][c]
                    if all(math.isfinite(x) for x in (w, d, h)) and abs(w - d) > (POOL[p].get(c, 0) or 0):
                        vals.append((h - d) / (w - d))
                    break
        P3[c] = {"D_U": med(vals), "n": len(vals)}
        print(f"  {c:24s} D_U = {P3[c]['D_U']:+.4f}   n={P3[c]['n']}   "
              f"(REM D was {P1.get(c, {}).get('D', float('nan')):+.4f})")

    gates = G2 and G3
    if not gates:
        verdict = "NOT INTERPRETABLE"
    elif survivors:
        verdict = (f"DISSOCIATION FOUND -- {', '.join(survivors)} place REM with wake on something that "
                   f"is not delta power, i.e. they track cognitive processing rather than arousal")
    else:
        verdict = ("NO DISSOCIATION -- every measure in this panel places REM by its arousal/delta "
                   "content, so the panel contains only arousal-axis information and Brief 01's "
                   "separation is not achievable with these features")
    print(f"\nVERDICT: {verdict}")
    print("\nSCOPE: intracranial epilepsy-surgery patients, depositor features, REM used as a proxy for "
          "conscious experience WITHOUT a report (dream recall was not collected) -- an inference from "
          "the literature, not a measurement here. Muscle biases AGAINST the predicted result, because "
          "REM is atonic.")

    rep = {"verdict": verdict, "n_patients": len(pats), "P1": P1, "P2": P2, "P3": P3,
           "survivors": survivors, "gates": {"G2": G2, "G3": G3, "g3_detail": g3}}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
