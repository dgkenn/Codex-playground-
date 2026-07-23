# WX_ENSEMBLE_FORWARD.md -- 51-member ECMWF ensemble vs live Kalshi price (forward-only logger)

## Why forward-only, not a backtest

`wx_forecast_model.py` already tests the *deterministic* Open-Meteo forecast (one point value per
city-day) against Kalshi, with its own forward harness. The 51-member **ensemble**
(`ensemble-api.open-meteo.com/v1/ensemble`, `models=ecmwf_ifs025`) is a different signal: instead of a
single point forecast it gives a full empirical distribution of the daily extreme, so `P(clears strike)`
can be read directly as a member-fraction instead of assumed-Normal from a point + a fitted residual std.

But the ensemble endpoint only retains **~92h of history** server-side (confirmed 2026-07-23) -- there is
no way to ask it "what did the 51-member ensemble say three weeks ago." **This edge cannot be
backtested.** It can only be measured going forward: log the live ensemble's `P(clears strike)` next to the
live Kalshi price at snapshot time (no look-ahead -- settlement is scored independently, later, off the
public Kalshi API), then let the forward record accumulate. This is the same shape as the sibling forward
sleeves (`wx_earlylock_forward.py`, `wx_forecast_forward.py`); this one mirrors their idempotency and fee
accounting so all three stay directly comparable.

## Files

| File | Role |
|---|---|
| `wx_ens_forward.py` | `snapshot` (log candidates) / `settle` (score resolved ones) |
| `wx_ens_decision.py` | Reads `wx_ens_settled.jsonl` only, prints ACCRUING / ACTIVATE / KILL |
| `wx_ens_paper.jsonl` | Every logged candidate (append-only, idempotent per ticker) |
| `wx_ens_settled.jsonl` | Every scored/settled candidate (append-only, idempotent per ticker) |
| `kwx-ens.yml.proposed` | Draft GH Actions cron (operator installs on `main` separately) |

## How a candidate gets logged (`snapshot`)

For every active Kalshi weather city+kind (`kwx_runner.CITY` / `CITY_LOW_SERIES`, read-only, unmodified):

1. Pull the **current live** ECMWF 51-member ensemble (`temperature_2m` control + `member01..member50`)
   for the station's LST day, hourly, `forecast_days=2`, `timezone=<station tz>`.
2. Per member, take the daily **extreme** (max for `KXHIGH*`, min for `KXLOWT*`) over that day's
   **populated** local hours only -- Open-Meteo nulls some hours at the forecast window's edges; a member
   with zero populated hours for the target date is dropped, not imputed.
3. For every ACTIVE market on that city+kind ladder (`kwx_runner.event_rungs`, live), round each member's
   raw extreme to the nearest integer degF (Kalshi settles on the integer NWS CLI value) and compute
   `ensemble_P` = fraction of members whose ROUNDED extreme satisfies the market's YES condition, using
   Kalshi's ACTUAL settlement convention (verified live against the API's `strike_type` field -- this is
   **not** the same convention as `kwx_runner.locked_and_misses`, which is a margin-padded lock test that
   never has to resolve an exact boundary and was never a valid source for the settlement spec; an earlier
   draft of this module wrongly copied it and was caught by adversarial review before any decision was made
   off the data -- see `ensemble_prob_yes`'s docstring in `wx_ens_forward.py`):

   | floor only | cap only | both (bucket) |
   |---|---|---|
   | YES = `X > floor` | YES = `X < cap` | YES = `floor <= X <= cap` (INCLUSIVE both ends) |

   This table is IDENTICAL for `max` (`KXHIGH*`) and `min` (`KXLOWT*`) kinds -- the comparison is against
   the settled integer value itself, not the kind, so there is no kind-conditional branch in the code.

4. Compare `ensemble_P` to whichever side (`yes`/`no`) is cheaper to buy right now. Log ONE candidate
   (the larger-edge side) if `|ensemble_P - price| > EDGE_THR`, including a rounded-integer histogram of all
   51 members' extremes (`member_hist`) so the row can be re-scored later without re-fetching, if the
   settlement convention is ever questioned again.

## Pre-registered knobs (frozen before any settled data was read)

- **`EDGE_THR = 0.15`** (probability units). Derivation: at n=51 members, the binomial sampling SE of a
  member-fraction at the most conservative point p=0.5 is `sqrt(0.5*0.5/51) ~= 0.070`; 2x that SE (~0.14,
  rounded to 0.15) is the point past which a raw disagreement is unlikely to be pure ensemble-sampling
  noise -- chosen independently of any backtest (impossible here) and, not coincidentally, matches
  `wx_forecast_forward.EDGE_THR`, so all three forward sleeves share one bar.
- **Fee**: `ceil(7*p*(1-p))/100` per contract (CLAUDE.md rule; same formula/rounding as
  `kwx_runner._kalshi_fee_c`), applied at the **logged** entry price.
- **Settlement truth**: the live public Kalshi API, `GET /markets/{ticker}`, `status=="finalized"`,
  `result` in `{yes,no}` -- not IEM/ASOS (the sibling sleeves use ASOS; this one uses Kalshi's own result
  because the decision layer needs the *actual settlement basis Kalshi paid out on*, not an independent
  truth source, to score the ensemble-vs-Kalshi Brier comparison fairly).
