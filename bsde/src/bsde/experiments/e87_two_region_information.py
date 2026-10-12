"""E87 -- Does UCE v1's frontal/posterior split carry information, and does it decouple UNDER ANAESTHESIA?

REGISTERED BEFORE `ds004541_regional_aperiodic.csv` AND `ds005620_regional_aperiodic.csv` EXIST beyond a
three-row smoke test on `sub-02` of ds004541, whose values are disclosed at the end of this docstring.

=========================================================================================================
THE QUESTION, AND WHY IT IS THE ONE THAT DECIDES WHAT UCE IS
=========================================================================================================
`uce_v1.py` already establishes, by algebra before any data: for two STANDARDISED variables the correlation
matrix [[1,r],[r,1]] has eigenvectors (1/sqrt2)(1,1) and (1/sqrt2)(1,-1) **for all r**. Equal PC1 loadings
are a mathematical necessity, not an empirical finding; the frozen weights 0.696 and 0.718 have mean 0.7070
against 1/sqrt2 = 0.7071; and "96.8 % of variance explained" is exactly `r(frontal, posterior) = 0.936`
restated, since VE = (1+r)/2.

It also records the consequence measured in three cohorts, with no outcome label consulted:
r(uce_v1, whole_head_exponent) = +0.980 (eegmmidb, n=210), +0.882 (ds004541, n=124), +0.962 (chennu, n=80).

**But all three of those are dominated by AWAKE or lightly-altered recordings.** The claim UCE exists to
make is about ANAESTHESIA, and there is a real physiological reason the two regions might separate there
that does not apply awake: propofol produces frontal alpha and anteriorisation, so frontal and posterior
spectra are documented to behave differently under GABAergic anaesthesia in a way they do not at rest.

**If r(frontal, posterior) collapses under anaesthesia, the second coefficient earns its place and UCE is a
two-region measure after all. If it does not, UCE is a whole-head aperiodic exponent wearing two
coefficients, and the frontal/posterior framing has to be dropped from every description of it.** No
existing table in this repository can answer that, because none carries the regional exponents separately.

=========================================================================================================
PRIMARY
=========================================================================================================
Two deposits with a within-subject state contrast and enough channels for both regions:

    ds004541   62 channels, baseline -> post-LOC (general anaesthesia)
    ds005620   65 channels, awake -> sedated (propofol)

    P  DELTA-R = r(frontal, posterior | ANAESTHETISED) - r(frontal, posterior | AWAKE), computed across
       recordings within each deposit, with a recording-level bootstrap, reported per deposit and never
       pooled (rule 54: the deposits differ in agent, depth and montage).

    PREDICTED: **DELTA-R < 0** -- the regions decouple under anaesthesia. This prediction is AGAINST the
    reading this repository currently holds (that the split is decorative), which is the reason to write
    it down.

VERDICT, wrong direction first (rule 37):

    (a) DELTA-R interval excludes 0 and is POSITIVE -> MORE COLLINEAR UNDER ANAESTHESIA. The regions become
        MORE redundant exactly where the measure is meant to work. Not a null: it would mean the
        two-region framing is at its weakest in its own target condition.
    (b) interval includes 0 -> NO DECOUPLING. The split is decorative under anaesthesia too, and every
        description of UCE must say "whole-head aperiodic exponent".
    (c) interval excludes 0 and NEGATIVE -> DECOUPLES. The second coefficient earns its place; report how
        much r falls and what PC1 variance-explained that implies, because (1+r)/2 is the honest way to
        state it.

REPORTED BESIDE THE PRIMARY, and each is a number the current framing depends on:

    * r(frontal, posterior) within each state, per deposit, with the implied PC1 VE = (1+r)/2.
    * r(uce_v1_recomputed, aperiodic_wholehead) within each state. **This is the operational question**: if
      it stays above 0.95 under anaesthesia, then whatever the regions do, the SCORE is the whole-head
      mean and nothing downstream can distinguish them.
    * the frontal-minus-posterior difference as a state contrast in its own right -- the one quantity a
      two-region measure could carry that a whole-head mean cannot. If anteriorisation is real here, that
      difference should move with state even if the correlation does not fall.

GATES (rule 40):

    G1  CHANNELS   >= 5 frontal and >= 5 posterior channels in every included recording, and the counts
                   reported. A "posterior exponent" over one electrode is not the same measurement.
    G2  STATES     >= 5 recordings in each state per deposit.
    G3  RECOMPUTE MATCHES. `0.696*frontal + 0.718*posterior` recomputed here must reproduce the `uce_v1`
                   column of the existing table for the same recordings to within 1e-6. If it does not,
                   the stored column is not what its name says and nothing downstream is interpretable.

SCOPE. This is a question about the STRUCTURE of a score, not about consciousness, and it consults no
outcome label anywhere. Two deposits, both GABAergic; a null here does not establish that the regions never
decouple under any agent.

DISCLOSED (rule 26 -- the smoke test was on real labels again, and this time only three rows of one
subject, all from ds004541 `sub-02`): baseline frontal 2.2746 / posterior 1.9152 / whole-head 2.3106;
start-180 2.4780 / 1.9776 / 2.4018; start-120 2.7394 / 2.4112 / 2.7138; 14 frontal and 17 posterior
channels. **`sub-02` is excluded from ds004541's arm below**, named in the code, for the same reason
`sub-001` was excluded from E83.

    python -m bsde.experiments.e87_two_region_information
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

OUT = os.path.join(RESULTS, "e87_two_region_information.json")
BURNED = {"ds004541": {"sub-02"}}
MIN_CHANNELS = 5
MIN_PER_STATE = 5
REPS = 4000
SEED = 20260731

# state assignment is by the deposit's own recording_id, declared here rather than inferred at run time
DEPOSITS = {
    "ds004541": {"table": "ds004541_regional_aperiodic.csv",
                 "compare": "ds004541_v2.csv",
                 "awake": ("baseline",), "anaesthetised": ("post-loc", "postloc", "loc")},
    "ds005620": {"table": "ds005620_regional_aperiodic.csv",
                 "compare": "ds005620_features.csv",
                 "awake": ("awake", "eyesclosed", "rest"), "anaesthetised": ("sed", "propofol", "anes")},
}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def state_of(rid: str, spec) -> str:
    low = rid.lower()
    for s in ("awake", "anaesthetised"):
        if any(tok in low for tok in spec[s]):
            return s
    return ""


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
    res = {"deposits": {}, "gates": {}}
    any_ok = False
    for dep, spec in DEPOSITS.items():
        path = os.path.join(RESULTS, spec["table"])
        if not os.path.exists(path):
            print(f"{dep}: ABSENT ({spec['table']} not extracted yet)")
            res["deposits"][dep] = {"status": "ABSENT"}
            continue
        rows = [r for r in csv.DictReader(open(path, newline="")) if r.get("status") == "ok"]
        burned = BURNED.get(dep, set())
        rows = [r for r in rows if r.get("subject") not in burned]
        by = defaultdict(list)
        for r in rows:
            s = state_of(r["recording_id"], spec)
            if s:
                by[s].append(r)
        d = {"n_rows": len(rows), "excluded_subjects": sorted(burned),
             "n_awake": len(by["awake"]), "n_anaesthetised": len(by["anaesthetised"]),
             "states_seen": sorted({state_of(r["recording_id"], spec) or "(unassigned)" for r in rows})}
        print(f"\n=== {dep} ===  {len(rows)} usable rows; "
              f"awake {d['n_awake']}, anaesthetised {d['n_anaesthetised']}")

        # G1 channels
        nf = np.array([_f(r.get("n_frontal", "")) for r in rows])
        npo = np.array([_f(r.get("n_posterior", "")) for r in rows])
        g1 = bool(np.nanmin(nf) >= MIN_CHANNELS and np.nanmin(npo) >= MIN_CHANNELS) if rows else False
        d.update({"min_n_frontal": float(np.nanmin(nf)) if rows else None,
                  "min_n_posterior": float(np.nanmin(npo)) if rows else None, "G1_pass": g1})
        print(f"G1 channels   min frontal {d['min_n_frontal']}, min posterior {d['min_n_posterior']}   "
              f"{'PASS' if g1 else 'FAIL'}")

        # G3 the recomputation must reproduce the stored uce_v1 column
        cmp_path = os.path.join(RESULTS, spec["compare"])
        g3n, g3max = 0, 0.0
        if os.path.exists(cmp_path):
            stored = {r["recording_id"]: _f(r.get("uce_v1", "")) for r in csv.DictReader(open(cmp_path, newline=""))}
            for r in rows:
                v = stored.get(r["recording_id"])
                if v is None or not np.isfinite(v):
                    continue
                mine = W_FRONTAL * _f(r["aperiodic_frontal"]) + W_POSTERIOR * _f(r["aperiodic_posterior"])
                if np.isfinite(mine):
                    g3n += 1
                    g3max = max(g3max, abs(mine - v))
        d.update({"G3_shared": g3n, "G3_max_abs_diff": g3max, "G3_pass": bool(g3n > 0 and g3max < 1e-6)})
        print(f"G3 recompute  {g3n} shared rows, max |diff| {g3max:.3g}   "
              f"{'PASS' if d['G3_pass'] else ('FAIL' if g3n else 'no overlap to check')}")

        per_state = {}
        for st in ("awake", "anaesthetised"):
            rs = by[st]
            if len(rs) < MIN_PER_STATE:
                per_state[st] = {"n": len(rs), "status": "TOO FEW"}
                continue
            fr = np.array([_f(r["aperiodic_frontal"]) for r in rs])
            po = np.array([_f(r["aperiodic_posterior"]) for r in rs])
            wh = np.array([_f(r["aperiodic_wholehead"]) for r in rs])
            ok = np.isfinite(fr) & np.isfinite(po) & np.isfinite(wh)
            fr, po, wh = fr[ok], po[ok], wh[ok]
            uce = W_FRONTAL * fr + W_POSTERIOR * po
            r_fp = float(np.corrcoef(fr, po)[0, 1])
            lo, hi = boot_r(fr, po, SEED)
            r_uw = float(np.corrcoef(uce, wh)[0, 1])
            diff = fr - po
            per_state[st] = {"n": int(ok.sum()), "r_frontal_posterior": r_fp, "lo": lo, "hi": hi,
                             "implied_pc1_ve": (1.0 + r_fp) / 2.0,
                             "r_uce_wholehead": r_uw,
                             "mean_frontal_minus_posterior": float(np.mean(diff)),
                             "sd_frontal_minus_posterior": float(np.std(diff))}
            print(f"   {st:15s} n={ok.sum():3d}  r(F,P) {r_fp:+.4f} [{lo:+.4f}, {hi:+.4f}]  "
                  f"implied PC1 VE {100*(1+r_fp)/2:.1f}%  r(uce, wholehead) {r_uw:+.4f}  "
                  f"F-P {np.mean(diff):+.4f}")
        d["per_state"] = per_state

        a, b = per_state.get("awake", {}), per_state.get("anaesthetised", {})
        if "r_frontal_posterior" in a and "r_frontal_posterior" in b:
            delta = b["r_frontal_posterior"] - a["r_frontal_posterior"]
            # bootstrap the difference by resampling within each state independently
            rng = np.random.default_rng(SEED + 1)
            fr_a = np.array([_f(r["aperiodic_frontal"]) for r in by["awake"]])
            po_a = np.array([_f(r["aperiodic_posterior"]) for r in by["awake"]])
            fr_b = np.array([_f(r["aperiodic_frontal"]) for r in by["anaesthetised"]])
            po_b = np.array([_f(r["aperiodic_posterior"]) for r in by["anaesthetised"]])
            ds = []
            for _ in range(REPS):
                ia = rng.integers(0, fr_a.size, fr_a.size)
                ib = rng.integers(0, fr_b.size, fr_b.size)
                if min(np.std(fr_a[ia]), np.std(po_a[ia]), np.std(fr_b[ib]), np.std(po_b[ib])) < 1e-12:
                    continue
                ds.append(np.corrcoef(fr_b[ib], po_b[ib])[0, 1] - np.corrcoef(fr_a[ia], po_a[ia])[0, 1])
            ds = np.sort(ds)
            dlo, dhi = float(np.quantile(ds, .025)), float(np.quantile(ds, .975))
            v = ("MORE COLLINEAR UNDER ANAESTHESIA" if dlo > 0 else
                 "DECOUPLES" if dhi < 0 else "NO DECOUPLING")
            d.update({"DELTA_R": delta, "DELTA_R_lo": dlo, "DELTA_R_hi": dhi, "verdict": v})
            print(f"   PRIMARY DELTA-R = {delta:+.4f} [{dlo:+.4f}, {dhi:+.4f}]   {v}")
            any_ok = True
        res["deposits"][dep] = d

    if not any_ok:
        res["verdict"] = "ABSENT -- no deposit had both states extracted with enough recordings"
    else:
        vs = {k: v.get("verdict") for k, v in res["deposits"].items() if v.get("verdict")}
        res["verdict"] = "; ".join(f"{k}: {v}" for k, v in vs.items())
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
