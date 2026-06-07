import os, sys, duckdb, pandas as pd
from datetime import datetime, timedelta, timezone
from pmxt_archive import URL
OUT="alt_depth_parts"; os.makedirs(OUT,exist_ok=True)
aw=pd.read_parquet("alt_windows.parquet")
con=duckdb.connect(); con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET enable_progress_bar=false; SET preserve_insertion_order=false; SET memory_limit='8GB'; SET threads=4;")
s=datetime(2026,4,14,0,tzinfo=timezone.utc); e=datetime(2026,4,14,11,tzinfo=timezone.utc)
h=s; tot=0
while h<=e:
    hk=h.strftime("%Y-%m-%dT%H"); h0=int(h.timestamp())
    toks=aw[(aw.window_start>=h0)&(aw.window_start<h0+3600)].asset_id.astype(str).tolist()
    op=f"{OUT}/ad_{hk}.parquet"
    if toks and not (os.path.exists(op) and os.path.getsize(op)>0):
        ids=",".join("'"+a+"'" for a in toks)
        q=f"""COPY (SELECT timestamp, asset_id, CAST(best_bid AS DOUBLE) best_bid, CAST(best_ask AS DOUBLE) best_ask,
              CAST(price AS DOUBLE) price, CAST(size AS DOUBLE) size, side FROM read_parquet('{URL.format(h=hk)}')
              WHERE asset_id IN ({ids}) AND event_type='price_change' AND (price=best_bid OR price=best_ask)) TO '{op}' (FORMAT PARQUET);"""
        try: con.execute(q)
        except Exception as ex: print("warn",hk,str(ex)[:80])
    if os.path.exists(op): tot+=con.execute(f"SELECT count(*) FROM read_parquet('{op}')").fetchone()[0]
    print(hk,"done",flush=True); h+=timedelta(hours=1)
print("DONE",tot)
