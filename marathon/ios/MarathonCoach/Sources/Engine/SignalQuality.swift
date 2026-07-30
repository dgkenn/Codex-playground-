//
//  SignalQuality.swift
//  Swift port of `marathon_engine/signal_quality.py`. Verified against the shared golden vectors.
//
//  An arm-worn optical sensor produces four failure modes during running, and each one produces data
//  that looks *fine*:
//
//  1. **Dropout / artifact** — isolated implausible values. Cheap to catch.
//  2. **Cadence lock-on** — the PPG algorithm latches onto step frequency and reports a rock-steady,
//     physiologically plausible "heart rate" that is actually your cadence. It has *lower* variance
//     than real data, so every smoothness heuristic prefers it.
//  3. **Frozen HR** — Polar's own documentation: *"If movement is detected, the heart rate is fixed to
//     the last reliable value."* The device emits a stale but perfectly plausible number rather than
//     admitting it lost the signal. This is the most insidious of the four.
//  4. **Not worn** — and note that Polar documents skin-contact detection on this device as "very
//     unreliable", warning that it "might be possible for the device to output a heart rate that is
//     not 0 even the device is not worn". So the contact bit is never used as a gate; not-worn is
//     inferred from stillness *plus* a frozen value, the only combination that distinguishes it from a
//     person sitting quietly.
//
//  Design stance: **reject, never interpolate silently.** A rejected sample is reported as rejected and
//  the consumer decides. Quietly filling gaps with plausible numbers is how a controller ends up
//  confidently coaching off a number that is not a heart rate.
//

import Foundation

public enum SQ {
    /// 240 bpm … 24 bpm. Same window as the SleepController so HRV figures stay comparable.
    public static let ppiMinMs = 250.0
    public static let ppiMaxMs = 2500.0
    /// Malik / Task Force criterion: an interval >20% different from its predecessor is an artifact.
    public static let malikFraction = 0.20
    /// RMSSD is the most artifact-sensitive time-domain index; accepted practice is <5%.
    public static let maxArtifactFraction = 0.05

    public static let hrMinBpm = 30.0
    public static let hrMaxBpm = 230.0
    /// Real HR kinetics run 1–2 bpm/s; 8 is far above anything physiological while staying below the
    /// instantaneous jumps a dropout produces, so it catches artifacts without clipping a hard start.
    public static let maxHrSlewBpmPerS = 8.0
    public static let dropoutTimeoutS = 5.0

    public static let cadenceLockTolerance = 0.04
    public static let cadenceLockMinSamples = 20
    /// Below this coefficient of variation, cadence is effectively constant and a coincidentally-near
    /// heart rate is statistically indistinguishable from a locked one.
    public static let cadenceLockMinCV = 0.003

    public static let frozenWindowS = 12.0
    public static let frozenMinSamples = 8
    public static let frozenMovementSpm = 100.0
    public static let notWornStillnessG = 0.02

    /// Polar documents ~25 s to the first PPI batch; distrust HR for the first 30 s regardless.
    public static let ppgWarmupS = 30.0
}

public struct HrSample {
    public let tS: Double
    public let hrBpm: Double
    public let cadenceSpm: Double?
    /// SD of accelerometer magnitude over the last second, in g. Only used to infer not-worn.
    public let accelSdG: Double?

    public init(tS: Double, hrBpm: Double, cadenceSpm: Double? = nil, accelSdG: Double? = nil) {
        self.tS = tS; self.hrBpm = hrBpm; self.cadenceSpm = cadenceSpm; self.accelSdG = accelSdG
    }
}

// MARK: - Beat-interval cleaning

public struct IntervalCleanResult {
    public var clean: [Double] = []
    public var total = 0
    public var blocker = 0
    public var error = 0
    public var implausible = 0
    public var malik = 0
    public var kept: Int { clean.count }
    public var artifactFraction: Double { total > 0 ? 1.0 - Double(kept) / Double(total) : 0 }
}

