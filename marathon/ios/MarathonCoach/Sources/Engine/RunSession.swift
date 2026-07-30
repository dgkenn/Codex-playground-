//
//  RunSession.swift
//  The orchestrator: turns three async sensor streams into one coherent 1 Hz decision loop.
//
//  Everything else in this app is a pure function or a single-purpose driver. This is the file where
//  they meet, and it exists mainly to solve one problem: **the sensors do not agree on time.**
//
//  The Verity delivers heart rate at roughly 1 Hz and accelerometer batches at 52 Hz. CoreLocation
//  delivers fixes at a rate that varies with signal quality and can stop entirely for a minute under
//  tree cover. The controller needs exactly one tick per second with a consistent view of both. So
//  rather than letting whichever sensor fires last drive the loop — which produces a decision cadence
//  that varies with satellite geometry — a timer runs at 1 Hz and *samples* the most recent value from
//  each stream, marking anything stale as unavailable.
//
//  That choice matters for correctness, not just tidiness. The controller's lead compensation
//  estimates dHR/dt by regression over a 30-second window; if the sample spacing wobbles with GPS
//  quality, the slope estimate wobbles with it, and the controller starts responding to signal
//  conditions instead of physiology.
//
//  ## What is written where
//
//  * Every tick appends one line to the run's trace file — incrementally, so a crash at 2:40 into a
//    long run leaves everything up to 2:40 intact.
//  * The session summary and the HealthKit workout are written once, at the end.
//  * A safety abort writes the summary immediately, before anything else, because that is the case
//    where the app is most likely to be closed abruptly.
//

import Foundation
import Combine

@MainActor
public final class RunSession: ObservableObject {

    public enum State: String { case idle, running, paused, finished, aborted }

    @Published public private(set) var state: State = .idle
    @Published public private(set) var elapsed: TimeInterval = 0
    @Published public private(set) var decision: ControlDecision?
    @Published public private(set) var paceQuality: PaceSample.Quality = .unavailable
    @Published public private(set) var hrStatus: String = "dropout"

    // Display state, published so the run screen observes ONE controller rather than instantiating a
    // second one of its own. An earlier version did exactly that, and the screen showed a permanently
    // unknown zone state while the real controller ran invisibly behind it.
    @Published public private(set) var hr: Double?
    @Published public private(set) var paceSecKm: Double?
    @Published public private(set) var cadence: Double?
    @Published public private(set) var distanceM: Double = 0
    @Published public private(set) var targetBand: (low: Double, high: Double)?
    @Published public private(set) var lastCue: Cue?
    @Published public private(set) var zoneState: ZoneState = .unknown

    public enum ZoneState {
        case inZone, tooHard, tooEasy, unknown

        public var label: String {
            switch self {
            case .inZone: return "On target"
            case .tooHard: return "Too hard"
            case .tooEasy: return "Room to lift"
            case .unknown: return "No heart rate"
            }
        }
        /// Redundant with colour by design: red/green is the worst possible pair to rely on alone, and
        /// saturation washes out in sunlight.
        public var symbol: String {
            switch self {
            case .inZone: return "checkmark.circle.fill"
            case .tooHard: return "arrow.down.circle.fill"
            case .tooEasy: return "arrow.up.circle.fill"
            case .unknown: return "questionmark.circle.fill"
            }
        }
    }

    public let runID = UUID()

    private let sensor: VeritySensor
    private let location: LocationPace
    private let audio: AudioCoach
    private let store: Store
    private let controller: InRunController
    private let intent: SessionIntent
    private let profile: AthleteProfile
    private let zones: ZoneModel
    private let plannedTitle: String
    private let health: HealthKitBridge

    private var timer: Timer?
    private var startedAt: Date?
    private var bag = Set<AnyCancellable>()

    // Latest values sampled by the tick, plus when they arrived.
    private var lastHr: (value: Double, at: Date)?
    private var lastHrStatus: String = "dropout"
    private var lastCadence: (value: Double, at: Date)?
    private var lastPace: PaceSample?
    private var pendingPain: Int?
    private var pendingSymptom: String?

