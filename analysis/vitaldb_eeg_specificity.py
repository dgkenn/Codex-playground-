#!/usr/bin/env python3
"""IS IT SUPPRESSION, OR IS IT JUST ANAESTHETIC DEPTH? -- the specificity test, in the Brown-lab frame.

This is the make-or-break analysis for the whole claim, and it is also the one that puts the finding in the
framework Emery Brown's group actually uses. Brown/Purdon's central point about the anaesthetic EEG is that it is
not a one-dimensional "depth" axis: propofol produces a SPECIFIC set of oscillatory signatures -- frontal alpha
(~8-12 Hz, thalamocortical) and slow-delta (<1-4 Hz, cortical) -- and burst suppression is a distinct, deeper
dynamical state, not merely "more slowing".

If the pressure fall follows GENERAL SLOWING just as well as it follows SUPPRESSION, then the finding is about
anaesthetic depth, the EEG adds nothing beyond the dose, and the specific claim collapses. If the lead is carried
by SUPPRESSION and not by slow or alpha power at matched dose and matched pressure, then a specific cortical
dynamical state -- not depth in general -- marks the impending haemodynamic change. That is a mechanism claim
rather than a monitoring claim, and it is the distinction Brown's framework is built on.

Exposures, each run through the IDENTICAL estimator so they are directly comparable:
    bs        any burst suppression in the bin vs none          (the distinct dynamical state)
    slow      slow-delta power above the patient's own median   (cortical slow oscillation)
    alpha     frontal alpha power above the patient's own median (thalamocortical alpha, the propofol signature)
    emg       frontal EMG above the cohort median               (negative control: arousal, not depth)

Continuous exposures are dichotomised at each patient's OWN median so that "high slow power" means high FOR THAT
PATIENT. Absolute spectral power differs by an order of magnitude across patients (skull, electrode impedance,
montage), so a cohort-wide threshold would mostly encode who the patient is rather than what their brain is doing,
and the case fixed effects would then absorb the exposure itself.

Estimator, identical to `analysis/vitaldb_mechanism_decomposition.py`:
    outcome    signed change in MAP from t to t+k (forward) and t to t-k (backward)
    model      outcome ~ exposure + MAP(t) + Ce(t) + dCe + pre-trend, CASE FIXED EFFECTS
    pre-trend  MAP(t-k) - MAP(t-2k), i.e. BEFORE the backward window, so it is collinear with neither outcome
    inference  CASE-level cluster bootstrap; the forward-minus-backward contrast is the reported statistic

A second block adjusts each exposure for the OTHER TWO simultaneously. That is the sharp version: does suppression
still lead the pressure fall once slow and alpha power at the same instant are held fixed? Depth-related power and
suppression are strongly correlated, so this is a demanding test and the coefficient is expected to shrink; what
matters is whether it survives with its sign and its interval intact.

PRE-TREND WINDOW -- CORRECTED after adversarial review, and this changed a reported number.
The pre-trend was previously MAP(t-k) - MAP(t-2k). That is not exactly collinear with the backward outcome
MAP(t-k) - MAP(t), but it SHARES THE ENDPOINT MAP(t-k) with it. Measured on the real within-case demeaned data the
partial correlation was 0.528 against the backward outcome and 0.023 against the forward one. The consequence was
one-sided: adding it shrank the BACKWARD coefficient from -0.412 to -0.202 while leaving the FORWARD coefficient
untouched at -1.278, inflating the forward-minus-backward statistic from -0.870 to -1.076, i.e. by about 24 %,
entirely through the backward side. The pre-trend is now measured over [t-3k, t-2k], which shares NO endpoint with
either outcome (raw correlation with the backward outcome falls from 0.389 to 0.035). Roughly half of the apparent
benefit of pre-trend adjustment was this artefact; the corrected asymmetry is near -0.97 rather than -1.08. The
forward coefficient is unaffected by any of this.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)

# --- physiologic range filter for arterial pressure -------------------------------------------------
# The propofol pipeline never range-filtered MAP. bridge_bins.csv contains 4.27 % of values <= 0
# (minimum -78 mmHg -- negative arterial pressure is impossible) and 0.62 % above 200 mmHg: transducer
# zeroing, line flushes and disconnections. Left unfiltered they produced dMAP values up to +/-390 mmHg
# and inflated every forward-minus-backward statistic about three-fold (-0.33 -> -0.97 mmHg). Filtering
# implausible VALUES is the principled fix; winsorising the outcome would only mask them.
# The filtered estimate is stable across windows [30,150], [25,160], [20,180] and [40,140]
# (asymmetry -0.340, -0.330, -0.323, -0.333), so the exact threshold is not doing the work.
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
    """Parse a MAP field, returning NaN unless it lies in the physiologic window."""
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")



def load():
    """(caseid, bin_t) -> [bs, MAP, Ce, alpha_db, slow_db, EMG]."""
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]),
                              _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan,
                              float(d["alpha_db"]) if d["alpha_db"] else np.nan,
                              float(d["slow_db"]) if d["slow_db"] else np.nan,
                              np.nan]
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
                HD[cid][t][5] = float(d["emg"]) if d["emg"] else np.nan
            except Exception:
                pass
    return HD


def per_case_medians(HD):
    """Median alpha and slow power within each case's maintenance period."""
    med = {}
    for c, bd in HD.items():
        ts = [t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0]
        a = [bd[t][3] for t in ts if bd[t][3] == bd[t][3]]
        s = [bd[t][4] for t in ts if bd[t][4] == bd[t][4]]
        med[c] = (float(np.median(a)) if len(a) >= 20 else np.nan,
                  float(np.median(s)) if len(s) >= 20 else np.nan)
    return med


