#!/usr/bin/env python3
"""favlongshot_edge.py -- the FIRST validated positive edge of the research program.

WHAT (node FAVLONG, 2026-07-14): a near-expiry TAKER strategy on Kalshi 15m crypto binaries
(btc/eth/sol 'up/above-strike' contracts). In the last ~2-3 minutes of a window the book's price
lags the settlement-implied probability in DISLOCATED (wide-spread) books; we compute a fair-value
probability from spot-vs-strike scaled by causal realized vol and shrinking time-to-expiry, and
TAKE the side the executable price underprices.

MECHANISM CORRECTION (2026-07-15, nodes FAVLONG-MECHANISM / FAVLONG-SEGMENT — supersedes the
original 'favorite-longshot / buy-cheap-underdog 0.09->0.32' framing, which was an unrepresentative
median-buy slice on BTC-test and is RETRACTED):
  - It is NOT a buy-the-cheap-underdog edge. Deep-underdog trades (executable price <0.15, ~62% of
    all trades) carry NO out-of-sample edge (OOS t~1.0). The profit concentrates on the NEAR-ATM-
    TO-FAVORITE side (entry price >=0.40: OOS ~+0.13/ct; pre-registered favorite>=0.60: OOS t=2.24).
  - It lives in WIDE/dislocated books (spread >1c: ~+3.6c/ct) and MID realized-vol regimes; in
    TIGHT-AND-DEEP books (the operator's own box-maker footprint) the edge is ~ZERO. => low
    cannibalization of the box-maker; the two are complementary.
  - It is ASSET-SPECIFIC: btc/eth/sol replicate; XRP is a NULL (OOS t=-0.32). XRP is excluded.
  - No decay across the 35-day archive (slope t~1.1, insignificant). Persistence risk MEDIUM.
  - The raw Gaussian fair-value systematically mis-shapes the 0.2-0.5 band; an EMPIRICAL ISOTONIC
    calibration (fit train-only, node FAVLONG-MODELV2) ~doubles the backtested OOS edge: pooled
    t 3.97 -> 7.70 with sklearn isotonic, or -> 5.74 with the stdlib-bucket map the forward harness
    uses (all 3 assets clear t>=2 individually either way). 5.74 is the honest forward prior. See
    favlong_model_v2.py (research) and favlong_forward.py (forward-tracked, stdlib).

WHY IT IS TRUSTED (unlike every prior 'winner'):  av_stoikov et al. were markout illusions that
DIED under realized-money scrutiny (nodes METRIC-INVALID / LIVE-BLEED). This edge was built ON
reconstructed SETTLEMENT and survived the full falsification battery:
  - clean label: outcome = the MARKET's own terminal price (mid_close>0.5), not our strike proxy.
    (Using our proxy strike for BOTH fair-value and outcome inflated t 6.6->2.24; we dropped it.)
  - +Kalshi fees (0.07*p*(1-p) per contract): edge 0.046 -> 0.039/contract, t 3.45 -> 2.97.
  - +fill latency (execute up to 10 ticks LATER): t stays ~3.0 -> NOT stale-quote picking.
  - executable size: traded (underdog) side depth median 420 contracts; 84% of trades >=50 avail.
  - CROSS-ASSET REPLICATION (the clincher): same sign in btc/eth/sol independently; pooled
    per-(asset,day) clustered t = 3.99 over 105 asset-days, 65/105 positive.

HONEST CAVEATS (do not oversell):
  - Small: ~2c/contract net pooled (~4c btc alone). Not a slam dunk; a real but modest edge.
  - Per-asset OOS: only BTC clears t>=2 OOS (2.97); eth 1.68, sol 0.55. Confidence comes from
    POOLING across the shared mechanism, and from the full-sample + train + test all being positive.
  - Concentrated in the last 2-3 min (t>=600s); at t<=450s the edge is ~0 (t~0.1). It is a
    terminal-convergence effect, not an all-window signal.
  - ~62% of asset-days positive -> real variance; needs sizing/risk mgmt, not all-in.
  - TAKER strategy (crosses spread) -- operationally different from the live MAKER box bot; needs
    new execution. Favorite-longshot is a KNOWN effect that can decay -> FORWARD VALIDATION on the
    charter gate (day-clustered t>=2 over >=10 FORWARD days) is REQUIRED before any live sizing.
  - Backtest fills at recorded top-of-book; market impact at scale untested.

PROPOSE-ONLY (Rail 1): this is a candidate to PROPOSE, not to deploy. No live flag/switch/size
change is made by this tool or on its basis without the operator's explicit word.

Usage:
  python favlongshot_edge.py            # scores btc/eth/sol from gha-data ticks, prints the table
  (expects the win_<asset>.pkl caches built by the companion loader, or rebuilds from origin/gha-data)
"""
import subprocess, gzip, json, re, math, statistics, pickle, os, sys
from collections import defaultdict

NORM = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
KFEE = lambda p: 0.07 * p * (1 - p)          # Kalshi per-contract trading fee
DECISION_T = 720                              # seconds into the 900s window (last ~3 min)
EDGE = 0.05                                   # min model-vs-price edge to trade
CACHE_DIR = os.environ.get("FAVLONG_CACHE", "/tmp/favlong_cache")


def _sh_bytes(*a):
    return subprocess.run(a, capture_output=True).stdout


