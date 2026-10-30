# Cross-venue arbitrage: Kalshi ask + fee + sportsbook opposing price

Generated 2026-10-30T19:35:18.586258Z.  Spec: `CROSS_VENUE_SPEC.md` (registered 2026-10-30).  Code: `cross_venue.py`.  Raw snapshots: `cache/cross_venue/snapshots.jsonl.gz` (force-added to git; the cache dir is gitignored).

**Window:** 2026-10-30T17:36:35.357991Z to 2026-10-30T19:31:35.358344Z = 115.0 min, 231 snapshots cached (231 scored for NFL), median cadence 30.0 s.  Every pre-game line; all games scored were scheduled and not started.

**Verdict: KILL** (NFL game winners x 5 executable books; spec-literal 7-id variant: INSUFFICIENT). Details after the anchors in order: (a) gap distribution first.

## (a) Gap distribution (`100% - combined cost`, percentage points; arb iff > 0)

Gap = 1.00 - (Kalshi yes_ask + fee + book implied prob of the opposing side).  Negative = no arb.  Every pairing of every executable book in every scored snapshot (NFL).

All observations: n=30030  min -8.77  p5 -6.62  p25 -5.32  **median -4.73**  p75 -3.76  p95 -2.47  p99 -2.00  **max -1.67**

| gap bin (pp) | n observations |
|---|---:|
| [-100,-15) | 0 |
| [-15,-10) | 0 |
| [-10,-8) | 30 |
| [-8,-6) | 2955 |
| [-6,-5) | 6321 |
| [-5,-4) | 12178 |
| [-4,-3) | 5993 |
| [-3,-2) | 2147 |
| [-2,-1) | 406 |
| [-1,0) | 0 |
| [0,1) | 0 |
| [1,2) | 0 |
| [2,5) | 0 |
| [5,100) | 0 |

Near-miss counts (observations): {"gap>=0pp": 0, "gap>=-0.5pp": 0, "gap>=-1pp": 0, "gap>=-2pp": 406, "gap>=-3pp": 2553, "gap>=-4pp": 8546}

Best gap each (game, book, pairing) ever reached in the window (n=130): median -4.61, p75 -3.69, p95 -2.47, max -1.67.  Counts: {"gap>=0pp": 0, "gap>=-0.5pp": 0, "gap>=-1pp": 0, "gap>=-2pp": 4, "gap>=-3pp": 14, "gap>=-4pp": 44}

Top 25 near-misses (best gap per game/book/pairing):

