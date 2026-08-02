#!/usr/bin/env python3
"""Monitor availability as a CURVE, against the real landmark and against a placebo landmark.

MECHANICAL EXTRACTION, NOT AN EXPERIMENT. Fetches only `BIS/BIS` and `BIS/SQI` -- the monitor's two 1 Hz
numeric tracks -- and never touches an EEG waveform, a candidate feature or an outcome. It reports where
in time the monitor has a valid reading, and nothing else.

SUPERSEDES `vitaldb_monitor_availability_probe.py`, which recorded only six offsets and no placebo. Two
things had to be added and neither could be recovered from the first probe's summaries:

  1. **A PLACEBO LANDMARK.** A monotone decline in signal quality across any long recording would produce
     a falling curve around `aneend` with nothing to do with emergence. The control is the identical
     curve computed around a random MID-CASE time, at least 1,800 s from either transition -- same case,
     same track, same code path, no transition (rule 34; and rule 64, since a landmark placed near the
     end of a recording is a time split in disguise unless a random split is run beside it). The draw is
     seeded from the case id so it is reproducible and cannot be re-rolled.
  2. **THREE SQI THRESHOLDS.** `BIS/BIS` emits a literal 0.0 when the index is unavailable, so `SQI > 0`
     is the loosest possible validity test and OVERSTATES availability. The device's own guidance treats
     SQI below 50 as unreliable. Reporting >0, >=50 and >=80 makes the threshold a measured sensitivity
     rather than a choice, and the loosest one is the conservative direction for a claim that
     availability is LOW.

GRID: 60 s bins from -1800 s to +1800 s about each landmark, 60 bins. A bin counts as available if it
contains at least one sample meeting the threshold; `emit_*` counts a bin containing at least one sample
of any kind, which separates "the device stopped" from "the device says its output is unusable". That
separation is the whole point -- getting it wrong once already cost a wrong mechanism in a ledger row.

Output: one row per case, wide, appended and resumable, de-duplicated on `caseid` at load (rule 56).

    python bsde/scripts/vitaldb_monitor_availability_probe2.py --out bsde/results/vitaldb_bis_curve.csv
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import math
import os
import time
import urllib.error
import urllib.request

API = "https://api.vitaldb.net"
LO, HI, STEP = -1800.0, 1800.0, 60.0
NBIN = int((HI - LO) / STEP)                      # 60
THRESH = (("t0", 0.0), ("t50", 50.0), ("t80", 80.0))
BASE = ["caseid", "subjectid", "anestart_s", "aneend_s", "opdur_s", "n_bis", "n_valid_t0",
        "placebo_t_s", "placebo_ok", "ane_type", "age", "sex", "asa", "emop", "bmi", "error"]
FIELDS = BASE + [f"{arm}_{kind}_{i}" for arm in ("real", "plac")
                 for kind in ("emit", "t0", "t50", "t80") for i in range(NBIN)]


def _fetch(url: str, timeout: float = 300.0, tries: int = 5) -> str:
    last = None
    for i in range(tries):
        try:
            blob = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"}), timeout=timeout).read()
            if blob[:2] == b"\x1f\x8b":
                blob = gzip.decompress(blob)
            return blob.decode("utf-8-sig", "replace")
        except (urllib.error.URLError, OSError, TimeoutError) as e:
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
    out = []
    for line in text.splitlines()[1:]:
        p = line.split(",")
        if len(p) < 2:
            continue
        t, v = _f(p[0]), _f(p[1])
        if math.isfinite(t) and math.isfinite(v):
            out.append((t, v))
    out.sort()
    return out


def _placebo_time(cid: str, anestart: float, aneend: float):
    """A deterministic mid-case time >= 1800 s from either transition, or NaN if the case is too short."""
    lo = max(0.0, anestart if math.isfinite(anestart) else 0.0) + 1800.0
    hi = aneend - 1800.0
    if not math.isfinite(hi) or hi <= lo:
        return float("nan")
    h = int(hashlib.sha256(cid.encode()).hexdigest()[:12], 16) / float(1 << 48)
    return lo + h * (hi - lo)


def _bin(rel):
    b = int(math.floor((rel - LO) / STEP))
    return b if 0 <= b < NBIN else None


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
        if not {"BIS/BIS", "BIS/SQI", "BIS/EEG1_WAV"} <= set(tm):
            continue
        c = cases.get(cid)
        ae = _f((c or {}).get("aneend"))
        if c is None or not (math.isfinite(ae) and 0.0 < ae < 200000.0):
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
    print(f"[curve] eligible {len(eligible)} | shard {a.shard}/{a.of} -> {len(mine)} | "
          f"done {len(mine) - len(todo)} | to fetch {len(todo)}", flush=True)

    fh = open(a.out, "a" if done else "w", newline="")
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if not done:
        w.writeheader()

    for k, cid in enumerate(todo):
        c, tm = cases[cid], tmap[cid]
        ae, as_ = _f(c.get("aneend")), _f(c.get("anestart"))
        pt = _placebo_time(cid, as_, ae)
        row = {f: "" for f in FIELDS}
        row.update({"caseid": cid, "subjectid": c.get("subjectid", ""), "anestart_s": as_,
                    "aneend_s": ae, "opdur_s": (ae - as_) if math.isfinite(as_) else "",
                    "placebo_t_s": pt if math.isfinite(pt) else "",
                    "placebo_ok": 1 if math.isfinite(pt) else 0,
                    "ane_type": c.get("ane_type", ""), "age": c.get("age", ""),
                    "sex": c.get("sex", ""), "asa": c.get("asa", ""),
                    "emop": c.get("emop", ""), "bmi": c.get("bmi", "")})
        try:
            bis = _numeric(_fetch(f"{API}/{tm['BIS/BIS']}"))
            sqi = {round(t): v for t, v in _numeric(_fetch(f"{API}/{tm['BIS/SQI']}"))}
            row["n_bis"] = len(bis)
            row["n_valid_t0"] = sum(1 for t, _ in bis if sqi.get(round(t), 0.0) > 0.0)
            acc = {(arm, kind): [0] * NBIN
                   for arm in ("real", "plac") for kind in ("emit", "t0", "t50", "t80")}
            for arm, ref in (("real", ae), ("plac", pt)):
                if not math.isfinite(ref):
                    continue
                for t, _v in bis:
                    b = _bin(t - ref)
                    if b is None:
                        continue
                    acc[(arm, "emit")][b] = 1
                    q = sqi.get(round(t), 0.0)
                    for name, thr in THRESH:
                        # t0 is the loosest possible test (any positive SQI); t50/t80 are inclusive,
                        # matching how the device's guidance is written.
                        if (q > 0.0) if thr == 0.0 else (q >= thr):
                            acc[(arm, name)][b] = 1
            for (arm, kind), v in acc.items():
                if arm == "plac" and not math.isfinite(pt):
                    continue
                for i, x in enumerate(v):
                    row[f"{arm}_{kind}_{i}"] = x
        except Exception as e:
            row["error"] = f"{type(e).__name__}: {e}"[:200]
        w.writerow(row)
        fh.flush()
        os.fsync(fh.fileno())
        if (k + 1) % 100 == 0:
            print(f"[curve] shard {a.shard}: {k + 1}/{len(todo)}", flush=True)
    fh.close()
    print(f"[curve] shard {a.shard} complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
