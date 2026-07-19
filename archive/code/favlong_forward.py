#!/usr/bin/env python3
"""favlong_forward.py -- FORWARD-VALIDATION HARNESS for the FAVLONG edge (node FAVLONG).

WHAT: judges the near-expiry contrarian-taker edge PROSPECTIVELY, on tick-archive days that
arrive AFTER 2026-07-14 (data the strategy's design never saw). Tracks BOTH the raw model
(control) and the calibrated model (primary). The calibrated model applies an empirical
isotonic map fit on archive data (days <= 2026-07-14) to correct the Gaussian fair-value model.
The isotonic map is fit ONCE and FROZEN; forward days apply it unchanged (no refit to prevent
forward-data leakage).

DUAL MODELS:
  - raw: the validated tuned config from favlongshot_edge (decision_t=720, edge=0.05, +fees)
  - calibrated: same config, but fair values corrected via isotonic map (archive-fit only)

GATE (from FORWARD_LEDGER.md / charter, do not relax): pooled per-(asset,day) day-clustered
t >= 2 over >= 10 FORWARD days (days strictly AFTER 2026-07-14), across btc/eth/sol.
  - PASSED  : >= 10 forward days AND pooled t >= 2
  - FAILED  : >= 10 forward days AND pooled t < 0   (=> kill per charter)
  - not-yet : otherwise (clock not started, too few days, or 0 <= t < 2)

IDEMPOTENT: keyed on (model, asset, day); days already in the log are skipped. Only COMPLETE
forward days (strictly before today UTC) are scored, so logged data never changes.

ISOTONIC MAP SAFETY: The map is fit ONLY on archive rows (days <= 2026-07-14) pooled across
all assets. It is persisted as JSON (bucket bounds + means) for reproducibility. Forward runs
load and apply the frozen map unchanged — no refit, no forward-data contamination.

Usage:
  python favlong_forward.py             # fetch gha-data, score new complete forward days, print gates
  python favlong_forward.py --report    # just print the gate status from the existing log (no fetch)
  python favlong_forward.py --acceptance # reproduce model_v2 calibrated OOS on archive (self-check)
"""
import subprocess, json, os, sys, math, time, statistics
from datetime import datetime, timezone
from collections import defaultdict

import favlongshot_edge as fav
import favlong_model_v2 as v2

ASSETS = ["btc", "eth", "sol"]
FORWARD_START = "2026-07-14"     # forward clock = tick-archive days STRICTLY AFTER this
ARCHIVE_CUTOFF = "2026-07-14"    # isotonic map fit on archive days <= this (pre-forward TRAIN set)
GATE_MIN_DAYS = 10
GATE_T = 2.0
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "favlong_forward_log.jsonl")
ISOTONIC_MAP_FILE = os.path.join(HERE, "favlong_isotonic_map.json")

# ---- RAW model (control): the tuned baseline validated in favlongshot_edge ----
# keys match favlongshot_edge.score(...) kwargs (arith moneyness, edge=0.05, +fees, no lag)
CONFIG = dict(decision_t=fav.DECISION_T, edge=fav.EDGE, fee=True, lag=0)

# ---- CALIBRATED model (primary): the EXACT model_v2 selected variant ----
# baseline vol + logndrift moneyness + edge=0.03 + decision_t=720 + archive-fit isotonic bucket map.
# This is the recipe that ~doubles the OOS edge (pooled OOS t 3.97 -> ~5.7 with the stdlib bucket
# map). Applying the isotonic map on top of the RAW arith/edge0.05 config does NOT reproduce it and
# in fact degrades the edge -- the full recipe (vol/money/edge) is required together with the map.
CAL_VOL = "baseline"             # sigma estimator (favlong_model_v2.sigma_est vol=)
CAL_MONEY = "logndrift"          # moneyness/drift (favlong_model_v2.model_fair money=)
CAL_EDGE = 0.03                  # matches model_v2 EDGE (NOT the raw 0.05)
CAL_DECISION_T = v2.DECISION_T   # 720
CAL_CONFIG = dict(decision_t=CAL_DECISION_T, edge=CAL_EDGE, vol=CAL_VOL, money=CAL_MONEY,
                  fee=True, calibration="isotonic-bucket")

