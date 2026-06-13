# Kalshi fee model — factor into EVERY taker strategy (2026-06-13)

Operator flag: factor fees into the ETH (and all) strategies. Our backtests historically assumed
crypto15m FEE=0 — that is ~OK for resting MAKER legs but WRONG for any TAKER (crossing) action.

## The fee formula (from Kalshi fee schedule, 2026)
Per-contract fee = ceil( M * P * (1 - P) * 100 ) / 100   (rounded UP to the cent), P = price in $.
- PARABOLIC: peaks at P=0.50, -> ~0 at the extremes.
- TAKER multiplier M: standard categories 0.07; INDEX (S&P/Nasdaq) halved 0.035; CRYPTO is a PREMIUM
  category with a HIGHER multiplier than 0.07 (public sources say "higher"; exact value not published —
  plausibly ~0.14 (2x). TREAT AS UNCERTAIN; calibrate from our OWN realized-fee telemetry, below).
- MAKER multiplier ~ 1/4 of taker (~0.0175 standard); for small/unit trades it ROUNDS TO $0.00.
  => resting maker fills are ~free; TAKER crossings are not.

## Per-contract TAKER fee, standard M=0.07 (and crypto-premium M=0.14 in parens):
- P=0.50: ceil(0.0175)=0.02c... -> 1.75c rounds to 2c   (crypto 3.5c)   <- MAX, worst at the coin-flip
- P=0.70/0.30: 1.47c -> 2c                               (crypto ~2.94c -> 3c)
- P=0.85/0.15: 0.89c -> 1c                               (crypto ~1.79c -> 2c)
- P=0.90/0.10: 0.63c -> 1c                               (crypto ~1.26c -> 2c)
Note the ceil-to-cent makes even tiny fees cost a full cent — brutal on a market whose edges are ~1c.

## CALIBRATE FROM OUR OWN DATA (ground truth > guessing M)
The live trader logs realized fees: live-state branch live_state/<day>/kalshi_fees_btc15m.jsonl. Fit
M from realized fee vs P on our actual fills -> the exact crypto multiplier we pay. (TODO: do this once
enough live fills accumulate; until then model BOTH M=0.07 and M=0.14 as a sensitivity band.)

## IMPLICATIONS
1. **New ETH taker angles (favorite-longshot, lead-lag, stat-arb): a ~1-2c (crypto: 2-3.5c) taker fee
   sits ON TOP of the crossed half-spread (~0.9c on ETH favorites).** An angle must clear (half-spread
   + fee) ~= 2-4c of edge to be +EV. Lead-lag & favorite-longshot are NEGATIVE even at fee=0, so fees
   only deepen the no. The fair-value stat-arb (running) must clear this combined wall.
2. **MAKER strategies are the fee-advantaged class** (maker ~0). The one-sided favorite MAKER was the
   only ETH angle near break-even — but at zero cost and not significant.
3. **BROADER CAVEAT (BTC ladder): the COMPLETION-CHASE rung CROSSES to pair strands = TAKER fee**, and
   strands cluster near P~0.5 where the fee is MAX (2c std / 3.5c crypto). Our "complete is optimal /
   +4.63c per strand" finding was computed at fee=0 -> the true completion benefit is ~2-3.5c LOWER per
   crossed completion. Likewise the ETH flatten-all disposal (+0.91c, sells at touch = taker) is likely
   WIPED OUT by the taker fee. ACTION: re-evaluate the completion/flatten rungs with the taker fee.
4. The live MAKER box itself is ~fee-free (post-only), so the core box economics stand; it's the
   CROSSING actions (completion, flatten, all the new taker angles) that the fee hits.
