#!/usr/bin/env python3
"""MAYER WAVES — the one available instrument that indexes VASOMOTOR sympathetic outflow.

WHY THIS AND NOT HRV. The mechanism's remaining gap is the step from cortical suppression to vasodilation. The
candidate is withdrawal of central sympathetic outflow, which is established for propofol at induction by
microneurography (muscle sympathetic nerve activity falls 76 +/- 5 %) but has NOT been measured here. Two attempts
already failed for instrument reasons rather than physiological ones:

  * heart-rate variability showed no asymmetry (RMSSD +0.23 % [-0.90, +1.42]) -- but RMSSD is predominantly VAGAL
    and indexes CARDIAC autonomic control, not the vasomotor limb that sets systemic vascular resistance;
  * sequence-method baroreflex sensitivity was null but rested on 5,839 bins from 145 cases -- underpowered, and
    an earlier claim built on a 30-second-averaged heart-rate proxy was RETRACTED because the arterial baroreflex
    acts over one to three heartbeats.

Mayer waves are the right instrument. The ~0.1 Hz oscillation in arterial pressure arises from the sympathetic
vasomotor control loop itself, and its power is a recognised non-invasive index of vasomotor sympathetic activity.
It is a property of the PRESSURE signal, so it reports on the efferent limb that actually sets resistance.

    exposure   any burst suppression in bin t
    outcome    change in log LF power of the beat-to-beat systolic series (0.04-0.15 Hz, the Mayer band)
               from t to t+k, with the backward change t to t-k as the control
               secondary: lf_norm = LF/(LF+HF), which controls for overall pressure variability, and log HF
               (0.15-0.40 Hz, respiratory) as a within-signal comparator that should NOT track sympathetic tone
    model      outcome ~ suppression + logLF(t) + MAP(t) + dose + dCe + pre-trend + CASE FIXED EFFECTS
    inference  CASE-level cluster bootstrap

    PREDICTION, registered before running: suppression precedes a FALL in Mayer-band power, with the forward fall
    exceeding the backward one.
    FALSIFICATION: a null or reversed asymmetry means suppression produces vasodilation by a route that is not
    vasomotor sympathetic withdrawal -- which would point at direct vascular or metabolic effects and would make
    this a different paper. Either outcome is reportable; the mechanism is currently INFERRED FROM PRIOR
    PHARMACOLOGY rather than demonstrated in these data, and this test is what would change that.

WINDOW LENGTH IS A REAL CONFOUND AND IS HANDLED BY DESIGN. A 30 s window spans only ~3 cycles at 0.1 Hz, which is
short for a spectral estimate. The extraction therefore produced BOTH a 30 s version (temporal resolution matched
to every other analysis here) and a 120 s version centred on the same bin (far better frequency resolution, worse
temporal resolution). Both are analysed. If the answer depends on the window, it is a spectral-estimation artefact
rather than physiology, and that must be visible rather than hidden by picking one.

NEGATIVE CONTROL: frontal EMG through the identical model, as everywhere else in this project.

LIMITS. Mayer wave power is an INDEX of vasomotor outflow, not a measurement of it; it also depends on vascular
compliance and on the gain of the loop, both of which anaesthesia alters. Vasopressor infusions perturb the loop
directly. And the beat detector required two fixes during extraction (an 8 Hz low-pass before differentiation to
stop firing on quantisation noise, and a resync safeguard after line-flush artefacts poisoned the running-median
filter), so its output is trusted only because it was validated against the independently recorded systolic track.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
MIN_BEAT = int(os.environ.get("MIN_BEAT", "15"))
rng = np.random.default_rng(20260725)
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


def _plog(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return float(np.log(v)) if (v == v and v > 0) else float("nan")


def _plain(raw):
    try:
        return float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")


def load(mayer_file):
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]), _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan,
                              np.nan, np.nan, np.nan, np.nan]
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
                HD[cid][t][6] = float(d["emg"]) if d["emg"] else np.nan
            except Exception:
                pass
    p = f"{DATA}/{mayer_file}"
    if not os.path.exists(p):
        return None
    seen = set()
    with open(p) as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                    continue
                seen.add((cid, t))
                nb = _plain(d.get("nbeat"))
                if not (nb == nb and nb >= MIN_BEAT):
                    continue
                HD[cid][t][3] = _plog(d.get("lf_sbp"))
                HD[cid][t][4] = _plain(d.get("lf_norm"))
                HD[cid][t][5] = _plog(d.get("hf_sbp"))
            except Exception:
                pass
    return HD


IDX = {"lf": 3, "lfnorm": 4, "hf": 5}


def build(HD, k, which, exposure, emg_cut):
    col = IDX[which]
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd:
                continue
            bs, m, dose = bd[t][0], bd[t][1], bd[t][2]
            v0 = bd[t][col]; vf = bd[tf][col]; vb = bd[tb][col]; vb2 = bd[tb2][col]
            doseb = bd[tb][2]
            if not (v0 == v0 and vf == vf and vb == vb and vb2 == vb2):
                continue
            if not (m == m and dose == dose and doseb == doseb):
                continue
            if exposure == "bs":
                if bs != bs:
                    continue
                x = 1.0 if bs > 0 else 0.0
            else:
                e = bd[t][6]
                if e != e or emg_cut != emg_cut:
                    continue
                x = 1.0 if e > emg_cut else 0.0
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["x"].append(x)
            cols["v0"].append(v0); cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(vb - vb2)
            cols["df"].append(vf - v0); cols["db"].append(vb - v0)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def coef(D, dy, w):
    mat = np.column_stack([D["x"], D["v0"], D["m0"], D["dz"], D["dce"], D["pre"], dy])
    sw = np.bincount(D["case"], weights=w, minlength=D["ncase"])
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(D["case"], weights=w * mat[:, j], minlength=D["ncase"]) / sw
        dm[:, j] = mat[:, j] - mu[D["case"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        return float(np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[0])
    except np.linalg.LinAlgError:
        return None


def run(HD, k, which, exposure, label, emg_cut, pct=True):
    D = build(HD, k, which, exposure, emg_cut)
    n = len(D.get("x", []))
    if n < 4000:
        print(f"   {label:46s} insufficient ({n} bins)")
        return
    o = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][o]
    span = (np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
            - np.searchsorted(D["case"], np.arange(D["ncase"]), side="left"))
    w1 = np.ones(n)
    pf = coef(D, D["df"], w1); pb = coef(D, D["db"], w1)
    if pf is None or pb is None:
        print(f"   {label:46s} fit failed"); return
    bd = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        a = coef(D, D["df"], w); b = coef(D, D["db"], w)
        if a is not None and b is not None:
            bd.append(a - b)
    if len(bd) < 50:
        print(f"   {label:46s} bootstrap failed"); return
    lo, hi = np.percentile(bd, [2.5, 97.5])
    s = 100.0 if pct else 1.0
    u = "%" if pct else "  "
    tag = "*" if (lo > 0 or hi < 0) else "ns"
    print(f"   {label:46s} fwd={s*pf:+7.2f}{u} bwd={s*pb:+7.2f}{u}  fwd-bwd={s*(pf-pb):+7.2f}{u} "
          f"[{s*lo:+7.2f},{s*hi:+7.2f}] {tag}   n={n}, cases={D['ncase']}")


def main():
    k = int(os.environ.get("K", "2"))
    for fn, wl in (("mayer_bins.csv", "30 s window"), ("mayer_bins120.csv", "120 s window")):
        HD = load(fn)
        if HD is None:
            print(f"{fn} not present"); continue
        vals = [bd[t][6] for c, bd in HD.items() for t in bd if bd[t][6] == bd[t][6]]
        emg_cut = float(np.median(vals)) if len(vals) > 1000 else np.nan
        print(f"\n================ {wl}  ({fn}) ================")
        print(f"k=+/-{k} bins; case fixed effects; {NBOOT} case-level bootstrap reps; "
              f"bins need >= {MIN_BEAT} accepted beats")
        print("   PREDICTED: suppression precedes a FALL in Mayer-band (LF) power\n")
        run(HD, k, "lf", "bs", "LF power (Mayer band) after suppression", emg_cut)
        run(HD, k, "lfnorm", "bs", "LF normalised = LF/(LF+HF)", emg_cut, pct=False)
        run(HD, k, "hf", "bs", "HF power (respiratory) -- within-signal comparator", emg_cut)
        print("   -- negative control --")
        run(HD, k, "lf", "emg", "LF power after high frontal EMG", emg_cut)
    print("\n   If LF falls after suppression while HF does not, that is vasomotor sympathetic withdrawal and")
    print("   it closes the mechanism with our own measurement. If LF is null, the vasodilation runs by some")
    print("   other route and the sympathetic step stays INFERRED from prior pharmacology, not demonstrated.")
    print("   If the two window lengths disagree, the result is a spectral-estimation artefact, not physiology.")


if __name__ == "__main__":
    sys.exit(main())
