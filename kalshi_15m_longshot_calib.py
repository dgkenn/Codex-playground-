#!/usr/bin/env python3
"""Longshot-maker calibration of 15m BTC binaries, read straight from git (origin/gha-data),
applying the soft-market WINNING framework to the efficient corner: at the cheap tail
(up-binary mid 0.02-0.20) near window end, is the longshot OVERPRICED (realized < priced ->
maker-NO harvest) or well-calibrated (efficient -> dead)? Net of ~spread + Kalshi fee.
"""
import subprocess, gzip, io, json, math, sys
from collections import defaultdict

BRANCH = "origin/gha-data"
DECISION_T = 862.0   # seconds into the 900s window (2 min before close -- where longshots live)
FEE = lambda p: 0.07 * p * (1 - p)


def gshow(path):
    return subprocess.run(["git", "show", f"{BRANCH}:{path}"], capture_output=True).stdout


def files(pat):
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", BRANCH], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if pat in l]


def main():
    # 1. ws -> resolved_up from shadow_windows
    res = {}
    for f in files("shadow_windows_kalshi_btc15m"):
        for ln in gshow(f).splitlines():
            try:
                w = json.loads(ln)
            except Exception:
                continue
            if w.get("ws") is not None and w.get("resolved_up") is not None:
                res[w["ws"]] = int(w["resolved_up"])
    # 2. ws -> ALL up-binary ticks across files, then pick the tick closest to DECISION_T
    perws = {}   # ws -> list of (t, bid, ask)
    for f in files("ticks_kalshi_btc15m"):
        raw = gshow(f)
        try:
            data = gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode()
        except Exception:
            continue
        for ln in data.splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("role") != "up":
                continue
            ws = r.get("ws")
            if ws is None or ws not in res:
                continue
            for tk in (r.get("ticks") or []):
                if len(tk) < 7 or tk[0] is None or tk[4] is None or tk[6] is None:
                    continue
                perws.setdefault(ws, []).append((tk[0], tk[4], tk[6]))
    # pool ALL tick observations (not one/window): each tick = "market priced UP at X, did it resolve up?"
    obs = []   # (mid, bid, ask, resolved_up, ws)
    for ws, tks in perws.items():
        for t, bid, ask in tks:
            if 0 < bid <= ask < 1:
                obs.append(((bid + ask) / 2, float(bid), float(ask), res[ws], ws))
    print(f"windows with outcome={len(res)}  pooled tick observations={len(obs)} "
          f"(autocorr within window -> report distinct windows/band)\n")
    if len(obs) < 50:
        print("too few; widen dates."); return

    # 3. calibration by mid band, with maker-NO EV (rest NO buy at no_bid=1-ask) and taker-NO EV
    print(f"{'band':>10} {'ticks':>6} {'wins':>5} {'mid':>5} {'realUP':>7} {'bias_pp':>8} {'z':>5} {'MAKER_NO':>9} {'TAKER_NO':>9}")
    bands = [(0.02,0.05),(0.05,0.08),(0.08,0.12),(0.12,0.16),(0.16,0.20),
             (0.20,0.35),(0.35,0.50),(0.50,0.65),(0.80,0.88),(0.88,0.95),(0.95,0.98)]
    for lo, hi in bands:
        b = [(mid,bd,ak,r) for mid,bd,ak,r,w in obs if lo <= mid < hi]
        nw = len({w for mid,bd,ak,r,w in obs if lo <= mid < hi})
        if len(b) < 30:
            continue
        n=len(b); mmid=sum(x[0] for x in b)/n; up=sum(x[3] for x in b)/n
        # z on the DISTINCT-WINDOW count (honest power, not autocorrelated ticks)
        se=math.sqrt(max(mmid*(1-mmid),1e-9)/max(nw,1)); z=(up-mmid)/se
        # we sell the UP longshot from the NO side. NO wins when UP does NOT resolve (1-up).
        # MAKER NO: buy NO at no_bid = 1-ask (rest passively). EV=(1-up)-(1-ask)-fee = ak-up-fee.
        mak=sum((1-r)-(1-ak)-FEE(1-ak) for _,_,ak,r in b)/n
        # TAKER NO: buy NO at no_ask = 1-bid. EV=(1-up)-(1-bd)-fee = bd-up-fee.
        tak=sum((1-r)-(1-bd)-FEE(1-bd) for _,bd,_,r in b)/n
        print(f"{lo:.2f}-{hi:.2f} {n:>6} {nw:>5} {mmid:>5.2f} {up:>7.3f} {(up-mmid)*100:>+8.1f} {z:>+5.1f} "
              f"{mak*100:>+7.2f}c {tak*100:>+7.2f}c")
    print("\nbias_pp = realized UP-rate - mid (<0 => UP longshot OVERPRICED => NO harvest). MAKER_NO rests")
    print("at the NO touch (earns spread); TAKER_NO crosses. +EV at the cheap UP tail (0.02-0.20) => the")
    print("soft-market longshot edge ALSO lives in 15m crypto; ~0/negative => efficient corner confirmed.")


if __name__ == "__main__":
    main()
