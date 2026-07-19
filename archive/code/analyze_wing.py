#!/usr/bin/env python3
"""Analysis of Kalshi KXBTCD wing records produced by kalshi_wing_verify.py."""
import json, os, math, statistics
CACHE="/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/wing_cache"
recs=json.load(open(os.path.join(CACHE,"recs.json")))
WING_MAX=0.15
BINS=[(0.00,0.02),(0.02,0.04),(0.04,0.06),(0.06,0.10),(0.10,0.15)]

def kalshi_fee(price):
    return math.ceil(0.07*price*(1.0-price)*100.0)/100.0  # dollars, taker, 1 contract

def cluster_t(pairs):
    # pairs: list of (value, cluster_key). Returns (mean, t, N, G)
    vals=[p[0] for p in pairs]
    N=len(vals)
    if N<2: return (float('nan'),float('nan'),N,0)
    mean=sum(vals)/N
    # cluster sums of residuals
    from collections import defaultdict
    cs=defaultdict(float)
    for v,g in pairs: cs[g]+=(v-mean)
    G=len(cs)
    if G<2: return (mean,float('nan'),N,G)
    meat=sum(s*s for s in cs.values())
    c=(G/(G-1.0))*((N-1.0)/(N-1.0))  # K=1 -> (N-1)/(N-K)=1
    var=c*meat/(N*N)
    se=math.sqrt(var) if var>0 else float('nan')
    t=mean/se if se and se>0 else float('nan')
    return (mean,t,N,G)

def bin_of(p):
    for lo,hi in BINS:
        if p>lo and p<=hi: return (lo,hi)
    return None

def wvwap(pxlist_with_counts):
    pass

print("="*90)
print(f"TOTAL first-half-traded settled markets: {len(recs)}")
alldates=sorted(set(r['close_date'] for r in recs))
print(f"distinct close-dates in sample: {len(alldates)}  ({alldates[0]} .. {alldates[-1]})")

# ---------------- (1) CALIBRATION UNDER 3 ENTRY DEFS ----------------
print("\n"+"="*90)
print("(1) CALIBRATION under THREE independent entry-price definitions")
print("    edge_buyer = realized - entry (negative => YES OVERPRICED => selling YES gross-profits)")
print("    seller_net = (entry - result) - fee ; t = day-clustered (cluster=close_date)")
for defname in ["vwap","near","med"]:
    print(f"\n--- entry definition: {defname} ---")
    print(f"{'bin':>10} {'N':>5} {'dates':>5} {'entry':>7} {'realized':>8} {'edge_buy':>8} {'sellNet¢':>8} {'t_clust':>7}")
    for lo,hi in BINS:
        sub=[r for r in recs if (r[defname] is not None and lo<r[defname]<=hi)]
        if not sub:
            print(f"{lo:.2f}-{hi:.2f}      0"); continue
        entry=statistics.mean(r[defname] for r in sub)
        realized=statistics.mean(r['result'] for r in sub)
        pnl=[((r[defname]-r['result'])-kalshi_fee(r[defname]), r['close_date']) for r in sub]
        m,t,N,G=cluster_t(pnl)
        print(f"{lo:.2f}-{hi:.2f} {len(sub):>5} {G:>5} {entry:>7.3f} {realized:>8.3f} {realized-entry:>8.3f} {m*100:>8.2f} {t:>7.2f}")
    # aggregate all wings
    sub=[r for r in recs if (r[defname] is not None and 0<r[defname]<=WING_MAX)]
    pnl=[((r[defname]-r['result'])-kalshi_fee(r[defname]), r['close_date']) for r in sub]
    m,t,N,G=cluster_t(pnl)
    entry=statistics.mean(r[defname] for r in sub); realized=statistics.mean(r['result'] for r in sub)
    print(f"{'ALL<=.15':>10} {N:>5} {G:>5} {entry:>7.3f} {realized:>8.3f} {realized-entry:>8.3f} {m*100:>8.2f} {t:>7.2f}")

