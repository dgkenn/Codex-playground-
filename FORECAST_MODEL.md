# FORECAST_MODEL — does Kalshi mispricing vs a sharp external line exist on SPORTS markets?

**DEPLOYABLE: NO.** Kalshi's NFL moneyline market (`KXNFLGAME`) prices to within a fraction of a cent of
the devigged Vegas closing line, on average, across a full season (n=274 games, 2025 season). A
walk-forward model trained on 26 years of history independently confirms the market is *at least as good
as*, and by this test measurably *better than*, a mechanical, information-poor predictor. Honest capacity:
**$0/month.** This closes the "forecasting axis" (sharp external forecast vs Kalshi price) for sports, the
same way `FORECAST_OVERLAY_BACKTEST.md` closed it for weather and `PER_SERIES_SCAN.md` / `FAVORITE_LONGSHOT.md`
/ `MAKER_FAVLONG.md` closed the last_price/favorite-longshot axes.

---

## 1. Thesis (pre-registered before any Kalshi price was read)

Kalshi sports "Winner?" markets (`KXNFLGAME`, `KXNBAGAME`, `KXMLBGAME`, `KXNHLGAME`, ...) are retail-facing
prediction markets, distinct from the professional sportsbook market that sets the point spread / moneyline.
If Kalshi's own order book is slower to converge to "true" win probability than the sharp bookmaker consensus
— because Kalshi's liquidity providers are thinner/less sophisticated, or because Kalshi users anchor on
naive signals (record, name recognition) rather than a full sharp-line read — there could be a **non-latency**
edge: read the Vegas closing line (public, available pre-game), compare to Kalshi's own pre-game crossing
price, and buy whichever side Kalshi underprices relative to the sharp market. This is exactly the class of
edge the repo's DEPLOYABILITY bar is built for (enter pre-game, hold to settle, no speed race) — **if** it
exists net of Kalshi's fee and the real bid/ask spread.

**Two independent tests, pre-registered together** (see `analyze.py`'s docstring, written and committed to
before this script was ever run against real numbers):

- **Test A — sharp-line**: devigged Vegas **closing** moneyline (public, available before Kalshi entry) vs
  Kalshi's own pregame crossing price.
- **Test B — trained model**: a walk-forward Elo model fit on 1999–2024 NFL history (nflverse), continued
  week-by-week through the 2025 season using only games strictly before each prediction (true OOS, no
  leakage even within-season) — tests whether Kalshi is beatable by *any* mechanically-derived probability,
  not just the specific Vegas number.

**Pre-registered pass bar (fixed before reading any EV number, both tests must clear it):**
- entry rule: trade whichever side has raw edge (sharp/model prob − Kalshi crossing price) ≥ 0.03 (primary
  threshold; 0.00/0.05/0.08 reported as pre-registered sensitivity, not post-hoc cherry-picking)
- cost basis = the **real** crossing price (`yes_ask` to buy YES, `1 − yes_bid` to buy NO), never mid/last
- fee = `ceil(7·p·(1−p))/100` per contract (house formula), applied at the true cost-basis price
- clustering unit = **gameday** (calendar date) — games on the same Sunday are not independent draws
- **EV/contract net-of-fee ≥ +0.02, day-clustered t ≥ 2.5, n ≥ 100 qualifying trades, Wilson95 win-rate
  lower bound clears the fee-implied breakeven** — Bonferroni-over-2 (α=0.025 two-sided ≈ t≥2.24); this
  study uses the stricter t≥2.5 bar already established elsewhere in this repo.
- an honest null, on either test or after correction, is reported as **NOT DEPLOYABLE**, not re-run with a
  different threshold looking for significance.

---

## 2. Data sources

| Source | What | Access |
|---|---|---|
| Kalshi `KXNFLGAME` (moneyline "Winner?" markets) | 2025 NFL season pregame prices | `kx_history.py` parquet archive (event/market census) **+** official `/historical/markets/{ticker}/candlesticks` API (1-minute resolution, authoritative, last complete minute before kickoff = the real crossing price) |
| nflverse `nfldata/data/games.csv` | Vegas closing moneyline (`home_moneyline`/`away_moneyline`), final scores, kickoff time (`gameday`+`gametime`), 1999–2025 | Public GitHub raw CSV (`raw.githubusercontent.com/nflverse/nfldata`), pulled via `curl` per the house proxy note |