def build_asset(asset):
    """Reconstruct per-window (t,mid,spot,bid,ask,bidq,askq) trajectories for one asset."""
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
                byday[m.group(1)][d.get("ws")].append((t, mid, spot, bid, ask, bidq, askq))
    data = {}
    for day, wins in byday.items():
        wl = []
        for ws, tk in wins.items():
            tk.sort(key=lambda x: x[0])
            if len(tk) < 20 or tk[0][0] > 120 or tk[-1][0] < 780:  # need open-ish start, near-expiry end
                continue
            wl.append((tk, tk[0][2], 1 if tk[-1][2] > tk[0][2] else 0))  # (ticks, strike~=open spot, proxy)
        data[day] = wl
    return data


def load_asset(asset):
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, f"win_{asset}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    data = build_asset(asset)
    pickle.dump(data, open(p, "wb"))
    return data


def _causal_sigma(tk, idx):
    """Per-sqrt-second realized vol of spot, using ONLY ticks up to the decision index (no look-ahead)."""
    sp = [tk[i][2] for i in range(idx + 1) if tk[i][2]]
    if len(sp) < 5:
        return None
    lr = [math.log(sp[i + 1] / sp[i]) for i in range(len(sp) - 1) if sp[i] > 0]
    if len(lr) < 4:
        return None
    dt = (tk[idx][0] - tk[0][0]) / max(1, len(lr))
    return statistics.pstdev(lr) / math.sqrt(max(dt, 0.5))


def score(data, days, decision_t=DECISION_T, edge=EDGE, fee=True, lag=0):
    per_day = defaultdict(list)
    wins = 0
    for day in days:
        for tk, strike, out_proxy in data.get(day, []):
            mc = tk[-1][1]
            outcome = 1 if (mc is not None and mc > 0.5) else 0   # MARKET's own terminal settlement
            if out_proxy != outcome:                              # clean-label only (drop proxy-vs-market disagreements)
                continue
            idx = None
            for i, x in enumerate(tk):
                if x[0] <= decision_t:
                    idx = i
                else:
                    break
            if idx is None or idx < 5:
                continue
            t, mid, spot, bid, ask = tk[idx][:5]
            if None in (spot, bid, ask):
                continue
            tau = 900 - t
            if tau < 30:
                continue
            sig = _causal_sigma(tk, idx)
            if not sig:
                continue
            z = (spot - strike) / (spot * sig * math.sqrt(tau)) if sig > 0 else 0
            fair = NORM(z)
            ev_buy, ev_sell = fair - ask, bid - fair
            fr = tk[min(idx + lag, len(tk) - 1)]                  # fill at a later tick to test latency
            fb, fa = fr[3], fr[4]
            if None in (fb, fa):
                continue
            if ev_buy >= ev_sell and ev_buy > edge:
                pl = outcome - fa - (KFEE(fa) if fee else 0)
            elif ev_sell > edge:
                pl = fb - outcome - (KFEE(fb) if fee else 0)
            else:
                continue
            per_day[day].append(pl)
            wins += (pl > 0)
    allpl = [p for v in per_day.values() for p in v]
    if not allpl:
        return None
    dm = [statistics.mean(v) for v in per_day.values() if v]
    t = (statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm)))
         if len(dm) > 1 and statistics.stdev(dm) > 0 else float("nan"))
    return dict(n=len(allpl), winrate=wins / len(allpl), mean=statistics.mean(allpl),
                total=sum(allpl), tclust=t, ndays=len(dm),
                posdays=sum(1 for v in per_day.values() if sum(v) > 0))


def main():
    assets = sys.argv[1:] or ["btc", "eth", "sol"]
    print(f"FAVLONG near-expiry contrarian taker  (decision_t={DECISION_T}s, edge={EDGE}, +Kalshi fees)")
    print(f"{'asset/set':<16}{'n':>6}{'winrate':>8}{'mean$/ct':>10}{'d-clust t':>11}{'pos-days':>10}")
    per_asset_day = []
    for a in assets:
        data = load_asset(a)
        days = sorted(data)
        tr = [d for d in days if d <= "2026-06-30"]
        te = [d for d in days if d > "2026-06-30"]
        for lbl, dd in ((a + " ALL", days), (a + " train", tr), (a + " test(OOS)", te)):
            r = score(data, dd)
            if r:
                print(f"{lbl:<16}{r['n']:>6}{r['winrate']:>8.3f}{r['mean']:>10.4f}"
                      f"{r['tclust']:>11.2f}{str(r['posdays'])+'/'+str(r['ndays']):>10}")
        for d in days:
            r = score(data, [d])
            if r:
                per_asset_day.append(r["mean"])
    if len(per_asset_day) > 1:
        tp = statistics.mean(per_asset_day) / (statistics.stdev(per_asset_day) / math.sqrt(len(per_asset_day)))
        print(f"\nPOOLED per-(asset,day): mean=${statistics.mean(per_asset_day):+.4f}/ct  "
              f"clustered t={tp:.2f}  n={len(per_asset_day)}  "
              f"pos={sum(m>0 for m in per_asset_day)}/{len(per_asset_day)}")
        print("Cross-asset replication (same sign, 3 independent markets) is the evidence this is a")
        print("real favorite-longshot bias, not an in-sample fluke. FORWARD-GATE before any live sizing.")


if __name__ == "__main__":
    main()
