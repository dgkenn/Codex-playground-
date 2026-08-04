"""Resting-EEG features from Stieger's PRE-CUE baselines -- the Challenge B experiment E68 unblocked.

WHY NOW. E68 measured this deposit's label ceiling and it is **0.9652 [0.9568, 0.9706]** within session
against eegmmidb's 0.2918, lifting the attenuation ceiling from 0.5402 to **0.9825**. E41's Challenge B null
was measured through the old ceiling and was never interpretable. A null measured here would be a REAL null.
That was Q14's precondition and it is met, so the correlation can finally be run -- but it needs features,
and this is the pass that produces them.

WHAT IS EXTRACTED, AND WHY THE PRE-CUE WINDOW. `BCI.time` runs -2000 ... +9040 ms at 1000 Hz, so every trial
carries **2.00 s of task-free lead-in**. At 450 trials that is 900 s per session -- more task-free EEG than
most dedicated resting deposits hold per subject. **It is NOT a resting recording** (the subject is cued,
engaged and between trials) and Q14's caveat rides with every use of it.

EPOCHS ARE NOT CONCATENATED. Rule 27: joining 450 separate 2 s segments would glue unrelated time together.
Every feature is computed PER EPOCH and then summarised by the median across epochs, so no statistic ever
spans a join. That also means `lrtc_alpha` is untestable here and is not attempted -- Q14 established this
and `lrtc_envelope` now refuses rather than silently shrinking its scale range.

THE CONNECTIVITY FAMILY IS THE POINT. The Challenge B literature has moved to network measures -- resting
efficiency (PMID 26529439), microstates at AUC 0.83 (PMID 37759889), a three-dataset connectivity survey
(PMID 38986469) -- while **every Challenge B candidate this project has tested is an amplitude summary**.
Stieger's 62 channels can carry inter-channel phase where VitalDB's two-electrode strip could not (Q26).
Connectivity is computed on the project's standard 10-channel montage so it is comparable to everything
else, and the graph measures come from the wPLI matrix over those 45 pairs.

`TrialData.triallength` IS CAPTURED THIS TIME. The label pass kept only hit/miss, and a binary outcome
throws away most of a trial's information; time-to-target is continuous and costs nothing extra here.

    python bsde/scripts/extract_stieger_features.py --sessions-per-subject 3
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.features.connectivity import coherence, wpli                     # noqa: E402
from extract_stieger_labels import NAME, file_index                        # noqa: E402

OUT = os.path.join(HERE, "..", "results", "stieger_features.csv")
MONTAGE = ("Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2")
SFREQ = 1000.0
PRE_CUE_S = 2.0
MAX_EPOCHS = 120            # of 450; the median across 120 epochs is already stable and the DSP is O(n)
BANDS = {"theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}

SPECTRAL = ["exponent_low", "exponent_high", "whole_head_exponent", "relative_alpha_power",
            "relative_delta_power", "spectral_edge_95", "spectral_entropy", "lempel_ziv"]
CONN = [f"{k}_{b}" for b in BANDS for k in ("wpli", "coherence")]
GRAPH = ["wpli_alpha_global_efficiency", "wpli_alpha_clustering", "wpli_alpha_mean_degree"]
FIELDS = (["subject", "session", "n_epochs", "n_channels_used", "accuracy", "n_scored",
           "mean_triallength", "age", "gender", "handedness"] + SPECTRAL + CONN + GRAPH)


def _spectral(x, sfreq):
    """The project's standard single-channel features on one epoch."""
    from bsde.features.aperiodic import fit_aperiodic, welch_psd
    from bsde.features.complexity import lziv
    from bsde.features.spectral import relative_band_power, spectral_edge, spectral_entropy
    out = {}
    try:
        f, p = welch_psd(x, sfreq, window_s=1.0, overlap=0.5)
    except Exception:                                                      # noqa: BLE001
        return {k: float("nan") for k in SPECTRAL}
    for name, (lo, hi) in (("exponent_low", (1.0, 20.0)), ("exponent_high", (20.0, 40.0)),
                           ("whole_head_exponent", (1.0, 40.0))):
        try:
            out[name] = fit_aperiodic(f, p, lo, hi, "loglog_robust")["exponent"]
        except Exception:                                                  # noqa: BLE001
            out[name] = float("nan")
    # Same band edges and same 1-45 Hz denominator the rest of the project uses, so these columns are
    # comparable to every other deposit's rather than being a Stieger-only definition.
    for name, (lo, hi) in (("relative_alpha_power", (8.0, 13.0)), ("relative_delta_power", (1.0, 4.0))):
        try:
            out[name] = float(relative_band_power(f, p, lo, hi))
        except Exception:                                                  # noqa: BLE001
            out[name] = float("nan")
    for name, fn in (("spectral_edge_95", lambda: spectral_edge(f, p, 95.0)),
                     ("spectral_entropy", lambda: spectral_entropy(f, p)),
                     ("lempel_ziv", lambda: lziv(x))):
        try:
            out[name] = float(fn())
        except Exception:                                                  # noqa: BLE001
            out[name] = float("nan")
    return out


