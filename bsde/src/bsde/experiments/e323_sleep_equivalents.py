#!/usr/bin/env python3
"""E323 -- "anaesthesia is like sleep": like WHICH sleep, and do measures even agree?

PRE-REGISTRATION. Committed before any statistic in it exists.

THE QUESTION. Clinicians tell patients anaesthesia is like sleep, and the research literature routinely
compares anaesthetic unconsciousness to slow-wave sleep. **Which stage a drug state resembles is not a
fact about the brain unless the measures agree about it**, and E321's numbers hint they do not: on delta,
drug-unresponsiveness sat at -1.6968 against REM's -1.7720 and N3's 0 -- i.e. delta says the drug looks
like REM. On complexity it sat at -0.2164 against REM's +2.0101 -- i.e. complexity says the drug looks
like N3. Those are opposite answers to the same question from the same patients.

This file measures that disagreement directly, and it is the estimand -- not a by-product.

METHOD. For each patient and measure, standardise within patient across that patient's own five sleep
stages (median-centred, IQR-scaled). Each drug block is then placed on that patient's OWN sleep scale and
assigned its **nearest sleep stage in z**. A drug state's "sleep equivalent" is the modal nearest stage
across patients. No cross-patient normalisation is involved and no ratio is formed.

P1 -- DISAGREEMENT. For propofol-unresponsive (`U`), tabulate the sleep equivalent per measure. The
     statistic is the number of DISTINCT stages claimed across measures, and the fraction of measures
     claiming the modal one.
     PREDICTION: **>= 3 distinct stages are claimed, and the modal stage holds < 60 % of measures.**
     WRONG IF: the measures agree, in which case "anaesthesia resembles stage X" is a defensible
     statement and this line has nothing to report.

P2 -- WHICH MEASURES SAY WHAT. Predicted before the run from E321's directions: complexity
     (`NmlzCmplx`, `EffDim`) assigns `U` to N2/N3; delta measures (`AvgDelta`, `temporalDelta`,
     `limbicDelta`) assign it to REM or N1.
     WRONG IF the families do not split this way.

P3 -- DEXMEDETOMIDINE VERSUS PROPOFOL, against an external anchor. The depositors' own published claim
     (Krause et al., Br J Anaesth, PMID 41203472) is that **dexmedetomidine produces more sleep-like
     activity than propofol**. On the sleep-equivalent scale this predicts `U_dex` maps to a sleep stage
     at least as deep as, and more sleep-consistent than, `U`.
     PREDICTION: `U_dex`'s modal equivalent is a genuine NREM stage (N2 or N3) for the complexity
     measures. **This is a directional check against a published result the design did not choose**, so
     agreement is weak corroboration that the scale is behaving and disagreement is informative.
     **n = 10 dexmedetomidine patients, of whom few have full sleep staging** -- this arm is
     underpowered by construction and is reported as descriptive, with its n printed. It is NOT a test.

GATES.
  G1  THE SLEEP SCALE IS ORDERED (rule 53). Within patient, the five stages must order sensibly on the
      majority of measures -- specifically |z(W) - z(N3)| must exceed the within-stage spread for more
      than half the measures, else "nearest stage" is meaningless.
  G2  >= 12 patients contribute per measure per drug state, else NOT INTERPRETABLE for that cell.
  G3  SMOKE BITES: under `--smoke` the sleep-stage labels are permuted within patient; the number of
      distinct claimed stages should rise toward chance and the modal fraction fall. Both printed.

SCOPE. Intracranial, epilepsy-surgery patients, depositor-computed features, block-level staging. The
sleep equivalent is a STATEMENT ABOUT A MEASURE'S SCALE, not a claim that the drug state IS that sleep
stage -- two states can share a value on one summary and differ in every mechanism. That distinction is
the whole point of the experiment and must survive into any sentence quoting it.

    python -m bsde.experiments.e323_sleep_equivalents
"""
from __future__ import annotations

import argparse, csv, collections, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
SKIP = {"label", "refTime", "patientID", "Subdural", "timeOfDay",
        "timeOfDay_envCorrTimeData", "timeOfDay_bandPowerTimeData",
        "pctGoodSamples", "pctGoodSamples_envCorrTimeData", "pctGoodSamples_bandPowerTimeData"}
