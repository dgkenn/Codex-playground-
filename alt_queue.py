import glob, numpy as np, pandas as pd, queue_sim as Q

def load_alt_depth():
    df=pd.concat([pd.read_parquet(f) for f in [f for f in glob.glob("alt_dp_parts/dp_*.parquet") if __import__("os").path.getsize(f)>0]],ignore_index=True)
    df["ts_ms"]=pd.to_datetime(df["timestamp"],utc=True).to_numpy().astype("datetime64[ms]").view("int64")
    df["asset_id"]=df.asset_id.astype(str)
    bidu=(df.side=="BUY")&(np.isclose(df.price,df.best_bid)); asku=(df.side=="SELL")&(np.isclose(df.price,df.best_ask))
    df["bid_size"]=np.where(bidu,df["size"],np.nan); df["ask_size"]=np.where(asku,df["size"],np.nan)
    df=df.sort_values(["asset_id","ts_ms"])
    for c in ["bid_size","ask_size","best_bid","best_ask"]: df[c]=df.groupby("asset_id")[c].ffill()
    out={}
    for a,g in df.groupby("asset_id"):
        out[a]=(g.ts_ms.to_numpy(),g.bid_size.to_numpy(),g.ask_size.to_numpy(),g.best_bid.to_numpy(),g.best_ask.to_numpy())
    return out

def load_alt_trades():
    pairs=pd.read_parquet("alt_pairs.parquet"); pairs["asset_id"]=pairs.asset_id.astype(str)
    tr=pd.concat([pd.read_parquet(f) for f in [f for f in glob.glob("alt_tr_parts/tr_*.parquet") if __import__("os").path.getsize(f)>0]],ignore_index=True)
    tr["asset_id"]=tr.asset_id.astype(str)
    tr=tr.merge(pairs,on="asset_id",how="inner")
    tr["tok"]=np.where(tr.is_up,"U","D"); tr["win"]=tr.window_start; tr["res"]=tr.resolved_up; tr["wend"]=tr.window_end
    tr["t_ms"]=pd.to_datetime(tr["timestamp"],utc=True).to_numpy().astype("datetime64[ms]").view("int64")
    return tr.dropna(subset=["res"]).sort_values(["coin","win","t_ms"])

depth=load_alt_depth(); allt=load_alt_trades()
print("alt queue model (realistic: persist FIFO + reprice-reset, alpha=1):")
print(f"{'coin':>5}{'cfg':>10}{'windows':>8}{'fill':>7}{'net/win':>9}{'gross':>8}{'rebate':>8}{'net t':>7}")
for coin in ["eth","sol","xrp"]:
    a=allt[allt.coin==coin]
    a=a[a.asset_id.isin(depth)]
    for q in [20,50]:
        res,fv,tv=Q.sim(a,depth,1.0,q,persist=True)
        if not res: continue
        G=np.array([v[0] for v in res.values()]);R=np.array([v[1] for v in res.values()]);N=G+R
        t=N.mean()/(N.std(ddof=1)/np.sqrt(len(N))) if len(N)>1 and N.std()>0 else 0
        print(f"{coin:>5}{('Q='+str(q)):>10}{len(N):>8}{fv/tv:>7.1%}{N.mean():>+9.2f}{G.mean():>+8.2f}{R.mean():>+8.2f}{t:>+7.1f}")
