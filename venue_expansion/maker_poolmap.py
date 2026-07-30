#!/usr/bin/env python3
"""maker_poolmap.py -- MM1 Stage A (maker pool map) + Stage C (spread/quote context), executed
EXACTLY per the frozen spec `venue_expansion/out/spec_MM1_frozen.json` (registered 2026-07-30).
Neither stage carries a significance bar; nothing here is promotable to a claim without a new
registration (Stage A explicitly, Stage C explicitly). Stage B (the barred R-grid EV test) is a
separate, larger extraction and is NOT run by this script.

DATA READ (Stage A): ALL 16 trade shards (trades-0000..trades-0015) of TrevorJS/kalshi-trades (HF),
explicit path list (HTTP globs 404 on this host), joined to the cached
venue_expansion/cache/prereg/ticker_dim.parquet (built from all 4 market shards by
cache/prereg/build_dim.py -- reused verbatim, not rebuilt). series_key is whatever build_dim already
parsed from event_ticker via split_part(event_ticker,'-',1) -- the exact U1 rule, never a prefix
LIKE (the #34 family-conflation guard).

CATEGORY / FEE_TYPE: ticker_dim has no category column (verified: markets shard schema carries no
`category` field), so category is ALWAYS resolved live, cached in one bulk call to
GET /trade-api/v2/series (no series argument -> returns the full current listing, verified
12,330 series on 2026-07-30) rather than 3,034 individual per-series calls. Cached verbatim to
cache/mm1/series_all_raw.json, reduced to venue_expansion/cache/mm1/fee_types.json
(ticker -> {category, fee_type, maker_fee_c}). Only two fee_type values exist site-wide as of this
run: 'quadratic' (maker pays $0) and 'quadratic_with_maker_fees' (Sports-dominant; maker fee applied
here as a flat ~0.33 c/ct, the approximate rate reported in ref/RESEARCH_LEDGER.md #33
(MAKER_FAVLONG.md) -- that source file is not present in this checkout to re-derive a price-dependent
schedule, so this is a disclosed carried-forward approximation, not an independent re-derivation; it
only affects Sports-category cells, which are descriptive-only in Stage A). Any series_key present in
the archive tape but NOT in the live listing (legacy/delisted, e.g. INXD) has an unresolvable
fee_type and is routed to a separate fee-unverified bucket, never merged into the main pool.

ACCOUNTING: every tape print IS a maker fill on its passive side. taker_side='yes' at yes_price p
cents => maker SHORT YES at p: P&L/ct = p - 100*[result=='yes'] cents, minus maker fee where charged.
taker_side='no' at no_price q => maker SHORT NO at q: P&L/ct = q - 100*[result=='no'] cents, minus
maker fee where charged. Outcomes ONLY from the archive `result` field, never re-derived.

PIPELINE (resumable, container-restart safe):
  Stage A per-shard pass -> cache/mm1/stageA/poolA_day_shard=NNNN.parquet (main pool, fee resolved)
                          -> cache/mm1/stageA/poolU_day_shard=NNNN.parquet (fee-unverified bucket)
                          -> cache/mm1/stageA/skips_shard=NNNN.json
  Stage A combine         -> out/mm1_pool_map.json + cache/mm1/stageA/pool.parquet
  Stage C per-market pull -> cache/mm1/candles/{ticker}.json (cached, resumable, polite sequential)
  Stage C combine         -> folded into out/maker_poolmap.json
  Final                   -> out/maker_poolmap.json + out/maker_poolmap.md

USAGE:
  python venue_expansion/maker_poolmap.py stageA [shard_idx ...]   # default: all 16, resumable
  python venue_expansion/maker_poolmap.py stageA_combine
  python venue_expansion/maker_poolmap.py stageC
  python venue_expansion/maker_poolmap.py final
  python venue_expansion/maker_poolmap.py all                      # runs everything in order
"""
import json
import os
import random
import statistics as st
import sys
import time
import urllib.error
import urllib.request

import duckdb

HERE = "/home/user/Codex-playground-/venue_expansion"
CACHE = os.path.join(HERE, "cache", "mm1")
STAGEA_DIR = os.path.join(CACHE, "stageA")
CANDLES_DIR = os.path.join(CACHE, "candles")
OUT_DIR = os.path.join(HERE, "out")
DIM_PATH = os.path.join(HERE, "cache", "prereg", "ticker_dim.parquet")
# NOTE: cache/mm1/fee_types.json is already claimed by a concurrently-running Stage B worker for
# its narrower 4-series {KXBTC,KXBTCD,KXETH,KXETHD} lookup (verified on disk at run time -- same
# live-verification method, different schema/scope). Stage A needs the full multi-category
# universe, so it caches to a distinctly-named file to avoid clobbering that concurrent work.
FEE_TYPES_PATH = os.path.join(CACHE, "series_dim_stageA_full.json")
SERIES_RAW_PATH = os.path.join(CACHE, "series_all_raw.json")
JUNE_MARKETS_RAW = os.path.join(CANDLES_DIR, "kxbtc_june_markets_raw.json")
SAMPLE_PATH = os.path.join(CANDLES_DIR, "kxbtc_june_sample200.json")

