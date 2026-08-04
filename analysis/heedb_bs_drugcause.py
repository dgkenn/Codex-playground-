#!/usr/bin/env python3
"""H2 re-test: among patients who ALL have burst suppression, does a drug sufficient to CAUSE it change outcome?

WHY THIS REPLACES THE DEMOTED H2. The pre-registered secondary hypothesis was "iatrogenic suppression carries a
better outcome than injury suppression". It was tested with two defects, both fixed here:

  (1) OUTCOME. It used "a death record exists", which is differentially ascertained across the five modelled
      aetiologies (40.1-61.9 %), so it manufactures spread in the observed direction. This version uses the
      ascertainment-immune outcome: restrict to patients who ALL have a recorded death and model how SOON they
      died. See docs/research/39_HEEDB_FINDINGS.md section 4.
  (2) EXPOSURE. It used "ever received a sedative", 90.1 % prevalent in this cohort and therefore nearly
      contrast-free. This version anchors exposure to the EEG in time and restricts it to agents that can
      actually produce the state.

This also supersedes the older analysis/heedb_bs_iatrogenic.py, which predates the OMOP extraction: that script
inferred "iatrogenic" from the ABSENCE of cerebrovascular diagnosis codes rather than from any drug record, and
scored death from the EEG metadata's DateOfDeath, which is the ascertainment-compromised outcome. Kept for
history; not the basis of any reported figure.

THE EXPOSURE, and why it is the mechanistically right one. Burst suppression is produced by GABA-ergic
anaesthetics at sufficient dose: propofol, the barbiturates (pentobarbital, thiopental, phenobarbital) and
high-dose midazolam. It is NOT produced by dexmedetomidine at clinical doses -- dexmedetomidine acts through
alpha-2 adrenoceptors in locus coeruleus and yields a spindle-rich sleep-like EEG, not suppression. So:

    EXPOSED   = a burst-suppression-capable agent administered within +/- 24 h of the EEG
    UNEXPOSED = burst suppression on the report with NO such agent in that window, i.e. a cortex that suppressed
                with no pharmacological explanation

NEGATIVE-CONTROL EXPOSURE: dexmedetomidine in the same window, entered in the same model. It marks "this patient
was sedated" without marking "this patient received a drug that causes suppression". If the effect is really
about the drug causing the state, dexmedetomidine should not reproduce it; if it does, the signal is
being-sedated-at-all -- a proxy for clinical trajectory -- and the causal reading fails.

REGISTERED PREDICTIONS, stated before running.
  H2a  Peri-EEG exposure to a BS-capable anaesthetic predicts a NEGATIVE 30-day coefficient: suppression that a
       drug explains occurs in brains that are not dying, whereas suppression with no drug to explain it implies
       injury severe enough to suppress cortex unaided.
       FALSIFIED IF the coefficient is positive, or its interval covers zero with a point estimate above -2 pp.
  H2b  NEGATIVE CONTROL: dexmedetomidine should be NULL -- interval covering zero, point estimate materially
       smaller in magnitude than H2a.
       THE WHOLE TEST FAILS IF dexmedetomidine reproduces H2a.

  WHY H2a IS A SIGNED PREDICTION AND NOT A NULL. An earlier prediction in this project failed by equating
  "pharmacological" with "benign" (docs/LESSONS.md: epilepsy-without-status came out +2.13 pp ns where a negative
  was predicted). The distinction is real and worth stating: that test asked whether a pharmacological AETIOLOGY
  carries a protective signal in absolute terms, and the correct answer was that it carries no information at
  all. This test is a contrast BETWEEN PATIENTS WHO ALL SHARE THE SAME EEG FINDING, asking whether the presence
  of a sufficient drug cause distinguishes them. Only the second licenses a signed prediction.

CONFOUNDING, stated in advance and not resolvable here. Sedation is not randomised. Patients close to death may
have sedation withdrawn, which would produce this association with no causal role for the drug; agitated and
salvageable patients receive more. Aetiology terms are held in the model. This is an association, and the
negative control bounds one alternative explanation, not all of them.

Helpers are imported from the validated modules rather than reimplemented.
"""
import csv, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt, eeg_times

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))
WIN_H = float(os.environ.get("WIN_H", "24"))

