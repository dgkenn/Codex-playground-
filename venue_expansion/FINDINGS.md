# VENUE EXPANSION — RECOVERED FINDINGS (workflow wf_328b553a-c8f)

The hunt workflow launched 2026-07-23 died mid-run when the container restarted (last agent
activity 2026-07-23T23:49Z). **11 of its agents completed**; their results were recovered from
`journal.jsonl` into `out/workflow_recovered.txt`, and every artifact they wrote survived on disk.
Two registered specs (S1, S3) had their scripts written but never ran.

**Bottom line: still nothing deployable — but the map moved in three real ways, and one genuinely
new US-legal venue was found.**

---

## 1. Track A — Polymarket Chicago on true 1-minute ASOS: **PASS, adversarially upheld**

The pre-registered GO-check from `ref/pmkt_final_verdict.md` §5.1, executed and then attacked by a
Fable verifier that returned `upheld: true, severity: minor`.

| | result | bar |
|---|---:|---|
| Winner-bracket coverage | **64.2%** (43/67 days) | ≥55% ✅ |
| Wilson LB | **52.2%** | must exceed 40.9% hourly baseline ✅ |
| Deployed-rule false locks | **0/344** (Wilson upper 1.10%) | 0 ✅ |
| n usable days | 67 | ≥60 ✅ |

What makes this credible rather than another false positive:
- **Harness fidelity verified by diff** — every shared function against `pmkt_final_verdict.py`;
  only sleep durations changed. The lock rule was extracted byte-identical from `kwx_runner.py@bd90504`.
- **The hourly baseline was reproduced exactly** (usable=22, never_entered=13, coverage=40.9%)
  before the primary run.
- **The verifier ran its own paired test and it strengthened the result**: hourly coverage on the
  *same 67 days* is 28.4%, with 24 discordant days favouring 1-min and 0 against (McNemar p≈6e-8).
  The 64.2%-vs-40.9% headline is therefore **conservative**.
- **Settlement basis is sound.** Winners come from Polymarket's own resolved `outcomePrices == 1.0`
  — the venue's official outcome, not a self-computed bracket. This is exactly the check that killed
  the Kalshi forecast sleeve (`PAPER_TRADER_AUDIT.md`), and Track A passes it by construction.

**So the coverage blocker that produced the STILL-BLOCKED verdict is genuinely lifted for Chicago.**
That is a real state change, not a reinterpretation.

### The catch — the EV number is not usable in either direction

Track A's non-gating EV is **−19.41c/ct**, which looks damning. It isn't trustworthy:
`tracka_results.json` shows `live_spreads_c.chicago = 20.0c`, so every priced fire carries a **+10c
half-spread penalty taken from a single run-time book snapshot** — against 0.2c measured for the
same city in the prior study, 50–100× tighter. Layered on top is the item-2b reweighting, which
applies an 86.1% base rate instead of per-fire accounting. **The sign of that EV is unknown.**

Also disclosed: IEM's 1-minute archive has a genuine 14-day hole (2026-02-09..22) for KORD, verified
by live re-pull to be an archive gap rather than a cached failure. Backtest-feed only.

---

## 2. Feed hunts — and a correction to the original verdict

| City | Station | Verdict | Feed |
|---|---|---|---|
| Tokyo | RJTT / JMA Haneda | **VIABLE** | JMA 10-min AMeDAS, **144 rows/day**, verified 365 days back |
| London | EGLC | **VIABLE** | IEM 30-min, 48 rows/day, verified 164 days back |
| Paris | LFPB | **VIABLE** | IEM 30-min, 48 rows/day; Météo-France's own 6-min feed is precipitation-only |
| São Paulo | SBGR | **DEAD** | Genuinely hourly-only; no sub-hourly exists at that airport, free or paid |

**Correction worth noting:** `pmkt_final_verdict.py` queried IEM with `report_type=3` only, which
returns 24 obs/day. The correct call is `report_type=3&report_type=4`, which returns **48**. The
original STILL-BLOCKED verdict was computed on half the cadence actually available for London and
Paris. Both feed agents found this independently.

---

## 3. Spec S2 — Tokyo on the 10-minute feed: **FAIL** (clean negative)

Coverage rose **30.8% → 43.9%** (Wilson LB 34.8%, decisively above baseline) but missed the
pre-registered 50% floor, so bar (a) fails on its first conjunct. Bar (b) passed cleanly:
**0/755 false locks** (Wilson upper 0.60%), which doubles as an AMeDAS-vs-Wunderground
settlement-basis test — no basis problem. The hourly Tokyo baseline was reproduced exactly first.

