"""How much does one bad channel move a whole-head spectral feature? Measured, per deposit.

WHY THIS EXISTS. E20's registered gate failed, and the diagnosis was not biology. In `ds004541` the
per-channel standard deviations within a single 30 s window span **31 microvolts (Fz) to 4.2e4 (C2)** —
three orders of magnitude. `_mean_psd` in `candidates/seed.py` sums POWER across channels and divides by
their count, and power goes as amplitude squared, so a channel 1,000x too large contributes 1,000,000x the
weight of a good one. Every candidate built on `_mean_psd` — `relative_delta_power`, `relative_alpha_power`,
`spectral_edge_95`, `spectral_entropy` — is therefore, on that deposit, a measurement of its worst channel.

The signature is visible in the tables without any raw data: ds004541 reports a median relative delta of
0.89 in awake pre-drug windows and a median relative ALPHA of 0.01, against 0.20 and 0.42 on Chennu. An
awake human with 1 % alpha has not been recorded; a broken electrode has.

**THE FIRST VERSION OF THIS SCRIPT TESTED THE WRONG THING, AND THE CORRECTION IS THE POINT.** It compared
the mean-power aggregate against a per-frequency MEDIAN across channels, on the theory that one huge channel
was dominating the sum. The two agreed to 0.007 — because on ds004541 the median channel is bad too. The
per-channel amplitude distribution says why: in one 30 s window, **23 of 62 channels sit in a physiological
5-150 microvolt band and 39 do not**, running from 1,600 up to 153,000 microvolts. Restricted to the 23
plausible channels the same window gives relative delta 0.424 and relative alpha 0.097 — ordinary awake EEG.
Taken over all 62 it gives 0.799 and 0.021.

So the defect is not a weighting choice; it is that **the pipeline has no channel-quality rejection at
all**, and a deposit where most of the montage is dead produces confident nonsense. A robust aggregator
would not have saved it. High-pass filtering does not touch it either: filtering at 0.5 or 1.0 Hz moves the
median channel's delta from 0.687 to 0.651, so this is not drift leaking into the 1-4 Hz bin.

WHAT THIS SCRIPT DOES AND DOES NOT DO. It measures, per deposit, on one window: the per-channel amplitude
distribution, the fraction of channels in a physiological band, and what the headline spectral ratios become
under three aggregations — mean power (what the pipeline computes today), median PSD, and plausible channels
only. **It changes nothing.** Altering `_mean_psd` would change the definition fingerprint of five
candidates and invalidate the corresponding column in every table already extracted, so the exposure is
measured before anything is touched (rule 1: a correction propagates to everything downstream, and the list
of what it touches comes first).

Two-channel deposits (Sleep-EDF, VitalDB's frontal BIS strip) cannot show this failure the same way and are
included as controls.

THE AMPLITUDE BAND IS A JUDGEMENT AND IS DECLARED AS ONE. 5-150 microvolts brackets scalp EEG with room for
high-amplitude slow waves at the top and for a quiet channel at the bottom; it is not derived from these
data and it is not tuned. A channel outside it is *implausible*, not proven dead, which is why this script
reports the count rather than dropping anything.

    python bsde/scripts/diagnose_channel_spread.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

BANDS = (("delta", 1.0, 4.0), ("alpha", 8.0, 13.0))

"""The plausible-channel test now lives in `bsde.features.quality` and is imported rather than repeated, so
that the number this script reports and the number any future filter acts on cannot drift apart. It was
inline here first, and duplicating a threshold is how two scripts computing the same quantity come to
disagree (rule 20)."""


def _psd(ch, sfreq):
    from bsde.features.aperiodic import welch_psd
    return welch_psd(np.asarray(ch, float), sfreq, window_s=4.0, overlap=0.5)


def spread_report(label: str, data, ch_names, sfreq: float) -> dict:
    """Per-channel amplitude spread, and what it does to a mean-power aggregate.

    `mean_power` reproduces `_mean_psd` exactly: sum the per-channel PSDs, divide by the channel count.
    `median_psd` is the per-frequency median across channels, which is the cheapest robust alternative and
    is used here ONLY as a yardstick — nothing in the pipeline is switched to it by this script.
    """
    from bsde.features.spectral import relative_band_power

    x = np.asarray(data, float)
    sd = np.nanstd(x, axis=1)
    good = np.isfinite(sd) & (sd > 0)
    sd_ok = sd[good]
    med_sd = float(np.median(sd_ok)) if sd_ok.size else float("nan")
    ratio = float(sd_ok.max() / med_sd) if sd_ok.size and med_sd > 0 else float("nan")

    psds, freqs = [], None
    for ch in x:
        try:
            f, p = _psd(ch, sfreq)
        except Exception:
            continue
        freqs = f
        psds.append(p)
    if freqs is None or not psds:
        return {"label": label, "n_channels": int(x.shape[0]), "sd_ratio_max_over_median": ratio}
    P = np.vstack(psds)
    mean_p = P.mean(axis=0)
    med_p = np.median(P, axis=0)
    from bsde.features.quality import channel_quality
    plausible = np.asarray(channel_quality(x, ch_names, units="microvolts")["keep"], bool)
    plaus_p = P[plausible[:len(P)]].mean(axis=0) if plausible[:len(P)].any() else None

    out = {"label": label, "n_channels": int(x.shape[0]), "sfreq": float(sfreq),
           "sd_median_uv": med_sd, "sd_max_uv": float(sd_ok.max()) if sd_ok.size else float("nan"),
           "sd_ratio_max_over_median": ratio,
           "n_plausible": int(plausible.sum()),
           "frac_plausible": float(plausible.mean()) if plausible.size else float("nan")}
    for name, lo, hi in BANDS:
        out[f"{name}_mean_power"] = float(relative_band_power(freqs, mean_p, lo, hi))
        out[f"{name}_median_psd"] = float(relative_band_power(freqs, med_p, lo, hi))
        out[f"{name}_plausible"] = (float(relative_band_power(freqs, plaus_p, lo, hi))
                                    if plaus_p is not None else float("nan"))
    return out


def _print(rep: dict) -> None:
    if "delta_mean_power" not in rep:
        print(f"   {rep['label']:26s} could not be summarised (no usable PSD)")
        return
    print(f"   {rep['label']:28s} ch={rep['n_channels']:3d}  sd med={rep['sd_median_uv']:9.1f} uV  "
          f"max={rep['sd_max_uv']:11.1f}  plausible {rep['n_plausible']:3d}/{rep['n_channels']:<3d} "
          f"({rep['frac_plausible']:.0%})")
    for name, _, _ in BANDS:
        print(f"        rel_{name:6s} pipeline(mean-power) {rep[f'{name}_mean_power']:.3f}   "
              f"median-psd {rep[f'{name}_median_psd']:.3f}   plausible-only "
              f"{rep[f'{name}_plausible']:.3f}")


def main(argv=None) -> int:
    print("CHANNEL-SPREAD DIAGNOSTIC — one window per deposit. Measures exposure; changes nothing.\n")
    reports = []

    # ds004541 — the deposit whose numbers prompted this.
    try:
        from bsde.ingestion.ds004541 import (ACCESSION, BUCKET, EEG_ONLY, TASK, events, participants)
        from bsde.ingestion.http_edf import read_edf_window_http
        sub = participants()[0]
        ev = events(sub)
        t0 = max(0.0, float(ev.get("start", 300.0)) - 180.0)
        url = f"{BUCKET}/{ACCESSION}/{sub}/ses-01/eeg/{sub}_ses-01_task-{TASK}_eeg.edf"
        x, ch, sf, _ = read_edf_window_http(url, window_s=30.0, start_seconds=t0,
                                            channel_regex=EEG_ONLY)
        reports.append(spread_report(f"ds004541 {sub} awake", x, ch, sf))
    except Exception as e:                                    # noqa: BLE001
        print(f"   ds004541: unavailable ({type(e).__name__}: {e})")

    # VitalDB — two frontal channels, a control: this failure mode cannot arise the same way.
    try:
        from bsde.ingestion.vitaldb import VitalDBGridAdapter
        a = VitalDBGridAdapter(n_cases=1, grid_s=300.0, max_windows=6)
        refs = [r for r in a.list_recordings()]
        for r in refs[1:4]:
            try:
                x, ch, sf, _ = r.load()
                reports.append(spread_report(f"vitaldb {r.recording_id}", x, ch, sf))
                break
            except Exception:
                continue
    except Exception as e:                                    # noqa: BLE001
        print(f"   vitaldb: unavailable ({type(e).__name__}: {e})")

    # ds005620 — BrainVision, and the deposit that replicated `exponent_high` (0.762 [0.648, 0.885]).
    try:
        from bsde.ingestion.openneuro_brainvision import OpenNeuroBrainVisionAdapter
        ad = OpenNeuroBrainVisionAdapter("ds005620", dataset="ds005620", window_s=30.0)
        for r in ad.list_recordings()[:3]:
            try:
                x, ch, sf, _ = r.load()
                reports.append(spread_report(f"ds005620 {r.recording_id}"[:28], x, ch, sf))
                break
            except Exception:
                continue
    except Exception as e:                                    # noqa: BLE001
        print(f"   ds005620: unavailable ({type(e).__name__}: {e})")

    # ds007554 — EDF over S3.
    try:
        from bsde.ingestion.openneuro_s3 import OpenNeuroS3Adapter
        ad = OpenNeuroS3Adapter("ds007554", dataset="ds007554", suffix="_eeg.edf", window_s=30.0)
        for r in ad.list_recordings()[:3]:
            try:
                x, ch, sf, _ = r.load()
                reports.append(spread_report(f"ds007554 {r.recording_id}"[:28], x, ch, sf))
                break
            except Exception:
                continue
    except Exception as e:                                    # noqa: BLE001
        print(f"   ds007554: unavailable ({type(e).__name__}: {e})")

    # Chennu underpins most of this project's earlier results and is NOT reachable from this sandbox: the
    # Cambridge repository host fails TLS hostname verification (the same blocker that stopped E12). Its
    # exposure to this defect is therefore UNMEASURED, not measured-and-clean, and must be reported that way.
    print("   chennu: NOT PROBED — api.repository.cam.ac.uk fails TLS hostname verification from this")
    print("           sandbox (the E12 blocker). Its exposure is UNMEASURED, not clean.")

    for rep in reports:
        _print(rep)
    if not reports:
        print("   nothing reachable — no conclusion is drawn (rule 31: absent, not negative).")
        return 1
    print("\n   The column that matters is `plausible`. Where it is 100 %, the three aggregations agree and")
    print("   the deposit is unexposed. Where it is low, the pipeline's number and the number computed from")
    print("   the surviving channels are different measurements, and the pipeline's is the wrong one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
