# MAKER_VIABILITY (MM1/MM2) — FINAL: KILL, permanent (2026-07-30)

Door 1's go/no-go measurement. Two blind Sonnet builds, a Sonnet mechanical recompute (0/20+2 cell
mismatches against both builds, 5/5 independent per-fill reconstructions), and a Fable review gate.
**Fable final verdict: MM1 INSUFFICIENT upheld; MM2 FAIL → the study is permanently killed under its
own frozen registration** (anchor redesign was declared a one-shot spend; it was spent).

Artifacts: `maker_stageB_A.*`, `maker_stageB_B.*`, `out/spec_MM1_frozen.json`,
`MM2_REGISTRATION.md`, `out/mm1_verify_recompute.json`.

---

## What IS established (to arithmetic exactness, verified end-to-end)

Kalshi hourly BTC/ETH maker fills (Oct 2024 – Jan 2026, all 16 shards, official settlements,
independent Binance 1s clock):

- **The maker pool is real and positive.** All-fills maker EV ≈ **+0.76c/ct** (all-day universe,
  Build A) to **+1.25c/ct BTC** (final-hour universe, Build B, spec-literal estimator); best gated
  cell ≈ +2.4c/ct. Reconciles exactly (4dp) with U1's independent taker-loss measurement.
- Fee treatment (crypto maker $0, triple-verified) and settlement sourcing are sound in both builds.
- Two blind builds hit the same Binance timestamp-migration bug independently and fixed it the same
  way; every gated number reproduces from both builds' caches.

**But that number is strictly a front-of-queue, pool-average optimistic bound.**

## What KILLED it — the registered gates, not vibes

1. **Temporal instability (MM2 gate b, decisive).** Zero of 20 cells pass clauses 1–4 in *both*
   halves of the sample. BTC's 9 passing cells are all in H2; ETH's single passing cell is in H1 —
   **the two assets' good halves are opposite halves**, a classic nonstationarity signature. The
   corrected anchor likewise holds in only one half per asset (aligned-explained EV flips to the
   wrong sign in the other half: BTC-H1 +0.20c, ETH-H2 +0.60c).
2. **The mechanism is not demonstrated.** "Unexplained EV = queue rent a fast canceller keeps"
   requires informed (aligned-explained) flow to lose the maker money; full-sample it does (BTC
   −0.049c, ETH −0.063c) but with t ≈ −0.08 — statistically zero — and one half per asset it
   doesn't at all.
3. **The achievable population points the wrong way (MM2 gate c).** The listing-window cut — fills
   in the first 10 minutes after each hourly open, the *only* population where a new entrant is
   structurally front-of-queue — has **negative** point-estimate EV for both assets (BTC −0.99c,
   ETH −8.81c; underpowered, not significant). The only front-of-queue-realistic number in the
   study is not positive.

Plainly: **the pool-average positive EV lives in fills a scheduled new entrant would not capture,
in a regime that does not persist across the sample.** The optimistic bound was measured, and the
achievable subsets of it failed their registered tests.

## Verdict semantics honored

- MM1: INSUFFICIENT as frozen (both builds enforced anchor (b) against their own clause-clearing
  cells — no bar moved under maximal temptation, twice).
- MM2: corrected anchor passed full-sample but the registration required anchor + clauses 1–4 in
  **both** temporal halves; no cell qualifies. MM2-FAIL. The one-shot anchor-redesign spend is
  consumed → **permanently killed**; tiny-size live validation was contingent on MM2-PASS and is
  therefore **not** a registered next step. Revival via anchor redesign is foreclosed by the
  registration itself.
- Known residual forks, disclosed and non-outcome-changing: Build A's day-clustered t is U1's
  unweighted per-day formula while Build B's is the spec-literal contract-weighted ratio estimator
  (only B is spec-literal; MM2 gating used B only, as registered); A/B admission universes differ
  per the documented ambiguity (all-day vs final-hour) — the two builds replicate the phenomenon,
  not the same estimand.

## Graveyard row

| # | Strategy | Study | Verdict | Key Number | Mechanism That Killed It |
|---|---|---|---|---|---|
| 42 | Kalshi crypto-hourly maker (adverse-selection-filtered spread capture, reaction speed 1s–300s) | `MAKER_VIABILITY.md` | **MM2-FAIL → PERMANENT KILL** (2 blind builds + recompute + Fable gate) | Pool +0.76 to +1.25c/ct real (front-of-queue optimistic bound, U1-reconciled 4dp) but 0/20 cells stable across temporal halves (BTC good half = H2, ETH = H1); listing-window (achievable) EV negative both assets (−0.99c / −8.81c) | Nonstationarity + achievability: the positive pool concentrates in fills and regimes a scheduled back-of-queue entrant cannot access; the anchor that would certify the cancel mechanism holds in only one half per asset (aligned t ≈ −0.08, statistically zero) |

**Running total: 42 tested, 42 dead.** Door 1's answer is NO — delivered by a $0-infrastructure
measurement instead of a five-figure build-out and months of live losses. That was the point of
measuring first.