# ---------------- (2) TAKER-SIDE / EXECUTABLE SELL PRICE ----------------
print("\n"+"="*90)
print("(2) EXECUTABLE-SELL-PRICE analysis (VWAP is what BUYERS paid ~ ASK)")
wings=[r for r in recs if (r['vwap'] is not None and 0<r['vwap']<=WING_MAX)]
tot_buy=sum(r['buy_cnt'] for r in wings); tot_sell=sum(r['sell_cnt'] for r in wings)
print(f"\nEarly wing trades: aggressive-YES-BUY contracts={tot_buy:.0f}  aggressive-YES-SELL contracts={tot_sell:.0f}")
print(f"  fraction of early wing volume that is BUYERS lifting the offer: {tot_buy/(tot_buy+tot_sell):.3f}")
n_with_sell=sum(1 for r in wings if r['sell_cnt']>0)
print(f"  wings with ANY real taker-SELL (executable bid observed): {n_with_sell}/{len(wings)} = {n_with_sell/len(wings):.3f}")

# estimate half-spread within-market (markets with BOTH sides), by bin
print(f"\nWithin-market spread (markets with both a taker-BUY and taker-SELL early trade):")
print(f"{'bin':>10} {'nMkts':>6} {'askMean':>8} {'bidMean':>8} {'halfSprd¢':>9}")
halfspread_bin={}
for lo,hi in BINS:
    hs=[]; asks=[]; bids=[]
    for r in wings:
        if not (lo<r['vwap']<=hi): continue
        if r['first_buy_px'] and r['first_sell_px']:
            a=statistics.mean(r['first_buy_px']); b=statistics.mean(r['first_sell_px'])
            hs.append((a-b)/2.0); asks.append(a); bids.append(b)
    if hs:
        halfspread_bin[(lo,hi)]=statistics.median(hs)
        print(f"{lo:.2f}-{hi:.2f} {len(hs):>6} {statistics.mean(asks):>8.3f} {statistics.mean(bids):>8.3f} {statistics.median(hs)*100:>9.2f}")
    else:
        print(f"{lo:.2f}-{hi:.2f} {0:>6}")

# recompute SELLER pnl under 4 executable-price definitions
print("\nSELLER-of-YES net PnL (cents/contract) under different SELL-price assumptions:")
print("  A = sell at VWAP (optimistic, ~ask)         B = sell at real taker-SELL VWAP (actual bids)")
print("  C = VWAP - estimated within-bin half-spread D = VWAP - flat 1.0c")
print(f"{'bin':>10} {'N':>5} {'dates':>5} {'A_sell¢':>8} {'tA':>6} {'B_sell¢':>8} {'tB':>6} {'nB':>5} {'C_sell¢':>8} {'tC':>6} {'D_sell¢':>8} {'tD':>6}")
def seller_rows(sub, price_fn):
    out=[]
    for r in sub:
        ps=price_fn(r)
        if ps is None: continue
        out.append(((ps - r['result']) - kalshi_fee(max(ps,0.001)), r['close_date']))
    return out
for lo,hi in list(BINS)+[("ALL",WING_MAX)]:
    if lo=="ALL":
        sub=[r for r in wings]
    else:
        sub=[r for r in wings if lo<r['vwap']<=hi]
    if not sub:
        print(f"{str(lo):>10}      0"); continue
    hsp=halfspread_bin.get((lo,hi), statistics.median([v for v in halfspread_bin.values()]) if halfspread_bin else 0.01)
    A=seller_rows(sub, lambda r:r['vwap'])
    # B: real sell-side VWAP among taker=no trades
    def bfn(r):
        if not r['first_sell_px']: return None
        return statistics.mean(r['first_sell_px'])
    B=seller_rows(sub, bfn)
    C=seller_rows(sub, lambda r:r['vwap']-hsp)
    D=seller_rows(sub, lambda r:r['vwap']-0.01)
    mA,tA,NA,GA=cluster_t(A); mB,tB,NB,GB=cluster_t(B); mC,tC,NC,GC=cluster_t(C); mD,tD,ND,GD=cluster_t(D)
    lab=f"{lo:.2f}-{hi:.2f}" if lo!="ALL" else "ALL<=.15"
    print(f"{lab:>10} {NA:>5} {GA:>5} {mA*100:>8.2f} {tA:>6.2f} {mB*100:>8.2f} {tB:>6.2f} {NB:>5} {mC*100:>8.2f} {tC:>6.2f} {mD*100:>8.2f} {tD:>6.2f}")

