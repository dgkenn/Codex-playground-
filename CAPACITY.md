# CAPACITY / SCALE — BTC 15-min pair-gated maker box

**Question:** the pair-gated maker-box edge is real and net-positive (+0.46c/box, strand 1.9%,
IS==OOS) at 1 contract/leg, but earns only ~$0.40–0.63/day at $10. **How does the edge degrade as
we scale per-leg size S, and what bankroll saturates the BTC 15-min book's capacity?**

**Verdict up front:** the BTC 15-min book is **too thin to scale the +0.46c edge into real money.**
The edge survives passively only because we rest ~1 contract and a crossing taker fills it. The
binding constraint is the **fill rate**: the median taker print that crosses and fills our resting
leg is only ~10 contracts, and matched-contracts-per-box **plateaus at ~26 no matter how large we
rest.** Sizing optimally (depth-proportional) the strategy tops out at **~$27/day gross**,
saturating at a **~$100 bankroll**. Capital beyond ~$100–$1k buys nothing — extra resting size just
strands or walks the book.

Method: tape replay of the validated gate `depth >= med(~33k) + k<=10 + |sig|<10`. 916 BTC
windows-with-fills over 17.0 days (~54 traded windows/day). **Backtests SCREEN only** — the tape
fill model is optimistic (we let each leg absorb up to **3×** the observed crossing-taker volume,
`fill_mult=3`), so the decay shown is a **lower bound**; live decay is worse. Script:
`capacity_scale_study.py`.

---

## 1. SIZE vs EDGE curve (flat per-leg size S, fill_mult=3)

| S (contracts/leg) | matched/box | clean edge $ | impact $ | strand $ | net $ | **net/box** | $/day |
|------:|------:|------:|------:|------:|------:|------:|------:|
| 1   | 1.0  | +12.48 | −0.00 | −1.70 | +10.78 | **+0.435c** | +0.63 |
| 2   | 1.9  | +24.52 | −0.00 | −2.84 | +21.68 | +0.875c | +1.27 |
| 5   | 4.2  | +50.69 | −0.00 | −2.51 | +48.17 | +1.944c | +2.83 |
| 10  | 7.0  | +79.07 | −0.00 | +1.44 | +80.51 | +3.249c | +4.73 |
| 25  | 12.7 | +132.29 | −0.00 | −26.72 | +105.57 | +4.260c | +6.20 |
| 50  | 17.8 | +185.60 | −0.00 | −26.82 | +158.78 | +6.408c | +9.32 |
| 100 | 22.3 | +219.75 | −0.00 | −109.69 | +110.05 | +4.441c | +6.46 |
| 250 | 26.2 | +221.50 | −0.00 | −509.41 | −287.90 | **−11.618c** | −16.90 |

**Where the edge decays:** total $/box keeps rising until **S≈50** ($9.32/day), then *falls* — at
S=100 net/box drops back to +4.4c and at S=250 it goes deeply negative (−11.6c). On the flat-S
curve the per-box edge halves/zeroes only at very large S (~127/129) because clean edge keeps
accruing on the ~26 matched contracts while impact bites; but **the real ceiling is reached far
sooner** because matched contracts saturate (next section).

The decisive number is **matched/box**: it climbs 1 → 7 → 17.8 → 22.3 → **26.2** and then stops.
Resting 250 contracts buys only ~26 matched — the other ~224 strand and get crossed out at a loss.

---

## 2. The TWO decay channels, isolated

| S | (a) FILL fraction `matched/(S·boxes)` | (b) impact c/contract | net/box (fill only) | net/box (both) |
|---:|---:|---:|---:|---:|
| 1   | 96.9% | 0.000c | +0.504c | +0.435c |
| 2   | 95.2% | 0.000c | +0.989c | +0.875c |
| 5   | 83.2% | 0.000c | +2.045c | +1.944c |
| 10  | 70.4% | 0.000c | +3.191c | +3.249c |
| 25  | 50.9% | 0.000c | +5.339c | +4.260c |
| 50  | 35.7% | 0.000c | +7.490c | +6.408c |
| 100 | 22.3% | 0.000c | +8.868c | +4.441c |
| 250 | 10.5% | 0.000c | +8.939c | **−11.618c** |

**(a) FILL-RATE decay is the dominant channel.** A resting maker leg of size S only fills to the
extent takers cross it. The crossing-taker volume (`tksize`) has median ~10, q75 ~29, q90 ~87. So
the fraction of intended size that actually matches collapses: **97% at S=1 → 51% at S=25 → 36% at
S=50 → 10% at S=250.** This is intrinsic — it has nothing to do with the book's displayed depth; it
is about how much *flow* arrives to lift our quote inside one 15-min window. This caps matched/box
at ~26 and is why $/day plateaus.

**(b) IMPACT decay is secondary but lethal at the tail.** Top-5 depth (median ~33k) is spread over
~5 one-cent levels, so completing/disposing modest size walks ≈0 levels — impact is ~0c/contract up
to S~50. But the *unmatched residual* (which grows with S) must be crossed out to dispose the
strand, and that residual walks the book: strand cost stays small to S≈50, then explodes
(−$110 at S=100, −$509 at S=250). Impact is the channel that turns the curve negative once fill-rate
has already left a large residual stranded.

