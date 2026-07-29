# REOPEN FUNNEL — SYNTHESIS VERDICT (2026-07-29)

**Bottom line: 0 of 4 registered specs pass. Nothing clears the corrected bar. Nothing is
deployable. The repo's base rate goes from 37 tested / 37 dead to 41 tested / 41 dead.**

Three of the four specs did not reach their bar at all — they returned INSUFFICIENT because the
archive, filtered by each spec's own frozen entry rule, could not produce a testable sample. The
fourth (U1) reached its bar, produced 19 highly significant Stage-1 survivors, and passed none of
them — because 17 of the 19 are negative-EV taker unit-sides (a measurement of the cost of crossing
the spread, not an edge) and the 2 positive ones are in series that stopped trading before the
frozen validation window opened.

---

## 0. Provenance of this verdict, and one disclosure

Per non-negotiable 7, a reporting gap in my own inputs:

**The adversarial-verification block arrived complete for M1 only.** The RESULTS payload handed to
this judge was truncated mid-way through U1's `bar` field; the builder results and verifier reports
for U1, J1 and D1 were not in my input. Rather than treat those three as unverified, I read the
on-disk artifacts (`venue_expansion/out/spec_{U1,J1,D1}.{json,md}`, the spec sources, and the cached
per-day/per-decile aggregates under `venue_expansion/cache/prereg/tape/`) and ran my own
verification. What I independently re-derived is itemised below. Where I could not verify something,
I say so rather than assert it.

Independently re-derived by this judge (all reproduce exactly unless noted):

| Check | Result |
|---|---|
| Every exact t quantile quoted in the funnel registration (M1 df 39/59/99; J1 df 14; D1 df 99/184; U1 Stage-1 df 39/59/99/199/999 + z; U1 Stage-2 k=1/3/5/10 at df 99) | All 18 reproduce to 4 dp. The registration's arithmetic is correct. |
| U1 `m_units` = 473 frozen literal vs measured | 473 = 473, exact. `m_stage1` = 946 confirmed. |
| U1 Stage-1 statistics for 4 unit-sides, recomputed from cached day aggregates without the build's code | `KXHIGHNY\|B/yes` t=−7.1288, EV −6.3563c print / −4.7056c contract, 250 days, n=188,498, bar 4.4455 — matches claim to 4 dp. Same for `INXD\|T/yes` (+15.2638), `U3\|T/no` (+5.8235), `KXHIGHLAX\|T/yes` (−6.2493). |
| U1 Stage-2 statistic for the best candidate | `KXHIGHNY\|B/yes` validation t=−4.6260 (df=207), EV −4.2624c/−3.1220c, n=330,879 over 208 days — matches. |
| U1 claim that 5 advanced units have zero validation data | Confirmed directly: `INXD\|T`, `INXD\|B`, `U3\|T`, `HIGHMIA\|T`, `HIGHCHI\|T`, `NASDAQ100D\|T`, `HIGHNY\|B`, `INXW\|B` have **zero rows** in the validation window. Last `INXD` print 2024-12-31; last `U3` print 2024-11-01. |
| U1 Stage-1 screen coverage | 946 unit-sides scored; only **170** produced a computable t and only **143** met the min-n floor (≥2,000 FIT prints AND ≥40 FIT days). See §3.2 — this is conservative, but it was not stated in the builder's summary. |
| D1 skip-ledger arithmetic | SPEC 1: 5,029 skips + 5 qualifying = 5,034 ≈ all TEST bracket rungs. 4,188 (83%) killed by "no ask print in [H−30m,H]". SPEC 7: 260 TRAIN obs against 3,524 dropped for the same reason (93%). Confirmed. |
| J1 realized df | Archive splits 8 FIT / 16 VALIDATION. The registration froze "15 Thursday clusters exactly, bar 2.8640 (df=14)". Realized validation df would have been 15, exact bar **2.8366**. Divergence reported, not applied — nothing reached the bar. |

For M1 I adopt the supplied verifier's findings, which are detailed, reproduce the build's
arithmetic exactly, and identify two independent defects the builder did not.

---

## 1. Verdict per spec, after adversarial verification

