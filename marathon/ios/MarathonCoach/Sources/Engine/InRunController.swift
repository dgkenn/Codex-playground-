//
//  InRunController.swift
//  Swift port of `marathon_engine/realtime.py`. The Python version is the source of truth and
//  carries the test suite; this must stay behaviourally identical to it.
//
//  Read the Python module's docstring for the full reasoning. The short version of why this is not a
//  PID loop on heart rate: HR responds to a change in speed as a first-order system with dead time,
//  time constant ~45 s. So the heart rate you can see belongs to the speed you were running half a
//  minute ago. A controller that reacts to it directly oscillates — slow down, HR keeps rising, slow
//  down again, end up walking, HR falls below target, speed up, repeat.
//
//  Three mechanisms prevent that:
//    1. Control on the PREDICTED STEADY STATE, `HR_ss = HR + τ·dHR/dt`, not on the current reading.
//    2. A feedforward gain taken from the athlete's OWN ramp test (bpm per km/h) rather than a
//       guessed constant — this is the main payoff from having done the ramp test at all.
//    3. A deadband, a confirmation window, and cue rate limiting.
//
//  And two things that make it usable rather than merely correct:
//    • Cardiac drift on a long run is explained ONCE and the band widens, instead of nagging. A
//      runner who is told to slow down every 75 seconds on a hot long run switches the app off.
//    • "Heart rate unavailable" is a first-class state. Dropout and cadence lock-on fall back to
//      pace and feel rather than acting on a number that is probably the step rate.
//

import Foundation

// MARK: - Constants (must match realtime.py)

public enum RT {
    /// First-order time constant of the HR response to a speed change, seconds. Reported values
    /// cluster around 30–45 s in trained subjects and run longer in the untrained; 45 makes the
    /// controller more patient, which is the safe direction for a beginner.
    public static let tauHr: Double = 45
    public static let deadTimeS: Double = 5
    /// How long an error must persist outside the deadband before any cue fires.
    public static let confirmS: Double = 20
    /// Wider than sensor noise and wider than the beat-to-beat variation of a steady effort, so a
    /// runner legitimately sitting near a zone edge is not nagged.
    public static let hrDeadbandBpm: Double = 4
    /// A runner cued more often than this stops listening, which is worse than not cueing.
    public static let paceCueMinGapS: Double = 75

    public static let driftMaxBpmPerMin: Double = 1.5
    public static let stepMinBpmPerMin: Double = 6
    public static let paceSteadyCV: Double = 0.06

    /// Above any zone this plan prescribes, so reaching it means either an unplanned maximal effort
    /// or a problem.
    public static let abortHrFraction: Double = 0.95
    public static let abortHrSustainS: Double = 45
    /// Pain-monitoring model: 0–2 acceptable, 3–5 caps load, above 5 stop.
    public static let painWarn = 3
    public static let painStop = 5

    public static let repFadeAbortPct: Double = 0.08
    public static let recoveryHrFraction: Double = 0.75
    public static let decoupleConvert: Double = 0.10
}

// MARK: - Cues

public enum CueLevel: Int, Comparable {
    case info = 1, pace = 2, session = 3, safety = 4
    public static func < (a: CueLevel, b: CueLevel) -> Bool { a.rawValue < b.rawValue }

    var minGapS: Double {
        switch self {
        case .safety: return 0
        case .session: return 20
        case .pace: return RT.paceCueMinGapS
        case .info: return 120
        }
    }
}

public struct Cue: Equatable {
    public let level: CueLevel
    public let text: String
    /// Dedupe key: the same key will not repeat inside its cooldown.
    public let key: String
    public let cooldownS: Double

    public init(_ level: CueLevel, _ text: String, key: String, cooldownS: Double = 0) {
        self.level = level; self.text = text; self.key = key; self.cooldownS = cooldownS
    }
}

