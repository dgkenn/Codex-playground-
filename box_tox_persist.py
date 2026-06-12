#!/usr/bin/env python
"""DEEP DIVE 3: is toxicity PERSISTENT across 15-min windows (time-series/regime structure)?
Per-window metrics -> autocorr (adjacent-only), regime persistence, vol->strand clustering,
UTC-hour structure, and an IS/OOS session-level stand-down gate. COMPACT output only."""
import sys, numpy as np, pandas as pd
from kalshi_sizing import collect_fills
from box_policy_ab import _vpin_buckets, _vpin_at

ASSETS = ["btc", "eth", "sol", "xrp"]

def per_window(asset):
    hist = pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws").sort_index()
    tap = pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws").sort_index()
    fills = collect_fills(hist, tap, 0.0)
    g = fills.groupby("ws").agg(nb=("side", lambda s: int((s == "bid").sum())),
                                na=("side", lambda s: int((s == "ask").sum())),
                                pnl=("settle", "sum"))
    common = sorted(set(hist.index) & set(tap.index))
    rows = []
    for w in common:
        h, t = hist.loc[w], tap.loc[w]
        t_arr = np.asarray(t.t, float); sz = np.asarray(t.sz, float); buy = np.asarray(t.buy, bool)
        bt, bi = _vpin_buckets(t_arr, sz, buy)
        vp = _vpin_at(bt, bi, w + 60 * 7)                       # VPIN at minute 7
        spot = np.asarray(h.spot_path, float); ok = ~np.isnan(spot)
        mvb = abs(spot[ok][-1] / spot[ok][0] - 1) * 1e4 if ok.sum() >= 2 else np.nan
        V = sz.sum()
        fim = abs((sz[buy].sum() - sz[~buy].sum()) / V) if V > 0 else np.nan
        rows.append((w, vp, mvb, fim))
    pw = pd.DataFrame(rows, columns=["ws", "vpin7", "absmove", "fimb"]).set_index("ws")
    pw = pw.join(g, how="left")
    pw[["nb", "na"]] = pw[["nb", "na"]].fillna(0).astype(int)
    pw["pnl"] = pw.pnl.fillna(0.0)
    pw["fills"] = pw.nb + pw.na
    pw["traded"] = pw.fills > 0
    pw["strand"] = pw.traded & (np.minimum(pw.nb, pw.na) == 0)   # hard strand: fully one-sided window
    pw["pair_rate"] = np.where(pw.traded, 2 * np.minimum(pw.nb, pw.na) / pw.fills.clip(lower=1), np.nan)
    pw["asset"] = asset
    return pw.reset_index()

def lag_pairs(pw, col, L, col2=None):
    """values at ws and ws+900L (exact), within asset. Returns (x, y) arrays, NaN-dropped."""
    c2 = col2 or col
    a = pw[["ws", col]].rename(columns={col: "x"})
    b = pw[["ws", c2]].copy(); b["ws"] = b.ws - 900 * L; b = b.rename(columns={c2: "y"})
    m = a.merge(b, on="ws").dropna()
    return m.x.to_numpy(float), m.y.to_numpy(float)

def acorr(x, y):
    if len(x) < 10 or x.std() == 0 or y.std() == 0:
        return np.nan, np.nan, len(x)
    r = float(np.corrcoef(x, y)[0, 1]); n = len(x)
    t = r * np.sqrt(n - 2) / np.sqrt(max(1e-12, 1 - r * r))
    return r, t, n

