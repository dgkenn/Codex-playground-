import os, duckdb, pandas as pd, collections
from datetime import datetime, timedelta, timezone
from pmxt_archive import URL
os.makedirs("alt_tr_parts",exist_ok=True); os.makedirs("alt_dp_parts",exist_ok=True)
aw=pd.read_parquet("alt_windows.parquet"); aw["asset_id"]=aw.asset_id.astype(str)
upmeta=dict(zip(aw.asset_id, zip(aw.coin, aw.window_start, aw.window_end, aw.resolved_up)))
con=duckdb.connect(); con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET enable_progress_bar=false; SET preserve_insertion_order=false; SET memory_limit='8GB'; SET threads=4;")
s=datetime(2026,4,14,0,tzinfo=timezone.utc); e=datetime(2026,4,14,11,tzinfo=timezone.utc)
h=s; pairs=[]
while h<=e:
    hk=h.strftime("%Y-%m-%dT%H"); h0=int(h.timestamp()); url=URL.format(h=hk)
    ups=aw[(aw.window_start>=h0)&(aw.window_start<h0+3600)].asset_id.tolist()
    if not ups: print(hk,"no tokens"); h+=timedelta(hours=1); continue
    ids=",".join("'"+a+"'" for a in ups)
    mk=con.execute(f"SELECT DISTINCT CAST(market AS VARCHAR) m, asset_id FROM read_parquet('{url}') WHERE asset_id IN ({ids})").fetchall()
    ms=set(m for m,a in mk); mlist=",".join("'"+m+"'" for m in ms)
    allpairs=con.execute(f"SELECT DISTINCT CAST(market AS VARCHAR) m, asset_id FROM read_parquet('{url}') WHERE CAST(market AS VARCHAR) IN ({mlist})").fetchall()
    bym=collections.defaultdict(set)
    for m,a in allpairs: bym[m].add(str(a))
    toks=[]
    for m,a in mk:
        a=str(a); co,ws,we,ru=upmeta[a]; toks.append(a); toks.append("X")
        for t in bym[m]:
            is_up = (t==a); pairs.append((m,t,co,is_up,ws,we,ru)); toks.append(t)
    toks=list(set(t for t in toks if t!="X"))
    tids=",".join("'"+t+"'" for t in toks)
    tp=f"alt_tr_parts/tr_{hk}.parquet"; dp=f"alt_dp_parts/dp_{hk}.parquet"
    if not os.path.exists(tp):
        con.execute(f"COPY (SELECT timestamp,asset_id,CAST(price AS DOUBLE) price,CAST(size AS DOUBLE) size,side FROM read_parquet('{url}') WHERE asset_id IN ({tids}) AND event_type='last_trade_price' AND price IS NOT NULL) TO '{tp}' (FORMAT PARQUET);")
    if not os.path.exists(dp):
        con.execute(f"COPY (SELECT timestamp,asset_id,CAST(best_bid AS DOUBLE) best_bid,CAST(best_ask AS DOUBLE) best_ask,CAST(price AS DOUBLE) price,CAST(size AS DOUBLE) size,side FROM read_parquet('{url}') WHERE asset_id IN ({tids}) AND event_type='price_change' AND (price=best_bid OR price=best_ask)) TO '{dp}' (FORMAT PARQUET);")
    print(hk,"ok",len(toks),"tokens",flush=True); h+=timedelta(hours=1)
pd.DataFrame(pairs,columns=["market","asset_id","coin","is_up","window_start","window_end","resolved_up"]).drop_duplicates("asset_id").to_parquet("alt_pairs.parquet")
print("DONE pairs:",len(set(p[1] for p in pairs)))
