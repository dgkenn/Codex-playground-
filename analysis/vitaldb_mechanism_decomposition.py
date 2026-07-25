#!/usr/bin/env python3
"""MECHANISM: WHICH haemodynamic term falls after burst suppression?

The within-case result says that at a FIXED arterial pressure and a FIXED propofol concentration, a suppressed bin
is followed by a mean-pressure fall of about 1.2 mmHg at 60-120 s, while being preceded by none. That is an
ordering, not a mechanism. This file asks what actually moves, by decomposing the pressure into its physiological
factors and running each through the IDENTICAL estimator.

    MAP  =  CO x SVR  =  (SV x HR) x SVR
    pulse pressure (PP) tracks stroke volume; HR is measured; so  SVR  proportional to  MAP / (PP x HR).

Three mechanisms, three distinguishable signatures:

  VASODILATION / SYMPATHOLYSIS   SVR proxy falls.  PP preserved or RISING (a dilated arterial tree with unchanged
                                 stroke volume widens the pulse). HR unchanged or rising (baroreflex) .
                                 -> This is the signature predicted if burst suppression indexes a withdrawal of
                                    central sympathetic outflow, which is the mechanism Brown-lab work on
                                    brainstem arousal circuitry would predict.
  CARDIAC / REDUCED STROKE VOLUME  PP falls. SVR proxy unchanged or rising (compensatory vasoconstriction).
  CHRONOTROPIC                   HR falls and carries the CO fall; PP may rise (longer filling).

Design is deliberately identical to `analysis/vitaldb_within_case_delta.py` so the outcomes are comparable:
  * outcome  = signed change in the quantity from t to t+k (forward) and t to t-k (backward)
  * model    = outcome ~ exposure + MAP(t) + dose(t) + dCe + pre-trend, with CASE FIXED EFFECTS
               (dCe and the pre-trend are carried because they were the two surviving confounds; see
                `analysis/vitaldb_pretrend_dosekinetics.py`)
  * rows     = bins having BOTH a forward and a backward neighbour, so direction is the only thing that differs
  * inference= CASE-level cluster bootstrap; the forward-minus-backward contrast is the reported statistic
  * control  = frontal EMG through the identical pipeline

SVR is analysed on the LOG scale: it is a ratio of positive quantities, so a log change is the symmetric,
scale-free quantity, and additive models on a raw ratio are badly behaved.

HONEST LIMITS, to be carried into any write-up:
  * PP is a stroke-volume SURROGATE, not stroke volume. Arterial stiffness, line damping and -- critically --
    vasopressor titration decouple PP from SV, and pressors are given preferentially to sicker patients. A PP
    result is suggestive, never decisive.
  * MAP/(PP x HR) is a SVR PROXY, not a measured resistance. It shares PP's weaknesses and adds its own: MAP
    appears in the numerator, so any error in MAP propagates.
  * Because MAP is the numerator of the SVR proxy, a fall in MAP mechanically lowers the proxy unless PP x HR
    falls at least as much. The informative comparison is therefore ACROSS the four outcomes -- which of PP, HR
    and the proxy moves, and by how much relative to MAP -- not the proxy's sign on its own.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)


def load():
    """(caseid, bin_t) -> [bs, MAP, Ce, EMG, PP, HR] on the intersection of the EEG and arterial streams."""
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
                              np.nan, np.nan, np.nan]
            except Exception:
                pass
    seen = set()
    with open(f"{DATA}/bis_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                    continue
                seen.add((cid, t))
                HD[cid][t][3] = float(d["emg"]) if d["emg"] else np.nan
            except Exception:
                pass
    seen = set()
    with open(f"{DATA}/pp_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                    continue
                seen.add((cid, t))
                pp = float(d["pp"]) if d["pp"] else np.nan
                hr = float(d["hr"]) if d["hr"] else np.nan
                if not (10 < pp < 120):
                    pp = np.nan
                if not (20 < hr < 200):
                    hr = np.nan
                HD[cid][t][4] = pp; HD[cid][t][5] = hr
            except Exception:
                pass
    return HD


def value(rec, which):
    bs, m, ce, emg, pp, hr = rec
    if which == "map":
        return m
    if which == "pp":
        return pp
    if which == "hr":
        return hr
    if which == "logsvr":
        if not (m == m and pp == pp and hr == hr) or pp <= 0 or hr <= 0 or m <= 0:
            return np.nan
        return float(np.log(m / (pp * hr)))
    return np.nan


def build(HD, k, exposure, which, emg_cut):
    case = []; e = []; m0 = []; dz = []; dce = []; pre = []; df = []; db = []
    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k
            if tf not in bd or tb not in bd:
                continue
            rec = bd[t]
            bs, m, dose, emg = rec[0], rec[1], rec[2], rec[3]
            v0 = value(rec, which); vf = value(bd[tf], which); vb = value(bd[tb], which)
            mb = bd[tb][1]; doseb = bd[tb][2]
            if not (v0 == v0 and vf == vf and vb == vb):
                continue
            if not (m == m and mb == mb and dose == dose and doseb == doseb):
                continue
            if exposure == "bs":
                x = 1.0 if bs > 0 else 0.0
            else:
                if emg != emg or emg_cut is None:
                    continue
                x = 1.0 if emg > emg_cut else 0.0
            if c not in ci:
                ci[c] = len(ci)
            case.append(ci[c]); e.append(x); m0.append(m); dz.append(dose)
            dce.append(dose - doseb); pre.append(m - mb)
            df.append(vf - v0); db.append(vb - v0)
    if not case:
        return None
    return dict(case=np.array(case, np.int32), e=np.array(e), m0=np.array(m0), dz=np.array(dz),
                dce=np.array(dce), pre=np.array(pre), df=np.array(df), db=np.array(db), ncase=len(ci))


def demean(cols, case, ncase, w):
    sw = np.bincount(case, weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    return [v - (np.bincount(case, weights=w * v, minlength=ncase) / sw)[case] for v in cols]


def coef(D, dy, w):
    cols = [D["e"], D["m0"], D["dz"], D["dce"], D["pre"], dy]
    dm = demean(cols, D["case"], D["ncase"], w)
    X = np.column_stack(dm[:-1]); y = dm[-1]
    try:
        return np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[0]
    except np.linalg.LinAlgError:
        return None


def run(HD, k, exposure, which, unit, emg_cut, scale=1.0):
    D = build(HD, k, exposure, which, emg_cut)
    if D is None or len(D["case"]) < 5000:
        print(f"   {which:8s} insufficient")
        return
    order = np.argsort(D["case"], kind="stable")
    for key in ("case", "e", "m0", "dz", "dce", "pre", "df", "db"):
        D[key] = D[key][order]
    starts = np.searchsorted(D["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    w1 = np.ones(len(D["case"]))
    pf = coef(D, D["df"], w1); pb = coef(D, D["db"], w1)
    if pf is None or pb is None:
        print(f"   {which:8s} fit failed")
        return
    diffs = []; fwd = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        a = coef(D, D["df"], w); b = coef(D, D["db"], w)
        if a is not None and b is not None:
            diffs.append((a - b) * scale); fwd.append(a * scale)
    if len(diffs) < 50:
        print(f"   {which:8s} bootstrap failed")
        return
    fl, fh = np.percentile(fwd, [2.5, 97.5])
    dl, dh = np.percentile(diffs, [2.5, 97.5])
    tag = "*" if (dl > 0 or dh < 0) else "ns"
    print(f"   {which:8s} fwd={pf*scale:+8.3f} [{fl:+7.3f},{fh:+7.3f}] {unit:9s} | "
          f"fwd-bwd={(pf-pb)*scale:+8.3f} [{dl:+7.3f},{dh:+7.3f}] {tag}   n={len(D['case'])}, cases={D['ncase']}")


def main():
    k = int(os.environ.get("K", "4"))
    HD = load()
    vals = [bd[t][3] for c, bd in HD.items() for t in bd if bd[t][3] == bd[t][3]]
    emg_cut = float(np.median(vals)) if len(vals) > 1000 else None
    print(f"k=+/-{k} bins (+/-{30*k}s); case fixed effects + MAP(t) + dose(t) + dCe + pre-trend; "
          f"{NBOOT} case-level bootstrap reps")
    print("exposure = ANY burst suppression in the bin vs none; statistic = forward minus backward change\n")
    for expo, lab in (("bs", "BURST SUPPRESSION"), ("emg", "frontal EMG -- NEGATIVE CONTROL")):
        print(f"=== {lab} ===")
        run(HD, k, expo, "map", "mmHg", emg_cut)
        run(HD, k, expo, "pp", "mmHg", emg_cut)
        run(HD, k, expo, "hr", "bpm", emg_cut)
        run(HD, k, expo, "logsvr", "% (x100)", emg_cut, scale=100.0)
        print()
    print("READING THE TABLE:")
    print("  vasodilation/sympatholysis -> MAP falls, SVR proxy falls, PP preserved or rising, HR not falling")
    print("  reduced stroke volume      -> MAP falls, PP falls, SVR proxy flat or rising")
    print("  chronotropic               -> MAP falls, HR falls carrying it")
    print("  (the SVR proxy has MAP in its numerator -- judge it against the OTHER columns, not on its own sign)")


if __name__ == "__main__":
    sys.exit(main())