/// Rate-limited priority queue for spoken cues.
public final class CueScheduler {
    private var lastFired: [CueLevel: Double] = [:]
    private var lastKey: [String: Double] = [:]
    private var protectedUntil: Double = -1

    public init() {}

    /// Mark a window in which only safety and session cues may speak — used around interval rep
    /// boundaries, which already carry their own cue.
    public func protect(now: Double, seconds: Double = 8) { protectedUntil = now + seconds }

    public func submit(_ cues: [Cue], now: Double) -> Cue? {
        guard !cues.isEmpty else { return nil }
        for cue in cues.sorted(by: { $0.level > $1.level }) {
            if cue.level == .safety {
                lastFired[.safety] = now; lastKey[cue.key] = now
                return cue
            }
            if now < protectedUntil, cue.level < .session { continue }
            if let t = lastKey[cue.key], now - t < cue.cooldownS { continue }
            if let t = lastFired[cue.level], now - t < cue.level.minGapS { continue }
            // Do not talk under a higher-priority cue that just fired.
            let blocked = [CueLevel.pace, .session, .safety]
                .filter { $0 > cue.level }
                .contains { lvl in (lastFired[lvl]).map { now - $0 < lvl.minGapS } ?? false }
            if blocked { continue }
            lastFired[cue.level] = now; lastKey[cue.key] = now
            return cue
        }
        return nil
    }
}

// MARK: - Session model

public enum ControlMode: String { case hrAndPace, paceOnly, hrOnly, effortOnly }
public enum RunState: String {
    case warmup, steady, rep, recovery, cooldown, walkBreak, paused, aborted, done
}

public struct SessionIntent {
    public let kind: String
    public let targetZones: [Int]
    public let targetPaceSecKm: Double?
    public let paceTolerance: Double
    /// Planned duration in seconds, when the session declares one. Used to split a run into halves for
    /// the decoupling calculation, and to know how far through an effort a heart-rate peak occurred.
    public let plannedDurationS: Double?
    /// Easy and long runs are *ceiling*-controlled: too slow is fine, too fast is not.
    public let ceilingOnly: Bool

    public init(kind: String, targetZones: [Int], targetPaceSecKm: Double? = nil,
                paceTolerance: Double = 0.06, plannedDurationS: Double? = nil) {
        self.kind = kind
        self.targetZones = targetZones
        self.targetPaceSecKm = targetPaceSecKm
        self.paceTolerance = paceTolerance
        self.plannedDurationS = plannedDurationS
        self.ceilingOnly = ["easy", "long", "run_walk", "recovery"].contains(kind)
    }
}

public struct RunTick {
    public let tS: Double
    public let hrBpm: Double?
    public let hrStatus: String
    public let speedMPerS: Double?
    public let grade: Double
    public let cadenceSpm: Double?
    public let distanceM: Double
    public let pain0to10: Int?
    public let symptom: String?

    public init(tS: Double, hrBpm: Double?, hrStatus: String = "ok", speedMPerS: Double? = nil,
                grade: Double = 0, cadenceSpm: Double? = nil, distanceM: Double = 0,
                pain0to10: Int? = nil, symptom: String? = nil) {
        self.tS = tS; self.hrBpm = hrBpm; self.hrStatus = hrStatus; self.speedMPerS = speedMPerS
        self.grade = grade; self.cadenceSpm = cadenceSpm; self.distanceM = distanceM
        self.pain0to10 = pain0to10; self.symptom = symptom
    }
}

public struct ControlDecision {
    public let mode: ControlMode
    public let state: RunState
    public let inTarget: Bool?
    public let hrSteadyState: Double?
    public let targetBand: (low: Double, high: Double)?
    public let speedCorrectionMPerS: Double?
    public let cue: Cue?
    public let abort: Bool
    public let reason: String
}

// MARK: - Estimators