Read: finer cadence helps but does not by itself clear the bar outside Chicago. Chicago's true
1-minute feed is 6× finer than Tokyo's best available, and that difference appears to be decisive.

---

## 4. ForecastEx — the most usable new lead, and a fee correction

**ForecastEx** (IBKR's CFTC-regulated Forecast Contract DCM) lists **Daily Temperature** contracts.
Verified live by me on 2026-07-27, not just by the agent:

- **46 daily temperature products** (`UH*` highs, `UL*` lows) with real same-day volume —
  Atlanta 7,629 pairs, Charlotte 4,975, Boston 4,296 on 2026-07-26.
- **Free, unauthenticated, millisecond-timestamped public data lake** —
  `forecastex-public-data.s3.amazonaws.com` (daily summaries, prices, pairs). Live and fresh.
- **Uncapped one-sided threshold ladders** — the *native* shape of the one mechanism this program
  has actually confirmed (Kalshi mechanical lock), not the bracket shape that makes Polymarket hard.
- **Settles on Weather Underground**, the same source as Polymarket — and the repo already has WU
  basis measurements for US cities.
- **US-legal**, which is the constraint that caps everything on global Polymarket.

### Correcting the recovered claim about the fee

The venue-sweep agent flagged the flat **$0.01/contract** fee as possibly fatal, reasoning it
"does not shrink near p→1" the way a quadratic fee does. **That reasoning is wrong in the band that
matters.** Kalshi's fee is `ceil(7·p(1−p))` *cents* — the ceiling means it never goes below 1 cent:

| entry | Kalshi fee | ForecastEx fee |
|---|---|---|
| 98c | `ceil(0.137)` = **1c** | **1c** |
| 99c | `ceil(0.069)` = **1c** | **1c** |
| 95c | `ceil(0.333)` = **1c** | **1c** |

**In the 95–99c band where the mechanical lock operates, the two venues charge identically.** The
fee is a wash, not a blocker. Verified from the fee schedule PDF: `$0.01 per contract`, charged at
execution to both sides, **independent of resolution or settlement** — so a hold-to-settlement lock
pays it once, exactly like Kalshi.

Small tailwind on top: ForecastEx contracts earn a **monthly incentive coupon on daily settlement
value** — positive carry on held collateral that Kalshi does not pay.

**Not yet studied:** spec S3 (false-lock rate + flat-fee EV on the venue's own trade tape) was
written (`spec_S3.py`) but never ran. There is no false-lock rate and no EV for this venue yet.
Nothing here is a green light — it is the best-shaped unexplored candidate found so far.

---

## 5. Other venue results

- **Polymarket US (QCX): does NOT list weather markets** as of 2026-07-23 — sports-first launch,
  weather unconfirmed in their own dev docs, API application-gated. This resolves `GROUNDING.md`'s
  highest-value open question with a **no**, and it is why ForecastEx matters.
- **Global/on-chain venues: DEAD.** 11–12 venues queried directly through their own catalog
  endpoints (Limitless, Azuro, Overtime, SX Bet, Drift, Myriad, TrueO, Zeitgeist, Manifold, Betfair,
  Smarkets, Matchbook) — none lists a weather/mechanical-lock product on a readable book above
  $1k/day. Clean negative, not a coverage gap.
- **Kalshi: no new capacity** since the 2026-07-19 catalog scan (289→290 climate series, all
  pre-dating it).
- **`pmxt.dev` found and sample-verified** — a free, credential-free, CC-BY-4.0 **historical
  Polymarket order-book archive** (one parquet per UTC hour, coverage from 2026-04-13T19Z, confirmed
  live). This closes GO-path #4 from `pmkt_final_verdict.md`, which had recorded "no public endpoint
  found". It makes measured-ask EV answerable for the first time — but only from 2026-04-13 onward,
  so it does not retroactively cover the earlier half of the original backtest window.

---

## 6. What this leaves open

Two decisive experiments, both now specified and unblocked, neither run:

- **S1 — Polymarket whitelist EV at measured asks** (`spec_S1.py`, pmxt.dev archive). Replaces the
  proxy that makes Track A's −19.41c/ct meaningless. Pre-registered symmetric kill: if the one-sided
  98.33% upper bound is below +0.2c/ct, the sleeve is declared dead. Either sign is decisive.
  *Caveat: even a PASS is not deployable for a US person — global Polymarket remains geo-blocked.*
- **S3 — ForecastEx false-lock rate + flat-fee EV** (`spec_S3.py`, venue's own tape). The only
  candidate that is both structurally right and legally reachable.

**Recommended order: S3 first.** S1 answers a question about a venue the operator probably cannot
trade; S3 answers it about one they can, on the native shape of the only mechanism this program has
ever confirmed, using a free public tape.
