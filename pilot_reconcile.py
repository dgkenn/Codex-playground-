"""pilot_reconcile.py -- turn the $20 live pilot into a NUMBER, not a vibe.

The pilot's job is to confirm the three things paper can't (PAPER_VS_LIVE.md): is the rebate real, do we
actually fill (queue position), and is live adverse selection worse than paper. This reads the artifacts
live_trader.py writes on the box and reconciles them against the paper (shadow) baseline:

  order_log.jsonl  -- every placement (with window `ws`) + terminal state (filled/cancelled)
  fills_log.jsonl  -- every fill: price, size, trader_side (MAKER/TAKER!), fee_bps, markout_5s
  gha_data/fills_*.jsonl + shadow_windows_*.jsonl -- the PAPER micro_gate reference

Checks (each maps to a PAPER_VS_LIVE gap):
  1. FILL RATE (A4)         fills / placements -- >50% = queue winnable, <30% = fix latency first
  2. MAKER INTEGRITY (A3)   % of fills that are MAKER -- any TAKER = an accidental cross = edge-killer
  3. MARKOUT (A2)           live per-fill markout vs paper's -- is live adverse selection worse? (Welch t)
  4. REBATE (A1)            PREDICTED credit (fees.maker_rebate x size); operator confirms ACTUAL on-chain
  5. NET / WINDOW           live net (markout x size + rebate) per window + t-stat vs 0; paper as reference
  6. VERDICT               GO / NO-GO / INSUFFICIENT with the reason

    python pilot_reconcile.py [--order-log order_log.jsonl] [--fills-log fills_log.jsonl] [--min-fills 30]
"""
from __future__ import annotations
import argparse, glob, json, math


def load_jsonl(path):
    out = []
    try:
        for ln in open(path):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    except FileNotFoundError:
        return None
    return out


