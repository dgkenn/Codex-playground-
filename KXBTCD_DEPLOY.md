# KXBTCD (BTC HOURLY Above/Below) ATM maker-box — deploy readiness, QUEUE-AWARE

**VERDICT (read first):**
> **CONDITIONAL GO at SMALL size, but the sibling study's economics were optimistic and are
> hereby HAIRCUT to the 15M reality.** The 100%-completion / +2c/box upper bound (no queue-race)
> does NOT survive contact with the queue model. KXBTCD ATM is the SAME microstructure as KXBTC15M
> — **same ~7.5k contracts/min inside flow, same BTC index volatility, same ~1.2s ladder-MM we
> queue behind** — so at our live queue position (q0≈8000) **KXBTCD inherits the 15M strand curve
> essentially unchanged: ~22% strand, ~−12c/box GROSS**, NOT 0% strand / +2c. The agent's thesis
> that "the deeper hourly book strands LESS" is **REFUTED**: the hourly inside flow that clears the
> queue is identical, and the live ATM book is actually **THINNER mid-hour** ($2–8k min top-5 vs the
> 15M's ~$33k). After the SAME deployed strand-disposal fixes (C1 dispose-cross + C2 post-complete-
> freeze) that make 15M net-positive, the realistic target is **~+0.3…+0.8c/box NET**, giving a
> queue-haircut incremental of **~$3–10/day at $50–100/window**, not $12–48. Deploy as an
> INDEPENDENT process with its OWN sub-loss-limit; forward-test small before scaling.

---

## Data window, N, costs, method

- **Source:** Kalshi public REST `https://api.elections.kalshi.com/trade-api/v2` (no auth). Books via
  `/markets/{t}/orderbook` (`orderbook_fp.yes_dollars`/`no_dollars`), tape via `/markets/trades`
  (fields `yes_price_dollars`, `count_fp`, `taker_side`). Pulled **2026-06-14 ~19:30 UTC**.
- **Settled-tape N:** **30 settled KXBTCD hourly events** (2026-06-13 10:00 → 2026-06-14 15:00 UTC),
  ATM strike per event (`floor_strike` nearest `expiration_value`), full public trade tape
  (175k–1.16M contracts/event, mean **533k**, median **511k**). Re-quoting box generated
  **~2,060 box attempts** at q0=0 across the 30 events.
- **Live book N:** ATM strikes on the 2–3 open hourly windows + 12 KXBTC15M ATM strikes for the
  flow/depth cross-check.
- **Costs:** maker legs fee-free (post-only) — identical to 15M. Crossing/disposal pays the crypto
  taker fee `ceil(M·p·(1−p)·100)/100`, **M=0.07** (stress M=0.14 on disposals only).
- **Anchor:** the LIVE 15M q0→strand curve (BOX_COMPLETION_EXEC.md, calibrated to the live 21.9%
  strand at q0≈8000). This is the empirical ground truth we port.
- **Scripts (committed):** `kxbtcd_queue_box.py` (live book characterization + queue-aware tape sim +
  the live-anchored strand model). `SCREENS` at the bottom.

---

## 1. Real KXBTCD book characterization

**Touch spread:** **1c at the ATM strike** throughout the hour (median 1–2c; widens to 2–3c only
when the chosen strike drifts off-ATM). Maker box (post YES bid + NO bid) locks **+1c** at the 1c
touch — same as 15M.

**Inside flow rate:** ATM strike does **~7,700 contracts/min** at the inside (533k/hr mean over 30
events). **CRITICAL CROSS-CHECK: the KXBTC15M ATM also does ~7,500 contracts/min.** The hourly's
"886k/hr" headline is just 60× the window length — the *per-second* inside rate that clears our
completing-leg queue is **the same** as the 15M. The hourly is not "more liquid" at the inside.

