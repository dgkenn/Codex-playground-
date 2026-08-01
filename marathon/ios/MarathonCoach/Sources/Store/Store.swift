//
//  Store.swift
//  Persistence. One JSON file per entity kind, written atomically, no dependencies.
//
//  ## Why not Core Data or SQLite
//
//  Total data volume for a year of this is a few megabytes: one profile, a few hundred sessions, a few
//  hundred nights, a pain log. Core Data buys migrations and relational queries that nothing here
//  needs, at the cost of a model editor, a stack to debug, and a schema to migrate. SQLite would be a
//  reasonable choice; Codable JSON is a *better* one for this specific case because the data is
//  human-readable and trivially portable — which matters when there is one user who owns his own data
//  and may well want to hand a file to something else.
//
//  Per-run sample traces are the exception: those are large and are written as separate
//  newline-delimited JSON files, one per run, so a three-hour trace never has to be loaded to read a
//  summary.
//
//  ## Atomic writes
//
//  Every write goes to a temporary file and is then moved into place. A run crashing or the phone
//  dying mid-write must not leave a truncated JSON file that fails to parse — losing the last session
//  is annoying, losing the whole history is not acceptable. `Data.write(to:options:.atomic)` gives
//  this on Apple platforms.
//
//  ## Schema versioning
//
//  Every file carries a `schemaVersion`. Decode failures are surfaced and the file is preserved under
//  a `.corrupt` suffix rather than being overwritten, because silently starting fresh looks identical
//  to "the app lost all my data" from the outside.
//

import Foundation

// MARK: - Records

public struct AthleteProfile: Codable {
    public var schemaVersion = 1
    public var age: Double
    public var hrRest: Double
    public var hrMax: Double
    public var hrMaxSource: String
    public var vdot: Double
    public var vdotSource: String
    public var lthr: Double?
    /// bpm per km/h, from the ramp fit — the controller's feedforward gain.
    public var hrSpeedSlope: Double
    /// Cumulative unconfirmed HRmax raise, so the guard's total cap can be enforced across sessions.
    public var unconfirmedHrMaxRaise: Double = 0
    public var prescriptionBasis: String = "hr_from_ramp"
    public var cadenceBySpeed: [String: Double] = [:]
    public var calibratedStrideM: Double?
    public var screeningCleared: Bool = false
    public var screeningDate: Date?
    public var updatedAt: Date = Date()
}

public struct SessionRecord: Codable, Identifiable {
    public var schemaVersion = 1
    public var id: UUID = UUID()
    public var date: Date
    public var phase: String
    public var weekInPhase: Int
    public var plannedTitle: String
    public var sessionType: String
    public var completed: Bool
    public var durationMin: Double
    public var distanceKm: Double
    public var meanHr: Double?
    public var peakHr: Double?
    public var meanCadence: Double?
    public var rpe0to10: Double?
    /// Fraction of the run where HR was trustworthy — the honesty field. A session where HR was
    /// frozen for half the time should not contribute a confident TRIMP value.
    public var hrCoverage: Double = 0
    public var frozenFraction: Double = 0
    public var decoupling: Double?
    public var trimp: Double?
    public var readinessBand: String?
    public var adjustments: [String] = []
    public var notes: String = ""
    /// Filename of the sample trace, if one was kept.
    public var traceFile: String?
    /// True when this row came from the replay simulator rather than a run.
    ///
    /// Defaulted so existing stored sessions decode unchanged. Every consumer that computes training
    /// load must filter on this: a synthetic run that reached the load model would inflate chronic
    /// load, and an inflated chronic load makes the ramp governor permit a bigger week than the
    /// athlete has actually earned. That is the failure mode where a testing convenience causes an
    /// injury, so it is filtered at the source — see `Store.realSessions`.
    public var simulated: Bool = false
}

public struct NightRecord: Codable, Identifiable {
    public var schemaVersion = 1
    public var id: String { day }
    /// ISO date of the morning this night belongs to.
    public var day: String
    public var hrvMs: Double?
    public var restingHr: Double?
    public var totalSleepMin: Double?
    public var wakeEvents: Int?
    public var sleepEfficiency: Double?
    public var cleanIntervalCount: Int?
    public var artifactFraction: Double?
    public var sleepDebtMin: Double?
    /// Tagged so baselines never mix sources. HealthKit yields SDNN, which is a different quantity
    /// from RMSSD and cannot be converted to it.
    public var hrvSource: String = "polar_ppi_rmssd"
    public var hrvPosture: String = "sleep"
    public var shiftNight: Bool = false
    public var illness: Bool = false
    public var soreness1to7: Int?
    public var fatigue1to7: Int?
}

public struct PainRecord: Codable, Identifiable {
    public var schemaVersion = 1
    public var id: UUID = UUID()
    public var day: Date
    public var site: String
    public var level0to10: Int
    public var timing: String
    public var focal: Bool
    public var worsensDuringRun: Bool
    public var notes: String = ""
}

public struct PlanState: Codable {
    public var schemaVersion = 1
    public var currentPhase: String
    public var weekInPhase: Int
    public var weeksInPhase: Int
    public var startedAt: Date
    public var lastWeekVolumeKm: Double?
    public var weeksSinceCutback: Int = 0
    /// Weekly km history, oldest first — feeds the bone-load model and the ACWR series.
    public var weeklyKmHistory: [Double] = []
}

// MARK: - Store

public final class Store {

    public enum StoreError: Error, CustomStringConvertible {
        case decodeFailed(file: String, underlying: Error)
        public var description: String {
            switch self {
            case .decodeFailed(let f, let e): return "could not decode \(f): \(e)"
            }
        }
    }

