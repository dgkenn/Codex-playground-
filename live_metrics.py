"""live_metrics.py -- permanent recorder for everything ONLY a live session can measure.

The paper engine (shadow_compare) measures everything observable from the public tape; this module
records the residual -- the exact list from PAPER_VS_LIVE.md that paper structurally cannot capture:

  A1 (the rebate IS the edge): predicted rebate per fill, periodic USDC balance snapshots, and the
      venue's OWN earnings/rewards statements (get_earnings_for_user_for_day / get_current_rewards)
      -- the ground truth that the credit actually pays, at what rate, on which markets.
  A2 (reflexivity / observer effect): the book's reaction to OUR placements -- microprice/spread
      delta ~2s after each ack. Paper is invisible to the market; live is not. This is the only way
      to measure how much our resting size biases the very signal the gate runs on.
  A4 (queue reality): placement decision->ack latency per order, time-resting at fill, fill rate
      per placement -- true FIFO position is unobservable, but these are its live shadows.
  B1 (latency): rolling CLOB round-trip distributions, WS staleness episodes, event-loop wake rate.
  A3/C4/C6 (integrity): venue post-only rejects, reconciliation strays cancelled, error storms.
  D1 (PnL truth): per-window realized/mark/fee/fill summaries keyed by ws -- joins 1:1 against the
      paper shadow windows for the live-vs-paper gap that decides scale-up.

Design rules: append-only JSONL (live_metrics.jsonl, tiny at pilot scale), every public method is
exception-proof (a metrics failure must NEVER touch trading), and nothing here runs on the react
path -- balance/earnings polls belong to the housekeeping cadence. pilot_reconcile reads this file
alongside order_log.jsonl for the GO/NO-GO.
"""
from __future__ import annotations

import json
import os
import time


class LiveMetrics:
    def __init__(self, asset="btc", tenor_min=15, path=None):
        self.asset = asset
        self.tenor = tenor_min
        self.path = path or f"live_metrics_{asset}{tenor_min}m.jsonl"
        self._fh = None
        self._last_balance = 0.0          # throttle ts
        self._last_earn = 0.0
        self._counts = {}                 # per-window counters (placements, fills, rejects, ...)
        try:
            self._fh = open(self.path, "a")
        except Exception:
            self._fh = None

    # ---------------------------------------------------------------- core
    def event(self, kind, **f):
        """Append one record. NEVER raises into the trading loop."""
        if self._fh is None:
            return
        try:
            f.update({"ts": round(time.time(), 3), "kind": kind,
                      "asset": self.asset, "tenor_min": self.tenor})
            self._fh.write(json.dumps(f) + "\n")
            self._fh.flush()
        except Exception:
            pass

    def bump(self, key, n=1):
        self._counts[key] = self._counts.get(key, 0) + n

    # ---------------------------------------------------------------- hot-path hooks (no I/O wait)
    def place_ack(self, side, price, presigned, lat_ms):
        self.bump("placements")
        self.event("place_ack", side=side, price=price, presigned=bool(presigned),
                   lat_ms=round(lat_ms, 1))

    def place_reject(self, side, price, err):
        self.bump("rejects")
        self.event("place_reject", side=side, price=price, err=str(err)[:120])

    def cancel_batch(self, n, lat_ms, ok):
        self.bump("cancels", n)
        self.event("cancel_batch", n=n, lat_ms=round(lat_ms, 1), ok=bool(ok))

    def fill(self, side, price, size, resting_s, q_ahead, trader_side, fee_bps, rebate_pred):
        self.bump("fills")
        self.event("fill", side=side, price=price, size=size,
                   resting_s=round(resting_s, 2) if resting_s is not None else None,
                   q_ahead=q_ahead, trader_side=trader_side, fee_bps=fee_bps,
                   rebate_pred=round(rebate_pred, 6))

    def reflex(self, token, dmicro_2s, dspread_2s):
        """A2: how the book moved ~2s after OUR placement (observer effect)."""
        self.event("reflex", token=str(token)[:12],
                   dmicro_2s=round(dmicro_2s, 5) if dmicro_2s is not None else None,
                   dspread_2s=round(dspread_2s, 5) if dspread_2s is not None else None)

    def stray_cancelled(self, n):
        self.bump("strays", n)
        self.event("stray_cancelled", n=n)

    def ws_stale(self, stale_s):
        self.event("ws_stale", stale_s=round(stale_s, 1))

    def latency(self, med_ms, p95_ms, p99_ms):
        self.event("latency", med_ms=med_ms, p95_ms=p95_ms, p99_ms=p99_ms)

    # ---------------------------------------------------------------- housekeeping polls (live only)
    def poll_balance(self, client, every_s=60.0):
        """USDC collateral snapshot: the raw material for 'did the actual credit hit the wallet'
        (A1) -- balance delta over a session minus ledger P&L == external credits/debits."""
        now = time.time()
        if client is None or now - self._last_balance < every_s:
            return
        self._last_balance = now
        try:
            from py_clob_client_v2 import BalanceAllowanceParams, AssetType
            b = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
            self.event("balance", raw=b if isinstance(b, dict) else str(b)[:200])
        except Exception as e:  # noqa: BLE001
            self.event("balance_err", err=f"{type(e).__name__}: {str(e)[:80]}")

    def poll_earnings(self, client, every_s=3600.0):
        """The venue's OWN rewards statement (A1 ground truth). Hourly is plenty."""
        now = time.time()
        if client is None or now - self._last_earn < every_s:
            return
        self._last_earn = now
        for name, call in (("rewards", lambda: client.get_current_rewards()),
                           ("earnings", lambda: client.get_earnings_for_user_for_day(
                               time.strftime("%Y-%m-%d", time.gmtime())))):
            try:
                v = call()
                self.event(name, raw=v if isinstance(v, (list, dict)) else str(v)[:400])
            except Exception as e:  # noqa: BLE001
                self.event(f"{name}_err", err=f"{type(e).__name__}: {str(e)[:80]}")

    # ---------------------------------------------------------------- window close (D1 join key)
    def window_summary(self, ws, realized, window_mark, net_delta):
        c = dict(self._counts)
        self._counts = {}
        plc = c.get("placements", 0)
        self.event("window", ws=ws, realized=round(realized, 4), mark=round(window_mark, 4),
                   net_delta=round(net_delta, 3),
                   placements=plc, fills=c.get("fills", 0), rejects=c.get("rejects", 0),
                   cancels=c.get("cancels", 0), strays=c.get("strays", 0),
                   fill_rate=round(c.get("fills", 0) / plc, 3) if plc else None)
