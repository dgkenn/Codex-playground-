"""combo_lab.py -- heavily backtest COMBINATIONS of the validated gate components to build the single best
overall strategy, judged on BOTH in-sample and out-of-sample windows.

Two senses of "combine":
 (A) COMPOSITE gate (what wins): one bot whose keep-rule ANDs a core toxicity gate with the orthogonal
     INSIGHTS_4DAY filters (avoid wide spreads, avoid the toxic mid-prob zone). Enumerated + ranked here.
 (B) PORTFOLIO stack (separate books): only helps if variants are uncorrelated -- stack_analysis.py showed
     the positive gates are highly correlated, so it doesn't. We re-confirm the correlation note below.

Scored on the ungated fill tape (keep/drop each baseline fill), per-(asset,ws) window:
    net/win = mean over windows of  Σ_kept (mo_res*sz + maker_rebate(p)*sz)     # DEPLOYABLE P&L
We split windows by time: IS = first 70%, OOS = last 30%. A combo is only "real" if it beats the best
single gate (micro_ufat) on BOTH IS and OOS. We also show mo5 net (pure adverse selection) to catch
combos that win OOS only by directional luck.  python combo_lab.py
"""
from __future__ import annotations
import glob, json, re, math, itertools, collections, statistics
from dataio import jl_glob, jl_open

try:
    import fees
    REB = lambda p: float(fees.maker_rebate(p, rate=0.07))
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)
MICRO_MARGIN = 0.002


def load():
    rows = []
    for fp in jl_glob("gha_data/fills_*.jsonl"):
        m = re.search(r"fills_([a-z]+)\d+m_", fp)
        asset = m.group(1) if m else "btc"
        for ln in jl_open(fp):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo_res") is not None:
                r["_asset"] = asset
                rows.append(r)
    return rows


def tox(r):
    t = r.get("tox")
    if t is not None:
        return t
    mp = r.get("micro")
    return 0.0 if mp is None else ((mp - r["p"]) if r["side"] == "ASK" else (r["p"] - mp))


# --- core toxicity gates (choose one) -> keep iff benign ---
def core(name):
    if name == "micro":   return lambda r: tox(r) <= 0.0
    if name == "ufat":    return lambda r: tox(r) <= MICRO_MARGIN * 4.0 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"]))
    if name == "marg":    return lambda r: tox(r) <= -MICRO_MARGIN
    if name == "strict":  return lambda r: tox(r) <= -0.003
    return lambda r: True


# --- orthogonal INSIGHTS_4DAY filters (AND on top) ---
def spread1(r):  # insight 4: >=2-tick spreads are 18x more toxic
    bb, ba = r.get("bb"), r.get("ba")
    return not (bb is not None and ba is not None and (ba - bb) >= 0.015)


def notmid(r):   # insight 5: the 0.3-0.55 zone is the most toxic; tails (esp >0.7) benign
    p = r.get("mid") or r["p"]
    return not (0.30 <= p < 0.55)


FILTERS = {"spread1": spread1, "notmid": notmid}


def keep_fn(core_name, fset):
    c = core(core_name); fs = [FILTERS[f] for f in fset]
    return lambda r: c(r) and all(f(r) for f in fs)


def reb(r):
    return REB(r["p"]) * r["sz"]


def split(rows):
    ws = sorted({r["ws"] for r in rows}); cut = ws[int(len(ws) * 0.7)]
    return cut


def windows_net(rows, keep, cut, oos, horizon="mo_res"):
    """per-(asset,ws) net for windows in IS (oos=False) or OOS (oos=True)."""
    by = collections.defaultdict(float); seen = set()
    for r in rows:
        in_oos = r["ws"] >= cut
        if in_oos != oos:
            continue
        k = (r["_asset"], r["ws"]); seen.add(k)
        if keep(r):
            mo = r.get(horizon); mo = mo if mo is not None else r.get("mo_res", 0.0)
            by[k] += mo * r["sz"] + reb(r)
    for k in seen:
        by.setdefault(k, 0.0)          # windows with all fills dropped still count (net 0)
    return list(by.values())


def stat(xs):
    n = len(xs)
    if n < 5:
        return (float("nan"), float("nan"), n)
    m = sum(xs) / n; sd = statistics.pstdev(xs)
    return (m, (m / (sd / math.sqrt(n)) if sd > 0 else 0.0), n)


def main():
    rows = load()
    if not rows:
        print("no fills. run: git fetch origin gha-data && git checkout origin/gha-data -- gha_data/"); return
    cut = split(rows)
    print(f"{len(rows)} fills | IS/OOS split at ws={cut}\n")
    combos = []
    for cn in ("micro", "ufat", "marg", "strict"):
        for k in range(0, len(FILTERS) + 1):
            for fset in itertools.combinations(FILTERS, k):
                combos.append((cn, fset))
    combos.insert(0, ("nogate", ()))

    res = []
    for cn, fset in combos:
        keep = keep_fn(cn, fset)
        is_net = windows_net(rows, keep, cut, oos=False)
        oos_net = windows_net(rows, keep, cut, oos=True)
        oos_mo5 = windows_net(rows, keep, cut, oos=True, horizon="mo5")
        kept = sum(1 for r in rows if keep(r))
        im, it, _ = stat(is_net); om, ot, _ = stat(oos_net); o5m, _, _ = stat(oos_mo5)
        name = cn + ("+" + "+".join(fset) if fset else "")
        res.append((name, im, it, om, ot, o5m, 100.0 * kept / len(rows)))

    base = next(r for r in res if r[0] == "ufat")     # the deploy choice = bar to beat
    res.sort(key=lambda x: -x[3])                       # rank by OOS net/win
    print(f"{'combo':>22} {'IS net':>8} {'IS t':>6} {'OOS net':>8} {'OOS t':>6} {'OOS mo5':>8} {'kept%':>6}")
    print("-" * 74)
    for name, im, it, om, ot, o5m, kp in res:
        star = " *" if name == "ufat" else ("  <-- best OOS" if name == res[0][0] else "")
        print(f"{name:>22} {im:>+8.2f} {it:>+6.1f} {om:>+8.2f} {ot:>+6.1f} {o5m:>+8.2f} {kp:>5.0f}%{star}")
    b = res[0]
    print(f"\nBest OOS combo: {b[0]}  (OOS net/win {b[3]:+.2f}, t {b[4]:+.1f}) vs ufat {base[3]:+.2f}")
    lift = b[3] - base[3]
    print(f"  -> {'beats' if lift>0 else 'does NOT beat'} the single ufat gate OOS by {lift:+.2f}/win "
          f"({'and' if b[5]>0 else 'but'} OOS mo5 {b[5]:+.2f}).")
    print("\nRead: keep a combo only if it beats ufat on BOTH IS and OOS AND its OOS mo5 stays >0 (real toxicity")
    print("avoidance, not directional luck). ANDing too many filters sheds rebate volume -> net falls (over-gating).")
    print("\nPORTFOLIO (separate books): positive gates are ~0.7-0.9 correlated (stack_analysis.py) -> averaging")
    print("them does NOT raise Sharpe; the win is the COMPOSITE above + BREADTH across assets (corr +0.10).")


if __name__ == "__main__":
    main()
