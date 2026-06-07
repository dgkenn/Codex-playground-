"""Fetch trade prints for the DOWN tokens (for delta-neutral overround/vig capture)."""
import os, pandas as pd, pmxt_archive as arch
from datetime import datetime, timezone
dmap = pd.read_parquet("down_map.parquet")
ids = dmap["down_asset"].astype(str).tolist()
con = arch.connect()
keys = arch.hour_keys(datetime(2026,4,14,tzinfo=timezone.utc), datetime(2026,4,17,tzinfo=timezone.utc))
os.makedirs("data_downtr", exist_ok=True)
tot=0
for k in keys:
    n = arch.fetch_trades_hour_to_parquet(con, k, ids, f"data_downtr/{k}.parquet")
    tot += max(n,0)
con.execute("COPY (SELECT timestamp,asset_id,CAST(price AS DOUBLE) price,CAST(size AS DOUBLE) size,side FROM read_parquet('data_downtr/*.parquet')) TO 'down_trades.parquet' (FORMAT PARQUET)")
print("wrote down_trades.parquet:", con.execute("SELECT count(*) FROM read_parquet('down_trades.parquet')").fetchone()[0])
