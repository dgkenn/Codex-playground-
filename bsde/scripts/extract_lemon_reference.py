"""Build an adult awake normative reference from LEMON -- because there is nothing to download.

WHY THIS DEPOSIT AND WHY AT ALL. E91 records the search: six PubMed phrasings through E-utilities for a
normative aperiodic reference table all return **count = 0**. No published norms exist, and borrowed
constants would be unusable anyway, since an aperiodic exponent depends on fit range, PSD method, epoch
length, montage and reference and a published mean/SD carries none of them. So the reference has to be
built from data, and it should be built from a cohort that exists to be normative.

**LEMON (MPI Leipzig Mind-Brain-Body) is that cohort**: ~227 healthy adults, 62-channel resting-state EEG,
open access, spanning a wide adult age range -- which matters because the exponent is documented to change
with age (PMID 41468657, PMID 38373849). Every other awake cohort this project holds is a by-product:
eegmmidb's resting runs exist to baseline a BCI task, ds004541's and ds005620's exist to precede an
anaesthetic.

REACHABILITY VERIFIED BEFORE WRITING THIS, not assumed: the INDI S3 mirror returns HTTP 200 and lists
`EEG_Raw_BIDS_ID/sub-XXXXXX/RSEEG/sub-XXXXXX.{eeg,vhdr,vmrk}`, about **316 MB of raw binary per subject**.

WHY RAW AND NOT THE PREPROCESSED COPY. The deposit also ships an ICA-cleaned, band-limited EEGLAB version
at 28 MB per condition, which would be far cheaper. It is not used, because it has been through a
DIFFERENT preprocessing pipeline from every other table in this repository, and a reference whose
preprocessing differs from the data it references would confound "this cohort's brains differ" with "this
cohort's filters differ" -- the exact confusion the reference exists to remove. `read_brainvision_window_http`
takes one byte-range GET for the window it needs, so the raw file's size costs nothing beyond that window.

WHAT IS TAKEN, and the one honest limitation. LEMON's RSEEG run alternates 60 s eyes-open and eyes-closed
blocks. This takes `WINDOW_S` seconds starting at `START_S`, which **spans both conditions**. That is
defensible for a reference -- both are awake rest -- and it is a real source of within-cohort variance,
since eyes-open and eyes-closed differ substantially in alpha even if the aperiodic exponent differs less.
Anyone using this reference should know the SD it supplies is an EO/EC mixture SD, not an EC-only one.

    python bsde/scripts/extract_lemon_reference.py --limit 40
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import urllib.parse
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.seed import _exponents                                  # noqa: E402
from bsde.candidates.uce_v1 import regional_exponents                        # noqa: E402
from bsde.ingestion.openneuro_brainvision import (_check_format_and_orientation,   # noqa: E402
                                                  _http_get_range,
                                                  decode_brainvision_window, parse_vhdr)

BUCKET = "https://fcp-indi.s3.amazonaws.com/"
PREFIX = "data/Projects/INDI/MPI-LEMON/EEG_MPILMBB_LEMON/EEG_Raw_BIDS_ID/"
OUT = os.path.join(HERE, "..", "results", "lemon_regional_aperiodic.csv")
WINDOW_S, START_S = 240.0, 60.0
FIELDS = ["recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples",
          "aperiodic_frontal", "aperiodic_posterior", "aperiodic_wholehead", "n_frontal", "n_posterior"]

VHDR = re.compile(r"(sub-\d+)/RSEEG/(sub-\d+)\.vhdr$")


def read_window(vhdr_url: str, window_s: float, start_s: float):
    """LEMON's own reader, because `read_brainvision_window_http` cannot be used unmodified here.

    **THE DEPOSIT'S HEADERS ARE STALE.** `sub-032301.vhdr` declares `DataFile=sub-010002.eeg` -- the
    ORIGINAL recorder filename, not the BIDS re-identified one sitting beside it -- so resolving `DataFile`
    relative to the header, which is the correct and documented behaviour, yields a 404 on every subject.
    Verified: the `.vhdr` itself returns HTTP 200 and the declared `.eeg` does not.

    The correction is deposit-specific and is made explicitly rather than by loosening the shared adapter:
    the binary is taken to be the sibling file with the HEADER'S OWN basename. Everything else -- format
    and orientation checks, the single byte-range GET, the decode and the unit conversion -- is the shared
    implementation, unchanged.
    """
    with urllib.request.urlopen(urllib.request.Request(vhdr_url), timeout=120) as resp:
        header = parse_vhdr(resp.read().decode("utf-8", errors="replace"))
    data_url = vhdr_url[:-len(".vhdr")] + os.path.splitext(header["data_file"])[1]
    dtype = _check_format_and_orientation(header["binary_format"], header["data_orientation"])
    frame_bytes = header["n_channels"] * dtype.itemsize
    start_byte = max(0, int(round(start_s * header["sfreq"]))) * frame_bytes
    length = max(1, int(round(window_s * header["sfreq"]))) * frame_bytes
    raw = _http_get_range(data_url, start_byte, length, timeout=120)
    data = decode_brainvision_window(
        raw, n_channels=header["n_channels"], binary_format=header["binary_format"],
        data_orientation=header["data_orientation"], resolutions=header["resolutions"],
        units=header["units"])
    return data, list(header["ch_names"]), float(header["sfreq"])


def list_subjects(max_pages: int = 20):
    """Enumerate `.vhdr` keys by paging the public S3 listing. No credentials; no boto3."""
    out, token = [], None
    for _ in range(max_pages):
        url = f"{BUCKET}?list-type=2&prefix={PREFIX}&max-keys=1000"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token, safe="")
        with urllib.request.urlopen(url, timeout=120) as fh:
            x = fh.read().decode("utf8", "replace")
        out += [k for k in re.findall(r"<Key>(.*?)</Key>", x) if k.endswith(".vhdr")]
        m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", x)
        if not m or "<IsTruncated>true" not in x:
            break
        token = m.group(1)
    return sorted(set(out))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)

    keys = list_subjects()
    print(f"{len(keys)} LEMON RSEEG headers listed", flush=True)
    if a.limit:
        keys = keys[:a.limit]

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["subject"] for r in csv.DictReader(fh)}
        print(f"   resuming: {len(done)} subjects present", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        todo = [k for k in keys if (VHDR.search(k).group(1) if VHDR.search(k) else None) not in done]
        print(f"   {len(todo)} to go", flush=True)
        for i, key in enumerate(todo, 1):
            m = VHDR.search(key)
            if not m:
                continue
            sub = m.group(1)
            row = {"recording_id": f"lemon/{sub}", "dataset": "lemon", "subject": sub,
                   "status": "ok", "error": ""}
            try:
                data, ch_names, sfreq = read_window(BUCKET + key, WINDOW_S, START_S)
                reg = regional_exponents(_exponents(np.asarray(data, float), float(sfreq)), ch_names)
                row.update({"n_channels": len(ch_names), "sfreq": f"{sfreq:.6g}",
                            "n_samples": int(np.asarray(data).shape[1]),
                            "aperiodic_frontal": f"{reg['frontal']:.10g}",
                            "aperiodic_posterior": f"{reg['posterior']:.10g}",
                            "aperiodic_wholehead": f"{reg['whole_head']:.10g}",
                            "n_frontal": reg["n_frontal"], "n_posterior": reg["n_posterior"]})
                print(f"   [{i}/{len(todo)}] {sub}: {len(ch_names)} ch, "
                      f"F {reg['frontal']:+.4f} P {reg['posterior']:+.4f} "
                      f"({reg['n_frontal']}/{reg['n_posterior']} ch)", flush=True)
            except Exception as e:                                           # noqa: BLE001
                row.update({"status": "error", "error": f"{type(e).__name__}: {e}"[:200]})
                print(f"   [{i}/{len(todo)}] {sub}: FAIL {type(e).__name__}: {e}", flush=True)
            w.writerow({k: row.get(k, "") for k in FIELDS})
            fh.flush()
    print(f"   wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
