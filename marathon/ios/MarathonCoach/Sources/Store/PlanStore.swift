//
//  PlanStore.swift
//  Loads the bundled plan.json and answers "what am I doing today?"
//
//  Plan *generation* lives in Python and ships as a resource. Plan *interpretation* — which phase am I
//  in, which week, what does today look like after readiness and my rota have had their say — is
//  runtime and lives here.
//
//  The split is deliberate. Generation runs once a week and is a large body of arithmetic with a test
//  suite behind it; reimplementing it in Swift would double the surface where the two could drift for
//  no benefit. Interpretation has to run on device, offline, and instantly.
//

import Foundation

// MARK: - Decoded plan

public struct PlannedSessionDTO: Codable {
    public let day_offset: Int
    public let type: String
    public let title: String
    public let duration_min: Double?
    public let distance_km: Double?
    public let zones: [Int]
    public let structure: String
    public let intent: String
    public let optional: Bool
    public let cues: [String]
    public let pace_target: String?
    public let fuelling: String?
}

public struct PlannedWeekDTO: Codable {
    public let week_index: Int
    public let phase: String
    public let week_in_phase: Int
    public let is_cutback: Bool
    public let volume_target_km: Double?
    public let volume_target_min: Double?
    public let focus: String
    public let notes: [String]
    public let sessions: [PlannedSessionDTO]
}

public struct GateDTO: Codable {
    public let key: String
    public let op: String
    public let label: String
    public let rationale: String
    public let safety: Bool
}

public struct PhaseDTO: Codable {
    public let phase: String
    public let goal: String
    public let min_weeks: Int
    public let stall_review_weeks: Int?
    public let gates: [GateDTO]
    public let weeks: [PlannedWeekDTO]
}

public struct PlanDTO: Codable {
    public let export_version: Int
    public let phase_order: [String]
    public let phases: [PhaseDTO]
    public let vdot_ir_floor: Double
}

// MARK: - Store

public final class PlanStore {

    public enum PlanError: Error, CustomStringConvertible {
        case missingResource
        case decode(String)
        case versionMismatch(Int)
        public var description: String {
            switch self {
            case .missingResource: return "plan.json is not in the app bundle."
            case .decode(let m): return "plan.json could not be read: \(m)"
            case .versionMismatch(let v):
                return "plan.json is export version \(v); this build expects 1. Regenerate it with "
                     + "`python -m marathon_engine.export`."
            }
        }
    }

    public let plan: PlanDTO
    private let byPhase: [String: PhaseDTO]

    public init(bundle: Bundle = .main) throws {
        guard let url = bundle.url(forResource: "plan", withExtension: "json") else {
            throw PlanError.missingResource
        }
        let data = try Data(contentsOf: url)
        do {
            plan = try JSONDecoder().decode(PlanDTO.self, from: data)
        } catch {
            throw PlanError.decode("\(error)")
        }
        guard plan.export_version == 1 else {
            throw PlanError.versionMismatch(plan.export_version)
        }
        byPhase = Dictionary(uniqueKeysWithValues: plan.phases.map { ($0.phase, $0) })
    }

    public func phase(_ name: String) -> PhaseDTO? { byPhase[name] }

    /// The week template for a phase and week number.
    ///
    /// A gated plan can sit in a phase well past its minimum — that is the point of gating — so the
    /// export carries templates beyond the minimum and this **clamps to the last available week**
    /// rather than returning nil. Falling off the end of the templates would leave the athlete with no
    /// session at all, which is a worse failure than repeating the final week's shape.
    public func week(phase name: String, weekInPhase: Int) -> PlannedWeekDTO? {
        guard let p = byPhase[name], !p.weeks.isEmpty else { return nil }
        let idx = min(max(1, weekInPhase), p.weeks.count) - 1
        return p.weeks[idx]
    }

    public func gates(phase name: String) -> [GateDTO] { byPhase[name]?.gates ?? [] }

    public func nextPhase(after name: String) -> String? {
        guard let i = plan.phase_order.firstIndex(of: name), i + 1 < plan.phase_order.count else {
            return nil
        }
        return plan.phase_order[i + 1]
    }

    /// Today's session from a week template, by weekday. Returns nil on a rest day.
    public func session(in week: PlannedWeekDTO, weekday: Int) -> PlannedSessionDTO? {
        week.sessions.first { $0.day_offset == weekday && $0.type != "rest" }
    }

    /// Map a plan session type onto a controller intent.
    ///
    /// The zone list and the ceiling-only behaviour both come from the session's declared type rather
    /// than being inferred at the point of use, so an easy run cannot accidentally be treated as a
    /// session where running too slowly warrants a cue.
    public func intent(for s: PlannedSessionDTO, paces: [String: Double]) -> SessionIntent {
        let target: Double?
        switch s.type {
        case "threshold": target = paces["threshold"]
        case "intervals": target = paces["interval"]
        case "marathon_pace": target = paces["marathon"]
        case "repetition": target = paces["repetition"]
        default: target = paces["easy"]
        }
        return SessionIntent(kind: s.type,
                             targetZones: s.zones.isEmpty ? [1, 2] : s.zones,
                             targetPaceSecKm: target,
                             plannedDurationS: s.duration_min.map { $0 * 60 })
    }
}
