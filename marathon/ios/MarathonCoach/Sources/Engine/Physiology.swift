//
//  Physiology.swift
//  Swift port of the parts of `marathon_engine/physiology.py` that must run on the phone.
//
//  The Python package remains the source of truth and carries the test suite that pins these
//  numbers to published tables. Anything changed here must be changed there first, and the
//  golden-vector fixtures in `Tests/Fixtures/` exist so the two implementations can be shown to
//  agree rather than assumed to.
//
//  Only the runtime-necessary functions are ported. Plan generation stays in Python and ships as a
//  bundled JSON resource, because it runs once per week rather than once per second and duplicating
//  it would double the surface where the two implementations could drift apart.
//

import Foundation

public enum Physiology {

    // MARK: - Units

    public static func paceToSpeed(secPerKm: Double) -> Double {
        precondition(secPerKm > 0, "pace must be positive")
        return 1000.0 / secPerKm
    }

    public static func speedToPace(mPerS: Double) -> Double {
        precondition(mPerS > 0, "speed must be positive")
        return 1000.0 / mPerS
    }

    /// `m:ss`, the only pace format anyone reads at a glance mid-run.
    public static func formatPace(_ secPerKm: Double, perMile: Bool = false) -> String {
        let s = Int((perMile ? secPerKm * 1.609344 : secPerKm).rounded())
        return String(format: "%d:%02d", s / 60, s % 60)
    }

    // MARK: - Heart rate

    /// Tanaka, Monahan & Seals 2001: `208 − 0.7 × age`. Standard error ≈ 7 bpm, and an individual
    /// can sit 15–20 bpm away, so this is a seed that gets replaced by an observed maximum.
    public static func hrMaxEstimate(age: Double) -> Double { 208.0 - 0.7 * age }

    /// Karvonen: heart rate at a fraction of heart-rate *reserve*.
    ///
    /// Reserve rather than %HRmax because the two diverge badly at the low end, which is exactly
    /// where a beginner spends nearly all of their time.
    public static func hr(atReserveFraction f: Double, hrMax: Double, hrRest: Double) -> Double {
        precondition(hrMax > hrRest, "hrMax must exceed hrRest")
        return hrRest + f * (hrMax - hrRest)
    }

    public static func reserveFraction(atHr hr: Double, hrMax: Double, hrRest: Double) -> Double {
        precondition(hrMax > hrRest, "hrMax must exceed hrRest")
        return (hr - hrRest) / (hrMax - hrRest)
    }

    // MARK: - Grade adjustment

    /// Minetti et al. 2002, energy cost of running at a gradient, J/kg/m.
    ///
    /// `Cr = 155.4i⁵ − 30.4i⁴ − 43.3i³ + 46.3i² + 19.5i + 3.6`
    ///
    /// Validated over −0.45…+0.45 and clamped outside it, because the polynomial misbehaves beyond
    /// its fitted range. The minimum sits at a *downhill* grade near −10%, not at zero.
    public static func minettiCost(grade: Double) -> Double {
        let i = max(-0.45, min(0.45, grade))
        return 155.4 * pow(i, 5) - 30.4 * pow(i, 4) - 43.3 * pow(i, 3)
             + 46.3 * i * i + 19.5 * i + 3.6
    }

    public static func gradeAdjustedPaceFactor(grade: Double) -> Double {
        minettiCost(grade: grade) / minettiCost(grade: 0)
    }

    /// Flat-equivalent pace for a pace actually run on a grade.
    public static func gradeAdjustedPace(_ secPerKm: Double, grade: Double) -> Double {
        secPerKm / gradeAdjustedPaceFactor(grade: grade)
    }

    // MARK: - Within-run analysis

    /// Speed per heartbeat, ×1000 for readability. Only ever compare between similar sessions in
    /// similar conditions — otherwise it measures the weather.
    public static func efficiencyFactor(meanSpeedMPerS: Double, meanHr: Double) -> Double {
        precondition(meanHr > 0)
        return meanSpeedMPerS / meanHr * 1000.0
    }