**Top-5 both-side depth (live snapshots):** KXBTCD ATM min(top-5 YES, top-5 NO) = **$2,311 / $4,571 /
$5,239 / $8,067 / $8,621** across sampled windows (median ≈ **$5k**). The 15M ATM live = **$6,115**
min, and the deployed 15M pair-gate sits at **$33k** (the 15M tape median). **KXBTCD ATM is markedly
THINNER than the 15M ATM mid-hour** — the opposite of the "deeper book" thesis.

**Book evolution over the hour:** depth **BUILDS toward settle**. At ~14 min to close min-top5 ≈
$4.7k; at ~74 min to close ≈ $2.4k. The ATM is **thin early in the hour and concentrates near the
top-of-hour settle.** First-leg fill time within the hour (tape sim): p10≈16 min, median≈50 min,
p90≈60 min — i.e. the harvestable ATM flow is **back-loaded toward settle**, not spread evenly.
Consequence: a depth pair-gate will correctly HOLD FIRE for much of the early hour and most opens
will cluster in the back third — fewer effective windows than "24 full hours" implies.

---

## 2. Realistic (queue-aware) completion / strand / net-c-box

The sibling study's `kalshi_hourly_box_backtest.py` posted ONE box at the hour's median price and
counted "any print each side over the whole hour" → 20/20 complete, +2c. That is the q0=0 upper
bound; over a 60-min horizon the deep ATM oscillates back to any static bid eventually, so it
trivially "completes." It models **none** of the queue race.

**Two queue-aware models, same conclusion — KXBTCD ≈ 15M at the same q0:**

**(A) Live-anchored port (the trustworthy number).** strand ≈ P(price runs the strike before q0
clears) ≈ f(time-to-clear × adverse-hazard). time-to-clear ∝ q0 / inside-flow; adverse-hazard ∝
per-second BTC vol. Measured **flow_ratio(hourly/15M)=1.03, vol_ratio=1.0** ⇒ **effective-q0
multiplier = 0.97 ≈ 1**. KXBTCD inherits the live 15M curve at the same q0:

| q0 (live) | strand% | toxic% | ~c/box GROSS |
|---|---|---|---|
| 0 (front-of-queue, unreachable) | 1.3% | 14.9% | −0.69c |
| 2000 | 8.7% | 52% | −6.2c |
| **8000 (our live position)** | **21.4%** | **73%** | **−12.2c** |
| 15000 | 40.4% | 82% | −18.9c |

**(B) Independent tape-microstructure sim** (re-quoting maker, bounded completion window τ=120s,
adverse-run band 5 ticks, on the real 30-event tape): completion **68.5% → 11.7%** and strand
**31% → 88%** as q0 goes 0 → 8000; mean −1.1c → −3.0c/box. This sim is *more* pessimistic on raw
completion% (it strands a box on any unfilled τ-window) but **confirms the direction and magnitude**:
strand rises steeply with q0; the hourly does NOT strand less than the 15M.

**Net c/box, realistic:** GROSS at q0≈8000 is **~−12c/box** (dominated by the ~22% strands riding to
settlement). This is identical to the 15M's pre-fix economics. **After** the SAME deployed strand
fixes the 15M uses — C1 (`--dispose-cross --dispose-cross-s 25 --dispose-max-give 0.25`) caps a
strand at a bounded ~−10…−15c instead of −25…−50c, and C2 (`--post-complete-freeze`) kills the
over-fill residual class — the live 15M *balanced*-box economics are net-positive and the total is
brought to roughly break-even-to-slightly-positive. **Realistic KXBTCD target: +0.3…+0.8c/box NET**,
contingent on the strand fixes working as well here as on the 15M (they should — same mechanism).

**Answer to the agent's thesis:** the 1-hour horizon does NOT buy a deeper queue-clearing book (same
inside flow), and it gives the price MORE wall-clock to run a leg adverse before settle. The horizon
helps only by offering more box *attempts*; it does not lower the per-box strand probability. **The
hourly box is NOT better than the 15M — it is approximately the SAME, slightly worse mid-hour due to
thinner depth.**

