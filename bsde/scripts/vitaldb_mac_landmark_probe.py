#!/usr/bin/env python3
"""Where is the anaesthetic actually switched off? A landmark probe on the drug record.

MECHANICAL EXTRACTION, NOT AN EXPERIMENT. Fetches only `Primus/MAC` -- the anaesthesia machine's own
minimum-alveolar-concentration figure, computed from end-tidal agent -- and never touches an EEG
waveform, a candidate feature, BIS or an outcome. It reports, per case, the shape of the agent's
withdrawal. Nothing here can be a result about a measure.

WHY (rule 41: the feasibility probe runs BEFORE the registration, not after the gate fails; rule 63: a
threshold must be derived from what the machinery can reach, not picked as a round number).

E246 landmarked on `aneend`, a charted administrative time, and its incumbent never reacted to it. The
successor moves the landmark onto an EXPOSURE (rule 86): the moment the agent stops being delivered.
That moment has to be DEFINED, and the definition cannot be invented at a desk -- it has to come from
the observed shape of MAC's descent. This probe measures that shape so the crossing rule can be written
down, with numbers behind it, before any candidate is computed.

WHAT IT MEASURES, per case:
  * `mac_max`             the case's peak MAC -- an aliveness check. A case whose vaporiser was never
                          opened has no withdrawal to find, and rule 87 says a track being PRESENT is a
                          fact about the machine, not about the patient: `Primus/MAC` logs on a
                          gas-capable machine whether or not any agent was ever given.
  * `t_last_above_X`      last time MAC >= X, for X in a ladder, relative to `aneend`
  * `t_first_below_X_after_peak`  the DESCENT crossing -- the candidate landmark
  * `descent_slope`       MAC units per second between the 0.6 and 0.2 crossings, so the steepness of
                          the switch-off is measured rather than assumed
  * `n_descents`          how many times MAC crosses 0.3 downward after being above 0.6. More than one
                          means the agent was turned down and back up, and a single "the agent was
                          switched off" landmark is then ill-defined for that case -- which is exactly
                          the kind of thing that must be counted before it is excluded (rule 14).

The ladder is 1.0 / 0.6 / 0.3 / 0.2 / 0.1 / 0.05 MAC. It is deliberately wider than any plausible final
choice so that the crossing rule can be selected from a measured distribution instead of the ladder
being quietly reshaped afterwards.

Output is one row per case, appended and resumable, de-duplicated on `caseid` at load (rule 56).

    python bsde/scripts/vitaldb_mac_landmark_probe.py --out bsde/results/vitaldb_mac_landmark.csv
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import math
import os
import time
import urllib.error
import urllib.request

API = "https://api.vitaldb.net"
LADDER = (1.0, 0.6, 0.3, 0.2, 0.1, 0.05)
FIELDS = (["caseid", "subjectid", "aneend_s", "n_mac", "mac_max", "t_mac_max_rel"]
          + [f"t_last_above_{str(x).replace('.', 'p')}" for x in LADDER]
          + [f"t_desc_below_{str(x).replace('.', 'p')}" for x in LADDER]
          + ["descent_slope", "n_descents", "ane_type", "age", "sex", "asa", "error"])


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
        if not {"BIS/BIS", "BIS/SQI", "BIS/EEG1_WAV", "Primus/MAC"} <= set(tm):
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
    print(f"[mac] eligible {len(eligible)} | shard {a.shard}/{a.of} -> {len(mine)} | "
          f"done {len(mine) - len(todo)} | to fetch {len(todo)}", flush=True)

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
            mac = _numeric(_fetch(f"{API}/{tm['Primus/MAC']}"))
            row["n_mac"] = len(mac)
            if mac:
                vmax = max(v for _, v in mac)
                tmax = max((v, t) for t, v in mac)[1]
                row["mac_max"] = round(vmax, 4)
                row["t_mac_max_rel"] = round(tmax - ae, 1)
                for x in LADDER:
                    ab = [t for t, v in mac if v >= x]
                    row[f"t_last_above_{str(x).replace('.', 'p')}"] = (round(ab[-1] - ae, 1) if ab else "")
                    aft = [t for t, v in mac if t > tmax and v < x]
                    row[f"t_desc_below_{str(x).replace('.', 'p')}"] = (round(aft[0] - ae, 1) if aft else "")
                d6 = [t for t, v in mac if t > tmax and v < 0.6]
                d2 = [t for t, v in mac if t > tmax and v < 0.2]
                if d6 and d2 and d2[0] > d6[0]:
                    row["descent_slope"] = round(-0.4 / (d2[0] - d6[0]), 6)
                nd, armed = 0, False
                for _, v in mac:
                    if v >= 0.6:
                        armed = True
                    elif armed and v < 0.3:
                        nd += 1
                        armed = False
                row["n_descents"] = nd
        except Exception as e:
            row["error"] = f"{type(e).__name__}: {e}"[:200]
        w.writerow(row)
        fh.flush()
        os.fsync(fh.fileno())
        if (k + 1) % 100 == 0:
            print(f"[mac] shard {a.shard}: {k + 1}/{len(todo)}", flush=True)
    fh.close()
    print(f"[mac] shard {a.shard} complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
