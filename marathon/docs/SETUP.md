# Setup

Everything needed to go from an unopened Verity Sense to a coached run, in the order it has to happen.

---

## 0. The one hard prerequisite

**You need a Mac with Xcode to put this on your iPhone.** There is no way around it. iOS will not run
an app that has not been signed and installed through Apple's toolchain, and that toolchain is
macOS-only. No Mac means no app on the phone — not "harder", not "slower", not possible.

If you have a Mac, go to §2. If you do not, §1 is a real path that still gets value out of the sensor
tomorrow, and it happens to be the path you suggested yourself.

---

## 1. No Mac: use the coach from a terminal

The iPhone app is a port of `engine/` plus a sensor driver and a voice. So without it you lose exactly
two things — live reading of the armband, and being talked to mid-run — and keep everything else. The
same brain, reached through a terminal:

```bash
cd marathon/engine
python -m marathon_engine.cli init --age 30 --hr-rest 55   # start from estimates, clearly labelled
python -m marathon_engine.cli protocol                     # the calibration session to record
python -m marathon_engine.cli import export.tcx --save     # your real numbers, from a Polar export
python -m marathon_engine.cli today                        # what to do today
python -m marathon_engine.cli week                         # the whole week
python -m marathon_engine.cli log --minutes 32 --km 4.1 --rpe 4
python -m marathon_engine.cli status                       # where you are, what the gates want
python -m marathon_engine.cli review --advance             # end of week
```

State lives in `~/.marathon-coach` as plain JSON, one file per concern — readable, editable,
backup-able, and outliving whatever code reads it.

**`import` is the important one.** Polar Flow exports TCX, and TCX carries per-second heart rate and
cumulative distance. That is enough to fit the line relating your heart rate to your speed, which is
both the basis of every pace you are prescribed and the feedforward gain the in-run controller would
use. It is the single most valuable thing week 1 was going to do.

What TCX cannot give you, and the import says so rather than pretending otherwise: no accelerometer
or gyroscope, so gait metrics do not run, and — if the export also lacks cadence — neither the
cadence-lock nor the frozen-heart-rate detector can run at all. Both need evidence you were moving
before a suspiciously steady pulse means anything.

### Running today, with no app

One URL, opened in **Bluefy** on the iPhone:

```
https://raw.githack.com/dgkenn/Codex-playground-/claude/iphone-marathon-training-app-d2xxuc/docs/index.html
```

GPS pace, the plan, the five tones, spoken splits, and — because Bluefy has Web Bluetooth where
Safari does not — live heart rate from the Verity Sense. No Mac, no install, no sign-in. Safari
works too and gives you everything except the armband.

The decision logic is not a re-implementation by eye: it is checked against the same golden vectors
as the Python engine and the Swift port, so all three agree tone-for-tone on eight full-session
traces. The page itself is tested in a real browser as well — booted, every button clicked, the
rehearsal run end to end — because every device fault so far has lived in the gap between "the
module is correct" and "the page works", and all of them looked identical from the phone: nothing
happens.

**Sessions are saved on the phone.** The recording is written down every two seconds while it runs,
not at the end — a page that reloads mid-run, which iOS does by itself to a backgrounded tab with no
warning, used to take the whole session with it. On the next load an unfinished session is offered
back rather than overwritten, and the last eight finished sessions sit in **Saved sessions** with a
Copy button each. Storage is capped by count and by size; a full disk evicts the oldest finished
session rather than failing the write that is trying to preserve the run in progress.

**Today, in one tap.** The card at the top of the page names whatever the plan has scheduled for
today and starts it in the right mode: run/walk sets the intervals from the plan and calls them out;
a paced session loads its own band; the ramp test runs the whole protocol. Nothing to copy across.

**The ramp test can be run on the street.** Tick "On the street, not a treadmill" and each stage
becomes a paced block: the instruction is spoken as a pace rather than a dial setting, the pace band
is re-armed at that stage's speed, and the ordinary tones hold you in it. The ladder in miles is
roughly 19:19, 16:06, 13:48, 12:04, 10:44, 9:39 — four minutes each, after a walk warm-up.

Two things differ from a treadmill and both are deliberate. Grade is **not** compensated for, unlike
every other mode: the whole output of this session is a line relating heart rate to speed, and
adjusting the target for hills would erase the thing being measured. Run somewhere flat; the
recorded grade says whether you managed it. And the app enforces the protocol's own stop rule — at
85% of heart-rate reserve it says so and ends the test, rather than printing the rule on a card and
leaving you to watch for it.

