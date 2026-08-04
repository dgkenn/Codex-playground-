"""PER-TRIAL pre-cue features from Stieger 2021 — one row per trial, not one row per session.

WHY THIS TABLE EXISTS. `extract_stieger_features.py` already reads exactly the right segment: `BCI.time`
runs -2000 ... +9040 ms, so every trial carries **2 s of pre-cue spontaneous EEG**. It then takes the
median across up to 120 trials and emits ONE row per session. Every Challenge B result this project has
produced — thirty ledger rows — predicts a SUBJECT-LEVEL TRAIT from that collapsed row: "is this person a
good BCI user?"

**The trial-level structure was computed and thrown away, and it answers a different and more clinically
apt question:** given the spontaneous state in the two seconds before a cue, is THIS trial's command
followed? A bedside assessment of a patient with a disorder of consciousness does not ask whether the
patient is a good BCI user; it asks whether the command response is present in this moment. That question
uses each subject as their own control and has ~450 observations per session instead of one.

WHAT IS EXTRACTED
    per trial   the 2 s pre-cue segment, spectral panel taken as the median over a 10-electrode montage,
                plus the sensorimotor mu variables the SMR literature actually names (C3/C4 relative
                alpha, and their lateralisation), which the montage median cannot express
    per trial   `result` (hit/miss), `forcedresult`, `artifact`, `triallength`, `targetnumber`,
                `tasknumber`, `runnumber`, and the trial's index within the session

WHAT IS DELIBERATELY NOT EXTRACTED. The connectivity and graph families. A 2 s window admits four 0.5 s
sub-windows, which is too few for a stable wPLI, and error-catalogue rule 60 / E73 established that this
project's alpha graph measures are mean connectivity strength restated (r = +0.9962 with mean degree). A
per-trial version would be a noisier copy of a family already shown to be redundant.

COST. 620 MB per session file, streamed and deleted. Resumable on (subject, session) and shardable by
subject, following the convention in `results/IN_FLIGHT.md`.

    for k in 0 1 2 3; do
      python bsde/scripts/extract_stieger_trials.py --sessions-per-subject 1 --shard $k --of 4 \
             --out bsde/results/stieger_trials.s$k.csv &
    done; wait
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from extract_stieger_features import MONTAGE, SFREQ, PRE_CUE_S, SPECTRAL, _spectral  # noqa: E402
from extract_stieger_labels import NAME, file_index                                  # noqa: E402

OUT = os.path.join(HERE, "..", "results", "stieger_trials.csv")
MU = ("C3", "C4")

TRIAL_COLS = ["result", "forcedresult", "artifact", "triallength", "targetnumber",
              "tasknumber", "runnumber"]
FIELDS = (["subject", "session", "trial", "n_channels_used"] + TRIAL_COLS + SPECTRAL
          + ["mu_c3", "mu_c4", "mu_mean", "mu_lateralisation"])


def _get(t, name):
    try:
        v = getattr(t, name)
    except AttributeError:
        return float("nan")
    try:
        return float(np.atleast_1d(v)[0])
    except (TypeError, ValueError, IndexError):
        return float("nan")


def trial_rows(path, subject, session, max_trials):
    from scipy.io import loadmat
    bci = loadmat(path, struct_as_record=False, squeeze_me=True)["BCI"]
    labels = [str(x) for x in np.atleast_1d(bci.chaninfo.label)]
    idx = {}
    for want in tuple(MONTAGE) + MU:
        for j, lab in enumerate(labels):
            if lab.strip().upper() == want.upper():
                idx[want] = j
                break
    if len(idx) < 6:
        raise ValueError(f"only {len(idx)} montage channels found in {labels[:8]}...")
    chans = [idx[c] for c in MONTAGE if c in idx]
    mu_ch = {c: idx[c] for c in MU if c in idx}

    data = bci.data
    td = np.atleast_1d(bci.TrialData)
    n_pre = int(PRE_CUE_S * SFREQ)
    n = min(len(data), len(td), max_trials)
    out = []
    for e in range(n):
        seg = np.asarray(data[e], float)
        if seg.ndim != 2 or seg.shape[1] < n_pre:
            continue
        pre = seg[:, :n_pre]
        block = pre[chans]
        if not np.isfinite(block).all():
            continue
        rows = [_spectral(block[c], SFREQ) for c in range(block.shape[0])]
        f = {k: float(np.nanmedian([r[k] for r in rows])) for k in SPECTRAL}
        mu = {}
        for c, j in mu_ch.items():
            x = pre[j]
            mu[c] = _spectral(x, SFREQ)["relative_alpha_power"] if np.isfinite(x).all() else float("nan")
        c3, c4 = mu.get("C3", float("nan")), mu.get("C4", float("nan"))
        f.update({"mu_c3": c3, "mu_c4": c4, "mu_mean": float(np.nanmean([c3, c4])),
                  # signed, so a positive value means MORE mu over the LEFT sensorimotor cortex
                  "mu_lateralisation": (c3 - c4) / (c3 + c4) if np.isfinite(c3 + c4) and (c3 + c4) > 0
                  else float("nan")})
        for k in TRIAL_COLS:
            f[k] = _get(td[e], k)
        f.update({"subject": subject, "session": session, "trial": e,
                  "n_channels_used": len(chans)})
        out.append(f)
    if not out:
        raise ValueError("no usable trials")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions-per-subject", type=int, default=1, dest="k")
    ap.add_argument("--min-session", type=int, default=1,
                    help="skip sessions below this number -- used to build a HELD-OUT table of later "
                         "sessions without re-downloading the ones already extracted")
    ap.add_argument("--max-trials", type=int, default=500)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--tmp", default="/tmp/eeg_probe/stieger_trials")
    a = ap.parse_args(argv)

    want = []
    for f in file_index():
        m = NAME.match(f["name"])
        if (m and a.min_session <= int(m.group(2)) <= a.k
                and int(m.group(1)) % a.of == a.shard):
            want.append((m.group(1), m.group(2), f))
    want.sort(key=lambda t: (int(t[0]), int(t[1])))

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            # de-duplicate on the key when loading, because a second writer on one CSV has happened here
            # before and produced 419 duplicated ids (error-catalogue rule 56)
            done = {(r["subject"], r["session"]) for r in csv.DictReader(fh)}
    todo = [t for t in want if (t[0], t[1]) not in done]
    print(f"shard {a.shard}/{a.of}: {len(want)} sessions wanted, {len(done)} done, {len(todo)} to go",
          flush=True)

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
                rows = trial_rows(dest, subj, sess, a.max_trials)
                for r in rows:
                    w.writerow({k: r.get(k, "") for k in FIELDS})
                fh.flush()
                hit = np.nanmean([r["result"] for r in rows])
                print(f"   [{i}/{len(todo)}] S{subj} s{sess}: {len(rows)} trials, hit {hit:.3f}",
                      flush=True)
            except Exception as e:                                          # noqa: BLE001
                print(f"   [{i}/{len(todo)}] S{subj} s{sess}: FAIL {type(e).__name__}: {e}", flush=True)
            finally:
                if os.path.exists(dest):
                    os.remove(dest)
    print(f"   wrote -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
