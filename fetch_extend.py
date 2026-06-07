"""Extend the 2-sided maker dataset: discover BTC 15m up+down tokens + resolution
for a longer range, fetch up+down trades, to firm the bookmaker edge's t-stat."""
import json, os, sys, pandas as pd, requests
from datetime import datetime, timezone
import pmxt_archive as arch
G="https://gamma-api.polymarket.com"; WIN=900
start=datetime(2026,4,17,tzinfo=timezone.utc); end=datetime(2026,4,27,tzinfo=timezone.utc)
t0,t1=int(start.timestamp()),int(end.timestamp())
sess=requests.Session(); rows=[]
for ts in range(t0-(t0%WIN),t1,WIN):
    try: ev=sess.get(G+"/events",params={"slug":f"btc-updown-15m-{ts}"},timeout=20).json()
    except: ev=None
    if not ev: continue
    m=ev[0]["markets"][0]; toks=json.loads(m["clobTokenIds"]); pr=json.loads(m.get("outcomePrices") or "[]")
    rup=(1 if float(pr[0])>0.5 else 0) if (m.get("closed") and pr) else None
    if rup is None: continue
    rows.append({"window_start":ts,"window_end":ts+WIN,"up_asset":str(toks[0]),"down_asset":str(toks[1]),"resolved_up":rup})
w=pd.DataFrame(rows); w.to_parquet("ext_windows.parquet",index=False)
print(f"discovered {len(w)} resolved windows",flush=True)
con=arch.connect(); keys=arch.hour_keys(start,end)
for side,col,pdir,out in [("up","up_asset","data_uptr_ext","up_trades_ext.parquet"),("down","down_asset","data_dntr_ext","down_trades_ext.parquet")]:
    os.makedirs(pdir,exist_ok=True); ids=w[col].tolist(); tot=0
    for k in keys:
        n=arch.fetch_trades_hour_to_parquet(con,k,ids,f"{pdir}/{k}.parquet"); tot+=max(n,0)
    con.execute(f"COPY (SELECT timestamp,asset_id,CAST(price AS DOUBLE) price,CAST(size AS DOUBLE) size,side FROM read_parquet('{pdir}/*.parquet')) TO '{out}' (FORMAT PARQUET)")
    print(f"{side}: wrote {out} ({tot} trades)",flush=True)