    // Accumulators for the summary.
    private var hrSamples: [(Date, Double)] = []
    private var hrTicks = 0
    private var usableHrTicks = 0
    private var frozenTicks = 0
    private var cadenceSamples: [Double] = []
    // Pace-quality tallies, so stride calibration can require that GPS was genuinely good rather than
    // merely present.
    private var paceTicks = 0
    private var goodPaceTicks = 0
    // Labelled tuples, because Swift will not implicitly convert [(Double, Double)] into
    // [(speed: Double, hr: Double)] at the decoupling call site.
    private var firstHalf: [(speed: Double, hr: Double)] = []
    private var secondHalf: [(speed: Double, hr: Double)] = []

    /// The gate that decides whether a heart rate may drive control at all.
    private var gate = HrGate()

    public init(sensor: VeritySensor, location: LocationPace, audio: AudioCoach, store: Store,
                health: HealthKitBridge, profile: AthleteProfile, zones: ZoneModel,
                intent: SessionIntent, plannedTitle: String) {
        self.sensor = sensor
        self.location = location
        self.audio = audio
        self.store = store
        self.health = health
        self.profile = profile
        self.zones = zones
        self.intent = intent
        self.plannedTitle = plannedTitle
        self.controller = InRunController(zones: zones, intent: intent,
                                          hrSpeedSlope: profile.hrSpeedSlope)
    }

    // MARK: Lifecycle

