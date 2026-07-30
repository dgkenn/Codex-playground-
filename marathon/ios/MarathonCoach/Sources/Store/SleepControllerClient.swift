//
//  SleepControllerClient.swift
//  Reads the nightly HRV/sleep series from the user's own SleepController dashboard.
//
//  ## Why this rather than HealthKit
//
//  The SleepController already computes **RMSSD from Polar RR/PPI intervals** with the same artifact
//  rejection this app uses — the plausibility window and the Malik criterion are literally the same
//  constants, deliberately, so the two systems' HRV figures are directly comparable. HealthKit can
//  only offer SDNN, which is a different quantity and cannot be converted.
//
//  So this is the authoritative source and HealthKit is a fallback that lands in its own series. The
//  practical consequence: the readiness band is calibrated on the metric it was designed for, rather
//  than on whatever the platform happened to expose.
//
//  ## Security posture
//
//  The dashboard is on the local network and authenticates with a bearer token — the same
//  `BCG_INGEST_TOKEN` mechanism the Verity forwarder uses. The token goes in the Keychain, never in
//  `UserDefaults` and never in a plist. HTTP to a `.local` address is allowed via an explicit ATS
//  exception for that host only, not a blanket `NSAllowsArbitraryLoads`, because the latter would
//  disable transport security for every request the app ever makes.
//
//  ## Failure posture
//
//  Every failure is non-fatal and *visible*. If the dashboard is unreachable — which will happen, it
//  is a home server — readiness falls back to whatever nights are already stored, and the UI says the
//  data is stale rather than silently showing yesterday's number as though it were today's. A
//  readiness score computed from a week-old baseline that presents itself as current is worse than no
//  score.
//

import Foundation
// Explicit rather than relying on Foundation to re-export it: the Keychain calls below are in Security,
// and a transitive re-export is not something to depend on.
#if canImport(Security)
import Security
#endif

public final class SleepControllerClient {

    public struct Config: Codable, Equatable {
        /// e.g. `http://sleep.local:8000` or `http://192.168.1.20:8000`
        public var baseURL: URL
        /// Seconds. A home server that is asleep should fail fast, not hang the UI.
        public var timeout: TimeInterval = 6
        public init(baseURL: URL, timeout: TimeInterval = 6) {
            self.baseURL = baseURL; self.timeout = timeout
        }
    }

    public enum ClientError: Error, CustomStringConvertible {
        case notConfigured
        case http(Int)
        case transport(String)
        case decode(String)

        public var description: String {
            switch self {
            case .notConfigured: return "The SleepController address has not been set."
            case .http(let c): return "Dashboard returned HTTP \(c)."
            case .transport(let m): return "Could not reach the dashboard: \(m)"
            case .decode(let m): return "Unexpected response from the dashboard: \(m)"
            }
        }
    }

    /// One night, as the dashboard reports it.
    public struct NightPayload: Decodable {
        public let day: String
        public let avg_hrv: Double?
        public let resting_hr: Double?
        public let total_sleep_min: Double?
        public let wake_events: Int?
        public let sleep_efficiency: Double?
        public let rr_count: Int?
        public let artifact_fraction: Double?
        public let sleep_debt_min: Double?
    }

    private struct NightsResponse: Decodable {
        let nights: [NightPayload]
    }

    private let config: Config?
    private let token: String?
    private let session: URLSession

    public init(config: Config?, token: String?) {
        self.config = config
        self.token = token
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = config?.timeout ?? 6
        c.waitsForConnectivity = false      // fail fast; this is a LAN server, not the internet
        session = URLSession(configuration: c)
    }

    private func request(_ path: String, query: [URLQueryItem] = []) throws -> URLRequest {
        guard let config else { throw ClientError.notConfigured }
        var comps = URLComponents(url: config.baseURL.appendingPathComponent(path),
                                  resolvingAgainstBaseURL: false)
        comps?.queryItems = query.isEmpty ? nil : query
        guard let url = comps?.url else { throw ClientError.notConfigured }
        var r = URLRequest(url: url)
        r.httpMethod = "GET"
        if let token { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        return r
    }

    /// Fetch the nightly series. Returns `NightRecord`s already tagged with the correct HRV source, so
    /// they cannot accidentally be merged into a HealthKit-SDNN series downstream.
    public func fetchNights(days: Int = 60) async throws -> [NightRecord] {
        let req = try request("api/nights", query: [URLQueryItem(name: "days", value: "\(days)")])
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw ClientError.transport(error.localizedDescription)
        }
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw ClientError.http(http.statusCode)
        }
        let decoded: [NightPayload]
        do {
            // Accept either a bare array or an object wrapping one, so a dashboard change in either
            // direction does not break the client.
            if let wrapped = try? JSONDecoder().decode(NightsResponse.self, from: data) {
                decoded = wrapped.nights
            } else {
                decoded = try JSONDecoder().decode([NightPayload].self, from: data)
            }
        } catch {
            throw ClientError.decode("\(error)")
        }
        return decoded.map { p in
            NightRecord(day: p.day, hrvMs: p.avg_hrv, restingHr: p.resting_hr,
                        totalSleepMin: p.total_sleep_min, wakeEvents: p.wake_events,
                        sleepEfficiency: p.sleep_efficiency, cleanIntervalCount: p.rr_count,
                        artifactFraction: p.artifact_fraction, sleepDebtMin: p.sleep_debt_min,
                        hrvSource: "polar_ppi_rmssd", hrvPosture: "sleep")
        }
    }

    /// Fetch the controller's own readiness view, if it exposes one. Used only for display alongside
    /// the running readiness band — the training decision is made locally from the raw nights, because
    /// the SleepController's readiness is tuned for clinical alertness rather than for training load
    /// and the two answer different questions.
    public func fetchClinicalReadiness() async throws -> [String: Any] {
        let req = try request("api/readiness")
        let (data, response) = try await session.data(for: req)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw ClientError.http(http.statusCode)
        }
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw ClientError.decode("not a JSON object")
        }
        return obj
    }

    public var isConfigured: Bool { config != nil }
}

// MARK: - Keychain

/// Minimal Keychain wrapper for the dashboard token.
///
/// `UserDefaults` would be simpler and is the wrong place for a bearer token: it is world-readable
/// within the app container, included in unencrypted backups, and trivially visible to anything with
/// filesystem access to a jailbroken or restored device.
#if canImport(Security)
public enum TokenStore {
    private static let service = "coach.marathon.sleepcontroller"
    private static let account = "ingest-token"

    public static func save(_ token: String) -> Bool {
        let data = Data(token.utf8)
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        query[kSecValueData as String] = data
        // Only readable while the device is unlocked, and never migrated to a new device by backup.
        query[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        return SecItemAdd(query as CFDictionary, nil) == errSecSuccess
    }

    public static func load() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    public static func delete() {
        SecItemDelete([
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ] as CFDictionary)
    }
}
#else
/// Non-Apple builds have no Keychain. The token is simply unavailable rather than being written
/// somewhere insecure as a convenience.
public enum TokenStore {
    public static func save(_ token: String) -> Bool { false }
    public static func load() -> String? { nil }
    public static func delete() {}
}
#endif
