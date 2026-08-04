#!/usr/bin/env python3
"""Is the controlled-to-spontaneous ventilation transition detectable, and in both directions?

MECHANICAL FEASIBILITY PROBE (rule 41: run it BEFORE registering, not after a gate fails). Fetches only
three 1 Hz numeric ventilator/capnography tracks and never touches an EEG waveform, BIS, or a candidate
feature. It answers one question -- can a state label be built from the airway record -- and reports
numbers without choosing any threshold.

WHY THIS LABEL. The investigator has relaxed Challenge A's criterion (c), which previously required a
state label that is neither the monitor nor the drug. Relaxing it admits two obvious labels and both are
circular for THIS challenge:

  * the DRUG RECORD (MAC, propofol Ce) makes "tracks state" and "follows the drug" the same quantity, and
    Challenge A's whole statistic is the separation between them;
  * BIS is computed from the same EEG a candidate is computed from, so label and candidate share the
    measurement act (rules 28 and 86).

The airway record is neither. Ventilation state is a BEHAVIOURAL OUTPUT -- brainstem-mediated -- and it
is independent of which agent was used and of the cortical EEG. It moves in BOTH directions within a
single case: spontaneous -> controlled at induction, controlled -> spontaneous at emergence. That is the
one label available on this deposit that is not the drug and not the EEG.

**AND IT IS NOT CONSCIOUSNESS.** Brief 01 exists to separate arousal, cognitive processing,
command-following and behavioural output; this measures the last of those, at the brainstem. A design
built on it tests "tracks loss and recovery of a behavioural output across agents", which is weaker than
the briefed construct. That weakening is exactly what relaxing (c) buys and it must be stated in any
result, not discovered by a reader.

WHAT IS MEASURED, per case, WITHOUT choosing a threshold:
  * coverage of each track and how much of it is finite
  * the distribution of measured respiratory rate (`Primus/RR_CO2`) against the ventilator's SET rate
    (`Primus/SET_RR_IPPV`) -- under controlled ventilation these agree; under spontaneous breathing the
    measured rate departs from the set rate and becomes variable
  * how many times, and when relative to `aneend`, the two series separate and re-converge
  * the same quantities relative to a deterministic mid-case placebo time, so that "a separation happens
    somewhere" can be told apart from "a separation happens AT the transition" before any threshold is
    picked (rule 34, and rule 64's random-split control)

It reports the raw distributions. **It does not decide what counts as a transition** -- that decision
belongs in a registration written after these numbers are known (rule 41: a probe that reports numbers,
never one that chooses thresholds).

    python bsde/scripts/vitaldb_ventilation_probe.py --out bsde/results/vitaldb_vent_probe.csv --limit 150
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import math
import os
import statistics
import time
import urllib.error
import urllib.request

API = "https://api.vitaldb.net"
NEED = ("BIS/EEG1_WAV", "Primus/MAC", "Primus/RR_CO2", "Primus/SET_RR_IPPV")
AGENTS = {"sevo": "Primus/EXP_SEVO", "des": "Primus/EXP_DES", "ppf": "Orchestra/PPF20_CE"}
GRID = 10.0                                     # s, the resolution both series are placed on
FIELDS = ["caseid", "subjectid", "aneend_s", "anestart_s", "agents", "arm",
          "n_rr", "n_set", "n_grid", "frac_both_finite",
          "med_abs_diff_all", "med_abs_diff_mid", "med_abs_diff_post",
          "frac_sep_mid", "frac_sep_post", "frac_sep_pre",
          "first_sep_after_aneend_s", "last_agree_before_aneend_s",
          "frac_sep_early", "t_first_agree_s", "t_last_agree_s", "rec_start_rel_aneend_s",
          "placebo_t_s", "frac_sep_placebo_post", "ane_type", "age", "sex", "asa", "error"]


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


def _grid(series, lo, hi):
    """Last-observation-carried-forward onto a GRID-second lattice; NaN before the first sample."""
    n = int((hi - lo) / GRID) + 1
    out = [float("nan")] * n
    j, cur = 0, float("nan")
    for i in range(n):
        t = lo + i * GRID
        while j < len(series) and series[j][0] <= t:
            cur = series[j][1]
            j += 1
        out[i] = cur
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--all", action="store_true",
                    help="every eligible case including the mixed-agent arm, sharded, instead of a "
                         "balanced sample of the single-agent arms")
    a = ap.parse_args(argv)

    trks = list(csv.DictReader(io.StringIO(_fetch(f"{API}/trks"))))
    cases = {r["caseid"]: r for r in csv.DictReader(io.StringIO(_fetch(f"{API}/cases")))}
    tmap = {}
    for r in trks:
        tmap.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]

    elig = []
    for cid, tm in tmap.items():
        if not set(NEED) <= set(tm):
            continue
        c = cases.get(cid)
        ae, as_ = _f((c or {}).get("aneend")), _f((c or {}).get("anestart"))
        if c is None or not (math.isfinite(ae) and 0.0 < ae < 200000.0):
            continue
        present = [k for k, t in AGENTS.items() if t in tm]
        arm = present[0] if len(present) == 1 else ("mixed" if present else "none")
        elig.append((cid, arm))
    # a BALANCED sample across arms, so the probe cannot be dominated by the largest one
    by_arm = {}
    for cid, arm in elig:
        by_arm.setdefault(arm, []).append(cid)
    for k in by_arm:
        by_arm[k].sort(key=lambda x: int(x))
    print("[probe] eligible by arm: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(by_arm.items())),
          flush=True)
    arm_of = dict(elig)
    if a.all:
        mine = sorted((cid for cid, _ in elig), key=lambda x: int(x))
        mine = [c for i, c in enumerate(mine) if i % a.of == a.shard]
        per = 0
    else:
        per = max(1, a.limit // max(1, len([k for k in by_arm if k in ("sevo", "des", "ppf")])))
        mine = []
        for k in ("sevo", "des", "ppf"):
            mine += by_arm.get(k, [])[:per]

    done = set()
    if os.path.exists(a.out) and os.path.getsize(a.out) > 0:
        with open(a.out) as fh:
            for r in csv.DictReader(fh):
                done.add(r.get("caseid"))
    todo = [c for c in mine if c not in done]
    print(f"[probe] {len(mine)} cases ({'ALL, sharded' if a.all else str(per) + ' per single-agent arm'}), {len(todo)} to fetch",
          flush=True)

    fh = open(a.out, "a" if done else "w", newline="")
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if not done:
        w.writeheader()

    for k, cid in enumerate(todo):
        c, tm = cases[cid], tmap[cid]
        ae, as_ = _f(c.get("aneend")), _f(c.get("anestart"))
        row = {f: "" for f in FIELDS}
        row.update({"caseid": cid, "subjectid": c.get("subjectid", ""), "aneend_s": ae,
                    "anestart_s": as_, "arm": arm_of.get(cid, "?"),
                    "agents": "|".join(sorted(k2 for k2, t in AGENTS.items() if t in tm)),
                    "ane_type": c.get("ane_type", ""), "age": c.get("age", ""),
                    "sex": c.get("sex", ""), "asa": c.get("asa", "")})
        try:
            rr = _numeric(_fetch(f"{API}/{tm['Primus/RR_CO2']}"))
            st = _numeric(_fetch(f"{API}/{tm['Primus/SET_RR_IPPV']}"))
            row["n_rr"], row["n_set"] = len(rr), len(st)
            lo, hi = 0.0, max(ae + 1200.0, (rr[-1][0] if rr else ae))
            g_rr, g_st = _grid(rr, lo, hi), _grid(st, lo, hi)
            n = len(g_rr)
            row["n_grid"] = n
            both = [i for i in range(n) if math.isfinite(g_rr[i]) and math.isfinite(g_st[i])]
            row["frac_both_finite"] = round(len(both) / n, 4) if n else ""
            diff = {i: abs(g_rr[i] - g_st[i]) for i in both}
            if diff:
                row["med_abs_diff_all"] = round(statistics.median(diff.values()), 3)

            def rel(i):
                return lo + i * GRID - ae

            h = int(hashlib.sha256(cid.encode()).hexdigest()[:12], 16) / float(1 << 48)
            plo, phi = max(0.0, as_ if math.isfinite(as_) else 0.0) + 1800.0, ae - 1800.0
            pt = plo + h * (phi - plo) if phi > plo else float("nan")
            row["placebo_t_s"] = round(pt, 1) if math.isfinite(pt) else ""

            def window(idx, centre, w0, w1):
                return [i for i in idx if w0 <= (lo + i * GRID - centre) <= w1]

            mid = window(both, ae, -3600.0, -1800.0)
            pre = window(both, ae, -900.0, -300.0)
            post = window(both, ae, 0.0, 900.0)
            for name, idx in (("mid", mid), ("post", post)):
                if idx:
                    row[f"med_abs_diff_{name}"] = round(statistics.median(diff[i] for i in idx), 3)
            # "separated" is reported at a RANGE of candidate cut-offs rather than one, so the probe
            # reports a distribution and the registration picks the cut-off knowing it (rule 63).
            for name, idx in (("mid", mid), ("pre", pre), ("post", post)):
                if idx:
                    row[f"frac_sep_{name}"] = round(sum(1 for i in idx if diff[i] >= 2.0) / len(idx), 4)
            if math.isfinite(pt):
                pidx = window(both, pt, 0.0, 900.0)
                if pidx:
                    row["frac_sep_placebo_post"] = round(
                        sum(1 for i in pidx if diff[i] >= 2.0) / len(pidx), 4)
            # THE LOSS DIRECTION. If the record begins while the patient is still breathing
            # spontaneously, an early separated stretch is followed by agreement once controlled
            # ventilation starts. If the record begins after intubation there is nothing to see, which
            # is a property of the deposit and must be counted rather than assumed either way (rule 5).
            early = [i for i in both if 0.0 <= lo + i * GRID <= 600.0]
            if early:
                row["frac_sep_early"] = round(sum(1 for i in early if diff[i] >= 2.0) / len(early), 4)
            agree = [i for i in both if diff[i] < 2.0]
            row["t_first_agree_s"] = round(lo + agree[0] * GRID, 1) if agree else ""
            row["t_last_agree_s"] = round(lo + agree[-1] * GRID, 1) if agree else ""
            row["rec_start_rel_aneend_s"] = round(lo - ae, 1)

            aft = [i for i in both if rel(i) >= 0 and diff[i] >= 2.0]
            row["first_sep_after_aneend_s"] = round(rel(aft[0]), 1) if aft else ""
            bef = [i for i in both if rel(i) < 0 and diff[i] < 2.0]
            row["last_agree_before_aneend_s"] = round(rel(bef[-1]), 1) if bef else ""
        except Exception as e:
            row["error"] = f"{type(e).__name__}: {e}"[:200]
        w.writerow(row)
        fh.flush()
        os.fsync(fh.fileno())
        if (k + 1) % 50 == 0:
            print(f"[probe] {k + 1}/{len(todo)}", flush=True)
    fh.close()
    print("[probe] complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
