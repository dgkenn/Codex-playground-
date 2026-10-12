"""E92 -- E87 repeated with parsed state labels, matched windows, and gates that actually gate.

REGISTERED AFTER E87 WAS REFUSED AND BECAUSE OF IT. E87's descriptive numbers are in the ledger and are
NOT carried forward as evidence; this file re-derives everything.

=========================================================================================================
WHAT E87 GOT WRONG -- three defects, and two of them were invisible until a fourth gate refused the run
=========================================================================================================
1. **A gate that was written and not wired.** G3 was registered as gating the primary. The code computed
   it, printed FAIL, and evaluated the primary anyway.

2. **ds004541's state assignment was wrong.** Its ids are offsets around loss of consciousness
   (`@start-180`, `@loc-300`, `@loc+30`); the anaesthetised token `loc` matched `@loc-300`, i.e. 300
   seconds BEFORE the event.

3. **ds005620's state assignment was ALSO wrong**, and this was found only while repairing (1) and (2).
   Its ids are BIDS (`task-sed2_acq-rest_run-1`); the awake token `rest` matched `acq-rest` INSIDE a
   sedated recording. E87 reported 164 awake and 38 anaesthetised where the deposit actually holds
   **59 `task-awake`, 92 `task-sed` and 51 `task-sed2`**. So the arm that produced E87's only DELTA-R had
   a contaminated awake set.

Defects 2 and 3 share one cause and it is now `CLAUDE.md` rule 61: a BIDS filename or an offset label is a
STRUCTURED string with fields, and `token in name` reads across the field boundaries. **This file parses
the entity and matches the parsed value.** Nothing in E87's labelling step could fail, which is why an
unrelated gate is the only reason the errors were caught.

=========================================================================================================
G3 IS REPLACED BY TWO GATES, and this is a specification repair, not a threshold move
=========================================================================================================
E87's G3 required `0.696*F + 0.718*P` to reproduce the stored `uce_v1` column to 1e-6 across all shared
rows, and it failed on both deposits. **Diagnosed, the two failures are different things and neither is
the thing the gate claimed to test.**

* On **ds005620** the two tables were on different windows -- 150,000 against 100,000 samples at 5 kHz,
  30 s against 20 s -- because the regional extractor defaulted to 30 s. The comparison was never valid.
  **Repaired at the source**: `ds005620_regional_aperiodic_w20.csv` is re-extracted at 20 s to match
  `ds005620_features.csv`. No gate changes for this; the tables are simply made comparable.
* On **ds004541** the windows already matched and the recomputation is EXACT -- diff 0.000000 -- on
  **123 of 125 rows**. Exactly two rows differ (`sub-04@loc+30` at 0.1230 and `sub-04@loc+180` at 0.1099),
  and on those two the whole-head exponent differs too, at identical channel counts. That is not a formula
  error; it is **two recordings that decoded differently between two independent network fetches**.

So the single gate conflated formula fidelity with fetch reproducibility and answered the wrong question.
It is split:

    G3a  FORMULA IS EXACT.  On every shared row where both passes agree on the whole-head exponent to
         1e-9, `0.696*F + 0.718*P` must reproduce the stored `uce_v1` to **1e-9**. STRICTER than E87's
         1e-6, because on comparable input the arithmetic is deterministic and anything else is a bug.
    G3b  FETCH IS REPRODUCIBLE.  The fraction of shared rows whose whole-head exponent differs between
         passes must be < 5 %, **and every such row is listed by name and EXCLUDED from the analysis.**
         Non-reproducible rows become visible and dropped rather than fatal or silent.

This is the ONE repair rule 58 permits, it is named, and its reason is a diagnosis rather than a wish.

=========================================================================================================
PRIMARY -- unchanged from E87
=========================================================================================================
    P  DELTA-R = r(frontal, posterior | ANAESTHETISED) - r(frontal, posterior | AWAKE), per deposit,
       never pooled, recording-level bootstrap.

    PREDICTED: DELTA-R < 0, the regions decouple under anaesthesia. Against the reading this repository
    currently holds (that the split is decorative), and unchanged from E87 so the prediction cannot be
    said to have followed the data.

VERDICT, wrong direction first (rule 37):
    (a) interval excludes 0 and POSITIVE -> MORE COLLINEAR UNDER ANAESTHESIA.
    (b) interval includes 0              -> NO DECOUPLING; the split is decorative and every description
                                            of UCE must say "whole-head aperiodic exponent".
    (c) interval excludes 0 and NEGATIVE -> DECOUPLES; the second coefficient earns its place.

REPORTED BESIDE IT: r(uce, whole-head) within each state -- the operational question, since if it stays
above 0.95 under anaesthesia the SCORE is the whole-head mean whatever the regions do -- the implied
PC1 variance explained (1+r)/2 beside every correlation, and the frontal-minus-posterior difference.

GATES: G1 >= 5 frontal and >= 5 posterior channels per recording; G2 >= 5 recordings per state per
deposit; G3a and G3b above. **All of them gate, and the code returns before the primary if any fails.**

EXCLUDED: `sub-02` of ds004541 (E87's smoke-test burn) and any row failing G3b, both named in the output.

    python -m bsde.experiments.e92_two_region_information_v2
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.uce_v1 import W_FRONTAL, W_POSTERIOR                    # noqa: E402

OUT = os.path.join(RESULTS, "e92_two_region_information_v2.json")
BURNED = {"ds004541": {"sub-02"}}
MIN_CHANNELS, MIN_PER_STATE = 5, 5
G3A_TOL, G3B_TOL, G3B_MAX_FRAC = 1e-9, 1e-9, 0.05
REPS = 4000
SEED = 20260731

TASK = re.compile(r"task-([A-Za-z0-9]+)")
OFFSET = re.compile(r"@(start|loc)([+-])(\d+)$")


def state_ds005620(rid: str) -> str:
    """Parse the BIDS `task-` entity. `acq-rest` inside `task-sed2` is NOT awake (rule 61)."""
    m = TASK.search(rid)
    if not m:
        return ""
    t = m.group(1).lower()
    if t == "awake":
        return "awake"
    if t.startswith("sed"):
        return "anaesthetised"
    return ""


def state_ds004541(rid: str) -> str:
    """Parse the offset and its SIGN. `@loc-300` is 300 s BEFORE loss of consciousness (rule 61)."""
    if rid.endswith("@baseline"):
        return "awake"
    m = OFFSET.search(rid)
    if not m:
        return ""
    anchor, sign, _ = m.group(1), m.group(2), m.group(3)
    if anchor == "start":
        return "awake"                       # before the infusion started
    return "anaesthetised" if sign == "+" else "awake"


DEPOSITS = {
    "ds004541": {"table": "ds004541_regional_aperiodic.csv", "compare": "ds004541_v2.csv",
                 "state": state_ds004541},
    "ds005620": {"table": "ds005620_regional_aperiodic_w20.csv", "compare": "ds005620_features.csv",
                 "state": state_ds005620},
}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def boot_r(x, y, seed, reps=REPS):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        i = rng.integers(0, x.size, x.size)
        if np.std(x[i]) > 1e-12 and np.std(y[i]) > 1e-12:
            out.append(float(np.corrcoef(x[i], y[i])[0, 1]))
    if len(out) < 50:
        return float("nan"), float("nan")
    out = np.sort(out)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    res = {"deposits": {}}
    any_primary = False
    for dep, spec in DEPOSITS.items():
        path = os.path.join(RESULTS, spec["table"])
        d = {"table": spec["table"]}
        if not os.path.exists(path):
            print(f"\n=== {dep} ===  ABSENT ({spec['table']} not extracted)")
            d["status"] = "ABSENT"
            res["deposits"][dep] = d
            continue
        rows = [r for r in csv.DictReader(open(path, newline="")) if r.get("status") == "ok"]
        burned = BURNED.get(dep, set())
        rows = [r for r in rows if r.get("subject") not in burned]

        cmp_path = os.path.join(RESULTS, spec["compare"])
        stored = {}
        if os.path.exists(cmp_path):
            stored = {r["recording_id"]: r for r in csv.DictReader(open(cmp_path, newline=""))}

        # ---- G3b: which rows are not reproducible between the two independent fetches?
        nonrep, shared = [], 0
        for r in rows:
            s = stored.get(r["recording_id"])
            if not s:
                continue
            shared += 1
            if abs(_f(r["aperiodic_wholehead"]) - _f(s.get("whole_head_exponent", ""))) > G3B_TOL:
                nonrep.append(r["recording_id"])
        frac = (len(nonrep) / shared) if shared else 1.0
        g3b = bool(shared > 0 and frac < G3B_MAX_FRAC)
        rows = [r for r in rows if r["recording_id"] not in set(nonrep)]

        # ---- G3a: on reproducible rows the formula must be EXACT
        g3a_n, g3a_max = 0, 0.0
        for r in rows:
            s = stored.get(r["recording_id"])
            if not s or not np.isfinite(_f(s.get("uce_v1", ""))):
                continue
            g3a_n += 1
            mine = W_FRONTAL * _f(r["aperiodic_frontal"]) + W_POSTERIOR * _f(r["aperiodic_posterior"])
            g3a_max = max(g3a_max, abs(mine - _f(s["uce_v1"])))
        g3a = bool(g3a_n > 0 and g3a_max <= G3A_TOL)

        nf = np.array([_f(r.get("n_frontal", "")) for r in rows])
        npo = np.array([_f(r.get("n_posterior", "")) for r in rows])
        g1 = bool(rows and np.nanmin(nf) >= MIN_CHANNELS and np.nanmin(npo) >= MIN_CHANNELS)

        by = defaultdict(list)
        for r in rows:
            st = spec["state"](r["recording_id"])
            if st:
                by[st].append(r)
        g2 = bool(len(by["awake"]) >= MIN_PER_STATE and len(by["anaesthetised"]) >= MIN_PER_STATE)

        d.update({"n_rows": len(rows), "excluded_subjects": sorted(burned),
                  "G3b_shared": shared, "G3b_nonreproducible": nonrep, "G3b_frac": frac,
                  "G3b_pass": g3b, "G3a_n": g3a_n, "G3a_max": g3a_max, "G3a_pass": g3a,
                  "G1_pass": g1, "G2_pass": g2,
                  "n_awake": len(by["awake"]), "n_anaesthetised": len(by["anaesthetised"]),
                  "unassigned": len(rows) - len(by["awake"]) - len(by["anaesthetised"])})
        print(f"\n=== {dep} ===  {len(rows)} rows after exclusions; "
              f"awake {d['n_awake']}, anaesthetised {d['n_anaesthetised']}, "
              f"unassigned {d['unassigned']}")
        print(f"G3b reproducible  {len(nonrep)}/{shared} rows differ ({100*frac:.2f} %)   "
              f"{'PASS' if g3b else 'FAIL'}" + (f"  excluded: {nonrep}" if nonrep else ""))
        print(f"G3a formula exact {g3a_n} rows, max |diff| {g3a_max:.3g}   {'PASS' if g3a else 'FAIL'}")
        print(f"G1 channels       min F {np.nanmin(nf) if rows else 0:.0f}, "
              f"min P {np.nanmin(npo) if rows else 0:.0f}   {'PASS' if g1 else 'FAIL'}")
        print(f"G2 states         {'PASS' if g2 else 'FAIL'}")

        if not (g1 and g2 and g3a and g3b):
            print("   GATE FAILED -- no primary for this deposit. ABSENT, not a null (rule 31).")
            d["verdict"] = "GATE-FAILED"
            res["deposits"][dep] = d
            continue

        per_state = {}
        arrays = {}
        for st in ("awake", "anaesthetised"):
            rs = by[st]
            fr = np.array([_f(r["aperiodic_frontal"]) for r in rs])
            po = np.array([_f(r["aperiodic_posterior"]) for r in rs])
            wh = np.array([_f(r["aperiodic_wholehead"]) for r in rs])
            ok = np.isfinite(fr) & np.isfinite(po) & np.isfinite(wh)
            fr, po, wh = fr[ok], po[ok], wh[ok]
            arrays[st] = (fr, po)
            uce = W_FRONTAL * fr + W_POSTERIOR * po
            r_fp = float(np.corrcoef(fr, po)[0, 1])
            lo, hi = boot_r(fr, po, SEED)
            per_state[st] = {"n": int(fr.size), "r_frontal_posterior": r_fp, "lo": lo, "hi": hi,
                             "implied_pc1_ve": (1.0 + r_fp) / 2.0,
                             "r_uce_wholehead": float(np.corrcoef(uce, wh)[0, 1]),
                             "mean_frontal_minus_posterior": float(np.mean(fr - po))}
            print(f"   {st:15s} n={fr.size:3d}  r(F,P) {r_fp:+.4f} [{lo:+.4f}, {hi:+.4f}]  "
                  f"implied PC1 VE {100*(1+r_fp)/2:.1f}%  r(uce, wholehead) "
                  f"{per_state[st]['r_uce_wholehead']:+.4f}  F-P {np.mean(fr - po):+.4f}")
        d["per_state"] = per_state

        rng = np.random.default_rng(SEED + 1)
        fa, pa = arrays["awake"]
        fb, pb = arrays["anaesthetised"]
        ds = []
        for _ in range(REPS):
            ia = rng.integers(0, fa.size, fa.size)
            ib = rng.integers(0, fb.size, fb.size)
            if min(np.std(fa[ia]), np.std(pa[ia]), np.std(fb[ib]), np.std(pb[ib])) < 1e-12:
                continue
            ds.append(np.corrcoef(fb[ib], pb[ib])[0, 1] - np.corrcoef(fa[ia], pa[ia])[0, 1])
        ds = np.sort(ds)
        delta = per_state["anaesthetised"]["r_frontal_posterior"] - per_state["awake"]["r_frontal_posterior"]
        dlo, dhi = float(np.quantile(ds, .025)), float(np.quantile(ds, .975))
        v = ("MORE COLLINEAR UNDER ANAESTHESIA" if dlo > 0 else
             "DECOUPLES" if dhi < 0 else "NO DECOUPLING")
        d.update({"DELTA_R": delta, "DELTA_R_lo": dlo, "DELTA_R_hi": dhi, "verdict": v})
        print(f"   PRIMARY DELTA-R = {delta:+.4f} [{dlo:+.4f}, {dhi:+.4f}]   {v}")
        any_primary = True
        res["deposits"][dep] = d

    vs = {k: v.get("verdict") for k, v in res["deposits"].items() if v.get("verdict")}
    res["verdict"] = ("; ".join(f"{k}: {v}" for k, v in vs.items()) if any_primary
                      else "ABSENT -- no deposit produced a primary")
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
