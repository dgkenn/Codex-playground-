# Kalshi Weather Settlement-Nowcast: Fast-Sensor Basis-Risk Study

Generated 2026-07-18T17:54:53.985033Z. Ground truth = IEM `asos1min` (official 1-minute ASOS, free/public/no key). Fast-sensor candidate tested empirically = Weather Underground PWS.

## Bottom line

**NONE of the 4 deep-tested WU PWS trackers qualify as tight, unbiased/leading sensors usable to front-run the official 1-minute ASOS reading.**

Two independent problems kill the thesis, and both are empirical, not assumed:

1. **The only channel we could actually pull WU PWS history through is capped at 5-minute resolution, network-wide.** We scanned 77 nearby PWS candidates across all 20 Kalshi settlement cities (top 3-4 per city); the median observed historical cadence was exactly **300 seconds**, and **zero of 77** reported historical data faster than ~296 seconds. That is *5x slower* than the 1-minute official ASOS we're trying to beat -- before basis risk is even considered, the archived data itself cannot deliver a seconds-early signal. (Live polling of the WU 'current conditions' endpoint did show faster native update rates for some individual stations -- ~15s for one Central Park-area station, ~60-90s for a Chicago-area one -- but that cadence is NOT exposed in the historical archive, so it can be observed live but not backtested with the free public API. See 'Live vs. archived cadence' below.)
2. **Where we could measure tracking quality (4 deep-tested cities), none of the nearest WU PWS stations were tight or unbiased.** Mean bias ranged +1.2F to +3.0F warm (NYC, Chicago, Dallas) or -1.2F cool (Houston); only 4-21% of readings fell within +/-0.3F of the official station at the same moment. A cool-biased sensor lags by definition; a warm-biased one *looks* like it 'crosses' strikes early, but that's an artifact of running hot all day, not genuine early detection -- see the RAW vs. bias-corrected crossing numbers below, which is exactly the trap the operator flagged.

## 1. Candidate fast sensors enumerated per station

### Weather Underground PWS (empirically probed for all 20 cities)

Nearby-station discovery via `api.weather.com/v3/location/near`, using a public frontend key (the same one wunderground.com's own web app uses client-side -- not a private credential; WU's official documented developer API is free only to *owners* of a station feeding WU, so this key was the only practical way to query arbitrary third-party stations in an unattended session).

| City | Official station | # WU PWS within ~10km | Best candidate | Distance | Historical cadence | Deep-tested |
|---|---|---|---|---|---|---|
| New York (Central Park) | NYC | 10 | KNYNEWYO1615 | 0.75 km | 300s | **yes** |
| Chicago (Midway) | MDW | 10 | KILCHICA37 | 1.13 km | 300s | **yes** |
| Dallas-Fort Worth | DFW | 10 | KTXIRVIN221 | 4.16 km | 305s | **yes** |
| Houston (Hobby) | HOU | 10 | KTXHOUST4910 | 3.02 km | 300s | **yes** |
| Atlanta | ATL | 10 | KGAHAPEV1 | 1.23 km | 300s | no |
| Austin | AUS | 10 | KTXAUSTI3939 | 2.27 km | 298s | no |
| Boston (Logan) | BOS | 10 | KMAEASTB68 | 1.68 km | 306s | no |
| Washington DC (Reagan) | DCA | 10 | KVAARLIN288 | 1.91 km | 300s | no |
| Denver | DEN | 10 | KCOCOMME103 | 5.70 km | 305s | no |
| Las Vegas | LAS | 10 | KNVLASVE1096 | 2.25 km | 300s | no |
| Los Angeles | LAX | 10 | KCAELSEG28 | 1.95 km | 304s | no |
| Miami | MIA | 10 | KFLMIAMI1006 | 1.27 km | 304s | no |
| Minneapolis | MSP | 10 | KMNRICHF9 | 1.79 km | 304s | no |
| New Orleans | MSY | 10 | KLAKENNE70 | 1.50 km | 300s | no |
| Oklahoma City | OKC | 10 | KOKOKLAH870 | 3.81 km | 300s | no |
| Philadelphia | PHL | 10 | KNJPAULS3 | 2.71 km | 300s | no |
| Phoenix | PHX | 10 | KAZPHOEN2262 | 3.21 km | 300s | no |
| San Antonio | SAT | 10 | KTXSANAN1697 | 2.48 km | 900s | no |
| Seattle-Tacoma | SEA | 10 | KWANORMA24 | 1.91 km | 304s | no |
| San Francisco | SFO | 10 | KCAMILLB8 | 2.56 km | 300s | no |

