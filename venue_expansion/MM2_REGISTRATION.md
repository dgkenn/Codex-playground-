# MM2 — Anchor-corrected re-evaluation of the maker viability study (REGISTERED 2026-07-30)

**Status: FROZEN at registration. Written while the MM1 workflow's second independent build and
Fable reconciler are still running, before their results are read.**

## Why this exists

MM1 Stage B build 1 returned INSUFFICIENT — not because the signal was weak (all 20 cells positive,
Bonferroni-cleared, pool EV positive both assets, U1 reconciliation exact) but because frozen sanity
anchor (b) breached. The anchor required explained-fill EV to be *sharply negative* (≥1.0c below
unexplained). It was frozen **side-agnostically**: a fill is EXPLAINED if spot moved ≥θ in the R
seconds before it, regardless of direction relative to the taker's bet.

That definition pools two populations with opposite expected signs:
- **Aligned-explained** (spot moved *toward* the taker's side): informed flow — the fills a canceling
  maker dodges. Expected sharply negative.
- **Anti-aligned-explained** (spot moved *against* the taker's side): the taker traded into adverse
  public information — mechanically favorable to the maker. Expected positive.

Pooling them dilutes the negative signal the anchor was designed to detect. The anchor tested a
mixture; the mixture failed the fixed 1.0c gap. This is a registration-design defect in the
diagnostic, not evidence the classification clock is broken.

**Taint disclosure, stated plainly:** the alignment decomposition that motivated this fix was
computed by build 1 on the full dataset. This registration is therefore informed by data already
read. MM2 mitigates that three ways (below); it cannot eliminate it. MM2's conclusions will carry
this disclosure permanently.

## What MM2 changes — the anchor only

Everything else in the frozen MM1 spec — cells, R grid, θ values, EV accounting, volume weighting,
day clustering, Bonferroni bars, pass/kill clauses 1–4, the queue-position framing — is **unchanged**.

**Anchor (b), corrected:** at the designated check cell (R=60s, θ=10bp, per asset):
1. **Aligned-explained** maker EV must be **< 0** and at least **1.0c below** unexplained EV.
2. Anti-aligned-explained fills are excluded from the anchor (reported, not gated).

## New conditions MM2 adds (harder, not tuned to observed numbers)

To offset the registration taint, MM2 adds gates that build 1's diagnostic did NOT compute, so they
cannot have been fitted to known results:

3. **Temporal split**: the corrected anchor AND pass clauses 1–4 must hold independently in BOTH
   halves of the date range (split at the midpoint date of each asset's fill history). A cell passes
   only if it passes in each half at the half-sample Bonferroni bar.
4. **Independent replication**: MM2's gating numbers must come from the MM1 **second build's**
   pipeline (built blind to build 1) as recomputed or corrected by the Fable reconciler — never from
   build 1's own code.
5. **Listing-window cut** (new, feeds the queue-position question): unexplained-fill EV recomputed
   restricted to fills in the first 10 minutes after each hourly market's open_time, where a
   scheduled maker is structurally front-of-queue. Reported with its own day-clustered t. Not gated,
   but this is the number that converts the pool-average optimistic bound into something closer to
   an achievable bound for the strategy actually contemplated.

## Verdict semantics (frozen)

- MM2-PASS: corrected anchor holds AND clauses 1–4 hold in both temporal halves in the replicated
  pipeline, for at least one cell per the original Bonferroni accounting.
- Any other outcome: MM2-FAIL or INSUFFICIENT as applicable. No further anchor redesigns — a second
  anchor failure under the corrected definition kills the study permanently (anchor redesign is a
  one-shot spend, declared here).
- A PASS remains a **front-of-queue optimistic bound** and a necessary-but-not-sufficient condition:
  the only permissible next step is tiny-size live validation (canary scale, hard caps), never a
  scaled build.