def mean_sd(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan"), 0
    m = sum(xs) / n
    sd = (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5 if n > 1 else float("nan")
    return m, sd, n


def t_vs_0(xs):
    m, sd, n = mean_sd(xs)
    return (m / (sd / math.sqrt(n))) if (n > 1 and sd and sd > 0) else float("nan")


def welch_t(a, b):
    """Two-sample Welch t (live vs paper). >0 => live markout BETTER than paper; <0 => worse."""
    ma, sa, na = mean_sd(a); mb, sb, nb = mean_sd(b)
    if na < 2 or nb < 2 or not (sa and sb):
        return float("nan")
    se = math.sqrt(sa * sa / na + sb * sb / nb)
    return (ma - mb) / se if se > 0 else float("nan")


def paper_reference():
    """micro_gate per-fill 5s markout + per-window net from the shadow data (the bar to match)."""
    mo5 = []
    for fp in glob.glob("gha_data/fills_*.jsonl"):
        for r in (load_jsonl(fp) or []):
            if r.get("var") == "micro_gate" and r.get("reason") == "fill" and r.get("mo5") is not None:
                mo5.append(r["mo5"])
    net = []
    seen = {}
    for fp in glob.glob("gha_data/shadow_windows_*.jsonl"):
        for r in (load_jsonl(fp) or []):
            mg = r.get("micro_gate")
            if r.get("ws") is not None and isinstance(mg, dict) and "net" in mg:
                seen[r["ws"]] = mg["net"]
    net = list(seen.values())
    return mo5, net


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order-log", default="order_log.jsonl")
    ap.add_argument("--fills-log", default="fills_log.jsonl")
    ap.add_argument("--min-fills", type=int, default=30, help="below this, verdict is INSUFFICIENT")
    ap.add_argument("--rate", type=float, default=0.07, help="taker fee rate for the rebate prediction")
    a = ap.parse_args()

    orders = load_jsonl(a.order_log)
    fills = load_jsonl(a.fills_log)
    if not orders and not fills:
        print("No live pilot artifacts found.\n"
              f"  expected: {a.order_log} + {a.fills_log} (written by live_trader.py on the box)\n"
              "  run a pilot first, e.g.:\n"
              "    I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live --presign "
              "--max-notional 25 --loss-limit 5 --duration 7200\n"
              "  then re-run this from the same directory.")
        return
    orders = orders or []; fills = fills or []

    # --- map oid -> window from placements; count placements + terminal states ---
    oid_ws, placements, terminals = {}, 0, {}
    for r in orders:
        if r.get("type") == "place":
            placements += 1
            if r.get("ws") is not None:
                oid_ws[r.get("oid")] = r["ws"]
        elif r.get("type") == "terminal":
            terminals[r.get("oid")] = r.get("state")
    n_fill_terminal = sum(1 for s in terminals.values() if s == "filled")

    try:
        import fees
        rebate_of = lambda p: float(fees.maker_rebate(p, rate=a.rate))
    except Exception:
        rebate_of = lambda p: 0.25 * a.rate * p * (1.0 - p)   # inline fallback (share=0.25)

    # --- per-fill aggregation ---
    live_mo, maker_n, taker_n, reb_pred, vol = [], 0, 0, 0.0, 0.0
    by_ws = {}
    for r in fills:
        if r.get("type") != "fill":
            continue
        mo = r.get("markout_5s"); px = r.get("price"); sz = r.get("size") or 0
        ts = (r.get("trader_side") or "").upper()
        if ts == "MAKER":
            maker_n += 1
        elif ts == "TAKER":
            taker_n += 1
        if mo is not None:
            live_mo.append(mo)
        if px is not None:
            reb = rebate_of(px) * sz; reb_pred += reb; vol += sz
            ws = oid_ws.get(r.get("oid"))
            if ws is not None and mo is not None:
                d = by_ws.setdefault(ws, {"pnl": 0.0, "reb": 0.0})
                d["pnl"] += mo * sz; d["reb"] += reb
    n_fills = len(live_mo)

    pap_mo, pap_net = paper_reference()

    print("=" * 70)
    print("PILOT RECONCILIATION  (live vs paper micro_gate)")
    print("=" * 70)

    # 1. FILL RATE (A4)
    fr = (n_fills / placements * 100) if placements else float("nan")
    fr2 = (n_fill_terminal / placements * 100) if placements else float("nan")
    print(f"\n[1] FILL RATE (A4 queue position)")
    print(f"    placements={placements}  fills={n_fills}  filled-terminals={n_fill_terminal}")
    print(f"    fill rate = {fr:.0f}%   ->  " +
          (">50% queue winnable, GOOD" if fr >= 50 else
           "<30% poor queue -> fix latency first (DEPLOY sec.3)" if fr < 30 else
           "30-50% marginal -> tighten latency"))

    # 2. MAKER INTEGRITY (A3)
    tot_sided = maker_n + taker_n
    mk_pct = (maker_n / tot_sided * 100) if tot_sided else float("nan")
    print(f"\n[2] MAKER INTEGRITY (A3 accidental-taker guard)")
    print(f"    MAKER={maker_n}  TAKER={taker_n}  -> {mk_pct:.0f}% maker")
    if taker_n > 0:
        print(f"    !! {taker_n} TAKER fill(s) -- accidental crosses pay the fee + flip the edge. "
              "Confirm post-only guard is active (would_cross) and the SDK post-only flag is set.")

    # 3. MARKOUT (A2)
    lm, lsd, _ = mean_sd(live_mo); pm, psd, _ = mean_sd(pap_mo)
    wt = welch_t(live_mo, pap_mo)
    print(f"\n[3] PER-FILL 5s MARKOUT (A2 adverse selection)")
    print(f"    live  mean {lm:+.5f}  (n={n_fills})")
    print(f"    paper mean {pm:+.5f}  (n={len(pap_mo)}, micro_gate)")
    if wt == wt:
        worse = wt < -2
        print(f"    live-vs-paper Welch t = {wt:+.2f}  -> " +
              ("LIVE SIGNIFICANTLY WORSE (reflexive adverse selection; gate harder)" if worse
               else "live not significantly worse than paper, GOOD"))

    # 4. REBATE (A1)
    print(f"\n[4] REBATE (A1 -- the entire edge)")
    print(f"    matched volume = {vol:.1f} shares")
    print(f"    PREDICTED rebate credit = ${reb_pred:.4f}  (${reb_pred/n_fills:.4f}/fill avg)" if n_fills
          else "    (no fills)")
    print(f"    >> CONFIRM the ACTUAL credit hit the burner wallet (USDC balance delta / rebate statement).")
    print(f"    >> If actual << predicted, the rebate tier/program differs from assumption -> re-derive the rate.")

    # 5. NET / WINDOW
    nets = [d["pnl"] + d["reb"] for d in by_ws.values()]
    nm, nsd, nn = mean_sd(nets); nt = t_vs_0(nets)
    pnm, _, pnn = mean_sd(pap_net)
    print(f"\n[5] NET / WINDOW (markout x size + predicted rebate)")
    if nn:
        print(f"    live  net/win {nm:+.4f}  t(vs 0) {nt:+.2f}  (n={nn} windows)")
    else:
        print(f"    live  net/win: (no windows joined -- need placements with `ws` + matched fills)")
    print(f"    paper net/win {pnm:+.3f}  (n={pnn}, micro_gate; different clip scale -> compare SIGN/t, not $)")

    # 6. VERDICT
    print(f"\n[6] VERDICT")
    reasons = []
    if n_fills < a.min_fills:
        reasons.append(f"only {n_fills} fills (<{a.min_fills}) -- collect more before deciding")
    if taker_n > 0:
        reasons.append(f"{taker_n} accidental TAKER fill(s) -- fix post-only before risking more")
    if fr == fr and fr < 30:
        reasons.append("fill rate <30% -- queue not winnable at current latency")
    if wt == wt and wt < -2:
        reasons.append("live markout significantly worse than paper -- gate harder / reduce footprint")
    if nn >= 5 and nt == nt and nt < 0:
        reasons.append(f"live net/win negative (t={nt:+.2f})")
    if n_fills < a.min_fills:
        verdict = "INSUFFICIENT"
    elif reasons:
        verdict = "NO-GO (yet)"
    else:
        verdict = "GO (scale up cautiously; confirm actual rebate first)"
    print(f"    {verdict}")
    for r in reasons:
        print(f"      - {r}")
    print("\n(Reminder: net/window confidence is scale-invariant -- bigger clips do NOT confirm faster;\n"
          " more windows do. The pilot's unique job is checks [2] and [4] -- maker integrity + real rebate.)")


if __name__ == "__main__":
    main()
