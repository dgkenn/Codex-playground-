#!/usr/bin/env python3
"""Turn the ventilation probe's output into per-case landmarks, and DERIVE the rule from its distribution.

MECHANICAL, NOT AN EXPERIMENT. Reads the probe's summary table and the two 1 Hz ventilator tracks; never
touches an EEG waveform, BIS, or a candidate feature.

Two modes, and the separation is the point (rule 41: a probe reports numbers, a registration chooses
thresholds, and the choosing happens once and in the open):

  --report   print the distributions that the landmark rule has to be chosen against, and stop.
  --emit     apply the rule with the arguments given and write per-case landmarks plus a window plan.

WHY THE RULE NEEDS DERIVING RATHER THAN PICKING. Under controlled ventilation the measured respiratory
rate equals the ventilator's set rate exactly, so |RR - SET| is a hard zero, not a small number. That
makes the SEPARATION threshold easy and the SUSTAIN duration the real choice: a single stray sample of
disagreement is a dropped capnography packet, not a breath. The probe measured, on a balanced 30-case
sample, a median |RR - SET| of 0.0 in deep maintenance and 0.000-0.089 separated fraction at a mid-case
placebo landmark, against ~1.00 after the transition. The sustain length is set here from the observed
run-length distribution of spurious separations in the maintenance window -- i.e. from what the noise
actually does -- and NOT from a round number (rule 63).

LANDMARKS, per case:
  t_loss   the END of the last sustained SEPARATED run that precedes the first sustained AGREEING run
           -- the patient stops breathing for themselves and controlled ventilation takes over.
  t_rec    the END of the last sustained AGREEING run -- controlled ventilation stops carrying the
           patient and spontaneous breathing resumes.

Both are transitions of the same binary in opposite directions, inside one case, which is what
Challenge A's criterion (b) asks for and what no other label on this deposit supplies.

WINDOWS. A FIXED number of FIXED-length windows at FIXED offsets from each landmark, identical for every
case. That is not a stylistic choice: E154 found recording duration identified the anaesthetic agent at
|AUC-0.5| = 0.3771, above every candidate feature, because sevoflurane cases run longer. Any summary
whose window count or span depends on case length re-imports that confound. With a fixed grid, recording
length cannot enter the summary at all.

    python bsde/scripts/vitaldb_vent_landmarks.py --report
    python bsde/scripts/vitaldb_vent_landmarks.py --emit --sustain-s <derived> --out ...
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import io
import json
import math
import os
import statistics
import time
import urllib.error
import urllib.request

API = "https://api.vitaldb.net"
GRID = 10.0
SEP = 2.0                       # breaths/min; |RR - SET| at or above this is "separated"
OFFSETS = [float(x) for x in range(-300, 301, 30)]   # 21 windows per landmark, fixed for every case
WIN_S = 10.0
AGENTS = {"sevo": "Primus/EXP_SEVO", "des": "Primus/EXP_DES", "ppf": "Orchestra/PPF20_CE"}


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
    n = int((hi - lo) / GRID) + 1
    out, j, cur = [float("nan")] * n, 0, float("nan")
    for i in range(n):
        t = lo + i * GRID
        while j < len(series) and series[j][0] <= t:
            cur = series[j][1]
            j += 1
        out[i] = cur
    return out


def runs(flags):
    """[(value, start_index, length)] over a list of 0/1/None, skipping None."""
    out = []
    for i, v in enumerate(flags):
        if v is None:
            continue
        if out and out[-1][0] == v and out[-1][1] + out[-1][2] == i:
            out[-1][2] += 1
        else:
            out.append([v, i, 1])
    return [tuple(r) for r in out]


def report(paths):
    """Print the run-length distribution of SPURIOUS separations during deep maintenance.

    This is the number the sustain rule has to clear. If a stray separation almost never lasts more than
    k grid steps, a sustain of k+1 makes the landmark robust to dropped packets without erasing real
    transitions -- and it is derived rather than chosen.
    """
    rows = []
    for p in sorted(paths):
        with open(p) as fh:
            rows += [r for r in csv.DictReader(fh) if not (r.get("error") or "")]
    print(f"[report] {len(rows)} probe rows")
    for k in ("frac_sep_mid", "frac_sep_pre", "frac_sep_post", "frac_sep_placebo_post",
              "frac_sep_early", "frac_both_finite"):
        v = sorted(_f(r.get(k)) for r in rows if r.get(k) not in (None, ""))
        v = [x for x in v if math.isfinite(x)]
        if not v:
            print(f"  {k:24s} (empty)")
            continue
        q = lambda p_: v[min(len(v) - 1, int(p_ * len(v)))]
        print(f"  {k:24s} n={len(v):5d}  median {statistics.median(v):7.4f}  "
              f"q10 {q(.10):7.4f}  q90 {q(.90):7.4f}")
    rel = [_f(r.get("t_last_agree_s")) - _f(r.get("aneend_s")) for r in rows
           if r.get("t_last_agree_s") and r.get("aneend_s")]
    rel = sorted(x for x in rel if math.isfinite(x))
    if rel:
        print(f"\n  recovery landmark relative to aneend: n={len(rel)} median "
              f"{statistics.median(rel):+.0f} s, q10 {rel[int(.1*len(rel))]:+.0f}, "
              f"q90 {rel[int(.9*len(rel))]:+.0f}")
    first = sorted(_f(r.get("t_first_agree_s")) for r in rows if r.get("t_first_agree_s"))
    first = [x for x in first if math.isfinite(x)]
    if first:
        print(f"  loss landmark (first sustained agreement): n={len(first)} median "
              f"{statistics.median(first):.0f} s into the record, q10 {first[int(.1*len(first))]:.0f}, "
              f"q90 {first[int(.9*len(first))]:.0f}")
    arms = {}
    for r in rows:
        arms[r.get("arm", "?")] = arms.get(r.get("arm", "?"), 0) + 1
    print("\n  arm sizes:", ", ".join(f"{k}={v}" for k, v in sorted(arms.items())))
    print("\nCHOOSE THE SUSTAIN LENGTH FROM THE frac_sep_mid COLUMN ABOVE AND WRITE IT INTO THE")
    print("REGISTRATION BEFORE RUNNING --emit. It is the only free parameter in the landmark rule.")


def measure_runs(paths, n_cases=60):
    """The RUN-LENGTH distribution of spurious separations during deep maintenance.

    The report's `frac_sep_mid` gives the RATE of spurious separation, and a sustain length derived from
    a rate alone assumes the spurious samples are independent. They are not -- a dropped capnography
    packet or a brief spontaneous effort lasts several samples -- so the rate would understate the
    sustain needed by a large factor. This measures the thing the rule actually has to clear.
    """
    rows = []
    for p in sorted(paths):
        with open(p) as fh:
            rows += [r for r in csv.DictReader(fh) if not (r.get("error") or "")]
    rows = [r for r in rows if r.get("arm") in ("sevo", "des", "ppf")]
    rows.sort(key=lambda r: int(r["caseid"]))
    step = max(1, len(rows) // n_cases)
    sample = rows[::step][:n_cases]
    trks = list(csv.DictReader(io.StringIO(_fetch(f"{API}/trks"))))
    tmap = {}
    for r in trks:
        tmap.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]
    lens, mirror = [], []
    used = mirror_cases = 0
    for r in sample:
        cid = r["caseid"]
        try:
            tm = tmap[cid]
            rr = _numeric(_fetch(f"{API}/{tm['Primus/RR_CO2']}"))
            st = _numeric(_fetch(f"{API}/{tm['Primus/SET_RR_IPPV']}"))
            ae = _f(r.get("aneend_s"))
            lo, hi = ae - 3600.0, ae - 1800.0          # deep maintenance only
            if lo < 0:
                continue
            g_rr, g_st = _grid(rr, lo, hi), _grid(st, lo, hi)
            flags = [None if not (math.isfinite(a) and math.isfinite(b)) else
                     (1 if abs(a - b) >= SEP else 0) for a, b in zip(g_rr, g_st)]
            lens += [x[2] for x in runs(flags) if x[0] == 1]
            # The MIRROR direction. A sustain derived only from spurious SEPARATIONS during controlled
            # ventilation is one-sided: the landmark rule can equally be corrupted by a spurious
            # AGREEMENT during spontaneous breathing, which would manufacture a false agreeing run and
            # move t_rec. Same statistic, opposite background, measured in the post-recovery window.
            plo, phi = ae + 300.0, ae + 1500.0
            gp_rr, gp_st = _grid(rr, plo, phi), _grid(st, plo, phi)
            pf = [None if not (math.isfinite(x) and math.isfinite(y)) else
                  (1 if abs(x - y) >= SEP else 0) for x, y in zip(gp_rr, gp_st)]
            if sum(1 for v in pf if v == 1) >= 10:      # only where spontaneous breathing is the state
                mirror.extend(x[2] for x in runs(pf) if x[0] == 0)
                mirror_cases += 1
            used += 1
        except Exception:
            continue
    lens.sort()
    print(f"[runs] {used} cases, maintenance window [aneend-3600, aneend-1800]")
    print(f"[runs] {len(lens)} spurious separated runs")
    if not lens:
        print("[runs] none at all -- any sustain >= 1 grid step suffices")
        return
    q = lambda p_: lens[min(len(lens) - 1, int(p_ * len(lens)))]
    print(f"[runs] run length in {GRID:.0f} s steps: median {statistics.median(lens):.0f}  "
          f"q90 {q(.90):.0f}  q95 {q(.95):.0f}  q99 {q(.99):.0f}  max {lens[-1]:.0f}")
    mirror.sort()
    print(f"[runs] MIRROR: {mirror_cases} cases with spontaneous breathing in [aneend+300, aneend+1500], "
          f"{len(mirror)} spurious AGREEING runs")
    if mirror:
        mq = lambda p_: mirror[min(len(mirror) - 1, int(p_ * len(mirror)))]
        print(f"[runs] MIRROR run length: median {statistics.median(mirror):.0f}  q90 {mq(.90):.0f}  "
              f"q99 {mq(.99):.0f}  max {mirror[-1]:.0f}")
    print(f"\n{'sustain':>16} {'sep runs/case':>15} {'agree runs/case':>17}")
    for k in (1, 2, 3, 4, 6, 9, 12, 18, 24, 30):
        a = sum(1 for x in lens if x >= k) / max(1, used)
        b = sum(1 for x in mirror if x >= k) / max(1, mirror_cases)
        print(f"{k:3d} steps ({k*GRID:5.0f} s) {a:15.2f} {b:17.2f}")
    print("\nPICK THE SMALLEST SUSTAIN AT WHICH BOTH COLUMNS ARE WELL BELOW 1 PER CASE. One false run")
    print("per case would corrupt the landmark in most cases, and the rule has to survive BOTH")
    print("directions -- a spurious separation during controlled ventilation and a spurious agreement")
    print("during spontaneous breathing corrupt different landmarks.")


def emit(paths, sustain_s, out_path, plan_path, limit=0, shard=0, of=1):
    need = int(round(sustain_s / GRID))
    rows = []
    for p in sorted(paths):
        with open(p) as fh:
            rows += [r for r in csv.DictReader(fh) if not (r.get("error") or "")]
    rows = [r for r in rows if r.get("arm") in ("sevo", "des", "ppf")]
    rows.sort(key=lambda r: int(r["caseid"]))
    rows = [r for i, r in enumerate(rows) if i % of == shard]
    if limit:
        rows = rows[:limit]

    trks = list(csv.DictReader(io.StringIO(_fetch(f"{API}/trks"))))
    tmap = {}
    for r in trks:
        tmap.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]

    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path) as fh:
            for r in csv.DictReader(fh):
                done.add(r.get("caseid"))
    fields = ["caseid", "subjectid", "arm", "aneend_s", "t_loss_s", "t_rec_s",
              "n_sep_runs", "n_agree_runs", "loss_ok", "rec_ok", "error"]
    fh = open(out_path, "a" if done else "w", newline="")
    w = csv.DictWriter(fh, fieldnames=fields)
    if not done:
        w.writeheader()

    todo = [r for r in rows if r["caseid"] not in done]
    print(f"[emit] sustain {sustain_s:.0f} s = {need} grid steps | {len(todo)} cases to fetch", flush=True)
    for k, r in enumerate(todo):
        cid = r["caseid"]
        row = {f: "" for f in fields}
        row.update({"caseid": cid, "subjectid": r.get("subjectid", ""), "arm": r.get("arm", ""),
                    "aneend_s": r.get("aneend_s", "")})
        try:
            tm = tmap[cid]
            rr = _numeric(_fetch(f"{API}/{tm['Primus/RR_CO2']}"))
            st = _numeric(_fetch(f"{API}/{tm['Primus/SET_RR_IPPV']}"))
            ae = _f(r.get("aneend_s"))
            lo, hi = 0.0, max(ae + 1200.0, rr[-1][0] if rr else ae)
            g_rr, g_st = _grid(rr, lo, hi), _grid(st, lo, hi)
            flags = [None if not (math.isfinite(a) and math.isfinite(b)) else
                     (1 if abs(a - b) >= SEP else 0) for a, b in zip(g_rr, g_st)]
            rs = [x for x in runs(flags) if x[2] >= need]
            row["n_sep_runs"] = sum(1 for x in rs if x[0] == 1)
            row["n_agree_runs"] = sum(1 for x in rs if x[0] == 0)
            agree = [x for x in rs if x[0] == 0]
            if agree:
                first_agree = agree[0]
                last_agree = agree[-1]
                row["t_loss_s"] = round(lo + first_agree[1] * GRID, 1)
                row["t_rec_s"] = round(lo + (last_agree[1] + last_agree[2]) * GRID, 1)
                row["loss_ok"] = 1 if any(x[0] == 1 and x[1] < first_agree[1] for x in rs) else 0
                row["rec_ok"] = 1 if any(x[0] == 1 and x[1] > last_agree[1] for x in rs) else 0
        except Exception as e:
            row["error"] = f"{type(e).__name__}: {e}"[:200]
        w.writerow(row)
        fh.flush()
        os.fsync(fh.fileno())
        if (k + 1) % 100 == 0:
            print(f"[emit] {k + 1}/{len(todo)}", flush=True)
    fh.close()

    plan = {}
    with open(out_path) as f2:
        for r in csv.DictReader(f2):
            times = []
            for key, ok in (("t_loss_s", "loss_ok"), ("t_rec_s", "rec_ok")):
                t0 = _f(r.get(key))
                if math.isfinite(t0) and (r.get(ok) == "1"):
                    times += [round(t0 + o, 1) for o in OFFSETS if t0 + o >= 0]
            if times:
                plan[r["caseid"]] = sorted(set(times))
    json.dump(plan, open(plan_path, "w"))
    n_win = sum(len(v) for v in plan.values())
    print(f"[emit] plan: {len(plan)} cases, {n_win} windows ({WIN_S:.0f} s each, "
          f"{len(OFFSETS)} fixed offsets per landmark) -> {plan_path}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--glob", default="bsde/results/vitaldb_vent_probe.s*.csv")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--measure-runs", type=int, default=0,
                    help="fetch N cases and measure the run-length distribution of spurious "
                         "separations in deep maintenance, which is what the sustain rule must clear")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--sustain-s", type=float, default=None)
    ap.add_argument("--out", default="bsde/results/vitaldb_vent_landmarks.csv")
    ap.add_argument("--plan", default="bsde/results/vitaldb_ventwin_plan.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)
    paths = sorted(glob.glob(a.glob))
    if not paths:
        print("no probe output matched", a.glob)
        return 2
    if a.measure_runs:
        measure_runs(paths, a.measure_runs)
        return 0
    if a.report or not a.emit:
        report(paths)
        return 0
    if a.sustain_s is None:
        print("--emit requires --sustain-s, derived from --report and written into the registration first")
        return 2
    emit(paths, a.sustain_s, a.out, a.plan, a.limit, a.shard, a.of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
