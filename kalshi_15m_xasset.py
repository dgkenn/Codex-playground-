#!/usr/bin/env python3
"""
Cross-asset lead-lag / relative-value taker test on Kalshi 15-min crypto binaries.

GOAL: Does BTC's UP-binary move (or BTC spot return) over [t-d, t] predict the
LAGGARD (XRP/SOL/ETH) UP-binary move over [t, t+d] and/or its resolved_up,
INCREMENTAL to the laggard's OWN current mid? If yes, can a TAKER cross the
laggard's spread profitably net of fee + spread, held to settlement?

ARTIFACT DISCIPLINE (the project's two prior traps):
  - 60s candle-timing artifact: the predictor is STRICTLY LAGGED vs the target
    (BTC info measured at t-d, used to predict laggard change from t onward); no
    look-ahead, predictor is stale relative to the response.
  - time-in-band / pooled-tick autocorrelation artifact: ONE observation per
    window at each fixed decision time t; significance is WINDOW-CLUSTERED
    (each window = one independent draw). Never pool intra-window ticks.

Reads raw ticks straight from git branch origin/gha-data. No API.
ticks line: {"ws":epoch,"role":"up","ticks":[[t_rel, mid, spot, ?, bid, bid_sz, ask, ask_sz],...]}
shadow line: {"ws":epoch,"resolved_up":0/1,...}
"""
import json, subprocess, sys, math
from collections import defaultdict
import numpy as np

BRANCH = "origin/gha-data"
ASSETS = ["btc", "eth", "sol", "xrp"]
WIN = 900.0  # 15 min in seconds
# decision times (seconds into the 15m window) and the lead-lag horizon delta
DECISION_TS = [300.0, 450.0, 600.0]
DELTA = 60.0  # seconds; predictor measured over [t-DELTA, t], response over [t, t+DELTA]
KALSHI_FEE_M = 0.07  # taker fee = M * p * (1-p) per contract (price in dollars)


def git_ls(pattern):
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", BRANCH],
                         capture_output=True, text=True, cwd=REPO).stdout
    return [l for l in out.splitlines() if pattern in l]


def read_gz_jsonl(path):
    p = subprocess.run(f"git show {BRANCH}:{path} | zcat", shell=True,
                       capture_output=True, text=True, cwd=REPO)
    for line in p.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except Exception:
                pass


def read_jsonl(path):
    p = subprocess.run(["git", "show", f"{BRANCH}:{path}"],
                       capture_output=True, text=True, cwd=REPO)
    for line in p.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except Exception:
                pass


REPO = sys.argv[1] if len(sys.argv) > 1 else "/tmp/xa"


def load_asset(asset):
    """Return {ws: {'ticks':[(t,mid,spot,bid,ask,bidsz,asksz)...sorted], 'res':0/1}}."""
    tick_files = git_ls(f"ticks_kalshi_{asset}15m")
    shadow_files = git_ls(f"shadow_windows_kalshi_{asset}15m")
    res = {}
    for f in shadow_files:
        for d in read_jsonl(f):
            ws = d.get("ws")
            ru = d.get("resolved_up")
            if ws is not None and ru is not None:
                res[ws] = int(ru)
    raw = defaultdict(list)
    for f in tick_files:
        for d in read_gz_jsonl(f):
            ws = d.get("ws")
            if ws is None:
                continue
            for tk in d.get("ticks", []):
                # [t_rel, mid, spot, ?, bid, bid_sz, ask, ask_sz]
                if len(tk) < 8:
                    continue
                t, mid, spot, _, bid, bidsz, ask, asksz = tk[:8]
                raw[ws].append((t, mid, spot, bid, ask, bidsz, asksz))
    out = {}
    for ws, lst in raw.items():
        if ws not in res:
            continue
        lst.sort(key=lambda x: x[0])
        out[ws] = {"ticks": lst, "res": res[ws]}
    return out


def step_at(ticks, t, idx):
    """Last tick value at or before time t (step function = no look-ahead).
    idx selects field: 1=mid,2=spot,3=bid,4=ask,5=bidsz,6=asksz. Returns None if none<=t."""
    lo, hi, best = 0, len(ticks) - 1, None
    if not ticks or ticks[0][0] > t:
        return None
    while lo <= hi:
        m = (lo + hi) // 2
        if ticks[m][0] <= t:
            best = ticks[m]
            lo = m + 1
        else:
            hi = m - 1
    return best[idx] if best is not None else None