**The ramp test runs itself.** It used to be a paragraph to read on a treadmill — time four-minute
stages by hand and remember which of six speeds comes next, during the one hour the entire plan is
derived from. Now every stage is announced, every speed change is called out, and the final minute
of each stage is flagged for the talk test. Every second of heart rate is recorded against the stage
it belongs to, which is what makes the recording analysable afterwards: copy it out, `cli import` it,
and the heart-rate/speed fit replaces the estimated paces with measured ones.

**When the armband will not connect, run the probe.** The **Bluetooth probe** button in the Armband
panel walks the whole connection one step at a time — availability, remembered devices, choosing,
connecting, every service and characteristic the band exposes, subscribing, and then twelve seconds
of watching for readings — and copies a timestamped report to the clipboard. It takes about twenty
seconds and wants the band on your arm.

It exists because guessing has been expensive. Short UUIDs, a name filter, another app holding the
radio: each was plausible, none was demonstrated, and the last was wrong — the Verity Sense holds
more than one connection at a time. The report distinguishes failures that look identical from the
outside: refused outright, refused-but-actually-connected, connected-then-dropped, connected but
exposing no heart-rate service, connected and subscribed but silent because the band is not against
skin.

Two things it records that are worth knowing about:

- **Which route the page arrived by** — `direct` or `via loader`, also shown in the footer. The
  loader hands over with `document.open()`, which removes every event listener on the document; a
  browser whose Web Bluetooth is a native bridge may route its callbacks through one. Try the
  loader-free URL in `docs/README.md` if the probe says `viaLoader: true`.
- **Whether the rejection carried a reason at all.** A promise rejected with no value is a finding,
  not an absence of one, and it used to render as the word "undefined".

**Three things to know before you rely on it.**

*Music.* A web page cannot ask iOS to mix with other audio the way a real app can — the iOS app sets
`.mixWithOthers` explicitly and there is no web equivalent. Your music may duck when a tone plays.
Press the tone buttons with Apple Music playing, standing in your kitchen, and you will know in
thirty seconds which it does. That is the single most important test to run before a session.

*The volume slider is real.* The earcons are synthesised at the chosen level rather than played at a
level the element is told to use, because iOS ignores `volume` on audio elements entirely. Set it
against your music before you leave.

*Backgrounding.* iOS suspends background tabs. Keep the page open and the screen on; it requests a
wake lock, but switching apps or locking the screen stops the coaching. This is the real cost of not
having an app, and it is worth stating plainly rather than discovering at minute twelve.

*Fixes take up to five minutes to arrive.* The page is served through a CDN that holds a copy for
that long, so after a fix is pushed, wait a minute or two and reload. The build id in the footer
says which one you have — compare it against the one you were given, rather than guessing.

*If something goes wrong,* press **Copy diagnostics** at the bottom of the page and paste it into
the chat. It carries the build id, what the browser can and cannot do, the tone and sensor state and
the last forty log lines — enough to fix it without a second app, a console, or a cable. If the
browser has no clipboard API it puts the same text on the page, selected, instead.

### Which recorder for which session

Bluetooth reaches about ten metres, so what can record a session depends on what stays near you.

| Session | Recorder | What you get |
|---|---|---|
| Treadmill ramp test | **Browser logger** (`tools/verity-logger.html`) on a laptop at the machine | HR + accelerometer + labelled stages. Full sensor health. |
| Resting / orthostatic block | Browser logger, laptop beside you | Same |
| Outdoor run, recording only | **Polar Flow on your phone**, in your pocket | HR + GPS distance. No accelerometer, so sensor health reads partial. |
| Outdoor run, with coaching | **The hosted page in Bluefy**, armband connected | Live pace tones, spoken splits and heart-rate coaching in your AirPods, all recorded by the page. Copy the session out afterwards and `cli import` it. |
| Outdoor run, coaching without the armband | **The hosted page in Safari** + Polar Flow recording alongside | Pace tones and splits from the page; heart rate recorded by Flow for later import. |

The browser logger is not for outdoor runs and does not pretend to be: the moment you run away from
the machine the connection drops. That is handled rather than hidden — nothing is written while the
signal is gone, and it reconnects by itself when you come back. A gap in the file is honest; a
repeated last value would look like real data and be undetectable afterwards.

