# Fact-Check Log — "Forty-Two Kills"

Method: every numeric claim, verdict label, date, and mechanism description in `00_front.md`,
`01_intro_methodology.md`, `02_catalog_1_21.md`, `03_catalog_22_42.md`, and `04_lessons_outro.md`
was traced to its source document in the corpus (`venue_expansion/ref/RESEARCH_LEDGER.md`,
`ref/pmkt_*.md`, `ref/wx_new_capacity_scan.md`, `PAPER_TRADER_AUDIT.md`, `DATA_SOURCES.md`,
`FINDINGS.md`, `S3_FORECASTEX.md`, `REOPENABLE.md`, `REOPEN_FUNNEL.md`, `MAKER_VIABILITY.md`,
`MM2_REGISTRATION.md`, `ENGINEERING_STACK.md`, `STRUCTURAL_REVENUE.md`). All 42 catalog entries
(#1–#42) were checked cell-by-cell against `RESEARCH_LEDGER.md`'s graveyard table and, for
#38–#42, against their individual source docs. Cross-part references (Part 4's lessons citing
back to specific case numbers) were checked against the catalog entries they cite.

## Corrections made (factual errors, fixed in place)

1. **`01_intro_methodology.md`, §2 (venues/toolkit).** Was: "its long tail of 297-series climate
   catalog." No corpus document contains "297." `wx_new_capacity_scan.md` (2026-07-19) measures
   Kalshi's Climate-and-Weather category at **289** series; `FINDINGS.md` (2026-07-23) reports it
   grew to **290** by the time of a later recheck. Fixed to "roughly 289 climate-and-weather
   series."

