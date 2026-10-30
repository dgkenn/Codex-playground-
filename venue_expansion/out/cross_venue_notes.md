## Plain reading

**KILL. Zero fee-inclusive arbitrage instances in 115 minutes and 231 paired snapshots, 13 NFL games, 5 real sportsbooks.** The best
pairing the venues ever offered was 1.67 percentage points *short* of break-even (Tennessee YES at 14c + 1c fee + DraftKings
Bengals -650 at 86.7c = 101.67c). The median pairing was 4.7 pp short. The venues agree to within the fee, and then some: with
Kalshi's fee set to zero the best NFL gap would have been +0.04 pp, on 2 games. The whole of the edge budget is eaten by the
sportsbook's own vig (median 4.25 pp) plus Kalshi's ask spread (median 1 pp) plus the 1-2c fee. This is the last untested mechanism
in the program and it does not produce an edge in NFL game winners.

There is no 60-second survival rate for NFL because there is nothing to re-check (0 of 0). The re-check machinery ran on live data in the
NHL secondary universe and works (see below).

## Things that contradict the spec's premises (read these before trusting any "7 books" number)

1. **Two of the "7 distinct book_ids" are not sportsbooks.** `GET /web/v1/books` names them: id 15 = **Consensus**, id 30 = **Open**
   (the opening line). Only 49 Caesars, 68 DraftKings, 69 FanDuel, 71 BetRivers, 75 BetMGM can be bet. This was fixed before
   collection began (see the docstring of `cross_venue.py`), so the verdict universe is NFL x 5 executable books.
2. **Applying the spec literally (all 7 ids) gives INSUFFICIENT, not KILL, and the reason is an artifact.** The opening line produces
   9 "arbs" in 9 NFL games (median edge 3.0 pp, up to 10.6 pp), every one of which "survives" the re-check because the opening line is frozen: it
   never changed in the window (0 of 28 NFL Open lines moved over 231 snapshots, versus 4 of 28 for DraftKings and 10 of 28 for Consensus). That is Kalshi having moved away from a days-old price, not a trade. Both verdicts are in
   the variants table; the executable-books one is the verdict.
3. **Only 13 NFL games are matchable, not 28.** Kalshi lists 28 open `KXNFLGAME` events; the Action Network scoreboard shows only the
   current week. The 15 Kalshi events dated Nov 5-9 are unmatched in every snapshot (not yet on the board). The Thursday game (GB/CAR)
   is `complete` on Action Network and has no open Kalshi market. The spec's ">= 10 distinct games" bar was reachable (13).
4. **`KXNFL1QWINNER`, `KXNFL2HWINNER`, `KXNFL3QWINNER`, `KXNFL4QWINNER` have zero open markets today.** `KXNFLSPREAD` and `KXNFLTOTAL`
   are open but are not comparable to Action Network's moneyline and were not scored (spread/total comparison is untested here).
5. **The "new" Kalshi depth is mostly decorative on this week's games.** Ask sizes on most Nov 1 games are 10^5 to 4.3 x 10^6
   contracts (a 4.3M-contract ask at 14c is a $600k notional). That is market-maker quote size, not tradable liquidity, and the binding
   size limit on any real arb would be the sportsbook's bet limit, which this data cannot see. The spec's "cap at the Kalshi ask size"
   therefore does not bind in NFL, and dollar sizes derived from it should not be read as capacity. Later-week games and the thin
   NHL/NFL stubs have real small sizes (13-70 contracts).
6. **A data defect that would have fabricated an arb was caught.** At about 17:47 UTC, BetMGM's NHL line for Winnipeg/Florida appeared with the two
   teams' odds swapped relative to all other books (Winnipeg -225 / Florida +185 against +185 / -225 everywhere else): a 28.9 pp fake arb
   at 91k contracts. A feed-integrity filter (book more than 15 pp from the cross-book median is excluded and counted) was added after seeing it.
   It can only remove candidates; the unfiltered counts are disclosed above (NFL unfiltered: still 0 arbs). It removed no NFL executable-book row.

## Secondary universes (disclosure, cannot move the verdict)

- **NBA** (10 games), **NCAAF** (50 matched events; the rest are not on the Action Network board or have unmatched team names): 0 arbs on executable
  books. NCAAF best gap -0.49 pp (Maryland/Illinois, BetRivers). NBA best -2.0 pp.
- **NHL**: 104 episodes on executable books, **all in one game** (Calgary/Seattle, 4 books) and all the same thing: a 50-contract (once 65) resting
  Kalshi ask at 44-45c that sits 5-6c under the 107k-contract ask at 50c. Median edge 0.51 pp, median Kalshi leg $22, profit about $0.26 per episode, $30.70 if
  every one were filled. Re-check survival 0 of 95 (9 censored): the stub is gone or re-priced to 50c within 60 s every time. This fails bars 1b, 2, 3, 5.
  It is a $22 stub, not an edge. The only larger NHL gap (3.5 pp, BetMGM -102) is the same stub.

## Caveats the code cannot remove

- Action Network does not timestamp individual lines. If its feed lags a book, a stale book price could look like a disagreement. That bias
  runs toward *finding* arbs, so a zero count is robust to it.
- Fee is `ceil(7 p (1-p))` cents per contract as the spec says. Kalshi rounds per order, so at size the true fee is lower; the zero-fee
  counterfactual above bounds that effect (it cannot change the NFL answer: the best pre-fee gap is +0.04 pp).
- NFL ties pay 50c per side on Kalshi and typically push at the book, so even a true arb here would have a small tie-state wrinkle (a few tenths of a percent of games).
- This is one 115-minute window on a Friday afternoon, pre-game, with no news shock that I identified in it. News shocks, which is when venues disagree,
  would be the cases to test next (event study on line moves), and a Sunday-morning window is untested. Neither bar can be moved after the fact; this is a KILL on the
  pre-registered window, not a proof of no arb ever.
- Sportsbook limiting of winning accounts (spec section "does not claim") is untouched by this result; there was nothing to limit.
