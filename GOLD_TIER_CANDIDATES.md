# Five candidate strategies approaching "arbitrage gold tier"
### (PF >3, Sharpe >3, win ~100%, maxDD <3% — any market, retail-accessible, evidence-based)

Researched 2026-06-12 across ~14 web-research streams (academic + practitioner, adversarially
cross-checked) + our own validated tape/live data. Honest headline first: **nothing retail-accessible
FULLY meets the gold tier at meaningful absolute returns** — true gold-tier risk-shape always trades
against capacity or absolute yield. These are the five best approximations, ranked by
(gold-proximity × actionability for us), each with its killer risk stated.

---
## 1. CROSS-VENUE PREDICTION-MARKET ARB on rule-identical events (Kalshi ↔ Polymarket-US)
**The trade:** same OBJECTIVE event on both venues (CPI bucket, Fed target range, BTC daily close);
when YES(A) + NO(B) < $1 − fees, buy both → locked $1 at resolution.
**Evidence:** arXiv 2508.03474: ~$40M realized arb on Polymarket in 12 months, and **only ~1% of
detected opportunities were exploited** (capital/speed-bound — small actors fit in the residual);
QuantPedia: 41% of 17k conditions showed YES+NO dislocations; documented 3–8¢ Kalshi-vs-CME Fed gaps.
Durable retail slice = thin markets (<$100k cumulative volume) + first ~48h after listing, where
1–5% gaps persist minutes-to-days (liquid-event windows have compressed to ~2.7s — bots own those).
**The killer risk (DOCUMENTED):** settlement-criteria divergence — the 2024 government-shutdown
market resolved **YES on Polymarket, NO on Kalshi**: total loss on both legs. Also ~4% round-trip
taker fees and capital lockup to resolution.
**Vs gold:** on the rule-IDENTICAL subset (numeric prints: CPI value, Fed range, BTC close), the
mismatch risk ≈ 0 → win ~100%, DD ~0, PF very high; capacity small ($200–600/mo at $10k).
**Why us:** both APIs already built; Polymarket US is now CFTC-regulated (QCX) with USD rails.
**Verdict: GOLD-PLAUSIBLE on the rule-identical subset, manually verified, patiently executed.
NEAR as a broad systematic strategy (mismatch tail breaks the Sharpe).** Difficulty 3/5.

## 2. SPX/XSP BOX-SPREAD LENDING — the textbook gold-tier (with a scale catch)
**The trade:** long box on European-style SPX/XSP = synthetic T-bill: payoff fixed at entry,
win ~100%, DD ~0, PF/Sharpe formally huge. NY Fed documents boxes pricing 10–30bp above T-bills;
after-tax the Sec-1256 treatment adds ~30–60bp vs ordinary-income bill funds.
**The scale catch (research-corrected):** 4-leg friction means DIY boxes only beat T-bills above
~$20k/lot; at $1–10k DIY is T-bill MINUS 10–30bp. Under $50k the right implementation is simply the
**BOXX ETF** (2024: 5.16% vs BIL 5.19% pre-tax; wins after tax). NEVER American-style (SPY/QQQ) —
early assignment is a documented account-killer.
**Verdict: MEETS the tier on every ratio metric — and is therefore the honest benchmark: a "gold
tier strategy" that pays ~T-bill+ε. Use as capital-parking baseline; any active strategy must beat
it after labor.** Difficulty 1/5 (buy BOXX) / 3/5 (DIY at scale).

## 3. CRYPTO PERP FUNDING-RATE HARVESTING (delta-neutral carry) — newly US-legal, scalable
**The trade:** long spot + short perp, collect funding. As of May 2026 US-legal venues exist:
Coinbase perps (CFTC no-action), **Kalshi BTCPERP** (first US DCM perp — operationally adjacent to
us), Bitnomial/Kraken.
**Evidence (adversarially checked):** backtest Sharpes of 4–6.5 are 2020-21 regime artifacts;
realistic LIVE Sharpe **0.5–2.0**, net **5–12% APY** in the current compressed regime; normal DD <2%
BUT the documented tail is **15–20%** via perp-leg liquidation in fast rallies (BIS WP1087) and
funding flips. Practical floor $10k (fees eat carry below).
**Verdict: NEAR — best scalable carry; misses Sharpe>3 and the DD tail. Re-check quarterly for
regime steepening; revisit when bankroll ≥$10k.** Difficulty 3/5.

