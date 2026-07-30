//
//  WeeklyReview.swift
//  The weekly decision: advance, hold, cut, rebuild, or take a cutback — and whether the phase changes.
//
//  Swift port of `marathon_engine.adapt.replan_week` and `plan.evaluate_gates`. These two have to run
//  on device: they are what the app does every Monday morning, offline, with no server. Plan
//  *generation* stays in Python and ships as a resource, because it runs weekly and is large;
//  plan *decisions* are small rule sets and belong here.
//
//  Both are covered by golden vectors in `PortParityTests`, so the port is checked rather than assumed.
//
//  ## The rule this file exists to enforce
//
//  **Volume is never carried forward.** A missed session is gone. Absorbing a skipped run by adding it
//  to next week converts a rest into a spike, which is precisely what the ramp caps exist to prevent.
//  `carryForward` is a stored constant rather than a computed value so the rule is visible in the type
//  rather than implied by the absence of code.
//

import Foundation

public enum ReviewConstants {
    /// Week-over-week volume growth ceiling. The "10% rule" has never been supported by a trial (Buist
    /// 2008 randomised novices and found no difference), but "no evidence 10% helps" is not "evidence
    /// 40% is safe", and the injury being guarded against is slow to appear and slow to heal.
    public static let maxWeeklyRamp = 0.10
    public static let cutbackFactor = 0.70
    public static let cutbackEvery = 4
    public static let acwrSweetHigh = 1.30
    public static let acwrHardCap = 1.50
    /// Below this completion fraction the week rebuilds from what was achieved instead of advancing.
    public static let disruptedWeekFraction = 0.60
    /// Pain at or above this holds volume, regardless of everything else.
    public static let painHoldsVolume = 3
}

public struct ReplanDecision: Equatable {
    public enum Action: String { case advance, hold, cut, cutback, rebuild }
    public let action: Action
    public let nextVolumeKm: Double?
    public let completedFraction: Double
    public let reasons: [String]
    public let warnings: [String]
    /// Always "none". Kept explicit so the never-carry-forward rule is visible.
    public let carryForward = "none"
}

public struct GateEvaluation {
    public struct Row: Equatable {
        public let key: String
        public let label: String
        public let rationale: String
        public let safety: Bool
        public let observed: Double?
    }
    public let phase: String
    public let met: [Row]
    public let unmet: [Row]
    public let unknown: [Row]
    public let minWeeksSatisfied: Bool
    public let canAdvance: Bool
    public let stalled: Bool
    public let nextPhase: String?
    public let guidance: String
    public let diagnostics: [String]
}

public enum WeeklyReview {

    // MARK: Load ratio

    /// EWMA with `lambda = 2/(n+1)`, over a gap-filled daily series including rest days as zero.
    /// Omitting rest days is the most common way to make this number lie.
    public static func ewma(_ loads: [Double], nDays: Int) -> Double {
        guard nDays > 0, let first = loads.first else { return 0 }
        let lambda = 2.0 / (Double(nDays) + 1.0)
        var e = first
        for x in loads.dropFirst() { e = x * lambda + e * (1 - lambda) }
        return e
    }

    public struct Acwr { public let acute: Double; public let chronic: Double
                         public let ratio: Double; public let band: String }

    /// Acute:chronic ratio, used as a **ramp-rate governor and never as a risk score**. The published
    /// "sweet spot" analyses are affected by mathematical coupling (acute load appears in both
    /// numerator and denominator) and have failed to replicate (Impellizzeri 2020/2021; Wang 2020).
    ///
    /// With fewer than 28 days of history the ratio is reported as insufficient and must gate nothing:
    /// a beginner's chronic load starts at literally zero, so the ratio explodes on the first easy jog.
    public static func acwr(_ dailyLoads: [Double]) -> Acwr {
        let n = dailyLoads.count
        let a = ewma(n >= 7 ? Array(dailyLoads.suffix(7)) : dailyLoads, nDays: 7)
        let c = ewma(dailyLoads, nDays: 28)
        guard n >= 28, c > 0 else {
            return Acwr(acute: a, chronic: c, ratio: c > 0 ? a / c : 0,
                        band: "insufficient_history")
        }
        let r = a / c
        let band: String
        if r < 0.80 { band = "detraining" }
        else if r <= ReviewConstants.acwrSweetHigh { band = "optimal" }
        else if r <= ReviewConstants.acwrHardCap { band = "caution" }
        else { band = "danger" }
        return Acwr(acute: a, chronic: c, ratio: r, band: band)
    }

