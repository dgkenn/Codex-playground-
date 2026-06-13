#!/usr/bin/env python3
"""live_gate.py -- the LIVE re-validation gate monitor (live RCA 2026-06-13).

Reads the real-money microstructure telemetry the trader now writes -- kalshi_winrec_<asset>15m.jsonl
(per-window: strand state, legging gap, maker/taker mix, dispose-cross firing, box costs) -- across
the FULL live-state git history (the file is overwritten per cycle, so we walk every commit and dedup
by ws). Falls back to reconstructing strands from kalshi_fees if winrecs are absent (pre-fix cycles).

This is the ONLY validator that captures live fill dynamics (the tape/shadow A/B mis-modeled strands
4x: predicted 13%, live was 48%). The shadow A/B (box_policy_ab.py) stays the forward paper-test; THIS
measures the real-money truth and the GO/NO-GO gate after the dispose-cross + rate fixes.

Usage:  python live_gate.py [--asset btc] [--day 2026-06-13]
Run from a repo with the live-state branch fetched (it walks origin/live-state history).
"""
import argparse, json, subprocess, datetime as dt
from collections import defaultdict

def _walk(path):
    """All unique json lines of `path` across origin/live-state history (per-cycle overwrite)."""
    try:
        commits = subprocess.check_output(["git", "log", "--format=%H", "origin/live-state"]).decode().split()
    except Exception:
        return []
    out = []
    for c in commits:
        try:
            blob = subprocess.check_output(["git", "show", f"{c}:{path}"], stderr=subprocess.DEVNULL).decode()
        except Exception:
            continue
        for ln in blob.splitlines():
            if ln.strip():
                try: out.append(json.loads(ln))
                except Exception: pass
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--day", default=dt.datetime.utcnow().strftime("%Y-%m-%d"))
    a = ap.parse_args()
    base = f"live_state/{a.day}"
    # ---- primary: per-window microstructure records (post-fix) ----
    wr = {}
    for r in _walk(f"{base}/kalshi_winrec_{a.asset}15m.jsonl"):
        if "ws" in r: wr[r["ws"]] = r
    winrecs = sorted(wr.values(), key=lambda r: r["ws"])

    print(f"=== LIVE RE-VALIDATION GATE [{a.asset} {a.day}] ===")
    if winrecs:
        n = len(winrecs)
        strand = [w for w in winrecs if w.get("stranded")]
        sr = 100.0 * len(strand) / n
        legs = [w["legging_gap_s"] for w in winrecs if w.get("legging_gap_s") is not None]
        legs.sort()
        taker = sum(w.get("n_taker", 0) for w in winrecs)
        maker = sum(w.get("n_maker", 0) for w in winrecs)
        xcross = sum(w.get("n_dispose_cross", 0) for w in winrecs)
        boxes = sum(w.get("n_boxes", 0) for w in winrecs)
        # per-window net P&L proxy from costs + settlement: payout(winning contracts) - cost
        pnl = 0.0; have_settle = 0
        for w in winrecs:
            s = w.get("settle")
            if s not in ("yes", "no"):
                continue
            have_settle += 1
            # winning $ = (#yes contracts if settle yes else #no), cost = cost_yes+cost_no
            ny = w.get("n_yes", 0); nn = w.get("n_no", 0)
            win = ny if s == "yes" else nn
            pnl += win - (w.get("cost_yes", 0.0) + w.get("cost_no", 0.0))
        med_leg = legs[len(legs)//2] if legs else float("nan")
        p90_leg = legs[int(.9*len(legs))] if legs else float("nan")
        print(f"windows={n}  boxes={boxes}  STRAND RATE={sr:.0f}%  (gate (a): target <=15%)")
        print(f"legging gap: median {med_leg:.1f}s  p90 {p90_leg:.1f}s")
        print(f"fills: maker={maker} TAKER={taker}  dispose-cross fired={xcross}x  (gate (b): >0 if any strands)")
        print(f"settled windows={have_settle}  DAY P&L=${pnl:+.2f}  (gate (d): >= ~0)")
        # per-strand realized cost (gate (c): target ~ -5..-10c, NOT -21.76c hold)
        scost = []
        for w in strand:
            s = w.get("settle")
            if s not in ("yes", "no"): continue
            ny = w.get("n_yes", 0); nn = w.get("n_no", 0)
            win = ny if s == "yes" else nn
            scost.append((win - (w.get("cost_yes",0)+w.get("cost_no",0))))
        if scost:
            print(f"per-stranded-window P&L: mean {100*sum(scost)/len(scost):+.1f}c  (gate (c): hold was -21.76c)")
        print()
        ok_a = sr <= 15.0; ok_b = (xcross > 0 or len(strand) == 0); ok_d = pnl >= -0.01
        print(f"GATE: (a)strand<=15%%:{'PASS' if ok_a else 'FAIL'}  (b)cross-fires:{'PASS' if ok_b else 'FAIL'}  (d)net>=0:{'PASS' if ok_d else 'FAIL'}")
        print(f">>> {'GO (keep on / consider scale)' if (ok_a and ok_b and ok_d) else 'HOLD / re-diagnose'} <<<  (need ~50-100 windows for confidence; n={n})")
    else:
        # ---- fallback: reconstruct strands from raw fills (pre-fix cycles) ----
        fl = {}
        for r in _walk(f"{base}/kalshi_fees_{a.asset}15m.jsonl"):
            tid = (r.get("raw") or {}).get("trade_id")
            if tid: fl[tid] = r
        W = defaultdict(list)
        for r in fl.values(): W[r["ticker"]].append(r)
        nstr = sum(1 for v in W.values() if sum(1 for x in v if x["side"]=="yes") != sum(1 for x in v if x["side"]=="no"))
        tak = sum(1 for r in fl.values() if (r.get("raw") or {}).get("is_taker"))
        print(f"(no winrecs yet -- pre-fix fallback from fills) windows={len(W)} strand~{100*nstr/max(len(W),1):.0f}% taker={tak}/{len(fl)}")
        print("Re-arm with the dispose-cross/winrec build to populate the gate.")

if __name__ == "__main__":
    main()