Net: **fill-rate caps the upside; impact punishes the oversize residual.** Both worsen with S; the
crossover where they jointly kill the edge is at the **flat optimum S≈50** ($9.32/day, +6.4c/box).

---

## 3. Depth-conditional sizing: `S = clip(alpha · top5_depth, 1, cap)`

Because the gate already guarantees depth ≥ ~33k, size can scale with each window's displayed depth
instead of using a flat S. This **does capture more** than flat S — the right rule lifts $/day from
$9.32 (best flat) to **$27.28**:

| rule | matched/box | net $ | net/box | $/day |
|---|---:|---:|---:|---:|
| **BEST FLAT S=50** | 17.8 | +158.78 | +6.408c | +9.32 |
| S = 0.0005·depth | 12.4 | +175.47 | +6.881c | +10.30 |
| S = 0.001·depth | 17.5 | +306.76 | +12.030c | +18.01 |
| S = 0.002·depth | 22.1 | +360.29 | +14.129c | +21.15 |
| **S = 0.005·depth** | **26.1** | **+464.55** | **+18.218c** | **+27.28** |
| S = 0.01·depth | 27.5 | +194.51 | +7.628c | +11.42 |
| S = 0.02·depth | 27.6 | −1068.88 | −41.917c | −62.76 |

**Recommended rule: `S ≈ 0.005 × top5_depth` (≈ 0.5% of displayed depth, ~165 contracts at the
median 33k window).** It nearly **3×'s** $/day vs the best flat size and keeps net/box strongly
positive (+18.2c). Pushing harder (1%+ of depth) re-triggers the same fill-rate+impact collapse and
goes negative by 2% of depth. Depth-proportional sizing works because it puts more size only where
the window can actually absorb it; but it still hits the same ~26–27 matched/box wall.

---

## 4. $/day vs BANKROLL

A matched box ties up ~$1 of collateral per contract (YES buy + NO buy ≈ $1 total). A rational
operator sizes each window to the **profit-maximizing** size (the depth-proportional optimum), not
blindly to bankroll — extra resting size beyond the absorbable amount only strands (negative EV).
Peak working capital ≈ matched/box (~26) × boxes/window (~2.71) × $1 ≈ **$70 per (non-overlapping)
15-min window**, so a few hundred dollars already funds the optimum across the whole day.

| bankroll | best sizing | matched/box | $/day | annualized |
|---:|---|---:|---:|---:|
| $10 | flat S≈2 | 1.9 | +1.27 | +4647% |
| $100 | S=0.005·depth | 26.1 | **+27.28** | +9956% |
| $1,000 | S=0.005·depth | 26.1 | +27.28 | +996% |
| $10,000 | S=0.005·depth | 26.1 | +27.28 | +100% |
| $100,000 | S=0.005·depth | 26.1 | +27.28 | +10% |

**$/day CEILING ≈ $27/day (~$10k/yr gross), saturating at a ~$100 bankroll.** Beyond ~$100–$1k the
BTC 15-min book cannot absorb more maker size without strand+impact eating the edge. Annualized
return on capital is astronomical at small size precisely *because* capacity is tiny — it is a
nickel-grinder, not a capital sink.

Caveats that make even $27/day optimistic: (i) `fill_mult=3` is generous; at `fill_mult=1` matched/box
and $/day fall materially. (ii) The model ignores queue position (we assume our resting size is at
the touch and fully ahead of the crossing taker) and competition from other makers, both of which
reduce realized fill. (iii) No latency/cancel slippage. **Treat $27/day as a hard upper bound; live
is plausibly $10–20/day.**

---

## 5. VERDICT

- **The edge is real but the book is too thin to scale it into meaningful money.** The +0.46c/box
  edge does not "halve at a large S" in any useful sense — it is **fill-rate-capped**: matched
  contracts per box plateau at **~26** regardless of resting size (median crossing taker ~10).
- **Decay channels:** (a) FILL-RATE dominates — fill fraction 97%→51%→36%→10% from S=1→25→50→250;
  (b) IMPACT is ~0 to S≈50 then explodes on the unmatched residual, taking net/box negative by
  S≈250 (flat curve zero-crossing S≈129, but the economic optimum is far lower).
- **Best policy:** depth-proportional `S ≈ 0.005 × top5_depth` (~165 contracts at median depth),
  3× better than the best flat size (S≈50).
- **Capacity:** **$/day ceiling ≈ $27 gross (~$10k/yr), saturating at ~$100 bankroll.** A realistic
  haircut for queue/competition/`fill_mult=1` puts the live ceiling closer to **$10–20/day**.
- **Bottom line:** this is a **small, capacity-constrained nickel strategy** — fine as one sleeve of
  a multi-asset / multi-market book (ETH/SOL/XRP add parallel capacity), but **not a path to real
  money on BTC 15-min alone.** Scale by adding *markets*, not *size*.
