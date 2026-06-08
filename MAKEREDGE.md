# Expanding the maker edge — research & roadmap

Our edge today (EDGE.md): **rebate (20% of taker fees, crypto) + spread**, bounded by **queue position**
and **adverse selection**, kept directionally small. The proven lever is toxicity-avoidance (micro_gate,
gross-positive). This note researches ways to make the maker seat bigger, cross-checked with the
literature, ranked by EV × feasibility, with each tagged **[paper-testable]**, **[live-only]**, or
**[infra]**. The honest frame: there's no free risk-free money here (BOXARB.md), so "more edge" =
(a) capture more rebate volume, (b) lose less to adverse selection, (c) remove the directional
resolution risk that currently forces us to quote small.

## 1. Delta-hedge the resolution risk on a BTC perp  — **[live-only]; MEASURED: only worth it if we size UP**
The idea: BTC Up/Down inventory is a directional bet on the 15-min outcome, so **short/long a BTC perp**
to offset net delta and quote bigger/both-sides for pure spread + rebate (DWF Labs; Guéant-Lehalle
dealer-markets-with-hedging, arXiv:2106.06974). Basis note: the market settles on **Chainlink/Binance**
(we consume it via RTDS), so a **Binance perp is the cleanest hedge**.

**Quantified it first (`hedge_value.py`, 59 windows) — and the result kills the naive version.** Using
the minimum-variance hedge ratio, hedging the directional factor `end_delta·(r−rbar)` removes only
**0–10% of P&L variance (size× ≈ 1.0–1.1)** for every current variant, and `mean dir ≈ 0`. Why: our
variants are **already effectively delta-neutral** (cap/skew squeeze end_delta to ~0), so the bulk of
P&L variance is **spread/fill/queue, not resolution risk** — there's almost nothing for a perp hedge to
buy back. **So delta-hedging at our current tight inventory is a no-op (and would only add perp
fee+funding cost).** It becomes worthwhile ONLY if combined with **deliberately larger inventory**: run
a wide-cap config and hedge its delta, converting the relaxed inventory budget into rebate volume. That
is a *different* config than anything on the tape, so the next test is a `hedged_big` variant (large cap,
near-zero skew, model the hedge as removing the directional term) to see if `Δrebate > hedge cost` once
inventory is intentionally large. Bottom line: hedging is a **sizing enabler, not a standalone edge**,
and only if we first decide to carry inventory — at today's tight settings it's off the table.

## 2. Mint-sourced balanced inventory (box → MM bridge)  — **[live-only], novel**
Today inventory accumulates *passively* and *adversely* (we get hit on the side informed flow wants,
drifting us directionally exactly when it hurts). Instead, **mint complete sets** (split $1 → 1 Up +
1 Down) to hold **pre-balanced, delta-zero inventory**, then post **both legs as sells from inventory**.
You become a structurally flat two-sided maker: every fill is a sale from a hedged pair, so inventory
never drifts directional and there's no resolution risk to skew against. This is the `--box-arb` mint
primitive repurposed from arb to MM. Pairs naturally with #1 (or replaces the need for it). Hot-path
safe because minting is done out-of-band (DEPLOY.md): the loop only posts CLOB sells.

## 3. Quote to maximize fill-prob × post-fill markout (not just spread)  — **[paper-testable]**
The maker's real objective is `E[P&L] = fill_prob(δ) × (spread(δ) + rebate + E[markout | fill, δ])`,
and fill_prob falls sharply as you widen (arXiv:2502.18625 "Market Maker's Dilemma"; 2508.20225
"Optimal Quoting under Adverse Selection"). In a 1-tick market we can't widen, so the controllable
term is **E[markout | fill]** — i.e. *when* to quote. micro_gate is the binary version (pull when
toxic). The expansion is **continuous**: scale size by expected favorability (`size ∝ max(0, −E[tox])`)
rather than a hard gate. We already log per-fill markout + tox; a `mo_size` shadow variant (size up
when the book/flow is benign, size to zero when toxic) is directly backtestable on the existing tape.

