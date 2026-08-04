#!/usr/bin/env python3
"""ACUTE KIDNEY INJURY, recomputed on the corrected pipeline — and reframed around dwell time.

WHY THIS SUPERSEDES `vitaldb_bs_aki_mediation.py`. That analysis was run before two errors were found:
  * arterial pressure was never range-filtered (4.27 % of MAP values <= 0, minimum -78 mmHg), so every
    hypotension-derived quantity in it was contaminated;
  * the mediator was defined from case-AVERAGED or coupled-window hypotension, and its reported proportion
    mediated (58.5 % [29 %, 184 %]) had an out-of-range upper bound, which is a sign the ratio estimator was
    unstable at that event count rather than a result to quote.

WHAT CHANGED IN THE EXPOSURE, and why. The bin-level work established that the haemodynamic consequence is graded
by CUMULATIVE DWELL TIME in the suppressed state, not by whether suppression ever occurred: forward dMAP runs
-0.14 -> -0.85 mmHg across occupancy bands, monotonically. A case-level analysis should use the matching exposure.
So the primary exposure here is the TOTAL MINUTES SUPPRESSED during maintenance, not the mean suppressed fraction,
with the fraction retained as a secondary for comparability with the earlier work.

    outcome    KDIGO AKI: peak post-operative creatinine within 7 days >= 1.5x the pre-operative baseline,
               OR an absolute rise >= 0.3 mg/dL.
    exposure   minutes suppressed during maintenance (primary); mean suppressed fraction (secondary)
    mediator   MINUTES SPENT HYPOTENSIVE (MAP < 65) during maintenance, computed on FILTERED pressure
    adjust     age, ASA, baseline creatinine, maintenance duration, mean anaesthetic concentration
    inference  case-level nonparametric bootstrap; the mediation is reported on the RISK-DIFFERENCE scale via a
               linear probability model, because odds ratios are non-collapsible and a change in an OR on
               adding a mediator confounds mediation with non-collapsibility.

HONEST FRAMING, unchanged from before and still binding. Burst suppression, hypotension and anaesthetic depth
share common causes. This estimates ATTENUATION CONSISTENT WITH MEDIATION, not a randomised causal effect. Duration
of surgery is both a confounder and a collider-ish quantity here (longer cases accumulate more of everything), so
it is adjusted but the adjustment is not innocent.

WHAT WOULD FALSIFY THE CLINICAL LIMB: if suppression minutes carry no association with AKI once duration and
baseline creatinine are adjusted, then the bin-level haemodynamic finding -- however clean -- has no demonstrated
downstream consequence in these data, and the paper should say so rather than implying one.
"""
import csv, math, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
SP = os.environ.get("VITAL_SCRATCH",
                    "/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad/vitaldb")
NBOOT = int(os.environ.get("NBOOT", "2000"))
rng = np.random.default_rng(20260725)
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


def build():
    per = defaultdict(lambda: dict(bs=[], mbp=[], ce=[], age=np.nan))
    seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                ce = float(d["ce"]) if d["ce"] else np.nan
                if not (ce == ce and ce >= 1.0):
                    continue
                bs = float(d["bs"])
                if bs != bs:
                    continue
                p = per[cid]
                p["bs"].append(bs); p["mbp"].append(_map_ok(d["mbp"])); p["ce"].append(ce)
                if d.get("age"):
                    p["age"] = float(d["age"])
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
            cid = r.get("caseid") or r.get("﻿caseid")
            meta[cid] = r
    rows = []
    for cid, p in per.items():
        if len(p["bs"]) < 20:
            continue
        s = cr.get(cid); m = meta.get(cid)
        if not s or not m:
            continue
        pre = [v for t, v in s if t <= 0]
        post = [v for t, v in s if 0 < t <= 7 * 24 * 3600]
        if not pre or not post:
            continue
        try:
            asa = float((m.get("asa") or "").strip()[0]); age = float(m.get("age"))
        except Exception:
            continue
        mbp = np.asarray(p["mbp"], float)
        nvalid = int(np.isfinite(mbp).sum())
        if nvalid < 20:
            continue
        bs = np.asarray(p["bs"], float)
        nbin = len(bs)
        b0 = min(pre); pk = max(post)
        rows.append(dict(
            cid=cid,
            supp_min=float(np.sum(bs > 0)) * 0.5,                 # minutes with any suppression
            supp_frac=float(np.mean(bs > 0)),
            hypo_min=float(np.nansum(mbp < 65)) * 0.5,            # minutes hypotensive, FILTERED pressure
            ce=float(np.mean(p["ce"])), age=age, asa=asa,
            dur=nbin * 0.5, base_cr=b0,
            aki=1.0 if (pk >= 1.5 * b0 or (pk - b0) >= 0.3) else 0.0))
    return rows


