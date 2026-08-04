#!/usr/bin/env python3
"""I-CARE: does cortical suppression precede AUTONOMIC WITHDRAWAL in patients receiving NO ANAESTHETIC?

WHY THIS COHORT MATTERS MORE THAN ANOTHER REPLICATION. Every VitalDB analysis in this project has propofol as a
lurking common cause: the drug produces both burst suppression and vasodilation, so any observed coupling might be
the drug acting twice rather than the brain acting on the circulation. That confound has been attacked with dose
adjustment, dose-kinetics adjustment, within-patient matching at fixed effect-site concentration, and a
stable-infusion subgroup -- but it never fully goes away, because adjustment is not randomisation.

I-CARE removes it BY CONSTRUCTION. These are comatose survivors of cardiac arrest (PhysioNet/BDSP, 7 hospitals).
Burst suppression here is the classic post-anoxic pattern, arising from hypoxic-ischaemic injury rather than from a
drug being infused to produce it. If cortical suppression precedes autonomic withdrawal in a population where
nobody is titrating an anaesthetic, the dose explanation is dead by design rather than by covariate.

WHAT IS AVAILABLE AND WHAT IS NOT. I-CARE carries 19-channel EEG and continuous 500 Hz ECG on one clock, so
heart-rate variability is measurable. Its only other channel is SpO2 -- there is NO blood pressure. So this tests
the FIRST and most confounded edge of the chain (cortex -> autonomic outflow) and cannot test the second
(autonomic -> pressure). That second edge stays in VitalDB.

    exposure   any burst suppression in the 30 s bin (same detector family as the VitalDB work)
    outcome    change in log RMSSD from t to t+k, with the backward change t to t-k as the control
               RMSSD indexes vagally-mediated beat-to-beat variability. Log scale because it is a positive,
               right-skewed quantity whose meaningful changes are proportional.
    model      outcome ~ suppression + logRMSSD(t) + pre-trend + PATIENT-SEGMENT FIXED EFFECTS
               Segments are separate hour-long recordings, often hours or days apart, so the fixed effect is per
               (patient, segment) rather than per patient -- a patient's autonomic state at hour 12 is not a
               sensible control for their state at hour 60.
    inference  PATIENT-level cluster bootstrap (not segment-level: segments within a patient are dependent)

    PREDICTION, registered before running: suppression precedes a FALL in RMSSD, and the forward fall exceeds the
    backward one. FALSIFICATION: a null or reversed asymmetry means cortical suppression does not lead autonomic
    withdrawal once the anaesthetic is removed from the picture, and the mechanism's first edge is unsupported
    outside the drug context.

CONFOUNDERS THAT CANNOT BE REMOVED HERE, and they are serious.
  * Targeted temperature management (33 C in much of this cohort) depresses BOTH the EEG and heart-rate
    variability. It is a per-patient constant within a segment, so the segment fixed effect absorbs its LEVEL, but
    not the timing of rewarming.
  * Sedation IS given to many post-arrest patients and is NOT recorded in this dataset. This weakens but does not
    void the design: sedation depth is not titrated to an EEG target here as it is intraoperatively, and it is
    absent in the many patients whose suppression is driven by injury.
  * Post-arrest autonomic function is deranged and RMSSD is low throughout (median 20.7 ms), so this is a
    comparison between two already-abnormal states.
  * 93 % of bins contain some suppression, so the unexposed reference is a small minority -- the opposite of the
    VitalDB balance, and a real power limitation.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
MIN_RR = int(os.environ.get("MIN_RR", "15"))
rng = np.random.default_rng(20260725)


def load():
    """(patient, segment) -> {bin_t: [bs, logRMSSD]} plus patient-level metadata."""
    SEG = defaultdict(dict); meta = {}
    with open(f"{DATA}/icare_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                pid = d["patient"]; seg = d["segment"]; t = float(d["bin_t"])
                bs = float(d["bs"]) if d["bs"] not in ("", None) else np.nan
                rm = float(d["rmssd"]) if d["rmssd"] not in ("", None) else np.nan
                nrr = float(d["nrr"]) if d["nrr"] not in ("", None) else 0.0
                if nrr < MIN_RR or not (rm == rm and rm > 0):
                    rm = np.nan
                SEG[(pid, seg)][t] = [bs, np.log(rm) if rm == rm else np.nan]
                meta[pid] = (d.get("hospital", ""), d.get("cpc", ""), d.get("ttm", ""))
            except Exception:
                pass
    return SEG, meta


def build(SEG, k):
    cols = defaultdict(list); si = {}; pi = {}
    for (pid, seg), bd in SEG.items():
        ts = sorted(bd)
        if len(ts) < 12:
            continue
        for t in ts:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd:
                continue
            bs, v0 = bd[t]
            vf = bd[tf][1]; vb = bd[tb][1]; vb2 = bd[tb2][1]
            if not (bs == bs and v0 == v0 and vf == vf and vb == vb and vb2 == vb2):
                continue
            key = (pid, seg)
            if key not in si:
                si[key] = len(si)
            if pid not in pi:
                pi[pid] = len(pi)
            cols["seg"].append(si[key]); cols["pat"].append(pi[pid])
            cols["e"].append(1.0 if bs > 0 else 0.0)
            cols["v0"].append(v0)
            cols["pre"].append(vb - vb2)          # trend BEFORE the backward window
            cols["df"].append(vf - v0); cols["db"].append(vb - v0)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["seg"] = D["seg"].astype(np.int32); D["pat"] = D["pat"].astype(np.int32)
    D["nseg"] = len(si); D["npat"] = len(pi)
    return D


def coef(D, dy, w):
    mat = np.column_stack([D["e"], D["v0"], D["pre"], dy])
    sw = np.bincount(D["seg"], weights=w, minlength=D["nseg"])
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(D["seg"], weights=w * mat[:, j], minlength=D["nseg"]) / sw
        dm[:, j] = mat[:, j] - mu[D["seg"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        return float(np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[0])
    except np.linalg.LinAlgError:
        return None


def main():
    k = int(os.environ.get("K", "2"))
    SEG, meta = load()
    D = build(SEG, k)
    n = len(D.get("e", []))
    if n < 1000:
        print(f"insufficient rows ({n}) -- extraction may still be running"); return
    print(f"I-CARE: {n} bins, {D['nseg']} patient-segments, {D['npat']} patients; k=+/-{k} bins (+/-{30*k}s)")
    print(f"exposure: any suppression ({100*D['e'].mean():.1f} % of bins); outcome: change in log RMSSD")
    print(f"fixed effects per (patient, segment); {NBOOT} PATIENT-level bootstrap reps\n")

    # patient-level resampling: draw patients, take all their segments' rows
    order = np.argsort(D["pat"], kind="stable")
    for key in list(D.keys()):
        if key not in ("nseg", "npat"):
            D[key] = D[key][order]
    span = (np.searchsorted(D["pat"], np.arange(D["npat"]), side="right")
            - np.searchsorted(D["pat"], np.arange(D["npat"]), side="left"))
    w1 = np.ones(n)
    pf = coef(D, D["df"], w1); pb = coef(D, D["db"], w1)
    if pf is None or pb is None:
        print("fit failed"); return
    bf, bb, bd = [], [], []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["npat"], D["npat"]), minlength=D["npat"]).astype(np.float64)
        w = np.repeat(cnt, span)
        a = coef(D, D["df"], w); b = coef(D, D["db"], w)
        if a is not None and b is not None:
            bf.append(a); bb.append(b); bd.append(a - b)
    if len(bd) < 50:
        print("bootstrap failed"); return
    for nm, pt, bs_ in (("forward   dlogRMSSD", pf, bf), ("backward  dlogRMSSD", pb, bb)):
        lo, hi = np.percentile(bs_, [2.5, 97.5])
        print(f"   {nm:22s} {100*pt:+7.3f} % [{100*lo:+7.3f},{100*hi:+7.3f}] {'*' if (lo>0 or hi<0) else 'ns'}")
    lo, hi = np.percentile(bd, [2.5, 97.5])
    d = pf - pb
    verdict = ("AUTONOMIC WITHDRAWAL FOLLOWS SUPPRESSION (predicted)" if hi < 0 else
               ("REVERSED" if lo > 0 else "no asymmetry -- prediction NOT supported"))
    print(f"   {'forward MINUS backward':22s} {100*d:+7.3f} % [{100*lo:+7.3f},{100*hi:+7.3f}]   {verdict}")
    print("\n   No anaesthetic is being titrated in this cohort, so a positive result here cannot be the")
    print("   dose-confound that every VitalDB estimate has to adjust away. Sedation is unrecorded, however,")
    print("   and targeted temperature management depresses both signals -- see the docstring.")


if __name__ == "__main__":
    sys.exit(main())