## 4. Full Avellaneda-Stoikov two-sided quoting  — **[paper-testable]**
We use A-S only as an inventory *gate* (av_stoikov). The full model sets **both** quotes around an
inventory-skewed **reservation price** `r = mid − q·γσ²(T−t)` with an optimal half-spread
`δ = γσ²(T−t)/2 + ln(1+γ/k)/γ` (Avellaneda-Stoikov 2008; Guéant-Lehalle-Tapia closed forms). Near
expiry `(T−t)→0` it auto-tightens and de-skews — principled, parameter-light, and a clean replacement
for our ad-hoc cap/skew dials. Implement as a quoting *mode* (not a gate) in the shadow framework and
compare GROSS vs baseline.

## 5. Cross-asset / cross-tenor breadth  — **[infra], high practical EV**
Run the *same* maker on **5-min + 15-min × BTC/ETH/SOL/XRP** simultaneously. Same code, same RTDS feed
(it carries all symbols), but: (a) **more rebate volume** (rebate is a *share of the fee pool* ∝ your
filled volume — see #6), (b) **diversified resolution risk** across uncorrelated-ish 15-min outcomes,
(c) inventory can be **netted/hedged across correlated assets** (Guéant multi-asset, arXiv:1810.04383:
correlation/cointegration reduces aggregate inventory risk). Biggest bang-for-effort after co-location.

## 6. Rebate-tier flywheel  — **[infra]**
Maker rebate = `(your fee-equivalent volume / total) × pool`, and the **taker** rebate is tiered
**3–50% by 30-day volume**. So volume compounds the rebate rate. Implication: quoting more markets (#5)
and being higher-fill (latency, #8) isn't just linearly more rebate — it climbs the tier and lifts the
*rate* on everything. Track our 30-day volume vs the tier thresholds and treat tier-climbing as an
explicit objective when sizing the program.

## 7. Event / volatility-aware spread & pull  — **[paper-testable]**
Adverse selection clusters around BTC volatility bursts (the lead-lag pickoff). Beyond the per-tick
micro_gate, add a **regime gate**: widen/pull *all* quotes when short-horizon BTC realized vol (from the
in-region RTDS feed) spikes, and quote full size in calm regimes (Glosten-Milgrom: pull when the
probability of informed flow rises). Testable: a `vol_gate` variant keyed on RTDS realized vol.

## 8. Latency as front-of-queue value  — **[done / ongoing]**
Cartea-Sánchez-Betancourt's "shadow price of latency": in a 1-tick book where you can't price-improve,
**queue position is the only contestable edge**, and it's bought with speed. The sub-10ms work
(DEPLOY.md, --presign, in-region RTDS, netfast) is therefore *directly* a maker-edge expansion: faster
⇒ earlier in queue ⇒ more fills at the *same* toxicity ⇒ more rebate, and faster cancels ⇒ less
adverse selection. This is the one lever that lifts both (a) and (b) at once.

## Priority

1. **Quantify the hedge value** (#1 decomposition) from the existing tape — decides if #1/#2 are worth it.
2. **Ship #8** (sub-10ms) — already in flight; it compounds everything.
3. **Paper-test #3 (mo_size), #4 (full A-S), #7 (vol_gate)** as shadow variants — cheap, on current data.
4. **#5 cross-asset breadth** — highest practical EV once a co-located box exists (and feeds #6).
5. **#1 hedge / #2 mint-balanced inventory** live — the structural unlock, after the decomposition says so.

## Literature
- Avellaneda & Stoikov 2008 (reservation price / optimal spread); Guéant-Lehalle-Tapia (closed forms,
  inventory constraints → ODEs); Guéant multi-asset (arXiv:1810.04383); dealer markets w/ hedging &
  impact (arXiv:2106.06974). Optimal quoting under adverse selection (arXiv:2508.20225); fill-prob vs
  markout (arXiv:2502.18625); robust "to quote or not" (arXiv:2508.16588). Make/take fee & rebate
  market-quality (Malinova-Park; dYdX LP review arXiv:2307.03935). Cartea-Sánchez-Betancourt latency.
