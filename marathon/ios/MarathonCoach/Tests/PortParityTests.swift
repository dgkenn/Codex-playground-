//
//  PortParityTests.swift
//  Asserts the Swift port agrees with the Python engine, against the same golden-vector file.
//
//  This file is the reason "the Swift port is faithful" is a claim that can be checked rather than
//  hoped for. `marathon_engine/export.py` writes `golden_vectors.json`; the Python suite produces it,
//  and these tests consume it. Where they disagree, **Python is authoritative by definition** — it is
//  the implementation with the science tests and the published-table calibration behind it.
//
//  Regenerate after any change to the shared logic:
//
//      cd marathon/engine
//      python -m marathon_engine.export ../ios/MarathonCoach/Resources
//
//  A vector drifting is not a test failure to be silenced by loosening a tolerance. It means the two
//  implementations have diverged, and one of them is now prescribing something different from what the
//  tested one prescribes.
//

import XCTest
@testable import MarathonCoachCore

final class PortParityTests: XCTestCase {

    private struct Vectors: Decodable {
        struct ZoneCase: Decodable {
            struct Z: Decodable { let index: Int; let low_bpm: Int; let high_bpm: Int }
            let hr_max: Double; let hr_rest: Double; let lthr: Double?; let zones: [Z]
        }
        struct GradeCase: Decodable { let grade: Double; let factor: Double; let cost: Double }
        struct PaceCase: Decodable {
            let vdot: Double; let easy: Double; let marathon: Double; let threshold: Double
            let interval: Double; let repetition: Double; let ir_prescribable: Bool
        }
        struct SteadyCase: Decodable { let hr: Double; let slope_bpm_s: Double; let hr_ss: Double }
        struct CorrectionCase: Decodable {
            let hr_error: Double; let slope_bpm_kmh: Double; let delta_m_s: Double
        }
        struct RiseCase: Decodable {
            let `case`: String
            let hr: [[Double]]
            let speed: [[Double]]
            let expected_kind: String
        }
        struct SQCase: Decodable {
            struct S: Decodable {
                let t_s: Double; let hr_bpm: Double
                let cadence_spm: Double?; let accel_sd_g: Double?
            }
            let `case`: String
            let samples: [S]
            let cadence_lock: Double
            let frozen: Double
            let not_worn: Double
        }
        struct Trace: Decodable {
            struct C: Decodable {
                let t_s: Double; let cue_key: String; let level: Int
                let hr_ss: Double?; let correction: Double?
            }
            let hr_speed_slope: Double
            let cues: [C]
            let final_hr_approx: Double
        }
        let export_version: Int
        let zones: [ZoneCase]
        let grade_factors: [GradeCase]
        let paces: [PaceCase]
        let steady_state_hr: [SteadyCase]
        let speed_correction: [CorrectionCase]
        let hr_rise: [RiseCase]
        let signal_quality: [SQCase]
        let controller_trace: Trace
    }

    private static var vectors: Vectors!

    override class func setUp() {
        super.setUp()
        guard let url = Bundle.module.url(forResource: "golden_vectors", withExtension: "json"),
              let data = try? Data(contentsOf: url) else {
            XCTFail("golden_vectors.json is missing from the test bundle. Regenerate it with "
                    + "`python -m marathon_engine.export ../ios/MarathonCoach/Resources`.")
            return
        }
        do {
            vectors = try JSONDecoder().decode(Vectors.self, from: data)
        } catch {
            XCTFail("golden_vectors.json did not decode — the export schema and this test have "
                    + "drifted apart: \(error)")
        }
    }

    private var v: Vectors { Self.vectors }

    func testVectorFileVersionMatches() {
        XCTAssertEqual(v.export_version, 1,
                       "Export version changed; review what else moved before updating this.")
    }

    // MARK: Zones

    func testZoneBoundariesMatchPython() {
        for c in v.zones {
            let m = ZoneModel.fiveZone(hrMax: c.hr_max, hrRest: c.hr_rest, lthr: c.lthr)
            XCTAssertEqual(m.zones.count, c.zones.count)
            for (swift, py) in zip(m.zones, c.zones) {
                XCTAssertEqual(swift.index, py.index)
                XCTAssertEqual(swift.lowBpm, py.low_bpm,
                               "zone \(py.index) low bound differs at hrMax \(c.hr_max), "
                               + "lthr \(String(describing: c.lthr))")
                XCTAssertEqual(swift.highBpm, py.high_bpm,
                               "zone \(py.index) high bound differs")
            }
        }
    }