| game | book | pairing | gap pp | K ask | fee c | book odds (opp. side) | book p | K ask size |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Cincinnati Bengals vs Tennessee Titans | DraftKings | kalshi_away+book_home | -1.667 | 0.14 | 1 | -650 | 0.8667 | 4289148.0 |
| Detroit Lions vs Minnesota Vikings | DraftKings | kalshi_away+book_home | -1.963 | 0.37 | 2 | -170 | 0.6296 | 70.0 |
| Los Angeles Rams vs Los Angeles Chargers | DraftKings | kalshi_away+book_home | -1.973 | 0.27 | 2 | -270 | 0.7297 | 2373783.0 |
| Dallas Cowboys vs Arizona Cardinals | BetRivers | kalshi_home+book_away | -2.0 | 0.75 | 2 | 300 | 0.25 | 1577330.7 |
| Cincinnati Bengals vs Tennessee Titans | BetRivers | kalshi_away+book_home | -2.013 | 0.14 | 1 | -670 | 0.8701 | 4289148.0 |
| Miami Dolphins vs New England Patriots | FanDuel | kalshi_home+book_away | -2.19 | 0.24 | 2 | -320 | 0.7619 | 536808.53 |
| Miami Dolphins vs New England Patriots | DraftKings | kalshi_home+book_away | -2.471 | 0.24 | 2 | -325 | 0.7647 | 536808.53 |
| Miami Dolphins vs New England Patriots | BetMGM | kalshi_home+book_away | -2.471 | 0.24 | 2 | -325 | 0.7647 | 536808.53 |
| Cincinnati Bengals vs Tennessee Titans | BetMGM | kalshi_away+book_home | -2.5 | 0.14 | 1 | -700 | 0.875 | 4289148.0 |
| Detroit Lions vs Minnesota Vikings | FanDuel | kalshi_away+book_home | -2.504 | 0.37 | 2 | -174 | 0.635 | 70.0 |
| Indianapolis Colts vs Jacksonville Jaguars | FanDuel | kalshi_home+book_away | -2.608 | 0.81 | 2 | 410 | 0.1961 | 3301854.14 |
| Detroit Lions vs Minnesota Vikings | BetRivers | kalshi_away+book_home | -2.636 | 0.37 | 2 | -175 | 0.6364 | 70.0 |
| Tampa Bay Buccaneers vs Atlanta Falcons | FanDuel | kalshi_away+book_home | -2.752 | 0.45 | 2 | -126 | 0.5575 | 3753623.4 |
| Cincinnati Bengals vs Tennessee Titans | FanDuel | kalshi_home+book_away | -2.925 | 0.87 | 1 | 570 | 0.1493 | 311028.31 |
| Miami Dolphins vs New England Patriots | Caesars | kalshi_home+book_away | -3.011 | 0.24 | 2 | -335 | 0.7701 | 536808.53 |
| New York Jets vs Las Vegas Raiders | FanDuel | kalshi_away+book_home | -3.128 | 0.47 | 2 | -118 | 0.5413 | 1450051.91 |
| Detroit Lions vs Minnesota Vikings | Caesars | kalshi_away+book_home | -3.158 | 0.37 | 2 | -179 | 0.6416 | 70.0 |
| Cincinnati Bengals vs Tennessee Titans | Caesars | kalshi_away+book_home | -3.235 | 0.14 | 1 | -750 | 0.8824 | 4289148.0 |
| Philadelphia Eagles vs Washington Commanders | FanDuel | kalshi_home+book_away | -3.303 | 0.71 | 2 | 230 | 0.303 | 2382047.54 |
| Dallas Cowboys vs Arizona Cardinals | FanDuel | kalshi_home+book_away | -3.316 | 0.75 | 2 | 280 | 0.2632 | 1577362.02 |
| Los Angeles Rams vs Los Angeles Chargers | Caesars | kalshi_away+book_home | -3.359 | 0.27 | 2 | -290 | 0.7436 | 2373783.0 |
| Cincinnati Bengals vs Tennessee Titans | BetMGM | kalshi_home+book_away | -3.385 | 0.87 | 1 | 550 | 0.1538 | 310977.78 |
| Philadelphia Eagles vs Washington Commanders | BetRivers | kalshi_away+book_home | -3.429 | 0.3 | 2 | -250 | 0.7143 | 1613952.35 |
| Philadelphia Eagles vs Washington Commanders | BetMGM | kalshi_away+book_home | -3.429 | 0.3 | 2 | -250 | 0.7143 | 1613952.35 |
| Tampa Bay Buccaneers vs Atlanta Falcons | DraftKings | kalshi_home+book_away | -3.455 | 0.56 | 2 | 120 | 0.4545 | 14126.63 |

Best gap per game across all executable books:

