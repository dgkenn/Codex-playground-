//
//  RunScenario.swift
//  A runner that does not exist, running a session that never happened, so the coaching can be wrong
//  somewhere cheap.
//
//  ## Why a plant and not a recording
//
//  The obvious way to test a run controller is to replay a recorded run through it. That is useful
//  and this file supports it (`RunScenario.replaying`), but on its own it tests an **open** loop: the
//  recording does not react, so the controller can say "ease off" a hundred times and the heart rate
//  in the file will do exactly what it always did. Every oscillation bug survives that test.
//
//  So the default scenarios close the loop. A simple physiological plant converts speed into heart
//  rate with a first-order lag, and a simulated athlete converts the controller's cues into speed
//  changes after a human reaction delay. Now a controller that over-corrects produces a heart rate
//  that overshoots, which produces the opposite cue, which is visible in the transcript as the
//  cue sequence oscillating — the failure mode that actually matters, and the one an open-loop replay
//  cannot show.
//
//  ## The plant
//
//  Heart rate follows speed as a first-order system with the same 45 s time constant the controller
//  assumes (`RT.tauHr`). This is deliberately *not* an independent model: using a different tau here
//  would mostly test whether the two guesses agree. What it does test is everything the controller
//  adds on top — deadband, confirmation window, rate limiting, the gate — under a plant that lags in
//  the way real physiology lags.
//
//  Cardiac drift is added as a slow upward ramp, because drift is the single most common reason a
//  steady effort earns a "slow down" forty minutes in, and the controller's response to it is one of
//  the things most worth watching.
//
//  ## What this file may not import
//
//  Foundation only. No Combine, no CoreBluetooth, no SwiftUI — this has to run under `swift test` on
//  a machine with no Apple frameworks, because a harness you can only run on the hardware you are
//  trying to avoid needing is not a harness.
//

import Foundation

// MARK: - Faults

/// A sensor or environment failure, injected over a time window.
///
/// These are the four optical-HR failure modes the signal-quality layer exists to catch, plus the two
/// environmental ones. Being able to inject them on demand is most of the value of this harness: on a
/// real run you have to wait for a strap to shift, and you cannot ask it to shift again.
public enum RunFault: Equatable {
    /// Heart rate sticks at the last value. Polar's own documentation: "If movement is detected, the
    /// heart rate is fixed to the last reliable value."
    case frozenHr(from: Double, to: Double)
    /// No readings arrive at all.
    case dropout(from: Double, to: Double)
    /// The optical sensor locks onto step rate instead of pulse, so HR tracks cadence.
    case cadenceLock(from: Double, to: Double)
    /// Band off the arm: still reporting, stillness in the accelerometer. Polar warns skin-contact
    /// detection on this device is unreliable, so this must be caught from the signal, not the flag.
    case notWorn(from: Double, to: Double)
    /// GPS degrades to unusable — a tunnel, a city street, heavy tree cover.
    case gpsLoss(from: Double, to: Double)
    /// A hill, as a constant grade over a window.
    case grade(from: Double, to: Double, rise: Double)
    /// The athlete reports pain at a moment.
    case pain(at: Double, level: Int)
    /// The athlete ignores the cues, to check the escalation path.
    case nonCompliance(from: Double, to: Double)

    var window: (Double, Double) {
        switch self {
        case .frozenHr(let a, let b), .dropout(let a, let b), .cadenceLock(let a, let b),
             .notWorn(let a, let b), .gpsLoss(let a, let b), .nonCompliance(let a, let b):
            return (a, b)
        case .grade(let a, let b, _): return (a, b)
        case .pain(let t, _): return (t, t + 1)
        }
    }
    func active(at t: Double) -> Bool { let w = window; return t >= w.0 && t < w.1 }
}

// MARK: - The simulated athlete's body

/// First-order heart-rate response to speed, plus cardiac drift.
public struct RunnerPlant {
    /// Heart rate at rest and the slope of HR against speed, in bpm per m/s.
    public var hrRest: Double
    public var hrMax: Double
    /// bpm per km/h — the same units the controller's feedforward gain uses, converted internally.
    public var hrPerKmh: Double
    /// Cardiac drift in bpm per minute at steady effort.
    public var driftBpmPerMin: Double
    /// Heart rate now.
    public private(set) var hr: Double
    /// Speed now, m/s.
    public private(set) var speed: Double

    private var driftAccumulated: Double = 0

    public init(hrRest: Double = 55, hrMax: Double = 187, hrPerKmh: Double = 12,
                driftBpmPerMin: Double = 0.25, startSpeed: Double = 0) {
        self.hrRest = hrRest
        self.hrMax = hrMax
        self.hrPerKmh = hrPerKmh
        self.driftBpmPerMin = driftBpmPerMin
        self.hr = hrRest
        self.speed = startSpeed
    }

    /// Steady-state heart rate for a speed, before drift.
    public func steadyState(for speedMPerS: Double, grade: Double = 0) -> Double {
        // Grade costs energy; reuse the same Minetti-derived factor the rest of the app uses so a hill
        // in the simulator costs what a hill costs in the plan.
        let equivalent = speedMPerS * Physiology.gradeAdjustedPaceFactor(grade: grade)
        let kmh = equivalent * 3.6
        return min(hrMax, hrRest + kmh * hrPerKmh)
    }

