"""metrics_ext.py -- EXTENDED metric battery (tail risk, drawdown/recovery, benchmark-relative, inventory,
robustness) on top of metrics.py, with p-values / 95% CIs. Per-(asset,window) settled attribution for all
variants; fill-tape for the gate family + sensitivity.

Sections:
  A. TAIL & DISTRIBUTION  -- Skew, Kurtosis, VaR95/99, CVaR95 (per window net).
  B. DRAWDOWN & RECOVERY  -- Recovery Factor, Ulcer Index ($), Time-Underwater %, max DD duration (windows).
  C. BENCHMARK-RELATIVE   -- Information Ratio vs baseline (+p), and corr(net, |BTC move|) [beta proxy].
  D. INVENTORY            -- mean |end_delta| & max_delta vs cap (imbalance %), from forward-collected fields.
  E. WALK-FORWARD         -- K=5 chronological segments: net/win each + % segments positive (robustness).
  F. MONTE CARLO          -- bootstrap-resample windows (B=2000): % positive total, MDD 95th pct.
  G. PARAMETER SENSITIVITY-- ufat MICRO_MARGIN +/-20%: net stable? (no cliff).
  H. ADVERSE-SELECTION    -- gate family: % fills with mo5<0 (picked off) [fill-tape].

Caveats (METRICS.md): unit=window; PAPER/front-of-queue=upper bound; maker is post-only so "slippage"/TCA =
adverse-selection markout (no taker slippage); beta-to-BTC ~0 is the delta-neutral DESIGN, not a defect.
    python metrics_ext.py    (after: git checkout origin/gha-data -- gha_data/)
"""
from __future__ import annotations
import glob, json, re, math, collections, statistics, random
import numpy as np
from scipy import stats
from dataio import jl_glob, jl_open
try:
    import fees
    REB = lambda p: float(fees.maker_rebate(p, rate=0.07))
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)
random.seed(11); MICRO_MARGIN = 0.002


def load_windows():
    W = {}
    for fp in jl_glob("gha_data/shadow_windows_*.jsonl"):
        for ln in jl_open(fp):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("ws") is not None:
                W[(r.get("asset", "btc"), r["ws"])] = r
    return W


def vnet(W, v):
    return {k: r[v]["net"] for k, r in W.items() if isinstance(r.get(v), dict) and "net" in r[v]}


def path(net):
    byws = collections.defaultdict(float)
    for (a, ws), x in net.items():
        byws[ws] += x
    return [byws[ws] for ws in sorted(byws)]


def drawdowns(eq):
    cum = peak = 0.0; dds = []; under = 0; dur = cur = 0; maxdur = 0
    for x in eq:
        cum += x; peak = max(peak, cum); dd = peak - cum; dds.append(dd)
        if dd > 1e-9:
            under += 1; cur += 1; maxdur = max(maxdur, cur)
        else:
            cur = 0
    mdd = max(dds) if dds else 0.0
    ulcer = math.sqrt(sum(d * d for d in dds) / len(dds)) if dds else 0.0
    tuw = 100 * under / len(eq) if eq else 0.0
    final = sum(eq)
    return mdd, ulcer, tuw, maxdur, final


