#!/usr/bin/env python3
"""ofi_forward.py -- forward scorer for the PRE-REGISTERED EXO-OFI experiment (node EXO-OFI).

Implements the FROZEN rule in OFI_FORWARD.md. Joins Coinbase signed-flow snapshots
(gha_data/<day>/ofi_coinbase_<asset>_r*.jsonl.gz) to Kalshi 15m windows (from the tick archive,
which supplies each window's start `ws`, the decision-instant Kalshi bid/ask at t<=720, and the
terminal outcome = final mid>0.5), and computes the pooled day-clustered gate. No tuning knobs:
signal = OFI over [ws+600, ws+720] normalized by trailing-30-window median |OFI|; threshold Z=1.0;
bet WITH the flow; net Kalshi fees. Prints CLOCK-NOT-STARTED until >=10 forward days of OFI exist.

Run: `python ofi_forward.py`  (fetches gha-data, scores, prints gate; writes ofi_forward_log.jsonl)
     `python ofi_forward.py --report`  (gate from the log without re-fetching)
"""
import subprocess, gzip, json, re, math, statistics, os, sys
from collections import defaultdict

KFEE = lambda p: 0.07 * p * (1 - p)
DECISION_T = 720
Z = 1.0                       # FROZEN threshold (pre-registered)
ASSETS = ["btc", "eth", "sol"]
LOG = "ofi_forward_log.jsonl"


def _sh_bytes(*a):
    return subprocess.run(a, capture_output=True).stdout


def _ls(branch):
    return subprocess.run(["git", "ls-tree", "-r", "--name-only", branch],
                          capture_output=True, text=True).stdout.splitlines()


def kalshi_windows(asset):
    """{ws_unix: (day, dec_bid, dec_ask, outcome)} from the tick archive for one asset."""
    out = {}
    for f in _ls("origin/gha-data"):
        if f"ticks_kalshi_{asset}15m" not in f:
            continue
        m = re.search(r"(2026-\d\d-\d\d)", f)
        if not m:
            continue
        try:
            txt = gzip.decompress(_sh_bytes("git", "show", f"origin/gha-data:{f}")).decode()
        except Exception:
            continue
        for l in txt.splitlines():
            try:
                d = json.loads(l)
            except Exception:
                continue
            ws = d.get("ws")
            tks = d.get("ticks", [])
            if ws is None or len(tks) < 20:
                continue
            tks = sorted(tks, key=lambda x: x[0])
            if tks[0][0] > 120 or tks[-1][0] < 780:
                continue
            mc = tks[-1][1]
            if mc is None:
                continue
            outcome = 1 if mc > 0.5 else 0
            dec = None
            for tk in tks:
                if tk[0] <= DECISION_T:
                    dec = tk
                else:
                    break
            if dec is None:
                continue
            bid, ask = dec[4], dec[6]
            if None in (bid, ask):
                continue
            out[int(ws)] = (m.group(1), bid, ask, outcome)
    return out


def ofi_snapshots(asset):
    """List of (ts, ofi) for one asset from all collected ofi_coinbase files."""
    rows = []
    for f in _ls("origin/gha-data"):
        if f"ofi_coinbase_{asset}_" not in f:
            continue
        try:
            txt = gzip.decompress(_sh_bytes("git", "show", f"origin/gha-data:{f}")).decode()
        except Exception:
            continue
        for l in txt.splitlines():
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("ts") is not None and r.get("ofi") is not None:
                rows.append((float(r["ts"]), float(r["ofi"])))
    rows.sort()
    return rows


def ofi_2m(snaps, ws):
    """(net OFI, gross |OFI|) over [ws+600, ws+720]."""
    lo, hi = ws + 600, ws + 720
    net = gross = 0.0
    got = False
    for ts, ofi in snaps:
        if ts < lo:
            continue
        if ts > hi:
            break
        net += ofi
        gross += abs(ofi)
        got = True
    return (net, gross) if got else (None, None)


def score():
    per_day = defaultdict(list)          # (asset,day) -> list of pnl
    for asset in ASSETS:
        wins = kalshi_windows(asset)
        snaps = ofi_snapshots(asset)
        if not snaps:
            continue
        # windows sorted by ws so trailing-median scale uses prior windows only (causal)
        trailing = []
        for ws in sorted(wins):
            day, bid, ask, outcome = wins[ws]
            net, gross = ofi_2m(snaps, ws)
            if net is None:
                continue
            scale = statistics.median(trailing) if len(trailing) >= 5 else None
            trailing.append(gross)
            if len(trailing) > 30:
                trailing.pop(0)
            if not scale or scale <= 0:
                continue
            S = net / scale
            if abs(S) < Z:
                continue
            if S > 0:
                pl = outcome - ask - KFEE(ask)
            else:
                pl = bid - outcome - KFEE(bid)
            per_day[(asset, day)].append(pl)
    return per_day


def gate(per_day):
    dm = {k: statistics.mean(v) for k, v in per_day.items() if v}
    means = list(dm.values())
    ndays = len(means)
    if ndays < 2:
        return dict(status="CLOCK-NOT-STARTED", ndays=ndays, t=float("nan"), mean=float("nan"))
    sd = statistics.stdev(means)
    t = statistics.mean(means) / (sd / math.sqrt(ndays)) if sd > 0 else float("nan")
    btc_mean = statistics.mean([v for (a, d), v in dm.items() if a == "btc"]) \
        if any(a == "btc" for a, d in dm) else float("nan")
    forward_days = len(set(d for a, d in dm))
    if forward_days >= 10 and t >= 2 and (btc_mean > 0):
        status = "PASS"
    elif forward_days >= 10 and t < 0:
        status = "KILL"
    else:
        status = "ACCRUING"
    return dict(status=status, ndays=ndays, forward_days=forward_days, t=t,
                mean=statistics.mean(means), btc_mean=btc_mean)


def main():
    if "--report" not in sys.argv:
        subprocess.run(["git", "fetch", "origin", "gha-data", "--depth=200"],
                       capture_output=True)
    per_day = score()
    g = gate(per_day)
    print("EXO-OFI forward gate (frozen rule; Z=1.0; net Kalshi fees)")
    print(f"  status={g['status']}  asset-days={g['ndays']}  "
          f"forward-days={g.get('forward_days','?')}  pooled t={g['t']:.2f}  "
          f"mean=${g['mean']:+.4f}/ct  btc-mean=${g.get('btc_mean',float('nan')):+.4f}")
    if g["status"] == "CLOCK-NOT-STARTED":
        print("  No joined OFI+window data yet — collector must accrue. Gate opens at >=10 forward days.")
    # persist a snapshot row for the record
    try:
        with open(LOG, "a") as fh:
            fh.write(json.dumps(dict(g)) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
