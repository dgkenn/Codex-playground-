# Getting the most from the Verity Sense: what the Polar SDK offers, and what the app uses

Polar publishes the [Polar BLE SDK](https://github.com/polarofficial/polar-ble-sdk). It contains the
Android and iOS libraries, and the byte-level protocols underneath them: the measurement service
(PMD) and the file service (PSFTP). This app is a web page, so it can't link the libraries. It speaks
the protocols directly over Web Bluetooth (Bluefy on iPhone), ported from the SDK's own source and
checked against the SDK's unit-test byte vectors.

## SDK mode, and whether there is a way round it switching off heart rate

There isn't. Polar's own description:

> "all algorithms on the device are disabled ... any computed data such as heart rate, PP intervals,
> RR intervals, etc. is not available anymore ... Enabling the SDK mode shutdowns all sensors"
> ([SdkModeExplained](https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/SdkModeExplained.md))

The only "workaround" would be to compute heart rate on the phone from the raw optical (PPG) signal.
That means replacing Polar's validated, motion-compensated algorithm with a home-made one, during
running, which is exactly when motion artifacts are worst. That is a bad trade.

Nothing is lost by avoiding SDK mode. **Normal mode already streams everything a runner can use,
alongside heart rate** ([Verity Sense](https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/products/PolarVeritySense.md)):

| Stream | Normal mode | SDK mode adds |
|---|---|---|
| Accelerometer | 52 Hz, ±8 g | 26–416 Hz, other ranges |
| Gyroscope | 52 Hz | 26–416 Hz |
| Raw PPG | 55 Hz | up to 176 Hz |
| Magnetometer | 10–100 Hz | — |
| Heart rate, PPI | yes | **no** |

What SDK mode adds is higher sample rates. Steps come at about 3 Hz and heartbeats at about 3 Hz, so
52–55 Hz is already far above what either needs.

Running SDK mode *after* the run would measure nothing: the run is over by then. What does help after
the run is a recording made *during* it, which is offline recording, below.

## What the app uses, and why

### 1. Accelerometer stream: pacing (`sensor.js`, `fusion.js`)

The band's 52 Hz accelerometer is a second step counter next to the phone's. Each has its own stride
model, and both feed the speed fusion. See [PACE_TRACKING_REVIEW.md](PACE_TRACKING_REVIEW.md).

### 2. Beat-to-beat intervals at rest: a morning readiness check (`readiness.js`)

PPI is the time between pulses, computed on the band. Polar is blunt about when it is usable:

> "P-P intervals are much more sensitive to noise (movement ...) It means that this metric
> **cannot** be measured accurately during activity. It should only be used at complete rest."
> ([PPIData](https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/PPIData.md))

PPI also slows heart-rate updates to every 5 s while it streams. So it is never used on a run. It
powers a **lying-still check on waking**, which works like this:

- **Measurement.** The first minute is settling and is discarded. The check then runs until it has
  240 clean beats, between 5 and 8 minutes.
  - Beats are dropped if the band flags movement, if they fall outside 250–2500 ms, or if they
    differ more than 20% from the previous accepted beat (Malik).
  - A check with more than 5% of beats rejected doesn't count.
- **The rule** is the engine's HRV-guided-training rule (`engine/marathon_engine/readiness.py`, held
  to it by a parity test):
  - The 7-day mean of lnRMSSD is compared with the 60-day personal baseline ± 0.5 SD (Plews et al.).
  - Inside or above the band: run the plan as written.
  - Below it: **no extra blocks today**.
  - Well below it for two days, or feeling ill, or short sleep with low HRV: rest. In the
    HRV-guided recreational-runner trial (Vesterinen et al. 2016), this approach produced fewer
    hard sessions and more improvement than a fixed plan.
- **Honest limit.** The Verity Sense's resting heart rate is accurate. Its RMSSD reads high against a
  chest strap and agrees poorly in absolute terms, worse when upright (a Georgia Southern University
  thesis against the Polar H10). So every check is in the same posture, it is compared only with
  your own baseline, and no band is drawn until there are 14 checks.
- **Resting heart rate.** Once three checks agree, their median replaces the typed-in resting heart
  rate that every training zone is built from.

### 3. Offline recording: heart rate in the band's own memory (`polar-offline.js`, `backfill.js`)

