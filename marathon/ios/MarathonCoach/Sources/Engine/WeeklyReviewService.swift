//
//  WeeklyReviewService.swift
//  Runs the weekly review when a week has actually elapsed, and applies its decision.
//
//  This is the piece that was missing: `WeeklyReview` had the rules and nothing called them. A planner
//  that only advances when the user happens to tap something is not an adaptive plan.
//
//  ## When it runs
//
//  On launch, and only when the ISO week has changed since the last review. Not on a timer, not on a
//  background task: there is nothing time-critical about it, and a review that fires while you are
//  mid-run would be actively unhelpful. The stored `lastReviewedWeek` makes it idempotent, so opening
//  the app five times on a Monday runs it once.
//
//  ## What it decides, and what it refuses to decide
//
//  It decides next week's volume target and whether the phase advances. It does **not** silently apply
//  a phase change: advancing is shown with the gate evidence behind it and requires a tap, because a
//  plan that reorganises itself overnight without saying why is the black-box complaint that makes
//  people distrust these apps. Volume adjustments *are* applied automatically — they are small,
//  reversible, and always downward or capped.
//

import Foundation

@MainActor
public final class WeeklyReviewService {

    public struct Outcome: Identifiable {
        /// Identity is the reviewed week, so presenting the same review twice is a no-op.
        public var id: String { ISO8601DateFormatter().string(from: weekBounds.start) }
        public let decision: ReplanDecision
        public let gates: GateEvaluation
        public let weekBounds: (start: Date, end: Date)
        /// Set when the gates allow a phase change. Deliberately not applied automatically.
        public let phaseAdvanceAvailable: String?
    }

    private let store: Store
    private let plans: PlanStore

    public init(store: Store, plans: PlanStore) {
        self.store = store
        self.plans = plans
    }

    private static let lastReviewKey = "lastReviewedISOWeek"

