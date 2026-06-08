"""leaderboard.py -- rank ALL strategy variants from the live paper-trading windows. Splits the windows by
time into IN-SAMPLE ("backtest", first 70%) and OUT-OF-SAMPLE ("prospective", last 30%) so you see both
the backtest standing and whether the edge HOLDS forward. Per variant: net/win, win-rate, GROSS/win
(edge beyond rebate), fills/win, paired-t vs baseline. python leaderboard.py
"""
from __future__ import annotations
import glob, json, math


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
    pairs = [r[v]["net"] - r[base]["net"] for r in rows if v in r and base in r
             and isinstance(r[v], dict) and isinstance(r[base], dict)]
    t = float("nan")
    if len(pairs) >= 2 and v != base:
        dm = sum(pairs) / len(pairs); sd = (sum((x - dm) ** 2 for x in pairs) / (len(pairs) - 1)) ** 0.5
        t = dm / (sd / math.sqrt(len(pairs))) if sd > 0 else float("nan")
    return {"net": mean, "gross": gm, "win": winr, "fills": sum(fl) / n, "t": t, "n": n}


def board(rows, title):
    variants = sorted({k for r in rows for k, v in r.items() if isinstance(v, dict) and "net" in v})
    table = [(v, stats(rows, v)) for v in variants]
    table = [(v, s) for v, s in table if s]
    table.sort(key=lambda x: -x[1]["net"])
    print(f"\n=== {title} ({len(rows)} windows) ===")
    print(f"{'#':>3} {'variant':>13} {'net/win':>8} {'win%':>5} {'GROSS/w':>8} {'t vs base':>9} {'fills/w':>7}")
    for i, (v, s) in enumerate(table, 1):
        edge = " <edge>" if s["gross"] == s["gross"] and s["gross"] > 0 else ""
        tt = f"{s['t']:+.2f}" if s["t"] == s["t"] else "  --"
        print(f"{i:>3} {v:>13} {s['net']:>+8.2f} {s['win']:>4.0f}% {s['gross']:>+8.2f} {tt:>9} {s['fills']:>7.0f}{edge}")


def main():
    rows = load()
    if not rows:
        print("no shadow windows (sync gha-data first)"); return
    cut = int(len(rows) * 0.7)
    board(rows, "FULL — prospective live paper (all variants ranked by net/win)")
    board(rows[:cut], "IN-SAMPLE / backtest (first 70% of windows)")
    board(rows[cut:], "OUT-OF-SAMPLE / prospective (last 30% — does the edge HOLD?)")
    print("\nRead: net/win is rebate-inclusive (the deployable P&L); GROSS/win>0 = edge beyond the rebate "
          "(<edge>); t vs base = significance over baseline. A real edge ranks high in BOTH IS and OOS.")


if __name__ == "__main__":
    main()
