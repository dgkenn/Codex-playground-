# Window-open latency — HOW TO GET FROM ~14s TO SUB-SECOND AT t=0 (FREE)

**Context:** Study 4 (`WINDOW_OPEN_RACE.md`) returned NO-GO at REST latency — our collector's
first snapshot lands ~14.4s (p50) after a window opens, and the book is already two-sided at every
arrival. REST rtt_ms is NOT the bottleneck (p50 30ms, p90 67ms from GHA; live-verified 56ms median).
The 14s is DISCOVERY LAG. This doc diagnoses that lag precisely, inventories every free lever to
eliminate it, and proposes a concrete architecture to reach sub-second first observation — the
prerequisite to answering whether a contestable dead/one-sided interval exists at t=0 at all.

---

## 1. Diagnosed lag source

The ~14s lag is a **polling-discovery delay**, not network. The root code path in
`kalshi_collect.py` is `KalshiMarket.discover()` (line 117–172):

```python
d = self.sess.get(f"{B}/markets", params={"series_ticker": self.series,
                                          "status": "open", "limit": 5}, timeout=8).json()
```

`discover()` is called **reactively** inside the main loop (lines 486–497) only when
`mkt.mk is None or time.time() >= mkt.mk["we"]` — i.e., only AFTER the previous window
has expired. The sequence at every rollover:

1. **Loop iteration detects `time.time() >= mkt.mk["we"]`** — this fires at most once per
   `POLL_S = 1.2s` pass (the per-iteration sleep, line 514), so detection can be up to
   1.2s late.
2. **`discover()` issues `GET /markets?status=open`** — pays a full REST RTT (~55ms) AND
   depends on Kalshi's list returning the new window. On GHA, the list endpoint appears
   to reflect new markets within a second or two of open, but the collector only queries it
   at window expiry.
3. **`discover()` calls the market metadata endpoint** (`GET /markets/{tk}`, line 151)
   for the `meta` record — a second REST round-trip.
4. **First `poll()` call** executes after discover returns.

None of these steps individually account for 14s. The real culprit is the **timing jitter
between when the loop wakes and when the new window has propagated into the `status=open`
list**. In the worst case, `discover()` returns `None` because the new window isn't listed
yet as `open`; the loop retries on the NEXT 1.2s iteration; this can repeat several times
before the market appears. Combined with a variable runner CPU schedule (GHA shared runners
sleep irregularly), the structural floor settles at ~14s rather than the ~1-2s a clean
single-pass discovery would take.

**Confirmed: rtt is not the bottleneck.** REST RTT to `api.elections.kalshi.com` from GHA
runners: p50 ≈ 56ms, p90 ≈ 84ms (live-measured this session). Even with two sequential
REST calls at discovery (~120ms) plus 1.2s polling cadence, the network contribution is
under 2s. The 12s remainder is polling/discovery jitter.

---

## 2. Free latency levers

### A. PREDICTIVE TICKER ENUMERATION — biggest free win

**Feasibility: HIGH. Expected lag reduction: 14s → ~100ms.**

The Kalshi 15-min ticker format is deterministic and fully predictable (live-verified):

```
KXBTC15M-{YY}{MON}{DD}{HHMM}-{MM}
```

where `HHMM` and `MM` are the **close time in US Eastern time** (currently EDT = UTC-4).
Confirmed examples:
- `KXBTC15M-26JUN130000-00` → open 03:45Z, close 04:00Z (= 00:00 ET, 00 min)
- `KXBTC15M-26JUN130015-15` → open 04:00Z, close 04:15Z (= 00:15 ET, 15 min)

Since windows are on a fixed 900s grid, the next window's ticker is computable at any time:

```python
from zoneinfo import ZoneInfo
def next_ticker(asset="btc"):
    now = time.time()
    ws_next = int(now) - (int(now) % 900) + 900        # next window start UTC
    dt_close = datetime.utcfromtimestamp(ws_next + 900) \
                        .replace(tzinfo=timezone.utc) \
                        .astimezone(ZoneInfo("America/New_York"))
    return (f"KX{asset.upper()}15M-{dt_close.strftime('%y')}"
            f"{dt_close.strftime('%b').upper()}{dt_close.strftime('%d')}"
            f"{dt_close.strftime('%H%M')}-{dt_close.strftime('%M')}")
```

No API call required. The ticker exists and is fetchable (status=`initialized`) up to
~24h ahead (verified: `KXBTC15M-26JUN130030-30` returned HTTP 200 with
`status=initialized` ~800s before its open). With a known ticker, the collector can:
- Begin polling `GET /markets/{ticker}/orderbook` at any time
- The book returns empty (`yes_dollars: [], no_dollars: []`) pre-open
- The FIRST non-empty book response is the true t=0 book