| game | book | pairing | gap pp | ask | fee c | opp. odds | ask size |
|---|---|---|---:|---:|---:|---:|---:|
| Cincinnati Bengals vs Tennessee Titans | DraftKings | kalshi_away+book_home | -1.667 | 0.14 | 1 | -650 | 4289148.0 |
| Detroit Lions vs Minnesota Vikings | DraftKings | kalshi_away+book_home | -1.963 | 0.37 | 2 | -170 | 70.0 |
| Los Angeles Rams vs Los Angeles Chargers | DraftKings | kalshi_away+book_home | -1.973 | 0.27 | 2 | -270 | 2373783.0 |
| Dallas Cowboys vs Arizona Cardinals | BetRivers | kalshi_home+book_away | -2.0 | 0.75 | 2 | 300 | 1577330.7 |
| Miami Dolphins vs New England Patriots | FanDuel | kalshi_home+book_away | -2.19 | 0.24 | 2 | -320 | 536808.53 |
| Indianapolis Colts vs Jacksonville Jaguars | FanDuel | kalshi_home+book_away | -2.608 | 0.81 | 2 | 410 | 3301854.14 |
| Tampa Bay Buccaneers vs Atlanta Falcons | FanDuel | kalshi_away+book_home | -2.752 | 0.45 | 2 | -126 | 3753623.4 |
| New York Jets vs Las Vegas Raiders | FanDuel | kalshi_away+book_home | -3.128 | 0.47 | 2 | -118 | 1450051.91 |
| Philadelphia Eagles vs Washington Commanders | FanDuel | kalshi_home+book_away | -3.303 | 0.71 | 2 | 230 | 2382047.54 |
| Cleveland Browns vs Pittsburgh Steelers | Caesars | kalshi_away+book_home | -3.517 | 0.36 | 2 | -190 | 11751.34 |
| Chicago Bears vs Seattle Seahawks | FanDuel | kalshi_away+book_home | -3.687 | 0.39 | 2 | -168 | 2079.03 |
| Buffalo Bills vs Baltimore Ravens | FanDuel | kalshi_away+book_home | -3.687 | 0.39 | 2 | -168 | 3112616.49 |
| Denver Broncos vs Kansas City Chiefs | DraftKings | kalshi_home+book_away | -4.128 | 0.48 | 2 | -118 | 13.89 |

Median components of the best-reached pairing per (game, book, pairing): Kalshi ask 0.505 + fee 0.020 + book implied 0.523 = cost 1.046 (arb needs < 1.000).

Venue costs, same snapshots: Kalshi ask-pair overround (ask_home + ask_away - 1) median 1.00 pp (p5 0.00, p95 2.00); sportsbook vig (p_home + p_away - 1) median 4.25 pp (p5 3.85, p95 5.29).  Cost of a hedged pair = 1 + Kalshi overround/2-ish + fee + book vig/2-ish, i.e. roughly 4-5 pp over par before any disagreement.

Counterfactual (not a result): with Kalshi's fee set to ZERO the best NFL gap would be 0.04 pp; 232 observations across 2 games would be positive.

## Arbitrage instances (fee-inclusive cost < 100%), NFL, executable books

Episodes (distinct game/book/pairing runs): **0**, across 0 distinct games, 0 distinct game/book/pairing triples; raw snapshot-level arb observations: 0.

## 60-second survival

Survive 0, fail (arb closed) 0, fail (leg gone) 0, censored (no re-check snapshot in 60-90 s) 0.  Episode survival rate: **n/a**.  Snapshot-level: {"survive": 0, "fail": 0, "rate": null}

## Concentration

By book: {} (max share n/a).  By game: {} (max share n/a).

## VERDICT: **KILL**  (NFL game winners x 5 executable books; spec-literal 7-id variant: INSUFFICIENT)

| bar (frozen) | threshold | observed | met |
|---|---:|---:|:---:|
| 1a >= 20 fee-inclusive instances | 20 | 0 | NO |
| 1b across >= 10 distinct games | 10 | 0 | NO |
| 2 median arb >= 1.0% (1.00 - cost, pp) | 1.0 | None | NO |
| 3 median executable size >= $100 (Kalshi leg notional) | 100.0 | None | NO |
| 4 no single book > 50% | 0.5 | None | NO |
| 5 >= 50% survive 60 s re-check | 0.5 | None | NO |

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

