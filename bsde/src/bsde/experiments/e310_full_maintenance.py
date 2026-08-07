#!/usr/bin/env python3
"""E310 -- re-estimate the two n-limited analyses on the COMPLETE maintenance cohort.

**THIS IS A PRECISION UPGRADE, NOT A NEW TEST, AND THE DISTINCTION IS THE POINT.**

E296 (depth-quintile trend) and E281 (leakage after matching arms on BIS) are the two analyses that
arbitrate "is the maintenance effect depth or drug", and both were computed on a 750-case balanced
subsample -- 146 cases per quintile, 158-179 matched pairs. The full eligible set is 2,353 cases. This
file re-runs **those exact procedures, unchanged**, on all of them.

WHAT IS AND IS NOT LEGITIMATE HERE. Rule 46 permits raising a replicate count after seeing a boundary
result, because it changes no threshold, cohort definition or estimand. Extending a cohort to every
eligible case is the same move: the eligibility rule was fixed when the first plan was built (recovery
landmark usable, control centre 2,400 s earlier, >= 900 s clear of both landmarks, inside the anaesthetic
with margin), and the extension simply stops subsampling it. **No threshold, statistic, family
assignment or verdict rule is altered.** I have seen the 750-case results, so nothing here is blind, and
these numbers are reported as *more precise estimates of the same quantities* -- never as independent
confirmation, which they are not.

WHAT CHANGES, arithmetically and predictably:
  * arms go from 250/250/250 to roughly 1,182 sevo / 358 des / 823 ppf;
  * the sevo-vs-ppf leakage floor falls from ~0.051 to ~0.026, des-limited pairs improve much less;
  * quintiles hold ~470 cases instead of 146, and BIS matching yields far more pairs.
**Desflurane remains the limiting arm** and no amount of extraction fixes that -- it is the smallest
single-agent group in the deposit.

A1 -- DEPTH-QUINTILE TREND, method identical to E296. Spearman of leakage against within-cohort BIS
     quintile, per candidate, median across the top six, against a within-arm BIS permutation null.
A2 -- BIS-MATCHED LEAKAGE, method identical to E281. Joint 10-90th trim then 1:1 nearest-neighbour
     matching on control-window BIS with a 3-unit caliper; report retention against the unmatched value.
A3 -- HEADLINE LEAKAGE, method identical to E260/E270, for the record at full n.

REPORTING RULE, fixed before the run: if a full-cohort estimate differs materially from its subsample
estimate, **both are reported and the subsample one is not deleted**. A precision upgrade that quietly
replaces an inconvenient number is indistinguishable from a goalpost move.

    python -m bsde.experiments.e310_full_maintenance
"""
from __future__ import annotations

import argparse, csv, glob, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
TOP = ["whole_head_exponent", "multiscale_entropy_slope", "critical_slowing_ar1",
       "exponent_low", "emg_beta_gamma_fraction", "alpha_peak_hz"]


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def midranks(vals):
    o = sorted(range(len(vals)), key=lambda i: vals[i]); r = [0.0] * len(vals); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and vals[o[j + 1]] == vals[o[i]]:
            j += 1
        av = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[o[k]] = av
        i = j + 1
    return r


def auc(p, n):
    p = [x for x in p if math.isfinite(x)]; n = [x for x in n if math.isfinite(x)]
    if not p or not n:
        return float("nan")
    r = midranks(p + n)
    return (sum(r[:len(p)]) - len(p) * (len(p) + 1) / 2.0) / (len(p) * len(n))


def lk(a_, b_, minn=8):
    a_ = [x for x in a_ if math.isfinite(x)]; b_ = [x for x in b_ if math.isfinite(x)]
    if len(a_) < minn or len(b_) < minn:
        return float("nan")
    return abs(auc(a_, b_) - 0.5)


def null95(n1, n2):
    return 1.959964 * math.sqrt((n1 + n2 + 1) / (12.0 * n1 * n2))


