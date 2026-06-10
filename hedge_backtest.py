"""hedge_backtest.py -- PROPER delta-hedge backtest (not the mo30 proxy): simulate a BTC-perp hedge against
the REAL per-window spot path (ticks_*.jsonl, ~1Hz) for each gate's reconstructed inventory, with perp fees
+ rebalance hysteresis, then recompute the full risk suite hedged vs unhedged (IS+OOS, p-values, 95% CIs).

Hypothesis under test: delta-hedging strips the residual inventory's BTC-directional swing (which drives
ufat_band's drawdown), so hedged ufat_band should keep its high return but cut MDD -> Calmar/Sortino above
BOTH unhedged ufat_band AND plain ufat.

Model (units in $): token value V = q.fair(S); dV = (q_up-q_dn).f'(S).dS. A perp of notional N has dP =
N.dS/S, so the neutralizing notional is N* = -(q_up-q_dn).f'(S).S (= hedger.target_perp_usd). We hold N
along the tick path, accrue hedge_pnl = N.(S_t-S_{t-1})/S_{t-1}, rebalance to N* when |N*-N|>hysteresis
(charging perp fee on the traded notional). gross = realized token P&L to resolution; rebate from fills.
    unhedged_net = gross + rebate ;  hedged_net = gross + rebate + hedge_pnl - fees
    python hedge_backtest.py [fee_bps] [hyst_usd]
"""
from __future__ import annotations
import glob, json, re, sys, math, statistics, random
import numpy as np
from scipy import stats
try:
    import fees
    REB = lambda p: float(fees.maker_rebate(p, rate=0.07))
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)
SIGMA = 6.5e-5; MICRO_MARGIN = 0.002; random.seed(13)


_INV_SQRT2PI = 0.3989422804014327


def dfair_dS(S, s0, sigma, tau):
    """Closed-form d(fair_up)/dS. fair_up = Phi(z), z = ln(S/s0)/(sigma*sqrt(tau)); so
    dfair/dS = phi(z) * dz/dS = exp(-z^2/2)/sqrt(2pi) / (S*sigma*sqrt(tau)). ~100x faster than 2x fair_up."""
    if tau <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    denom = sigma * math.sqrt(tau)
    z = math.log(S / s0) / denom
    return _INV_SQRT2PI * math.exp(-0.5 * z * z) / (S * denom)


def akey(fp, pat):
    m = re.search(pat, fp); return (m.group(1), int(m.group(2))) if m else ("btc", 15)


def load_ticks():
    T = {}
    for fp in glob.glob("gha_data/ticks_*.jsonl"):
        a, ten = akey(fp, r"ticks_([a-z]+)(\d+)m_")
        for ln in open(fp):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("ws") is not None and r.get("ticks"):
                path = [(t[0], t[2]) for t in r["ticks"] if t[2]]      # (t-ws, spot)
                if len(path) > 20:
                    T[(a, r["ws"])] = {"res": r.get("res_up"), "win": ten * 60, "path": path}
    return T


def load_fills():
    F = {}
    for fp in glob.glob("gha_data/fills_*.jsonl"):
        a, ten = akey(fp, r"fills_([a-z]+)(\d+)m_")
        for ln in open(fp):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("ws") is not None:
                r["_k"] = (a, r["ws"]); F.setdefault(r["_k"], []).append(r)
    return F


def toxv(r):
    t = r.get("tox")
    if t is not None: return t
    mp = r.get("micro"); return 0.0 if mp is None else ((mp - r["p"]) if r["side"] == "ASK" else (r["p"] - mp))