BS_CAPABLE = ("propofol", "pentobarbital", "thiopental", "phenobarbital", "midazolam")
NEG_CONTROL = ("dexmedetomidine", "precedex")


def main():
    rng = np.random.default_rng(20260725)
    pids = {int(x) for x in open("/tmp/heedb_bs_patients.txt").read().split() if x.strip().isdigit()}

    aet, cond_seen = defaultdict(set), set()
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, pre in AETIOLOGY.items():
                if any(c.startswith(x) for x in pre):
                    aet[p].add(lab)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    et = eeg_times()

    exp_bs, exp_nc, drug_seen = set(), set(), set()
    with open(f"{OMOP}/drug_exposure.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            drug_seen.add(p)
            t = et.get(p)
            if t is None:
                continue
            s = dt(r.get("drug_exposure_start_datetime"))
            if s is None:
                continue
            if abs((s - t).total_seconds()) > WIN_H * 3600.0:
                continue
            v = (r.get("drug_source_value") or "").lower()
            if any(x in v for x in BS_CAPABLE):
                exp_bs.add(p)
            if any(x in v for x in NEG_CONTROL):
                exp_nc.add(p)

    base = sorted(pids & cond_seen)
    rows = []
    keys = list(AETIOLOGY)
    for p in base:
        d, t = death.get(p), et.get(p)
        # require a drug record for the patient, else "unexposed" would conflate "no drug given" with
        # "this patient's medication history was never extracted"
        if d is None or t is None or p not in drug_seen:
            continue
        days = (d - t).days
        if days < -1:
            continue
        labs = aet.get(p, set())
        rows.append(dict(d30=1.0 if days <= 30 else 0.0, d90=1.0 if days <= 90 else 0.0,
                         bs_drug=1.0 if p in exp_bs else 0.0,
                         dexmed=1.0 if p in exp_nc else 0.0,
                         **{k: (1.0 if k in labs else 0.0) for k in keys}))
    n = len(rows)
    print(f"analysable (death record + EEG time + drug record): {n} patients   window +/-{WIN_H:.0f} h")
    if n < 300:
        print("insufficient"); return 1
    pe = float(np.mean([r["bs_drug"] for r in rows])); pn = float(np.mean([r["dexmed"] for r in rows]))
    print(f"  peri-EEG BS-capable anaesthetic    : {100*pe:5.1f} %  (n={int(round(pe*n))})")
    print(f"  peri-EEG dexmedetomidine (neg ctrl): {100*pn:5.1f} %  (n={int(round(pn*n))})")
    if pe < 0.03 or pe > 0.97:
        print("  *** exposure has almost no contrast at this window; result NOT interpretable")
        return 1

    expo = ["bs_drug"] + (["dexmed"] if 0.02 < pn < 0.98 else []) \
           + [k for k in keys if sum(r[k] for r in rows) >= 30]
    if "dexmed" not in expo:
        print("  *** dexmedetomidine too rare/ubiquitous to serve as a negative control at this window")
    for out, lab in (("d30", "death within 30 days"), ("d90", "death within 90 days")):
        y = np.asarray([r[out] for r in rows], float)
        X = np.column_stack([np.ones(n)] + [np.asarray([r[k] for r in rows], float) for k in expo])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        boots = defaultdict(list)
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            try:
                bb = np.linalg.lstsq(X[i], y[i], rcond=None)[0]
            except Exception:
                continue
            for j, k in enumerate(expo, 1):
                boots[k].append(bb[j])
        print(f"\n   --- {lab} (baseline {100*y.mean():.1f} %) ---")
        for j, k in enumerate(expo, 1):
            lo, hi = np.percentile(boots[k], [2.5, 97.5])
            star = "*" if lo > 0 or hi < 0 else "ns"
            note = {"bs_drug": "   <-- H2a: predicted NEGATIVE",
                    "dexmed": "   <-- H2b negative control: predicted NULL"}.get(k, "")
            print(f"      {k:14s} {100*b[j]:+7.2f} pp [{100*lo:+7.2f},{100*hi:+7.2f}] {star}{note}")

    print("\n   Sedation is not randomised. Patients close to death may have sedation withdrawn, which would")
    print("   produce this association with no causal role for the drug. This is an association; the negative")
    print("   control bounds one alternative explanation, not all of them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
