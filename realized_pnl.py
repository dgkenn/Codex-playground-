#!/usr/bin/env python3
"""realized_pnl.py -- BALANCE-TRUTH realized P&L reconciliation for the live Kalshi 15m BTC box maker.

WHY THIS EXISTS (node METRIC-INVALID / LIVE-BLEED, 2026-07-14): our strategy validation ran on the
paper shadow layer's MARKOUT metric (5-min mid change, simulated fills, rebate-inclusive, per-win
units, scored as Δ-vs-baseline). That metric scored a *losing* live baseline at +6.9/win and crowned
av_stoikov "mega profitable, never negative" -- while the actual account BLED. Three live P&L numbers
(markout, window_mark, balance) disagree in sign. This tool computes REALIZED box P&L from the live
telemetry and RECONCILES it to the account balance, so we can score strategies on money, not markout.

Realized box economics (the ground truth for a box maker):
  - A COMPLETE (paired) box settles to exactly $1 regardless of mid. Its realized P&L is
    n_boxes*$1 - (cost_yes + cost_no)  == winrec 'window_mark' (verified identity in LIVE-BLEED).
    NEGATIVE-WIDTH completions (cost > $1) are the dominant leak (avg -13c vs +5c wins, 2.5:1).
  - A STRAND (naked leg) settles $0/$1 -> realized is winrec 'net_final' on stranded windows (high
    variance, +-$1-2 each).
  - A FRACTIONAL residual (abs_strand not integer, node F14) rides to settlement unhedged.
  Do NOT trust: 'markout' (mid proxy), 'realized' (cumulative running-sum of window_mark).

Usage:
  git fetch origin live-state
  python realized_pnl.py --start 2026-07-12T15:30 --end 2026-07-14T23:59
Reads the live-state branch directly via `git show` (files are per-run-overwritten; we dedup winrec
by cid keeping the last version, and scan metrics for the last line that actually carries a balance).
"""
import argparse, subprocess, json, datetime, calendar, statistics


def _sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def _versions(path):
    """All historical contents of a per-run-overwritten live-state file, newest first."""
    out = []
    for h in _sh("git", "log", "--format=%H", "origin/live-state", "--", path).split():
        t = _sh("git", "show", f"{h}:{path}")
        if t.strip():
            out.append(t)
    return out


def _epoch(s):
    return calendar.timegm(datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M").timetuple())


def load_winrec(days, lo, hi):
    W = {}  # cid -> last winrec seen (settled version wins because newest run overwrites)
    for d in days:
        # iterate oldest->newest so the newest version of each cid is the one kept
        for t in reversed(_versions(f"live_state/{d}/kalshi_winrec_btc15m.jsonl")):
            for l in t.splitlines():
                try:
                    w = json.loads(l)
                except Exception:
                    continue
                if lo <= (w.get("ts") or 0) <= hi:
                    W[w.get("cid")] = w
    return list(W.values())


def balance_trajectory(days, lo, hi):
    pts = []
    for d in days:
        for t in _versions(f"live_state/{d}/live_metrics_kalshi_btc15m.jsonl"):
            bal = bts = None
            for l in t.splitlines():
                try:
                    o = json.loads(l)
                except Exception:
                    continue
                r = o.get("raw")
                if isinstance(r, dict) and "balance" in r:
                    bal, bts = r["balance"], o.get("ts")
            if bal is not None and bts and lo <= bts <= hi:
                pts.append((bts, bal))
    return sorted(set(pts))


def fees(days, lo, hi):
    tot = 0.0
    seen = set()
    for d in days:
        for t in _versions(f"live_state/{d}/kalshi_fees_btc15m.jsonl"):
            for l in t.splitlines():
                try:
                    f = json.loads(l)
                except Exception:
                    continue
                k = (round(f.get("ts", 0), 3), f.get("ticker"), f.get("price"), f.get("count"))
                if k in seen or not (lo <= (f.get("ts") or 0) <= hi):
                    continue
                seen.add(k)
                try:
                    tot += float(f.get("fee_reported") or 0)
                except Exception:
                    pass
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DDTHH:MM (UTC)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DDTHH:MM (UTC)")
    a = ap.parse_args()
    lo, hi = _epoch(a.start), _epoch(a.end)
    days = sorted({datetime.datetime.utcfromtimestamp(x).strftime("%Y-%m-%d")
                   for x in range(lo, hi + 1, 3600)})

    ws = load_winrec(days, lo, hi)
    paired = [w for w in ws if not w.get("stranded") and w.get("n_boxes") and w.get("cost_yes") is not None]
    strands = [w for w in ws if w.get("stranded")]
    frac = [w for w in ws if abs((w.get("abs_strand") or 0) - round(w.get("abs_strand") or 0)) > 1e-6]

    paired_pl = sum((w.get("window_mark") or 0) for w in paired)   # == n_boxes - cost, box settles $1
    wins = [w for w in paired if (w.get("window_mark") or 0) > 1e-9]
    losses = [w for w in paired if (w.get("window_mark") or 0) < -1e-9]
    strand_pl = sum((w.get("net_final") or 0) for w in strands)
    fee_tot = fees(days, lo, hi)

    bal = balance_trajectory(days, lo, hi)
    bal_delta = (bal[-1][1] - bal[0][1]) / 100 if len(bal) >= 2 else float("nan")

    print(f"=== REALIZED P&L RECONCILIATION  {a.start} -> {a.end} ===")
    print(f"windows={len(ws)}  paired={len(paired)}  strands={len(strands)}  fractional-residual={len(frac)}")
    print("\nPAIRED-BOX REALIZED (settles to $1/box):")
    print(f"  net = $ {paired_pl:+.2f}")
    if wins and losses:
        print(f"  wins  {len(wins):3d} @ avg {100*statistics.mean([w['window_mark'] for w in wins]):+.1f}c")
        print(f"  losses{len(losses):3d} @ avg {100*statistics.mean([w['window_mark'] for w in losses]):+.1f}c  "
              f"(negative-width completions -- the leak; loss:win size ratio "
              f"{abs(statistics.mean([w['window_mark'] for w in losses])/statistics.mean([w['window_mark'] for w in wins])):.1f}:1)")
    print(f"\nSTRAND settlement (net_final): $ {strand_pl:+.2f}   (high variance, +-$1-2/strand)")
    print(f"FEES (fee_reported):           $ {-fee_tot:+.2f}")
    frac_fires = sum(1 for w in ws if (w.get("frac_flatten_count") or 0))
    print(f"F14: {len(frac)} fractional-residual windows rode to settlement | flatten fires: {frac_fires}"
          + ("  <-- BUG: fix deployed but not firing" if frac and not frac_fires else ""))

    telem = paired_pl + strand_pl - fee_tot
    print("\n=== RECONCILE ===")
    print(f"  telemetry realized (paired + strand - fees): $ {telem:+.2f}")
    print(f"  BALANCE delta (ground truth):                $ {bal_delta:+.2f}")
    print(f"  UNEXPLAINED GAP:                             $ {bal_delta - telem:+.2f}")
    print("  (gap = open-position mark at snapshot + fractional-residual settlement + window_mark's")
    print("   optimistic 'every box settles $1' assumption. A large gap means telemetry != money.)")


if __name__ == "__main__":
    main()