    func testZonesRemainContiguousAfterLthrPinning() {
        // A gap or overlap here would let a heart rate fall into no zone, or two.
        for c in v.zones {
            let m = ZoneModel.fiveZone(hrMax: c.hr_max, hrRest: c.hr_rest, lthr: c.lthr)
            for (a, b) in zip(m.zones, m.zones.dropFirst()) {
                XCTAssertEqual(a.highBpm, b.lowBpm, "zones not contiguous at \(a.name)")
            }
        }
    }

    // MARK: Grade adjustment

    func testMinettiFactorsMatchPython() {
        for c in v.grade_factors {
            XCTAssertEqual(Physiology.minettiCost(grade: c.grade), c.cost, accuracy: 1e-9,
                           "Minetti cost differs at grade \(c.grade)")
            XCTAssertEqual(Physiology.gradeAdjustedPaceFactor(grade: c.grade), c.factor,
                           accuracy: 1e-9, "grade factor differs at \(c.grade)")
        }
    }

    func testGradeExtremesAreClampedIdenticallyInBothImplementations() {
        // The polynomial misbehaves outside Minetti's validated ±0.45, so both sides must clamp rather
        // than extrapolate — and clamp at the same place.
        XCTAssertEqual(Physiology.minettiCost(grade: 0.9), Physiology.minettiCost(grade: 0.45),
                       accuracy: 1e-12)
        XCTAssertEqual(Physiology.minettiCost(grade: -0.9), Physiology.minettiCost(grade: -0.45),
                       accuracy: 1e-12)
    }

    // MARK: Controller estimators

    func testSteadyStateHrMatchesPython() {
        for c in v.steady_state_hr {
            XCTAssertEqual(RTMath.predictSteadyStateHr(hrNow: c.hr, slopeBpmPerS: c.slope_bpm_s),
                           c.hr_ss, accuracy: 1e-9)
        }
    }

    func testSpeedCorrectionMatchesPython() {
        for c in v.speed_correction {
            XCTAssertEqual(RTMath.speedCorrection(hrErrorBpm: c.hr_error,
                                                  slopeBpmPerKmh: c.slope_bpm_kmh),
                           c.delta_m_s, accuracy: 1e-9,
                           "correction differs for error \(c.hr_error) at slope \(c.slope_bpm_kmh)")
        }
    }

    func testDriftClassificationMatchesPython() {
        for c in v.hr_rise {
            let hr = c.hr.map { (t: $0[0], v: $0[1]) }
            let sp = c.speed.map { (t: $0[0], v: $0[1]) }
            let got = RTMath.classifyHrRise(hrSeries: hr, speedSeries: sp)
            XCTAssertEqual(got.kind, c.expected_kind,
                           "case '\(c.case)' classified as \(got.kind), Python says \(c.expected_kind)")
        }
    }

    // MARK: Signal quality

    func testSignalQualityDetectorsMatchPython() {
        for c in v.signal_quality {
            let hist = c.samples.map {
                HrSample(tS: $0.t_s, hrBpm: $0.hr_bpm, cadenceSpm: $0.cadence_spm,
                         accelSdG: $0.accel_sd_g)
            }
            XCTAssertEqual(cadenceLockSuspicion(hist), c.cadence_lock, accuracy: 0.002,
                           "cadence lock differs for '\(c.case)'")
            XCTAssertEqual(frozenHrSuspicion(hist), c.frozen, accuracy: 0.002,
                           "frozen score differs for '\(c.case)'")
            XCTAssertEqual(notWornSuspicion(hist), c.not_worn, accuracy: 0.002,
                           "not-worn score differs for '\(c.case)'")
        }
    }

