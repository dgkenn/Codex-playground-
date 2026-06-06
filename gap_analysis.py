"""Gap analysis: why a high win rate does NOT mean a profitable strategy.

The real backtest in ``run_real.py`` trades the *gap* between a model fair value
and the market quote, then settles at the binary outcome (fill-at-quote). This
module isolates the single most important failure mode of that kind of backtest
-- the "World-B trap" -- on synthetic data where we control the truth.

Setup (identical mechanics in both worlds): we look only at *favourites* -- Up
tokens whose true probability ``q`` of resolving UP is well above 0.5 -- and we
buy one share at the offered ``ask`` and hold to resolution. Because we only buy
favourites, we WIN MOST OF OUR BETS in both worlds (high win rate). The only
difference is the price we pay:

  * World A ("real edge"): the market systematically *underprices* favourites,
        ask = q - edge. We collect the gap. PnL per share ~ edge - fee > 0.
  * World B ("efficient + fees", the trap): the market prices favourites fairly,
        ask = q. There is no gap to collect; all we do is pay the fee on every
        trade. PnL per share ~ -fee < 0 -- negative EV *despite* an identical,
        high win rate.

``validate_gap.py`` asserts: World A total PnL > 0, World B total PnL < 0, and
both have a high win rate. The lesson carried into ``run_real.py``: on real data
a high win rate that clusters on favourites and evaporates once you demand a
margin above the fee is the World-B trap, not edge.
"""
from __future__ import annotations

import numpy as np

from fairvalue import fee_per_share


def simulate_world(world, n=200_000, fee_bps=1000, edge=0.03, seed=0):
    """Simulate buying favourites at the quote and holding to resolution.

    Returns a dict with n, win_rate, total_pnl, avg_pnl, avg_price.
    """
    rng = np.random.default_rng(seed)

    # Favourites only: true UP probability between 0.55 and 0.97.
    q = rng.uniform(0.55, 0.97, size=n)
    outcome_up = rng.random(n) < q              # realized resolution

    if world.upper() == "A":
        ask = q - edge                          # market underprices the favourite
    elif world.upper() == "B":
        ask = q.copy()                          # efficient: no edge to collect
    else:
        raise ValueError("world must be 'A' or 'B'")
    ask = np.clip(ask, 0.01, 0.99)

    payoff = outcome_up.astype(float)           # 1 if UP else 0
    fee = fee_per_share(ask, fee_bps)
    pnl = payoff - ask - fee                    # buy 1 share at ask, settle 0/1

    return {
        "world": world.upper(),
        "n": int(n),
        "win_rate": float((pnl > 0).mean()),
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()),
        "avg_price": float(ask.mean()),
    }