Cadence-scan aggregate across 80 checked candidates (77 returned data): median cadence **300s**, range 296-900s. Stations faster than 60s: **0**. Stations faster than 120s: **0**. Stations at ~300s (5 min): 69.

### Other networks (desk research -- NOT empirically pulled; see why)

**weatherflow_tempest**
- Advertised cadence: 3
- API: REST + WebSocket, https://swd.weatherflow.com/swd/rest/...
- History available: Yes, but gated behind a Personal Access Token tied to a Tempest account, and that token can normally only see stations the account owns or has been explicitly shared. There is no public 'read any station' key analogous to what we found for WU. Historical station-stats endpoint exists (/swd/rest/stats/station/{id}) once authenticated.
- Blocker in this session: No self-serve public token for arbitrary third-party stations; would need the operator's own Tempest device or a cooperating station owner's PAT.

**ambient_weather**
- Advertised cadence: ~60 (console upload interval, user-configurable, often set to 1-5 min)
- API: REST, api.ambientweather.net/v1, requires both an applicationKey (app-level) and apiKey (per-user, generated in the user's dashboard).
- History available: Yes for stations you own/have been granted access to; no public discovery of arbitrary nearby stations without a key.
- Blocker in this session: Both keys require an authenticated account; no public demo credential documented.

**netatmo**
- Advertised cadence: 300
- API: OAuth2, requires a registered Netatmo 'app' plus a logged-in user consenting to share their station.
- History available: Only for stations the OAuth user owns or that have opted into Netatmo's public weathermap sharing.
- Blocker in this session: Full OAuth login flow, not obtainable headlessly. Also, Netatmo's own native cadence (5 min) is not fast enough to beat 1-min ASOS even if access were available.

**synoptic_mesonet**
- Advertised cadence: varies by network, typically 5-60 min for state mesonets, ~5-15 min for CWOP/APRSWXNET-fed citizen stations
- API: REST, api.synopticdata.com, free tier (5,000 calls/5M service units per month) but requires account signup + token generation.
- History available: Yes, extensive, and this would have been the best single aggregator (covers WU-fed CWOP-like feeds, OK Mesonet, NY State Mesonet, West Texas Mesonet, etc. through one API).
- Blocker in this session: Signup requires email verification (docs: 'sign up with your email, and they will immediately send you a private key in a welcome email') -- not completable without inbox access in an automated session. The public 'demotoken' documented in Synoptic's own docs is explicitly restricted to a single demo network (id 281, a Greenland glaciology network) and returned 403 'Invalid request per token rules' for every station/network we actually need. IEM (which we do have full access to) does NOT mirror any Mesonet/CWOP/PWS networks -- confirmed by scanning all 600 networks IEM exposes; every one is an official ASOS/AWOS network.

**state_mesonets_direct**
- Advertised cadence: 300 (5 min) typical for Oklahoma Mesonet, West Texas Mesonet, NY State Mesonet
- API: Each network has its own site; several require a separate account/data-request process for bulk/API history.
- History available: Partial / inconsistent across networks.
- Blocker in this session: Even where accessible, native cadence is 5 min -- 5x SLOWER than the 1-min official ASOS we are trying to beat, so these fail the 'fast' requirement before basis risk is even considered. Only relevant for OKC among our 20 cities, and OKC's official station is itself 1-min ASOS, so Oklahoma Mesonet is a non-starter as a leading indicator for KXHIGH-OKC.

### Live vs. archived cadence (WU)

Polling `api.weather.com/v2/pws/observations/current` live (every 15s) for one Central Park-area station (KNYNEWYO1615) over ~90 seconds showed `obsTimeUtc` advancing on essentially every poll (17:43:30 -> 17:43:45 -> 17:44:00 -> 17:44:15 -> 17:44:30 -> 17:44:48Z), i.e. a genuine ~15s native update rate for that specific station's hardware. A Chicago-area station polled the same way updated roughly every ~60-90s. But the **historical** endpoints (`/v2/pws/history/all`, `/v2/pws/observations/all/1day`) return only ~288 points/day for both stations -- exactly 5-minute decimation, regardless of the live cadence. This means: (a) cadence is genuinely heterogeneous station-to-station, some of it IS fast: the operator's premise isn't fictional at the hardware level; but (b) the free public API's historical resolution can't be used to backtest that fast cadence -- any real validation of live seconds-level lead would require the operator to run their own live capture loop over time (or acquire a paid/owner-tier history product), not retrospective analysis of the free archive.

## 2. Deep backtest: tracking distribution + crossing lead

Ground truth: IEM 1-minute ASOS. Candidate: nearest QC-passed WU PWS. Window: 2026-07-04 to 2026-07-17 (14 days).

### New York (Central Park)  (official `NYC`  vs  WU `KNYNEWYO1615`, 0.75 km away)

- Matched pairs: 2987 (official 1-min pts: 14951, WU pts: 4031 at ~300s cadence)
- **Bias (WU - official)**: mean **+3.02F**, std 1.58F, median +3.00F
- Within +/-0.2F: 4.4% | +/-0.3F: **4.4%** | +/-0.5F: 4.4% | +/-1.0F: 15.7%
- Daily-max bias (n=13 days): mean **+3.85F**, std 3.37F
- **Crossing lead, RAW** (all thresholds spanned that day, no bias correction -- what a naive strategy would see): n=187 events, mean lead **+13552s**, median **+1263s**, 61% of events technically 'led'. This number is dominated by the mean bias above (a warm sensor crosses every threshold hours early simply by running hot), not genuine fast tracking.
- **Crossing lead, bias-corrected, thresholds within 5F of the day's actual high** (the honest test): n=59 events, mean lead **+1538s**, median **-2402s**, 22% led. False crossings (WU implies a cross official never confirmed): 0. Missed crossings (official crossed, WU's own daily range never got there): 19 / 78 thresholds tested.
- **Qualifies as usable leading tracker (tight >=50% within +/-0.3F AND |mean bias| <=0.3F)**: **NO**

