#!/usr/bin/env python3
"""ATTRIBUTABLE HYPOTENSIVE BURDEN — translating the effect into the units clinicians and trialists use.

THE PROBLEM THIS SOLVES. The primary result is an asymmetry of about 0.33 mmHg, rising to 0.85 mmHg at high
suppression occupancy. Stated that way it reads as trivial, and a reader would be right to shrug: nobody titrates
an anaesthetic to protect a third of a millimetre of mercury.

But mmHg-per-bin is not the unit this field uses. The established exposure metric — the one that predicts acute
kidney injury, myocardial injury and mortality in the large perioperative outcome studies — is TIME SPENT BELOW A
PRESSURE THRESHOLD, conventionally minutes with MAP < 65 mmHg. A small average displacement sustained over a long
operation can move that quantity substantially, because what matters is how much of the pressure distribution is
pushed across a threshold, not the mean shift itself.

So this file asks: HOW MANY MINUTES OF INTRAOPERATIVE HYPOTENSION ARE ATTRIBUTABLE TO BURST SUPPRESSION?

METHOD — g-computation (standardisation) on the within-case estimator.
  1. Fit, within case, the probability that MAP < 65 at t+k as a function of recent suppression occupancy, with
     the same covariates and fixed effects as every other model here. A linear probability model is used because
     it is collapsible and because the quantity wanted is a RISK DIFFERENCE that can be summed over bins into
     minutes; an odds ratio cannot be summed.
  2. Predict each bin's hypotension probability under the observed occupancy, and again under the counterfactual
     in which occupancy is set to ZERO for every bin (no suppression at any point).
  3. The difference, summed over a case's bins and multiplied by 0.5 min/bin, is that case's ATTRIBUTABLE
     HYPOTENSIVE MINUTES.
  4. Aggregate: total attributable minutes, attributable minutes per case, and the POPULATION ATTRIBUTABLE
     FRACTION — attributable minutes divided by observed hypotensive minutes.

WHAT THIS IS AND IS NOT. This is a standardisation of an observational within-patient association, not a trial
result. It answers "if the suppression-associated component of hypotension were removed, and nothing else changed,
how much hypotensive time would disappear?" It does NOT answer "what would happen if you titrated the anaesthetic
to avoid suppression", because that intervention also changes the dose, and the dose has its own direct
haemodynamic effect that is adjusted OUT of this estimator. The two are different quantities and conflating them
is exactly the error that would make this misleading. The counterfactual here is deliberately the narrower one.

ALSO REPORTED, because a trialist needs it: the implied per-case difference is the effect size a randomised
depth-titration trial would be trying to detect on this endpoint. ENGAGES reduced suppression substantially and
found no delirium benefit; it was not powered on hypotensive minutes, and this gives the number that would have
been needed.

Inference: case-level cluster bootstrap over the whole procedure (refitting the model in each replicate), so the
intervals include the uncertainty in the effect estimate, not just sampling of cases.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))
THRESH = float(os.environ.get("THRESH", "65"))
BIN_MIN = 0.5


def _map_ok(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


def load(cohort):
    HD = defaultdict(dict); seen = set()
    fn = "bridge_bins.csv" if cohort == "prop" else "sevo_bins.csv"
    with open(f"{DATA}/{fn}") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]), _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan]
            except Exception:
                pass
    return HD


def build(HD, k):
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        occ = {}
        for i, t in enumerate(ts):
            w = ts[max(0, i - 9):i + 1]
            occ[t] = float(sum(1.0 for x in w if bd[x][0] == bd[x][0] and bd[x][0] > 0))
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            bs, m, dose = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and mb3 == mb3
                    and dose == dose and doseb == doseb and bs == bs):
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["occ"].append(occ[t])
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb2 - mb3)
            cols["y"].append(1.0 if mf < THRESH else 0.0)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def demean(mat, case, ncase, w):
    sw = np.bincount(case, weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    out = np.empty_like(mat)
    mus = np.empty((ncase, mat.shape[1]))
    for j in range(mat.shape[1]):
        mu = np.bincount(case, weights=w * mat[:, j], minlength=ncase) / sw
        mus[:, j] = mu
        out[:, j] = mat[:, j] - mu[case]
    return out, mus


def attributable(D, w):
    """Fit within-case LPM, then contrast observed occupancy against occupancy set to zero."""
    X = np.column_stack([D["occ"], D["m0"], D["dz"], D["dce"], D["pre"]])
    mat = np.column_stack([X, D["y"]])
    dm, _ = demean(mat, D["case"], D["ncase"], w)
    Xd = dm[:, :-1]; yd = dm[:, -1]
    try:
        b = np.linalg.solve((Xd.T * w) @ Xd + 1e-10 * np.eye(Xd.shape[1]), (Xd.T * w) @ yd)
    except np.linalg.LinAlgError:
        return None
    beta_occ = b[0]
    # counterfactual contrast: only the occupancy term changes, fixed effects and covariates cancel
    delta_p = beta_occ * D["occ"]                    # excess hypotension probability attributable to occupancy
    attr_min = float(np.sum(w * delta_p) * BIN_MIN)
    obs_min = float(np.sum(w * D["y"]) * BIN_MIN)
    ncase_eff = float(np.sum(w > 0)) if False else None
    return beta_occ, attr_min, obs_min


def main():
    cohort = os.environ.get("COHORT", "prop")
    k = int(os.environ.get("K", "4"))
    D = build(load(cohort), k)
    n = len(D.get("case", []))
    if n < 10000:
        print(f"insufficient rows ({n})"); return
    o = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][o]
    span = (np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
            - np.searchsorted(D["case"], np.arange(D["ncase"]), side="left"))
    w1 = np.ones(n)
    print(f"cohort={cohort}  k=+{k} bins (+{30*k}s ahead);  {n} bins, {D['ncase']} cases")
    print(f"outcome: MAP < {THRESH:.0f} mmHg;  exposure: suppressed bins in the preceding 5 min (0-10)")
    print(f"MAP filtered to [{MAP_LO},{MAP_HI}];  {NBOOT} case-level bootstrap replicates\n")
    base = attributable(D, w1)
    if base is None:
        print("fit failed"); return
    beta, attr, obs = base
    print(f"observed hypotensive time in the analysed bins: {obs:,.0f} min "
          f"({obs/D['ncase']:.1f} min per case)")
    print(f"mean suppression occupancy: {D['occ'].mean():.2f} of the last 10 bins\n")
    bb, ba, bf, bpc = [], [], [], []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        r = attributable(D, w)
        if r is None:
            continue
        b2, a2, o2 = r
        bb.append(b2); ba.append(a2)
        if o2 > 0:
            bf.append(100 * a2 / o2)
        bpc.append(a2 / D["ncase"])
    if len(ba) < 50:
        print("bootstrap failed"); return
    lo, hi = np.percentile(bb, [2.5, 97.5])
    print(f"risk of hypotension per suppressed bin of the last 10:  {100*beta:+.3f} pp "
          f"[{100*lo:+.3f},{100*hi:+.3f}] {'*' if (lo>0 or hi<0) else 'ns'}")
    lo, hi = np.percentile(bpc, [2.5, 97.5])
    print(f"\nATTRIBUTABLE HYPOTENSIVE MINUTES PER CASE:  {attr/D['ncase']:.2f} min "
          f"[{lo:.2f},{hi:.2f}]")
    lo, hi = np.percentile(bf, [2.5, 97.5])
    print(f"POPULATION ATTRIBUTABLE FRACTION of hypotensive time:  {100*attr/obs:.1f} % "
          f"[{lo:.1f} %,{hi:.1f} %]")
    print(f"\n   Interpretation: of the {obs/D['ncase']:.1f} minutes per case spent below {THRESH:.0f} mmHg in")
    print(f"   these bins, about {attr/D['ncase']:.2f} are attributable to the suppression-associated component.")
    print("   This is a standardisation of an observational within-patient association, NOT a trial result, and")
    print("   NOT the effect of titrating anaesthetic depth -- that intervention also changes the dose, whose own")
    print("   direct haemodynamic effect is adjusted out of this estimator. The counterfactual here is the")
    print("   narrower one, deliberately.")
    print("   The per-case figure is also the effect size a randomised depth-titration trial would need to")
    print("   detect on this endpoint.")


if __name__ == "__main__":
    sys.exit(main())
