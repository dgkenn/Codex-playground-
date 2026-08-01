//
//  LocationPace.swift
//  Pace and distance from CoreLocation, fused with cadence, with the noise actually dealt with.
//
//  ## Why this is not just `location.speed`
//
//  Instantaneous `CLLocation.speed` is noisy at roughly the ±10–15 s/km level under a clear sky, and
//  far worse under trees or between buildings. That is the same order of magnitude as the pace
//  corrections the controller computes, so feeding raw GPS speed into it would produce cues driven by
//  satellite geometry rather than by how hard the runner is working. Three things fix it:
//
//  1. **Gate on the accuracy fields Apple provides and most apps ignore.** `speedAccuracy` is the
//     one that matters — it is the standard deviation of the speed estimate in m/s, and a negative
//     value means the speed is *invalid entirely*. Also gate on `horizontalAccuracy`, and reject
//     stale fixes by timestamp, because CoreLocation will happily hand you a cached fix from before
//     the run started.
//  2. **A one-dimensional Kalman filter on speed**, with the measurement variance taken from
//     `speedAccuracy` per sample rather than assumed constant. That is the whole reason to use a
//     Kalman filter here instead of a moving average: it automatically trusts a clean fix more than a
//     dirty one, whereas a fixed-window average weights a terrible fix exactly as much as a good one.
//  3. **Cadence as a sanity check and a fallback.** If GPS says you have stopped but the accelerometer
//     says you are running at 168 spm, GPS is wrong. Under trees and in tunnels this is common, and
//     the honest response is to hold the last good pace and mark it estimated rather than to report a
//     collapse in pace that did not happen.
//
//  ## Distance
//
//  Distance accumulates from filtered point-to-point displacement, not from integrating filtered
//  speed, and rejects displacements that imply an implausible speed. Integrating speed accumulates
//  filter bias over three hours; summing displacement does not.
//
//  ## Treadmill
//
//  There is no GPS indoors. `.treadmill` mode derives distance from cadence and a calibrated stride
//  length instead, and is explicit that this is only as good as the calibration — which is why the
//  calibration comes from a measured outdoor run rather than a formula.
//

import Foundation
import CoreLocation
import Combine

public final class LocationPace: NSObject, ObservableObject {

    /// `PaceMode` and `PaceSample` live in `SensorTypes.swift` so the simulator can produce pace
    /// without linking CoreLocation. Aliased so `LocationPace.Mode` still reads correctly.
    public typealias Mode = PaceMode

    @Published public private(set) var latest: PaceSample?
    @Published public private(set) var authorizationDenied = false
    @Published public private(set) var mode: Mode = .outdoor
    public let samples = PassthroughSubject<PaceSample, Never>()

    // MARK: Gating thresholds

    /// Reject a fix whose horizontal accuracy is worse than this. 25 m is permissive — the aim is to
    /// drop genuinely broken fixes, not to demand survey quality, because being too strict outdoors
    /// leaves the controller with no pace at all under tree cover.
    private let maxHorizontalAccuracyM: CLLocationAccuracy = 25
    /// `speedAccuracy` above this makes the speed unusable for control. 2 m/s of standard deviation is
    /// about 1:40/km of uncertainty — well past the point where a pace cue would be meaningless.
    private let maxSpeedAccuracyMPerS: CLLocationAccuracy = 2.0
    /// Tight enough to drive the controller without qualification.
    private let goodSpeedAccuracyMPerS: CLLocationAccuracy = 0.7
    /// A fix older than this is stale; CoreLocation will serve cached fixes on start-up.
    private let maxFixAgeS: TimeInterval = 3.0
    /// Physiological ceiling. Anything above this is a GPS jump, not a human.
    private let maxPlausibleSpeedMPerS: Double = 8.0

    // MARK: State