    /// The three cases whose *classification* matters most, asserted on the action threshold rather
    /// than the score, because that is what actually changes behaviour.
    func testCriticalSignalQualityDecisionsAgree() {
        func hist(_ name: String) -> [HrSample] {
            let c = v.signal_quality.first { $0.case == name }!
            return c.samples.map {
                HrSample(tS: $0.t_s, hrBpm: $0.hr_bpm, cadenceSpm: $0.cadence_spm,
                         accelSdG: $0.accel_sd_g)
            }
        }
        XCTAssertGreaterThanOrEqual(cadenceLockSuspicion(hist("cadence_lock_true")), 0.8,
                                    "a real lock must be caught")
        XCTAssertLessThan(cadenceLockSuspicion(hist("cadence_lock_false_independent_hr")), 0.8,
                          "an independently-wandering HR near cadence must not be flagged")
        XCTAssertLessThan(cadenceLockSuspicion(hist("cadence_lock_coincidence_constant_cadence")), 0.8,
                          "constant cadence cannot confirm a lock and must not discard the signal")
        XCTAssertGreaterThanOrEqual(frozenHrSuspicion(hist("frozen_running")), 0.8,
                                    "a frozen value during running is unambiguous")
        XCTAssertLessThan(frozenHrSuspicion(hist("frozen_resting")), 0.8,
                          "a repeated resting HR is weak evidence, not a fault")
        XCTAssertGreaterThanOrEqual(notWornSuspicion(hist("not_worn")), 0.7)
        XCTAssertEqual(notWornSuspicion(hist("worn_still_person")), 0.0,
                       "a person sitting still must not read as a removed band")
    }

    // MARK: The controller, end to end

    /// Replays the same closed-loop simulation Python ran and asserts the cue sequence matches.
    ///
    /// This is the strongest parity check in the file: it exercises the lead compensation, the deadband,
    /// the confirmation window, the rate limiter and the feedforward gain together. If any one of them
    /// differs between the two implementations, the cue timing diverges and this fails.
    func testControllerTraceMatchesPython() {
        let t = v.controller_trace
        let zones = ZoneModel.fiveZone(hrMax: 187, hrRest: 55)
        let controller = InRunController(
            zones: zones,
            intent: SessionIntent(kind: "easy", targetZones: [1, 2]),
            hrSpeedSlope: t.hr_speed_slope)
        controller.setState(.steady)

        var hr = 165.0
        var speed = 3.2
        var fired: [(Double, String)] = []
        for tick in 1..<600 {
            let d = controller.update(RunTick(tS: Double(tick), hrBpm: hr, speedMPerS: speed))
            if let cue = d.cue {
                fired.append((Double(tick), cue.key))
                if let c = d.speedCorrectionMPerS { speed = max(1.5, speed + c) }
            }
            // Same first-order plant Python used: 12 bpm per KM/H, so convert the m/s delta.
            let hrTarget = 142.0 + (speed - 2.4) * 3.6 * 12.0
            hr += (hrTarget - hr) / RT.tauHr
        }

        XCTAssertEqual(fired.count, t.cues.count,
                       "cue count differs: Swift \(fired.map(\.1)), Python \(t.cues.map(\.cue_key))")
        for (swift, py) in zip(fired, t.cues) {
            XCTAssertEqual(swift.1, py.cue_key, "cue key differs at t=\(swift.0)")
            XCTAssertEqual(swift.0, py.t_s, accuracy: 1.0,
                           "cue \(py.cue_key) fired at t=\(swift.0), Python had \(py.t_s)")
        }
        XCTAssertEqual(hr, t.final_hr_approx, accuracy: 1.5,
                       "the loop converged somewhere different")
    }

    func testControllerConvergesAndDoesNotOscillate() {
        // The property that matters, stated independently of the recorded trace: a runner starting well
        // above target must be brought into range with very few cues.
        let zones = ZoneModel.fiveZone(hrMax: 187, hrRest: 55)
        let controller = InRunController(
            zones: zones, intent: SessionIntent(kind: "easy", targetZones: [1, 2]),
            hrSpeedSlope: 12)
        controller.setState(.steady)
        var hr = 175.0, speed = 3.4, cues = 0
        for tick in 1..<1200 {
            let d = controller.update(RunTick(tS: Double(tick), hrBpm: hr, speedMPerS: speed))
            if let c = d.speedCorrectionMPerS, d.cue != nil {
                cues += 1
                speed = max(1.5, speed + c)
            }
            let hrTarget = 142.0 + (speed - 2.4) * 3.6 * 12.0
            hr += (hrTarget - hr) / RT.tauHr
        }
        XCTAssertGreaterThan(cues, 0, "the controller must actually intervene")
        XCTAssertLessThanOrEqual(cues, 8, "oscillation: \(cues) cues in 20 minutes")
        let band = zones.band(forZoneIndices: [1, 2])
        XCTAssertLessThan(hr, band.high + 8, "failed to bring HR into range")
    }

    // MARK: Paces