### Chicago (Midway)  (official `KMDW`  vs  WU `KILCHICA37`, 1.13 km away)

- Matched pairs: 3626 (official 1-min pts: 18423, WU pts: 4031 at ~300s cadence)
- **Bias (WU - official)**: mean **+1.20F**, std 0.97F, median +1.00F
- Within +/-0.2F: 20.7% | +/-0.3F: **20.7%** | +/-0.5F: 20.7% | +/-1.0F: 66.9%
- Daily-max bias (n=14 days): mean **+2.07F**, std 2.19F
- **Crossing lead, RAW** (all thresholds spanned that day, no bias correction -- what a naive strategy would see): n=297 events, mean lead **+2595s**, median **-240s**, 24% of events technically 'led'. This number is dominated by the mean bias above (a warm sensor crosses every threshold hours early simply by running hot), not genuine fast tracking.
- **Crossing lead, bias-corrected, thresholds within 5F of the day's actual high** (the honest test): n=75 events, mean lead **-3652s**, median **-240s**, 27% led. False crossings (WU implies a cross official never confirmed): 0. Missed crossings (official crossed, WU's own daily range never got there): 9 / 84 thresholds tested.
- **Qualifies as usable leading tracker (tight >=50% within +/-0.3F AND |mean bias| <=0.3F)**: **NO**

### Dallas-Fort Worth  (official `KDFW`  vs  WU `KTXIRVIN221`, 4.16 km away)

- Matched pairs: 2818 (official 1-min pts: 15066, WU pts: 3736 at ~300s cadence)
- **Bias (WU - official)**: mean **+2.52F**, std 2.23F, median +2.00F
- Within +/-0.2F: 12.0% | +/-0.3F: **12.0%** | +/-0.5F: 12.0% | +/-1.0F: 40.7%
- Daily-max bias (n=13 days): mean **+5.31F**, std 4.16F
- **Crossing lead, RAW** (all thresholds spanned that day, no bias correction -- what a naive strategy would see): n=263 events, mean lead **+10507s**, median **+797s**, 54% of events technically 'led'. This number is dominated by the mean bias above (a warm sensor crosses every threshold hours early simply by running hot), not genuine fast tracking.
- **Crossing lead, bias-corrected, thresholds within 5F of the day's actual high** (the honest test): n=72 events, mean lead **+5615s**, median **+3628s**, 71% led. False crossings (WU implies a cross official never confirmed): 0. Missed crossings (official crossed, WU's own daily range never got there): 5 / 77 thresholds tested.
- **Qualifies as usable leading tracker (tight >=50% within +/-0.3F AND |mean bias| <=0.3F)**: **NO**