NORM = fav.NORM
KFEE = fav.KFEE


# ---- Isotonic calibration (stdlib-only, no sklearn) ----------------------------------------------
# The calibrated fair-value is computed by REUSING favlong_model_v2.window_rows / model_fair (the
# validated baseline/logndrift recipe). The isotonic map itself is a stdlib bucket-mean fit --
# byte-for-byte the same algorithm as favlong_model_v2.fit_isotonic's sklearn-free fallback -- but
# stored as (bounds, means) so it can be persisted to JSON and applied deterministically. We force
# the stdlib path (never sklearn) so the GHA runner and this fit agree exactly.
v2.HAVE_ISO = False              # GHA runner has no sklearn; force the bucket-mean path everywhere


def _fit_bucket_map(xs, ys, nb=12):
    """Stdlib bucket-mean isotonic fit -> (bounds, means). Identical algorithm to
    favlong_model_v2.fit_isotonic's no-sklearn fallback, but returns serializable params."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    edges = [order[int(k * len(order) / nb)] for k in range(nb)] + [order[-1]]
    bnds = [xs[e] for e in edges]
    means = []
    for k in range(nb):
        lo, hi = bnds[k], bnds[k + 1]
        sel = [ys[i] for i in range(len(xs)) if lo <= xs[i] <= hi]
        means.append(statistics.mean(sel) if sel else 0.5)
    return bnds, means


def fit_isotonic_map_archive(datasets, archive_cutoff=ARCHIVE_CUTOFF, nb=12):
    """Fit the isotonic map on ALL archive data (days <= archive_cutoff), pooled across assets,
    from the CALIBRATED model's fair-values (baseline vol / logndrift moneyness). Returns
    (bounds, means). Stdlib-only (no sklearn).

    CRITICAL: fit ONLY on archive data (days <= archive_cutoff) and frozen; applied unchanged to
    forward days -> no forward-data leakage. Reuses favlong_model_v2.window_rows for fair-values."""
    rows = []
    for asset in ASSETS:
        if asset not in datasets:
            continue
        data = datasets[asset]
        archive_days = [d for d in sorted(data) if d <= archive_cutoff]
        # window_rows yields (day, fair, outcome, bid, ask) using the baseline/logndrift model
        rows.extend(v2.window_rows(data, archive_days, CAL_VOL, CAL_MONEY,
                                   decision_t=CAL_DECISION_T))

    if not rows:
        sys.stderr.write(f"WARN: no archive rows for isotonic fit (archive_cutoff={archive_cutoff})\n")
        return None, None

    xs = [r[1] for r in rows]  # model fair probabilities (baseline/logndrift)
    ys = [r[2] for r in rows]  # outcomes (0 or 1)
    bnds, means = _fit_bucket_map(xs, ys, nb=nb)
    sys.stderr.write(f"Isotonic map fit on {len(rows)} archive rows (<= {archive_cutoff}), "
                     f"{len(means)} buckets, model={CAL_VOL}/{CAL_MONEY}\n")
    return bnds, means


def save_isotonic_map(bnds, means, path=ISOTONIC_MAP_FILE):
    """Persist the frozen isotonic map as JSON for reproducibility."""
    data = {"bounds": bnds, "means": means}
    with open(path, "w") as f:
        json.dump(data, f)
    sys.stderr.write(f"Isotonic map saved to {path}\n")


def load_isotonic_map(path=ISOTONIC_MAP_FILE):
    """Load the frozen isotonic map from JSON. Returns (bounds, means) or (None, None)."""
    if not os.path.exists(path):
        return None, None
    try:
        with open(path) as f:
            data = json.load(f)
        return data["bounds"], data["means"]
    except Exception as e:
        sys.stderr.write(f"WARN: failed to load isotonic map from {path}: {e}\n")
        return None, None


def apply_isotonic_map(fair_raw, bnds, means):
    """Apply the frozen isotonic map to a raw fair probability.
    Returns the calibrated fair probability (bucket mean lookup)."""
    if bnds is None or means is None:
        return fair_raw
    for k in range(len(means)):
        if fair_raw <= bnds[k + 1]:
            return means[k]
    return means[-1]


def _git_fetch_gha_data(retries=5):
    """git fetch origin gha-data with retry/backoff; returns True on success."""
    for i in range(retries):
        r = subprocess.run(["git", "fetch", "--depth=1", "origin", "gha-data"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return True
        sys.stderr.write(f"git fetch gha-data failed (attempt {i+1}/{retries}): "
                         f"{r.stderr.strip()[:200]}\n")
        time.sleep(min(2 ** i, 30))
    return False


def load_log():
    recs = []
    if os.path.exists(LOG):
        with open(LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except Exception:
                    continue
    return recs


def append_records(new_recs):
    with open(LOG, "a") as f:
        for r in new_recs:
            f.write(json.dumps(r) + "\n")


def score_day_raw(data, asset, day):
    """Score one (asset, day) with the validated config (raw model, no calibration).
    Always returns a record; n_trades=0 marks a complete forward day with no qualifying trades."""
    r = fav.score(data, [day], **CONFIG)
    if not r:
        return dict(model="raw", asset=asset, day=day, n_trades=0, mean_ct=None, day_pnl=0.0,
                    winrate=None, config=CONFIG)
    return dict(model="raw", asset=asset, day=day, n_trades=r["n"], mean_ct=r["mean"],
                day_pnl=r["total"], winrate=r["winrate"], config=CONFIG)


def _score_rows_calibrated(rows, bnds, means, edge=CAL_EDGE, fee=True):
    """Apply taker mechanics to CALIBRATED rows (from v2.window_rows). Returns list of per-contract
    P&L. IDENTICAL mechanics to favlong_model_v2.score_rows: calibrate the model fair with the
    isotonic map, take the side underpriced by > edge, fill at recorded bid/ask (no lag), +Kalshi
    fee. This reproduces the validated model_v2 numbers exactly."""
    pls = []
    for (day, fair, outcome, bid, ask) in rows:
        p = apply_isotonic_map(fair, bnds, means)
        ev_buy, ev_sell = p - ask, bid - p
        if ev_buy >= ev_sell and ev_buy > edge:
            pl = outcome - ask - (KFEE(ask) if fee else 0)
        elif ev_sell > edge:
            pl = bid - outcome - (KFEE(bid) if fee else 0)
        else:
            continue
        pls.append(pl)
    return pls


def score_day_calibrated(data, asset, day, bnds, means):
    """Score one (asset, day) with the CALIBRATED model = the EXACT model_v2 selected variant
    (baseline vol / logndrift moneyness / edge=0.03 / decision_t=720 + archive-fit isotonic map).
    Reuses favlong_model_v2.window_rows for the fair-values. Always returns a record; n_trades=0
    marks a complete forward day that produced no qualifying trades (or no frozen map)."""
    if bnds is None or means is None:
        return dict(model="calibrated", asset=asset, day=day, n_trades=0, mean_ct=None,
                    day_pnl=0.0, winrate=None, config=CAL_CONFIG)
    rows = v2.window_rows(data, [day], CAL_VOL, CAL_MONEY, decision_t=CAL_DECISION_T)
    pls = _score_rows_calibrated(rows, bnds, means, edge=CAL_EDGE, fee=CAL_CONFIG["fee"])
    if not pls:
        return dict(model="calibrated", asset=asset, day=day, n_trades=0, mean_ct=None,
                    day_pnl=0.0, winrate=None, config=CAL_CONFIG)
    return dict(model="calibrated", asset=asset, day=day, n_trades=len(pls),
                mean_ct=statistics.mean(pls), day_pnl=sum(pls),
                winrate=sum(1 for p in pls if p > 0) / len(pls),
                config=CAL_CONFIG)


def compute_gate(recs, model="raw"):
    """Pooled per-(asset,day) day-clustered t over traded forward records for a specific model."""
    traded = [r for r in recs if r.get("model") == model and r.get("n_trades", 0) > 0
              and r.get("mean_ct") is not None]
    means = [r["mean_ct"] for r in traded]
    days = sorted({r["day"] for r in traded})
    ndays = len(days)
    n_points = len(means)
    total_pnl = sum(r.get("day_pnl", 0.0) or 0.0 for r in traded)
    t = float("nan")
    mean_ct = float("nan")
    if n_points >= 1:
        mean_ct = statistics.mean(means)
    if n_points > 1 and statistics.stdev(means) > 0:
        t = statistics.mean(means) / (statistics.stdev(means) / math.sqrt(n_points))

    if ndays == 0:
        status = "CLOCK-NOT-STARTED"
    elif ndays < GATE_MIN_DAYS:
        status = "not-yet"
    elif not math.isnan(t) and t >= GATE_T:
        status = "PASSED"
    elif not math.isnan(t) and t < 0:
        status = "FAILED"
    else:
        status = "not-yet"
    return dict(status=status, ndays=ndays, n_points=n_points, t=t, mean_ct=mean_ct,
                total_pnl=total_pnl, days=days, n_pos=sum(1 for m in means if m > 0))


def print_gates(recs):
    """Print gate status for both raw (control) and calibrated (primary) models."""
    cfg_line = {
        "raw": (f"config[raw/control]: decision_t={CONFIG['decision_t']}s edge={CONFIG['edge']} "
                f"money=arith fees={CONFIG['fee']} lag={CONFIG['lag']}  (POOLED btc+eth+sol)"),
        "calibrated": (f"config[calibrated/primary]: decision_t={CAL_CONFIG['decision_t']}s "
                       f"edge={CAL_CONFIG['edge']} vol={CAL_CONFIG['vol']} money={CAL_CONFIG['money']} "
                       f"cal={CAL_CONFIG['calibration']} fees={CAL_CONFIG['fee']}  "
                       f"(POOLED btc+eth+sol)"),
    }
    for model in ["raw", "calibrated"]:
        g = compute_gate(recs, model=model)
        print(f"\n=== FAVLONG forward gate [{model}] ===")
        print(cfg_line[model])
        if g["ndays"] == 0:
            print("forward clock has NOT started: no COMPLETE forward day (> "
                  f"{FORWARD_START}) with trades is logged yet.")
            print(f"status: {g['status']}  (gate opens after >= {GATE_MIN_DAYS} forward days, "
                  f"pooled t >= {GATE_T})")
            continue
        tstr = "nan" if math.isnan(g["t"]) else f"{g['t']:+.2f}"
        print(f"forward days: {g['ndays']} (gate needs >= {GATE_MIN_DAYS})   "
              f"per-(asset,day) points: {g['n_points']} ({g['n_pos']} positive)")
        print(f"pooled mean: ${g['mean_ct']:+.4f}/ct   pooled day-clustered t: {tstr}   "
              f"forward total P&L: ${g['total_pnl']:+.2f}")
        print(f"days: {', '.join(g['days'])}")
        verdict = {
            "PASSED": f"PASSED -- >= {GATE_MIN_DAYS} forward days and pooled t >= {GATE_T}.",
            "FAILED": f"FAILED -- >= {GATE_MIN_DAYS} forward days and pooled t < 0 => KILL per charter.",
            "not-yet": (f"not-yet -- "
                        + ("need more forward days." if g["ndays"] < GATE_MIN_DAYS
                           else f"have >= {GATE_MIN_DAYS} days but pooled t < {GATE_T} (not < 0).")),
        }[g["status"]]
        print(f"status: {verdict}")


def run(fetch=True, datasets=None):
    if fetch:
        if not _git_fetch_gha_data():
            sys.stderr.write("WARN: could not fetch origin gha-data; scoring against local refs.\n")

    # Load or build datasets
    if datasets is None:
        datasets = {}
        for asset in ASSETS:
            try:
                datasets[asset] = fav.build_asset(asset)
            except Exception as e:
                sys.stderr.write(f"build_asset({asset}) failed: {e}\n")

    # Fit or load isotonic map (archive-only, fit once and freeze)
    bnds, means = load_isotonic_map()
    if bnds is None:
        sys.stderr.write(f"Fitting isotonic map on archive data (days <= {ARCHIVE_CUTOFF})...\n")
        bnds, means = fit_isotonic_map_archive(datasets, archive_cutoff=ARCHIVE_CUTOFF)
        if bnds is not None:
            save_isotonic_map(bnds, means)
        else:
            sys.stderr.write("WARN: could not fit isotonic map\n")

    recs = load_log()
    keys = {(r["model"], r["asset"], r["day"]) for r in recs}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new = []
    for asset in ASSETS:
        if asset not in datasets:
            continue
        data = datasets[asset]
        # COMPLETE forward days only: strictly after the forward start AND strictly before today UTC
        days = [d for d in sorted(data) if FORWARD_START < d < today]
        for day in days:
            # Score both raw and calibrated models
            for model in ["raw", "calibrated"]:
                if (model, asset, day) in keys:
                    continue
                if model == "raw":
                    rec = score_day_raw(data, asset, day)
                else:
                    rec = score_day_calibrated(data, asset, day, bnds, means)
                new.append(rec)
                keys.add((model, asset, day))
                nt = rec["n_trades"]
                mc = rec["mean_ct"]
                mcs = "n/a" if mc is None else f"${mc:+.4f}/ct"
                print(f"scored {model:12s} {asset} {day}: n_trades={nt} mean={mcs} day_pnl=${rec['day_pnl']:+.2f}")
    if new:
        append_records(new)
        recs += new
        print(f"appended {len(new)} new record(s) to {LOG}")
    else:
        print("no new complete forward days to score (clock may not have started, or all logged).")
    print_gates(recs)


def acceptance_test(train_cutoff="2026-06-30"):
    """HARD ACCEPTANCE TEST: prove the calibrated wiring reproduces favlong_model_v2's
    STDLIB-bucket OOS numbers on the ARCHIVE test set (days > train_cutoff), using the SAME
    fit/score path the forward harness uses (fit_isotonic_map_archive + _score_rows_calibrated).

    Target (from favlong_model_v2, stdlib bucket path):
      calibrated OOS pooled t ~= 5.7 (btc ~4.2, eth ~2.9, sol ~2.9), mean ~= $0.051/ct
      raw tuned baseline OOS ~= t 3.97  ==>  calibrated MUST beat raw.

    Fit is TRAIN-only (days <= train_cutoff); scored on TEST (days > train_cutoff). No leak.
    Uses fav.load_asset (cached windows). Returns True iff the acceptance criteria pass."""
    try:
        datasets = {a: fav.load_asset(a) for a in ASSETS}
    except SystemExit as e:
        print(f"acceptance-test SKIPPED: {e}")
        return False

    # ---- fit the isotonic map on TRAIN only (days <= train_cutoff), pooled across assets ----
    train_rows = []
    for a in ASSETS:
        tr_days = [d for d in sorted(datasets[a]) if d <= train_cutoff]
        train_rows.extend(v2.window_rows(datasets[a], tr_days, CAL_VOL, CAL_MONEY,
                                         decision_t=CAL_DECISION_T))
    xs = [r[1] for r in train_rows]
    ys = [r[2] for r in train_rows]
    bnds, means = _fit_bucket_map(xs, ys)

    # ---- score CALIBRATED on the OOS test set (days > train_cutoff), per-(asset,day) ----
    def _pooled(day_means):
        dm = [m for m in day_means if m is not None]
        if len(dm) < 2 or statistics.stdev(dm) == 0:
            return float("nan"), (statistics.mean(dm) if dm else float("nan")), len(dm)
        return (statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm))),
                statistics.mean(dm), len(dm))

    cal_all_daymeans, raw_all_daymeans = [], []
    cal_per_asset, raw_per_asset = {}, {}
    for a in ASSETS:
        te_days = [d for d in sorted(datasets[a]) if d > train_cutoff]
        cal_dm, raw_dm = [], []
        for d in te_days:
            # calibrated: same path as the forward harness (baseline/logndrift + map + edge0.03)
            crows = v2.window_rows(datasets[a], [d], CAL_VOL, CAL_MONEY, decision_t=CAL_DECISION_T)
            cpls = _score_rows_calibrated(crows, bnds, means, edge=CAL_EDGE, fee=True)
            if cpls:
                cal_dm.append(statistics.mean(cpls))
            # raw tuned baseline reference: baseline/arith/sigma_mult=0.8 + edge0.03 (no calibration)
            rrows = v2.window_rows(datasets[a], [d], "baseline", "arith", sigma_mult=0.8,
                                   decision_t=CAL_DECISION_T)
            rpls = _score_rows_calibrated(rrows, None, None, edge=CAL_EDGE, fee=True)
            if rpls:
                raw_dm.append(statistics.mean(rpls))
        cal_all_daymeans += cal_dm
        raw_all_daymeans += raw_dm
        cal_per_asset[a] = _pooled(cal_dm)
        raw_per_asset[a] = _pooled(raw_dm)

    cal_t, cal_mean, cal_n = _pooled(cal_all_daymeans)
    raw_t, raw_mean, raw_n = _pooled(raw_all_daymeans)

    print("\n=== FAVLONG calibrated-wiring ACCEPTANCE TEST (archive OOS, days > "
          f"{train_cutoff}) ===")
    print("reproduces favlong_model_v2 STDLIB-bucket OOS; map fit TRAIN-only (no leak), stdlib-only.")
    print(f"  CALIBRATED (baseline/logndrift/iso-bucket/edge={CAL_EDGE}) OOS: "
          f"pooled t={cal_t:+.2f}  mean=${cal_mean:+.4f}/ct  asset-days={cal_n}")
    for a in ASSETS:
        t, m, n = cal_per_asset[a]
        print(f"     {a}: t={t:+.2f} mean=${m:+.4f}/ct days={n}")
    print(f"  RAW tuned (baseline/arith/sigma0.8/edge={CAL_EDGE}) OOS: "
          f"pooled t={raw_t:+.2f}  mean=${raw_mean:+.4f}/ct  asset-days={raw_n}")

    # ---- acceptance criteria ----
    beats_raw = (not math.isnan(cal_t)) and (not math.isnan(raw_t)) and cal_t > raw_t
    near_target = (not math.isnan(cal_t)) and abs(cal_t - 5.7) <= 1.0 and abs(cal_mean - 0.051) <= 0.015
    per_asset_ok = all((not math.isnan(cal_per_asset[a][0])) and cal_per_asset[a][0] >= 2.0
                       for a in ASSETS)
    ok = beats_raw and near_target and per_asset_ok
    print(f"  check: calibrated t~=5.7? {'YES' if near_target else 'NO'} "
          f"(got {cal_t:+.2f}, mean ${cal_mean:+.4f})   "
          f"beats raw? {'YES' if beats_raw else 'NO'} ({cal_t:+.2f} vs {raw_t:+.2f})   "
          f"all 3 assets t>=2? {'YES' if per_asset_ok else 'NO'}")
    print(f"  ACCEPTANCE: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    if "--acceptance" in sys.argv[1:]:
        ok = acceptance_test()
        sys.exit(0 if ok else 1)
    if "--report" in sys.argv[1:]:
        recs = load_log()
        if not recs:
            print(f"no log yet at {LOG} -- forward clock has not started.")
        print_gates(recs)
        return
    run(fetch=True)


if __name__ == "__main__":
    main()