    // MARK: The weekly decision

    /// Decide next week's volume from what actually happened. Precedence order is deliberate and the
    /// first match wins.
    public static func replan(plannedVolumeKm: Double?, achievedVolumeKm: Double,
                              sessionsPlanned: Int, sessionsCompleted: Int,
                              acwrResult: Acwr? = nil,
                              readinessBands: [String] = [],
                              maxPain: Int = 0,
                              weeksSinceCutback: Int = 0) -> ReplanDecision {
        let frac = sessionsPlanned > 0
            ? Double(sessionsCompleted) / Double(sessionsPlanned) : 0
        let base = achievedVolumeKm > 0 ? achievedVolumeKm : (plannedVolumeKm ?? 0)
        let badDays = readinessBands.filter { $0 == "suppressed" || $0 == "strained" }.count

        // 1. Pain. Never add load onto a niggle.
        if maxPain >= ReviewConstants.painHoldsVolume {
            return ReplanDecision(
                action: .hold, nextVolumeKm: (base * 10).rounded() / 10, completedFraction: frac,
                reasons: ["Pain reached \(maxPain)/10 this week. Volume holds where it is until two "
                          + "consecutive pain-free weeks — this is the cheapest injury prevention "
                          + "available."],
                warnings: [])
        }

        // 2. Load ratio above the hard cap.
        if let r = acwrResult, r.ratio > ReviewConstants.acwrHardCap,
           r.band != "insufficient_history" {
            // Scale by the ratio's overshoot rather than targeting chronic x 1.3. The latter does not
            // actually cut anything, because the spike week is itself inside the chronic EWMA and
            // inflates it — the same mathematical coupling that makes the metric contested.
            let scaled = base * (ReviewConstants.acwrSweetHigh / r.ratio)
            // Floored at 60% of achieved: a 4-week rolling metric should not be able to halve next
            // week on its own, or the plan whiplashes.
            let target = max(base * 0.60, scaled)
            return ReplanDecision(
                action: .cut, nextVolumeKm: (min(base, target) * 10).rounded() / 10,
                completedFraction: frac,
                reasons: [String(format: "Acute:chronic load ratio is %.2f, above the %.2f cap. "
                                 + "Cutting to %.1f to bring the ramp back under control.",
                                 r.ratio, ReviewConstants.acwrHardCap, target)],
                warnings: ["This ratio is a ramp-rate governor, not a risk score. A ratio in range "
                           + "does not mean you are safe, and one out of range does not mean you are "
                           + "injured — it means the plan is changing load faster than it intends to."])
        }

        // 3. Two or more poor readiness days.
        if badDays >= 2 {
            return ReplanDecision(
                action: .hold, nextVolumeKm: (base * 10).rounded() / 10, completedFraction: frac,
                reasons: ["\(badDays) days of suppressed or strained readiness. Holding volume rather "
                          + "than adding — when recovery markers are down, added load does not become "
                          + "fitness."],
                warnings: ["If this repeats, look at sleep first: chronic debt caps adaptation more "
                           + "than any training variable."])
        }

        // 4. A disrupted week rebuilds from what was achieved, not from the plan.
        if frac < ReviewConstants.disruptedWeekFraction {
            var target: Double
            var reason: String
            if achievedVolumeKm <= 0 {
                // Coming back at half the plan, not at 105% of it. Using `base` here would fall back
                // to the planned figure and emit the largest jump the engine can produce, in exactly
                // the situation calling for the smallest.
                target = (plannedVolumeKm ?? 0) * 0.50
                reason = String(format: "Nothing was run this week. Coming back at half the planned "
                                + "volume (%.1f) rather than picking up where the plan left off — a "
                                + "week off costs very little fitness, and resuming at full volume "
                                + "after one is a textbook load spike.", target)
            } else {
                target = achievedVolumeKm * 1.05
                reason = String(format: "Only %d of %d sessions done. Next week rebuilds from what "
                                + "you actually ran (%.1f), not from the plan. Nothing is owed — "
                                + "missed volume is gone, and trying to make it up is how a quiet "
                                + "week becomes an injury.",
                                sessionsCompleted, sessionsPlanned, achievedVolumeKm)
            }
            if let p = plannedVolumeKm { target = min(target, p) }
            return ReplanDecision(action: .rebuild, nextVolumeKm: (target * 10).rounded() / 10,
                                  completedFraction: frac, reasons: [reason], warnings: [])
        }

        // 5. Cutback due.
        if weeksSinceCutback >= ReviewConstants.cutbackEvery - 1 {
            return ReplanDecision(
                action: .cutback,
                nextVolumeKm: (base * ReviewConstants.cutbackFactor * 10).rounded() / 10,
                completedFraction: frac,
                reasons: ["Fourth week — cutback. Volume drops so the slow tissues catch up with the "
                          + "fast ones."],
                warnings: [])
        }

        // 6. Advance, capped off ACHIEVED volume rather than planned.
        let cap = base * (1 + ReviewConstants.maxWeeklyRamp)
        let target = plannedVolumeKm.map { min($0, cap) } ?? cap
        return ReplanDecision(
            action: .advance, nextVolumeKm: (target * 10).rounded() / 10, completedFraction: frac,
            reasons: [String(format: "Good week (%d/%d done). Advancing to %.1f, capped at +%.0f%% "
                             + "off what you actually ran.",
                             sessionsCompleted, sessionsPlanned, target,
                             ReviewConstants.maxWeeklyRamp * 100)],
            warnings: [])
    }

