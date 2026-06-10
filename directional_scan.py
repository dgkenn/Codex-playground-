"""directional_scan.py -- exhaustive, honest hunt for DIRECTIONAL edges in the 15-min markets.

The standing conclusion ("no directional alpha"; alpha_scan/drift_predict, R^2~0) predates the
current dataset. This re-opens the question over EVERY tick window collected, with the discipline
that earlier saved us from the lookahead/regime traps:

  TARGET   = residual = res_up - up_mid(t)   (the market's pricing ERROR from decision time t --
             predicting res_up itself is trivial, the price already does that)
  UNIT     = one observation per (asset, ws, t): windows are the cluster; features at MULTIPLE
             decision times tau in {120s, 450s, 690s, 810s into the window}
  PROTOCOL = train on the first 60% of windows (sign + threshold learned there ONLY), confirm on
             the last 40%; an "edge" must have |t|>=2.5 in train AND same-sign t>=2 in test
  COSTS    = three tradeability tiers per surviving edge:
             maker-skew (fee-free; tilt the ladder)  >  taker net of half-spread (~0.005)
             > taker net of half-spread + taker fee (~p(1-p)*0.07*~3 -> ~0.0175 at p=0.5)

FEATURES (all decision-time observable; the spot column for ALT windows is BTC in the historical
data -- the old per-asset-spot bug -- so spot features on alts ARE the cross-asset BTC-lead test):
  tok_mom     token mid move since window open (momentum vs reversal of the token itself)
  spot_mom    spot move since open, bps (does the book under-react to the underlying?)
  spot_rec    spot move over the last ~60s, bps (fresh information not yet in the mid?)
  gap_model   fair_up(S_t, S_0, sigma_rlz, tau) - mid  (model-market disagreement; btc only,
              alts' own spot wasn't recorded historically)
  rvol        realized spot vol so far in the window (regime interaction)
  prev_resid  PREVIOUS window's residual (serial error correlation)
  prev_out    previous window's outcome +-1 (15m momentum/reversal)
  mid_dist    |mid-0.5| (favorite-longshot shape feature)

Plus a CALIBRATION table (res_up vs mid bucket, binomial CIs) -- the favorite-longshot re-test with
~4x the n of the original rejection.    python directional_scan.py
"""
from __future__ import annotations

import re

import numpy as np

from dataio import jl_glob, jl_lines
from fairvalue import fair_up

TAUS = (120, 450, 690, 810)          # seconds INTO the window (tau_remaining = 900 - t_in)
HALF_SPREAD = 0.005
TAKER_FEE = 0.0175                   # ~p(1-p)*rate*scale at p~0.5; the worst-case wall


def load_windows():
    rows = []
    for fp in jl_glob("gha_data/ticks_*.jsonl"):
        m = re.search(r"ticks_([a-z]+)(\d+)m_", fp)
        asset, tenor = (m.group(1), int(m.group(2))) if m else ("btc", 15)
        for w in jl_lines(fp):
            ts = w.get("ticks") or []
            if len(ts) < 120 or w.get("res_up") is None:
                continue
            if w.get("role") == "down":
                continue                              # new-format down-token rows: skip (up is canon)
            t = np.array([a[0] for a in ts], float)
            mid = np.array([a[1] if a[1] is not None else np.nan for a in ts], float)
            sp = np.array([a[2] if a[2] is not None else np.nan for a in ts], float)
            if np.isnan(mid).all() or np.isnan(sp).all():
                continue
            rows.append({"asset": asset, "tenor": tenor, "ws": int(w["ws"]),
                         "res": int(w["res_up"]), "t": t, "mid": mid, "sp": sp})
    rows.sort(key=lambda r: (r["ws"], r["asset"]))
    return rows


def snap(arr, t, target):
    """Last valid value at/before target seconds into the window (None if absent)."""
    idx = np.where((t <= target) & ~np.isnan(arr))[0]
    return float(arr[idx[-1]]) if len(idx) else None


