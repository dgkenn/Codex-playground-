//
//  StoreTests.swift
//  Persistence and plan-interpretation tests — the parts that can fail silently.
//
//  The emphasis is on the failure paths. A store that loses data on a decode error, or a plan loader
//  that returns nil when a phase runs long, both fail *quietly*: the app keeps working and the user
//  discovers the problem weeks later.
//

import XCTest
@testable import MarathonCoachCore

final class StoreTests: XCTestCase {

    private var tmp: URL!
    private var store: Store!

    override func setUpWithError() throws {
        tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("mc-tests-\(UUID().uuidString)")
        store = try Store(directory: tmp)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: tmp)
    }

    private func profile() -> AthleteProfile {
        AthleteProfile(age: 30, hrRest: 55, hrMax: 187, hrMaxSource: "age_formula",
                       vdot: 22, vdotSource: "ramp", lthr: 142, hrSpeedSlope: 11.5)
    }

    // MARK: Round trips

    func testProfileRoundTrip() throws {
        try store.save(profile: profile())
        let loaded = store.loadProfile()
        XCTAssertEqual(loaded?.hrMax, 187)
        XCTAssertEqual(loaded?.lthr, 142)
        XCTAssertEqual(loaded?.hrSpeedSlope, 11.5)
    }

    func testMissingFileReturnsNilRatherThanThrowing() {
        XCTAssertNil(store.loadProfile())
        XCTAssertEqual(store.loadSessions().count, 0)
    }

    func testSessionsAppend() throws {
        for i in 0..<3 {
            try store.append(session: SessionRecord(
                date: Date().addingTimeInterval(Double(i) * 86400), phase: "base_1",
                weekInPhase: i + 1, plannedTitle: "Easy run", sessionType: "easy",
                completed: true, durationMin: 40, distanceKm: 5))
        }
        XCTAssertEqual(store.loadSessions().count, 3)
    }

    func testNightsUpsertByDayRatherThanDuplicating() throws {
        try store.upsert(nights: [NightRecord(day: "2026-08-01", hrvMs: 60)])
        try store.upsert(nights: [NightRecord(day: "2026-08-01", hrvMs: 72),
                                  NightRecord(day: "2026-08-02", hrvMs: 65)])
        let all = store.loadNights()
        XCTAssertEqual(all.count, 2, "re-fetching a night must update, not duplicate")
        XCTAssertEqual(all.first { $0.day == "2026-08-01" }?.hrvMs, 72)
    }

    func testNightsAreSortedByDay() throws {
        try store.upsert(nights: [NightRecord(day: "2026-08-03"), NightRecord(day: "2026-08-01"),
                                  NightRecord(day: "2026-08-02")])
        XCTAssertEqual(store.loadNights().map(\.day), ["2026-08-01", "2026-08-02", "2026-08-03"])
    }

    func testHrvSourceDefaultsToPolarAndIsPreserved() throws {
        // The tag is a correctness requirement, not metadata: HealthKit SDNN and Polar RMSSD must never
        // land in one baseline, and the only thing preventing that is this field surviving a round trip.
        try store.upsert(nights: [NightRecord(day: "2026-08-01", hrvMs: 60,
                                              hrvSource: "healthkit_sdnn")])
        XCTAssertEqual(store.loadNights().first?.hrvSource, "healthkit_sdnn")
        try store.upsert(nights: [NightRecord(day: "2026-08-02", hrvMs: 60)])
        XCTAssertEqual(store.loadNights().first { $0.day == "2026-08-02" }?.hrvSource,
                       "polar_ppi_rmssd")
    }

    // MARK: The failure path that matters

    func testCorruptFileIsPreservedNotSilentlyDiscarded() throws {
        try store.save(profile: profile())
        // Simulate a truncated write.
        let u = tmp.appendingPathComponent("profile.json")
        try Data("{ \"age\": ".utf8).write(to: u)

        let reopened = try Store(directory: tmp)
        XCTAssertNil(reopened.loadProfile(), "unreadable data must not be returned as if valid")
        XCTAssertFalse(reopened.loadErrors.isEmpty,
                       "a decode failure must be surfaced — starting empty silently is "
                       + "indistinguishable from losing everything")
        let preserved = try FileManager.default.contentsOfDirectory(atPath: tmp.path)
            .filter { $0.contains("corrupt") }
        XCTAssertFalse(preserved.isEmpty, "the original file must be kept for recovery")
    }

    // MARK: Traces

    func testTraceAppendsIncrementally() {
        let id = UUID()
        for t in 0..<5 { store.appendTrace(runID: id, line: ["t_s": t, "hr": 140 + t]) }
        let text = (try? String(contentsOf: store.traceURL(runID: id))) ?? ""
        let lines = text.split(separator: "\n").filter { !$0.isEmpty }
        XCTAssertEqual(lines.count, 5, "each tick must be one line, written as it happens")
    }

    func testTraceSurvivesBeingReopened() {
        // The property that matters: a crash mid-run must leave everything up to that point intact.
        let id = UUID()
        store.appendTrace(runID: id, line: ["t_s": 1])
        let second = try! Store(directory: tmp)
        second.appendTrace(runID: id, line: ["t_s": 2])
        let text = (try? String(contentsOf: store.traceURL(runID: id))) ?? ""
        XCTAssertEqual(text.split(separator: "\n").filter { !$0.isEmpty }.count, 2)
    }

    // MARK: Export

    func testExportIncludesEverythingAndIsValidJson() throws {
        try store.save(profile: profile())
        try store.append(session: SessionRecord(
            date: Date(), phase: "base_1", weekInPhase: 1, plannedTitle: "Long run",
            sessionType: "long", completed: true, durationMin: 90, distanceKm: 12))
        try store.upsert(nights: [NightRecord(day: "2026-08-01", hrvMs: 61)])
        try store.append(pain: PainRecord(day: Date(), site: "left_calf", level0to10: 2,
                                         timing: "after_run", focal: false,
                                         worsensDuringRun: false))
        let data = try store.exportAll()
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertNotNil(obj?["profile"] as? [String: Any])
        XCTAssertEqual((obj?["sessions"] as? [Any])?.count, 1)
        XCTAssertEqual((obj?["nights"] as? [Any])?.count, 1)
        XCTAssertEqual((obj?["pain"] as? [Any])?.count, 1)
    }

    func testExportWithNoDataStillProducesValidJson() throws {
        // An empty export must not throw: encoding an Optional at the top level is exactly the kind of
        // thing that works until the day the profile happens to be nil.
        let data = try store.exportAll()
        XCTAssertNotNil(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    }
}