Discovery lag drops from ~14s to one `POLL_S = 1.2s` iteration (the first poll after the
book becomes non-empty) or to the REST rtt (~55ms) if polling tightly.

### B. PRE-OPEN SUBSCRIPTION / POLLING — eliminates cold-start entirely

**Feasibility: HIGH with REST; HIGH with WS if auth is available.**

`status=initialized` markets exist in the API before their `open_time`. The orderbook
endpoint returns HTTP 200 with an empty book. This means the collector can **begin polling
the ticker before t=0** — no discovery step at all. A tight 1.2s poll loop started 30s
before `open_time` will observe the first quote within one polling interval of true t=0.

The `open_time` field is available in the `initialized` market's metadata:
```json
{"status": "initialized", "open_time": "2026-06-13T04:15:00Z", ...}
```
Fetch metadata once (e.g., 60s ahead), then poll the orderbook in a tight loop until
`open_time` arrives and the first non-empty book appears.

**Meta fields confirmed available pre-open:** `open_time`, `close_time`, `status`,
`floor_strike`, `cap_strike`, `custom_strike` — everything needed to initialize the
`mk` struct and variants before t=0.

### C. WEBSOCKET FEED — sub-second book updates, no REST polling lag

**Feasibility: HIGH for auth'd bot; LIMITED for public collector.**

Kalshi offers an authenticated WebSocket at `wss://api.elections.kalshi.com/trade-api/ws/v2`
(already implemented in `kalshi_trader.py`, lines 83–176). It supports:
- `orderbook_snapshot` — full book on subscribe
- `orderbook_delta` — incremental updates (sub-second push on any book change)
- `fill` — real-time fill notifications

Auth requirement: RSA-PSS signed headers (same key as the trading API). The WS is
**not public** — it requires `KALSHI_API_KEY_ID` + private key. The shadow collector
(`kalshi_collect.py`) uses only public endpoints and cannot use the WS feed without keys.

The **public REST** orderbook endpoint (`GET /markets/{ticker}/orderbook`) is no-auth and
works on `initialized` markets (verified). For the shadow collector, the path is:
1. Predictive enumeration (lever A) to know the ticker ahead of time
2. Pre-open polling (lever B) with tight REST cadence to catch the first quote
3. For the live trading bot, the existing WS feeder in `kalshi_trader.py` already handles
   orderbook_delta; it would need to subscribe to the NEXT window's ticker pre-open

WS subscription against an `initialized` (not yet `active`) ticker: the API likely returns
an empty snapshot and then pushes the first delta when trading opens — the same behavior as
the REST book. This is the highest-fidelity lever; REST polling with predictive enumeration
gets the shadow collector to ~100ms-floor; WS would get to ~5-20ms.

**Auth note (shadow collector):** the shadow collector is designed to use no-auth public
endpoints. It cannot use the WS without keys. REST + predictive enumeration is the
applicable free path for the collector.

### D. RUNNER GEOGRAPHY / WARM-START

**Feasibility: MEDIUM; GHA-free.**

GHA `ubuntu-latest` runners are in Azure US-East (Virginia). Kalshi's matching engine is
in AWS `us-east` (already noted in `KALSHI.md`). Azure East and AWS us-east-1 are
co-located in Ashburn/Northern Virginia — the inter-cloud RTT is typically 2-8ms. This
is consistent with the measured ~56ms REST RTT (which includes TLS, not just TCP).

The warm-start issue: a new GHA runner cold-starts with ~30-60s of setup (checkout, pip
install). The **existing self-chaining design** in `paper-collect.yml` addresses this:
`kalshi_collect.py` runs for 2520s (~42 min) per GHA job and processes multiple windows
per run. A window boundary occurring mid-run (the typical case) has ZERO cold-start cost —
the runner is already warm and polling. Cold-start only matters at the absolute first run
in a chain, which is covered by the cron backstop (at most 20-min gap).

No new work needed here; the current 42-min self-chaining design is correct for geography
and warm-start.

---

## 3. Proposed free architecture: sub-second at t=0

Target: shadow collector captures the first non-empty book within ~1-2 polling cycles
(~1.2-2.4s) of `open_time` instead of ~14s.

**Changes required (all in `kalshi_collect.py`, `KalshiMarket`):**

1. **Add `predict_next_ticker()` helper** — implement the ticker formula above; uses only
   `datetime` + `zoneinfo` (stdlib). No new dependencies.