    // MARK: Gates

    /// Evaluate a phase's gates against measured evidence.
    ///
    /// Advancement requires **all** gates met **and** the minimum weeks served. Unknown evidence counts
    /// as not-met for advancement but is reported separately, because "you have not measured this yet"
    /// needs different advice ("go and do the trial") from "you measured it and fell short".
    public static func evaluateGates(phase: PhaseDTO, weeksInPhase: Int,
                                     evidence: [String: Double?],
                                     nextPhase: String?) -> GateEvaluation {
        var met: [GateEvaluation.Row] = []
        var unmet: [GateEvaluation.Row] = []
        var unknown: [GateEvaluation.Row] = []

        for g in phase.gates {
            let row = GateEvaluation.Row(key: g.key, label: g.label, rationale: g.rationale,
                                         safety: g.safety, observed: evidence[g.key] ?? nil)
            guard let observed = evidence[g.key] ?? nil else { unknown.append(row); continue }
            let passed: Bool
            switch g.op {
            case ">=": passed = observed >= gateValue(g)
            case "<=": passed = observed <= gateValue(g)
            case "true": passed = observed != 0
            default: unknown.append(row); continue
            }
            if passed { met.append(row) } else { unmet.append(row) }
        }

        let minOK = weeksInPhase >= phase.min_weeks
        let can = minOK && unmet.isEmpty && unknown.isEmpty
        let stalled = (phase.stall_review_weeks.map { weeksInPhase >= $0 } ?? false)
            && !(unmet.isEmpty && unknown.isEmpty)

        let guidance: String
        if can {
            guidance = "All gates met and \(weeksInPhase) weeks served — advance to "
                     + "\(nextPhase ?? "the end")."
        } else if !minOK {
            let remaining = phase.min_weeks - weeksInPhase
            guidance = "\(remaining) more week(s) in this phase first. Bone and tendon adapt more "
                     + "slowly than heart and lungs; this floor is the whole point of the plan."
        } else if unmet.isEmpty && !unknown.isEmpty {
            guidance = "Nothing has failed — some evidence is simply missing: "
                     + unknown.map(\.label).joined(separator: ", ") + "."
        } else {
            guidance = "Outstanding: " + unmet.map(\.label).joined(separator: ", ") + "."
        }

        let diagnostics = stalled ? [
            "Hold volume where it is rather than adding — a stalled gate plus rising load is how an "
            + "overuse injury gets built.",
            "Check the readiness trend: a chronically suppressed HRV baseline or persistent sleep debt "
            + "will cap adaptation no matter how the sessions are arranged.",
            "Check energy availability. Under-fuelling looks exactly like 'not adapting' and is the "
            + "most common invisible cause, especially on a resident's schedule.",
            "Check whether a low-grade niggle is quietly capping every session.",
            "If the gate is a race checkpoint, the answer may just be that no race has been run — "
            + "schedule it.",
        ] : []

        return GateEvaluation(phase: phase.phase, met: met, unmet: unmet, unknown: unknown,
                              minWeeksSatisfied: minOK, canAdvance: can, stalled: stalled,
                              nextPhase: nextPhase, guidance: guidance, diagnostics: diagnostics)
    }

    /// Gate thresholds arrive from JSON as either a number or a bool. Booleans become 1/0 so one
    /// comparison path handles both.
    private static func gateValue(_ g: GateDTO) -> Double {
        if let d = g.valueNumber { return d }
        return g.valueBool == true ? 1 : 0
    }
}