final class PlanStoreTests: XCTestCase {

    private func loadPlan() throws -> PlanStore {
        // plan.json is a declared test resource, so this should always succeed. Failing loudly is
        // correct: a missing plan resource means the exporter was not run, and every one of these
        // tests would otherwise skip and protect nothing.
        try PlanStore(bundle: .module)
    }

    func testWeekClampsRatherThanReturningNilPastTheTemplates() throws {
        let plans = try loadPlan()
        let phase = plans.plan.phases.first { !$0.weeks.isEmpty }!
        let beyond = plans.week(phase: phase.phase, weekInPhase: phase.weeks.count + 50)
        XCTAssertNotNil(beyond,
                        "a gated plan can sit in a phase past its templates; falling off the end "
                        + "would leave the athlete with no session at all")
        XCTAssertEqual(beyond?.week_in_phase, phase.weeks.last?.week_in_phase)
    }

    func testWeekZeroAndNegativeClampToTheFirstWeek() throws {
        let plans = try loadPlan()
        let phase = plans.plan.phases.first { !$0.weeks.isEmpty }!
        XCTAssertEqual(plans.week(phase: phase.phase, weekInPhase: 0)?.week_in_phase, 1)
        XCTAssertEqual(plans.week(phase: phase.phase, weekInPhase: -3)?.week_in_phase, 1)
    }

    func testIntentMapsSessionTypeToTheRightPace() throws {
        let plans = try loadPlan()
        let paces = ["easy": 450.0, "marathon": 400.0, "threshold": 370.0, "interval": 340.0]
        func intent(_ type: String) -> SessionIntent {
            plans.intent(for: PlannedSessionDTO(
                day_offset: 0, type: type, title: "t", duration_min: 40, distance_km: nil,
                zones: [4], structure: "", intent: "", optional: false, cues: [],
                pace_target: nil, fuelling: nil), paces: paces)
        }
        XCTAssertEqual(intent("threshold").targetPaceSecKm, 370)
        XCTAssertEqual(intent("intervals").targetPaceSecKm, 340)
        XCTAssertEqual(intent("marathon_pace").targetPaceSecKm, 400)
        XCTAssertEqual(intent("easy").targetPaceSecKm, 450)
    }

    func testEasyAndLongIntentsAreCeilingOnly() {
        // Running an easy day too slowly is not worth interrupting someone about.
        XCTAssertTrue(SessionIntent(kind: "easy", targetZones: [1, 2]).ceilingOnly)
        XCTAssertTrue(SessionIntent(kind: "long", targetZones: [1, 2]).ceilingOnly)
        XCTAssertFalse(SessionIntent(kind: "threshold", targetZones: [4]).ceilingOnly)
    }
}
