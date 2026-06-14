#!/usr/bin/env python3
"""box_adverse_open.py -- Is the maker-box's TOXIC (adversely-selected) loss PREDICTABLE and
AVOIDABLE at OPEN time, ON TOP of the deployed pair-gate (depth>=33k, k<=10, |sig|<10)?

Reframe vs BOX_DISPOSAL_EV (which only studied STRANDS): a strand that gets COMPLETED by crossing
is recorded as a BALANCED box yet still carries the toxic basis (basis = cost_yes + cost_no > $1
=> guaranteed loss). So the true adverse-selection rate >> the ~2% strand rate. We classify EVERY
box (paired OR stranded) by its settle-adjusted realized P&L into CLEAN (+~1c) vs TOXIC (losing
tail), quantify the toxic fraction + c/box drag, then ask whether OPEN-TIME features predict it.

Box-level realized P&L (settle-adjusted, from the reconstructed fills, $/box-contract):
  - PAIRED box: settle_open + settle_pair  (each leg's settle = res-b0 for YES, a0-res for NO,
    so this is exactly payout(winning side) - total cost = 1 - (cost_yes + cost_no) ).
  - STRANDED leg disposed by capcross (the deployed disposal): disposal_value() incl. taker fee.

OPEN-TIME features = the OPEN leg's decision-time fields (known when the FIRST leg fills, before
committing the box): k, |sig|, depth, spread, |p-0.5| (moneyness), side, flow/queue-imbalance, tau,
vpin (markout/toxicity of the just-filled leg), tksize.

Method: front-of-queue (q0=0) replay on the historical tape (box_policy_ab.window_fills), the
repo-standard offline reconstruction. 60/40 IS/OOS time split. Fees: crossing/disposal taker fee
modeled (FEES.md crypto M; sensitivity M=0.07 and 0.14). BACKTEST = SCREEN.
"""
from __future__ import annotations
import sys, math, json
import numpy as np
import pandas as pd

from box_policy_ab import window_fills

HIST = 'hist_kalshi_btc15m.parquet'
TRADES = 'trades_kalshi_btc15m.parquet'

# ---- Deployed pair-gate (EDGE_OPTIMIZE.md / CAPACITY.md) ----
GATE_DEPTH = 33000.0
GATE_K = 10
GATE_SIG = 10.0

# ---- Toxic label threshold (settle-adjusted box P&L, $/contract). CLEAN boxes earn ~+1c; a box
#      that loses money is adversely selected. Use 0 as the economic boundary (loss = toxic).
TOX_THRESH = 0.0

# ---- Fees ----
M_TAKER = 0.07   # standard; crypto-premium 0.14 tested as sensitivity


def parse_arr(v):
    if isinstance(v, np.ndarray):
        return v.astype(float)
    if isinstance(v, list):
        return np.array(v, float)
    import ast
    return np.array(ast.literal_eval(str(v)), float)


def taker_fee(price, M=M_TAKER):
    """Per-contract Kalshi taker fee = ceil(M*P*(1-P)*100)/100 (FEES.md)."""
    p = min(max(price, 0.0), 1.0)
    return math.ceil(M * p * (1.0 - p) * 100.0) / 100.0


def load_windows(asset='btc'):
    hist = pd.read_parquet(HIST)
    trades = pd.read_parquet(TRADES)
    hist_idx = {r['ws']: r for _, r in hist.iterrows()}
    trades_idx = {r['ws']: r for _, r in trades.iterrows()}
    common = sorted(set(hist_idx) & set(trades_idx))
    fpw = {}
    for ws in common:
        h, t = hist_idx[ws], trades_idx[ws]
        try:
            fills = window_fills(ws, int(h['res_up']),
                                 parse_arr(h['bid_path']), parse_arr(h['ask_path']),
                                 parse_arr(h['spot_path']), parse_arr(h['vol_path']),
                                 (parse_arr(t['t']), parse_arr(t['p']), parse_arr(t['sz']),
                                  parse_arr(t['buy']).astype(bool)),
                                 oi_slope=None, q0=0.0)
        except Exception:
            fills = []
        if fills:
            fpw[ws] = fills
    return fpw, sorted(fpw)


