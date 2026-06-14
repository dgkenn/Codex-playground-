# EDGE OPTIMIZE — pushing the Kalshi 15-min BTC maker-box net/box higher

Harness: `edge_optimize_study.py`, reusing the **validated** `pair_gate_study.walk_gate /
opening_fill_table` net-walk and box sim. BTC 15m, 916 windows, IS = first 60% (549) /
OOS = last 40% (367). Disposal = `capcross` (early-cross unless the lock is worse than the
give-cap, then hold). **Backtests SCREEN** — the fill model is optimistic on strands, so
treat strand-side gains as directional and require IS/OOS stability before believing them.

## Validated baseline (reproduced)
`depth>=33000 + k<=10 + |sig|<10`, capcross give-cap 15c.

| split | trade% | strand% | box edge | **net/box** | net/win | Sharpe |
|------|-------:|-------:|--------:|-----------:|--------:|------:|
| FULL | 86.0 | 1.9 | +0.499c | **+0.467c** | +1.528c | +0.230 |
| IS   | 83.2 | 1.3 | +0.489c | +0.468c | +1.325c | +0.244 |
| OOS  | 90.2 | 2.7 | +0.511c | +0.466c | +1.807c | +0.225 |

Matches the established +0.46c, IS==OOS. This is the reference for every delta below.

---

## SWEEP 1 — Depth threshold (k<=10, |sig|<10, cap 15c)

| depth | trade% | strand% | box edge | net/box | net/win | boxes | total cents | IS/OOS net/box |
|------|-------:|-------:|--------:|-------:|--------:|------:|-----------:|:--------------|
| 15k | 99.7 | 4.4 | +0.308 | +0.271 | +1.535 | 5163 | +1401.5 | +0.179 / +0.396 |
| 25k | 95.9 | 3.0 | +0.408 | +0.372 | +1.609 | 3799 | +1412.4 | +0.310 / +0.444 |
| **33k** | 86.0 | 1.9 | +0.499 | **+0.467** | +1.528 | 2580 | +1203.7 | +0.468 / +0.466 |
| 50k | 51.9 | 1.9 | +0.474 | +0.411 | +0.778 | 899 | +369.7 | +0.423 / +0.403 |
| 75k | 13.9 | 0.0 | +0.460 | +0.460 | +0.608 | 168 | +77.2 | -0.118 / +0.671 |

- **net/box-maximizing point is 33k** (+0.467c). Going lower (15-25k) trades more volume but
  net/box collapses because strand rate rises and box edge erodes (thinner books pair worse).
- **Total-cents-maximizing point is ~25k** (+1412c, marginally above 15k's +1401c and 33k's
  +1204c) — but that buys ~+0.21c more total at the cost of -0.10c net/box and 3.0% strand.
- 50k/75k buy nothing: net/box flat-to-down and volume falls off a cliff. **75k is IS/OOS
  unstable** (IS -0.118 vs OOS +0.671 — a trade-count artifact, only 168 boxes). 
- **Verdict: 33k is the net/box and net/win optimum.** It is not too high. If you want raw
  $ throughput and can tolerate 3% strand, 25k is the alternative, but it is *lower* net/box.

## SWEEP 2 — Give-cap x early-cross disposal

| disposal | net/box | net/win | IS/OOS net/box |
|---------|-------:|--------:|:--------------|
| cap 8c  | +0.464 | +1.518 | +0.468 / +0.460 |
| cap 10c | +0.464 | +1.518 | +0.468 / +0.460 |
| cap 15c | +0.467 | +1.528 | +0.468 / +0.466 |
| cap 20c | +0.467 | +1.530 | +0.468 / +0.467 |
| pure HOLD | +0.456 | +1.492 | — |
| pure EARLY (always cross) | +0.467 | +1.530 | — |

Residual stranded legs (n=136): HOLD mean -6.44c / worst -95.6c; EARLY mean -6.81c /
worst -87.3c. **The disposal knob barely moves net/box** (≤0.011c) because the gate already
cut strands to 1.9% — there is almost nothing left to dispose. Cheapest disposal for the
residual is **early-cross (cap >= 15c ≈ always-cross)**: it caps the worst single lock at
-87c vs HOLD's -96c and is +0.011c/box better than pure-hold. Keep **15c**; 20c is identical;
sub-10c starts re-holding the deep losers and gives back the gain. **No meaningful edge here.**

## SWEEP 3 — k-slot x |sig| (depth>=33k, cap 15c)