public enum RTMath {
    /// Where HR is heading. For a first-order system `τ·dHR/dt = HR_ss − HR`.
    public static func predictSteadyStateHr(hrNow: Double, slopeBpmPerS: Double,
                                           tau: Double = RT.tauHr) -> Double {
        hrNow + tau * slopeBpmPerS
    }

    /// Speed change (m/s) that should remove an HR error, using the athlete's own ramp slope.
    /// Positive `hrErrorBpm` means HR is too high, so the correction is negative.
    public static func speedCorrection(hrErrorBpm: Double, slopeBpmPerKmh: Double) -> Double {
        let slope = max(3.0, slopeBpmPerKmh)   // below 3 the fit is unusable
        return (-hrErrorBpm / slope) / 3.6
    }

    /// Classify a rising HR. The discriminator is pace: drift is a slow rise at CONSTANT pace.
    /// Getting this wrong toward "effort increase" produces an app that nags on every hot long run.
    public static func classifyHrRise(hrSeries: [(t: Double, v: Double)],
                                      speedSeries: [(t: Double, v: Double)])
        -> (kind: String, slopeBpmPerMin: Double, paceCV: Double) {
        guard hrSeries.count >= 6 else { return ("stable", 0, 0) }
        let ts = hrSeries.map(\.t), vs = hrSeries.map(\.v)
        let spanMin = (ts.last! - ts.first!) / 60
        guard spanMin > 0 else { return ("stable", 0, 0) }
        let mt = ts.reduce(0, +) / Double(ts.count)
        let mv = vs.reduce(0, +) / Double(vs.count)
        let sxx = ts.reduce(0) { $0 + ($1 - mt) * ($1 - mt) }
        let slopePerS = sxx == 0 ? 0 : zip(ts, vs).reduce(0) { $0 + ($1.0 - mt) * ($1.1 - mv) } / sxx
        let slopePerMin = slopePerS * 60

        let speeds = speedSeries.map(\.v).filter { $0 > 0 }
        var cv = 1.0
        if speeds.count > 2 {
            let m = speeds.reduce(0, +) / Double(speeds.count)
            let sd = (speeds.reduce(0) { $0 + ($1 - m) * ($1 - m) } / Double(speeds.count)).squareRoot()
            cv = m > 0 ? sd / m : 1.0
        }
        let paceSteady = cv <= RT.paceSteadyCV

        if slopePerMin < RT.driftMaxBpmPerMin * 0.3 { return ("stable", slopePerMin, cv) }
        if paceSteady && slopePerMin <= RT.driftMaxBpmPerMin { return ("drift", slopePerMin, cv) }
        if slopePerMin >= RT.stepMinBpmPerMin || !paceSteady {
            return ("effort_increase", slopePerMin, cv)
        }
        return ("ambiguous", slopePerMin, cv)
    }

    /// Hard safety criteria, checked before any control logic.
    ///
    /// The symptom list is the part that matters: a heart-rate threshold cannot detect the things
    /// that actually require stopping. Advisory only — this is not a diagnosis, and the app's job is
    /// to stop the run and say so plainly.
    public static func safetyCheck(_ tick: RunTick, hrMax: Double, sustainedHighS: Double) -> Cue? {
        if let s = tick.symptom {
            let messages = [
                "chest_pain": "Stop now. Chest pain or pressure during exercise needs to be assessed today, not after the run. Walk, do not push on, and seek medical attention.",
                "dizzy": "Stop and sit down. Light-headedness or feeling faint during a run means stop and rehydrate; if it does not resolve quickly, get assessed.",
                "focal_bone_pain": "Stop running and walk home. A specific point of bone pain that worsens with each step is how a stress fracture presents. Do not run again until it has been assessed — running through this is how a 6-week problem becomes a 6-month one.",
                "calf_swelling": "Stop. A swollen, painful calf that hurts at rest needs to be ruled out as a clot before you run again. Get it assessed.",
                "confusion": "Stop. Confusion or a headache with nausea late in a long effort can be heat illness or hyponatraemia. Do not drink a large volume of plain water; get help.",
            ]
            return Cue(.safety, messages[s] ?? "Stop the run and get this checked.",
                       key: "symptom_\(s)")
        }
        if let p = tick.pain0to10, p > RT.painStop {
            return Cue(.safety,
                       "Pain \(p) out of 10 — stop running and walk. Above \(RT.painStop)/10 the "
                       + "rule is stop, every time. Nothing in this plan is worth the next three weeks.",
                       key: "pain_stop")
        }
        if let hr = tick.hrBpm, tick.hrStatus == "ok",
           hr >= RT.abortHrFraction * hrMax, sustainedHighS >= RT.abortHrSustainS {
            return Cue(.safety,
                       "Heart rate has been above \(Int(RT.abortHrFraction * 100))% of your maximum "
                       + "for \(Int(sustainedHighS)) seconds. Ease to a walk. No session in this "
                       + "plan requires that.", key: "hr_abort")
        }
        return nil
    }
}

