"""Extract perturbational (TMS-EEG) features from ds005620 -- WITH A SHAM ARM IN THE SAME EXTRACTION.

WHY THIS EXISTS. Challenge A's experiments to date have been validation-shaped, and the session's results
converge on one statement: everything measured so far is a single arousal axis. `uce_v1` is the whole-head
exponent restated; E92 found no decoupling between two regions; E73/E86's network measures reduce to mean
connectivity; E93/E95/E100 all order on arousal. **The discovery question is whether a SECOND axis exists.**
Perturbational complexity (Casali et al. 2013, PMID 23946194) is the best-established candidate, and
ds005620 carries an unused TMS arm with `task-awake` and `task-sed` WITHIN subject.

=========================================================================================================
WHAT THE FEASIBILITY PROBE FORCES THIS SCRIPT TO DO DIFFERENTLY
=========================================================================================================
`bsde/results/tms_feasibility_note.md` (five diagnostics) established, on sub-1016:

  * the pulse artefact is present and ~1,800x above background (23,408 vs 10.5 uV/sample);
  * the data is NOT artefact-removed (identical-consecutive-sample fraction 0.1935 near the marker vs
    0.1950 far away);
  * **the shipped markers do not index it.** `.vmrk` and `events.tsv` agree with each other to 0.2 ms and
    BOTH are wrong: marker windows sit at percentile 49.5 of randomly chosen windows, 0 of 15 above the
    95th, while the detected pulses form an independent ~2 s train with different jitter. Rule 65.

So: **pulses are detected from the signal, never read from a marker file** -- and that is done for EVERY
recording identically, including any whose markers might be fine, because handling recordings differently
according to a property of their metadata is a selection effect (rule 32's shape).

CONTIGUOUS BLOCK, NOT TARGETED WINDOWS, for the same reason and one more: targeted reads need correct
pulse times, which is what we do not have. One contiguous block per recording gives detection and epoching
from the same bytes. `--block-s 90` at 5 kHz x 64 ch x 4 B is ~115 MB per recording.

=========================================================================================================
THE SHAM ARM IS NOT OPTIONAL AND IS NOT A SEPARATE SCRIPT
=========================================================================================================
Rule 28, twice-earned: two measurements separated in space or time are not thereby measuring different
things. A "perturbational" complexity that merely reflects how complex the ongoing EEG is would reproduce
every state difference a spontaneous measure gives, and would look like a new axis. **The sham anchors sit
midway between consecutive detected pulses** -- same recording, same channels, same epoch length, same
count, same pipeline, no perturbation -- and every feature below is emitted twice, once real and once
sham. Any experiment consuming this table must gate on the real-minus-sham contrast, not on the real value.

Emitting them together also guarantees they cannot drift apart: one segmentation, one detector, one
baseline rule (rule 20 -- when two paths compute the same quantity, they must be the same code).

=========================================================================================================
FEATURES, and why each is defensible
=========================================================================================================
Epoch -500..+500 ms, baseline-corrected per channel on -500..-100 ms. **-5..+30 ms is BLANKED** (set to
nan) because the TMS artefact and the cranial muscle twitch live there; `blank_frac` records how much of
the analysis window that removes, so no experiment can quietly treat a blanked epoch as an intact one.

  n_pulses, iti_median, iti_iqr   detector output, so any state contrast can be checked for being a
                                  contrast between two detection rates rather than two brains (rule 32)
  det_separation                  max|diff| at detections / max|diff| at random points -- the detector's
                                  own evidence that it selected pulses (rule 5)
  evoked_rms                      across-channel mean RMS of the averaged evoked response, 30-300 ms
  baseline_rms                    the same statistic on -500..-100 ms; evoked_rms alone is not a response
  response_duration_ms            last 10 ms bin in 30-500 ms whose across-channel mean |evoked| exceeds
                                  the pre-pulse 95th percentile
  n_channels_responding           channels whose 30-300 ms RMS exceeds their OWN pre-pulse 95th percentile
  evoked_lz                       LZ76 complexity of the binarised significant/not map over
                                  (responding channels x 10 ms bins), normalised -- the PCI-family
                                  construction, computed here on a fixed threshold rather than on a
                                  bootstrap significance map, which is a simplification and is named as one
  spont_exponent                  aperiodic exponent of the PRE-PULSE segments -- the spontaneous axis the
                                  perturbational measure must be shown to decouple from, measured on the
                                  same bytes so no cross-recording alignment is needed

SCOPE. This script extracts. It computes no contrast, fits no model, and reads no state label beyond the
BIDS `task-` entity that names the file. Nothing here tests or claims anything about consciousness.

    python bsde/scripts/extract_ds005620_perturbation.py --limit 4          # smoke, PERMUTED nothing
    python bsde/scripts/extract_ds005620_perturbation.py                    # full pass, resumable
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.features.aperiodic import fit_aperiodic, welch_psd                      # noqa: E402
from bsde.features.complexity import lempel_ziv_complexity_fast                   # noqa: E402
from bsde.ingestion.openneuro_brainvision import (parse_vhdr, decode_brainvision_window,  # noqa: E402
                                                  _http_get_range,
                                                  _check_format_and_orientation)

BASE = "https://s3.amazonaws.com/openneuro.org/"
DATASET = "ds005620"
OUT = os.path.abspath(os.path.join(HERE, "..", "results", "ds005620_perturbation.csv"))

PRE_S, POST_S = 0.500, 0.500
BASE_LO, BASE_HI = -0.500, -0.100
BLANK_LO, BLANK_HI = -0.005, 0.030
RESP_LO, RESP_HI = 0.030, 0.300
BIN_S = 0.010
MIN_PULSES = 12
SEED = 20260731

FIELDS = ["recording_id", "subject", "task", "run", "status", "error", "sfreq", "n_channels",
          "block_start_s", "block_s", "n_pulses", "iti_median", "iti_iqr", "det_separation",
          "blank_frac", "spont_exponent",
          "real_evoked_rms", "real_baseline_rms", "real_response_duration_ms",
          "real_n_channels_responding", "real_evoked_lz",
          "sham_evoked_rms", "sham_baseline_rms", "sham_response_duration_ms",
          "sham_n_channels_responding", "sham_evoked_lz"]


def _get(url, timeout=120):
    return urllib.request.urlopen(url, timeout=timeout).read()


def list_tms_keys():
    """Every `acq-tms` .vhdr in the deposit, from the OpenNeuro S3 listing (rule 39: parse, do not fetch
    through a summariser)."""
    keys, token = [], None
    while True:
        url = (f"{BASE}?list-type=2&prefix={DATASET}/&max-keys=1000"
               + (f"&continuation-token={urllib.parse.quote(token)}" if token else ""))
        txt = _get(url).decode("utf8", "replace")
        keys += [m for m in re.findall(r"<Key>([^<]+)</Key>", txt)
                 if "acq-tms" in m and m.endswith("_eeg.vhdr")]
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", txt)
        if not m:
            break
        token = m.group(1)
    return sorted(keys)


def first_marker_s(stem):
    """A COARSE anchor only: the earliest marker position, used to choose where to start reading.

    The feasibility probe showed these times are wrong at the millisecond level. They are still a correct
    statement about WHICH PART OF THE RECORDING was stimulated, which is all this is used for. No epoch is
    ever cut from a marker.
    """
    try:
        txt = _get(BASE + stem + "_eeg.vmrk").decode("utf8", "replace")
    except Exception:
        return None
    pos = [int(d) for _, b, c, d in re.findall(r"^(Mk\d+)=([^,]*),([^,]*),(\d+),", txt, re.M)
           if c.strip() not in ("", "S  1")]
    return min(pos) if pos else None


def detect_pulses(d, sf, rng):
    """Slew-based detection with the stability and separation evidence the verdict needs.

    Threshold is a FRACTION OF THE BLOCK MAXIMUM, not a robust-z cut: a TMS pulse is not the tail of the
    EEG amplitude distribution, it is a different physical event, and a MAD-based threshold came out three
    orders of magnitude too loose in diagnostic 2.
    """
    g = np.max(np.abs(np.diff(d, axis=1)), axis=0)
    gmax = float(g.max()) if g.size else 0.0
    if gmax <= 0:
        return [], float("nan"), g
    peaks = []
    for i in np.flatnonzero(g > 0.10 * gmax):
        if not peaks or i - peaks[-1] > int(0.5 * sf):
            peaks.append(int(i))
        elif g[i] > g[peaks[-1]]:
            peaks[-1] = int(i)
    half = int(round(0.025 * sf))
    if peaks and g.size > 4 * half:
        r = rng.integers(half, g.size - half, size=200)
        at_det = np.median([g[max(0, p - half):p + half].max() for p in peaks])
        at_rnd = np.median([g[i - half:i + half].max() for i in r])
        sep = float(at_det / at_rnd) if at_rnd > 0 else float("nan")
    else:
        sep = float("nan")
    return peaks, sep, g


def epoch(d, sf, anchors, n_pre, n_post):
    """Baseline-corrected epochs with the artefact window blanked. Returns (epochs, blank_frac)."""
    b0, b1 = int(round((BASE_LO + PRE_S) * sf)), int(round((BASE_HI + PRE_S) * sf))
    k0, k1 = int(round((BLANK_LO + PRE_S) * sf)), int(round((BLANK_HI + PRE_S) * sf))
    out = []
    for a in anchors:
        if a - n_pre < 0 or a + n_post > d.shape[1]:
            continue
        seg = d[:, a - n_pre:a + n_post].astype(float)
        seg = seg - seg[:, b0:b1].mean(axis=1, keepdims=True)
        seg[:, k0:k1] = np.nan
        out.append(seg)
    blank = (k1 - k0) / float(n_pre + n_post)
    return out, float(blank)


def evoked_features(eps, sf):
    """The PCI-family feature set on one list of epochs. Identical code for the real and sham arms."""
    if len(eps) < MIN_PULSES:
        return {k: float("nan") for k in
                ("evoked_rms", "baseline_rms", "response_duration_ms",
                 "n_channels_responding", "evoked_lz")}
    E = np.nanmean(np.stack(eps), axis=0)                     # channels x time
    b0, b1 = int(round((BASE_LO + PRE_S) * sf)), int(round((BASE_HI + PRE_S) * sf))
    r0, r1 = int(round((RESP_LO + PRE_S) * sf)), int(round((RESP_HI + PRE_S) * sf))

    def rms(a):
        a = a[np.isfinite(a)]
        return float(np.sqrt(np.mean(a ** 2))) if a.size else float("nan")

    base_rms = rms(E[:, b0:b1])
    evk_rms = rms(E[:, r0:r1])

    # per-channel threshold from that channel's OWN pre-pulse distribution
    thr = np.nanpercentile(np.abs(E[:, b0:b1]), 95, axis=1)
    ch_rms = np.array([rms(E[c, r0:r1]) for c in range(E.shape[0])])
    n_resp = int(np.sum(np.isfinite(ch_rms) & (ch_rms > thr)))

    # binarised significance map over (channels x 10 ms bins), 30..500 ms
    nb = int(round((POST_S - RESP_LO) / BIN_S))
    binmap = np.zeros((E.shape[0], nb), dtype=np.int8)
    for j in range(nb):
        s = int(round((RESP_LO + j * BIN_S + PRE_S) * sf))
        e = int(round((RESP_LO + (j + 1) * BIN_S + PRE_S) * sf))
        w = E[:, s:e]
        with np.errstate(invalid="ignore"):
            binmap[:, j] = (np.nanmax(np.abs(w), axis=1) > thr).astype(np.int8)

    dur = float("nan")
    col = binmap.mean(axis=0)
    hot = np.flatnonzero(col >= 0.10)          # >=10 % of channels above their own 95th percentile
    if hot.size:
        dur = float((RESP_LO + (hot.max() + 1) * BIN_S) * 1000.0)

    flat = binmap.ravel()
    n = flat.size
    lz = float(lempel_ziv_complexity_fast(flat) / (n / math.log2(n))) if n > 1 else float("nan")
    return {"evoked_rms": evk_rms, "baseline_rms": base_rms, "response_duration_ms": dur,
            "n_channels_responding": n_resp, "evoked_lz": lz}


def process(key, block_s, rng):
    stem = key[:-len("_eeg.vhdr")]
    ent = {}
    for p in os.path.basename(stem).split("_"):
        if "-" in p:
            k, v = p.split("-", 1)
            ent[k] = v
    row = {"recording_id": stem, "subject": ent.get("sub", ""), "task": ent.get("task", ""),
           "run": ent.get("run", ""), "status": "ok", "error": ""}
    h = parse_vhdr(_get(BASE + key).decode("utf8", "replace"))
    sf = float(h["sfreq"])
    dt = _check_format_and_orientation(h["binary_format"], h["data_orientation"])
    fb = h["n_channels"] * dt.itemsize
    row["sfreq"], row["n_channels"] = sf, h["n_channels"]

    anchor = first_marker_s(stem)
    start = max(0, (anchor if anchor is not None else int(10 * sf)) - int(round(2.0 * sf)))
    n = int(round(block_s * sf))
    raw = _http_get_range(BASE + stem + "_eeg.eeg", start * fb, n * fb, timeout=900)
    d = decode_brainvision_window(raw, n_channels=h["n_channels"], binary_format=h["binary_format"],
                                  data_orientation=h["data_orientation"], resolutions=h["resolutions"],
                                  units=h["units"]).astype(float)
    row["block_start_s"] = round(start / sf, 3)
    row["block_s"] = round(d.shape[1] / sf, 3)

    peaks, sep, _ = detect_pulses(d, sf, rng)
    row["n_pulses"] = len(peaks)
    row["det_separation"] = sep
    if len(peaks) >= 2:
        iti = np.diff(peaks) / sf
        row["iti_median"] = float(np.median(iti))
        row["iti_iqr"] = float(np.percentile(iti, 75) - np.percentile(iti, 25))
    else:
        row["iti_median"] = row["iti_iqr"] = float("nan")
    if len(peaks) < MIN_PULSES:
        row["status"] = "too_few_pulses"
        return row

    n_pre, n_post = int(round(PRE_S * sf)), int(round(POST_S * sf))
    real, blank = epoch(d, sf, peaks, n_pre, n_post)
    # SHAM anchors: midway between consecutive detected pulses. Same count-1, same length, no perturbation.
    sham_anchors = [(peaks[i] + peaks[i + 1]) // 2 for i in range(len(peaks) - 1)]
    sham, _ = epoch(d, sf, sham_anchors, n_pre, n_post)
    row["blank_frac"] = blank

    for arm, eps in (("real", real), ("sham", sham)):
        for k, v in evoked_features(eps, sf).items():
            row[f"{arm}_{k}"] = v

    # spontaneous exponent on the pre-pulse stretches, concatenated per channel
    b0, b1 = int(round((BASE_LO + PRE_S) * sf)), int(round((BASE_HI + PRE_S) * sf))
    if real:
        pre = np.concatenate([e[:, b0:b1] for e in real], axis=1)
        exps = []
        for c in range(pre.shape[0]):
            x = pre[c][np.isfinite(pre[c])]
            if x.size < int(4 * sf):
                continue
            f, p = welch_psd(x, sf, window_s=1.0)
            fit = fit_aperiodic(f, p, fit_lo_hz=1.0, fit_hi_hz=40.0)
            e = fit.get("exponent", float("nan"))
            if np.isfinite(e):
                exps.append(e)
        row["spont_exponent"] = float(np.median(exps)) if exps else float("nan")
    else:
        row["spont_exponent"] = float("nan")
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--block-s", type=float, default=90.0, dest="block_s")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)

    done = set()
    if os.path.exists(a.out):
        for r in csv.DictReader(open(a.out, newline="")):
            done.add(r["recording_id"])
    keys = list_tms_keys()
    keys = [k for i, k in enumerate(keys) if i % a.of == a.shard]
    todo = [k for k in keys if k[:-len("_eeg.vhdr")] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(keys)} acq-tms recordings in shard {a.shard}/{a.of}; {len(done)} already done; "
          f"{len(todo)} to do -> {a.out}", flush=True)

    new = not os.path.exists(a.out)
    fh = open(a.out, "a", newline="")
    w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
    if new:
        w.writeheader()
    rng = np.random.default_rng(SEED)
    for i, k in enumerate(todo):
        stem = k[:-len("_eeg.vhdr")]
        try:
            row = process(k, a.block_s, rng)
        except Exception as e:
            row = {"recording_id": stem, "status": "error", "error": f"{type(e).__name__}: {e}"}
        w.writerow(row)
        fh.flush()
        print(f"[{i+1}/{len(todo)}] {os.path.basename(stem)}  {row.get('status')}  "
              f"pulses={row.get('n_pulses')}  sep={row.get('det_separation')}  "
              f"real_lz={row.get('real_evoked_lz')}  sham_lz={row.get('sham_evoked_lz')}", flush=True)
    fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