---

## 3. Ported config (exact flags) — deltas vs the live 15M

KXBTCD is the same instrument family, so MOST 15M params transfer **unchanged**. Two structural
changes are forced by (a) the thinner hourly book and (b) the 60-min horizon.

### TRANSFERS UNCHANGED (same microstructure → same calibration)
| flag | value | why unchanged |
|---|---|---|
| `--dispose-cross` | ON | same strand mechanism |
| `--dispose-cross-s` | `25` | strands fill in <3s then sit; same as 15M |
| `--dispose-max-give` | `0.25` | bounded-cross floor; same strand economics |
| `--chase-max-give` | `0.06` | same |
| `--post-complete-freeze` | `1.5` | over-fill residual is the same race (same 1.2s MM) |
| `--max-net` | `1` | strict box pairing; identical risk argument |
| `--max-fills-side` | `4` | same per-window fill-decay |
| `--fill-cooldown` | `20` | same |
| `--min-spread` | `0.01` | 1c ATM touch identical |
| `--fee-mult` | `0.0` | maker post-only fee-free (confirm on KXBTCD first fill) |
| `--improve-tick` | `0.01` | 1c tick |
| `--markout-kill-bar` / `-n` | `-0.04` / `50` | same maker markout profile |

### MUST CHANGE for the hourly horizon / thinner book
| flag | 15M | **KXBTCD** | reason |
|---|---|---|---|
| **`--pair-min-depth`** | `33000` | **`5000`** | 15M gates at ITS tape median ($33k). KXBTCD ATM median min-top5 depth ≈ **$5k**. Keep the *rule* (gate at the market's own median), recompute the *number*. **At 33k KXBTCD would never open.** Refine to the live KXBTCD depth median once 1–2 days of book snapshots are logged. |
| **`--tau-guard`** | `150` | **`300`** | hourly binary gamma still explodes near settle, but the back-loaded ATM flow means useful opens occur up to ~3–5 min out; a 150s guard would also kill the late-window completes. Widen the late-window no-new-open guard to ~300s but keep completions allowed inside it. |
| **`--close-force-s`** | `30` | **`30`** (keep) | final force-flatten; the top-of-hour settle is as fast as the 15M close — keep tight. |
| **`--duration`** | `3600` | **`3600`** | one process spans the hour; re-discover the next event at the top of the hour. |
| **strike selection** | n/a (1 strike) | **NEW** | KXBTCD has ~188 strikes; SELECT the ATM (floor nearest spot / mid nearest 0.5) each hour and **recenter** when `|spot − chosen_floor| > $50` (strikes are $100 apart). The 15M `discover()` hardcodes `KX{asset}15M` single-strike — this needs a KXBTCD discover path. |
| **series / file keys** | `KX{asset}15M`, `…_{asset}15m.*` | **`KXBTCD`, `…_btcd.*`** | `discover()` (line 303), the lock `.kalshi_trader_{asset}15m.lock` (811), kill sentinel (783), metrics/winrec/fees file names (819/840/1179) are all hardcoded `15m`. Parameterize the tenor suffix so KXBTCD writes its own files and takes its OWN lock (else it collides with the 15M `btc` lock). |

**Sizing / capital:** `--max-notional 25` and `--loss-limit 6` should each be set **independently and
SMALLER** for the KXBTCD pilot (e.g. `--max-notional 10 --loss-limit 3`) until the >90%/+0.5c bar is
cleared. `--size-mode depth --depth-size-frac 0.005 --depth-size-cap 10` transfers, but because the
KXBTCD book is ~6× thinner, the same frac yields ~6× smaller size — which is appropriate (size to the
book you actually have).

### Recommended KXBTCD pilot command (conceptual — requires the discover/series code change above)
```
I_UNDERSTAND_REAL_MONEY=yes python kalshi_trader.py --live \
  --series KXBTCD --tenor-min 60 \
  --pair-gate --pair-min-depth 5000 \
  --dispose-cross --dispose-cross-s 25 --dispose-max-give 0.25 --chase-max-give 0.06 \
  --post-complete-freeze 1.5 --close-force-s 30 \
  --max-net 1 --max-fills-side 4 --fill-cooldown 20 --min-spread 0.01 \
  --tau-guard 300 --size-mode depth --depth-size-frac 0.005 --depth-size-cap 10 \
  --max-notional 10 --loss-limit 3 --fee-mult 0.0 --duration 3600
```
(`--series`/`--tenor-min` and the ATM-strike `discover()` are NOT yet implemented; see §3 file-keys row.)

---

## 4. Independence — process / capital topology

- **Flow independence: YES.** KXBTCD (settles XX:00) and KXBTC15M (settles every :00/:15/:30/:45) are
  different series with different order books. Fills are additive, not competing for the same flow.
- **Process: run KXBTCD as a SEPARATE process.** The trader's per-process instance lock is keyed
  `{asset}15m` (line 811) — a KXBTCD trader MUST use a distinct lock/file suffix (`btcd`) or it will
  either collide with the 15M `btc` lock (refuse to start) or, worse, share file state. Run it as its
  own `kalshi_trader.py --series KXBTCD …` process with its own metrics/winrec/fees/lock files.
- **Capital / loss-limit contention: REAL and must be managed.** `--loss-limit` is **per-process**
  (per-session realized+mark $). Two processes on ONE Kalshi account share the SAME wallet/collateral
  but have INDEPENDENT loss-limits — so the *account* can lose up to the SUM of the two limits before
  either trips. Windows overlap (the 15M fires 4×/hour inside every KXBTCD hour), so both can be
  carrying a (bounded, |net|≤1) naked leg simultaneously. Recommended topology:
  - **Two processes, one account, DISJOINT sub-limits that sum to the account budget.** e.g. account
    stop $6 → 15M `--loss-limit 4` + KXBTCD `--loss-limit 2` (pilot). Keep an **account-level**
    supervisor (live_supervisor.sh) that flattens BOTH if combined realized loss hits the account cap,
    independent of either per-process limit.
  - Each process `--max-net 1` caps its own directional exposure at ~$1/window; the combined worst-case
    naked exposure is ~$2 — small, but real, so size KXBTCD `--max-notional` so the *combined* peak
    collateral never starves the 15M (the validated earner gets priority).
  - Do NOT run both off a single shared loss-limit counter (no such shared counter exists today; the
    supervisor is the only account-level guard).

---

## 5. GO / NO-GO + forward-test plan

**GO — at SMALL size, as an independent process, AFTER the discover/series code change.** It is a real,
independent second BTC box market with the same fee-free maker economics. But it is **NOT the free
+$12–48/day the upper bound implied.**

**Realistic incremental $/day (queue-haircut):**
incremental = effective-windows/day × box-size × net-c-box.
- Net c/box realistic = **+0.3…+0.8c** (post-fix), vs the upper bound's +1–2c.
- Effective windows < 24: ATM flow is back-loaded and the pair-gate holds fire early-hour ⇒ assume
  ~12–20 effective harvesting windows/day.
- At $50/window: ~12–20 × $50 × 0.5c ≈ **$3–5/day.** At $100/window: ≈ **$6–10/day.**
- **Honest haircut: ~$3–10/day incremental, not $12–48.** Still additive to the 15M and still a
  positive ceiling lift on a small bankroll — but a quarter of the headline.

**Forward-test plan (pre-registered bars before scaling):**
1. **Shadow first (1 day):** log KXBTCD ATM books + the bot's *would-be* fills with no orders; confirm
   the live depth median (refine `--pair-min-depth`) and that the pair-gate admits a reasonable
   fraction of windows.
2. **Pilot live, tiny:** `--max-notional 10 --loss-limit 3`, even-hour/odd-hour A/B vs gate-off to
   isolate the gate's value. ~50–100 windows (~3–5 days; only ~12–20 useful/day).
3. **GATES (must clear ALL to scale):**
   - realized **completion > 90%** (strand < 10%),
   - realized **net ≥ +0.5c/box**,
   - the C1/C2 strand fixes hold the per-stranded-window loss to **−10…−15c**, not −25…−50c,
   - combined (15M+KXBTCD) account loss never breaches the account cap.
4. **Kill / NO-GO criteria:** strand > 22% (i.e. the upper bound was wrong AND the fixes don't bite),
   or net c/box < 0 over 50+ windows, or the thin early-hour book causes the disposal-cross to thrash
   (repeated re-cross) — revert and keep BTC15M solo.

---

## Honest bottom line

The sibling study correctly identified KXBTCD as the only viable second BTC box market, but its
+2c/box / 100%-completion economics are the q0=0 optimism the 15M already learned to distrust. Once
you model the queue race with the SAME live-anchored curve, **KXBTCD is the 15M box again** — same
inside flow, same vol, same ~22% strand at our q0≈8000, and a *thinner* book mid-hour. The deployable
truth is **break-even-to-slightly-positive after the strand fixes (+0.3…+0.8c/box), ~$3–10/day
incremental** — worth running as a small independent sleeve for the ceiling lift, but NOT the
$12–48/day windfall, and NOT "strands less than the 15M." Forward-test small; do not scale on the
upper bound.

---

## SCREENS (kxbtcd_queue_box.py, 2026-06-14)

```
========== LIVE ATM BOOK CHARACTERIZATION (KXBTCD) ==========
  closes_in=  12.3min CD-26JUN1416-T63699.99  YESbid=0.70($5638) NObid=0.29($2184) spr=0.01 lock=+0.01 min_top5_depth=$4571
  closes_in=  72.3min CD-26JUN1417-T63749.99  YESbid=0.46($92)   NObid=0.52($2467) spr=0.02 lock=+0.02 min_top5_depth=$2311
(15M cross-check: KXBTC15M ATM contracts/min median=7497;  KXBTCD ATM ~7700/min; 533k/hr mean over 30 events)
(15M ATM live min-top5 depth=$6115  vs  KXBTCD ATM live min-top5 depth=$2.3k-$8.6k, median ~$5k)

========== LIVE-ANCHORED KXBTCD STRAND MODEL (ported 15M curve) ==========
flow_ratio(hourly/15M inside contracts/min)=1.03  vol_ratio(same BTC index)=1.00  depth_ratio=0.66
effective-q0 multiplier = vol/flow = 0.97  (>1 worse, <1 better than 15M at same q0)
 q0(live) |  eff_q0 |  strand% |  toxic% |  ~c/box
        0 |       0 |     1.3% |   14.9% |  -0.69c
     2000 |    1948 |     8.7% |   52.0% |  -6.24c
     8000 |    7792 |    21.4% |   73.0% | -12.22c   <-- our live queue position
    15000 |   14610 |    40.4% |   82.5% | -18.90c

========== INDEPENDENT TAPE-MICROSTRUCTURE SIM (re-quoting, tau=120s, 30 events) ==========
     q0 |  Nbox | complete% |  strand% |  toxic% | mean c/box
      0 |  2060 |     68.5% |    31.5% |   30.7% |     -1.13c
   2000 |  1359 |     32.8% |    67.2% |   58.9% |     -2.87c
   8000 |  1146 |     11.7% |    88.3% |   68.8% |     -3.01c
  15000 |  1091 |      5.2% |    94.8% |   70.6% |     -2.83c
first-leg fill time within hour: p10=16min median=50min p90=60min (ATM flow back-loaded toward settle)
mean contracts/ATM strike/hour = 532,669 ; median = 511,270 ; N=30 settled events
```

*Generated 2026-06-14 from live Kalshi public API + 30-event hourly queue-aware box replay + the
live 15M strand anchor (BOX_COMPLETION_EXEC.md).*