    /// Aerobic decoupling: `EF_firstHalf / EF_secondHalf − 1`.
    ///
    /// Positive means HR drifted up relative to pace. Friel's rule of thumb is that under 5% means
    /// the effort was genuinely aerobic. Only meaningful over a steady effort of ≳45 min with the
    /// warm-up excluded.
    public static func decoupling(firstHalf: [(speed: Double, hr: Double)],
                                  secondHalf: [(speed: Double, hr: Double)]) -> Double? {
        func ef(_ samples: [(speed: Double, hr: Double)]) -> Double? {
            let good = samples.filter { $0.speed > 0 && $0.hr > 0 }
            guard !good.isEmpty else { return nil }
            let ms = good.map(\.speed).reduce(0, +) / Double(good.count)
            let mh = good.map(\.hr).reduce(0, +) / Double(good.count)
            return efficiencyFactor(meanSpeedMPerS: ms, meanHr: mh)
        }
        guard let a = ef(firstHalf), let b = ef(secondHalf), b > 0 else { return nil }
        return a / b - 1.0
    }

    public static let decouplingOK = 0.05
}

// MARK: - Zones

public struct Zone: Identifiable, Codable, Equatable {
    public let index: Int
    public let name: String
    public let lowBpm: Int
    public let highBpm: Int
    public let purpose: String

    public var id: Int { index }
    public func contains(_ hr: Double) -> Bool {
        hr >= Double(lowBpm) && hr < Double(highBpm)
    }
}

public struct ZoneModel: Codable, Equatable {
    public let hrMax: Double
    public let hrRest: Double
    public let lthr: Double?
    public let zones: [Zone]

    /// Five HR-reserve zones, aligned to the Daniels intensity families rather than to any vendor's
    /// colour bands. A measured `lthr` pins the Z3/Z4 boundary, because a beginner's threshold
    /// routinely sits away from the population guess and threshold work is where that matters most.
    public static func fiveZone(hrMax: Double, hrRest: Double, lthr: Double? = nil) -> ZoneModel {
        let spec: [(String, Double, Double, String)] = [
            ("Z1 Recovery", 0.45, 0.60, "active recovery, pure aerobic base, conversational"),
            ("Z2 Easy", 0.60, 0.73, "the bread and butter: mitochondrial and capillary adaptation"),
            ("Z3 Steady", 0.73, 0.81, "marathon-pace effort; the classic junk-mile trap"),
            ("Z4 Threshold", 0.81, 0.90, "lactate threshold, about a one-hour race effort"),
            ("Z5 VO2max", 0.90, 1.05, "3–5 minute interval intensity, the aerobic ceiling"),
        ]
        var zones = spec.enumerated().map { i, s in
            Zone(index: i + 1, name: s.0,
                 lowBpm: Int(Physiology.hr(atReserveFraction: s.1, hrMax: hrMax, hrRest: hrRest).rounded()),
                 highBpm: Int(Physiology.hr(atReserveFraction: s.2, hrMax: hrMax, hrRest: hrRest).rounded()),
                 purpose: s.3)
        }
        if let lthr, Double(zones[2].lowBpm) < lthr, lthr < Double(zones[3].highBpm) {
            let pinned = Int(lthr.rounded())
            zones[2] = Zone(index: 3, name: zones[2].name, lowBpm: zones[2].lowBpm,
                            highBpm: pinned, purpose: zones[2].purpose)
            zones[3] = Zone(index: 4, name: zones[3].name, lowBpm: pinned,
                            highBpm: zones[3].highBpm, purpose: zones[3].purpose)
        }
        return ZoneModel(hrMax: hrMax, hrRest: hrRest, lthr: lthr, zones: zones)
    }

    /// Which zone an HR falls in, clamped to the first/last zone outside the modelled range so a
    /// heart rate can never fall into no zone at all.
    public func zone(for hr: Double) -> Zone {
        if let z = zones.first(where: { $0.contains(hr) }) { return z }
        return hr < Double(zones[0].lowBpm) ? zones[0] : zones[zones.count - 1]
    }

    public func band(forZoneIndices idx: [Int]) -> (low: Double, high: Double) {
        let selected = zones.filter { idx.contains($0.index) }
        let use = selected.isEmpty ? [zones[1]] : selected
        return (Double(use.map(\.lowBpm).min()!), Double(use.map(\.highBpm).max()!))
    }
}
