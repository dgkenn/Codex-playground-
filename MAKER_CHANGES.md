# 10 data-backed changes to be more profitable (from the winning makers)

> _Historical — superseded by the gating validation + 4-day multi-asset data. Kept for provenance; where this disagrees with current docs, **README.md / GATING.md / INSIGHTS_4DAY.md win**._

Every change below is backed by a measured number from the wallet tape (250 BTC + 185 ETH 15-min
markets, 430 maker-like wallets) via `makers_levers.py` (per-trade markout-to-resolution + cross-maker
P&L regressions) and `makers_scan.py`/`makers_fingerprint.py`. Markout = signed(payoff − price) per
share held to resolution; it includes spread + outcome, so it measures whether a fill *made money*.
NOTE: tape P&L is GROSS of the 20% maker rebate — winners' gross is ~0, so the rebate is the edge,
which makes the volume/breadth levers (1,2,10) the highest-EV ones.

| # | Change | Data backing | Code |
|---|---|---|---|
| 1 | **Maximize market coverage / uptime** — quote *every* window, all the time | `corr(P&L, #markets)=+0.59` (the single strongest signal); bottom-quartile-by-#markets makers run −32.9/$1k, top-quartile +0.5/$1k | run continuously; latency/uptime (DEPLOY.md) |
| 2 | **Run one book across assets (BTC+ETH+…)** | the same wallets top both books (`0x20d2309cd9` #1 on BTC *and* ETH); breadth multiplies fee-eligible volume across ~uncorrelated outcomes | `multi_market.py` |
| 3 | **Cap clips at ≤15 shares** | markout 6–15 sh **+0.0097** vs >40 sh **+0.0039** (−60%): big clips eat adverse selection/impact. Median winning clip = 7–11 | `--post`/cap ≤15 (cap25 ✓); `graded` uses cap 25 |
| 4 | **Pull only the WITH-move side on BTC moves ≥2bp** (not both, not neither) | on ≥2bp moves, fills traded WITH the move markout **−4.7¢** (2–6bp) / **−1.8¢** (>6bp); the with-move side is the toxic one | `spot`/`spot_react` gate (2bp, with-move-only) ✓ — now in `graded` |
| 5 | **KEEP/refresh the AGAINST-move side during big moves** (overshoot capture) | on >6bp moves, AGAINST-move fills markout **+5.0¢/sh** — the far resting quote gets filled as price overshoots and reverts | per-side gates already keep the against side; `graded` does not pull it |
| 6 | **Quote both sides when calm (<2bp)** — stop over-gating | <2bp moves: WITH **+3.7¢**, AGAINST **+3.2¢** — both profitable; binary "pull on any move" forgoes this | graded gate only fires ≥2bp (calm → quote both) |
| 7 | **Only quote the moderate-probability band (~0.2–0.8)** | markout +1.1¢ (0.4) to **+2.3¢ (0.7)** vs **−0.5¢ at ≤0.1** and ~0 at ≥0.9; the deep ITM/OTM tails don't pay | new `band` gate; `band_p` + `graded` variants |
| 8 | **Treat the rebate as the product — push fee-eligible maker volume & climb the tier** | makers' GROSS P&L/$1k is ~0 to −33; the winners are net-positive *only* via the 20% rebate | quote in-band (≤3¢) for reward eligibility; volume → 30-day tier (#6) |
| 9 | **Don't be a late-window-concentrated quoter** | wallet-level: high late-fraction quartile **−16.9/$1k** vs low-late **−0.9/$1k** (late-concentrated makers underperform; they're the forced/adverse flow) | reduce size last ~3–4 min (late_gate); winners' late-fraction 0.03–0.17 |
| 10 | **Stay delta-neutral with small carried inventory** | winning cohort is 0.46–0.49 two-sided; `hedge_value.py` shows carried inventory is variance, not edge (hedging it removes ≤10% of variance only because they're already flat) | dneutral/skew tight ✓; both sides quoted |

## What's newly implemented (paper-testable now)
- **`band` gate** + **`band_p`** variant — skip quoting outside P(Up)∈[0.20,0.80] (change #7).
- **`graded`** variant (cap 25, skew 0.15, gate=band∪micro∪spot) — the consolidated winner: tight clip
  (#3), moderate-band only (#7), pull the with-move/micro-adverse side at ≥2bp (#4) while keeping the
  against side (#5) and quoting both when calm (#6). This is the single variant that bundles the
  data-backed maker behaviors; the GHA collector will score it vs baseline/micro_gate over live windows.

## What the data CONFIRMS we already had right
- `spot_react`/`micro_spot` (per-side with-move pull at 2bp) — change #4/#5 validate the design and the
  **2bp threshold is data-optimal**; the in-region RTDS feed should make them bite (paper feed was slow).
- `cap25`/tight skew (#3, #10), `late_gate` (#9), breadth `multi_market` (#1,#2,#8), rebate thesis (#8).

## Honest caveats
- Tape has no maker/taker flag → markout mixes maker & taker fills; the maker-like filter (two-sided,
  small clips) reduces but doesn't remove taker contamination. Treat magnitudes as directional.
- BTC cross-ref (changes #4–6) uses 24 overlapping windows we collected — strong signs, but re-confirm
  as the gha-data sample grows. The `graded` variant is the live OOS test of these rules.
- Changes #1,#2,#8 (breadth/uptime/rebate) are the highest-EV but need live infra (co-located maker
  across assets), not paper. #3–7,#9,#10 are paper-testable and several are now wired as variants.
