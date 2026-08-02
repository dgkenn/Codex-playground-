"""PER-TRIAL pre-trial features and GRADED tracking outcome from Forenzo & He's continuous-pursuit BCI.

WHY THIS DEPOSIT. E181's surviving Challenge B result is that pre-cue alpha predicts **how well a followed
command is executed**, on a graded scale — discovered on 123 held-out Stieger sessions and confirmed on
session 1. E188 tested E172's *binary* decodability construct on Dreyer 2023 with real EMG channels and
returned ABSENT in both arms, but **it could not test E181**: the Graz paradigm has a fixed feedback period
and therefore no graded execution quality at all. Its arm B used a confidence proxy and was declared as the
weaker analogue before the run.

Continuous pursuit supplies the missing thing directly. A cursor is driven by motor imagery to follow a
randomly drifting target for 60 s, and cursor and target positions are logged at 25 Hz, so **every trial
carries a continuous, graded execution-quality score** rather than a hit or a miss.

FEASIBILITY PROBE, run before this file was written (rule 41), on `S26/S26_Se01_AR_R01.mat`:

    28 subjects (S01-S14 "Main", 8 sessions; S15-S28 "Transfer Learning", 4 sessions), disjoint sets
    62 EEG channels at 1 kHz, Neuroscan/BCI2000, no mastoids and **no EMG channel**
    5 trials of exactly 60.0 s per run, 10 events per run (5 TrialStart / 5 TrialEnd)
    **inter-trial gap 2.28 s before the first trial and 3.20-3.24 s before the rest**, so a 2 s pre-trial
        window fits with room to spare
    per-trial mean cursor-target distance in one probe run: 0.2655 / 0.3601 / 0.2443 / 0.3074 / 0.2874 —
        real within-run spread, which is what the matched adjacent-pair design needs
    .mat files are MATLAB v7.3 (HDF5) and are deflate-compressed inside the zip, so a member must be
        pulled whole (~52 MiB, ~17 s); h5py reads them, scipy.io does not

WHAT IS EXTRACTED, per trial
  * the 2 s PRE-TRIAL window ending at TrialStart, with **`_spectral` imported from the Stieger extractor**
    so the features are the same computation and not merely the same names (rule 20), taken as the median
    over a ten-electrode montage, plus C3/C4 relative alpha and their lateralisation
  * `emg_index`, a CONSTRUCTED proxy over the same window. **This deposit has no EMG channel**, so the
    muscle control here is the proxy rule 57 warns about — it is extracted for continuity with E172/E181
    and is NOT ground truth. E188 is what settles the muscle question, with real EMGg/EMGd channels.
  * the GRADED OUTCOME over the 60 s trial: mean and median cursor-target distance, the fraction of
    samples inside a 0.1-workspace hit radius, and the correlation between cursor velocity and the
    direction to the target — four scorings of the same execution, so a successor cannot pick one after
    the fact without it being visible
  * subject, session, run, decoder, sub-study, trial index within the run, and the pre-trial gap length

SELECTION. Two modes, both outcome-blind with respect to any EEG feature, and both fixed by protocol
rather than by performance. `--session Se01` takes the first session; `--last-session` takes each subject's
FINAL session. Either gives 12-13 runs and ~60 trials per subject, uniform across subjects; the alternative
— taking all sessions — is 109 GB of transfer for a question that needs ~50 matched pairs per subject.

**Se01 turned out to be the wrong choice and `--last-session` exists because of it.** E192 ran on Se01 and
failed its BCI-aliveness gate: pooled cursor-velocity-to-target alignment **−0.0738** against a sign-flip
95th percentile of **+0.0416**, with only **6 of 28 subjects positive**, a median cursor-target distance of
0.4831 where a random pair averages ~0.52, and — for the 14 "Main" subjects — only the traditional AR
decoder present in that session. Execution quality has no estimand when the cursor is not being driven at
the target. The final session is the most-trained one and carries the study's later decoders; that is a
protocol-level criterion, not a ranking on the outcome, and the aliveness gate is unchanged so it can
still fail.

Resumable on (subject, session, run) and shardable by subject.

    for k in 0 1 2 3; do
      python bsde/scripts/extract_cp_trials.py --shard $k --of 4 \
             --out bsde/results/cp_trials.s$k.csv &
    done; wait
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.ingestion.remote_zip import RemoteZip                                 # noqa: E402
from extract_stieger_features import SPECTRAL, _spectral                        # noqa: E402

ARTICLE = "https://api.figshare.com/v2/articles/25360300"
OUT = os.path.join(HERE, "..", "results", "cp_trials.csv")
MEMBER = re.compile(r"(S\d\d)_(Se\d\d)_([A-Z]{2})_(R\d\d)\.mat$")

SESSION_KEEP = "Se01"
MONTAGE = ("FZ", "FCZ", "CZ", "CPZ", "PZ", "C3", "C4", "F3", "F4", "P3", "P4")
PRE_S = 2.0
HIT_RADIUS = 0.10
RETRIES = 5

OUTCOMES = ["mean_dist", "median_dist", "frac_within", "vel_alignment"]
FIELDS = (["subject", "session", "run", "decoder", "study", "trial", "pre_gap_s",
           "n_channels_used", "trial_dur_s"] + SPECTRAL
          + ["mu_c3", "mu_c4", "mu_mean", "mu_lateralisation", "emg_index"] + OUTCOMES)


def _get(url, timeout=90):
    for a in range(RETRIES):
        try:
            return urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "bsde-research/1.0"}), timeout=timeout).read()
        except Exception:                                                       # noqa: BLE001
            if a == RETRIES - 1:
                raise
            time.sleep(2 ** a)
    raise RuntimeError("unreachable")


def _read_member(url, name):
    """RemoteZip read with backoff — figshare's S3 redirect resets connections under load."""
    for a in range(RETRIES):
        try:
            return RemoteZip(url).read_member(name)
        except Exception:                                                       # noqa: BLE001
            if a == RETRIES - 1:
                raise
            time.sleep(2 ** a)
    raise RuntimeError("unreachable")


