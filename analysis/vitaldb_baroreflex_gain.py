#!/usr/bin/env python3
"""DOES BURST SUPPRESSION IMPAIR THE BAROREFLEX? — the missing link in the mechanism.

WHAT IS ESTABLISHED, after correcting the artefacts. Within the same patient, at the same arterial pressure and
the same propofol concentration, burst suppression is followed by a fall in mean arterial pressure that is not
preceded by one (asymmetry -0.332 mmHg), the fall occurs by VASODILATION rather than pump failure (measured
cardiac output RISES +0.27 % while systemic vascular resistance falls), it scales monotonically with cumulative
dwell time in the suppressed state (-0.14 -> -0.85 mmHg across occupancy bands), and it is SPECIFIC to suppression:
slow-delta power (+0.023, ns) and frontal alpha (+0.004, ns) carry no lead at all.

WHAT IS MISSING. Vasodilation alone should not lower pressure much, because an intact baroreflex opposes it --
falling pressure unloads the arterial baroreceptors, which raises sympathetic outflow and heart rate and restores
tone. For a vasodilatory stimulus to actually MOVE the pressure, the reflex that defends pressure must itself be
attenuated. So the mechanism predicts something specific and testable: burst suppression should reduce BAROREFLEX
GAIN.

There is already a hint in the data: heart rate rises only +0.124 bpm after suppression despite a measurable
pressure fall. That is a small response to a real stimulus, but "small" is not a test without a comparison.

THE TEST. Baroreflex gain is the coupling between a pressure change and the heart-rate response it evokes:

        dHR(t+k -> t+2k)  ~  beta * dMAP(t -> t+k)     with   beta < 0 for an intact reflex
                                                       (pressure falls -> heart rate rises)

Estimate that coupling separately for bins that are burst-suppressed and bins that are not, WITHIN the same
patient, and test the difference. The interaction coefficient IS the change in baroreflex gain during suppression.

        dHR  ~  dMAP  +  SUPPRESSED  +  dMAP x SUPPRESSED  +  MAP(t) + dose + dCe + CASE FIXED EFFECTS

    PREDICTION, registered before running: the interaction is POSITIVE -- i.e. the (negative) baroreflex slope is
    made LESS negative by suppression, meaning a blunted reflex.

    FALSIFICATION: if the interaction is null or negative, suppression does not impair the baroreflex, and the
    "vasodilation goes undefended" account fails. The vasodilation itself would remain, but the reason it moves
    pressure would be unexplained.

NEGATIVE CONTROL. The identical interaction is estimated for frontal EMG. EMG marks arousal, which should if
anything be associated with a MORE responsive reflex, and certainly should not mimic suppression. Given that EMG
has repeatedly shown its own opposite-signed physiology in this project, its interaction is reported alongside and
a suppression effect is only credible if it is not matched by EMG.

TIMING. The heart-rate response is measured over the window AFTER the pressure change, not the same window, so the
reflex has somewhere to act and the regression is not fitting a contemporaneous identity. The baroreflex operates
within a few heartbeats, so a 30-120 s response window is generous rather than tight; this measures sustained
reflex tone, not the fast dynamic gain a sequence method would capture.

LIMITS. Heart rate here is the monitor's beat-averaged value per 30 s bin, not beat-to-beat, so this is a coarse
reflex index. Anaesthesia depresses baroreflex gain globally, so the comparison is between two already-depressed
states within the same patient. Vasopressors, opioid boluses and surgical stimulation all perturb both variables;
dose and its rate of change are adjusted but stimulation is not measured.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
rng = np.random.default_rng(20260725)

MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))
HR_LO = float(os.environ.get("HR_LO", "25"))
HR_HI = float(os.environ.get("HR_HI", "180"))


def _rng_ok(raw, lo, hi):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and lo <= v <= hi) else float("nan")


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
                              _rng_ok(d["mbp"], MAP_LO, MAP_HI),
                              float(d["ce"]) if d["ce"] else np.nan,
                              np.nan, np.nan]
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
                HD[cid][t][3] = _rng_ok(d["hr"], HR_LO, HR_HI)
                HD[cid][t][4] = float(d["emg"]) if d["emg"] else np.nan
            except Exception:
                pass
    return HD


def build(HD, k, exposure, emg_cut):
    """dMAP over [t, t+k]; dHR over [t+k, t+2k] -- the response window FOLLOWS the stimulus window."""
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            t1 = t + 30.0 * k; t2 = t + 60.0 * k; tb = t - 30.0 * k
            if t1 not in bd or t2 not in bd or tb not in bd:
                continue
            bs, m, dose, hr, emg = bd[t]
            m1 = bd[t1][1]; hr1 = bd[t1][3]; hr2 = bd[t2][3]; doseb = bd[tb][2]
            if not (m == m and m1 == m1 and hr1 == hr1 and hr2 == hr2 and dose == dose and doseb == doseb):
                continue
            if exposure == "bs":
                if bs != bs:
                    continue
                x = 1.0 if bs > 0 else 0.0
            else:
                if emg != emg or emg_cut != emg_cut:
                    continue
                x = 1.0 if emg > emg_cut else 0.0
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["x"].append(x)
            cols["dmap"].append(m1 - m)
            cols["dhr"].append(hr2 - hr1)
            cols["m0"].append(m); cols["dz"].append(dose); cols["dce"].append(dose - doseb)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def fit(D, w):
    """Returns (baroreflex slope in unexposed bins, interaction = change in slope when exposed)."""
    inter = D["dmap"] * D["x"]
    mat = np.column_stack([D["dmap"], inter, D["x"], D["m0"], D["dz"], D["dce"], D["dhr"]])
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
    return b[0], b[1]


def run(HD, k, exposure, label, emg_cut):
    D = build(HD, k, exposure, emg_cut)
    if len(D.get("case", [])) < 20000:
        print(f"\n=== {label} === insufficient ({len(D.get('case', []))} bins)")
        return
    o = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][o]
    span = (np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
            - np.searchsorted(D["case"], np.arange(D["ncase"]), side="left"))
    w1 = np.ones(len(D["case"]))
    pt = fit(D, w1)
    if pt is None:
        print(f"\n=== {label} === fit failed"); return
    bs_slope, bs_int = [], []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        v = fit(D, np.repeat(cnt, span))
        if v is not None:
            bs_slope.append(v[0]); bs_int.append(v[1])
    if len(bs_int) < 50:
        print(f"\n=== {label} === bootstrap failed"); return
    print(f"\n=== {label} ===   {len(D['case'])} bins, {D['ncase']} cases, "
          f"{int(D['x'].sum())} exposed")
    lo, hi = np.percentile(bs_slope, [2.5, 97.5])
    print(f"   baroreflex slope, UNEXPOSED bins   dHR/dMAP = {pt[0]:+7.4f} bpm/mmHg [{lo:+7.4f},{hi:+7.4f}] "
          f"{'*' if (lo>0 or hi<0) else 'ns'}")
    lo, hi = np.percentile(bs_int, [2.5, 97.5])
    verdict = ("REFLEX BLUNTED (predicted)" if lo > 0 else
               ("reflex ENHANCED (against prediction)" if hi < 0 else "no change in gain"))
    print(f"   INTERACTION (change when exposed)           {pt[1]:+7.4f} bpm/mmHg [{lo:+7.4f},{hi:+7.4f}]   {verdict}")
    print(f"   implied slope while exposed                 {pt[0]+pt[1]:+7.4f} bpm/mmHg")


def main():
    k = int(os.environ.get("K", "2"))
    HD = load()
    vals = [bd[t][4] for c, bd in HD.items() for t in bd if bd[t][4] == bd[t][4]]
    emg_cut = float(np.median(vals)) if len(vals) > 1000 else np.nan
    print(f"k={k} bins ({30*k}s stimulus window, response measured over the FOLLOWING {30*k}s)")
    print(f"MAP filtered to [{MAP_LO},{MAP_HI}], HR to [{HR_LO},{HR_HI}]; {NBOOT} case-level bootstrap reps")
    print("an intact baroreflex gives a NEGATIVE slope: pressure falls -> heart rate rises")
    run(HD, k, "bs", "BURST SUPPRESSION", emg_cut)
    run(HD, k, "emg", "frontal EMG -- NEGATIVE CONTROL", emg_cut)


if __name__ == "__main__":
    sys.exit(main())
