#!/usr/bin/env python3
"""Stream PhysioNet's CAP Sleep Database and emit `whole_head_exponent` per sleep stage per subject.

WHY THIS DEPOSIT. E211 recorded a blocker rather than working around it: the reference recommendation it
validated internally has **no forward test available with local data**, because every deposit carrying
`whole_head_exponent` is either part of a reference, or was a prior transport target, or is awake children.
`capslpdb` is 108 subjects across eight diagnostic groups plus healthy controls, openly licensed
(ODC-By 1.0) and downloadable without credentials — a clinically heterogeneous population, which is the
hard case for a normative reference rather than the convenient one.

**IT IS NOT sleep-edfx.** Sleep-EDF Expanded looks ideal on every axis a dataset search scores and is
disqualified, because `e95_span_reference_deep.sleep_stages()` already reads it: it IS the ladder E198 and
E211 resolve. Testing a recommendation on its own evaluation cohort is the circularity E211 declined.

=========================================================================================================
THE TIME AXIS IS THE PART THAT BREAKS (rules 27, 65)
=========================================================================================================
The scoring is a RemLogic text export keyed to **wall-clock `hh:mm:ss`**; the signal is an EDF whose header
carries its own start time. Aligning them is an offset subtraction with two ways to go silently wrong — a
recording that starts before midnight and runs past it, and a scoring file whose first epoch precedes the
EDF's start. Catalogue rule 65 records that a marker file agreeing with another marker file is not
validation, and that the only check that settles it compares the statistic AT the markers against the same
statistic at random times.

So this extractor carries its own alignment control and **writes it into every row**:

    `delta_ratio_deep_minus_wake` — mean relative delta power in S3+S4 epochs minus that in W epochs, using
    the alignment as computed.

Deep sleep has more delta than wakefulness. That is not in doubt and it is not the finding; it is the
instrument check. A record whose alignment is broken will scramble the stage labels and drive this toward
zero, and a record where it is strongly positive has an alignment that works. **Any downstream experiment
must gate on this column and must not assume it.**

Day rollover is handled explicitly: epoch times are monotone non-decreasing by construction, so a decrease
against the previous epoch adds 24 hours.

=========================================================================================================
CHANNEL SELECTION (rule 61)
=========================================================================================================
CAP is a clinical PSG montage and carries EOG (`ROC-LOC`), EMG (`EMG1-EMG2`), ECG and respiratory channels
alongside EEG derivations, and the montage differs between records. Substring matching a channel name is
exactly the failure rule 61 was written for. Channels are therefore selected by **exact, case-insensitive
membership of an explicit allowlist of EEG derivations**, and every record reports how many it kept. A
record with fewer than `MIN_CH` EEG channels is skipped and NAMED, never silently dropped (rule 14).

    python bsde/scripts/stream_capslpdb.py --out /tmp/eeg_probe/capslpdb_stages.csv --limit 20
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))

BASE = "https://physionet.org/files/capslpdb/1.0.0"
STAGES = ("W", "S1", "S2", "S3", "S4", "R")
EVENT_TO_STAGE = {"SLEEP-S0": "W", "SLEEP-S1": "S1", "SLEEP-S2": "S2",
                  "SLEEP-S3": "S3", "SLEEP-S4": "S4", "SLEEP-REM": "R"}

# EEG derivations observed across clinical PSG montages. Exact match, case-insensitive (rule 61).
EEG_ALLOW = {
    "C3-A2", "C4-A1", "C3A2", "C4A1", "O1-A2", "O2-A1", "F3-A2", "F4-A1",
    "FP1-F3", "F3-C3", "C3-P3", "P3-O1", "FP2-F4", "F4-C4", "C4-P4", "P4-O2",
    "FP1-F7", "F7-T3", "T3-T5", "T5-O1", "FP2-F8", "F8-T4", "T4-T6", "T6-O2",
    "F3-C3", "F4-C4", "C3-O1", "C4-O2", "FP2-F8", "F2-F4", "F1-F3",
    "C3", "C4", "O1", "O2", "F3", "F4", "FP1", "FP2", "P3", "P4",
}

MIN_CH = 2
EPOCH_S = 30.0
MAX_EPOCHS_PER_STAGE = 12

# The panel is the DOSE-I survivor set plus the incumbent and two cheap descriptors. It is fixed here,
# before any analysis of this deposit exists, so that no later design can choose what to extract after
# seeing what would help. `multiscale_entropy_slope` costs roughly a second per epoch and is the reason
# MAX_EPOCHS_PER_STAGE is 12 rather than 40.
PANEL = ("whole_head_exponent", "relative_alpha_power", "multiscale_entropy_slope",
         "spectral_edge_95", "spectral_entropy", "relative_delta_power", "lempel_ziv")


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "bsde-extractor"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as fh:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            fh.write(b)
    return os.path.getsize(dest)


def parse_scoring(text):
    """Return [(seconds_from_first_epoch, stage)] with day rollover resolved by monotonicity.

    THE COLUMN LAYOUT IS READ FROM THE HEADER, NOT ASSUMED. This deposit ships at least three variants of
    the same RemLogic export and the first two parsers I wrote each matched one and silently returned zero
    rows for another:

        n1.txt     `Sleep Stage  Position  Time [hh:mm:ss]  Event  Duration[s]  Location`   22:09:33
        brux1.txt  same columns                                                             22.18.17
        ins1.txt   `Sleep Stage  Time [hh:mm:ss]  Event  Duration[s]  Location`  -- NO Position column

    Hardcoding "time is field 2, event is field 3" is the same mistake as substring-matching a structured
    identifier (rule 61): the fields have names, so read them. Both time separators are accepted.
    """
    out, prev, day = [], None, 0
    i_time = i_event = None
    for line in text.splitlines():
        line = line.replace("\r", "")
        if line.startswith("Sleep Stage"):
            head = [h.strip() for h in re.split(r"\t+", line)]
            for i, h in enumerate(head):
                if h.lower().startswith("time"):
                    i_time = i
                elif h.lower() == "event":
                    i_event = i
            continue
        if i_time is None or i_event is None:
            continue
        parts = re.split(r"\t+", line.strip())
        if len(parts) <= max(i_time, i_event):
            continue
        m = re.match(r"^(\d{1,2})[:.](\d{2})[:.](\d{2})$", parts[i_time].strip())
        ev = parts[i_event].strip()
        if not m or ev not in EVENT_TO_STAGE:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        if prev is not None and t + day * 86400 < prev:
            day += 1
        t += day * 86400
        prev = t
        out.append((t, EVENT_TO_STAGE[ev]))
    return out


def eeg_picks(names):
    want = {w.upper().replace(" ", "") for w in EEG_ALLOW}
    return [i for i, n in enumerate(names) if (n or "").strip().upper().replace(" ", "") in want]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/eeg_probe/capslpdb_stages.csv")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tmp", default="/tmp/capslpdb_work")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args()

    import numpy as np
    import mne
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    from bsde.features.spectral import BANDS
    mne.set_log_level("ERROR")

    # Per-process working directory. Two concurrent copies of this script briefly shared one,
    # which would have had each deleting the other's EDF mid-read -- rule 56, one writer.
    a.tmp = os.path.join(a.tmp, str(os.getpid()))
    os.makedirs(a.tmp, exist_ok=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)

    recs = urllib.request.urlopen(f"{BASE}/RECORDS", timeout=120).read().decode().split()
    # RECORDS lists filenames WITH the .edf extension; the .txt scoring file does not carry it.
    recs = [r.strip()[:-4] if r.strip().endswith(".edf") else r.strip() for r in recs if r.strip()]
    if a.limit:
        recs = recs[: a.limit]
    # The bottleneck here is the DOWNLOAD, not the DSP -- one record took 1 s of CPU in 109 s of
    # wall clock. Sharding by position raises aggregate throughput if PhysioNet throttles per
    # connection; each shard writes its own file and works in its own directory (rule 56).
    if a.of > 1:
        recs = [r for i, r in enumerate(recs) if i % a.of == a.shard]

    done = set()
    if os.path.exists(a.out):
        with open(a.out, newline="") as fh:
            for r in csv.DictReader(fh):
                done.add(r["record"])          # de-duplicate on the key at load (rule 56)
    todo = [r for r in recs if r not in done]
    print(f"{len(recs)} records listed, {len(done)} already done, {len(todo)} to go", flush=True)

    cols = (["record", "subject", "group", "stage", "n_epochs", "n_eeg_channels", "sfreq"]
            + list(PANEL) + ["delta_ratio_deep_minus_wake", "note"])
    new = not os.path.exists(a.out)
    fh_out = open(a.out, "a", newline="")
    w = csv.DictWriter(fh_out, cols)
    if new:
        w.writeheader()

    fns = {nm: REGISTRY.get(nm).fn for nm in PANEL}
    dlo, dhi = BANDS["delta"]

    for rec in todo:
        edf = os.path.join(a.tmp, f"{rec}.edf")
        try:
            txt = urllib.request.urlopen(f"{BASE}/{rec}.txt", timeout=300).read().decode("latin-1")
            epochs = parse_scoring(txt)
            # rule 5: empty is not evidence of absence until the filter is shown able to match.
            if not epochs:
                n_ev = sum(1 for L in txt.splitlines() if "SLEEP-S" in L or "SLEEP-REM" in L)
                w.writerow({"record": rec, "note": f"parser matched 0 rows but the file contains "
                                                   f"{n_ev} SLEEP- event lines"})
                fh_out.flush(); print(f"{rec}: PARSER FAILED on {n_ev} event lines", flush=True)
                continue
            fetch(f"{BASE}/{rec}.edf", edf)
            raw = mne.io.read_raw_edf(edf, preload=False, verbose=False)
            picks = eeg_picks(raw.ch_names)
            if len(picks) < MIN_CH:
                w.writerow({"record": rec, "n_eeg_channels": len(picks),
                            "note": f"only {len(picks)} allow-listed EEG channels: {raw.ch_names[:8]}"})
                fh_out.flush(); os.remove(edf); continue
            sf = float(raw.info["sfreq"])
            t0 = epochs[0][0]
            byst = {}
            for t, st in epochs:
                byst.setdefault(st, []).append(t - t0)

            names = [raw.ch_names[i] for i in picks]
            vals, dvals, counts = {}, {}, {}
            for st, offs in byst.items():
                take = offs[:: max(1, len(offs) // MAX_EPOCHS_PER_STAGE)][:MAX_EPOCHS_PER_STAGE]
                acc = {nm: [] for nm in PANEL}
                dv = []
                for off in take:
                    s0 = int(off * sf)
                    s1 = s0 + int(EPOCH_S * sf)
                    if s0 < 0 or s1 > raw.n_times:
                        continue
                    X = raw.get_data(picks=picks, start=s0, stop=s1) * 1e6
                    if not np.isfinite(X).all() or X.std() < 1e-9:
                        continue
                    for nm, fn in fns.items():
                        try:
                            acc[nm].append(float(fn(X, names, sf, {})))
                        except Exception:
                            pass
                    f = np.fft.rfftfreq(X.shape[1], 1.0 / sf)
                    P = (np.abs(np.fft.rfft(X, axis=1)) ** 2).mean(axis=0)
                    tot = P[(f >= 1.0) & (f <= 45.0)].sum()
                    dv.append(float(P[(f >= dlo) & (f < dhi)].sum() / tot) if tot > 0 else float("nan"))
                med = {}
                for nm in PANEL:
                    good = [x for x in acc[nm] if np.isfinite(x)]
                    med[nm] = float(np.median(good)) if good else float("nan")
                    counts[(st, nm)] = len(good)
                dv = [x for x in dv if np.isfinite(x)]
                if any(np.isfinite(v) for v in med.values()):
                    vals[st] = (med, max(counts[(st, nm)] for nm in PANEL))
                if dv:
                    dvals[st] = float(np.median(dv))

            deep = [dvals[s] for s in ("S3", "S4") if s in dvals]
            ctrl = (float(np.mean(deep)) - dvals["W"]) if (deep and "W" in dvals) else float("nan")
            for st in STAGES:
                if st not in vals:
                    continue
                med, n = vals[st]
                row = {"record": rec, "subject": rec, "group": re.sub(r"\d+$", "", rec),
                       "stage": st, "n_epochs": n, "n_eeg_channels": len(picks), "sfreq": sf,
                       "delta_ratio_deep_minus_wake": f"{ctrl:.6f}", "note": ""}
                for nm in PANEL:
                    row[nm] = f"{med[nm]:.6f}"
                w.writerow(row)
            fh_out.flush()
            print(f"{rec}: {len(picks)} EEG ch, stages {sorted(vals)}, alignment control {ctrl:+.4f}",
                  flush=True)
        except Exception as e:
            w.writerow({"record": rec, "note": f"{type(e).__name__}: {e}"[:200]})
            fh_out.flush()
            print(f"{rec}: FAILED {type(e).__name__}: {e}", flush=True)
        finally:
            if os.path.exists(edf):
                os.remove(edf)     # 40 GB deposit, fixed disk allowance: never keep two records at once
    fh_out.close()
    print(f"wrote -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