    public mutating func step(dt: Double, grade: Double = 0) {
        let target = steadyState(for: speed, grade: grade) + driftAccumulated
        // Exponential approach with the controller's assumed time constant.
        let alpha = 1 - exp(-dt / RT.tauHr)
        hr += (target - hr) * alpha
        // Drift only accumulates while actually working.
        if speed > 1.5 { driftAccumulated += driftBpmPerMin * dt / 60.0 }
        hr = min(hrMax, max(hrRest, hr))
    }

    public mutating func setSpeed(_ s: Double) { speed = max(0, s) }
}

// MARK: - The simulated athlete's compliance

/// Turns a spoken cue into a change of speed, after a delay.
///
/// The delay matters. A runner who responded instantly would hide exactly the lag the controller's
/// confirmation window exists to tolerate; a runner who responded not at all would make every test an
/// escalation test.
public struct AthleteResponse {
    /// Seconds between hearing a cue and the legs changing.
    public var reactionS: Double = 4
    /// Fraction of the requested correction actually applied.
    public var compliance: Double = 0.85
    /// How much a qualitative cue ("ease off") changes speed, m/s.
    public var qualitativeStep: Double = 0.25

    public init(reactionS: Double = 4, compliance: Double = 0.85, qualitativeStep: Double = 0.25) {
        self.reactionS = reactionS
        self.compliance = compliance
        self.qualitativeStep = qualitativeStep
    }

    public func speedChange(for cue: Cue, requested: Double?) -> Double {
        if let r = requested { return r * compliance }
        let text = cue.text.lowercased()
        if text.contains("ease") || text.contains("slow") || text.contains("walk") {
            return -qualitativeStep * compliance
        }
        if text.contains("lift") || text.contains("pick") || text.contains("faster") {
            return qualitativeStep * compliance
        }
        return 0
    }
}

// MARK: - Scenario

public struct RunScenario {
    public let name: String
    public let summary: String
    public let intent: SessionIntent
    public let durationS: Double
    /// Speed the athlete intends to hold, m/s, as a function of elapsed time. This is the athlete's
    /// own plan; the controller then corrects it.
    public let intendedSpeed: (Double) -> Double
    public let faults: [RunFault]
    public var plant: RunnerPlant
    public var response: AthleteResponse
    public var indoor: Bool

    public init(name: String, summary: String, intent: SessionIntent, durationS: Double,
                intendedSpeed: @escaping (Double) -> Double, faults: [RunFault] = [],
                plant: RunnerPlant = RunnerPlant(), response: AthleteResponse = AthleteResponse(),
                indoor: Bool = false) {
        self.name = name
        self.summary = summary
        self.intent = intent
        self.durationS = durationS
        self.intendedSpeed = intendedSpeed
        self.faults = faults
        self.plant = plant
        self.response = response
        self.indoor = indoor
    }
}

// MARK: - One tick of simulated sensor output

public struct ScenarioTick {
    public let tS: Double
    public let hrBpm: Double?
    public let speedMPerS: Double?
    public let cadenceSpm: Double?
    public let grade: Double
    public let distanceM: Double
    public let accelSdG: Double?
    public let paceQuality: PaceSample.Quality
    public let pain: Int?
}

// MARK: - Result

public struct SimulationResult {
    public let scenario: String
    public var ticks: [ScenarioTick] = []
    public var decisions: [ControlDecision] = []
    /// `(second, cue)` for everything actually spoken.
    public var spoken: [(t: Double, cue: Cue)] = []
    public var hrStatuses: [String] = []
    public var aborted = false
    public var abortReason: String?
    public var distanceM: Double = 0

    public var spokenTexts: [String] { spoken.map(\.cue.text) }
    public var usableHrFraction: Double {
        guard !hrStatuses.isEmpty else { return 0 }
        return Double(hrStatuses.filter { $0 == "ok" }.count) / Double(hrStatuses.count)
    }
    /// Cue rate per minute — the number that decides whether the app is a coach or a nag.
    public var cuesPerMinute: Double {
        guard let last = ticks.last?.tS, last > 0 else { return 0 }
        return Double(spoken.count) / (last / 60.0)
    }

    /// A human-readable transcript. This is the artefact worth reading before a first real run: it is
    /// literally what the app will say, in order, with the reason beside it.
    public func transcript() -> String {
        var out = ["=== \(scenario) ==="]
        for (t, cue) in spoken {
            let mm = Int(t) / 60, ss = Int(t) % 60
            out.append(String(format: "%02d:%02d  [%@] %@", mm, ss,
                              String(describing: cue.level), cue.text))
        }
        if aborted { out.append("ABORTED: \(abortReason ?? "unknown")") }
        out.append(String(format: "-- %d cues in %.0f min (%.2f/min), HR usable %.0f%%, %.2f km",
                          spoken.count, (ticks.last?.tS ?? 0) / 60, cuesPerMinute,
                          usableHrFraction * 100, distanceM / 1000))
        return out.joined(separator: "\n")
    }
}

