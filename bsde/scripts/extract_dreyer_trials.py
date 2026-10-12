"""PER-TRIAL pre-cue features from Dreyer 2023 — the external replication cohort E175 could not supply.

WHY THIS DEPOSIT AND WHY NOW. E172 found a pre-cue alpha effect on Stieger, E174 did not replicate it on
held-out sessions, and **E181 found the effect that does replicate**: pre-cue alpha predicts how FAST a
followed command is executed, discovered on 123 held-out sessions and confirmed on session 1. All of that
is one deposit. **E175's external test on eegmmidb gate-failed for power** — 45 trials per subject yields
matched adjacent pairs in only 8 of 105 subjects.

A feasibility probe of Dreyer's archive (run before this file was written — rule 41) settles that it is the
right deposit:

    87 subjects, 4 online runs each (`R3`-`R6_onlineT.gdf`, 87/87/86/86) plus 2 acquisition runs
    512 Hz, 32 EEG channels, **40 trials per run** -> ~160 online trials per subject, 3.5x eegmmidb
    event codes per trial: 768 trial start, 786 fixation, 33282, **769/770 the left/right cue**,
        781 feedback onset, 800 trial end; the cue sits 3 s after trial start and feedback 1.25 s after
        the cue, so a clean **2 s pre-cue window** exists at [cue - 2, cue)
    **EMG1/EMG2 are real channels** (`EMGg`, `EMGd`), which Stieger and eegmmidb do not have

That last point matters independently: E172 could not score its incumbent because Stieger's artefact flag
is 0 in 27,705 of 27,900 trials, and rule 57 records that this project has been burned by using a
constructed EMG proxy as ground truth. Dreyer ships the real thing.

WHAT IS EXTRACTED, per trial
  * the 2 s PRE-CUE window, with **`_spectral` imported from the Stieger extractor** so the features are
    the same computation and not merely the same names (rule 20), taken as the median over a ten-electrode
    montage, plus C3/C4 relative alpha and their lateralisation
  * the POST-CUE window [cue + 0.5, cue + 3.5], mu and beta band power over C3/C4/Cz, so a per-trial
    decoder correctness label can be built downstream without a second pass over 20 GB
  * `emg_pre`, the log RMS of the two EMG channels over the same pre-cue window — **log, because rule 57
    records that raw EMG amplitude carries a subject-specific gain and is not a magnitude**
  * `y` (0 = left cue, 1 = right cue), subject, run, trial index and the cue time

Reads by HTTP byte range from the 27.5 GB Zip64 archive, one member at a time, nothing written to disk
beyond a temporary file per run. Resumable on (subject, run) and shardable by subject.

    for k in 0 1 2 3; do
      python bsde/scripts/extract_dreyer_trials.py --shard $k --of 4 \
             --out bsde/results/dreyer_trials.s$k.csv &
    done; wait
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.ingestion.remote_zip import RemoteZip                                 # noqa: E402
from extract_dreyer_graph import ZIP_URL                                        # noqa: E402
from extract_stieger_features import SPECTRAL, _spectral                        # noqa: E402

OUT = os.path.join(HERE, "..", "results", "dreyer_trials.csv")
MEMBER = re.compile(r"([A-C]\d+)_(R\d)_onlineT\.gdf$")

MONTAGE = ("Fz", "FCz", "Cz", "CPz", "Pz", "C3", "C4", "F3", "F4", "P3", "P4")
MU = ("C3", "C4")
DECODE_CH = ("C3", "C4", "Cz")
EMG_CH = ("EMGg", "EMGd")
CUE_LEFT, CUE_RIGHT = "769", "770"
PRE_CUE_S = 2.0
POST = (0.5, 3.5)
BANDS = ((8.0, 13.0), (13.0, 30.0))

POST_COLS = [f"f{i}" for i in range(len(DECODE_CH) * len(BANDS))]
FIELDS = (["subject", "run", "trial", "y", "cue_s", "n_channels_used"] + SPECTRAL
          + ["mu_c3", "mu_c4", "mu_mean", "mu_lateralisation", "emg_pre"] + POST_COLS)


def _band_power(seg, sfreq):
    from numpy.fft import rfft, rfftfreq
    x = seg - seg.mean(axis=1, keepdims=True)
    w = np.hanning(x.shape[1])
    p = np.abs(rfft(x * w, axis=1)) ** 2
    f = rfftfreq(x.shape[1], 1.0 / sfreq)
    out = []
    for lo, hi in BANDS:
        m = (f >= lo) & (f < hi)
        out.extend(np.log(np.maximum(p[:, m].mean(axis=1), 1e-20)))
    return np.asarray(out, float)


def run_rows(blob, subject, run):
    import mne
    with tempfile.NamedTemporaryFile(suffix=".gdf", delete=False) as fh:
        fh.write(blob)
        path = fh.name
    try:
        raw = mne.io.read_raw_gdf(path, preload=True, verbose="ERROR")
        sf = float(raw.info["sfreq"])
        names = list(raw.ch_names)
        data = raw.get_data() * 1e6                     # mne returns volts; this project works in uV
        ann = raw.annotations
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    idx = {c: names.index(c) for c in set(MONTAGE + MU + DECODE_CH + EMG_CH) if c in names}
    mont = [idx[c] for c in MONTAGE if c in idx]
    if len(mont) < 6:
        raise ValueError(f"only {len(mont)} montage channels in {names[:8]}...")
    dec = [idx[c] for c in DECODE_CH if c in idx]
    if len(dec) != len(DECODE_CH):
        raise ValueError(f"decoder channels missing: {set(DECODE_CH) - set(idx)}")
    emg = [idx[c] for c in EMG_CH if c in idx]

    n_pre = int(round(PRE_CUE_S * sf))
    j0, j1 = int(round(POST[0] * sf)), int(round(POST[1] * sf))
    out = []
    for t, (onset, desc) in enumerate(zip(ann.onset, ann.description)):
        d = str(desc)
        if d not in (CUE_LEFT, CUE_RIGHT):
            continue
        c = int(round(float(onset) * sf))
        if c - n_pre < 0 or c + j1 > data.shape[1]:
            continue
        pre = data[:, c - n_pre:c]
        post = data[dec, c + j0:c + j1]
        block = pre[mont]
        if not (np.isfinite(block).all() and np.isfinite(post).all()):
            continue
        rows = [_spectral(block[k], sf) for k in range(block.shape[0])]
        f = {k: float(np.nanmedian([r[k] for r in rows])) for k in SPECTRAL}
        a3 = _spectral(pre[idx["C3"]], sf)["relative_alpha_power"] if "C3" in idx else float("nan")
        a4 = _spectral(pre[idx["C4"]], sf)["relative_alpha_power"] if "C4" in idx else float("nan")
        f.update({"mu_c3": a3, "mu_c4": a4, "mu_mean": float(np.nanmean([a3, a4])),
                  "mu_lateralisation": (a3 - a4) / (a3 + a4)
                  if np.isfinite(a3 + a4) and (a3 + a4) > 0 else float("nan")})
        # LOG rms: raw EMG amplitude carries a subject-specific gain and is not a magnitude (rule 57)
        f["emg_pre"] = (float(np.log(np.maximum(np.sqrt(np.mean(pre[emg] ** 2)), 1e-12)))
                        if emg else float("nan"))
        for i, v in enumerate(_band_power(post, sf)):
            f[f"f{i}"] = float(v)
        f.update({"subject": subject, "run": run, "trial": t, "cue_s": float(onset),
                  "y": 1.0 if d == CUE_RIGHT else 0.0, "n_channels_used": len(mont)})
        out.append(f)
    if not out:
        raise ValueError("no usable trials")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    rz = RemoteZip(ZIP_URL)
    want = []
    for m in rz.index():
        mm = MEMBER.search(os.path.basename(m["name"]))
        if not mm:
            continue
        subj, run = mm.group(1), mm.group(2)
        # shard on the numeric part of the subject id -- never hash(), which Python salts per
        # process and would make the sharding non-reproducible (CLAUDE.md conventions)
        if int(re.sub(r"\D", "", subj)) % a.of != a.shard:
            continue
        want.append((subj, run, m["name"]))
    want.sort()

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {(r["subject"], r["run"]) for r in csv.DictReader(fh)}
    todo = [t for t in want if (t[0], t[1]) not in done]
    print(f"shard {a.shard}/{a.of}: {len(want)} runs wanted, {len(done)} done, {len(todo)} to go",
          flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, (subj, run, name) in enumerate(todo, 1):
            try:
                rows = run_rows(rz.read_member(name), subj, run)
                for r in rows:
                    w.writerow({k: r.get(k, "") for k in FIELDS})
                fh.flush()
                print(f"   [{i}/{len(todo)}] {subj} {run}: {len(rows)} trials", flush=True)
            except Exception as e:                                          # noqa: BLE001
                print(f"   [{i}/{len(todo)}] {subj} {run}: FAIL {type(e).__name__}: {e}", flush=True)
    print(f"   wrote -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
