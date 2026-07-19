#!/usr/bin/env python3
"""crossasset_edge.py -- EXO cross-asset LEAD-LAG test (node EXO-XASSET, 2026-07-15).

HYPOTHESIS: BTC leads the alts. Does BTC's recent EXOGENOUS spot move near expiry predict the
ETH/SOL 15m binary's terminal outcome BEYOND the alt's own market mid? If the alt book lags BTC by
2-3 min, sign(BTC_return) predicts (alt_outcome - alt_mid) and a taker overlay clears fees.

NULL (efficient): ETH/SOL spot tracks BTC within seconds via arbitrage, so the alt mid already
embeds BTC's move; BTC's 2-min-ago return carries no residual signal for the alt binary.

DISCIPLINE (same as EXO-MOM): market-settlement label (final alt mid>0.5), NO strike proxy, NO
outcome-based window dropping; causal predictor; ONE pre-registered signal (BTC log-return over a
fixed lookback) + a small FIXED threshold set reported in full (no per-target cherry-pick); day-
clustered t; +Kalshi fees. Windows aligned by shared ws (15m boundaries are common across assets).
Also reports the reverse (alt->BTC) as a falsification control.
"""
import subprocess, gzip, json, re, math, statistics, os, sys, pickle
from collections import defaultdict

KFEE = lambda p: 0.07 * p * (1 - p)
DECISION_T = 720
CACHE_DIR = os.environ.get("FAVLONG_CACHE", "/tmp/favlong_cache")


def _sh_bytes(*a):
    return subprocess.run(a, capture_output=True).stdout


def build_asset(asset):
    """{ws: {'day','ticks':[(t,mid,spot,bid,ask)],'outcome'}} for one asset, keyed by window start."""
    files = [f for f in subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "origin/gha-data"],
        capture_output=True, text=True).stdout.splitlines()
        if f"ticks_kalshi_{asset}15m" in f]
    byday = defaultdict(lambda: defaultdict(list))
    dayof = {}
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
            ws = d.get("ws")
            if ws is None:
                continue
            for tk in d.get("ticks", []):
                if len(tk) < 8:
                    continue
                t, mid, spot, micro, bid, bidq, ask, askq = (tk + [None] * 8)[:8]
                byday[ws][d.get("ws")]  # noop to keep structure simple
                byday[ws]["t"].append((t, mid, spot, bid, ask))
            dayof[ws] = m.group(1)
    out = {}
    for ws, dd in byday.items():
        tk = sorted(dd["t"], key=lambda x: x[0])
        if len(tk) < 20 or tk[0][0] > 120 or tk[-1][0] < 780:
            continue
        mc = tk[-1][1]
        if mc is None:
            continue
        out[int(ws)] = dict(day=dayof[ws], ticks=tk, outcome=1 if mc > 0.5 else 0)
    return out


def load(asset):
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, f"xa_{asset}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    d = build_asset(asset)
    pickle.dump(d, open(p, "wb"))
    return d


def _dec(tk):
    idx = None
    for i, x in enumerate(tk):
        if x[0] <= DECISION_T:
            idx = i
        else:
            break
    return idx


def _spot_ret(tk, idx, sec):
    """causal log-return of spot over the last `sec` up to idx."""
    t_dec = tk[idx][0]
    s1 = tk[idx][2]
    s0 = None
    for i in range(idx + 1):
        if tk[i][0] <= t_dec - sec and tk[i][2]:
            s0 = tk[i][2]
    if s0 and s0 > 0 and s1 and s1 > 0:
        return math.log(s1 / s0)
    return None


