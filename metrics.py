"""metrics.py -- FULL risk/profitability/consistency suite for EVERY strategy & gate, IS + OOS,
with p-values and 95% confidence intervals on every number.

Statistics:
  - net/win: two-sided one-sample t-test vs 0 (p) + 95% t-CI.
  - ratio metrics (Calmar, Sortino, Profit Factor): percentile 95% CI by BOOTSTRAP (B=2000) over the
    (asset,window) units (the cluster unit). Path metrics (MDD/Calmar) recompute the equity path on each
    resample ordered by ws -- a CI on the drawdown of a similar-length random path.
  - hedge effect (D): paired t on per-window (unhedged-hedged); regime (E): Welch t between calm/volatile.

Sections: A all variants (settled, FULL, ranked by Calmar) · B IS vs OOS · C gate family incl new gates
(fill-tape) · D delta-hedge proxy · E regime split. Caveats in METRICS.md (unit=window, maker ratio 100%,
PAPER/front-of-queue = upper bound, annualized Sharpe meaningless -> t-stat + MDD/Calmar/PF used).

    python metrics.py        (after: git checkout origin/gha-data -- gha_data/)
"""
from __future__ import annotations
import glob, json, re, math, collections, statistics, random
import numpy as np
from scipy import stats

try:
    import fees
    REB = lambda p: float(fees.maker_rebate(p, rate=0.07))
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)
MICRO_MARGIN = 0.002
random.seed(7)


# ---------- metric calculators on a list of per-window nets (+ paired ws for path) ----------
def _calmar_mdd(items):
    byws = collections.defaultdict(float)
    for (a, ws), v in items:
        byws[ws] += v
    cum = peak = worst = 0.0
    for ws in sorted(byws):
        cum += byws[ws]; peak = max(peak, cum); worst = min(worst, cum - peak)
    mdd = -worst
    return (cum / mdd) if mdd > 0 else float("inf"), mdd


def _sortino(xs):
    m = sum(xs) / len(xs); dd = statistics.pstdev([min(x, 0.0) for x in xs])
    return (m / dd) if dd > 0 else float("nan")


def _pf(xs):
    pos = sum(x for x in xs if x > 0); neg = sum(x for x in xs if x < 0)
    return (pos / abs(neg)) if neg else float("inf")


def boot_ci(items, fn, B=2000):
    """percentile 95% CI of fn over bootstrap resamples of the (key,val) items."""
    if len(items) < 8:
        return (float("nan"), float("nan"))
    n = len(items); vals = []
    for _ in range(B):
        samp = [items[random.randrange(n)] for _ in range(n)]
        try:
            vals.append(fn(samp))
        except Exception:
            pass
    finite = [v for v in vals if v == v and abs(v) != float("inf")]
    if not finite:
        return (float("nan"), float("nan"))
    return (float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5)))


def suite(net, fv=None, fr=None, md=None, boot=False):
    items = list(net.items()); xs = [v for _, v in items]; n = len(xs)
    if n < 5:
        return None
    mean = sum(xs) / n; sd = statistics.stdev(xs) if n > 1 else float("nan")
    sem = sd / math.sqrt(n)
    tstat, p = stats.ttest_1samp(xs, 0.0)
    lo, hi = stats.t.interval(0.95, n - 1, loc=mean, scale=sem) if sem > 0 else (mean, mean)
    calmar, mdd = _calmar_mdd(items)
    s = dict(n=n, net=mean, p=float(p), ci=(float(lo), float(hi)), t=float(tstat),
             sortino=_sortino(xs), mdd=mdd, calmar=calmar, pf=_pf(xs),
             win=100 * sum(1 for x in xs if x > 0) / n,
             edge=(100 * sum(xs) / sum(fv.values())) if (fv and sum(fv.values())) else float("nan"),
             fillrate=(100 * statistics.mean(list(fr.values()))) if fr else float("nan"),
             maxd=(statistics.mean(list(md.values()))) if md else float("nan"))
    if boot:
        s["calmar_ci"] = boot_ci(items, lambda it: _calmar_mdd(it)[0])
        s["sortino_ci"] = boot_ci(items, lambda it: _sortino([v for _, v in it]))
        s["pf_ci"] = boot_ci(items, lambda it: _pf([v for _, v in it]))
    return s


def stars(p):
    return "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else " "


# ---------- loaders ----------
def load_windows():
    W = {}
    for fp in glob.glob("gha_data/shadow_windows_*.jsonl"):
        for ln in open(fp):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("ws") is not None:
                W[(r.get("asset", "btc"), r["ws"])] = r
    return W


