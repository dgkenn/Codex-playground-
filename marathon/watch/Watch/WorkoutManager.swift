// The run, on the watch: a HealthKit workout session (so the app keeps running with the screen off,
// which the web app on the phone never could), heart rate from the watch, and the run/walk blocks
// from CoachCore called once a second with a tap on the wrist at every change.

import Foundation
import HealthKit
import WatchKit
import CoachCore

/// What the athlete sets before a run. Defaults are the current web-app session (6 x 3 min, 170/133).
struct SessionSettings: Codable, Equatable {
    var ceilingBpm: Double = 170
    var floorBpm: Double = 133
    var runMin: Double = 3
    var walkMin: Double = 2
    var reps: Int = 6

    static let key = "pacecoach.settings.v1"

    static func load() -> SessionSettings {
        guard let data = UserDefaults.standard.data(forKey: key),
              let s = try? JSONDecoder().decode(SessionSettings.self, from: data) else { return SessionSettings() }
        return s
    }

    func save() {
        if let data = try? JSONEncoder().encode(self) { UserDefaults.standard.set(data, forKey: Self.key) }
    }
}

final class WorkoutManager: NSObject, ObservableObject {
    /// The armband-style delay allowance (seconds) the block calls use; the watch's own optical heart
    /// rate lags too. See hr-blocks.js lagS.
    static let sensorDelayS = 10.0

    let store = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?
    private var blocks: HrBlocks?
    private var timer: Timer?
    private var startDate: Date?
    private var lastHrAt: Date?
    private var easedThisBlock = false

    @Published var settings = SessionSettings.load() { didSet { settings.save() } }
    @Published var running = false
    @Published var heartRate: Double?
    @Published var elapsed: Double = 0
    @Published var phase: BlockPhase = .warmup
    @Published var rep = 0
    @Published var phaseElapsed: Double = 0
    @Published var summary: HrBlockSummary?
    @Published var message: String?

    var authorized: Bool {
        store.authorizationStatus(for: HKObjectType.workoutType()) == .sharingAuthorized
    }

    func requestAuthorization() {
        let read: Set<HKObjectType> = [
            HKQuantityType(.heartRate),
            HKQuantityType(.distanceWalkingRunning),
            HKQuantityType(.activeEnergyBurned),
            HKObjectType.workoutType(),
        ]
        store.requestAuthorization(toShare: [HKObjectType.workoutType()], read: read) { _, error in
            if let error {
                DispatchQueue.main.async { self.message = error.localizedDescription }
            }
        }
    }

    func start() {
        let config = HKWorkoutConfiguration()
        config.activityType = .running
        config.locationType = .outdoor
        do {
            let s = try HKWorkoutSession(healthStore: store, configuration: config)
            let b = s.associatedWorkoutBuilder()
            b.dataSource = HKLiveWorkoutDataSource(healthStore: store, workoutConfiguration: config)
            s.delegate = self
            b.delegate = self
            session = s
            builder = b
            let now = Date()
            s.startActivity(with: now)
            b.beginCollection(withStart: now) { _, _ in }
            startDate = now

            var cfg = HrBlockConfig()
            cfg.lagS = Self.sensorDelayS
            let st = settings
            blocks = HrBlocks(ceilingBpm: st.ceilingBpm, floorBpm: st.floorBpm,
                              runBlockS: st.runMin * 60, walkS: st.walkMin * 60, reps: st.reps,
                              runningTargetS: st.runMin * 60 * Double(st.reps), config: cfg)
            summary = nil
            heartRate = nil
            phase = .warmup
            rep = 0
            running = true
            message = nil
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.tick() }
        } catch {
            message = error.localizedDescription
        }
    }

    func end() {
        timer?.invalidate()
        timer = nil
        let now = Date()
        if let blocks, let startDate {
            blocks.finish(t: now.timeIntervalSince(startDate))
            summary = blocks.summary()
        }
        session?.end()
        builder?.endCollection(withEnd: now) { [weak self] _, _ in
            self?.builder?.finishWorkout { _, _ in }
        }
        running = false
        WKInterfaceDevice.current().play(.stop)
    }

    private func tick() {
        guard let startDate, let blocks else { return }
        let t = Date().timeIntervalSince(startDate)
        elapsed = t
        let fresh = lastHrAt.map { Date().timeIntervalSince($0) < 5 } ?? false
        if let tr = blocks.update(t: t, hr: fresh ? heartRate : nil) {
            easedThisBlock = false
            switch tr.phase {
            case .run: WKInterfaceDevice.current().play(.start)
            case .walk: WKInterfaceDevice.current().play(.stop)
            case .cooldown: WKInterfaceDevice.current().play(.success)
            default: break
            }
        }
        // One "ease off" tap a block, as heart rate heads within 5 of the ceiling.
        if blocks.phase == .run, !easedThisBlock, let a = blocks.hrAhead, fresh,
           a >= blocks.ceilingBpm - 5, a < blocks.ceilingBpm {
            easedThisBlock = true
            WKInterfaceDevice.current().play(.directionDown)
        }
        phase = blocks.phase
        rep = blocks.rep
        phaseElapsed = blocks.elapsed(t)
    }
}

extension WorkoutManager: HKWorkoutSessionDelegate {
    func workoutSession(_ workoutSession: HKWorkoutSession, didChangeTo toState: HKWorkoutSessionState,
                        from fromState: HKWorkoutSessionState, date: Date) {}

    func workoutSession(_ workoutSession: HKWorkoutSession, didFailWithError error: Error) {
        DispatchQueue.main.async { self.message = error.localizedDescription }
    }
}

extension WorkoutManager: HKLiveWorkoutBuilderDelegate {
    func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) {}

    func workoutBuilder(_ workoutBuilder: HKLiveWorkoutBuilder, didCollectDataOf collectedTypes: Set<HKSampleType>) {
        let hrType = HKQuantityType(.heartRate)
        guard collectedTypes.contains(hrType),
              let q = workoutBuilder.statistics(for: hrType)?.mostRecentQuantity() else { return }
        let bpm = q.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
        DispatchQueue.main.async {
            self.heartRate = bpm
            self.lastHrAt = Date()
        }
    }
}