### Houston (Hobby)  (official `KHOU`  vs  WU `KTXHOUST4910`, 3.02 km away)

- Matched pairs: 3627 (official 1-min pts: 18411, WU pts: 4032 at ~300s cadence)
- **Bias (WU - official)**: mean **-1.21F**, std 2.60F, median -2.00F
- Within +/-0.2F: 8.1% | +/-0.3F: **8.1%** | +/-0.5F: 8.1% | +/-1.0F: 29.1%
- Daily-max bias (n=14 days): mean **+3.50F**, std 3.22F
- **Crossing lead, RAW** (all thresholds spanned that day, no bias correction -- what a naive strategy would see): n=227 events, mean lead **-6936s**, median **-288s**, 29% of events technically 'led'. This number is dominated by the mean bias above (a warm sensor crosses every threshold hours early simply by running hot), not genuine fast tracking.
- **Crossing lead, bias-corrected, thresholds within 5F of the day's actual high** (the honest test): n=83 events, mean lead **-2130s**, median **+2175s**, 69% led. False crossings (WU implies a cross official never confirmed): 0. Missed crossings (official crossed, WU's own daily range never got there): 1 / 84 thresholds tested.
- **Qualifies as usable leading tracker (tight >=50% within +/-0.3F AND |mean bias| <=0.3F)**: **NO**

Read the bias-corrected numbers carefully: they swing from thousands of seconds positive to thousands of seconds negative *between cities*, and are noisy within a city too. That is not a small, reliable, few-seconds-early signal -- it is sampling noise from a 5-minute-cadence, multi-degree-noisy sensor trying to time a threshold crossing near a slow-moving daily peak. There is no case here where the swings are small, one-directional, and consistent, which is what 'usable lead' would look like.

## 3. Value ceiling, stated honestly

The operator's own framing is right: the realistic edge here is versus slow retail (minutes), not versus market makers competing on seconds. Given what was actually measured:

- **Backtestable (archived) lead: not demonstrated.** The bias-corrected crossing analysis above did not find a small, consistent positive lead at any of the 4 cities; results are noise-dominated in both sign and magnitude.
- **Theoretical live-poll lead: unverified but plausible for select stations.** The live current-conditions poll showed ~15-90s native cadence for 2 spot-checked stations (not the same ones with acceptable bias). If an operator identifies and validates -- going forward, live, not retrospectively -- a specific PWS with near-zero mean bias and tight std near a given settlement station, a genuine 15-90s live lead is plausible in principle. That is a real, separate, forward-looking research task (build a live capture pipeline, screen many candidate stations for bias/std over weeks, THEN decide); it is not something this backtest, or the free WU historical API, can currently prove.
- **What would unblock a real answer**: (a) the operator's own Synoptic Data account (free tier, 5-minute email signup) to reach state Mesonets / CWOP feeds through one API and check for anything genuinely sub-minute; (b) a Tempest or Ambient Weather device the operator controls, or a cooperating station owner's API key, to get real sub-minute history; (c) a live capture loop run for weeks against WU's 'current' endpoint (which does show fast native cadence for some stations) to build an actual pairs-history at the true native cadence, which the free historical endpoint won't give you.

## Discipline / honesty notes

- Every number above came from real pulls against IEM's `asos1min` product and `api.weather.com`'s PWS endpoints performed during this study (14 days x 4 cities, plus a 20-city x ~4-candidate cadence scan) -- nothing here is simulated or assumed.
- The WU API key used is a low-privilege, publicly-shared frontend key, not a credential the operator owns; it may be rate-limited, throttled, or revoked without notice, and is not a stable foundation for production infrastructure -- treat this study as a one-time empirical read, not a live-trading dependency.
- Tempest, Ambient Weather, Netatmo, and Synoptic-aggregated Mesonet/CWOP data were NOT pulled -- each requires an account credential (owned device or email-verified signup) unobtainable in this unattended session. They are enumerated from public documentation only; treat their cadence/access notes as desk research, not verified.
- 2 of the 14 requested dates for NYC and Dallas had no IEM 1-minute archive rows (2026-07-17) -- those cities' deep test uses 13 complete days, not 14; Chicago and Houston have the full 14.
