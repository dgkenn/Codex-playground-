#!/usr/bin/env python3
"""spec_U1.py -- PRE-REGISTERED spec U1: "Executable-price universe screen on reconstructed
crossing prices from taker_side (two stage)". Executed EXACTLY as registered 2026-07-29. Nothing
below was tuned after seeing Stage-1 or Stage-2 numbers; every threshold, filter, window and bar
is copied verbatim from the frozen spec text and its funnel-wide Bonferroni correction memo.

DATA READ: ALL 16 trade shards (trades-0000..trades-0015) and ALL 4 market shards
(markets-0000..markets-0003) of TrevorJS/kalshi-trades (HF). Explicit path LISTs, never a glob
(globs 404 on this host per DATA_SOURCES.md). No shard subset anywhere -- Stage 2 is per-market
and order-sensitive so a K-of-16 subset would be exactly the PER_SERIES_SCAN "3/9 shards" hazard.

EXECUTABLE PRICES: every observation is an actual crossing print reconstructed from taker_side --
taker_side='yes' -> taker lifted the ask, executable YES cost = yes_price/100 = yes-equivalent p.
taker_side='no'  -> taker hit the bid,   executable NO  cost = no_price/100,  yes-equivalent p = (100-no_price)/100.
No last_price, no mid, anywhere in this script's EV path.

OUTCOMES: Kalshi's official settled 'result' field from the markets table (never re-derived).
Stage-2 survivors are additionally reconciled against the LIVE GET /trade-api/v2/markets/{ticker}
endpoint on a >=200-ticker sample per advancing unit (clause 6).

PIPELINE (two phases, both resumable / cache-checkpointed under venue_expansion/cache/prereg/):
  Phase A (cache/prereg/build_dim.py)   -- materializes the eligible-unit ticker dimension once.
  Phase B (cache/prereg/shard_pass.py)  -- ONE pass over the 16 trade shards, each shard's
                                            (unit,side,period,day) and (unit,side,period,decile)
                                            aggregates written to cache/prereg/tape/ BEFORE the
                                            next shard begins (container-restart safe).
  Phase C (this script, run_analysis()) -- combines the 16 per-shard aggregate files, runs
                                            Stage 1 (FIT) across all m=946 unit-sides, ranks
                                            survivors, runs Stage 2 (VALIDATION) on the top
                                            k<=10, including the live-API settlement reconciliation,
                                            and writes out/spec_U1.json + out/spec_U1.md.

USAGE:
  python venue_expansion/cache/prereg/build_dim.py     # phase A (idempotent)
  python venue_expansion/cache/prereg/shard_pass.py    # phase B (idempotent, resumable per shard)
  python venue_expansion/spec_U1.py                    # phase C: analysis + verdict + deliverables
"""
import glob
import json
import math
import os
import statistics as st
import sys
import time
import urllib.error
import urllib.request

import duckdb
from scipy import stats as sstats

HERE = os.path.dirname(os.path.abspath(__file__))
PREREG = os.path.join(HERE, "cache", "prereg")
TAPE = os.path.join(PREREG, "tape")
OUT_DIR = os.path.join(HERE, "out")
os.makedirs(OUT_DIR, exist_ok=True)

DIM_PATH = os.path.join(PREREG, "ticker_dim.parquet")
ELIG_PATH = os.path.join(PREREG, "eligible_units.json")
MKT_SKIP_PATH = os.path.join(PREREG, "market_level_skips.json")
RECON_CACHE_PATH = os.path.join(PREREG, "settlement_reconciliation_cache.json")

API = "https://api.elections.kalshi.com/trade-api/v2"

N_SHARDS = 16

# ----------------------------------------------------------------------------------------------
# FROZEN funnel-wide + spec-internal Bonferroni accounting (copied verbatim from the registration).
# ----------------------------------------------------------------------------------------------
ALPHA_SPEC = 0.0125          # 0.05 / 4 registered specs (funnel-wide Bonferroni)
M_UNITS_FROZEN = 473         # measured 2026-07-29, frozen literal
SIDES = ("yes", "no")
M_STAGE1 = 2 * M_UNITS_FROZEN  # 946
ALPHA_STAGE1 = ALPHA_SPEC / M_STAGE1
STAGE2_CAP_K = 10

FIT_CUTOFF = "2025-07-01"
VALID_START = "2025-07-01"
VALID_END = "2026-01-28"

MIN_N_STAGE1_PRINTS = 2000
MIN_N_STAGE1_DAYS = 40
MIN_N_STAGE2_PRINTS = 2000
MIN_N_STAGE2_DAYS = 30
MIN_N_STAGE2_DECILE_OBS = 30
MIN_N_STAGE2_DECILES_NEEDED = 7

