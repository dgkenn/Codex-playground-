#!/usr/bin/env python3
"""spec_M1.py -- FROZEN pre-registered spec M1 (macro-surprise pass-through drift into the
next-meeting Fed-decision market). See venue_expansion/GROUNDING.md, PAPER_TRADER_AUDIT.md,
REOPENABLE.md for context, and the spec text embedded in the task for the frozen rules.

Read-only. Reads local cached tape (venue_expansion/cache/prereg/tape/shard-*.parquet, produced
by cache/prereg/m1_tape_pull.py from the HF TrevorJS/kalshi-trades archive, ALL 16 trade shards,
predicate-filtered server-side to the union ticker universe: KXFEDDECISION/FEDDECISION +
the six macro-surprise families, exact series-key match) and the local markets snapshot
(cache/M1/markets_universe.json, pulled from all 4 HF markets shards).

Writes:
  venue_expansion/out/spec_M1.json  -- full records + summary
  venue_expansion/out/spec_M1.md    -- method + results + skip ledger
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics as st
import sys
import time
from datetime import datetime, timedelta, timezone

import duckdb
from scipy import stats as sstats

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "M1")
TAPE_DIR = os.path.join(HERE, "cache", "prereg", "tape")
OUT_JSON = os.path.join(HERE, "out", "spec_M1.json")
OUT_MD = os.path.join(HERE, "out", "spec_M1.md")

WINDOW_START = "2023-04-07"
WINDOW_END = "2026-01-28"
FIT_END = "2025-01-01"  # FIT = release_date < FIT_END; VALIDATION = release_date >= FIT_END

THETA_GRID = [0.5, 1.0, 1.5, 2.0]

FAMILIES = {
    "CPI": {"CPI": 1, "CPICORE": 1, "CPIYOY": 1, "CPICOREYOY": 1,
             "KXCPI": 1, "KXCPICORE": 1, "KXCPIYOY": 1, "KXCPICOREYOY": 1},
    "EMPLOYMENT": {"PAYROLLS": 1, "KXPAYROLLS": 1, "KXU3": -1},
    "JOBLESS": {"JOBLESS": -1, "KXJOBLESSCLAIMS": -1},
    "PCE": {"PCECORE": 1, "KXPCECORE": 1},
    "GDP": {"GDP": 1, "KXGDP": 1},
    "ISM": {"KXISMPMI": 1},
}
SERIES_TO_FAMILY = {}
SERIES_HAWK = {}
for fam, dd in FAMILIES.items():
    for s, sign in dd.items():
        SERIES_TO_FAMILY[s] = fam
        SERIES_HAWK[s] = sign

STRIKE_RE = re.compile(r'^[A-Za-z]*(-?\d+\.?\d*)$')

HOLD_RE = re.compile(r'maintain|no change|no cut|no hike|\b0\s*bps\b', re.I)
CUT_RE = re.compile(r'\bcut\b', re.I)
HIKE_RE = re.compile(r'\bhike\b|\braise\b', re.I)

FIVE_MIN = timedelta(minutes=5)
TWENTY_MIN = timedelta(minutes=20)
SIXTY_MIN = timedelta(minutes=60)
ONE_TWENTY_MIN = timedelta(minutes=120)
TWENTYFOUR_H = timedelta(hours=24)

SKIP_LOG = []  # every dropped release event, mandatory ledger

def skip(event_key, reason, extra=None):
    rec = {"event": event_key, "reason": reason}
    if extra:
        rec["extra"] = extra
    SKIP_LOG.append(rec)


def parse_dt(s):
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(s)


def parse_strike(ticker, event_ticker):
    assert ticker.startswith(event_ticker + "-"), (ticker, event_ticker)
    suffix = ticker[len(event_ticker) + 1:]
    m = STRIKE_RE.match(suffix)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def fee_cents(p):
    """Kalshi taker fee, ceil(7*p*(1-p)) CENTS, p = leg's own transacted price in [0,1]."""
    p = max(0.0, min(1.0, p))
    return math.ceil(7 * p * (1 - p))


def classify_fed_rung(title, sub_title):
    text = f"{sub_title or ''} {title or ''}"
    if HOLD_RE.search(text):
        return None
    if CUT_RE.search(text):
        return -1
    if HIKE_RE.search(text):
        return 1
    return None


