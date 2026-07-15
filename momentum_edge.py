#!/usr/bin/env python3
"""momentum_edge.py -- EXOGENOUS-SIGNAL test (node EXO-MOM, 2026-07-15).

HYPOTHESIS (operator-chosen new domain): does recent EXOGENOUS spot momentum near expiry
predict the Kalshi 15m binary's terminal outcome BEYOND what the market price already reflects?
FAVLONG's fair value assumed ZERO drift (martingale). If short-horizon spot order-flow has
un-priced continuation, then the residual (outcome - market_mid) at the decision instant should
be predictable from recent spot return -- a directional taker overlay the book is missing.

EFFICIENT-MARKET NULL: at a ~2-3 min horizon spot is ~a martingale and the mid already prices
any drift, so cov(recent_return, outcome - mid) ~ 0 and any tradeable version dies after fees.

DISCIPLINE (learned from FAVLONG double-artifact):
  - LABEL = market's own terminal settlement (mid_close > 0.5). NO strike proxy anywhere
    (the proxy-strike misspecification was artifact #2). NO clean-label filter (artifact #1) --
    every window with usable ticks is scored, no outcome-dependent dropping.
  - Predictor uses ONLY ticks up to the decision index (causal, no look-ahead).
  - Threshold/horizon SELECTED on TRAIN, evaluated on TEST exactly once.
  - Day-clustered t; +Kalshi fees for the tradeable P&L.

Two reported statistics:
  (A) RESIDUAL predictability (no trading, no fee): pooled day-clustered t of
      corr-style signal = mean over windows of sign(ret)*(outcome - mid). >0 means momentum
      leads the mid. This is the cleanest 'is there un-priced drift' test.
  (B) TRADEABLE overlay: bet the binary in the direction of recent spot move when |ret| exceeds
      a train-selected threshold; P&L = outcome - ask - fee (buy) or bid - outcome - fee (sell).
      Net of Kalshi fees. This is what actually matters for deployment.
"""
import subprocess, gzip, json, re, math, statistics, os, sys
from collections import defaultdict

KFEE = lambda p: 0.07 * p * (1 - p)
DECISION_T = 720
CACHE_DIR = os.environ.get("FAVLONG_CACHE", "/tmp/favlong_cache")


def _sh_bytes(*a):
    return subprocess.run(a, capture_output=True).stdout


def build_asset(asset):
    """Per-window trajectories: list of tick tuples (t,mid,spot,micro,bid,bidq,ask,askq)."""
    files = [f for f in subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "origin/gha-data"],
        capture_output=True, text=True).stdout.splitlines()
        if f"ticks_kalshi_{asset}15m" in f]
    byday = defaultdict(lambda: defaultdict(list))
    for f in files:
        m = re.search(r"(2026-\d\d-\d\d)", f)
        if not m:
            continue
        try:
            txt = gzip.decompress(_sh_bytes("git", "show", f"origin/gha-data:{f}")).decode()
        except Exception:
            continue
        for l in txt.splitlines():
            try:
                d = json.loads(l)
            except Exception:
                continue
            for tk in d.get("ticks", []):
                if len(tk) < 8:
                    continue
                t, mid, spot, micro, bid, bidq, ask, askq = (tk + [None] * 8)[:8]
                byday[m.group(1)][d.get("ws")].append((t, mid, spot, micro, bid, ask))
    data = {}
    for day, wins in byday.items():
        wl = []
        for ws, tk in wins.items():
            tk.sort(key=lambda x: x[0])
            if len(tk) < 20 or tk[0][0] > 120 or tk[-1][0] < 780:
                continue
            wl.append(tk)
        data[day] = wl
    return data


def _spot_at(tk, target_t, upto_idx):
    """Spot at the last tick with t <= target_t, searching only up to upto_idx (causal)."""
    best = None
    for i in range(upto_idx + 1):
        if tk[i][0] <= target_t and tk[i][2]:
            best = tk[i][2]
    return best


def features(tk, decision_t=DECISION_T):
    """Causal predictors at the decision index. Returns (mid, ask, bid, outcome, feats) or None."""
    idx = None
    for i, x in enumerate(tk):
        if x[0] <= decision_t:
            idx = i
        else:
            break
    if idx is None or idx < 5:
        return None
    t, mid, spot, micro, bid, ask = tk[idx]
    if None in (mid, spot, bid, ask):
        return None
    mc = tk[-1][1]
    if mc is None:
        return None
    outcome = 1 if mc > 0.5 else 0                      # market's own terminal settlement
    feats = {}
    for lbl, sec in (("ret1m", 60), ("ret2m", 120), ("ret3m", 180), ("ret5m", 300)):
        s0 = _spot_at(tk, decision_t - sec, idx)
        if s0 and s0 > 0 and spot > 0:
            feats[lbl] = math.log(spot / s0)
        else:
            feats[lbl] = None
    feats["micro_dev"] = (micro - mid) if (micro is not None) else None   # book lean
    return mid, ask, bid, outcome, feats


def residual_stat(data, days, feat, decision_t=DECISION_T):
    """(A) Does sign(feat) align with (outcome - mid)? day-clustered t, no trading."""
    per_day = defaultdict(list)
    for day in days:
        for tk in data.get(day, []):
            r = features(tk, decision_t)
            if not r:
                continue
            mid, ask, bid, outcome, fs = r
            v = fs.get(feat)
            if v is None or v == 0:
                continue
            per_day[day].append((1 if v > 0 else -1) * (outcome - mid))
    dm = [statistics.mean(v) for v in per_day.values() if v]
    if len(dm) < 2:
        return None
    n = sum(len(v) for v in per_day.values())
    sd = statistics.stdev(dm)
    t = statistics.mean(dm) / (sd / math.sqrt(len(dm))) if sd > 0 else float("nan")
    return dict(n=n, ndays=len(dm), mean=statistics.mean(dm), tclust=t)