def zs(v):
    v = np.asarray(v, float); s = v.std()
    return (v - v.mean()) / (s if s > 1e-9 else 1.0)


def lpm(X, y):
    """Linear probability model: risk-difference scale, collapsible, so mediation is interpretable."""
    try:
        return np.linalg.lstsq(X, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None


def design(R, expo, med=None):
    n = len(R)
    cols = [np.ones(n), zs([r[expo] for r in R]), zs([r["age"] for r in R]), zs([r["asa"] for r in R]),
            zs([r["ce"] for r in R]), zs([r["dur"] for r in R]), zs([r["base_cr"] for r in R])]
    if med:
        cols.append(zs([r[med] for r in R]))
    return np.column_stack(cols), np.asarray([r["aki"] for r in R], float)


def main():
    R = build()
    n = len(R)
    if n < 300:
        print(f"insufficient cases ({n})"); return
    ev = int(sum(r["aki"] for r in R))
    print(f"cases with EEG + filtered arterial pressure + pre/post creatinine: {n}")
    print(f"AKI: {ev} events ({100*ev/n:.1f} %)")
    print(f"  median suppressed minutes {np.median([r['supp_min'] for r in R]):.1f}, "
          f"hypotensive minutes {np.median([r['hypo_min'] for r in R]):.1f}, "
          f"maintenance {np.median([r['dur'] for r in R]):.0f} min")
    print(f"  MAP filtered to [{MAP_LO},{MAP_HI}]; {NBOOT} case-level bootstrap replicates")
    print("  risk-difference scale (linear probability model): coefficients are absolute AKI risk per SD\n")

    for expo, lab in (("supp_min", "suppressed MINUTES (primary)"), ("supp_frac", "suppressed FRACTION (secondary)")):
        Xt, y = design(R, expo)
        bt = lpm(Xt, y)
        Xm, _ = design(R, expo, "hypo_min")
        bm = lpm(Xm, y)
        if bt is None or bm is None:
            print(f"{lab}: fit failed"); continue
        tot_b, dir_b, props = [], [], []
        for _ in range(NBOOT):
            idx = rng.integers(0, n, n)
            Rs = [R[i] for i in idx]
            X1, y1 = design(Rs, expo); X2, _ = design(Rs, expo, "hypo_min")
            b1 = lpm(X1, y1); b2 = lpm(X2, y1)
            if b1 is None or b2 is None:
                continue
            tot_b.append(b1[1]); dir_b.append(b2[1])
            if abs(b1[1]) > 1e-6:
                props.append(100 * (1 - b2[1] / b1[1]))
        if len(tot_b) < 100:
            print(f"{lab}: bootstrap failed"); continue
        lo, hi = np.percentile(tot_b, [2.5, 97.5])
        print(f"{lab}")
        print(f"   TOTAL  effect on AKI risk  {100*bt[1]:+6.2f} pp/SD [{100*lo:+6.2f},{100*hi:+6.2f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
        lo2, hi2 = np.percentile(dir_b, [2.5, 97.5])
        print(f"   DIRECT (adj hypotensive minutes) {100*bm[1]:+6.2f} pp/SD [{100*lo2:+6.2f},{100*hi2:+6.2f}] "
              f"{'*' if (lo2>0 or hi2<0) else 'ns'}")
        if (lo > 0 or hi < 0) and len(props) > 200:
            p = np.array([x for x in props if np.isfinite(x)])
            pl, ph = np.percentile(p, [2.5, 97.5])
            print(f"   proportion mediated by hypotensive minutes: {np.median(p):.0f} % [{pl:.0f} %,{ph:.0f} %]")
        else:
            print("   proportion mediated NOT reported: it is a ratio and is only interpretable when the")
            print("   total effect is clearly non-null. Reporting it otherwise produces the out-of-range")
            print("   intervals seen in the earlier version of this analysis.")
        print()
    print("Falsification note: if suppressed minutes carry no association with AKI after adjustment, the")
    print("bin-level haemodynamic finding has no demonstrated downstream consequence in these data, and the")
    print("paper must say so rather than implying one.")


if __name__ == "__main__":
    sys.exit(main())
