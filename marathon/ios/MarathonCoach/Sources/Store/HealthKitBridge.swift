//
//  HealthKitBridge.swift
//  Writing workouts to Health, and reading sleep — with one specific trap avoided.
//
//  ## The trap: HealthKit HRV is SDNN, not RMSSD
//
//  HealthKit exposes exactly one HRV type: `heartRateVariabilitySDNN`. There is no RMSSD identifier
//  and no beat-to-beat interval type at all. **SDNN and RMSSD are different quantities and one cannot
//  be converted into the other** — SDNN reflects total variability over the window including slow
//  respiratory and circadian components, RMSSD reflects beat-to-beat parasympathetic activity.
//
//  This matters because the readiness engine's band is calibrated on lnRMSSD, and a difference in
//  metric shifts the value by far more than the band being detected. So anything read from HealthKit
//  is tagged `healthkit_sdnn` and kept in its own series with its own baseline. The authoritative
//  series is the Polar-derived RMSSD from the SleepController. Mixing them would produce a spurious
//  "suppressed" flag on whichever day the source changed, and keep producing it until the window
//  rolled over.
//
//  ## Writing workouts without an Apple Watch
//
//  An iPhone-only app can absolutely record a proper workout: `HKWorkoutBuilder` (iOS 17+:
//  `HKWorkoutSession` is watchOS-only, but the builder is available on iOS) accepts the samples we
//  collect and produces a real `HKWorkout` that appears in Fitness and Activity rings. The samples
//  come from the Verity (heart rate) and CoreLocation (distance), which is a *better* heart-rate
//  source than a wrist watch anyway.
//
//  ## What is deliberately not written
//
//  No HRV is ever written back to HealthKit. Writing a Polar-derived RMSSD into a field labelled SDNN
//  would corrupt the user's own health record with a mislabelled metric, and would poison any other
//  app reading it.
//

import Foundation
#if canImport(HealthKit)
import HealthKit
#endif

public final class HealthKitBridge {

    public enum HKError: Error, CustomStringConvertible {
        case unavailable
        case notAuthorized
        case failed(String)
        public var description: String {
            switch self {
            case .unavailable: return "HealthKit is not available on this device."
            case .notAuthorized: return "HealthKit permission has not been granted."
            case .failed(let m): return "HealthKit error: \(m)"
            }
        }
    }

    /// A nightly summary as read from HealthKit. Note the metric tag: this is SDNN.
    public struct NightFromHealth {
        public let day: Date
        public let sdnnMs: Double?
        public let restingHr: Double?
        public let asleepMin: Double?
        public let awakeningCount: Int?
        /// Always `"healthkit_sdnn"`. Present so callers cannot forget which metric they are holding.
        public let hrvSource = "healthkit_sdnn"
    }

#if canImport(HealthKit)
    private let store = HKHealthStore()

    public init() {}

