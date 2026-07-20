# Spec #2 Backtest: OFF-AIR PASSIVE QUOTING, MENTIONS

**Series:** KXFEDMENTION, KXHANNITYMENTION
**Run date:** 2026-07-20
**Verdict: INCONCLUSIVE** (pre-registered failure path — minimum-n gate not met).
Even so, the descriptive numbers computed on all accessible data lean **negative**,
and the mandatory pre-air adverse-selection sub-check **fails** in every cut. This
is not a "no data, shrug" null — it's a null with a warning sign attached.

## 1. Data-availability finding (read this first)

The pre-registered spec assumed 45 settled KXFEDMENTION markets across 12 events
and 29 settled KXHANNITYMENTION markets across 2 events. The 29/2 Hannity number
checked out exactly. The Fed number did not survive contact with the live API:

- `GET /events?series_ticker=KXFEDMENTION&status=settled` does list all 12 events
  (25JAN through 26JUN) as metadata.
- `GET /markets?series_ticker=KXFEDMENTION&status=settled` and
  `GET /events?...&with_nested_markets=true` only return nested market detail
  (tickers, prices, results) for the **single most recently settled event**
  (KXFEDMENTION-26JUN, 45 markets). The other 11 events come back with an empty
  `markets: []` array — the metadata shell exists, but no market/trade data is
  retrievable through the public API. This was verified with `status=settled`,
  `status=finalized`, `status=closed`, and no-status queries, all with the same
  result.

Net accessible data: **3 event-days total** (1 Fed press conference + 2 Hannity
broadcasts), 74 markets, 19,501 raw trade prints — versus the pre-registered
minimum of **≥10 event-days**. This is a hard data-retention wall on Kalshi's
public API for this low-volume custom-strike series family, not a bug in the
harvest. It independently confirms the house-rules illiquidity warning: for
long-tail "Mentions" markets, you frequently can't even get the history needed to
judge tradeability, let alone trade it.

Because the min-n bar was pre-registered specifically to prevent exactly this
failure mode (drawing conclusions from too few days), the formal verdict is
**INCONCLUSIVE**, not PASS or FAIL, per the pre-registration. All numbers below
are reported for transparency, not as a basis for deployment.

## 2. Mechanics as executed (verbatim intent from spec)

- **Broadcast windows:** Fed air time = median of the clustered
  `occurrence_datetime` timestamps across the 26JUN event's markets (2026-06-17
  ~19:36 UTC), excluding four markets whose `occurrence_datetime` equalled the
  market's `expiration_time` (a "word never said" placeholder sentinel, not a real
  occurrence). Hannity air time = 9:00pm America/New_York on the broadcast date
  (2026-05-19, 2026-05-21), hardcoded per spec, converted to UTC.
- **Window:** trade prints filtered to `(air-2h, air+3h]` per market.
- **Simulated quote:** reference price seeded from the last print at/before
  `air-2h` (or the first in-window print if none exists before the window).
  Quote re-centers to `last_print ± k` after every print. A later print strictly
  through the bid/ask counts as a fill at our limit price, size capped at the
  printed trade's size.
- **k grid:** {5, 8, 12} cents, chosen per series on the fit set only by maximizing
  mean net markout; **k=12c won for both series** on the (thin) fit data.
- **Fee verification (mandatory):** `GET /series/KXFEDMENTION` and
  `/series/KXHANNITYMENTION` both report `fee_type: "quadratic"`,
  `fee_multiplier: 1` — i.e., the **standard nonzero** Kalshi fee schedule, with no
  indication of a maker exemption for this series. Per the spec's own
  instruction ("include if nonzero"), the house EV formula
  `ceil(7*p*(1-p))/100` per contract was applied to every simulated maker fill,
  not just taker fills. This is the more conservative and more defensible choice.