def trade_stat(data, days, feat, thresh, decision_t=DECISION_T, fee=True):
    """(B) Directional overlay: bet with recent spot move when |feat|>=thresh. Net Kalshi fees."""
    per_day = defaultdict(list)
    wins = 0
    for day in days:
        for tk in data.get(day, []):
            r = features(tk, decision_t)
            if not r:
                continue
            mid, ask, bid, outcome, fs = r
            v = fs.get(feat)
            if v is None or abs(v) < thresh:
                continue
            if v > 0:                                   # momentum up -> buy YES
                pl = outcome - ask - (KFEE(ask) if fee else 0)
            else:                                       # momentum down -> sell YES (buy NO)
                pl = bid - outcome - (KFEE(bid) if fee else 0)
            per_day[day].append(pl)
            wins += (pl > 0)
    allpl = [p for v in per_day.values() for p in v]
    if not allpl:
        return None
    dm = [statistics.mean(v) for v in per_day.values() if v]
    sd = statistics.stdev(dm) if len(dm) > 1 else 0
    t = statistics.mean(dm) / (sd / math.sqrt(len(dm))) if len(dm) > 1 and sd > 0 else float("nan")
    return dict(n=len(allpl), winrate=wins / len(allpl), mean=statistics.mean(allpl),
                total=sum(allpl), tclust=t, ndays=len(dm),
                posdays=sum(1 for v in per_day.values() if sum(v) > 0))


def main():
    assets = sys.argv[1:] or ["btc", "eth", "sol"]
    print(f"EXO-MOM exogenous-momentum test  (decision_t={DECISION_T}s)\n")
    feats = ["ret1m", "ret2m", "ret3m", "ret5m", "micro_dev"]

    print("== (A) RESIDUAL predictability: pooled day-clustered t of sign(feat)*(outcome-mid) ==")
    print("   (no trading/fees; >0 => momentum leads the mid; efficient-null => ~0)")
    print(f"{'asset':<8}{'set':<8}" + "".join(f"{f:>11}" for f in feats))
    train_pick = defaultdict(dict)
    for a in assets:
        data = load_cached(a)
        days = sorted(data)
        tr = [d for d in days if d <= "2026-06-30"]
        te = [d for d in days if d > "2026-06-30"]
        for lbl, dd in (("train", tr), ("test", te), ("ALL", days)):
            row = f"{a:<8}{lbl:<8}"
            for f in feats:
                r = residual_stat(data, dd, f)
                row += f"{(r['tclust'] if r else float('nan')):>11.2f}"
                if lbl == "train" and r:
                    train_pick[a][f] = r["tclust"]
            print(row)
        print()

    print("== (B) TRADEABLE overlay (net Kalshi fees): TRAIN-select best feat+thresh, TEST once ==")
    print(f"{'asset':<8}{'feat':<10}{'thr':>8}{'set':<7}{'n':>6}{'win':>7}{'mean$':>9}{'d-t':>8}{'posD':>8}")
    pooled_test = []
    for a in assets:
        data = load_cached(a)
        days = sorted(data)
        tr = [d for d in days if d <= "2026-06-30"]
        te = [d for d in days if d > "2026-06-30"]
        # select feat+threshold on TRAIN by pooled tradeable t (n>=30 guard)
        best = None
        for f in feats:
            scale = 1.0 if f == "micro_dev" else 1.0
            for thr in ([0.0, 0.01, 0.02, 0.03, 0.05] if f == "micro_dev"
                        else [0.0, 0.0003, 0.0006, 0.001, 0.0015, 0.002]):
                r = trade_stat(data, tr, f, thr)
                if r and r["n"] >= 30 and (best is None or (r["tclust"] or -9) > best[0]):
                    best = ((r["tclust"] or -9), f, thr, r)
        if not best:
            continue
        _, bf, bthr, btr = best
        rte = trade_stat(data, te, bf, bthr)
        print(f"{a:<8}{bf:<10}{bthr:>8}{'train':<7}{btr['n']:>6}{btr['winrate']:>7.3f}"
              f"{btr['mean']:>9.4f}{btr['tclust']:>8.2f}{str(btr['posdays'])+'/'+str(btr['ndays']):>8}")
        if rte:
            print(f"{'':<8}{'':<10}{'':>8}{'test':<7}{rte['n']:>6}{rte['winrate']:>7.3f}"
                  f"{rte['mean']:>9.4f}{rte['tclust']:>8.2f}{str(rte['posdays'])+'/'+str(rte['ndays']):>8}")
            # collect per-asset-day OOS means for pooling
            for d in te:
                rr = trade_stat(data, [d], bf, bthr)
                if rr:
                    pooled_test.append(rr["mean"])
    if len(pooled_test) > 1:
        tp = statistics.mean(pooled_test) / (statistics.stdev(pooled_test) / math.sqrt(len(pooled_test)))
        print(f"\nPOOLED OOS per-(asset,day): mean=${statistics.mean(pooled_test):+.4f}/ct  "
              f"clustered t={tp:.2f}  n={len(pooled_test)}  "
              f"pos={sum(m>0 for m in pooled_test)}/{len(pooled_test)}")


import pickle
def load_cached(asset):
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, f"mom_{asset}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    data = build_asset(asset)
    pickle.dump(data, open(p, "wb"))
    return data


if __name__ == "__main__":
    main()