/// Filter a beat-interval series.
///
/// Applied in order: the device's own verdict (blocker bit, reported error), then plausibility, then
/// Malik. The Malik comparison is against the previous **accepted** interval rather than the previous
/// raw one — otherwise a single artifact drags its innocent neighbour out with it.
public func cleanIntervals(_ intervalsMs: [Double], blockers: [Bool]? = nil,
                           errorMs: [Double]? = nil,
                           maxErrorMs: Double = 30) -> IntervalCleanResult {
    var r = IntervalCleanResult()
    r.total = intervalsMs.count
    var prev: Double?
    for (i, v) in intervalsMs.enumerated() {
        if let b = blockers, i < b.count, b[i] { r.blocker += 1; continue }
        if let e = errorMs, i < e.count, e[i] > maxErrorMs { r.error += 1; continue }
        guard v >= SQ.ppiMinMs, v <= SQ.ppiMaxMs else { r.implausible += 1; continue }
        if let p = prev, abs(v - p) > SQ.malikFraction * p { r.malik += 1; continue }
        r.clean.append(v)
        prev = v
    }
    return r
}

public func rmssd(_ intervalsMs: [Double]) -> Double? {
    guard intervalsMs.count >= 2 else { return nil }
    var sum = 0.0
    for i in 0..<(intervalsMs.count - 1) {
        let d = intervalsMs[i + 1] - intervalsMs[i]
        sum += d * d
    }
    return (sum / Double(intervalsMs.count - 1)).squareRoot()
}

public func lnRmssd(_ intervalsMs: [Double]) -> Double? {
    guard let r = rmssd(intervalsMs), r > 0 else { return nil }
    return log(r)
}

// MARK: - Detectors

private func mean(_ xs: [Double]) -> Double {
    xs.isEmpty ? 0 : xs.reduce(0, +) / Double(xs.count)
}

private func pstdev(_ xs: [Double]) -> Double {
    guard xs.count > 1 else { return 0 }
    let m = mean(xs)
    return (xs.reduce(0) { $0 + ($1 - m) * ($1 - m) } / Double(xs.count)).squareRoot()
}

/// Score (0…1) that HR has locked onto cadence.
///
/// The test is a conjunction, because each condition alone has an innocent explanation: HR sitting
/// near cadence *and* the HR-to-cadence ratio being unusually constant. A runner whose true HR happens
/// to equal their cadence — entirely possible around 160 — shows the first and not the second, because
/// their heart rate still wanders independently.
///
/// And when cadence is essentially constant there is no discriminating evidence at all, so the score
/// is capped below the action threshold rather than firing: the evidence for a lock is HR *following*
/// cadence, which requires cadence to lead.
public func cadenceLockSuspicion(_ history: [HrSample]) -> Double {
    let pts = history.compactMap { s -> (Double, Double)? in
        guard let c = s.cadenceSpm, c > 100, s.hrBpm > 0 else { return nil }
        return (s.hrBpm, c)
    }
    guard pts.count >= SQ.cadenceLockMinSamples else { return 0 }

    let cadences = pts.map(\.1)
    let cadMean = mean(cadences)
    let cadCV = cadMean > 0 ? pstdev(cadences) / cadMean : 0
    let cadenceVaries = cadCV >= SQ.cadenceLockMinCV

    var near = 0
    var ratios: [Double] = []
    for (hr, cad) in pts {
        ratios.append(hr / cad)
        for mult in [0.5, 1.0, 2.0] where abs(hr - cad * mult) <= SQ.cadenceLockTolerance * cad * mult {
            near += 1
            break
        }
    }
    let fracNear = Double(near) / Double(pts.count)
    let ratioSD = pstdev(ratios)
    let lockTight = ratioSD < 0.01 ? 1.0 : max(0, 1.0 - (ratioSD - 0.01) / 0.03)
    var score = min(1.0, 0.5 * fracNear + 0.5 * lockTight * fracNear)
    if !cadenceVaries { score = min(score, 0.5) }
    return (score * 1000).rounded() / 1000
}

