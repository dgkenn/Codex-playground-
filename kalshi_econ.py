"""kalshi_econ.py -- is a toxicity-gated MAKER viable on Kalshi's 15-min crypto markets?

Kalshi pays no maker rebate (fee_type=quadratic applies to takers; maker fee assumed 0 -- VERIFY on
the published fee schedule before live), so unlike Polymarket the maker edge must be GROSS spread
capture net of adverse selection. This estimates exactly that from the public per-minute candles
(hist_kalshi_*.parquet from fetch_kalshi.py).

CANDLE-LEVEL FILL MODEL (coarse but sign-honest, biased AGAINST the maker):
  Each minute k we rest 1 contract at the CLOSE bid and 1 at the CLOSE ask of minute k.
  The bid FILLS if minute k+1's bid LOW trades at/below our price (the level was hit);
  the ask FILLS if minute k+1's ask HIGH trades at/above ours (the level was lifted).
  Fill price = our resting price. This requires the touch to MOVE INTO us -- pure
  adverse-direction fills, no benign same-level queue traffic -- so realized markouts are a
  PESSIMISTIC bound on live capture (live also collects the benign flow a queue position earns).
  Every fill is held to SETTLEMENT (the strategy's hold-to-resolution book), markouts also shown
  at +1/+3 minutes.

GATE (honest, decision-time): skip resting on minute k if the |spot move over the last 3 minutes|
exceeds a threshold (the candle-resolution analog of the deployed microprice/staleness gate), and
skip the side the spot just moved against (directional pull, like spot_react/ufat's purpose).

Outputs per asset: spread/volume stats, ungated vs gated maker net per window (IS/OOS split),
plus the taker-fee context.    python kalshi_econ.py hist_kalshi_btc15m.parquet
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

GATE_BPS = 8.0          # |3-min spot move| in bps beyond which the book is "in play" (toxic)


def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "hist_kalshi_btc15m.parquet"
    df = pd.read_parquet(path)
    mid = np.stack(df.mid_path.to_numpy()); bid = np.stack(df.bid_path.to_numpy())
    ask = np.stack(df.ask_path.to_numpy()); vol = np.stack(df.vol_path.to_numpy())
    spot = np.stack(df.spot_path.to_numpy()); res = df.res_up.to_numpy(float)
    ws = df.ws.to_numpy(np.int64)
    n = len(df)
    print(f"{n} windows from {path} "
          f"({pd.to_datetime(ws.min(), unit='s'):%Y-%m-%d} .. {pd.to_datetime(ws.max(), unit='s'):%Y-%m-%d})\n")

    spr = ask - bid
    print("=== microstructure ===")
    print(f"  spread: mean {np.nanmean(spr)*100:.2f}c | p50 {np.nanmedian(spr)*100:.2f}c | "
          f"p90 {np.nanpercentile(spr,90)*100:.2f}c | minutes at <=1c: {np.nanmean(spr <= 0.0101)*100:.0f}%")
    print(f"  volume/min: median {np.nanmedian(vol):,.0f} | mean {np.nanmean(vol):,.0f} contracts")
    print(f"  windows/day available: 96/asset; both-sides resting opportunities/min: ~2\n")

    # conservative spot shift (candle close k = info at end of minute k; use it for minute k+1 decisions)
    spot_l = np.concatenate([np.full((n, 1), np.nan), spot[:, :-1]], axis=1)

    def run(gated):
        nets, fills_ct, gross_per_fill = [], 0, []
        for i in range(n):
            pnl = 0.0
            for k in range(2, 13):                       # rest during minutes 2..12, fill seen at k+1
                b0, a0 = bid[i, k], ask[i, k]
                if np.isnan(b0) or np.isnan(a0) or not (0.03 <= mid[i, k] <= 0.97):
                    continue
                rest_bid = rest_ask = True
                if gated:
                    s_now, s_then = spot_l[i, k], spot_l[i, max(k - 3, 0)]
                    if np.isnan(s_now) or np.isnan(s_then) or s_then <= 0:
                        rest_bid = rest_ask = False
                    else:
                        mv = (s_now / s_then - 1) * 1e4
                        if abs(mv) > GATE_BPS:           # book in play: quote only the safe side
                            rest_bid = mv > 0            # spot up -> bids are safe, asks get lifted
                            rest_ask = mv < 0
                # fills (next-minute touch moves into us)
                if rest_bid and not np.isnan(bid[i, k + 1]) and bid[i, k + 1] < b0 - 1e-9:
                    pnl += (res[i] - b0); fills_ct += 1
                    gross_per_fill.append(res[i] - b0)
                if rest_ask and not np.isnan(ask[i, k + 1]) and ask[i, k + 1] > a0 + 1e-9:
                    pnl += (a0 - res[i]); fills_ct += 1
                    gross_per_fill.append(a0 - res[i])
            nets.append(pnl)
        return np.array(nets), fills_ct, np.array(gross_per_fill)

    def run_both_sides(gated):
        """OPTIMISTIC bound: both sides fill every rested minute (queue traffic in a 39k-contracts/min
        book). Real capture sits between this and the adverse-only model below."""
        nets = []
        for i in range(n):
            pnl = 0.0
            for k in range(2, 13):
                b0, a0 = bid[i, k], ask[i, k]
                if np.isnan(b0) or np.isnan(a0) or not (0.03 <= mid[i, k] <= 0.97):
                    continue
                ok = True
                if gated:
                    s_now, s_then = spot_l[i, k], spot_l[i, max(k - 3, 0)]
                    ok = not (np.isnan(s_now) or np.isnan(s_then) or s_then <= 0) and                         abs((s_now / s_then - 1) * 1e4) <= GATE_BPS
                if ok:
                    pnl += (res[i] - b0) + (a0 - res[i])   # = the spread, both legs settled
            nets.append(pnl)
        return np.array(nets)

    cut = int(n * 0.6)
    print("=== maker spread-capture BOUNDS (truth between; live shadow collection decides) ===")
    for name, gated in (("UPPER both-sides", False), ("UPPER gated", True)):
        nets = run_both_sides(gated)
        print(f"{name:>22} {'':>7} {np.mean(nets):>+9.4f} {tstat(nets):>+6.1f} | "
              f"{np.mean(nets[:cut]):>+10.4f} {np.mean(nets[cut:]):>+11.4f} {tstat(nets[cut:]):>+6.1f}")
    print("=== LOWER bound (adverse-direction fills ONLY -- you only fill when the touch moves into you) ===")
    print(f"{'config':>22} {'fills':>7} {'net/win':>9} {'t':>6} | {'IS net/win':>10} {'OOS net/win':>11} {'OOS t':>6}")
    for name, gated in (("ungated", False), (f"gated ({GATE_BPS:g}bps/3m)", True)):
        nets, fc, gpf = run(gated)
        print(f"{name:>22} {fc:>7} {np.mean(nets):>+9.4f} {tstat(nets):>+6.1f} | "
              f"{np.mean(nets[:cut]):>+10.4f} {np.mean(nets[cut:]):>+11.4f} {tstat(nets[cut:]):>+6.1f}")
    print("\n  (per-fill gross is the capture-vs-adverse-selection balance; live adds benign queue")
    print("   traffic on top, so a NET-POSITIVE result here is strong and a small negative is")
    print("   inconclusive-to-promising. No rebate assumed; maker fee assumed 0 -- VERIFY schedule.)")
    print("\n  taker context: fee at p=0.5 ~ 1.75c/contract + half-spread -> any taker idea needs")
    print("  >2.25c/contract of true edge; the directional battery (directional_deep.py on this")
    print("  same parquet) tests exactly that.")


if __name__ == "__main__":
    main()
