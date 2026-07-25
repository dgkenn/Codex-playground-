#!/usr/bin/env python3
"""OUT-OF-SAMPLE PREDICTIONS OF THE SYMPATHOLYSIS MECHANISM — registered before running.

A mechanism earns its keep by predicting things that were not used to build it, including the NULLS. The proposed
mechanism is: burst suppression marks a depth of anaesthesia at which central sympathetic outflow is withdrawn;
the consequence is vasodilation (SVR falls, cardiac output preserved or rising), which manifests as a pressure
fall over the following 60-120 s.

If that is right, the size of the lead must scale with how much SYMPATHETIC TONE THERE IS TO WITHDRAW, and must
vanish where that tone is already gone or is being replaced pharmacologically. Those are quantitative, directional,
falsifiable predictions, and they are stated here BEFORE the numbers are seen.

  P1  AGE. Baroreflex gain and sympathetic reserve decline with age. Older patients have less capacity to defend
      pressure when outflow is withdrawn, so the lead should be LARGER in the elderly.
      Direction: more negative forward-minus-backward with increasing age.

  P2  ANAESTHETIC DEPTH (Ce). More propofol means more sympatholysis. Within a patient, at higher effect-site
      concentration the same suppression should be followed by a LARGER fall.
      Direction: more negative in the upper Ce tertile than the lower.
      NOTE this is not circular: dose is already adjusted for in every model as a covariate: the prediction is
      about EFFECT MODIFICATION by dose, not about the main effect of dose.

  P3  EXOGENOUS VASOPRESSOR. If a vasoconstrictor infusion is running, vascular tone is being supplied
      pharmacologically rather than neurally, so withdrawing central outflow should have less pressure consequence.
      The lead should be ATTENUATED or ABOLISHED in vasopressor-exposed bins.
      Direction: closer to zero when a pressor is running. This is the sharpest test, because it predicts the
      DISAPPEARANCE of an effect rather than its presence.

  P4  OPIOID CO-ADMINISTRATION. Remifentanil is itself sympatholytic. More opioid means more of the outflow is
      already suppressed, so the marginal effect of a suppression episode should be LARGER (additive suppression
      of the same pathway) -- OR smaller if the pathway is already saturated. This one is genuinely ambiguous in
      direction, so it is registered as a two-sided test and will NOT be counted as confirmatory either way.

FALSIFICATION: P1, P2 and P3 all have a stated direction. If P3 in particular fails -- if the lead is just as large
while a vasopressor is running -- the vasodilation mechanism is in serious trouble, because the pressure fall would
then be occurring without a neural vascular route.

Estimator is unchanged: within-case fixed effects, adjustment for MAP(t), dose, dCe, and the pre-trend measured
over [t-2k, t-k]; bins holding both a forward and a backward neighbour; case-level cluster bootstrap. Each
moderator is tested by fitting the SAME model in strata and comparing the forward-minus-backward statistic, with
the between-stratum DIFFERENCE bootstrapped from the same resampled cases so the comparison is properly
correlated (comparing two significance verdicts is the error this project already made once).
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)


def load():
    """(caseid, bin_t) -> [bs, MAP, Ce, age, pressor_flag, remi_ce]."""
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]),
                              float(d["mbp"]) if d["mbp"] else np.nan,
                              float(d["ce"]) if d["ce"] else np.nan,
                              float(d["age"]) if d["age"] else np.nan,
                              np.nan, np.nan]
            except Exception:
                pass
    path = f"{DATA}/drug_bins.csv"
    if os.path.exists(path):
        seen = set()
        with open(path) as fh:
            for d in csv.DictReader(fh):
                try:
                    cid = d["caseid"]; t = float(d["bin_t"])
                    if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                        continue
                    seen.add((cid, t))
                    # A blank vasopressor column means that track does not exist for the case, i.e. the drug was
                    # never given -- those bins are UNEXPOSED, not unknown. Treating blank as missing (an earlier
                    # bug here) left only 96 comparator bins, because the only press==0 rows were cases that had a
                    # pressor track recording an explicit zero.
                    press = 0.0
                    for k in ("phe", "nepi", "epi", "dopa", "dobu", "vaso", "ephed"):
                        v = d.get(k, "")
                        if v in ("", None):
                            continue
                        try:
                            if float(v) > 0:
                                press = 1.0
                        except Exception:
                            pass
                    HD[cid][t][4] = press
                    r = d.get("remi_ce", "")
                    HD[cid][t][5] = float(r) if r not in ("", None) else np.nan
                except Exception:
                    pass
    return HD


def build(HD, k):
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd:
                continue
            bs, m, dose, age, press, remi = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and dose == dose and doseb == doseb):
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["e"].append(1.0 if bs > 0 else 0.0)
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb - mb2)
            cols["df"].append(mf - m); cols["db"].append(mb - m)
            cols["age"].append(age); cols["press"].append(press); cols["remi"].append(remi)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def coef(sub, dy, w, ncase):
    mat = np.column_stack([sub["e"], sub["m0"], sub["dz"], sub["dce"], sub["pre"], dy])
    sw = np.bincount(sub["case"], weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(sub["case"], weights=w * mat[:, j], minlength=ncase) / sw
        dm[:, j] = mat[:, j] - mu[sub["case"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        return float(np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[0])
    except np.linalg.LinAlgError:
        return None


def contrast(D, mask_a, mask_b, label_a, label_b, title):
    """forward-minus-backward in each stratum, plus their DIFFERENCE, from one shared case bootstrap."""
    print(f"\n=== {title} ===")
    for nm, msk in ((label_a, mask_a), (label_b, mask_b)):
        if msk.sum() < 3000:
            print(f"   {nm}: insufficient ({int(msk.sum())} bins)"); return
    subs = {}
    for tag, msk in (("a", mask_a), ("b", mask_b)):
        s = {kk: D[kk][msk] for kk in ("case", "e", "m0", "dz", "dce", "pre", "df", "db")}
        o = np.argsort(s["case"], kind="stable")
        s = {kk: v[o] for kk, v in s.items()}
        subs[tag] = s
    starts = {t: np.searchsorted(subs[t]["case"], np.arange(D["ncase"]), side="left") for t in subs}
    ends = {t: np.searchsorted(subs[t]["case"], np.arange(D["ncase"]), side="right") for t in subs}
    span = {t: ends[t] - starts[t] for t in subs}
    pts = {}
    for t in subs:
        w1 = np.ones(len(subs[t]["case"]))
        f = coef(subs[t], subs[t]["df"], w1, D["ncase"]); b = coef(subs[t], subs[t]["db"], w1, D["ncase"])
        pts[t] = None if (f is None or b is None) else f - b
    if pts["a"] is None or pts["b"] is None:
        print("   fit failed"); return
    ba, bb, bd = [], [], []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        vals = {}
        for t in subs:
            w = np.repeat(cnt, span[t])
            f = coef(subs[t], subs[t]["df"], w, D["ncase"]); b = coef(subs[t], subs[t]["db"], w, D["ncase"])
            vals[t] = None if (f is None or b is None) else f - b
        if vals["a"] is None or vals["b"] is None:
            continue
        ba.append(vals["a"]); bb.append(vals["b"]); bd.append(vals["a"] - vals["b"])
    if len(bd) < 50:
        print("   bootstrap failed"); return
    for nm, pt, bs_ , msk in ((label_a, pts["a"], ba, mask_a), (label_b, pts["b"], bb, mask_b)):
        lo, hi = np.percentile(bs_, [2.5, 97.5])
        print(f"   {nm:34s} fwd-bwd = {pt:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}   bins={int(msk.sum())}")
    lo, hi = np.percentile(bd, [2.5, 97.5])
    print(f"   {'DIFFERENCE (a - b)':34s}           {pts['a']-pts['b']:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
          f"{'*' if (lo>0 or hi<0) else 'ns'}")


def main():
    k = int(os.environ.get("K", "4"))
    D = build(load(), k)
    print(f"k=+/-{k} bins (+/-{30*k}s); {len(D['case'])} bins, {D['ncase']} cases; {NBOOT} bootstrap reps")
    print("statistic = forward minus backward change in MAP; more negative = a STRONGER lead\n")

    age = D["age"]
    ok = np.isfinite(age)
    if ok.sum() > 10000:
        cut = np.percentile(age[ok], [33, 67])
        contrast(D, ok & (age >= cut[1]), ok & (age < cut[0]),
                 f"P1 older  (age >= {cut[1]:.0f})", f"P1 younger (age < {cut[0]:.0f})",
                 "P1 AGE -- predicted: LARGER lead in the elderly (less baroreflex reserve)")

    ce = D["dz"]
    cut = np.percentile(ce, [33, 67])
    contrast(D, ce >= cut[1], ce < cut[0],
             f"P2 high Ce (>= {cut[1]:.2f})", f"P2 low Ce  (< {cut[0]:.2f})",
             "P2 DEPTH -- predicted: LARGER lead at higher effect-site concentration")

    pr = D["press"]
    ok = np.isfinite(pr)
    if ok.sum() > 10000 and (ok & (pr > 0)).sum() > 3000:
        contrast(D, ok & (pr > 0), ok & (pr == 0),
                 "P3 vasopressor RUNNING", "P3 no vasopressor",
                 "P3 VASOPRESSOR -- predicted: lead ATTENUATED when vascular tone is supplied pharmacologically")
    else:
        n = int((ok & (pr > 0)).sum()) if ok.any() else 0
        print(f"\n=== P3 VASOPRESSOR === insufficient exposed bins ({n}); drug extraction may still be running")

    rm = D["remi"]
    ok = np.isfinite(rm) & (rm > 0)
    if ok.sum() > 10000:
        cut = np.percentile(rm[ok], [33, 67])
        contrast(D, ok & (rm >= cut[1]), ok & (rm < cut[0]),
                 f"P4 high remi (>= {cut[1]:.2f})", f"P4 low remi  (< {cut[0]:.2f})",
                 "P4 OPIOID -- two-sided, registered as NON-confirmatory in either direction")
    else:
        print(f"\n=== P4 OPIOID === insufficient bins with remifentanil ({int(ok.sum())})")


if __name__ == "__main__":
    sys.exit(main())
