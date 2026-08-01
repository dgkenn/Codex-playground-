"""Blankertz's published SMR predictor on Dreyer -- does the FIELD's own predictor of BCI performance
replicate, now that ours does not?

WHY. E124 and E125 closed this project's only Challenge B positive: `ge_norm` predicts BCI accuracy in
Stieger's 62 subjects (+0.3069) but not in eegmmidb (-0.1298, excluding an effect of that size) and not in
Dreyer's ONLINE-control cohort either (-0.2065, inside its own permutation interval). Two independent
cohorts, one construct-matched, both negative. E86 is cohort-specific.

**That leaves a question worth more than another measure of ours: does ANYONE's predictor replicate?**
The field's canonical one is

    Blankertz B, Sannelli C, Halder S, Hammer EM, Kubler A, Muller KR, Curio G, Dickhaus T.
    "Neurophysiological predictor of SMR-based BCI performance." Neuroimage 2010;51(4):1303-9.
    PMID 20303409.   (verified from the MEDLINE record, rule 25)

and Dreyer is close to a direct replication cohort for it. Quoting the abstract:

    "we propose a neurophysiological predictor of BCI performance which can be determined from a two
     minute recording of a 'relax with eyes open' condition using two Laplacian EEG channels. A
     correlation of r=0.53 between the proposed predictor and BCI feedback performance was obtained on a
     large data base with N=80 BCI-naive participants in their first session"

Dreyer: N=87, BCI-naive, first and only session, online feedback performance, and an `OE_baseline`
recording. **The window this project already used for the graph extraction is 120 s -- two minutes -- so
even that matches without adjustment.** An r of 0.53 is far larger than E86's +0.3069, so n=87 has ample
power; a null here would be a strong statement about the field, not about sample size.

WHAT IS QUOTED AND WHAT IS INFERRED (rule 42). Quoted: two minutes, relax-with-eyes-open, two Laplacian
channels, r = 0.53, N = 80. **The formula is NOT in the abstract and the paper is paywalled**, so the
implementation below is the standard SMR-peak-above-noise-floor construction that the description
specifies up to convention, and it is labelled an inference rather than presented as Blankertz's content.
Specifically:

    * large Laplacian at C3 and C4 -- C3 - mean(FC3, C1, CP3, C5) and C4 - mean(FC4, C2, CP4, C6). All
      eight neighbours exist in Dreyer's 32-channel montage, so no substitution is needed.
    * Welch PSD over the 120 s eyes-open baseline.
    * a 1/f background fitted on log-log EXCLUDING the SMR band, so the band cannot pull its own baseline.
    * the predictor is the maximum decibel excess of the PSD over that background within the SMR band,
      taken as the LARGER of the two Laplacian channels -- "two Laplacian channels" yielding one number.

THE PRE-EXISTING APPROXIMATION IS REPORTED ALONGSIDE, NOT INSTEAD. `dreyer_graph.csv` already carries
`alpha_prom`, which is the same idea (peak residual above an aperiodic fit) but computed over 7-13 Hz as a
MEDIAN OVER ALL CHANNELS rather than over a sensorimotor Laplacian. It is a different measure and is
carried as a separate column so the two cannot be confused (rule 28's habit: two measurements separated in
space are not thereby measuring different things -- and here they may well be measuring the same one,
which is worth knowing).

SCOPE. This script extracts. It correlates nothing with performance and makes no claim.

    python bsde/scripts/extract_dreyer_smr.py --limit 2
    python bsde/scripts/extract_dreyer_smr.py --shard k --of 6
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.ingestion.remote_zip import RemoteZip                            # noqa: E402
from extract_dreyer_graph import ZIP_URL, WINDOW_S, _read_gdf_prefix       # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
OUT = os.path.join(RESULTS, "dreyer_smr.csv")

# "two Laplacian EEG channels" -- the large Laplacian at each sensorimotor site.
LAPLACIAN = {"C3": ("FC3", "C1", "CP3", "C5"),
             "C4": ("FC4", "C2", "CP4", "C6")}
SMR_LO, SMR_HI = 8.0, 15.0          # the sensorimotor mu/SMR band
FIT_LO, FIT_HI = 3.0, 35.0          # range over which the 1/f background is fitted
FIELDS = ["subject", "dataset", "run", "status", "error", "sfreq", "n_samples",
          "smr_C3_db", "smr_C4_db", "smr_predictor_db", "smr_peak_hz"]


def smr_excess_db(x, sfreq):
    """Peak decibel excess of the PSD over a 1/f background fitted OUTSIDE the SMR band.

    Excluding the band from its own baseline fit is the part that matters: including it lets a large SMR
    peak raise the background it is measured against, which compresses exactly the subjects the predictor
    is meant to separate. Returns (excess_dB, peak_frequency)."""
    from scipy.signal import welch
    f, p = welch(x, fs=sfreq, nperseg=int(min(len(x), 4 * sfreq)))
    m_fit = (f >= FIT_LO) & (f <= FIT_HI) & (p > 0)
    m_band = (f >= SMR_LO) & (f <= SMR_HI)
    m_bg = m_fit & ~m_band
    if m_bg.sum() < 8 or m_band.sum() < 3:
        return float("nan"), float("nan")
    b = np.polyfit(np.log10(f[m_bg]), np.log10(p[m_bg]), 1)
    bg = 10.0 ** np.polyval(b, np.log10(np.clip(f, 1e-9, None)))
    excess_db = 10.0 * np.log10(np.clip(p[m_band], 1e-30, None) / np.clip(bg[m_band], 1e-30, None))
    k = int(np.argmax(excess_db))
    return float(excess_db[k]), float(f[m_band][k])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=-1)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)
    if a.shard >= 0:
        root, ext = os.path.splitext(a.out)
        a.out = f"{root}.s{a.shard}{ext}"

    rz = RemoteZip(ZIP_URL)
    # EYES OPEN ONLY. The source says "relax with eyes open"; the eyes-closed run is a different condition
    # with a much larger occipital alpha, and averaging the two would not be Blankertz's predictor.
    members = [m for m in rz.index() if re.search(r"_OE_baseline\.gdf$", m["name"])]
    jobs = []
    for m in members:
        base = m["name"].split("/")[-1]
        mm = re.match(r"([A-C]\d+)_OE_baseline\.gdf$", base)
        if mm:
            jobs.append({"member": m["name"], "subject": mm.group(1), "dataset": mm.group(1)[0]})
    jobs.sort(key=lambda j: j["subject"])
    if a.shard >= 0:
        jobs = [j for i, j in enumerate(jobs) if i % a.of == a.shard]
    if a.limit:
        jobs = jobs[:a.limit]

    out_path = os.path.abspath(a.out)
    import glob as _glob
    root, ext = os.path.splitext(os.path.abspath(a.out).replace(f".s{a.shard}", "")
                                 if a.shard >= 0 else os.path.abspath(a.out))
    done = set()
    for p in {out_path, *_glob.glob(f"{root}.s*{ext}"), f"{root}{ext}"}:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            for r in csv.DictReader(open(p, newline="")):
                done.add(r["subject"])
    todo = [j for j in jobs if j["subject"] not in done]
    print(f"{len(members)} eyes-open baselines; {len(jobs)} in shard, {len(done)} done, "
          f"{len(todo)} to fetch -> {out_path}", flush=True)
    if not todo:
        return 0

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for i, j in enumerate(todo, 1):
            row = {"subject": j["subject"], "dataset": j["dataset"], "run": "OE",
                   "status": "ok", "error": ""}
            try:
                x, names, sf = _read_gdf_prefix(rz.read_member(j["member"]))
                idx = {n: k for k, n in enumerate(names)}
                need = int(WINDOW_S * sf)
                if x.shape[1] < need:
                    raise ValueError(f"{x.shape[1]} samples, need {need}")
                seg = x[:, :need]
                vals = {}
                for site, nbrs in LAPLACIAN.items():
                    if site not in idx or any(nb not in idx for nb in nbrs):
                        raise ValueError(f"montage missing {site} or a neighbour")
                    lap = seg[idx[site]] - np.mean([seg[idx[nb]] for nb in nbrs], axis=0)
                    vals[site] = smr_excess_db(lap, sf)
                row["sfreq"], row["n_samples"] = f"{sf:g}", seg.shape[1]
                row["smr_C3_db"] = f"{vals['C3'][0]:.6g}"
                row["smr_C4_db"] = f"{vals['C4'][0]:.6g}"
                best = max(vals.values(), key=lambda t: (t[0] if np.isfinite(t[0]) else -1e9))
                row["smr_predictor_db"] = f"{best[0]:.6g}"
                row["smr_peak_hz"] = f"{best[1]:.6g}"
            except Exception as e:                                          # noqa: BLE001
                row.update({"status": "error", "error": f"{type(e).__name__}: {e}"[:200]})
            w.writerow(row)
            fh.flush()
            print(f"   [{i}/{len(todo)}] {j['subject']} {row['status']} "
                  f"smr={row.get('smr_predictor_db', '')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
