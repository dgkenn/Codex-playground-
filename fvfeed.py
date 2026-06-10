"""Low-latency spot -> fair-value feed for the LIVE maker's predictive repricing.

The ONE lever the fill-tape backtest could not score (see FINDINGS.md "Tier 1"):
move the resting quote when the MODEL moves, before the informed taker arrives. That
is a latency/queue effect, invisible to tape replay (the tape only has fills that
happened, not the cancels you'd have won). So it can only be measured live -- and only
if the feed is real-time and the fair value is the same model validated offline:

    p_up = Phi( log(St/S0) / (sigma * sqrt(tau)) )            [fairvalue.fair_up]

This module owns: the spot poll (Binance public REST, no key), the window-open anchor
S0, a LIVE sigma estimate from the recent spot tape (falls back to the offline-calibrated
constant), and p_up(tau). It degrades safely: if the feed is unreachable, `ok` goes
False and the caller MUST fall back to the validated book-pegged baseline (never quote
off a stale model).
"""
from __future__ import annotations

import time
from collections import deque

from fairvalue import fair_up, realized_vol_per_s

SIGMA_DEFAULT = 6.5e-5          # per-second log-vol, from the offline BTC calibration (the live
                                # sigma() estimate takes over once ~8s of tape accrues, so non-BTC
                                # assets converge to their own vol within seconds of startup)

# Spot sources tried in order (first reachable wins) -> resilient to any one venue/region
# block. Each entry: (url, params, extractor). All public, no key. PARAMETRIZED BY ASSET --
# an ETH/SOL/XRP maker pricing its toxicity overlay off BTC spot is gating on the wrong underlying.
def _binance(j): return float(j["price"])
def _coinbase(j): return float(j["data"]["amount"])
def _cryptocom(j): return float(j["result"]["data"][0]["a"])      # 'a' = latest trade price
def _kraken(j): return float(next(iter(j["result"].values()))["c"][0])


def sources_for(symbol="BTCUSDT"):
    """Per-asset source list. `symbol` is the Binance-style ticker (BTCUSDT/ETHUSDT/...)."""
    base = symbol.upper().replace("USDT", "").replace("USD", "") or "BTC"
    kraken_pair = {"BTC": "XBTUSD"}.get(base, f"{base}USD")       # kraken calls BTC 'XBT'
    return [
        ("https://api.binance.com/api/v3/ticker/price", {"symbol": f"{base}USDT"}, _binance),
        (f"https://api.coinbase.com/v2/prices/{base}-USD/spot", {}, _coinbase),
        ("https://api.crypto.com/exchange/v1/public/get-tickers",
         {"instrument_name": f"{base}USD-PERP"}, _cryptocom),
        ("https://api.kraken.com/0/public/Ticker", {"pair": kraken_pair}, _kraken),
    ]


SOURCES = sources_for("BTCUSDT")    # module-level default kept for backwards compatibility


class SpotFair:
    def __init__(self, sess, symbol="BTCUSDT", sigma_default=SIGMA_DEFAULT, win_s=600):
        self.sess = sess; self.symbol = symbol; self.sigma_default = sigma_default
        self.sources = sources_for(symbol)             # asset-correct spot endpoints
        self.tape = deque()            # (t_s, spot) over the last win_s seconds
        self.win_s = win_s
        self.s0 = None                 # spot at the current window's open
        self.last = None; self.ok = False
        self.source = None             # which venue is currently feeding us (audit)

    def _fetch(self):
        last_err = None
        for url, params, extract in self.sources:
            try:
                r = self.sess.get(url, params=params, timeout=5)
                px = extract(r.json())
                if px and px > 0:
                    self.source = url.split("/")[2]
                    return px
            except Exception as e:  # noqa: BLE001 -- try the next venue
                last_err = e
        if last_err:
            raise last_err
        raise RuntimeError("no spot source returned a price")

    def update(self):
        """Poll spot; append to the tape; return spot or None (and set self.ok)."""
        try:
            px = self._fetch(); now = time.time()
            self.tape.append((now, px)); self.last = px; self.ok = True
            while self.tape and now - self.tape[0][0] > self.win_s:
                self.tape.popleft()
            return px
        except Exception:
            self.ok = False
            return None

    def set_window(self, s0):
        """Anchor S0 at window open (caller passes the spot sampled at the rollover)."""
        self.s0 = s0

    def sigma(self):
        """Live per-second vol from the recent tape; fall back to the calibrated const.
        Uses ~even 1s spacing; realized_vol_per_s needs >=3 points."""
        if len(self.tape) >= 8:
            px = [p for _, p in self.tape]
            dt = max((self.tape[-1][0] - self.tape[0][0]) / max(len(self.tape) - 1, 1), 0.5)
            try:
                s = realized_vol_per_s(px, dt)
                if s and s > 0:
                    return s
            except Exception:
                pass
        return self.sigma_default

    def p_up(self, tau_s):
        """Model P(window resolves Up) given seconds remaining. None if no anchor/feed."""
        if self.s0 is None or self.last is None or not self.ok:
            return None
        return float(fair_up(self.last, self.s0, self.sigma(), max(tau_s, 0.0)))

    def fair_token(self, is_up, tau_s):
        """Model fair price of one token (Up -> p_up, Down -> 1-p_up). None if unavailable."""
        p = self.p_up(tau_s)
        if p is None:
            return None
        return p if is_up else (1.0 - p)
