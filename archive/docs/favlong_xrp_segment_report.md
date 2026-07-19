# FAVLONG — XRP replication + segmentation study

Offline backtest research only. No live flag/switch/size changed. Config held fixed at the
validated setting throughout: `decision_t=720`, `edge=0.05`, `+Kalshi fees`, clean labels
(outcome = market's own terminal `mid_close>0.5`), fill at decision tick (`lag=0`).
Train = days ≤ 2026-06-30; Test(OOS) = days > 2026-06-30. Clustering unit = per-(asset,day)
mean $/ct; reported `t` is the day-clustered t across those asset-day means.

Caches: `win_xrp.pkl` built via `favlongshot_edge.build_asset('xrp')` into
`FAVLONG_CACHE=/tmp/favlong_cache` (36 days, 2921 windows). Segmentation uses an enriched
rebuild (`enr_{asset}.pkl`) that additionally keeps the window Unix timestamp `ws` for the
time-of-day cut; the standard `build_asset` drops it. The instrumented scorer reproduces the
node's published numbers (btc+eth+sol full-sample pooled t = **3.98**, matching the documented 3.99).

---

## Part 1 — XRP replication

### Per-asset (validated config)

| asset / set | n | mean $/ct | day-clust t | pos asset-days |
|---|--:|--:|--:|--:|
| btc ALL | 1417 | +0.0263 | 3.49 | 23/36 |
| btc train | 843 | +0.0175 | 1.72 | 13/21 |
| btc test (OOS) | 574 | +0.0392 | 3.34 | 10/15 |
| eth ALL | 1460 | +0.0165 | 1.64 | 23/36 |
| eth train | 864 | +0.0147 | 0.98 | 14/21 |
| eth test (OOS) | 596 | +0.0191 | 1.34 | 9/15 |
| sol ALL | 1491 | +0.0172 | 1.70 | 20/36 |
| sol train | 867 | +0.0221 | 1.80 | 12/21 |
| sol test (OOS) | 624 | +0.0105 | 0.44 | 8/15 |
| **xrp ALL** | **1588** | **−0.0056** | **−1.35** | **19/36** |
| **xrp train** | **955** | **−0.0097** | **−1.39** | **10/21** |
| **xrp test (OOS)** | **633** | **+0.0007** | **−0.32** | **9/15** |

(XRP row reproduced identically by the stock tool: `python favlongshot_edge.py xrp` → ALL n=1588, mean −0.0056, t=−1.35.)

**XRP does NOT replicate.** Full-sample is mildly negative (t = −1.35); the OOS mean is
essentially zero (+0.0007/ct, t = −0.32). It is a genuine null — the edge sign that btc/eth/sol
share independently does not appear on the 4th asset. Reported honestly, not massaged.

### Pooled per-(asset,day) — effect of adding XRP

| pool | n trades | asset-days | mean $/ct | day-clust t | pos |
|---|--:|--:|--:|--:|--:|
| btc+eth+sol — TEST(OOS) | 1794 | 45 | +0.0226 | **3.03** | 27/45 |
| **+xrp (4 assets) — TEST(OOS)** | 2427 | 60 | +0.0168 | **2.63** | 36/60 |
| btc+eth+sol — FULL | 4368 | 108 | +0.0199 | **3.98** | 66/108 |
| **+xrp (4 assets) — FULL** | 5956 | 144 | +0.0131 | **2.83** | 85/144 |

Adding a 4th, null asset **dilutes but does not break** the pooled edge: OOS t 3.03 → 2.63,
full t 3.98 → 2.83 (both still > 2), mean/ct down ~25–35%.

**Verdict (Part 1):** The mechanism is **not universal** across Kalshi 15m crypto binaries.
It is present and independently significant in btc/eth/sol but **absent in xrp**. A 4th positive
asset would have strengthened the mechanism claim; this negative one weakens the
"favorite-longshot bias in all crypto binaries" framing and argues the effect is
asset/microstructure-specific (xrp's book behaves differently near expiry). The 3-asset pooled
result stands on its own; xrp should be excluded from any sized universe unless/until it
forward-validates on its own.

---

## Part 2 — Segmentation (train-only selection, single OOS look)

**Scope:** pooled over the edge-bearing assets **btc/eth/sol** (xrp carries no edge to
concentrate). Base pooled: TRAIN +0.0181/ct (t 2.60, n 2574); TEST +0.0226/ct (t 3.03, n 1794).
For each dimension, the best segment is chosen **on TRAIN** (by train mean $/ct, min 30 trades &
5 asset-days), then that same segment's OOS is reported **once**. Median splits (depth, vol) are
computed on TRAIN only. **Total segments examined across all dimensions: 38** (4 moneyness + 2
depth + 2 vol + 24 hourly + 6 four-hour blocks).

"Entry" = executable cost of the position actually held: `ask` for a buy, `1−bid` for a sell.

### (a) Moneyness / entry-price bucket — 4 segments

| segment | TRAIN n | TR mean | TR t | OOS n | OOS mean | OOS t | OOS pos |
|---|--:|--:|--:|--:|--:|--:|--:|
| deep-underdog <0.15 | 1595 | −0.0016 | −1.25 | 1155 | +0.0064 | 1.04 | 24/45 |
| mid 0.15–0.40 | 617 | +0.0149 | 0.53 | 426 | +0.0099 | 0.74 | 22/42 |
| near-ATM 0.40–0.60 | 206 | +0.0990 | 3.48 | 118 | +0.1435 | 2.63 | 27/39 |
| **favorite ≥0.60 (best-on-train)** | 156 | +0.1256 | 4.16 | 95 | **+0.1258** | **2.24** | 26/36 |

Clean, monotone dose-response and **both rich buckets replicate OOS independently** (near-ATM
t 2.63, favorite t 2.24) — not the signature of a single lucky pick. Train-selected best
(favorite ≥0.60): **OOS +0.126/ct, t 2.24**.

Post-hoc (flagged) natural grouping of the two rich buckets, **entry ≥0.40**:
TRAIN +0.1105/ct (t 5.15, n 362) → **OOS +0.1356/ct, t 4.06** (n 213, 31/41 asset-days) — ~6× the
pooled mean/ct at higher significance. Dropping only the dead deep-underdog bucket (**entry ≥0.15**):
TRAIN t 2.96 → OOS +0.0518/ct, t 3.06.

### (b) Executable depth — 2 segments (TRAIN median = 100 ct)

| segment | TRAIN n | TR mean | TR t | OOS n | OOS mean | OOS t |
|---|--:|--:|--:|--:|--:|--:|
| **thin < median (best-on-train)** | 1283 | +0.0205 | 2.20 | 959 | **+0.0087** | **1.53** |
| thick ≥ median | 1291 | +0.0157 | 1.35 | 835 | +0.0385 | 2.87 |

Train picks "thin", which fails OOS (t 1.53). (Thick was stronger OOS but was not the
train-selected segment — reporting the honest single look.) No robust concentrator.

### (c) Realized-vol regime — 2 segments (TRAIN median σ ≈ 9e-5)

| segment | TRAIN n | TR mean | TR t | OOS n | OOS mean | OOS t |
|---|--:|--:|--:|--:|--:|--:|
| **low-vol < median (best-on-train)** | 1287 | +0.0188 | 1.29 | 1042 | **+0.0275** | **1.95** |
| high-vol ≥ median | 1287 | +0.0175 | 2.15 | 752 | +0.0157 | 1.18 |

Train-selected low-vol replicates weakly OOS (t 1.95). Modest, not a strong sizing lever.

### (d) Time-of-day, UTC hour — 24 segments

Best-on-train = hour 15 (TR +0.0699, t 0.50) → **OOS +0.0555/ct, t 1.56**. With 24 comparisons
and a train t of only 0.50, this is noise-selection. The coarser 6× four-hour-block cut
(6 segments) picks block 04–08 on train → **OOS −0.0024, t −0.35** (outright fails). Time-of-day
gives no robust concentrator.

### Segmentation verdict

The **only** dimension that yields a materially stronger, honestly train-selected, OOS-surviving
sub-population is **moneyness / entry-price**:

- **The edge is concentrated in near-ATM-to-favorite executable entries** (held-position cost
  ≥0.40). Train-selected favorite bucket: OOS +0.126/ct, t 2.24; near-ATM independently OOS
  t 2.63; their union (entry ≥0.40) OOS +0.136/ct, t 4.06 (31/41 asset-days). OOS
  return-on-cost is also higher there (+0.24/$ vs +0.10/$ for deep-underdog).
- **The deep-underdog (<0.15) trades carry essentially no edge** (TRAIN −0.0016, OOS +0.0064,
  t 1.04) — even though they are ~62% of all trades. This partially **contradicts the node's
  headline framing** ("buy the ~0.09 longshot"): mechanically, the profit comes from trades where
  the model pushes toward a *confident* outcome the book underprices (avg fair ~0.65 buys /
  ~0.35 sells), i.e. we hold the richer side — not from cheap-longshot buying.

**Is a segment worth concentrating size?** Yes, cautiously: tilt size toward **entry ≥0.40**
(equivalently, drop the deep-underdog <0.15 trades). Caveats before acting: (1) it is only
~14% of trades (362 train / 213 test), so far fewer opportunities and more capital at risk per
contract; (2) the ≥0.40 *union* is a post-hoc grouping — the pre-registered single-bucket claim
(favorite ≥0.60, OOS t 2.24) is the conservative version; (3) depth/vol/time-of-day offer no
robust lever; (4) this is still backtest at recorded top-of-book — **forward-validation on the
charter gate (day-clustered t≥2 over ≥10 forward days) remains required** before any live sizing,
and the moneyside concentration should be part of what is forward-tested.
