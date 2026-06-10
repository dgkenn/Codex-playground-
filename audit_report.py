"""Turn the paper-run audit logs into the production blueprint's key metrics:
P&L, FILL RATE (the decisive metric), per-side balance, and MARKOUT (adverse
selection) at +5s/+30s. Read-only over audit_*.jsonl.

    python audit_report.py
"""
from __future__ import annotations

import bisect
import json
from datetime import datetime


def load(path):
    out = []
    try:
        for line in open(path):
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except FileNotFoundError:
        pass
    return out


def ts(s):
    return datetime.fromisoformat(s).timestamp()


def main():
    windows = load("audit_windows.jsonl")
    fills = load("audit_fills.jsonl")
    book = load("audit_book.jsonl")
    trades = load("audit_trades.jsonl")

    print("=== PAPER-RUN METRICS (blueprint) ===")
    # --- P&L from settled windows ---
    if windows:
        net = sum(w["net"] for w in windows); gross = sum(w["gross"] for w in windows)
        reb = sum(w["rebate"] for w in windows); nf = sum(w["fills"] for w in windows)
        pos = sum(1 for w in windows if w["net"] > 0)
        print(f"P&L: {len(windows)} settled windows | net={net:+.3f} gross={gross:+.3f} "
              f"rebate={reb:+.3f} | net/window={net/len(windows):+.4f} | "
              f"positive windows={pos}/{len(windows)} | fills={nf}")
        mb = sum(w.get("mk_buy", 0) for w in windows); ms = sum(w.get("mk_sell", 0) for w in windows)
        print(f"per-side fills: maker-BUY={mb} maker-SELL={ms} (balance={'ok' if min(mb,ms)>0 else 'one-sided'})")
    else:
        print("P&L: no settled windows yet")

    # --- fill rate (capture proxy): our fills vs observed trades ---
    print(f"FILL RATE: our fills={len(fills)} | observed trades={len(trades)} | "
          f"capture={len(fills)/max(len(trades),1):.2%} of trades")

    # --- markout / adverse selection from fills + book mids ---
    bypfx = {}
    for b in book:
        if b.get("bb") is not None and b.get("ba") is not None:
            bypfx.setdefault(b["token"], []).append((ts(b["ts"]), (b["bb"] + b["ba"]) / 2))
    for k in bypfx:
        bypfx[k].sort()

    def mid_at(pfx, t):
        arr = bypfx.get(pfx)
        if not arr:
            return None
        i = bisect.bisect_left(arr, (t, -1))
        return arr[i][1] if i < len(arr) else (arr[-1][1] if arr else None)

    for horizon in (5, 30):
        mks = []
        for f in fills:
            pfx = f.get("token") or str(f.get("asset", ""))[:12]   # WS uses 'token', polling used 'asset'
            if not pfx:
                continue
            m = mid_at(pfx, ts(f["ts"]) + horizon)
            if m is None:
                continue
            # taker BUY -> we SOLD (short): favorable if mid falls; taker SELL -> we BOUGHT (long)
            mk = (f["fill_price"] - m) if f["taker_side"] == "BUY" else (m - f["fill_price"])
            mks.append(mk)
        if mks:
            avg = sum(mks) / len(mks)
            print(f"MARKOUT +{horizon}s: mean={avg:+.5f}/share over {len(mks)} fills "
                  f"({'adverse (picked off)' if avg < -0.001 else 'ok' if avg > -0.001 else 'flat'})")
        else:
            print(f"MARKOUT +{horizon}s: insufficient book overlap yet")
    print("\nNote: markout here marks at MID (queue-favorable); true fill quality needs tiny-live orders.")


if __name__ == "__main__":
    main()
