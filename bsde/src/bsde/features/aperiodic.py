"""Aperiodic (1/f) exponent and offset — the feature the frozen UCE v1 is built from.

METHOD AND ITS KNOWN WEAKNESS, STATED HERE BECAUSE IT DRIVES EVERY DOWNSTREAM CLAIM. The exponent is the
negative slope of log10(PSD) against log10(f) over a fit range. A plain OLS fit is biased by any oscillatory
peak inside that range: alpha power sitting on the line pulls the slope. Two mitigations are provided and the
choice is a config parameter, never a silent default:

    mode="loglog_ols"     plain OLS over the fit range. Fast, transparent, peak-biased.
    mode="loglog_robust"  iterative peak-suppression: fit, drop the points furthest ABOVE the line
                          (peaks add power, they do not subtract it), refit. Reduces peak bias without
                          committing to a parametric peak model.

Sign convention: `exponent` is POSITIVE for a spectrum falling with frequency (typical EEG ~ 1-3). This
matches the FOOOF/specparam convention. A negative value indicates a rising spectrum, which in practice means
EMG contamination or a broken recording, and is surfaced rather than clipped.
"""
from __future__ import annotations

from typing import Dict

import numpy as np


def welch_psd(x: np.ndarray, sfreq: float, window_s: float = 4.0,
              overlap: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Welch PSD via Hann-windowed segments. Implemented directly to keep the stdlib+numpy dependency floor."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    nper = int(round(window_s * sfreq))
    if nper < 16 or len(x) < nper:
        raise ValueError(f"signal too short for a {window_s}s window")
    step = max(1, int(nper * (1.0 - overlap)))
    win = np.hanning(nper)
    # Power normalisation for a windowed periodogram; U corrects the window's power loss.
    U = (win ** 2).sum() * sfreq
    segs = [x[i:i + nper] for i in range(0, len(x) - nper + 1, step)]
    if not segs:
        raise ValueError("no complete segments")
    P = np.zeros(nper // 2 + 1)
    for s in segs:
        P += np.abs(np.fft.rfft((s - s.mean()) * win)) ** 2
    P /= (len(segs) * U)
    P[1:-1] *= 2.0                      # one-sided
    freqs = np.fft.rfftfreq(nper, 1.0 / sfreq)
    return freqs, P


def fit_aperiodic(freqs: np.ndarray, psd: np.ndarray, fit_lo_hz: float = 1.0, fit_hi_hz: float = 40.0,
                  mode: str = "loglog_ols", exclude_line_hz: float | None = None,
                  line_halfwidth_hz: float = 2.0, robust_iters: int = 3,
                  robust_drop: float = 0.15) -> Dict[str, float]:
    """Return {'exponent', 'offset', 'r2', 'n_points'} for one PSD.

    exponent > 0 means power falls with frequency.
    """
    freqs = np.asarray(freqs, float)
    psd = np.asarray(psd, float)
    m = (freqs >= fit_lo_hz) & (freqs <= fit_hi_hz) & (psd > 0) & np.isfinite(psd)
    if exclude_line_hz:
        for harm in (1, 2):
            c = exclude_line_hz * harm
            m &= ~((freqs > c - line_halfwidth_hz) & (freqs < c + line_halfwidth_hz))
    if m.sum() < 5:
        return {"exponent": float("nan"), "offset": float("nan"), "r2": float("nan"), "n_points": 0}
    lf, lp = np.log10(freqs[m]), np.log10(psd[m])

    def ols(a, b):
        A = np.vstack([a, np.ones_like(a)]).T
        coef, *_ = np.linalg.lstsq(A, b, rcond=None)
        pred = A @ coef
        ss_res = float(((b - pred) ** 2).sum())
        ss_tot = float(((b - b.mean()) ** 2).sum())
        return coef, (1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")), pred

    coef, r2, pred = ols(lf, lp)
    if mode == "loglog_robust":
        keep = np.ones(lf.size, bool)
        for _ in range(robust_iters):
            resid = lp - pred
            # Peaks ADD power, so drop the largest POSITIVE residuals only. Dropping symmetric outliers
            # would also discard the low-power tail and bias the slope the other way.
            k = int(round(robust_drop * keep.sum()))
            if k < 1 or keep.sum() - k < 5:
                break
            order = np.argsort(np.where(keep, resid, -np.inf))
            keep[order[-k:]] = False
            coef, r2, p_sub = ols(lf[keep], lp[keep])
            pred = coef[0] * lf + coef[1]
    elif mode != "loglog_ols":
        raise ValueError(f"unknown mode {mode!r}")
    return {"exponent": float(-coef[0]), "offset": float(coef[1]),
            "r2": float(r2), "n_points": int(m.sum())}


def channel_aperiodic(data: np.ndarray, sfreq: float, cfg: Dict | None = None) -> list[Dict[str, float]]:
    """Per-channel aperiodic fits for data[n_channels, n_samples]."""
    cfg = cfg or {}
    ap = cfg.get("aperiodic", {})
    ps = cfg.get("psd", {})
    out = []
    for ch in np.atleast_2d(data):
        try:
            f, p = welch_psd(ch, sfreq, ps.get("window_s", 4.0), ps.get("overlap", 0.5))
            out.append(fit_aperiodic(f, p, ap.get("fit_lo_hz", 1.0), ap.get("fit_hi_hz", 40.0),
                                     ap.get("mode", "loglog_ols"), ap.get("exclude_line_hz")))
        except Exception:
            out.append({"exponent": float("nan"), "offset": float("nan"),
                        "r2": float("nan"), "n_points": 0})
    return out
