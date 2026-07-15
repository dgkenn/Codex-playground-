#!/usr/bin/env python3
"""favlong_taker.py -- PAPER-mode near-expiry contrarian TAKER for the FAVLONG edge.

WHAT THIS IS
  A self-contained, paper-only execution module for node FAVLONG: the first validated positive
  edge of the research program (see favlongshot_edge.py, the SOURCE OF TRUTH for the math). On
  Kalshi 15-minute crypto binaries (btc/eth/sol "up/above-strike"), the book is OVER-CONFIDENT in
  the last ~2-3 minutes of a 900s window (favorite-longshot bias / terminal overconfidence). We
  compute a fair-value probability of settling above strike from spot-vs-strike, scaled by CAUSAL
  realized vol and shrinking time-to-expiry, and if the executable price underprices our fair value
  by more than the edge threshold, we TAKE that side (buy the up-contract at ask if fair-ask>edge,
  or sell at bid if bid-fair>edge).

  This module reproduces favlongshot_edge.py's decision math IDENTICALLY (NORM, the per-contract
  Kalshi fee KFEE=0.07*p*(1-p), _causal_sigma, DECISION_T=720s, EDGE=0.05) and wraps it in a clean
  book-feed interface + a PAPER fill/settlement simulator + telemetry consistent with the live bot.

PROPOSE-ONLY / PAPER-MODE (Rail 1 -- non-negotiable)
  This tool CANNOT place real orders. It runs in PAPER/dry-run mode only: it simulates fills at the
  recorded executable price, applies the Kalshi fee, and books realized P&L against the window's
  terminal settlement. There is NO live order path. `--mode live` HARD-REFUSES: it raises before
  doing anything, because live sizing on this edge requires BOTH
    (1) the FORWARD GATE to have passed -- the charter gate of a pooled, day-clustered t >= 2 over
        >= 10 FORWARD days (favorite-longshot is a known effect that can decay, so in-sample edge is
        not sufficient), AND
    (2) EXPLICIT OPERATOR AUTHORIZATION.
  Neither is granted here, and this module does not implement the wiring to place orders even if
  they were. It only PROPOSES fills on paper so the lead can study economics.

VALIDATED PRIORS (from favlongshot_edge.py, node FAVLONG 2026-07-14)
  - decision_t = 720s into the 900s window (last ~3 min); edge < ~450s in ~= 0 (terminal effect).
  - EDGE = 0.05 minimum model-vs-price edge to trade; +Kalshi fee 0.07*p*(1-p) per contract.
  - Clean label: outcome = the MARKET's own terminal price (mid_close > 0.5), not our strike proxy.
  - Magnitude: ~2c/contract net pooled across assets, ~4c/contract on BTC alone. Real but MODEST;
    ~62% of asset-days positive -> real variance, needs sizing/risk mgmt, not all-in.
  - Only BTC clears t>=2 OOS (2.97); confidence comes from cross-asset POOLING (pooled t=3.99 over
    105 asset-days) of the shared mechanism, not from any single market.

Usage
  python3 favlong_taker.py                       # offline self-test over cached BTC windows
  python3 favlong_taker.py --asset btc --days 4  # self-test, first N days, prints paper P&L
  python3 favlong_taker.py --mode live           # HARD-REFUSES (guardrail demo)
  FAVLONG_CACHE=/tmp/favlong_cache python3 favlong_taker.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import statistics
import sys
import time
from collections import defaultdict, namedtuple
from typing import Iterable, Optional

# --- validated constants, mirrored EXACTLY from favlongshot_edge.py (source of truth) ----------
NORM = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
KFEE = lambda p: 0.07 * p * (1 - p)          # Kalshi per-contract trading fee
DECISION_T = 720                              # seconds into the 900s window (last ~3 min)
EDGE = 0.05                                   # min model-vs-price edge to trade
WINDOW_S = 900                                # 15-minute binary window
TAU_MIN = 30                                  # skip if < 30s to expiry (matches favlongshot_edge)
MIN_IDX = 5                                   # need >=5 ticks before the decision index
CACHE_DIR = os.environ.get("FAVLONG_CACHE", "/tmp/favlong_cache")

# A single near-expiry book observation, matching the cache tick layout
# (t,mid,spot,bid,ask,bidq,askq) used by favlongshot_edge.build_asset / the live collector.
Book = namedtuple("Book", "t mid spot bid ask bidq askq")

# The taker's decision for one window (paper-only; price is the executable ask/bid).
TakerOrder = namedtuple("TakerOrder", "side price size fair ev spot strike sig tau idx depth")


# ------------------------------------------------------------------------------------------------
# math -- reproduced identically from favlongshot_edge.py
# ------------------------------------------------------------------------------------------------
def causal_sigma(ticks, idx):
    """Per-sqrt-second realized vol of spot using ONLY ticks up to the decision index (no
    look-ahead). Identical to favlongshot_edge._causal_sigma."""
    sp = [ticks[i][2] for i in range(idx + 1) if ticks[i][2]]
    if len(sp) < 5:
        return None
    lr = [math.log(sp[i + 1] / sp[i]) for i in range(len(sp) - 1) if sp[i] > 0]
    if len(lr) < 4:
        return None
    dt = (ticks[idx][0] - ticks[0][0]) / max(1, len(lr))
    return statistics.pstdev(lr) / math.sqrt(max(dt, 0.5))


def fair_value(spot, strike, sig, tau):
    """P(settle above strike): a shrinking-time gaussian on log-ish spot moves. Matches the
    z = (spot-strike)/(spot*sig*sqrt(tau)); fair = NORM(z) used in favlongshot_edge.score."""
    z = (spot - strike) / (spot * sig * math.sqrt(tau)) if sig and sig > 0 else 0.0
    return NORM(z)


def decision_index(ticks, decision_t=DECISION_T):
    """Last tick index with t <= decision_t (same scan as favlongshot_edge.score)."""
    idx = None
    for i, x in enumerate(ticks):
        if x[0] <= decision_t:
            idx = i
        else:
            break
    return idx


def decide(ticks, strike, decision_t=DECISION_T, edge=EDGE, max_contracts=50, lag=0):
    """Compute the FAVLONG taker decision for one window near expiry.

    Returns a TakerOrder (paper intent) or None (no edge / unusable window). The side/price logic
    is identical to favlongshot_edge.score; here we additionally size the order by executable depth
    (capped at max_contracts) so paper P&L can scale beyond one contract.

    `lag` fills at a later tick to stress-test stale-quote picking (favlongshot_edge's `lag`).
    """
    idx = decision_index(ticks, decision_t)
    if idx is None or idx < MIN_IDX:
        return None
    t, mid, spot, bid, ask = ticks[idx][:5]
    if None in (spot, bid, ask):
        return None
    tau = WINDOW_S - t
    if tau < TAU_MIN:
        return None
    sig = causal_sigma(ticks, idx)
    if not sig:
        return None
    fair = fair_value(spot, strike, sig, tau)
    ev_buy, ev_sell = fair - ask, bid - fair

    # fill at a possibly-later tick (latency test); executable price + resting depth come from there
    fr = ticks[min(idx + lag, len(ticks) - 1)]
    fb, fa, fbq, faq = fr[3], fr[4], fr[5], fr[6]
    if None in (fb, fa):
        return None

    if ev_buy >= ev_sell and ev_buy > edge:
        depth = faq or 0                       # buying the up-contract: lift the ask
        size = int(max(0, min(max_contracts, math.floor(depth))))
        if size <= 0:
            return None
        return TakerOrder("buy", fa, size, fair, ev_buy, spot, strike, sig, tau, idx, depth)
    if ev_sell > edge:
        depth = fbq or 0                       # selling the up-contract: hit the bid
        size = int(max(0, min(max_contracts, math.floor(depth))))
        if size <= 0:
            return None
        return TakerOrder("sell", fb, size, fair, ev_sell, spot, strike, sig, tau, idx, depth)
    return None


def terminal_outcome(ticks):
    """MARKET's own terminal settlement: 1 if the closing mid > 0.5 else 0. This is the clean label
    favlongshot_edge trusts (using our strike proxy for BOTH fair-value and outcome inflated t)."""
    mc = ticks[-1][1]
    return 1 if (mc is not None and mc > 0.5) else 0


def contract_pnl(order: TakerOrder, outcome: int, fee=True):
    """Realized per-CONTRACT P&L at settlement (contract pays $1 if outcome, else $0).
    buy:  outcome - fill - fee ;  sell:  fill - outcome - fee.  Matches favlongshot_edge.score."""
    if order.side == "buy":
        return outcome - order.price - (KFEE(order.price) if fee else 0.0)
    return order.price - outcome - (KFEE(order.price) if fee else 0.0)


# ------------------------------------------------------------------------------------------------
# PAPER execution + telemetry
# ------------------------------------------------------------------------------------------------
def kalshi_ticker(asset: str, when=None) -> str:
    """Kalshi 15m ticker for an asset window, e.g. KXBTC15M-26JUL141915. Cosmetic here (the cache
    carries no ticker); provided so a live feed adapter can label telemetry like the live bot."""
    when = time.gmtime(when if when is not None else time.time())
    return "KX%s15M-%s" % (asset.upper(), time.strftime("%y%b%d%H%M", when).upper())


class PaperTaker:
    """PAPER-only FAVLONG taker. Consumes per-window book snapshots, decides + simulates a fill,
    and logs intent/fill/settlement to a JSONL telemetry file consistent with the live bot's
    flat-record-with-ctx style (kalshi_fees / winrec conventions)."""

    def __init__(self, asset="btc", decision_t=DECISION_T, edge=EDGE, max_contracts=50,
                 fee=True, lag=0, telemetry_path=None, mode="paper"):
        if mode != "paper":
            _refuse_live(mode)
        self.asset = asset
        self.decision_t = decision_t
        self.edge = edge
        self.max_contracts = max_contracts
        self.fee = fee
        self.lag = lag
        self.mode = "paper"
        self.telemetry_path = telemetry_path or f"favlong_paper_{asset}15m.jsonl"
        self._fh = None

    # -- telemetry -------------------------------------------------------------------------------
    def _log(self, rec: dict):
        if self._fh is None:
            self._fh = open(self.telemetry_path, "a")
        self._fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self._fh.flush()

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    # -- per-window trade ------------------------------------------------------------------------
    def trade_window(self, ticks, strike, ws=None, outcome=None, log=True) -> Optional[dict]:
        """Decide + paper-fill + settle ONE window. `ticks` is an iterable of book snapshots
        (t,mid,spot,bid,ask,bidq,askq). `outcome` (0/1) overrides the terminal-mid label if the
        caller has the true settlement; otherwise we use the market's terminal mid. Returns a
        settlement record, or None if no trade was taken."""
        ticks = [tuple(t) for t in ticks]
        order = decide(ticks, strike, self.decision_t, self.edge, self.max_contracts, self.lag)
        if order is None:
            return None
        out = terminal_outcome(ticks) if outcome is None else int(outcome)
        pnl_ct = contract_pnl(order, out, self.fee)
        fee_ct = KFEE(order.price) if self.fee else 0.0
        rec = {
            "ts": time.time(),
            "mode": "paper",
            "event": "favlong_paper_trade",
            "asset": self.asset,
            "ticker": kalshi_ticker(self.asset, ws),
            "ws": ws,
            "side": order.side,                       # buy=lift ask (up-contract), sell=hit bid
            "price": round(order.price, 6),           # executable fill price
            "size": order.size,                        # capped by depth & max_contracts
            "count": order.size,                       # live-bot fee-ledger field name
            "fee_per_ct": round(fee_ct, 6),
            "fee_reported": round(fee_ct * order.size, 6),
            "outcome": out,                            # 1 if settled above strike (market terminal)
            "pnl_per_ct": round(pnl_ct, 6),
            "pnl_total": round(pnl_ct * order.size, 6),
            "ctx": {                                   # decision context (mirrors live fee-ledger ctx)
                "decision_t": self.decision_t,
                "edge": self.edge,
                "spot": round(order.spot, 6),
                "strike": round(order.strike, 6),
                "bid": round(ticks[order.idx][3], 6),
                "ask": round(ticks[order.idx][4], 6),
                "mid": round(ticks[order.idx][1], 6) if ticks[order.idx][1] is not None else None,
                "sig": round(order.sig, 9),
                "tau": round(order.tau, 3),
                "fair": round(order.fair, 6),
                "ev": round(order.ev, 6),
                "depth": order.depth,
                "lag": self.lag,
            },
        }
        if log:
            self._log(rec)
        return rec

    def run_windows(self, windows: Iterable, log=True) -> dict:
        """Run over an iterable of (ticks, strike[, outcome]) tuples. Returns a paper P&L summary
        (per-contract and total). `windows` may be the cache list of (ticks, strike, out_proxy)."""
        per_ct, tot, n_trades, n_wins = [], 0.0, 0, 0
        for w in windows:
            if len(w) >= 3:
                ticks, strike, extra = w[0], w[1], w[2]
            else:
                ticks, strike, extra = w[0], w[1], None
            rec = self.trade_window(ticks, strike, outcome=None, log=log)
            if rec is None:
                continue
            per_ct.append(rec["pnl_per_ct"])
            tot += rec["pnl_total"]
            n_trades += 1
            n_wins += rec["pnl_per_ct"] > 0
        return {
            "n_trades": n_trades,
            "winrate": (n_wins / n_trades) if n_trades else float("nan"),
            "mean_per_ct": statistics.mean(per_ct) if per_ct else float("nan"),
            "total_per_ct": sum(per_ct),
            "total_pnl": tot,
        }


def _refuse_live(mode):
    raise SystemExit(
        f"REFUSED: favlong_taker is PROPOSE-ONLY / paper-mode; requested mode={mode!r} would place "
        "real orders and is not permitted.\n"
        "  Live sizing on the FAVLONG edge requires BOTH:\n"
        "   (1) the FORWARD GATE to have passed -- pooled, day-clustered t >= 2 over >= 10 FORWARD "
        "days (favorite-longshot bias is a known effect that can decay), AND\n"
        "   (2) explicit OPERATOR AUTHORIZATION.\n"
        "  This module implements NO live order path. Run with --mode paper (the default)."
    )


# ------------------------------------------------------------------------------------------------
# offline self-test -- reproduce favlongshot_edge.py's per-contract edge on the same windows
# ------------------------------------------------------------------------------------------------
def load_asset(asset):
    """Load the cached per-day windows {day:[(ticks,strike,out_proxy)]} built by favlongshot_edge."""
    p = os.path.join(CACHE_DIR, f"win_{asset}.pkl")
    if not os.path.exists(p):
        raise SystemExit(
            f"cache not found: {p}\nSet FAVLONG_CACHE (currently {CACHE_DIR!r}) or build it with "
            "favlongshot_edge.py (load_asset)."
        )
    return pickle.load(open(p, "rb"))


def selftest(asset="btc", ndays=None, edge=EDGE, decision_t=DECISION_T, clean_label=True,
             fee=True, lag=0, verbose=True):
    """Score the cached windows the SAME way favlongshot_edge.score does (clean-label filter on,
    per-contract, fee on) so the lead can confirm this module reproduces the validated numbers.
    With clean_label=True this is a like-for-like check of the decision math (per-CONTRACT edge)."""
    data = load_asset(asset)
    days = sorted(data)
    if ndays:
        days = days[:ndays]
    taker = PaperTaker(asset=asset, decision_t=decision_t, edge=edge, fee=fee, lag=lag,
                       telemetry_path=os.path.join(CACHE_DIR, f"favlong_paper_{asset}15m.jsonl"))
    per_day = defaultdict(list)
    n_windows = 0
    for day in days:
        for ticks, strike, out_proxy in data.get(day, []):
            n_windows += 1
            ticks = [tuple(t) for t in ticks]
            outcome = terminal_outcome(ticks)
            if clean_label and out_proxy != outcome:
                continue                            # drop proxy-vs-market disagreements (favlongshot)
            rec = taker.trade_window(ticks, strike, ws=None, outcome=outcome, log=True)
            if rec is None:
                continue
            per_day[day].append(rec["pnl_per_ct"])
    taker.close()

    allpl = [p for v in per_day.values() for p in v]
    if not allpl:
        if verbose:
            print(f"[{asset}] no trades over {len(days)} days / {n_windows} windows")
        return None
    dm = [statistics.mean(v) for v in per_day.values() if v]
    tclust = (statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm)))
              if len(dm) > 1 and statistics.stdev(dm) > 0 else float("nan"))
    res = dict(asset=asset, n=len(allpl), ndays=len(dm),
               winrate=sum(p > 0 for p in allpl) / len(allpl),
               mean_per_ct=statistics.mean(allpl), total_per_ct=sum(allpl), tclust=tclust,
               posdays=sum(1 for v in per_day.values() if sum(v) > 0),
               telemetry=taker.telemetry_path)
    if verbose:
        print(f"FAVLONG paper self-test  asset={asset}  days={len(days)}  windows={n_windows}  "
              f"decision_t={decision_t}s  edge={edge}  clean_label={clean_label}  +fee={fee}")
        print(f"  trades={res['n']}  winrate={res['winrate']:.3f}  "
              f"mean=${res['mean_per_ct']:+.4f}/ct  total=${res['total_per_ct']:+.2f}/ct  "
              f"d-clust t={res['tclust']:.2f}  pos-days={res['posdays']}/{res['ndays']}")
        lo, hi = (0.02, 0.04) if asset == "btc" else (0.0, 0.04)
        ok = res["mean_per_ct"] > 0
        print(f"  sanity: mean edge {'POSITIVE' if ok else 'NON-POSITIVE'} "
              f"(expect ~2-4c/ct on BTC){' <-- OK' if ok and asset == 'btc' and lo <= res['mean_per_ct'] else ''}")
        print(f"  telemetry -> {res['telemetry']}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="FAVLONG paper-mode near-expiry contrarian taker "
                                             "(PROPOSE-ONLY; see module docstring).")
    ap.add_argument("--mode", default="paper", help="paper (default). 'live' HARD-REFUSES (guardrail).")
    ap.add_argument("--asset", default="btc", help="btc | eth | sol")
    ap.add_argument("--days", type=int, default=6, help="offline self-test: first N cached days")
    ap.add_argument("--edge", type=float, default=EDGE)
    ap.add_argument("--decision-t", type=int, default=DECISION_T)
    ap.add_argument("--lag", type=int, default=0, help="fill at N ticks later (latency stress test)")
    ap.add_argument("--no-clean-label", action="store_true",
                    help="do NOT drop proxy-vs-market disagreements (favlongshot uses clean-label)")
    ap.add_argument("--no-fee", action="store_true", help="disable the Kalshi per-contract fee")
    a = ap.parse_args(argv)

    if a.mode != "paper":
        _refuse_live(a.mode)                       # guardrail: never places orders

    print(f"FAVLONG_CACHE={CACHE_DIR}")
    selftest(asset=a.asset, ndays=a.days, edge=a.edge, decision_t=a.decision_t,
             clean_label=not a.no_clean_label, fee=not a.no_fee, lag=a.lag)


if __name__ == "__main__":
    main()
