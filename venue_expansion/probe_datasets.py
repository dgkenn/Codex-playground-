"""probe_datasets.py -- verify the public Kalshi/Polymarket historical datasets we rely on.

Checks, with real remote queries (no downloads -- DuckDB parquet metadata + predicate pushdown):
  - true shard count and row count of TrevorJS/kalshi-trades  (kx_history.py hardcodes 9 trade
    shards; the archive has 10, so the 10th is silently invisible to every study)
  - real coverage window (the dataset card's "Jan 2026" vs what the data actually holds)
  - whether shards are time-partitioned or hash-scattered (decides whether sampling K of N shards
    is a TIME SLICE or a RANDOM SAMPLE of trades -- these are not interchangeable in a backtest)
  - schemas
  - thomaswmitch/kalshi-prediction-markets-betting as a cross-check source

Run: python venue_expansion/probe_datasets.py    (writes venue_expansion/out/datasets_probe.json)
"""
from __future__ import annotations

import json
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "datasets_probe.json")
TREVOR = "https://huggingface.co/datasets/TrevorJS/kalshi-trades/resolve/main"
THOMAS = "https://huggingface.co/datasets/thomaswmitch/kalshi-prediction-markets-betting/resolve/main"

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
res = {}


def one(sql, label):
    try:
        r = con.execute(sql).fetchone()
        print(f"  {label}: {r}")
        return r
    except Exception as e:
        print(f"  {label}: ERR {str(e)[:110]}")
        return None


print("== TrevorJS/kalshi-trades: per-shard census (HTTP globs 404 -> must enumerate) ==")
shards = {}
for i in range(12):  # probe past the known end to detect growth
    r = one(f"SELECT count(*), min(created_time), max(created_time) "
            f"FROM read_parquet('{TREVOR}/trades-{i:04d}.parquet')", f"trades-{i:04d}")
    if r:
        shards[f"trades-{i:04d}"] = {"rows": r[0], "min": str(r[1]), "max": str(r[2])}
    else:
        break
res["trevor_trade_shards"] = shards
res["trevor_trade_shard_count"] = len(shards)
res["trevor_trade_rows_total"] = sum(v["rows"] for v in shards.values())

mk = {}
for i in range(6):
    r = one(f"SELECT count(*) FROM read_parquet('{TREVOR}/markets-{i:04d}.parquet')", f"markets-{i:04d}")
    if r:
        mk[f"markets-{i:04d}"] = r[0]
    else:
        break
res["trevor_market_shards"] = mk
res["trevor_market_rows_total"] = sum(mk.values())

print("\n== schemas ==")
for name, path in (("trades", f"{TREVOR}/trades-0000.parquet"), ("markets", f"{TREVOR}/markets-0000.parquet")):
    try:
        cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}') LIMIT 1").fetchall()
        res[f"schema_{name}"] = [(c[0], c[1]) for c in cols]
        print(f"  {name}: " + ", ".join(f"{c[0]}:{c[1]}" for c in cols))
    except Exception as e:
        print(f"  {name}: ERR {str(e)[:110]}")

print("\n== are shards time-partitioned or hash-scattered? (same ticker across shards = scattered) ==")
try:
    tkr = con.execute(f"SELECT ticker FROM read_parquet('{TREVOR}/trades-0000.parquet') LIMIT 1").fetchone()[0]
    hits = []
    for i in range(len(shards)):
        n = con.execute(f"SELECT count(*) FROM read_parquet('{TREVOR}/trades-{i:04d}.parquet') "
                        f"WHERE ticker = ?", [tkr]).fetchone()[0]
        hits.append(n)
    print(f"  ticker {tkr} trade counts per shard: {hits}")
    res["partition_probe"] = {"ticker": tkr, "per_shard_counts": hits,
                              "scattered": sum(1 for h in hits if h > 0) > 1}
    print("  -> " + ("HASH-SCATTERED: one market's trades span many shards; sampling K of N shards is a "
                     "RANDOM SUBSAMPLE of each market's trades, NOT a time slice"
                     if res["partition_probe"]["scattered"] else
                     "shard-local: this market's trades live in one shard"))
except Exception as e:
    print(f"  ERR {str(e)[:150]}")

print("\n== thomaswmitch/kalshi-prediction-markets-betting ==")
for i in range(2):
    r = one(f"SELECT count(*) FROM read_parquet('{THOMAS}/data/train-{i:05d}-of-00002.parquet')",
            f"train-{i:05d}")
    if r:
        res.setdefault("thomas_rows", []).append(r[0])
try:
    cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{THOMAS}/data/train-00000-of-00002.parquet') "
                       f"LIMIT 1").fetchall()
    res["schema_thomas"] = [(c[0], c[1]) for c in cols]
    print("  schema: " + ", ".join(f"{c[0]}:{c[1]}" for c in cols))
except Exception as e:
    print(f"  schema ERR {str(e)[:110]}")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w"), indent=1, default=str)
print(f"\nwrote {OUT}")
