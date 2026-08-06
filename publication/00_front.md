# Forty-Two Kills

### What a Year of Adversarially-Verified Trading Research Measured About Retail Prediction-Market Efficiency

---

**Abstract.** Over roughly a year, a retail-scale trading operation pre-registered 42
studies against Kalshi, Polymarket, and (in a late cameo) ForecastEx — testing maker
rebates, taker mechanics, directional forecasting, favorite-longshot bias, near-miss
conversion, cross-venue arbitrage, latency, calibration fades, and ensemble-probability
edges. All 42 closed without a deployable edge, each nailed to a specific number and
mechanism rather than a shrug — though the catalog keeps a distinction its headline can't:
some died as clean measured negatives, and some closed because they never reached their own
pre-registered sample bar, which is not the same thing as being disproven.
This publication is that graveyard as a readable catalog rather than a raw research
ledger: the pre-registration discipline that makes a negative result trustworthy,
case-by-case verdicts for every study, and the transferable lessons — which market roles
closed against a retail-scale operator, which artifacts keep faking an edge, what a verified
engineering stack is actually worth — that the negatives add up to. It measures against one
honest scoreboard throughout: the operator's stated $4,000/month target, never reached, and
by exactly how much.

## Contents

- **Part 1 — Introduction and Methodology.** The punchline up front; three venues and three
  generations of infrastructure tested; the verification method (frozen bars,
  executable-price EV, day-clustered statistics, settlement-truth reconciliation, blind
  replication, adversarial review) worked through on the program's best-looking fake edge.
- **Part 2 — The Catalog, Cases 1–21.** Maker capture, directional forecasting funnels,
  near-miss conversion, calibration fades, and the illiquid-market arbitrage hunt.
- **Part 3 — The Catalog, Cases 22–42.** Stacked and cross-venue edges, favorite-longshot
  bias at taker and maker prices, the sports and weather forecasting axes, the latency
  study, the reopened graveyard entries, ForecastEx, and the final crypto-maker kill.
- **Part 4 — Lessons and Outro.** Seven transferable lessons cited back to specific kills;
  what survived the year (a verified engineering stack, a corrected data-source register, an
  honestly-bounded structural-revenue plan); and what we'd tell someone starting tonight
  with $1,000 and a bot framework.

- **Appendix — Provenance.** All 42 cases with verbatim verdicts, their source study document,
  and whether a runnable reproduction artifact actually survives (11 do; 31 don't).

## Scope note

Every factual claim here is sourced from the underlying research corpus — pre-registered
study specs, backtest outputs, and adversarial-review notes covering roughly 2021–2026
market history and a live-trading window through late July 2026 — and hedged exactly as its
source document hedges it: an optimistic bound stays an optimistic bound, a proxy stays a
proxy, an unverified figure stays unverified. Every numbered case is tied to a named study
document, but a runnable reproduction harness survives for only **11 of the 42** — the
appendix lists which, and says plainly what a reader can and cannot check for themselves.
**This is a record of research
findings, not investment advice** — it documents what didn't work and why, for readers doing
their own diligence, not a recommendation to trade any instrument named here.
