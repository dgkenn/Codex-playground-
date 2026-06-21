# Sports-exchange MAKER side: can a patient retail liquidity provider harvest the longshot premium? (2026-06-21)

Follow-up to `SPORTS_EXCHANGE.md` / `SPORTS_VERDICT.md` / `SHARP_VS_KALSHI.md`, which looked at the
**TAKER / value-bettor** side of US sports exchanges and found them fragile, sweepstakes-fragmented, and
SIG-efficient where liquid. This doc asks the **MAKER** question those did not: on a peer-to-peer sports
exchange you can POST a price and earn the spread when recreational money lifts it — the *same edge the
Kalshi maker study (`KALSHI_MAKER_VERDICT.md`) validated*: "be the LP who sells overpriced longshots to
uninformed lottery flow." Does that edge port from Kalshi to the sports exchanges?

**TL;DR VERDICT (details §6): NO — DEAD for retail.** The edge is structurally real on these venues
(recreational backers overload favorites → longshots are laid rich → a maker who *sells* longshots
collects a favorite-longshot premium), exactly as on Kalshi. **But two independent walls kill it for a
retail maker, and they are the same two that capped the Kalshi version — only worse here:**

1. **The maker-longshot edge has already been professionalized.** The single best academic dataset on
   prediction-market maker P&L (Becker, 72.1M Kalshi trades) finds makers earn +1.12% and takers −1.12%
   via the "optimism tax" of selling longshots — **but that edge only appeared AFTER Oct 2024, when pro
   LPs arrived. Before professionalization, amateur makers LOST −2.0% and takers WON +2.0%.** The premium
   is captured by professional, institutional-scale liquidity provision; *"retail makers cannot
   consistently harvest this premium without institutional-scale operations."*
   ([Becker microstructure](https://www.jbecker.dev/research/prediction-market-microstructure))
2. **On a liquid exchange the queue is contested by exactly those pros, and the favorite-longshot bias
   is competed away** (Betfair shows little-to-no average FLB; SIG is Kalshi's flagship MM at 30× depth,
   2–3¢ spreads; ProphetX explicitly hires third-party institutional market makers). Where it ISN'T
   competed away — illiquid props/niche legs — **there is no recreational flow to harvest** and you can't
   fill size. Same soft↔thin / deep↔contested wall, now with a pro MM standing on the bid.

Plus the **in-play adverse-selection reversal**: pre-match a maker laying longshots earns the premium,
but as information arrives "longshot bets generate large, systematic losses even for liquidity providers"
— informed takers pick off the very longshot quotes the recreational story says are free money.

The one *new* positive vs `SPORTS_EXCHANGE.md`: **the venues are no longer collapsing — Novig and ProphetX
both won CFTC DCM approval in June 2026** and are converting to real-money. So the venue-survival leg
improved. It just doesn't matter, because the maker edge is pro-owned and the rest is thin.

---

## 1. VENUE STATUS — June 2026 (the landscape moved since `SPORTS_EXCHANGE.md`)

| Venue | Live? | Legal/real-money | Retail can POST maker orders? | Maker economics | Liquidity / flow |
|---|---|---|---|---|---|
| **Novig** | **Yes** — CFTC DCM approved **Jun 16 2026**; nationwide real-money rollout "this summer." Currently still sweepstakes (Coins/Cash) mid-transition. | Federal CFTC DCM (Ludlow Exchange LLC) → real-money in all 50 states. Was sweeps in ~42 states, hit by 11-state dual-currency bans. | **Yes** — Make/Take limit orders; you post a price, fill if someone matches. **BUT once matched you CANNOT cash out or sell the position** (no in-play exit). | "No vig," no trade fee; **occasional small maker rebate in Novig Cash**; ~1–4% only on "market-maker contests," 0 on P2P. | $5B+ cumulative volume, $75M Series B (Pantera); deep on NFL/NBA, thin off-flagship. House sometimes **seeds** the book. |
| **ProphetX** | **Yes** — CFTC DCM **and DCO** approved **Jun 11 2026**; transitioned sweeps→real-money. | Federal CFTC DCM/DCO real-money; "first sports-native direct-clearing prediction market." | **Yes** — back-and-lay via +/− buttons (nudge price up = maker/resting; pull down = taker/instant). | **2% commission on NET WINNINGS only** (none on losses/stake); parlays free. | No hard caps — "how much you can wager depends entirely on liquidity posted by other users"; strong on majors, thin/nonexistent on props/niche. **Explicitly uses THIRD-PARTY institutional market makers** (refuses an affiliated trading arm). |
| **Sporttrade** | **No (real-money)** — exited NJ/CO/IA/AZ/VA sportsbook (all access gone ~Jun 2026); **awaiting** CFTC DCM/DCO. | The original true state-regulated exchange; now pivoting to CFTC, nothing tradable today. | (was) 0–100 limit orders, two-sided exit | (was) 2% commission on profitable trades; ~10¢ lines | SIG-backed (SIGSports invested since 2023); was the tightest book — but **offline**. |
| **Kalshi (as exchange)** | **Yes** — most liquid US prediction exchange. | CFTC real-money. | **Yes** — full maker/taker; soft categories **zero maker fee** (`fee_type=quadratic`). | See `KALSHI_MAKER_VERDICT.md`: +~1¢/contract selling longshots, **but capacity-capped $30–150/mo**. | **SIG = flagship MM**: ~30× prior liquidity, **2–3¢ spreads, 100k-contract depth, 98% uptime**. Sports game-lines SIG-efficient. |

Sources: [CNBC Novig CFTC](https://www.cnbc.com/amp/2026/06/16/novig-wins-cftc-approval-as-competition-intensifies-in-sports-prediction-markets.html),
[Covers Novig](https://www.covers.com/industry/novig-cftc-approval-prediction-market-designation-launch-june-2026),
[Novig PRNewswire](https://www.prnewswire.com/news-releases/novig-secures-cftc-designation-bringing-the-first-prediction-market-built-for-sports-fans-nationwide-302801964.html),
[oddsassist Novig](https://oddsassist.com/prediction-markets/novig/) (Make/Take, no cash-out after match, rebate in Cash),
[oddsassist ProphetX](https://oddsassist.com/prediction-markets/prophetx/) (back/lay +/− buttons, 2% on net winnings, real-money post-CFTC),
[Sportico ProphetX no affiliated trading arm](https://www.sportico.com/business/sports-betting/2026/prophetx-prediction-market-affiliated-trading-arms-1234909865/),
[bettingstartups Novig+ProphetX CFTC](https://news.bettingstartups.com/p/novig-prophetx-prediction-market-cftc-license),
[Sportsbook Review Novig](https://www.sportsbookreview.com/news/novig-lands-cftc-approval-to-offer-sports-markets-june-18-2026/),
[Kalshi liquidity/SIG](https://news.kalshi.com/p/liquid-prediction-markets-are-finally-here).

**Net venue change vs the prior doc:** the survival risk that killed `SPORTS_EXCHANGE.md` has eased —
Novig & ProphetX are now CFTC-regulated real-money exchanges (same bucket as Kalshi), not dying
sweepstakes. That removes the legal-access objection. It does not touch the maker-edge objections below.

---

## 2. RECREATIONAL FLOW — is there enough uninformed crossing flow to harvest?

**The good half is real:** the *direction* of recreational flow is exactly what the maker story needs.
On exchanges, backers systematically pile onto favorites — on Betfair, **46% of all money staked is on
the favorite** ([Sporting Life FLB](https://www.sportinglife.com/free-bets/guides/betfair-exchange-education/favourites-and-longshots)).
That money imbalance is what *creates* generously-priced longshots: "layers are far more comfortable
making the 15.00 chance available at 20.00 than the 2.50 chance available at 2.90." And the
prediction-market version is sharper: takers disproportionately buy YES at longshot prices, and **"YES
longshots underperform NO longshots by up to 64 percentage points"** — the recreational lottery flow is
genuinely there and genuinely uninformed ([Becker](https://www.jbecker.dev/research/prediction-market-microstructure)).
This is the same uninformed-longshot-buyer pool the Kalshi maker study found.

**The bad half:** on these *sports* exchanges that flow concentrates on the **flagship leagues**
(NFL/NBA) — precisely where SIG/third-party MMs already stand on the book and the price is already fair.
Off-flagship (props, niche), where a retail maker could be the *only* LP, **there is no recreational
crossing flow** — "thin or nonexistent action, fills uncertain" (ProphetX), "liquidity drops off fast
past the major markets." So the recreational flow exists, but it is sitting in the contested liquid
markets, not the uncontested thin ones. You cannot have *both* the soft flow and the empty queue.

---

## 3. THE MAKER EDGE vs ADVERSE SELECTION — the crux

Two opposing forces, and the sign flips depending on who you trade against:

**Force toward profit (favorite-longshot premium).** Pre-match, on a book dominated by recreational
favorite-backers, a maker who LAYS/SELLS longshots collects the rich longshot price and pays out less
often than priced. This is the Kalshi "optimism tax" / "sell overpriced longshots" edge, and it is
**academically confirmed: makers +1.12%, takers −1.12% across 72.1M trades, widening to +57% maker
edge at 1-cent contracts** ([Becker](https://www.jbecker.dev/research/prediction-market-microstructure)).
On Kalshi soft markets we independently measured the survivable pocket at **+0.97¢/contract at ~17σ,
net of adverse selection and fee** (`KALSHI_MAKER_ADVSEL.md`).

**Force toward loss (adverse selection / informed takers).** The premium is NOT free; it is
compensation for being picked off. The Whelan/Betfair transaction-level work finds that **as a match
progresses, "longshot bets generate large, systematic losses even for liquidity providers, and profits
emerge for those who accept offers on favorites"** — i.e. in-play, informed takers selectively lift the
maker's too-generous longshot quotes, and the maker's longshot lay book bleeds
([Whelan, Economics of Betting Exchanges](https://www.karlwhelan.com/Papers/Betfair.pdf);
[Sciencedirect in-play](https://www.sciencedirect.com/science/article/abs/pii/S0169207021000996)). On
average across Betfair the favorite-longshot bias is **competed flat** — "the average odds on Betfair did
not display a favorite-longshot bias" — because layers have already arbed it to the overround.

**Where the two forces net out tells you everything:**
- On **pre-settlement, low-information soft markets** (weather, politics longshots) the optimism tax
  dominates → the edge survives. *That is the Kalshi pocket — non-sports.*
- On **sports** the information clock is fast and the takers include sharps; the in-play adverse-selection
  reversal applies, and the average bias is already competed to ~0 on the liquid leg. The retail maker
  selling sports longshots is therefore standing in front of (a) a competed-flat average price and (b)
  informed takers who only lift quotes that are *mispriced in their favor*. **That is adverse selection
  that eats the premium.** Net of ProphetX's 2% on winnings, it goes negative.

The Becker result is the decisive one for the *retail* version: **the maker edge is real but
amateur-makers historically realized the WRONG sign of it (−2.0% pre-Oct-2024); it only became +EV once
professional LPs systematized spread capture.** A patient retail maker posting by hand is the amateur in
that experiment.

---

## 4. COMPETITION — is the maker queue contested by pros?

Decisively contested where the flow is:

- **Kalshi:** SIG is the flagship MM — ~30× prior liquidity, **2–3¢ spreads, 100k-contract depth**.
  SIG built a dedicated prediction-markets desk (first quant firm to, 2023); DRW also active. The
  professionalization is exactly what turned the maker edge positive — *for the pros*
  ([Kalshi/SIG](https://news.kalshi.com/p/liquid-prediction-markets-are-finally-here);
  [Susquehanna prediction desk](https://www.wisdomai.com/insights/Odd%20Lots/prediction-markets-susquehanna-market-making-liquidity-69e67bfa)).
- **ProphetX:** does not run an affiliated trading arm; instead "works with **third-party institutional
  market makers** that will provide liquidity." So the maker layer is *outsourced to pros by design*
  ([Sportico](https://www.sportico.com/business/sports-betting/2026/prophetx-prediction-market-affiliated-trading-arms-1234909865/)).
- **Novig:** the house itself **seeds** the book with Make orders during low liquidity, and SIG-style
  capital ($75M Series B) backs the operation.
- **Sporttrade:** SIG-invested (SIGSports since 2023) — built around institutional liquidity.

So on every venue, the liquid markets where recreational flow crosses are front-run by institutional MMs
with capital, speed, and inventory tools a retail maker lacks. The retail maker is **last in the queue
behind a pro at the same price** — and the pro will already have skewed the longshot quote to the fair
side, leaving the retail maker to fill only when the price is *worse* than fair (adverse selection,
again). This is the identical structural conclusion as the Kalshi 15m-MM box (`KALSHI_15M_VERDICT.md`):
liquid + contested-by-MM → no reachable edge for a slow retail participant.

---

## 5. NET-OF-RAKE EDGE + CAPACITY

- **Gross signal:** the favorite-longshot / optimism-tax premium is real and the same one that yields
  ~+1¢/contract on *Kalshi soft non-sports* markets.
- **Net of rake:** ProphetX takes **2% of net winnings**; Novig "no vig" but pays makers only an
  occasional small **rebate in sweepstakes Cash** and **forbids exiting a matched position** (you are
  married to settlement → maximum adverse-selection exposure, no inventory management). On sports the
  premium is already competed toward 0 on the liquid leg, so after the 2% it is **net negative on the
  fillable markets** and **net positive only where there is no flow to fill against.**
- **Capacity:** even granting a positive net pocket, capacity is the same binding wall as Kalshi
  (`KALSHI_MAKER_CAPACITY.md`): the soft/uncontested flow lives in thin markets that turn over a few
  hundred to low-thousands of contracts over their whole life, shared across all makers, filling in
  3–4-contract nibbles, settlement-loaded (the fillable flow is the most adverse). On sports exchanges
  this is *worse* than Kalshi because the thin markets are props/niche with the least recreational flow
  and the most informed takers. Realistic harvest for a retail maker: **≈ $0 net after rake and adverse
  selection; not a positive annuity, and it does not scale with bankroll** (flow-capped, not
  capital-capped).

---

## 6. VERDICT + 7-trait honesty

**Not viable for a retail maker.** The "sell overpriced longshots to uninformed flow" edge that works on
Kalshi *soft non-sports* markets (capped at $30–150/mo) **does not port to the US sports exchanges.** The
favorite-longshot premium is structurally present, but on these venues it is (a) **already captured by
professional/institutional LPs** (the edge only turns positive *with* professionalization — amateurs
historically realize the wrong sign), (b) **competed to ~0 on the liquid leg** where the recreational
flow actually crosses, (c) **reversed in-play by informed-taker adverse selection** on the fast sports
information clock, and (d) **net-negative after rake** (ProphetX 2% on winnings; Novig forbids position
exit and rebates only in sweepstakes Cash). Where it isn't competed away — thin props/niche — there is no
recreational flow to harvest and no fillable size. The one genuine improvement vs `SPORTS_EXCHANGE.md`
(Novig + ProphetX now CFTC real-money, not dying sweepstakes) fixes the venue-survival leg but leaves the
maker-edge leg dead. Consistent with `SPORTS_VERDICT.md`: **promo extraction remains the only deployable
sports edge; the exchange maker side is not a second one.**

**7-trait honesty:**
1. **Falsifiable test that would change the verdict:** a forward, live, hand-or-bot maker log on
   ProphetX/Novig sports + props showing net-of-2%-rake maker P&L > 0 on *fillable* size with positive
   +10-min markout (no informed-taker pickoff), out-of-sample, after the venues are fully real-money.
   Until then this is REFUTED-by-analogy, not merely unmeasured.
2. **Disconfirming evidence I'm relying on:** Becker (amateur makers −2.0% pre-professionalization;
   "retail cannot harvest without institutional-scale ops") and Whelan/Betfair (longshot LPs take
   systematic in-play losses). These directly contradict the optimistic read and I am weighting them.
3. **Strongest counter-argument:** the venues are brand-new real-money exchanges (days old) with
   immature MM coverage off-flagship — there could be a brief window before pros fully blanket props
   where a retail maker captures FLB. Rebuttal: that window is thin-flow (no recreational takers to fill
   you) and short-lived (ProphetX *outsources* MM to pros by design), so it's not a durable edge.
4. **Base rate:** every prior maker/queue study in this repo (Kalshi 15m box, crypto box) found liquid +
   spot/info-anchored markets are pro-contested behind a queue a slow retail participant can't reach;
   this is the same pattern, not an exception.
5. **What I did NOT verify directly:** exact current Novig/ProphetX maker rebate bps, minimum order
   sizes, and live off-flagship book depth (sources were paywalled/403 on some review pages). These
   affect the *magnitude* of the loss, not the sign.
6. **Venue-survival risk (still nonzero):** real-money launches are days old; rollout "this summer" not
   complete; state-level friction and CFTC scrutiny of sports event contracts persist. Don't build on a
   2-week-old regulatory status.
7. **Selection/sample caveat:** the strongest pro-edge datapoint (Becker +1.12% maker) is **Kalshi
   all-category**, not sports-only, and post-professionalization — it describes the *pros'* edge, which
   is the opposite of evidence for a *retail* sports-maker edge.

**Bottom line:** liquid sports-exchange markets are MM-contested (no retail maker edge); thin ones have no
recreational flow to harvest (no capacity). Neither hits the sweet spot. The maker side is rake/sharp/
competition-killed for retail — same answer as the taker side, for a different (microstructure) reason.

---

### Sources
- [CNBC — Novig wins CFTC approval](https://www.cnbc.com/amp/2026/06/16/novig-wins-cftc-approval-as-competition-intensifies-in-sports-prediction-markets.html)
- [Covers — Novig CFTC designation](https://www.covers.com/industry/novig-cftc-approval-prediction-market-designation-launch-june-2026)
- [PRNewswire — Novig CFTC](https://www.prnewswire.com/news-releases/novig-secures-cftc-designation-bringing-the-first-prediction-market-built-for-sports-fans-nationwide-302801964.html)
- [Betting Startups — Novig + ProphetX CFTC licenses](https://news.bettingstartups.com/p/novig-prophetx-prediction-market-cftc-license)
- [Sportsbook Review — Novig CFTC](https://www.sportsbookreview.com/news/novig-lands-cftc-approval-to-offer-sports-markets-june-18-2026/)
- [oddsassist — Novig (Make/Take, no exit after match, Cash rebate)](https://oddsassist.com/prediction-markets/novig/)
- [oddsassist — ProphetX (back/lay +/−, 2% on net winnings, real-money)](https://oddsassist.com/prediction-markets/prophetx/)
- [Sportico — ProphetX rejects affiliated trading arm, uses 3rd-party MMs](https://www.sportico.com/business/sports-betting/2026/prophetx-prediction-market-affiliated-trading-arms-1234909865/)
- [Becker — Microstructure of Wealth Transfer in Prediction Markets](https://www.jbecker.dev/research/prediction-market-microstructure)
- [Whelan — Agreeing to Disagree: Economics of Betting Exchanges (Betfair)](https://www.karlwhelan.com/Papers/Betfair.pdf)
- [ScienceDirect — Informational efficiency in in-play prediction markets](https://www.sciencedirect.com/science/article/abs/pii/S0169207021000996)
- [Sporting Life — Favourites and longshots on Betfair (46% of money on favourite)](https://www.sportinglife.com/free-bets/guides/betfair-exchange-education/favourites-and-longshots)
- [Kalshi — Liquid prediction markets / SIG flagship MM](https://news.kalshi.com/p/liquid-prediction-markets-are-finally-here)
- [WisdomAI/Odd Lots — Why Susquehanna is building prediction markets](https://www.wisdomai.com/insights/Odd%20Lots/prediction-markets-susquehanna-market-making-liquidity-69e67bfa)
