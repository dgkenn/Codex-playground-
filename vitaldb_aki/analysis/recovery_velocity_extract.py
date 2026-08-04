"""recovery_velocity_extract.py -- resumable per-case extraction of TRUE
post-nadir MAP recovery-velocity features from the raw numeric MAP time-series
(Solar8000/ART_MBP, ~0.5-2 Hz). The summary-statistic proxy (analysis/
reperfusion_dynamics.py) could not test the "how perfusion is restored" thesis;
this measures the actual rate at which MAP climbs back out of each hypotensive
episode.

Thesis under test: at MATCHED hypotension burden, a SLOW climb back from a
nadir (slow repayment of the perfusion debt) carries more organ-injury risk than
a fast one. Static burden (area/time below threshold) is blind to this -- two
cases with the same auc_below_65 can have very different recovery trajectories.

Cohort: cases with any MAP<65 episode (auc_below_65 > 0 in cache/map_thresholds.csv).
Recovery velocity is UNDEFINED without an episode, so restricting here both speeds
extraction and removes the no-episode artifact that contaminated the proxy version
(cases with no hypotension got a trivially tiny "lag").

Per-episode (contiguous run with MAP < REC_THRESH, MAX_DT gap cap):
  nadir   = min MAP in the run, at t_nadir
  recover = first sample after t_nadir with MAP >= REC_THRESH (else unrecovered)
  depth   = REC_THRESH - nadir                       (mmHg below target at the nadir)
  t_rec   = (t_recover - t_nadir)/60                 (minutes to climb back)
  slope   = depth / t_rec                            (mmHg/min, the recovery velocity)

Per-case features (cache/recovery_velocity.csv, one row per case):
  rv_n_episodes, rv_median_slope, rv_min_slope (slowest=worst), rv_mean_slope,
  rv_depthwt_slope = sum(depth)/sum(t_rec)  (overall debt-repayment rate),
  rv_max_time_to_recover, rv_frac_unrecovered, rv_total_unrecovered_min,
  rv_worst_depth, rv_median_tau (exp-decay time constant of the recovery limb).

Resumable (skips caseids already in the CSV); purges each MAP track after use to
bound disk while discovery/aline also run. stdlib only at module level (the
loaders import heavy deps lazily, matching repo convention).
"""
import csv
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

MAP_CANDIDATES = ["Solar8000/ART_MBP", "Solar8000/NIBP_MBP", "EV1000/ART_MBP"]
MAP_MIN, MAP_MAX = 20.0, 200.0
MAX_DT = 10.0          # gap cap (s): samples farther apart than this break an episode
REC_THRESH = 65.0      # hypotension / recovery-target threshold (mmHg)
MIN_DEPTH = 2.0        # ignore trivial dips (< 2 mmHg below threshold)
MIN_REC_MIN = 1.0 / 60 # floor on t_rec (1 s) to avoid divide-by-tiny slope blowups


def _episodes(samples):
    """Yield hypotensive episodes as (i_start, i_end_inclusive) index runs where
    MAP < REC_THRESH, breaking a run when the inter-sample gap exceeds MAX_DT."""
    runs = []
    i = 0
    n = len(samples)
    while i < n:
        if samples[i][1] < REC_THRESH:
            j = i
            while j + 1 < n and samples[j + 1][1] < REC_THRESH \
                    and (samples[j + 1][0] - samples[j][0]) <= MAX_DT:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def _tau_recovery(rec_pts, nadir_v):
    """Exponential time-constant (min) of the recovery limb: fit
    REC_THRESH - v(t) ~ depth0 * exp(-(t-t0)/tau) via OLS on log-gap. Returns None
    if too few points or non-decaying. rec_pts = [(t_s, v)] from nadir to recovery."""
    if len(rec_pts) < 4:
        return None
    t0 = rec_pts[0][0]
    xs, ys = [], []
    for t, v in rec_pts:
        gap = REC_THRESH - v
        if gap <= 0.5:           # essentially recovered; stop contributing
            continue
        xs.append((t - t0) / 60.0)
        ys.append(math.log(gap))
    if len(xs) < 3:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    sxy = sum((xs[k] - mx) * (ys[k] - my) for k in range(n))
    slope = sxy / sxx            # d(log gap)/dt; recovery => slope < 0, tau = -1/slope
    if slope >= -1e-6:
        return None
    return min(-1.0 / slope, 600.0)