// MARK: - Controller

public final class InRunController {
    private let zones: ZoneModel
    private let intent: SessionIntent
    /// bpm per km/h, from the ramp-test fit. The whole point of the ramp test.
    private let hrSpeedSlope: Double
    public private(set) var state: RunState = .warmup
    public let scheduler = CueScheduler()

    private var hrHist: [(t: Double, v: Double)] = []
    private var spHist: [(t: Double, v: Double)] = []
    private var errorSince: Double?
    private var errorSign = 0
    private var highHrSince: Double?
    private var driftAnnounced = false
    private var bandWidenedBpm: Double = 0
    private var repPaces: [Double] = []
    private var aborted = false
    /// How many times each sensor-degradation cue has actually been spoken this run. Capped at two.
    private var degradedSaid: [String: Int] = [:]

    public init(zones: ZoneModel, intent: SessionIntent, hrSpeedSlope: Double = 12) {
        self.zones = zones; self.intent = intent; self.hrSpeedSlope = hrSpeedSlope
    }

    public func setState(_ s: RunState) { state = s }

    private func targetBand() -> (low: Double, high: Double) {
        let b = zones.band(forZoneIndices: intent.targetZones)
        return (b.low, b.high + bandWidenedBpm)
    }

    private func hrSlope(window: Double = 30) -> Double {
        guard hrHist.count >= 4, let end = hrHist.last?.t else { return 0 }
        let pts = hrHist.filter { $0.t >= end - window }
        guard pts.count >= 4 else { return 0 }
        let mt = pts.map(\.t).reduce(0, +) / Double(pts.count)
        let mv = pts.map(\.v).reduce(0, +) / Double(pts.count)
        let sxx = pts.reduce(0) { $0 + ($1.t - mt) * ($1.t - mt) }
        guard sxx != 0 else { return 0 }
        return pts.reduce(0) { $0 + ($1.t - mt) * ($1.v - mv) } / sxx
    }

    private func mode(_ tick: RunTick) -> ControlMode {
        let hrOK = tick.hrBpm != nil && tick.hrStatus == "ok"
        let paceOK = (tick.speedMPerS ?? 0) > 0.3
        if hrOK && paceOK { return .hrAndPace }
        if paceOK { return .paceOnly }
        if hrOK { return .hrOnly }
        return .effortOnly
    }