The calibration ramp is a treadmill protocol, so the session that matters most is the one the logger
handles best.

### Recording it

The Verity Sense records **standalone**, with no phone involved: hold the button until it enters
recording mode and it logs to its own internal memory, which you later sync through Polar's own Flow
app on your iPhone.

That is enough to do the single most useful thing available on day one:

1. Charge it, then pair it with **Polar Flow** on your iPhone and let it update firmware.
2. Wear it for a **walk/jog session** — twenty to thirty minutes, alternating easy jogging and
   walking, no attempt to push.
3. Wear it **overnight** for one night, and take a **still, seated five-minute reading** the next
   morning before getting up.
4. Sync, export, and hand me the files.

From that I can seed the plan with your real numbers instead of population estimates — your actual
resting heart rate, your actual HR response to easy running, the slope of heart rate against speed
that the in-run controller uses as its feedforward gain. Everything the app would otherwise spend
week 1 measuring. See `engine/marathon_engine/calibration.py` for exactly what gets extracted and
`docs/PLAN.md` for the protocol.

The plan itself does not require the app. It is a document. You can run week 1 off `docs/PLAN.md` and
a watch, and add the app when you have a Mac.

---

## 2. Getting it onto your phone

Three ways, and the differences matter more than they look.

| Route | Cost | Rebuild every | Good for |
|---|---|---|---|
| **Free provisioning** | £0 | **7 days** | Trying it out. The app stops launching after a week until you rebuild from Xcode. |
| **Apple Developer Program** | $99/yr | 1 year | What you actually want. Install once, forget about it for a year. |
| **TestFlight** | needs the $99 | 90 days | Pointless here — TestFlight is for distributing to other people, and there are no other people. |

**The App Store is not involved at any point.** You never submit this, never get reviewed, never
publish. A single-user app installs directly from Xcode to your own device. That also means none of
App Review's rules apply to it — no privacy manifest to argue about, no health-claims scrutiny.

For a training plan measured in months, the seven-day expiry of free provisioning will become
infuriating around week three. Budget the $99 if you intend to stick with this.

```bash
cd marathon/engine
python -m marathon_engine.export ../ios/MarathonCoach/Resources   # REQUIRED — app refuses to start without it
cd ../ios/MarathonCoach
xcodegen generate && open MarathonCoach.xcodeproj
```

**Set `SWIFT_TREAT_WARNINGS_AS_ERRORS` to `NO` for your first build.** Eighteen files have never been
compiled; with warnings-as-errors on you will be fixing style noise interleaved with real errors and
unable to tell them apart. Turn it back on once it builds clean.

---

## 3. Rehearse before you run

Before the sensor matters at all, **Settings → Rehearse a run**.

This plays a scripted session through the real controller, the real voice and the real audio session,
with no sensor connected. Start Apple Music first — the point is to confirm that a cue ducks your
music and hands it back, in your AirPods, rather than stopping playback.

Twelve scenarios are included, and they are the ones worth hearing: the week 1 walk/run, an easy run
with cardiac drift, a tempo, a hill, and the failure modes — frozen heart rate, a band that has worked
loose, cadence lock-on, a dropout, GPS lost under cover, pain reported mid-run.

Run them at 60× to hear a whole session's cues in forty seconds. Run the one you are about to do for
real at 1× to judge whether the cue rate is tolerable — that is the only speed at which that question
has a meaningful answer.

Nothing a rehearsal produces is saved as training. It cannot reach the load model, the plan, or the
Health app.

---

## 3a. What you will hear

Two channels, because one cannot do both jobs.

**Tones** answer "am I on pace", continuously, without ducking your music.

| Sound | Means |
|---|---|
| Two notes falling | Ease off — you are faster than the band |
| Two notes rising | Lift — you are slower than the band |
| One single note | Back on pace |
| Three quick rising notes | The voice is about to say something |
| Two low dull notes | Signal lost; guidance has degraded |

**Silence means you are inside the band.** That is the design, not an absence of one. Two things stop
silence being ambiguous: the single note when you come back on pace, so every correction closes its
own loop, and a two-second spoken split each kilometre ("2K. 8:41. On pace.") which doubles as proof
the app is alive.

The margin is the session's own tolerance — ±6% by default, ±4% on a tempo. At 8:40/km that is about
±31 s/km, which is roughly where GPS noise stops dominating. Tighter would beep at measurement error
rather than at you.