    public func start(indoor: Bool = false) {
        guard state == .idle else { return }
        startedAt = Date()
        state = .running
        controller.setState(.warmup)

        // .run mode, explicitly: PPI would throttle heart rate to one update per five seconds, which
        // is useless for a controller whose HR time constant is forty-five.
        sensor.start(mode: .run)
        location.start(mode: indoor ? .treadmill : .outdoor)

        sensor.readings
            .receive(on: DispatchQueue.main)
            .sink { [weak self] r in self?.ingest(sensor: r) }
            .store(in: &bag)
        location.samples
            .receive(on: DispatchQueue.main)
            .sink { [weak self] s in self?.ingest(pace: s) }
            .store(in: &bag)

        // Fixed 1 Hz decision cadence, independent of sensor arrival times. See the file header.
        let t = Timer(timeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    public func pause() {
        guard state == .running else { return }
        state = .paused
        controller.setState(.paused)
    }

    public func resume() {
        guard state == .paused else { return }
        state = .running
        controller.setState(.steady)
    }

    /// Called by the UI when the runner logs pain. Reaches the controller on the next tick, which is
    /// where the safety abort lives.
    public func reportPain(_ level: Int) { pendingPain = level }
    public func reportSymptom(_ symptom: String) { pendingSymptom = symptom }

    /// Mark the warm-up over so the controller starts correcting pace.
    public func beginMainSet() { controller.setState(.steady) }

    public func finish() async {
        guard state == .running || state == .paused else { return }
        state = .finished
        await teardown(aborted: false)
    }

    // MARK: Ingest

    private func ingest(sensor r: VerityReading) {
        if let hr = r.hrBpm, hr > 0 {
            lastHr = (Double(hr), r.timestamp)
        }
        if let cad = r.cadenceSpm {
            lastCadence = (cad, r.timestamp)
            location.updateCadence(cad, at: r.timestamp)
        }
    }

    private func ingest(pace s: PaceSample) {
        lastPace = s
        paceQuality = s.quality
    }

    // MARK: The loop

    private func tick() {
        guard state == .running, let started = startedAt else { return }
        let now = Date()
        elapsed = now.timeIntervalSince(started)

        // Sample HR, marking it stale rather than trusting an old value. Two seconds is generous at
        // 1 Hz and tight enough that a dropout is caught within a tick.
        var hrValue: Double?
        if let last = lastHr, now.timeIntervalSince(last.at) <= 2.0 {
            hrValue = last.value
        }
        var cadValue: Double?
        if let last = lastCadence, now.timeIntervalSince(last.at) <= 5.0 {
            cadValue = last.value
        }

        // Run the gate. This is what catches dropout, cadence lock-on, a frozen value, and a band
        // that is not being worn -- none of which the raw number reveals.
        if let hr = hrValue {
            lastHrStatus = gate.update(HrSample(tS: elapsed, hrBpm: hr, cadenceSpm: cadValue,
                                                accelSdG: nil))
        } else {
            lastHrStatus = gate.tick(elapsed)
        }
        hrStatus = lastHrStatus

        hrTicks += 1
        if lastHrStatus == "ok" { usableHrTicks += 1 }
        if lastHrStatus == "frozen" { frozenTicks += 1 }
        if let hr = hrValue, lastHrStatus == "ok" { hrSamples.append((now, hr)) }
        if let c = cadValue { cadenceSamples.append(c) }
        if let q = pace?.quality {
            paceTicks += 1
            if q == .good { goodPaceTicks += 1 }
        }

        let pace = lastPace
        let speed = pace?.speedMPerS
        if let s = speed, let hr = hrValue, lastHrStatus == "ok", s > 0.5 {
            // Split-half accumulation for decoupling. Halved by elapsed time rather than by sample
            // count so a mid-run GPS gap does not skew which samples land in which half.
            if elapsed < (intent.plannedDurationS ?? 3600) / 2 {
                firstHalf.append((speed: s, hr: hr))
            } else {
                secondHalf.append((speed: s, hr: hr))
            }
        }

        let tick = RunTick(tS: elapsed,
                           hrBpm: lastHrStatus == "ok" ? hrValue : nil,
                           hrStatus: lastHrStatus,
                           speedMPerS: speed,
                           grade: pace?.grade ?? 0,
                           cadenceSpm: cadValue,
                           distanceM: pace?.distanceM ?? 0,
                           pain0to10: pendingPain,
                           symptom: pendingSymptom)
        pendingPain = nil
        pendingSymptom = nil

        let d = controller.update(tick)
        decision = d
        if let cue = d.cue {
            audio.speak(cue)
            lastCue = cue
        }

        // Publish display state from the one controller that is actually running.
        hr = lastHrStatus == "ok" ? hrValue : nil
        cadence = cadValue
        distanceM = pace?.distanceM ?? 0
        paceSecKm = (speed ?? 0) > 0.3 ? Physiology.speedToPace(mPerS: speed!) : nil
        targetBand = d.targetBand
        switch (d.inTarget, d.mode) {
        case (_, .effortOnly), (nil, _):
            zoneState = .unknown
        case (true?, _):
            zoneState = .inZone
        case (false?, _):
            if let ss = d.hrSteadyState, let b = d.targetBand {
                zoneState = ss > b.high ? .tooHard : (intent.ceilingOnly ? .inZone : .tooEasy)
            } else {
                zoneState = .tooHard
            }
        }

        store.appendTrace(runID: runID, line: [
            "t_s": round(elapsed),
            "hr": hrValue ?? NSNull(),
            "hr_status": lastHrStatus,
            "speed_m_s": speed ?? NSNull(),
            "cadence_spm": cadValue ?? NSNull(),
            "grade": pace?.grade ?? NSNull(),
            "distance_m": pace?.distanceM ?? 0,
            "pace_quality": pace?.quality.rawValue ?? "unavailable",
            "in_target": d.inTarget ?? NSNull(),
            "hr_ss": d.hrSteadyState ?? NSNull(),
            "cue": d.cue?.key ?? NSNull(),
        ])

        if d.abort {
            state = .aborted
            Task { await teardown(aborted: true) }
        }
    }

    // MARK: Teardown

    private func teardown(aborted: Bool) async {
        timer?.invalidate(); timer = nil
        bag.removeAll()
        sensor.stop()
        location.stop()
        audio.stop()

        guard let started = startedAt else { return }
        let end = Date()
        let durationMin = end.timeIntervalSince(started) / 60
        let distanceKm = (lastPace?.distanceM ?? 0) / 1000

        let hrs = hrSamples.map(\.1)
        let meanHr = hrs.isEmpty ? nil : hrs.reduce(0, +) / Double(hrs.count)
        let peakHr = hrs.max()
        let meanCad = cadenceSamples.isEmpty
            ? nil : cadenceSamples.reduce(0, +) / Double(cadenceSamples.count)
        let coverage = hrTicks > 0 ? Double(usableHrTicks) / Double(hrTicks) : 0
        let frozenFraction = hrTicks > 0 ? Double(frozenTicks) / Double(hrTicks) : 0

        // Decoupling only when there is enough of both halves to mean anything. Reporting it from a
        // 20-minute run would be noise wearing a number's clothes.
        var decoupling: Double?
        if firstHalf.count > 300 && secondHalf.count > 300 {
            decoupling = Physiology.decoupling(firstHalf: firstHalf, secondHalf: secondHalf)
        }

        // TRIMP is only meaningful with decent HR coverage. Below 80% the number would understate the
        // session, and an understated load feeds a ramp that then adds more than it should.
        var trimp: Double?
        if let mean = meanHr, coverage >= 0.8 {
            let dhr = max(0, min(1.3, (mean - profile.hrRest) / (profile.hrMax - profile.hrRest)))
            trimp = durationMin * dhr * 0.64 * exp(1.92 * dhr)
        }

        // Treadmill stride calibration, derived rather than asked for.
        //
        // Stride length is distance divided by steps taken. It is only trustworthy from a run where GPS
        // was actually good, so the quality gate matters more than the arithmetic: calibrating from a
        // run under tree cover would bake a GPS error into every future treadmill session. Kept as a
        // running average over calibrations rather than overwritten, because stride varies with pace and
        // one run at one pace is a narrow sample.
        if location.mode == .outdoor, let cad = meanCad, cad > 100,
           distanceKm > 2.0, goodPaceTicks >= Int(0.8 * Double(max(1, paceTicks))) {
            let steps = cad * durationMin
            let stride = (distanceKm * 1000) / steps
            // Adult running stride is roughly 0.9-1.6 m; anything outside that is a measurement fault,
            // not a person.
            if stride > 0.85, stride < 1.75 {
                var p = profile
                if let existing = p.calibratedStrideM {
                    p.calibratedStrideM = existing * 0.7 + stride * 0.3
                } else {
                    p.calibratedStrideM = stride
                }
                try? store.save(profile: p)
            }
        }

        var record = SessionRecord(
            date: started, phase: "", weekInPhase: 0, plannedTitle: plannedTitle,
            sessionType: intent.kind, completed: !aborted, durationMin: durationMin,
            distanceKm: distanceKm, meanHr: meanHr, peakHr: peakHr, meanCadence: meanCad,
            rpe0to10: nil, hrCoverage: coverage, frozenFraction: frozenFraction,
            decoupling: decoupling, trimp: trimp)
        record.traceFile = store.traceURL(runID: runID).lastPathComponent
        if aborted {
            record.notes = "Aborted by the safety check: \(decision?.reason ?? "unknown")."
        }
        if coverage < 0.8 {
            record.notes += (record.notes.isEmpty ? "" : " ")
                + String(format: "Heart rate was usable for only %.0f%% of this run, so no training "
                         + "load was recorded for it. ", coverage * 100)
        }
        if frozenFraction > 0.1 {
            record.notes += String(format: "Heart rate was frozen at a stale value for %.0f%% of the "
                                   + "run — check the strap position. ", frozenFraction * 100)
        }
        try? store.append(session: record)

        // HealthKit last: it is the least important write and the most likely to fail (permissions),
        // so it must never be able to lose the session record.
        if !hrSamples.isEmpty || distanceKm > 0 {
            let payload = HealthKitBridge.WorkoutPayload(
                start: started, end: end, distanceM: lastPace?.distanceM ?? 0,
                activeEnergyKcal: nil, heartRates: hrSamples,
                indoor: location.mode == .treadmill)
            try? await health.save(workout: payload)
        }
    }
}
