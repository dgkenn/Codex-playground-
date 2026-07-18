# Kalshi corporate-earnings beat-rate mispricing -- OOS test
_Generated 2026-07-18T15:36:24.238529+00:00 | venue: Kalshi | data: public trade-api v2 (no auth)._
## TL;DR verdict
**The literal hypothesis is NOT instrumentable on Kalshi.** Kalshi has **zero** binary "Will <company> beat consensus EPS?" markets in the settled universe. Its corporate products are **operational-KPI threshold ladders** ("Will <co> report ABOVE X deliveries/customers/transactions in Q?"). 0 EPS markets; 7 "revenue"-qualified markets.
We tested the closest deployable analog -- systematic **upside/beat bias** in those ladders vs **executable pre-close** prices, **net of Kalshi fees**, clustered at the event level.
- Sample: **201 settled ladder markets** across **21 distinct events** (company-quarter-metric), 20 companies, 9 settlement weeks.
- Realized YES ("beat") rate = **0.592** vs mean priced mid **0.601** (mean executable yes_ask 0.619).
- Median-strike beat test (metric above the ~50c strike): beat rate **0.286** over **21 events**, t vs 0.5 = **-2.12**.
- Best net-of-fee strategy: **buy NO, all liquid strikes** -> NET **-0.0214/ct**, t_event **0.392**.
- **VERDICT: NO fee-surviving edge (NULL).** n is far too small (21 events) for a deployable, statistically credible conclusion. Treat as **NULL / not deployable**.

## Fee model
Kalshi trading fee (quadratic, fee_multiplier=1 for these series): `fee = ceil_to_cent(0.07 * C * p * (1-p))` per order, charged on the taker at entry. Per-contract we charge `ceil(100*0.07*p*(1-p))/100` at the executable entry price. Continuous `0.07*p*(1-p)` reported as a lower bound. At p=0.5 that is 1.75c/ct (2c after ceil) EACH WAY -- a large hurdle for any near-50/50 bet.

## Base-rate / calibration
| entry mid band | n | mean mid | realized YES |
|---|---|---|---|
| [0.00,0.10) | 56 | 0.044 | 0.000 |
| [0.10,0.25) | 15 | 0.175 | 0.133 |
| [0.25,0.40) | 7 | 0.322 | 0.286 |
| [0.40,0.60) | 9 | 0.514 | 0.556 |
| [0.60,0.75) | 7 | 0.684 | 0.714 |
| [0.75,0.90) | 9 | 0.829 | 0.778 |
| [0.90,1.01) | 98 | 0.985 | 1.000 |

If companies systematically 'beat', realized should exceed mean mid in the mid/low bands. Read the gap vs the fee hurdle (~2c/side at 50c). **Observed: the ladders are essentially well-calibrated** -- each mid band maps cleanly to its realized rate, and overall realized YES (0.592) ~ priced mid (0.601). No systematic under-pricing of the upside. This matches the strong prior that Kalshi markets are well-calibrated.

> Note on the median-strike beat test: it looks negative (rate 0.286, t -2.12), but it is a NOISY proxy -- many KPI ladders are coarse/thin and have NO strike near 50c (nearest mids land at 0.02, 0.04, 0.76, ...), so the 'median strike' is frequently a mispicked deep strike rather than the true central expectation. The calibration table above is the cleaner, unbiased read and shows no beat edge.

## Strategies tested (net of fees, executable entry, event-clustered t)
- **S1_buyYES_all**   buy YES, all liquid strikes: n=201 (ev=21, wk=9) | gross=-0.0272 | NET/ct=-0.0348 | t_event=-2.761 t_week=-2.432 | win=0.174
- **S2_buyYES_midband**   buy YES, mid mid in [.35,.65]: n=12 (ev=7, wk=5) | gross=-0.0533 | NET/ct=-0.0733 | t_event=-2.363 t_week=-2.328 | win=0.5
- **S3_buyYES_liqband**   buy YES, mid in [.10,.90]: n=48 (ev=17, wk=9) | gross=-0.0442 | NET/ct=-0.0617 | t_event=-2.069 t_week=-1.73 | win=0.458
- **S4_buyYES_lowband**   buy YES, mid in [.10,.35] (upside longshot): n=21 (ev=15, wk=9) | gross=-0.0505 | NET/ct=-0.0686 | t_event=-0.819 t_week=-0.598 | win=0.19
- **S5_buyNO_all**   buy NO, all liquid strikes: n=201 (ev=21, wk=9) | gross=-0.0097 | NET/ct=-0.0214 | t_event=0.392 t_week=0.752 | win=0.408
- **S6_buyNO_midband**   buy NO, mid in [.35,.65]: n=12 (ev=7, wk=5) | gross=-0.0125 | NET/ct=-0.0325 | t_event=1.668 t_week=1.712 | win=0.5

Multiple-testing looks: **14** (6 PnL strategies + 7 calibration bins + 1 median-strike test). No multiplicity correction would survive at this n.

## Capacity, concentration, correlation
- Median entry bid/ask spread: **0.020** (wide -> taker cost real). Mean entry taken **16.47h** before close.
- Company concentration (top): [('Tesla Inc.', 36), ('Rivian Automotive Inc.', 18), ('Boeing Company (The)', 14), ('United Airlines Holdings Inc.', 13), ('Vail Resorts Inc.', 12), ('CAVA Group Inc.', 11)]
- Series concentration (top): [('KXTSLA', 36), ('KXRIVN', 18), ('KXBA', 14), ('KXUAL', 13), ('KXMTN', 12), ('KXCAVA', 11)]
- **Capacity:** Kalshi KPI markets are thin and episodic (a handful of names per earnings week, low OI). Even if an edge existed, deployable size is tiny.
- **Correlation with crypto edge:** earnings/KPI outcomes are idiosyncratic, firm-specific events -> effectively **uncorrelated** with the BTC/ETH crypto microstructure edge. (Diversifying in principle, but see verdict.)

## Caveats / discipline
- Only SETTLED markets (survivorship is fine here, but noted). Sample dominated by a few names (Tesla deliveries, Rivian, Vail, Boeing).
- Entry is the last valid two-sided candle strictly before close (pre-announcement); terminal last_price (pinned 0.01/0.99) is deliberately NOT used.
- Ladder strikes within an event are highly correlated -> event-clustered t is the honest unit. With ~22 events, power is near zero.
- The literal EPS-beat edge from the Polymarket tool does not port: the Kalshi instrument (consensus-EPS binary) does not exist here.