| Spec | Builder claimed | **Final verdict** | Overridden? |
|---|---|---|---|
| **M1** — macro-surprise pass-through into the open Fed-decision market (reopen of graveyard #29) | NULL (self-kill, no signal) | **INSUFFICIENT** | **YES — verifier overrides builder.** The FIT statistic that fired the self-kill contains zero information about the hypothesis, and the frozen min-n gate was unreachable *ex ante*. "No signal" is a category error; the drift was never measured once. |
| **U1** — executable-price universe screen on reconstructed crossing prices (two-stage) | FAIL (19 Stage-1 survivors, 10 advanced, 0 passed Stage 2) | **FAIL** | No — upheld, and I reproduce every number I checked. But the *reading* of the survivors is materially corrected: 17 of 19 are not candidate edges, they are the taker spread. |
| **J1** — KXJOBLESSCLAIMS weekly-relist fade (reopen of graveyard #24) | INSUFFICIENT (FIT theta selection undefined) | **INSUFFICIENT** | No — upheld. Correct handling of a genuinely unexecutable selection rule; no substitute improvised. |
| **D1** — directional SPECs 1/3/7 re-run at archive n (reopen of graveyard #3/#5/#9) | INSUFFICIENT (all three legs) | **INSUFFICIENT** | No — upheld on all three legs. |

**Passes: 0 of 4.**

---

## 2. Funnel-wide multiple-comparison accounting

Frozen 2026-07-29, before any test data was read. Reproduced by this judge; no bar moved.

- **Specs registered and tested: 4** (M1, U1, J1, D1). Family-wise error rate 0.05, Bonferroni over 4
  → **per-spec two-sided α = 0.0125** (z = 2.4977; exact t quantile at df = n_clusters − 1 used
  everywhere, never the z).
- **M1** — 1 gating leg at α = 0.0125. Bar |t| ≥ 2.6189 (df=39) / 2.5766 (df=59) / 2.5442 (df=99).
  **Never reached** — validation never opened.
- **J1** — 1 gating leg at α = 0.0125. Registered bar |t| ≥ 2.8640 (df=14); realized df would have
  been 15 → 2.8366. **Never reached** — FIT theta selection undefined at every grid cell.
- **D1** — 3 legs, internally Bonferroni-split: α/leg = 0.0125/3 = 0.0041667 → |t| ≥ 2.9334 (df=99),
  2.9015 (df=184). SPEC 7 is not a t-test; bar = 3-of-5 price-bin sign agreement at |gap| ≥ 0.04
  with MIN_GROUP_N = 20. **No leg reached its min-n floor.**
- **U1** — Stage 1: m = 2 × 473 = 946, α₁ = 0.0125/946 = **1.321353e-05**, realized bars 4.376–4.483
  at each unit-side's own df. **Reached.** 19 survivors (expected under the null over the 143
  unit-sides that actually met min-n: **0.0019**). Stage 2: k = min(19, 10) = 10, α₂ = 0.0125/10 =
  0.00125, realized bars 3.2721–3.2723 at df 207–208. **Reached. 0 passes.**
- Net accounting for the one spec that got there: a U1 Stage-2 pass would have survived
  4 × 946 × 10 implied comparisons on a closed sequential test over temporally disjoint data.
  No such pass occurred.
- **No FDR/BH substitution was used anywhere. No one-sided test was used anywhere. No bar moved.**

**Does anything clear the corrected bar? No.** The only unit-sides that cleared any bar in this
funnel cleared it in the *wrong direction* (§3.2).

---

## 3. What was actually measured, per spec

### 3.1 M1 — macro-surprise pass-through (reopen of #29) → **INSUFFICIENT**

**Measured.** All 16 HF trade shards + all 4 markets shards, predicate-filtered to the
KXFEDDECISION/FEDDECISION universe plus six exact macro-surprise family series keys (exact keys, not
a `KXCPI%` prefix — the conflation bug that killed #34). 895,660 trades, 2,213 tickers, cached at
`venue_expansion/cache/prereg/tape/`. 243 family release events built; 112 in the frozen window
[2023-04-07, 2026-01-28]; FIT = 40 (pre-2025-01-01), VALIDATION = 72.

**Honest numbers.** FIT theta grid, release-date-clustered:

| θ | trades | clusters | mean net | t |
|---|---:|---:|---:|---:|
| 0.5 | 2 | 2 | −3.0c/ct | −3.0 |
| 1.0 | 1 | 1 | −2.0c/ct | undefined |
| 1.5 | 0 | 0 | — | — |
| 2.0 | 0 | 0 | — | — |

σ_family (1.4826 × MAD of FIT surprises): CPI 0.0519 (n=3), EMPLOYMENT 68,866.8 (n=2), GDP 0.2439
(n=4), **PCE / JOBLESS / ISM undefined (n=0 computable in FIT)**.

**Mechanism behind the verdict.** Two independent reasons, both determinable without opening
validation P&L:

1. **The self-kill statistic carries no information about the hypothesis.** Both FIT trades have
   *no opposite-side print* in the exit window [t0+60m, t0+120m]. Under the spec's own mark-out rule
   their gross P&L is identically zero, so net = −(entry fee + exit fee) = −4c and −2c **by
   construction**. t = −3.0 is a restatement of `ceil(7p(1−p))`; it would be negative under any
   hypothesis, true or false. Separately, the frozen trigger reads "if **all four** FIT theta cells
   have t ≤ 0" — only one cell has a defined t, so the literal condition was not met. Both paths are
   non-positive, so no edge was manufactured, but NULL was substituted for the INSUFFICIENT the
   spec's own kill_conditions mandate.
2. **The min-n gate was unreachable before any test data was touched.** σ_family is undefined for
   JOBLESS, PCE and ISM, which own **41 of the 72** validation events. The residual ceiling is
   CPI 14 + EMPLOYMENT 13 + GDP 4 = **31 events**, strictly below the frozen floor of ≥40 events and
   ≥40 release-date clusters — before the |x| ≥ θ trigger or the entry-print filter remove anything
   further. The 2023-04..2024-12 FIT window simply predates half the registered family universe
   (KXJOBLESSCLAIMS starts 2025-06-12; KXISMPMI 2025-04-01).

Two further defects, neither of which can rescue the spec but both of which mean the computed FIT is
not the FIT the spec described:

- **Silent strike sign mis-parse.** The frozen regex reads Kalshi's `TN<x>` negative-strike
  convention as positive (`GDP-23JUL27-TN0.6`, sub-title "Above −0.6%", parses to +0.6). 48 markets
  affected; 3 of the 4 GDP FIT surprises contaminated including **one outright sign flip**
  (u −0.022 → +0.045). Because the regex *matched*, none of this appears in the mandatory skip
  ledger. Corrected, the surviving GDP trade's x moves 0.742 → ~1.26 and repopulates a different
  theta cell.
- **Unregistered all-or-nothing ladder filter.** The implementation discards an entire ladder if
  *any single rung* lacks a pre-t0 print. That requirement is nowhere in the registration. It kills
  **95 of 104 FIT ladders (91%)** — and all 95 are killed by rungs that **never traded anywhere in
  the archive** (4 confirmed by direct 16-shard query). An archive coverage hole in deep-tail rungs
  was amplified into the study's dominant filter and labelled as a market fact.

Settlement handling is clean: outcomes come from the archive `result` field only, nothing
re-derived, and the PAPER_TRADER_AUDIT off-by-one class does not reproduce. Live reconciliation is
structurally impossible (every archived-era ticker 404s; a current-week ticker resolves) — honestly
disclosed, though the reconciliation step is not present in the reproducible artifact.

**Graveyard #29 is not closed. It was not tested.**

---

### 3.2 U1 — executable-price universe screen → **FAIL**

**Measured.** All 16 trade shards (154,505,005 rows scanned; 17,006,887 qualifying after the frozen
admission bands) and all 4 markets shards. Unit = (series_key from `event_ticker`, rung_class);
473 units × 2 executable actions = 946 hypotheses. Prices are reconstructed crossing prices from
`taker_side` — `yes` = lifted the ask at `yes_price`, `no` = hit the bid at `no_price`. No
`last_price`, no mid, anywhere in the EV path. Fee `ceil(7p(1−p))` at that same crossing price.
FIT = created_time < 2025-07-01; VALIDATION = [2025-07-01, 2026-01-28].

**Honest numbers — and a coverage figure the builder's summary omitted.** Of the 946 unit-sides,
**only 170 produced a computable day-clustered t and only 143 met the FIT min-n floor** (≥2,000
prints AND ≥40 days). So the effective screen examined **143 unit-sides against a Bonferroni
denominator of 946**. That is conservative and does not move any bar, but it means U1's coverage of
the "473-unit eligible universe" is 15%, not 100%, and it should be reported as such.

19 Stage-1 survivors. **17 have negative t and negative EV; 2 are positive.**

**Mechanism 1 — 17 of 19 survivors are the spread, not a signal.** A negative-EV taker unit-side is
not a tradeable position. Its inverse is *not* "take the other side" — that is a different
unit-side, separately tested. Its inverse is *resting a bid*, i.e. maker capture, which is graveyard
#1 and #33, killed twice. The paired-complement table I built from the cache makes this explicit:

| unit | EV(yes-taker) | EV(no-taker) | sum |
|---|---:|---:|---:|
| KXHIGHNY\|B | −6.36c | −2.57c | **−8.93c** |
| KXHIGHCHI\|B | −6.27c | −1.06c | **−7.32c** |
| KXHIGHAUS\|B | −6.11c | −0.90c | **−7.01c** |
| KXHIGHPHIL\|B | −5.90c | −0.31c | **−6.21c** |
| KXHIGHDEN\|B | −4.90c | −1.69c | **−6.59c** |
| KXDOGED\|T | −6.07c | −4.42c | **−10.48c** |

Both sides negative, summing to −6 to −10c — that sum *is* the round-trip taker spread plus fee.
Every KX-era survivor is of this shape. The screen re-measured the cost of crossing, at scale,
across the whole eligible universe. That is a real and useful measurement; it is not an edge.

**Mechanism 2 — a bar-design flaw that made 17 survivors structurally dead on arrival.** Stage 1
gates on two-sided |t|, but Stage-2 clause 5 requires a Wilson 95% lower bound on the *win rate*
strictly above the fee-inclusive breakeven — which a negative-EV unit-side can never satisfy. So the
17 negative survivors were incapable of passing from the moment they survived, and 8 of them
consumed advancement slots under the k = 10 cap. **This run lost nothing** (the only other positive
survivor, `U3|T/no` at rank 14, has zero validation-window data anyway), but the flaw is real: a
genuine positive-EV candidate ranked 11th or lower by |t| would have been squeezed out by dead
negatives. The bars stand for this funnel; the next registration must rank Stage-1 advancement on
signed t, not |t|.

**Mechanism 3 — both positive survivors are extinct series.** `INXD|T/yes` (t = +15.264, +12.67c
print / +52.42c contract) and `U3|T/no` (t = +5.823, +10.74c) are legacy pre-`KX` series. I verified
directly against the cached day aggregates that `INXD|T`, `INXD|B`, `U3|T`, `HIGHMIA|T`, `HIGHCHI|T`,
`NASDAQ100D|T`, `HIGHNY|B` and `INXW|B` have **zero rows** in the validation window. Five of the ten
advanced unit-sides returned Stage-2 INSUFFICIENT with total_n = 0. These edges are unfalsifiable in
this archive **by construction** — the instruments stopped trading before the frozen validation
boundary.

**Mechanism 4 — and the extinct positives are very probably artifacts anyway.** The `INXD|T/yes`
price-decile profile:

| decile (price) | n | EV/print | win rate |
|---|---:|---:|---:|
| 60–70c | 93 | +26.1c | 0.925 |
| **70–80c** | **100** | **+24.0c** | **1.000** |
| **80–90c** | **77** | **+13.8c** | **1.000** |
| 90–100c | 58 | +0.5c | 0.948 |

with the complementary `INXD|T/no` side at **exactly 0.000** in the same deciles. A deterministic
outcome at a 75c transacted price is the signature of prints landing in markets whose outcome was
already determined — the same stale/locked-print artifact family as graveyard #19, #20 and #34. The
frozen [0.03, 0.97] price band does not exclude an already-locked market trading at 0.85.
`U3|T/no` is the other familiar shape: 3,436 prints over 671 days (5/day), buying NO at a mean 14.9c
wins 53% for +36.9c/print — illiquid longshot bias, graveyard #30/#32 class, no capacity.

**Stage 2 (validation, read once).** 5 INSUFFICIENT (n = 0, extinct series), 5 FAIL. The
best-scoring candidate, `KXHIGHNY|B/yes`, cleared clauses 1–4 — validation mean −4.262c print /
−3.122c contract, day-clustered t = −4.626 (df=207) against a bar of 3.2723, 10/10 deciles
sign-stable, still −2.26c after dropping the 5 best calendar days — and died on clause 5 exactly as
the bar was designed to make it die. I reproduced that t to 4 dp from the cache. One genuine
fit→validation sign flip: `KXHIGHLAX|T/yes` goes −12.19c in FIT to +0.61c print-weighted in
validation with only 3/10 deciles sign-stable, and is correctly labelled a residual-conflation
artifact.

**Divergences, reported not waived.**
- **Clause 6 (live settlement reconciliation) is infrastructure-blocked and, as written, makes
  U1's Stage 2 unpassable on archive data.** 0/220 sampled validation tickers return a live record
  (retention wall; a market closing the day before the run resolves fine). The builder scored it
  FAIL literally, improvised no waiver, and verified it was never the *sole* failing clause for any
  candidate — that is the correct handling under non-negotiable 1. But the structural consequence
  must be stated: any unit whose validation window is more than ~6 months old can never satisfy
  clause 6. **This must be fixed in a future registration, before the run, not waived after it.**
- Market-admission ticker/event_ticker mismatches measured 2,386 vs the registration's 2,474.
  Reported; does not change m_units = 473, which reproduced exactly.
- Stage-2 clause 1 reads "mean EV ≥ +0.50 c/ct, SAME SIGN as Stage 1" — internally contradictory for
  a negative Stage-1 unit. The implementation resolved it as |EV| ≥ 0.50 with sign match, i.e. the
  *lenient* reading. Under the strict literal reading every negative candidate fails clause 1
  immediately, so **U1 is FAIL a fortiori** and the interpretation does not affect the verdict.

**What U1 actually established.** REOPENABLE.md named the executable-price universe screen as
priority 2 and the single biggest methodological gap in the repo — every prior screen ran on
`last_price` or mid and lost its survivors at the realistic-entry retest. It has now been run
properly: all 16 shards, true crossing prices, whole eligible universe, Bonferroni-correct.
**Result: the universe contains no positive-EV taker unit-side that survives into a temporally
disjoint validation window at the corrected bar.** The screen has power — 19 survivors against 0.002
expected under the null is not chance — and what it detected is the taker spread. That is a real
negative and it closes the methodological hole rather than leaving it open.

---

### 3.3 J1 — KXJOBLESSCLAIMS weekly-relist fade (reopen of #24) → **INSUFFICIENT**

**Measured.** All 16 shards via the shared M1 tape pull; 9,812 KXJOBLESSCLAIMS trades. Markets from
all 4 shards, `series_key == 'KXJOBLESSCLAIMS'` exact. 24 events, 2025-06-12 .. 2026-02-05.
FIT = first 8 ordinal events, VALIDATION = remaining 16.

**Honest numbers.** FIT theta grid {0.15, 0.25, 0.35} — identical at every cell: **n_entries = 1,
n_Thursdays = 1, mean net +$0.53/ct, t undefined** (fewer than 2 populated clusters). Only 1 of the
7 anchorable FIT Thursdays produces a qualifying entry, at any theta.

**Mechanism.** The frozen selection rule is "pick the theta with the highest FIT t". With t undefined
at all three cells the rule cannot be executed, and this is *not* the spec's self-kill clause
(t ≤ 0 presumes t is defined). No substitute rule was improvised; validation was never read. That is
the correct call under non-negotiable 1. The underlying cause is entry starvation on an illiquid
relist — skip ledger (263 entries): 192 live-reconciliation-unavailable, 32 "no print within 6h of
open", 20 "result unavailable (neither live nor archive)", 14 "anchor ambiguous", 5 "no prior event
to anchor on".

**Divergences.** (a) The spec's literal FIT date span 2025-06-12..2025-07-31 holds only 7 events —
there is no `KXJOBLESSCLAIMS-25JUN19` — so the ordinal rule (first 8 chronological) was used, which
is the only reading consistent with the spec's own "max 16 available" validation clause. No bar
moved. (b) The funnel registration froze "15 Thursday clusters exactly, so 2.8640 (df=14) is THE
number"; the archive splits 8/16, so the realized validation df would have been 15 and the exact bar
2.8366. Reported; nothing reached either number. (c) All 212 live settlement lookups returned 404,
so the reported "0 disagreements" means **0 possible comparisons, not agreement**; 20 markets have
no settlement source at all and were logged as such rather than guessed.

**Graveyard #24 is not closed.** Its kill reason has changed, though: it died against the live-API
retention wall, and the archive removes the wall but not the illiquidity.

---

### 3.4 D1 — directional SPECs 1/3/7 at archive n (reopen of #3/#5/#9) → **INSUFFICIENT** ×3

**Measured.** All 16 trade shards + all 4 markets shards. 5,817,335 trades, 18,230 tickers, span
2024-10-24..2026-01-28. Eight city series matched **exactly** (`KXHIGHNY`, `KXHIGHCHI`, `KXHIGHAUS`,
`KXHIGHMIA`, `KXHIGHDEN`, `KXHIGHPHIL`, `KXHIGHLAX`, `KXHIGHHOU`) — not a `KXHIGH%` prefix, which is
the family-conflation bug that killed #34. 19,088 rungs parsed, 0 unparseable. Per-city chronological
60/40 TRAIN/TEST (city date ranges differ; KXHIGHHOU has only 70 settled dates).

**Honest numbers.**

| Leg | Floor | Achieved | Verdict |
|---|---|---|---|
| SPEC 1 (horizon-conditional calibration fade) | n ≥ 200, ≥40 date clusters | **n = 5, 5 clusters** (isotonic fit n=565 on TRAIN) | INSUFFICIENT |
| SPEC 3 (thin-book longshot fade) | n ≥ 300 | **n = 12, 11 clusters** | INSUFFICIENT |
| SPEC 7 (salient-threshold anchoring) | ≥3 of 5 price bins with ≥20 per (bin, salience) cell | **0 of 5 bins** (original kill mode was 2 of 5); TRAIN n_obs = 260 | INSUFFICIENT — TRAIN self-kill, TEST never opened |

**Mechanism — this is the transferable finding of the whole funnel.** REOPENABLE.md's premise was
that the archive holds ~100× the data the original kills reached (3,279 KXHIGH events, 19,355
settled markets). **That is true of coverage and false of usable sample.** D1 spans ~3,300 city-days,
roughly 50× the original SPEC 1 window, and produced *fewer* qualifying entries than the original
study did: **5 vs 17** for SPEC 1, **12 vs 84** for SPEC 3.

The reason is precisely the methodological upgrade this funnel exists to exploit. The original
studies triggered on quoted bid/ask snapshots. D1 requires an **actually-transacted crossing print**
in [H−30m, H], where H = close_time − 2h. Measured:

- **4,188 of 5,034 TEST bracket rungs (83%)** have no ask print in that window.
- **3,524 of 3,784 TRAIN threshold rungs (93%)** have no print in that window for SPEC 7.

Executable-price discipline and sample size are in direct tension on illiquid rungs, and on KXHIGH
ladders the tension is roughly 20:1. This is the same wall U1 hit from the other direction, and it
is the honest reason these three graveyard entries cannot be closed with this archive under these
entry rules.

**Minor reporting defects (disclosed, not hidden).** SPEC 7's 3,524 drops live in a `train_drop`
dict rather than in its 56-entry skip-ledger list; SPEC 1's and SPEC 3's ledgers have different
scopes (SPEC 1 logs all TEST bracket rungs, SPEC 3 only post-trigger candidates), so their counts
are not comparable to each other. Neither affects a verdict.

**Graveyard #3/#5/#9 remain INSUFFICIENT**, with their status unchanged but their reason now
measured: it is not "the market is too young", it is "these entry rules do not produce executable
fills at any archive depth."

---

## 4. RESEARCH_LEDGER graveyard rows (ready to paste into §3)

```
| 38 | Executable-price universe screen on reconstructed crossing prices from `taker_side` (473 eligible units × 2 taker actions, two-stage) | REOPEN_FUNNEL.md / `out/spec_U1.json` | CONFIRMED FAIL | All 16 shards, 154.5M trades scanned / 17.0M qualifying. Stage 1 (FIT, α=0.0125/946=1.32e-5, day-clustered, exact t at own df): 19 survivors of 946 hypotheses — but only 143 unit-sides met the ≥2,000-print/≥40-day floor, so the effective screen is 143 wide. **17 of 19 survivors are NEGATIVE-EV.** Stage 2 (VALIDATION, k=10, α=0.00125, bar \|t\|≥3.2723 at df=207): 5 INSUFFICIENT (validation n=0), 5 FAIL, **0 PASS**. Best candidate KXHIGHNY\|B/yes: validation EV −4.262c print / −3.122c contract, t=−4.626, 10/10 deciles sign-stable, −2.26c after dropping 5 best days — clears clauses 1–4 in the *losing* direction and dies on clause 5 | Two structural mechanisms, both verified against the cached aggregates. (1) **A negative-EV taker unit-side is the spread, not a signal**: paired complements are both negative and sum to −6 to −10c (KXHIGHNY\|B yes −6.36c / no −2.57c; KXHIGHCHI\|B −6.27/−1.06; KXDOGED\|T −6.07/−4.42) — that sum IS the round-trip taker cost. Its inverse is resting a bid, i.e. maker capture, already dead twice (#1, #33). (2) **Both positive survivors are extinct instruments**: INXD\|T/yes (t=+15.26) and U3\|T/no (t=+5.82) are pre-KX legacy series with ZERO validation-window rows (last INXD print 2024-12-31, last U3 2024-11-01) — unfalsifiable by construction. And they are probably artifacts anyway: INXD\|T/yes wins at rate exactly 1.000 in the 70–80c (n=100) and 80–90c (n=77) deciles with the complement at exactly 0.000, the already-locked/stale-print signature of #19/#20/#34; U3\|T/no is 5 prints/day buying NO at 14.9c for 53% wins, the illiquid-longshot shape of #30/#32. **Closes REOPENABLE.md priority 2**: the executable-price screen is now run properly and the universe contains no positive-EV taker unit-side that survives into disjoint validation. Two registration defects to fix before any re-run: Stage-1 advancement ranks on \|t\| so 8 of 10 slots went to structurally-unpassable negatives; and clause 6 (live settlement reconciliation) is unsatisfiable for any validation window >~6 months old under Kalshi's retention wall (0/220 sampled tickers resolve) |
| 39 | Macro-surprise pass-through drift into the still-open next-meeting Fed-decision market (REOPEN of #29) | REOPEN_FUNNEL.md / `out/spec_M1.json` | INSUFFICIENT — **NOT TESTED**, not underpowered-negative | All 16 shards, 895,660 trades / 2,213 tickers. 112 family release events in window, FIT=40 / VAL=72. FIT theta grid: θ=0.5 → 2 trades / 2 clusters / −3.0c/ct / t=−3.0; θ=1.0 → 1 trade, t undefined; θ≥1.5 → 0 trades. σ_family undefined for JOBLESS, PCE and ISM (0 computable FIT observations each). Bar \|t\|≥2.5442–2.6189 never reached — validation never opened | Builder returned NULL via a "self-kill, no signal" gate; **verifier overrode to INSUFFICIENT** on two independent grounds. (1) The self-kill statistic contains zero information about the hypothesis: both FIT trades have no opposite-side print in the exit window [t0+60m,t0+120m], so gross ≡ 0 and net = −(entry fee + exit fee) = −4c/−2c BY CONSTRUCTION — t=−3.0 is a restatement of `ceil(7p(1−p))`, negative under any hypothesis. The frozen trigger also reads "all FOUR theta cells ≤0" and only one cell has a defined t. (2) The min-n gate was unreachable ex ante: JOBLESS(22)+PCE(12)+ISM(7)=41 of 72 validation events can never be scored, leaving a hard ceiling of 31 < the frozen floor of 40. Two further defects mean the computed FIT is not the specified FIT: a silent `TN<x>` negative-strike sign mis-parse (48 markets; 3 of 4 GDP FIT surprises contaminated, one outright sign flip u −0.022→+0.045; invisible to the ledger because the regex matched), and an unregistered all-rungs-must-have-a-pre-t0-print filter that kills 95 of 104 FIT ladders (91%), every one of them via rungs that never traded anywhere in the archive. **#29 remains genuinely open — the drift was never measured once.** The most interesting measured fact: both events that reached entry produced no tradeable exit at the 60–120 min horizon |
| 40 | KXJOBLESSCLAIMS weekly-relist fade (REOPEN of #24) | REOPEN_FUNNEL.md / `out/spec_J1.json` | INSUFFICIENT — **NOT TESTED** | 24 archive events 2025-06-12..2026-02-05, FIT=8 / VAL=16, 9,812 trades from all 16 shards. FIT theta grid {0.15,0.25,0.35} identical at every cell: n_entries=1, n_Thursdays=1, mean net +$0.53/ct, **t undefined** (<2 populated clusters). Bar 2.8640 (df=14 as registered; realized df would be 15 → 2.8366) never reached; validation never opened | Entry starvation, not a negative result. Only 1 of 7 anchorable FIT Thursdays yields a qualifying entry at any theta; skip ledger (263): 192 live-reconciliation-unavailable, 32 "no print within 6h of open", 20 "result unavailable", 14 "anchor ambiguous", 5 "no prior event to anchor on". The frozen "highest FIT t" selection rule is unexecutable when t is undefined, and this is NOT the spec's self-kill clause (t≤0 presumes t defined) — no substitute rule was improvised. Settlement note: all 212 live lookups 404'd, so the reported "0 disagreements" is 0 POSSIBLE comparisons, not agreement. **#24's kill reason has changed**: it died against the live-API retention wall; the archive removes the wall but not the illiquidity |
| 41 | Directional SPECs 1 / 3 / 7 re-run at full archive n, on executable crossing prints (REOPEN of #3/#5/#9) | REOPEN_FUNNEL.md / `out/spec_D1.json` | INSUFFICIENT ×3 — **NOT TESTED** | All 16 shards, 5,817,335 trades / 18,230 tickers, 8 city series matched EXACTLY (not `KXHIGH%`), 19,088 rungs, 0 unparseable, per-city chronological 60/40 split. SPEC 1: TEST n=5 / 5 clusters vs floor ≥200 / ≥40 (original kill reached n=17). SPEC 3: n=12 / 11 clusters vs floor ≥300 (original reached n=84). SPEC 7: 0 of 5 price bins reached MIN_GROUP_N=20 per (bin,salience) cell vs a 3-of-5 requirement (original reached 2 of 5); TRAIN self-kill, TEST never opened. α/leg = 0.0125/3 = 0.0041667, bars \|t\|≥2.9334 (df=99) / 2.9015 (df=184) — no leg reached its min-n floor | **REOPENABLE.md's ~100× coverage premise is true of coverage and false of usable sample.** D1 spans ~50× the original SPEC 1 window and produced FEWER qualifying entries (5 vs 17; 12 vs 84). The cause is the methodological upgrade itself: the original studies triggered on quoted bid/ask snapshots, D1 requires an actually-transacted crossing print in [H−30m,H]. Measured, 4,188 of 5,034 TEST bracket rungs (83%) and 3,524 of 3,784 TRAIN threshold rungs (93%) have no such print. Executable-price discipline and sample size are in direct tension on illiquid rungs, ~20:1 on KXHIGH ladders. #3/#5/#9 keep their INSUFFICIENT status, but the reason is now measured: not "the market is too young", but "these entry rules do not produce executable fills at any archive depth" |
```

**Summary-of-graveyard lines to amend:**
- `**Refuted (actively disproven):**` — append `, executable-price universe screen across the whole eligible unit universe (#38)`.
- `**Insufficient/inconclusive (underpowered or data-walled, not disproven):**` — append
  `; macro-surprise #29 re-attempt (#39, NOT TESTED — self-kill statistic carried no information and the min-n gate was unreachable ex ante); jobless relist #24 re-attempt (#40, NOT TESTED — 1 qualifying entry in 7 FIT Thursdays); directional SPECs 1/3/7 re-attempt on executable prints (#41, NOT TESTED — 83–93% of rungs have no crossing print in the signal window)`.
- Header count: **37 tested / 37 dead → 41 tested / 41 dead.**

---

## 5. What remains genuinely open, and what it would take to close it

Stated with the distinction the brief demands: **disproved** ≠ **underpowered** ≠ **not attempted**.

### Newly CLOSED (a real negative, record it as one)

**The executable-price universe screen.** REOPENABLE.md called this priority 2 and "the
methodological hole that killed the most studies". It has now been run on all 16 shards, on true
crossing prices reconstructed from `taker_side`, across the full eligible universe, Bonferroni-correct
at α = 1.32e-5 with a disjoint validation stage. At the corrected bar, **the universe contains zero
positive-EV taker unit-sides that survive into a temporally disjoint validation window.** The screen
demonstrably has power (19 survivors vs 0.002 expected under the null), and what it detected was the
taker spread. Do not re-run this design. What it *did not* test: maker-side EV (dead twice already),
conditional/signal-gated entries (this is an unconditional screen by construction), and units below
the 2,000-print / 40-day floor (803 of 946 unit-sides, i.e. the illiquid tail — where the graveyard
says edges "appear" and capacity does not exist).

### Genuinely OPEN — not tested, not disproved

**(a) #29 macro-surprise pass-through drift.** Nothing in this run bears on the hypothesis. To close
it, in this order:
1. **Cheapest and decisive first: a mechanism preflight on EXIT-print availability.** Both M1 events
   that reached entry produced *no opposite-side print* at the 60–120 minute horizon. Count
   two-sided prints in [t0+60m, t0+120m] across all 22 settled FEDDECISION/KXFEDDECISION events.
   Runs in minutes off the existing local cache. **If the Fed-decision tape has no two-sided prints
   at a 1–2h horizon, the strategy is structurally dead and no parsing fix matters.** Do this before
   re-registering anything.
2. Sign-correct strike parsing off `yes_sub_title` ("Above −0.6%"), not the ticker suffix — `TN<x>`
   means negative. 48 markets currently mis-signed.
3. A *registered* rule for partially-printed ladders (a declared minimum rung coverage, e.g. ≥60% of
   rungs with a pre-t0 print), replacing the current unfrozen all-or-nothing filter that kills 91%
   of FIT ladders on rungs that never traded at all.
4. Move the fit/validation boundary or shrink the family set. The frozen FIT window (pre-2025-01-01)
   predates KXJOBLESSCLAIMS (starts 2025-06-12) and KXISMPMI (2025-04-01) entirely, so σ_family is
   undefined for half the registered universe. Either fit σ on a later window (and re-cut
   validation), or register only CPI / EMPLOYMENT / GDP / PCE and accept the smaller family count.
   Note this makes the ≥3-families clause tight, so re-do the power arithmetic *before* freezing.

**(b) #24 jobless relist.** Not tested. The retention wall is gone; the illiquidity is not.
Cheapest decisive test: count two-sided prints in the first 6h after open for each of the 24 events.
Minutes off the existing cache. If the answer is "≤1 event has a fillable entry", the reopen is
dead on frequency and should be moved from "insufficient" to "structurally closed" — which is a
better outcome than leaving it nominally open forever.

**(c) #3/#5/#9 directional SPECs 1/3/7.** Not tested at executable prices; the original quote-based
kills stand exactly as they were. The binding number to design against is the measured 83% (bracket)
/ 93% (threshold) no-print rate in [H−30m, H]. To close: either pre-register a wider signal window
(e.g. last crossing print at or before H with no 30-minute cap) and accept the staleness that
introduces — declaring the staleness bound in advance — or accept that these rules are unfillable
and close them on market-structure grounds. Family prior remains poor; REOPENABLE.md already ranked
this lowest priority and nothing here improves it.

### NOT open, do not reopen

**U1's extinct positives** (`INXD|T`, `U3|T`, `HIGHMIA|T`, `NASDAQ100D|T`, `HIGHCHI|T`). Unfalsifiable
in this archive by construction — the instruments stopped trading before the validation boundary.
Their successor `KX*` series were separately tested in the same screen and did not survive Stage 1.
The decile profiles are the already-locked-print and illiquid-longshot signatures already in the
graveyard three times over. There is no follow-up here worth running.

**Clause-6-style live settlement reconciliation on archive-era data.** Structurally impossible:
0/220 sampled tickers resolve; every archived-era ticker 404s while a current-week ticker resolves
fine. This is a fact about Kalshi's retention window, confirmed independently in three of the four
specs. Any future registration that includes a live-reconciliation clause must scope it to markets
closing within the retention window, or drop it — it cannot be waived after a run.

---

## 6. If any spec passed

**None did. 0 of 4.** There is no positive result in this funnel requiring an artifact analysis, and
no follow-up test is warranted to confirm a pass, because there is no pass.

For completeness, the closest thing to a positive — and it is not close, because it never reached a
validation stage — was U1's `INXD|T/yes` at Stage-1 t = +15.264, +12.67c/print. It is reported here
as **UNVALIDATABLE, PROBABLE ARTIFACT**, not as a candidate:

- *What would have to be true for it to be real:* that legacy `INXD` threshold rungs were
  systematically underpriced on the YES side by ~13c/print over 335 trading days, and that the
  effect is a property of the instrument rather than of when the prints landed.
- *Why it is probably not:* win rate is **exactly 1.000** in the 70–80c decile (n=100) and **exactly
  1.000** in the 80–90c decile (n=77), with the complementary side at exactly 0.000 — deterministic
  outcomes at non-deterministic prices, which is the already-locked/stale-print signature of
  graveyard #19/#20/#34. The 4× gap between contract-weighted (+52.4c) and print-weighted (+12.7c)
  EV points the same way: a few large prints dominate.
- *Cheapest decisive test, if anyone insists:* for every `INXD|T` print in the 70–90c band, measure
  the time from the print to market close and whether any subsequent print in the same market ever
  crossed back through the price. Locked markets show a one-way ratchet with no crossing-back and a
  short residual life. That is one query against the already-cached local tape and would settle it
  in minutes. **It should not be run**, because even if the effect were real the instrument has not
  traded since 2024-12-31 and there is nothing to deploy against.

---

## 7. One-paragraph honest summary

Four specs, all pre-registered before any test data was read, all bars frozen and none moved. Three
never reached their bar: M1 and J1 because their frozen selection rules could not execute on the
samples the archive actually yields, D1 because 83–93% of the rungs its entry rule targets have no
transacted print in the signal window. The fourth, U1, reached its bar cleanly and returned zero
passes out of 946 hypotheses — its 19 highly significant survivors are, on inspection, 17
measurements of the taker spread and 2 extinct instruments with artifact-shaped decile profiles.
The one thing this funnel genuinely closed is the methodological gap it was built to close: an
honest executable-price screen across the whole eligible universe finds no positive-EV taker edge
surviving into disjoint validation. The three graveyard reopens (#29, #24, #3/#5/#9) are still open
in the strict sense that they were never tested — and the measured reason they could not be tested
(entry rules that do not produce executable fills) is more useful than another underpowered negative
would have been. **41 tested, 41 dead.**

---

*Artifacts: `venue_expansion/out/spec_{M1,U1,J1,D1}.{json,md}`; caches under
`venue_expansion/cache/{prereg,M1,J1,D1}/` (gitignored). No commits, no branch changes, no live-path
files touched.*
