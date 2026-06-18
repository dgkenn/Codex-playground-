#!/usr/bin/env python3
"""kalshi_maker_harvest.py -- MAKER side of the favorite-longshot edge on Kalshi soft
markets (GWU "makers win, takers lose"). Taker tests (KALSHI_FAVLONG_SCAN.md) crossed the
spread and lost; this asks whether PROVIDING liquidity (rest a bid, get lifted) captures
the bias, net of fee. Liquid single-outcome settled binaries, real mid-life two-sided
quote (bid,ask), result; per band: TAKER buy-YES@ask / buy-NO@(1-bid) vs MAKER buy-YES@bid
/ buy-NO@(1-ask), net of Kalshi quadratic fee. CAVEAT: assumes you get filled and ignores
fill-conditional adverse selection (see KALSHI_MAKER_ADVSEL.md) -- positive here is
necessary-not-sufficient. Public API, no auth.  python kalshi_maker_harvest.py
"""
import urllib.request, json, time, urllib.parse, datetime as dt, math
BASE="https://api.elections.kalshi.com/trade-api/v2"
CATS=["Economics","Politics","Climate and Weather","Entertainment","Science and Technology","World","Companies"]
FEE=lambda p:0.07*p*(1-p); BANDS=[(i/20,(i+1)/20) for i in range(20)]; MAXSPREAD=0.20; MAXMKTS=900
def get(path,params=""):
    u=f"{BASE}{path}"+("?"+params if params else "")
    for a in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"r"}),timeout=25))
        except Exception:
            if a==3: raise
            time.sleep(1.2*(a+1))
def fnum(x):
    try: return float(x)
    except: return None
def ts(s): return int(dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()) if s else None
def series_for(cat,cap=60):
    out,cur=[],""
    while len(out)<cap:
        d=get("/series",f"category={urllib.parse.quote(cat)}&limit=100"+(f"&cursor={cur}" if cur else ""))
        out+=[s["ticker"] for s in d.get("series",[]) if s.get("ticker")]; cur=d.get("cursor") or ""
        if not cur: break
    return out[:cap]
def settled(st,cap=100):
    out,cur=[],""
    while len(out)<cap:
        d=get("/markets",f"series_ticker={st}&status=settled&limit=100"+(f"&cursor={cur}" if cur else ""))
        ms=d.get("markets",[]); out+=ms; cur=d.get("cursor") or ""
        if not cur or not ms: break
    return out[:cap]
def midq(st,m):
    o,c=ts(m.get("open_time")),ts(m.get("close_time"))
    if not o or not c or c<=o: return None
    try: cs=get(f"/series/{st}/markets/{m['ticker']}/candlesticks",f"start_ts={o}&end_ts={c}&period_interval=60").get("candlesticks",[])
    except: return None
    if not cs: return None
    tgt=(o+c)/2; cs.sort(key=lambda k:abs((k.get("end_period_ts") or 0)-tgt))
    for k in cs:
        yb=fnum((k.get("yes_bid") or {}).get("close_dollars")); ya=fnum((k.get("yes_ask") or {}).get("close_dollars"))
        if yb is None or ya is None: continue
        if 0<yb<ya<1 and (ya-yb)<=MAXSPREAD: return (yb,ya)
    return None
def main():
    rows,seen,nf=[],set(),0
    for cat in CATS:
        try: sers=series_for(cat)
        except: continue
        n0=len(rows)
        for st in sers:
            if nf>=MAXMKTS: break
            try: ms=settled(st)
            except: continue
            for m in ms:
                if nf>=MAXMKTS: break
                tk=m.get("ticker")
                if tk in seen: continue
                seen.add(tk)
                if m.get("mve_collection_ticker") or (m.get("market_type") and m.get("market_type")!="binary"): continue
                if (m.get("result") or "").lower() not in ("yes","no"): continue
                if (fnum(m.get("volume_fp")) or 0)<300: continue
                nf+=1; q=midq(st,m)
                if q is None: continue
                bid,ask=q; rows.append((bid,ask,(bid+ask)/2,1 if m["result"].lower()=="yes" else 0))
        print(f"[{cat}] fetched~{nf} usable={len(rows)-n0}",flush=True)
    print(f"\nTOTAL {len(rows)} (fetches {nf})\n")
    if len(rows)<60: print("too few."); return
    print(f"{'band':>10} {'n':>4} {'mid':>5} {'WR':>5} {'z':>5} {'TAKER':>7} {'MAKER':>7} {'side':>4}")
    for lo,hi in BANDS:
        b=[(bd,ak,w) for bd,ak,mid,w in rows if lo<=mid<hi]
        if len(b)<20: continue
        n=len(b); mmid=sum((x+y)/2 for x,y,_ in b)/n; wr=sum(w for _,_,w in b)/n
        se=math.sqrt(max(mmid*(1-mmid),1e-9)/n); z=(wr-mmid)/se
        ty=sum(w-ak-FEE(ak) for _,ak,w in b)/n; tn=sum((1-w)-(1-bd)-FEE(1-bd) for bd,_,w in b)/n
        my=sum(w-bd-FEE(bd) for bd,_,w in b)/n; mn=sum((1-w)-(1-ak)-FEE(1-ak) for _,ak,w in b)/n
        tak=max(ty,tn); mak=max(my,mn); side="YES" if my>=mn else "NO"
        print(f"{lo:.2f}-{hi:.2f} {n:>4} {mmid:>5.2f} {wr:>5.2f} {z:>+5.1f} {tak*100:>+6.2f}c {mak*100:>+6.2f}c {side:>4}")
    print("\nMaker buys@bid/sells@ask => earns the spread the taker pays. Positive = necessary-not-sufficient; "
          "gate is adverse selection (KALSHI_MAKER_ADVSEL.md) + capacity (KALSHI_MAKER_CAPACITY.md).")
if __name__=="__main__": main()
