#!/usr/bin/env python3
"""Mechanical extraction of 12 x 5-stage x 19-subject epoch samples from ds006695, by HTTP byte range.

NOT an experiment. This script only fetches bytes and writes them out; it makes no claim and computes no
statistic beyond the validation prints the task requires. See `bsde/scripts/ds006695_labels.py` for the
companion that produced `bsde/results/ds006695_hypnograms.csv` (subject, n_epochs per stage) this script
depends on for the >=12-per-stage feasibility check, and for the original MAT5-byte-range technique this
script generalizes.

WHY BYTE RANGE. ds006695 is 10.05 GB across 19 subjects; each subject's `.set` file alone is 283-424 MB
(EEGLAB metadata -- the actual samples live in a companion `.fdt`, 171-247 MB per subject here). Downloading
either whole file to reach a few hundred 30 s epochs would cost ~10 GB for ~1140 epochs x 3 channels x 30 s
(~205 MB of actual signal). MAT5 is a flat, self-describing sequence of tagged elements (each tag carries
its own byte length), so the `.set` can be WALKED without loading it, and the `.fdt` is a flat sample-major
float32 array that supports exact byte-range addressing per epoch.

MAT5 DETAIL BEYOND THE LABELS SCRIPT. This deposit's `.set` files were saved with something equivalent to
MATLAB's `save(file, '-struct', 'EEG')`, which unpacks the EEG struct's fields into separate TOP-LEVEL MAT5
variables (`setname`, `nbchan`, `pnts`, `srate`, ..., `chanlocs`, ..., `VisualHypnogram`, ...) rather than one
nested struct -- confirmed empirically by walking sub-101 and printing every top-level tag's decoded name.
The labels script's tag walker has a latent bug that this script had to fix to use: it assumes every array-name
subelement uses the regular (tag, length, data) MAT5 layout, but MAT5 uses a compact "Small Data Element"
(SDE) encoding for any subelement payload <= 4 bytes, which is exactly the case for the fields with 4-letter
names this script needs (`pnts`, `xmin`, `xmax`, `data`). Under SDE the type+length are packed into the first
4-byte word and the payload sits in the next 4 bytes directly, with no separate 8-byte data tag. The labels
script never hit this because "VisualHypnogram" (16 chars) is far past the SDE threshold; `read_tag` below
handles both forms and was verified against sub-101 by decoding `nbchan`/`pnts`/`srate` with scipy.io.loadmat
and cross-checking pnts/srate/3600 against the companion hypnogram's `hours` column.

    python bsde/scripts/ds006695_signal.py \
        --out-npz bsde/results/ds006695_epochs.npz \
        --out-csv bsde/results/ds006695_epoch_index.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import struct
import sys
import urllib.request

BASE = "https://s3.amazonaws.com/openneuro.org/ds006695"
SUBJECTS = ("101", "102", "104", "105", "106", "107", "109", "110", "111", "112",
            "114", "116", "117", "119", "122", "123", "124", "125", "126")
STAGE_CODE = {"W": 1, "REM": 2, "N1": 3, "N2": 4, "N3": 5}   # 0 = UNKNOWN/movement, dropped -- see labels script
STAGES = ("W", "REM", "N1", "N2", "N3")
EPOCH_SEC = 30
N_PICK = 12
MI_MATRIX = 14
DEPOSIT_BYTES = 10.05e9

WANT_VARS = frozenset({"nbchan", "pnts", "srate", "chanlocs", "VisualHypnogram"})


def _rng(url: str, a: int, b: int) -> bytes:
    r = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
    return urllib.request.urlopen(r, timeout=180).read()


def _head_len(url: str) -> int:
    r = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(r, timeout=180) as resp:
        cl = resp.headers.get("Content-Length")
    if cl is None:
        raise RuntimeError(f"no Content-Length header from HEAD {url}")
    return int(cl)


def read_tag(buf: bytes, pos: int):
    """Read one MAT5 tag at local offset `pos`, handling the Small Data Element (SDE) form.

    Returns (dtype, payload_nbytes, payload_start_local_offset, next_tag_local_offset).
    Regular form: 4-byte dtype, 4-byte length, then length bytes padded to a multiple of 8.
    SDE form (payload <= 4 bytes): dtype in the low 16 bits and length in the high 16 bits of the
    FIRST 4-byte word, payload in the immediately following 4 bytes, total element exactly 8 bytes.
    """
    v1, v2 = struct.unpack_from("<II", buf, pos)
    if (v1 >> 16) != 0:
        dt = v1 & 0xFFFF
        nb = (v1 >> 16) & 0xFFFF
        return dt, nb, pos + 4, pos + 8
    dt = v1
    nb = v2
    pad = ((nb + 7) // 8) * 8
    return dt, nb, pos + 8, pos + 8 + pad


def walk_vars(url: str, want, max_vars: int = 90):
    """Walk top-level MAT5 elements, fetching the byte range of each named variable in `want`.

    Returns (decoded: dict[name -> ndarray-ish via scipy.io.loadmat], fetched_bytes: int).
    Stops as soon as every wanted name has been found, or after `max_vars` top-level elements.
    """
    import scipy.io as sio

    want = set(want)
    head = _rng(url, 0, 127)
    fetched = len(head)
    pos = 128
    found = {}
    n = 0
    while n < max_vars and len(found) < len(want):
        t = _rng(url, pos, pos + 7)
        fetched += 8
        if len(t) < 8:
            break
        dt, nb = struct.unpack("<II", t)
        if dt != MI_MATRIX:
            break
        h = _rng(url, pos + 8, pos + 8 + 127)
        fetched += 128
        _fdt, _fnb, _fds, fnext = read_tag(h, 0)     # array flags subelement
        _ddt, _dnb, _dds, dnext = read_tag(h, fnext)  # dimensions subelement
        _ndt, nnb, nds, _nnext = read_tag(h, dnext)   # array name subelement
        name = h[nds:nds + nnb].decode("latin-1", errors="replace")
        if name in want and name not in found:
            blob = _rng(url, pos, pos + nb + 7)
            fetched += nb + 8
            found[name] = sio.loadmat(io.BytesIO(head + blob))[name]
        pos += 8 + ((nb + 7) // 8) * 8
        n += 1
    missing = want - found.keys()
    if missing:
        raise RuntimeError(f"variables not found within {max_vars} top-level elements: {sorted(missing)}")
    return found, fetched


def channel_labels(chanlocs_struct) -> list:
    return [str(chanlocs_struct[0, i]["labels"][0]) for i in range(chanlocs_struct.shape[1])]


def pick_epochs(avail, n_pick: int = N_PICK):
    """Evenly-spaced deterministic selection over sorted available epoch indices."""
    import numpy as np
    idx_pos = np.unique(np.round(np.linspace(0, avail.size - 1, n_pick)).astype(int))
    return avail[idx_pos], idx_pos.size


def main() -> int:
    import numpy as np

    ap = argparse.ArgumentParser()
    ap.add_argument("--out-npz", default="bsde/results/ds006695_epochs.npz")
    ap.add_argument("--out-csv", default="bsde/results/ds006695_epoch_index.csv")
    ap.add_argument("--subjects", nargs="*", default=list(SUBJECTS))
    a = ap.parse_args()

    npz_arrays = {}
    rows = []
    subject_labels = {}
    subject_epochs = {}     # sub -> list of (nbchan, n_samples) arrays, for RMS
    total_bytes = 0

    for s in a.subjects:
        set_url = f"{BASE}/sub-{s}/eeg/sub-{s}_task-sleep_eeg.set"
        fdt_url = f"{BASE}/sub-{s}/eeg/sub-{s}_task-sleep_eeg.fdt"

        found, fetched = walk_vars(set_url, WANT_VARS)
        total_bytes += fetched
        nbchan = int(np.asarray(found["nbchan"]).ravel()[0])
        pnts = int(np.asarray(found["pnts"]).ravel()[0])
        srate = int(np.asarray(found["srate"]).ravel()[0])
        hyp = np.asarray(found["VisualHypnogram"]).ravel().astype(int)
        labels = channel_labels(found["chanlocs"])
        assert len(labels) == nbchan, f"sub-{s}: chanlocs has {len(labels)} labels but nbchan={nbchan}"
        subject_labels[s] = labels

        samples_per_epoch = EPOCH_SEC * srate
        n_full_epochs = pnts // samples_per_epoch
        usable_len = min(hyp.size, n_full_epochs)
        assert usable_len > 0, f"sub-{s}: no full 30 s epochs available (pnts={pnts}, srate={srate})"
        hyp_al = hyp[:usable_len]

        expected_fdt_bytes = nbchan * pnts * 4
        actual_fdt_bytes = _head_len(fdt_url)
        if actual_fdt_bytes != expected_fdt_bytes:
            sys.exit(
                f"ABORT sub-{s}: .fdt size mismatch. expected nbchan({nbchan}) * pnts({pnts}) * 4 = "
                f"{expected_fdt_bytes} bytes, HTTP HEAD Content-Length reports {actual_fdt_bytes}. "
                f"Refusing to guess a layout -- fix the source of nbchan/pnts or re-check the file."
            )

        print(f"sub-{s}: nbchan={nbchan} pnts={pnts} srate={srate} hyp_epochs={hyp.size} "
              f"full_data_epochs={n_full_epochs} usable={usable_len} labels={labels} "
              f"fdt_bytes={actual_fdt_bytes} (OK)", flush=True)

        subject_epochs[s] = []
        for stage in STAGES:
            code = STAGE_CODE[stage]
            avail = np.where(hyp_al == code)[0]
            print(f"  sub-{s} {stage}: n_avail={avail.size}", flush=True)
            assert avail.size > 0, f"sub-{s} {stage}: zero available epochs -- filter matched nothing"
            assert avail.size >= N_PICK, (
                f"sub-{s} {stage}: only {avail.size} available epochs, need >= {N_PICK}. Aborting "
                f"rather than silently taking fewer."
            )
            chosen, n_chosen = pick_epochs(avail, N_PICK)
            assert n_chosen == N_PICK, (
                f"sub-{s} {stage}: evenly-spaced linspace selection produced {n_chosen} unique indices "
                f"(avail={avail.size}), need exactly {N_PICK}."
            )

            for epoch_index in chosen:
                epoch_index = int(epoch_index)
                start_sample = epoch_index * samples_per_epoch
                end_sample = start_sample + samples_per_epoch
                byte_start = start_sample * nbchan * 4
                byte_end = end_sample * nbchan * 4 - 1
                raw = _rng(fdt_url, byte_start, byte_end)
                expected_n = samples_per_epoch * nbchan * 4
                assert len(raw) == expected_n, (
                    f"sub-{s} {stage} epoch {epoch_index}: fetched {len(raw)} bytes, expected {expected_n}"
                )
                arr = np.frombuffer(raw, dtype="<f4").reshape(samples_per_epoch, nbchan).T.copy()
                key = f"sub-{s}__{stage}__{epoch_index}"
                npz_arrays[key] = arr
                subject_epochs[s].append(arr)
                total_bytes += len(raw)
                rows.append({
                    "subject": f"sub-{s}", "stage": stage, "epoch_index": epoch_index,
                    "t_start_s": epoch_index * EPOCH_SEC, "n_channels": nbchan,
                    "sfreq": srate, "bytes_fetched": len(raw),
                })

    assert rows, "no epoch rows produced at all -- filter matched nothing across every subject"
    print(f"\nextracted {len(rows)} epochs across {len(a.subjects)} subjects "
          f"({len(rows) // len(a.subjects) if a.subjects else 0} per subject expected "
          f"{len(STAGES) * N_PICK})", flush=True)

    np.savez_compressed(a.out_npz, **npz_arrays)
    with open(a.out_csv, "w", newline="") as fh:
        cols = ["subject", "stage", "epoch_index", "t_start_s", "n_channels", "sfreq", "bytes_fetched"]
        w = csv.DictWriter(fh, cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote -> {a.out_npz}")
    print(f"wrote -> {a.out_csv}")

    # ---------------------------------------------------------------------------------------------
    # MANDATORY VALIDATION
    # ---------------------------------------------------------------------------------------------
    print("\n=== VALIDATION 1: independent byte-range re-read, different offset arithmetic ===")
    val_sub = a.subjects[0]
    val_rows = [r for r in rows if r["subject"] == f"sub-{val_sub}" and r["stage"] == "W"]
    assert val_rows, f"no stage-W rows for sub-{val_sub} to validate against"
    val_row = min(val_rows, key=lambda r: r["epoch_index"])
    v_idx = val_row["epoch_index"]
    v_key = f"sub-{val_sub}__W__{v_idx}"
    original = npz_arrays[v_key]

    found2, _ = walk_vars(f"{BASE}/sub-{val_sub}/eeg/sub-{val_sub}_task-sleep_eeg.set",
                           {"nbchan", "pnts", "srate"})
    nbchan2 = int(np.asarray(found2["nbchan"]).ravel()[0])
    srate2 = int(np.asarray(found2["srate"]).ravel()[0])
    samples_per_epoch2 = EPOCH_SEC * srate2

    # Different arithmetic: cumulative addition instead of multiplication, and fetch TWO epochs at once
    # (this epoch plus its neighbour) via one contiguous range, then slice out the overlap.
    cum_start_sample = 0
    for _ in range(v_idx):
        cum_start_sample += samples_per_epoch2
    wide_byte_start = cum_start_sample * nbchan2 * 4
    wide_n_samples = 2 * samples_per_epoch2
    wide_byte_end = wide_byte_start + wide_n_samples * nbchan2 * 4 - 1
    wide_raw = _rng(f"{BASE}/sub-{val_sub}/eeg/sub-{val_sub}_task-sleep_eeg.fdt",
                     wide_byte_start, wide_byte_end)
    wide_arr = np.frombuffer(wide_raw, dtype="<f4").reshape(wide_n_samples, nbchan2).T
    overlap = wide_arr[:, :samples_per_epoch2]
    max_abs_diff = float(np.max(np.abs(overlap - original)))
    print(f"sub-{val_sub} epoch {v_idx} (stage W): original shape {original.shape}, "
          f"wide-range overlap shape {overlap.shape}")
    print(f"max abs difference (must be exactly 0.0): {max_abs_diff}")
    assert max_abs_diff == 0.0, "byte-range re-read did NOT match -- extraction is not verified"

    print("\n=== VALIDATION 2: per-subject per-channel RMS in native (file) units ===")
    all_rms = []
    for s in a.subjects:
        stacked = np.concatenate(subject_epochs[s], axis=1)  # (nbchan, total_samples)
        rms = np.sqrt(np.mean(stacked.astype(np.float64) ** 2, axis=1))
        all_rms.append(rms)
        print(f"sub-{s}: RMS per channel {np.array2string(rms, precision=6, floatmode='fixed')}")
    all_rms = np.stack(all_rms, axis=0)
    grand_rms = float(np.mean(all_rms))
    print(f"grand mean RMS across all subjects/channels: {grand_rms:.6g}")
    if grand_rms < 1e-3:
        unit_guess = "volts (~1e-5 scale)"
    elif 1 <= grand_rms <= 1000:
        unit_guess = "microvolts (~10 scale)"
    else:
        unit_guess = "UNRECOGNIZED scale -- neither ~1e-5 (V) nor ~10 (uV)"
    print(f"native-unit interpretation: {unit_guess} (values NOT rescaled)")

    print("\n=== VALIDATION 3: total bytes fetched vs deposit size ===")
    print(f"total bytes fetched this run: {total_bytes} ({total_bytes / 1e9:.4f} GB)")
    print(f"stated deposit size: {DEPOSIT_BYTES / 1e9:.2f} GB")
    print(f"fraction of deposit actually transferred: {total_bytes / DEPOSIT_BYTES * 100:.4f}%")

    print("\n=== VALIDATION 4: channel labels ===")
    print(f"sub-101 channel labels (verbatim): {subject_labels.get('101', subject_labels[a.subjects[0]])}")
    uniq_label_sets = {tuple(v) for v in subject_labels.values()}
    if len(uniq_label_sets) == 1:
        print(f"channel labels IDENTICAL across all {len(subject_labels)} subjects: {list(uniq_label_sets)[0]}")
    else:
        print(f"channel labels DIFFER across subjects -- {len(uniq_label_sets)} distinct sets found:")
        for s, labs in subject_labels.items():
            print(f"  sub-{s}: {labs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
