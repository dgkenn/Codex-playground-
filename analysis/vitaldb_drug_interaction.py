#!/usr/bin/env python3
"""PROPOFOL vs SEVOFLURANE, tested as a FORMAL INTERACTION rather than by comparing two separate analyses.

WHY THIS FILE EXISTS. This project has already made the difference-of-significance error once, and it cost a
retracted headline claim: the two-phenotype dissociation rested on one stratum being significant and the other
not, and when finally tested as an interaction it was 1.08 [0.89, 1.32] — nothing. Every subsequent statement
about drug class in this work has been made the same wrong way: propofol shows a duration gradient, sevoflurane
does not, therefore they differ. That is not a test. Two estimates can differ in significance while being
statistically indistinguishable, especially when the cohorts differ in size and in exposure prevalence.

So the drug comparison is done here as it should be: BOTH cohorts in ONE model, with a drug indicator and its
interaction with the exposure, and the interaction bootstrapped over cases so the two arms move together.

    pooled rows   propofol (Ce >= 1.0 ug/mL) and sevoflurane (end-tidal >= 1.0 %) maintenance bins
    exposure      any burst suppression in bin t
    model         dMAP ~ suppression + suppression x SEVO + MAP(t) + dose + dCe + pre-trend
                        + CASE FIXED EFFECTS
                  The drug main effect is absorbed by the case fixed effect — a case is entirely one agent — so
                  only the INTERACTION is identified, which is exactly the quantity of interest.
    outcomes      forward dMAP, backward dMAP, and the forward-minus-backward asymmetry
    inference     CASE-level cluster bootstrap; the interaction's interval is computed from the same replicates

DOSE IS NOT COMPARABLE ACROSS AGENTS and this is the honest limitation. Propofol effect-site concentration in
ug/mL and end-tidal sevoflurane in % are different quantities on different scales; "adjusting for dose" therefore
means something different in each arm. The dose covariate is retained because omitting it is worse, but the
interaction cannot be read as "the same depth produces different haemodynamics". A supplementary run standardises
dose WITHIN each cohort (z-scored per agent), which at least puts the covariate on a common footing, and both
versions are reported.

    PREDICTION registered before running: the interaction is POSITIVE (a weaker effect under sevoflurane),
    because sevoflurane's separate analyses have consistently shown smaller point estimates.
    FALSIFICATION: an interval spanning zero means the agents are NOT distinguishable on this evidence, and every
    statement in this project contrasting them must be withdrawn and replaced with a pooled estimate.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
rng = np.random.default_rng(20260725)
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


def load_one(fn, tag):
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/{fn}") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = f"{tag}:{d['caseid']}"; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]), _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan]
            except Exception:
                pass
    return HD


def build(k):
    cols = defaultdict(list); ci = {}
    for fn, tag, sevo in (("bridge_bins.csv", "P", 0.0), ("sevo_bins.csv", "S", 1.0)):
        HD = load_one(fn, tag)
        # dose standardised WITHIN cohort so the covariate is on a common footing across agents
        allce = [bd[t][2] for c, bd in HD.items() for t in bd
                 if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0]
        mu = float(np.mean(allce)); sd = float(np.std(allce)) or 1.0
        for c, bd in HD.items():
            ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
            if len(ts) < 32:
                continue
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
                cols["case"].append(ci[c]); cols["sevo"].append(sevo)
                cols["x"].append(1.0 if bs > 0 else 0.0)
                cols["m0"].append(m)
                cols["dz_raw"].append(dose)
                cols["dz_std"].append((dose - mu) / sd)
                cols["dce"].append(dose - doseb); cols["pre"].append(mb2 - mb3)
                cols["df"].append(mf - m); cols["db"].append(mb - m)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def fit(D, dy, w, dosecol):
    inter = D["x"] * D["sevo"]
    mat = np.column_stack([D["x"], inter, D["m0"], D[dosecol], D["dce"], D["pre"], dy])
    sw = np.bincount(D["case"], weights=w, minlength=D["ncase"])
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(D["case"], weights=w * mat[:, j], minlength=D["ncase"]) / sw
        dm[:, j] = mat[:, j] - mu[D["case"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        b = np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)
    except np.linalg.LinAlgError:
        return None
    return b[0], b[1]          # propofol effect, sevo-vs-propofol interaction


def run(D, dosecol, label):
    n = len(D["case"])
    span = (np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
            - np.searchsorted(D["case"], np.arange(D["ncase"]), side="left"))
    w1 = np.ones(n)
    ff = fit(D, D["df"], w1, dosecol); bb = fit(D, D["db"], w1, dosecol)
    if ff is None or bb is None:
        print(f"   {label}: fit failed"); return
    a_prop = ff[0] - bb[0]                  # propofol asymmetry
    a_int = ff[1] - bb[1]                   # difference in asymmetry, sevo vs propofol
    bp, bi = [], []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        f2 = fit(D, D["df"], w, dosecol); b2 = fit(D, D["db"], w, dosecol)
        if f2 is None or b2 is None:
            continue
        bp.append(f2[0] - b2[0]); bi.append(f2[1] - b2[1])
    if len(bi) < 50:
        print(f"   {label}: bootstrap failed"); return
    lo, hi = np.percentile(bp, [2.5, 97.5])
    print(f"\n   [{label}]")
    print(f"      propofol asymmetry                 {a_prop:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
          f"{'*' if (lo>0 or hi<0) else 'ns'}")
    lo, hi = np.percentile(bi, [2.5, 97.5])
    verdict = ("agents DIFFER" if (lo > 0 or hi < 0) else "agents NOT distinguishable")
    print(f"      INTERACTION (sevo - propofol)      {a_int:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}]   {verdict}")
    print(f"      implied sevoflurane asymmetry      {a_prop + a_int:+7.3f} mmHg")


def main():
    k = int(os.environ.get("K", "4"))
    D = build(k)
    n = len(D["case"])
    if n < 20000:
        print(f"insufficient rows ({n})"); return
    o = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][o]
    npro = len(np.unique(D["case"][D["sevo"] == 0]))
    nsev = len(np.unique(D["case"][D["sevo"] == 1]))
    print(f"pooled: {n} bins, {D['ncase']} cases ({npro} propofol, {nsev} sevoflurane); k=+/-{k} bins")
    print(f"suppression prevalence: propofol {D['x'][D['sevo']==0].mean():.3f}, "
          f"sevoflurane {D['x'][D['sevo']==1].mean():.3f}")
    print(f"{NBOOT} case-level bootstrap replicates; the drug main effect is absorbed by the case fixed effect")
    run(D, "dz_raw", "dose on its native scale (ug/mL vs %) -- NOT comparable across agents")
    run(D, "dz_std", "dose z-scored WITHIN each cohort -- covariate on a common footing")
    print("\n   If the interaction interval spans zero the agents are not distinguishable on this evidence, and")
    print("   every drug-class contrast in this project must be replaced by the pooled estimate.")


if __name__ == "__main__":
    sys.exit(main())
