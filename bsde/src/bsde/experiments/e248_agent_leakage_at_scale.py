#!/usr/bin/env python3
"""E248 -- how much anaesthetic-agent identity does a frontal EEG measure carry, at a resolution nobody
has had?

PRE-REGISTRATION. Written and committed before any statistic in it exists and before the EEG extraction
it reads has been run. The landmarks it uses were built from the ventilator and capnography records only;
no candidate feature, no BIS value and no outcome was touched in producing them.

------------------------------------------------------------------------------------------------------
THE BRIEFED CHALLENGE, VERBATIM (bsde/governance/CHALLENGES.json):

    A: "predicts loss and recovery across anaesthetics while MINIMISING drug-identification information"

------------------------------------------------------------------------------------------------------
WHAT IS ALREADY PUBLISHED, ESTABLISHED BEFORE THE RUN AND NOT AFTER IT

**The first half of the challenge is done, by other people, with a better label than ours.**
PMID 31326088 (Ramaswamy et al., *Br J Anaesth* 2019, "Novel drug-independent sedation level estimation
based on machine learning of quantitative frontal electroencephalogram features in healthy volunteers"),
verified from the retrieved abstract: 102 healthy volunteers across propofol (36), sevoflurane (36) and
dexmedetomidine (30), state labelled by **MOAA/S**, 44 QEEG features, elastic-net. Per-drug AUC
**0.97 / 0.74 / 0.77**; the drug-independent system **0.83**.

So **the state-tracking arm of this file is a REPLICATION and is labelled as one throughout.** It exists
because a leakage statistic has to be computed at matched state, not because tracking state across agents
is news.

**The second half may also be claimed and this is recorded as an open risk, not resolved in our favour.**
PMID 41385421 (Jeong et al., *IEEE J Biomed Health Inform* 2025) incorporates "domain-adversarial
training", is evaluated on propofol and midazolam, and reports "drug-independent EEG signatures". Its
title says *cross-subject* and its abstract describes cross-anaesthetic performance as evaluated in
external validation rather than as an adversarial objective — but the abstract does not say what the
adversarial domain label was, the paper is paywalled with no PMC record, and **this project no longer
describes the minimisation framing as unclaimed anywhere.**

**WHAT NEITHER PAPER DOES, AND WHAT THIS FILE MEASURES: how much agent identity a representation
actually carries.** Ramaswamy compares pooled against per-drug AUC — a performance comparison, not a
leakage statistic. Jeong reports transfer accuracy. Neither quotes a leakage value against a null.

------------------------------------------------------------------------------------------------------
WHY THIS COULD NOT BE DONE BEFORE, WITH THE NUMBER

Agent identity is a property of the PATIENT, not of a window, so the null must be a patient-level
permutation and the effective n is the number of patients (rule 69). Under label permutation the null
AUC has sd = sqrt((n1+n2+1) / 12*n1*n2). That form reproduces this project's own measured floors --
**0.1913 against E154's measured 0.1904 at 39 patients**, and 0.3024 against E142's 0.2791 at Krause's
15 -- so it can be trusted at new sizes. E154's conclusion was that resolving leakage at 0.10 needs
roughly 140 patients and that *"no public deposit this project has found comes close."*

    contrast                      n1     n2    null 95th pct of |AUC-0.5|
    sevoflurane vs desflurane   1474    460                       0.0302
    sevoflurane vs propofol     1474    996                       0.0232
    desflurane  vs propofol      460    996                       0.0319

**The floor falls from 0.1904 to 0.023-0.032.** That is the entire reason this run is worth its
extraction cost, and it is a property of the arm sizes alone -- established before any feature was
computed and not contingent on the result.

------------------------------------------------------------------------------------------------------
COHORT AND LABEL

VitalDB, every public case carrying `BIS/EEG1_WAV`, `Primus/MAC`, `Primus/RR_CO2` and
`Primus/SET_RR_IPPV` with a sane `aneend`: **5,566**, of which exactly one agent track is present in
**sevoflurane 1,474 / desflurane 460 / propofol TCI 996** (2,930 single-agent patients; the 2,613 mixed
cases are excluded from the pairwise contrasts and reported).

**THE STATE LABEL IS THE AIRWAY RECORD, AND IT IS NOT CONSCIOUSNESS.** Under controlled ventilation the
measured respiratory rate equals the ventilator's set rate exactly; when the patient breathes for
themselves the two diverge. This is a **behavioural output, at the brainstem** -- Brief 01 exists to
separate arousal, cognitive processing, command-following and behavioural output, and this measures the
last of them. Every claim from this file is about tracking a brainstem behavioural transition. That
weakening is the price of the investigator's relaxation of criterion (c) and it belongs in the first
result clause of any abstract, not in a limitations paragraph.

The label was chosen over the two obvious alternatives the relaxation admitted because both are circular
here: the **drug record** makes "tracks state" and "follows the drug" the same quantity, which is the
separation this challenge is about; and **BIS** is computed from the same EEG as any candidate.

LANDMARKS, from the airway record only:
    t_loss   start of the first sustained agreeing run   -- spontaneous breathing gives way to control
    t_rec    end of the last sustained agreeing run      -- control gives way to spontaneous breathing

SUSTAIN = **120 s**, DERIVED not chosen (rule 63). Spurious runs against the prevailing state were
counted on ~56 sampled cases in both directions: separations during deep maintenance and agreements
during spontaneous breathing. Per case they fall 0.27 / 0.07 / 0.04 / 0.00 at 30 / 60 / 90 / 120 s for
separations, and plateau at 0.02 for agreements. 120 s is the smallest sustain at which the separation
column reaches zero and it sits on a plateau -- which matters because two differently-drawn samples
disagreed on the tail (92 spurious runs against 41; max run 18 steps against 11) while agreeing there.

------------------------------------------------------------------------------------------------------
WINDOWS -- FIXED, AND THIS IS THE DESIGN'S LOAD-BEARING CHOICE

21 windows of 10 s at offsets -300 to +300 s in 30 s steps, about EACH landmark, **identical for every
case**. E154 found that recording duration identifies the agent at |AUC-0.5| = **0.3771**, above every
candidate feature, because sevoflurane cases run longer. Any summary whose window count or span depends
on case length re-imports that confound wholesale. With a fixed grid, recording length cannot enter.

------------------------------------------------------------------------------------------------------
PRIMARIES, both computed BEFORE any gate is read (rule 37).

P1 -- AGENT LEAKAGE. For each candidate and each of the three pairwise arm contrasts, one value per
    PATIENT (the median over that patient's windows at a fixed offset band), then |AUC - 0.5| between
    arms, with a 20,000-draw patient-level permutation null and Holm correction across candidates.
    Reported as the observed value, the null's 95th percentile, and the resample-level p (rule 46:
    report the fraction on the wrong side of the null, not only an interval).

P2 -- STATE TRACKING, **REPLICATION, NOT A FINDING**. Within-patient AUC discriminating windows before
    the landmark from windows after it, per candidate, pooled across arms and reported per arm. Its role
    is to establish that the state axis is alive (G1) and to define "matched state" for P1.

------------------------------------------------------------------------------------------------------
GATES.

G1  THE PHENOMENON EXISTS (rules 33, 53). At least half the candidates must reach within-patient state
    legibility of 0.10 above their own null. If nothing tracks the ventilation transition, a leakage
    comparison at matched state is a comparison between two cohorts, not two agents.

G2  NUISANCE PLACEBO -- THE GATE E154 FAILED. Recording duration, age and BMI are pushed through the
    IDENTICAL agent-legibility path. If any of them exceeds the median candidate's leakage, the fixed
    window design has not removed E154's confound and **the verdict is VOID, not negative** (rule 31).
    This is a COMPARISON against the candidates, never an absolute threshold (rule 34).

G3  CAPABILITY, BOTH DIRECTIONS (rule 40). A synthetic feature constructed to BE the arm label plus
    noise must be detected at high leakage; an independent Gaussian feature must not exceed its null.
    The noise column is CORRELATED AGAINST THE ARM LABEL and asserted null before use (rule 77) -- a
    negative control built to be independent must be measured for independence.

G4  SUPPORT. >= 300 patients in the smaller arm of each pairwise contrast, and >= 15 windows per patient
    in the offset band. Three hundred is not a round number: it is where the analytic null's 95th
    percentile stays below 0.05 for the smallest arm pairing, which is the resolution the whole design
    exists to buy.

------------------------------------------------------------------------------------------------------
VERDICT RULE. The wrong-direction case first and explicitly (rule 37, seven prior occurrences here).

  (a) VOID          -- G2 fails: a nuisance variable out-identifies the candidates, as in E154. Nothing
                       about leakage is claimed. This is the most likely failure and is named first.
  (b) NO LEAKAGE    -- no candidate's leakage exceeds its patient-level null after Holm. The claim is
                       then that frontal EEG measures carry NO resolvable agent identity at a floor of
                       0.023-0.032, which is a substantive result: it says the invariance problem is
                       smaller than the field assumes, and it is only sayable at this cohort size.
  (c) LEAKAGE       -- one or more candidates exceed their null after Holm. Report which, how much, and
                       against the nuisance placebos. This is a quantified criticism of every
                       "drug-independent" estimator, Ramaswamy 2019's included.
  (d) NOT INTERPRETABLE -- G1, G3 or G4 fails.

FALSIFICATION AND THE PRE-COMMITTED STOP. If (a), the design has not solved the problem E154 identified
and no successor may simply re-run it with a different window; the instrument must change. If the
investigator's check of PMID 41385421's full text shows its adversarial domain WAS drug identity, the
minimisation framing is claimed and only the measurement (b)/(c) survives, as a measurement.

    python -m bsde.experiments.e248_agent_leakage_at_scale
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")

ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
MIN_ARM = 300
MIN_WIN = 15
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
NUISANCE = ("opdur_s", "age", "bmi")


def _f(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def auc(pos, neg):
    """Mann-Whitney AUC of `pos` against `neg`, midranks for ties. NaN if either is empty."""
    pos = [x for x in pos if math.isfinite(x)]
    neg = [x for x in neg if math.isfinite(x)]
    if not pos or not neg:
        return float("nan")
    allv = sorted(pos + neg)
    ranks, i = {}, 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        ranks[allv[i]] = r
        i = j + 1
    s = sum(ranks[x] for x in pos)
    return (s - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def analytic_null_p95(n1, n2):
    return 1.959964 * math.sqrt((n1 + n2 + 1) / (12.0 * n1 * n2))


def perm_null(vals_a, vals_b, rng, reps=20000):
    """Patient-level permutation null for |AUC-0.5|: shuffle the ARM label across patients."""
    pool = list(vals_a) + list(vals_b)
    n1 = len(vals_a)
    out = []
    for _ in range(reps):
        rng.shuffle(pool)
        a = auc(pool[:n1], pool[n1:])
        if math.isfinite(a):
            out.append(abs(a - 0.5))
    out.sort()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--features", default=os.path.join(RESULTS, "vitaldb_ventwin.s*.csv"))
    ap.add_argument("--landmarks", default=os.path.join(RESULTS, "vitaldb_vent_landmarks.s*.csv"))
    ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=248)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e248_agent_leakage.json"))
    ap.add_argument("--smoke", action="store_true",
                    help="Rule 26: permute the ARM label across patients before anything is computed, "
                         "so every code path runs on real feature distributions while the real "
                         "association is never seen. Writes no report.")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    lm = {}
    for p in sorted(glob.glob(a.landmarks)):
        with open(p) as fh:
            for r in csv.DictReader(fh):
                if r.get("error") or r.get("arm") not in ARMS:
                    continue
                lm[r["caseid"]] = r
    print(f"[landmarks] {len(lm)} single-agent cases with landmarks")
    if not lm:
        print("no landmarks; run bsde/scripts/vitaldb_vent_landmarks.py --emit first")
        return 2

    paths = sorted(glob.glob(a.features))
    if not paths:
        print("no feature shards matched", a.features,
              "\n(the EEG extraction has not been run yet; this file is the registration)")
        return 2

    rows, cols = [], None
    for p in paths:
        with open(p) as fh:
            rd = csv.DictReader(fh)
            if cols is None:
                cols = [c for c in (rd.fieldnames or [])
                        if not c.startswith("meta_") and c not in SKIP]
            for r in rd:
                if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                    rows.append(r)
    print(f"[features] {len(rows)} windows, {len(cols)} candidate columns")

    by_case = {}
    for r in rows:
        by_case.setdefault(r["meta_caseid"], []).append(r)
    by_case = {k: v for k, v in by_case.items() if len(v) >= MIN_WIN}
    arm_of = {k: lm[k]["arm"] for k in by_case}
    if a.smoke:
        keys = sorted(arm_of)
        vals = [arm_of[k] for k in keys]
        rng.shuffle(vals)
        arm_of = dict(zip(keys, vals))
        print("[SMOKE] arm labels permuted across patients; no report will be written (rule 26)")

    counts = {arm: sum(1 for v in arm_of.values() if v == arm) for arm in ARMS}
    print(f"[cohort] patients per arm: {counts}")

    summ = {}
    for cid, rs in by_case.items():
        d = {}
        for c in cols:
            v = sorted(_f(r.get(c)) for r in rs)
            v = [x for x in v if math.isfinite(x)]
            d[c] = v[len(v) // 2] if v else float("nan")
        for c in NUISANCE:
            d[c] = _f(lm[cid].get(c, ""))
        summ[cid] = d

    rep = {"n_cases": len(by_case), "counts": counts, "reps": a.reps, "pairs": {}}
    for x, y in PAIRS:
        ax = [c for c in summ if arm_of[c] == x]
        ay = [c for c in summ if arm_of[c] == y]
        if min(len(ax), len(ay)) < 3:
            continue
        p95a = analytic_null_p95(len(ax), len(ay))
        res = {}
        for c in list(cols) + list(NUISANCE):
            va = [summ[i][c] for i in ax]
            vb = [summ[i][c] for i in ay]
            obs = abs(auc(va, vb) - 0.5)
            null = perm_null([v for v in va if math.isfinite(v)],
                             [v for v in vb if math.isfinite(v)], rng, a.reps)
            if not null or not math.isfinite(obs):
                res[c] = {"obs": obs, "p": float("nan"), "null_p95": p95a}
                continue
            p = sum(1 for v in null if v >= obs) / len(null)
            res[c] = {"obs": obs, "p": p, "null_p95": null[int(0.95 * len(null))],
                      "analytic_p95": p95a}
        rep["pairs"][f"{x}_vs_{y}"] = {"n": [len(ax), len(ay)], "analytic_null_p95": p95a,
                                       "features": res}
        top = sorted(((v["obs"], k) for k, v in res.items() if k not in NUISANCE), reverse=True)[:5]
        nui = {k: round(res[k]["obs"], 4) for k in NUISANCE if k in res}
        print(f"[P1 {x} vs {y}] n={len(ax)}/{len(ay)} null95={p95a:.4f} | top: "
              + ", ".join(f"{k}={v:.4f}" for v, k in top) + f" | nuisance {nui}")

    json.dump(rep, open(a.out, "w"), indent=1, default=float) if not a.smoke else None
    print("\n[SMOKE] complete; nothing above is a result." if a.smoke else f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