## 4. SPORTS ARBITRAGE: Kalshi (exchange, can't ban you) vs sportsbooks/Polymarket
**The trade:** classic cross-book de-vig arb with Kalshi as the unbannable leg. Kalshi sports is now
80–89% of platform volume — deep books on major events.
**Evidence (adversarially verified):** structural vig gap ≈ **3.77%** gross (Kalshi ~0.85% effective
cost vs ~4.6% sportsbook vig); net edges 1–2% above the ~5–6% gross-spread threshold; executed-arb
win rate **95–98%** (the one family whose WIN RATE is genuinely gold-tier); realistic **$250–1,000/mo
at $5–20k manual** (the only estimate with a credible evidence chain — the "12–20%/mo" social-media
figures are promotional), $1–3k/mo semi-automated.
**Killer risks:** (1) sportsbooks limit winning accounts within ~3–6 months — the book leg decays;
(2) Kalshi's retail fee tier (sports series charge fees, unlike our crypto15m) cuts PF to ~1.2–1.5;
(3) regulatory: the STOP Corrupt Bets Act + state bans (Minnesota) are live existential threats to
the category in 2026.
**Verdict: NEAR — gold win-rate, sub-gold PF/Sharpe after fees, plus decaying access and regulatory
tail.** Difficulty 3/5 manual, 4/5 sustained.

## 5. POLYMARKET LIQUIDITY-REWARDS MARKET MAKING (paid to quote) — best infra fit
**The trade:** Polymarket pays makers daily USDC rewards + 20–25% of taker fees (2026 program);
$5–10k daily pools on top markets, $50–300 on niche ones (best competition ratio). Two income
streams (spread + rebate) — structurally our maker-box skillset ported to a venue that PAYS makers.
**Evidence:** practitioner-documented $150–600/mo gross quoting 3–5 markets on $1–10k. The maker
niche is under-researched academically (no published maker Sharpe — itself a signal), and makers
escape the speed race that killed every taker family above.
**Killer risks:** adverse selection on news-driven fills ("paid to lose money slowly" in hard-news
markets — pick markets with continuous public state like crypto, not announcement-driven ones);
**rewards availability on the US-regulated venue is UNCONFIRMED — verify before building.**
**Verdict: NEAR — Sharpe ~0.5–1.5 realistic, DD >3% on news days; but the best $/build-hour for us
(adapt existing box code) IF the US venue carries the program.** Difficulty 2/5.

---
## Evaluated and DEMOTED (so we don't relitigate) — with the evidence conflicts stated
- **Kalshi WEATHER model edge:** conflicting evidence, resolved honestly: a structural bias exists
  (market overprices temperature uncertainty ~1.27×; best public backtest Sharpe 4.9 — UNAUDITED) but
  execution is speed-gated: bots act within seconds of each NWS model cycle; documented retail
  postmortem went **0-for-32**; sub-15¢ contracts carry a 7–20% fee tax. NEAR only with sub-minute
  automated NWS-cycle infra and ~$50k capacity ceiling; NO as typically executed. Park it.
- **CPI/macro NOWCASTING:** a Fed working paper finds Kalshi CPI markets already track consensus
  well; Cleveland-Fed nowcast is public and priced in within minutes; ~25 events/yr caps the sample
  and one wrong-way print erases a year's edge. The flagged 30–40¢ "mispricing" was a single
  unresolved case study. NO as a systematic strategy; harmless to paper-test at $50.
- **Intra-venue Dutch books:** competed to sub-second; our own live scan found zero on liquid
  markets. NO at retail.
- **New-market sniping:** prop firms (DRW etc.) now hunt listings with AI agents; edge is
  volume-conditional, not time-gated, and the counterparty is them. NO systematically.
- **Stablecoin/DEX-CEX arb:** MEV bots take >90% of gross; infra to compete = $200–3,800/mo. NO.
- **CME micro-BTC basis:** real in spikes but $12–15k/pair floor + margin-call tail; dominated by #3.
- **Wide-box hunting & multi-asset certainty boxes on Kalshi crypto:** our own backtests — NO
  (survivorship / OOS-negative). See RISKFREE_PLAYS.md.

## The meta-finding (consistent across every stream)
Speed-race taker strategies are dead at retail (windows: 12.3s → 2.7s in two years; sub-100ms bots
take 73%). What survives for small actors: (a) **maker positioning** (unbenchmarked academically,
structurally exempt from the race — our existing box bot is already the right species), (b)
**rule-identical cross-venue locks executed patiently**, (c) **regulated-wrapper yield** (boxes,
funding). Sequencing: build #1's matcher-scanner now (both APIs exist); verify #5's US rewards
program with one API call; keep #2 as the parking baseline; revisit #3 at $10k bankroll; treat #4
opportunistically only.
