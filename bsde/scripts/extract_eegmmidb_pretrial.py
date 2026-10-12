"""PER-TRIAL PRE-CUE features from eegmmidb, for an EXTERNAL replication of E172.

WHY. E172 found that pre-cue alpha amplitude is higher before a followed command, on matched adjacent
hit/miss pairs in Stieger's online BCI (0.5176 [0.5054, 0.5303], p = 0.0060). That is one deposit, one
paradigm, one montage. eegmmidb is a different deposit, a different paradigm (offline motor imagery with no
feedback), a different montage (64 channels at 160 Hz) and 104 different subjects — so it is the external
test, and it needs a table this project does not have.

WHAT IS EXTRACTED, per trial:
  * the PRE-CUE window, `onset - 2.0 .. onset` s, the same 2 s length E172 used, with the same spectral
    panel and the same C3/C4 mu variables. **`_spectral` is imported from the Stieger extractor rather
    than reimplemented**, so the two deposits' features are the same computation by construction and not
    by agreement (rule 20).
  * the POST-CUE features the decoder uses, `onset + 0.5 .. onset + 3.5`, imported unchanged from
    `build_eegmmidb_bci_label` — `_band_power`, `CHANNELS`, `EPOCH` — so a per-trial CORRECTNESS label can
    be computed downstream from the same rows without a second S3 pass.
  * `y`, the class (T1 left fist = 0, T2 right fist = 1), the subject, run and trial index.

THE LABEL DIFFERENCE, STATED HERE BECAUSE IT IS THE MAIN LIMITATION. Stieger's trials have a behavioural
outcome: the cursor hits the target or it times out. eegmmidb has no feedback, so "was the command
followed" can only mean "was the covert command LEGIBLE in this trial", i.e. did a cross-validated decoder
classify it correctly. That is a weaker construct and a fair one for covert consciousness — a bedside
assessment also has no behavioural readout and asks exactly whether the response is detectable.

One HTTP read per RUN, not per trial, following the builder's own note: a run is 125 s of 64 channels at
160 Hz, and reading it whole is both cheaper than 45 slices and the only way the epoch boundaries come
from one consistent decode.

    for k in 0 1 2 3; do
      python bsde/scripts/extract_eegmmidb_pretrial.py --shard $k --of 4 \
             --out bsde/results/eegmmidb_pretrial.s$k.csv &
    done; wait
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.ingestion.eegmmidb import (IMAGERY_LR_RUNS, events, read_window,      # noqa: E402
                                     record_duration_s, subjects)
from build_eegmmidb_bci_label import CHANNELS, EPOCH, _band_power               # noqa: E402
from extract_stieger_features import SPECTRAL, _spectral                        # noqa: E402

OUT = os.path.join(HERE, "..", "results", "eegmmidb_pretrial.csv")
PRE_CUE_S = 2.0
POST = [f"f{i}" for i in range(6)]
FIELDS = (["subject", "run", "trial", "y", "n_channels_used"] + SPECTRAL
          + ["mu_c3", "mu_c4", "mu_mean", "mu_lateralisation"] + POST)


def subject_rows(sub):
    out = []
    for run in IMAGERY_LR_RUNS:
        ev = events(sub, run)
        full, names, sf, _ = read_window(sub, run, 0.0, record_duration_s(sub, run))
        full = np.asarray(full, float)
        ch_idx = [names.index(c) for c in CHANNELS if c in names]
        if len(ch_idx) < len(CHANNELS):
            raise ValueError(f"montage lacks {set(CHANNELS) - set(names)}")
        c3, c4 = names.index("C3.."), names.index("C4..")
        n_pre = int(round(PRE_CUE_S * sf))
        n_ep = int(round((EPOCH[1] - EPOCH[0]) * sf))
        for t, (onset, label, _d) in enumerate(ev):
            if label == "T0":
                continue
            i0 = int(round(onset * sf)) - n_pre
            j0 = int(round((onset + EPOCH[0]) * sf))
            if i0 < 0:
                continue
            pre = full[:, i0:i0 + n_pre]
            post = full[ch_idx, j0:j0 + n_ep]
            if pre.shape[1] < n_pre or post.shape[1] < n_ep:
                continue
            block = pre[ch_idx]
            if not (np.isfinite(block).all() and np.isfinite(post).all()):
                continue
            rows = [_spectral(block[k], sf) for k in range(block.shape[0])]
            f = {k: float(np.nanmedian([r[k] for r in rows])) for k in SPECTRAL}
            a3 = _spectral(pre[c3], sf)["relative_alpha_power"]
            a4 = _spectral(pre[c4], sf)["relative_alpha_power"]
            f.update({"mu_c3": a3, "mu_c4": a4, "mu_mean": float(np.nanmean([a3, a4])),
                      "mu_lateralisation": (a3 - a4) / (a3 + a4)
                      if np.isfinite(a3 + a4) and (a3 + a4) > 0 else float("nan")})
            bp = _band_power(post, sf)
            for i, v in enumerate(np.asarray(bp, float).ravel()[:6]):
                f[f"f{i}"] = float(v)
            f.update({"subject": sub, "run": run, "trial": t, "y": 1.0 if label == "T2" else 0.0,
                      "n_channels_used": len(ch_idx)})
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

    subs = [s for i, s in enumerate(subjects()) if i % a.of == a.shard]
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["subject"] for r in csv.DictReader(fh)}
    todo = [s for s in subs if s not in done]
    print(f"shard {a.shard}/{a.of}: {len(subs)} subjects, {len(done)} done, {len(todo)} to go", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, sub in enumerate(todo, 1):
            try:
                rows = subject_rows(sub)
                for r in rows:
                    w.writerow({k: r.get(k, "") for k in FIELDS})
                fh.flush()
                print(f"   [{i}/{len(todo)}] {sub}: {len(rows)} trials", flush=True)
            except Exception as e:                                          # noqa: BLE001
                print(f"   [{i}/{len(todo)}] {sub}: FAIL {type(e).__name__}: {e}", flush=True)
    print(f"   wrote -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