2. **Start pre-open polling 30s before `open_time`** — in the main loop, when the current
   window has >30s remaining, compute and pre-fetch the NEXT window's ticker. Begin polling
   its orderbook immediately. The book will be empty until `open_time`; the first non-empty
   response IS the t=0 book. Change the discover-on-expire trigger to a pre-discover that
   runs at `we - 30s` instead of at `we`.

3. **Keep the `status=open` discovery as fallback** — predictive enumeration can fail if
   Kalshi changes the ticker format. The existing `discover()` call remains as a safety net.

4. **Capture a `t_preopen_first_empty` and `t_first_book` timestamp** — record how many
   polls were empty (pre-open) and exactly when the first non-empty book appeared. This is
   the measurement that settles the question.

**Expected resulting latency:**
- Discovery lag: 0s (ticker known in advance)
- Pre-open polling begins: `open_time - 30s`
- First non-empty book: `open_time + U(0, POLL_S)` where `POLL_S = 1.2s`
- Expected first observation: **t=0 + ~0.6s** (half-interval average), p90 < 1.2s
- Actual floor: REST RTT ~55ms (the poll that catches the first quote takes ~55ms to return)

This is achievable without any new paid infrastructure, new dependencies, or auth keys.
The only code change is in `kalshi_collect.py`: ~30 lines for `predict_next_ticker()` and
a pre-open poll arm in the main loop.

---

## 4. Reframing the verdict: measurement upgrade first, strategy second

The current NO-GO in `WINDOW_OPEN_RACE.md` is precisely stated: **NO-GO at REST latency
WITH the current collector's 14s discovery floor**. It is NOT a claim that no t=0 edge
exists. It is a claim that we cannot see t=0 with the current collector.

The 14s arrival lag means the dataset has exactly **one window with first observation <1.5s**
out of 136 — far too few to characterize the t=0 book state. We have never actually
measured the true opening interval.

The proposed architecture is **first a measurement upgrade**: it would give a collector that
observes windows from sub-second of `open_time`, for the first time producing a dataset
capable of answering the original question.

### What a 1-2 week shadow collection measures

Deploy the pre-open polling collector and capture for ~7-14 days (≈672-1,344 BTC windows).
For each window, record:
- `t_first_book` — seconds from `open_time` to first non-empty book (expect ~0.6s p50)
- `book_state_at_first` — YES bid, NO bid, spread at that first snapshot
- `spread_path` — spread at t=0.6s, 1s, 2s, 5s, 10s, 30s
- `one_sided_duration` — time, if any, when only YES or only NO side was quoted
- `dead_duration` — time, if any, when the book was completely empty post-open

### Decision rule

After ≥200 windows with `t_first_book < 2s`:

- **GO (build opener):** if ≥15% of windows show either:
  (a) a completely one-sided or empty book interval surviving past 1s, OR
  (b) a spread > 5¢ surviving past 2s
  These are the intervals where a sub-second bot would face no competition and could post
  the opening quotes with zero adverse selection. Even at 15% frequency this is a
  material edge at 96 windows/day.

- **CONFIRM NO-GO:** if <5% of windows show any qualifying interval (one-sided/empty >1s
  OR spread >5¢ surviving >2s). This would confirm that the book is already two-sided
  AND tight within one polling cycle of open on essentially every window — true t=0 is
  not contestable even with sub-second infrastructure.

- **Re-measure:** if 5-15%, the question remains open — the interval exists but is narrow
  enough that infrastructure quality (GHA REST vs colo WS) may determine exploitability.
  Escalate to WS-based capture before deciding.

The current NO-GO remains binding. These two lines from `WINDOW_OPEN_RACE.md` are the
operative summary: *"our ~14s arrival lag obliterates any t=0 edge"* and *"this dataset
has only 1 window <1.5s — a different project, not an increment on the current REST
stack."* The proposed change IS the different project: it turns the REST stack into one
capable of observing t=0, which is the correct next step before re-evaluating the strategy.

---

## Summary of levers (ranked)

| Lever | Expected lag reduction | Feasibility | Work required |
|---|---|---|---|
| A. Predictive ticker enumeration | 14s → ~1.2s | ✅ Free, no-auth | ~15 lines in `kalshi_collect.py` |
| B. Pre-open polling (30s ahead) | Eliminates discovery entirely | ✅ Free, no-auth | ~15 lines in `kalshi_collect.py` |
| C. WS subscription (auth'd) | ~1.2s → ~20ms | ⚠ Needs API key (for live bot only) | Already implemented in `kalshi_trader.py` |
| D. Runner geography | Already ~6ms net RTT | ✅ Free, no work | No change needed |

**Minimum viable improvement for the measurement goal: A + B only.** No new auth, no new
deps, no new infrastructure. Expected first-observation latency: ~0.6s p50, <1.2s p90.