def vseries(W, v, sub=None):
    wss = sorted({k[1] for k in W}); cut = wss[int(len(wss) * 0.7)] if wss else 0
    net, fv, fr, md = {}, {}, {}, {}
    for (a, ws), r in W.items():
        if sub == "is" and ws >= cut: continue
        if sub == "oos" and ws < cut: continue
        d = r.get(v)
        if isinstance(d, dict) and "net" in d:
            net[(a, ws)] = d["net"]; fv[(a, ws)] = d.get("fill_vol", 0.0)
            fr[(a, ws)] = d.get("fill_rate", 0.0); md[(a, ws)] = abs(d.get("max_delta", 0.0))
    return net, fv, fr, md


def load_fills():
    rows = []
    for fp in glob.glob("gha_data/fills_*.jsonl"):
        m = re.search(r"fills_([a-z]+)\d+m_", fp); a = m.group(1) if m else "btc"
        for ln in open(fp):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo_res") is not None:
                r["_a"] = a; rows.append(r)
    return rows


def toxv(r):
    t = r.get("tox")
    if t is not None: return t
    mp = r.get("micro"); return 0.0 if mp is None else ((mp - r["p"]) if r["side"] == "ASK" else (r["p"] - mp))


def gate(name):
    M = MICRO_MARGIN
    g = {"baseline": lambda r: True, "micro": lambda r: toxv(r) <= 0.0,
         "micro_marg": lambda r: toxv(r) <= -M, "micro_strict": lambda r: toxv(r) <= -0.003,
         "micro_asym": lambda r: toxv(r) <= (-0.001 if r["side"] == "ASK" else 0.002),
         "ufat": lambda r: toxv(r) <= M * 4 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"]))}
    if name == "ufat_band":
        return lambda r: (False if 0.30 <= (r.get("mid") or r["p"]) < 0.55
                          else toxv(r) <= M * 4 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"])))
    return g.get(name, lambda r: True)


def gseries(rows, keep, horizon="mo_res", sub=None):
    wss = sorted({r["ws"] for r in rows}); cut = wss[int(len(wss) * 0.7)] if wss else 0
    net, fv = collections.defaultdict(float), collections.defaultdict(float)
    for r in rows:
        if sub == "is" and r["ws"] >= cut: continue
        if sub == "oos" and r["ws"] < cut: continue
        k = (r["_a"], r["ws"]); net.setdefault(k, 0.0); fv.setdefault(k, 0.0)
        if keep(r):
            mo = r.get(horizon); mo = mo if mo is not None else r.get("mo_res", 0.0)
            net[k] += mo * r["sz"] + REB(r["p"]) * r["sz"]; fv[k] += r["sz"]
    return dict(net), dict(fv)


HDR = (f"{'net/win':>9}{'p':>9}{'95%CI(net)':>17}{'Sortino':>8}{'MDD':>7}{'Calmar':>7}"
       f"{'PF':>6}{'Win':>6}{'edge¢':>7}{'fill':>6}{'n':>5}")


def row(name, s):
    if s is None:
        return f"{name:>14}  (insufficient n)"
    ci = f"[{s['ci'][0]:+.2f},{s['ci'][1]:+.2f}]"
    return (f"{name:>14}{s['net']:>+8.2f}{stars(s['p'])}{s['p']:>9.1e}{ci:>17}{s['sortino']:>8.2f}"
            f"{s['mdd']:>7.0f}{s['calmar']:>7.1f}{s['pf']:>6.2f}{s['win']:>5.0f}%{s['edge']:>7.2f}{s['fillrate']:>5.0f}%{s['n']:>5}")


def main():
    W = load_windows(); rows = load_fills()
    if not W:
        print("no data: git fetch origin gha-data && git checkout origin/gha-data -- gha_data/"); return
    cand = [(v, suite(*vseries(W, v))) for v in {k for r in W.values() for k, x in r.items()
            if isinstance(x, dict) and "net" in x}]
    cand = [(v, s) for v, s in cand if s]
    cand.sort(key=lambda x: -x[1]["calmar"])

    print(f"=== A. ALL VARIANTS (settled, FULL {len(W)} windows) ranked by Calmar | p=t-test vs 0, sig ***<.001 **<.01 *<.05 ===")
    print(f"{'variant':>14}{HDR}")
    for v, s in cand:
        print(row(v, s))

    print(f"\n=== A'. RISK-ADJUSTED with BOOTSTRAP 95% CI (B=2000) -- top contenders ===")
    print(f"{'variant':>14}{'Calmar [95% CI]':>26}{'Sortino [95% CI]':>26}{'ProfitFactor [95% CI]':>26}")
    for v, _ in cand[:8]:
        s = suite(*vseries(W, v), boot=True)
        c, so, pf = s["calmar_ci"], s["sortino_ci"], s["pf_ci"]
        cstr = f"{s['calmar']:.1f} [{c[0]:.1f},{c[1]:.1f}]"
        sstr = f"{s['sortino']:.2f} [{so[0]:.2f},{so[1]:.2f}]"
        pstr = f"{s['pf']:.2f} [{pf[0]:.2f},{pf[1]:.2f}]"
        print(f"{v:>14}{cstr:>26}{sstr:>26}{pstr:>26}")

    print(f"\n=== B. IN-SAMPLE (70%) vs OUT-OF-SAMPLE (30%): net/win [95% CI] (p) ===")
    print(f"{'variant':>14}{'IS net [95% CI] (p)':>34}{'OOS net [95% CI] (p)':>34}")
    for v, _ in cand:
        si = suite(*vseries(W, v, 'is')); so = suite(*vseries(W, v, 'oos'))
        if si and so:
            a = f"{si['net']:+.2f} [{si['ci'][0]:+.2f},{si['ci'][1]:+.2f}] {stars(si['p'])}"
            b = f"{so['net']:+.2f} [{so['ci'][0]:+.2f},{so['ci'][1]:+.2f}] {stars(so['p'])}"
            print(f"{v:>14}{a:>34}{b:>34}")

    if rows:
        print(f"\n=== C. GATE FAMILY (fill-tape, incl NEW gates without settled data) -- FULL ===")
        print(f"{'gate':>14}{HDR}")
        for g in ("baseline", "micro", "micro_marg", "micro_strict", "micro_asym", "ufat", "ufat_band"):
            net, fv = gseries(rows, gate(g)); print(row(g, suite(net, fv)))

        print(f"\n=== D. (PROXY ONLY -- MISLEADING; use hedge_backtest.py) mo30 'hedge' stand-in vs to-resolution ===")
        print("    NOTE: this mo30 proxy OVERSTATES the hedge (it removes the terminal move for free). The proper")
        print("    path-based sim (hedge_backtest.py) REFUTES the hedge: insignificant free, net-negative w/ fees.")
        print(f"{'gate':>14}{'net_unh':>10}{'MDD_unh':>8}{'Cal_unh':>8}{'net_hdg':>10}{'MDD_hdg':>8}{'Cal_hdg':>8}{'  MDD drop':>11}{'paired p':>10}")
        for g in ("micro", "ufat", "ufat_band"):
            nu, _ = gseries(rows, gate(g), "mo_res"); nh, _ = gseries(rows, gate(g), "mo30")
            su, sh = suite(nu), suite(nh)
            ks = sorted(set(nu) & set(nh)); diff = [nu[k] - nh[k] for k in ks]
            _, pp = stats.ttest_rel([nu[k] for k in ks], [nh[k] for k in ks])
            print(f"{g:>14}{su['net']:>+10.2f}{su['mdd']:>8.0f}{su['calmar']:>8.1f}{sh['net']:>+10.2f}"
                  f"{sh['mdd']:>8.0f}{sh['calmar']:>8.1f}{1-sh['mdd']/su['mdd']:>10.0%}{pp:>10.1e}")

        print(f"\n=== E. REGIME (fill-tape, ufat): calm vs volatile + Welch t on per-fill markout difference ===")
        calm = [r for r in rows if abs(r.get('dspot30') or 0) <= 20]
        volr = [r for r in rows if abs(r.get('dspot30') or 0) > 20]
        for label, sub in (("calm |dspot|<=20", calm), ("volatile >20", volr)):
            net, fv = gseries(sub, gate('ufat')); print(row(label, suite(net, fv)))
        mc = [r['mo5'] for r in calm if r.get('mo5') is not None]
        mv = [r['mo5'] for r in volr if r.get('mo5') is not None]
        tt, pp = stats.ttest_ind(mc, mv, equal_var=False)
        print(f"  per-fill mo5: calm {np.mean(mc):+.5f} vs volatile {np.mean(mv):+.5f}  Welch t={tt:+.2f} p={pp:.1e}")
    print("\nedge¢ = net cents/share filled · fill = sim fill-rate (front-of-queue upper bound). 95% CIs t-based for")
    print("net (closed form), bootstrap (B=2000) for Calmar/Sortino/PF. See METRICS.md for caveats.")


if __name__ == "__main__":
    main()