def run(leader, target, sec, thresholds, fee=True):
    """leader spot move -> trade target binary. Returns dict of threshold -> (train,test) t."""
    L = load(leader)
    T = load(target)
    common = sorted(set(L) & set(T))
    # per-target-window: leader ret at same ws, target mid/ask/bid/outcome at its decision
    rows = []   # (day, lead_ret, mid, ask, bid, outcome)
    for ws in common:
        lt = L[ws]["ticks"]
        tt = T[ws]["ticks"]
        li, ti = _dec(lt), _dec(tt)
        if li is None or li < 5 or ti is None or ti < 5:
            continue
        lr = _spot_ret(lt, li, sec)
        if lr is None:
            continue
        mid, spot, bid, ask = tt[ti][1], tt[ti][2], tt[ti][3], tt[ti][4]
        if None in (mid, bid, ask):
            continue
        rows.append((T[ws]["day"], lr, mid, ask, bid, T[ws]["outcome"]))
    res = {}
    for thr in thresholds:
        for split, pred in (("train", lambda d: d <= "2026-06-30"),
                            ("test", lambda d: d > "2026-06-30")):
            per_day = defaultdict(list)
            for day, lr, mid, ask, bid, outcome in rows:
                if not pred(day) or abs(lr) < thr:
                    continue
                if lr > 0:
                    pl = outcome - ask - (KFEE(ask) if fee else 0)
                else:
                    pl = bid - outcome - (KFEE(bid) if fee else 0)
                per_day[day].append(pl)
            dm = [statistics.mean(v) for v in per_day.values() if v]
            if len(dm) > 1 and statistics.stdev(dm) > 0:
                t = statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm)))
                res[(thr, split)] = (t, statistics.mean(dm) if dm else float('nan'),
                                     sum(len(v) for v in per_day.values()))
            else:
                res[(thr, split)] = (float('nan'), float('nan'), 0)
    return res


def residual(leader, target, sec):
    """gross sign(lead_ret)*(outcome-mid), pooled day-clustered t, train/test."""
    L, T = load(leader), load(target)
    common = sorted(set(L) & set(T))
    out = {}
    for split, pred in (("train", lambda d: d <= "2026-06-30"), ("test", lambda d: d > "2026-06-30")):
        per_day = defaultdict(list)
        for ws in common:
            lt, tt = L[ws]["ticks"], T[ws]["ticks"]
            li, ti = _dec(lt), _dec(tt)
            if li is None or li < 5 or ti is None or ti < 5:
                continue
            lr = _spot_ret(lt, li, sec)
            if lr is None or lr == 0:
                continue
            day = T[ws]["day"]
            if not pred(day):
                continue
            per_day[day].append((1 if lr > 0 else -1) * (T[ws]["outcome"] - tt[ti][1]))
        dm = [statistics.mean(v) for v in per_day.values() if v]
        if len(dm) > 1 and statistics.stdev(dm) > 0:
            out[split] = statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm)))
        else:
            out[split] = float('nan')
    return out


def main():
    sec = 120
    print(f"EXO-XASSET cross-asset lead-lag  (leader spot ret over {sec}s -> trade target binary)\n")
    pairs = [("btc", "eth"), ("btc", "sol"), ("eth", "btc"), ("sol", "btc")]  # last two = controls
    print("== RESIDUAL (gross, no cost): pooled day-clustered t of sign(lead_ret)*(outcome-mid) ==")
    print(f"{'leader->target':<18}{'train t':>10}{'test t':>10}")
    for lead, tgt in pairs:
        r = residual(lead, tgt, sec)
        tag = "  (control)" if lead != "btc" else ""
        print(f"{lead+'->'+tgt:<18}{r['train']:>10.2f}{r['test']:>10.2f}{tag}")
    print("\n== TRADEABLE (net Kalshi fees): fixed thresholds, train AND test day-clustered t ==")
    thr = [0.0, 0.0005, 0.001, 0.002]
    print(f"{'leader->target':<18}{'thr':>8}{'train t':>10}{'test t':>10}{'test mean$':>12}{'test n':>8}")
    for lead, tgt in pairs[:2]:
        res = run(lead, tgt, sec, thr)
        for th in thr:
            trt = res[(th, "train")][0]
            tet, tem, ten = res[(th, "test")]
            print(f"{lead+'->'+tgt:<18}{th:>8}{trt:>10.2f}{tet:>10.2f}{tem:>12.5f}{ten:>8}")


if __name__ == "__main__":
    main()