def features_at(w, t_in, prev):
    mid = snap(w["mid"], w["t"], t_in)
    sp = snap(w["sp"], w["t"], t_in)
    mid0 = snap(w["mid"], w["t"], 90)               # "open" = first 90s (joins can be slightly late)
    sp0 = snap(w["sp"], w["t"], 90)
    sp_rec0 = snap(w["sp"], w["t"], t_in - 60)
    if None in (mid, sp, mid0, sp0, sp_rec0) or not (0.02 <= mid <= 0.98):
        return None
    seg = w["sp"][(w["t"] <= t_in) & ~np.isnan(w["sp"])]
    if len(seg) < 10 or sp0 <= 0:
        return None
    lr = np.diff(np.log(seg))
    dt = max((w["t"][-1] - w["t"][0]) / max(len(w["t"]) - 1, 1), 0.5)
    sigma = float(np.std(lr) / np.sqrt(dt))          # per-second realized vol so far
    tau_rem = max(w["tenor"] * 60 - t_in, 1.0)
    f = {
        "tok_mom": mid - mid0,
        "spot_mom": (sp - sp0) / sp0 * 1e4,
        "spot_rec": (sp - sp_rec0) / sp0 * 1e4,
        "rvol": sigma,
        "mid_dist": abs(mid - 0.5),
        "prev_resid": prev.get((w["asset"], w["ws"] - w["tenor"] * 60), {}).get("resid", 0.0),
        "prev_out": prev.get((w["asset"], w["ws"] - w["tenor"] * 60), {}).get("out", 0.0),
    }
    if w["asset"] == "btc" and sigma > 0:
        f["gap_model"] = float(fair_up(sp, sp0, sigma, tau_rem)) - mid
    return mid, f


