# Kalshi index daily-bracket strategy test (S&P 500 / Nasdaq range)
_generated 2026-07-18T15:34:57.832690+00:00_

Kalshi-native daily bracket markets: exclusive-exhaustive 'index will close between X and Y' contracts (25-pt SPX brackets, ~30/day + two tails).
All PnL NET of Kalshi quadratic fee (0.07*p*(1-p)/ct). Executable prices: seller RECEIVES yes_bid. Entry from ~15:00Z (11am ET) intraday candle (first-half RTH, no terminal look-ahead). t clustered by DAY.

Multiple-testing count: 6 tests (2 series x [1 short-vol + 2 structural snapshots]).

## KXINX (S&P 500) -- 45 settled daily events

Exhaustive (exactly 1 winner) days: 45/45; non-exhaustive: 0

### Short-vol (SELL outer brackets, entry yes_bid in (0.05, 0.3))

- n_days=45, n_trades=209
- seller net PnL/ct (continuous fee): -0.0202, day-clustered t = -1.26
- seller net PnL/ct (ceil fee): -0.0254, day-clustered t = -1.58
- seller win rate (bracket settles NO): 0.847
- calibration: avg priced mid=0.157, avg bid=0.140, realized YES rate=0.153
- worst day mean PnL/ct: -0.2552

### Structural (exclusive-exhaustive bracket set)

- [mid_am] full-buyable days=45, underround(1-buycost) mean=-0.8526666666666671, max=-0.6400000000000003, positive_days=0
- [mid_am] full-sellable days=0, overround(selltake-1) mean=None, max=None, positive_days=0
- [early_pm] full-buyable days=45, underround(1-buycost) mean=-0.8433333333333337, max=-0.6300000000000001, positive_days=0
- [early_pm] full-sellable days=0, overround(selltake-1) mean=None, max=None, positive_days=0

- capacity: median event volume=68444 ct, max=224953 ct


## KXNASDAQ100 (Nasdaq-100) -- 45 settled daily events

Exhaustive (exactly 1 winner) days: 45/45; non-exhaustive: 0

### Short-vol (SELL outer brackets, entry yes_bid in (0.05, 0.3))

- n_days=45, n_trades=268
- seller net PnL/ct (continuous fee): -0.0313, day-clustered t = -2.82
- seller net PnL/ct (ceil fee): -0.0361, day-clustered t = -3.26
- seller win rate (bracket settles NO): 0.858
- calibration: avg priced mid=0.139, avg bid=0.120, realized YES rate=0.142
- worst day mean PnL/ct: -0.3058

### Structural (exclusive-exhaustive bracket set)

- [mid_am] full-buyable days=45, underround(1-buycost) mean=-1.0371111111111115, max=-0.6600000000000006, positive_days=0
- [mid_am] full-sellable days=0, overround(selltake-1) mean=None, max=None, positive_days=0
- [early_pm] full-buyable days=45, underround(1-buycost) mean=-1.0528888888888892, max=-0.6800000000000004, positive_days=0
- [early_pm] full-sellable days=0, overround(selltake-1) mean=None, max=None, positive_days=0

- capacity: median event volume=30812 ct, max=417048 ct


## BLUNT VERDICT

- Fee-surviving short-vol edge? **False**
- Fee-surviving structural arb? **False**
- Deployable? **False**

NO fee-surviving Kalshi index-bracket edge. Daily S&P/Nasdaq brackets are near-perfectly calibrated (priced mid ~= realized YES rate to ~1pt). Selling outer brackets loses net of fee+spread (Nasdaq significantly negative, t=-2.8/-3.3), consistent with the prior calibrated-Kalshi-longshot null. Structurally the bracket set is verified exhaustive (45/45 days exactly one winner) but the bid/ask straddles $1.00 with a wide spread (sum asks ~1.6-2.0, sum bids ~0.85 with 24/30 wings bidless): no underround, no sellable overround, no risk-free lock. Nothing deployable; correlation with the crypto short-vol edge is moot (no edge to add).

### Correlation-with-crypto note
Equity-index daily brackets and the confirmed crypto daily short-vol edge both amount to shorting daily realized-vs-implied vol, so a *real* index premium would be a partially-correlated (equity/crypto beta ~0.3-0.5 in risk-on/off) but distinct VRP stream -- attractive diversification IF it existed. It does not: the index brackets are efficiently priced, so there is nothing to add to the portfolio.