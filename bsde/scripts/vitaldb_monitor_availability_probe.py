#!/usr/bin/env python3
"""How long does the BIS monitor stay attached across emergence? A population-scale feasibility probe.

MECHANICAL EXTRACTION, NOT AN EXPERIMENT. This script fetches only `BIS/BIS` and `BIS/SQI` -- the
monitor's own two 1 Hz numeric tracks -- and never touches an EEG waveform, a candidate feature or an
outcome. It computes, per case, WHEN the monitor has a valid reading relative to `aneend`, and nothing
else. Nothing here can be a result about a measure.

WHY IT EXISTS (catalogue rule 41: run the feasibility probe BEFORE registering, not after failing).
E246 registered a timing experiment against BIS on 134 VitalDB cases and its incumbent-aliveness gate
failed at 0.343. The measured reason was not that BIS is slow: cases carrying any finite BIS in 200 s
bins from `aneend` go 130 / 120 / 73 / 33 / 14 / 5, while the same bins for an EEG measure go
134 / 134 / 134 / 134 / 121 / 71. **The sensor comes off before emergence completes.** The adapter's own
module docstring had said so in words ("the EEG runs past `aneend` and the BIS strip does not"); E246
re-measured it the expensive way.

The successor design must restrict to the stratum where the monitor is present THROUGH the transition,
report that exclusion, and check whether it is outcome-related (rule 14) -- so the first thing anyone
needs is the size and composition of that stratum across all 5,867 eligible cases, not 134.

AND IT IS 20-50x CHEAPER THAN FINDING OUT THE OTHER WAY. One `BIS/EEG1_WAV` track is ~9.4 MB; the two
numeric tracks together are ~100-200 kB. Extracting EEG for all 5,870 eligible cases would be ~55 GB of
downloads against a fixed disk allowance, most of it spent on cases the successor will exclude anyway.
This probe decides which cases are worth the waveform fetch.

DETACHED-SENSOR HANDLING is taken from the adapter rather than reinvented: `BIS/BIS` emits a literal
`0.0` while the sensor is off and 0 is inside the index's valid range, so validity is a POSITIVE test on
`BIS/SQI > 0` (vitaldb.py's docstring, defect 1). A sample is counted only where SQI is available and
above zero.

OUTPUT, one row per case, appended and resumable (rule 56: de-duplicate on the key when loading, and
never assume you were the only writer):

    caseid, subjectid, aneend_s, n_bis, n_valid, first_valid_rel, last_valid_rel,
    valid_at_m300, valid_at_m100, valid_at_0, valid_at_p100, valid_at_p300, valid_at_p600,
    frac_valid_pre, frac_valid_post, ane_type, age, sex, asa, error

`valid_at_X` is 1 when at least one SQI-positive BIS sample falls within +/-30 s of `aneend + X`. The
+/-30 s tolerance is derived from the sampling: BIS is nominally 1 Hz but drops packets, so a single
instant is not a reliable test of presence and a half-minute either side is the smallest span that is
robust to that without smearing across the 100 s grid it is placed on.

    python bsde/scripts/vitaldb_monitor_availability_probe.py --out bsde/results/vitaldb_bis_availability.csv
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import math
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.vitaldb.net"
OFFSETS = (-300.0, -100.0, 0.0, 100.0, 300.0, 600.0)
TOL = 30.0
FIELDS = ["caseid", "subjectid", "aneend_s", "n_bis", "n_valid", "first_valid_rel", "last_valid_rel",
          *[f"valid_at_{'m' if o < 0 else 'p'}{abs(int(o))}" for o in OFFSETS],
          "frac_valid_pre", "frac_valid_post", "ane_type", "age", "sex", "asa", "error"]


def _fetch(url: str, timeout: float = 300.0, tries: int = 5) -> str:
    last = None
    for i in range(tries):
        try:
            blob = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"}), timeout=timeout).read()
            if blob[:2] == b"\x1f\x8b":
                blob = gzip.decompress(blob)
            return blob.decode("utf-8-sig", "replace")
        except (urllib.error.URLError, OSError, TimeoutError) as e:   # transient; back off and retry
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"fetch failed after {tries} tries: {url}: {last}")


def _f(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _numeric(text: str):
    """A VitalDB 1 Hz numeric track, as [(t, value)]. Header line, then `time,value` rows."""
    out = []
    for line in text.splitlines()[1:]:
        p = line.split(",")
        if len(p) < 2:
            continue
        t, v = _f(p[0]), _f(p[1])
        if math.isfinite(t) and math.isfinite(v):
            out.append((t, v))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    trks = list(csv.DictReader(io.StringIO(_fetch(f"{API}/trks"))))
    cases = {r["caseid"]: r for r in csv.DictReader(io.StringIO(_fetch(f"{API}/cases")))}
    tmap = {}
    for r in trks:
        tmap.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]

    eligible = []
    for cid, tm in tmap.items():
        if "BIS/BIS" not in tm or "BIS/SQI" not in tm or "BIS/EEG1_WAV" not in tm:
            continue
        c = cases.get(cid)
        if c is None:
            continue
        ae = _f(c.get("aneend"))
        if not (math.isfinite(ae) and 0.0 < ae < 200000.0):   # rule 5: case 4476 carries -3.69e9
            continue
        eligible.append(cid)
    eligible.sort(key=lambda x: int(x))
    mine = [c for i, c in enumerate(eligible) if i % a.of == a.shard]
    if a.limit:
        mine = mine[:a.limit]

    done = set()
    if os.path.exists(a.out) and os.path.getsize(a.out) > 0:
        with open(a.out) as fh:
            for r in csv.DictReader(fh):
                done.add(r.get("caseid"))
    todo = [c for c in mine if c not in done]
    print(f"[probe] eligible {len(eligible)} | shard {a.shard}/{a.of} -> {len(mine)} | "
          f"already done {len(mine) - len(todo)} | to fetch {len(todo)}", flush=True)

    fh = open(a.out, "a" if done else "w", newline="")
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if not done:
        w.writeheader()

    for k, cid in enumerate(todo):
        c, tm = cases[cid], tmap[cid]
        ae = _f(c.get("aneend"))
        row = {f: "" for f in FIELDS}
        row.update({"caseid": cid, "subjectid": c.get("subjectid", ""), "aneend_s": ae,
                    "ane_type": c.get("ane_type", ""), "age": c.get("age", ""),
                    "sex": c.get("sex", ""), "asa": c.get("asa", "")})
        try:
            bis = _numeric(_fetch(f"{API}/{tm['BIS/BIS']}"))
            sqi = {round(t): v for t, v in _numeric(_fetch(f"{API}/{tm['BIS/SQI']}"))}
            valid = [(t, v) for t, v in bis if sqi.get(round(t), 0.0) > 0.0]
            rel = sorted(t - ae for t, _ in valid)
            row["n_bis"] = len(bis)
            row["n_valid"] = len(valid)
            row["first_valid_rel"] = rel[0] if rel else ""
            row["last_valid_rel"] = rel[-1] if rel else ""
            for o in OFFSETS:
                key = f"valid_at_{'m' if o < 0 else 'p'}{abs(int(o))}"
                row[key] = 1 if any(abs(r - o) <= TOL for r in rel) else 0
            pre = [r for r in rel if -600.0 <= r < 0.0]
            post = [r for r in rel if 0.0 < r <= 600.0]
            row["frac_valid_pre"] = round(len(pre) / 600.0, 4)
            row["frac_valid_post"] = round(len(post) / 600.0, 4)
        except Exception as e:                                  # recorded per case, never fatal
            row["error"] = f"{type(e).__name__}: {e}"[:200]
        w.writerow(row)
        fh.flush()
        os.fsync(fh.fileno())
        if (k + 1) % 100 == 0:
            print(f"[probe] shard {a.shard}: {k + 1}/{len(todo)}", flush=True)
    fh.close()
    print(f"[probe] shard {a.shard} complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