| config | trade% | strand% | box edge | net/box | net/win | IS/OOS net/box (gap) |
|-------|-------:|-------:|--------:|-------:|--------:|:--------------------|
| k<=9  \|sig\|<8  | 82.1 | 0.8 | +0.486 | +0.469 | +1.330 | +0.480/+0.458 (+0.022) |
| k<=9  \|sig\|<10 | 83.6 | 1.0 | +0.466 | +0.449 | +1.342 | +0.424/+0.474 (-0.050) |
| k<=10 \|sig\|<8  | 84.2 | 1.7 | +0.519 | **+0.485** | +1.508 | +0.523/+0.447 (+0.075) |
| **k<=10 \|sig\|<10** | 86.0 | 1.9 | +0.499 | +0.467 | +1.528 | +0.468/+0.466 (+0.002) |
| k<=10 \|sig\|<12 | 87.6 | 2.5 | +0.500 | +0.450 | +1.549 | +0.430/+0.470 (-0.039) |
| k<=11 \|sig\|<8  | 86.8 | 2.6 | +0.440 | +0.370 | +1.235 | +0.362/+0.380 (-0.018) |
| k<=11 \|sig\|<10 | 88.8 | 3.3 | +0.431 | +0.355 | +1.254 | +0.318/+0.393 (-0.075) |
| k<=11 \|sig\|<12 | 90.1 | 4.0 | +0.450 | +0.360 | +1.341 | +0.313/+0.408 (-0.095) |

- **k<=11 is strictly worse** on every metric (net/box -0.10c, strand doubles, Sharpe halves):
  catastrophic last-minute strands confirm k<=10 is the right cap. **k<=9 over-trims** volume
  for no net/box gain (+0.469 vs +0.467, within noise).
- **|sig|<8 helps a little**: `k<=10 |sig|<8` gives **+0.485c net/box** (+0.018c vs baseline),
  strand 1.7%, keeps 84% volume — tighter |sig| screens out the few directional-spike opens.
  BUT it is **mildly IS/OOS unstable** (IS +0.523 / OOS +0.447, gap +0.075c) — the gain lives
  in-sample. Treat as a *soft, screen-only* improvement, not robust.
- **Most IS/OOS-stable cell is the baseline k<=10 |sig|<10** (gap +0.002c). 

## SWEEP 4 — Edge-proportional sizing on clean boxes (gate fixed, cap 15c)

Paired boxes are ~risk-free +0.50c, so concentrate capital on the deepest/widest. Size the
opening leg, cap at 3x. **net/UNIT = total pnl / total contracts deployed is the unbiased
risk-free-capture metric** (net/box and net/win inflate mechanically with size).

| sizing | net/box | net/win | **net/unit** | Sharpe |
|-------|-------:|--------:|------------:|------:|
| flat 1x (ref) | +0.467 | +1.528 | +0.467 | +0.230 |
| size~margin (spread, 1-3x) | +0.525 | +1.719 | +0.513 | +0.194 |
| size~depth (33k ref, 1-3x) | +0.725 | +2.373 | **+0.493** | +0.231 |

IS/OOS for size~depth: net/unit IS +0.464 / OOS +0.520 (stable).

- **Sizing genuinely raises per-unit capture**: depth-sizing +0.493c/unit (+0.026c), spread-
  sizing +0.513c/unit (+0.046c) — wider-spread boxes lock in more, deeper books pair more
  reliably, so up-sizing them is +EV and IS/OOS-stable. net/win rises to +2.37c but that is
  partly mechanical leverage; the honest number is **net/unit +0.49–0.51c**.
- **Caveat:** the +0.046c from spread-sizing comes with a Sharpe drop (+0.194 vs +0.230) —
  concentration raises per-window variance. Capacity cap (3x, <= displayed depth) keeps it
  realistic. This is the **most robust real improvement** found, but modest.

## SWEEP 5 — Price-region band on top of depth gate

| band | trade% | strand% | box edge | net/box | net/win | IS/OOS net/box |
|-----|-------:|-------:|--------:|-------:|--------:|:--------------|
| all (0-1) | 86.0 | 1.9 | +0.499 | +0.467 | +1.528 | +0.468/+0.466 |
| balanced .35-.65 | 49.3 | 0.0 | +0.189 | +0.189 | +0.389 | -0.003/+0.350 |
| **balanced .40-.60** | 38.9 | 0.0 | +0.495 | +0.495 | +0.848 | +0.461/+0.522 |
| favorite .55-.85 | 45.7 | 0.0 | +0.310 | +0.310 | +0.628 | +0.231/+0.392 |
| underdog .15-.45 | 52.1 | 0.6 | +0.475 | +0.458 | +0.971 | +0.567/+0.359 |
| extreme-out .25-.75 | 65.6 | 0.0 | +0.479 | +0.479 | +1.243 | +0.528/+0.436 |

- **The balanced .40-.60 band drives strand to 0.0% and net/box to +0.495c** (+0.028c vs
  baseline), IS/OOS-stable (+0.461/+0.522). But it **halves volume to 39%** — net/win falls to
  +0.848c and total throughput drops sharply. The .31c "balanced-band" finding from BOX_YIELD
  reproduces *directionally* but the marginal net/box gain is small and volume-costly.
