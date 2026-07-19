# Phase 2 / Tier 2 Research — Item 5 (Real-Time 1-Min Obs Feed) & Item 7 (Kalshi Position Limits)

Date: 2026-07-18 (all timestamps UTC unless noted). All numbers below are from live test calls made during this session, not recalled/assumed, except where explicitly marked "per vendor docs (unverified by us)".

---

## ITEM 5 — Real-time 1-minute (or better) obs feed

### Summary ranking (best → worst, for the 20 settlement stations)

| Rank | Source | Resolution | Measured/claimed latency | Signup? | Coverage of the 20 | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Synoptic HF-ASOS** (`api.synopticdata.com`, network suffix `1M`, e.g. `KDEN1M`) | true 1-minute | vendor doc: 2–5 min "when operational" (**not independently verified — no token available**) | **Yes, API token required** (401/403 without one; free academic "Open Access" for .edu, else paid commercial, 14-day trial) | Likely most/all — "most ASOS airport sensors" but excludes AWOS-only sites; not individually confirmed per-station | Best resolution+latency on paper, but unverified by us and has a rocky reliability record |
| 2 | **api.weather.gov (NWS API) sub-hourly obs** `/stations/{ICAO}/observations` | 5-minute (native, non-METAR "special" obs) | **MEASURED: 16–24 minutes**, and drifting worse over a 10-min observation window, not improving | **No signup, fully public** | 18/20 confirmed with clean 5-min cadence live; KDEN was stuck 2 hrs stale, KNYC irregular (10–30 min gaps) at test time | Free, no-signup, real 5-min resolution — but latency is far too slow for detection |
| 3 | **aviationweather.gov METAR** (`/api/data/metar`) | Hourly (SPECI only on wx-significant events, not temp-triggered) | **MEASURED: ingest itself is fast (~3–4 min from obs to receipt)**, but product cadence is hourly | No signup | Full (all 20 are METAR stations) | Fine as a slow confirmation/settlement gate; useless for detection |
| 4 | **NOAA MADIS direct** (1-min ASOS / "OMO" product) | 1-minute (same underlying feed Synoptic re-sells) | Per docs: current+previous hour reprocessed every 5 min; portal explicitly says on-demand REST is *not* meant for continuous real-time use — recommends FTP/LDM for that | **Free but requires account application**, approval timeline unstated, distribution-category gated | Full nominally (it's the primary 1-min source) | Same underlying data as Synoptic HF-ASOS, free, but heavier lift (FTP/LDM ingestion, not a simple REST poll) and unverified approval speed |
| 5 | IEM real-time "currents" API (non-archive) | Unclear | Not usable — endpoint returned empty results in testing (`/api/1/currents.json`), likely wrong query params/network codes; not pursued further given #2 already gave a working free baseline | No signup | n/a | Untested/inconclusive — **gap, not ruled in or out** |

### Detailed test evidence

**a. Synoptic Data.**
- `GET https://api.synopticdata.com/v2/stations/timeseries?stid=KDEN&recent=30&vars=air_temp` with no token → `{"RESPONSE_CODE":2,"RESPONSE_MESSAGE":"Missing token","HTTP_STATUS_CODE":401}`.
- Same call with `token=demotoken` (a token that appears in some old Synoptic doc examples) → `403 "Invalid request per token rules"` even against Synoptic's own example station (`WBB`) and the HF-ASOS network alias (`KSLC1M`). **No usable public/demo token exists anymore — a real signup is mandatory to test or use this.**
- Per Synoptic's own docs (`docs.synopticdata.com/services/high-frequency-asos`): HF-ASOS is explicitly labeled **"experimental,"** was **unavailable at the source from October 2023 to January 2026** (i.e., down for over two years, only recently restored), and "outages remain common due to limited operational priority from the FAA and NOAA." Typical latency when working: **2–5 minutes** (vendor claim, not tested by us).
- Pricing: no public dollar figures found on `synopticdata.com/pricing/` or the commercial-pricing subpage; sales-assisted tiering, 14-day free trial, or the "Open Access Program."
- **Open Access Program is relevant to this user** (`dgkenn@bu.edu` — a .edu address): free API access for accredited-university students/faculty, but explicitly restricted to **non-commercial, defined-scope academic research** (thesis/coursework), requires crediting Synoptic, 1-year renewable term, and is NOT positioned for "open-ended" or production use. **Deploying it inside a live-money trading bot is very likely outside the program's terms of service** — flagging this as a real constraint, not a free lunch.
- **Bottom line for 5a: cannot be tested without a human doing account signup (paid or academic-but-ToS-limited). This is a required human step before Item 5 can be closed out.**

**b. NWS/aviationweather endpoints.**
- `GET https://api.weather.gov/stations/{ICAO}/observations/latest` and `.../observations?limit=N` (no auth needed) return **5-minute-resolution non-METAR observations** interleaved with the hourly METAR, for most of the 20 stations — this is a genuine, free, no-signup near-real-time feed most people miss (they only know the hourly `/latest` METAR).
- Live cadence check across all 20 stations (single snapshot, `now`=18:49–18:51 UTC): KMIA, KMDW, KBOS, KAUS, KSEA, KSFO, KMSP, KDCA, KATL, KDFW, KSAT, KOKC, KLAS, KPHX, KHOU, KPHL, KMSY, KLAX all showed clean 5-minute-spaced timestamps (`...18:30, 18:25, 18:20...`). **KDEN was stuck at 16:53 (~2 hrs stale — a real outage at that moment)**, **KNYC showed irregular gaps (17:51, 17:43, 17:16 — 8 to 27 min apart, not clean 5-min)** — coverage/reliability is not uniform across all 20.
- **Latency measured directly**: polled KAUS `/observations/latest` repeatedly over a ~10-minute wall-clock window:
  - 18:48–18:51 UTC: latest obs stuck at `18:30:00Z` (16–21 min behind wall clock)
  - 18:58:49 UTC: latest obs still only `18:35:00Z` (**23.8 min behind wall clock**)
  - Latency **increased**, not decreased, over the observation window — this is not a one-off blip, it's a real, non-trivial, possibly worsening pipeline lag.
  - HTTP headers show `cache-control: public, max-age=300, s-maxage=120` (a 2–5 min CDN cache), which explains only a small fraction of the ~16–24 min gap — the bulk of the latency is upstream ingest lag, not caching.
- `GET https://aviationweather.gov/api/data/metar?ids=...&format=json` (no auth): confirmed **hourly-only** cadence for calm-weather periods (no SPECIs fired in the 3-hour window checked for KAUS). `receiptTime` vs `obsTime` shows AWC's own ingest is fast (obs at `17:53Z`, `receiptTime` `17:56:34Z` — under 4 minutes), but that speed is wasted because the product only updates once an hour under normal conditions.
- **Conclusion for 5b: NWS/AWC public endpoints are free and reliable to reach, but the fastest one we could get sub-hourly data from (`api.weather.gov` 5-min product) has a measured real-world latency of ~16–24 minutes — not the sub-5-minute latency implied by "real-time."**

**c. Free options without paid signup, ranked:** `api.weather.gov` 5-min product (free, no signup, but ~16–24 min measured latency) is the best fully-free, no-token option found. Nothing free and testable came in under 5 minutes of latency. MADIS direct access is nominally free but gated behind an account application (approval time unknown) and the portal itself says the REST/on-demand interface is not meant for continuous real-time polling — a genuine continuous feed would mean standing up FTP/LDM ingestion, a materially bigger engineering lift.

**d. Conclusion.**
- **No source we could independently verify meets the <2 min detection requirement.** The only source that claims to (Synoptic HF-ASOS, 2–5 min) is paywalled/signup-gated and could not be tested in this session — that is a **required human step** (create a Synoptic account, get an API token; note the academic Open Access track is very likely a ToS mismatch for a live trading bot, so budget for the paid commercial tier).
- If Synoptic HF-ASOS performs per its own documentation (2–5 min latency), the bot lands in the **"act@2–5min" band** — the outer edge of the stated +0.15–0.17/ct sweet spot, i.e. workable but not comfortably inside it, and with real downside risk given HF-ASOS's own history of extended outages (2+ years down until early 2026) and per-station AWOS/ASOS coverage gaps that weren't individually confirmed here.
- **`api.weather.gov`'s free 5-min product, at a measured ~16–24 min latency, is too slow to be a detection feed under any interpretation of the ~3.3-minute profit half-life** — by the time it reports a crossing, the edge has decayed through several half-lives. It is only useful as a delayed confirmation/sanity-check layer, or for post-hoc settlement-adjacent verification, never as the primary trigger.
- **Hourly METAR does not suffice for ANY subset of fires, including "slow-moving" ones** — even a temperature crossing that takes 30+ minutes to develop still crosses the strike at a specific minute, and the ~3.3-min half-life means the profit gap is gone long before the next hourly METAR could report it. There is no regime where hourly cadence preserves the edge.
- **Net recommendation: a genuine ~1-minute feed is mandatory, not optional, and today the only credible path to it is Synoptic HF-ASOS (paid/commercial signup) or a from-scratch MADIS FTP/LDM integration (free but a bigger, slower-to-approve engineering project).** Both require a human step this session could not complete (no credentials available for either).

### Honest gaps for Item 5
- Synoptic's actual latency/resolution/coverage across the 20 stations is **unverified** — we could not get past the token wall. Everything reported about Synoptic is from vendor docs, not our own measurement.
- MADIS account-approval turnaround time is unknown; we did not (and could not, in this session) actually apply for an account.
- IEM's non-archive "current obs" REST API returned empty results in our tests; we did not chase down the correct query parameters — this is a loose end, not a ruled-out option, given limited remaining scope in this session.
- We only spot-checked cadence/latency at a handful of points in time (roughly an 18:47–18:59 UTC window on 2026-07-18); we have not confirmed whether `api.weather.gov`'s ~16–24 min lag is typical/constant or was an unusually bad window (e.g., possible NWS-side backlog at the time of testing). Recommend a longer-duration (multi-hour, multi-day) latency monitor before finalizing the "too slow" conclusion as a hard constant, though even in the best case shown (16 min) it is still far outside the ~1–2 min requirement.

---

## ITEM 7 — Kalshi position/notional limits on weather markets

### Headline finding
Every weather-temperature contract-terms document checked (10 of them, spanning both the legacy per-city template and the newer consolidated `GLOBALTEMPERATURE`/`CITYLOW` template) specifies the **same number: 25,000 contracts per strike per Member**, which — since each contract has a $1 settlement value — is described interchangeably as **"$25,000 per Member"** or **"25,000 contracts per Member."** This matches the historical Kalshi default ($25k) confirmed independently via the Feb 2023 CFTC rule-amendment filing (Rule 5.14(a) at the time: *"Kalshi has imposed Position Limits of 25,000 USD on all Contracts"*), and is current as of the contract-terms PDFs pulled live today (`series.last_updated_ts` for KXHIGHDEN = 2026-03-16, i.e. this year).

**Important nuance — the enforcement mechanism differs by contract, and Kalshi uses two different rules for it (current Rulebook v1.24, Chapter 5):**

- **Rule 5.19 "POSITION LIMITS" (hard cap):** *"Any Participant entering bids or offers, if accepted, which would cause that Participant to exceed the applicable Position Limit shall be in violation of this rule."* This is enforced as a genuine pre-trade/system-level cap.
- **Rule 5.18 "POSITION ACCOUNTABILITY" (soft threshold):** Crossing this level does **not** block the order. Instead: *"Any Participant who exceeds a Position Accountability Level is required to provide to Kalshi's Compliance staff all information regarding its position,"* must refrain from growing the position or unwind "in a timely fashion" if instructed, and if they don't, *"Kalshi shall have the authority to liquidate the applicable position to a level below the Position Accountability Level."* So you *can* technically exceed 25,000 contracts on these markets, but doing so invites compliance contact and possible forced unwind, not an automatic order rejection.

**Per-station breakdown (from the actual contract terms PDF fetched for each series/template):**

| Mechanism | $25k = hard order-blocking "Position Limit" | $25k = soft "Position Accountability Level" (no auto-block, but compliance/forced-liquidation risk) |
|---|---|---|
| Stations (of the 20) | KDEN (DENHIGH.pdf), KMIA (MIAHIGH.pdf), KNYC (NHIGH.pdf), KAUS (AUSHIGH.pdf), KPHL (PHILHIGH.pdf) | KMDW (CHIHIGH.pdf), KHOU (HOUHIGH.pdf), KLAX (LAXHIGH.pdf), KBOS/KSEA/KSFO/KMSP/KDCA/KATL/KDFW/KSAT/KOKC/KLAS/KPHX/KMSY (all via the shared GLOBALTEMPERATURE.pdf template) |

(5 hard-limit stations + 15 soft-accountability stations = all 20 accounted for.)

Exact quoted language, e.g. DENHIGH.pdf: *"Position Limit: The Position Limit for the $1 referred Contract shall be $25,000 per Member."* CHIHIGH.pdf / HOUHIGH.pdf: *"Position Accountability Level: The Position Accountability Level for the $1 referred Contract shall be 25,000 contracts per Member."* GLOBALTEMPERATURE.pdf (used for BOS/SEA/SFO/MSP/DCA/ATL/DFW/SAT/OKC/LAS/PHX/MSY): *"Position Accountability Level: The Position Accountability Level for the Contract shall be $25,000 per strike, per Member."*

### Does it bind before book depth?
**No, not close.** Live order books pulled for KXHIGHDEN today show top-of-book sizes on individual strikes in the **5–100 contract range** (e.g., `yes_bid_size_fp: 76`, `yes_ask_size_fp: 5`, `100`, `29`, `23`, `16.53`, `8`, `0.63`), consistent with the task's own ~10–40-contract book-depth assumption. The exchange-imposed cap (25,000 contracts / $25,000 per strike per Member) is **roughly 250×–5,000× larger** than the observed book depth on a single rung. **Book depth is overwhelmingly the binding constraint** on per-market size for this strategy; the Kalshi position/accountability limit is not a practical concern at the size this ladder strategy would actually be able to fill.

### Honest gaps for Item 7
- We did not find a way to query a Member's *actual current limit* via the public API (no `/positions`-with-limits or account-limit endpoint is exposed publicly, as expected — that requires authenticated account access). Everything above comes from the public contract-terms documents and Rulebook, which is the correct source per Kalshi's own rule text ("as specified in each contract's Terms and Conditions"), but we could not additionally confirm from a live authenticated account that no *account-specific* override is in place (Kalshi does grant higher limits to some members/market makers on request — Rule 4.5 gives Market Makers 10× the standard Position Accountability Level on contracts where they have quoting obligations). If this bot is or becomes a registered market maker on any of these series, its effective limit could be up to 250,000 contracts instead of 25,000 — still nowhere near book depth as a binding constraint either way.
- We spot-checked 10 of the ~20 stations' contract-terms PDFs directly (DEN, MIA, NYC, AUS, PHL individually, plus CHI, HOU, LAX, and the shared GLOBALTEMPERATURE template covering the other 12) rather than all 20 individually — but since 12 of them share one literal template file, this amounts to full coverage of all 20 station templates, just not 20 independently-worded documents.
- We did not attempt to independently confirm whether Kalshi has ever granted this specific account (or any retail account) a higher limit via prior arrangement — that's account-specific information not visible from a public/unauthenticated API.

---

## Session notes
- All Kalshi calls used the public base `https://api.elections.kalshi.com/trade-api/v2` with no auth, as instructed, and all succeeded.
- All weather-feed calls were made live during this session (timestamps embedded above); nothing here is estimated or recalled from training data except where marked "(unverified by us)."
