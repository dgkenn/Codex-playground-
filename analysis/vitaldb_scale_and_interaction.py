#!/usr/bin/env python3
"""TWO decisive checks the earlier tables cannot settle. Run on ONE identical row set so nothing else varies.

CHECK 1 -- SCALE vs FUNCTIONAL FORM.
The primary models report an OR "per full suppression" (a 0 -> 1 change in the bin's suppression fraction), while
the RTM-immune Mantel-Haenszel analysis reports "any suppression vs none". Those are different contrasts and are
NOT comparable: if the average suppressed bin is only ~20 % suppressed, an OR of 1.9 per unit IS an OR of
1.9^0.2 = 1.14 for the any-vs-none contrast. Before concluding that exact MAP stratification shrank the effect, the
scale change must be removed. Three models on identical rows:
    A  continuous exposure, MAP linear        (the original specification)
    B  binary exposure,     MAP linear        (changes ONLY the scale)
    C  binary exposure,     MAP exact 2 mmHg  (changes ONLY the functional form; = the MH estimator)
A vs B isolates scale. B vs C isolates regression to the mean. Both are reported per-case-bootstrap.

CHECK 2 -- IS THE DISSOCIATION REAL?
The two-phenotype claim rests on "significant above baseline, not significant below". That is the difference-of-
significance fallacy: the below-baseline stratum has ~14x fewer bins, so it is underpowered by construction. The
claim requires a formal INTERACTION -- the ratio of the two odds ratios, with an interval. Computed here by
resampling CASES with replacement and recomputing both stratum ORs inside each replicate, so the two estimates
move together and their ratio is properly correlated.

Verdict rule stated in advance: if the OR-ratio interval includes 1, the two-phenotype dissociation is NOT
established by these data and must not be presented as a finding.
"""
import csv, math, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
rng = np.random.default_rng(20260725)


def load():
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                ce = float(d["ce"]) if d["ce"] else np.nan
                HD[cid][t] = (float(d["bs"]),
                              float(d["mbp"]) if d["mbp"] else np.nan,
                              ce,
                              float(d["age"]) if d["age"] else np.nan)
            except Exception:
                pass
    return HD