2. **`01_intro_methodology.md`, §3 "Frozen bars that never move."** Was: "because two of the five
   macro-release families included in the original registration turned out not to exist yet in
   the fit window." `REOPEN_FUNNEL.md`'s M1 section registers **six** macro-surprise family keys
   (CPI, EMPLOYMENT, GDP, PCE, JOBLESS, ISM), not five, and states the FIT window "predates half
   the registered market families entirely," naming KXJOBLESSCLAIMS (starts 2025-06-12) and
   KXISMPMI (starts 2025-04-01) as the concrete examples — i.e., three of six, not two of five.
   (Part 3's own #40 entry already gets this right, quoting "predates half the registered market
   families entirely" correctly — this was a Part 1 paraphrase error, not a corpus error, and it
   contradicted Part 3 internally.) Fixed to "the fit window predates half of the six registered
   macro-release families entirely (jobless claims and ISM PMI markets among them, both of which
   simply hadn't launched yet)."

## Hedges added (claims accurate but source demands a caveat not originally carried over)

3. **`03_catalog_22_42.md`, #39 (U1 executable-price screen).** The entry reported "946
   hypotheses" and "19 survivors" without noting that only 143 of the 946 unit-sides actually
   cleared the pre-registered minimum-sample floor and produced a computable statistic.
   `REOPEN_FUNNEL.md` flags this explicitly as a coverage figure "the builder's summary omitted"
   and says outright "it should be reported as such." Added a sentence disclosing the 143/946
   (15%) effective coverage, noting it's conservative and doesn't move any bar.

4. **`01_intro_methodology.md`, §2.** The description of Polymarket's weather-ladder work ("across
   51 cities") read as though it had been tested to a verdict alongside everything else described
   in that paragraph. The corpus shows this thread never reached a kill: `pmkt_final_verdict.md`
   returned STILL-BLOCKED (coverage-limited, not disproven), and `FINDINGS.md` later reports a
   PASS on signal coverage for Chicago specifically on its true 1-minute feed — but the EV
   question was left explicitly unresolved ("the sign of that EV is unknown"), with the decisive
   follow-up spec (S1) never run. This is why the weather-ladder study correctly has no numbered
   catalog entry — it isn't a kill, dead or alive. Reworded to state plainly that this line of
   work "stayed unresolved rather than closing."

## Numbering-consistency note (reviewed, no manuscript change needed)

The corpus itself contains an unresolved numbering collision: `S3_FORECASTEX.md` (dated
2026-07-29) labels itself graveyard row **#38** assuming a prior total of 37; `REOPEN_FUNNEL.md`
(also dated 2026-07-29) independently labels its four new specs U1/M1/J1/D1 as **#38–#41**,
also assuming a prior total of 37 and with no apparent awareness of `S3_FORECASTEX.md`;
`MAKER_VIABILITY.md` (2026-07-30) then labels itself **#42** assuming a prior total of 41. These
three documents cannot all be literally true at once (37 + S3 + 4 reopen specs + MAKER_VIABILITY
= 43 distinguishable studies, not 42) — this is a genuine artifact of parallel, uncoordinated
research branches in the underlying repo, not something a fact-checker can resolve by picking one
document as "correct." The manuscript's own resolution — S3 = #38, U1 = #39, {M1, J1} bundled
under #40, D1 = #41, MAKER_VIABILITY = #42 — is internally consistent throughout all four parts
(no number 1–42 is skipped, duplicated, or contradicted between Part 2, Part 3, and the citations
back to specific case numbers in Part 4), and every underlying figure attached to each of those
labels was verified correct against its true source document regardless of which integer it's
filed under. No changes made; flagging for the record since the corpus itself disagrees with
itself here.

## Spot-checks that came back clean (representative, not exhaustive)

- Scoreboard figures ($4,000/mo target; $146–149/mo live-observed; $1,173+/mo optimistic bound)
  — match `RESEARCH_LEDGER.md` §1 exactly, including the "+"-marked hedge on the optimistic
  number, carried through consistently in Parts 1 and 4.
- Weather mechanical lock (+1.1¢/ct, ~99.6% win rate backtest; $10 canary; 0 fills / 189
  near-misses in ~4 days, all `ask>98`) — matches `RESEARCH_LEDGER.md` §1–2 exactly in both Part 1
  and Part 4.
- Worked example (forecast sleeve, four-arm EV/t table, 37/261 = 14.2% mis-scored trades, both
  bugs) — reconciles to the cent and to two decimal places of t against `PAPER_TRADER_AUDIT.md`.
- Engineering-stack numbers (255–354ms cold subprocess vs 0.37–0.68ms warm; ~500–650× tax;
  500–655ms cold reconnect; 1.0–2.0ms cross-AZ RTT; 1.4–2.7ms compute+wire floor; $5–20/mo VPS)
  — match `ENGINEERING_STACK.md` exactly, consistent between Part 1 and Part 4.
- Data-source register (N_TRADE_SHARDS=9 hiding 7 of 16 shards, ~44% / ~70M of ~160M trades
  invisible) — matches `DATA_SOURCES.md` exactly.
- ForecastEx kill (#38): 8,646 locks, 190 false locks / 2.198% / Wilson UB 2.559%; cushion table
  (2°F 183/7,615; 3°F 10/481; 4°F 2/245; ≥5°F zero); fill≥98c EV −0.571¢, t=−5.66, UB −0.357¢;
  headline +9.20¢/t=15.42 population-mixing explanation; KLGA 2026-06-12 worked case — all match
  `S3_FORECASTEX.md` digit-for-digit.
- Reopen funnel (#39–#41): 154,505,005 rows / 17,006,887 qualifying; paired-complement table
  (KXHIGHNY|B −6.36¢/−2.57¢ = −8.93¢); extinct-series last-print dates (INXD 2024-12-31, U3
  2024-11-01); KXHIGHNY|B/yes validation −4.262¢, t=−4.626; M1's 31-vs-40 ceiling and "no
  opposite-side print" mechanism; J1's 1-of-7 Thursdays; D1's 5-vs-17 / 12-vs-84 and 83%/93%
  no-print rates — all match `REOPEN_FUNNEL.md` and `REOPENABLE.md`'s correction header exactly.
- Maker viability (#42): +0.76 to +1.25¢/ct pool, U1-reconciled to 4dp; 0/20 cells stable across
  temporal halves; BTC good half = H2, ETH = H1; listing-window EV −0.99¢ BTC / −8.81¢ ETH — match
  `MAKER_VIABILITY.md` and `MM2_REGISTRATION.md` exactly.
- Structural revenue (Part 4 "What survived"): ForecastEx coupon floor 1.565%; Kalshi APY −$5 to
  −$10/mo vs T-bill at $10k; LIP program $10–$1,000/day, 2026-09-01 deadline; "hundreds per month,
  not thousands" — verbatim match to `STRUCTURAL_REVENUE.md`.
- All 21 Part 2 entries (#1–#21) and the remaining Part 3 entries (#22–#37) checked cell-by-cell
  against `RESEARCH_LEDGER.md`'s graveyard table; every EV figure, t-stat, sample size, floor, and
  verdict label matches exactly, including secondary details (e.g. #35's DAL@PHI 2025-09-04
  devigged-Vegas spot check, #36's independent-rebuild −9.5¢/ct figure, #37's Brier scores).
- Privacy check: no account balances beyond corpus-stated figures (the $10 canary and the
  ≤$1,000 LIP-pilot recommendation are both stated directly in the corpus as programmatic facts,
  not disclosed as current live-position detail); no personal names found; every reference uses
  "the operator"; no API keys, credentials, or secrets present anywhere in the four parts.

## Counts

- Claims checked: ~210 (every numbered kill's key figures, both scoreboard numbers, all
  engineering/data-source/structural-revenue figures, and every Part 4 lesson's back-citation)
- Corrections: 2
- Hedges added: 2
