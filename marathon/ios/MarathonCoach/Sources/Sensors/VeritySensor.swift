//
//  VeritySensor.swift
//  CoreBluetooth plumbing for the Polar Verity Sense. All protocol logic lives in PolarPMD.swift.
//
//  What this class does that a naive BLE manager does not:
//
//  • **Two modes, because PPI and real-time control are mutually exclusive.** This is the single
//    most important design decision in this file. Polar documents that *with PPI enabled, heart rate
//    updates only every ~5 seconds* — and the SleepController's own `polar_pmd.py` records the same
//    thing (`PPI_HR_UPDATE_S = 5.0`). A 5-second-stale heart rate is fine for overnight HRV and
//    useless for a 1 Hz controller doing lead compensation over a 30-second slope. So:
//
//      - `.run`  — subscribe to the standard HR service (0x180D) for ~1 Hz heart rate, plus ACC for
//                  cadence. **PPI is NOT started.** No beat-to-beat HRV during a run, which we do
//                  not need: in-run decisions use heart rate, pace, cadence and drift.
//      - `.rest` — start PPI (and ACC), for the overnight and orthostatic HRV that feeds readiness.
//                  Here the 5-second HR update and the 25-second warm-up cost nothing.
//
//    Getting this wrong is subtle and expensive: the app would appear to work, while every
//    real-time decision was made on heart-rate data five seconds out of date, which is a
//    meaningful fraction of the HR time constant the controller is built around.
//
//    A related hardware fact worth knowing: unlike the H10 chest strap, the **Verity Sense does not
//    report RR intervals in the standard Heart Rate Measurement characteristic**. Beat intervals are
//    available only through PMD/PPI. So `.run` mode genuinely has no beat-interval source on this
//    device, and that is a property of the hardware rather than a limitation of this code.
//
//  • **Streams the accelerometer, not just heart rate.** This is not a nice-to-have. Cadence from
//    the armband's own ACC is the only reliable way to detect PPG *cadence lock-on*, where the
//    optical algorithm latches onto step frequency and reports a rock-steady, plausible-looking
//    "heart rate" that is actually your step rate. Without ACC that failure is undetectable, and
//    the controller would confidently coach off a fake number.
//
//  • **Respects the PPI warm-up.** With PPI enabled, Polar documents that HR updates only every
//    ~5 s and the first PPI batch takes ~25 s. A manager that treats 25 s of silence as a fault
//    will reconnect in a loop and never get data. `PmdCodec.warmupState` encodes the rule and
//    nothing here reconnects while it returns `.warmingUp`.
//
//  • **Detects the SDK-mode trap.** If another app left the device in SDK mode, PPI starts
//    "successfully" and never delivers a sample. That is surfaced as a specific, actionable message
//    (power-cycle the band) rather than a generic timeout.
//
//  • **Falls back to the standard HR service.** If PMD is unavailable, 0x180D still gives HR and RR
//    intervals — which also means a Polar H10 chest strap works with this app unchanged.
//
//  Background operation: the app declares `bluetooth-central` in UIBackgroundModes so the stream
//  survives a locked screen for the length of a long run. Two caveats worth knowing rather than
//  discovering at 25 km: iOS will not scan for *new* peripherals reliably in the background, so the
//  band must be connected before the run starts; and a `CBCentralManager` created with a restore
//  identifier can be relaunched into the background after a crash, which is why state restoration
//  is wired up here rather than left out.
//

import Foundation
import CoreBluetooth
import Combine

// MARK: - Manager

public final class VeritySensor: NSObject, ObservableObject {

    /// `SensorMode` lives in `SensorTypes.swift` so the simulator can name a mode without linking
    /// CoreBluetooth. Aliased here because `VeritySensor.Mode` reads better at the call sites.
    public typealias Mode = SensorMode

    @Published public private(set) var mode: Mode = .run
    @Published public private(set) var status: VerityStatus = .disconnected(willRetry: false)
    @Published public private(set) var latest: VerityReading?
    @Published public private(set) var batteryPercent: Int?

    /// Continuous stream of readings for the run controller.
    public let readings = PassthroughSubject<VerityReading, Never>()

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var controlChar: CBCharacteristic?
    private var dataChar: CBCharacteristic?
    private var hrChar: CBCharacteristic?

    private var streamStart: Date?
    private var framesSeen = 0
    private var warmupTimer: Timer?

    /// Rolling ACC magnitudes for cadence estimation.
    private var accWindow: [(t: Date, magnitude: Double)] = []
    private var lastCadence: Double?

