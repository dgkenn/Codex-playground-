import sys, os; sys.path.insert(0, "/home/user/Codex-playground-")
"""How big is the counterparty-avoidance prize? On the 20k-fill BTC tape: what fraction of fills are
toxic (lose at settlement), what's the total drag, and which single feature best separates toxic from
good fills (AUC) -- INCLUDING the new take-size signal the fingerprint work surfaced."""
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from kalshi_sizing import collect_fills
hist=pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
tap=pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")
df=collect_fills(hist,tap,0.0)
df["k"]=np.round(15*(1-df.tau)).astype(int)
df["toxic"]=(df.settle<0).astype(int)
print(f"fills={len(df)} | toxic (settle<0) = {df.toxic.mean()*100:.1f}% | mean settle {df.settle.mean()*100:+.2f}c")
print(f"toxic fills mean settle {df[df.toxic==1].settle.mean()*100:+.1f}c | good fills {df[df.toxic==0].settle.mean()*100:+.1f}c")
print(f"TOTAL drag from toxic fills: {df[df.toxic==1].settle.sum()*100:.0f}c over {len(df)} fills "
      f"({df[df.toxic==1].settle.sum()/df.settle.sum() if df.settle.sum()!=0 else 0:.1f}x the net)")
print("\nSingle-feature separation of toxic vs good (AUC, higher=better signal):")
feats={"|p-0.5|":(df.p-0.5).abs(),"spread":df.spread,"k(late)":df.k,
       "sig_adv":df.sig_adv,"flow_adv":df.flow_adv,"abs_flow":df.flow_adv.abs()}
for nm,v in feats.items():
    v=v.fillna(0); 
    try: a=roc_auc_score(df.toxic, v); a=max(a,1-a)
    except: a=float("nan")
    print(f"  {nm:12s} AUC {a:.3f}")
# the prize framed economically: if we could perfectly skip the toxic fills, net goes from X to Y
keep=df[df.toxic==0]
print(f"\nPRIZE: net = {df.settle.sum()*100:.0f}c (all) vs {keep.settle.sum()*100:.0f}c (toxic-free, "
      f"oracle) -- the { (keep.settle.sum()-df.settle.sum())*100:.0f}c gap is the max avoidance prize")
