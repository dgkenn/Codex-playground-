"""Cue-locked sensorimotor ERD on ds007554 -- the instrument E82's gate said was missing.

WHY. E82 asked whether anything separates covert command-following (`motorimagery`) from passive
stimulation (`passivemotor`) within subject, and **its overt anchor failed**: `activemotor` versus
`passivemotor` gave the incumbent `relative_alpha_power` d_z = +0.393 [-0.028, +0.934], an interval
including zero with the wrong sign for sensorimotor ERD. The gate refused the primary, correctly -- a null
on covert attempt means nothing if overt movement is undetectable.

**The diagnosis was the reduction, not the deposit.** `ds007554_features.csv` holds ONE whole-recording
summary per run, median-reduced across 33 channels. Alpha ERD is transient (about a second around movement
onset), cue-locked, and focal to the sensorimotor strip. That reduction removes all three properties.

WHAT THIS PASS CHANGES, and it is ONE instrument change, named (rule 58): whole-run median over all
channels -> **cue-locked epochs on sensorimotor channels, each trial expressed against its own pre-cue
baseline.** Nothing else moves: same deposit, same three tasks, same subjects, same sessions.

VERIFIED BEFORE WRITING THIS, against the deposit rather than from memory (rules 25/39):

    every run ships `*_events.tsv`     onset / duration / trial_type, 19 `target` events in the first run
    every run ships `*_channels.tsv`   32 channels including C1 C2 C3 C4 Cz FC3 FC4 CP1 CP2 -- full
                                       sensorimotor coverage, so the focal requirement is satisfiable

THE STATISTIC, fixed here before any value exists. For each `target` onset:

    ERD = log10( mean alpha power over POST seconds / mean alpha power over PRE seconds )

with PRE = [-2.0, -0.5] s and POST = [+0.5, +2.5] s relative to onset, alpha = 8-13 Hz, averaged over
`SENSORIMOTOR` channels present in that run, then averaged over trials to one value per run. Expressing
each trial against its OWN baseline is what makes this a within-trial contrast rather than another
between-run amplitude comparison -- a subject-specific or session-specific gain cancels in the ratio
(rule 57).

A whole-head control column, `erd_wholehead`, is written beside it using the identical timing on every
channel. It exists so the successor experiment can ask whether any effect is sensorimotor-specific or
merely global arousal, which is the objection a bilateral ERD invites.

    python bsde/scripts/extract_ds007554_erd.py
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.ingestion.openneuro_s3 import list_all_keys                       # noqa: E402

BUCKET_URL = "https://s3.amazonaws.com/openneuro.org/"
OUT = os.path.join(HERE, "..", "results", "ds007554_erd.csv")
TC_OUT = os.path.join(HERE, "..", "results", "ds007554_erd_timecourse.csv")
TASKS = ("motorimagery", "passivemotor", "activemotor")
SENSORIMOTOR = ("C1", "C2", "C3", "C4", "CZ", "FC3", "FC4", "CP1", "CP2")
PRE, POST = (-2.0, -0.5), (0.5, 2.5)
ALPHA = (8.0, 13.0)
FIELDS = ["subject", "session", "task", "n_trials", "n_sm_channels", "n_channels",
          "erd_sm", "erd_wholehead", "sfreq"]

# --- time course, added 2026-07-31 for E85 -------------------------------------------------------------
# E83's anchor failed and the literature says why: PMID 31425038 shows passive haptic movement elicits mu
# and beta ERD of its own, and PMID 27529874 finds that under volition "ERDs began EARLIER". A fixed
# [+0.5, +2.5] s average cannot see a latency difference. These bins make the time course available so a
# successor can use an EARLY window and a latency estimate instead of one late average. The two columns
# above are unchanged and the existing table is not rewritten.
BIN_S = 0.25
TC_FROM, TC_TO = -2.0, 4.0
N_BINS = int(round((TC_TO - TC_FROM) / BIN_S))
TC_FIELDS = (["subject", "session", "task", "n_trials", "n_sm_channels"]
             + [f"b{i:02d}" for i in range(N_BINS)])

KEY = re.compile(r"ds007554/(sub-\d+)/(ses-\d+)/eeg/\1_\2_task-([a-z]+)_eeg\.edf$")


def _get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read()


def events_onsets(base):
    txt = _get(base + "_events.tsv").decode("utf8", "replace").splitlines()
    if not txt:
        return []
    hdr = txt[0].split("\t")
    if "onset" not in hdr:
        return []
    io_ = hdr.index("onset")
    out = []
    for line in txt[1:]:
        p = line.split("\t")
        if len(p) > io_:
            try:
                out.append(float(p[io_]))
            except ValueError:
                pass
    return out


def channel_names(base):
    txt = _get(base + "_channels.tsv").decode("utf8", "replace").splitlines()
    return [l.split("\t")[0].strip() for l in txt[1:] if l.strip()]


def band_power(x, sfreq, lo, hi):
    if x.size < 16:
        return float("nan")
    w = np.hanning(x.size)
    f = np.fft.rfftfreq(x.size, 1.0 / sfreq)
    p = np.abs(np.fft.rfft((x - x.mean()) * w)) ** 2
    m = (f >= lo) & (f <= hi)
    return float(p[m].mean()) if m.any() else float("nan")


def run_erd(edf_bytes, onsets, labels):
    import mne
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".edf", delete=False) as fh:
        fh.write(edf_bytes)
        path = fh.name
    try:
        raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
        sf = float(raw.info["sfreq"])
        data = raw.get_data() * 1e6                      # mne reads volts; this project works in uV
        names = [c.strip().upper() for c in raw.ch_names]
    finally:
        os.unlink(path)
    if len(labels) == data.shape[0]:
        names = [c.strip().upper() for c in labels]
    sm = [i for i, c in enumerate(names) if c in SENSORIMOTOR]
    n = data.shape[1]

    def erd_over(idx):
        vals = []
        for t in onsets:
            a0, a1 = int((t + PRE[0]) * sf), int((t + PRE[1]) * sf)
            b0, b1 = int((t + POST[0]) * sf), int((t + POST[1]) * sf)
            if a0 < 0 or b1 > n:
                continue
            pre = np.nanmean([band_power(data[c, a0:a1], sf, *ALPHA) for c in idx])
            post = np.nanmean([band_power(data[c, b0:b1], sf, *ALPHA) for c in idx])
            if np.isfinite(pre) and np.isfinite(post) and pre > 0 and post > 0:
                vals.append(np.log10(post / pre))
        return (float(np.mean(vals)) if vals else float("nan")), len(vals)

    def timecourse(idx):
        """Mean over trials of log10(bin alpha power / that trial's own pre-cue baseline), per bin."""
        acc = [[] for _ in range(N_BINS)]
        for t in onsets:
            a0, a1 = int((t + PRE[0]) * sf), int((t + PRE[1]) * sf)
            if a0 < 0 or int((t + TC_TO) * sf) > n:
                continue
            base = np.nanmean([band_power(data[c, a0:a1], sf, *ALPHA) for c in idx])
            if not np.isfinite(base) or base <= 0:
                continue
            for b in range(N_BINS):
                s0 = int((t + TC_FROM + b * BIN_S) * sf)
                s1 = int((t + TC_FROM + (b + 1) * BIN_S) * sf)
                v = np.nanmean([band_power(data[c, s0:s1], sf, *ALPHA) for c in idx])
                if np.isfinite(v) and v > 0:
                    acc[b].append(np.log10(v / base))
        return [float(np.mean(a)) if a else float("nan") for a in acc]

    e_sm, n_tr = erd_over(sm) if sm else (float("nan"), 0)
    e_wh, _ = erd_over(list(range(data.shape[0])))
    tc = timecourse(sm) if sm else [float("nan")] * N_BINS
    return {"erd_sm": e_sm, "erd_wholehead": e_wh, "n_trials": n_tr,
            "n_sm_channels": len(sm), "n_channels": data.shape[0], "sfreq": sf,
            "_tc": tc}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--tc-out", default=TC_OUT, dest="tc_out")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)

    keys = [k for k in list_all_keys("openneuro.org", "ds007554/") if KEY.match(k)]
    want = [(m.group(1), m.group(2), m.group(3), k)
            for k, m in ((k, KEY.match(k)) for k in keys) if m.group(3) in TASKS]
    want.sort()
    if a.limit:
        want = want[:a.limit]
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {(r["subject"], r["session"], r["task"]) for r in csv.DictReader(fh)}
    todo = [t for t in want if (t[0], t[1], t[2]) not in done]
    print(f"{len(want)} runs across {len(TASKS)} tasks, {len(done)} done, {len(todo)} to go", flush=True)

    tc_path = os.path.abspath(a.tc_out)
    tc_done = set()
    if os.path.exists(tc_path) and os.path.getsize(tc_path) > 0:
        with open(tc_path, newline="") as fh:
            tc_done = {(r["subject"], r["session"], r["task"]) for r in csv.DictReader(fh)}
    todo = [t for t in want if (t[0], t[1], t[2]) not in done or (t[0], t[1], t[2]) not in tc_done]
    print(f"   {len(todo)} runs to (re)compute once the time course is included", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    tc_new = not os.path.exists(tc_path) or os.path.getsize(tc_path) == 0
    tcfh = open(tc_path, "a", newline="")
    tcw = csv.DictWriter(tcfh, fieldnames=TC_FIELDS)
    if tc_new:
        tcw.writeheader()
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, (sub, ses, task, key) in enumerate(todo, 1):
            base = BUCKET_URL + key[:-len("_eeg.edf")]
            try:
                onsets = events_onsets(base)
                if not onsets:
                    print(f"   [{i}/{len(todo)}] {sub} {ses} {task}: SKIP no events", flush=True)
                    continue
                labels = channel_names(base)
                row = run_erd(_get(BUCKET_URL + key), onsets, labels)
            except Exception as e:                                          # noqa: BLE001
                print(f"   [{i}/{len(todo)}] {sub} {ses} {task}: FAIL {type(e).__name__}: {e}", flush=True)
                continue
            row.update({"subject": sub, "session": ses, "task": task})
            if (sub, ses, task) not in done:
                w.writerow({k: row.get(k, "") for k in FIELDS})
                fh.flush()
            if (sub, ses, task) not in tc_done:
                tr = {"subject": sub, "session": ses, "task": task,
                      "n_trials": row["n_trials"], "n_sm_channels": row["n_sm_channels"]}
                tr.update({f"b{i:02d}": f"{v:.6g}" for i, v in enumerate(row["_tc"])})
                tcw.writerow(tr)
                tcfh.flush()
            print(f"   [{i}/{len(todo)}] {sub} {ses} {task}: {row['n_trials']} trials, "
                  f"{row['n_sm_channels']} SM ch, erd_sm {row['erd_sm']:+.4f}", flush=True)
    tcfh.close()
    print(f"   wrote -> {out_path} and {tc_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