## Variants (disclosed, not the verdict)

| universe | pair obs | best gap pp | arb episodes | games | median edge pp | median Kalshi $ | survival | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| nfl / executable_books (VERDICT) | 30030 | -1.67 | 0 | 0 | n/a | n/a | n/a | KILL |
| nfl / spec_literal_7_ids (VERDICT) | 41580 | 10.64 | 9 | 9 | 3.000 | 600480.7 | 1.000 | INSUFFICIENT |
| nfl / pseudo_books_only (VERDICT) | 11550 | 10.64 | 9 | 9 | 3.000 | 600480.7 | 1.000 | - |
| nba / executable_books (secondary) | 23100 | -2.00 | 0 | 0 | n/a | n/a | n/a | KILL |
| nba / spec_literal_7_ids (secondary) | 31878 | 4.46 | 6 | 6 | 2.538 | 67364.9 | 1.000 | INSUFFICIENT |
| nba / pseudo_books_only (secondary) | 8778 | 4.46 | 6 | 6 | 2.538 | 67364.9 | 1.000 | - |
| nhl / executable_books (secondary) | 8998 | 3.50 | 104 | 1 | 0.512 | 22.0 | 0.000 | KILL |
| nhl / spec_literal_7_ids (secondary) | 12694 | 3.50 | 139 | 3 | 0.512 | 22.0 | 0.016 | KILL |
| nhl / pseudo_books_only (secondary) | 3696 | 1.55 | 35 | 3 | 0.083 | 22.0 | 0.062 | - |
| ncaaf / executable_books (secondary) | 114500 | -0.49 | 0 | 0 | n/a | n/a | n/a | KILL |
| ncaaf / spec_literal_7_ids (secondary) | 159402 | 7.22 | 54 | 18 | 1.611 | 76096.4 | 1.000 | INSUFFICIENT |
| ncaaf / pseudo_books_only (secondary) | 44902 | 7.22 | 54 | 18 | 1.611 | 76096.4 | 1.000 | - |

### nhl arb episodes (secondary, executable books)

| game | book | pairing | K ask | fee c | opp. odds | edge pp | ask size | Kalshi leg $ | profit $ | re-check |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Calgary Flames vs Seattle Kraken | BetMGM | kalshi_home+book_away | 0.44 | 2 | -102 | 3.505 | 50.0 | 22.0 | 1.75 | fail_closed |
| Calgary Flames vs Seattle Kraken | BetMGM | kalshi_home+book_away | 0.45 | 2 | -102 | 2.505 | 65.0 | 29.25 | 1.63 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | censored |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -114 | 0.729 | 50.0 | 22.0 | 0.36 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | censored |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | censored |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | Caesars | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | DraftKings | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | DraftKings | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | DraftKings | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | DraftKings | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | DraftKings | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |
| Calgary Flames vs Seattle Kraken | DraftKings | kalshi_home+book_away | 0.44 | 2 | -115 | 0.5116 | 50.0 | 22.0 | 0.26 | fail_closed |

## Feed-integrity filter and its unfiltered disclosure

A book whose home-team implied probability is more than 15pp from the median of the executable books is excluded (counted in Exclusions). It was added after BetMGM's NHL line for Winnipeg/Florida appeared with both teams' odds swapped relative to every other book (a 28.9pp fake arb). It can only remove candidate arbs. Same scoring with the filter OFF (executable books):

- nfl: 30030 pair observations, 0 arb observations, max gap -1.67 pp
- nba: 23100 pair observations, 0 arb observations, max gap -2.00 pp
- nhl: 9240 pair observations, 484 arb observations, max gap 28.91 pp
- ncaaf: 114500 pair observations, 0 arb observations, max gap -0.49 pp

## (b) Simultaneity

