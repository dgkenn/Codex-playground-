#!/usr/bin/env python3
"""E330 -- what actually kills a pre-registered biomarker experiment? 225 of them, with the record intact.

PRE-REGISTRATION. Committed before any statistic in it exists. This is META-RESEARCH on this project's
own registration ledger, not a new claim about the brain.

THE ASSET, AND WHY IT IS RARE. Published EEG-consciousness literature contains survivors. An experiment
that died because its gate could not fire, its placebo could not be built, its incumbent turned out to be
dead, or its statistic was passed by noise **does not become a paper**, so the field has no denominator.
This project has registered every design before running it -- 225 of them, each with its primary, its
gates, its placebo, its incumbent and its outcome, in an append-only ledger whose rows cannot be edited
except to attach an outcome. **That is a denominator, and it is the only one I am aware of for this
question.**

WHAT IS BEING MEASURED
  M1  The outcome distribution, and specifically the fraction that died on MACHINERY (`gate_failed`)
      rather than on biology (`positive`/`negative`/`absent`).
  M2  The publication-visible rate: what an outside reader would infer if only positives were reported,
      against the true rate in the register.
  M3  Whether the machinery-failure rate FALLS over the programme's life as its error catalogue grows --
      a learning curve. Registered dates are in the ledger.
  M4  Reversals: registered outcomes later withdrawn or overturned, as a fraction of positives.
  M5  Whether experiments carrying MORE gates fail more often on machinery, and whether that is a defect
      or the mechanism working.

PREDICTIONS, committed before computing any of it:
  P1  **Machinery failure is >= 15 % of all registrations.** If the gate discipline is doing anything, a
      substantial minority of designs must die before reaching their hypothesis.
  P2  **The positive fraction is <= 40 %**, so a positives-only literature would overstate the success
      rate by more than a factor of two.
  P3  **The machinery-failure rate falls between the first and second half of the programme.** The error
      catalogue grew from 25 rules to 97 over that span; if it is worth anything, later designs should
      die on machinery less often.
      WRONG IF it rises or is flat -- which would mean the catalogue documents failures without
      preventing them, and that is the more important result and is named first.
  P4  **More gates associates with more machinery failure**, and this is reported as the discipline
      working rather than as a defect -- a gate that never fires is rule 40's dead gate.

**THE LIMITATION THAT BOUNDS EVERY NUMBER HERE, stated before the run.** This is ONE programme, on
anaesthesia and sleep EEG, with a single analyst lineage. It is not a sample of the field. The
generalisable object is the **method** -- keep an append-only register with gates and outcomes, and these
quantities become measurable -- and the specific rates are this programme's, not anyone else's. No
sentence from this file may be written as a claim about how other laboratories fare.

    python -m bsde.experiments.e330_ledger_metascience
"""
from __future__ import annotations

import argparse, collections, json, math, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LEDGER = os.path.join(ROOT, "governance", "REGISTRATION_LEDGER.jsonl")

CANON = {"positive", "negative", "absent", "gate_failed", "blocked", "withdrawn", "closed",
         "registered", "mixed"}