// MARK: - The simulator

public enum RunSimulator {

    /// Run a scenario through the real controller, gate and cue scheduler at 1 Hz.
    ///
    /// Deterministic: no randomness, no wall clock. The same scenario always produces the same
    /// transcript, which is what makes it usable as a snapshot test.
    public static func run(_ scenario: RunScenario, zones: ZoneModel,
                           hrSpeedSlope: Double = 12) -> SimulationResult {
        var s = scenario
        var result = SimulationResult(scenario: scenario.name)
        let controller = InRunController(zones: zones, intent: scenario.intent,
                                         hrSpeedSlope: hrSpeedSlope)
        let gate = HrGate()
        let scheduler = CueScheduler()

        var distance: Double = 0
        var frozenAt: Double?
        var pendingChange: (applyAt: Double, delta: Double)?
        var controllerSpeedBias: Double = 0

        controller.setState(.warmup)
        var state: RunState = .warmup

        var t: Double = 0
        while t < s.durationS {
            let faultsNow = s.faults.filter { $0.active(at: t) }
            func has(_ match: (RunFault) -> Bool) -> Bool { faultsNow.contains(where: match) }

            let grade = faultsNow.compactMap { f -> Double? in
                if case .grade(_, _, let rise) = f { return rise }
                return nil
            }.first ?? 0

            // --- the athlete's legs -------------------------------------------------------------
            let compliant = !has { if case .nonCompliance = $0 { return true }; return false }
            if let p = pendingChange, t >= p.applyAt {
                if compliant { controllerSpeedBias += p.delta }
                pendingChange = nil
            }
            let intended = s.intendedSpeed(t) + controllerSpeedBias
            s.plant.setSpeed(max(0, intended))
            s.plant.step(dt: 1.0, grade: grade)

            // --- what the sensors report --------------------------------------------------------
            let trueHr = s.plant.hr
            // Cadence rises with speed; the relationship is loose in reality but monotonic, which is
            // all the cadence-lock detector needs to be exercised.
            var cadence: Double? = s.plant.speed > 0.5 ? 150 + s.plant.speed * 6 : nil
            var reportedHr: Double? = trueHr
            var accelSd: Double? = s.plant.speed > 0.5 ? 0.35 : 0.01

            if has({ if case .dropout = $0 { return true }; return false }) {
                reportedHr = nil
            }
            if has({ if case .frozenHr = $0 { return true }; return false }) {
                if frozenAt == nil { frozenAt = trueHr }
                reportedHr = frozenAt
            } else {
                frozenAt = nil
            }
            if has({ if case .cadenceLock = $0 { return true }; return false }) {
                // The classic artefact: reported HR equals step rate.
                cadence = 168
                reportedHr = 168
            }
            if has({ if case .notWorn = $0 { return true }; return false }) {
                reportedHr = 95          // plausible-looking, which is exactly the danger
                accelSd = 0.005          // but the arm is not moving
                cadence = nil
            }

            let gpsLost = has { if case .gpsLoss = $0 { return true }; return false }
            let quality: PaceSample.Quality = gpsLost ? .estimated : .good
            let reportedSpeed: Double? = gpsLost ? nil : s.plant.speed
            distance += s.plant.speed

            // --- the gate -----------------------------------------------------------------------
            var status = "dropout"
            if let hr = reportedHr {
                status = gate.update(HrSample(tS: t, hrBpm: hr, cadenceSpm: cadence,
                                              accelSdG: accelSd))
            } else {
                status = gate.tick(t)
            }
            result.hrStatuses.append(status)

            let pain: Int? = faultsNow.compactMap { f -> Int? in
                if case .pain(_, let level) = f { return level }
                return nil
            }.first

            // --- the controller ------------------------------------------------------------------
            // Warm-up ends at five minutes, which is where the plan's warm-ups end.
            if state == .warmup, t >= 300 { state = .steady; controller.setState(.steady) }

            let tick = RunTick(tS: t, hrBpm: gate.usableForControl ? gate.value : nil,
                               hrStatus: status, speedMPerS: reportedSpeed, grade: grade,
                               cadenceSpm: cadence, distanceM: distance,
                               pain0to10: pain, symptom: nil)
            let decision = controller.update(tick)
            result.decisions.append(decision)

            if let cue = decision.cue, let spoken = scheduler.submit([cue], now: t) {
                result.spoken.append((t, spoken))
                let delta = s.response.speedChange(for: spoken,
                                                   requested: decision.speedCorrectionMPerS)
                if delta != 0 { pendingChange = (t + s.response.reactionS, delta) }
            }

            result.ticks.append(ScenarioTick(
                tS: t, hrBpm: reportedHr, speedMPerS: reportedSpeed, cadenceSpm: cadence,
                grade: grade, distanceM: distance, accelSdG: accelSd,
                paceQuality: quality, pain: pain))

            if decision.abort {
                result.aborted = true
                result.abortReason = decision.reason
                break
            }
            t += 1
        }
        result.distanceM = distance
        return result
    }
}
