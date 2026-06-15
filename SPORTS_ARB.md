# Sports ARBITRAGE for a small US bankroll: cross-book sure-betting vs the Kalshi-leg angle (2026-06-15)

Brutally honest answer to: *can a small-bankroll US operator run (a) classic cross-sportsbook
"sure betting" and/or (b) the novel angle — **arbitrage / middle a Kalshi (CFTC exchange) contract
against a sportsbook line, using the un-bannable Kalshi leg** — as a deployable, sustainable +EV
income? And does Kalshi's can't-ban property change the "dead US sports-exchange" verdict from
`SPORTS_EXCHANGE.md`?*

Builds on `SPORTS_BETTING.md` (soft books beat-able but ban winners; Pinnacle US-illegal; Kalshi
liquid games SIG-efficient), `SHARP_VS_KALSHI.md` (Kalshi closing mid ≈ sharp consensus, overround
~0%, 1–3c spreads on liquid games; only a marginal favorite–longshot tail bias), and
`SPORTS_EXCHANGE.md` (Sporttrade exiting; Novig/ProphetX/BetOpenly legally-fragile sweepstakes — no
surviving regulated real-money exchange except the CFTC venues). **This doc is specifically about
LOCKED two-leg positions (arb / middle), not single-leg value betting.**

**TL;DR VERDICT (details §6):** **Pure arbitrage is real, tiny, fast-closing, and self-terminating —
on BOTH structures — and Kalshi's can't-ban leg does NOT rescue it.**

1. **Cross-book sure betting:** mathematically guaranteed but **~98% of arbs return <1.2%**, live arbs
   exist only **~4.5% of game time and last ~13 seconds** (Princeton), execution latency routinely
   leaves you half-hedged, and **US books limit/void arbers within days–weeks** (stake caps to **$5**,
   bet voids, deposit refunds; MA's June-2026 letters literally cite *"arbitrage"* and *"latency
   exploitation"*). Realistic sustainable income on a $2–5k bankroll = **low hundreds of $/month for a
   few-week window, often net-negative after the $100–200/mo tool fee** — the durable money is
   **signup-bonus conversion + account churn, not ongoing arb.**
2. **Kalshi-vs-book arb/middle:** Kalshi's can't-ban leg is **genuinely the one structural thing soft
   books can't offer** — the Kalshi side is un-limitable, position limits are ~$25k/market (irrelevant
   for a small bankroll), and liquid games are deep. **BUT the lock still requires the *book* leg to be
   off-market**, because liquid Kalshi prices ≈ the sharp de-vigged consensus (overround ~0) while the
   book carries 4.5–10% vig — so `k_ask + book_implied + Kalshi_fee` is **>1.0 almost always on liquid
   games** (no lock). A lock appears only when the **book is stale/soft** — which is *exactly* the
   pricing error that gets the **book account limited**. So Kalshi solves the *hedge-venue* problem but
   **not the binding constraint** (the book leg is still bannable, and that's the leg that has to be
   wrong for the arb to exist). Net divergence clears fee+vig only on **soft/illiquid spots with near-
   zero capacity**, and a "lock" is frequently broken by **settlement-grading mismatch** (Kalshi resolves
   at *last-traded-fair-price* / DNP-priced-in, NOT the sportsbook *void* — one trader lost $30k to
   exactly this).
3. **Net:** Kalshi's can't-ban property **improves the picture vs `SPORTS_EXCHANGE.md`** (the un-bannable
   exchange exists, survives, and is deep on liquid games — unlike Sporttrade) but **does not create a
   deployable arb**, because efficiency-on-liquid + ban-on-the-book-leg + grading-mismatch still bind.
   It is a **cheaper, un-bannable place to take a bet** (1–2% effective cost vs 4.5–10% book vig), **not
   a guaranteed-profit machine.** **Not a deployable sustainable arb edge; small bankroll +EV fails on
   capacity/limiting/frequency exactly as the prior sports docs predicted.**

The closed-form friction model behind these numbers is in **`sports_arb_econ.py`** (run it: it prints
the Kalshi fee curve, cross-book arb returns, and the Kalshi-vs-book lock condition); the live Kalshi
order-book snapshot is reproduced from `kalshi_sports_probe.py`.

---

