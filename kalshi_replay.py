"""kalshi_replay.py -- queue-replay maker backtest on Kalshi's REAL trade tape.

Collapses kalshi_econ.py's bounds: instead of assuming fills, we replay the actual taker tape
(trades_kalshi_*.parquet) against the per-minute touch (hist_kalshi_*.parquet) with the same
queue semantics as the Polymarket paper engine:

  * each minute we (re)join the close bid and close ask with queue_ahead = Q0 (scenario knob --
    displayed depth isn't in candles, so we scan Q0 and report the breakeven);
  * taker SELLs at/below our bid consume its queue, then fill us (clip contracts); taker BUYs
    at/above our ask likewise; a touch CHANGE re-joins with fresh queue (reset-on-move, the
    conservative queue model);
  * every fill held to settlement (the deployable hold-to-resolution book), no rebate, maker fee 0.

GATES replayed from honest decision-time features (per-minute spot, shifted one bar = strictly
stale): 'spot8' = pull the side a >8bps/3min spot move runs against; 'spot5' = 5bps.

    python kalshi_replay.py btc
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

CLIP = 25.0                 # contracts per fill opportunity (pilot-scale clip)
Q0S = (0.0, 500.0, 2000.0, 5000.0)


def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def replay_window(ws, res, bid, ask, tape, spot_l, q0, gate_bps):
    """One window -> (net_per_contract_sum, fills). tape: arrays t, p, sz, buy."""
    net = 0.0; fills = 0
    t_arr, p_arr, sz_arr, buy_arr = tape
    for k in range(2, 13):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
            continue
        rest_bid = rest_ask = True
        if gate_bps:
            s_now, s_then = spot_l[k], spot_l[max(k - 3, 0)]
            if np.isnan(s_now) or np.isnan(s_then) or s_then <= 0:
                rest_bid = rest_ask = False
            else:
                mv = (s_now / s_then - 1) * 1e4
                if abs(mv) > gate_bps:
                    rest_bid = mv > 0          # spot up -> the bid is the safe side
                    rest_ask = mv < 0
        lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
        i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
        qb = qa = q0
        done_b = not rest_bid; done_a = not rest_ask
        for i in range(i0, i1):
            if done_b and done_a:
                break
            p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
            if not done_b and not buy and p <= b0 + 1e-9:   # taker SELL into the bid side
                if qb >= sz:
                    qb -= sz
                else:
                    net += (res - b0) * min(CLIP, sz - qb) / CLIP
                    fills += 1; done_b = True
            if not done_a and buy and p >= a0 - 1e-9:       # taker BUY lifting the ask side
                if qa >= sz:
                    qa -= sz
                else:
                    net += (a0 - res) * min(CLIP, sz - qa) / CLIP
                    fills += 1; done_a = True
    return net, fills


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else "btc"
    hist = pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
    tap = pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws")
    common = sorted(set(hist.index) & set(tap.index))
    print(f"{asset}: {len(common)} windows with book+tape "
          f"({pd.to_datetime(common[0], unit='s'):%m-%d} .. {pd.to_datetime(common[-1], unit='s'):%m-%d})\n")
    cut = common[int(len(common) * 0.6)]
    print(f"{'q_ahead':>8} {'gate':>7} {'fills/win':>9} {'net/win(c)':>11} {'t':>6} | "
          f"{'IS net':>8} {'OOS net':>8} {'OOS t':>6}")
    print("-" * 70)
    for q0 in Q0S:
        for gname, gbps in (("none", 0.0), ("spot8", 8.0), ("spot5", 5.0)):
            nets, fl = [], 0
            for w in common:
                h = hist.loc[w]
                t = tap.loc[w]
                spot = np.asarray(h.spot_path, float)
                spot_l = np.concatenate([[np.nan], spot[:-1]])
                tape = (np.asarray(t.t, float), np.asarray(t.p, float),
                        np.asarray(t.sz, float), np.asarray(t.buy, bool))
                n, f = replay_window(w, float(h.res_up), np.asarray(h.bid_path, float),
                                     np.asarray(h.ask_path, float), tape, spot_l, q0, gbps)
                nets.append(n); fl += f
            nets = np.array(nets)
            is_m = np.array([w < cut for w in common])
            print(f"{q0:>8.0f} {gname:>7} {fl/len(common):>9.1f} {np.mean(nets)*100:>+11.2f} "
                  f"{tstat(nets):>+6.1f} | {np.mean(nets[is_m])*100:>+8.2f} "
                  f"{np.mean(nets[~is_m])*100:>+8.2f} {tstat(nets[~is_m]):>+6.1f}")
    print("\nRead: net/win in CENTS per 1-contract-normalized clip. q_ahead = displayed queue joined")
    print("behind (scan; live snapshots put BTC touch depth ~1-5k). A config is viable if OOS net>0")
    print("with t>=3 at the realistic q_ahead. Maker fee assumed 0 -- verify the schedule.")


if __name__ == "__main__":
    main()
