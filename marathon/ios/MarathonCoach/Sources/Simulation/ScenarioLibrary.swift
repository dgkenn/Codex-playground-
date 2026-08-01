//
//  ScenarioLibrary.swift
//  The sessions worth rehearsing before the sensor arrives.
//
//  These are not arbitrary test fixtures. Each one is a session that appears in the generated plan, or
//  a failure that the signal-quality layer exists to catch, chosen so that running the whole library
//  answers a specific question: **on the day this session comes up, will the app say something
//  sensible, and will it say it the right number of times?**
//
//  The cue *rate* is as important as the cue *content*. A coach that is right forty times an hour is
//  not a coach, it is a nag you will mute, and a muted coach cannot warn you about anything. So every
//  scenario here asserts a ceiling on cues per minute as well as on what they say.
//

import Foundation

public enum ScenarioLibrary {

    /// The profile these scenarios assume: a 30-year-old beginner, HRmax from Tanaka, resting HR
    /// typical for someone who lifts but has not run. Deliberately *not* an athlete — the plan starts
    /// before a first 5K, so the simulator should too.
    public static func defaultZones() -> ZoneModel {
        ZoneModel.fiveZone(hrMax: 187, hrRest: 55, lthr: nil)
    }

    // MARK: - Week 1

    /// Week 1, run 1: the walk/run session the plan actually opens with.
    ///
    /// The question this answers: does the app stay quiet during walk breaks instead of nagging
    /// someone to speed up when they are *supposed* to be walking?
    public static var week1WalkRun: RunScenario {
        RunScenario(
            name: "Week 1 — walk/run 30 min",
            summary: "60 s jog / 90 s walk × 12. Checks the app does not chase a walk break.",
            intent: SessionIntent(kind: "run_walk", targetZones: [1, 2], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in
                if t < 300 { return 1.15 }                 // walking warm-up
                let cycle = (t - 300).truncatingRemainder(dividingBy: 150)
                return cycle < 60 ? 1.9 : 1.15             // 60 s jog, 90 s walk
            },
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13, driftBpmPerMin: 0.2))
    }

    // MARK: - Easy runs

    /// A steady easy run with normal cardiac drift. The commonest session in the whole plan.
    ///
    /// The question: does drift alone trigger a stream of "ease off" cues late in the run? Some
    /// correction is right — drift means the effort really is rising — but it must be occasional.
    public static var easyRunWithDrift: RunScenario {
        RunScenario(
            name: "Easy 40 min with cardiac drift",
            summary: "Constant speed, drift 0.4 bpm/min. Checks drift is corrected but not nagged.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 2400),
            durationS: 2400,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.95 },
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13, driftBpmPerMin: 0.4))
    }

    /// Someone going out far too hard, which is what a beginner does on day one.
    public static var easyRunStartedTooFast: RunScenario {
        RunScenario(
            name: "Easy run started far too hard",
            summary: "Opens at threshold effort. Checks the app pulls it back and then stops talking.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 2400),
            durationS: 2400,
            intendedSpeed: { t in t < 240 ? 1.55 : 2.85 },
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13))
    }

    // MARK: - Quality

    /// Tempo at threshold, where the band is narrow and the cue budget is tight.
    public static var tempoRun: RunScenario {
        RunScenario(
            name: "Tempo — 20 min at threshold",
            summary: "Narrow Z4 band. Checks the app holds a tight band without oscillating.",
            intent: SessionIntent(kind: "threshold", targetZones: [4], targetPaceSecKm: 415,
                                  paceTolerance: 0.04, plannedDurationS: 2400),
            durationS: 2400,
            intendedSpeed: { t in
                if t < 600 { return 1.75 }                // warm-up jog
                if t < 1800 { return 2.41 }               // the tempo block, Z4 by construction
                return 1.65                               // cool-down
            },
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13, driftBpmPerMin: 0.5))
    }

    /// A hilly easy run: the grade should be absorbed by the grade-adjustment, not treated as the
    /// athlete running too hard.
    public static var hillyEasyRun: RunScenario {
        RunScenario(
            name: "Easy run over a hill",
            summary: "6% climb for 5 min, then descent. Checks grade is adjusted for, not punished.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 2400),
            durationS: 2400,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.95 },
            faults: [.grade(from: 900, to: 1200, rise: 0.06),
                     .grade(from: 1200, to: 1500, rise: -0.06)],
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13))
    }

    // MARK: - Sensor failures

    public static var frozenHeartRate: RunScenario {
        RunScenario(
            name: "Frozen heart rate mid-run",
            summary: "HR sticks at one value from 12 to 22 min — Polar's documented behaviour. "
                   + "Checks the app notices and stops coaching off it.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 2400),
            durationS: 2400,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.98 },
            faults: [.frozenHr(from: 720, to: 1320)])
    }

    public static var cadenceLock: RunScenario {
        RunScenario(
            name: "Cadence lock-on",
            summary: "Optical HR locks to step rate at 168. Checks the app refuses to coach off it.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.95 },
            faults: [.cadenceLock(from: 600, to: 1500)])
    }

    public static var bandFellOff: RunScenario {
        RunScenario(
            name: "Band works loose",
            summary: "Still reports a plausible 95 bpm but the arm is not moving. Polar warns "
                   + "skin-contact detection is unreliable, so this must be caught from the signal.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.95 },
            faults: [.notWorn(from: 900, to: 1800)])
    }

    public static var sensorDropout: RunScenario {
        RunScenario(
            name: "Sensor drops out for 3 min",
            summary: "No readings at all. Checks the app degrades to pace-only rather than guessing.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.95 },
            faults: [.dropout(from: 600, to: 780)])
    }

    public static var gpsLostInTunnel: RunScenario {
        RunScenario(
            name: "GPS lost for 4 min",
            summary: "Under cover, no speed. Checks HR-only control takes over cleanly.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.95 },
            faults: [.gpsLoss(from: 700, to: 940)])
    }

    // MARK: - Safety

    public static var painReported: RunScenario {
        RunScenario(
            name: "Pain reported at 6/10",
            summary: "Above the stop threshold. Checks the run is ended, not negotiated.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in t < 300 ? 1.55 : 1.95 },
            faults: [.pain(at: 900, level: 6)])
    }

    /// The escalation path: someone drifting toward their HRmax who does not respond to being told.
    public static var ignoredCuesToAbort: RunScenario {
        RunScenario(
            name: "Cues ignored, HR climbs to the ceiling",
            summary: "Non-compliant athlete at 95%+ of HRmax. Checks the safety abort actually fires.",
            intent: SessionIntent(kind: "easy", targetZones: [2], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in t < 300 ? 1.7 : 3.2 },
            faults: [.nonCompliance(from: 0, to: 1800)],
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 15))
    }

    // MARK: - Later phases

    /// The 2000 m trial from week 5 of BASE_1 -- the first time the plan asks for a real effort.
    ///
    /// Worth rehearsing precisely because it is the session most likely to be run wrong: a beginner
    /// asked for a "hard" 2000 m goes out at 800 m pace and dies. The app's job is to catch that in
    /// the first lap, when it is still recoverable.
    public static var timeTrial2000m: RunScenario {
        RunScenario(
            name: "2000 m time trial (BASE_1 week 5)",
            summary: "Warm-up then a hard 2000 m, started 20% too fast. Checks the app catches the "
                   + "over-pacing early enough to save the trial.",
            intent: SessionIntent(kind: "time_trial", targetZones: [4, 5], plannedDurationS: 1800),
            durationS: 1800,
            intendedSpeed: { t in
                if t < 600 { return 1.7 }                 // warm-up jog
                if t < 720 { return 3.1 }                 // the over-eager first 400 m
                if t < 1380 { return 2.5 }                // settles, still hard
                return 1.5                                // cool-down
            },
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13, driftBpmPerMin: 0.6))
    }

    /// Interval reps, where the controller manages recovery between efforts rather than within them.
    public static var intervals: RunScenario {
        RunScenario(
            name: "Intervals — 5 × 3 min",
            summary: "Hard reps with 2 min jog recoveries. Checks the app stays quiet *during* a rep "
                   + "and judges the set on recovery instead.",
            intent: SessionIntent(kind: "intervals", targetZones: [5], plannedDurationS: 2700),
            durationS: 2700,
            intendedSpeed: { t in
                if t < 600 { return 1.75 }
                let into = t - 600
                if into > 1500 { return 1.6 }             // cool-down
                let cycle = into.truncatingRemainder(dividingBy: 300)
                return cycle < 180 ? 2.8 : 1.6            // 3 min hard, 2 min jog
            },
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13, driftBpmPerMin: 0.5))
    }

    /// A two-hour long run, where drift is the whole story.
    public static var longRunTwoHours: RunScenario {
        RunScenario(
            name: "Long run — 2 hours",
            summary: "Steady effort with heavy cardiac drift. Checks the app explains drift once and "
                   + "widens the band, rather than demanding a slowdown every ten minutes.",
            intent: SessionIntent(kind: "long", targetZones: [2], plannedDurationS: 7200),
            durationS: 7200,
            intendedSpeed: { t in t < 300 ? 1.5 : 1.9 },
            plant: RunnerPlant(hrRest: 55, hrMax: 187, hrPerKmh: 13, driftBpmPerMin: 0.55))
    }

    // MARK: - All

    public static var all: [RunScenario] {
        [week1WalkRun, easyRunWithDrift, easyRunStartedTooFast, tempoRun, hillyEasyRun,
         timeTrial2000m, intervals, longRunTwoHours,
         frozenHeartRate, cadenceLock, bandFellOff, sensorDropout, gpsLostInTunnel,
         painReported, ignoredCuesToAbort]
    }
}