def gate(name):
    M = MICRO_MARGIN
    if name == "micro": return lambda r: toxv(r) <= 0.0
    if name == "ufat": return lambda r: toxv(r) <= M * 4 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"]))
    if name == "ufat_band":
        return lambda r: (False if 0.30 <= (r.get("mid") or r["p"]) < 0.55
                          else toxv(r) <= M * 4 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"])))
    return lambda r: True


def realized_sigma(path):
    """per-second log-vol from the window's own spot path -> the RIGHT hedge ratio (vs a fixed prior)."""
    r = []
    for i in range(1, len(path)):
        s0_, s1_ = path[i - 1][1], path[i][1]; dt = max(path[i][0] - path[i - 1][0], 1e-6)
        if s0_ > 0 and s1_ > 0:
            r.append(math.log(s1_ / s0_) / math.sqrt(dt))
    return (statistics.pstdev(r) or SIGMA) if len(r) >= 5 else SIGMA


def simulate(tk, fills, fee_bps, hyst, band=0.15, tau_min_frac=0.13):
    """REALISTIC delta-hedge for one window. Binary delta explodes as tau->0 (gamma/pin risk), so:
    (1) hedge ratio uses the window's REALIZED vol; (2) FREEZE the hedge in the last tau_min (hold the
    position to resolution -- you can't hedge a binary in the final minutes); (3) rebalance only past a
    PROPORTIONAL band (avoid churning fees on a large notional). returns (unhedged, hedged, hpnl, fee)."""
    res = tk["res"]; win = tk["win"]; path = tk["path"]; s0 = path[0][1]
    sigma = realized_sigma(path); tau_min = tau_min_frac * win
    fl = sorted(fills, key=lambda r: r.get("t", 0)); t_ws = fl[0]["ws"]
    ev = [(r["t"] - t_ws, bool(r["up"]), r["side"], r["p"], r["sz"]) for r in fl]
    gross = rebate = 0.0
    for trel, is_up, side, p, sz in ev:
        rt = res if is_up else (1 - res)
        signed = sz if side == "SELL" else -sz                 # taker SELL -> we BUY (long); BUY -> we're short
        gross += signed * (rt - p); rebate += REB(p) * sz
    q_up = q_dn = 0.0; N = 0.0; S_prev = s0; hpnl = fee = 0.0; i = 0
    for trel, S in path:
        if S_prev > 0:
            hpnl += N * (S - S_prev) / S_prev                  # accrue P&L on the HELD notional
        S_prev = S
        while i < len(ev) and ev[i][0] <= trel:
            _, is_up, side, p, sz = ev[i]; signed = sz if side == "SELL" else -sz
            if is_up:
                q_up += signed
            else:
                q_dn += signed
            i += 1
        tau = win - trel
        if tau >= tau_min:                                     # freeze the hedge in the final tau_min
            Nt = -(q_up - q_dn) * dfair_dS(S, s0, sigma, tau) * S
            if abs(Nt - N) > max(hyst, band * max(abs(N), abs(Nt))):
                fee += abs(Nt - N) * fee_bps / 1e4; N = Nt
    return gross + rebate, gross + rebate + hpnl - fee, hpnl, fee


def msuite(net):
    xs = list(net.values()); n = len(xs)
    if n < 5: return None
    mean = sum(xs) / n; sd = statistics.stdev(xs); sem = sd / math.sqrt(n)
    _, p = stats.ttest_1samp(xs, 0.0); lo, hi = stats.t.interval(0.95, n - 1, loc=mean, scale=sem) if sem > 0 else (mean, mean)
    dd = statistics.pstdev([min(x, 0.0) for x in xs])
    import collections
    byws = collections.defaultdict(float)
    for (a, ws), v in net.items(): byws[ws] += v
    cum = peak = worst = 0.0
    for ws in sorted(byws):
        cum += byws[ws]; peak = max(peak, cum); worst = min(worst, cum - peak)
    mdd = -worst
    return dict(n=n, net=mean, p=p, ci=(lo, hi), sortino=(mean / dd) if dd > 0 else float("nan"),
                mdd=mdd, calmar=(cum / mdd) if mdd > 0 else float("inf"), skew=float(stats.skew(xs)),
                var95=float(np.percentile(xs, 5)))


def boot_calmar(net, B=1500):
    items = list(net.items()); n = len(items); vals = []
    import collections
    for _ in range(B):
        s = [items[random.randrange(n)] for _ in range(n)]
        byws = collections.defaultdict(float)
        for (a, ws), v in s: byws[ws] += v
        cum = peak = worst = 0.0
        for ws in sorted(byws):
            cum += byws[ws]; peak = max(peak, cum); worst = min(worst, cum - peak)
        if -worst > 0: vals.append(cum / -worst)
    return (np.percentile(vals, 2.5), np.percentile(vals, 97.5)) if vals else (float("nan"), float("nan"))


def run(gname, T, F, fee_bps, hyst):
    """simulate ALL windows ONCE for a gate -> {k:(unhedged,hedged)} + totals."""
    keep = gate(gname); out = {}; tot_h = tot_f = 0.0
    for k, tk in T.items():
        if tk.get("res") is None:
            continue
        fl = [r for r in F.get(k, []) if keep(r)]
        if not fl:
            continue
        u, h, hp, fe = simulate(tk, fl, fee_bps, hyst); out[k] = (u, h); tot_h += hp; tot_f += fe
    return out, tot_h, tot_f


def main():
    fee_bps = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    hyst = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
    T = load_ticks(); F = load_fills()
    if not T or not F:
        print("no data: git fetch origin gha-data && git checkout origin/gha-data -- gha_data/"); return
    wss = sorted({k[1] for k in T}); cut = wss[int(len(wss) * 0.7)]
    print(f"hedge backtest: {len(set(T) & set(F))} windows w/ spot-path+fills | perp fee {fee_bps}bps, hysteresis ${hyst}\n")
    print(f"{'gate':>11}{'mode':>9}{'net/win':>9}{'p':>9}{'95%CI(net)':>17}{'Sortino':>8}{'MDD':>7}{'Calmar':>8}{'skew':>7}{'VaR95':>8}")
    cache = {}
    for g in ("micro", "ufat", "ufat_band"):
        res, th, tf = run(g, T, F, fee_bps, hyst); cache[g] = res
        unh = {k: v[0] for k, v in res.items()}; hed = {k: v[1] for k, v in res.items()}
        for mode, d in (("unhedged", unh), ("hedged", hed)):
            s = msuite(d)
            if s:
                ci = f"[{s['ci'][0]:+.2f},{s['ci'][1]:+.2f}]"
                print(f"{g:>11}{mode:>9}{s['net']:>+9.2f}{s['p']:>9.1e}{ci:>17}{s['sortino']:>8.2f}{s['mdd']:>7.0f}{s['calmar']:>8.1f}{s['skew']:>+7.2f}{s['var95']:>+8.2f}")
        cu = boot_calmar(unh); ch = boot_calmar(hed)
        ks = sorted(res); _, pp = stats.ttest_rel([hed[k] for k in ks], [unh[k] for k in ks])
        print(f"{'':>11}{'CalmarCI':>9}  unhedged [{cu[0]:.1f},{cu[1]:.1f}]  hedged [{ch[0]:.1f},{ch[1]:.1f}]  "
              f"hedge_pnl/win {th/max(1,len(ks)):+.2f} fee/win {tf/max(1,len(ks)):.3f}  paired p(hed-unh)={pp:.1e}\n")

    print("=== IS / OOS (Calmar, hedged vs unhedged) -- filtered from the same sims ===")
    for g in ("ufat", "ufat_band"):
        res = cache[g]
        for lab, pred in (("IS", lambda ws: ws < cut), ("OOS", lambda ws: ws >= cut)):
            unh = {k: v[0] for k, v in res.items() if pred(k[1])}; hed = {k: v[1] for k, v in res.items() if pred(k[1])}
            su, sh = msuite(unh), msuite(hed)
            if su and sh:
                print(f"  {g:>10} {lab:>3}: unhedged net {su['net']:+.2f} Calmar {su['calmar']:.1f} | "
                      f"hedged net {sh['net']:+.2f} Calmar {sh['calmar']:.1f}")
    print("\nVERDICT -> does HEDGED ufat_band beat (a) unhedged ufat_band and (b) plain ufat on Calmar?")


if __name__ == "__main__":
    main()