def day_clustered_t(cluster_means):
    """cluster_means: list of per-cluster mean net (cents). Returns (mean, t, n_clusters)."""
    n = len(cluster_means)
    if n < 2:
        return (cluster_means[0] if n == 1 else None), None, n
    m = st.mean(cluster_means)
    sd = st.stdev(cluster_means)
    se = sd / math.sqrt(n)
    t = (m / se) if se > 0 else float("inf") if m > 0 else (float("-inf") if m < 0 else 0.0)
    return m, t, n


def wilson_lb(k, n, z=1.959963984540054):
    if n == 0:
        return None
    phat = k / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    adj = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return (center - adj) / denom


def t_crit(alpha_two_sided, df):
    return sstats.t.ppf(1 - alpha_two_sided / 2, df)


def main():
    t_start = time.time()
    log_lines = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    # ---------- load local caches (no network past this point except a bounded live-recon probe) ----------
    universe = json.load(open(os.path.join(CACHE, "markets_universe.json")))
    ucols = universe["cols"]; uidx = {c: i for i, c in enumerate(ucols)}
    urows = universe["rows"]

    events_blob = json.load(open(os.path.join(CACHE, "events.json")))
    all_events = events_blob["events"]
    unparseable_log = events_blob["unparseable_log"]
    for u in unparseable_log:
        skip(f"ladder:{u['event_ticker']}", "ladder strikes unparseable", u)

    # DuckDB over the local cached tape (16 shards already pulled, union ticker universe)
    con = duckdb.connect()
    shard_re = re.compile(r'^shard-\d{4}\.parquet$')
    shard_files = sorted(os.path.join(TAPE_DIR, f) for f in os.listdir(TAPE_DIR) if shard_re.match(f))
    assert len(shard_files) == 16, f"expected 16 cached shards, found {len(shard_files)}: {shard_files}"
    tape_src = "read_parquet([" + ",".join(f"'{p}'" for p in shard_files) + "])"
    n_trades, n_tickers, tmin, tmax = con.execute(
        f"SELECT count(*), count(DISTINCT ticker), min(created_time), max(created_time) FROM {tape_src}"
    ).fetchone()
    log(f"local tape: {n_trades} trades, {n_tickers} distinct tickers, {tmin} .. {tmax}")

    # Build an in-memory table for fast per-ticker last-trade / first-trade / volume queries.
    con.execute(f"CREATE TEMP TABLE tape AS SELECT ticker, count, yes_price, no_price, taker_side, created_time FROM {tape_src}")
    con.execute("CREATE INDEX idx_tape_ticker ON tape(ticker)")

    def last_trade_before(ticker, t0):
        r = con.execute(
            "SELECT yes_price, no_price, taker_side, created_time FROM tape "
            "WHERE ticker=? AND created_time < ? ORDER BY created_time DESC LIMIT 1",
            [ticker, t0]).fetchone()
        return r

    def first_trade_side(ticker, t_lo, t_hi, side):
        r = con.execute(
            "SELECT yes_price, no_price, taker_side, created_time, count FROM tape "
            "WHERE ticker=? AND created_time>=? AND created_time<? AND taker_side=? "
            "ORDER BY created_time ASC LIMIT 1",
            [ticker, t_lo, t_hi, side]).fetchone()
        return r

    def volume_window(ticker, t_lo, t_hi):
        r = con.execute(
            "SELECT coalesce(sum(count),0) FROM tape WHERE ticker=? AND created_time>=? AND created_time<?",
            [ticker, t_lo, t_hi]).fetchone()
        return r[0]

    # ---------- Fed-decision event/rung universe ----------
    fed_events = {}  # event_ticker -> {close_time, rungs: [{ticker, rung_sign(None=HOLD)}]}
    for r in urows:
        sk = r[uidx["series_key"]]
        if sk not in ("KXFEDDECISION", "FEDDECISION"):
            continue
        evt = r[uidx["event_ticker"]]
        fed_events.setdefault(evt, {"close_time": r[uidx["close_time"]], "rungs": []})
        sign = classify_fed_rung(r[uidx["title"]], r[uidx["yes_sub_title"]])
        fed_events[evt]["rungs"].append({
            "ticker": r[uidx["ticker"]], "sign": sign,
            "yes_sub_title": r[uidx["yes_sub_title"]],
        })
    fed_list = sorted(fed_events.items(), key=lambda kv: kv[1]["close_time"])
    log(f"Fed-decision events (KXFEDDECISION+FEDDECISION): {len(fed_list)}")

    def select_target(t0_dt, event_key):
        cutoff = t0_dt + TWENTYFOUR_H
        cands = [(evt, info) for evt, info in fed_list if parse_dt(info["close_time"]) > cutoff]
        if not cands:
            skip(event_key, "no still-open Fed event > t0+24h")
            return None
        evt, info = min(cands, key=lambda kv: parse_dt(kv[1]["close_time"]))
        non_hold = [rr for rr in info["rungs"] if rr["sign"] is not None]
        if not non_hold:
            skip(event_key, "all rungs classified HOLD", {"fed_event": evt})
            return None
        vols = []
        for rr in non_hold:
            v = volume_window(rr["ticker"], (t0_dt - TWENTYFOUR_H).isoformat(), t0_dt.isoformat())
            vols.append((v, rr["ticker"], rr))
        vols.sort(key=lambda x: (-x[0], x[1]))
        best = vols[0][2]
        return {"fed_event": evt, "target_ticker": best["ticker"], "rung_sign": best["sign"],
                "target_close_time": info["close_time"], "pre_vol": vols[0][0]}

    # ---------- per-ladder u(e) computation (needs pre-t0 ladder AND settlement result) ----------
    def ladder_u(lad):
        """Returns (u, n_rungs_used, reason_if_none)."""
        t0 = parse_dt(lad["t0"])
        rungs = lad["rungs"]
        if len(rungs) < 1:
            return None, 0, "empty ladder"
        p_pre = []
        r_val = []
        for rr in rungs:
            tr = last_trade_before(rr["ticker"], t0.isoformat())
            if tr is None:
                return None, 0, "no pre-t0 ladder print"
            yes_price, no_price, taker_side, ctime = tr
            p = (yes_price / 100.0) if taker_side == "yes" else ((100 - no_price) / 100.0)
            p_pre.append(p)
            if rr["result"] not in ("yes", "no"):
                return None, 0, "settlement result unavailable (archive blank, live API 404s -- retention wall)"
            r_val.append(1.0 if rr["result"] == "yes" else 0.0)
        strikes = [rr["strike"] for rr in rungs]
        strike_min = strikes[0]
        e_pre = strike_min + sum(p_pre[i] * (strikes[i + 1] - strikes[i]) for i in range(len(strikes) - 1))
        r = strike_min + sum(r_val[i] * (strikes[i + 1] - strikes[i]) for i in range(len(strikes) - 1))
        u = r - e_pre
        return u, len(rungs), None

    # attach u to every ladder in-window; collect FIT u's per family for sigma
    in_window = [e for e in all_events if WINDOW_START <= e["release_date"] <= WINDOW_END]
    fit_events = [e for e in in_window if e["release_date"] < FIT_END]
    val_events = [e for e in in_window if e["release_date"] >= FIT_END]
    log(f"release events in window [{WINDOW_START},{WINDOW_END}]: {len(in_window)}  FIT={len(fit_events)}  VALIDATION={len(val_events)}")

    fit_u_by_family = {fam: [] for fam in FAMILIES}
    ladder_u_cache = {}  # (event_ticker) -> (u, reason)
    for e in in_window:
        for lad in e["ladders"]:
            u, nr, reason = ladder_u(lad)
            ladder_u_cache[lad["event_ticker"]] = (u, reason)
            if u is not None and e["release_date"] < FIT_END:
                fit_u_by_family[lad["family"]].append(u)

    sigma_family = {}
    sigma_undefined = []
    for fam, us in fit_u_by_family.items():
        if len(us) >= 2:
            med = st.median(us)
            mad = st.median([abs(x - med) for x in us])
            sigma_family[fam] = 1.4826 * mad if mad > 0 else None
            if sigma_family[fam] is None or sigma_family[fam] == 0:
                sigma_undefined.append((fam, "MAD=0 (degenerate)", len(us)))
                sigma_family[fam] = None
        else:
            sigma_family[fam] = None
            sigma_undefined.append((fam, "zero or one FIT observation", len(us)))
    log(f"FIT u-sample sizes per family: { {k: len(v) for k, v in fit_u_by_family.items()} }")
    log(f"sigma_family: {sigma_family}")
    log(f"sigma UNDEFINED (families with no usable FIT signal): {sigma_undefined}")

    def event_x(e):
        """Collapse this event's sub-ladders into one x(e) = mean over available ladder-level x_i."""
        xs = []
        used = []
        reasons = []
        for lad in e["ladders"]:
            u, reason = ladder_u_cache[lad["event_ticker"]]
            fam = lad["family"]
            if u is None:
                reasons.append((lad["event_ticker"], reason))
                continue
            sig = sigma_family.get(fam)
            if sig is None:
                reasons.append((lad["event_ticker"], f"sigma_family[{fam}] undefined"))
                continue
            z = u / sig
            x = lad["hawk_sign"] * z
            xs.append(x)
            used.append(lad["event_ticker"])
        if not xs:
            return None, used, reasons
        return st.mean(xs), used, reasons

    # ---------- trade construction for one event at a fixed theta ----------
    def build_trade(e, theta):
        key = f"{e['family']}:{e['release_date']}"
        x, used_ladders, reasons = event_x(e)
        if x is None:
            skip(key, "no usable ladder (" + "; ".join(f"{u}:{r}" for u, r in reasons) + ")")
            return None
        if abs(x) < theta:
            return None  # not a skip -- simply doesn't trigger; not logged as a "drop" reason
        t0 = parse_dt(e["t0"])
        tgt = select_target(t0, key)
        if tgt is None:
            return None  # select_target already logged the skip
        side_val = tgt["rung_sign"] * x
        if side_val == 0:
            skip(key, "expected move exactly zero (degenerate side)")
            return None
        side = "yes" if side_val > 0 else "no"
        entry_lo = (t0 + FIVE_MIN).isoformat()
        entry_hi = (t0 + TWENTY_MIN).isoformat()
        entry_side_taker = side  # buy YES needs a taker_side='yes' print (lifted ask); buy NO needs taker_side='no'
        etr = first_trade_side(tgt["target_ticker"], entry_lo, entry_hi, entry_side_taker)
        if etr is None:
            skip(key, "no executable entry print in [t0+5m,t0+20m]", {"target": tgt["target_ticker"], "side": side})
            return None
        eyes, eno, etaker, ectime, ecount = etr
        entry_price_c = eyes if side == "yes" else eno
        exit_lo = (t0 + SIXTY_MIN).isoformat()
        exit_hi = (t0 + ONE_TWENTY_MIN).isoformat()
        opp_taker = "no" if side == "yes" else "yes"
        xtr = first_trade_side(tgt["target_ticker"], exit_lo, exit_hi, opp_taker)
        no_exit = xtr is None
        if not no_exit:
            xyes, xno, xtaker, xctime, xcount = xtr
            exit_price_c = (100 - xno) if side == "yes" else (100 - xyes)
        else:
            skip(key, "no exit print in [t0+60m,t0+120m]", {"target": tgt["target_ticker"], "side": side})
            exit_price_c = entry_price_c  # marked out at entry cost, zero gross

        fee_entry_c = fee_cents(entry_price_c / 100.0)
        fee_exit_c = fee_cents(entry_price_c / 100.0) if no_exit else fee_cents(
            (xno if side == "yes" else xyes) / 100.0)
        net_c = (exit_price_c - entry_price_c) - fee_entry_c - fee_exit_c

        return {
            "family": e["family"], "release_date": e["release_date"], "t0": e["t0"],
            "x": x, "theta_used": theta, "used_ladders": used_ladders,
            "target_fed_event": tgt["fed_event"], "target_ticker": tgt["target_ticker"],
            "rung_sign": tgt["rung_sign"], "pre_vol": tgt["pre_vol"],
            "side": side, "entry_price_c": entry_price_c, "entry_count": ecount,
            "entry_time": ectime.isoformat() if hasattr(ectime, "isoformat") else str(ectime),
            "exit_price_c": exit_price_c, "no_exit": no_exit,
            "fee_entry_c": fee_entry_c, "fee_exit_c": fee_exit_c,
            "net_c": net_c,
        }

    # ---------- FIT: choose theta ----------
    log("\n=== FIT theta selection ===")
    fit_results_by_theta = {}
    for theta in THETA_GRID:
        trades = []
        for e in fit_events:
            tr = build_trade(e, theta)
            if tr is not None:
                trades.append(tr)
        byday = {}
        for tr in trades:
            byday.setdefault(tr["release_date"], []).append(tr["net_c"])
        cluster_means = [st.mean(v) for v in byday.values()]
        m, t, ncl = day_clustered_t(cluster_means)
        fit_results_by_theta[theta] = {"n_trades": len(trades), "n_clusters": ncl, "mean_net_c": m, "t": t,
                                        "trades": trades}
        log(f"theta={theta}: n_trades={len(trades)} n_clusters={ncl} mean_net_c={m} t={t}")

    # clear the skip log accumulated during FIT theta search -- those are exploratory, not the
    # final skip ledger (the mandated ledger is for the run's actual VALIDATION construction,
    # logged fresh below). We keep a copy for the record.
    fit_skip_log = list(SKIP_LOG)
    SKIP_LOG.clear()

    usable_thetas = {th: r for th, r in fit_results_by_theta.items() if r["t"] is not None}
    all_le_zero = all((r["t"] is not None and r["t"] <= 0) or r["t"] is None for r in fit_results_by_theta.values())
    # SELF-KILL: if all four FIT theta cells have FIT day-clustered t <= 0
    valid_t = [r["t"] for r in fit_results_by_theta.values() if r["t"] is not None]
    self_kill = (len(valid_t) > 0 and all(t <= 0 for t in valid_t))

    result = {
        "spec_id": "M1",
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "window": [WINDOW_START, WINDOW_END], "fit_end": FIT_END,
        "shards_read": "all 16 (tape cached locally after a single shared filtered pass over all 16 HF trade shards)",
        "n_trades_local_tape": n_trades, "n_tickers_local_tape": n_tickers,
        "tape_span": [str(tmin), str(tmax)],
        "fit_events_total": len(fit_events), "val_events_total": len(val_events),
        "fit_u_sample_sizes": {k: len(v) for k, v in fit_u_by_family.items()},
        "sigma_family": sigma_family, "sigma_undefined_families": sigma_undefined,
        "fit_theta_grid": fit_results_by_theta,
        "self_kill_no_signal": self_kill,
        "fit_skip_ledger_exploratory": fit_skip_log,
    }

    if self_kill:
        result["verdict"] = "NULL"
        result["verdict_reason"] = "all FIT theta cells have day-clustered t <= 0 (self-kill); validation not opened."
        log("\nSELF-KILL triggered: all FIT theta t <= 0. Validation window is NOT opened, per kill_conditions.")
        finalize(result, log_lines, chosen_theta=None)
        return

    chosen_theta = max(usable_thetas.items(), key=lambda kv: kv[1]["t"])[0]
    log(f"\nchosen theta (max FIT day-clustered t, frozen henceforth): {chosen_theta}")
    result["chosen_theta"] = chosen_theta

    # ---------- VALIDATION ----------
    log("\n=== VALIDATION (theta frozen) ===")
    val_trades = []
    for e in val_events:
        tr = build_trade(e, chosen_theta)
        if tr is not None:
            val_trades.append(tr)
    log(f"VALIDATION qualifying trades (triggered + entry executed): {len(val_trades)}")
    result["skip_ledger"] = list(SKIP_LOG)
    result["fit_skip_ledger_exploratory"] = fit_skip_log

    fams_present = sorted(set(tr["family"] for tr in val_trades))
    days_present = sorted(set(tr["release_date"] for tr in val_trades))
    n = len(val_trades)
    n_fams = len(fams_present)
    n_clusters = len(days_present)
    result["n_qualifying"] = n
    result["families_present"] = fams_present
    result["n_families"] = n_fams
    result["n_clusters"] = n_clusters

    MIN_N = 40
    if n < MIN_N or n_fams < 3 or n_clusters < MIN_N:
        result["verdict"] = "INSUFFICIENT"
        result["verdict_reason"] = (
            f"min_n gate failed: n_qualifying={n} (need >=40), n_families={n_fams} (need >=3), "
            f"n_clusters={n_clusters} (need >=40)."
        )
        log("\n" + result["verdict_reason"])
        finalize(result, log_lines, chosen_theta=chosen_theta, val_trades=val_trades)
        return

    # ---- pass-bar clauses ----
    byday = {}
    for tr in val_trades:
        byday.setdefault(tr["release_date"], []).append(tr)

    print_weighted_mean = st.mean(tr["net_c"] for tr in val_trades)
    total_contracts = sum(tr["entry_count"] for tr in val_trades)
    contract_weighted_mean = sum(tr["net_c"] * tr["entry_count"] for tr in val_trades) / total_contracts

    cluster_means = [st.mean(t["net_c"] for t in v) for v in byday.values()]
    mean_c, t_stat, ncl = day_clustered_t(cluster_means)
    df = ncl - 1
    bar = t_crit(0.0125, df)

    fam_counts = {}
    for tr in val_trades:
        fam_counts.setdefault(tr["family"], []).append(tr["net_c"])
    fam_order = sorted(fam_counts.items(), key=lambda kv: -len(kv[1]))[:3]
    fam_sign_ok = sum(1 for _, v in fam_order if st.mean(v) > 0)

    day_mean_pairs = sorted(byday.items(), key=lambda kv: -st.mean(t["net_c"] for t in kv[1]))
    dropped_days = set(k for k, _ in day_mean_pairs[:5])
    remaining_trades = [tr for tr in val_trades if tr["release_date"] not in dropped_days]
    robust_mean = st.mean(tr["net_c"] for tr in remaining_trades) if remaining_trades else None

    wins = sum(1 for tr in val_trades if tr["net_c"] > 0)
    wlb = wilson_lb(wins, n)
    mean_entry_price = st.mean(tr["entry_price_c"] for tr in val_trades) / 100.0
    mean_entry_fee = st.mean(tr["fee_entry_c"] for tr in val_trades) / 100.0
    breakeven_win_rate = mean_entry_price + mean_entry_fee

    clause1 = (contract_weighted_mean >= 0.50) and (print_weighted_mean >= 0.50)
    clause2 = (t_stat is not None) and (t_stat >= bar)
    clause3 = fam_sign_ok >= 2
    clause4 = (robust_mean is not None) and (robust_mean > 0)
    clause5 = (wlb is not None) and (wlb > breakeven_win_rate)

    all_pass = clause1 and clause2 and clause3 and clause4 and clause5

    result.update({
        "print_weighted_mean_c": print_weighted_mean,
        "contract_weighted_mean_c": contract_weighted_mean,
        "day_clustered_t": t_stat, "df": df, "t_bar_exact": bar,
        "n_clusters_used": ncl,
        "top3_families_by_n": [(k, len(v), st.mean(v)) for k, v in fam_order],
        "fam_sign_ok_count": fam_sign_ok,
        "dropped_5_best_days": sorted(dropped_days),
        "robustness_mean_after_drop5_c": robust_mean,
        "wins": wins, "n_for_wilson": n, "wilson_lb": wlb,
        "mean_entry_price_dollars": mean_entry_price, "mean_entry_fee_dollars": mean_entry_fee,
        "breakeven_win_rate": breakeven_win_rate,
        "clauses": {
            "1_mean_ev_both_weightings_ge_0.50c": clause1,
            "2_day_clustered_t_ge_bar": clause2,
            "3_sign_consistency_2of3_largest_families": clause3,
            "4_robust_after_drop5": clause4,
            "5_wilson_lb_above_breakeven": clause5,
        },
        "verdict": "PASS" if all_pass else "FAIL",
    })
    if not all_pass:
        failed = [k for k, v in result["clauses"].items() if not v]
        result["verdict_reason"] = f"pass-bar clauses failed: {failed}"
    log(f"\nclauses: {result['clauses']}")
    log(f"VERDICT: {result['verdict']}")

    finalize(result, log_lines, chosen_theta=chosen_theta, val_trades=val_trades)


