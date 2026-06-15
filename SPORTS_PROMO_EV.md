# Promotional / Bonus +EV Extraction in US Sports Betting (2026-06-15)

Brutally honest research answer to: *is promo/bonus extraction (matched betting, bonus-bet
conversion, profit/odds boosts, risk-free bets) a real, deployable +EV edge for a US small
bankroll — and does a CFTC exchange (Kalshi/Novig/ProphetX) solve the "no US betting exchange"
hedge-leg problem that the prior line-value studies flagged?*

**TL;DR verdict (details in §6):** Promo extraction is the **single most real, documented retail
+EV in US sports betting** — and unlike line-value (SPORTS_BETTING.md / SHARP_VS_KALSHI.md), the
edge is **structurally guaranteed by the sportsbooks themselves**: they pay customer-acquisition
subsidies (deposit matches, bonus bets, profit boosts, no-sweat bets) that convert to **~70-80
cents on the dollar of near-risk-free cash** via hedging. The honest shape is **a large one-time
haul that then collapses to a small grind**:

- **One-time (sign-up bonuses, all books in your state): ~$1,000-$5,000 net** in the first
  ~1 month, 10-20 hours of work (≈ $150-$400/hr effective). State-dependent (more books = more).
- **Recurring (reloads/boosts after sign-ups exhausted): a realistic ~$100-$500/month** *while
  your accounts survive* — and this is **exactly the activity that gets you limited/banned within
  weeks**, so the sustainable post-limiting run-rate decays toward the **low end ($100-$300/mo)**
  and keeps falling as books restrict you book-by-book, market-by-market.