    /// Current ISO year-week, as a stable comparable string.
    private func isoWeek(_ date: Date = Date()) -> String {
        var cal = Calendar(identifier: .iso8601)
        cal.timeZone = .current
        let c = cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: date)
        return "\(c.yearForWeekOfYear ?? 0)-W\(c.weekOfYear ?? 0)"
    }

    public var isDue: Bool {
        UserDefaults.standard.string(forKey: Self.lastReviewKey) != isoWeek()
    }

    /// Run the review for the week that just ended. Returns nil when not due.
    public func runIfDue(now: Date = Date()) -> Outcome? {
        guard isDue else { return nil }
        let outcome = review(now: now)
        UserDefaults.standard.set(isoWeek(now), forKey: Self.lastReviewKey)
        apply(outcome)
        return outcome
    }

    /// Compute the review without recording it — for a "what would happen" view.
    public func review(now: Date = Date()) -> Outcome {
        var cal = Calendar(identifier: .iso8601)
        cal.timeZone = .current
        // The week that just ended, not the one in progress: reviewing a partial week would read every
        // Monday as a disrupted week and rebuild volume downward every single time.
        let thisWeekStart = cal.dateInterval(of: .weekOfYear, for: now)?.start ?? now
        let lastWeekStart = cal.date(byAdding: .day, value: -7, to: thisWeekStart) ?? now
        let bounds = (start: lastWeekStart, end: thisWeekStart)

        let sessions = store.loadSessions()
        let inWeek = sessions.filter { $0.date >= bounds.start && $0.date < bounds.end }
        let achieved = inWeek.filter(\.completed).reduce(0.0) { $0 + $1.distanceKm }
        let completed = inWeek.filter(\.completed).count

        let state = store.loadPlanState()
        let phaseName = state?.currentPhase ?? plans.plan.phase_order.first ?? "assess"
        let weekInPhase = state?.weekInPhase ?? 1
        let template = plans.week(phase: phaseName, weekInPhase: weekInPhase)
        let planned = template?.sessions.filter {
            $0.type != "rest" && $0.type != "strength" && !$0.optional
        }.count ?? 3

        // Pain over the reviewed week, from the log rather than from memory.
        let maxPain = store.loadPain()
            .filter { $0.day >= bounds.start && $0.day < bounds.end }
            .map(\.level0to10).max() ?? 0

        // Readiness bands for the week, from stored nights.
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        let bands = store.loadNights().compactMap { n -> String? in
            guard let d = fmt.date(from: n.day), d >= bounds.start, d < bounds.end else { return nil }
            // A night with no HRV cannot produce a band; counting it as normal would let a week of
            // missing data read as a green week.
            guard n.hrvMs != nil else { return nil }
            if let sleep = n.totalSleepMin, sleep < 360 { return "suppressed" }
            if n.illness { return "strained" }
            return "normal"
        }

        // Daily load series for the ratio, gap-filled with zeros. Omitting rest days is the most
        // common way to make an EWMA lie.
        let daily = dailyLoadSeries(sessions: sessions, endingBefore: bounds.end, days: 42)
        let ratio = WeeklyReview.acwr(daily)

        let decision = WeeklyReview.replan(
            plannedVolumeKm: template?.volume_target_km,
            achievedVolumeKm: achieved,
            sessionsPlanned: planned,
            sessionsCompleted: completed,
            acwrResult: ratio,
            readinessBands: bands,
            maxPain: maxPain,
            weeksSinceCutback: state?.weeksSinceCutback ?? 0)

        let gates = WeeklyReview.evaluateGates(
            phase: plans.phase(phaseName) ?? PhaseDTO(phase: phaseName, goal: "", min_weeks: 1,
                                                      stall_review_weeks: nil, gates: [], weeks: []),
            weeksInPhase: state?.weeksInPhase ?? weekInPhase,
            evidence: evidence(sessions: sessions, state: state),
            nextPhase: plans.nextPhase(after: phaseName))

        return Outcome(decision: decision, gates: gates, weekBounds: bounds,
                       phaseAdvanceAvailable: gates.canAdvance ? gates.nextPhase : nil)
    }

    /// One entry per calendar day, zero on rest days.
    private func dailyLoadSeries(sessions: [SessionRecord], endingBefore end: Date,
                                 days: Int) -> [Double] {
        let cal = Calendar.current
        var byDay: [Date: Double] = [:]
        for s in sessions where s.completed {
            // Session RPE load survives a dead heart-rate sensor, so it is the fallback when TRIMP was
            // withheld for poor coverage. Using zero there would understate the week and let the ramp
            // add more than it should.
            let load = s.trimp ?? ((s.rpe0to10 ?? 5) * s.durationMin)
            let day = cal.startOfDay(for: s.date)
            byDay[day, default: 0] += load
        }
        var out: [Double] = []
        for offset in stride(from: days, through: 1, by: -1) {
            guard let d = cal.date(byAdding: .day, value: -offset, to: end) else { continue }
            out.append(byDay[cal.startOfDay(for: d)] ?? 0)
        }
        return out
    }

    /// Assemble the gate evidence from stored history. Anything genuinely unknown is left absent rather
    /// than defaulted, because "not measured" and "measured and failed" get different advice.
    private func evidence(sessions: [SessionRecord], state: PlanState?) -> [String: Double?] {
        let done = sessions.filter(\.completed)
        var e: [String: Double?] = [:]

        // Three consecutive weeks at or above a volume floor.
        let history = state?.weeklyKmHistory ?? []
        if history.count >= 3 {
            e["weekly_km_3wk_min"] = history.suffix(3).min()
        }

        e["continuous_run_min"] = done
            .filter { $0.sessionType == "easy" || $0.sessionType == "long" }
            .map(\.durationMin).max()
        e["long_run_km"] = done.filter { $0.sessionType == "long" }.map(\.distanceKm).max()
        e["longest_run_min"] = done.filter { $0.sessionType == "long" }.map(\.durationMin).max()
        e["long_runs_over_26km"] = Double(done.filter {
            $0.sessionType == "long" && $0.distanceKm >= 26 }.count)
        e["mp_long_run_done"] = Double(done.filter { $0.sessionType == "marathon_pace" }.count)

        // Race checkpoints, in ascending order. A trial only counts if it was actually completed.
        func covered(_ km: Double) -> Double {
            done.contains { $0.distanceKm >= km - 0.15 } ? 1 : 0
        }
        e["time_trial_2000m_done"] = done.contains {
            $0.sessionType == "time_trial" && $0.distanceKm >= 1.9 } ? 1 : 0
        e["five_k_completed"] = covered(5)
        e["ten_k_completed"] = covered(10)
        e["half_completed"] = covered(21.0)

        // Pain over the trailing fortnight. Absent history means no pain reported, which for this gate
        // genuinely is the same as zero.
        let fortnightAgo = Calendar.current.date(byAdding: .day, value: -14, to: Date()) ?? Date()
        e["max_pain_2wk"] = Double(store.loadPain()
            .filter { $0.day >= fortnightAgo }.map(\.level0to10).max() ?? 0)

        // Completion rate over four weeks.
        let fourWeeksAgo = Calendar.current.date(byAdding: .day, value: -28, to: Date()) ?? Date()
        let recent = sessions.filter { $0.date >= fourWeeksAgo }
        if !recent.isEmpty {
            e["sessions_completed_pct_4wk"] =
                Double(recent.filter(\.completed).count) / Double(recent.count)
        }

        // Decoupling from the most recent long run that produced a figure.
        e["long_run_decoupling"] = done
            .filter { $0.sessionType == "long" && $0.decoupling != nil }
            .sorted { $0.date > $1.date }.first?.decoupling

        return e
    }

    /// Apply the volume decision. Phase advancement is deliberately NOT applied here.
    private func apply(_ outcome: Outcome) {
        guard var state = store.loadPlanState() else { return }
        state.weekInPhase += 1
        state.weeksInPhase += 1
        state.lastWeekVolumeKm = outcome.decision.nextVolumeKm
        state.weeksSinceCutback = outcome.decision.action == .cutback
            ? 0 : state.weeksSinceCutback + 1
        if let v = outcome.decision.nextVolumeKm {
            state.weeklyKmHistory.append(v)
            // Two years of weekly history is plenty for a 28-day ratio and a bone-load window.
            if state.weeklyKmHistory.count > 104 { state.weeklyKmHistory.removeFirst() }
        }
        try? store.save(planState: state)
    }

    /// Advance the phase, once the athlete has seen the evidence and agreed.
    public func advancePhase(to next: String) {
        guard var state = store.loadPlanState() else { return }
        state.currentPhase = next
        state.weekInPhase = 1
        state.weeksInPhase = 1
        state.weeksSinceCutback = 0
        try? store.save(planState: state)
    }
}