The band can record to its own memory, and the recording carries on if the connection drops
([SdkOfflineRecordingExplained](https://github.com/polarofficial/polar-ble-sdk/blob/master/documentation/SdkOfflineRecordingExplained.md)).
Heart rate is the one data type that can be streamed live *and* recorded offline at the same time.

That is the answer to iOS freezing the page whenever another app is in front or the screen locks.
On 13 October that froze 16 minutes of a run. The flow:

1. **At Start**, the app also tells the band to record heart rate to memory.
2. **After the run**, it stops the recording and reads the file back over Polar's file service.
   It tries 15 s after Finish and again at 6 minutes, because the band can take up to 5 minutes to
   write the file. If the armband isn't connected then, it tries the next time it connects, for up
   to a week.
3. **The band's trace is lined up** against the heart rate the page did record. Nothing sets the
   band's clock, so the app slides one trace against the other: whole-hour candidates for time
   zones, then each second around them. Nothing is filled unless the two agree within 3 bpm on
   average over at least 2 minutes.
4. **Only holes are filled**: seconds with no heart rate, and stretches the page never recorded.
   Speed, grade and motion stay empty there, because those came from the phone, which was asleep.
5. **The band's memory is cleared** of what was read, once nothing is waiting. The band never deletes
   recordings itself, and under 2 MB free it refuses to start a new one.

**Not yet verified on hardware**, and worth checking on the first real run:

- **The file service.** The app now asks for permission to use the band's file service (PSFTP,
  0xFEEE). A band remembered before this change may need to be picked once more: Remembered devices
  → forget, then Connect.
- **Bluefy.** Whether Bluefy exposes that service at all. If it doesn't, the log will say
  "band memory not read" and nothing else changes.
- **Timestamps.** The recording's time stamp (UTC or local) and its 1 Hz spacing are assumed. The
  alignment step makes the first one not matter.

## Keeping the connection, and getting it back (`sensor.js`)

On 24 October the link dropped nine times in 26 minutes and lost a third of the heart rate. The
connection layer is now built around one rule: **every stream is watched on its own, and each
symptom gets the smallest repair that could fix it before anything bigger is tried.**

| Symptom | Detected by | Repair |
|---|---|---|
| Heart rate quiet 8 s, link alive | Supervisor every 2 s | Re-subscribe heart rate only (notifications off and on) |
| Heart rate still quiet at 20 s, or re-subscribe fails | Supervisor | Rebuild the link |
| Link down | The browser's disconnect event, **or** polling `gatt.connected` (bridges miss the event) | Reconnect at once, then after 0.5, 1, 2 and 4 s, repeating at 4 s during a run |
| A connect that hangs | 8 s per attempt | Cut it and try again; a fresh device object every 3 failures |
| Down for a minute | Supervisor | Ask for a tap (by voice during a run), and keep trying automatically |
| Motion stream quiet, heart rate fine | Supervisor | Restart the motion stream only; a third restart in 10 min stops it for good |
| Two link losses in 10 min with motion streaming | Link-loss record | Stop the optional motion stream to protect heart rate |
| 0 bpm from the band | Each reading | Not a reading. The next 30 s of readings are ignored while the pulse is re-acquired, but they still count as proof the link is alive |

**After every reconnect, everything that was on is put back:**
- heart rate;
- battery;
- the motion stream (unless it was stopped for good);
- the morning check's beat-to-beat intervals.

The page then checks the one thing only it knows about. During a run, the band must still be
recording heart rate to its own memory. A band that restarted has stopped that recording, so the
page starts it again.

**Plumbing:**
- Radio operations run one at a time.
- Control-point requests are queued start-to-answer, because there is one answer slot.
- Listeners are attached once per characteristic, so a reconnect cannot double every frame.

**Redundancy for the data itself:**
- **Heart rate:** the live stream, plus the band's own memory recording, read back after the run to
  fill any gap.
- **Motion and pace:** the band's accelerometer, plus the phone's own motion, plus GPS. Any one can
  drop out.
- **The session:** autosaved every 6 s and again whenever the page is hidden, with enough context to
  be judged if the page never reaches Stop.
- **Link history:** every drop, stall, repair and recovery is in the session's `link` record, so the
  next analysis can see what failed rather than guess. The coach's own log of what it said and did is
  saved with the run as well (`log`).
- **Everything on the phone:** **Save backup** writes it all to one file; **Restore backup** puts it
  back on a new phone or after the browser's data is cleared (`backup.js`).

## Considered and not done

- **SDK mode at any time.** It switches off heart rate and PPI, and its only gain is sample rates
  nothing here needs.
- **HRV (DFA α1) during runs as an aerobic-threshold marker.** It needs ECG-grade RR intervals.
  Optical PPI in motion is exactly what Polar says not to use. A Polar H10 chest strap would make it
  possible.
- **Gyroscope.** It is available in normal mode and could measure arm swing directly. The
  half-cadence guard in `fusion.js` already handles the arm-swing failure, so it would add little for
  now.

## The remote bench (`remote-bench.js`, `bench.py`)

The band only talks to the phone. To test the real band from a machine with no radio, the phone acts
as the bench:

1. Open the app with `#bench=<topic>` on the end of its link.
2. Tap **Allow** on the banner.
3. The page polls `ntfy.sh/<topic>-cmd` every 6 s, runs each command on the band, and answers on
   `<topic>-out`.

`python3 marathon/tools/bench.py <topic> <command> [json]` sends a command and prints the answer.

**Commands.** A fixed list, with no code execution:
- `ping`, `state`, `log`
- `hr`, `battery`, `acc`
- `selftest`, `ppi`
- `offline` (`status` / `start` / `stop`)
- `recordings`, `disk`, `fetch-hr`
- `resubscribe`, `rebuild`
- `settings`

**Limits:**
- During a run, only `ping`, `state`, `log` and `hr`.
- Nothing deletes recordings or enters SDK mode.
- It stops itself after 30 minutes.

**What goes over the relay:** test results (heart rate, battery, timings), never location. The topic
is the only key, so share it only with whoever runs the bench.
