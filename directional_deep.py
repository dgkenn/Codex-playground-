"""directional_deep.py -- the directional battery at DEEP-HISTORY power (hist_*.parquet from
fetch_history.py; thousands of windows vs the collector's hundreds).

Same discipline as directional_scan.py, adapted to 1-minute fidelity:
  TARGET = residual = res_up - mid(t_min)      (the market's pricing error at minute t)
  SPLIT  = train on the first 60% of windows (sign/threshold learned there ONLY), test on the rest
  COSTS  = maker-skew (fee-free) / taker net of half-spread / net of half-spread + taker fee
  BAR    = |t|>=3 train AND same-sign |t|>=2.5 test (stricter than the small-n scan: with
           thousands of windows, weak-but-real effects will clear this; noise will not)

Features at decision minutes {5, 7, 11, 13} (all backward-looking; sigma from the PRE-WINDOW hour
of 1m spot bars -- decision-time observable, independent of the in-window path):
  gap_model   fair_up(S_t, S_0, sigma_pre, tau) - mid     (the small-n scan's one near-miss)
  tok_mom     mid(t) - mid(1)
  spot_mom    spot(t)/spot(0) - 1, bps
  spot_rec    spot(t)/spot(t-3) - 1, bps (recent 3 minutes)
  mid_dist    |mid - 0.5|
  prev_out    previous window outcome (+-1)        prev_resid  previous window residual
  hour_sin/cos  UTC time-of-day seasonality (deep history finally has the n for it)

Also: the favorite-longshot calibration at scale, and a per-month stability table for anything that
clears (an edge that lives in one month died with that regime).   python directional_deep.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fairvalue import fair_up

DEC_MIN = (5, 7, 11, 13)
HALF_SPREAD = 0.005
TAKER_FEE = 0.0175


def t_of(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def corr_t(x, y):
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    if len(x) < 20 or x.std() == 0 or y.std() == 0:
        return float("nan"), float("nan"), 0
    c = float(np.corrcoef(x, y)[0, 1])
    t = c * np.sqrt(len(x) - 2) / np.sqrt(max(1 - c * c, 1e-12))
    return c, t, len(x)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "hist_btc15m.parquet"
    df = pd.read_parquet(path)
    print(f"{len(df)} windows from {path} "
          f"({pd.to_datetime(df.ws.min(), unit='s')} .. {pd.to_datetime(df.ws.max(), unit='s')})\n")
    mid = np.stack(df.mid_path.to_numpy())            # (n, 15)
    spot = np.stack(df.spot_path.to_numpy())          # (n, 15)
    prev = np.stack(df.spot_prev.to_numpy())          # (n, 60)
    res = df.res_up.to_numpy(float)
    ws = df.ws.to_numpy(np.int64)

    # pre-window sigma (per-second, from the prior hour of 1m bars)
    with np.errstate(all="ignore"):
        lr = np.diff(np.log(prev), axis=1)
        sigma_pre = np.nanstd(lr, axis=1) / np.sqrt(60.0)
    s0 = spot[:, 0]

    # previous-window features (by exact ws-900 match)
    idx = {int(w): i for i, w in enumerate(ws)}
    mid13 = mid[:, 13]
    prev_out = np.full(len(df), np.nan); prev_resid = np.full(len(df), np.nan)
    for i, w in enumerate(ws):
        j = idx.get(int(w) - 900)
        if j is not None:
            prev_out[i] = 2 * res[j] - 1
            if not np.isnan(mid13[j]):
                prev_resid[i] = res[j] - mid13[j]

    # ---------------- calibration / favorite-longshot at scale ----------------
    print("=== CALIBRATION (favorite-longshot at scale): P(up | mid bucket) ===")
    print(f"{'min':>4} {'bucket':>12} {'n':>6} {'mid_avg':>8} {'P(up)':>7} {'bias':>8} {'z':>7}")
    flb = {}
    for t_min in (7, 13):
        m_t = mid[:, t_min]
        for lo, hi in ((0.02, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 0.98)):
            sel = (m_t >= lo) & (m_t < hi) & ~np.isnan(m_t)
            if sel.sum() < 50:
                continue
            ma, pr = float(m_t[sel].mean()), float(res[sel].mean())
            se = np.sqrt(ma * (1 - ma) / sel.sum())
            z = (pr - ma) / se if se > 0 else float("nan")
            flb[(t_min, lo)] = z
            print(f"{t_min:>4} {f'{lo:.2f}-{hi:.2f}':>12} {sel.sum():>6} {ma:>8.3f} {pr:>7.3f} "
                  f"{pr - ma:>+8.3f} {z:>+7.2f}")
    print()

    # ---------------- conditional battery ----------------
    print("=== FEATURE BATTERY (train 60% -> test 40%; bar: |t|>=3 train, same-sign >=2.5 test) ===")
    hdr = (f"{'min':>4} {'feature':>10} {'n':>6} {'tr_corr':>8} {'tr_t':>7} {'te_corr':>8} "
           f"{'te_t':>7} | {'maker/win':>10} {'tk-spr':>8} {'tk-fee':>8}  verdict")
    print(hdr); print("-" * len(hdr))
    cut = ws[int(len(ws) * 0.6)]
    is_tr = ws < cut
    survivors = []
    hour = ((ws % 86400) / 3600.0)
    for t_min in DEC_MIN:
        m_t = mid[:, t_min]
        ok_mid = ~np.isnan(m_t) & (m_t > 0.02) & (m_t < 0.98)
        resid = res - m_t
        sp_t = spot[:, t_min]; sp_rec0 = spot[:, max(t_min - 3, 0)]
        tau = (15 - t_min) * 60.0
        with np.errstate(all="ignore"):
            gap = np.array([float(fair_up(sp_t[i], s0[i], sigma_pre[i], tau)) - m_t[i]
                            if (sp_t[i] > 0 and s0[i] > 0 and sigma_pre[i] > 0) else np.nan
                            for i in range(len(df))])
        feats = {
            "gap_model": gap,
            "tok_mom": m_t - mid[:, 1],
            "spot_mom": (sp_t / s0 - 1) * 1e4,
            "spot_rec": (sp_t / sp_rec0 - 1) * 1e4,
            "mid_dist": np.abs(m_t - 0.5),
            "prev_out": prev_out,
            "prev_resid": prev_resid,
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
        }
        for k, x in feats.items():
            vtr = ok_mid & is_tr & ~np.isnan(x)
            vte = ok_mid & ~is_tr & ~np.isnan(x)
            if vtr.sum() < 200 or vte.sum() < 120:
                continue
            ctr, ttr, ntr = corr_t(x[vtr], resid[vtr])
            cte, tte, nte = corr_t(x[vte], resid[vte])
            thr = float(np.median(x[vtr])); sgn = np.sign(ctr)
            bet = sgn * np.sign(x[vte] - thr)
            pnl = bet * resid[vte]
            mk = float(np.nanmean(pnl))
            tk_s = mk - HALF_SPREAD
            tk_f = mk - HALF_SPREAD - TAKER_FEE
            hit = abs(ttr) >= 3.0 and np.sign(ttr) == np.sign(tte) and abs(tte) >= 2.5
            if hit:
                survivors.append((t_min, k, ctr, cte, ttr, tte, mk, tk_s, tk_f, x, resid, ok_mid))
            print(f"{t_min:>4} {k:>10} {ntr + nte:>6} {ctr:>+8.3f} {ttr:>+7.1f} {cte:>+8.3f} "
                  f"{tte:>+7.1f} | {mk:>+10.4f} {tk_s:>+8.4f} {tk_f:>+8.4f}  {'EDGE' if hit else ''}")

    # ---------------- verdict + stability for survivors ----------------
    print("\n=== VERDICT ===")
    if not survivors:
        print("NO directional edge clears the deep-history bar. With thousands of windows this is a")
        print("decisive null: 15-min pricing is efficient after costs; the edge is the maker seat.")
        return
    print(f"{len(survivors)} edge(s) clear BOTH halves at deep-history power:")
    months = pd.to_datetime(ws, unit="s").to_period("W")
    for t_min, k, ctr, cte, ttr, tte, mk, tk_s, tk_f, x, resid, ok_mid in survivors:
        tier = ("TAKER-VIABLE (beats fee+spread)" if tk_f > 0 else
                "beats spread, not the fee" if tk_s > 0 else "MAKER-SKEW ONLY (fee-free tilt)")
        print(f"\n  min={t_min} {k}: corr {ctr:+.3f} (t={ttr:+.1f}) -> {cte:+.3f} (t={tte:+.1f}); "
              f"maker {mk:+.4f}/win; {tier}")
        print(f"    per-week stability (corr in each week):")
        for per in sorted(set(months)):
            sel = ok_mid & (months == per).to_numpy() & ~np.isnan(x)
            c, t, n = corr_t(x[sel], resid[sel])
            if n >= 60:
                print(f"      {per}: corr {c:+.3f} (t={t:+.1f}, n={n})")
    print("\nNext per discipline: express the strongest as a MAKER skew tilt in a shadow A/B variant;")
    print("taker expression only if tk-fee stays positive out-of-sample AND live fills confirm.")


if __name__ == "__main__":
    main()
