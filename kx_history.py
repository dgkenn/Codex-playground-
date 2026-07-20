#!/usr/bin/env python3
"""kx_history.py -- query the external Kalshi historical trade tape WITHOUT the API's ~1-2-events/series wall.

The public Kalshi API truncates historical market/trade data (confirmed by the 2026-07-20 illiquid-markets
funnel), which blocked backtesting the low-attention long tail. This module reads a free, MIT/CC-BY external
archive of the FULL settled history via DuckDB predicate-pushdown over remote parquet -- so a backtest pulls
only the columns/rows for the series it needs, never the whole 36 GiB dump (disk here is a fixed allowance).

Source (verified 2026-07-20, queryable, settlement-truth present):
  HF  TrevorJS/kalshi-trades   -- 172M trades, markets-*.parquet + trades-*.parquet, Jun2021-Jan2026, CC-BY-4.0
  (cross-check GH Jon-Becker/prediction-market-analysis -- 72M trades, MIT, same universe)

MARKETS cols: ticker,event_ticker,market_type,title,yes_sub_title,no_sub_title,status,yes_bid,yes_ask,
              no_bid,no_ask,last_price,volume,volume_24h,open_interest,result,created_time,open_time,close_time
TRADES  cols: trade_id,ticker,count,yes_price,no_price,taker_side,created_time

READ-ONLY analysis tool. No orders, no repo trading-path import. Requires `pip install duckdb`.

Usage:
  python kx_history.py schema                         # print both schemas
  python kx_history.py series                         # long-tail census: series x n_markets x median volume
  python kx_history.py market KXHIGHDEN-24JUL04-T95   # one market's trades + settlement
  # or import: from kx_history import q, MARKETS, TRADES ; q("SELECT ... FROM read_parquet(MARKETS(0)) ...")
"""
import sys

BASE = "https://huggingface.co/datasets/TrevorJS/kalshi-trades/resolve/main"
N_MARKET_SHARDS = 4   # markets-0000..0003 as of 2026-07-20; bump if the archive grows
N_TRADE_SHARDS = 9    # trades-0000..0008

def MARKETS(shard="*"):
    return f"{BASE}/markets-{'*' if shard=='*' else f'{int(shard):04d}'}.parquet"

def TRADES(shard="*"):
    return f"{BASE}/trades-{'*' if shard=='*' else f'{int(shard):04d}'}.parquet"

def _con():
    import duckdb
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; SET enable_progress_bar=false;")
    return c

def q(sql, con=None):
    """Run SQL and return list-of-tuples. Reuse a passed con across calls to amortize httpfs setup."""
    return (con or _con()).execute(sql).fetchall()

def _print_rows(rows, headers=None):
    if headers:
        print(" | ".join(headers))
    for r in rows:
        print(" | ".join(str(x) for x in r))

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "schema"
    con = _con()
    if cmd == "schema":
        for name, path in [("MARKETS", MARKETS(0)), ("TRADES", TRADES(0))]:
            cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}') LIMIT 1").fetchall()
            print(f"{name}: " + ", ".join(c[0] for c in cols))
    elif cmd == "series":
        # long-tail census on ONE shard (fast, representative). Whole-archive: swap MARKETS(0)->MARKETS('*').
        rows = con.execute(f"""
            SELECT regexp_extract(ticker,'^[A-Z]+',0) AS series, count(*) n,
                   round(median(volume)) med_vol,
                   count(*) FILTER (WHERE volume BETWEEN 1 AND 500) semi_thin
            FROM read_parquet('{MARKETS(0)}') GROUP BY 1 ORDER BY n DESC LIMIT 40
        """).fetchall()
        _print_rows(rows, ["series", "n_markets", "median_vol", "semi_thin(1-500)"])
    elif cmd == "market":
        tkr = sys.argv[2]
        m = con.execute(f"SELECT ticker,title,status,result,volume,open_interest,close_time "
                        f"FROM read_parquet('{MARKETS()}') WHERE ticker=? LIMIT 1", [tkr]).fetchall()
        _print_rows(m, ["ticker", "title", "status", "result", "volume", "OI", "close_time"])
        t = con.execute(f"SELECT created_time,taker_side,yes_price,no_price,count "
                        f"FROM read_parquet('{TRADES()}') WHERE ticker=? ORDER BY created_time LIMIT 50", [tkr]).fetchall()
        print(f"\n{len(t)} trades (first 50):")
        _print_rows(t, ["time", "taker_side", "yes_c", "no_c", "count"])
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