def canon(o):
    """Map a free-text outcome onto its canonical class by its leading token."""
    o = (o or "").strip().lower()
    for k in ("gate_failed", "withdrawn", "blocked", "closed", "absent", "mixed",
              "positive", "negative", "registered"):
        if o.startswith(k):
            return k
    if "not confirmed" in o or "refuted" in o:
        return "negative"
    if "confirmed" in o:
        return "positive"
    return "other"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "e330_ledger_metascience.json"))
    a = ap.parse_args(argv)

    rows = [json.loads(l) for l in open(a.ledger) if l.strip()]
    n = len(rows)
    cls = [canon(r.get("outcome")) for r in rows]
    cnt = collections.Counter(cls)
    print(f"[ledger] {n} registrations\n")

    print("=" * 84 + "\nM1 -- outcome distribution")
    for k, v in cnt.most_common():
        print(f"  {k:14s} {v:4d}   {v/n:6.1%}")
    mach = cnt["gate_failed"]
    print(f"\n  MACHINERY FAILURE (gate_failed): {mach} of {n} = {mach/n:.1%}")
    p1 = mach / n >= 0.15
    print(f"  PREDICTED >= 15%  ->  {'MET' if p1 else 'NOT MET'}")

    print("\n" + "=" * 84 + "\nM2 -- what a positives-only literature would show")
    pos = cnt["positive"]
    concl = pos + cnt["negative"] + cnt["absent"]
    print(f"  positives                         {pos:4d}")
    print(f"  reached a biological conclusion   {concl:4d}  (positive + negative + absent)")
    print(f"  registered but never concluded    {n - concl:4d}")
    print(f"  TRUE positive rate over all registrations : {pos/n:.1%}")
    print(f"  positive rate among those that concluded  : {pos/concl:.1%}")
    print(f"  a positives-only literature implies       : 100%")
    print(f"  OVERSTATEMENT FACTOR                      : {1.0/(pos/n):.2f}x")
    p2 = pos / n <= 0.40
    print(f"  PREDICTED positive fraction <= 40%  ->  {'MET' if p2 else 'NOT MET'}")

    print("\n" + "=" * 84 + "\nM3 -- does machinery failure fall as the error catalogue grows?")
    dated = [(r.get("registered_date") or "", canon(r.get("outcome"))) for r in rows]
    dated = [d for d in dated if re.match(r"\d{4}-\d{2}-\d{2}", d[0])]
    dated.sort()
    half = len(dated) // 2
    for nm, seg in (("first half", dated[:half]), ("second half", dated[half:])):
        m = sum(1 for _, c in seg if c == "gate_failed")
        print(f"  {nm:12s} {seg[0][0]} .. {seg[-1][0]}   {m}/{len(seg)} = {m/len(seg):6.1%}")
    m1 = sum(1 for _, c in dated[:half] if c == "gate_failed") / max(1, half)
    m2 = sum(1 for _, c in dated[half:] if c == "gate_failed") / max(1, len(dated) - half)
    p3 = m2 < m1
    print(f"  change: {m1:.1%} -> {m2:.1%}   PREDICTED a fall  ->  {'MET' if p3 else 'NOT MET'}")
    if not p3:
        print("  NOTE: a flat or rising rate is the MORE important result -- it would mean the catalogue")
        print("        documents failures without preventing them.")

    print("\n" + "=" * 84 + "\nM4 -- reversals")
    wd = cnt["withdrawn"]
    detail = " ".join((r.get("outcome_detail") or "").lower() for r in rows)
    revwords = sum(detail.count(w) for w in ("overturn", "withdraw", "reversed", "retract",
                                             "supersed", "corrected"))
    print(f"  outcome == withdrawn                     {wd:4d}  ({wd/n:.1%})")
    print(f"  reversal language in outcome_detail      {revwords:4d} mentions across the register")
    print(f"  positives that were later qualified in their own detail text: "
          f"{sum(1 for r in rows if canon(r.get('outcome')) == 'positive' and any(w in (r.get('outcome_detail') or '').lower() for w in ('but ', 'however', 'qualif', 'caveat', 'not licensed')))}")

    print("\n" + "=" * 84 + "\nM5 -- gates carried vs machinery failure")
    byg = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        g = len(r.get("gates") or [])
        b = byg[min(g, 5)]
        b[1] += 1
        if canon(r.get("outcome")) == "gate_failed":
            b[0] += 1
    for g in sorted(byg):
        f_, t = byg[g]
        print(f"  {g if g < 5 else '5+'} gates: {f_:3d}/{t:3d} machinery failures = "
              f"{(f_/t if t else 0):6.1%}")
    lo = sum(byg[g][0] for g in byg if g <= 2) / max(1, sum(byg[g][1] for g in byg if g <= 2))
    hi = sum(byg[g][0] for g in byg if g >= 4) / max(1, sum(byg[g][1] for g in byg if g >= 4))
    p4 = hi > lo
    print(f"  <=2 gates {lo:.1%}  vs  >=4 gates {hi:.1%}   PREDICTED more gates -> more failures  "
          f"->  {'MET' if p4 else 'NOT MET'}")

    print("\n" + "=" * 84)
    print("LIMITATION, registered before the run: ONE programme, anaesthesia/sleep EEG, a single analyst")
    print("lineage. Not a sample of the field. The generalisable object is the METHOD -- keep an")
    print("append-only register with gates and outcomes and these quantities become measurable -- not")
    print("the specific rates, which are this programme's alone.")

    rep = {"n": n, "outcomes": dict(cnt), "machinery_rate": mach / n,
           "positive_rate_all": pos / n, "positive_rate_concluded": pos / concl,
           "overstatement_factor": 1.0 / (pos / n),
           "machinery_first_half": m1, "machinery_second_half": m2,
           "withdrawn": wd, "reversal_mentions": revwords,
           "gates_vs_failure": {str(k): v for k, v in byg.items()},
           "predictions": {"P1": p1, "P2": p2, "P3": p3, "P4": p4}}
    json.dump(rep, open(a.out, "w"), indent=1, default=float)
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
