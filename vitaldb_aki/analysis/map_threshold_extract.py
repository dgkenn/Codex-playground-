"""map_threshold_extract.py -- resumable per-case MAP burden at a full threshold
grid (50..80 mmHg), so the MAP-target question can be analysed at 70/75 (the
confirmatory matrix only has 50/55/60/65). Writes cache/map_thresholds.csv,
one row per case; safe to re-run (skips caseids already written). Streams: the
per-case MAP track is purged after use to bound disk while discovery also runs.

Columns per case: caseid, map_mean, map_lowest, and for each T in THRESHOLDS:
  min_below_T  (minutes below T, time-weighted, 10s gap cap)
  auc_below_T  (mmHg*min area below T)
"""
import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

THRESHOLDS = [50, 55, 60, 65, 70, 75, 80]
MAP_CANDIDATES = ["Solar8000/ART_MBP", "Solar8000/NIBP_MBP", "EV1000/ART_MBP"]
MAP_MIN, MAP_MAX = 20.0, 200.0
MAX_DT = 10.0


def _burdens(samples):
    """time-weighted minutes below each T and mmHg*min AUC below each T."""
    mins = {T: 0.0 for T in THRESHOLDS}
    auc = {T: 0.0 for T in THRESHOLDS}
    for i in range(len(samples) - 1):
        t_i, v = samples[i]
        dt = min(samples[i + 1][0] - t_i, MAX_DT)
        if dt <= 0:
            continue
        for T in THRESHOLDS:
            if v < T:
                mins[T] += dt / 60.0
                auc[T] += (T - v) * dt / 60.0
    return mins, auc


def main():
    from common.config import load_yaml
    from vitaldb_aki.data.tracks import download_track, first_available, tid_for
    from vitaldb_aki.features.pfds import _intraop_window, _clip_to_window, _filter_physiologic
    from vitaldb_aki.data.client import fetch_cases

    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cdir = cfg["data"]["cache_dir"]
    out = os.path.join(cdir, "map_thresholds.csv")
    tdir = os.path.join(cdir, "tracks")

    # cohort
    with open(os.path.join(cdir, "cohort_composite.csv"), newline="") as fh:
        caseids = [r["caseid"] for r in csv.DictReader(fh)]
    cases = {str(c["caseid"]): c for c in fetch_cases(cfg)}

    done = set()
    if os.path.exists(out):
        with open(out, newline="") as fh:
            done = {r["caseid"] for r in csv.DictReader(fh)}
    cols = (["caseid", "map_mean", "map_lowest"]
            + [f"min_below_{T}" for T in THRESHOLDS]
            + [f"auc_below_{T}" for T in THRESHOLDS])
    new = not os.path.exists(out)
    fh = open(out, "a", newline="")
    w = csv.DictWriter(fh, fieldnames=cols)
    if new:
        w.writeheader()
    n = 0
    for cid in caseids:
        if cid in done:
            continue
        case = cases.get(str(cid))
        row = {c: "" for c in cols}
        row["caseid"] = cid
        if case is not None:
            t0, t1 = _intraop_window(case)
            tname, raw = first_available(cfg, str(cid), MAP_CANDIDATES)
            if raw:
                s = _filter_physiologic(_clip_to_window(raw, t0, t1), MAP_MIN, MAP_MAX)
                if len(s) >= 2:
                    row["map_mean"] = round(sum(v for _, v in s) / len(s), 3)
                    row["map_lowest"] = round(min(v for _, v in s), 3)
                    mins, auc = _burdens(s)
                    for T in THRESHOLDS:
                        row[f"min_below_{T}"] = round(mins[T], 4)
                        row[f"auc_below_{T}"] = round(auc[T], 4)
                # purge the MAP track file (bound disk; discovery is also running)
                tid = tid_for(cfg, str(cid), tname) if tname else None
                if tid:
                    try:
                        os.remove(os.path.join(tdir, f"{tid}.csv"))
                    except OSError:
                        pass
        w.writerow(row)
        n += 1
        if n % 50 == 0:
            fh.flush()
            print(f"[map_thr] {n} new cases written ({len(done)+n}/{len(caseids)})", flush=True)
    fh.close()
    open(os.path.join(cdir, "_map_thresholds_done.json"), "w").write("{}")
    print(f"[map_thr] DONE: {len(done)+n}/{len(caseids)} cases -> {out}", flush=True)


if __name__ == "__main__":
    main()
