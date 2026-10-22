# Pace and location tracking: what the literature says, and what the app does with it

This review covers the two questions behind `tools/fusion.js` and the Polar accelerometer channel in
`tools/sensor.js`:

1. How do you get **accurate** distance and speed from an iPhone and a Polar Verity Sense?
2. How do you make the estimate **granular**, so a change of pace shows in seconds rather than tens of
   seconds?

## The problem as measured

Checked against map-matched route lengths, the app's GPS-speed distance read **11% short** on one
session and **14% short** on another. Polar Flow, recording on the same phone, read just as short, so
the bias is in the speed the phone reports, not only in the app's arithmetic. Distance summed from GPS
*positions* read **7–11% long** instead, because every wobble of a fix adds length. The pace verdict
also averaged pace over a 20-second window, so a change from walking to running took most of that
window to register.

## What the literature says

### Distance and speed from GNSS alone

- **Doppler speed beats position differencing.** A phone's speed comes from the Doppler shift of the
  satellite carrier. It is smoother and less noisy than differencing positions, which turns every
  metre of position jitter into speed jitter that can only add distance
  ([Wieser et al., FIG 2016](https://fig.net/resources/proceedings/fig_proceedings/fig2016/ppt/ts06b/TS06B_wieser_boffi_et_al_8443_ppt.pdf);
  [GPS speed of locomotion, Eur J Clin Nutr](https://www.nature.com/articles/1600403)).
- **iPhone GPS apps read slightly short on a track, by about 2%.** Benson et al. validated an
  iPhone GPS app against a measured course and found good reliability with a small under-read
  ([Benson et al., Deakin](https://deakin.figshare.com/articles/journal_contribution/Reliability_and_validity_of_a_GPS-enabled_iPhone_app_to_measure_physical_activity/20826010);
  [related validation](https://lida.sport-iat.de/ta/Record/4039254)). So 11–14% is not a law of
  nature. It is a per-device, per-placement bias that can be measured and taken out.
- **Positions are unbiased over long baselines.** Endpoint error is a few metres. Over 100 m or more
  of straight travel it is a few percent per window and averages out across windows, which makes
  long straight chords a usable reference for calibrating Doppler speed.

### Step-based speed (pedestrian dead reckoning)

- **Stride is the variable to model; cadence is the easy part.** Within running, speed rises mostly
  through stride length while step frequency changes little. A stride fixed by cadence alone
  therefore follows a change of pace only as fast as the GPS re-teaches it
  ([Frontiers in Sports, 2021](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2021.585809/pdf);
  [PMC8014039](https://pmc.ncbi.nlm.nih.gov/articles/PMC8014039)).
- **Calibrate stride against GNSS where GNSS is good.** AutoGait learns a person's stride–cadence
  relation from GPS on straight segments and then estimates distance without GPS
  ([AutoGait, Bell Labs](https://nokia.com/bell-labs/publications-and-media/publications/autogait-a-mobile-platform-that-accurately-estimates-the-distance-walked)).
  Garmin's stride length and footpods work the same way and are typically within 1–5% once calibrated
  ([the5krunner on Garmin stride length](https://the5krunner.com/garmin-features/running-dynamics/stride-length/);
  [US 11131562](https://patents.google.com/patent/US11131562)).
- **A GNSS-calibrated wrist IMU reaches about 0.14 m/s RMSE for running speed**, which is the best
  published figure for a body-worn, non-foot sensor
  ([Frontiers 2021](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2021.585809/pdf)).
- **Impact intensity carries speed information.** Peak acceleration rises with running speed at a
  fixed cadence, so an accelerometer can see a change of pace that cadence alone cannot
  ([Deusto repository, IMU running speed](https://deustoteka.deusto.es/bitstreams/363a5a59-ecd9-4455-a6ba-f12dd171242f/download);
  [Sensors 2024, 24(16):5247](https://www.mdpi.com/1424-8220/24/16/5247)).

### Combining them

- **Kalman fusion of GNSS and IMU** gives a better frequency response than either source alone. GNSS
  anchors the level and the IMU follows the changes
  ([arXiv 2006.02348](https://arxiv.org/pdf/2006.02348)).
- **Stand/walk mode switching (zero-velocity detection)** suppresses the drift that GNSS shows when
  stationary. A still phone's fixes wander a metre or two per second.
- **Factor-graph / robust estimators beat a plain Kalman filter on outliers**
  ([arXiv 2307.04866](https://arxiv.org/pdf/2307.04866), preprint). This is worth revisiting if
  outliers turn out to dominate. With per-source gating, a 1-D filter is enough here.

### The Polar Verity Sense

- In its **normal mode** the Verity Sense streams accelerometer data at 52 Hz, ±8 g, over Polar's
  measurement (PMD) service, alongside heart rate. It must be asked for the settings it supports and
  then started with them ([Polar BLE SDK: Verity Sense](https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/products/PolarVeritySense.md)).
- **SDK mode** offers more sample rates but **switches off heart rate and PPI**, so it is not used
  ([SDK mode explained](https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/SdkModeExplained.md)).
- **iOS Safari has no Web Bluetooth.** Bluefy provides it. Background execution of a web page is
  frozen by iOS whatever the browser
  ([Apple developer forums](https://developer.apple.com/forums/thread/125490)).

## What the app now does

Four independent speed channels feed one Kalman filter every second. Any of them can drop out and the
others carry on.

| Channel | What it is good at | How it is calibrated |
|---|---|---|
| GPS Doppler speed × learned scale | Smooth, responsive, available most of the time | Scale = Σ chord / Σ integrated speed over straight 60 s windows with tight fixes. Kept between sessions. |
| GPS positions over a 10–25 s baseline | Unbiased when Doppler is missing | None needed. Trusted less. |
| Phone accelerometer steps × stride | Works under trees and in GPS drop-outs; responds within a step | Stride = ridge regression on cadence and landing intensity, learned against GPS while the pace is steady |
| **Armband accelerometer steps × stride** (new) | The same, from a second body site; the armband stays on when the phone is in a hand or a pocket | Its own stride model. Started over Polar PMD in normal mode, so heart rate is unaffected. |

On top of the channels:

- **Stillness.** When every step source that has shown it can see steps has been quiet for 3 s, and
  GPS does not say "moving", speed is pinned to zero.
- **Self-checks.** A step source that sees no steps while GPS says "moving" for 20 s is set aside for
  the session, so a phone wedged somewhere cannot freeze the speed.
- **No double-counting.** The two accelerometers enter the filter as one measurement (a weighted
  mean, trusted as much as the better one), because both strides were taught by the same GPS.

**Granularity.**

- Cadence is now the median of the last four step intervals (about 1.5 s of history) instead of a
  6 s count.
- The stride model uses landing intensity, so a pace change at the same cadence shows without GPS.
- The pace verdict window is **8 s** on the fused speed instead of 20 s on raw GPS. The Python engine
  keeps 20 s for raw GPS.

**Simulated results** (`tests/fusion-test.mjs`: phone speed biased 12% low, wobbling positions, a 90 s
GPS drop-out, a stop):

- Fused distance is within **1%** of the truth, against −14% for the phone speed alone.
- Per-second median speed error is **0.01 m/s**.
- A run/walk change settles in about **1 s**.
- The armband accelerometer alone is within **1%**.
- With no GPS at a constant 165 spm, steps alone tell 2.95 from 2.18 m/s by how they land (truth: 3.0
  and 2.2).

## What to check on the next real run

- The chip under the heart rate should read **"arm motion on"**. If it reads **"no arm motion (…)"**,
  the reason in brackets says why the band refused (for example "in charger").
- Diagnostics → `fusion` shows:
  - `scale` and `scaleWindows`: the GPS correction and how many straight stretches it came from;
  - `strideSeconds` and `armStrideSeconds`;
  - `shares`: the seconds each source led the estimate.
- Distance should now land within a few percent of the mapped route, not 11–14% short.