Both legs' fetch start/end epoch times are stored in every snapshot.  Rule: discard if (latest leg end - earliest leg start) > 60.0 s.  Observed max span 5.46 s, median 0.97 s; pairs discarded: 0.  The guard is exercised in `selftest` on a synthetic pair 62 s apart (discarded).  Caveat the code cannot see: Action Network's own refresh lag versus the books' live prices (the payload carries no per-line timestamp).

## (c) Executable prices only: AST audit

`audit_executable_only` parses `cross_venue.py` and raises on any identifier/attribute/string naming the buy-side-low quote or the average of two quotes (the forbidden words), and on `(a+b)/2` / `(a+b)*0.5` patterns.  Clean source passes: **True**.  Negative controls (doctored copies; each must raise):

- `control_1_mean_of_two_quotes_named`: raised = **True** (line 925: forbidden token ['mid'] in 'mid_price'; line 925: (a+b)/2 pattern; line 925: forbidden token ['bid'] in 'yes_bid')
- `control_2_bare_average_pattern`: raised = **True** (line 925: (a+b)/2 pattern)
- `control_3_reads_the_low_side_field`: raised = **True** (line 925: forbidden token ['bid'] in 'yes_bid_dollars')
- `control_4_half_multiplication`: raised = **True** (line 925: (a+b)*0.5 pattern)

The collector stores only ask-side Kalshi fields (ticker, event, name, yes_ask, yes_ask_size, status, times).

## (d) Fee provenance (from `GET /series/{ticker}` at collection time)

| league | series | fee_type | fee_multiplier |
|---|---|---|---:|
| nfl | KXNFLGAME | quadratic_with_maker_fees | 1 |
| nba | KXNBAGAME | quadratic_with_maker_fees | 1 |
| nhl | KXNHLGAME | quadratic_with_maker_fees | 1 |
| ncaaf | KXNCAAFGAME | quadratic_with_maker_fees | 1 |

Fee used: `ceil(7 * fee_multiplier * p * (1-p))` cents per contract at the ask, per the spec.  Table check (selftest): {"50": 2, "70": 2, "85": 1, "95": 1, "1": 1, "99": 1}.  Kalshi's real fee is rounded on the whole order, so the per-contract ceiling overstates the fee at size (conservative against finding an arb).

## (e) Size in dollars

Every stage above reports dollars: Kalshi-leg notional (ask size x ask), two-leg outlay (ask size x cost), profit (ask size x edge), and the sportsbook stake the hedge would need (ask size x book implied probability).  Ask sizes are capped by nothing but the resting Kalshi quote; the sportsbook leg's own bet limit is unobserved and is typically far below the larger sizes seen here.

## Exclusions (count, reason)

| count | reason |
|---:|---|
| 231 | nba:book30_excluded:feed_anomaly_gt_15pp_from_cross_book_median |
| 6006 | nba:kalshi_event_unmatched:no_AN_game_with_both_names |
| 1374 | ncaaf:AN_game_not_pregame(status!=scheduled or started) |
| 220 | ncaaf:book15_excluded:line_status_opener |
| 229 | ncaaf:book30_excluded:feed_anomaly_gt_15pp_from_cross_book_median |
| 43052 | ncaaf:kalshi_event_unmatched:no_AN_game_with_both_names |
| 2 | ncaaf:leg_fetch_error_snapshot_discarded |
| 231 | nfl:AN_game_not_pregame(status!=scheduled or started) |
| 231 | nfl:book30_excluded:feed_anomaly_gt_15pp_from_cross_book_median |
| 3465 | nfl:kalshi_event_unmatched:no_AN_game_with_both_names |
| 121 | nhl:book75_excluded:feed_anomaly_gt_15pp_from_cross_book_median |
| 10164 | nhl:kalshi_event_unmatched:no_AN_game_with_both_names |

Matching (events matched / unmatched, final union across snapshots):

