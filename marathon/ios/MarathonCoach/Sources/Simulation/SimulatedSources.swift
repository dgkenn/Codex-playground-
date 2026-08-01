//
//  SimulatedSources.swift
//  Drop-in replacements for the armband and the GPS, so a whole run can be rehearsed on the sofa.
//
//  The portable scenario engine (`RunScenario.swift`) already proves the *control logic* is right,
//  instantly and on any machine. This file exists for the half that engine cannot reach: the audio
//  session, the run screen, the HealthKit write path, the trace file, and everything else that only
//  exists once the app is running on a phone.
//
//  In particular it is the only way to answer the question that matters most day to day — **does a
//  cue duck Apple Music and hand it back cleanly, in the right voice, at the right moment, through
//  AirPods** — without going for a run. The iOS Simulator has no Bluetooth, so a real `VeritySensor`
//  can never answer it there, and on a phone the answer would otherwise cost forty minutes and a
//  pair of shoes each time.
//
//  What is deliberately *not* simulated: `AudioCoach`. The whole point is to hear the real one.
//

import Foundation
import Combine

// MARK: - Heart rate

/// Replays a scenario's heart rate, cadence and fault injection as if it were the armband.
public final class SimulatedHeartRateSource: HeartRateSource {

    public let readings = PassthroughSubject<VerityReading, Never>()
    public private(set) var status: VerityStatus

    private let scenario: RunScenario
    private let zones: ZoneModel
    private var precomputed: [ScenarioTick] = []
    private var index = 0
    private var timer: Timer?
    private let timeScale: Double

    public init(scenario: RunScenario, zones: ZoneModel, timeScale: Double = 1) {
        self.scenario = scenario
        self.zones = zones
        self.timeScale = max(1, timeScale)
        self.status = .simulating(scenario: scenario.name)
        // Precomputed from the same simulator the tests use, so what plays on the phone is the run
        // the test suite asserted about. Two different generators would be two different runs.
        self.precomputed = RunSimulator.run(scenario, zones: zones).ticks
    }

    public func start(mode: SensorMode) {
        stop()
        index = 0
        status = .simulating(scenario: scenario.name)
        let t = Timer(timeInterval: 1.0 / timeScale, repeats: true) { [weak self] _ in
            self?.emit()
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func emit() {
        guard index < precomputed.count else { stop(); return }
        let tick = precomputed[index]
        index += 1
        // A dropout is the *absence* of a reading, not a reading containing nil. Emitting nothing is
        // what makes the session's staleness check the thing under test.
        guard let hr = tick.hrBpm else { return }
        readings.send(VerityReading(timestamp: Date(), hrBpm: Int(hr.rounded()),
                                    intervalsMs: [], cadenceSpm: tick.cadenceSpm,
                                    skinContact: nil, batteryPercent: 88, source: .simulated))
    }
}

// MARK: - Pace

public final class SimulatedPaceSource: PaceSource {

    public let samples = PassthroughSubject<PaceSample, Never>()
    public private(set) var mode: PaceMode = .outdoor
    public var calibratedStrideM: Double?

    private let ticks: [ScenarioTick]
    private var index = 0
    private var timer: Timer?
    private let timeScale: Double

    public init(scenario: RunScenario, zones: ZoneModel, timeScale: Double = 1) {
        self.timeScale = max(1, timeScale)
        self.ticks = RunSimulator.run(scenario, zones: zones).ticks
    }

    public func start(mode: PaceMode) {
        stop()
        self.mode = mode
        index = 0
        let t = Timer(timeInterval: 1.0 / timeScale, repeats: true) { [weak self] _ in
            self?.emit()
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
    }

    /// Accepted and ignored: the scenario already knows what the cadence was.
    public func updateCadence(_ spm: Double?, at time: Date) {}

    private func emit() {
        guard index < ticks.count else { stop(); return }
        let tick = ticks[index]
        index += 1
        samples.send(PaceSample(timestamp: Date(), speedMPerS: tick.speedMPerS,
                                distanceM: tick.distanceM, grade: tick.grade,
                                quality: tick.paceQuality))
    }
}

// MARK: - Workout recorder

/// Swallows the workout instead of writing it.
///
/// `RunSession` already refuses to write a simulated run to HealthKit, so this is the second of two
/// independent guards. Two guards rather than one because the failure is silent and permanent: a
/// fabricated 10 km workout in the Health app is not obviously wrong when you see it, and removing it
/// later means finding it first.
public final class DiscardingWorkoutRecorder: WorkoutRecorder {
    public private(set) var attempts = 0
    public init() {}
    public func save(workout: MarathonWorkoutPayload) async throws { attempts += 1 }
}

// MARK: - Factory

public enum SimulatedRun {

    /// Build a `RunSession` wired to a scenario, using the **real** audio coach and the real store.
    ///
    /// - Parameter timeScale: simulated seconds per real second. 1 plays in real time, which is what
    ///   you want when judging whether the cue rate is tolerable. 30–60 is for checking a whole run's
    ///   worth of cues quickly.
    @MainActor
    public static func session(scenario: RunScenario, zones: ZoneModel, profile: AthleteProfile,
                               audio: CoachAudio, store: Store,
                               timeScale: Double = 1) -> RunSession {
        RunSession(sensor: SimulatedHeartRateSource(scenario: scenario, zones: zones,
                                                    timeScale: timeScale),
                   location: SimulatedPaceSource(scenario: scenario, zones: zones,
                                                 timeScale: timeScale),
                   audio: audio,
                   store: store,
                   health: DiscardingWorkoutRecorder(),
                   profile: profile,
                   zones: zones,
                   intent: scenario.intent,
                   plannedTitle: "SIMULATED — \(scenario.name)",
                   simulated: true,
                   timeScale: timeScale)
    }
}