def finalize(result, log_lines, chosen_theta, val_trades=None):
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    result["val_trades"] = val_trades or []
    json.dump(result, open(OUT_JSON, "w"), indent=1, default=str)
    print(f"\nwrote {OUT_JSON}")
    write_md(result)
    print(f"wrote {OUT_MD}")


def write_md(r):
    lines = []
    lines.append("# spec_M1 -- macro-surprise pass-through drift into next-meeting Fed-decision market")
    lines.append("")
    lines.append(f"Run: {r['run_ts']}")
    lines.append("")
    lines.append("## Data")
    lines.append(f"- Shards read: {r['shards_read']}")
    lines.append(f"- Local cached tape: {r['n_trades_local_tape']} trades, {r['n_tickers_local_tape']} distinct tickers, "
                 f"span {r['tape_span'][0]} .. {r['tape_span'][1]}")
    lines.append(f"- Window: t0 in [{r['window'][0]}, {r['window'][1]}]; FIT = release_date < {r['fit_end']}, "
                 "VALIDATION = release_date >= that date (calendar split, frozen; #29's original 2026-04-01 TEST "
                 "start is outside the archive entirely and unreachable, exactly as declared up front in the spec).")
    lines.append(f"- FIT release events: {r['fit_events_total']}; VALIDATION release events: {r['val_events_total']}")
    lines.append("- Outcomes: Kalshi's own `result` field in the archived markets table (GROUNDING.md states this "
                 "IS Kalshi's official settled outcome). Live reconciliation via GET /trade-api/v2/markets/{ticker} "
                 "was attempted for every rung with a blank archive result, and separately spot-checked against a "
                 "handful of settled family/Fed rungs spanning all 6 families -- **every single archived-era ticker "
                 "404s** on the live endpoint (a live KXHIGH weather ticker from the current week returns fine, "
                 "confirming the endpoint itself works). This is the same live-API retention wall documented in "
                 "REOPENABLE.md for /events; it blocks the spec's literal 'reconcile against GET /markets' "
                 "instruction for anything in the archive window. DIVERGENCE, reported per non-negotiable 1: "
                 "settlement truth for this run is the archive's `result` field alone; live reconciliation could not "
                 "be performed on any archived-era ticker.")
    lines.append("- Executable prices: entry = first trade with taker_side on our required side inside "
                 "[t0+5m,t0+20m] (that trade's own yes_price/no_price, i.e. the price the taker actually paid, "
                 "never mid, never best-in-window). Exit = first trade with the opposite taker_side inside "
                 "[t0+60m,t0+120m], priced via the spec's own complement formula. Missing exit -> marked out at "
                 "entry cost, both fees still charged, logged.")
    lines.append("")
    lines.append("## Interpretive constructions required by the frozen spec text (documented, not bar-moving)")
    lines.append("1. **Multi-ladder event collapse.** The spec defines a release EVENT as (family, calendar date) "
                 "and explicitly gives EMPLOYMENT per-sub-series hawkish signs (payrolls +1, KXU3 -1), which only "
                 "makes sense if multiple sub-ladders can be live for one event. The spec's u/z/x formulas are "
                 "written per-event (singular), so this run computes u/z/x per LADDER (per exact series-month), "
                 "then sets the event's x(e) = mean of the available per-ladder x_i(e). sigma_family remains a "
                 "single pooled FIT MAD per family (all ladders in that family, as literally specified).")
    lines.append("2. **Fee-inclusive breakeven for clause 5.** The spec names this without a formula. Implemented "
                 "as breakeven_win_rate = mean(entry_price) + mean(entry_fee), both in dollars per contract -- the "
                 "cost basis of acquiring the position, matching the clause's own text ('implied by the MEAN ENTRY "
                 "PRICE'). Note fee(p) = fee(1-p) exactly (the formula is symmetric), so which literal print-side "
                 "price is used for the exit leg's fee does not change any number in this run.")
    lines.append("")
    lines.append("## FIT theta selection")
    lines.append(f"- sigma_family (1.4826*MAD of FIT u, per family): {r['sigma_family']}")
    lines.append(f"- FIT u sample sizes per family: {r['fit_u_sample_sizes']}")
    if r.get("sigma_undefined_families"):
        lines.append(f"- **sigma UNDEFINED for**: {r['sigma_undefined_families']} -- these families have zero or "
                     "one FIT-window release event in the archive (JOBLESS: legacy `JOBLESS` series ends 2022-12-01, "
                     "`KXJOBLESSCLAIMS` does not start until 2025-06-12 -- there is a dead zone spanning the entire "
                     "FIT window; ISM's `KXISMPMI` does not start until 2025-04-01, also entirely after FIT ends). "
                     "**DIVERGENCE, reported per non-negotiable 1**: the frozen entry_rule requires sigma_family "
                     "estimated ON FIT ONLY, with no fallback specified. Per the frozen rule, x(e) and hence the "
                     "trigger are UNDEFINED for JOBLESS and ISM events -- every JOBLESS/ISM validation event is "
                     "skipped for this reason, not improvised around with a pooled or validation-window sigma.")
    for th, cell in r["fit_theta_grid"].items():
        lines.append(f"  - theta={th}: n_trades={cell['n_trades']}, n_clusters={cell['n_clusters']}, "
                     f"mean_net_c={cell['mean_net_c']}, t={cell['t']}")
    if r.get("self_kill_no_signal"):
        lines.append("")
        lines.append(f"**SELF-KILL: {r.get('verdict_reason')}**")
    else:
        lines.append("")
        lines.append(f"Chosen theta (max FIT day-clustered t, frozen henceforth): **{r.get('chosen_theta')}**")
    lines.append("")
    if "n_qualifying" in r:
        lines.append("## VALIDATION")
        lines.append(f"- Qualifying trades (triggered + entry executed): n={r['n_qualifying']}, "
                     f"families={r['families_present']} (n={r['n_families']}), "
                     f"release-date clusters={r['n_clusters']}")
        lines.append(f"- min_n gate: needs n>=40, families>=3, clusters>=40 -> "
                     f"{'CLEARED' if r['n_qualifying']>=40 and r['n_families']>=3 and r['n_clusters']>=40 else 'NOT CLEARED'}")
        if "clauses" in r:
            lines.append("")
            lines.append(f"- contract-weighted mean net EV: {r['contract_weighted_mean_c']:.4f} c/ct")
            lines.append(f"- print-weighted mean net EV: {r['print_weighted_mean_c']:.4f} c/ct")
            lines.append(f"- day-clustered t = {r['day_clustered_t']}, df={r['df']}, exact bar={r['t_bar_exact']:.4f}")
            lines.append(f"- top-3 families by n: {r['top3_families_by_n']}, sign-consistent in {r['fam_sign_ok_count']}/3")
            lines.append(f"- robustness (drop 5 best release-date clusters {r['dropped_5_best_days']}): "
                         f"{r['robustness_mean_after_drop5_c']}")
            lines.append(f"- win rate {r['wins']}/{r['n_for_wilson']}, Wilson 95% LB={r['wilson_lb']}, "
                         f"breakeven={r['breakeven_win_rate']:.4f}")
            lines.append("")
            lines.append(f"Clauses: {r['clauses']}")
    lines.append("")
    lines.append(f"## VERDICT: {r['verdict']}")
    if r.get("verdict_reason"):
        lines.append(f"Reason: {r['verdict_reason']}")
    lines.append("")
    lines.append("## Skip ledger (mandatory -- every dropped release event, with reason)")
    if r.get("self_kill_no_signal"):
        lines.append("VALIDATION was never opened (self-kill fired at the FIT stage, per kill_conditions -- "
                     "reading validation after a self-kill would itself be a non-negotiable-1 violation). "
                     "The ledger below is every FIT-phase drop across all four theta trials (theta grid re-run "
                     "means the same event can appear once per theta cell it was tried against).")
        ledger = r.get("fit_skip_ledger_exploratory", [])
    else:
        ledger = r.get("skip_ledger", [])
    lines.append(f"Total skip-ledger entries: {len(ledger)}")

    def _bucket(reason):
        for tag in ("no pre-t0 ladder print", "settlement result unavailable", "sigma_family",
                    "no executable entry print", "no exit print", "ladder strikes unparseable",
                    "no still-open Fed event", "all rungs classified HOLD"):
            if tag in reason:
                return tag
        return reason[:60]
    reason_counts = {}
    for s in ledger:
        b = _bucket(s["reason"])
        reason_counts[b] = reason_counts.get(b, 0) + 1
    lines.append(f"By reason: {reason_counts}")
    lines.append("")
    lines.append("<details><summary>full skip ledger</summary>")
    lines.append("")
    lines.append("```")
    for s in ledger:
        lines.append(json.dumps(s, default=str))
    lines.append("```")
    lines.append("</details>")
    if not r.get("self_kill_no_signal"):
        lines.append("")
        lines.append("Also recorded (exploratory, not the mandated ledger): FIT-phase skips across all four theta "
                     "trials, in spec_M1.json under `fit_skip_ledger_exploratory`.")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("```")
    lines.append("python venue_expansion/cache/prereg/m1_markets_pull.py   # -> cache/M1/markets_universe.json")
    lines.append("python venue_expansion/cache/prereg/m1_build_events.py   # -> cache/M1/events.json")
    lines.append("python venue_expansion/cache/prereg/m1_tape_pull.py      # -> cache/prereg/tape/shard-*.parquet (all 16)")
    lines.append("python venue_expansion/spec_M1.py                        # -> out/spec_M1.json, out/spec_M1.md")
    lines.append("```")
    open(OUT_MD, "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