def p_yeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)


def open_gate(f):
    """The DEPLOYED pair-gate, applied to an OPENING leg."""
    d = f.get('depth')
    d = 0.0 if (d is None or (isinstance(d, float) and np.isnan(d))) else float(d)
    if d < GATE_DEPTH:
        return False
    if f.get('k', 99) > GATE_K:
        return False
    if abs(f.get('sig', 0.0) or 0.0) >= GATE_SIG:
        return False
    return True


def build_boxes(fpw, ws_list, gate=None, M=M_TAKER, extra_open=None):
    """Walk each window with the always-pair (--max-net 1) policy. A gate is applied to OPENING legs
    (the pair-gate, plus optional extra_open). Returns one row per BOX (paired) or stranded leg.
    Box P&L is settle-adjusted from fills; stranded legs disposed by capcross (deployed) w/ taker fee.

    OPEN-TIME features come from the OPEN leg (the first leg of the box)."""
    rows = []
    for ws in ws_list:
        net = 0
        open_leg = None
        for f in fpw[ws]:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                # pairing fill: completes the box. Completing leg is a MAKER fill in q0=0 replay
                # (rests at touch), so no taker fee on it; box basis = cost_open+cost_pair captured
                # by the two settle values. (If completion required crossing, the toxic basis is the
                # same magnitude -- captured here as a negative settle sum either way.)
                box_pnl = f['settle'] + (open_leg['settle'] if open_leg else 0.0)
                rows.append(_row(ws, open_leg, box_pnl, 'paired'))
                open_leg = None
            else:
                if gate is not None and not gate(f):
                    continue
                if extra_open is not None and not extra_open(f):
                    continue
                open_leg = f
            net = nn
        if open_leg is not None:
            # stranded leg: deployed disposal = capcross (cross early unless lock worse than give-cap
            # 0.10), incl. taker fee on the crossing.
            hold = open_leg['settle']
            early = open_leg.get('exit', hold)
            # crossing price ~ the touch we cross to flatten; approximate fee at the leg's own price.
            fee = taker_fee(p_yeq(open_leg), M)
            disp = hold if (early - fee) < -0.10 else (early - fee)
            rows.append(_row(ws, open_leg, disp, 'strand'))
    return pd.DataFrame(rows)


def _row(ws, f, pnl, kind):
    return dict(
        ws=ws, kind=kind, pnl=pnl,
        side=f['side'], side_bin=1 if f['side'] == 'bid' else 0,
        k=f.get('k', np.nan), tau=f.get('tau', np.nan),
        absig=abs(f.get('sig', 0.0) or 0.0), sig=f.get('sig', 0.0) or 0.0,
        depth=(0.0 if f.get('depth') is None or (isinstance(f.get('depth'), float) and np.isnan(f.get('depth'))) else float(f['depth'])),
        spread=f.get('spread', np.nan),
        absp05=abs(p_yeq(f) - 0.5), p_yeq=p_yeq(f),
        flow=f.get('flow', 0.0) or 0.0, absflow=abs(f.get('flow', 0.0) or 0.0),
        vpin=(np.nan if f.get('vpin') is None else float(f.get('vpin'))),
        tksize=(np.nan if f.get('tksize') is None else float(f.get('tksize'))),
    )


def summ(df, label):
    if len(df) == 0:
        print(f"  {label}: EMPTY"); return
    tox = df['pnl'] < TOX_THRESH
    print(f"  {label}: N={len(df)}  toxic_frac={tox.mean()*100:5.1f}%  "
          f"mean={df['pnl'].mean()*100:+.3f}c  median={df['pnl'].median()*100:+.3f}c  "
          f"clean_mean={df.loc[~tox,'pnl'].mean()*100:+.3f}c  tox_mean={df.loc[tox,'pnl'].mean()*100:+.3f}c  "
          f"strand_frac={ (df['kind']=='strand').mean()*100:.1f}%")