- **Both-side accounting**: a NO position's win payoff is `100 - entry_price_c` cents (the same `$1 -
  entry` formula as YES, since a NO contract's notional and payout structure mirror YES exactly) -- never
  a flat `100`.

## Activation bar (`wx_ens_decision.py`)

Frozen **before** reading any settled row, never moved after seeing results (CLAUDE.md research discipline):

| Check | Bar |
|---|---|
| day-clustered t (one-sample t on per-day mean pnl) | `>= 3.0` |
| EV/contract, net of fee | `> 0` |
| distinct settled days | `>= 30` |
| ensemble Brier score vs Kalshi Brier score | ensemble `<` Kalshi |

**Why the Brier check matters here specifically:** the ensemble's raison d'etre is a genuinely informative
51-member distribution, not just a directionally profitable trade that got lucky. `ensemble_brier =
mean((ensemble_P - y)^2)`, `kalshi_brier = mean((kalshi_p_yes - y)^2)` (y = 1 if the market resolved YES),
computed over the *same paired sample*. If the ensemble is not better-calibrated than the market's own
price, ACTIVATE is refused even if EV/t happen to clear -- that combination would mean the observed profit
is a small-sample fluke, not a real edge, and the CLAUDE.md rule ("every claimed positive must pass
adversarial verification") treats it that way.

`KILL` fires once `n_days >= 30` and the bar above is NOT cleared. `ACCRUING(n/30)` covers everything in
between, with an honest ETA in calendar days (not a naive rate ratio -- see the comment on
`wx_ens_decision._eta_days` for the units bug that formula avoids).

## A known, IMPORTANT caveat seen on the live snapshots

The `ecmwf_ifs025` ensemble (0.25° global ECMWF) can disagree substantially with Open-Meteo's own
deterministic `best_match` forecast (which blends in higher-resolution regional/local models for the US),
and the Kalshi ladder tends to price closer to the deterministic/local-model view. A re-verified live
snapshot (2026-07-23, after the settlement-convention fix below) logged 68 candidates across 39 city+kind
events / 234 markets scored -- e.g. `KXHIGHMIA-...-B88.5` (Miami, floor=88/cap=89) scored `ensemble_P=0.608`
against a 1c `yes_ask`. That kind of gap may be a genuine information edge (a coarser global ensemble
catching something priced-out elsewhere) or it may just be **coarse-resolution model bias vs a
better-calibrated market**, indistinguishable without the forward record. There is no backtest to calibrate
a bias correction against (that's the whole reason this is forward-only), so `wx_ens_forward.py`
intentionally logs the RAW member fraction, uncorrected, and lets the Brier check above be the arbiter over
30+ real days. Do not read a high snapshot candidate count as evidence of an edge by itself.

**Correction note (2026-07-23, pre-deploy adversarial review):** the first draft of `ensemble_prob_yes`
copied `kwx_runner.locked_and_misses`' margin-padded LOCK convention (a different, non-boundary check) and
compared it against raw continuous member temps instead of Kalshi's actual integer-settlement, inclusive-
bucket convention. Measured impact on a candidate logged under the old code: `ensemble_P` off by up to
+/-25 points on some rungs -- larger than `EDGE_THR`, so candidate selection itself was measuring the bug,
not the ensemble. Caught before any decision was made off the data; fixed in `ensemble_prob_yes` (see its
docstring for the corrected convention), and the 68 rows logged under the wrong definition were discarded
and regenerated under the corrected one before this sleeve was registered.

## Reading the logs

```
python wx_ens_forward.py snapshot   # one live pass, prints n candidates + up to 12 examples
python wx_ens_forward.py settle     # scores resolved candidates from the public Kalshi API
python wx_ens_decision.py           # ACCRUING / ACTIVATE / KILL against the bar above
```

Each `wx_ens_paper.jsonl` row: `ts, ensemble_run_time, ticker, event, city, station, kind, date, floor,
cap, strike, ensemble_P, n_members, n_members_total, member_hist, kalshi_side, entry_price_c, fee_c,
yes_ask_c, no_ask_c, edge, thr`. `member_hist` is `{rounded_int_degF: count}` over all `n_members` members --
the re-scoring source of truth if `ensemble_prob_yes`'s convention is ever revisited (it already was once,
before any decision was made off the data; see the settlement-convention note above). `settle` appends
`result, won, pnl` to make a `wx_ens_settled.jsonl` row.

`ensemble_run_time` is the UTC instant the ensemble HTTP response was received -- a deliberately
CONSERVATIVE proxy for the ECMWF model's true init/cycle time (which the API response does not expose):
using fetch-time instead of init-time can only make the logged instant LATER than the true forecast
issuance, the safe direction for a no-look-ahead audit. `settle()` additionally refuses to score any row
until its LST `date` is strictly before the current UTC date, so no row can be scored before its own
outcome existed.

## Deploying the workflow

`kwx-ens.yml.proposed` is a draft (not installed). To go live: review it, drop the `.proposed` suffix,
commit it under `.github/workflows/`, and it runs `settle` -> `snapshot` -> `wx_ens_decision.py` on the
US-afternoon cron plus one post-midnight settle+report pass, force-committing only the two `.jsonl` logs
(pattern identical to `kwx-earlylock.yml`).
