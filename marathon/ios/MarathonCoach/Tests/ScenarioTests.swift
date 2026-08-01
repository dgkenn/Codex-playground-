//
//  ScenarioTests.swift
//  What the coach says, asserted.
//
//  These tests exist because reading the controller and believing it was right is exactly what
//  produced the four defects they now pin down. Every one of the following was found by running the
//  scenarios and reading the transcript, not by reading the code:
//
//   1. A session with a pace target opened by telling the athlete their **warm-up** was too slow. The
//      HR branch had a warm-up guard; the pace-only fallback did not.
//   2. On a 6% climb the app offered "Try about 16:01 per kilometre" — a walking pace, delivered as a
//      running instruction, produced by correct grade-adjustment arithmetic.
//   3. A frozen heart rate and a band that had worked loose were **completely silent**. The gate
//      stopped trusting them, control degraded to pace, and the athlete was never told — so the one
//      remedy that would have worked (reseat the strap) was never suggested.
//   4. A persistent fault repeated its message every five minutes for the rest of the run.
//
//  The assertions are deliberately about *what is said and how often*, not about internal state. A
//  cue rate is the difference between a coach and a nag, and a nag gets muted — at which point none
//  of the safety cues can reach you either.
//

import XCTest
@testable import MarathonCoachCore

final class ScenarioTests: XCTestCase {

    private let zones = ScenarioLibrary.defaultZones()

    private func run(_ s: RunScenario) -> SimulationResult {
        RunSimulator.run(s, zones: zones)
    }

    // MARK: - Cue budget

    /// No session may exceed one cue per two minutes on average. Above that the app is talking over
    /// the music often enough that it stops being tolerable, and a muted app is a useless one.
    func testNoScenarioNagsTheAthlete() {
        for sc in ScenarioLibrary.all {
            let r = run(sc)
            XCTAssertLessThanOrEqual(r.cuesPerMinute, 0.5,
                "\(sc.name) speaks \(r.spoken.count) times in \(r.ticks.count / 60) min:\n"
                + r.transcript())
        }
    }

    /// A persistent sensor fault is mentioned twice and then dropped.
    func testPersistentSensorFaultIsNotRepeatedForever() {
        let r = run(ScenarioLibrary.bandFellOff)
        let notWorn = r.spoken.filter { $0.cue.key == "hr_not_worn" }
        XCTAssertEqual(notWorn.count, 2,
                       "expected exactly two mentions, got \(notWorn.count):\n" + r.transcript())
    }

    // MARK: - Silence where silence is right

    /// Walk breaks are part of the session. The app must not chase them.
    func testWalkRunSessionDoesNotChaseTheWalkBreaks() {
        let r = run(ScenarioLibrary.week1WalkRun)
        XCTAssertTrue(r.spoken.filter { $0.cue.key == "speed_up" }.isEmpty,
                      "told a beginner to speed up during a planned walk break:\n" + r.transcript())
    }

    /// Defect 1. A warm-up is *supposed* to be slower than the session's target.
    func testNoPaceCorrectionDuringTheWarmUp() {
        for sc in ScenarioLibrary.all {
            let r = run(sc)
            let early = r.spoken.filter { $0.t < 300 && $0.cue.level == .pace }
            XCTAssertTrue(early.isEmpty,
                          "\(sc.name) corrected pace during the warm-up: \(early.map(\.cue.text))")
        }
    }

    // MARK: - Speaking up where silence is wrong

    /// Defect 3. The gate catching a frozen heart rate is necessary but not sufficient — the athlete
    /// has to be told, because the athlete is the only one who can fix it.
    func testFrozenHeartRateIsAnnounced() {
        let r = run(ScenarioLibrary.frozenHeartRate)
        XCTAssertTrue(r.spokenTexts.contains { $0.contains("stuck on the same value") },
                      "frozen HR was never announced:\n" + r.transcript())
        XCTAssertLessThan(r.usableHrFraction, 0.85, "the gate should have rejected the frozen span")
    }