def build(HD, med, k, emg_cut):
    """One row set carrying ALL exposures, so every model runs on identical rows."""
    cols = defaultdict(list)
    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        amed, smed = med.get(c, (np.nan, np.nan))
        if not (amed == amed and smed == smed):
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            bs, m, dose, al, sl, emg = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and mb3 == mb3 and dose == dose and doseb == doseb):
                continue
            if not (al == al and sl == sl and emg == emg):
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c])
            cols["bs"].append(1.0 if bs > 0 else 0.0)
            cols["alpha"].append(1.0 if al > amed else 0.0)
            cols["slow"].append(1.0 if sl > smed else 0.0)
            cols["emg"].append(1.0 if emg > emg_cut else 0.0)
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb2 - mb3)   # [t-3k, t-2k]: shares NO endpoint with db (see docstring)
            cols["df"].append(mf - m); cols["db"].append(mb - m)
    if not cols:
        return None
    D = {k2: np.asarray(v, np.float64) for k2, v in cols.items()}
    D["case"] = D["case"].astype(np.int32)
    D["ncase"] = len(ci)
    return D


def demean(mat, case, ncase, w):
    sw = np.bincount(case, weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    out = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(case, weights=w * mat[:, j], minlength=ncase) / sw
        out[:, j] = mat[:, j] - mu[case]
    return out


def coef(D, expo_names, dy, w):
    mat = np.column_stack([D[n] for n in expo_names] + [D["m0"], D["dz"], D["dce"], D["pre"], dy])
    dm = demean(mat, D["case"], D["ncase"], w)
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        b = np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)
    except np.linalg.LinAlgError:
        return None
    return b[:len(expo_names)]


def run(D, expo_names, label, span):
    w1 = np.ones(len(D["case"]))
    pf = coef(D, expo_names, D["df"], w1)
    pb = coef(D, expo_names, D["db"], w1)
    if pf is None or pb is None:
        print(f"   {label}: fit failed")
        return
    boots = [[] for _ in expo_names]
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        a = coef(D, expo_names, D["df"], w); b = coef(D, expo_names, D["db"], w)
        if a is None or b is None:
            continue
        for j in range(len(expo_names)):
            boots[j].append(a[j] - b[j])
    print(f"   {label}")
    for j, nm in enumerate(expo_names):
        if len(boots[j]) < 50:
            print(f"      {nm:8s} bootstrap failed")
            continue
        lo, hi = np.percentile(boots[j], [2.5, 97.5])
        tag = "*" if (lo > 0 or hi < 0) else "ns"
        print(f"      {nm:8s} fwd-bwd = {pf[j]-pb[j]:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] {tag}")


def main():
    k = int(os.environ.get("K", "4"))
    HD = load()
    med = per_case_medians(HD)
    vals = [bd[t][5] for c, bd in HD.items() for t in bd if bd[t][5] == bd[t][5]]
    emg_cut = float(np.median(vals)) if len(vals) > 1000 else np.nan
    D = build(HD, med, k, emg_cut)
    if D is None:
        print("no rows"); return
    order = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][order]
    starts = np.searchsorted(D["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    print(f"k=+/-{k} bins (+/-{30*k}s); {len(D['case'])} bins, {D['ncase']} cases; "
          f"{NBOOT} case-level bootstrap reps")
    print("exposures dichotomised at each patient's OWN median (alpha, slow) or the cohort median (EMG)")
    print("statistic = forward minus backward change in MAP; negative = the marker LEADS a pressure fall\n")
    print("=== BLOCK 1: each exposure alone ===")
    for nm in ("bs", "slow", "alpha", "emg"):
        run(D, [nm], f"{nm} alone", span)
    print("\n=== BLOCK 2: suppression adjusted for simultaneous slow and alpha power ===")
    run(D, ["bs", "slow", "alpha"], "bs + slow + alpha, mutually adjusted", span)
    print("\n=== BLOCK 3: all four together ===")
    run(D, ["bs", "slow", "alpha", "emg"], "bs + slow + alpha + emg", span)
    print("\nREADING IT: if `slow` carries a lead as large as `bs`, the finding is about anaesthetic DEPTH and the")
    print("suppression-specific claim fails. If `bs` survives BLOCK 2 with its sign and interval intact while slow")
    print("and alpha do not, a specific cortical dynamical state -- not depth -- marks the impending fall.")


if __name__ == "__main__":
    sys.exit(main())
