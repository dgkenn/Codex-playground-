"""leaderboard.py -- rank ALL strategy variants from the live paper-trading windows, RISK-ADJUSTED.
Splits windows into IN-SAMPLE (first 70%) and OUT-OF-SAMPLE (last 30%). Per variant: net/win (+p, 95% CI),
win-rate, GROSS/win, Sortino, MDD, Calmar, paired-t vs baseline. Ranked by Calmar (return per unit of worst
drawdown) -- not raw net -- because a higher-net variant with a fat drawdown is worse (see METRICS.md).
For the full per-(asset,window) suite with bootstrap CIs use metrics.py. python leaderboard.py
"""
from __future__ import annotations
import glob, json, math, statistics
try:
    from scipy import stats as _st
except Exception:
    _st = None


def load():
    by_ws = {}
    for fp in sorted(glob.glob("gha_data/shadow_windows_*.jsonl")):
        for ln in open(fp):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("ws") is not None:
                by_ws.setdefault(r["ws"], r)          # dedupe by window
    return [by_ws[k] for k in sorted(by_ws)]


def stats(rows, v, base="baseline"):
    nets = [r[v]["net"] for r in rows if v in r and isinstance(r[v], dict) and "net" in r[v]]
    if not nets:
        return None
    n = len(nets); mean = sum(nets) / n
    gr = [r[v].get("gross") for r in rows if v in r and isinstance(r[v], dict) and r[v].get("gross") is not None]
    gm = sum(gr) / len(gr) if gr else float("nan")
    fl = [r[v].get("fills", 0) for r in rows if v in r and isinstance(r[v], dict)]
    winr = 100 * sum(1 for x in nets if x > 0) / n
    # risk-adjusted: Sortino (downside dev), MDD (cum equity path), Calmar (total/ MDD)
    dd = statistics.pstdev([min(x, 0.0) for x in nets]) if n > 1 else 0.0
    sortino = (mean / dd) if dd > 0 else float("nan")
    cum = peak = worst = 0.0
    for x in nets:
        cum += x; peak = max(peak, cum); worst = min(worst, cum - peak)
    mdd = -worst; calmar = (cum / mdd) if mdd > 0 else float("inf")
    # net/win significance + 95% CI (one-sample vs 0)
    sd0 = statistics.stdev(nets) if n > 1 else float("nan"); sem = sd0 / math.sqrt(n) if n > 1 else float("nan")
    if _st is not None and n > 1 and sem > 0:
        _, p = _st.ttest_1samp(nets, 0.0); lo, hi = _st.t.interval(0.95, n - 1, loc=mean, scale=sem)
    else:
        p, lo, hi = float("nan"), float("nan"), float("nan")
    pairs = [r[v]["net"] - r[base]["net"] for r in rows if v in r and base in r
             and isinstance(r[v], dict) and isinstance(r[base], dict)]
    t = float("nan")
    if len(pairs) >= 2 and v != base:
        dm = sum(pairs) / len(pairs); sd = (sum((x - dm) ** 2 for x in pairs) / (len(pairs) - 1)) ** 0.5
        t = dm / (sd / math.sqrt(len(pairs))) if sd > 0 else float("nan")
    return {"net": mean, "gross": gm, "win": winr, "fills": sum(fl) / n, "t": t, "n": n,
            "sortino": sortino, "mdd": mdd, "calmar": calmar, "p": p, "ci": (lo, hi)}


def board(rows, title):
    variants = sorted({k for r in rows for k, v in r.items() if isinstance(v, dict) and "net" in v})
    table = [(v, stats(rows, v)) for v in variants]
    table = [(v, s) for v, s in table if s]
    table.sort(key=lambda x: -x[1]["calmar"])      # rank by RISK-ADJUSTED return, not raw net
    print(f"\n=== {title} ({len(rows)} windows) -- ranked by Calmar ===")
    print(f"{'#':>3} {'variant':>13} {'net/win':>8} {'p':>8} {'95%CI(net)':>16} {'win%':>5} "
          f"{'GROSS/w':>8} {'Sortino':>7} {'MDD':>6} {'Calmar':>7} {'fills/w':>7}")
    for i, (v, s) in enumerate(table, 1):
        edge = " <edge>" if s["gross"] == s["gross"] and s["gross"] > 0 else ""
        ci = f"[{s['ci'][0]:+.1f},{s['ci'][1]:+.1f}]" if s["ci"][0] == s["ci"][0] else "--"
        pp = f"{s['p']:.1e}" if s["p"] == s["p"] else "--"
        print(f"{i:>3} {v:>13} {s['net']:>+8.2f} {pp:>8} {ci:>16} {s['win']:>4.0f}% "
              f"{s['gross']:>+8.2f} {s['sortino']:>7.2f} {s['mdd']:>6.0f} {s['calmar']:>7.1f} {s['fills']:>7.0f}{edge}")


def main():
    rows = load()
    if not rows:
        print("no shadow windows (sync gha-data first)"); return
    cut = int(len(rows) * 0.7)
    board(rows, "FULL — prospective live paper")
    board(rows[:cut], "IN-SAMPLE / backtest (first 70% of windows)")
    board(rows[cut:], "OUT-OF-SAMPLE / prospective (last 30% — does the edge HOLD?)")
    print("\nRead: ranked by CALMAR (return per unit of max-drawdown) -- a high-net variant with a fat MDD "
          "is worse. net/win is rebate-inclusive deployable P&L (p, 95% CI vs 0); GROSS/win>0 = edge beyond "
          "the rebate (<edge>). NOTE: windows deduped by ws here (collapses assets); metrics.py is the full "
          "per-(asset,window) suite with bootstrap CIs. A real edge ranks high on Calmar in BOTH IS and OOS.")


if __name__ == "__main__":
    main()