    /// Set once we know the ACC stream's actual configuration, so magnitudes scale correctly.
    private var accResolutionBits = 16
    private var accRangeG = 8

    private let restoreIdentifier = "coach.marathon.verity"
    private var wantsReconnect = true

    public override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main, options: [
            CBCentralManagerOptionRestoreIdentifierKey: restoreIdentifier,
            CBCentralManagerOptionShowPowerAlertKey: true,
        ])
    }

    /// Switch mode. Safe to call while connected: the streams are stopped and restarted.
    public func setMode(_ newMode: Mode) {
        guard newMode != mode else { return }
        mode = newMode
        guard let p = peripheral, let control = controlChar else { return }
        p.writeValue(PmdCodec.buildStopCommand(.ppi), for: control, type: .withResponse)
        p.writeValue(PmdCodec.buildStopCommand(.acc), for: control, type: .withResponse)
        startPmdStreams(p)
    }

    public func start(mode requested: Mode = .run) {
        mode = requested
        wantsReconnect = true
        guard central.state == .poweredOn else { return }
        // Prefer a known peripheral: background scanning for new devices is unreliable, so a run
        // that starts with the band already paired is far more robust than one that scans.
        let known = central.retrieveConnectedPeripherals(withServices: [
            CBUUID(string: PMD.serviceUUID), CBUUID(string: PMD.heartRateServiceUUID),
        ])
        if let p = known.first {
            connect(p)
        } else {
            status = .scanning
            central.scanForPeripherals(withServices: [
                CBUUID(string: PMD.heartRateServiceUUID), CBUUID(string: PMD.serviceUUID),
            ], options: nil)
        }
    }

    public func stop() {
        wantsReconnect = false
        warmupTimer?.invalidate(); warmupTimer = nil
        if let p = peripheral {
            if let c = controlChar {
                p.writeValue(PmdCodec.buildStopCommand(.ppi), for: c, type: .withResponse)
                p.writeValue(PmdCodec.buildStopCommand(.acc), for: c, type: .withResponse)
            }
            central.cancelPeripheralConnection(p)
        }
        central.stopScan()
        status = .disconnected(willRetry: false)
    }

    private func connect(_ p: CBPeripheral) {
        peripheral = p
        p.delegate = self
        status = .connecting
        central.stopScan()
        central.connect(p, options: nil)
    }

    // MARK: Warm-up supervision

    private func beginWarmupSupervision() {
        streamStart = Date()
        framesSeen = 0
        warmupTimer?.invalidate()
        warmupTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.evaluateWarmup()
        }
    }

    private func evaluateWarmup() {
        guard let start = streamStart else { return }
        let elapsed = Date().timeIntervalSince(start)
        switch PmdCodec.warmupState(elapsed: elapsed, framesSeen: framesSeen) {
        case .streaming:
            status = .streaming
            warmupTimer?.invalidate(); warmupTimer = nil
        case .warmingUp:
            // Deliberately do NOT reconnect or warn here — silence is documented and expected.
            status = .warmingUp(secondsElapsed: Int(elapsed))
        case .stalled:
            status = .stalled(reason: "no frames after \(Int(elapsed))s")
        case .sdkModeSuspect:
            status = .sdkModeSuspect(hint: sdkModeHint, remedy: sdkModeRemedy)
            warmupTimer?.invalidate(); warmupTimer = nil
        }
    }

    // MARK: Cadence from ACC

    /// Estimate cadence (steps per minute) from ACC magnitude peaks over a rolling window.
    ///
    /// Peak counting with a refractory period rather than an FFT: a runner's step rate sits in a
    /// narrow band (roughly 140–200 spm), the signal is strongly periodic, and peak counting has no
    /// window-length latency. The refractory period of 0.25 s caps detection at 240 spm, safely
    /// above any real cadence, and stops the double-bounce of a heel strike being counted twice.
    private func updateCadence(with samples: [PmdCodec.AccSample], at time: Date) {
        let mags = PmdCodec.accMagnitudesG(samples, resolutionBits: accResolutionBits,
                                           rangeG: accRangeG)
        for (i, m) in mags.enumerated() {
            // Spread the batch across the sample interval so timings stay roughly right.
            let dt = Double(mags.count - i) / 52.0
            accWindow.append((t: time.addingTimeInterval(-dt), magnitude: m))
        }
        let cutoff = time.addingTimeInterval(-6.0)
        accWindow.removeAll { $0.t < cutoff }
        guard accWindow.count > 60 else { return }

        let values = accWindow.map(\.magnitude)
        let mean = values.reduce(0, +) / Double(values.count)
        let sd = (values.map { ($0 - mean) * ($0 - mean) }.reduce(0, +)
                  / Double(values.count)).squareRoot()
        // Below this the arm is not swinging rhythmically — walking slowly or standing still.
        guard sd > 0.05 else { lastCadence = nil; return }

        let threshold = mean + 0.5 * sd
        var peaks: [Date] = []
        var lastPeak: Date?
        for i in 1..<(accWindow.count - 1) {
            let p = accWindow[i]
            guard p.magnitude > threshold,
                  p.magnitude >= accWindow[i - 1].magnitude,
                  p.magnitude >= accWindow[i + 1].magnitude else { continue }
            if let lp = lastPeak, p.t.timeIntervalSince(lp) < 0.25 { continue }
            peaks.append(p.t); lastPeak = p.t
        }
        guard peaks.count >= 4, let first = peaks.first, let last = peaks.last else { return }
        let span = last.timeIntervalSince(first)
        guard span > 1.0 else { return }
        let stepsPerMin = Double(peaks.count - 1) / span * 60.0
        lastCadence = (stepsPerMin > 100 && stepsPerMin < 240) ? stepsPerMin : nil
    }

    private func emit(hr: Int?, intervalsMs: [Double], skinContact: Bool?,
                     source: VerityReading.Source) {
        let r = VerityReading(timestamp: Date(), hrBpm: hr, intervalsMs: intervalsMs,
                              cadenceSpm: lastCadence, skinContact: skinContact,
                              batteryPercent: batteryPercent, source: source)
        latest = r
        readings.send(r)
    }
}