def _recovery_features(samples):
    """Compute per-case recovery-velocity features from raw [(t_s, v)] MAP samples."""
    runs = _episodes(samples)
    slopes, depths, t_recs, taus = [], [], [], []
    n_unrec = 0
    total_unrec_min = 0.0
    worst_depth = 0.0
    n = len(samples)
    for (a, b) in runs:
        seg = samples[a:b + 1]
        nadir_v = min(v for _, v in seg)
        depth = REC_THRESH - nadir_v
        if depth < MIN_DEPTH:
            continue
        worst_depth = max(worst_depth, depth)
        # nadir index within the episode
        k_nadir = a + min(range(len(seg)), key=lambda k: seg[k][1])
        t_nadir = samples[k_nadir][0]
        # recovery point: first sample at/after nadir reaching REC_THRESH, no gap break
        rec_pts = [(samples[k_nadir][0], samples[k_nadir][1])]
        recovered = False
        k = k_nadir
        while k + 1 < n and (samples[k + 1][0] - samples[k][0]) <= MAX_DT:
            k += 1
            rec_pts.append((samples[k][0], samples[k][1]))
            if samples[k][1] >= REC_THRESH:
                recovered = True
                break
        if not recovered:
            n_unrec += 1
            total_unrec_min += max((rec_pts[-1][0] - t_nadir) / 60.0, 0.0)
            continue
        t_rec = max((samples[k][0] - t_nadir) / 60.0, MIN_REC_MIN)
        slopes.append(depth / t_rec)            # mmHg/min recovery velocity
        depths.append(depth)
        t_recs.append(t_rec)
        tau = _tau_recovery(rec_pts, nadir_v)
        if tau is not None:
            taus.append(tau)

    n_epi = len(slopes) + n_unrec
    if n_epi == 0:
        return None
    feats = {
        "rv_n_episodes": n_epi,
        "rv_frac_unrecovered": round(n_unrec / n_epi, 4),
        "rv_total_unrecovered_min": round(total_unrec_min, 4),
        "rv_worst_depth": round(worst_depth, 3),
    }
    if slopes:
        ss = sorted(slopes)
        feats["rv_median_slope"] = round(ss[len(ss) // 2], 4)
        feats["rv_min_slope"] = round(min(slopes), 4)
        feats["rv_mean_slope"] = round(sum(slopes) / len(slopes), 4)
        feats["rv_depthwt_slope"] = round(sum(depths) / sum(t_recs), 4)
        feats["rv_max_time_to_recover"] = round(max(t_recs), 4)
    if taus:
        ts = sorted(taus)
        feats["rv_median_tau"] = round(ts[len(ts) // 2], 4)
    return feats


COLS = ["caseid", "rv_n_episodes", "rv_frac_unrecovered", "rv_total_unrecovered_min",
        "rv_worst_depth", "rv_median_slope", "rv_min_slope", "rv_mean_slope",
        "rv_depthwt_slope", "rv_max_time_to_recover", "rv_median_tau"]


def _hypotensive_cohort(cdir):
    """Caseids with any MAP<65 episode (auc_below_65 > 0), from map_thresholds.csv."""
    path = os.path.join(cdir, "map_thresholds.csv")
    ids = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                if float(r.get("auc_below_65") or 0) > 0:
                    ids.append(r["caseid"])
            except (TypeError, ValueError):
                continue
    return ids


def main():
    from common.config import load_yaml
    from vitaldb_aki.data.tracks import first_available, tid_for
    from vitaldb_aki.features.pfds import _intraop_window, _clip_to_window, _filter_physiologic
    from vitaldb_aki.data.client import fetch_cases

    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cdir = cfg["data"]["cache_dir"]
    out = os.path.join(cdir, "recovery_velocity.csv")
    tdir = os.path.join(cdir, "tracks")

    caseids = _hypotensive_cohort(cdir)
    cases = {str(c["caseid"]): c for c in fetch_cases(cfg)}

    done = set()
    if os.path.exists(out):
        with open(out, newline="") as fh:
            done = {r["caseid"] for r in csv.DictReader(fh)}
    print(f"[recovery_velocity] {len(caseids)} hypotensive cases; "
          f"{len(done)} already extracted; {len(caseids) - len(done)} to go", flush=True)

    new = not os.path.exists(out)
    fh = open(out, "a", newline="")
    w = csv.DictWriter(fh, fieldnames=COLS)
    if new:
        w.writeheader()
    n = 0
    for cid in caseids:
        if cid in done:
            continue
        case = cases.get(str(cid))
        row = {c: "" for c in COLS}
        row["caseid"] = cid
        if case is not None:
            t0, t1 = _intraop_window(case)
            tname, raw = first_available(cfg, str(cid), MAP_CANDIDATES)
            if raw:
                s = _filter_physiologic(_clip_to_window(raw, t0, t1), MAP_MIN, MAP_MAX)
                if len(s) >= 2:
                    feats = _recovery_features(s)
                    if feats:
                        for k, v in feats.items():
                            row[k] = v
                tid = tid_for(cfg, str(cid), tname) if tname else None
                if tid:
                    try:
                        os.remove(os.path.join(tdir, f"{tid}.csv"))
                    except OSError:
                        pass
        w.writerow(row)
        n += 1
        if n % 25 == 0:
            fh.flush()
            print(f"[recovery_velocity] {n} new ({len(done)+n}/{len(caseids)})", flush=True)
    fh.close()
    open(os.path.join(cdir, "_recovery_velocity_done.json"), "w").write("{}")
    print(f"[recovery_velocity] EXTRACT DONE: {len(done)+n}/{len(caseids)} -> {out}",
          flush=True)


if __name__ == "__main__":
    main()