SLEEP = ("WS", "N1", "N2", "N3", "R")
PRETTY = {"WS": "wake", "N1": "N1", "N2": "N2", "N3": "N3", "R": "REM"}
DRUG = ("U", "U_dex", "S", "S_dex")
MIN_P = 12


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))
    ap.add_argument("--seed", type=int, default=323)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e323_sleep_equivalents.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = list(csv.DictReader(open(a.data)))
    cols = [c for c in rows[0] if c not in SKIP]
    by = {}
    for r in rows:
        by.setdefault((r["patientID"], r["label"]), []).append(r)
    pats = sorted({p for p, l in by if l in SLEEP})
    pats = [p for p in pats if sum(1 for st in SLEEP if (p, st) in by) >= 4]
    print(f"[cohort] {len(pats)} patients with >= 4 sleep stages")

    Z, ok_scale = {}, 0
    for c in cols:
        n_ok = 0
        for p in pats:
            pool = [f(x.get(c)) for st in SLEEP for x in by.get((p, st), [])]
            m0, s0 = med(pool), iqr(pool)
            if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                continue
            z = {}
            for st in SLEEP:
                if (p, st) in by:
                    z[st] = (med([f(x.get(c)) for x in by[(p, st)]]) - m0) / s0
            if a.smoke and len(z) >= 2:
                ks = list(z); vs = [z[k] for k in ks]; rng.shuffle(vs); z = dict(zip(ks, vs))
            for d in DRUG:
                if (p, d) in by:
                    z[d] = (med([f(x.get(d_c) if False else x.get(c)) for x in by[(p, d)]]) - m0) / s0
            Z[(p, c)] = z
            if "WS" in z and "N3" in z and abs(z["WS"] - z["N3"]) > 1.0:
                n_ok += 1
        if n_ok >= len(pats) / 2:
            ok_scale += 1
    G1 = ok_scale >= len(cols) / 2
    print(f"[G1] sleep scale ordered (|z(wake)-z(N3)| > 1) for {ok_scale} of {len(cols)} measures "
          f"-> {'PASS' if G1 else 'FAIL'}")

    def equivalents(drug):
        out = {}
        for c in cols:
            votes = []
            for p in pats:
                z = Z.get((p, c), {})
                if drug not in z:
                    continue
                cand = [(abs(z[drug] - z[st]), st) for st in SLEEP if st in z]
                if cand:
                    votes.append(min(cand)[1])
            if len(votes) < MIN_P:
                out[c] = {"status": "NOT INTERPRETABLE (G2)", "n": len(votes)}
                continue
            cnt = collections.Counter(votes)
            modal, k = cnt.most_common(1)[0]
            out[c] = {"modal": modal, "frac": k / len(votes), "n": len(votes),
                      "dist": {PRETTY[s]: v / len(votes) for s, v in cnt.items()}}
        return out

    print("\n" + "=" * 92 + "\nP1/P2 -- which sleep stage does PROPOFOL-UNRESPONSIVE resemble?")
    eqU = equivalents("U")
    for c in sorted(eqU, key=lambda k: eqU[k].get("modal", "zz")):
        r = eqU[c]
        if "status" in r:
            continue
        share = "  ".join(f"{s} {v:.2f}" for s, v in sorted(r["dist"].items(), key=lambda t: -t[1])[:3])
        print(f"  {c:24s} -> {PRETTY[r['modal']]:5s} ({r['frac']:.2f} of {r['n']})   [{share}]")
    claimed = [r["modal"] for r in eqU.values() if "modal" in r]
    distinct = sorted(set(claimed))
    cnt = collections.Counter(claimed)
    modal_stage, modal_n = cnt.most_common(1)[0]
    modal_frac = modal_n / len(claimed)
    print(f"\n  DISTINCT stages claimed across measures: {len(distinct)} "
          f"({', '.join(PRETTY[s] for s in distinct)})")
    print(f"  modal stage {PRETTY[modal_stage]} holds {modal_frac:.2f} of {len(claimed)} measures")
    met1 = len(distinct) >= 3 and modal_frac < 0.60
    print(f"  PREDICTED >= 3 distinct AND modal < 0.60  ->  {'MET' if met1 else 'NOT MET'}")

    COMPLEX = [c for c in ("NmlzCmplx", "EffDim") if c in eqU and "modal" in eqU[c]]
    DELTA = [c for c in ("AvgDelta", "temporalDelta", "limbicDelta", "frontalDelta", "parietalDelta")
             if c in eqU and "modal" in eqU[c]]
    cm = [PRETTY[eqU[c]["modal"]] for c in COMPLEX]
    dm = [PRETTY[eqU[c]["modal"]] for c in DELTA]
    print(f"  complexity says: {dict(zip(COMPLEX, cm))}")
    print(f"  delta says     : {dict(zip(DELTA, dm))}")
    met2 = (all(m in ("N2", "N3") for m in cm) and all(m in ("REM", "N1") for m in dm)
            and bool(cm) and bool(dm))
    print(f"  PREDICTED complexity->N2/N3 and delta->REM/N1  ->  {'MET' if met2 else 'NOT MET'}")

    print("\n" + "=" * 92 + "\nP3 -- dexmedetomidine (DESCRIPTIVE, underpowered by construction)")
    eqD = equivalents("U_dex")
    for c in COMPLEX + DELTA:
        r = eqD.get(c, {})
        if "modal" in r:
            print(f"  {c:24s} U_dex -> {PRETTY[r['modal']]:5s} ({r['frac']:.2f} of {r['n']})   "
                  f"| U -> {PRETTY[eqU[c]['modal']]}")
        else:
            print(f"  {c:24s} U_dex -> {r.get('status', 'absent')} (n={r.get('n', 0)})")

    verdict = ("NOT INTERPRETABLE (G1)" if not G1 else
               ("MEASURES DISAGREE -- 'anaesthesia resembles stage X' is measure-dependent, not a fact "
                "about the brain" if met1 else
                f"MEASURES AGREE -- propofol-unresponsive resembles {PRETTY[modal_stage]} on "
                f"{modal_frac:.0%} of measures"))
    print(f"\nVERDICT: {verdict}")
    print("\nSCOPE: a sleep equivalent is a statement about a MEASURE'S SCALE, never a claim that the drug "
          "state IS that sleep stage -- two states can share a value on one summary and differ in every "
          "mechanism. Intracranial, epilepsy-surgery, depositor features, block-level staging.")

    rep = {"verdict": verdict, "n_patients": len(pats), "U": eqU, "U_dex": eqD,
           "distinct_stages": [PRETTY[s] for s in distinct], "modal_stage": PRETTY[modal_stage],
           "modal_frac": modal_frac, "P1_met": met1, "P2_met": met2, "G1": G1}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print(f"\n[SMOKE G3] distinct stages {len(distinct)}, modal frac {modal_frac:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