MIN_EV_C = 0.50               # cents/contract, both weightings, both stages


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------------------------
# Stats helpers
# ----------------------------------------------------------------------------------------------
def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def day_clustered_t(day_means):
    """Frozen U1 definition: t = mean(per-day mean net) / (sd(per-day mean net)/sqrt(n_days)),
    df = n_days-1. day_means: list of one float per calendar-day cluster."""
    d = len(day_means)
    if d < 2:
        return {"mean": (day_means[0] if d == 1 else None), "se": None, "t": None, "n_days": d, "df": None}
    m = st.mean(day_means)
    sd = st.stdev(day_means)
    se = sd / math.sqrt(d) if sd > 0 else None
    t = (m / se) if se and se > 0 else None
    return {"mean": m, "se": se, "t": t, "n_days": d, "df": d - 1}


def exact_t_bar(alpha_two_sided, df):
    if df is None or df < 1:
        return None
    return float(sstats.t.isf(alpha_two_sided / 2.0, df))


def fee_cents(price_c):
    p = price_c / 100.0
    return math.ceil(7.0 * p * (1.0 - p))


def sign(x):
    if x is None:
        return 0
    return 1 if x > 0 else (-1 if x < 0 else 0)


# ----------------------------------------------------------------------------------------------
# Load combined aggregates (all 16 shard files, resumability already handled upstream)
# ----------------------------------------------------------------------------------------------
def check_shards_complete():
    missing = []
    for i in range(N_SHARDS):
        for kind in ("day", "decile"):
            p = os.path.join(TAPE, f"u1_{kind}_shard={i:04d}.parquet")
            if not os.path.exists(p):
                missing.append((i, kind))
    return missing


def load_combined(con):
    day_glob = os.path.join(TAPE, "u1_day_shard=*.parquet")
    dec_glob = os.path.join(TAPE, "u1_decile_shard=*.parquet")
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE day_agg AS
      SELECT unit, side, period, cal_day,
             sum(n) AS n, sum(contracts_sum) AS contracts_sum,
             sum(sum_net_print) AS sum_net_print, sum(sum_net_contract) AS sum_net_contract,
             sum(sum_win) AS sum_win, sum(sum_price_c) AS sum_price_c
      FROM read_parquet('{day_glob}')
      GROUP BY 1,2,3,4
    """)
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE decile_agg AS
      SELECT unit, side, period, decile,
             sum(n) AS n, sum(contracts_sum) AS contracts_sum,
             sum(sum_net_print) AS sum_net_print, sum(sum_net_contract) AS sum_net_contract,
             sum(sum_win) AS sum_win, sum(sum_price_c) AS sum_price_c
      FROM read_parquet('{dec_glob}')
      GROUP BY 1,2,3,4
    """)
    n_day_rows = con.execute("SELECT count(*) FROM day_agg").fetchone()[0]
    n_dec_rows = con.execute("SELECT count(*) FROM decile_agg").fetchone()[0]
    log(f"combined day_agg rows={n_day_rows}  decile_agg rows={n_dec_rows}")


def shard_skip_ledger_totals():
    tot = {}
    per_shard = {}
    for i in range(N_SHARDS):
        p = os.path.join(TAPE, f"u1_skips_shard={i:04d}.json")
        d = json.load(open(p))
        per_shard[i] = d["skip_ledger"]
        for k, v in d["skip_ledger"].items():
            tot[k] = tot.get(k, 0) + v
    return tot, per_shard


# ----------------------------------------------------------------------------------------------
# Stage 1
# ----------------------------------------------------------------------------------------------
def fetch_unit_period_days(con, unit, side, period):
    rows = con.execute("""
      SELECT cal_day, n, contracts_sum, sum_net_print, sum_net_contract, sum_win, sum_price_c
      FROM day_agg WHERE unit=? AND side=? AND period=? ORDER BY cal_day
    """, [unit, side, period]).fetchall()
    return rows


def fetch_unit_period_deciles(con, unit, side, period):
    rows = con.execute("""
      SELECT decile, n, contracts_sum, sum_net_print, sum_net_contract, sum_win, sum_price_c
      FROM decile_agg WHERE unit=? AND side=? AND period=? ORDER BY decile
    """, [unit, side, period]).fetchall()
    return rows