def _emg_index(block, sf):
    """The project's constructed muscle proxy: high-band fraction over the montage.

    NOT ground truth — this deposit ships no EMG channel and rule 57 records that a constructed proxy
    correlates with a real submental channel at only rho ~ +0.20. Kept for continuity with E172/E181.
    """
    from numpy.fft import rfft, rfftfreq
    x = block - block.mean(axis=1, keepdims=True)
    w = np.hanning(x.shape[1])
    p = np.abs(rfft(x * w, axis=1)) ** 2
    f = rfftfreq(x.shape[1], 1.0 / sf)
    hi = (f >= 30.0) & (f < 100.0)
    tot = (f >= 1.0) & (f < 100.0)
    if not hi.any() or not tot.any():
        return float("nan")
    return float(np.nanmedian(p[:, hi].sum(axis=1) / np.maximum(p[:, tot].sum(axis=1), 1e-20)))


def run_rows(blob):
    import h5py
    with tempfile.NamedTemporaryFile(suffix=".mat", delete=False) as fh:
        fh.write(blob)
        path = fh.name
    try:
        f = h5py.File(path, "r")
        e = f["eeg"]

        def _s(key):
            return "".join(chr(c) for c in np.ravel(e[key][()]))

        sf = float(np.ravel(e["fs"][()])[0])
        labels = [("".join(chr(c) for c in np.ravel(f[e["channellabels"][0][i]][()]))).upper()
                  for i in range(e["channellabels"].shape[1])]
        ev = e["event"]

        def _ref(ds, i):
            return np.ravel(f[ds[i][0]][()])

        n_ev = ev["type"].shape[0]
        types = ["".join(chr(c) for c in _ref(ev["type"], i)) for i in range(n_ev)]
        lats = [float(_ref(ev["latency"], i)[0]) for i in range(n_ev)]
        starts = [l for t, l in zip(types, lats) if t == "TrialStart"]
        ends = [l for t, l in zip(types, lats) if t == "TrialEnd"]
        if not starts or len(starts) != len(ends):
            raise ValueError(f"{len(starts)} starts / {len(ends)} ends")

        data = e["data"]                                     # (n_samples, 62), volts already in uV
        times = np.ravel(e["times"][()])
        pt = np.ravel(e["postimes"][()])
        cx, cy = np.ravel(e["cursorpos"]["x"][()]), np.ravel(e["cursorpos"]["y"][()])
        tx, ty = np.ravel(e["targetpos"]["x"][()]), np.ravel(e["targetpos"]["y"][()])
        vx, vy = np.ravel(e["cursorvel"]["x"][()]), np.ravel(e["cursorvel"]["y"][()])
        meta = {"subject": _s("subject"), "session": _s("session"), "run": _s("run"),
                "decoder": _s("decoder"), "study": _s("study")}

        idx = {c: labels.index(c) for c in MONTAGE if c in labels}
        # h5py fancy indexing requires strictly increasing indices; the montage is order-free here
        # because every feature is a median across these channels.
        mont = sorted(idx[c] for c in MONTAGE if c in idx)
        if len(mont) < 6:
            raise ValueError(f"only {len(mont)} montage channels of {MONTAGE}")

        n_pre = int(round(PRE_S * sf))
        dist = np.hypot(cx - tx, cy - ty)
        out, prev_end = [], float(times[0])
        for k, (s0, e0) in enumerate(zip(starts, ends)):
            i0 = int(np.searchsorted(times, s0))
            if i0 - n_pre < 0:
                prev_end = e0
                continue
            block = np.asarray(data[i0 - n_pre:i0, mont], float).T      # (n_ch, n_pre)
            if block.shape[1] != n_pre or not np.isfinite(block).all():
                prev_end = e0
                continue
            rows = [_spectral(block[j], sf) for j in range(block.shape[0])]
            r = {c: float(np.nanmedian([q[c] for q in rows])) for c in SPECTRAL}
            a3 = (_spectral(np.asarray(data[i0 - n_pre:i0, idx["C3"]], float), sf)
                  ["relative_alpha_power"] if "C3" in idx else float("nan"))
            a4 = (_spectral(np.asarray(data[i0 - n_pre:i0, idx["C4"]], float), sf)
                  ["relative_alpha_power"] if "C4" in idx else float("nan"))
            r.update({"mu_c3": a3, "mu_c4": a4, "mu_mean": float(np.nanmean([a3, a4])),
                      "mu_lateralisation": (a3 - a4) / (a3 + a4)
                      if np.isfinite(a3 + a4) and (a3 + a4) > 0 else float("nan"),
                      "emg_index": _emg_index(block, sf)})

            m = (pt >= s0) & (pt <= e0)
            if m.sum() < 100:
                prev_end = e0
                continue
            dx, dy = tx[m] - cx[m], ty[m] - cy[m]
            nrm = np.hypot(dx, dy)
            vn = np.hypot(vx[m], vy[m])
            ok = (nrm > 1e-9) & (vn > 1e-9)
            align = (float(np.nanmean((vx[m][ok] * dx[ok] + vy[m][ok] * dy[ok])
                                      / (vn[ok] * nrm[ok]))) if ok.sum() > 50 else float("nan"))
            r.update({"mean_dist": float(np.nanmean(dist[m])),
                      "median_dist": float(np.nanmedian(dist[m])),
                      "frac_within": float(np.nanmean(dist[m] < HIT_RADIUS)),
                      "vel_alignment": align,
                      "trial": k, "pre_gap_s": (s0 - prev_end) / 1000.0,
                      "trial_dur_s": (e0 - s0) / 1000.0, "n_channels_used": len(mont)})
            r.update(meta)
            out.append(r)
            prev_end = e0
        f.close()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if not out:
        raise ValueError("no usable trials")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--session", default=SESSION_KEEP)
    ap.add_argument("--last-session", action="store_true",
                    help="use each subject's FINAL session instead of --session. A protocol-level "
                         "criterion (most-trained) rather than a performance ranking: E192 showed the "
                         "BCI is not alive in session 1, with only 6 of 28 subjects driving the cursor "
                         "toward the target, so 'execution quality' had no estimand there.")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    art = json.loads(_get(ARTICLE).decode())
    subj_url = {f["name"][:-4]: f["download_url"] for f in art["files"]
                if re.fullmatch(r"S\d\d\.zip", f["name"])}
    # shard on the numeric subject id -- never hash(), which Python salts per process
    subs = sorted(s for s in subj_url if int(s[1:]) % a.of == a.shard)

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {(r["subject"], r["session"], r["run"], r["decoder"])
                    for r in csv.DictReader(fh)}
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    print(f"shard {a.shard}/{a.of}: {len(subs)} subjects {subs}, {len(done)} run-files done",
          flush=True)

    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for s in subs:
            url = subj_url[s]
            try:
                members = [m["name"] for m in RemoteZip(url).index()]
            except Exception as ex:                                             # noqa: BLE001
                print(f"   {s}: INDEX FAIL {type(ex).__name__}: {ex}", flush=True)
                continue
            parsed = [(MEMBER.search(os.path.basename(n)), n) for n in members]
            parsed = [(m, n) for m, n in parsed if m]
            if a.last_session:
                keep = max((m.group(2) for m, _ in parsed), default=None)
            else:
                keep = a.session
            want = [(m.group(1), m.group(2), m.group(4), m.group(3), n)
                    for m, n in parsed if m.group(2) == keep]
            want.sort()
            todo = [t for t in want if (t[0], t[1], t[2], t[3]) not in done]
            print(f"   {s}: {len(want)} run-files in "
                  f"{want[0][1] if want else a.session}, {len(todo)} to go", flush=True)
            for i, (_su, _se, _r, _d, name) in enumerate(todo, 1):
                try:
                    rows = run_rows(_read_member(url, name))
                    for r in rows:
                        w.writerow({k: r.get(k, "") for k in FIELDS})
                    fh.flush()
                    print(f"      [{i}/{len(todo)}] {os.path.basename(name)}: {len(rows)} trials",
                          flush=True)
                except Exception as ex:                                         # noqa: BLE001
                    print(f"      [{i}/{len(todo)}] {os.path.basename(name)}: "
                          f"FAIL {type(ex).__name__}: {ex}", flush=True)
    print(f"   wrote -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