def hac_ols(y, X, names, maxlag=0):
    """OLS with HC0 (window obs already independent; we report HC0 robust SEs).
    Returns dict name->(coef, se, t). One obs/window => no clustering needed beyond robust."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, k = X.shape
    XtX = X.T @ X
    XtXi = np.linalg.pinv(XtX)
    beta = XtXi @ (X.T @ y)
    resid = y - X @ beta
    # HC0 robust (White) sandwich
    S = (X * resid[:, None])
    meat = S.T @ S
    cov = XtXi @ meat @ XtXi
    se = np.sqrt(np.maximum(np.diag(cov), 0))
    res = {}
    for i, nm in enumerate(names):
        tstat = beta[i] / se[i] if se[i] > 0 else 0.0
        res[nm] = (beta[i], se[i], tstat)
    return res, beta, resid


def main():
    print("Loading assets from git (this reads ~1320 gz files)...", file=sys.stderr)
    data = {}
    for a in ASSETS:
        data[a] = load_asset(a)
        print(f"  {a}: {len(data[a])} resolved windows", file=sys.stderr)

    btc = data["btc"]
    report = {"decision_ts": DECISION_TS, "delta": DELTA}
    report["coverage"] = {a: len(data[a]) for a in ASSETS}

    leadlag = {}
    taker = {}
    for target in ["eth", "sol", "xrp"]:
        tgt = data[target]
        common = sorted(set(btc) & set(tgt))
        leadlag[target] = {}
        taker[target] = {}
        for t in DECISION_TS:
            rows = []  # one per window
            for ws in common:
                bt = btc[ws]["ticks"]
                tt = tgt[ws]["ticks"]
                # BTC predictor measured STRICTLY before t: BTC binary-mid change & spot ret over [t-DELTA, t]
                b_mid_t = step_at(bt, t, 1)
                b_mid_tm = step_at(bt, t - DELTA, 1)
                b_spot_t = step_at(bt, t, 2)
                b_spot_tm = step_at(bt, t - DELTA, 2)
                # target current mid at t (the thing already priced); response = target mid change [t, t+DELTA]
                g_mid_t = step_at(tt, t, 1)
                g_mid_fut = step_at(tt, t + DELTA, 1)
                g_spot_t = step_at(tt, t, 2)
                g_spot_tm = step_at(tt, t - DELTA, 2)
                g_bid = step_at(tt, t, 3)
                g_ask = step_at(tt, t, 4)
                g_bidsz = step_at(tt, t, 5)
                g_asksz = step_at(tt, t, 6)
                ru = tgt[ws]["res"]
                if None in (b_mid_t, b_mid_tm, b_spot_t, b_spot_tm, g_mid_t,
                            g_mid_fut, g_spot_t, g_spot_tm, g_bid, g_ask):
                    continue
                if b_spot_tm <= 0 or g_spot_tm <= 0:
                    continue
                d_b_mid = b_mid_t - b_mid_tm                      # BTC binary move (lagged predictor)
                b_spot_ret = (b_spot_t / b_spot_tm) - 1.0         # BTC spot ret (lagged predictor)
                g_spot_ret = (g_spot_t / g_spot_tm) - 1.0         # target own spot ret (control)
                d_g_mid_fut = g_mid_fut - g_mid_t                 # target future binary move (response)
                rows.append(dict(ws=ws, d_b_mid=d_b_mid, b_spot_ret=b_spot_ret,
                                 g_spot_ret=g_spot_ret, g_mid_t=g_mid_t,
                                 d_g_mid_fut=d_g_mid_fut, ru=ru,
                                 g_bid=g_bid, g_ask=g_ask, g_bidsz=g_bidsz, g_asksz=g_asksz))
            n = len(rows)
            if n < 30:
                leadlag[target][t] = {"n": n, "note": "too few"}
                continue
            ws_arr = np.array([r["ws"] for r in rows])
            d_b_mid = np.array([r["d_b_mid"] for r in rows])
            b_spot_ret = np.array([r["b_spot_ret"] for r in rows])
            g_spot_ret = np.array([r["g_spot_ret"] for r in rows])
            g_mid_t = np.array([r["g_mid_t"] for r in rows])
            d_g_mid_fut = np.array([r["d_g_mid_fut"] for r in rows])
            ru = np.array([r["ru"] for r in rows], float)

            # standardize predictors for comparable coefs
            def z(x):
                s = x.std()
                return (x - x.mean()) / s if s > 0 else x * 0.0

            # ---- Test A: does lagged BTC binary move predict target FUTURE binary move,
            #              incremental to target current mid? (one obs/window, HC robust) ----
            X = np.column_stack([np.ones(n), z(d_b_mid), z(b_spot_ret), z(g_spot_ret), g_mid_t])
            resA, _, _ = hac_ols(d_g_mid_fut, X,
                                 ["const", "btc_binmove", "btc_spotret", "own_spotret", "own_mid"])

            # ---- Test B: does lagged BTC binary move predict target RESOLVED_UP,
            #              incremental to target current mid? (LPM, one obs/window) ----
            X2 = np.column_stack([np.ones(n), z(d_b_mid), z(b_spot_ret), g_mid_t])
            resB, _, _ = hac_ols(ru, X2, ["const", "btc_binmove", "btc_spotret", "own_mid"])

            leadlag[target][t] = {
                "n": n,
                "A_future_binmove": {k: [round(v[0], 5), round(v[1], 5), round(v[2], 3)]
                                     for k, v in resA.items()},
                "B_resolved_up": {k: [round(v[0], 5), round(v[1], 5), round(v[2], 3)]
                                  for k, v in resB.items()},
            }

            # ---- Taker sim: use lagged BTC signal to pick a side, cross the laggard spread,
            #      hold to settlement. Net = payoff - entry - fee. Window-clustered CI. ----
            # Fair-shift direction: sign of BTC binary move (lagged). If BTC moved up beyond
            # threshold and target hasn't kept up, BUY target YES at ask; if down, BUY NO at 1-bid.
            # We use a simple threshold on standardized lagged BTC binary move.
            g_bid = np.array([r["g_bid"] for r in rows])
            g_ask = np.array([r["g_ask"] for r in rows])
            g_bidsz = np.array([r["g_bidsz"] for r in rows])
            g_asksz = np.array([r["g_asksz"] for r in rows])
            zb = z(d_b_mid)
            for thr in [0.0, 0.5, 1.0]:
                pnl = []
                caps = []
                for i in range(n):
                    sig = zb[i]
                    if abs(sig) < thr:
                        continue
                    if sig > 0:  # BTC up -> buy target YES at ask
                        entry = g_ask[i]
                        payoff = ru[i]  # YES pays 1 if up
                        cap = g_asksz[i]
                    else:        # BTC down -> buy target NO at (1 - bid)
                        entry = 1.0 - g_bid[i]
                        payoff = 1.0 - ru[i]
                        cap = g_bidsz[i]
                    if entry <= 0 or entry >= 1:
                        continue
                    fee = KALSHI_FEE_M * entry * (1.0 - entry)
                    pnl.append(payoff - entry - fee)
                    caps.append(cap if cap is not None else 0.0)
                if len(pnl) >= 20:
                    pnl = np.array(pnl)
                    mean = pnl.mean()
                    se = pnl.std(ddof=1) / math.sqrt(len(pnl))
                    taker[target].setdefault(t, {})[f"thr{thr}"] = {
                        "n_trades": len(pnl),
                        "net_cents": round(mean * 100, 3),
                        "ci95_cents": [round((mean - 1.96 * se) * 100, 3),
                                       round((mean + 1.96 * se) * 100, 3)],
                        "t": round(mean / se, 2) if se > 0 else 0.0,
                        "med_cap": round(float(np.median(caps)), 1),
                    }

    # ---- OOS time-split taker check on the best-looking (thr) config ----
    oos = {}
    for target in ["eth", "sol", "xrp"]:
        tgt = data[target]
        common = sorted(set(btc) & set(tgt))
        # chronological split by ws
        split = common[int(0.6 * len(common))] if common else None
        for t in DECISION_TS:
            tr_pnl, te_pnl = [], []
            for ws in common:
                bt = btc[ws]["ticks"]; tt = tgt[ws]["ticks"]
                b_mid_t = step_at(bt, t, 1); b_mid_tm = step_at(bt, t - DELTA, 1)
                g_ask = step_at(tt, t, 4); g_bid = step_at(tt, t, 3)
                ru = tgt[ws]["res"]
                if None in (b_mid_t, b_mid_tm, g_ask, g_bid):
                    continue
                sig = b_mid_t - b_mid_tm
                if abs(sig) < 0.01:  # ~1c BTC binary move gate
                    continue
                if sig > 0:
                    entry = g_ask; payoff = ru
                else:
                    entry = 1.0 - g_bid; payoff = 1.0 - ru
                if entry <= 0 or entry >= 1:
                    continue
                fee = KALSHI_FEE_M * entry * (1 - entry)
                val = payoff - entry - fee
                (tr_pnl if ws < split else te_pnl).append(val)
            def summ(p):
                if len(p) < 10:
                    return {"n": len(p)}
                p = np.array(p); se = p.std(ddof=1) / math.sqrt(len(p))
                return {"n": len(p), "net_cents": round(p.mean() * 100, 3),
                        "t": round(p.mean() / se, 2) if se > 0 else 0.0}
            oos.setdefault(target, {})[t] = {"IS": summ(tr_pnl), "OOS": summ(te_pnl)}

    out = {"meta": report, "leadlag": leadlag, "taker": taker, "oos": oos}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