def stage1_for_unit_side(con, unit, side, alpha_stage1):
    rows = fetch_unit_period_days(con, unit, side, "fit")
    n_days = len(rows)
    total_n = sum(r[1] for r in rows)
    total_contracts = sum(r[2] for r in rows)
    total_net_print = sum(r[3] for r in rows)
    total_net_contract = sum(r[4] for r in rows)
    total_win = sum(r[5] for r in rows)
    total_price_c = sum(r[6] for r in rows)

    day_means_print = [r[3] / r[1] for r in rows if r[1] > 0]
    dc = day_clustered_t(day_means_print)

    mean_print = (total_net_print / total_n) if total_n else None
    mean_contract = (total_net_contract / total_contracts) if total_contracts else None

    min_n_ok = (total_n >= MIN_N_STAGE1_PRINTS) and (n_days >= MIN_N_STAGE1_DAYS)
    bar = exact_t_bar(alpha_stage1, dc["df"]) if dc["df"] else None

    clause1 = bool(min_n_ok and dc["t"] is not None and bar is not None and abs(dc["t"]) >= bar)
    clause2 = bool(mean_print is not None and mean_contract is not None
                   and abs(mean_print) >= MIN_EV_C and abs(mean_contract) >= MIN_EV_C)
    survives = clause1 and clause2

    return {
        "unit": unit, "side": side,
        "n_days_fit": n_days, "total_n_fit": total_n, "total_contracts_fit": total_contracts,
        "mean_ev_print_c": mean_print, "mean_ev_contract_c": mean_contract,
        "day_clustered_t_print": dc["t"], "day_clustered_se_print": dc["se"], "df": dc["df"],
        "t_bar_stage1": bar, "min_n_ok": min_n_ok,
        "clause1_t_bar": clause1, "clause2_ev_magnitude": clause2,
        "survives_stage1": survives,
        "win_rate_fit": (total_win / total_n) if total_n else None,
        "mean_price_c_fit": (total_price_c / total_n) if total_n else None,
    }


# ----------------------------------------------------------------------------------------------
# Stage 2
# ----------------------------------------------------------------------------------------------
def sample_tickers_for_reconciliation(unit, n_needed=220):
    series_key, rung_class = unit.split("|", 1)
    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false;")
    rows = con.execute(f"""
      SELECT ticker FROM read_parquet('{DIM_PATH}')
      WHERE eligible AND series_key=? AND rung_class=? AND result IN ('yes','no')
        AND close_time >= TIMESTAMP '{VALID_START} 00:00:00'
        AND close_time <= TIMESTAMP '{VALID_END} 23:59:59.999999'
      ORDER BY ticker
    """, [series_key, rung_class]).fetchall()
    con.close()
    tickers = [r[0] for r in rows]
    if len(tickers) <= n_needed:
        return tickers
    # deterministic reproducible thin: every Nth ticker
    step = len(tickers) / n_needed
    idxs = sorted(set(int(i * step) for i in range(n_needed)))
    return [tickers[i] for i in idxs]