def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def main():
    rows = load_windows()
    print(f"{len(rows)} resolved tick windows | assets: "
          f"{sorted(set(r['asset'] for r in rows))} | span "
          f"{min(r['ws'] for r in rows)}..{max(r['ws'] for r in rows)}\n")

    # previous-window map (serial features)
    prev = {}
    for w in rows:
        m_end = snap(w["mid"], w["t"], w["tenor"] * 60 - 30) or 0.5
        prev[(w["asset"], w["ws"])] = {"resid": w["res"] - m_end, "out": 2 * w["res"] - 1}

    # ---------------- calibration / favorite-longshot (the big-n re-test) ----------------
    print("=== CALIBRATION: P(res=Up | mid bucket), pooled over assets, by decision time ===")
    print(f"{'t_in':>5} {'bucket':>12} {'n':>5} {'mid_avg':>8} {'P(up)':>7} {'bias':>7} {'binom_z':>8}")
    for t_in in (450, 810):
        obs = []
        for w in rows:
            mm = snap(w["mid"], w["t"], t_in)
            if mm is not None and 0.02 <= mm <= 0.98:
                obs.append((mm, w["res"]))
        for lo, hi in ((0.02, 0.25), (0.25, 0.45), (0.45, 0.55), (0.55, 0.75), (0.75, 0.98)):
            b = [(m, r) for m, r in obs if lo <= m < hi]
            if len(b) < 15:
                continue
            ms = np.mean([m for m, _ in b]); pr = np.mean([r for _, r in b])
            se = np.sqrt(ms * (1 - ms) / len(b))
            z = (pr - ms) / se if se > 0 else float("nan")
            print(f"{t_in:>5} {f'{lo:.2f}-{hi:.2f}':>12} {len(b):>5} {ms:>8.3f} {pr:>7.3f} "
                  f"{pr - ms:>+7.3f} {z:>+8.2f}")
    print("  (|z|>2.5 in BOTH t_in rows = a candidate mispricing; one row alone = noise)\n")

    # ---------------- conditional feature battery, train/test ----------------
    print("=== FEATURE BATTERY: corr(feature, residual) train->test + tradeability ===")
    print("(train = first 60% of windows; sign & threshold learned on train ONLY)")
    hdr = (f"{'t_in':>5} {'feature':>10} {'n':>5} {'tr_corr':>8} {'tr_t':>6} {'te_corr':>8} "
           f"{'te_t':>6} | {'maker/win':>10} {'tk-spr':>8} {'tk-fee':>8}  verdict")
    print(hdr); print("-" * len(hdr))
    survivors = []
    for t_in in TAUS:
        data = []
        for w in rows:
            out = features_at(w, t_in, prev)
            if out is None:
                continue
            mid, f = out
            data.append((w["ws"], w["asset"], mid, w["res"] - mid, f))
        if len(data) < 80:
            continue
        data.sort(key=lambda d: d[0])
        cut = data[int(len(data) * 0.6)][0]
        tr = [d for d in data if d[0] < cut]; te = [d for d in data if d[0] >= cut]
        feat_names = sorted({k for *_, f in data for k in f})
        for k in feat_names:
            xtr = np.array([f.get(k, np.nan) for *_, f in tr], float)
            rtr = np.array([d[3] for d in tr], float)
            xte = np.array([f.get(k, np.nan) for *_, f in te], float)
            rte = np.array([d[3] for d in te], float)
            mtr = ~np.isnan(xtr); mte = ~np.isnan(xte)
            if mtr.sum() < 50 or mte.sum() < 30:
                continue
            xtr, rtr, xte, rte = xtr[mtr], rtr[mtr], xte[mte], rte[mte]
            if xtr.std() == 0:
                continue
            ctr = float(np.corrcoef(xtr, rtr)[0, 1])
            ttr = ctr * np.sqrt(max(len(xtr) - 2, 1)) / np.sqrt(max(1 - ctr * ctr, 1e-9))
            cte = float(np.corrcoef(xte, rte)[0, 1]) if xte.std() > 0 else float("nan")
            tte = cte * np.sqrt(max(len(xte) - 2, 1)) / np.sqrt(max(1 - cte * cte, 1e-9))
            thr = float(np.median(xtr)); sgn = np.sign(ctr)
            bet = sgn * np.sign(xte - thr)
            mk = float(np.mean(bet * rte))
            tk_s = float(np.mean(bet * rte - np.abs(bet) * HALF_SPREAD))
            tk_f = float(np.mean(bet * rte - np.abs(bet) * (HALF_SPREAD + TAKER_FEE)))
            ok = abs(ttr) >= 2.5 and np.sign(ttr) == np.sign(tte) and abs(tte) >= 2.0
            verdict = "EDGE?" if ok else ""
            if ok:
                survivors.append((t_in, k, ctr, cte, mk, tk_s, tk_f, len(xtr), len(xte)))
            print(f"{t_in:>5} {k:>10} {len(xtr) + len(xte):>5} {ctr:>+8.3f} {ttr:>+6.1f} "
                  f"{cte:>+8.3f} {tte:>+6.1f} | {mk:>+10.4f} {tk_s:>+8.4f} {tk_f:>+8.4f}  {verdict}")

    print("\n=== VERDICT ===")
    n_tests = len(TAUS) * 8
    if not survivors:
        print(f"NO directional edge survives the train->test screen across ~{n_tests} feature/time "
              f"tests.\nThe market's 15-min pricing is consistent with efficient (given costs); the "
              f"validated edge remains\nthe maker rebate + toxicity avoidance, not direction.")
    else:
        print(f"{len(survivors)} candidate(s) survive BOTH halves (of ~{n_tests} tests -- expect "
              f"~{n_tests * 0.01:.1f} false positives\nat this bar by chance; treat as hypotheses for "
              f"the live A/B, not proof):")
        for t_in, k, ctr, cte, mk, tk_s, tk_f, ntr, nte in survivors:
            tier = ("TAKER-VIABLE (beats fee+spread)" if tk_f > 0 else
                    "spread-crossing viable, fee kills it" if tk_s > 0 else
                    "MAKER-SKEW ONLY (tilt the ladder; fee-free)")
            print(f"  t_in={t_in}s {k}: corr {ctr:+.3f}->{cte:+.3f}, maker {mk:+.4f}/win, "
                  f"taker-fee net {tk_f:+.4f} -> {tier}")
        print("\nNext step per discipline: wire the strongest as a shadow A/B variant (maker-skew "
              "expression),\nconfirm prospectively before ANY deployment.")


if __name__ == "__main__":
    main()