def pear(x, y):
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 3:
        return float("nan")
    n = len(q); mx = sum(t[0] for t in q) / n; my = sum(t[1] for t in q) / n
    sxy = sum((t[0] - mx) * (t[1] - my) for t in q)
    sxx = sum((t[0] - mx) ** 2 for t in q); syy = sum((t[1] - my) ** 2 for t in q)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def spear(x, y):
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 3:
        return float("nan")
    return pear(midranks([t[0] for t in q]), midranks([t[1] for t in q]))


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def pct(v, q):
    v = sorted(x for x in v if math.isfinite(x))
    return v[min(len(v) - 1, int(q * len(v)))] if v else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=310)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e310_full_maintenance.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    lm = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_vent_landmarks.s?.csv"))):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r
    rows, cols = [], None
    for pat in ("vitaldb_ctrlwin.s?.csv", "vitaldb_ctrlwin2.s?.csv"):
        for p in sorted(glob.glob(os.path.join(RESULTS, pat))):
            rd = csv.DictReader(open(p))
            if cols is None:
                cols = [c for c in (rd.fieldnames or [])
                        if not c.startswith("meta_") and c not in SKIP]
            for r in rd:
                if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                    rows.append(r)
    by = {}
    for r in rows:
        by.setdefault(r["meta_caseid"], []).append(r)
    by = {k: v for k, v in by.items() if len(v) >= 15}
    fin = {c: sum(1 for r in rows if math.isfinite(f(r.get(c)))) for c in cols}
    cols = [c for c in cols if fin[c] >= 0.20 * len(rows)]
    arm = {k: lm[k]["arm"] for k in by}
    if a.smoke:
        ks = sorted(arm); vs = [arm[k] for k in ks]; rng.shuffle(vs); arm = dict(zip(ks, vs))
        print("[SMOKE] arm labels permuted")
    cmed, cbis = {}, {}
    for cid, rs in by.items():
        for c in cols + ["meta_bis"]:
            cmed.setdefault(c, {})[cid] = med([f(r.get(c)) for r in rs])
        cbis[cid] = cmed["meta_bis"][cid]
    cbis = {k: v for k, v in cbis.items() if math.isfinite(v)}
    counts = {x: sum(1 for k in by if arm[k] == x) for x in ARMS}
    print(f"[cohort] FULL maintenance: {len(by)} cases {counts}  "
          f"(subsample was 740, 250/arm)")
    print("  analytic leakage floors: " + ", ".join(
        f"{x}/{y} {null95(counts[x], counts[y]):.4f}" for x, y in PAIRS))
    top = [c for c in TOP if c in cols]

    # ------------------------------------------------------------------ A3
    print("\n" + "=" * 92 + "\nA3 -- headline leakage at full n")
    a3 = {}
    for c in top:
        d = {f"{x}_vs_{y}": lk([cmed[c][i] for i in by if arm[i] == x],
                               [cmed[c][i] for i in by if arm[i] == y]) for x, y in PAIRS}
        a3[c] = d
        print(f"  {c:28s} " + "  ".join(f"{k[:9]} {v:.4f}" for k, v in d.items()))

    # ------------------------------------------------------------------ A1
    print("\n" + "=" * 92 + "\nA1 -- depth-quintile trend (method identical to E296)")

    def qgrad(bmap):
        cuts = [pct(list(bmap.values()), (i + 1) / 5.0) for i in range(4)]
        buckets = [[] for _ in range(5)]
        for i, b in bmap.items():
            k = 0
            while k < 4 and b > cuts[k]:
                k += 1
            buckets[k].append(i)
        out = {}
        for c in top:
            vs = []
            for ids in buckets:
                vals = [lk([cmed[c][i] for i in ids if arm.get(i) == x],
                           [cmed[c][i] for i in ids if arm.get(i) == y]) for x, y in PAIRS]
                vals = [v for v in vals if math.isfinite(v)]
                vs.append(max(vals) if vals else float("nan"))
            out[c] = vs
        return out, [len(b) for b in buckets]

    g, nb = qgrad(cbis)
    print(f"  quintile n = {nb}   (quintile 0 = deepest BIS)")
    rhos = {}
    for c in top:
        rhos[c] = spear(list(range(5)), g[c])
        print(f"  {c:28s} rho = {rhos[c]:+.4f}   " + " ".join(f"{v:.3f}" for v in g[c]))
    obs = med(list(rhos.values()))
    null = []
    for _ in range(200):
        perm = {}
        for x in ARMS:
            ids = [i for i in cbis if arm.get(i) == x]
            vals = [cbis[i] for i in ids]; rng.shuffle(vals)
            perm.update(dict(zip(ids, vals)))
        gp, _ = qgrad(perm)
        null.append(med([spear(list(range(5)), gp[c]) for c in top]))
    null.sort()
    p = sum(1 for v in null if v <= obs) / len(null)
    print(f"  median rho = {obs:+.4f}   null 5th = {null[int(0.05*len(null))]:+.4f}   p = {p:.4f}")
    print(f"  [750-case subsample gave median rho -0.9000, p = 0.0000]")

    # ------------------------------------------------------------------ A2
    print("\n" + "=" * 92 + "\nA2 -- BIS-matched leakage (method identical to E281)")
    a2, rets = {}, []
    for x, y in PAIRS:
        ax = [i for i in cbis if arm.get(i) == x]; ay = [i for i in cbis if arm.get(i) == y]
        lo = max(pct([cbis[i] for i in ax], 0.10), pct([cbis[i] for i in ay], 0.10))
        hi = min(pct([cbis[i] for i in ax], 0.90), pct([cbis[i] for i in ay], 0.90))
        ax2 = sorted([i for i in ax if lo <= cbis[i] <= hi], key=lambda i: cbis[i])
        ay2 = sorted([i for i in ay if lo <= cbis[i] <= hi], key=lambda i: cbis[i])
        pool = list(ay2); ma, mb = [], []
        for i in ax2:
            if not pool:
                break
            j = min(range(len(pool)), key=lambda k: abs(cbis[pool[k]] - cbis[i]))
            if abs(cbis[pool[j]] - cbis[i]) <= 3.0:
                ma.append(i); mb.append(pool.pop(j))
        d = {}
        for c in top:
            full = a3[c][f"{x}_vs_{y}"]
            m = lk([cmed[c][i] for i in ma], [cmed[c][i] for i in mb])
            d[c] = {"full": full, "matched": m,
                    "retained": m / full if full and full > 0 else float("nan")}
            if math.isfinite(d[c]["retained"]):
                rets.append(d[c]["retained"])
        a2[f"{x}_vs_{y}"] = {"n_matched": len(ma), "features": d}
        print(f"  {x}_vs_{y:5s} matched {len(ma)} pairs (was 158-179): "
              + ", ".join(f"{c[:16]} {d[c]['full']:.3f}->{d[c]['matched']:.3f}" for c in top[:3]))
    print(f"  median retention = {med(rets):.4f}   [750-case subsample gave 1.086]")

    rep = {"counts": counts, "n_cases": len(by),
           "floors": {f"{x}_vs_{y}": null95(counts[x], counts[y]) for x, y in PAIRS},
           "A3_leakage": a3, "A1_rhos": rhos, "A1_median_rho": obs, "A1_p": p,
           "A1_quintile_n": nb, "A1_gradient": g,
           "A2": a2, "A2_median_retention": med(rets),
           "subsample_reference": {"A1_median_rho": -0.9000, "A1_p": 0.0000,
                                   "A2_median_retention": 1.086},
           "note": "precision upgrade of E296/E281 on the complete eligible cohort; method unchanged; "
                   "not blind and not independent confirmation"}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