def _graph(W):
    """Global efficiency, clustering and mean degree from a symmetric non-negative wPLI matrix."""
    n = W.shape[0]
    A = np.clip(np.abs(W), 0, None)
    np.fill_diagonal(A, 0.0)
    deg = A.sum(axis=1) / max(1, n - 1)
    # inverse-weight shortest paths (Floyd-Warshall on 1/w), the standard weighted efficiency
    with np.errstate(divide="ignore"):
        D = np.where(A > 0, 1.0 / A, np.inf)
    np.fill_diagonal(D, 0.0)
    for k in range(n):
        D = np.minimum(D, D[:, k][:, None] + D[k, :][None, :])
    off = ~np.eye(n, dtype=bool)
    eff = float(np.mean(1.0 / D[off][np.isfinite(D[off]) & (D[off] > 0)])) if off.any() else float("nan")
    # weighted clustering (Onnela): geometric mean of triangle weights
    Aw = A / (A.max() if A.max() > 0 else 1.0)
    cub = np.cbrt(Aw)
    tri = np.diag(cub @ cub @ cub)
    kdeg = (A > 0).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(kdeg > 1, tri / (kdeg * (kdeg - 1)), np.nan)
    return {"wpli_alpha_global_efficiency": eff,
            "wpli_alpha_clustering": float(np.nanmean(c)),
            "wpli_alpha_mean_degree": float(np.mean(deg))}


def session_features(path, subject, session):
    from scipy.io import loadmat
    bci = loadmat(path, struct_as_record=False, squeeze_me=True)["BCI"]
    # `chaninfo.label` is a plain 62-element string array matching `data`'s channel axis. `electrodes`
    # holds 63 structs (62 channels plus a reference) and is NOT aligned to the data, so it must not be
    # used for indexing -- a first version read `electrodes[].labels` and failed on every file.
    labels = [str(x) for x in np.atleast_1d(bci.chaninfo.label)]
    idx = {}
    for want in MONTAGE:
        for j, lab in enumerate(labels):
            if lab.strip().upper() == want.upper():
                idx[want] = j
                break
    if len(idx) < 6:
        raise ValueError(f"only {len(idx)} of {len(MONTAGE)} montage channels found in {labels[:8]}...")
    chans = [idx[c] for c in MONTAGE if c in idx]

    data = bci.data
    n_pre = int(PRE_CUE_S * SFREQ)
    n_ep = min(MAX_EPOCHS, len(data))
    per_ep, wmats = [], []
    for e in range(n_ep):
        seg = np.asarray(data[e], float)[chans, :n_pre]
        if not np.isfinite(seg).all():
            continue
        rows = [_spectral(seg[c], SFREQ) for c in range(seg.shape[0])]
        f = {k: float(np.nanmedian([r[k] for r in rows])) for k in SPECTRAL}
        W = np.zeros((seg.shape[0], seg.shape[0]))
        for b, (lo, hi) in BANDS.items():
            wv, cv = [], []
            for i in range(seg.shape[0]):
                for j in range(i + 1, seg.shape[0]):
                    w = wpli(seg[i], seg[j], SFREQ, lo, hi, window_s=0.5)
                    c = coherence(seg[i], seg[j], SFREQ, lo, hi, window_s=0.5)
                    wv.append(w)
                    cv.append(c)
                    if b == "alpha":
                        W[i, j] = W[j, i] = w if np.isfinite(w) else 0.0
            f[f"wpli_{b}"] = float(np.nanmean(wv))
            f[f"coherence_{b}"] = float(np.nanmean(cv))
        per_ep.append(f)
        wmats.append(W)
    if not per_ep:
        raise ValueError("no usable epochs")
    out = {k: float(np.nanmedian([p[k] for p in per_ep])) for k in SPECTRAL + CONN}
    out.update(_graph(np.nanmedian(np.stack(wmats), axis=0)))

    td = bci.TrialData
    res = np.array([float(getattr(t, "result")) for t in td], float)
    tl = np.array([float(getattr(t, "triallength")) for t in td], float)
    ok = np.isfinite(res)
    md = bci.metadata
    out.update({"subject": subject, "session": session, "n_epochs": len(per_ep),
                "n_channels_used": len(chans),
                "accuracy": f"{float(res[ok].mean()):.6f}" if ok.any() else "",
                "n_scored": int(ok.sum()),
                "mean_triallength": f"{float(np.nanmean(tl)):.4f}" if np.isfinite(tl).any() else "",
                "age": getattr(md, "age", ""), "gender": getattr(md, "gender", ""),
                "handedness": getattr(md, "handedness", "")})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions-per-subject", type=int, default=3, dest="k")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--tmp", default="/tmp/eeg_probe/stieger_feat")
    a = ap.parse_args(argv)

    files = file_index()
    want = []
    for f in files:
        m = NAME.match(f["name"])
        if m and int(m.group(2)) <= a.k:
            want.append((m.group(1), m.group(2), f))
    want.sort(key=lambda t: (int(t[0]), int(t[1])))
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {(r["subject"], r["session"]) for r in csv.DictReader(fh)}
    todo = [t for t in want if (t[0], t[1]) not in done]
    print(f"{len(want)} sessions wanted, {len(done)} done, {len(todo)} to go", flush=True)

    os.makedirs(a.tmp, exist_ok=True)
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, (subj, sess, f) in enumerate(todo, 1):
            dest = os.path.join(a.tmp, f["name"])
            try:
                urllib.request.urlretrieve(f["download_url"], dest)
                row = session_features(dest, subj, sess)
                w.writerow({k: row.get(k, "") for k in FIELDS})
                fh.flush()
                print(f"   [{i}/{len(todo)}] S{subj} s{sess}: {row['n_epochs']} epochs, "
                      f"{row['n_channels_used']} ch, acc {row['accuracy']}", flush=True)
            except Exception as e:                                         # noqa: BLE001
                print(f"   [{i}/{len(todo)}] S{subj} s{sess}: FAIL {type(e).__name__}: {e}", flush=True)
            finally:
                if os.path.exists(dest):
                    os.remove(dest)
    print(f"   wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