def main():
    pws = [per_window(a) for a in ASSETS]
    pool = pd.concat(pws, ignore_index=True)
    pool["hour"] = (pool.ws // 3600) % 24
    ntr = int(pool.traded.sum())
    print(f"windows: total={len(pool)} traded={ntr} strand-rate(traded)={pool[pool.traded].strand.mean():.3f} "
          f"| per asset " + " ".join(f"{a}={len(p)}" for a, p in zip(ASSETS, pws)))

    # 1) AUTOCORR (adjacent chains only; pooled within-asset pairs)
    print("\n[1] autocorr (pooled, within-asset, exact 900L gap)  r (t-stat, n)")
    print(f"{'metric':<10}" + "".join(f"{'lag'+str(L):>20}" for L in range(1, 6)))
    for col in ["vpin7", "absmove", "fimb", "strand", "pair_rate"]:
        cells = []
        for L in range(1, 6):
            xs, ys = [], []
            for p in pws:
                q = p if col != "pair_rate" else p[p.traded]
                x, y = lag_pairs(q, col, L)
                xs.append(x); ys.append(y)
            x = np.concatenate(xs); y = np.concatenate(ys)
            if col == "strand":
                x = x.astype(float); y = y.astype(float)
            r, t, n = acorr(x, y)
            cells.append(f"{r:+.3f} (t={t:+.1f},n={n})" if np.isfinite(r) else "n/a")
        print(f"{col:<10}" + "".join(f"{c:>20}" for c in cells))

    # 2) REGIME PERSISTENCE: toxic = top-quartile vpin7 (per-asset q75) OR strand
    for p in pws:
        thr = p.vpin7.quantile(0.75)
        p["toxic"] = (p.vpin7 >= thr) | p.strand
    pool2 = pd.concat(pws, ignore_index=True)
    pool2["hour"] = (pool2.ws // 3600) % 24
    base = pool2.toxic.mean()
    x, y = np.concatenate([lag_pairs(p, "toxic", 1)[0] for p in pws]), \
           np.concatenate([lag_pairs(p, "toxic", 1)[1] for p in pws])
    p_tt = y[x > 0.5].mean(); p_nt = y[x < 0.5].mean(); npairs = len(x)
    # run lengths over contiguous chains
    runs = []
    for p in pws:
        p = p.sort_values("ws")
        tox = p.toxic.to_numpy(); ws = p.ws.to_numpy()
        cur = 0
        for i in range(len(p)):
            if tox[i] and (cur == 0 or ws[i] - ws[i - 1] == 900):
                cur += 1
            else:
                if cur: runs.append(cur)
                cur = 1 if tox[i] else 0
        if cur: runs.append(cur)
    runs = np.array(runs)
    print(f"\n[2] regime: base P(toxic)={base:.3f}  P(toxic|prev toxic)={p_tt:.3f}  "
          f"P(toxic|prev clean)={p_nt:.3f}  lift={p_tt/base:.2f}x  (adjacent pairs n={npairs})")
    print(f"    toxic run-length: mean={runs.mean():.2f} median={np.median(runs):.0f} "
          f"P(len>=2)={np.mean(runs>=2):.3f} P(len>=3)={np.mean(runs>=3):.3f} (nruns={len(runs)})")
    # strand-only persistence
    xs = np.concatenate([lag_pairs(p, "strand", 1)[0] for p in pws])
    ys = np.concatenate([lag_pairs(p, "strand", 1)[1] for p in pws])
    sb = pool2.strand.mean()
    print(f"    strand-only: base={sb:.3f}  P(strand|prev strand)={ys[xs>0.5].mean():.3f} "
          f"(lift {ys[xs>0.5].mean()/sb:.2f}x, n_prev_strand={int(xs.sum())})")

    # 3) VOL -> next-window STRAND
    x = np.concatenate([lag_pairs(p, "absmove", 1, "strand")[0] for p in pws])
    y = np.concatenate([lag_pairs(p, "absmove", 1, "strand")[1] for p in pws])
    r, t, n = acorr(x, y.astype(float))
    x0 = np.concatenate([lag_pairs(p, "absmove", 0, "strand")[0] for p in pws]) if False else None
    rsame, tsame, nsame = acorr(*[arr.astype(float) for arr in
        (np.concatenate([p.absmove.to_numpy() for p in pws]), np.concatenate([p.strand.to_numpy() for p in pws]))])
    print(f"\n[3] corr(vol_N, strand_N+1) = {r:+.3f} (t={t:+.1f}, n={n})   "
          f"[same-window corr(vol_N,strand_N)={rsame:+.3f} (t={tsame:+.1f})]")
    # top-quartile vol -> next strand rate
    hv = []
    for p in pws:
        thr = p.absmove.quantile(0.75)
        x, y = lag_pairs(p, "absmove", 1, "strand")
        hv.append((y[x >= thr], y[x < thr]))
    hi = np.concatenate([a for a, b in hv]); lo = np.concatenate([b for a, b in hv])
    print(f"    next-window strand rate: after top-quartile vol={hi.mean():.3f} vs rest={lo.mean():.3f}")

    # 4) UTC hour structure (pooled; stability = first vs second half ranks)
    h = pool2.groupby("hour").agg(vpin=("vpin7", "mean"), strand=("strand", "mean"),
                                  pnl=("pnl", "mean"), n=("ws", "size"))
    worst = h.sort_values("strand", ascending=False).head(5)
    print(f"\n[4] worst UTC hours by strand rate (pooled mean strand={pool2.strand.mean():.3f}):")
    for hr, row in worst.iterrows():
        print(f"    h{int(hr):02d}: strand={row.strand:.3f} vpin={row.vpin:.3f} pnl/win={row.pnl:+.3f} n={int(row.n)}")
    med = pool2.ws.median()
    h1 = pool2[pool2.ws < med].groupby("hour").strand.mean()
    h2 = pool2[pool2.ws >= med].groupby("hour").strand.mean()
    both = pd.concat([h1, h2], axis=1, keys=["a", "b"]).dropna()
    rs = both.a.rank().corr(both.b.rank())
    print(f"    hour-rank stability (1st vs 2nd half, spearman) = {rs:+.3f}  "
          f"h22: strand={h.loc[22,'strand']:.3f} vpin={h.loc[22,'vpin']:.3f} n={int(h.loc[22,'n'])}")

    # 5) SESSION GATE: after toxic window N (strand OR vpin7>=IS-q75), skip windows N+1..N+M
    print("\n[5] session gate backtest (skip M windows after toxic; IS=first 60% per asset, OOS=last 40%)")
    for p in pws:
        cut = p.ws.quantile(0.6)
        thr = p[p.ws < cut].vpin7.quantile(0.75)                  # IS-calibrated threshold
        p["tox_sig"] = ((p.vpin7 >= thr) | p.strand)
        p["is_"] = p.ws < cut
    def run_gate(M, seg):
        kept_pnl, kept_n, skip_pnl, skip_n, kept_str, kept_tr = 0.0, 0, 0.0, 0, 0, 0
        for p in pws:
            q = p[p.is_] if seg == "is" else p[~p.is_]
            tox_ws = p.loc[p.tox_sig, "ws"].to_numpy()
            blocked = set()
            for w in tox_ws:
                for j in range(1, M + 1):
                    blocked.add(w + 900 * j)
            sk = q.ws.isin(blocked)
            kept_pnl += q.loc[~sk, "pnl"].sum(); kept_n += int((~sk).sum())
            skip_pnl += q.loc[sk, "pnl"].sum(); skip_n += int(sk.sum())
            kk = q[~sk & q.traded]; kept_str += int(kk.strand.sum()); kept_tr += len(kk)
        return kept_pnl, kept_n, skip_pnl, skip_n, kept_str, kept_tr
    # baselines
    for seg in ["is", "oos"]:
        q = pd.concat([p[p.is_] if seg == "is" else p[~p.is_] for p in pws])
        print(f"    {seg.upper()} baseline: pnl/win={q.pnl.mean():+.4f} strand-rate(traded)={q[q.traded].strand.mean():.3f} "
              f"nwin={len(q)} ntraded={int(q.traded.sum())}")
    best_m, best_v = None, -9e9
    for M in [1, 2, 3, 4, 6, 8]:
        kp, kn, sp, sn, ks, kt = run_gate(M, "is")
        tot = pd.concat([p[p.is_] for p in pws]).pnl
        v = kp / max(kn, 1)                                       # pnl per KEPT window
        print(f"    IS  M={M}: kept pnl/win={kp/max(kn,1):+.4f} skipped pnl/win={sp/max(sn,1):+.4f} "
              f"(skip {sn}/{kn+sn}={sn/(kn+sn):.1%}) strand(kept)={ks/max(kt,1):.3f}")
        if v > best_v: best_v, best_m = v, M
    print(f"    -> optimal M (IS, pnl/kept-win) = {best_m}")
    for M in [best_m]:
        kp, kn, sp, sn, ks, kt = run_gate(M, "oos")
        q = pd.concat([p[~p.is_] for p in pws])
        # t-stat: skipped windows pnl vs kept windows pnl
        blocked_all = []
        for p in pws:
            qq = p[~p.is_]
            tox_ws = p.loc[p.tox_sig, "ws"].to_numpy()
            blocked = set(w + 900 * j for w in tox_ws for j in range(1, M + 1))
            blocked_all.append(qq.assign(sk=qq.ws.isin(blocked)))
        qq = pd.concat(blocked_all)
        a, b = qq[qq.sk].pnl, qq[~qq.sk].pnl
        se = np.sqrt(a.var() / max(len(a), 1) + b.var() / max(len(b), 1))
        tt = (b.mean() - a.mean()) / se if se > 0 else np.nan
        print(f"    OOS M={M}: kept pnl/win={kp/max(kn,1):+.4f} vs skipped={sp/max(sn,1):+.4f} "
              f"(diff t={tt:+.2f}) skip-rate={sn/(kn+sn):.1%} strand(kept)={ks/max(kt,1):.3f} "
              f"vs baseline strand={q[q.traded].strand.mean():.3f} | total pnl kept={kp:+.1f} baseline={q.pnl.sum():+.1f}")

if __name__ == "__main__":
    main()
