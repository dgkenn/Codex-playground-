#!/usr/bin/env python3
"""AKI: outcome-definition sensitivity and a NEGATIVE-CONTROL OUTCOME.

Written to a file because these results were originally produced by an inline script whose output was never
persisted. An external fact-check correctly flagged them as unsourced -- a number that cannot be regenerated from
a committed script has no business in a document shown to anyone.

TWO QUESTIONS.
  1. Does the suppression-AKI association depend on KDIGO's baseline-relative definition? Suppression is
     associated with LOWER pre-operative creatinine, and KDIGO triggers on peak >= 1.5x baseline OR a >= 0.3 mg/dL
     rise, so a lower baseline makes both criteria easier to meet. If the association survives an absolute-rise
     definition that never divides by baseline, that artefact is excluded.
  2. NEGATIVE-CONTROL OUTCOME: does suppression 'predict' PRE-OPERATIVE creatinine? Intraoperative suppression
     cannot cause a value measured before the operation. Any association is residual patient-level confounding,
     and its size bounds how much of the AKI association can be trusted.

Also reports the case-level a-path (suppression -> hypotensive minutes), because it runs OPPOSITE in sign to the
within-case estimate and that contrast is itself the finding: between patients, more suppression goes with more
hypotension; within a patient, it does not.

Risk-difference scale throughout (linear probability model), case-level bootstrap.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
SP = os.environ.get("VITAL_SCRATCH",
                    "/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad/vitaldb")
NBOOT = int(os.environ.get("NBOOT", "1500"))
rng = np.random.default_rng(20260725)
MAP_LO, MAP_HI = 30.0, 150.0


def _map_ok(r):
    try:
        v = float(r) if r not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


def build():
    per = defaultdict(lambda: dict(bs=[], mbp=[], ce=[])); seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                c = d["caseid"]; t = float(d["bin_t"])
                if (c, t) in seen:
                    continue
                seen.add((c, t))
                ce = float(d["ce"]) if d["ce"] else np.nan
                if not (ce == ce and ce >= 1.0):
                    continue
                bs = float(d["bs"])
                if bs != bs:
                    continue
                p = per[c]; p["bs"].append(bs); p["mbp"].append(_map_ok(d["mbp"])); p["ce"].append(ce)
            except Exception:
                pass
    cr = defaultdict(list)
    with open(f"{SP}/labs.csv") as fh:
        for r in csv.DictReader(fh):
            if r["name"] != "cr":
                continue
            try:
                cr[r["caseid"]].append((float(r["dt"]), float(r["result"])))
            except Exception:
                pass
    meta = {}
    with open(f"{SP}/cases.csv") as fh:
        for r in csv.DictReader(fh):
            meta[r.get("caseid") or r.get("﻿caseid")] = r
    R = []
    for cid, p in per.items():
        if len(p["bs"]) < 40:
            continue
        s = cr.get(cid); m = meta.get(cid)
        if not s or not m:
            continue
        pre = [v for t, v in s if t <= 0]; post = [v for t, v in s if 0 < t <= 7 * 24 * 3600]
        if not pre or not post:
            continue
        try:
            age = float(m.get("age")); asa = float((m.get("asa") or "").strip()[0])
        except Exception:
            continue
        mbp = np.asarray(p["mbp"], float)
        if np.isfinite(mbp).sum() < 40:
            continue
        bs = np.asarray(p["bs"], float); b0 = min(pre); pk = max(post)
        R.append(dict(supp=float(np.sum(bs > 0)) * 0.5, hypo=float(np.nansum(mbp < 65)) * 0.5,
                      ce=float(np.mean(p["ce"])), age=age, asa=asa, dur=len(bs) * 0.5,
                      base_cr=b0, delta=pk - b0,
                      aki_kdigo=1.0 if (pk >= 1.5 * b0 or (pk - b0) >= 0.3) else 0.0,
                      aki_ratio=1.0 if pk >= 1.5 * b0 else 0.0,
                      aki_abs=1.0 if (pk - b0) >= 0.3 else 0.0))
    return R


def zs(v):
    v = np.asarray(v, float); s = v.std()
    return (v - v.mean()) / (s if s > 1e-9 else 1.0)


def fit(Rs, out, terms):
    X = np.column_stack([np.ones(len(Rs))] + [zs([r[t] for r in Rs]) for t in terms])
    return np.linalg.lstsq(X, np.asarray([r[out] for r in Rs], float), rcond=None)[0]


def main():
    R = build(); n = len(R)
    print(f"cases={n}  AKI(KDIGO)={int(sum(r['aki_kdigo'] for r in R))}  "
          f"AKI(ratio)={int(sum(r['aki_ratio'] for r in R))}  AKI(abs)={int(sum(r['aki_abs'] for r in R))}")
    print(f"MAP filtered to [{MAP_LO},{MAP_HI}]; {NBOOT} case-level bootstrap replicates\n")
    T = ["supp", "age", "asa", "dur", "ce", "base_cr"]

    def boot(out, terms):
        p = fit(R, out, terms)[1]; bs = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            try:
                bs.append(fit([R[j] for j in i], out, terms)[1])
            except Exception:
                pass
        lo, hi = np.percentile(bs, [2.5, 97.5]); return p, lo, hi

    print("=== 1. does the AKI signal depend on dividing by baseline? ===")
    for out, lab in (("aki_kdigo", "KDIGO (ratio OR absolute)"),
                     ("aki_ratio", "ratio criterion only (>=1.5x)"),
                     ("aki_abs", "absolute only (>=0.3 mg/dL, no baseline division)")):
        p, lo, hi = boot(out, T)
        print(f"   {lab:52s} {100*p:+6.2f} pp/SD [{100*lo:+6.2f},{100*hi:+6.2f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
    p, lo, hi = boot("delta", T)
    print(f"   {'creatinine RISE (continuous mg/dL)':52s} {p:+6.4f} [{lo:+6.4f},{hi:+6.4f}] "
          f"{'*' if (lo>0 or hi<0) else 'ns'}")

    print("\n=== 2. NEGATIVE CONTROL: suppression -> PRE-OPERATIVE creatinine ===")
    print("    intraoperative suppression cannot cause a pre-operative value; any association is confounding")
    p, lo, hi = boot("base_cr", ["supp", "age", "asa", "dur", "ce"])
    flag = "*  <-- CONFOUNDED" if (lo > 0 or hi < 0) else "ns  <-- clean"
    print(f"   {'suppression -> BASELINE creatinine':52s} {p:+.4f} mg/dL per SD [{lo:+.4f},{hi:+.4f}] {flag}")

    print("\n=== 3. the case-level a-path, which runs OPPOSITE to the within-case estimate ===")
    p, lo, hi = boot("hypo", ["supp", "age", "asa", "dur", "ce"])
    print(f"   {'suppression -> hypotensive MINUTES (between patients)':52s} {p:+.3f} min/SD "
          f"[{lo:+.3f},{hi:+.3f}] {'*' if (lo>0 or hi<0) else 'ns'}")
    print("   Within patient the same exposure predicts FEWER hypotensive minutes (-0.98 [-1.96,-0.08],")
    print("   analysis/vitaldb_attributable_burden.py). Same data, opposite signs: the case-level 'mediation'")
    print("   was measuring between-patient severity confounding, not a pathway.")


if __name__ == "__main__":
    sys.exit(main())
