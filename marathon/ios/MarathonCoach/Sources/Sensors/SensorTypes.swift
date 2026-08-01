//
//  SensorTypes.swift
//  The data the sensors produce, separated from the frameworks that produce it.
//
//  These types used to live inside `VeritySensor.swift` and `LocationPace.swift`. That was fine until
//  it wasn't: those files import CoreBluetooth and CoreLocation, which do not exist off-Apple, so
//  every type declared beside them was equally unbuildable — including types that are nothing but
//  numbers and dates.
//
//  Moving them here has one purpose. It lets the simulation harness construct a heart-rate reading or
//  a pace sample without a radio, and lets the whole run be replayed in `swift test` on any machine.
//  A type that describes a measurement should not require the hardware that took it.
//
//  Nothing here imports anything beyond Foundation, and nothing here should ever start to.
//

import Foundation

// MARK: - Heart rate

/// One reading from the armband.
///
/// `intervalsMs` is empty in `.run` mode by design, not by accident: PPI and 1 Hz heart rate are
/// mutually exclusive on this hardware. See `SensorMode`.
public struct VerityReading {
    public let timestamp: Date
    public let hrBpm: Int?
    /// Beat intervals in **milliseconds**, already unit-converted and quality-filtered.
    public let intervalsMs: [Double]
    public let cadenceSpm: Double?
    public let skinContact: Bool?
    public let batteryPercent: Int?
    public let source: Source

    public enum Source: String { case pmdPpi, heartRateService, simulated }

    public init(timestamp: Date, hrBpm: Int?, intervalsMs: [Double] = [], cadenceSpm: Double? = nil,
                skinContact: Bool? = nil, batteryPercent: Int? = nil, source: Source) {
        self.timestamp = timestamp
        self.hrBpm = hrBpm
        self.intervalsMs = intervalsMs
        self.cadenceSpm = cadenceSpm
        self.skinContact = skinContact
        self.batteryPercent = batteryPercent
        self.source = source
    }
}

/// What the sensor is being used for right now.
///
/// This is not a preference. Polar's PPI algorithm runs instead of the 1 Hz heart-rate stream, not
/// alongside it, and in PPI mode heart rate updates only every five seconds with roughly a
/// twenty-five second wait for the first sample. A controller whose heart-rate time constant is
/// forty-five seconds cannot work off a five-second update, so a run must use `.run`.
public enum SensorMode: String, CaseIterable {
    /// Real-time coaching: 1 Hz HR from the standard 0x180D service, plus ACC-derived cadence.
    case run
    /// Overnight and orthostatic HRV: PPI plus ACC. The slow HR update does not matter at rest.
    case rest

    public var usesPpi: Bool { self == .rest }
}

public enum VerityStatus: Equatable {
    case bluetoothOff
    case unauthorized
    case scanning
    case connecting
    case warmingUp(secondsElapsed: Int)
    case streaming
    case stalled(reason: String)
    case sdkModeSuspect(hint: String, remedy: String)
    case disconnected(willRetry: Bool)
    /// The simulator is driving this session. Surfaced rather than hidden, so a replayed run can
    /// never be mistaken on screen for a real one.
    case simulating(scenario: String)

    /// Whether the controller may act on readings from this state.
    public var isUsable: Bool {
        switch self {
        case .streaming, .simulating: return true
        default: return false
        }
    }

    public var userMessage: String {
        switch self {
        case .bluetoothOff: return "Bluetooth is off."
        case .unauthorized: return "This app needs Bluetooth permission to reach the armband."
        case .scanning: return "Looking for your Verity Sense…"
        case .connecting: return "Connecting…"
        case .warmingUp(let s):
            return "Warming up (\(s)s). Polar takes about 25 seconds to send the first beat "
                 + "intervals — this is normal."
        case .streaming: return "Streaming"
        case .stalled(let r): return "Connected but no data: \(r)"
        case .sdkModeSuspect(let hint, let remedy): return "\(hint) \(remedy)"
        case .disconnected(let retry):
            return retry ? "Lost the armband — reconnecting…" : "Disconnected."
        case .simulating(let s): return "SIMULATED RUN — \(s). No sensor is connected."
        }
    }
}

// MARK: - Pace

public struct PaceSample {
    public let timestamp: Date
    /// Filtered speed in m/s. Nil when there is no trustworthy estimate at all.
    public let speedMPerS: Double?
    public let distanceM: Double
    /// Instantaneous grade (rise/run) from altitude change, smoothed. Nil when unavailable.
    public let grade: Double?
    public let quality: Quality

    public enum Quality: String {
        /// GPS fix good, speed accuracy tight.
        case good
        /// Usable but degraded — accuracy loose, or fused with cadence.
        case degraded
        /// No trustworthy GPS. Speed is held/estimated from cadence.
        case estimated
        /// Nothing usable.
        case unavailable
    }

    public init(timestamp: Date, speedMPerS: Double?, distanceM: Double, grade: Double?,
                quality: Quality) {
        self.timestamp = timestamp
        self.speedMPerS = speedMPerS
        self.distanceM = distanceM
        self.grade = grade
        self.quality = quality
    }
}

public enum PaceMode: String { case outdoor, treadmill }

// MARK: - Workout

/// A finished run, in the shape HealthKit wants but without depending on it.
///
/// Named `MarathonWorkoutPayload` rather than `WorkoutPayload` because the unqualified name is
/// generic enough to collide; `HealthKitBridge.WorkoutPayload` is aliased to this, so call sites did
/// not change.
public struct MarathonWorkoutPayload {
    public let start: Date
    public let end: Date
    public let distanceM: Double
    public let activeEnergyKcal: Double?
    /// `(date, bpm)` pairs from the armband.
    public let heartRates: [(Date, Double)]
    public let indoor: Bool

    public init(start: Date, end: Date, distanceM: Double, activeEnergyKcal: Double?,
                heartRates: [(Date, Double)], indoor: Bool) {
        self.start = start; self.end = end; self.distanceM = distanceM
        self.activeEnergyKcal = activeEnergyKcal
        self.heartRates = heartRates; self.indoor = indoor
    }
}