/// Score (0…1) that the device has frozen HR at its last reliable value.
///
/// The discriminator is **identity**, not low variance: a real heart rate at steady effort still varies
/// by a beat or two second to second, and a run of exactly equal values is a plateau no physiology
/// produces. When cadence shows movement this is unambiguous — that is exactly the condition Polar
/// documents — so it reports full confidence immediately rather than ramping, because ramping would
/// leave the controller acting on stale data for another several seconds.
public func frozenHrSuspicion(_ history: [HrSample]) -> Double {
    guard history.count >= SQ.frozenMinSamples, let last = history.last?.hrBpm else { return 0 }
    var run: [HrSample] = []
    for s in history.reversed() {
        if s.hrBpm != last { break }
        run.append(s)
    }
    guard run.count >= SQ.frozenMinSamples,
          let newest = run.first?.tS, let oldest = run.last?.tS else { return 0 }
    let span = newest - oldest
    guard span >= SQ.frozenWindowS else { return 0 }

    let cadences = run.compactMap(\.cadenceSpm)
    let moving = !cadences.isEmpty && mean(cadences) >= SQ.frozenMovementSpm
    if moving { return 1.0 }
    let depth = min(0.6, span / (SQ.frozenWindowS * 2))
    return (depth * 1000).rounded() / 1000
}

/// Score (0…1) that the armband is not on an arm.
///
/// Exists because the device's own contact bit cannot be used. Requires accelerometer data and returns
/// 0 without it rather than guessing — a false positive here discards a real run.
public func notWornSuspicion(_ history: [HrSample]) -> Double {
    guard history.count >= SQ.frozenMinSamples else { return 0 }
    let sds = history.compactMap(\.accelSdG)
    guard !sds.isEmpty, mean(sds) < SQ.notWornStillnessG else { return 0 }
    let frozen = frozenHrSuspicion(history)
    guard frozen > 0 else { return 0 }
    return (min(1.0, frozen * 1.4) * 1000).rounded() / 1000
}

// MARK: - Live gate

/// Stateful gate for a live HR stream. Feed every sample; read `value` and `status`.
///
/// The controller must treat `dropout`, `cadenceLock`, `frozen` and `notWorn` as "HR is unavailable"
/// and fall back to pace and effort rather than acting on the number.
public final class HrGate {
    public private(set) var value: Double?
    public private(set) var status: String = "dropout"
    private var lastGoodT: Double?
    private var history: [HrSample] = []

    public init() {}

    public var usableForControl: Bool { status == "ok" }

    @discardableResult
    public func update(_ sample: HrSample) -> String {
        history.append(sample)
        if history.count > 240 { history.removeFirst() }

        guard sample.hrBpm >= SQ.hrMinBpm, sample.hrBpm <= SQ.hrMaxBpm else {
            status = "rejected"
            return expire(now: sample.tS)
        }
        if let v = value, let t = lastGoodT {
            let dt = max(0.001, sample.tS - t)
            if abs(sample.hrBpm - v) / dt > SQ.maxHrSlewBpmPerS {
                status = "rejected"
                return expire(now: sample.tS)
            }
        }
        value = sample.hrBpm
        lastGoodT = sample.tS

        // Ordered by severity: a band that is off the arm is a different problem from a stale value,
        // which is a different problem from a locked one.
        if sample.tS < SQ.ppgWarmupS {
            status = "warmup"
        } else if notWornSuspicion(history) >= 0.7 {
            status = "not_worn"
        } else if frozenHrSuspicion(history) >= 0.8 {
            status = "frozen"
        } else if cadenceLockSuspicion(history) >= 0.8 {
            status = "cadence_lock"
        } else {
            status = "ok"
        }
        return status
    }

    /// Call on a timer even when no sample arrived, so dropout is detected promptly.
    @discardableResult
    public func tick(_ now: Double) -> String { expire(now: now) }

    private func expire(now: Double) -> String {
        if lastGoodT == nil || now - (lastGoodT ?? 0) > SQ.dropoutTimeoutS {
            status = "dropout"
            value = nil
        }
        return status
    }
}