    private let manager = CLLocationManager()
    private var lastLocation: CLLocation?
    private var accumulatedDistanceM: Double = 0
    private var lastCadenceSpm: Double?
    private var lastCadenceAt: Date?
    private var lastGoodSpeed: Double?
    private var lastGoodSpeedAt: Date?
    private var altitudeWindow: [(t: Date, altitude: Double, distance: Double)] = []

    /// Kalman state for speed: estimate and its variance.
    private var kSpeed: Double = 0
    private var kVariance: Double = 4.0
    /// Process noise: how much true speed can change between samples. A runner can change speed by
    /// roughly 0.3 m/s in a second when they mean to, so this is set just above that — high enough to
    /// track a deliberate surge, low enough to smooth satellite noise.
    private let processVariance: Double = 0.09

    /// Metres per step, for treadmill mode. Calibrated from a measured outdoor run rather than a
    /// height formula, because stride length varies more between people than any formula captures.
    public var calibratedStrideM: Double?

    public override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation
        manager.activityType = .fitness
        // Do NOT set a distanceFilter: we want every fix, because the filter needs the sample rate.
        manager.distanceFilter = kCLDistanceFilterNone
        manager.pausesLocationUpdatesAutomatically = false   // a long slow run must not be "paused"
    }

    public func requestAuthorization() {
        manager.requestWhenInUseAuthorization()
    }

    public func start(mode: Mode = .outdoor) {
        self.mode = mode
        reset()
        guard mode == .outdoor else { return }
        manager.allowsBackgroundLocationUpdates = true
        manager.startUpdatingLocation()
    }

    public func stop() {
        manager.stopUpdatingLocation()
        manager.allowsBackgroundLocationUpdates = false
    }

    public func reset() {
        lastLocation = nil
        accumulatedDistanceM = 0
        lastGoodSpeed = nil
        lastGoodSpeedAt = nil
        altitudeWindow.removeAll()
        kSpeed = 0
        kVariance = 4.0
    }

    /// Feed cadence in from the armband. Used for the GPS sanity check and treadmill distance.
    public func updateCadence(_ spm: Double?, at time: Date = Date()) {
        lastCadenceSpm = spm
        lastCadenceAt = time
        guard mode == .treadmill, let spm, let stride = calibratedStrideM else { return }
        // Treadmill: distance from cadence x stride. Only as good as the calibration, which is why
        // the calibration is measured rather than estimated.
        let dt = 1.0
        let metres = spm / 60.0 * stride * dt
        accumulatedDistanceM += metres
        let speed = metres / dt
        emit(speed: speed, quality: .estimated, grade: 0, at: time)
    }

    private var cadenceSuggestsRunning: Bool {
        guard let spm = lastCadenceSpm, let at = lastCadenceAt else { return false }
        return spm > 120 && Date().timeIntervalSince(at) < 5
    }

    // MARK: Kalman

    /// One-dimensional Kalman update. The measurement variance comes from `speedAccuracy` per sample,
    /// which is the entire reason to use a filter here rather than a moving average: a clean fix moves
    /// the estimate a lot and a dirty one barely moves it, automatically.
    private func kalmanUpdate(measurement: Double, measurementSD: Double) -> Double {
        kVariance += processVariance
        let measurementVariance = max(0.01, measurementSD * measurementSD)
        let gain = kVariance / (kVariance + measurementVariance)
        kSpeed += gain * (measurement - kSpeed)
        kVariance *= (1 - gain)
        return kSpeed
    }

    private func smoothedGrade() -> Double? {
        // Need a reasonable baseline of horizontal travel or the grade is dominated by altitude noise:
        // GPS vertical error is typically 1.5–3x the horizontal error, so over a short distance the
        // computed grade is essentially random.
        guard let first = altitudeWindow.first, let last = altitudeWindow.last else { return nil }
        let run = last.distance - first.distance
        guard run >= 30 else { return nil }
        let rise = last.altitude - first.altitude
        let grade = rise / run
        // Clamp to the range Minetti validated; beyond it the polynomial is extrapolating anyway.
        return max(-0.45, min(0.45, grade))
    }

    private func emit(speed: Double?, quality: PaceSample.Quality, grade: Double?, at time: Date) {
        let s = PaceSample(timestamp: time, speedMPerS: speed, distanceM: accumulatedDistanceM,
                           grade: grade, quality: quality)
        latest = s
        samples.send(s)
    }
}