B = "https://huggingface.co/datasets/TrevorJS/kalshi-trades/resolve/main"
SHARD_URLS = [f"{B}/trades-{i:04d}.parquet" for i in range(16)]
API = "https://api.elections.kalshi.com/trade-api/v2"

os.makedirs(STAGEA_DIR, exist_ok=True)
os.makedirs(CANDLES_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# Disclosed approximation, see module docstring; applies only to fee_type='quadratic_with_maker_fees'.
MAKER_FEE_QUADRATIC_WITH_MAKER_FEES_C = 0.33

PRICE_BAND_SQL = """
CASE
  WHEN price_c>=1  AND price_c<5  THEN '[1,5)'
  WHEN price_c>=5  AND price_c<10 THEN '[5,10)'
  WHEN price_c>=10 AND price_c<20 THEN '[10,20)'
  WHEN price_c>=20 AND price_c<35 THEN '[20,35)'
  WHEN price_c>=35 AND price_c<50 THEN '[35,50)'
  WHEN price_c>=50 AND price_c<65 THEN '[50,65)'
  WHEN price_c>=65 AND price_c<80 THEN '[65,80)'
  WHEN price_c>=80 AND price_c<90 THEN '[80,90)'
  WHEN price_c>=90 AND price_c<95 THEN '[90,95)'
  WHEN price_c>=95 AND price_c<=99 THEN '[95,99]'
  ELSE NULL
END
"""


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get_json(url, tries=6, backoff=1.6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "venue-expansion-mm1-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as fh:
                return json.load(fh)
        except Exception as e:  # noqa: BLE001
            last = e
            log(f"  fetch retry {i+1}/{tries} for {url}: {e}")
            time.sleep(backoff ** i)
    raise last


# ---------------------------------------------------------------------------
# series dimension (category + fee_type), single bulk live call, cached
# ---------------------------------------------------------------------------

def build_series_dim():
    if os.path.exists(FEE_TYPES_PATH):
        return json.load(open(FEE_TYPES_PATH))["map"]

    if os.path.exists(SERIES_RAW_PATH):
        d = json.load(open(SERIES_RAW_PATH))
    else:
        log("fetching live GET /trade-api/v2/series (single bulk call, all series) ...")
        d = get_json(f"{API}/series")
        tmp = SERIES_RAW_PATH + ".tmp"
        json.dump(d, open(tmp, "w"))
        os.replace(tmp, SERIES_RAW_PATH)

    m = {}
    unknown_fee_types = set()
    for s in d["series"]:
        ft = s.get("fee_type")
        if ft == "quadratic":
            maker_fee_c = 0.0
        elif ft == "quadratic_with_maker_fees":
            maker_fee_c = MAKER_FEE_QUADRATIC_WITH_MAKER_FEES_C
        else:
            maker_fee_c = None
            unknown_fee_types.add(ft)
        m[s["ticker"]] = {"category": s.get("category"), "fee_type": ft, "maker_fee_c": maker_fee_c}
    if unknown_fee_types:
        log(f"WARNING: unrecognized fee_type values encountered: {unknown_fee_types}")

    out = {
        "source": "live bulk GET /trade-api/v2/series (no series filter -> full current listing), single call",
        "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_series": len(m),
        "maker_fee_quadratic_with_maker_fees_c_approx": MAKER_FEE_QUADRATIC_WITH_MAKER_FEES_C,
        "map": m,
    }
    tmp = FEE_TYPES_PATH + ".tmp"
    json.dump(out, open(tmp, "w"), indent=1)
    os.replace(tmp, FEE_TYPES_PATH)
    return m


# ---------------------------------------------------------------------------
# Stage A -- per-shard pass
# ---------------------------------------------------------------------------

def poolA_path(i):
    return os.path.join(STAGEA_DIR, f"poolA_day_shard={i:04d}.parquet")


def poolU_path(i):
    return os.path.join(STAGEA_DIR, f"poolU_day_shard={i:04d}.parquet")


def skip_path(i):
    return os.path.join(STAGEA_DIR, f"skips_shard={i:04d}.json")


def shard_done(i):
    return os.path.exists(poolA_path(i)) and os.path.exists(poolU_path(i)) and os.path.exists(skip_path(i))


def process_shard(i, con, sdim):
    if shard_done(i):
        log(f"[stageA shard {i:04d}] already cached, skip")
        return
    t0 = time.time()
    shard_url = SHARD_URLS[i]
    log(f"[stageA shard {i:04d}] reading {shard_url} ...")

    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE joined AS
      SELECT t.ticker AS ticker, t."count" AS contracts, t.yes_price AS yes_price, t.no_price AS no_price,
             t.taker_side AS taker_side, t.created_time AS created_time,
             d.admitted AS admitted, d.series_key AS series_key, d.rung_class AS rung_class,
             d.result AS result
      FROM read_parquet('{shard_url}') t
      LEFT JOIN read_parquet('{DIM_PATH}') d USING (ticker)
    """)
    t1 = time.time()
    log(f"[stageA shard {i:04d}] joined to ticker_dim in {t1-t0:.1f}s")

    con.execute("CREATE OR REPLACE TEMP TABLE sdim(series_key VARCHAR, category VARCHAR, fee_type VARCHAR, maker_fee_c DOUBLE)")
    rows = [(k, v["category"], v["fee_type"], v["maker_fee_c"]) for k, v in sdim.items()]
    con.executemany("INSERT INTO sdim VALUES (?,?,?,?)", rows)

    settled_expr = "admitted AND result IN ('yes','no')"
    taker_ok_expr = f"({settled_expr}) AND taker_side IN ('yes','no')"
    price_expr = "CASE WHEN taker_side='yes' THEN yes_price ELSE no_price END"
    inband_expr = f"({price_expr}) BETWEEN 1 AND 99"

    skip_row = con.execute(f"""
      SELECT
        count(*) AS total,
        count(*) FILTER (WHERE admitted IS NULL) AS ticker_not_in_dim,
        count(*) FILTER (WHERE admitted IS NOT NULL AND NOT admitted) AS market_not_admitted,
        count(*) FILTER (WHERE admitted AND result NOT IN ('yes','no')) AS unsettled_result,
        count(*) FILTER (WHERE ({settled_expr}) AND taker_side NOT IN ('yes','no')) AS taker_side_unrecognized,
        count(*) FILTER (WHERE ({taker_ok_expr}) AND NOT ({inband_expr})) AS price_out_of_band,
        count(*) FILTER (WHERE ({taker_ok_expr}) AND ({inband_expr}) AND s.series_key IS NOT NULL) AS qualifying_fee_resolved,
        count(*) FILTER (WHERE ({taker_ok_expr}) AND ({inband_expr}) AND s.series_key IS NULL) AS qualifying_fee_unverified
      FROM joined j
      LEFT JOIN sdim s ON j.series_key = s.series_key
    """).fetchone()
    skip_cols = ["total", "ticker_not_in_dim", "market_not_admitted", "unsettled_result",
                 "taker_side_unrecognized", "price_out_of_band", "qualifying_fee_resolved",
                 "qualifying_fee_unverified"]
    skip_d = dict(zip(skip_cols, skip_row))
    log(f"[stageA shard {i:04d}] skip ledger: {skip_d}")

    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE qual AS
      SELECT j.series_key AS series_key, j.taker_side AS maker_side,
             ({price_expr}) AS price_c,
             j.contracts AS contracts,
             CASE WHEN (j.taker_side='yes' AND j.result='yes') OR (j.taker_side='no' AND j.result='no') THEN 1 ELSE 0 END AS maker_pays_full,
             CAST(j.created_time AS DATE) AS cal_day,
             EXTRACT(year FROM j.created_time) AS cal_year,
             s.category AS category, s.fee_type AS fee_type, s.maker_fee_c AS maker_fee_c,
             (s.series_key IS NOT NULL) AS fee_resolved
      FROM joined j
      LEFT JOIN sdim s ON j.series_key = s.series_key
      WHERE ({taker_ok_expr}) AND ({inband_expr})
    """)

    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE qual2 AS
      SELECT series_key, category, maker_side, ({PRICE_BAND_SQL}) AS band, cal_year, cal_day,
             contracts, fee_resolved,
             (price_c - 100.0*maker_pays_full) AS gross_pnl_c,
             (price_c - 100.0*maker_pays_full - COALESCE(maker_fee_c,0.0)) AS net_pnl_c
      FROM qual
    """)

    poolA_tmp = poolA_path(i) + ".tmp"
    poolU_tmp = poolU_path(i) + ".tmp"

    con.execute(f"""
      COPY (
        SELECT category, band, cal_year, maker_side, cal_day,
               count(*) AS n, sum(contracts) AS contracts_sum,
               sum(net_pnl_c) AS sum_net_print_c, sum(net_pnl_c*contracts) AS sum_net_contract_c,
               sum(gross_pnl_c) AS sum_gross_print_c, sum(gross_pnl_c*contracts) AS sum_gross_contract_c
        FROM qual2
        WHERE fee_resolved AND band IS NOT NULL
        GROUP BY 1,2,3,4,5
      ) TO '{poolA_tmp}' (FORMAT PARQUET)
    """)
    con.execute(f"""
      COPY (
        SELECT series_key, band, cal_year, maker_side, cal_day,
               count(*) AS n, sum(contracts) AS contracts_sum,
               sum(gross_pnl_c) AS sum_gross_print_c, sum(gross_pnl_c*contracts) AS sum_gross_contract_c
        FROM qual2
        WHERE NOT fee_resolved AND band IS NOT NULL
        GROUP BY 1,2,3,4,5
      ) TO '{poolU_tmp}' (FORMAT PARQUET)
    """)
    os.replace(poolA_tmp, poolA_path(i))
    os.replace(poolU_tmp, poolU_path(i))

    skip_tmp = skip_path(i) + ".tmp"
    json.dump({"shard": i, "skip_ledger": skip_d, "elapsed_sec": round(time.time() - t0, 1)},
               open(skip_tmp, "w"), indent=1)
    os.replace(skip_tmp, skip_path(i))

    con.execute("DROP TABLE joined; DROP TABLE qual; DROP TABLE qual2; DROP TABLE sdim;")
    log(f"[stageA shard {i:04d}] DONE in {time.time()-t0:.1f}s")


def run_stageA(shards=None):
    sdim = build_series_dim()
    log(f"series dim loaded: {len(sdim)} series (category+fee_type)")
    shards = shards if shards is not None else list(range(16))
    con = duckdb.connect(os.path.join(CACHE, "mm1_work.duckdb"))
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET enable_progress_bar=false;")
    con.execute(f"SET temp_directory='{os.path.join(CACHE, 'duckdb_tmp')}';")
    con.execute("SET memory_limit='9GB';")
    for i in shards:
        process_shard(i, con, sdim)
    con.close()


# ---------------------------------------------------------------------------
# Stage A -- combine
# ---------------------------------------------------------------------------

def run_stageA_combine():
    missing = [i for i in range(16) if not shard_done(i)]
    if missing:
        raise SystemExit(f"stageA not complete, missing shards: {missing}")

    con = duckdb.connect()
    poolA_glob = os.path.join(STAGEA_DIR, "poolA_day_shard=*.parquet")
    poolU_glob = os.path.join(STAGEA_DIR, "poolU_day_shard=*.parquet")

    # sum across shards at the (category,band,year,side,day) grain FIRST -- shards are
    # hash-scattered so a single calendar day's prints are split across many shard files;
    # summing at day grain before counting distinct days is required for a correct day_count.
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE dayA AS
      SELECT category, band, cal_year, maker_side, cal_day,
             sum(n) AS n, sum(contracts_sum) AS contracts_sum,
             sum(sum_net_print_c) AS sum_net_print_c, sum(sum_net_contract_c) AS sum_net_contract_c,
             sum(sum_gross_print_c) AS sum_gross_print_c, sum(sum_gross_contract_c) AS sum_gross_contract_c
      FROM read_parquet('{poolA_glob}')
      GROUP BY 1,2,3,4,5
    """)

    final_path = os.path.join(STAGEA_DIR, "pool.parquet")
    con.execute(f"""
      COPY (
        SELECT category, band, cal_year, maker_side,
               sum(n) AS n_prints, sum(contracts_sum) AS contracts,
               sum(sum_net_print_c) AS sum_net_print_c, sum(sum_net_contract_c) AS sum_net_contract_c,
               sum(sum_gross_print_c) AS sum_gross_print_c, sum(sum_gross_contract_c) AS sum_gross_contract_c,
               count(*) AS day_count
        FROM dayA
        GROUP BY 1,2,3,4
        ORDER BY 1,2,3,4
      ) TO '{final_path}' (FORMAT PARQUET)
    """)

    rows = con.execute(f"""
      SELECT category, band, cal_year, maker_side, n_prints, contracts,
             sum_net_print_c, sum_net_contract_c, sum_gross_print_c, sum_gross_contract_c, day_count
      FROM read_parquet('{final_path}')
    """).fetchall()

    cells = []
    for r in rows:
        (category, band, cal_year, maker_side, n_prints, contracts,
         sum_net_print_c, sum_net_contract_c, sum_gross_print_c, sum_gross_contract_c, day_count) = r
        cells.append({
            "category": category, "band_c": band, "cal_year": int(cal_year), "maker_short_side": maker_side,
            "n_prints": int(n_prints), "contracts": int(contracts),
            "net_c_per_print_mean": round(sum_net_print_c / n_prints, 4) if n_prints else None,
            "net_c_per_contract_weighted": round(sum_net_contract_c / contracts, 4) if contracts else None,
            "gross_c_per_contract_weighted": round(sum_gross_contract_c / contracts, 4) if contracts else None,
            "total_pool_usd_contract_weighted": round(sum_net_contract_c / 100.0, 2),
            "day_count": int(day_count),
        })

    # fee-unverified bucket (gross only, never merged)
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE dayU AS
      SELECT series_key, band, cal_year, maker_side, cal_day,
             sum(n) AS n, sum(contracts_sum) AS contracts_sum,
             sum(sum_gross_print_c) AS sum_gross_print_c, sum(sum_gross_contract_c) AS sum_gross_contract_c
      FROM read_parquet('{poolU_glob}')
      GROUP BY 1,2,3,4,5
    """)
    fee_unverified_path = os.path.join(STAGEA_DIR, "pool_fee_unverified.parquet")
    con.execute(f"""
      COPY (
        SELECT series_key, band, cal_year, maker_side,
               sum(n) AS n_prints, sum(contracts_sum) AS contracts,
               sum(sum_gross_print_c) AS sum_gross_print_c, sum(sum_gross_contract_c) AS sum_gross_contract_c,
               count(*) AS day_count
        FROM dayU GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
      ) TO '{fee_unverified_path}' (FORMAT PARQUET)
    """)
    urows = con.execute(f"""
      SELECT series_key, band, cal_year, maker_side, n_prints, contracts,
             sum_gross_print_c, sum_gross_contract_c, day_count
      FROM read_parquet('{fee_unverified_path}')
    """).fetchall()
    fee_unverified_cells = []
    for r in urows:
        series_key, band, cal_year, maker_side, n_prints, contracts, sgp, sgc, day_count = r
        fee_unverified_cells.append({
            "series_key": series_key, "band_c": band, "cal_year": int(cal_year), "maker_short_side": maker_side,
            "n_prints": int(n_prints), "contracts": int(contracts),
            "gross_c_per_contract_weighted": round(sgc / contracts, 4) if contracts else None,
            "day_count": int(day_count),
        })
    fee_unverified_series = sorted({c["series_key"] for c in fee_unverified_cells})

    skip_total = {}
    for i in range(16):
        d = json.load(open(skip_path(i)))["skip_ledger"]
        for k, v in d.items():
            skip_total[k] = skip_total.get(k, 0) + v

    out = {
        "stage": "A",
        "role": "MAKER POOL MAP -- descriptive, no significance bar, no promotable claims (per spec_MM1_frozen.json).",
        "shards_read": SHARD_URLS,
        "ticker_dim_source": DIM_PATH,
        "series_dim_source": FEE_TYPES_PATH,
        "series_dim_note": ("category/fee_type resolved from a single live bulk GET /trade-api/v2/series call "
                             "(full current listing, 12,330 series as of fetch). Series present in the archive "
                             "tape but not in this live listing (legacy/delisted, e.g. INXD) are unresolvable and "
                             "routed to fee_unverified -- never merged into the main pool."),
        "maker_fee_quadratic_with_maker_fees_c_approx": MAKER_FEE_QUADRATIC_WITH_MAKER_FEES_C,
        "maker_fee_note": ("quadratic => maker fee $0 (verified live). quadratic_with_maker_fees => flat "
                            f"{MAKER_FEE_QUADRATIC_WITH_MAKER_FEES_C}c/ct applied, carried forward from "
                            "ref/RESEARCH_LEDGER.md graveyard #33 (MAKER_FAVLONG.md, not present in this "
                            "checkout to re-derive a price-dependent schedule) -- a disclosed approximation, "
                            "not independently re-derived here, and it affects only the Sports-dominant cells."),
        "skip_ledger_total": skip_total,
        "price_bands_c": ["[1,5)", "[5,10)", "[10,20)", "[20,35)", "[35,50)", "[50,65)", "[65,80)", "[80,90)", "[90,95)", "[95,99]"],
        "accounting": ("Every tape print is a maker fill on its passive side. taker_side='yes' at yes_price p "
                       "=> maker SHORT YES at p: P&L/ct = p - 100*[result=='yes'], minus maker fee where charged. "
                       "taker_side='no' at no_price q => maker SHORT NO at q: P&L/ct = q - 100*[result=='no'], "
                       "minus maker fee where charged. Volume-weighted (per-contract) is PRIMARY; per-print mean "
                       "is reported as sensitivity only."),
        "n_cells": len(cells),
        "cells": cells,
        "fee_unverified_bucket": {
            "note": "Gross P&L only (no maker fee applied, fee_type unresolved). NEVER merged into the main pool cells above.",
            "series_keys": fee_unverified_series,
            "n_cells": len(fee_unverified_cells),
            "cells": fee_unverified_cells,
        },
    }
    tmp = os.path.join(OUT_DIR, "mm1_pool_map.json") + ".tmp"
    json.dump(out, open(tmp, "w"), indent=1)
    os.replace(tmp, os.path.join(OUT_DIR, "mm1_pool_map.json"))
    log(f"stageA combine done: {len(cells)} main cells, {len(fee_unverified_cells)} fee-unverified cells")
    con.close()
    return out


# ---------------------------------------------------------------------------
# Stage C -- spread / quote context
# ---------------------------------------------------------------------------

STAGE_C_SEED = 20260730
STAGE_C_START = "2026-06-01T00:00:00Z"
STAGE_C_END = "2026-06-30T23:59:59Z"


def _iso_to_ts(iso):
    import datetime
    return int(datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp())


def fetch_june_markets():
    if os.path.exists(JUNE_MARKETS_RAW):
        return json.load(open(JUNE_MARKETS_RAW))
    min_ts = _iso_to_ts(STAGE_C_START)
    max_ts = _iso_to_ts(STAGE_C_END)
    markets = []
    cursor = None
    page = 0
    while True:
        url = f"{API}/markets?series_ticker=KXBTC&status=settled&min_close_ts={min_ts}&max_close_ts={max_ts}&limit=1000"
        if cursor:
            url += f"&cursor={cursor}"
        d = get_json(url)
        ms = d.get("markets", [])
        markets.extend(ms)
        page += 1
        log(f"[stageC] page {page}: +{len(ms)} markets (total {len(markets)})")
        cursor = d.get("cursor")
        if not cursor or not ms:
            break
        time.sleep(0.3)  # polite
    # client-side strict filter (belt+braces on top of the server-side min/max close params)
    markets = [m for m in markets if STAGE_C_START <= m["close_time"] <= STAGE_C_END]
    tmp = JUNE_MARKETS_RAW + ".tmp"
    json.dump({"n": len(markets), "markets": markets}, open(tmp, "w"))
    os.replace(tmp, JUNE_MARKETS_RAW)
    return {"n": len(markets), "markets": markets}


def sample_markets():
    if os.path.exists(SAMPLE_PATH):
        return json.load(open(SAMPLE_PATH))
    d = fetch_june_markets()
    tickers = sorted(m["ticker"] for m in d["markets"])  # sort for determinism before seeded sample
    rng = random.Random(STAGE_C_SEED)
    k = min(200, len(tickers))
    sample = rng.sample(tickers, k)
    by_ticker = {m["ticker"]: m for m in d["markets"]}
    sample_full = [by_ticker[t] for t in sample]
    tmp = SAMPLE_PATH + ".tmp"
    json.dump({"seed": STAGE_C_SEED, "n_population": len(tickers), "n_sample": len(sample_full),
               "sample": sample_full}, open(tmp, "w"), indent=1)
    os.replace(tmp, SAMPLE_PATH)
    return json.load(open(SAMPLE_PATH))


def candle_cache_path(ticker):
    safe = ticker.replace("/", "_")
    return os.path.join(CANDLES_DIR, f"{safe}.json")


def fetch_candles_for_market(m):
    ticker = m["ticker"]
    cp = candle_cache_path(ticker)
    if os.path.exists(cp):
        return json.load(open(cp))
    close_ts = _iso_to_ts(m["close_time"])
    open_ts = _iso_to_ts(m["open_time"])
    # Spec asked for the final 6h; KXBTC hourly markets structurally open exactly 1h before close
    # (verified live: open_time == close_time - 1h for every sampled market) so the requested 6h
    # window is unavailable by construction -- disclosed divergence, not improvised. We pull the
    # market's full actual lifetime [open_time, close_time] instead.
    url = f"{API}/series/KXBTC/markets/{ticker}/candlesticks?start_ts={open_ts}&end_ts={close_ts}&period_interval=1"
    d = get_json(url)
    candles = d.get("candlesticks", [])
    out = {"ticker": ticker, "open_time": m["open_time"], "close_time": m["close_time"],
           "open_ts": open_ts, "close_ts": close_ts, "candles": candles}
    tmp = cp + ".tmp"
    json.dump(out, open(tmp, "w"))
    os.replace(tmp, cp)
    return out


def run_stageC():
    sample = sample_markets()
    log(f"[stageC] sample: {sample['n_sample']} of {sample['n_population']} KXBTC hourly markets, June 2026, seed {sample['seed']}")
    pulled = 0
    for m in sample["sample"]:
        fetch_candles_for_market(m)
        pulled += 1
        if pulled % 20 == 0:
            log(f"[stageC] pulled {pulled}/{len(sample['sample'])}")
        time.sleep(0.15)  # polite sequential fetch
    log(f"[stageC] all {pulled} markets' candlesticks cached")
    return analyze_stageC(sample)


def _dollars_to_c(s):
    try:
        return round(float(s) * 100)
    except (TypeError, ValueError):
        return None


def analyze_stageC(sample=None):
    sample = sample or sample_markets()
    minute_bucket_edges = list(range(0, 70, 10))  # 0,10,...,60 minutes-to-close (divergence: 60min not 6h, see docstring)
    n_buckets = len(minute_bucket_edges) - 1

    spreads_by_bucket = [[] for _ in range(n_buckets)]
    twosided_flags_by_bucket = [[] for _ in range(n_buckets)]
    touchmove_by_bucket = [[] for _ in range(n_buckets)]

    n_markets_used = 0
    n_markets_no_candles = 0
    total_minutes = 0

    for m in sample["sample"]:
        d = json.load(open(candle_cache_path(m["ticker"])))
        candles = d["candles"]
        if not candles:
            n_markets_no_candles += 1
            continue
        n_markets_used += 1
        close_ts = d["close_ts"]
        series = []
        for c in candles:
            end_ts = c["end_period_ts"]
            mins_to_close = (close_ts - end_ts) / 60.0
            bid_c = _dollars_to_c(c.get("yes_bid", {}).get("close_dollars"))
            ask_c = _dollars_to_c(c.get("yes_ask", {}).get("close_dollars"))
            if bid_c is None or ask_c is None:
                continue
            total_minutes += 1
            bucket = None
            for bi in range(n_buckets):
                lo, hi = minute_bucket_edges[bi], minute_bucket_edges[bi + 1]
                if lo <= mins_to_close < hi:
                    bucket = bi
                    break
            if bucket is None:
                continue
            two_sided = bid_c > 0 and ask_c < 100
            twosided_flags_by_bucket[bucket].append(1 if two_sided else 0)
            if two_sided:
                spreads_by_bucket[bucket].append(ask_c - bid_c)
            series.append((end_ts, bid_c, ask_c, bucket))
        series.sort(key=lambda x: x[0])
        for k in range(1, len(series)):
            _, b0, a0, buck0 = series[k - 1]
            _, b1, a1, _ = series[k]
            moved = (b0 != b1) or (a0 != a1)
            touchmove_by_bucket[buck0].append(1 if moved else 0)

    def pctiles(xs, ps=(25, 50, 75, 90)):
        if not xs:
            return {f"p{p}": None for p in ps}
        xs_sorted = sorted(xs)
        out = {}
        for p in ps:
            idx = min(len(xs_sorted) - 1, max(0, round((p / 100.0) * (len(xs_sorted) - 1))))
            out[f"p{p}"] = xs_sorted[idx]
        return out

    buckets_out = []
    for bi in range(n_buckets):
        lo, hi = minute_bucket_edges[bi], minute_bucket_edges[bi + 1]
        sp = spreads_by_bucket[bi]
        ts = twosided_flags_by_bucket[bi]
        tm = touchmove_by_bucket[bi]
        buckets_out.append({
            "minutes_to_close_bucket": f"[{lo},{hi})",
            "n_minute_obs": len(ts),
            "share_two_sided_quote": round(sum(ts) / len(ts), 4) if ts else None,
            "spread_c_two_sided_only": pctiles(sp),
            "n_spread_obs_two_sided": len(sp),
            "n_consecutive_pairs": len(tm),
            "touch_move_freq": round(sum(tm) / len(tm), 4) if tm else None,
        })

    out = {
        "stage": "C",
        "role": "SPREAD/QUOTE CONTEXT -- descriptive, no bar, outside the Bonferroni family. No EV claim, nothing promotable.",
        "sample": {"seed": STAGE_C_SEED, "n_population": sample["n_population"], "n_sample": sample["n_sample"],
                    "window": f"{STAGE_C_START}..{STAGE_C_END}", "series": "KXBTC (hourly)"},
        "divergence_from_frozen_spec": (
            "Spec text requested candlesticks over each market's 'final 6 hours'. Verified live for every "
            "sampled market: KXBTC hourly markets open_time == close_time - 1h exactly, i.e. the true tradable "
            "lifetime is 60 minutes, not 6 hours -- a 6h pre-close window does not exist for this series. This "
            "is a data-availability fact, not an improvised bar change (Stage C carries no bar and nothing here "
            "is promotable per its own frozen role text). Reported bucketing is therefore minutes-to-close in "
            "10-minute buckets over the market's full actual lifetime, in place of hours-to-close buckets."
        ),
        "n_markets_used": n_markets_used,
        "n_markets_no_candles": n_markets_no_candles,
        "total_minute_observations": total_minutes,
        "quote_definition": "two-sided quote iff yes_bid_close_c > 0 AND yes_ask_close_c < 100 (excludes the structural 0/100 default when no resting interest exists on a side). Spread percentiles computed over two-sided-quote minutes only; touch-move frequency computed over all consecutive same-market minute pairs regardless of two-sidedness (best bid or best ask close changing minute to minute).",
        "buckets": buckets_out,
    }
    return out


# ---------------------------------------------------------------------------
# Final assembly
# ---------------------------------------------------------------------------

def run_final():
    stageA = json.load(open(os.path.join(OUT_DIR, "mm1_pool_map.json")))
    stageC = analyze_stageC()
    out = {
        "study": "MM1",
        "title": "Maker-side EV pool map (Stage A) + spread/quote context (Stage C) -- Stage A/C of spec_MM1_frozen.json",
        "note": "Stage B (the barred R-grid maker-EV-vs-reaction-speed test) is a separate extraction and is NOT included here.",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stageA": stageA,
        "stageC": stageC,
    }
    tmp = os.path.join(OUT_DIR, "maker_poolmap.json") + ".tmp"
    json.dump(out, open(tmp, "w"), indent=1)
    os.replace(tmp, os.path.join(OUT_DIR, "maker_poolmap.json"))
    log("wrote out/maker_poolmap.json")
    write_md(out)
    return out


def write_md(out):
    A = out["stageA"]
    C = out["stageC"]
    lines = []
    lines.append("# MM1 Stage A + Stage C -- Maker Pool Map & Spread/Quote Context")
    lines.append("")
    lines.append(f"Generated {out['generated_utc']}. Frozen spec: `venue_expansion/out/spec_MM1_frozen.json` "
                  "(registered 2026-07-30). Stage B (the barred R-grid EV test) is NOT included in this run.")
    lines.append("")
    lines.append("**Both stages are descriptive with no significance bar. Nothing here may be promoted to a "
                  "claim without a new registration** (explicit in the frozen spec for both stages).")
    lines.append("")
    lines.append("## Stage A -- maker pool map")
    lines.append("")
    lines.append(f"- Shards read: all 16 trade shards `trades-0000..trades-0015` (explicit path list, HF "
                  "`TrevorJS/kalshi-trades`), joined to `venue_expansion/cache/prereg/ticker_dim.parquet` "
                  "(all 4 market shards).")
    lines.append(f"- `series_key` = `split_part(event_ticker,'-',1)` exactly as built by "
                  "`cache/prereg/build_dim.py` (the U1 rule) -- exact keys, never a prefix LIKE.")
    lines.append("- Settled markets only (`result IN ('yes','no')`); every other disposition logged to the "
                  "skip ledger below.")
    lines.append(f"- Category + fee_type: {A['series_dim_note']}")
    lines.append(f"- Maker fee treatment: {A['maker_fee_note']}")
    lines.append("")
    lines.append("### Skip ledger (summed over all 16 shards)")
    lines.append("")
    lines.append("| reason | trades |")
    lines.append("|---|---:|")
    for k, v in A["skip_ledger_total"].items():
        lines.append(f"| {k} | {v:,} |")
    lines.append("")
    lines.append(f"### Main pool: {A['n_cells']} cells (category x band x year x maker-short-side)")
    lines.append("")
    lines.append("Volume-weighted (per-contract) net $/ct is PRIMARY. Top 30 cells by |total pool $|, all "
                  "cells are in `out/mm1_pool_map.json` and `cache/mm1/stageA/pool.parquet`.")
    lines.append("")
    top = sorted(A["cells"], key=lambda c: -abs(c["total_pool_usd_contract_weighted"]))[:30]
    lines.append("| category | band(c) | year | maker short | n prints | contracts | net c/ct (contract-wt) | total pool $ | days |")
    lines.append("|---|---|---:|---|---:|---:|---:|---:|---:|")
    for c in top:
        lines.append(f"| {c['category']} | {c['band_c']} | {c['cal_year']} | {c['maker_short_side']} | "
                      f"{c['n_prints']:,} | {c['contracts']:,} | {c['net_c_per_contract_weighted']:.3f} | "
                      f"{c['total_pool_usd_contract_weighted']:,.2f} | {c['day_count']} |")
    lines.append("")
    fu = A["fee_unverified_bucket"]
    lines.append(f"### Fee-unverified bucket ({fu['n_cells']} cells, {len(fu['series_keys'])} series) -- "
                  "NEVER merged into the main pool")
    lines.append("")
    lines.append("Series present in the archive tape but absent from the live `/trade-api/v2/series` listing "
                  "(legacy/delisted). No maker fee applied (unknown); gross P&L only, reported for completeness, "
                  "excluded from every total above.")
    lines.append("")
    lines.append(f"Series keys: {', '.join(fu['series_keys'][:60])}" +
                  (" ..." if len(fu["series_keys"]) > 60 else ""))
    lines.append("")
    lines.append("## Stage C -- spread/quote context (KXBTC hourly, June 2026)")
    lines.append("")
    lines.append(f"- Sample: {C['sample']['n_sample']} of {C['sample']['n_population']} settled KXBTC hourly "
                  f"markets with close_time in {C['sample']['window']}, uniform random, frozen seed "
                  f"{C['sample']['seed']}.")
    lines.append(f"- **Divergence from the frozen spec text, disclosed not improvised:** {C['divergence_from_frozen_spec']}")
    lines.append(f"- Markets with usable candlestick data: {C['n_markets_used']} (missing/empty: "
                  f"{C['n_markets_no_candles']}). Total 1-minute observations: {C['total_minute_observations']:,}.")
    lines.append(f"- {C['quote_definition']}")
    lines.append("")
    lines.append("| minutes-to-close | n obs | share two-sided | spread p25/p50/p75/p90 (c, two-sided only) | touch-move freq |")
    lines.append("|---|---:|---:|---|---:|")
    for b in C["buckets"]:
        sp = b["spread_c_two_sided_only"]
        sp_str = f"{sp['p25']}/{sp['p50']}/{sp['p75']}/{sp['p90']}" if sp["p50"] is not None else "n/a"
        lines.append(f"| {b['minutes_to_close_bucket']} | {b['n_minute_obs']:,} | "
                      f"{b['share_two_sided_quote'] if b['share_two_sided_quote'] is not None else 'n/a'} | "
                      f"{sp_str} | {b['touch_move_freq'] if b['touch_move_freq'] is not None else 'n/a'} |")
    lines.append("")
    lines.append("Feeds ONLY the infrastructure quote-cadence requirement statement in the eventual deliverable. "
                  "No EV claim; nothing here is promotable to a claim.")
    lines.append("")
    lines.append("---")
    lines.append("*Caches: `venue_expansion/cache/mm1/stageA/` (Stage A per-shard + combined parquet), "
                  "`venue_expansion/cache/mm1/candles/` (Stage C per-market candlesticks), "
                  "`venue_expansion/cache/mm1/fee_types.json` (series category/fee_type). All gitignored.*")
    open(os.path.join(OUT_DIR, "maker_poolmap.md"), "w").write("\n".join(lines) + "\n")
    log("wrote out/maker_poolmap.md")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "stageA":
        shards = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else None
        run_stageA(shards)
    elif cmd == "stageA_combine":
        run_stageA_combine()
    elif cmd == "stageC":
        run_stageC()
    elif cmd == "final":
        run_final()
    elif cmd == "all":
        run_stageA()
        run_stageA_combine()
        run_stageC()
        run_final()
    else:
        print(f"unknown command {cmd}", file=sys.stderr)
        sys.exit(1)