// MARK: - CBCentralManagerDelegate

extension VeritySensor: CBCentralManagerDelegate {

    public func centralManager(_ c: CBCentralManager, willRestoreState dict: [String: Any]) {
        // Relaunched into the background (e.g. after a crash mid-run). Pick the connection back up
        // rather than starting a fresh scan, which would likely fail in the background.
        if let ps = dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral],
           let p = ps.first {
            peripheral = p
            p.delegate = self
        }
    }

    public func centralManagerDidUpdateState(_ c: CBCentralManager) {
        switch c.state {
        case .poweredOn: if wantsReconnect { start(mode: mode) }
        case .poweredOff: status = .bluetoothOff
        case .unauthorized: status = .unauthorized
        default: status = .disconnected(willRetry: false)
        }
    }

    public func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral,
                               advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = (p.name ?? "").lowercased()
        // Accept a Verity Sense or an H10 — the HR-service path is identical for both.
        guard name.contains("polar") || name.contains("verity") || name.contains("sense") else { return }
        connect(p)
    }

    public func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        p.discoverServices([
            CBUUID(string: PMD.serviceUUID),
            CBUUID(string: PMD.heartRateServiceUUID),
            CBUUID(string: PMD.batteryServiceUUID),
        ])
    }

    public func centralManager(_ c: CBCentralManager, didFailToConnect p: CBPeripheral,
                               error: Error?) {
        status = .disconnected(willRetry: wantsReconnect)
        if wantsReconnect { start(mode: mode) }
    }

    public func centralManager(_ c: CBCentralManager, didDisconnectPeripheral p: CBPeripheral,
                               error: Error?) {
        warmupTimer?.invalidate(); warmupTimer = nil
        status = .disconnected(willRetry: wantsReconnect)
        // Reconnect directly to the known peripheral; iOS will hold the request until the band is
        // back in range, which is exactly what we want mid-run.
        if wantsReconnect { central.connect(p, options: nil) }
    }
}

// MARK: - CBPeripheralDelegate

extension VeritySensor: CBPeripheralDelegate {

