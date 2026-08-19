//
//  PaceBandMonitor.swift
//  Port of marathon_engine/audio.py. Python is authoritative; see PortParityTests.
//
//  The reasoning lives in the Python module's docstring and is not repeated here. The short version:
//  the spoken channel is tuned to say almost nothing, which is right for speech and useless to a
//  runner who cannot see the screen. This is the second channel — short non-speech tones, silence
//  while you are in band, and a confirming pip when you come back.
//

import Foundation

/// The complete non-speech vocabulary. Five sounds, and that is the ceiling on purpose.
public enum Earcon: String, CaseIterable {
    /// Two descending pips. Running faster than the band.
    case ease
    /// Two ascending pips. Running slower than the band. Never on a ceiling-only session.
    case lift
    /// One mid pip. Back in the band — this is what closes the loop on a correction.
    case inBand = "in_band"
    /// Three quick rising pips, immediately before speech.
    case attend
    /// A soft double-thud. The signal degraded and guidance with it.
    case degraded
}

public struct AudioEvent: Equatable {
    public let earcon: Earcon
    public let tS: Double
    /// Signed fractional pace error. Negative is fast, positive is slow.
    public let error: Double
    public let reason: String
}

public enum AudioTuning {
    /// Anti-nag floor between two *reminder* tones.
    public static let toneMinGapS: Double = 15
    /// Absolute floor between any two tones, so they cannot overlap in the ear. Confirmations and
    /// degradation notices obey only this one — see the Python module for why.
    public static let overlapFloorS: Double = 2
    /// Reminder ladder, keyed by how far outside the band you are as a multiple of the tolerance.
    /// Three tiers rather than two: two was wrong at the edge, reminding someone a fraction of a
    /// percent past a 6% tolerance at the same rate as someone 20% out.
    public static let marginalMultiple: Double = 1.2
    public static let marginalGapS: Double = 60
    public static let mildGapS: Double = 30
    public static let largeGapS: Double = 15
    public static let mildMultiple: Double = 1.5
    public static let returnFraction: Double = 0.6
    /// How long the athlete may be slower than target, having never reached it, before the channel
    /// says so once anyway. Bounds the acquisition rule so silence does not become approval.
    public static let acquireGraceS: Double = 180
    /// How many "not up to pace" nudges before the channel gives up saying it. Same reasoning as the
    /// sensor-fault cap: actionable twice, nagging after that.
    public static let maxUnacquiredNudges = 2
    /// Cap on how far the reminder interval backs off while a correction is ignored.
    ///
    /// Found by simulation: at a fixed 15 s interval, an athlete a third too fast and holding it
    /// earned thirty tones in seven minutes — the same nagging failure the three-tier ladder exists
    /// to prevent, reached from the other direction. The ladder handles how far out you are and had
    /// nothing to say about how long you have been told. Each unheeded reminder now doubles the
    /// wait, to eight times the base; the counter resets on returning to the band.
    public static let reminderBackoffMax = 8
    public static let smoothingS: Double = 20
    public static let minSamples = 8
}

/// Decides, once a second, whether to play a tone.
public final class PaceBandMonitor {

    public enum State: String { case unknown, inBand = "in", fast, slow }

    public private(set) var state: State = .unknown

    private let targetPaceSecKm: Double?
    private let tolerance: Double
    private let ceilingOnly: Bool
    public var enabled: Bool

    private var window: [(t: Double, pace: Double)] = []
    private var lastToneT: Double?
    /// True once the athlete has been inside the band at least once this session. Until then, being
    /// **slow** earns silence — a warm-up is deliberately slower than the target and policing it
    /// produced twenty tones in five minutes. Being **fast** is policed from the first second.
    public private(set) var acquired = false
    /// Gates the confirming pip, so a pip is never heard without a warning it refers to.
    private var pendingAck = false
    /// When the current unbroken slow stretch began, for the acquisition grace.
    private var slowSince: Double?
    /// How many "not up to pace yet" nudges have been played. Capped.
    private var unacquiredNudges = 0
    /// Reminders played during the current unbroken excursion. Drives the backoff.
    private var consecutiveReminders = 0

    public init(targetPaceSecKm: Double?, tolerance: Double = 0.06,
                ceilingOnly: Bool = false, enabled: Bool = true) {
        self.targetPaceSecKm = targetPaceSecKm
        self.tolerance = tolerance
        self.ceilingOnly = ceilingOnly
        self.enabled = enabled
    }

    /// Feed one second, get back a tone to play or nil.
    ///
    /// - Parameter running: false during warm-ups, walk breaks and pauses. A walk break in a
    ///   run-walk session is the prescription, not a pace failure, and beeping at it would teach you
    ///   to ignore the beeps.
    public func update(tS: Double, paceSecKm: Double?, grade: Double = 0,
                       paceTrusted: Bool = true, running: Bool = true) -> AudioEvent? {
        guard enabled, let target = targetPaceSecKm, running else {
            window.removeAll()
            return nil
        }

        guard paceTrusted, let pace = paceSecKm, pace > 0 else {
            window.removeAll()
            if state != .unknown {
                state = .unknown
                return emit(.degraded, tS, 0, "pace untrusted")
            }
            return nil
        }

        window.append((tS, pace))
        window.removeAll { $0.t < tS - AudioTuning.smoothingS }
        guard window.count >= AudioTuning.minSamples else { return nil }

        let mean = window.reduce(0.0) { $0 + $1.pace } / Double(window.count)
        let adjusted = target * Physiology.gradeAdjustedPaceFactor(grade: grade)
        let error = (mean - adjusted) / adjusted
        return decide(tS: tS, error: error)
    }