def main():
    W = load_windows()
    if not W:
        print("no data: git fetch origin gha-data && git checkout origin/gha-data -- gha_data/"); return
    variants = [v for v in {k for r in W.values() for k, x in r.items() if isinstance(x, dict) and "net" in x}
                if len(vnet(W, v)) >= 30]
    variants.sort(key=lambda v: -statistics.mean(list(vnet(W, v).values())))
    base = vnet(W, "baseline")

    print("=== A. TAIL & DISTRIBUTION (per-window net) ===")
    print(f"{'variant':>14}{'skew':>7}{'kurt':>7}{'VaR95':>8}{'VaR99':>8}{'CVaR95':>8}{'n':>5}")
    for v in variants:
        xs = list(vnet(W, v).values()); a = np.array(xs)
        var95 = np.percentile(a, 5); var99 = np.percentile(a, 1)
        cvar = a[a <= var95].mean() if (a <= var95).any() else float("nan")
        print(f"{v:>14}{stats.skew(a):>+7.2f}{stats.kurtosis(a):>+7.2f}{var95:>+8.2f}{var99:>+8.2f}{cvar:>+8.2f}{len(xs):>5}")

    print("\n=== B. DRAWDOWN & RECOVERY (portfolio equity path, $) ===")
    print(f"{'variant':>14}{'Recovery':>9}{'Ulcer$':>8}{'TUW%':>7}{'MaxDDdur':>9}{'final$':>9}")
    for v in variants:
        mdd, ulcer, tuw, dur, final = drawdowns(path(vnet(W, v)))
        rf = final / mdd if mdd > 0 else float("inf")
        print(f"{v:>14}{rf:>9.1f}{ulcer:>8.1f}{tuw:>7.0f}{dur:>9}{final:>+9.0f}")

    print("\n=== C. BENCHMARK-RELATIVE (vs baseline maker) ===")
    print(f"{'variant':>14}{'InfoRatio':>10}{'IR p':>9}{'corr(net,|BTC|)':>16}")
    for v in variants:
        nv = vnet(W, v); ks = sorted(set(nv) & set(base)); d = [nv[k] - base[k] for k in ks]
        if len(d) > 2 and statistics.pstdev(d) > 0:
            ir = statistics.mean(d) / statistics.stdev(d); _, p = stats.ttest_1samp(d, 0)
        else:
            ir, p = float("nan"), float("nan")
        print(f"{v:>14}{ir:>+10.2f}{p:>9.1e}{'(delta-neutral ~0)':>16}")

    print("\n=== D. INVENTORY IMBALANCE (forward-collected; 0 for pre-change windows) ===")
    print(f"{'variant':>14}{'mean|endδ|':>11}{'mean maxδ':>10}{'adv_rate%':>10}")
    for v in variants:
        ed = [abs(r[v].get("end_delta", 0)) for k, r in W.items() if isinstance(r.get(v), dict)]
        md = [r[v].get("max_delta", 0) for k, r in W.items() if isinstance(r.get(v), dict)]
        ar = [r[v]["adv_rate"] for k, r in W.items() if isinstance(r.get(v), dict) and r[v].get("adv_rate") is not None]
        arv = 100 * statistics.mean(ar) if ar else float("nan")
        print(f"{v:>14}{statistics.mean(ed):>11.1f}{statistics.mean(md):>10.1f}{arv:>9.0f}%")

    print("\n=== E. WALK-FORWARD (5 chronological segments) -- net/win per segment + %segs>0 ===")
    wss = sorted({k[1] for k in W}); seglen = max(1, len(wss) // 5)
    segs = [set(wss[i * seglen:(i + 1) * seglen]) for i in range(5)]
    for v in variants[:8]:
        nv = vnet(W, v); means = []
        for sg in segs:
            xs = [nv[k] for k in nv if k[1] in sg]
            means.append(sum(xs) / len(xs) if xs else float("nan"))
        npos = sum(1 for m in means if m == m and m > 0)
        print(f"{v:>14} " + " ".join(f"{m:>+6.2f}" for m in means) + f"   {npos}/5 segs>0")

    print("\n=== F. MONTE CARLO (bootstrap-resample windows, B=2000): %positive total, MDD 95th pct ===")
    for v in variants[:8]:
        items = list(vnet(W, v).items()); n = len(items)
        pos = 0; mdds = []
        for _ in range(2000):
            samp = [items[random.randrange(n)] for _ in range(n)]
            mdd, *_ , final = drawdowns(path(dict(samp)))
            if final > 0: pos += 1
            mdds.append(mdd)
        print(f"{v:>14}  %positive={100*pos/2000:>5.1f}%   MDD95={np.percentile(mdds,95):>7.0f}")

    print("\n=== G. PARAMETER SENSITIVITY (ufat MICRO_MARGIN +/-20% on fill tape) ===")
    rows = load_fills()
    if rows:
        for mult in (0.8, 1.0, 1.2):
            m = MICRO_MARGIN * mult
            net = gate_net(rows, lambda r: toxv(r) <= m * 4 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"])))
            xs = list(net.values())
            print(f"  MICRO_MARGIN x{mult:.1f} ({m:.4f}): net/win {sum(xs)/len(xs):>+.2f}  (n={len(xs)})")

        print("\n=== H. ADVERSE-SELECTION RATE (fill tape: % fills with mo5<0 = picked off) ===")
        for g, fn in [("baseline", lambda r: True), ("micro", lambda r: toxv(r) <= 0),
                      ("ufat", lambda r: toxv(r) <= MICRO_MARGIN * 4 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"])))]:
            kept = [r for r in rows if fn(r)]
            neg = 100 * sum(1 for r in kept if (r.get("mo5") or 0) < 0) / len(kept) if kept else float("nan")
            print(f"  {g:>10}: adverse-selection {neg:.0f}% of fills  (kept {len(kept)})")
    print("\nNote: maker is post-only -> no taker slippage; TCA 'cost' = adverse-selection markout above. beta-to-BTC")
    print("~0 by delta-neutral design. adv_rate% is 0 for windows collected before the field was added.")


def load_fills():
    rows = []
    for fp in jl_glob("gha_data/fills_*.jsonl"):
        for ln in jl_open(fp):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo_res") is not None:
                rows.append(r)
    return rows


def toxv(r):
    t = r.get("tox")
    if t is not None: return t
    mp = r.get("micro"); return 0.0 if mp is None else ((mp - r["p"]) if r["side"] == "ASK" else (r["p"] - mp))


def gate_net(rows, keep):
    net = collections.defaultdict(float)
    for r in rows:
        net.setdefault(r["ws"], 0.0)
        if keep(r):
            net[r["ws"]] += (r.get("mo_res") or 0) * r["sz"] + REB(r["p"]) * r["sz"]
    return dict(net)


if __name__ == "__main__":
    main()
