#!/usr/bin/env python3
"""Does burst suppression precede a fall in HEART-RATE VARIABILITY? -- the remaining edge of the mechanism.

WHERE THE MECHANISM STANDS. Established, all after correcting the arterial-pressure artefacts:
  * suppression precedes a fall in mean arterial pressure (asymmetry -0.332 mmHg), and slow-delta (+0.023, ns)
    and frontal alpha (+0.004, ns) carry NO lead -- the effect is specific to the suppressed state, not to depth;
  * the fall is VASODILATORY: measured cardiac output RISES (+0.273 %) while resistance falls;
  * it scales monotonically with cumulative dwell time (-0.14 -> -0.85 mmHg across occupancy bands);
  * the baroreflex does NOT change during suppression (interaction +0.0001 [-0.0044, +0.0045]) -- but the reflex
    is already at the floor under anaesthesia (-0.0115 bpm/mmHg, of order 1 % of awake gain), so the vasodilation
    is undefended in EVERY bin. That is a property of general anaesthesia, not of suppression.

WHAT IS STILL UNEXPLAINED: why suppression produces the vasodilation in the first place. The candidate is a
withdrawal of central sympathetic outflow. Outflow cannot be measured directly without microneurography, but
heart-rate variability is its standard non-invasive proxy.

THE TEST, in the cohort where the exposure is well balanced. I-CARE was tried first because it has no anaesthetic
and therefore no dose confound, but 95 % of its bins are suppressed, leaving almost no unexposed reference; its
asymmetry was -3.16 % [-7.57, +2.44], an underpowered null rather than evidence against. Here the balance is
favourable (suppression in roughly 40 % of bins) at the cost of reintroducing the drug as a common cause -- which
is why dose and its rate of change are adjusted, exactly as in every other model in this suite.

    exposure   any burst suppression in bin t
    outcome    change in log RMSSD from t to t+k, with the backward change as the control
               RMSSD indexes beat-to-beat variability. Log because it is positive and right-skewed.
               Secondary outcomes: log SDNN (overall variability) and log LF/HF, the latter reported only as
               supporting -- LF/HF as a "sympathovagal balance" index is contested, and a 30 s bin spans only
               1-4 LF cycles, which is too short to take seriously on its own.
    model      outcome ~ suppression + logRMSSD(t) + MAP(t) + dose + dCe + pre-trend + CASE FIXED EFFECTS
    inference  CASE-level cluster bootstrap

    PREDICTION, registered before running: suppression precedes a FALL in RMSSD, with the forward fall exceeding
    the backward one. FALSIFICATION: a null or reversed asymmetry means the sympathetic-withdrawal account of the
    vasodilation is unsupported, and the mechanism would stand as "suppression is followed by vasodilation" with
    the route left open.

NEGATIVE CONTROL. Frontal EMG through the identical model. EMG marks arousal and movement, which raise sympathetic
tone, so it should if anything precede a RISE. It has shown its own opposite-signed physiology throughout this
project, and a suppression result is only credible if EMG does not mimic it.

LIMITS. RMSSD over a 30 s bin rests on roughly 20-40 accepted RR intervals, so each estimate is noisy. Bins with
fewer than 15 accepted intervals are dropped, and that exclusion is not random -- it is commoner when rhythm is
irregular. Anaesthesia depresses HRV globally, so this compares two already-depressed states within a patient.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
MIN_RR = int(os.environ.get("MIN_RR", "15"))
rng = np.random.default_rng(20260725)
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


def _pos_log(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return float(np.log(v)) if (v == v and v > 0) else float("nan")


def load():
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
    p = f"{DATA}/auto_bins.csv"
    if not os.path.exists(p):
        return HD
    seen = set()
    with open(p) as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                    continue
                seen.add((cid, t))
                nrr = float(d["nrr"]) if d["nrr"] not in ("", None) else 0.0
                if nrr < MIN_RR:
                    continue
                HD[cid][t][3] = _pos_log(d.get("rmssd"))
                HD[cid][t][4] = _pos_log(d.get("sdnn"))
                HD[cid][t][5] = _pos_log(d.get("lfhf"))
            except Exception:
                pass
    return HD


IDX = {"rmssd": 3, "sdnn": 4, "lfhf": 5}


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


def run(HD, k, which, exposure, label, emg_cut):
    D = build(HD, k, which, exposure, emg_cut)
    n = len(D.get("x", []))
    if n < 5000:
        print(f"   {label:44s} insufficient ({n} bins)")
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
        print(f"   {label:44s} fit failed"); return
    bd = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        a = coef(D, D["df"], w); b = coef(D, D["db"], w)
        if a is not None and b is not None:
            bd.append(a - b)
    if len(bd) < 50:
        print(f"   {label:44s} bootstrap failed"); return
    lo, hi = np.percentile(bd, [2.5, 97.5])
    d = pf - pb
    tag = "*" if (lo > 0 or hi < 0) else "ns"
    print(f"   {label:44s} fwd={100*pf:+7.2f}% bwd={100*pb:+7.2f}%  fwd-bwd={100*d:+7.2f}% "
          f"[{100*lo:+7.2f},{100*hi:+7.2f}] {tag}   n={n}, cases={D['ncase']}")


def main():
    k = int(os.environ.get("K", "2"))
    HD = load()
    vals = [bd[t][6] for c, bd in HD.items() for t in bd if bd[t][6] == bd[t][6]]
    emg_cut = float(np.median(vals)) if len(vals) > 1000 else np.nan
    print(f"k=+/-{k} bins (+/-{30*k}s); case fixed effects; {NBOOT} case-level bootstrap reps")
    print(f"outcome = % change in the log HRV measure; negative = variability FELL\n")
    print("=== BURST SUPPRESSION (predicted: forward fall exceeding backward) ===")
    for w in ("rmssd", "sdnn", "lfhf"):
        run(HD, k, w, "bs", f"{w} after suppression", emg_cut)
    print("\n=== frontal EMG -- NEGATIVE CONTROL ===")
    for w in ("rmssd", "sdnn", "lfhf"):
        run(HD, k, w, "emg", f"{w} after high EMG", emg_cut)
    print("\n   LF/HF is supporting only: the index is contested and a 30 s bin spans 1-4 LF cycles.")


if __name__ == "__main__":
    sys.exit(main())