**Universe**: 331 `KXNFLGAME` events in the archive for the 2025 season (Aug 2025 – Jan 2026); 49 are
preseason (no Vegas line in nflverse, correctly excluded) → **282 regular-season + playoff (WC/DIV) games
matched** by (kickoff date ±2 days, home/away team abbreviation parsed from the Kalshi title's city name).
274/282 had a usable pregame candlestick (8 markets had zero trades in the 3-hour pre-kickoff window —
noted, not filled with a stale proxy). The archive is frozen ~Jan 2026, so the 2 Conference Championship
games and the Super Bowl (played after the freeze) are out of scope — not selection bias, just a data-freeze
boundary; excluding 3 games from a 282-game sample cannot move any of the numbers below.

**Why this pair of sources is a fair, non-latency test**: both the Vegas closing line and the Kalshi pregame
crossing price are read at the *same* point in information time (right before kickoff) — no lag advantage
either way is assumed or required. This is a "does Kalshi under- or over-react to already-public information"
test, not a speed race.

---

## 3. Backtest A — sharp-line (devigged Vegas closing moneyline)

Devig method: proportional (`p_i / Σp_i` over the two American-odds implied probabilities) — standard,
simplest de-vig; not tuned to this dataset.

| threshold | n trades | distinct gamedays | win rate | Wilson95 | avg cost | EV/contract (net of fee) | day-clustered t |
|---|---|---|---|---|---|---|---|
| 0.00 (trade every game with any edge either side) | 189 | 49 | 49.7% | [42.7%, 56.8%] | 0.478 | **−0.0001** | **−0.13** |
| 0.03 (pre-registered primary) | 3 | 3 | 33.3% | [6.1%, 79.2%] | 0.487 | −0.1733 | −0.82 |
| 0.05 | 0 | — | — | — | — | — | — |
| 0.08 | 0 | — | — | — | — | — | — |

**Reading this**: at the loosest threshold (any nonzero edge, n=189, 49 distinct Sundays — a well-powered
sample), EV/contract is **−0.01 cents**, day-clustered t=−0.13 — statistically and economically
indistinguishable from zero. At the pre-registered 3-cent bar, only **3 of 274 games** ever show a Vegas-vs-Kalshi
gap that large, and even those 3 (n far below the 100-trade floor, reported for completeness only) lost
money. **No threshold in the pre-registered sensitivity sweep produces a positive, well-powered signal.**

**One example, spot-checked end-to-end** (DAL @ PHI, 2025-09-04, Thursday opener): Vegas closing moneyline
DAL +330 / PHI −425 → devigged P(DAL wins) = **22.32%**. Kalshi's last-minute-before-kickoff price:
yes_ask **22c** / yes_bid **21c**. Final score PHI 24–20 (PHI, the favorite, won). Kalshi's market matched the
sharp consensus to within three tenths of a cent — the median case across the whole sample, not a cherry-pick
(the full-sample edge distribution: p10 = −0.36c, median = **+0.36c**, p90 = +1.70c, max = +4.66c across all
274 games).

## 4. Backtest B — trained model (walk-forward Elo, 1999–2024 → OOS 2025)

Vanilla Elo (`elo_model.py`): init 1500, K=20, home-field-advantage=55 Elo points, **no** margin-of-victory
multiplier, **no** tuning against this dataset — deliberately unsophisticated so this is a genuine "can a
mechanical, public-information-only model beat Kalshi" test, not a strawman. Fit walk-forward on 7,276
games (1999–2024 regular/postseason), then continued week-by-week through 2025 using **only** games strictly
before each prediction (true OOS; even within-season, ratings only use the past). Test-season Brier score:
**0.236** (0.25 = coin flip; this is in the normal range for a published, unaugmented NFL Elo system —
not a broken model).

| threshold | n trades | distinct gamedays | win rate | Wilson95 | avg cost | EV/contract (net of fee) | day-clustered t |
|---|---|---|---|---|---|---|---|
| 0.00 | 266 | 61 | 39.8% | [34.2%, 45.8%] | 0.422 | −0.0427 | −1.33 |
| 0.03 | 215 | 54 | 37.7% | [31.5%, 44.3%] | 0.417 | −0.0593 | −1.64 |
| 0.05 | 175 | 48 | 36.6% | [29.8%, 43.9%] | 0.402 | −0.0554 | −1.44 |
| 0.08 (pre-registered, highest-confidence disagreements) | 132 | 42 | 34.8% | [27.3%, 43.3%] | 0.396 | **−0.0667** | **−2.21** |

**Reading this**: trading against Kalshi whenever the Elo model disagrees with it is **negative EV at every
threshold, and gets *more* negative as the Elo/Kalshi disagreement grows** (−4.3c → −6.7c/contract from
loosest to tightest filter, t drifting from −1.33 to −2.21). That is the signature of Kalshi's price
containing real information the Elo model lacks (injuries, recent form, situational factors) — the market is
**better than** this mechanical predictor, not worse. This is not a fragile or borderline result; it is
directionally opposite to what a deployable edge would look like, and the effect strengthens (doesn't wash
out) as the filter tightens, which is the opposite of a noise artifact.

---

## 5. Self-adversarial verification pass

**Process note**: the repo's binding model policy calls for a separate Fable-model judge on any claimed
positive result. Nothing here is a claimed positive result — both tests are null-or-negative — but the
`kwx-study-audit` 10-point checklist was still run in full, adversarially, against this null, because a
*wrongly-null* result (e.g. a look-ahead bug that only appears to erase a real edge) would be just as bad a
research-integrity failure as a false positive. This session had no mechanism to spawn a literal separate
Fable-model process; the checklist below was applied by the same session with the goal of finding a bug that
would overturn the null, not confirm it.

1. **Look-ahead in the sharp line?** No — nflverse's `home_moneyline`/`away_moneyline` are the market's own
   *closing* consensus, definitionally available at kickoff; no future information beyond what a bettor
   could see pre-game is used.
2. **Look-ahead in the Kalshi price?** No — the candlestick's `end_period_ts` is bounded `≤ kickoff`, and the
   API call's own `end_ts` parameter was set to the kickoff timestamp, so no in-game (post-snap) trade can
   leak into the "pregame" price. Cross-checked against the official `/historical/*` trade tape for one
   ticker: the tape shows trading volume is dominated by **in-game** activity (thousands of trades per
   quarter as score/win-prob evolves) — using "most recent trade" instead of "last candle before kickoff"
   would have been a real look-ahead bug; the candlestick-endpoint approach was adopted specifically to avoid
   it (documented in `fetch_candles.py`'s docstring).
3. **Selection bias in game matching?** 274/282 (97%) matched with a live price; the 8 unmatched had zero
   trades in a 3-hour pre-kickoff window (illiquid pre-game book), not excluded for any outcome-related
   reason. Team/date matching spot-checked against a real box score (DAL@PHI above) and reproduces exactly.
4. **Devig-method sensitivity?** Only one method (proportional) was used; alternative devig methods (Shin,
   power) shift fair probabilities by a few tenths of a percent at typical NFL vig levels — far smaller than
   what would be needed to turn a −0.01c/contract null into a deployable edge. Not separately reported
   because there is nothing here for a devig-method choice to rescue.
5. **Multiple-comparisons / threshold-shopping?** 4 thresholds pre-registered per test, all reported (not
   just the best one); none shows a positive, well-powered result at any threshold in either test, so there
   is no cherry-picked row driving the conclusion. Bonferroni-over-2-tests was pre-registered and is moot —
   nothing clears even the uncorrected bar.
6. **Fee/entry realism?** Cost basis is the real `yes_ask`/`1−yes_bid` crossing price (never mid/last), fee
   applied via the house formula at that price — this is the same standard the rest of this repo's
   deployability gate uses.
7. **Day-clustering correctness?** Yes — every t-stat above is computed on per-gameday means (49–61 distinct
   Sundays/weeks depending on threshold), not a naive per-game t-test, per the house statistical-discipline
   requirement.
8. **Is the "trained model" a fair, non-strawman test?** Yes — Brier 0.236 is in the normal range for
   published vanilla NFL Elo (not artificially crippled), and it was never tuned against Kalshi prices or
   this season's outcomes; its own historical fit (26 seasons, 7,276 games) is entirely independent of
   anything Kalshi-related.
9. **Capacity, if there had been an edge?** `KXNFLGAME` median per-market cumulative volume is in the
   millions of contracts per season; capacity was never going to be the binding constraint here — moot,
   since there is no edge to size.
10. **Reproducibility?** All scripts and intermediate data live under
    `/tmp/claude-0/.../scratchpad/forecast/` (`build_games.py`, `elo_model.py`, `fetch_candles.py`,
    `analyze.py`, `data/*.json`) — read-only public-API/public-data pulls, reproducible from the commands in
    each script's own header. Nothing in this study touches the live trading path.

**Verdict: the null survives adversarial pressure on both tests.** No mechanism was found that would turn
either result into a real edge; if anything, the Elo test's *strengthening negative* signal at tighter
thresholds is independent evidence the market genuinely outperforms a naive predictor, not evidence of an
artifact suppressing a real edge.

---

## 6. Honest OOS capacity + drawdown

**Capacity: $0/month.** There is no verified positive edge on either test to size. The "drawdown" question
is moot for the same reason — nothing is proposed for paper or live deployment.

For context only (not a deployability input): had an edge existed, `KXNFLGAME` liquidity (median volume in
the millions of contracts/season, `yes_bid`/`yes_ask` spreads of ~1 cent on the spot-checked example) would
not have been a binding constraint — this is a liquid, well-quoted market. The kill here is pure market
efficiency, not an execution/capacity problem, which is the same mechanism (not the same market) that has
now closed every axis this repo has tested: weather forecast-overlay (`FORECAST_OVERLAY_BACKTEST.md`),
last_price bias at series and category granularity (`PER_SERIES_SCAN.md`, `WX_EXPANSION.md`), and
favorite-longshot capture at taker and maker execution (`FAVORITE_LONGSHOT.md`, `MAKER_FAVLONG.md`).

---

## 7. Actions taken

1. **Do NOT deploy.** No sleeve is built, no live/paper harness is added, no change to the live mechanical-lock
   path (`kwx_runner.py`, `kwx_paper_gate.py`, `kalshi_exec.py`) — none was made or considered.
2. `p4k_params.json` is **not** modified — there is no capacity to register (per the task's own branching:
   sleeve files and a `p4k_params.json` entry are only warranted `IF DEPLOYABLE`).
3. `RESEARCH_LEDGER.md` updated: graveyard row #35 (sports sharp-line/trained-model forecasting axis) and a
   new meta-conclusion update closing this axis alongside the weather forecast-overlay closure.
4. Reproduction artifacts kept under the session scratchpad (not committed — read-only public-data backtest,
   reproducible from the scripts' own headers), per house caching convention; large intermediate caches are
   deleted at the end of this session.