def main():
    print("=" * 78)
    print("BOX ADVERSE-SELECTION AT OPEN -- BTC 15m maker-box (SCREEN, q0=0 replay)")
    print("=" * 78)
    fpw, ws = load_windows('btc')
    n = len(ws)
    cut = int(n * 0.6)
    ws_is, ws_oos = ws[:cut], ws[cut:]
    import datetime as dt
    span = f"{dt.datetime.utcfromtimestamp(ws[0]):%Y-%m-%d} .. {dt.datetime.utcfromtimestamp(ws[-1]):%Y-%m-%d}"
    print(f"windows w/ fills (need book+tape): {n}  span {span}  IS={len(ws_is)} OOS={len(ws_oos)}")

    # ---------- 1. TRUE TOXIC FRACTION (ungated vs pair-gated) ----------
    print("\n[1] TRUE toxic fraction (box settle-adjusted P&L < 0), M=0.07 taker fee on disposal")
    all_box = build_boxes(fpw, ws, gate=None)
    gated_box = build_boxes(fpw, ws, gate=open_gate)
    summ(all_box, "UNGATED (no pair-gate)")
    summ(gated_box, "PAIR-GATED (depth>=33k,k<=10,|sig|<10)  <-- the live baseline")

    # decompose pair-gated toxic by kind
    g = gated_box
    print(f"\n  pair-gated toxic boxes by kind: "
          f"paired-toxic={((g['pnl']<0)&(g['kind']=='paired')).sum()}  "
          f"strand-toxic={((g['pnl']<0)&(g['kind']=='strand')).sum()}  "
          f"of {len(g)} boxes; the COMPLETED-but-toxic (balanced) boxes are the hidden cost")
    paired = g[g['kind']=='paired']
    print(f"  pair-gated PAIRED boxes: N={len(paired)} mean={paired['pnl'].mean()*100:+.3f}c "
          f"toxic_frac={(paired['pnl']<0).mean()*100:.1f}% (these slip through the strand-gate)")
    # P&L distribution
    qs = g['pnl'].quantile([0.01,0.05,0.10,0.25,0.5,0.75,0.9,0.95,0.99]).values*100
    print(f"  pair-gated box P&L pctiles (c): "
          + " ".join(f"p{int(q)}={v:+.1f}" for q,v in zip([1,5,10,25,50,75,90,95,99],qs)))

    # crypto-premium fee sensitivity
    g14 = build_boxes(fpw, ws, gate=open_gate, M=0.14)
    print(f"  [fee sensitivity M=0.14]: toxic_frac={(g14['pnl']<0).mean()*100:.1f}%  mean={g14['pnl'].mean()*100:+.3f}c")

    # ---------- 2/3. OPEN-TIME PREDICTABILITY ----------
    print("\n[2/3] Is TOXICITY predictable at OPEN, on the PAIR-GATED boxes? (IS-fit, OOS-test)")
    gb_is = build_boxes(fpw, ws_is, gate=open_gate)
    gb_oos = build_boxes(fpw, ws_oos, gate=open_gate)
    print(f"  pair-gated boxes IS={len(gb_is)} (tox {(gb_is['pnl']<0).mean()*100:.1f}%)  "
          f"OOS={len(gb_oos)} (tox {(gb_oos['pnl']<0).mean()*100:.1f}%)")

    feats = ['k','tau','absig','depth','spread','absp05','side_bin','absflow','vpin','tksize']
    # single-feature OOS AUC (rank corr of feature vs toxic label)
    from sklearn.metrics import roc_auc_score
    yo = (gb_oos['pnl'] < 0).astype(int).values
    yi = (gb_is['pnl'] < 0).astype(int).values
    print("\n  single-feature OOS AUC (sign-aligned on IS; >0.55 = some signal):")
    aucs = {}
    for c in feats:
        xi = gb_is[c].fillna(gb_is[c].median()).values
        xo = gb_oos[c].fillna(gb_is[c].median()).values
        if np.std(xi) == 0 or len(np.unique(yi)) < 2:
            continue
        # orient by IS correlation sign
        sgn = 1.0 if np.corrcoef(xi, yi)[0,1] >= 0 else -1.0
        try:
            a = roc_auc_score(yo, sgn*xo)
        except Exception:
            continue
        aucs[c] = a
        print(f"    {c:9s} OOS AUC {a:.3f}  (IS corr {np.corrcoef(xi,yi)[0,1]:+.3f})")

    # multivariate logistic (1-3 features), standardized, IS-fit
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    def fit_logit(cols):
        Xi = gb_is[cols].fillna(gb_is[cols].median())
        Xo = gb_oos[cols].fillna(gb_is[cols].median())
        sc = StandardScaler().fit(Xi)
        if len(np.unique(yi)) < 2:
            return None
        lr = LogisticRegression(max_iter=1000, C=1.0).fit(sc.transform(Xi), yi)
        po = lr.predict_proba(sc.transform(Xo))[:,1]
        return roc_auc_score(yo, po), lr, sc
    print("\n  multivariate logistic OOS AUC:")
    for cols in [['absp05'], ['spread'], ['absp05','spread'],
                 ['absp05','spread','k'], feats[:6], feats]:
        r = fit_logit(cols)
        if r: print(f"    {str(cols):55s} OOS AUC {r[0]:.3f}")

    # ---------- 4. BEST INCREMENTAL GATE ON TOP OF PAIR-GATE (net-of-volume) ----------
    print("\n[4] Best INCREMENTAL open-gate ON TOP of pair-gate -- net c/box AND volume retained")
    print("    (baseline = pair-gated; a gate must RAISE net c/box while keeping enough volume)")
    base_n = len(gb_oos); base_net = gb_oos['pnl'].mean()*100
    base_tot = gb_oos['pnl'].sum()*100
    print(f"    BASELINE pair-gated OOS: N={base_n}  net={base_net:+.3f}c/box  total={base_tot:+.1f}c")

    # candidate incremental thresholds (IS-chosen direction, OOS-evaluated), each a 1-feature gate
    cands = []
    def ev(name, mask_is_fn, mask_oos_fn):
        ki = mask_is_fn(gb_is); ko = mask_oos_fn(gb_oos)
        if ko.sum() < 20:
            return
        net = gb_oos.loc[ko,'pnl'].mean()*100
        tot = gb_oos.loc[ko,'pnl'].sum()*100
        vol = ko.mean()*100
        tox = (gb_oos.loc[ko,'pnl']<0).mean()*100
        cands.append((name, net, vol, tot, tox, base_tot))
        print(f"    {name:34s} keep {vol:5.1f}%  net {net:+.3f}c/box  total {tot:+7.1f}c "
              f"(base {base_tot:+.1f})  tox {tox:4.1f}%  net-of-vol {'WORSE' if tot<base_tot else 'OK'}")

    # moneyness gates (closer to 0.5 => deeper book, pairs balanced)
    for thr in [0.10, 0.15, 0.20, 0.25, 0.30]:
        ev(f"absp05 <= {thr}", lambda d,t=thr: d['absp05']<=t, lambda d,t=thr: d['absp05']<=t)
    # spread gates (wider spread = more captured edge)
    for thr in [0.015, 0.02, 0.025]:
        ev(f"spread >= {thr}", lambda d,t=thr: d['spread']>=t, lambda d,t=thr: d['spread']>=t)
    # k gates (earlier = more time to pair balanced)
    for thr in [5,6,7,8]:
        ev(f"k <= {thr}", lambda d,t=thr: d['k']<=t, lambda d,t=thr: d['k']<=t)
    # tighter sig
    for thr in [3.0,5.0,7.0]:
        ev(f"|sig| <= {thr}", lambda d,t=thr: d['absig']<=t, lambda d,t=thr: d['absig']<=t)
    # deeper depth
    for thr in [40000,50000,60000]:
        ev(f"depth >= {thr}", lambda d,t=thr: d['depth']>=t, lambda d,t=thr: d['depth']>=t)
    # favorite-only opens (t29 survivor): leg's own cost >= 0.45 (= absp05 fav side). Encode as
    # "the open leg is the favored side": leg cost = p_yeq (bid) or 1-p_yeq (ask) >= 0.45.
    def legcost(d):
        return d.apply(lambda r: r['p_yeq'] if r['side']=='bid' else 1.0-r['p_yeq'], axis=1)
    ev("legcost >= 0.45 (favorite-only)", lambda d: legcost(d)>=0.45, lambda d: legcost(d)>=0.45)

    print("\n  Verdict screen: a gate is a real incremental lever only if OOS total c >= baseline")
    print("  total c (does NOT win merely by trading less) AND net c/box rises with material volume.")

    # combined best: try absp05<=0.20 (mid-book) AND spread>=0.02
    print("\n  combined mid-book + wide-spread (absp05<=0.20 & spread>=0.02):")
    ko = (gb_oos['absp05']<=0.20)&(gb_oos['spread']>=0.02)
    if ko.sum()>=20:
        print(f"    keep {ko.mean()*100:.1f}%  net {gb_oos.loc[ko,'pnl'].mean()*100:+.3f}c  "
              f"total {gb_oos.loc[ko,'pnl'].sum()*100:+.1f}c (base {base_tot:+.1f})  "
              f"tox {(gb_oos.loc[ko,'pnl']<0).mean()*100:.1f}%")

    # ---------- LIVE sanity check ----------
    print("\n[LIVE] sanity check (walk origin/live-state winrecs + fills, settle via API)")
    try:
        live_check()
    except Exception as e:
        print(f"  live check skipped: {e}")