    public func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        for s in p.services ?? [] {
            switch s.uuid.uuidString.uppercased() {
            case PMD.serviceUUID:
                p.discoverCharacteristics([CBUUID(string: PMD.controlUUID),
                                           CBUUID(string: PMD.dataUUID)], for: s)
            case CBUUID(string: PMD.heartRateServiceUUID).uuidString.uppercased():
                p.discoverCharacteristics([CBUUID(string: PMD.heartRateMeasurementUUID)], for: s)
            case CBUUID(string: PMD.batteryServiceUUID).uuidString.uppercased():
                p.discoverCharacteristics([CBUUID(string: PMD.batteryLevelUUID)], for: s)
            default: break
            }
        }
    }

    public func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService,
                           error: Error?) {
        for ch in s.characteristics ?? [] {
            switch ch.uuid.uuidString.uppercased() {
            case PMD.controlUUID:
                controlChar = ch
                p.setNotifyValue(true, for: ch)
            case PMD.dataUUID:
                dataChar = ch
                p.setNotifyValue(true, for: ch)
                startPmdStreams(p)
            case CBUUID(string: PMD.heartRateMeasurementUUID).uuidString.uppercased():
                hrChar = ch
                // Always subscribe: it is the fallback if PMD fails, and it costs nothing.
                p.setNotifyValue(true, for: ch)
            case CBUUID(string: PMD.batteryLevelUUID).uuidString.uppercased():
                p.readValue(for: ch)
                p.setNotifyValue(true, for: ch)
            default: break
            }
        }
    }

    private func startPmdStreams(_ p: CBPeripheral) {
        guard let control = controlChar else { return }
        do {
            // ACC always: it is the cadence source, and cadence is the only way to detect the
            // optical sensor locking onto step rate.
            p.writeValue(try PmdCodec.buildStartCommand(.acc, settings: pmdDefaultAccSettings),
                         for: control, type: .withResponse)

            if mode.usesPpi {
                // PPI takes NO settings — passing any is an error the device will reject.
                p.writeValue(try PmdCodec.buildStartCommand(.ppi), for: control, type: .withResponse)
                beginWarmupSupervision()
            } else {
                // .run mode: deliberately no PPI, so heart rate keeps arriving at ~1 Hz from the
                // standard Heart Rate Measurement characteristic instead of being throttled to
                // every 5 seconds. There is no PPI warm-up to wait for either, so a run can start
                // immediately rather than 25 seconds later.
                status = .streaming
            }
        } catch {
            status = .stalled(reason: "could not build PMD start command: \(error)")
        }
    }

    public func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic,
                           error: Error?) {
        guard let data = ch.value else { return }
        switch ch.uuid.uuidString.uppercased() {

        case PMD.controlUUID:
            guard let r = try? PmdCodec.parseControlResponse(data) else { return }
            if !r.isSuccess {
                // "already in state" is benign — it means the stream we asked for is running.
                if r.errorCode != 6 {
                    status = .stalled(reason: "PMD rejected the request: \(r.errorName)")
                }
            }
            // Adopt the resolution/range the device actually reports, so magnitudes scale right.
            if let res = r.settings[PmdSetting.resolution.rawValue]?.first { accResolutionBits = res }
            if let rng = r.settings[PmdSetting.range.rawValue]?.first { accRangeG = rng }

        case PMD.dataUUID:
            framesSeen += 1
            guard let type = PmdCodec.frameMeasurementType(data) else { return }
            if type == PmdMeasurement.ppi.rawValue {
                guard let (_, samples) = try? PmdCodec.parsePpiFrame(data) else { return }
                let good = samples.filter(\.ok)
                let hr = good.last?.hr ?? samples.last?.hr
                emit(hr: hr, intervalsMs: good.map { Double($0.ppiMs) },
                     skinContact: samples.last?.skinContact, source: .pmdPpi)
                if case .streaming = status {} else { status = .streaming }
            } else if type == PmdMeasurement.acc.rawValue {
                guard let (_, samples) = try? PmdCodec.parseAccFrame(data) else { return }
                updateCadence(with: samples, at: Date())
            }

        case CBUUID(string: PMD.heartRateMeasurementUUID).uuidString.uppercased():
            guard let m = try? PmdCodec.parseHeartRateMeasurement(data) else { return }
            // In .run mode this characteristic is the AUTHORITATIVE heart-rate source, not a
            // fallback — PPI is deliberately not running. In .rest mode it is the fallback, used
            // only when PPI is not delivering: PPI carries per-beat quality flags that the plain HR
            // service does not, and mixing the two would produce an HRV series with inconsistent
            // filtering and a step change in lnRMSSD on every switch.
            if mode == .run || latest?.source != .pmdPpi || !status.isUsable {
                emit(hr: m.bpm, intervalsMs: m.rrIntervalsMs, skinContact: m.sensorContact,
                     source: .heartRateService)
            }

        case CBUUID(string: PMD.batteryLevelUUID).uuidString.uppercased():
            batteryPercent = data.first.map(Int.init)

        default: break
        }
    }
}
