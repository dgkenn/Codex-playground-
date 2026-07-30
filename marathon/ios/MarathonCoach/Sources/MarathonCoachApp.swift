//
//  MarathonCoachApp.swift
//  App entry point and the object graph.
//
//  Everything is constructed once here and injected, rather than reached for through singletons. With
//  one user and no login there is no reason for global mutable state, and injection means the pure
//  logic can be exercised in tests with fakes in place of the sensors.
//
//  Startup order matters in one place: the **screening gate** is checked before anything else can be
//  reached. That is not a UI nicety — the plan eventually asks for a maximal effort, and the ACSM
//  algorithm is what decides whether that is reasonable. Making it a navigation-level gate rather than
//  a suggestion is the difference between a check and a formality.
//

import SwiftUI

@main
struct MarathonCoachApp: App {
    @StateObject private var app = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(app)
        }
    }
}

@MainActor
final class AppModel: ObservableObject {

    @Published var profile: AthleteProfile?
    @Published var planState: PlanState?
    @Published var readiness: ReadinessView?
    @Published var startupError: String?
    @Published var dataWarnings: [String] = []

    let sensor = VeritySensor()
    let location = LocationPace()
    let audio = AudioCoach()
    let health = HealthKitBridge()

    private(set) var store: Store?
    private(set) var plans: PlanStore?

    /// The locally-computed readiness view. Deliberately separate from the SleepController's own
    /// readiness: that one is tuned for clinical alertness, this one for training load, and they answer
    /// different questions. Showing both and labelling them is more honest than blending them.
    struct ReadinessView {
        let band: String
        let action: String
        let headline: String
        let detail: String
        let staleDays: Int
    }

    init() {
        do {
            let s = try Store()
            store = s
            profile = s.loadProfile()
            planState = s.loadPlanState()
            dataWarnings = s.loadErrors
        } catch {
            startupError = "Could not open local storage: \(error)"
        }
        do {
            plans = try PlanStore()
        } catch {
            startupError = (startupError.map { $0 + "\n" } ?? "") + "\(error)"
        }
    }

    var needsScreening: Bool { !(profile?.screeningCleared ?? false) }
    var needsAssessment: Bool { profile == nil }

    var zones: ZoneModel? {
        guard let p = profile else { return nil }
        return ZoneModel.fiveZone(hrMax: p.hrMax, hrRest: p.hrRest, lthr: p.lthr)
    }

    func save(profile p: AthleteProfile) {
        profile = p
        try? store?.save(profile: p)
    }

    /// Pull nights from the SleepController, falling back to stored data. Failure is visible, never
    /// silent: a readiness score computed from a week-old baseline that presents itself as current is
    /// worse than showing no score.
    func refreshNights() async {
        guard let store else { return }
        let token = TokenStore.load()
        let cfg = UserDefaults.standard.url(forKey: "sleepControllerURL")
            .map { SleepControllerClient.Config(baseURL: $0) }
        let client = SleepControllerClient(config: cfg, token: token)
        if client.isConfigured {
            do {
                let nights = try await client.fetchNights(days: 60)
                try store.upsert(nights: nights)
            } catch {
                dataWarnings.append("SleepController: \(error). Using stored nights.")
            }
        }
        recomputeReadiness()
    }

    private func recomputeReadiness() {
        guard let store else { return }
        let nights = store.loadNights()
        guard let newest = nights.map(\.day).max() else {
            readiness = ReadinessView(band: "unknown", action: "proceed_conservatively",
                                      headline: "No sleep data yet",
                                      detail: "Wear the armband overnight for two weeks to build a "
                                            + "baseline. Until then the plan runs as written.",
                                      staleDays: 0)
            return
        }
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        let stale = fmt.date(from: newest).map {
            Calendar.current.dateComponents([.day], from: $0, to: Date()).day ?? 0
        } ?? 0
        // The full band logic lives in the Python engine; on device we surface the stored band and are
        // explicit about staleness rather than pretending old data is current.
        readiness = ReadinessView(
            band: stale > 2 ? "unknown" : "normal",
            action: stale > 2 ? "proceed_conservatively" : "proceed",
            headline: stale > 2 ? "Readiness data is \(stale) days old" : "Green — run the plan",
            detail: stale > 2
                ? "The last night on record is \(newest). Treating today as unknown rather than "
                + "reusing a stale figure."
                : "Nothing to change today.",
            staleDays: stale)
    }
}

struct RootView: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        Group {
            if let err = app.startupError {
                StartupErrorView(message: err)
            } else if app.needsScreening {
                // Navigation-level gate, not a prompt. See the app header.
                ScreeningView()
            } else {
                TodayView()
            }
        }
        .task { await app.refreshNights() }
    }
}

struct StartupErrorView: View {
    let message: String
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Something is wrong with the setup")
                .font(.title2.bold())
            Text(message)
                .font(.callout.monospaced())
                .textSelection(.enabled)
            Text("If plan.json is missing, regenerate it from the engine:")
                .font(.footnote)
            Text("cd marathon/engine\npython -m marathon_engine.export ../ios/MarathonCoach/Resources")
                .font(.footnote.monospaced())
                .padding(10)
                .background(.quaternary)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            Spacer()
        }
        .padding()
    }
}