    func testTrainingPaceFloorAgrees() {
        // Physiology.swift does not port the VDOT tables (plan generation stays in Python), but the
        // I/R prescribability floor is a decision the app has to honour, so the boundary is asserted
        // here against the exported values.
        for c in v.paces {
            let expected = c.vdot >= 35
            XCTAssertEqual(c.ir_prescribable, expected,
                           "VDOT \(c.vdot): interval/repetition prescribability disagrees")
        }
    }
}

// MARK: - Weekly review parity
//
// `WeeklyReview` is ported to Swift because it has to run on device every Monday with no server. That
// makes it exactly as much of a divergence risk as the controller, so it gets the same treatment.

final class WeeklyReviewParityTests: XCTestCase {

    private struct Vectors: Decodable {
        struct ReplanCase: Decodable {
            let `case`: String
            let daily_loads: [Double]?
            let planned_volume: Double?
            let achieved_volume: Double
            let sessions_planned: Int
            let sessions_completed: Int
            let readiness_bands: [String]
            let max_pain: Int
            let weeks_since_cutback: Int
            let expected_action: String
            let expected_next_volume: Double?
        }
        struct AcwrCase: Decodable {
            let `case`: String
            let daily_loads: [Double]
            let acute: Double
            let chronic: Double
            let ratio: Double
            let band: String
        }
        let replan: [ReplanCase]
        let acwr: [AcwrCase]
    }

    private static var vectors: Vectors!

    override class func setUp() {
        super.setUp()
        guard let url = Bundle.module.url(forResource: "golden_vectors", withExtension: "json"),
              let data = try? Data(contentsOf: url) else {
            XCTFail("golden_vectors.json missing from the test bundle")
            return
        }
        do { vectors = try JSONDecoder().decode(Vectors.self, from: data) }
        catch { XCTFail("vectors did not decode: \(error)") }
    }

    private var v: Vectors { Self.vectors }

    func testAcwrMatchesPython() {
        for c in v.acwr {
            let got = WeeklyReview.acwr(c.daily_loads)
            XCTAssertEqual(got.acute, c.acute, accuracy: 1e-6, "acute differs for '\(c.case)'")
            XCTAssertEqual(got.chronic, c.chronic, accuracy: 1e-6, "chronic differs for '\(c.case)'")
            XCTAssertEqual(got.ratio, c.ratio, accuracy: 1e-6, "ratio differs for '\(c.case)'")
            XCTAssertEqual(got.band, c.band, "band differs for '\(c.case)'")
        }
    }

    /// The guard that stops a beginner's exploding ratio from vetoing their first weeks of training.
    func testBeginnerRatioIsReportedAsInsufficientHistory() {
        let c = v.acwr.first { $0.case == "beginner_insufficient_history" }!
        let got = WeeklyReview.acwr(c.daily_loads)
        XCTAssertEqual(got.band, "insufficient_history")
        XCTAssertGreaterThan(got.ratio, ReviewConstants.acwrHardCap,
                             "the ratio really is above the cap — which is exactly why the band, not "
                             + "the number, must gate the decision")
    }

    func testReplanDecisionsMatchPython() {
        for c in v.replan {
            let ratio = c.daily_loads.map { WeeklyReview.acwr($0) }
            let d = WeeklyReview.replan(
                plannedVolumeKm: c.planned_volume,
                achievedVolumeKm: c.achieved_volume,
                sessionsPlanned: c.sessions_planned,
                sessionsCompleted: c.sessions_completed,
                acwrResult: ratio,
                readinessBands: c.readiness_bands,
                maxPain: c.max_pain,
                weeksSinceCutback: c.weeks_since_cutback)
            XCTAssertEqual(d.action.rawValue, c.expected_action,
                           "action differs for '\(c.case)'")
            if let expected = c.expected_next_volume {
                XCTAssertEqual(d.nextVolumeKm ?? -1, expected, accuracy: 0.15,
                               "next volume differs for '\(c.case)'")
            }
        }
    }

    /// The rule that stops a disrupted week becoming next week's spike, asserted independently of the
    /// recorded vectors.
    func testMissedVolumeIsNeverCarriedForward() {
        for (planned, achieved, done) in [(40.0, 10.0, 1), (40.0, 20.0, 2), (60.0, 0.0, 0)] {
            let d = WeeklyReview.replan(plannedVolumeKm: planned, achievedVolumeKm: achieved,
                                        sessionsPlanned: 3, sessionsCompleted: done)
            XCTAssertEqual(d.carryForward, "none")
            XCTAssertLessThanOrEqual(d.nextVolumeKm ?? 0, planned,
                                     "the deficit must not be added to next week")
        }
    }

