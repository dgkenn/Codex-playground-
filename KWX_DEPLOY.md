# K-WX weather-nowcast — deployment harness & runbook

The one confirmed legal Kalshi edge: buy the ladder rung that just **mechanically locked** (observed
station temperature cleared the strike, so the daily max/min can only settle in-the-money) before slow
retail finishes repricing. Validated on the full all-city history (Phase-2 Track A): deployable
**+0.207/ct, 99.6% win, t=37** — but only on the ~37% of fires with a real gap, and the gap has a
**~3.3-minute half-life**, so detection speed is the whole game.

## Components (all built, PROPOSE-ONLY)

| file | role | status |
|---|---|---|
| `aviationweather_metar.py` | real-time published-METAR feed (tenths-°F); confirmation gate + slow-fire detector | works |
| `kwx_runner.py` | LIVE loop: feed → running max/min → **adaptive cadence** (polls faster near a strike) → glitch/sustain cross → locked rungs → dry-run order | works (paper) |
| `kalshi_exec.py` | order client — **DRY-RUN unless `KWX_LIVE=1` AND `.kalshi_creds` both present** | works |
| `kwx_forward.py` | settles paper fires vs Kalshi result, compares realized **live vs backtest** (tested==live gate) | works |
| `phase2_trackA_price.py` | the full-history backtest (the source of truth for params/EV) | done |

Data flow: `MetarFeed` (or a faster feed) → `kwx_runner.poll_once()` → `KalshiExec.buy_yes/no()` (dry-run)
→ `kwx_runner_plan.jsonl` → `kwx_forward.py settle` → `kwx_forward_settled.jsonl` → `report` (tested==live).

## Frozen strategy params (Phase-2 Track A walk-forward)
margin = 1 °F, sustain = 3 min (Tier-1 study may lower sustain to capture more gap), max pay 98¢ (skip
dead-on-arrival), size per market from the depth/impact study. Edge lives in the **between/less bracket
rungs**, not the headline ">X" rung; KXLOW ≥ KXHIGH.

## The speed problem (why infra matters)
Gap half-life ≈ 3.3 min. Captured EV: +0.187/ct if we act at the cross, +0.15–0.17 at 2–5 min, ~nothing by
60 min. Consequences:
- **GitHub-Actions 2-hour cron is far too slow for detection.** It is fine only for the confirmation-level
  paper gate, not for capturing fills.
- The runner needs a **persistent low-latency host** (a small always-on process) polling during every
  city's afternoon window — which, across US time zones, is ~all day.
- Published METAR is ~hourly → good as the *confirmation* gate, too slow to *detect* fast fires. A true
  1-min real-time feed (Synoptic HF-ASOS, ~2–5 min latency) is needed to reach the +0.15–0.17 band. That is
  Tier-2 item 5 (in research); swap it in via `kwx_runner.set_feed(...)`.

## Human steps required before ANY live capital (nothing below is automated)
1. **Kalshi account + API credentials.** Create `.kalshi_creds` (gitignored) as
   `{"access_key_id": "...", "private_key_pem": "..."}`. Without it the exec client stays dry-run.
2. **Explicitly enable live** with `KWX_LIVE=1` in the runner's environment. Both gates are required; there
   is no code path that trades live without both.
3. **Real-time 1-min feed** (Synoptic token, ~5-min signup) if we want the fast-fire band (Tier-2 item 5).
4. **Persistent host** for the runner (not GitHub Actions).
5. **`pip install cryptography`** on that host (only needed for live request signing).
6. **Fund + set limits**: start tiny (this is a small-capital, high-%, depth-capped edge — not large-AUM),
   with a per-market size and a cross-city daily cap from the Tier-1 capacity/correlation study.

## Go-live sequence (do NOT skip the gate) — staged, each stage gates the next
1. **Paper** — run `python kwx_paper_gate.py` (turnkey: drives the runner in paper, hourly settles +
   reports, writes `kwx_gate_status.txt` with a READY-FOR-CANARY verdict). Equivalent to `kwx_runner.py loop` on the persistent host (free feed is fine). Daily
   `kwx_forward.py settle` then `report`.
2. **Paper gate** — proceed only once forward `report` shows **live == tested** (win ≈99.6%,
   EV ≈+0.20, n≥~30 clustered). This is the hard gate; nothing live before it passes.
3. **$10 canary** — set `BANKROLL = 10` in `kwx_runner.py`, place `.kalshi_creds`, set `KWX_LIVE=1`.
   At $10 the sizer floors to **1 contract per fire** (~$0.80) — the point is to shake out REAL execution
   (fills, fee rounding, API quirks, settlement/withdrawal flow) at trivial risk, not to make money. Run it
   ~1 week. Worst realistic day ≈ -$5 (a heat-dome day, ~6 fires all lose). Watch `kwx_exec_log.jsonl`.
4. **$50 full** — only once the canary shows live orders behave exactly as the dry-run predicted, bump
   `BANKROLL = 50` and let it run at the quarter-Kelly/5%-cap sizing. Scale further only on realized PnL.

### Guards active at every stage (free; only bite in anomalies)
- **Kill switch**: `touch .kwx_halt` blocks ALL live orders instantly; `rm` to resume.
- **Circuit breaker**: >15 fires in one cycle auto-writes `.kwx_halt` (assumes a feed glitch) — you review.
- **Daily-deployment cap**: never opens more than 60% of bankroll across a day's fires.
- **Fat-finger ceilings**: refuses any order >200 contracts or >98¢.
- **Idempotency**: `client_order_id` per ticker+side — a crash/retry can't double-fill.
- **Feed-staleness drop**: a feed silent >45 min is dropped from the consensus.
- Per-station margin/size derates (Phoenix etc.) and per-station feed policy stay on throughout.
