"""reopen_check.py -- which graveyard kills were DATA WALLS rather than disproofs?

Eight entries in RESEARCH_LEDGER's graveyard were not refuted; they ran out of sample:

  #22 illiquid r1s1  KXFEDMENTION / KXHANNITYMENTION -- "collapses to 1 retrievable event ...
                     older events return `markets: []`"          (n=16 vs >=30 floor)
  #24 illiquid r1s3  KXJOBLESSCLAIMS relist -- "/events lists 47 settled events but 37 return
                     `markets: []`; only 10 servable"            (10 Thursdays vs >=15)
  #26 stacked r1s2   KXJOBLESSCLAIMS AR(1)+MA -- "10 of 28 TEST weeks servable
                     (~10-week retention wall)"                  (vs >=60-week gate)
  #29 stacked r2s2   macro-surprise pass-through                 (~31 events vs >=40)
  #3/#5/#9           directional SPECs 1/3/7 on KXHIGH*          (n=17/84 vs 200/300 floors)

EVERY one of those quoted reasons is a LIVE-API retention wall -- Kalshi's /events endpoint stops
serving markets for older events. The HF parquet archive has no such wall: it is a static dump of
17.5M markets back to 2021-06. If these series are present there with real history, the walls were
an artifact of the data source, not a property of the market, and the studies are reopenable at
genuine n.

Compounding this: kx_history.py reads 9 of the archive's 16 trade shards (see DATA_SOURCES.md), so
even the studies that DID use the archive ran on ~56% of the tape.

This script counts, per series, how many settled markets and distinct event-days the archive holds,
and compares to the n the kill reports actually achieved.

Read-only. Public parquet over HTTPS, predicate-pushdown (no bulk download).
Run: python venue_expansion/reopen_check.py
"""
from __future__ import annotations

import json
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "reopen_check.json")
B = "https://huggingface.co/datasets/TrevorJS/kalshi-trades/resolve/main"
MARKETS = [f"'{B}/markets-{i:04d}.parquet'" for i in range(4)]

# series -> (what the kill achieved, what the kill needed)
TARGETS = {
    "KXFEDMENTION":     ("#22 illiquid r1s1", "1 retrievable event (live API)", "n>=30 / >=8 event-days"),
    "KXHANNITYMENTION": ("#22 illiquid r1s1", "2 retrievable events (live API)", "n>=30 / >=8 event-days"),
    "KXJOBLESSCLAIMS":  ("#24 / #26", "10 servable Thursdays / 10 of 28 weeks", ">=15 Thursdays / >=60 weeks"),
    "KXHIGH":           ("#3/#5/#9 directional", "n=17 / n=84 entries", "n>=200 / n>=300"),
    "KXCPI":            ("#29 macro-surprise", "~31 TEST events", ">=40 events, >=3 families"),
    "KXPAYROLL":        ("#29 macro-surprise", "~31 TEST events", ">=40 events, >=3 families"),
}

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
src = "read_parquet([" + ",".join(MARKETS) + "])"

print("Counting archive coverage per series (settled markets, distinct events, date span)\n")
print(f"{'series':<20s} {'markets':>9s} {'settled':>9s} {'events':>8s} {'first':>12s} {'last':>12s}")
print("-" * 78)

results = {}
for series, (entry, achieved, needed) in TARGETS.items():
    try:
        r = con.execute(f"""
            SELECT count(*)                                   AS n_markets,
                   count(*) FILTER (WHERE result IN ('yes','no')) AS n_settled,
                   count(DISTINCT event_ticker)               AS n_events,
                   min(close_time)::DATE                      AS first_day,
                   max(close_time)::DATE                      AS last_day
            FROM {src}
            WHERE ticker LIKE '{series}%'
        """).fetchone()
        results[series] = {"kill_entry": entry, "kill_achieved": achieved, "kill_needed": needed,
                           "archive_markets": r[0], "archive_settled": r[1],
                           "archive_events": r[2],
                           "first_day": str(r[3]), "last_day": str(r[4])}
        print(f"{series:<20s} {r[0]:>9,} {r[1]:>9,} {r[2]:>8,} {str(r[3]):>12s} {str(r[4]):>12s}")
    except Exception as e:
        results[series] = {"error": str(e)[:200]}
        print(f"{series:<20s} ERR {str(e)[:60]}")

print("\n" + "=" * 78)
print("VERDICT PER KILL (archive events vs what the kill could reach on the live API)")
print("=" * 78)
for s, v in results.items():
    if "error" in v:
        continue
    print(f"\n{s}  [{v['kill_entry']}]")
    print(f"   kill reached : {v['kill_achieved']}")
    print(f"   kill needed  : {v['kill_needed']}")
    print(f"   ARCHIVE HAS  : {v['archive_events']:,} distinct events, {v['archive_settled']:,} settled markets, "
          f"{v['first_day']} .. {v['last_day']}")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(results, open(OUT, "w"), indent=1)
print(f"\nwrote {OUT}")