    public var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    private var readTypes: Set<HKObjectType> {
        var s = Set<HKObjectType>()
        if let t = HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN) { s.insert(t) }
        if let t = HKObjectType.quantityType(forIdentifier: .restingHeartRate) { s.insert(t) }
        if let t = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) { s.insert(t) }
        if let t = HKObjectType.quantityType(forIdentifier: .heartRate) { s.insert(t) }
        return s
    }

    private var writeTypes: Set<HKSampleType> {
        var s = Set<HKSampleType>()
        s.insert(HKObjectType.workoutType())
        // Heart rate and distance are written as part of the workout. HRV is deliberately absent from
        // this set: see the file header.
        if let t = HKObjectType.quantityType(forIdentifier: .heartRate) { s.insert(t) }
        if let t = HKObjectType.quantityType(forIdentifier: .distanceWalkingRunning) { s.insert(t) }
        if let t = HKObjectType.quantityType(forIdentifier: .activeEnergyBurned) { s.insert(t) }
        return s
    }

    public func requestAuthorization() async throws {
        guard isAvailable else { throw HKError.unavailable }
        try await store.requestAuthorization(toShare: writeTypes, read: readTypes)
    }

    // MARK: Reading

    /// Read nightly SDNN, resting HR and sleep duration for the last `days` days.
    ///
    /// Returns SDNN under an unambiguous name. Callers must keep it in a separate series from
    /// Polar-derived RMSSD — see the file header for why that is a correctness requirement rather
    /// than tidiness.
    public func readNights(days: Int = 60) async throws -> [NightFromHealth] {
        guard isAvailable else { throw HKError.unavailable }
        let cal = Calendar.current
        let end = Date()
        guard let start = cal.date(byAdding: .day, value: -days, to: end) else { return [] }

        async let sdnn = dailyAverage(.heartRateVariabilitySDNN,
                                      unit: HKUnit.secondUnit(with: .milli),
                                      from: start, to: end)
        async let rhr = dailyAverage(.restingHeartRate,
                                     unit: HKUnit.count().unitDivided(by: .minute()),
                                     from: start, to: end)
        async let sleep = dailySleep(from: start, to: end)

        let (s, r, sl) = try await (sdnn, rhr, sleep)
        let allDays = Set(s.keys).union(r.keys).union(sl.keys).sorted()
        return allDays.map { day in
            NightFromHealth(day: day, sdnnMs: s[day], restingHr: r[day],
                            asleepMin: sl[day]?.minutes, awakeningCount: sl[day]?.awakenings)
        }
    }

    private func dailyAverage(_ id: HKQuantityTypeIdentifier, unit: HKUnit,
                              from: Date, to: Date) async throws -> [Date: Double] {
        guard let type = HKQuantityType.quantityType(forIdentifier: id) else { return [:] }
        let cal = Calendar.current
        let anchor = cal.startOfDay(for: from)
        return try await withCheckedThrowingContinuation { cont in
            let q = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: HKQuery.predicateForSamples(withStart: from, end: to),
                options: .discreteAverage, anchorDate: anchor,
                intervalComponents: DateComponents(day: 1))
            q.initialResultsHandler = { _, results, error in
                if let error { cont.resume(throwing: HKError.failed("\(error)")); return }
                var out: [Date: Double] = [:]
                results?.enumerateStatistics(from: from, to: to) { stat, _ in
                    if let v = stat.averageQuantity()?.doubleValue(for: unit) {
                        out[cal.startOfDay(for: stat.startDate)] = v
                    }
                }
                cont.resume(returning: out)
            }
            store.execute(q)
        }
    }

    private struct SleepNight { var minutes: Double; var awakenings: Int }

    private func dailySleep(from: Date, to: Date) async throws -> [Date: SleepNight] {
        guard let type = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis) else { return [:] }
        return try await withCheckedThrowingContinuation { cont in
            let q = HKSampleQuery(
                sampleType: type,
                predicate: HKQuery.predicateForSamples(withStart: from, end: to),
                limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error { cont.resume(throwing: HKError.failed("\(error)")); return }
                let cal = Calendar.current
                var out: [Date: SleepNight] = [:]
                for s in (samples as? [HKCategorySample]) ?? [] {
                    // Attribute a night to the morning it ends on, matching how the readiness engine
                    // keys nights. A sample starting at 23:00 belongs to the following day.
                    let day = cal.startOfDay(for: s.endDate)
                    let minutes = s.endDate.timeIntervalSince(s.startDate) / 60
                    let asleep: Bool
                    if #available(iOS 16.0, *) {
                        asleep = [HKCategoryValueSleepAnalysis.asleepCore.rawValue,
                                  HKCategoryValueSleepAnalysis.asleepDeep.rawValue,
                                  HKCategoryValueSleepAnalysis.asleepREM.rawValue,
                                  HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue]
                            .contains(s.value)
                    } else {
                        asleep = s.value == HKCategoryValueSleepAnalysis.asleep.rawValue
                    }
                    var night = out[day] ?? SleepNight(minutes: 0, awakenings: 0)
                    if asleep {
                        night.minutes += minutes
                    } else if #available(iOS 16.0, *),
                              s.value == HKCategoryValueSleepAnalysis.awake.rawValue {
                        night.awakenings += 1
                    }
                    out[day] = night
                }
                cont.resume(returning: out)
            }
            store.execute(q)
        }
    }

    // MARK: Writing a workout

    public struct WorkoutPayload {
        public let start: Date
        public let end: Date
        public let distanceM: Double
        public let activeEnergyKcal: Double?
        /// `(date, bpm)` pairs from the armband.
        public let heartRates: [(Date, Double)]
        public let indoor: Bool

        public init(start: Date, end: Date, distanceM: Double, activeEnergyKcal: Double?,
                    heartRates: [(Date, Double)], indoor: Bool) {
            self.start = start; self.end = end; self.distanceM = distanceM
            self.activeEnergyKcal = activeEnergyKcal
            self.heartRates = heartRates; self.indoor = indoor
        }
    }

    /// Write a completed run as a real `HKWorkout`, from an iPhone, with no watch involved.
    public func save(workout p: WorkoutPayload) async throws {
        guard isAvailable else { throw HKError.unavailable }
        let config = HKWorkoutConfiguration()
        config.activityType = .running
        config.locationType = p.indoor ? .indoor : .outdoor

        let builder = HKWorkoutBuilder(healthStore: store, configuration: config, device: .local())
        try await builder.beginCollection(at: p.start)

        var samples: [HKSample] = []
        if let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate) {
            let unit = HKUnit.count().unitDivided(by: .minute())
            // One sample per reading, each spanning to the next — HealthKit wants intervals, and
            // zero-length samples are silently unhelpful in the Health app's charts.
            for (i, hr) in p.heartRates.enumerated() {
                let next = i + 1 < p.heartRates.count ? p.heartRates[i + 1].0 : p.end
                let end = max(next, hr.0.addingTimeInterval(1))
                samples.append(HKQuantitySample(
                    type: hrType,
                    quantity: HKQuantity(unit: unit, doubleValue: hr.1),
                    start: hr.0, end: end))
            }
        }
        if p.distanceM > 0,
           let dType = HKQuantityType.quantityType(forIdentifier: .distanceWalkingRunning) {
            samples.append(HKQuantitySample(
                type: dType,
                quantity: HKQuantity(unit: .meter(), doubleValue: p.distanceM),
                start: p.start, end: p.end))
        }
        if let kcal = p.activeEnergyKcal, kcal > 0,
           let eType = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) {
            samples.append(HKQuantitySample(
                type: eType,
                quantity: HKQuantity(unit: .kilocalorie(), doubleValue: kcal),
                start: p.start, end: p.end))
        }

        if !samples.isEmpty {
            try await builder.addSamples(samples)
        }
        try await builder.endCollection(at: p.end)
        _ = try await builder.finishWorkout()
    }

#else
    // Non-Apple build (e.g. running the pure-logic tests on Linux). Everything degrades to
    // unavailable rather than failing to compile, so the engine-facing code stays portable.
    public init() {}
    public var isAvailable: Bool { false }
    public func requestAuthorization() async throws { throw HKError.unavailable }
    public func readNights(days: Int = 60) async throws -> [NightFromHealth] { throw HKError.unavailable }
#endif
}