def build(HD, lag_bins=4):
    case = []; phen = []; strat = []; bsf = []; mapv = []; cev = []; agev = []; out = []
    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        bv = [bd[t][1] for t in ts[:10] if bd[t][1] == bd[t][1]]
        if len(bv) < 5:
            continue
        b0 = float(np.median(bv))
        for t in ts[20:]:
            t2 = t + 30.0 * lag_bins
            if t2 not in bd:
                continue
            bs, m, ce, age = bd[t]; m2 = bd[t2][1]
            if m != m or m2 != m2:
                continue
            if m >= b0:
                ph = 1
            elif m < 0.9 * b0:
                ph = 0
            else:
                continue
            if c not in ci:
                ci[c] = len(ci)
            case.append(ci[c]); phen.append(ph); strat.append(int(np.clip(m, 30, 160) // 2))
            bsf.append(bs); mapv.append(m); cev.append(ce); agev.append(age if age == age else 55.0)
            out.append(1 if m2 < 65 else 0)
    return dict(case=np.array(case, np.int32), phen=np.array(phen, np.int8),
                strat=np.array(strat, np.int16), bs=np.array(bsf, np.float64),
                map=np.array(mapv, np.float64), ce=np.array(cev, np.float64),
                age=np.array(agev, np.float64), y=np.array(out, np.float64), ncase=len(ci))


def logit_w(X, y, w, iters=60):
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        W = np.clip(p * (1 - p), 1e-9, None) * w
        z = X @ b + np.where(W > 0, (y - p) / np.clip(p * (1 - p), 1e-9, None), 0.0)
        try:
            nb = np.linalg.solve((X.T * W) @ X + 1e-6 * np.eye(X.shape[1]), (X.T * W) @ z)
        except np.linalg.LinAlgError:
            return None
        if np.max(np.abs(nb - b)) < 1e-8:
            b = nb; break
        b = nb
    return b


def mh_or(strat, expo, out, w):
    k = int(strat.max()) + 1
    cell = strat.astype(np.int64) * 4 + expo.astype(np.int64) * 2 + out.astype(np.int64)
    cnt = np.bincount(cell, weights=w, minlength=k * 4).reshape(k, 4)
    b = cnt[:, 2]; a = cnt[:, 3]; d_ = cnt[:, 0]; c_ = cnt[:, 1]
    n = a + b + c_ + d_
    ok = n > 0
    num = np.sum(a[ok] * d_[ok] / n[ok]); den = np.sum(b[ok] * c_[ok] / n[ok])
    if den <= 0 or num <= 0:
        return np.nan
    return num / den


def main():
    lag = int(os.environ.get("LAG", "4"))
    D = build(load(), lag)
    print(f"rows={len(D['y'])}  cases={D['ncase']}  lag=+{lag} bins (+{30*lag}s)")
    exposed = D["bs"] > 0
    pooled_mwe = float(D["bs"][exposed].mean())
    print(f"suppression present in {100*exposed.mean():.1f}% of bins; among those the mean suppressed "
          f"FRACTION of the bin is {pooled_mwe:.3f} (pooled over both phenotypes)")
    # The rescaling below is applied to a coefficient fitted ONLY on the sensitivity stratum, so the exposure
    # intensity used to rescale it must come from that same stratum. The two strata are defined by different
    # physiology and need not share a mean suppressed fraction; using the pooled value would rescale by the
    # wrong scalar and print a number that does not correspond to the model it is compared against.
    sens = D["phen"] == 1
    se_ = sens & exposed
    mean_when_exposed = float(D["bs"][se_].mean())
    print(f"  within the sensitivity stratum (MAP >= own baseline) that mean is {mean_when_exposed:.3f}")
    print(f"  => a 'per full suppression' OR of X corresponds to X^{mean_when_exposed:.3f} on the any-vs-none scale")

    # multiplicity vector machinery for case-level bootstrap
    order = np.argsort(D["case"], kind="stable")
    for k in ("case", "phen", "strat", "bs", "map", "ce", "age", "y"):
        D[k] = D[k][order]
    starts = np.searchsorted(D["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts

    def draw():
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        return np.repeat(cnt, span)

    print("\n=== CHECK 1: scale vs functional form (sensitivity phenotype, MAP >= own baseline) ===")
    s = D["phen"] == 1
    y = D["y"][s]; w1 = np.ones(s.sum())
    Xc = np.column_stack([np.ones(s.sum()), D["bs"][s], D["map"][s], D["ce"][s], D["age"][s]])
    Xb = Xc.copy(); Xb[:, 1] = (D["bs"][s] > 0).astype(float)
    st = D["strat"][s]; ex = (D["bs"][s] > 0).astype(np.int8); ou = D["y"][s].astype(np.int8)

    bA = logit_w(Xc, y, w1); bB = logit_w(Xb, y, w1); orC = mh_or(st, ex, ou, w1)
    if bA is None or bB is None or not (orC == orC):
        print("   point-estimate fit failed (singular design) -- cannot report CHECK 1")
        return
    a_boot = []; b_boot = []; c_boot = []
    for _ in range(NBOOT):
        w = draw(); ws = w[s]
        ra = logit_w(Xc, y, ws); rb = logit_w(Xb, y, ws); rc = mh_or(st, ex, ou, ws)
        if ra is not None: a_boot.append(ra[1])
        if rb is not None: b_boot.append(rb[1])
        if rc == rc and 0 < rc < 1e6: c_boot.append(math.log(rc))

    def rep(name, point, boots, note=""):
        lo, hi = np.percentile(boots, [2.5, 97.5])
        print(f"   {name:52s} OR={math.exp(point):5.2f} [{math.exp(lo):.2f},{math.exp(hi):.2f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}  {note}")

    rep("A  continuous exposure, MAP linear   (per full suppr.)", bA[1], a_boot)
    print(f"   A  ... rescaled to the any-vs-none contrast          "
          f"OR={math.exp(bA[1]*mean_when_exposed):5.2f}   <- compare this to B and C")
    rep("B  binary exposure (any vs none), MAP linear          ", bB[1], b_boot)
    rep("C  binary exposure, MAP exact 2 mmHg strata (MH)      ", math.log(orC), c_boot)
    print("   [A-rescaled vs B = scale effect;  B vs C = regression-to-the-mean / functional-form effect]")

    print("\n=== CHECK 2: formal phenotype interaction (ratio of the two Mantel-Haenszel ORs) ===")
    s1 = D["phen"] == 1; s0 = D["phen"] == 0
    o1 = mh_or(D["strat"][s1], (D["bs"][s1] > 0).astype(np.int8), D["y"][s1].astype(np.int8), np.ones(s1.sum()))
    o0 = mh_or(D["strat"][s0], (D["bs"][s0] > 0).astype(np.int8), D["y"][s0].astype(np.int8), np.ones(s0.sum()))
    ex1 = (D["bs"][s1] > 0).astype(np.int8); ex0 = (D["bs"][s0] > 0).astype(np.int8)
    st1 = D["strat"][s1]; st0 = D["strat"][s0]
    y1 = D["y"][s1].astype(np.int8); y0 = D["y"][s0].astype(np.int8)
    ratios = []; e1s = []; e0s = []
    for _ in range(NBOOT):
        w = draw()
        r1 = mh_or(st1, ex1, y1, w[s1]); r0 = mh_or(st0, ex0, y0, w[s0])
        if r1 == r1 and r0 == r0 and 0 < r1 < 1e6 and 0 < r0 < 1e6:
            ratios.append(math.log(r1 / r0)); e1s.append(math.log(r1)); e0s.append(math.log(r0))
    l1, h1 = np.percentile(e1s, [2.5, 97.5]); l0, h0 = np.percentile(e0s, [2.5, 97.5])
    lr, hr = np.percentile(ratios, [2.5, 97.5])
    print(f"   sensitivity phenotype  (MAP >= own baseline)  OR={o1:.2f} [{math.exp(l1):.2f},{math.exp(h1):.2f}]"
          f"   bins={int(s1.sum())}")
    print(f"   hypoperfusion phenotype(MAP <  own baseline)  OR={o0:.2f} [{math.exp(l0):.2f},{math.exp(h0):.2f}]"
          f"   bins={int(s0.sum())}")
    print(f"   RATIO OF ODDS RATIOS (the interaction)        {math.exp(np.mean(ratios)):.2f} "
          f"[{math.exp(lr):.2f},{math.exp(hr):.2f}]  (B={len(ratios)})")
    if lr < 0 < hr:
        print("   VERDICT: interval includes 1 -> the two-phenotype DISSOCIATION IS NOT ESTABLISHED.")
        print("            The earlier 'positive above baseline / null below' contrast is a difference-of-")
        print("            significance artefact driven by the 14-fold difference in bin counts.")
    else:
        print("   VERDICT: interval excludes 1 -> the dissociation survives a formal interaction test.")


if __name__ == "__main__":
    sys.exit(main())