- The wider .35-.65 band is the *worst* (net/box +0.189, IS-unstable) — do not use it.
- **Verdict:** the price band adds a small, real net/box bump (+0.03c) only by discarding most
  volume; it is a net/box-per-box trick, not a throughput win.

## SWEEP 6 — Best combined (max net/box net of volume, IS/OOS-stable)

Criterion: maximize net/box s.t. OOS net/box>0, |IS-OOS gap|<0.25c, traded>=20%, strand<4%.
Top viable:

| config | net/box | IS/OOS (gap) | trade% | strand% | net/win | boxes |
|-------|-------:|:------------|-------:|-------:|--------:|------:|
| **d33k k10 s10 p.40-.60 c10** | **+0.495** | +0.461/+0.522 (0.061) | 38.9 | 0.0 | +0.848 | 610 |
| d33k k10 s8 pall c15 | +0.485 | +0.523/+0.447 (0.075) | 84.0 | 1.7 | +1.508 | 2396 |
| d33k k9 s8 pall c15 | +0.469 | +0.480/+0.458 (0.022) | 82.1 | 0.8 | +1.330 | 2132 |
| d33k k10 s10 pall c15 (baseline) | +0.467 | +0.468/+0.466 (0.002) | 86.0 | 1.9 | +1.528 | 2580 |

The mechanical net/box winner is the **.40-.60 band** (+0.495c) but at 39% volume. For an
edge that keeps throughput, **d33k k10 |sig|<8 (all prices, cap 15c)** gives +0.485c net/box
while keeping 84% volume and cutting strand to 1.7%.

### Recommended config (net/win net of volume, layering the robust pieces)
Keep the validated gate, add **depth-proportional sizing** (the only robust per-unit gain),
and tighten **|sig|<8**:

```
--pair-gate
--pair-min-depth 33000
--pair-k-max 10
--pair-max-sig 8
--dispose capcross
--dispose-max-give 0.15
--dispose-cross-s 15
--box-size-mode depth        # size ~ min(book_depth/33000, 3.0), capped <= displayed depth
--box-size-cap 3.0
```
This delivers net/box +0.485c (gate) with depth-sizing lifting **per-unit capture to ~+0.49c
and net/win to ~+2.3c** at 84% volume, IS/OOS-stable on the sizing axis. If you want the
purest risk-free per-box number and can give up volume, add `--pair-price-min 0.40
--pair-price-max 0.60` for +0.495c net/box at 0% strand / 39% volume.

---

## Net/box improvement vs current +0.46c (with IS/OOS)

| lever | net/box | Δ vs +0.467 | IS/OOS | robust? |
|------|-------:|-----------:|:------|:-------|
| baseline (validated) | +0.467 | — | +0.468/+0.466 | yes (reference) |
| give-cap tuning | +0.467 | +0.000 | +0.468/+0.467 | no edge to win |
| \|sig\|<8 | +0.485 | **+0.018** | +0.523/+0.447 | **soft** (IS-leaning) |
| price band .40-.60 | +0.495 | **+0.028** | +0.461/+0.522 | yes but -47% volume |
| depth-sizing (net/unit) | +0.493/unit | **+0.026/unit** | +0.464/+0.520 | **yes, modest** |

**Best honest improvement: ~+0.49–0.50c net/box (from +0.467c), i.e. +0.02–0.03c.**

## Robust vs overfit — honest note
- **Robust:** 33k is the depth optimum (not higher, not lower); k<=10 (not 11); give-cap 15c
  ≈ always-early-cross. Depth-proportional sizing genuinely lifts per-unit capture to ~+0.49c,
  IS/OOS-stable — the most defensible real gain, but small (+0.026c) and costs Sharpe.
- **Soft / screen-only:** `|sig|<8` (+0.018c) lives in-sample (IS +0.523 / OOS +0.447); the
  .40-.60 band gain (+0.028c) is real but buys it by discarding 47% of volume, so it raises
  net/box-per-box without raising throughput. Neither is a free lunch.
- **Overfit traps avoided:** depth>=75k looks fine on net/box (+0.460) but is IS/OOS unstable
  (only 168 boxes) — a trade-count artifact. The wide .35-.65 band is IS-negative — rejected.
- **CROSS-ASSET — the edge is BTC-specific.** With a per-asset relative gate (depth>=median,
  k<=10, |sig|<10): BTC +0.463c net/box (strand 1.9%), but **ETH -1.29c, SOL -2.41c, XRP
  -1.81c** with strand 9-14%. Alt books are 30-150x thinner in $; the maker box does not pair
  there and disposal dominates. Do not port this to alts.
- **Bottom line:** the validated +0.46c is near-optimal. Realistic upside is **+0.49–0.50c
  net/box** by adding depth-proportional sizing (robust) and optionally |sig|<8 (soft). The
  big-volume regime stays at depth>=33k, k<=10, |sig|<8–10, cap 15c. Backtests SCREEN —
  forward-validate the sizing and |sig|<8 before sizing up live.