- nfl: 13 matched events; unmatched: {"KXNFLGAME-26NOV09BUFMIN": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08TBCHI": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08GBNE": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08ARISEA": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08LVSF": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08HOULAC": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08LARWAS": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08NYGPHI": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08DETMIA": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08DALIND": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08DENCAR": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08CLENO": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08NYJKC": "no_AN_game_with_both_names", "KXNFLGAME-26NOV08CINATL": "no_AN_game_with_both_names", "KXNFLGAME-26NOV05JACBAL": "no_AN_game_with_both_names"}
- nba: 10 matched events; unmatched: {"KXNBAGAME-26NOV02MIALAL": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02TORLAC": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02PHXGSW": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02PORDEN": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02UTASAS": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02BOSHOU": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02MILMIN": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02NOPMEM": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02SACDAL": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02CHIPHI": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02WASORL": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02BKNNYK": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02ATLIND": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02DETCHA": "no_AN_game_with_both_names", "KXNBAGAME-26NOV02OKCCLE": "no_AN_game_with_both_names", "KXNBAGAME-26NOV01TORLAL": "no_AN_game_with_both_names", "KXNBAGAME-26NOV01LACGSW": "no_AN_game_with_both_names", "KXNBAGAME-26NOV01BKNIND": "no_AN_game_with_both_names", "KXNBAGAME-26NOV01BOSORL": "no_AN_game_with_both_names", "KXNBAGAME-26OCT31OKCHOU": "no_AN_game_with_both_names", "KXNBAGAME-26OCT31MINSAS": "no_AN_game_with_both_names", "KXNBAGAME-26OCT31CLEMIL": "no_AN_game_with_both_names", "KXNBAGAME-26OCT31SACMEM": "no_AN_game_with_both_names", "KXNBAGAME-26OCT31ATLNOP": "no_AN_game_with_both_names", "KXNBAGAME-26OCT31PHICHA": "no_AN_game_with_both_names", "KXNBAGAME-26OCT31PORUTA": "no_AN_game_with_both_names"}
- nhl: 4 matched events; unmatched: {"KXNHLGAME-26NOV05NSHCOL": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05VANWPG": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05ANAEDM": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05CHITB": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05DALCBJ": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05CARNYI": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05UTAMTL": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05PHINYR": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05BOSPIT": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05STLNJ": "no_AN_game_with_both_names", "KXNHLGAME-26NOV05VGKDET": "no_AN_game_with_both_names", "KXNHLGAME-26NOV04SJLA": "no_AN_game_with_both_names", "KXNHLGAME-26NOV04CHIFLA": "no_AN_game_with_both_names", "KXNHLGAME-26NOV04OTTBUF": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03ANAVAN": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03CARNSH": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03UTATOR": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03EDMNJ": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03DALWSH": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03STLNYR": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03COLCBJ": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03VGKPIT": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03DETTB": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03WPGMTL": "no_AN_game_with_both_names", "KXNHLGAME-26NOV03MINPHI": "no_AN_game_with_both_names", "KXNHLGAME-26NOV02CGYSJ": "no_AN_game_with_both_names", "KXNHLGAME-26NOV02COLCHI
- ncaaf: 50 matched events; unmatched: {"KXNCAAFGAME-26NOV12ULLULM": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV12MEMUSF": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV11MASSTOL": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV11SACCMU": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV11BUFFBALL": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV10OHIOMOH": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV10KENTBGSU": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV10WMUAKR": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07OREOSU": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07WAGMHU": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07UGAMISS": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07ALALSU": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07BYUUTAH": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07MRMKWAKE": "no_AN_game_with_both_names", "KXNCAAFGAME-26OCT31DSUNORF": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07WYOUNLV": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07TXSTORST": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07FRESUSU": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07UWFLUNA": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07IWSELA": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07ACTARL": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07UTUUCD": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07SIUINST": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07MTSTIDST": "no_AN_game_with_both_names", "KXNCAAFGAME-26NOV07MIAND": "no_AN_game_with_both_names", "KXNCA