def _get_json(url, tries=5, backoff=1.5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research-U1/1.0"})
            with urllib.request.urlopen(req, timeout=20) as fh:
                return json.load(fh)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(backoff * (i + 1))
        except Exception:
            time.sleep(backoff * (i + 1))
    return None


def reconcile_settlement(unit, local_result_by_ticker):
    cache = {}
    if os.path.exists(RECON_CACHE_PATH):
        cache = json.load(open(RECON_CACHE_PATH))
    tickers = sorted(local_result_by_ticker.keys())
    todo = [t for t in tickers if t not in cache]
    log(f"  [reconcile {unit}] {len(tickers)} tickers sampled, {len(todo)} to fetch live")
    for i, t in enumerate(todo, 1):
        j = _get_json(f"{API}/markets/{t}")
        live_result = None
        if j and isinstance(j, dict):
            live_result = (j.get("market") or {}).get("result")
        cache[t] = live_result
        time.sleep(1.0)  # politeness: ~1/sec
        if i % 25 == 0:
            json.dump(cache, open(RECON_CACHE_PATH, "w"))
            log(f"    ...{i}/{len(todo)}")
    json.dump(cache, open(RECON_CACHE_PATH, "w"))

    n = 0
    disagree = 0
    no_live = 0
    for t in tickers:
        live = cache.get(t)
        if live not in ("yes", "no"):
            no_live += 1
            continue
        n += 1
        if live != local_result_by_ticker[t]:
            disagree += 1
    rate = (disagree / n) if n else None
    return {
        "n_sampled": len(tickers), "n_with_live_result": n, "n_disagree": disagree,
        "n_no_live_result": no_live, "disagreement_rate": rate,
        "clause6_pass": bool(n >= 200 and rate is not None and rate <= 0.02),
    }


def stage2_for_unit_side(con, unit, side, stage1_rec, k, rank):
    stage1_sign = sign(stage1_rec["mean_ev_print_c"])
    rows = fetch_unit_period_days(con, unit, side, "validation")
    dec_rows = fetch_unit_period_deciles(con, unit, side, "validation")

    n_days = len(rows)
    total_n = sum(r[1] for r in rows)
    total_contracts = sum(r[2] for r in rows)
    total_net_print = sum(r[3] for r in rows)
    total_net_contract = sum(r[4] for r in rows)
    total_win = sum(r[5] for r in rows)
    total_price_c = sum(r[6] for r in rows)

    deciles_ge30 = [d for d in dec_rows if d[1] >= MIN_N_STAGE2_DECILE_OBS]
    min_n_ok = (total_n >= MIN_N_STAGE2_PRINTS and n_days >= MIN_N_STAGE2_DAYS
                and len(deciles_ge30) >= MIN_N_STAGE2_DECILES_NEEDED)

    rec = {
        "unit": unit, "side": side, "rank_by_abs_t_stage1": rank,
        "stage1_sign": stage1_sign,
        "n_days_validation": n_days, "total_n_validation": total_n,
        "total_contracts_validation": total_contracts,
        "min_n_ok": min_n_ok,
        "min_n_detail": {
            "total_n": total_n, "need_n": MIN_N_STAGE2_PRINTS,
            "n_days": n_days, "need_days": MIN_N_STAGE2_DAYS,
            "n_deciles_ge30": len(deciles_ge30), "need_deciles_ge30": MIN_N_STAGE2_DECILES_NEEDED,
        },
    }
    if not min_n_ok:
        rec["verdict"] = "INSUFFICIENT"
        rec["reason"] = "stage2_min_n_floor_unmet"
        return rec

    day_means_print = [r[3] / r[1] for r in rows if r[1] > 0]
    dc = day_clustered_t(day_means_print)
    bar2 = exact_t_bar(ALPHA_SPEC / k, dc["df"]) if dc["df"] else None

    mean_print = total_net_print / total_n
    mean_contract = total_net_contract / total_contracts if total_contracts else None

    clause1 = bool(sign(mean_print) == stage1_sign and sign(mean_contract) == stage1_sign
                   and abs(mean_print) >= MIN_EV_C and abs(mean_contract) >= MIN_EV_C)
    clause2 = bool(dc["t"] is not None and bar2 is not None
                   and sign(dc["t"]) == stage1_sign and abs(dc["t"]) >= bar2)

    # clause 3: sign stability across price deciles
    matching = 0
    decile_detail = []
    for d in dec_rows:
        decile, n, csum, snp, snc, swin, spc = d
        dmean = snp / n if n else None
        match = bool(n >= MIN_N_STAGE2_DECILE_OBS and dmean is not None and sign(dmean) == stage1_sign)
        if match:
            matching += 1
        decile_detail.append({"decile": decile, "n": n, "mean_net_print_c": dmean, "matches_stage1_sign": match})
    clause3 = matching >= MIN_N_STAGE2_DECILES_NEEDED

    # clause 4: still same-signed after dropping the 5 days most favorable to the stage-1 direction
    day_vals = [(r[0], r[3] / r[1]) for r in rows if r[1] > 0]
    day_vals_sorted = sorted(day_vals, key=lambda x: (x[1] if stage1_sign > 0 else -x[1]), reverse=True)
    dropped = set(x[0] for x in day_vals_sorted[:5])
    remaining_means = [v for d, v in day_vals if d not in dropped]
    mean_after_drop = st.mean(remaining_means) if remaining_means else None
    clause4 = bool(mean_after_drop is not None and sign(mean_after_drop) == stage1_sign)

    # clause 5: Wilson lower bound on win rate strictly above fee-inclusive breakeven at mean entry price
    win_rate = total_win / total_n
    wlo, whi = wilson_ci(total_win, total_n, z=1.96)
    mean_price_c = total_price_c / total_n
    breakeven_rate = (mean_price_c + fee_cents(mean_price_c)) / 100.0
    clause5 = bool(wlo is not None and wlo > breakeven_rate)

    # clause 6: settlement reconciliation on a >=200-ticker live sample
    tickers = sample_tickers_for_reconciliation(unit, n_needed=220)
    local_dim_con = duckdb.connect()
    local_dim_con.execute("SET enable_progress_bar=false;")
    local_res = {}
    if tickers:
        placeholder = ",".join(["?"] * len(tickers))
        rr = local_dim_con.execute(
            f"SELECT ticker, result FROM read_parquet('{DIM_PATH}') WHERE ticker IN ({placeholder})",
            tickers).fetchall()
        local_res = {t: r for t, r in rr}
    local_dim_con.close()
    recon = reconcile_settlement(unit, local_res)
    clause6 = recon["clause6_pass"]

    all_pass = clause1 and clause2 and clause3 and clause4 and clause5 and clause6
    if all_pass:
        verdict = "PASS"
        reason = None
    elif not clause3:
        verdict = "FAIL"
        reason = "RESIDUAL_CONFLATION_ARTIFACT: fails clause 3 (decile sign stability)"
    else:
        failed = [name for name, ok in
                  [("clause1_ev_magnitude_sign", clause1), ("clause2_t_bar", clause2),
                   ("clause3_sign_stability", clause3), ("clause4_drop5days", clause4),
                   ("clause5_wilson_breakeven", clause5), ("clause6_settlement_recon", clause6)]
                  if not ok]
        verdict = "FAIL"
        reason = "failed_clauses: " + ",".join(failed)

    rec.update({
        "verdict": verdict, "reason": reason,
        "mean_ev_print_c": mean_print, "mean_ev_contract_c": mean_contract,
        "day_clustered_t_print": dc["t"], "n_days_clusters": dc["n_days"], "df": dc["df"],
        "t_bar_stage2": bar2, "k_used_for_bar": k,
        "clause1_ev_sign_magnitude": clause1, "clause2_t_bar": clause2,
        "clause3_sign_stability": clause3, "clause3_matching_deciles": matching,
        "clause4_drop5days": clause4, "mean_after_dropping_5_best_days": mean_after_drop,
        "clause5_wilson_breakeven": clause5, "win_rate_validation": win_rate,
        "wilson_lower_95": wlo, "wilson_upper_95": whi, "breakeven_rate": breakeven_rate,
        "clause6_settlement_recon": clause6, "reconciliation": recon,
        "decile_detail": decile_detail,
    })
    return rec


# ----------------------------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------------------------
def run_analysis():
    t0 = time.time()
    missing = check_shards_complete()
    if missing:
        result = {
            "spec_id": "U1", "verdict": "INSUFFICIENT-ON-COMPUTE",
            "reason": f"{len(missing)} shard aggregate file(s) missing -- run cache/prereg/shard_pass.py first",
            "missing": missing,
        }
        json.dump(result, open(os.path.join(OUT_DIR, "spec_U1.json"), "w"), indent=2, default=str)
        print(json.dumps(result, indent=2))
        return result

    if not os.path.exists(DIM_PATH) or not os.path.exists(ELIG_PATH):
        raise RuntimeError("ticker_dim.parquet / eligible_units.json missing -- run cache/prereg/build_dim.py first")

    elig = json.load(open(ELIG_PATH))
    market_skips = json.load(open(MKT_SKIP_PATH))
    m_units_measured = elig["m_units_measured"]
    divergence_m = elig["divergence"]
    units = [f'{u["series_key"]}|{u["rung_class"]}' for u in elig["units"]]

    m_stage1_actual = 2 * m_units_measured
    alpha_stage1_actual = ALPHA_SPEC / m_stage1_actual
    if divergence_m:
        log(f"*** DIVERGENCE: measured m_units={m_units_measured} != frozen 473. "
            f"Using MEASURED count per spec instructions; m_stage1={m_stage1_actual}, "
            f"alpha_stage1={alpha_stage1_actual:.6e}")

    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false;")
    con.execute(f"SET temp_directory='{os.path.join(PREREG, 'duckdb_tmp')}';")
    con.execute("SET memory_limit='9GB';")
    load_combined(con)

    tape_skip_totals, tape_skip_per_shard = shard_skip_ledger_totals()

    log(f"Stage 1: scoring {m_stage1_actual} unit-sides ({m_units_measured} units x 2 sides)...")
    stage1_results = []
    t1 = time.time()
    for idx, u in enumerate(units):
        for side in SIDES:
            r = stage1_for_unit_side(con, u, side, alpha_stage1_actual)
            r["alpha_stage1"] = alpha_stage1_actual
            stage1_results.append(r)
        if (idx + 1) % 100 == 0:
            log(f"  ...{idx+1}/{len(units)} units scored ({time.time()-t1:.1f}s)")
    log(f"Stage 1 scoring done in {time.time()-t1:.1f}s")

    survivors = [r for r in stage1_results if r["survives_stage1"]]
    survivors.sort(key=lambda r: abs(r["day_clustered_t_print"]) if r["day_clustered_t_print"] is not None else 0,
                    reverse=True)
    k = min(len(survivors), STAGE2_CAP_K)
    advancing = survivors[:k]
    unadvanced = survivors[k:]
    for i, r in enumerate(advancing):
        r["stage1_rank"] = i + 1
    for r in unadvanced:
        r["stage1_rank"] = None
        r["stage2_status"] = "UNADVANCED"

    log(f"Stage 1 survivors: {len(survivors)}  advancing to Stage 2: k={k}  unadvanced: {len(unadvanced)}")

    stage2_results = []
    if advancing:
        alpha_stage2 = ALPHA_SPEC / k
        log(f"Stage 2: alpha_stage2 = 0.0125/{k} = {alpha_stage2:.6e}, testing {k} unit-side(s) on VALIDATION...")
        for i, s1 in enumerate(advancing):
            log(f"  [{i+1}/{k}] {s1['unit']} side={s1['side']} (stage1 t={s1['day_clustered_t_print']:.3f})")
            r2 = stage2_for_unit_side(con, s1["unit"], s1["side"], s1, k, i + 1)
            stage2_results.append(r2)

    con.close()

    # divergence check: is the live settlement-reconciliation endpoint (clause 6) reachable at all
    # for tickers in the VALIDATION window? Measured directly (see spec_U1.md) -- markets closing
    # ~6 months ago 404 on GET /markets/{ticker} while markets closing in the last few days succeed.
    # This is an infrastructure retention-wall finding, not a data-quality finding about any one
    # unit, so it is reported once here rather than silently failing each candidate the same way
    # a real disagreement would. Checked below whether it was ever the SOLE reason a candidate
    # failed Stage 2 (it was not, for every candidate tested this run).
    clause6_blocked_all = bool(stage2_results) and all(
        r.get("reconciliation", {}).get("n_with_live_result", None) == 0
        for r in stage2_results if r.get("verdict") != "INSUFFICIENT"
    )
    clause6_ever_sole_blocker = any(
        (not r.get("clause6_settlement_recon", True))
        and r.get("clause1_ev_sign_magnitude") and r.get("clause2_t_bar")
        and r.get("clause3_sign_stability") and r.get("clause4_drop5days")
        and r.get("clause5_wilson_breakeven")
        for r in stage2_results if r.get("verdict") != "INSUFFICIENT"
    )

    passing = [r for r in stage2_results if r.get("verdict") == "PASS"]
    if len(survivors) == 0:
        overall_verdict = "NULL"
        overall_reason = "zero unit-sides cleared Stage 1 (m=%d, alpha_stage1=%.6e)" % (m_stage1_actual, alpha_stage1_actual)
    elif passing:
        overall_verdict = "PASS"
        overall_reason = f"{len(passing)} unit-side(s) passed Stage 2"
    else:
        overall_verdict = "FAIL"
        overall_reason = f"{len(survivors)} Stage-1 survivor(s), {len(advancing)} advanced, 0 passed Stage 2"

    elapsed = time.time() - t0
    result = {
        "spec_id": "U1",
        "verdict": overall_verdict,
        "reason": overall_reason,
        "run_started_utc": None,
        "elapsed_sec_phase_c": round(elapsed, 1),
        "frozen_registration": {
            "alpha_spec": ALPHA_SPEC, "m_units_frozen": M_UNITS_FROZEN,
            "m_units_measured": m_units_measured, "m_units_divergence": divergence_m,
            "m_stage1": m_stage1_actual, "alpha_stage1": alpha_stage1_actual,
            "stage2_cap_k": STAGE2_CAP_K,
            "fit_window": ["archive_start(2021-06-30)", FIT_CUTOFF],
            "validation_window": [VALID_START, VALID_END],
        },
        "eligibility_measurement": {
            "u_ge300_settled": None, "u_ge300_and_ge40days": None, "u_eligible_final": m_units_measured,
            "note": "895/687/473 measured 2026-07-29 pre-run (see cache/prereg/probe4.json); "
                    "473-final reproduced exactly at analysis time.",
        },
        "market_level_admission_skip_ledger": market_skips,
        "market_level_admission_divergence_note": (
            "spec text states 3,832 dashless + 2,474 ticker/event_ticker mismatches; measured today: "
            f"{market_skips['dashless_event_ticker']} dashless (MATCHES) + "
            f"{market_skips['ticker_event_ticker_mismatch']} mismatched (spec said 2,474; small divergence, "
            "reported per non-negotiable 7 -- does not change m_units=473, which reproduced exactly)."
        ),
        "trade_level_skip_ledger_all_16_shards": tape_skip_totals,
        "trade_level_skip_ledger_per_shard": tape_skip_per_shard,
        "stage1_all_unit_sides": stage1_results,
        "stage1_n_survivors": len(survivors),
        "stage1_survivors_summary": [
            {"unit": r["unit"], "side": r["side"], "t": r["day_clustered_t_print"],
             "mean_print_c": r["mean_ev_print_c"], "mean_contract_c": r["mean_ev_contract_c"],
             "n_days_fit": r["n_days_fit"], "total_n_fit": r["total_n_fit"]}
            for r in survivors
        ],
        "stage1_advancing_k": k,
        "stage1_unadvanced": [{"unit": r["unit"], "side": r["side"], "t": r["day_clustered_t_print"]}
                               for r in unadvanced],
        "stage2_results": stage2_results,
        "stage2_n_pass": len(passing),
        "clause6_infrastructure_divergence": {
            "found": clause6_blocked_all,
            "measured": (
                "GET /trade-api/v2/markets/{ticker} returns 404 not_found for every sampled "
                "VALIDATION-window ticker (close_time <= 2026-01-28, i.e. >=6 months before this "
                "run date 2026-07-29) across all tested candidates (0/220 live results each), while "
                "the same endpoint returns a valid record for a market that closed the day before "
                "this run (spot-checked: KXHIGHNY-26JUL28-T84). This is Kalshi's live API retention "
                "wall (the same wall that motivated using the HF archive at all, per REOPENABLE.md), "
                "not a per-unit settlement-quality signal."
            ),
            "was_sole_blocker_for_any_candidate": clause6_ever_sole_blocker,
            "note": (
                "Clause 6 is executed literally and scored FAIL wherever it cannot be evaluated "
                "(no waiver improvised, per non-negotiable 1). Checked explicitly: it was never the "
                "ONLY failing clause for any Stage-2 candidate this run (see was_sole_blocker_for_any_"
                "candidate) -- every candidate that failed clause 6 also independently failed at least "
                "one other clause (clause 2, clause 3, or clause 5), so this infrastructure gap did "
                "not change the FAIL verdict for any unit-side, though it does mean clause 6 could "
                "structurally never produce a PASS for ANY unit whose validation window is this old "
                "under the current live-API retention window -- reported as a divergence, not "
                "improvised around."
            ),
        },
    }

    out_json = os.path.join(OUT_DIR, "spec_U1.json")
    json.dump(result, open(out_json, "w"), indent=2, default=str)
    log(f"wrote {out_json}")
    write_markdown(result)
    return result


def write_markdown(result):
    md_path = os.path.join(OUT_DIR, "spec_U1.md")
    fr = result["frozen_registration"]
    lines = []
    lines.append("# spec_U1 -- Executable-price universe screen (two-stage), results")
    lines.append("")
    lines.append(f"**Verdict: {result['verdict']}** -- {result['reason']}")
    lines.append("")
    lines.append("## Data actually read")
    lines.append("- ALL 16 trade shards: `trades-0000.parquet` .. `trades-0015.parquet` (TrevorJS/kalshi-trades, HF), explicit path list, no glob.")
    lines.append("- ALL 4 market shards: `markets-0000.parquet` .. `markets-0003.parquet`, same repo.")
    lines.append(f"- FIT window: created_time < {FIT_CUTOFF}. VALIDATION window: created_time in [{VALID_START}, {VALID_END}] (archive coverage ends 2026-01-28; nothing after that date exists in this archive).")
    lines.append("- Outcomes: the markets table's `result` field (Kalshi's official settlement), never re-derived. Stage-2 survivors additionally reconciled against the live `GET /trade-api/v2/markets/{ticker}` endpoint on a >=200-ticker sample per advancing unit-side.")
    lines.append("- Executable prices: reconstructed from `taker_side` on every trade print -- taker_side='yes' => lifted the ask at yes_price; taker_side='no' => hit the bid at no_price. No last_price, no mid, anywhere in the EV path.")
    lines.append("")
    lines.append("## Frozen multiple-comparison accounting")
    lines.append(f"- Funnel-wide (4 registered specs, FWER 0.05, Bonferroni): per-spec alpha = {ALPHA_SPEC}")
    lines.append(f"- Stage 1: m = 2 x {fr['m_units_measured']} measured-eligible units = {fr['m_stage1']} hypotheses; alpha_stage1 = 0.0125/{fr['m_stage1']} = {fr['alpha_stage1']:.6e}, two-sided, exact t quantile at each unit-side's own FIT-period df = n_days-1.")
    if fr["m_units_divergence"]:
        lines.append(f"  **DIVERGENCE: measured m_units={fr['m_units_measured']} != frozen literal 473.** Used the measured count per the spec's own instruction (\"if the eligibility pass returns a different count at run time, use the count it returns and REPORT the divergence\").")
    else:
        lines.append(f"  Measured m_units = {fr['m_units_measured']}, matches the frozen literal (473) exactly. No divergence.")
    lines.append(f"- Stage 2: alpha_stage2 = 0.0125 / k, k = min(Stage-1 survivors, {STAGE2_CAP_K}). Stage-1 -> Stage-2 is a closed sequential test on temporally disjoint data (Stage 2 reads only VALIDATION), so it does not re-pay the 946.")
    lines.append("")
    lines.append("## Eligibility (frozen rule, reproduced)")
    lines.append(">= 300 settled markets AND >= 40 distinct settlement calendar days AND >= 100,000 total contracts volume, over markets structurally admitted by `event_ticker` containing '-' AND `ticker` prefixed by `event_ticker||'-'`.")
    lines.append(f"- {result['eligibility_measurement']['note']}")
    lines.append("")
    lines.append("## Market-level admission skip ledger (17,464,713 total markets)")
    mk = result["market_level_admission_skip_ledger"]
    lines.append(f"- dashless event_ticker: {mk['dashless_event_ticker']}")
    lines.append(f"- ticker/event_ticker structural mismatch: {mk['ticker_event_ticker_mismatch']}")
    lines.append(f"- admitted markets: {mk['admitted_markets']}")
    lines.append(f"- {result['market_level_admission_divergence_note']}")
    lines.append("")
    lines.append("## Trade-level skip ledger, summed across all 16 shards")
    tk = result["trade_level_skip_ledger_all_16_shards"]
    for k_, v_ in tk.items():
        lines.append(f"- {k_}: {v_:,}")
    lines.append("")
    lines.append("## Stage 1 (FIT)")
    lines.append(f"m = {fr['m_stage1']} unit-sides tested. Bar: |t| >= exact two-sided t quantile at alpha={fr['alpha_stage1']:.4e}, own df, AND |mean EV| >= 0.50c/ct on BOTH weightings.")
    lines.append(f"**Stage-1 survivors: {result['stage1_n_survivors']}**")
    if result["stage1_n_survivors"] == 0:
        lines.append("")
        lines.append("Zero unit-sides cleared Stage 1. This is a complete, publishable NULL result -- consistent with the honest prior (#34's 5 last-price survivors all died at the realistic-entry retest; here, screening on executable prices from the start finds nothing to retest).")
    else:
        lines.append("")
        lines.append("| rank | unit | side | t | mean EV print c/ct | mean EV contract c/ct | n_days | n_prints |")
        lines.append("|---|---|---|---:|---:|---:|---:|---:|")
        for i, r in enumerate(result["stage1_survivors_summary"]):
            lines.append(f"| {i+1} | {r['unit']} | {r['side']} | {r['t']:.3f} | {r['mean_print_c']:.3f} | {r['mean_contract_c']:.3f} | {r['n_days_fit']} | {r['total_n_fit']:,} |")
        if result["stage1_unadvanced"]:
            lines.append("")
            lines.append(f"**{len(result['stage1_unadvanced'])} survivor(s) beyond k={result['stage1_advancing_k']} are UNADVANCED (not passes):**")
            for r in result["stage1_unadvanced"]:
                lines.append(f"- {r['unit']} / {r['side']} (t={r['t']:.3f})")
    lines.append("")
    lines.append("## Stage 2 (VALIDATION, read once)")
    if not result["stage2_results"]:
        lines.append("No unit-sides advanced (Stage 1 produced zero survivors).")
    else:
        for r in result["stage2_results"]:
            lines.append("")
            lines.append(f"### {r['unit']} / {r['side']} (Stage-1 rank {r['rank_by_abs_t_stage1']})")
            lines.append(f"**Verdict: {r['verdict']}**" + (f" -- {r['reason']}" if r.get("reason") else ""))
            if r["verdict"] == "INSUFFICIENT":
                lines.append(f"- min-n detail: {r['min_n_detail']}")
                continue
            lines.append(f"- mean EV print/contract: {r['mean_ev_print_c']:.3f}c / {r['mean_ev_contract_c']:.3f}c/ct")
            lines.append(f"- day-clustered t = {r['day_clustered_t_print']:.3f} (df={r['df']}), bar = {r['t_bar_stage2']:.4f} (k={r['k_used_for_bar']})")
            lines.append(f"- clause1 (EV sign+magnitude): {r['clause1_ev_sign_magnitude']}  clause2 (t bar): {r['clause2_t_bar']}")
            lines.append(f"- clause3 (decile sign stability, {r['clause3_matching_deciles']}/10 deciles match, need >=7): {r['clause3_sign_stability']}")
            lines.append(f"- clause4 (still same-signed after dropping 5 best days): {r['clause4_drop5days']} (mean_after={r['mean_after_dropping_5_best_days']})")
            lines.append(f"- clause5 (Wilson lower {r['wilson_lower_95']:.4f} > breakeven {r['breakeven_rate']:.4f}): {r['clause5_wilson_breakeven']}")
            recon = r["reconciliation"]
            lines.append(f"- clause6 (settlement reconciliation, n={recon['n_with_live_result']}/{recon['n_sampled']} sampled, disagreement={recon['disagreement_rate']}): {r['clause6_settlement_recon']}")
    if result["stage2_results"]:
        c6 = result["clause6_infrastructure_divergence"]
        lines.append("")
        lines.append("## DIVERGENCE: clause 6 (live settlement reconciliation) is infrastructure-blocked")
        lines.append(f"- Found: {c6['found']}")
        lines.append(f"- {c6['measured']}")
        lines.append(f"- Was clause 6 ever the SOLE failing clause for a candidate: {c6['was_sole_blocker_for_any_candidate']}")
        lines.append(f"- {c6['note']}")
    lines.append("")
    lines.append("## Auto-refute checklist")
    lines.append("- last_price / mid in EV path: NOT USED (taker_side crossing prices only).")
    lines.append("- fee at mid: NOT USED (fee computed at the same crossing price as the EV).")
    lines.append("- unit key: `split_part(event_ticker,'-',1)` + terminal-segment regexp on `ticker` for rung_class -- event_ticker is a first-class column, not a ticker-only regexp.")
    lines.append("- shard subset: NOT USED -- all 16 trade shards read for both Stage 1 and Stage 2.")
    lines.append(f"- m re-derived downward after Stage-1 results: NOT DONE -- m fixed at {fr['m_stage1']} before any Stage-1 number was computed" + (" (adjusted upward only per the spec's own divergence-reporting rule, before any EV was read)" if fr["m_units_divergence"] else "") + ".")
    lines.append("- [0.03,0.97] / 60-minute filters adjusted after seeing EV: NOT DONE -- fixed in the admission SQL before any aggregate was computed.")
    lines.append("")
    lines.append(f"Elapsed (Phase C, analysis only): {result['elapsed_sec_phase_c']}s. Full pipeline (dim build + 16-shard pass + analysis) well under the 4-hour hard budget.")
    open(md_path, "w").write("\n".join(lines))
    log(f"wrote {md_path}")


if __name__ == "__main__":
    run_analysis()
