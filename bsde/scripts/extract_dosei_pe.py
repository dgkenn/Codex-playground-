"""Compute THIS repo's `permutation_entropy` on DOSE-I raw EEG, beside the depositors' own PE31.

CORRECTION, 2026-07-31, added AFTER this script ran. **The "WHY" paragraph below was copied from
`extract_dosei_sfs.py` and describes SynchFastSlow, not permutation entropy.** It is left in place rather
than rewritten, because a pre-registration docstring that gets quietly edited after its run is worth less
than an honest one with a correction on top. What the paragraph gets right and what it gets wrong:

  * RIGHT, and it is the reason this script exists: rule 23 -- self-written code plus self-written tests
    share blind spots, and DOSE-I ships an independent implementation to check ours against.
  * WRONG: the columns quoted (33 SynchFastSlow, 35 PowerFastSlow) are not the ones this script reads.
    It reads column 30, named `PE31` in the deposit's CSVs: "Permutation Entropy (PE) according to
    Olofsen et al. (2008), band: 0.5-45 Hz, n=3, tau=1, tie=0.5 uV", and column 31, named `PE32`, which is
    the same at tau=2. Our call is order 3, delay 1, so `PE31` is the matching parameterisation and `PE32`
    is carried only as a contrast.
  * The reciprocal-sign argument below is about SFS and has no bearing on PE, whose two implementations are
    expected to agree POSITIVELY.

The ALIGNMENT paragraph, the fetch strategy and the causal windowing below are this script's own and are
accurate. What was measured with it is QUEUE.md Q36; what it left unexplained is registered as E76.

WHY. `bsde/src/bsde/features/bis_subparams.py` added the first genuinely bispectral quantity in this repo,
and it has only self-written tests. Rule 23: self-written code plus self-written tests share blind spots,
and an independent implementation catches what unit tests cannot. **DOSE-I ships one.** Its
`pEEG_parameter_description.txt` defines, verbatim:

    Column 33: SynchFastSlow according to Miller et al. (2004), log of bispectral power quotient 40-47 Hz
               over 1-47 Hz, see also Rampil et al. (1998)
    Column 35: PowerFastSlow according to Miller et al. (2004), log of power quotient 40-47 Hz over 1-47 Hz

**Their SFS is the RECIPROCAL of Rampil's**, which is what this repo implemented -- log of the whole
triangle over the 40-47 Hz sub-region. So the two must be strongly NEGATIVELY related, and that sign is
fixed by the parameter description rather than by any data. Column 35 is the second gift: a PURE POWER
ratio over the identical bands, which makes it possible to ask whether the bispectral machinery is doing
bispectral work or restating a power ratio (rule 28).

WHAT IS FETCHED, AND HOW LITTLE. `data.zip` is 724 MB and is never downloaded. `RemoteZip` reads one
member at a time over HTTP Range requests -- about 4 MB compressed per recording -- and the member is
decompressed in memory and discarded. Deflate is sequential, so a member is fetched whole; there is no
partial-member saving to be had and the script does not pretend otherwise.

ALIGNMENT IS DECLARED HERE, BEFORE ANY CORRELATION IS COMPUTED, because it is the one free parameter that
could be tuned into agreement. The depositors' series is 1 Hz. This computes `sync_fast_slow` over the
`WINDOW_S` seconds **ENDING** at each pEEG timestamp -- causal, the way a monitor would -- at every
`STRIDE_S`-th second. No lag search is performed anywhere, and E59's placebo tests alignment directly by
shifting the window and checking the agreement collapses.

    python bsde/scripts/extract_dosei_pe.py --n-recordings 40
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.features.complexity import permutation_entropy                 # noqa: E402
from bsde.ingestion.remote_zip import RemoteZip                           # noqa: E402

DATA_URL = "https://zenodo.org/records/18483292/files/data.zip?download=1"
PEEG_ZIP = os.path.join(HERE, "..", "results", "dosei_pEEG.zip")
OUT = os.path.join(HERE, "..", "results", "dosei_pe_check.csv")

SFREQ = 125.0
WINDOW_S = 30.0          # window ENDING at the pEEG timestamp
STRIDE_S = 5             # evaluate every 5th pEEG second; the series is smooth at 1 Hz
NFFT = 256               # 2.048 s at 125 Hz -> 0.488 Hz resolution, 28 segments in a 30 s window
FIELDS = ["recording", "t_s", "mine_pe", "their_pe31", "their_pe32", "soc", "moaas"]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


TFMT = "%Y-%m-%d %H:%M:%S.%f"
TFMT_S = "%Y-%m-%d %H:%M:%S"


def _ts(s: str):
    from datetime import datetime
    return datetime.strptime(s, TFMT if "." in s else TFMT_S)


def peeg_series(z: zipfile.ZipFile, rec: str):
    """The depositors' 1 Hz table for one recording: absolute timestamp -> (SFS, PFS, SOC, MOAAS).

    BOTH tables carry the same de-identified wall clock (2022-01-01 00:00:00 plus elapsed), so the join is
    on the ABSOLUTE timestamp rather than on an assumed common origin. The pEEG series starts about 10 s
    after the raw record, which an origin-based alignment would have silently mis-shifted by that much.
    """
    with z.open(f"pEEG/pEEG/{rec}_pEEG.csv") as fh:
        rows = list(csv.DictReader(io.TextIOWrapper(fh)))
    return {_ts(r["Time"]): (_f(r["PE31"]), _f(r["PE32"]), _f(r["SOC"]), _f(r["MOAAS"]))
            for r in rows}


def raw_eeg(blob: bytes):
    """EEG_1 as a uniform 125 Hz array, plus the seconds offset of its first sample.

    The raw CSV is a 250 Hz ROW grid on which EEG appears every other row, so the EEG samples are taken in
    order and the time axis is reconstructed from the FIRST EEG timestamp and the nominal rate. Rows whose
    EEG cell is empty are structural, not dropouts, and skipping them does not glue time together (rule 27)
    -- but a genuine gap would, so the sample count is checked against the elapsed wall time below and the
    recording is refused if they disagree by more than 1 %.
    """
    rd = csv.DictReader(io.TextIOWrapper(io.BytesIO(blob)))
    ts, xs = [], []
    for r in rd:
        v = r.get("Intellivue/EEG_1", "")
        if v == "":
            continue
        ts.append(r["Time"])
        xs.append(_f(v))
    if len(xs) < int(60 * SFREQ):
        return None, None
    t0, t1 = _ts(ts[0]), _ts(ts[-1])
    elapsed = (t1 - t0).total_seconds()
    expected = (len(xs) - 1) / SFREQ
    if elapsed <= 0 or abs(expected - elapsed) / elapsed > 0.01:
        return None, None                       # a real gap: the uniform time axis would be a fiction
    return np.asarray(xs, float), t0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-recordings", type=int, default=40, dest="n_rec")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    pz = zipfile.ZipFile(os.path.abspath(PEEG_ZIP))
    have_peeg = {n.split("/")[-1].replace("_pEEG.csv", "")
                 for n in pz.namelist() if n.endswith("_pEEG.csv")}
    rz = RemoteZip(DATA_URL)
    members = [m for m in rz.index() if m["name"].endswith(".csv")]
    recs = [m["name"].split("/")[-1][:-4] for m in members]
    recs = [r for r in recs if r in have_peeg][:a.n_rec]
    print(f"{len(recs)} recordings selected (of {len(members)} in data.zip, "
          f"{len(have_peeg)} with a pEEG table)", flush=True)

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording"] for r in csv.DictReader(fh)}
        print(f"   resuming: {len(done)} recordings already present", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_win = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, rec in enumerate([r for r in recs if r not in done], 1):
            try:
                peeg = peeg_series(pz, rec)
                x, t0 = raw_eeg(rz.read_member(f"data/{rec}.csv"))
            except Exception as e:                                        # noqa: BLE001
                print(f"   [{i}] {rec}: SKIP {type(e).__name__}: {e}", flush=True)
                continue
            if x is None:
                print(f"   [{i}] {rec}: SKIP non-uniform time axis or too short", flush=True)
                continue
            n = int(WINDOW_S * SFREQ)
            wrote = 0
            for ts_abs in sorted(peeg):
                t = (ts_abs - t0).total_seconds()          # seconds into the RAW record
                if round(t) % STRIDE_S or t < WINDOW_S:
                    continue
                i1 = int(round(t * SFREQ))
                seg = x[i1 - n:i1]
                if seg.size < n:
                    continue
                s, p, soc, mo = peeg[ts_abs]
                w.writerow({"recording": rec, "t_s": f"{t:.0f}",
                            "mine_pe": f"{permutation_entropy(seg, order=3, delay=1):.10g}",
                            "their_pe31": f"{s:.10g}", "their_pe32": f"{p:.10g}",
                            "soc": f"{soc:.10g}", "moaas": f"{mo:.10g}"})
                wrote += 1
            fh.flush()
            n_win += wrote
            print(f"   [{i}] {rec}: {wrote} windows ({len(x) / SFREQ / 60:.1f} min of EEG)", flush=True)
    print(f"   wrote {n_win} windows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