    public func update(_ tick: RunTick) -> ControlDecision {
        if aborted {
            return ControlDecision(mode: mode(tick), state: .aborted, inTarget: nil,
                                   hrSteadyState: nil, targetBand: nil,
                                   speedCorrectionMPerS: nil, cue: nil, abort: true,
                                   reason: "already aborted")
        }
        if let hr = tick.hrBpm, tick.hrStatus == "ok" {
            hrHist.append((tick.tS, hr))
            if hrHist.count > 600 { hrHist.removeFirst() }
        }
        if let sp = tick.speedMPerS, sp > 0 {
            spHist.append((tick.tS, sp))
            if spHist.count > 600 { spHist.removeFirst() }
        }

        // 1. Safety always first.
        if let hr = tick.hrBpm, hr >= RT.abortHrFraction * zones.hrMax {
            highHrSince = highHrSince ?? tick.tS
        } else {
            highHrSince = nil
        }
        let sustained = highHrSince.map { tick.tS - $0 } ?? 0
        if let safety = RTMath.safetyCheck(tick, hrMax: zones.hrMax, sustainedHighS: sustained) {
            aborted = true; state = .aborted
            return ControlDecision(mode: mode(tick), state: .aborted, inTarget: false,
                                   hrSteadyState: tick.hrBpm, targetBand: targetBand(),
                                   speedCorrectionMPerS: nil,
                                   cue: scheduler.submit([safety], now: tick.tS),
                                   abort: true, reason: safety.key)
        }

        var cues: [Cue] = []
        let m = mode(tick)

        // 2. Pain in the warning band caps the session without stopping it.
        if let p = tick.pain0to10, p >= RT.painWarn, p <= RT.painStop {
            cues.append(Cue(.session,
                            "Pain \(p) out of 10. Finish this as an easy run — no faster running "
                            + "today, and if it is still there next run we hold volume rather than "
                            + "adding.", key: "pain_warn", cooldownS: 600))
        }

        // 3. Sensor degradation is reported, never acted on.
        // Every non-ok status gets a message. An earlier version reported only `cadence_lock` and
        // `dropout`, which left the two most insidious failures silent: a frozen heart rate and a
        // band that has worked loose both keep *producing numbers*, so the gate would quietly stop
        // trusting them and the athlete would finish the run with no idea the data was junk — and no
        // idea to reseat the strap, which is the one thing that would have fixed it.
        // Capped at two mentions per fault per run. The cooldown alone would repeat a persistent
        // fault every five minutes for the whole run — eight times on a long one. The message is
        // actionable exactly twice: once to tell you, once in case you missed it. After that it is
        // nagging about something you have already decided not to fix, and a coach you mute cannot
        // warn you about the things that matter.
        let degradedKey = ["frozen": "hr_frozen", "not_worn": "hr_not_worn",
                           "cadence_lock": "cadence_lock", "dropout": "hr_dropout"][tick.hrStatus]
        if let k = degradedKey, (degradedSaid[k] ?? 0) >= 2 {
            // Said enough. Silence here is deliberate.
        } else if tick.hrStatus == "frozen" {
            cues.append(Cue(.session,
                            "Heart rate has been stuck on the same value — that usually means the "
                            + "strap has shifted. Guiding by pace until it recovers. Snug the band a "
                            + "little higher on your forearm.",
                            key: "hr_frozen", cooldownS: 300))
        } else if tick.hrStatus == "not_worn" {
            cues.append(Cue(.session,
                            "The armband looks like it is not reading your skin. Check it has not "
                            + "worked loose. Guiding by pace until it is back.",
                            key: "hr_not_worn", cooldownS: 300))
        } else if tick.hrStatus == "cadence_lock" {
            cues.append(Cue(.session,
                            "Heart rate has locked onto your step rate, so I am ignoring it and "
                            + "guiding by pace. Try shifting the strap slightly and snugging it.",
                            key: "cadence_lock", cooldownS: 300))
        } else if tick.hrStatus == "dropout" {
            cues.append(Cue(.session,
                            "Lost the heart-rate signal. Guiding by pace and feel until it returns.",
                            key: "hr_dropout", cooldownS: 300))
        }

        // 4. Drift vs effort.
        let win = 300.0
        let hrWin = hrHist.filter { $0.t >= tick.tS - win }
        let spWin = spHist.filter { $0.t >= tick.tS - win }
        let rise = RTMath.classifyHrRise(hrSeries: hrWin, speedSeries: spWin)
        if rise.kind == "drift", ["long", "easy"].contains(intent.kind),
           !driftAnnounced, tick.tS > 1800 {
            driftAnnounced = true
            // Widen the ceiling rather than repeatedly demanding a slowdown. On a long run this rise
            // is expected, and the correct response is to keep effort rather than chase the number.
            bandWidenedBpm = 5
            cues.append(Cue(.info,
                            "Your heart rate is drifting up at steady pace — that is normal this far "
                            + "into a long run, not a sign you are going too hard. I have widened the "
                            + "target by 5 beats. Keep the effort, let the pace ease if it wants to, "
                            + "and drink.", key: "drift_explained", cooldownS: 3600))
        }

        // 5. Zone adherence on the lead-compensated HR.
        var inTarget: Bool?
        var hrSS: Double?
        var band: (low: Double, high: Double)?
        var correction: Double?

        if m == .hrAndPace || m == .hrOnly, let hr = tick.hrBpm {
            let slope = hrSlope()
            let ss = RTMath.predictSteadyStateHr(hrNow: hr, slopeBpmPerS: slope)
            hrSS = ss
            let b = targetBand(); band = b
            let tooHigh = ss > b.high + RT.hrDeadbandBpm
            let tooLow = (ss < b.low - RT.hrDeadbandBpm) && !intent.ceilingOnly
            inTarget = !(tooHigh || tooLow)

            let sign = tooHigh ? 1 : (tooLow ? -1 : 0)
            if sign == 0 {
                errorSince = nil; errorSign = 0
            } else {
                if errorSign != sign { errorSince = tick.tS; errorSign = sign }
                let held = tick.tS - (errorSince ?? tick.tS)
                if held >= RT.confirmS, state != .rep, state != .warmup {
                    let err = tooHigh ? ss - b.high : ss - b.low
                    correction = RTMath.speedCorrection(hrErrorBpm: err, slopeBpmPerKmh: hrSpeedSlope)
                    if tooHigh {
                        if rise.kind != "drift" {   // drift is handled above, not nagged about
                            var paceTxt = ""
                            if let sp = tick.speedMPerS, let c = correction {
                                let newPace = Physiology.speedToPace(mPerS: max(0.5, sp + c))
                                // Two cases where naming a pace is worse than naming none. On a
                                // climb pace is not the instruction, effort is — the grade-adjusted
                                // arithmetic is correct and still yields things like "16:01 per
                                // kilometre", a walking pace offered as a running target. And any
                                // target slower than 12:00/km is slower than a brisk walk, so the
                                // honest instruction is to walk.
                                if abs(tick.grade) >= 0.03 {
                                    paceTxt = " Do not chase a pace on this climb — back the effort "
                                            + "off and let the pace be whatever it is."
                                } else if newPace > 720 {
                                    paceTxt = " That is walking pace now — drop to a walk until your "
                                            + "heart rate comes back down."
                                } else {
                                    paceTxt = " Try about \(Physiology.formatPace(newPace)) per kilometre."
                                }
                            }
                            cues.append(Cue(.pace,
                                            "Ease off — you are heading for \(Int(ss)) beats and this "
                                            + "should top out around \(Int(b.high)).\(paceTxt)",
                                            key: "slow_down", cooldownS: RT.paceCueMinGapS))
                        }
                    } else {
                        cues.append(Cue(.pace,
                                        "You can pick it up a little — heart rate is settling around "
                                        + "\(Int(ss)) and the target starts at \(Int(b.low)).",
                                        key: "speed_up", cooldownS: RT.paceCueMinGapS))
                    }
                }
            }
        } else if m == .paceOnly, let target0 = intent.targetPaceSecKm, let sp = tick.speedMPerS,
                  state != .rep, state != .warmup {
            // The warm-up guard was missing here while the HR branch above had it, so a session with
            // a pace target opened by telling the athlete their warm-up jog was too slow. A warm-up
            // is supposed to be slower than the target; correcting it is wrong, and it lands in the
            // first ten seconds of the run where it does the most damage to trust in everything said
            // afterwards.
            let target = target0 * Physiology.gradeAdjustedPaceFactor(grade: tick.grade)
            let actual = Physiology.speedToPace(mPerS: sp)
            let tol = intent.paceTolerance
            inTarget = abs(actual - target) <= tol * target
            if actual < target * (1 - tol) {
                cues.append(Cue(.pace,
                                "That is \(Physiology.formatPace(actual)) — quicker than the "
                                + "\(Physiology.formatPace(target)) this session calls for. Ease back.",
                                key: "slow_down", cooldownS: RT.paceCueMinGapS))
            } else if actual > target * (1 + tol), !intent.ceilingOnly {
                cues.append(Cue(.pace,
                                "That is \(Physiology.formatPace(actual)); target is "
                                + "\(Physiology.formatPace(target)).",
                                key: "speed_up", cooldownS: RT.paceCueMinGapS))
            }
        }

        let chosen = scheduler.submit(cues, now: tick.tS)
        if let c = chosen, ["hr_frozen", "hr_not_worn", "cadence_lock", "hr_dropout"].contains(c.key) {
            // Counted on *speaking*, not on generating: a cue the scheduler suppressed was never
            // heard, so it must not consume one of the two mentions.
            degradedSaid[c.key] = (degradedSaid[c.key] ?? 0) + 1
        }
        return ControlDecision(mode: m, state: state, inTarget: inTarget, hrSteadyState: hrSS,
                               targetBand: band, speedCorrectionMPerS: correction,
                               cue: chosen, abort: false, reason: rise.kind)
    }