    private let root: URL
    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        e.dateEncodingStrategy = .iso8601
        return e
    }()
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    /// Surfaced to the UI rather than logged and forgotten: a decode failure means data loss, and the
    /// user should know rather than seeing an app that mysteriously starts empty.
    public private(set) var loadErrors: [String] = []

    public init(directory: URL? = nil) throws {
        root = directory ?? FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("MarathonCoach", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: root.appendingPathComponent("traces"),
                                                withIntermediateDirectories: true)
    }

    private func url(_ name: String) -> URL { root.appendingPathComponent(name) }

    // MARK: Generic load/save

    private func load<T: Decodable>(_ type: T.Type, _ name: String) -> T? {
        let u = url(name)
        guard let data = try? Data(contentsOf: u) else { return nil }
        do {
            return try decoder.decode(type, from: data)
        } catch {
            // Preserve the unreadable file instead of overwriting it. Starting fresh silently is
            // indistinguishable from losing everything, and the original may still be recoverable.
            let corrupt = url(name + ".corrupt-\(Int(Date().timeIntervalSince1970))")
            try? FileManager.default.moveItem(at: u, to: corrupt)
            loadErrors.append("\(name) could not be read and was preserved as "
                              + "\(corrupt.lastPathComponent): \(error)")
            return nil
        }
    }

    private func save<T: Encodable>(_ value: T, _ name: String) throws {
        let data = try encoder.encode(value)
        try data.write(to: url(name), options: [.atomic])
    }

    // MARK: Typed accessors

    public func loadProfile() -> AthleteProfile? { load(AthleteProfile.self, "profile.json") }
    public func save(profile: AthleteProfile) throws {
        var p = profile; p.updatedAt = Date()
        try save(p, "profile.json")
    }

    public func loadPlanState() -> PlanState? { load(PlanState.self, "plan_state.json") }
    public func save(planState: PlanState) throws { try save(planState, "plan_state.json") }

    /// Every session ever written, replayed ones included. Use this only for display.
    public func loadSessions() -> [SessionRecord] {
        load([SessionRecord].self, "sessions.json") ?? []
    }

    /// Sessions that actually happened.
    ///
    /// **This is what training load, weekly review and plan progression must read.** A simulated run
    /// carries no physiological cost, so counting one would raise chronic load without raising
    /// fitness, and the ramp governor would then authorise a larger week than the athlete has earned.
    /// The filter lives here rather than at each call site because there is no call site that
    /// legitimately wants synthetic runs in a load calculation, and a default that has to be
    /// remembered is a default that will be forgotten.
    public func realSessions() -> [SessionRecord] {
        loadSessions().filter { !$0.simulated }
    }
    public func append(session: SessionRecord) throws {
        var all = loadSessions()
        all.append(session)
        try save(all, "sessions.json")
    }
    public func replace(sessions: [SessionRecord]) throws { try save(sessions, "sessions.json") }

    public func loadNights() -> [NightRecord] { load([NightRecord].self, "nights.json") ?? [] }
    /// Upsert by day, so re-fetching a night from the SleepController updates rather than duplicates.
    public func upsert(nights incoming: [NightRecord]) throws {
        var byDay = Dictionary(uniqueKeysWithValues: loadNights().map { ($0.day, $0) })
        for n in incoming { byDay[n.day] = n }
        try save(byDay.values.sorted { $0.day < $1.day }, "nights.json")
    }

    public func loadPain() -> [PainRecord] { load([PainRecord].self, "pain.json") ?? [] }
    public func append(pain: PainRecord) throws {
        var all = loadPain(); all.append(pain)
        try save(all, "pain.json")
    }

    // MARK: Run traces

    /// Append one sample line to a run's trace. Newline-delimited JSON so a three-hour trace is
    /// written incrementally and survives a crash mid-run with everything up to that point intact.
    public func appendTrace(runID: UUID, line: [String: Any]) {
        let u = root.appendingPathComponent("traces/\(runID.uuidString).jsonl")
        guard let data = try? JSONSerialization.data(withJSONObject: line),
              var text = String(data: data, encoding: .utf8) else { return }
        text += "\n"
        guard let out = text.data(using: .utf8) else { return }
        if FileManager.default.fileExists(atPath: u.path),
           let handle = try? FileHandle(forWritingTo: u) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: out)
        } else {
            try? out.write(to: u, options: [.atomic])
        }
    }

    public func traceURL(runID: UUID) -> URL {
        root.appendingPathComponent("traces/\(runID.uuidString).jsonl")
    }

    /// Re-encode a Codable value as a plain JSON object for embedding in the export payload.
    ///
    /// Encoding an `Optional` at the top level is not something `JSONEncoder` accepts, so nil is
    /// substituted explicitly rather than being passed through and throwing.
    private func jsonObject<T: Encodable>(_ value: T?) -> Any {
        guard let value, let data = try? encoder.encode(value),
              let obj = try? JSONSerialization.jsonObject(with: data) else { return NSNull() }
        return obj
    }

    /// Bundle everything into a single JSON payload — for the calibration hand-off, and as the
    /// user's escape hatch. One user owning his own data should be able to take it elsewhere.
    public func exportAll() throws -> Data {
        let payload: [String: Any] = [
            "schema_version": 1,
            "exported_at": ISO8601DateFormatter().string(from: Date()),
            "profile": jsonObject(loadProfile()),
            "plan_state": jsonObject(loadPlanState()),
            "sessions": jsonObject(loadSessions()),
            "nights": jsonObject(loadNights()),
            "pain": jsonObject(loadPain()),
        ]
        return try JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted])
    }
}