Rules worth knowing before your first run:

- **Warm-ups are never policed for being slow.** You cannot be told to speed up until you have
  reached the target pace once. Being *too fast* is policed from the first second, because there is
  no session where going out hard is the prescription.
- **Easy and long runs are a ceiling.** Running slower than target on those is the session working,
  so the rising tone never plays.
- **Hills move the band.** A 6% climb costs about 37% in pace at the same effort, and the band moves
  with it rather than nagging you up every incline.
- **The acknowledgement lags your correction by up to twenty seconds.** That is the smoothing window
  that keeps the channel quiet on an evenly-run kilometre. Ease off, then expect the pip about twenty
  seconds later, not immediately.
- **Worst case is four tones a minute**, and only when you are a long way out and not correcting. A
  well-run easy session is silent.

Set the tone volume in **Settings → Audio → Play them now**, with Apple Music playing. If a tone
disappears under the music or startles you, that slider is the fix — and it is worth doing before a
run rather than during one.

---

## 4. Day one with the Verity

**Before anything else:** charge it fully, and update the firmware through Polar Flow. Do this the day
it arrives, not the morning of a run.

**Wearing it.** Upper forearm, a couple of finger-widths below the elbow, sensor against the inside of
the arm. Snug enough that it does not slide when you shake your arm, loose enough to slip a finger
under. This is not fussiness — every one of the four failure modes the app detects is caused by the
band moving, and the fix for all four is the same: put it back where it should be and tighten it one
notch.

**Which mode.** The app asks for `.run` mode and you should let it. Polar's PPI algorithm and the 1 Hz
heart-rate stream are mutually exclusive on this hardware: in PPI mode heart rate updates only every
five seconds, with roughly twenty-five seconds before the first sample arrives. A controller whose
heart-rate time constant is forty-five seconds cannot work off that. PPI is for the overnight and
seated-morning readings, where the slow update does not matter.

Do not start a PPI stream during a run. Polar documents that it aborts an ongoing training session.

**Two things Polar tells you about this device that the app is built around:**

- *"If movement is detected, the heart rate is fixed to the last reliable value."* A frozen heart rate
  looks completely normal — a plausible number, updating on schedule, simply not changing. The app
  detects it and tells you to reseat the strap.
- *"Skin contact detection is very unreliable in Polar Verity Sense… it might be possible for the
  device to output a heart rate that is not 0 even when the device is not worn."* So the app never
  trusts the contact flag; it infers a not-worn band from stillness in the accelerometer alongside a
  suspiciously steady pulse.

---

## 5. First week

Week 1 is diagnostic. Do not treat it as training and do not try to do well at it.

1. **Screening first.** The app will not let you start until the ACSM preparticipation screening is
   done. It takes two minutes and it is the one gate that exists to catch something that matters.
2. **The submaximal ramp**, not a maximal test. It walks you up through easy stages and fits the slope
   of heart rate against speed. That slope becomes the controller's feedforward gain and the basis of
   your paces. Nothing about week 1 requires you to run hard, and running hard would make the fit
   worse, not better.
3. **Three runs: Wednesday, Saturday, Sunday**, matching how you already train, with your two strength
   days kept where they are.
4. **Every night with the band on** if you can stand it. HRV baseline needs about two weeks before it
   means anything; starting it now means it is ready when it starts to matter.

The 2000 m time trial is week 5, not week 1. Everything before it is measurement.

---

## 6. When something looks wrong

| Symptom | Almost certainly |
|---|---|
| "Warming up" for more than a minute | Normal in `.rest` mode — PPI takes ~25 s for the first sample. In `.run` mode, reseat the band. |
| Heart rate looks plausible but never changes | Frozen. The app will say so twice. Reseat and tighten. |
| Heart rate sitting suspiciously close to your step rate | Cadence lock-on. Move the band a few centimetres and snug it. |
| Coach has gone quiet about heart rate | It stopped trusting the signal, which is the correct behaviour. Check the Signal row on the run screen for which of the four faults it saw. |
| No cues at all, ever | Check the app is not muted, and that a cue is not simply not warranted — on a well-executed easy run two cues in forty minutes is normal and correct. |
| App refuses to launch | `plan.json` was not exported. Re-run the export in §2. |

A session where the coach said nothing is usually a session you ran well. The app is built to be
quiet; if it talks more than about once every two minutes, that is a defect, and the test suite
asserts against it.