    /// Log a completed rep and decide whether the set should be cut short.
    ///
    /// The two HR arguments are deliberately separate. `hrAtRepEnd` is high by definition — a VO2max
    /// rep finishes near 90% of reserve, that is what makes it one — so testing *it* against a
    /// recovery threshold would cut almost every interval set ever run. Only `hrAfterRecovery`
    /// carries the "not recovering" signal, and the check is skipped when it is absent.
    public func recordRep(index: Int, repPaceSecKm: Double, hrAtRepEnd: Double, now: Double,
                          hrAfterRecovery: Double? = nil) -> Cue? {
        repPaces.append(repPaceSecKm)
        scheduler.protect(now: now, seconds: 8)
        guard repPaces.count >= 2, let first = repPaces.first else { return nil }
        let fade = (repPaceSecKm - first) / first
        if fade > RT.repFadeAbortPct {
            return Cue(.session,
                       "That rep was \(Int(fade * 100))% slower than your first. The set has done "
                       + "its job — stop here and jog easy for the rest. Grinding out slower reps "
                       + "adds fatigue, not fitness.", key: "set_cut_fade")
        }
        if let rec = hrAfterRecovery {
            let frac = Physiology.reserveFraction(atHr: rec, hrMax: zones.hrMax, hrRest: zones.hrRest)
            if frac > RT.recoveryHrFraction {
                return Cue(.session,
                           "Your heart rate is not coming down between reps. Finish the set here and "
                           + "jog easy — that is the honest read on today.", key: "set_cut_recovery")
            }
        }
        return nil
    }

    /// Mid-run decoupling check for a long run. Above the threshold past halfway, the remainder
    /// converts to easy running with walk breaks.
    public func checkLongRunDecoupling(_ decouple: Double, fractionDone: Double) -> Cue? {
        guard fractionDone >= 0.5, decouple > RT.decoupleConvert else { return nil }
        return Cue(.session,
                   "Heart rate has drifted \(Int(decouple * 100))% relative to pace. Switching the "
                   + "rest of this run to easy with walk breaks every 10 minutes — you will still "
                   + "get the time on feet, without the cost.", key: "long_run_converted")
    }
}