    func testBandNotWornIsAnnounced() {
        let r = run(ScenarioLibrary.bandFellOff)
        XCTAssertTrue(r.spokenTexts.contains { $0.contains("not reading your skin") },
                      "a loose band was never announced:\n" + r.transcript())
    }

    func testDropoutIsAnnounced() {
        let r = run(ScenarioLibrary.sensorDropout)
        XCTAssertTrue(r.spokenTexts.contains { $0.contains("Lost the heart-rate signal") },
                      "dropout was never announced:\n" + r.transcript())
    }

    /// A fault must never be able to *drive* control. This is the invariant behind all of the above:
    /// the app may talk about bad data, it may not coach off it.
    func testDegradedSignalNeverDrivesControl() {
        for sc in [ScenarioLibrary.frozenHeartRate, ScenarioLibrary.bandFellOff,
                   ScenarioLibrary.cadenceLock, ScenarioLibrary.sensorDropout] {
            let r = run(sc)
            for (i, d) in r.decisions.enumerated() where r.hrStatuses[i] != "ok" {
                XCTAssertNotEqual(d.mode, .hrAndPace,
                                  "\(sc.name) used HR for control while status was "
                                  + "\(r.hrStatuses[i]) at t=\(i)s")
                XCTAssertNotEqual(d.mode, .hrOnly,
                                  "\(sc.name) used HR-only control while status was "
                                  + "\(r.hrStatuses[i]) at t=\(i)s")
            }
        }
    }

    // MARK: - Instructions a person can act on

    /// Defect 2. Grade-adjusted arithmetic is right and the resulting number is unusable.
    func testNoAbsurdPaceTargetIsEverSpoken() {
        for sc in ScenarioLibrary.all {
            let r = run(sc)
            for (_, cue) in r.spoken {
                // Any spoken "N:NN per kilometre" must be a pace a person could actually run.
                guard let range = cue.text.range(of: #"[0-9]+:[0-9][0-9] per kilometre"#,
                                                 options: .regularExpression) else { continue }
                let mmss = cue.text[range].split(separator: " ")[0].split(separator: ":")
                let secs = Int(mmss[0])! * 60 + Int(mmss[1])!
                XCTAssertLessThanOrEqual(secs, 720,
                    "\(sc.name) told the athlete to run \(cue.text[range]) — slower than a brisk walk")
                XCTAssertGreaterThanOrEqual(secs, 150, "\(sc.name) suggested an impossible pace")
            }
        }
    }

    /// On a climb the instruction should be about effort, because pace on a hill is not an
    /// instruction anyone can follow.
    func testClimbIsCoachedByEffortNotPace() {
        let r = run(ScenarioLibrary.hillyEasyRun)
        XCTAssertTrue(r.spokenTexts.contains { $0.contains("climb") },
                      "no climb-aware cue on a 6% hill:\n" + r.transcript())
        XCTAssertFalse(r.spokenTexts.contains { $0.contains("climb") && $0.contains("per kilometre") },
                       "named a pace target on a climb anyway")
    }

    // MARK: - Safety

    func testPainAboveThresholdStopsTheRun() {
        let r = run(ScenarioLibrary.painReported)
        XCTAssertTrue(r.aborted)
        XCTAssertEqual(r.abortReason, "pain_stop")
        // And it is the last thing said — nothing coaches on after a stop.
        XCTAssertEqual(r.spoken.last?.cue.level, .safety)
    }

    func testIgnoredCuesEscalateToAnAbort() {
        let r = run(ScenarioLibrary.ignoredCuesToAbort)
        XCTAssertTrue(r.aborted, "a non-compliant athlete at the HR ceiling was never stopped")
        XCTAssertEqual(r.abortReason, "hr_abort")
        // The abort must not be the first thing said: warn, then stop.
        XCTAssertGreaterThan(r.spoken.count, 1, "aborted without warning first")
    }

    /// Determinism. Without this the transcripts are not evidence of anything.
    func testSimulationIsDeterministic() {
        for sc in ScenarioLibrary.all {
            XCTAssertEqual(run(sc).transcript(), run(sc).transcript(),
                           "\(sc.name) is not reproducible")
        }
    }
}