    func testZeroVolumeWeekComesBackAtHalfNotAtFullPlan() {
        // Using the planned figure as the base here would emit the largest jump the engine can produce,
        // in the situation calling for the smallest.
        let d = WeeklyReview.replan(plannedVolumeKm: 40, achievedVolumeKm: 0,
                                    sessionsPlanned: 3, sessionsCompleted: 0)
        XCTAssertEqual(d.action, .rebuild)
        XCTAssertEqual(d.nextVolumeKm ?? 0, 20, accuracy: 0.1)
    }

    func testPainTakesPrecedenceOverEverything() {
        let d = WeeklyReview.replan(plannedVolumeKm: 40, achievedVolumeKm: 40,
                                    sessionsPlanned: 3, sessionsCompleted: 3,
                                    maxPain: 5, weeksSinceCutback: 3)
        XCTAssertEqual(d.action, .hold, "pain must outrank a due cutback")
    }

    func testGateEvaluationRequiresBothGatesAndMinimumWeeks() throws {
        let plans = try PlanStore(bundle: .module)
        let phase = plans.phase("foundation")!
        let allMet: [String: Double?] = [
            "continuous_run_min": 35, "continuous_run_in_z2": 1,
            "max_pain_2wk": 0, "sessions_completed_pct_4wk": 0.9,
        ]
        let early = WeeklyReview.evaluateGates(phase: phase, weeksInPhase: 2,
                                              evidence: allMet, nextPhase: "base_1")
        XCTAssertFalse(early.canAdvance, "bone adapts on its own clock; good numbers cannot shortcut it")
        XCTAssertFalse(early.minWeeksSatisfied)

        let served = WeeklyReview.evaluateGates(phase: phase, weeksInPhase: phase.min_weeks,
                                               evidence: allMet, nextPhase: "base_1")
        XCTAssertTrue(served.canAdvance)
        XCTAssertEqual(served.nextPhase, "base_1")
    }

    func testUnknownEvidenceIsReportedSeparatelyFromFailure() throws {
        let plans = try PlanStore(bundle: .module)
        let phase = plans.phase("foundation")!
        // Deliberately omit one gate entirely rather than supplying a failing value.
        let partial: [String: Double?] = ["continuous_run_min": 35, "max_pain_2wk": 0]
        let e = WeeklyReview.evaluateGates(phase: phase, weeksInPhase: 12,
                                          evidence: partial, nextPhase: "base_1")
        XCTAssertFalse(e.canAdvance)
        XCTAssertFalse(e.unknown.isEmpty, "'not measured' must not be conflated with 'failed'")
        XCTAssertTrue(e.guidance.lowercased().contains("missing"))
    }

    func testSafetyGateFlagSurvivesIntoTheEvaluation() throws {
        let plans = try PlanStore(bundle: .module)
        let phase = plans.phase("base_1")!
        let e = WeeklyReview.evaluateGates(
            phase: phase, weeksInPhase: 12,
            evidence: ["max_pain_2wk": 7], nextPhase: "base_2")
        let pain = (e.unmet + e.met).first { $0.key == "max_pain_2wk" }
        XCTAssertNotNil(pain)
        XCTAssertTrue(pain!.safety, "a safety gate that loses its flag is one the app will let you waive")
    }

    func testStallProducesDiagnosticsIncludingFuelling() throws {
        let plans = try PlanStore(bundle: .module)
        let phase = plans.phase("foundation")!
        let e = WeeklyReview.evaluateGates(
            phase: phase, weeksInPhase: (phase.stall_review_weeks ?? 14) + 1,
            evidence: ["continuous_run_min": 12, "continuous_run_in_z2": 0,
                       "max_pain_2wk": 0, "sessions_completed_pct_4wk": 0.9],
            nextPhase: "base_1")
        XCTAssertTrue(e.stalled)
        XCTAssertTrue(e.diagnostics.contains { $0.lowercased().contains("fuel") },
                      "under-fuelling looks exactly like 'not adapting' and must be considered")
    }

    func testGateThresholdsDecodeForBothNumbersAndBooleans() throws {
        let plans = try PlanStore(bundle: .module)
        let gates = plans.gates(phase: "base_1")
        let numeric = gates.first { $0.key == "weekly_km_3wk_min" }
        let boolean = gates.first { $0.key == "time_trial_2000m_done" }
        XCTAssertEqual(numeric?.valueNumber, 20)
        XCTAssertEqual(boolean?.valueBool, true)
    }
}
