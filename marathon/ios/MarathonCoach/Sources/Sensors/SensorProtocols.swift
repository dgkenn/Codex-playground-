//
//  SensorProtocols.swift
//  The seams that let a run be driven by something other than hardware.
//
//  `RunSession` used to take `VeritySensor`, `LocationPace` and `AudioCoach` as concrete types. That
//  made one sentence in `MarathonCoachApp.swift` false — the one claiming the logic "can be exercised
//  in tests with fakes in place of the sensors." It could not: there was nothing to substitute.
//
//  The practical consequence was worse than the inaccuracy. The iOS Simulator has no CoreBluetooth,
//  so a concrete `VeritySensor` can never connect there, which meant the **first** execution of the
//  full loop — sensor to gate to controller to spoken cue — was always going to be a real run. A
//  defect found that way costs a training session, and worse, costs trust in the cues at the exact
//  moment the cues need to be obeyed.
//
//  These protocols are deliberately narrow: they expose only what `RunSession` actually calls, which
//  turned out to be nine members across three types. A wider protocol would be a re-description of
//  the classes rather than a seam.
//
//  This file imports Combine and is therefore Apple-only. The *data* types it traffics in are not —
//  see `SensorTypes.swift` — which is what lets the scenario engine run on any machine.
//

import Foundation
import Combine

// MARK: - Heart rate

/// Anything that can produce heart rate, cadence and beat intervals on a schedule.
public protocol HeartRateSource: AnyObject {
    var readings: PassthroughSubject<VerityReading, Never> { get }
    var status: VerityStatus { get }
    func start(mode: SensorMode)
    func stop()
}

// MARK: - Pace

/// Anything that can produce speed, distance and grade.
///
/// `updateCadence` is here because pace and cadence are not independent: in treadmill mode distance
/// *is* cadence times stride, and outdoors cadence is the sanity check that catches a GPS speed which
/// disagrees with the legs. A pace source that could not be told the cadence would have to guess.
public protocol PaceSource: AnyObject {
    var samples: PassthroughSubject<PaceSample, Never> { get }
    var mode: PaceMode { get }
    var calibratedStrideM: Double? { get set }
    func start(mode: PaceMode)
    func stop()
    func updateCadence(_ spm: Double?, at time: Date)
}

// MARK: - Voice

/// Anything that can say a cue out loud.
///
/// Kept separate from the sources because it is the one collaborator a simulated run should *not*
/// replace: the whole point of replaying a run on the phone is to hear the real cue, at the real
/// rate, ducking the real music.
public protocol CoachAudio: AnyObject {
    func speak(_ cue: Cue)
    func stop()
}

// MARK: - Workout storage

/// The one thing `RunSession` asks of HealthKit. Behind a protocol so a replayed run can be made
/// incapable of writing a fake workout into your real health record.
public protocol WorkoutRecorder: AnyObject {
    func save(workout: MarathonWorkoutPayload) async throws
}

// MARK: - Conformances

extension VeritySensor: HeartRateSource {}
extension LocationPace: PaceSource {}
extension AudioCoach: CoachAudio {}
extension HealthKitBridge: WorkoutRecorder {}
