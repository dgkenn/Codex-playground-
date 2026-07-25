#!/usr/bin/env python3
"""RESIDUAL AUTONOMIC TONE as the moderator — the non-circular version of a prediction I derived backwards.

THE ERROR BEING CORRECTED. Predictions P1 (age) and P2 (depth) were registered as "more sympatholytic burden ->
bigger effect" and both failed, significantly, in the opposite direction. The derivation was wrong, not merely the
guess: the magnitude of a sympatholytic effect depends on how much sympathetic tone REMAINS TO BE WITHDRAWN, not on
how much has already gone. A young patient at low propofol and low opioid has HIGH residual tone, so withdrawing it
drops pressure a lot; an elderly patient at high Ce on heavy remifentanil has already lost most of it, leaving
little to remove. Read that way the observed pattern is what sympatholysis predicts.

WHY THAT RE-READING IS WORTH NOTHING BY ITSELF. It is post hoc. Age, dose and opioid are demographic and
pharmacological PROXIES for residual tone, and they are also proxies for a dozen other things -- including, as the
duration analysis suggests, simply how much burst suppression a patient has. Reinterpreting a failed prediction
after the fact is exactly the move that turns a falsifiable mechanism into an unfalsifiable story.

WHAT MAKES THIS A REAL TEST. Residual autonomic tone is DIRECTLY MEASURABLE from the 500 Hz ECG, and those data did
not exist when the hypothesis was formed. This file tests whether the lead scales with a patient's MEASURED
pre-suppression autonomic tone:

    moderator (case level, measured BEFORE the exposure it is meant to modify):
        rmssd   root mean square of successive RR differences  -- vagal / parasympathetic tone
        lfhf    LF/HF power ratio                              -- sympathovagal balance (see caveat below)
        brs     spontaneous baroreflex sensitivity, ms/mmHg    -- baroreflex GAIN, the most direct index of the
                                                                  reflex that defends pressure when tone is lost
    computed over each case's EARLY maintenance bins only, so the moderator is not contaminated by the suppression
    episodes whose effect it is being used to stratify.

    PREDICTION, registered before running: the forward pressure fall after suppression is LARGER in cases with
    HIGHER baseline baroreflex sensitivity and HIGHER RMSSD -- i.e. more tone available to lose.

    THE DISCRIMINATING TEST is not the marginal one. Tone correlates with age and with dose, so the stratification
    is repeated WITHIN age tertiles and WITHIN Ce tertiles. If the tone gradient survives at fixed age and fixed
    depth, tone is doing work that age and dose were only proxying for. If it vanishes, then tone adds nothing and
    the whole residual-tone account should be dropped -- which is the outcome that would falsify it.

CAVEATS THAT MUST TRAVEL WITH ANY RESULT.
  * LF/HF as a "sympathovagal balance" index is contested and the interpretation is not accepted by everyone in the
    field; a 30 s bin also spans only ~1-4 LF cycles, which is short. It is reported because it is conventional,
    but BRS and RMSSD carry the argument and LF/HF is treated as supporting at best.
  * BRS by the sequence method requires spontaneous pressure-RR sequences; bins without valid sequences are missing
    NOT at random (they are more common when the reflex is suppressed), so the BRS subcohort is selected.
  * Anaesthesia itself depresses HRV, so "baseline" here means early-maintenance, not awake, tone.

Estimator unchanged: within-case fixed effects, MAP(t) + dose + dCe + pre-trend over [t-2k, t-k], bins holding both
a forward and a backward neighbour, case-level cluster bootstrap of the between-stratum difference.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
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
                HD[cid][t] = [float(d["bs"]),
                              float(d["mbp"]) if d["mbp"] else np.nan,
                              float(d["ce"]) if d["ce"] else np.nan,
                              float(d["age"]) if d["age"] else np.nan]
            except Exception:
                pass
    AU = defaultdict(dict); seen = set()
    p = f"{DATA}/auto_bins.csv"
    if not os.path.exists(p):
        return HD, AU
    with open(p) as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                def g(k):
                    v = d.get(k, "")
                    try:
                        return float(v) if v not in ("", None) else np.nan
                    except Exception:
                        return np.nan
                AU[cid][t] = (g("rmssd"), g("lfhf"), g("brs_seq"))
            except Exception:
                pass
    return HD, AU


def case_tone(HD, AU, n_early=40):
    """Case-level tone from EARLY maintenance bins only, so it precedes the episodes it will stratify."""
    tone = {}
    for c, bd in HD.items():
        if c not in AU:
            continue
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        early = ts[:n_early]
        vals = [AU[c][t] for t in early if t in AU[c]]
        if len(vals) < 8:
            continue
        arr = np.array(vals, float)
        def med(col):
            v = arr[:, col]; v = v[np.isfinite(v)]
            return float(np.median(v)) if len(v) >= 5 else np.nan
        tone[c] = (med(0), med(1), med(2))
    return tone


def build(HD, tone, k):
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        if c not in tone:
            continue
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        rm, lh, br = tone[c]
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd:
                continue
            bs, m, dose, age = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and dose == dose and doseb == doseb):
                continue
            if bs != bs:
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["e"].append(1.0 if bs > 0 else 0.0)
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb - mb2)
            cols["df"].append(mf - m); cols["db"].append(mb - m)
            cols["age"].append(age); cols["rmssd"].append(rm); cols["lfhf"].append(lh); cols["brs"].append(br)
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


def contrast(D, ma, mb, la, lb, title):
    if ma.sum() < 5000 or mb.sum() < 5000:
        print(f"\n=== {title} === insufficient ({int(ma.sum())} / {int(mb.sum())} bins)")
        return
    keys = ("case", "e", "m0", "dz", "dce", "pre", "df", "db")
    subs = {}
    for tag, msk in (("a", ma), ("b", mb)):
        s = {kk: D[kk][msk] for kk in keys}
        o = np.argsort(s["case"], kind="stable")
        subs[tag] = {kk: v[o] for kk, v in s.items()}
    span = {t: (np.searchsorted(subs[t]["case"], np.arange(D["ncase"]), side="right")
                - np.searchsorted(subs[t]["case"], np.arange(D["ncase"]), side="left")) for t in subs}
    pts = {}
    for t in subs:
        w1 = np.ones(len(subs[t]["case"]))
        f = coef(subs[t], subs[t]["df"], w1, D["ncase"]); b = coef(subs[t], subs[t]["db"], w1, D["ncase"])
        pts[t] = None if (f is None or b is None) else (f, f - b)
    if pts["a"] is None or pts["b"] is None:
        print(f"\n=== {title} === fit failed"); return
    fa, fb, dd = [], [], []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        v = {}
        for t in subs:
            w = np.repeat(cnt, span[t])
            v[t] = coef(subs[t], subs[t]["df"], w, D["ncase"])
        if v["a"] is None or v["b"] is None:
            continue
        fa.append(v["a"]); fb.append(v["b"]); dd.append(v["a"] - v["b"])
    if len(dd) < 50:
        print(f"\n=== {title} === bootstrap failed"); return
    print(f"\n=== {title} ===")
    for nm, pt, bs_, msk in ((la, pts["a"][0], fa, ma), (lb, pts["b"][0], fb, mb)):
        lo, hi = np.percentile(bs_, [2.5, 97.5])
        print(f"   {nm:34s} forward = {pt:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}  bins={int(msk.sum())}")
    lo, hi = np.percentile(dd, [2.5, 97.5])
    d = pts["a"][0] - pts["b"][0]
    verdict = ("HIGH-tone falls MORE (predicted)" if hi < 0 else
               ("HIGH-tone falls LESS (against prediction)" if lo > 0 else "no difference"))
    print(f"   {'DIFFERENCE (high - low)':34s}           {d:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}]   {verdict}")


def main():
    k = int(os.environ.get("K", "4"))
    HD, AU = load()
    if not AU:
        print("auto_bins.csv not present -- ECG extraction has not produced data yet."); return
    tone = case_tone(HD, AU)
    print(f"cases with an autonomic baseline: {len(tone)}")
    D = build(HD, tone, k)
    if len(D.get("case", [])) < 10000:
        print(f"insufficient joined bins ({len(D.get('case', []))}) -- extraction still in progress."); return
    print(f"k=+/-{k} bins; {len(D['case'])} bins, {D['ncase']} cases; {NBOOT} bootstrap reps")
    print("moderators are measured over EARLY maintenance bins, before the episodes they stratify\n")
    for key, nm in (("brs", "baroreflex sensitivity"), ("rmssd", "RMSSD"), ("lfhf", "LF/HF")):
        v = D[key]; ok = np.isfinite(v)
        if ok.sum() < 20000:
            print(f"=== {nm}: only {int(ok.sum())} bins with a value -- skipped ===")
            continue
        cut = np.percentile(v[ok], [33, 67])
        contrast(D, ok & (v >= cut[1]), ok & (v < cut[0]),
                 f"HIGH {nm} (>= {cut[1]:.3g})", f"LOW {nm} (< {cut[0]:.3g})",
                 f"{nm.upper()} -- predicted: LARGER fall where more tone remains")
        # the discriminating test: does it survive at fixed age and fixed depth?
        age = D["age"]; aok = ok & np.isfinite(age)
        if aok.sum() > 40000:
            amid = np.percentile(age[aok], [33, 67])
            band = aok & (age >= amid[0]) & (age < amid[1])
            if band.sum() > 20000:
                c2 = np.percentile(v[band], [33, 67])
                contrast(D, band & (v >= c2[1]), band & (v < c2[0]),
                         f"HIGH {nm}, middle age band", f"LOW {nm}, middle age band",
                         f"{nm.upper()} WITHIN a fixed age band -- does tone beat its own proxy?")
        ce = D["dz"]; cmid = np.percentile(ce, [33, 67])
        band = ok & (ce >= cmid[0]) & (ce < cmid[1])
        if band.sum() > 20000:
            c2 = np.percentile(v[band], [33, 67])
            contrast(D, band & (v >= c2[1]), band & (v < c2[0]),
                     f"HIGH {nm}, middle Ce band", f"LOW {nm}, middle Ce band",
                     f"{nm.upper()} WITHIN a fixed depth band -- does tone beat dose?")


if __name__ == "__main__":
    sys.exit(main())
