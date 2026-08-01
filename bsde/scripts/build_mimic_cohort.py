"""Challenge D substrate, assembled: one row per RASS observation with its sedative exposure history.

The extraction (`extract_mimic_sedation.py`) finished at 3,041,306 chartevents rows -- **1,656,001 RASS
observations across 83,575 ICU stays, 78,215 of them with three or more** -- plus 1,063,309 sedative
infusion segments over 35,325 stays. This script joins them and computes the exposure model
`CHALLENGE_D_PREREGISTRATION.md` commits a prediction about, so the experiment that reads the output can
be a pure analysis (rule 10: a per-subject aggregation is an analysis decision and belongs in the
experiment, not the extractor -- what belongs here is the join and the pharmacokinetics).

PARSING, WHICH `CHALLENGE_D_PREREGISTRATION.md` MADE GATE G4. RASS is stored as free text with a leading
signed integer. There are **exactly ten distinct strings** across 1.66 M rows and every one begins with
its numeric value -- `' 0  Alert and calm'`, `'-5 Unarousable, no response to voice or physical
stimulation'`, `'+4 Combative, violent, danger to staff'`. The parse takes the leading token; the
unparsed count is written to the manifest rather than silently dropped.

UNITS. `amount` is mg for propofol, midazolam and ketamine, mcg for dexmedetomidine and (mostly) fentanyl,
with a minority of fentanyl rows in mg. Everything is converted to **mg** from `amountuom`, per row, never
from the drug name -- 1,321 dexmedetomidine rows are in mg while 47,047 are in mcg, so a per-drug constant
would have been wrong for both.

EXPOSURE MODEL, matching E122's ladder so the transport comparison is like-for-like:
    L0  cumulative mg administered before the observation, per drug
    L2  the eight-half-life exponential basis from `bsde.pkpd.propofol.infusion_basis`, per drug -- the
        same object E122 used, verified there against an independent forward-Euler ODE at R^2 = 1.000000
Each `inputevents` row is a segment with a start, an end and a total amount, which is exactly the
constant-rate-infusion form `infusion_basis` takes.

**GOAL RASS RIDES ALONG.** `228299 Goal Richmond-RAS Scale` is carried as the most recent goal charted
before each observation. E127 killed E126 by showing the residual LEADS the concentration direction --
clinicians withhold drug from a patient who already looks deeper than intended -- and DOSE-I records no
target, so the confound could be detected and never removed. This is the column that makes it
conditionable, and it is extracted here so the experiment does not have to reach back into a 395 MB file.

COHORT CAP. `--max-stays` selects a random subset with a fixed seed, declared before the analysis, so the
compute is bounded without the selection being outcome-dependent. Stays are the sampling unit.

    python bsde/scripts/build_mimic_cohort.py --max-stays 4000
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
RASS = os.path.join(RESULTS, "mimic_rass.csv")
DRUGS = os.path.join(RESULTS, "mimic_sedative_inputevents.csv")
OUT = os.path.join(RESULTS, "mimic_cohort.csv")

DRUG_NAMES = ("propofol", "midazolam", "ketamine", "dexmedetomidine", "fentanyl", "fentanyl_conc")
TO_MG = {"mg": 1.0, "mcg": 1e-3, "ug": 1e-3, "g": 1000.0}
MIN_RASS = 3
# HORIZON, and the first choice was WRONG in the direction of my own prediction, which is why it changed.
# The declared basis was (2, 8, 32, 128) minutes. A smoke run over 30 stays showed the median observation
# sits 152 HOURS into the stay, at which point the 8-minute term has median 7.2e-105 and even the
# 128-minute term has median 6.6e-05 -- so the basis is numerically a single-term model at ICU timescales
# and could not represent the exposure at all. `CHALLENGE_D_PREREGISTRATION.md` predicts transport FAILS
# (rho < +0.25); a basis with no dynamic range would confirm that prediction for the wrong reason, so
# leaving it would have been the one change I am not entitled to make. The span is extended to cover
# minutes through 34 hours. This is a HORIZON decision made from the exposure's own time axis with no
# candidate-outcome relationship examined (rule 44: declare which is preserved -- here the question is
# preserved and the resolution is widened).
HALF_LIVES = (2.0, 8.0, 32.0, 128.0, 512.0, 2048.0)


def _ts(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()
    except (TypeError, ValueError):
        return float("nan")


def _f(s, d=float("nan")):
    try:
        v = float(s)
        return v if math.isfinite(v) else d
    except (TypeError, ValueError):
        return d


def parse_rass(v):
    """Leading signed integer of the free-text RASS string. Returns None if it does not parse."""
    t = (v or "").strip().split()
    if not t:
        return None
    try:
        return int(t[0])
    except ValueError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-stays", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=160)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    csv.field_size_limit(10 ** 7)

    # ---- pass 1: which stays have a sedative record --------------------------------------------------
    drug_stays = set()
    with open(DRUGS, newline="") as fh:
        for r in csv.DictReader(fh):
            drug_stays.add(r["stay_id"])
    print(f"{len(drug_stays):,} stays with a sedative record", flush=True)

    # ---- pass 2: RASS counts, and the parse audit ----------------------------------------------------
    counts = defaultdict(int)
    unparsed, seen_vals = 0, set()
    with open(RASS, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] != "rass":
                continue
            seen_vals.add(r["value"])
            if parse_rass(r["value"]) is None:
                unparsed += 1
                continue
            if r["stay_id"] in drug_stays:
                counts[r["stay_id"]] += 1
    elig = sorted(s for s, n in counts.items() if n >= MIN_RASS)
    print(f"G4 PARSE  {len(seen_vals)} distinct RASS strings, {unparsed:,} unparsed", flush=True)
    print(f"{len(elig):,} stays with a sedative record and >= {MIN_RASS} RASS observations", flush=True)

    rng = random.Random(a.seed)
    keep = set(elig if len(elig) <= a.max_stays else rng.sample(elig, a.max_stays))
    print(f"sampling {len(keep):,} stays (seed {a.seed})", flush=True)

    # ---- pass 3: the observations and the goals ------------------------------------------------------
    obs = defaultdict(list)
    goals = defaultdict(list)
    with open(RASS, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["stay_id"] not in keep:
                continue
            t = _ts(r["charttime"])
            v = parse_rass(r["value"])
            if not math.isfinite(t) or v is None:
                continue
            (obs if r["kind"] == "rass" else goals)[r["stay_id"]].append((t, v))
    for d in (obs, goals):
        for k in d:
            d[k].sort()

    # ---- pass 4: the infusion segments ---------------------------------------------------------------
    seg = defaultdict(lambda: defaultdict(list))
    weight = {}
    with open(DRUGS, newline="") as fh:
        for r in csv.DictReader(fh):
            sid = r["stay_id"]
            if sid not in keep:
                continue
            t0, t1 = _ts(r["starttime"]), _ts(r["endtime"])
            mg = _f(r["amount"]) * TO_MG.get((r["amountuom"] or "").strip().lower(), float("nan"))
            if not (math.isfinite(t0) and math.isfinite(t1) and math.isfinite(mg)) or mg <= 0:
                continue
            if t1 < t0:
                t0, t1 = t1, t0
            d = r["drug"]
            if d == "fentanyl_conc":
                d = "fentanyl"
            seg[sid][d].append((t0, max(t1, t0 + 1.0), mg))
            w = _f(r.get("patientweight", ""))
            if math.isfinite(w) and w > 0:
                weight[sid] = w
    print(f"segments assembled for {len(seg):,} stays", flush=True)

    from bsde.pkpd.propofol import infusion_basis

    fields = (["stay_id", "subject_id", "t", "rass", "goal_rass", "hours_in", "weight_kg", "n_obs"]
              + [f"cum_{d}" for d in ("propofol", "midazolam", "ketamine", "dexmedetomidine", "fentanyl")]
              + [f"k{h:g}_{d}" for d in ("propofol", "midazolam", "ketamine", "dexmedetomidine",
                                         "fentanyl") for h in HALF_LIVES])
    n = 0
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for i, sid in enumerate(sorted(keep), 1):
            ob = obs.get(sid) or []
            if len(ob) < MIN_RASS:
                continue
            t0 = ob[0][0]
            times = np.array([t for t, _ in ob], float)
            row_base = {"stay_id": sid, "weight_kg": f"{weight.get(sid, float('nan')):g}",
                        "n_obs": len(ob)}
            cum, kin = {}, {}
            for d in ("propofol", "midazolam", "ketamine", "dexmedetomidine", "fentanyl"):
                s = seg[sid].get(d) or []
                if s:
                    st = np.array([x[0] for x in s], float)
                    en = np.array([x[1] for x in s], float)
                    mg = np.array([x[2] for x in s], float)
                    rate = mg / np.maximum(en - st, 1.0)
                    cum[d] = np.array([mg[(en <= t)].sum() +
                                       (rate[(st < t) & (en > t)] * (t - st[(st < t) & (en > t)])).sum()
                                       for t in times], float)
                    B = infusion_basis(st, en, rate, times, half_lives_min=HALF_LIVES)
                    kin[d] = np.asarray(B, float)
                else:
                    cum[d] = np.zeros(len(times))
                    kin[d] = np.zeros((len(times), len(HALF_LIVES)))
            gl = goals.get(sid) or []
            gt = np.array([t for t, _ in gl], float) if gl else np.zeros(0)
            gv = np.array([v for _, v in gl], float) if gl else np.zeros(0)
            for j, (t, v) in enumerate(ob):
                g = float("nan")
                if len(gt):
                    prev = np.flatnonzero(gt <= t)
                    if len(prev):
                        g = float(gv[prev[-1]])
                row = dict(row_base)
                row.update({"subject_id": "", "t": f"{t:.0f}", "rass": v,
                            "goal_rass": ("" if not math.isfinite(g) else f"{g:g}"),
                            "hours_in": f"{(t - t0) / 3600.0:.3f}"})
                for d in cum:
                    row[f"cum_{d}"] = f"{cum[d][j]:.6g}"
                    for h_i, h in enumerate(HALF_LIVES):
                        row[f"k{h:g}_{d}"] = f"{kin[d][j, h_i]:.6g}"
                w.writerow(row)
                n += 1
            if i % 500 == 0:
                print(f"   {i:,}/{len(keep):,} stays, {n:,} rows", flush=True)
    manifest = {"stays_with_drug": len(drug_stays), "distinct_rass_strings": len(seen_vals),
                "unparsed_rass": unparsed, "eligible_stays": len(elig), "sampled_stays": len(keep),
                "seed": a.seed, "rows": n, "half_lives_min": list(HALF_LIVES), "min_rass": MIN_RASS}
    json.dump(manifest, open(a.out + ".manifest.json", "w"), indent=1)
    print(f"\nwrote {n:,} rows -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