# ---------------- (3) SELECTION / VOLUME ----------------
print("\n"+"="*90)
print("(3) SELECTION: volume distribution of wing markets & edge-vs-size")
vols=sorted(r['volume'] for r in wings)
def pct(p):
    i=min(len(vols)-1,int(p/100*len(vols))); return vols[i]
print(f"wing volume_fp (contracts) percentiles: p10={pct(10):.0f} p25={pct(25):.0f} p50={pct(50):.0f} p75={pct(75):.0f} p90={pct(90):.0f} p99={pct(99):.0f} max={vols[-1]:.0f}")
for thr in [10,50,100,500,1000]:
    n=sum(1 for v in vols if v<thr)
    print(f"  wings with total volume < {thr}: {n}/{len(vols)} = {n/len(vols):.3f}")
# edge by volume tertile (seller net at VWAP and at real-sell price B)
print("\nSeller PnL by wing VOLUME tertile:")
ws=sorted(wings,key=lambda r:r['volume'])
n=len(ws); t1=ws[:n//3]; t2=ws[n//3:2*n//3]; t3=ws[2*n//3:]
print(f"{'tertile':>10} {'N':>5} {'volRange':>16} {'sellVWAP¢':>10} {'t':>6} {'sellReal¢':>10} {'t':>6} {'nReal':>6}")
for name,grp in [("low",t1),("mid",t2),("high",t3)]:
    A=[((r['vwap']-r['result'])-kalshi_fee(r['vwap']),r['close_date']) for r in grp]
    B=[]
    for r in grp:
        if r['first_sell_px']:
            ps=statistics.mean(r['first_sell_px']); B.append(((ps-r['result'])-kalshi_fee(max(ps,0.001)),r['close_date']))
    mA,tA,_,_=cluster_t(A); mB,tB,NB,_=cluster_t(B)
    vr=f"{grp[0]['volume']:.0f}-{grp[-1]['volume']:.0f}"
    print(f"{name:>10} {len(grp):>5} {vr:>16} {mA*100:>10.2f} {tA:>6.2f} {mB*100:>10.2f} {tB:>6.2f} {NB:>6}")

# ---------------- (4) temporal split (IS/OOS) ----------------
print("\n"+"="*90)
print("(4) TEMPORAL SPLIT (calendar halves) seller net at VWAP vs real-sell price")
mid=alldates[len(alldates)//2]
for name,cond in [("first-half dates",lambda r:r['close_date']<mid),("second-half dates",lambda r:r['close_date']>=mid)]:
    sub=[r for r in wings if cond(r)]
    A=[((r['vwap']-r['result'])-kalshi_fee(r['vwap']),r['close_date']) for r in sub]
    B=[]
    for r in sub:
        if r['first_sell_px']:
            ps=statistics.mean(r['first_sell_px']); B.append(((ps-r['result'])-kalshi_fee(max(ps,0.001)),r['close_date']))
    mA,tA,NA,GA=cluster_t(A); mB,tB,NB,GB=cluster_t(B)
    print(f"{name:>18}: N={NA} dates={GA}  sellVWAP={mA*100:.2f}c t={tA:.2f} | sellReal={mB*100:.2f}c t={tB:.2f} nReal={NB}")
print("\nDONE")