// MARK: - CLLocationManagerDelegate

extension LocationPace: CLLocationManagerDelegate {

    public func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        switch m.authorizationStatus {
        case .denied, .restricted: authorizationDenied = true
        default: authorizationDenied = false
        }
    }

    public func locationManager(_ m: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard mode == .outdoor else { return }
        for loc in locations { ingest(loc) }
    }

    public func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {
        // A transient failure is not a reason to zero the pace. Hold, and let the age check downgrade
        // the quality if it persists.
        holdOrDrop(at: Date())
    }

    private func ingest(_ loc: CLLocation) {
        let now = loc.timestamp

        // 1. Stale fix. CoreLocation serves cached fixes on start-up, and one of those at the
        //    beginning of a run produces a phantom sprint from wherever you last used the phone.
        if abs(Date().timeIntervalSince(now)) > maxFixAgeS {
            return
        }
        // 2. Invalid accuracy.
        if loc.horizontalAccuracy < 0 || loc.horizontalAccuracy > maxHorizontalAccuracyM {
            holdOrDrop(at: now)
            return
        }

        // 3. Distance from displacement, with an implausible-jump reject.
        if let prev = lastLocation {
            let dt = now.timeIntervalSince(prev.timestamp)
            let d = loc.distance(from: prev)
            if dt > 0 {
                let impliedSpeed = d / dt
                // A jump implying a speed no human reaches is a GPS relocation, not movement. Skipping
                // it costs a metre of distance; accepting it adds a phantom 50 m.
                if impliedSpeed <= maxPlausibleSpeedMPerS {
                    accumulatedDistanceM += d
                }
            }
        }
        lastLocation = loc

        altitudeWindow.append((t: now, altitude: loc.altitude, distance: accumulatedDistanceM))
        altitudeWindow.removeAll { now.timeIntervalSince($0.t) > 60 }

        // 4. Speed. A NEGATIVE speedAccuracy means the speed is invalid — not merely imprecise. This
        //    is the field most commonly ignored, and ignoring it means feeding garbage to the
        //    controller with full confidence.
        let sa = loc.speedAccuracy
        let rawSpeed = loc.speed
        guard sa >= 0, rawSpeed >= 0, sa <= maxSpeedAccuracyMPerS else {
            holdOrDrop(at: now)
            return
        }

        let filtered = kalmanUpdate(measurement: min(rawSpeed, maxPlausibleSpeedMPerS),
                                    measurementSD: sa)

        // 5. Cadence cross-check. GPS reporting a stop while the accelerometer reports running
        //    cadence means GPS is wrong — common under trees and in tunnels.
        if filtered < 0.5 && cadenceSuggestsRunning {
            holdOrDrop(at: now)
            return
        }

        lastGoodSpeed = filtered
        lastGoodSpeedAt = now
        let quality: PaceSample.Quality = sa <= goodSpeedAccuracyMPerS ? .good : .degraded
        emit(speed: filtered, quality: quality, grade: smoothedGrade(), at: now)
    }

    /// No usable fix this tick. Hold the last good speed briefly — a runner's speed does not change
    /// much in two seconds, and a momentary GPS gap should not read as a collapse in pace — then
    /// admit we do not know.
    private func holdOrDrop(at now: Date) {
        if let s = lastGoodSpeed, let at = lastGoodSpeedAt, now.timeIntervalSince(at) <= 5 {
            emit(speed: s, quality: .estimated, grade: smoothedGrade(), at: now)
        } else {
            emit(speed: nil, quality: .unavailable, grade: nil, at: now)
        }
    }
}
