"""hedger.py -- BTC-perp delta-hedge HEDGE-RATIO computation. Kept for reference.

>>> IMPORTANT: a PROPER path-based backtest (`hedge_backtest.py`) REFUTED this as a drawdown fix. The
>>> mo30-based hint in metrics.py section D was a proxy artifact (it removes the terminal move for free).
>>> On the real spot path, hedging these 15-min binaries does NOT cut MDD: their delta explodes near expiry
>>> (pin risk) so the hedge must be frozen exactly when the outcome is decided -> insignificant free
>>> (ufat_band Calmar 5.7->6.1, p=0.76), net-negative with perp fees. Use tight inventory + breadth for
>>> risk, NOT this. This module remains only as the hedge-ratio reference / for other (non-binary) uses.

A hold-to-resolution maker carries the residual token inventory's directional swing; the 15m token is a
function of a tradable underlying (BTC), so in principle it's hedgeable -- but see the refutation above.

The token's price ~ P(up) = fair_up(S). So a position of q_up UP tokens (and q_dn DOWN) has BTC price
sensitivity dV/dS = (q_up - q_dn) * d(fair_up)/dS. We hold the OFFSETTING perp: target perp delta = -dV/dS,
i.e. short BTC when long net-UP exposure. Rebalance with hysteresis so we don't churn perp fees on noise.

LIVE-ONLY (needs a perp venue + key on your infra). Computation + dry-run here; wire into live_trader's
settle/loop. The validation that it helps is metrics.py D, not this file.
"""
from __future__ import annotations
import time
from fairvalue import fair_up


def dfair_dS(st, s0, sigma, tau, h_bps=1.0):
    """numerical d(fair_up)/dS at spot st (per $1 of BTC). h = h_bps of spot."""
    if st is None or s0 is None or tau is None or tau <= 0:
        return 0.0
    h = max(st * h_bps / 1e4, 1e-6)
    return (fair_up(st + h, s0, sigma, tau) - fair_up(st - h, s0, sigma, tau)) / (2 * h)


def book_btc_delta(up_qty, dn_qty, st, s0, sigma, tau):
    """BTC price-delta of the Polymarket position, in token-$ per $1 BTC move.
    dV/dS = (q_up - q_dn) * d(fair_up)/dS  (DOWN token = 1 - fair_up, so opposite sign)."""
    return (up_qty - dn_qty) * dfair_dS(st, s0, sigma, tau)


def target_perp_usd(up_qty, dn_qty, st, s0, sigma, tau):
    """USD-notional of BTC perp to hold to neutralize the book delta (negative = short BTC).
    perp_delta target = -dV/dS  -> notional = -(dV/dS) * S  (so a $1 BTC move offsets the book swing)."""
    if st is None:
        return 0.0
    return -book_btc_delta(up_qty, dn_qty, st, s0, sigma, tau) * st


class PerpHedger:
    """Rebalances a BTC-perp hedge against the live book delta, with hysteresis (don't churn fees).
    DRY by default; pass an executor(usd_target)->fill for live. Threshold in USD-notional."""

    def __init__(self, executor=None, rebalance_usd=25.0, live=False):
        self.exec = executor; self.thresh = rebalance_usd; self.live = live
        self.pos_usd = 0.0; self.n_rebal = 0; self.log = []

    def rebalance(self, up_qty, dn_qty, st, s0, sigma, tau):
        tgt = target_perp_usd(up_qty, dn_qty, st, s0, sigma, tau)
        if abs(tgt - self.pos_usd) < self.thresh:           # hysteresis: inside band -> hold
            return None
        delta = tgt - self.pos_usd
        rec = {"ts": time.time(), "target_usd": round(tgt, 2), "from_usd": round(self.pos_usd, 2),
               "trade_usd": round(delta, 2), "dry": not self.live}
        if self.live and self.exec:
            try:
                self.exec(delta)
            except Exception as e:
                rec["error"] = str(e)[:80]
        self.pos_usd = tgt; self.n_rebal += 1; self.log.append(rec)
        return rec


if __name__ == "__main__":
    # demo: net-long 100 UP near p=0.6 mid-window -> short ~$X BTC
    import fairvalue
    st, s0, sigma, tau = 100000.0, 99800.0, 6.5e-5, 450.0
    print("dfair/dS:", dfair_dS(st, s0, sigma, tau))
    print("book delta (100 UP, 0 DN):", round(book_btc_delta(100, 0, st, s0, sigma, tau), 4))
    print("target perp USD:", round(target_perp_usd(100, 0, st, s0, sigma, tau), 2),
          "(negative = short BTC to neutralize)")
    h = PerpHedger(rebalance_usd=25)
    print("rebalance:", h.rebalance(100, 0, st, s0, sigma, tau))
    print("NOTE: hedge_backtest.py REFUTED this as a drawdown fix for 15-min binaries (pin risk near expiry).")