    private func decide(tS: Double, error: Double) -> AudioEvent? {
        let magnitude = abs(error)
        let threshold = (state == .fast || state == .slow)
            ? tolerance * AudioTuning.returnFraction : tolerance
        let inside = magnitude <= threshold

        // ---- inside the band ----------------------------------------------------------------
        if inside {
            let wasOut = state == .fast || state == .slow
            state = .inBand
            acquired = true
            slowSince = nil
            consecutiveReminders = 0
            if wasOut, pendingAck {
                // Acknowledge only what was actually announced. Reaching target pace for the first
                // time is not "back in the band" — nothing was said, so nothing needs closing, and
                // a pip out of nowhere is a sound with no referent.
                pendingAck = false
                return emit(.inBand, tS, error, "back in the band")
            }
            pendingAck = false
            return nil
        }

        // ---- outside the band ---------------------------------------------------------------
        let side: State = error > 0 ? .slow : .fast

        if side == .slow, ceilingOnly {
            state = .inBand
            slowSince = nil
            return nil
        }

        let changedSide = side != state
        state = side

        if side == .slow {
            if slowSince == nil { slowSince = tS }
            if !acquired {
                if tS - slowSince! < AudioTuning.acquireGraceS { return nil }
                if unacquiredNudges >= AudioTuning.maxUnacquiredNudges { return nil }
            }
        } else {
            slowSince = nil
        }

        if changedSide {
            consecutiveReminders = 0
            return emit(tone(for: side), tS, error, "crossed to the other side")
        }
        guard let last = lastToneT else {
            return emit(tone(for: side), tS, error, "left the band")
        }

        let gap: Double
        if magnitude > tolerance * AudioTuning.mildMultiple {
            gap = AudioTuning.largeGapS
        } else if magnitude > tolerance * AudioTuning.marginalMultiple {
            gap = AudioTuning.mildGapS
        } else {
            gap = AudioTuning.marginalGapS
        }
        // Each unheeded reminder doubles the wait. See reminderBackoffMax.
        let backoff = min(AudioTuning.reminderBackoffMax,
                          1 << max(0, consecutiveReminders - 1))
        if tS - last >= gap * Double(backoff) {
            return emit(tone(for: side), tS, error, "still out of the band")
        }
        return nil
    }

    private func tone(for s: State) -> Earcon { s == .fast ? .ease : .lift }

    private func emit(_ earcon: Earcon, _ tS: Double, _ error: Double,
                      _ reason: String) -> AudioEvent? {
        let floor = (earcon == .inBand || earcon == .degraded)
            ? AudioTuning.overlapFloorS : AudioTuning.toneMinGapS
        if let last = lastToneT, tS - last < floor { return nil }
        lastToneT = tS
        if earcon == .ease || earcon == .lift {
            pendingAck = true
            consecutiveReminders += 1
            if earcon == .lift, !acquired { unacquiredNudges += 1 }
        }
        return AudioEvent(earcon: earcon, tS: tS,
                          error: (error * 10000).rounded() / 10000, reason: reason)
    }

    /// The current band as `(fastEdge, slowEdge)` in seconds per kilometre.
    public func band(grade: Double = 0) -> (fast: Double, slow: Double)? {
        guard let t = targetPaceSecKm else { return nil }
        let adjusted = t * Physiology.gradeAdjustedPaceFactor(grade: grade)
        return (adjusted * (1 - tolerance), adjusted * (1 + tolerance))
    }
}

// MARK: - Periodic spoken status

/// The short spoken line that makes silence unambiguous.
///
/// Two seconds, number first. "Eight forty, on pace" is usable at a breathing rate where a full
/// sentence is not — and worse than unusable, a full sentence teaches you these are not worth
/// listening to.
public final class SplitAnnouncer {

    private let everyM: Double?
    private let everyS: Double?
    private var lastSplitM: Double = 0
    private var lastSplitT: Double = 0
    private var lastSplitAt: Double = 0

    public init(everyM: Double? = 1000, everyS: Double? = nil) {
        self.everyM = everyM
        self.everyS = everyS
    }

    public func update(tS: Double, distanceM: Double, paceSecKm: Double?,
                       state: PaceBandMonitor.State) -> String? {
        var due = false
        // What gets spoken. For a distance split it is that split's own average -- see below.
        var reported = paceSecKm
        if let m = everyM, distanceM - lastSplitM >= m {
            lastSplitM += m
            // A split is how long that kilometre took, not the pace at the instant the odometer
            // turned over. It was the instantaneous value, which is a different quantity wearing
            // the same name: every watch means the average, and the momentary reading is far
            // noisier -- one surge or one bad fix at the wrong second becomes the kilometre you
            // remember running. It is also the only number of the run the athlete hears rather
            // than sees, so it has to mean what it says.
            //
            // Gated on there being a live pace at all: a nil paceSecKm is the caller saying the
            // pace channel is degraded, and a distance accumulated while it was degraded is not a
            // distance worth dividing by. Better to say "no pace signal" and leave the number out.
            let dt = tS - lastSplitAt
            if paceSecKm != nil, dt > 0 { reported = dt / (m / 1000) }
            lastSplitAt = tS
            due = true
        }
        if let s = everyS, tS - lastSplitT >= s { lastSplitT = tS; due = true }
        guard due else { return nil }

        var parts: [String] = []
        if everyM != nil {
            let km = lastSplitM / 1000
            parts.append(km == km.rounded() ? String(format: "%.0fK", km)
                                            : String(format: "%.1fK", km))
        }
        if let p = reported { parts.append(Physiology.formatPace(p)) }
        switch state {
        case .inBand: parts.append("on pace")
        case .fast: parts.append("easing")
        case .slow: parts.append("lift")
        case .unknown: parts.append("no pace signal")
        }
        return parts.joined(separator: ". ") + "."
    }
}