- **The hedge venue IS now solved** (the prior studies' blocker): US-legal CFTC/exchange venues
  — **Kalshi**, **Novig**, **ProphetX** — let you lay the other side, and **they cannot ban a
  winner**. Kalshi works for game-moneyline hedges; Novig/ProphetX are true no-vig exchanges. You
  no longer *need* a second soft sportsbook (or illegal Pinnacle/Betfair) for the hedge leg.

**Net: REAL and deployable, but it is a capped one-time grind ($1-5k) + a decaying small annuity
($100-300/mo) that limiting kills — not a scalable printer. Score 5/7 on the rubric (§5).** The
honest framing: it is the *best* small-bankroll sports +EV we've found, precisely because the edge
is a subsidy you're handed, not a mispricing you must out-sharp — but its ceiling is set by promo
supply, not skill, and the recurring leg erodes as you get limited.

---

## 1. The mechanics + the EV math

There are four promo types, each a distinct +EV conversion. The unifying tool is **hedging the
promo-side bet against the opposite outcome** so the outcome of the game is irrelevant and you keep
the promo subsidy as near-guaranteed cash.

### (a) Bonus bets / free bets — "stake-not-returned" (SNR) conversion

A bonus bet returns **only the winnings, not the stake** ("stake-not-returned"). So a $100 bonus
bet at decimal odds `d` pays `100·(d−1)` if it wins, $0 if it loses. To monetize, you **bet the
bonus on a longshot (high `d`) and hedge the other side in cash** on a second book or exchange.

The conversion identity (free-bet/SNR): you place the bonus on the underdog at `d_back`, and lay/
hedge the favorite in cash. Because the stake isn't returned, **higher back-odds → higher
conversion**:

| Bonus-bet odds (decimal) | Approx. cash conversion of bonus value |
|---|---|
| +150 (2.50) | ~55-60% |
| +200 (3.00) | ~65% |
| +300 (4.00) | **~70%+** (standard target) |
| +400-500 (5.00-6.00) | ~75-78% |

A **70% conversion is the standard "good" target** (turn $100 bonus → $70 cash); 75% great, 80%+
rare. Hedging cost = the exchange commission + any residual vig on the cash leg, which is why you
never get the full 100%. ([OddsJam](https://oddsjam.com/betting-calculators/free-bet-conversion),
[Action Network](https://wp-pressidium.actionnetwork.com/education/bonus-bet-conversion),
[betstamp calc](https://www.betstamp.com/calculators/bonus-bet),
[topendsports](https://www.topendsports.com/sport/betting-tools/bonus-bet-calculator.htm))

**Rule of thumb the whole edge rests on: a $X bonus bet ≈ $0.70-0.80·X of guaranteed cash.**

### (b) Deposit-match / "bet $5 get $X in bonus bets" sign-up offers

These are the headline new-customer offers. The qualifying bet (e.g. "bet $5") is itself ~breakeven
if hedged; the value is the **$X in bonus bets** unlocked, which you then convert at ~70-80% per (a).
So a "Bet $5, get $200 in bonus bets" offer ≈ **$200 × 0.75 ≈ $150 net**, minus the tiny qualifying
hedge cost. A "$1,500 first-bet-loss insurance" offer is worth its face only if the first bet loses;
expected value ≈ `P(loss) × $1500 × conversion`, so a true $1,500 "risk-free" first bet is worth
roughly `0.5 × 1500 × 0.75 ≈ $560` in expectation (and you hedge the qualifying bet so you don't eat
real variance). ([FanDuel/DK/BetMGM/Caesars offers via
GamingToday](https://www.gamingtoday.com/bonus/),
[LegalSportsReport promos](https://www.legalsportsreport.com/sportsbook-promos/),
[Covers](https://www.covers.com/betting/bonuses))

Representative live 2026 sign-up offers (state-dependent):
- **FanDuel** — Bet $5, get **$350** in bonus bets (released $50/day × 7 days).
- **DraftKings** — Bet $5, up to **$200** in bonus bets (7-day expiry).
- **BetMGM** — up to **$1,500** first-bet bonus (loss-insurance) + reward points.
- **Caesars** — deposit $10, **10× 100% profit-boost tokens**.
- **Fanatics** — up to **$100 FanCash/day × 10 days** ($1,000 face).
([GamingToday](https://www.gamingtoday.com/bonus/),
[SportsLine](https://www.sportsline.com/sportsbooks/promos/))

### (c) Profit boosts / odds boosts — +EV when boosted odds exceed fair

A **profit boost** multiplies your *profit* by the boost %: boosted decimal odds =
`1 + (d−1)·(1+boost)`. A 50% boost on `d=2.00` → `1 + 1.00·1.5 = 2.50` decimal. A boost is **+EV
whenever the boosted odds imply a lower probability than the true (de-vigged/exchange) probability**.

Two ways to monetize a boost token:
1. **Take +EV and hold** (don't hedge): apply the boost to a near-coinflip favorite; the boost
   typically adds **~15-30% EV** on a 50% boost applied to even-ish odds. Sharps target boosts with
   **≥8% EV**. This carries variance but the highest EV. ([OddsJam odds
   boost](https://oddsjam.com/betting-education/odds-boost),
   [Action Network boost math](https://www.actionnetwork.com/education/how-to-calculate-which-odds-boosts-are-actually-worth-betting),
   [betstamp](https://betstamp.com/education/evaluating-odds-boost-promos-are-they-worth-it))
2. **Boost + hedge** (low-variance): apply the boost to one side, hedge the other on an exchange;
   you bank a smaller but near-guaranteed fraction of the boost's EV.

Typical boosts are 10-25%; specials hit 50-100%. Books **cap boost stakes at ~$10-$50** precisely
because they know boosts are +EV, which caps per-token value to roughly **$1-$15 net** each.
([OddsJam](https://oddsjam.com/betting-education/odds-boost))

### (d) Risk-free / "no-sweat" bets

Functionally identical to (b)'s loss-insurance: if your first/qualifying bet loses you're refunded
in **bonus bets** (not cash), which you then convert at ~70-80%. So a "$1,000 no-sweat" is worth
`≈ P(loss) × $1000 × 0.75`. You hedge the qualifying bet so the real bet is a wash and you harvest
the expected bonus-bet refund.

---

## 2. Total realistic haul — one-time vs recurring (quantified)

### (a) One-time sign-up bonuses (the big, real number)

The cross-source consensus for a US bettor working **all books available in their state**:

- **Conservative / typical: ~$1,000-$5,000 net in the first month**, scaling with how many books
  operate in your state (5-15 books in mature states). Some aggressive sources cite up to
  $3,000-$5,000; DarkHorse cites **"$1,000 to $5,000+ depending on location"** across 5-15 books.
  ([DarkHorse what-is](https://about.darkhorseodds.com/guides/what-is-matched-betting),
  [HustlEdge](https://hustledge.com/matched-betting-beginners-guide/),
  [ProfitDuel how-much](https://www.profitduel.com/blog/how-much-can-you-make-matched-betting),
  [Caan Berry realistic figures](https://caanberry.com/matched-betting-how-much-can-you-make/))
- **Effort:** ~10-20 hours total over 2-4 weeks ⇒ **$150-$400/hour effective** — genuinely
  high $/hr, but a **one-time, finite stock**: once you've claimed every welcome offer in your
  state, that well is dry.
- Aggregate face value cited: **>$4,000 from ~6 major brands, >$10,000 in offer-rich states**;
  net after ~75% conversion lands in the $1-5k range above.
  ([SportsbookReview](https://www.sportsbookreview.com/bonuses/),
  [bookmakersreview by state](https://www.bookmakersreview.com/betting/bonus/by-state/))

This is the **defining feature of the edge: it is capped by promo supply, not skill.** Your
lifetime sign-up haul ≈ (# books in your state) × (~$100-$400 net each).

### (b) Recurring reload / boost promos (the small, decaying annuity)

After sign-ups, you pivot to **existing-customer reloads, daily/weekly profit-boost tokens,
odds boosts, parlay insurance, "bet-and-get" reloads**. Honest US figures:

- **~$100-$500/month** from ongoing offers if you actively work them; the UK matched-betting
  literature (more mature market, directly analogous mechanics) cites **£300-£1,000+/mo** from
  reloads for committed players, but **the US recurring market is thinner and the limiting is
  more aggressive**, so the realistic US sustainable figure sits at the **low-to-mid end:
  ~$100-$300/month** after you account for limiting.
  ([Outplayed how-much](https://outplayed.com/blog/how-much-can-you-make-from-matched-betting),
  [Outplayed after-signups](https://outplayed.com/blog/matched-betting-after-sign-up-offers),
  [ProfitDuel reloads](https://www.profitduel.com/blog/matched-betting-reload-offers))
- This figure is **not stable** — see §3. It decays as books limit you off boosts and reloads.

**One-time vs recurring summary:**

| | First ~month | Steady state (post-limiting) |
|---|---|---|
| Source | Sign-up welcome bonuses (finite) | Reloads + boost tokens (decaying) |
| Net $ | **~$1,000-$5,000** | **~$100-$300/month** |
| Driver | # books in state | # accounts still un-limited × offer flow |
| Trend | One-and-done | Declines as you get limited book-by-book |

---

## 3. The constraints (decisive) — limiting/banning and the decay curve

This is what separates promo extraction from a "printer." The edge is real but **self-limiting by
design**: the books hand out promos to acquire *recreational* customers and actively purge anyone
who only shows up for +EV.

- **You get limited within days to weeks of bonus-focused / sharp activity.** Books that once
  tolerated winners 12-18 months now restrict within weeks; **the first ~20 bets are the most
  scrutinized** (risk-profiling window). Matched/arbitrage/bonus patterns get **extra scrutiny**
  from risk teams; limits drop max stakes from $thousands to **$50 or less**, or deny boosts/
  restrict markets, or close the account.
  ([darkhorse dont-get-limited](https://about.darkhorseodds.com/guides/dont-get-limited),
  [BettorEdge](https://www.bettoredge.com/post/how-to-not-get-limited-at-sportsbooks),
  [tech-insider](https://tech-insider.org/sports-betting/sportsbooks-vs-betting-exchanges/),
  [boydsbets why-limit](https://www.boydsbets.com/why-sportsbooks-limit-winning-bettors/))
- **Limiting is granular, not binary.** Books limit *per market* (e.g. NBA props but not MLB),
  deny *boost eligibility* while leaving normal betting open, and cut max-stake in blocks as they
  build confidence you're +EV. So "limited" usually means **your recurring promo flow dries up
  while the account technically still exists.** ([ESPN on
  limiting](https://www.espn.com/sports-betting/story/_/id/41231266/),
  [Caan Berry DK restrictions](https://caanberry.com/draftkings-restrictions/))
- **Book-by-book variance:** DraftKings flags "bonus-abuse risk" via internal +EV-pattern
  algorithms and limits aggressively; FanDuel reportedly tolerates more but still cuts to ~$100
  max. Either way, **the recurring promo spigot closes fast** even if you can still place small
  bets. ([elitepickz](https://www.elitepickz.com/blog/do-sportsbooks-ban-winners-and-sharp-bettors),
  [bettingusa](https://www.bettingusa.com/sportsbooks-ban-smart-customers/))
- **State availability** caps the one-time haul: no legal books = no offers; offer-rich states
  (NJ, MI, PA, etc.) carry the $5-10k face, sparse states far less.
  ([bookmakersreview by state](https://www.bookmakersreview.com/betting/bonus/by-state/))
- **Tax:** bonus-bet *winnings* are **taxable ordinary income** (the credit itself isn't, but
  what you cash from it is). From **calendar 2026, books report net winnings ≥ $2,000** via
  W-2G/1099-MISC; you owe regardless of a form. Hedge losses on the opposite leg are deductible
  only if you itemize (and only up to winnings), so **matched betting can create asymmetric tax
  drag** — the winning leg is taxed as income while the offsetting loss may not be fully usable.
  ([Super Lawyers W-2G rule](https://www.superlawyers.com/resources/tax/personal-taxes/sports-betting-tax-w2g-rule/),
  [TurboTax](https://blog.turbotax.intuit.com/tax-help/i-won-money-on-a-sports-app-during-the-big-game-now-what-142930/),
  [CNBC](https://www.cnbc.com/select/sports-bets-taxes/))
- **The grind/effort** is real but front-loaded: 10-20 hrs for the one-time haul, then ongoing
  scanning for worthwhile reloads/boosts (with per-bet caps of $10-50 on the best boosts).

**Decay curve (honest model):** Month 1 = $1-5k one-time. Months 2-6 = $100-500/mo while accounts
are fresh. By ~month 6-12 most soft-book accounts are limited off the promos that mattered, dragging
the sustainable run-rate to **~$100-$300/mo** and trending down, with periodic bumps when new books
launch in your state or you can churn a new account. **It is a depleting resource, not an annuity.**

---

## 4. The Kalshi / exchange hedge angle — does it solve the "no US exchange" blocker?

The prior studies' central complaint about line-value was: the hedge/lay venue that *doesn't ban*
(Betfair, Pinnacle) is **US-illegal**, so US matched bettors were forced to hedge across **two soft
sportsbooks** — and the hedge leg is itself winning behavior that gets limited. **CFTC/exchange
venues largely solve this for the hedge leg:**

- **Kalshi** is a **CFTC-regulated Designated Contract Market** trading **binary event contracts**
  ($1 if outcome occurs, $0 if not), legal in ~47+ states, **operates nationally and is NOT a
  sportsbook** — so it is **not subject to state gambling limiting rules and structurally cannot
  ban a winner** (it's an exchange; it makes money on volume/fees, not on you losing). Its
  game-moneyline markets (MLB/NHL/WNBA/NBA/NFL) are two complementary YES contracts — i.e. you can
  buy the opposite side as your **lay/hedge leg**. Real-world hedging on Kalshi is documented (the
  "mini Mattress Mack" Knicks hedge). ([SI Kalshi review](https://www.si.com/prediction-markets/reviews/kalshi),
  [Built In](https://builtin.com/articles/what-is-kalshi),
  [sportscasting hedge example](https://www.sportscasting.com/news/mini-mattress-mack-kalshi-knicks-hedge-strategy))
- **Novig** and **ProphetX** are **true peer-to-peer betting exchanges** with **back/lay and no
  vig (just ~3% commission on net winnings)** — purpose-built for exactly this. ProphetX
  **explicitly encourages arbitrage/hedging** ("bet the boosted market at a sportsbook, lay the
  opposite at ProphetX for the calculator-recommended amount") and is moving to a **CFTC-regulated
  event-contract model** (legal in ~39 states via sweepstakes today, targeting all 50 post-CFTC).
  As exchanges, they also **don't limit/ban winners**. ([ProphetX review
  LSR](https://www.legalsportsreport.com/prediction-markets/prophetx-promo-code/),
  [bettingusa exchanges](https://www.bettingusa.com/sports/exchanges/),
  [Sportico ProphetX CFTC](https://www.sportico.com/business/sports-betting/2025/prophetx-prediction-market-cftc-sweepstakes-1234876170/))

**What this fixes and what it doesn't:**
- **Fixes the hedge leg.** You can place the *promo* bet at the soft sportsbook (DK/FD/MGM/etc.)
  and lay the *opposite* side on Kalshi/Novig/ProphetX — a venue that **cannot ban you** — so you
  no longer need a second soft book (or illegal Pinnacle) for the hedge. This is the genuine
  improvement over the line-value studies' dead end. The exchange leg also tends to be **tighter
  vig** than a second soft book, which can *raise* conversion above the cross-soft-book 70%.
- **Does NOT fix the promo leg.** The promo *must* originate at the soft sportsbook (only books
  give bonus bets/boosts), and that's the account that gets **limited**. The exchange solves
  *hedging*, not *promo supply* or *limiting*. So the binding constraints in §3 remain.
- **Caveat — basis/settlement risk:** Kalshi's binary settles to the game outcome (good for
  moneyline hedges) but for **spread/total/prop** promos you may not find an exactly-offsetting
  Kalshi contract, leaving residual basis risk; Novig/ProphetX (true sportsbook-style exchanges)
  hedge those more cleanly. Liquidity on illiquid Kalshi listings (5-10c spreads, per
  SHARP_VS_KALSHI.md) can also widen the hedge cost on non-flagship games.

**Bottom line:** the exchange answer is **YES for the hedge leg** — the prior "no US betting
exchange" blocker is materially solved by Kalshi/Novig/ProphetX — but it's **necessary, not
sufficient**, because the +EV still originates at limit-happy soft books.

---

## 5. The 7-trait rubric

Scoring promo extraction on the project's standard 7 traits (✓ = favorable, ~ = partial, ✗ = fails):

| Trait | Score | Why |
|---|---|---|
| **Recreational flow** | ✓ | Edge IS a customer-acquisition subsidy aimed at rec bettors — you harvest the books' marketing budget, not a counterparty's mistake. The purest "rec-flow" edge in the program. |
| **¬HFT (not latency/queue)** | ✓ | No co-located race, no queue position. Place promo bet, hedge on exchange, hold to settle. Seconds of latency irrelevant — opposite of the dead crypto box. |
| **Fair-value (clean to price)** | ✓ | Conversion math is deterministic ($X bonus → ~0.75X cash); boost +EV is a closed-form vs de-vig/exchange fair. No model risk. |
| **Access (US-legal, reachable)** | ✓ | Soft books legal in your state; Kalshi/Novig/ProphetX legal nationally-ish for the hedge. State-gated but genuinely reachable by a US retail person. |
| **¬ban (venue can't purge you)** | ✗ | **The decisive failure.** Soft books **limit/ban promo-takers within weeks**; this is the whole reason it's a one-time grind not an annuity. The hedge venue can't ban you, but the *promo* venue can and does. |
| **Small-cap friendly** | ✓ | Built for small bankrolls — boost caps $10-50, sign-ups need $10-50 deposits. A small account is *advantaged* (looks recreational longer). |
| **+EV net (after costs/tax)** | ✓ | Net positive after hedge cost and tax: ~$1-5k one-time + ~$100-300/mo decaying. Tax drag and effort trim it but don't flip it negative. |

**Score: 6 ✓ / 1 ~partial-leaning-✗ / 1 ✗ → 6 of 7 favorable, but the one ✗ (¬ban) is the
binding one.** Call it **5/7 on a strict read** (¬ban is a hard fail and the access trait is
state-gated). The profile is the **inverse of the line-value edge**: line-value passed ¬ban only on
Kalshi but failed +EV (efficient/thin); promo extraction **passes +EV decisively but fails ¬ban** —
the books purge you, capping the recurring leg.

---

## 6. Verdict

**Is promo extraction a real, deployable small-bankroll +EV?** **Yes — it is the single best
small-bankroll sports +EV in this entire research program, and the only one that clears +EV
decisively** — but it is a **capped one-time grind plus a decaying small annuity, not a scalable
printer**, and the cap is enforced by limiting/banning.

- **Realistic one-time:** **~$1,000-$5,000 net** from sign-up bonuses across all books in your
  state, ~10-20 hours (~$150-400/hr effective), **finite** — once claimed, gone.
- **Realistic sustainable:** **~$100-$300/month** from reloads/boosts *while accounts survive*,
  **decaying** as books limit you off promos within weeks-to-months (book-by-book, market-by-
  market). Do **not** model this as a stable $500/mo annuity; the honest steady state is lower and
  trending down, with bumps only when new books launch.
- **The hedge-venue problem IS solved:** Kalshi (binary game moneyline), and especially **Novig/
  ProphetX** (true no-vig back/lay exchanges), give a **US-legal hedge leg that cannot ban you** —
  directly fixing the "no US betting exchange" blocker the prior line-value studies hit. But this
  fixes only the *hedge* leg; the *promo* leg still originates at limit-happy soft books.
- **Deployability for a small bankroll:** **Deploy the one-time sign-up haul — it is genuinely
  worth it and small-account-friendly.** Treat the recurring leg as a **modest, depleting side
  income**, not a business. The binding constraint is **promo supply + limiting**, not signal —
  the mirror image of line-value, where signal was the problem.

**Honest one-line:** *Promo extraction is real, +EV, and worth doing for the ~$1-5k one-time and a
$100-300/mo decaying tail; the exchange hedge (Kalshi/Novig/ProphetX) finally solves the US lay-leg
problem, but limiting still turns the recurring edge into a depleting resource — collect the
one-time haul, don't quit your job on the reloads.*

**Why this beats every prior sports finding:** line-value (SPORTS_BETTING.md) and Kalshi
sharp-deviation (SHARP_VS_KALSHI.md) both failed on +EV (efficient-or-thin) despite Kalshi solving
¬ban. Promo extraction **flips it** — +EV is guaranteed (it's a subsidy), and the hedge venue solves
the US-exchange problem — leaving only the ¬ban wall, which caps but does not kill the edge. It is
the **first sports strategy in this program that is net-positive to actually deploy**, with eyes
open about its ceiling.