## 1. CROSS-BOOK SURE BETTING — frequency, size, speed, tools, and the limiting wall

### 1.1 Frequency & size
- **Margins are small and bottom-heavy.** Typical arb profit is **1–5% of stake**, but **~98% of
  arbitrage opportunities return <1.2%** — the 3–5% arbs are rare, stale, or capped.
  ([SportsBettingDime](https://www.sportsbettingdime.com/guides/strategy/avoiding-sportsbook-restrictions-arbitrage-betting/),
  [Wikipedia: Arbitrage betting](https://en.wikipedia.org/wiki/Arbitrage_betting))
- **Vendor volume claims are inflated.** OddsJam advertises *"hundreds every day"* — but that is across
  150+ books *globally* incl. obscure markets; a realistic per-user count on the 6 big US books
  (DK/FD/BetMGM/Caesars/Fanatics/ESPN BET) is **~10–25/day**, and the bulk are in **player props / alt
  lines / lower-tier markets** (the low-limit markets that *also* flag you fastest). The mainline
  game markets the big books price tightly rarely throw a true 2-way arb.
  ([OddsJam arbitrage tool](https://oddsjam.com/betting-tools/arbitrage))
- The economics (closed form, `sports_arb_econ.py`): two opposite sides at decimal odds `da,db` lock a
  profit iff `1/da + 1/db < 1`. Both books at −110 = `1.0476` (no arb, −4.55%); you need the books to
  *disagree* (e.g. +105 / −102 → 0.73% return; +115 / −105 → 2.32%, rare/stale).

### 1.2 How fast they close
- **The hard empirical anchor (Princeton thesis):** in live/in-play betting, arbitrage windows are
  present **only ~4.52% of total game time**, with a **typical duration of ~13 seconds** before lines
  realign. Pre-game windows are longer (~30s–5min) but still short.
  ([Princeton thesis](https://theses-dissertations.princeton.edu/statistics/items/437f7731-67ad-4af7-a1e6-648c1d003d46))
- **Execution latency is a real, money-losing problem for retail.** Sharp books update in ms; **US soft
  books take ~5–30s or suspend the market.** A few seconds of alert/network/processing delay flags arbs
  that are already gone; the common failure mode is **getting one leg down and the other moving** —
  leaving you on a naked, un-hedged position (i.e. an accidental directional bet).
  ([Claw Arbs](https://clawarbs.com/blog/live-in-play-arbitrage-betting/),
  [SharpAPI](https://sharpapi.io/learn/sports-betting-arbitrage-explained))

### 1.3 Tools (and their cost eats the thin margin)
| Tool | Cost | Function |
|---|---|---|
| **OddsJam** | Gold ~**$199/mo** (~$5.40/day annual); 7-day free trial | Real-time arb finder + +EV across 40+ US books, one-click placement ([RotoWire review](https://www.rotowire.com/betting/oddsjam-review)) |
| **RebelBetting** | **$99/mo** Starter, **$209/mo** Pro (annual cheaper); 14-day trial (50 bets/day) | Surebet (arb) scanner + value betting, bet tracking ([pricing](https://www.rebelbetting.com/pricing)) |
| **OddsBoom** | was ~$15/mo — **acquired by OddsJam**, users migrated to ~$199/mo | budget scanner, now effectively absorbed ([surebets.bet](https://surebets.bet/reviews/oddsboom/)) |
| **Crazyninjamath** | free | hedge/arb **calculator** (stake sizing), not a real-time finder |

A serious US arb finder is **~$100–200/mo**, which on a $2–5k bankroll and ~1% margins requires high,
limit-attracting volume just to break even on the subscription.

### 1.4 THE KILLER — limiting/voiding (the recurring wall)
This is where cross-book arbing dies, and 2026 evidence is unusually concrete:
- **Books name arbitrage in writing.** Under Massachusetts Gaming Commission rules (eff. **June 1,
  2026**) forcing books to state limiting reasons: **Fanatics cited *"potential arbitrage positions"***;
  **DraftKings cited *"attempting to exploit potential latency associated with live market updates"***
  — with a copy-paste error (*"indicative of indicative of"*) showing **templated mass-limiting.**
  ([ingame.com](https://www.ingame.com/limited-bettors-massachusetts-letters/))
- **Speed & severity.** Arbing *"is usually detected quickly,"* after which max wagers are *"decreased
  heavily…to the point of it no longer being viable,"* with documented precedent of *"half of an
  arbitrage bet being canceled, or even the closure of the bettor's account."* Practitioner reports of
  max bets slashed **from ~$500 to as little as $5**; flagged accounts risk the book **voiding existing
  bets and refunding the deposit.** ([Wikipedia](https://en.wikipedia.org/wiki/Arbitrage_betting),
  [SportsBettingDime](https://www.sportsbettingdime.com/guides/strategy/avoiding-sportsbook-restrictions-arbitrage-betting/),
  [RotoWire](https://www.rotowire.com/betting/oddsjam-review))
- **Detection signals:** beating the closing/market line consistently (DK flags *how good* your bets
  are, not just net P&L); round or hyper-specific stakes ($102.57); betting only the off-market side an
  arb tool surfaces; >50% win rate + deposit/withdrawal cycling; **shared cross-book security data.**
  ([SportsBettingDime](https://www.sportsbettingdime.com/guides/strategy/avoiding-sportsbook-restrictions-arbitrage-betting/))

### 1.5 Realistic $/month (small bankroll)
- An often-cited practitioner earned **$50–100/day** at **20–30 arbs/day × $2–4 each** — but spread
  **~$23,000 across 10 books**, far above a $2–5k bankroll. Scaled to $2–5k with capital split across
  books and ~1% margins, realistic **gross is low hundreds/month**, *before* the **$100–200/mo tool fee**
  and *before* limiting hits.
- **The "fresh-account gravy" lasts days to a few weeks** — gated by signup-bonus windows (DK/FD welcome
  offers run ~**7 days**). **The durable money is bonus-bet conversion + account churn**, not ongoing
  arb; pure cross-book arbing is mostly a *fast way to get limited*. (See `SPORTS_PROMO_EV.md` for the
  promo-extraction economics.)
  ([oddsassist bonus-bet arb](https://oddsassist.com/sports-betting/resources/bonus-bet-arbitrage/))

> **Cross-book arb verdict:** real but **self-terminating**. A short-window grind that decays to ~$5
> max bets; the real edge it's adjacent to is **promos**, not arb.

---

## 2. KALSHI-vs-SPORTSBOOK ARB / MIDDLE — does the can't-ban leg unlock a lock?

### 2.1 Kalshi sports structure
- **Markets:** game winners/moneyline, totals, spreads, props, futures across NFL/NBA/MLB/NHL/WNBA/
  tennis (ATP/WTA) and more. Each game = **two complementary YES markets (one per team), priced 1–99¢,
  $1 settlement.** Volume is large: **>$1B NFL contracts in month 1 of the 2025 season**; a record
  **$872M single day.** ([defirate sports](https://defirate.com/prediction-markets/sports/),
  [legalsportsreport](https://www.legalsportsreport.com/258357/kalshi-parlay-volume-surges-but-sports-prediction-economics-still-lag-sportsbooks/))
- **Who makes the market:** **Susquehanna/SIG** — first institutional market maker dedicated to event
  contracts (partnership Apr 2024), believed the largest on Kalshi. This is *why* liquid games are
  efficient and why retail tends to pay a slight edge to SIG.
  ([ingame: SIG named](https://www.ingame.com/market-maker-susquehanna-named-court-filings/),
  [sportico](https://www.sportico.com/business/sports-betting/2026/prediction-market-maker-affiliate-odds-1234884140/))
- **Liquidity is bimodal** — deep+tight on liquid games, thin+wide on the tail. **Live probe
  (`kalshi_sports_probe.py`, run 2026-06-15):**

  | Series | median touch spread | top-of-book depth | note |
  |---|---|---|---|
  | KXMLBGAME (78 games) | **1.0c** | 100k–1M+ contracts within 5c | deep, SIG-tight |
  | KXNBA / KXWNBAGAME | **1.0c** | 10k–250k within 5c | deep |
  | KXWTAMATCH / KXATPMATCH | **1.0c** (some 2c) | tens of thousands | liquid on featured matches |
  | KXNFLGAME (Sep, pre-season) | **4.0c** | 1–7k within 5c | thin off-season |
  | (illiquid props/futures/niche) | **5–10c+** | a few k | "spread is the gap, not edge" |

  General Kalshi rule of thumb: **<3c spread = liquid**; in low-volume markets your own order moves the
  price against you. ([Prediction Hunt liquidity](https://www.predictionhunt.com/blog/how-to-evaluate-prediction-market-liquidity),
  [predictionpilot](https://predictionpilot.io/blog/liquidity-first))

### 2.2 Kalshi fees (the un-bannable leg's cost)
- **Taker fee per contract = `round_up(0.07 · P · (1−P))` dollars** (P in $). **Max 1.75¢ at P=0.50**,
  shrinking toward the tails. **Because of the round-up-to-the-cent, the effective per-contract taker
  fee is ~2¢ across the whole middle (10¢–80¢)** — see `sports_arb_econ.py` fee table — i.e. *worse*
  than the headline 1.75¢. ([predictionhunt fees](https://www.predictionhunt.com/blog/kalshi-fees-complete-guide-2026),
  [marketmath](https://marketmath.io/blog/kalshi-fees-guide-2026))
- **Maker fee** = `round_up(0.0175 · P · (1−P))` ≈ **~25% of taker, and rounds to ~$0 for small trades**
  — so a resting limit order is effectively free, and makers are eligible for **Liquidity Incentive
  Program rebates ($10–$1,000/day pools, through Sep 1 2026).** ([marketmath](https://marketmath.io/blog/kalshi-fees-guide-2026),
  [predictionhunt](https://www.predictionhunt.com/blog/kalshi-fees-complete-guide-2026))
- **Sports markets use the full 0.07 multiplier** (NOT the halved 0.035 of S&P/Nasdaq) — no sports fee
  discount for the retail taker. The **Feb-2026 Sportsbook Hedging Rebate** (eff. ~Feb 23 2026 → Feb 1
  2027) waives taker/RFQ fees **only for sportsbooks hedging large volume** — it pulls sharp/book money
  ONTO Kalshi (making liquid games *more* efficient over time), and does **not** lower a retail arber's
  fee. ([CFTC rebate filing](https://www.cftc.gov/sites/default/files/filings/orgrules/26/02/rules02072638946.pdf),
  [gamingamerica](https://gamingamerica.com/news/1006858/kalshi-launches-prediction-market-rebate-program-for-sports-event-contracts))
- **Net effective cost:** Kalshi ≈ **1–2% of stake**, vs DraftKings/FanDuel **4.5–10% vig.** Kalshi is
  the **cheaper venue** — e.g. a May-2026 Chiefs–Bills moneyline: Kalshi KC YES $0.585 (58.5%) vs DK
  KC −135 (57.4% after vig) → Kalshi **1.1¢ better.** ([tech-insider 4.5% gap](https://tech-insider.org/prediction-markets/prediction-markets-vs-sportsbooks/),
  [predictionhunt DK-vs-Kalshi](https://www.predictionhunt.com/blog/prediction-markets-vs-sportsbooks-draftkings-kalshi))

### 2.3 Does divergence clear the cost? The lock condition
A **true risk-free lock** buying YES_team_A on Kalshi at `k_ask` and betting team_B at the book at
implied prob `book_implied` requires (closed form, `sports_arb_econ.py`):

```
k_ask + book_implied + Kalshi_fee  <  1.0
```

The structural problem: **liquid Kalshi ≈ sharp de-vigged consensus (overround ~0, per
`SHARP_VS_KALSHI.md`)**, while the **book line carries 4.5–10% vig baked into `book_implied`.** So on a
liquid game the two implied probs essentially *sum back through the book's own vig* → the inequality is
**>1.0 almost always.** Worked examples (`sports_arb_econ.py`):

| Kalshi YES_A | book B odds | book implied | sum | +fee | lock? | return |
|---|---|---|---|---|---|---|
| 55¢ | −110 | 0.524 | 1.074 | +2¢ | **No** | −9.4% |
| 50¢ | +105 | 0.488 | 0.988 | +2¢ | **No** (fee tips it) | −0.8% |
| 48¢ | +110 | 0.476 | 0.956 | +2¢ | **Yes** | +2.4% |
| 45¢ | +130 | 0.435 | 0.885 | +2¢ | **Yes** | +10.5% |

A lock only appears when **the book is OFF-MARKET (stale/soft, lines like +110/+130 against a true
~50% side)** — which is precisely the **soft-book mispricing that gets the book account limited** (§1.4).
On liquid games the book is *not* that wrong, so no lock. This matches the public finding that **fees
turn a 3% gross divergence into 1–2% net or a loss**, and that takeable, fee-clearing divergences are
**occasional, soft/illiquid, and small.** ([tech-insider](https://tech-insider.org/prediction-markets/prediction-markets-vs-sportsbooks/),
[sports-ai cross-market arb](https://www.sports-ai.dev/blog/prediction-markets-vs-bookmakers-ai-betting-2026))

**The MIDDLE variant** (e.g. buy a side on Kalshi *and* a non-mutually-exclusive side at the book where
both can win — like the documented "$49.95 on Kalshi YES Bucs @43¢ + $50 DK Bucs, collected $115 + $107
when Bucs won") is **not an arbitrage** — it's a *double-long that paid off*; if the Bucs lose you lose
both legs. A true *middle* needs a totals/spread gap where a band of outcomes wins both; those gaps on
liquid games are ~0 after Kalshi≈sharp, and only open on stale book lines.
([predictionhunt example](https://www.predictionhunt.com/blog/prediction-markets-vs-sportsbooks-draftkings-kalshi))

**Partial fills are the #1 lock-breaker.** Even when the math momentarily clears, Kalshi may fill only
part of your size (e.g. 60 of 100 contracts) before the book leg's line dries up — leaving you **naked
directional** on the unhedged remainder. Tellingly, vendors selling Kalshi arb/middle scanners
(OddsAssist ~$19.99/mo, ArbBets ~$59/mo) **decline to publish ROI** and post profitability disclaimers —
a strong signal the "locked arb" rarely survives execution. And the **variance cuts both ways**: the
Knicks' Game-4 29-point comeback let retail Kalshi traders take ~**$22M off the SIG market makers** in
one swing — proof retail *can* beat the makers on a big move, but that is **variance, not a systematic
edge.** ([Susquehanna Knicks loss](https://finance.yahoo.com/markets/options/articles/susquehanna-takes-biggest-sports-loss-213952606.html))

### 2.4 Does the can't-ban Kalshi leg help?
- **Yes, structurally — and it's real.** Kalshi is **CFTC-regulated, does not take the other side of
  your trade** (SIG and peers do), and **profits from volume regardless of who wins**, so it has **no
  incentive to limit/ban winners** the way books do. This is the one thing soft books and the now-dead
  Sporttrade-style exchanges can't offer a winner. ([Stinson LLP](https://www.stinson.com/newsroom-publications-sportsbooks-or-commodity-exchanges-the-rising-legal-tensions-between-sports-betting-and-prediction-markets),
  [news.kalshi What is Kalshi](https://news.kalshi.com/p/what-is-kalshi-f573))
- **But it doesn't help the part that binds.** The arb needs the **book leg** to be off-market, and the
  **book leg is still bannable** — so you can't *repeatedly* hit soft book lines without being limited;
  Kalshi being un-bannable doesn't fix that. The Kalshi leg's value is being a **cheaper, un-limitable
  place to put the *other* side**, not a source of edge.
- **Caveats on "can't ban":** Kalshi still enforces **position limits (~$25k/retail/market**, lower per
  small event), **conduct rules** (March 2026: banned athletes/insiders from trading their own events;
  insider-trading suspensions of 2–5 years + fines), is under active **state legal challenge**
  (NV/OH/NM rulings, class actions) that could gate access, AND retains a **settlement-carveout
  counter-risk** — Kalshi has voided/recarved markets on technicalities before (the Khamenei "death
  carveout" ~$54M episode wiped out directionally-correct holders), a tail risk that can break a leg you
  thought was locked. ([thelines parlay/limits](https://www.thelines.com/prediction-markets/kalshi/parlay/),
  [CFTC enforcement advisory](https://www.cftc.gov/PressRoom/PressReleases/9185-26),
  [NBC: Ohio ruling](https://www.nbcnews.com/news/us-news/ohio-judge-rules-kalshi-sports-betting-must-adhere-state-law-rcna262721))

### 2.5 Capacity
- **Kalshi leg is NOT the constraint for a small bankroll:** liquid games carry 100k–1M+ contracts
  within 5c of touch (live probe), and retail position limits are ~$25k/market — orders of magnitude
  above a $2–5k bankroll's per-game size.
- **The book leg IS the constraint:** once limited, your max book stake collapses to **$5–$50**, capping
  the *whole* two-leg position regardless of how deep Kalshi is. So **effective capacity = your current
  un-limited book stake**, which decays toward zero on the timescale of weeks.

---

## 3. FRICTION + LIMITING stack (what you actually pay / lose)
| Friction | Cross-book arb | Kalshi-vs-book |
|---|---|---|
| **Bid-ask, leg 1** | book line is the price (vig embedded) | Kalshi 1.0c liquid / 5–10c illiquid half-spread |
| **Bid-ask, leg 2** | second book line (vig embedded) | book line (4.5–10% vig embedded) |
| **Per-trade fee** | none explicit (vig only) | **Kalshi taker ~2¢/contract** (round-up), maker ~0 |
| **Tool/data** | $100–200/mo (OddsJam/RebelBetting) | same odds feed + Kalshi API (free) |
| **Execution risk** | leg-out: ~13s live windows, one leg moves → naked | Kalshi book is continuous, but book line can move pre-fill |
| **Limiting/voiding** | **books cap to $5, void bets, refund deposits in days–weeks** | **Kalshi can't ban; the BOOK leg still does** — binding |
| **Settlement/grading mismatch** | both legs are sportsbooks (mostly aligned grading) | **Kalshi ≠ sportsbook void rules** — see below |
| **Capital split** | spread thin across many books to stay under radar | Kalshi side flexible; book side shrinks with limits |

**Settlement-timing/grading mismatch (a lock-breaker unique to the Kalshi angle):** Kalshi often
resolves *not* by sportsbook convention. Where a book **voids** (player DNP, match abandoned), Kalshi
may resolve at the **"last-traded fair price"** (an exchange estimate from recent prints + resting
depth), and props are typically **"DNP priced in"** (NO settles $1 if the player doesn't play) rather
than voided. A trader from a sportsbook background **lost $30k** assuming a cancelled tennis match would
void on Kalshi — it settled at last-traded price instead. **A "locked" Kalshi-vs-book position can come
apart** when one venue voids and the other doesn't, turning a hedge into a naked leg.
([ufoholdings: I lost $30k to Kalshi void rules](https://ufoholdings.substack.com/p/i-lost-30k-due-to-kalshis-void-rules),
[ESPN: Kalshi prediction markets](https://www.espn.com/espn/betting/story/_/id/45377686/kalshi-prediction-markets-disrupt-sports-betting))

---

## 4. 7-trait scorecard (project standard; ✓ favorable / ~ partial / ✗ fails)

| Trait | Cross-book arb | Kalshi-vs-book arb |
|---|---|---|
| **Recreational (not pro-infra)** | ~ — clicky, but needs $100–200/mo scanner + fast execution | ~ — needs odds feed + Kalshi monitor; manual is too slow |
| **¬HFT (not latency/queue race)** | ✗ — **live arbs last ~13s; you lose the leg-out race to books/bots** | ~ — buy-and-hold-to-settle is fine, but capturing divergence still races book line moves |
| **Fair-value (clean to price)** | ✓ — arb math is deterministic (`1/da+1/db<1`) | ✓ — lock condition is closed-form (`k_ask+book_imp+fee<1`) |
| **Access (US-legal, reachable)** | ✓ — soft books legal in your state | ~ — Kalshi nationwide-ish but under active state legal challenge (NV/OH/NM) |
| **¬ban (venue can't purge you)** | ✗ — **books limit/void arbers in days–weeks; THE wall** | ✗ — **Kalshi can't ban, but the BOOK leg (which must be wrong) still does** |
| **Small-cap friendly** | ~ — built for small stakes, but capital must split across many books and decays to $5 caps | ✓ on Kalshi side (deep, $25k limit ≫ bankroll); ✗ on book side once limited |
| **+EV net (clears all cost)** | ✗ — ~98% <1.2%, minus $100–200/mo fee, minus limiting | ✗ — divergence clears fee+vig only on stale/soft/illiquid spots; grading mismatch risk |

**Cross-book arb: ~1.5 / 7** (only fair-value + access clear; ¬HFT, ¬ban, +EV all hard-fail).
**Kalshi-vs-book arb: ~2.5 / 7** (fair-value + Kalshi-side small-cap clear; ¬ban *partially* improved by
the un-bannable leg but still fails because the book leg binds; +EV fails on capacity/limiting/grading).
**The binding ✗ for both is ¬ban + +EV-net** — same wall as every prior sports doc.

---

## 5. Does Kalshi's can't-ban leg change the dead-sports-exchange picture?
`SPORTS_EXCHANGE.md` concluded the un-bannable regulated exchange was a **DEAD END via venue collapse**
(Sporttrade exiting; Novig/ProphetX legally-fragile sweepstakes). **Kalshi materially improves that:**
the un-bannable, CFTC-regulated, **deep-on-liquid-games** exchange **exists, survives, and is scaling**
(>$1B NFL month-1; SIG-backed). So the *venue* leg of the brutal bar — which Sporttrade failed by going
offline — **Kalshi passes.**

**But passing the venue leg does not pass the edge leg.** The exact properties that make Kalshi a great
*hedge venue* (deep, SIG-priced, efficient, un-bannable) are what make it a **poor arb source**: liquid
prices ≈ sharp consensus, so there's no gap against a de-vigged book to lock; the only gaps are on
**stale/soft book lines (book-leg limiting risk)** or **illiquid Kalshi listings (no capacity, wide
spread)** — plus the **grading-mismatch lock-breaker.** So Kalshi flips the verdict **from "no venue" to
"venue exists but the lock still doesn't close."** It is the **right hedge rail for the promo/value
plays** (`SPORTS_PROMO_EV.md`, `SHARP_VS_KALSHI.md`), **not a standalone arbitrage edge.**

---

## 6. VERDICT (honest)
- **Cross-book sure betting: NOT deployable as sustainable income.** Real and guaranteed per-bet, but
  **tiny (~98% <1.2%), ~13s live windows, books limit/void within days–weeks (caps to $5), and the
  $100–200/mo tool eats the margin.** Realistic sustainable: **low hundreds/month for a few weeks, then
  it decays to ~$0.** The adjacent edge that *does* pay is **signup-bonus conversion + churn**, not arb.
- **Kalshi-vs-book arb/middle: NOT a deployable lock.** The can't-ban Kalshi leg is **genuinely
  valuable and the one real structural advantage**, with ample capacity ($25k limit, deep books) — **but
  it doesn't relieve the binding constraint.** A lock needs the **book** to be off-market, the **book
  leg is still bannable**, liquid Kalshi ≈ sharp (no gap), illiquid Kalshi has no capacity, and the
  **last-traded-fair-price vs void grading mismatch can break a "locked" position** ($30k cautionary
  tale). Net divergence clears fee+vig only **occasionally, on soft/illiquid spots, at near-zero
  capacity.**
- **Does the can't-ban leg change the dead-exchange picture?** **Yes, partially — but not into a +EV
  arb.** Kalshi is the surviving, deep, un-bannable exchange `SPORTS_EXCHANGE.md` wished existed; it
  upgrades the venue from "dead" to "alive." It is best used as a **cheaper (1–2% vs 4.5–10% vig),
  un-limitable place to take/hedge a bet** — the hedge rail for promo extraction and any value-bet
  edge — **not as a guaranteed-profit arbitrage machine on its own.**

**Bottom line:** neither cross-book arb nor Kalshi-vs-book arb is a deployable, sustainable, small-
bankroll +EV income. Pure arb is real but **small, fast-closing, and self-terminating via limiting**;
Kalshi's un-bannable leg **removes the hedge-venue problem but not the edge/limiting/grading problem.**
**Use Kalshi as the un-bannable hedge rail for promos/value (the edges that actually pay), not as an
arbitrage source.**

---
*Artifacts: `sports_arb_econ.py` (fee curve + cross-book arb + Kalshi-vs-book lock model, closed form);
`kalshi_sports_probe.py` (live order-book snapshot, reused from prior work). Companion docs:
`SPORTS_BETTING.md`, `SHARP_VS_KALSHI.md`, `SPORTS_EXCHANGE.md`, `SPORTS_PROMO_EV.md`.*
