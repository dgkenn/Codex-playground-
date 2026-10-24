# The web coach

This is the app actually used on runs: one HTML page, opened in Bluefy on the iPhone, talking to the
Polar Verity Sense over Web Bluetooth. No install, no server, no account. It updates itself: the link
on the phone always loads the latest build pushed to this branch.

**Open it:** <https://raw.githack.com/dgkenn/Codex-playground-/claude/iphone-marathon-training-app-d2xxuc/docs/index.html>

## How it is put together

```
coach-template.html   the page: layout, styles, and the glue that runs a session
*.js                  the logic, one concern per module, each with its own tests
build-coach.mjs       inlines the modules into the template → one self-contained page
loader.html           the fixed entry point; fetches the latest page (see the note inside)
run-tests.mjs         every suite, in parallel
tests/                one test file per module, plus page-test.mjs (the whole page in Chromium)
bench.py              drives the remote bench from a terminal
```

The page is a single file on purpose. A phone browser on a run can lose its network at any moment,
and a page that needs a second request to start is a page that sometimes doesn't start.

### The modules

| Area | Module | What it does |
|---|---|---|
| Armband | `sensor.js` | The Verity Sense link: heart rate, motion and beat intervals, plus the supervisor that repairs each stream and reconnects on its own |
| | `polar-offline.js` | Heart rate recorded in the band's own memory, and read back over Polar's file service |
| | `backfill.js` | Lines that recording up against the run and fills the holes |
| | `selftest.js` | Tries every armband feature once on the real band |
| | `bt-probe.js` | What the browser's Bluetooth actually exposes |
| | `remote-bench.js` | Runs armband tests on command, relayed through the phone |
| Speed | `geo.js` | GPS fixes → pace, distance, grade, route |
| | `fusion.js` | GPS, phone steps and arm steps combined each second (Kalman filter, learned stride models) |
| | `terrain.js` | Hills from a terrain model rather than GPS altitude |
| | `pace-monitor.js` | Pace in or out of band; a port of the engine's `audio.py`, held to it by a parity test |
| Coaching | `hr-monitor.js`, `hr-blocks.js` | Coaching on heart rate; run/walk blocks decided by heart rate |
| | `pace-voice.js`, `tones.js` | What is said and played, and when |
| | `ramp.js` | The graded ramp test |
| Deciding | `threshold.js` | The aerobic ceiling, from the athlete's own sessions |
| | `progression.js` | Harder, same or easier next time, and how fast the ladder moves |
| | `readiness.js` | The morning check: lnRMSSD against a personal baseline (parity-tested against the engine) |
| | `benchmarks.js` | 2 km trials, measured maximum heart rate, 5K projection |
| | `load-watch.js` | Load spikes and the pain log |
| Keeping data | `session-store.js` | Autosave every 6 s, recovery after a reload, the archive |
| | `session-format.js` | The compact export the engine imports |
| | `run-stats.js` | The numbers a finished run is judged on |
| | `backup.js` | Everything in one file, and back |
| Map | `tiles.js` | The basemap under the route |

## Build and test

```bash
cd marathon/tools
node build-coach.mjs          # writes docs/pace-coach.html (both docs folders) and the hosted copy
node run-tests.mjs            # build + every module suite, in parallel
node run-tests.mjs --all      # also the Python engine and the full page in Chromium (~9 min)
```

The build refuses to write a page that would fail on the phone. It checks four things:

- every module parses;
- no two modules export the same name (each module gets its own scope, so only exports can collide);
- nothing the page uses is undeclared (eslint `no-undef`);
- the assembled page starts in headless Chromium without an error.

CI (`.github/workflows/marathon-tests.yml`) runs `run-tests.mjs --all` on every push touching
`marathon/`.

**After changing anything, rebuild and commit the generated pages too.** The phone loads
`docs/pace-coach.html` from this branch, so an unbuilt change never reaches it.

## Testing on the real armband from elsewhere

The band only talks to the phone, so the phone is the bench. Open the app with `#bench=<topic>` on
the end of the link and tap **Allow**. Then, from any machine:

```bash
python3 marathon/tools/bench.py <topic> selftest
python3 marathon/tools/bench.py <topic> hr '{"seconds": 20}'
```

Commands, limits and what goes over the relay: [POLAR_SDK.md](../docs/POLAR_SDK.md#the-remote-bench-remote-benchjs-benchpy).

## Your data

Everything lives in this browser's storage on the phone, under keys starting `band.`: profile,
ladder, ceilings, morning checks, benchmarks, pain log, and the last eight runs.

- **Save backup** (Saved sessions section) hands over one file through the share sheet: save it to
  Files or iCloud. The page reminds you when there are runs since the last backup over a week old.
- **Restore backup** replaces what is on the phone with a backup file, after a second tap.
- **Copy session** copies a run in the compact form `cli import` reads. Each saved run carries its
  link history (every drop and repair) and the coach's log of what it said and did.

## Further reading

| Document | About |
|---|---|
| [PACE_TRACKING_REVIEW.md](../docs/PACE_TRACKING_REVIEW.md) | How speed is measured, and the literature behind it |
| [POLAR_SDK.md](../docs/POLAR_SDK.md) | What the band can do, the connection supervisor, the remote bench |
| [FIVE_K_PLAN.md](../docs/FIVE_K_PLAN.md) | The route to a continuous 5K, and how it adapts |
| [RESEARCH.md](../docs/RESEARCH.md) | The evidence base for the plan as a whole |