- **Fit/validation split:** chronological, first 40% of events = fit, per series
  (matching Spec 1's convention). KXHANNITYMENTION: fit = 26MAY19, validation =
  26MAY21. KXFEDMENTION: only 1 accessible event exists, so it cannot be split
  without lookahead — it is fit-only/descriptive and contributes **zero** rows to
  the formal validation statistic.
- **Markout sign convention:** `net_markout` is the passive quoter's own signed
  per-contract PnL after fees (settlement − fill price for a resting buy fill;
  fill price − settlement for a resting sell fill), so a positive number always
  means "good for us," consistent with the adverse-selection pass/fail logic.

## 3. Headline numbers

### Pre-registered validation set (KXHANNITYMENTION-26MAY21 only — 1 event-day)

| metric | value |
|---|---|
| n fills | 115 |
| event-days | 1 (need ≥10) |
| win rate ("not on losing side") | 51.3% |
| Wilson 95% CI | [42.3%, 60.2%] |
| mean EV/contract, net of fee (markout) | **−2.29¢** |
| mean EV/contract, gross of fee | −0.36¢ |
| day-clustered t-stat | not computable — only 1 cluster |
| pre-air (≤24h) adverse-selection check | **FAIL** — mean net markout on the 14 pre-air fills = **−10.4¢** (must be ≥0) |
| >70%-losing-side check | pass — 48.7% of fills land on the losing side |

### All accessible data pooled (fit+validation, 756 fills, 3 event-days — exploratory only, not the pre-registered gate)

| metric | value |
|---|---|
| n fills | 756 |
| event-days | 3 |
| win rate | 48.4% |
| Wilson 95% CI | [44.9%, 52.0%] |
| mean EV/contract, net of fee | **−4.57¢** |
| mean EV/contract, gross of fee | −2.74¢ |
| day-clustered t-stat (3 clusters, exploratory) | t = −2.98, one-sided p = 0.95 (wrong sign — mean is negative, not positive) |
| pre-air (≤24h) adverse-selection check | **FAIL** — mean net markout on 567 pre-air fills = **−4.79¢** |
| >70%-losing-side check | pass — 51.6% |

By series: KXFEDMENTION alone (546 fills, 1 day) mean net markout −4.46¢, win
rate 48.4%. KXHANNITYMENTION alone (210 fills, 2 days) mean net markout −4.84¢,
win rate 48.6%.

**Pass bar comparison:** required mean net markout > +3¢/contract with clustered
one-sided p<0.005 (Bonferroni×10) and both adverse-selection sub-checks passing.
Actual: negative markout in every cut, pre-air adverse-selection sub-check fails
in every cut. Even ignoring the min-n gate, this would be a clean **FAIL**, not a
marginal miss.

## 4. Realistic capacity

**$0/month.** Two independent reasons: (1) the pre-registered minimum-n bar for
statistical validity is not met (3 accessible event-days vs. required 10), so no
claim of a real edge can be made; (2) even on the descriptive full-sample numbers,
mean net-of-fee markout is negative in every cut examined (validation, pooled,
and both series individually), and the core adverse-selection sub-check
(pre-air markout ≥ 0) fails everywhere it could be computed. A passive
"quote-around-last-print" maker strategy on these two series currently loses
money net of fees on the trade prints actually observed. No paper-only sleeve is
recommended from this spec.

## 5. What most worries me

The pre-air adverse-selection check failing hard (−10.4¢ in validation, −4.8¢
pooled, worse than the "earlier" bucket in every single cut) is the real signal
here, more than the missing data. It means: in the hours right before the
broadcast airs, prints on these mention markets are systematically moving in the
direction of the eventual settlement *before* our passive quote gets to
re-center — i.e., someone (or some combination of momentum + a few informed
traders) is pushing price toward the true outcome faster than a 12¢-wide,
last-print-following resting quote can track. Getting run over by that in the
pre-air window is exactly the informed-counterparty risk the pre-registration was
built to catch, and it caught it. Combined with the fact that Kalshi's own public
API won't even let a Fed-mention researcher see 11 of 12 historical events (so
this conclusion itself rests on one Fed press conference and two Hannity
episodes), I would treat "off-air passive quoting on mention markets" as
functionally dead rather than merely unproven — a bigger sample would need to
overturn a negative point estimate with a *failed* adverse-selection check, which
is a much higher bar than just accumulating more event-days.

## 6. Files

- `backtest.py` — runnable, reproduces `results.json` from cached trade/market
  JSON (cache directory has been deleted per instructions; re-running requires
  re-fetching via `fetch_trades.py` against the live Kalshi public API).
- `results.json` — full machine-readable output (all summaries, adverse-selection
  breakdowns, chosen k per series, fit/validation event lists).
- `fetch_trades.py` — the harvester used to pull full uncapped `/trades` per
  market with jittered backoff on errors/429s.