def live_check():
    """Classify live boxes CLEAN vs TOXIC from raw FILLS (per-ticker), settle via Kalshi API."""
    import subprocess, requests
    def walk(path):
        try:
            commits = subprocess.check_output(["git","log","--format=%H","origin/live-state"]).decode().split()
        except Exception:
            return []
        out=[]
        for c in commits:
            try:
                blob = subprocess.check_output(["git","show",f"{c}:{path}"],stderr=subprocess.DEVNULL).decode()
            except Exception:
                continue
            for ln in blob.splitlines():
                if ln.strip():
                    try: out.append(json.loads(ln))
                    except Exception: pass
        return out
    import datetime as dt
    days=["2026-06-13","2026-06-14"]
    fills={}
    for day in days:
        for r in walk(f"live_state/{day}/kalshi_fees_btc15m.jsonl"):
            tid=(r.get("raw") or {}).get("trade_id")
            if tid: fills[tid]=r
    byc={}
    for r in fills.values():
        byc.setdefault(r["ticker"],[]).append(r)
    B="https://api.elections.kalshi.com/trade-api/v2"; ses=requests.Session(); sc={}
    def settle(tk):
        if tk in sc: return sc[tk]
        s=None
        for _ in range(3):
            try: s=ses.get(f"{B}/markets/{tk}",timeout=8).json().get("market",{}).get("result"); break
            except Exception: pass
        sc[tk]=s if s in ("yes","no") else None
        return sc[tk]
    rows=[]
    for tk,fl in byc.items():
        s=settle(tk)
        if s not in ("yes","no"): continue
        ny=sum(r["count"] for r in fl if r["side"]=="yes")
        nn=sum(r["count"] for r in fl if r["side"]=="no")
        cost=sum(r["price"]*r["count"] for r in fl)
        payout=sum(r["count"] for r in fl if r["side"]==s)
        nboxes=min(ny,nn) if min(ny,nn)>0 else max(ny,nn)
        pnl=(payout-cost)/max(nboxes,1)
        rows.append((tk,ny,nn,pnl))
    if not rows:
        print("  no settled live boxes"); return
    df=pd.DataFrame(rows,columns=["tk","ny","nn","pnl_per_box"])
    tox=df["pnl_per_box"]<0
    print(f"  live settled markets: {len(df)}  toxic(P&L<0)={tox.sum()} ({tox.mean()*100:.0f}%)  "
          f"mean {df['pnl_per_box'].mean()*100:+.1f}c/box  median {df['pnl_per_box'].median()*100:+.1f}c")
    print(f"  worst 5 (c/box): "+", ".join(f"{v*100:+.0f}" for v in df['pnl_per_box'].nsmallest(5)))
    bal=df[df.ny==df.nn]
    print(f"  BALANCED (ny==nn) markets: {len(bal)}  toxic={ (bal['pnl_per_box']<0).sum() } "
          f"-- completed-but-toxic = the hidden adverse cost")


if __name__ == "__main__":
    main()
