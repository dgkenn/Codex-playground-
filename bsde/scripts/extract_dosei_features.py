"""Compute the TRANSPORTABLE feature set on DOSE-I raw EEG, for external validation of the BIS-like index.

WHY. `docs/BIS_FAITHFUL_OR_BRAIN_FAITHFUL.md` and Q22 leave the BIS-like index validated against ONE
reference on ONE deposit: device BIS, on VitalDB, in surgical maintenance. It has never met a human label.
**DOSE-I carries per-second clinician-scored MOAA/S and SOC with raw EEG and no branded index**, which makes
it the external test the index has not had -- a different device, a different population (procedural
sedation, not surgery), and a reference that is a person rather than a machine.

THE FEATURE SET IS FIXED BY WHAT BOTH DEPOSITS SUPPORT, AND IT IS FIXED HERE, BEFORE THE FIT. Fifteen
registry candidates are live on VitalDB (`spatial_participation_ratio`, `uce_v1` and `wpli_alpha` are
all-NaN there, needing a montage the BIS strip does not have) plus the four BIS subparameters. Nineteen
columns. **A model fitted on one feature set and applied to another is not the same model**, so the list is
written into `TRANSPORTABLE` rather than discovered per deposit.

DOSE-I IS TWO-CHANNEL FRONTO-TEMPORAL, which is a wider spacing than VitalDB's BIS strip -- so the
connectivity columns are computed too and carried alongside. They are NOT part of the transportable index
(VitalDB cannot supply `wpli_alpha`), and they are extracted because Q26 established that a strip cannot
carry wPLI and a wider pair might; that is worth measuring rather than assuming.

SAMPLING. The same causal windows as `extract_dosei_sfs.py`: `WINDOW_S` seconds ENDING at each depositor
timestamp, every `STRIDE_S`-th second, joined on the absolute de-identified clock. Recordings whose raw
time axis disagrees with their sample count by more than 1 % are refused whole (rule 27) -- 21 of 60 were,
in the E59 run, for real gaps up to 82.8 s.

    python bsde/scripts/extract_dosei_features.py --n-recordings 60
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.registry import REGISTRY                             # noqa: E402
from bsde.candidates.seed import seed_registry                            # noqa: E402
from bsde.candidates.bis_comparator import bis_candidates                 # noqa: E402
from bsde.ingestion.remote_zip import RemoteZip                           # noqa: E402

sys.path.insert(0, HERE)
from extract_dosei_sfs import DATA_URL, PEEG_ZIP, SFREQ, _f, _ts, raw_eeg  # noqa: E402

OUT = os.path.join(HERE, "..", "results", "dosei_features.csv")
WINDOW_S = 30.0
STRIDE_S = 5

TRANSPORTABLE = ["critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_index", "emg_kurtosis",
                 "exponent_gamma", "exponent_high", "exponent_low", "lempel_ziv",
                 "multiscale_entropy_slope", "pac_slow_alpha", "relative_alpha_power",
                 "relative_delta_power", "spectral_edge_95", "spectral_entropy",
                 "whole_head_exponent", "bis_rbr", "bis_bsr", "bis_quazi", "bis_sfs"]
CONN = ["coherence_delta", "coherence_theta", "coherence_alpha", "coherence_beta",
        "wpli_delta", "wpli_theta", "wpli_alpha_2ch", "wpli_beta"]
BANDS = {"delta": (1.0, 4.0), "theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}
FIELDS = (["recording", "t_s", "soc", "moaas", "propofol", "endoscopy", "their_sef95",
           "their_pe31", "n_finite"]
          + TRANSPORTABLE + CONN)


def peeg_rows(z, rec):
    with z.open(f"pEEG/pEEG/{rec}_pEEG.csv") as fh:
        import io
        return {_ts(r["Time"]): r for r in csv.DictReader(io.TextIOWrapper(fh))}


def raw_two(blob):
    """Both EEG channels on a uniform 125 Hz axis, or (None, None) if the time axis is not uniform."""
    import io
    from datetime import datetime
    rd = csv.DictReader(io.TextIOWrapper(io.BytesIO(blob)))
    ts, x1, x2 = [], [], []
    for r in rd:
        a = r.get("Intellivue/EEG_1", "")
        if a == "":
            continue
        ts.append(r["Time"])
        x1.append(_f(a))
        x2.append(_f(r.get("Intellivue/EEG_2", "")))
    if len(x1) < int(60 * SFREQ):
        return None, None, None
    t0, t1 = _ts(ts[0]), _ts(ts[-1])
    elapsed = (t1 - t0).total_seconds()
    if elapsed <= 0 or abs((len(x1) - 1) / SFREQ - elapsed) / elapsed > 0.01:
        return None, None, None
    return np.asarray(x1, float), np.asarray(x2, float), t0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-recordings", type=int, default=60, dest="n_rec")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--exclude-used", action="store_true", dest="exclude_used",
                    help="skip every recording this project has already computed a DOSE-I number on, so "
                         "the output is a genuine held-out partition. Default OFF: the flag changes "
                         "nothing about the existing table or how it was produced.")
    a = ap.parse_args(argv)

    seed_registry()
    bis_candidates()
    cands = {n: REGISTRY.get(n) for n in TRANSPORTABLE}
    from bsde.features.connectivity import coherence, wpli

    pz = zipfile.ZipFile(os.path.abspath(PEEG_ZIP))
    have = {n.split("/")[-1].replace("_pEEG.csv", "") for n in pz.namelist() if n.endswith("_pEEG.csv")}
    rz = RemoteZip(DATA_URL)
    recs = [m["name"].split("/")[-1][:-4] for m in rz.index() if m["name"].endswith(".csv")]
    recs = [r for r in recs if r in have]
    if a.exclude_used:
        used = set()
        for name in ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv"):
            q = os.path.join(HERE, "..", "results", name)
            if not os.path.exists(q):
                continue
            with open(q, newline="") as fh:
                rd = csv.DictReader(fh)
                key = "recording" if "recording" in (rd.fieldnames or []) else "recording_id"
                for r in rd:
                    if r.get(key):
                        used.add(r[key].split("@")[0])
        before = len(recs)
        recs = [r for r in recs if r not in used]
        print(f"--exclude-used: {before} -> {len(recs)} recordings ({len(used)} already used)", flush=True)
    recs = recs[:a.n_rec]

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording"] for r in csv.DictReader(fh)}
    todo = [r for r in recs if r not in done]
    print(f"{len(recs)} recordings selected, {len(done)} already done, {len(todo)} to go", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, rec in enumerate(todo, 1):
            try:
                peeg = peeg_rows(pz, rec)
                x1, x2, t0 = raw_two(rz.read_member(f"data/{rec}.csv"))
            except Exception as e:                                        # noqa: BLE001
                print(f"   [{i}/{len(todo)}] {rec}: SKIP {type(e).__name__}", flush=True)
                continue
            if x1 is None:
                print(f"   [{i}/{len(todo)}] {rec}: SKIP non-uniform time axis", flush=True)
                continue
            n = int(WINDOW_S * SFREQ)
            wrote = 0
            for ts_abs in sorted(peeg):
                t = (ts_abs - t0).total_seconds()
                if round(t) % STRIDE_S or t < WINDOW_S:
                    continue
                i1 = int(round(t * SFREQ))
                s1, s2 = x1[i1 - n:i1], x2[i1 - n:i1]
                if s1.size < n:
                    continue
                ok = np.isfinite(s1) & np.isfinite(s2)
                if ok.mean() < 0.9:
                    continue
                if not ok.all():
                    idx = np.flatnonzero(ok)
                    s1 = np.interp(np.arange(n), idx, s1[idx])
                    s2 = np.interp(np.arange(n), idx, s2[idx])
                src = peeg[ts_abs]
                row = {"recording": rec, "t_s": f"{t:.0f}", "soc": src.get("SOC", ""),
                       "moaas": src.get("MOAAS", ""), "propofol": src.get("Propofol", ""),
                       "endoscopy": src.get("Endoscopy", ""),
                       "their_sef95": src.get("SEF95", ""), "their_pe31": src.get("PE31", ""),
                       "n_finite": f"{ok.mean():.4f}"}
                data = s1[None, :]
                for name, c in cands.items():
                    try:
                        v = c.fn(data, ["EEG_1"], SFREQ, {})
                        row[name] = "" if v is None or not np.isfinite(v) else f"{float(v):.10g}"
                    except Exception:                                     # noqa: BLE001
                        row[name] = ""
                for b, (lo, hi) in BANDS.items():
                    for kind in ("coherence", "wpli"):
                        key = f"{kind}_{b}" if not (kind == "wpli" and b == "alpha") else "wpli_alpha_2ch"
                        try:
                            fn = coherence if kind == "coherence" else wpli
                            v = fn(s1, s2, SFREQ, lo, hi)
                            row[key] = "" if not np.isfinite(v) else f"{float(v):.10g}"
                        except Exception:                                 # noqa: BLE001
                            row[key] = ""
                w.writerow({k: row.get(k, "") for k in FIELDS})
                wrote += 1
            fh.flush()
            print(f"   [{i}/{len(todo)}] {rec}: {wrote} windows", flush=True)
    print(f"   wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
