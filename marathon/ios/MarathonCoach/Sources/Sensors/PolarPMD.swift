//
//  PolarPMD.swift
//  Polar Measurement Data (PMD) protocol codec — pure Swift, no CoreBluetooth dependency.
//
//  This is a faithful port of `scripts/polar_pmd.py` from the SleepController project, which has
//  been running against real Verity Sense hardware. Porting rather than rewriting is deliberate:
//  that file carries several hard-won corrections that a fresh implementation would get wrong, and
//  they are all preserved here with their reasoning intact:
//
//    1. CHANNELS (0x04) is a ONE-byte setting value, not two. Encoding it as uint16 writes an extra
//       byte into every START command that configures channel count and misaligns the parse of
//       every subsequent TLV in a response. Confirmed three ways: Polar's official PMD PDF
//       (Table 5), bleakheart's `start_streaming`, and polar-python's `PmdSettingType.field_size`.
//       FACTOR (0x05) is four bytes (IEEE 754). Everything else is two.
//    2. Frame compression is signalled SOLELY by bit 7 (0x80) of the frame-type byte. The low 7
//       bits are an independent raw-layout id, where 0/1/2 mean 8/16/24-bit uncompressed ACC
//       samples. Treating a literal frame-type of 0x02 as "delta compressed" collides with the
//       uncompressed 24-bit layout and silently runs raw frames through the delta decoder.
//    3. PPI's skin-contact-supported bit (bit 2) polarity is an unresolved disagreement between
//       Polar's PDF prose and polar-python's hardware-tested code. We keep the tested polarity and
//       flag the conflict rather than silently trusting either source.
//
//  SDK MODE IS DELIBERATELY NOT IMPLEMENTED, and no opcode for it appears here. Polar documents
//  that SDK mode disables every on-device algorithm — "any computed data such as heart rate, PP
//  intervals, RR intervals, etc. is not available anymore" — in exchange for raw PPG and higher ACC
//  rates this app does not need. Our entire cardiac path is the device-computed HR and PPI, so SDK
//  mode would destroy exactly the signal we came for. The real hazard is a device left in SDK mode
//  by *another* app: PPI then starts "successfully" and never delivers a sample. `warmupState(...)`
//  detects that symptom so the UI can say "power-cycle the armband" instead of showing a generic
//  connection error.
//
//  No I/O here: this file only builds command bytes and parses frames, so it is fully unit-testable
//  without hardware. `VeritySensor.swift` owns all the CoreBluetooth plumbing.
//

import Foundation

// MARK: - UUIDs

public enum PMD {
    /// Polar's vendor "PMD" service and its two characteristics.
    public static let serviceUUID = "FB005C80-02E7-F387-1CAD-8ACD2D8DF0C8"
    public static let controlUUID = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"   // write + indicate
    public static let dataUUID    = "FB005C82-02E7-F387-1CAD-8ACD2D8DF0C8"   // notify

    /// Standard BLE Heart Rate Service — the fallback path that also works with a Polar H10.
    public static let heartRateServiceUUID = "180D"
    public static let heartRateMeasurementUUID = "2A37"
    public static let batteryServiceUUID = "180F"
    public static let batteryLevelUUID = "2A19"
}

// MARK: - Opcodes, measurement types, settings

public enum PmdOpcode: UInt8 {
    case getSettings = 0x01
    case startMeasurement = 0x02
    case stopMeasurement = 0x03
    // NOTE: there is no SDK-mode case, and none may be added. See the file header.
}

public enum PmdMeasurement: UInt8, CaseIterable {
    case ecg = 0x00
    case ppg = 0x01
    case acc = 0x02
    case ppi = 0x03
    case gyro = 0x05
    case mag = 0x06

    public var name: String {
        switch self {
        case .ecg: return "ecg"
        case .ppg: return "ppg"
        case .acc: return "acc"
        case .ppi: return "ppi"
        case .gyro: return "gyro"
        case .mag: return "mag"
        }
    }
}

public enum PmdSetting: UInt8 {
    case sampleRate = 0x00
    case resolution = 0x01
    case range = 0x02
    // 0x03 ("RANGE_MILLIUNIT") exists in Polar's PDF but is labelled "NOT USED" there and is never
    // sent by either reference implementation — deliberately omitted.
    case channels = 0x04
    case factor = 0x05

    /// Wire width of this setting's value, in bytes. See correction (1) in the file header.
    public var fieldSize: Int {
        switch self {
        case .channels: return 1
        case .factor: return 4
        default: return 2
        }
    }
}

public let pmdControlResponseHeader: UInt8 = 0xF0

public let pmdErrorNames: [UInt8: String] = [
    0: "success", 1: "invalid op code", 2: "invalid measurement type", 3: "not supported",
    4: "invalid length", 5: "invalid parameter", 6: "already in state", 7: "invalid resolution",
    8: "invalid sample rate", 9: "invalid range", 10: "invalid MTU",
    11: "invalid number of channels", 12: "invalid state", 13: "device in charger",
]

/// Compression is bit 7 of the frame-type byte, and ONLY bit 7. See correction (2).
public let pmdFrameTypeCompressedBit: UInt8 = 0x80
public let pmdFrameTypeUncompressed: Set<UInt8> = [0x00, 0x01]

/// Default ACC stream configuration: 52 Hz, 16-bit, ±8 G. Ordered RANGE → SAMPLE_RATE → RESOLUTION
/// to reproduce Polar's own verified byte sequence exactly.
public let pmdDefaultAccSettings: [(PmdSetting, [Int])] = [
    (.range, [8]), (.sampleRate, [52]), (.resolution, [16]),
]

/// Gyroscope: 52 Hz, ±2000 deg/s, 16-bit.
///
/// Worth streaming during a *calibration* recording and not during ordinary runs. Arm-swing rotation
/// is a cleaner periodic signal than acceleration magnitude, so cadence and stride-to-stride
/// variability come out less noisy — but it is a third concurrent stream, and battery and BLE
/// throughput are finite over a three-hour long run. Cadence from ACC alone is good enough for
/// real-time use; gyro earns its place when the goal is measurement rather than coaching.
public let pmdDefaultGyroSettings: [(PmdSetting, [Int])] = [
    (.range, [2000]), (.sampleRate, [52]), (.resolution, [16]),
]

/// Magnetometer: 50 Hz, ±50 Gauss, 16-bit.
///
/// Not used by the coaching engine. Included for completeness because the SDK exposes it, and noted
/// here so the omission is a decision rather than an oversight: heading adds nothing to pace, effort
/// or gait, and CoreLocation already supplies a better heading when one is wanted.
public let pmdDefaultMagSettings: [(PmdSetting, [Int])] = [
    (.range, [50]), (.sampleRate, [50]), (.resolution, [16]),
]

// MARK: - Plausibility windows and warm-up timings

/// 240 bpm … 24 bpm. Identical to the SleepController's window so HRV figures from the two systems
/// stay directly comparable.
public let ppiMinMs = 250
public let ppiMaxMs = 2500

/// Per Polar's Verity Sense documentation: with PPI enabled, HR updates only every ~5 s and the
/// FIRST PPI batch takes ~25 s. Silence inside this window is NORMAL — nothing may reconnect or
/// warn during it, which is the single most common way an integration looks broken when it is not.
public let ppiFirstSampleSeconds: TimeInterval = 25
public let ppiHrUpdateSeconds: TimeInterval = 5
public let pmdStartupGraceSeconds: TimeInterval = 40
public let sdkModeSuspectSeconds: TimeInterval = 90

public let sdkModeHint = """
No PPI samples well past the documented warm-up. The most likely cause is that the armband was \
left in SDK mode by another app, in which case PPI starts successfully and never delivers data.
"""
public let sdkModeRemedy = "Power-cycle the Verity Sense (hold the button until it powers off, then on)."

// MARK: - Errors

public enum PmdError: Error, CustomStringConvertible {
    case parse(String)
    case settingOutOfRange(PmdSetting, Int)

    public var description: String {
        switch self {
        case .parse(let m): return "PMD parse error: \(m)"
        case .settingOutOfRange(let s, let v): return "PMD setting \(s) out of range: \(v)"
        }
    }
}

// MARK: - Command building

public enum PmdCodec {

    /// Build a START MEASUREMENT control-point command.
    ///
    /// Each TLV is `[settingType][count:uint8][value…]`, little-endian, with each value
    /// `setting.fieldSize` bytes wide. PPI takes NO settings — pass an empty array.
    ///
    /// Example: ACC at 25 Hz / 16-bit / 2 G is
    /// `02 02 | 02 01 02 00 | 00 01 19 00 | 01 01 10 00`.
    public static func buildStartCommand(_ measurement: PmdMeasurement,
                                        settings: [(PmdSetting, [Int])] = []) throws -> Data {
        var out = Data([PmdOpcode.startMeasurement.rawValue, measurement.rawValue])
        for (setting, values) in settings {
            let width = setting.fieldSize
            let maxValue = width >= 8 ? Int.max : (1 << (8 * width)) - 1
            for v in values where v < 0 || v > maxValue {
                throw PmdError.settingOutOfRange(setting, v)
            }
            out.append(setting.rawValue)
            out.append(UInt8(values.count & 0xFF))
            for v in values {
                for byte in 0..<width {
                    out.append(UInt8((v >> (8 * byte)) & 0xFF))
                }
            }
        }
        return out
    }

    public static func buildStopCommand(_ measurement: PmdMeasurement) -> Data {
        Data([PmdOpcode.stopMeasurement.rawValue, measurement.rawValue])
    }

    // MARK: - Control response parsing

    public struct ControlResponse {
        public let opcode: UInt8
        public let measurement: UInt8
        public let errorCode: UInt8
        public let more: Bool
        public let settings: [UInt8: [Int]]

        public var isSuccess: Bool { errorCode == 0 }
        public var errorName: String { pmdErrorNames[errorCode] ?? "unknown error \(errorCode)" }
    }

    /// Parse a control-point response: `[0xF0][opcode][measType][error][more][setting TLVs…]`.
    public static func parseControlResponse(_ data: Data) throws -> ControlResponse {
        let bytes = [UInt8](data)
        guard bytes.count >= 5 else {
            throw PmdError.parse("control response too short (\(bytes.count) bytes)")
        }
        guard bytes[0] == pmdControlResponseHeader else {
            throw PmdError.parse(String(format: "unexpected control response header 0x%02X", bytes[0]))
        }
        var settings: [UInt8: [Int]] = [:]
        var i = 5
        while i + 1 < bytes.count {
            let settingId = bytes[i]
            let count = Int(bytes[i + 1])
            let width = PmdSetting(rawValue: settingId)?.fieldSize ?? 2
            i += 2
            var values: [Int] = []
            for _ in 0..<count {
                guard i + width <= bytes.count else {
                    throw PmdError.parse("truncated setting TLV for id \(settingId)")
                }
                var v = 0
                for b in 0..<width { v |= Int(bytes[i + b]) << (8 * b) }
                values.append(v)
                i += width
            }
            settings[settingId] = values
        }
        return ControlResponse(opcode: bytes[1], measurement: bytes[2], errorCode: bytes[3],
                               more: bytes[4] != 0, settings: settings)
    }

    // MARK: - Data frame parsing

    /// Split a data frame into `(timestampNs, frameType, payload)`.
    ///
    /// Layout: `[measType][timestamp:uint64 LE ns][frameType][payload…]`. The timestamp is the time
    /// of the LAST sample in the frame, not the first — getting this backwards skews every
    /// derived rate.
    static func splitFrame(_ data: Data, expecting measurement: PmdMeasurement) throws
        -> (timestampNs: UInt64, frameType: UInt8, payload: [UInt8]) {
        let bytes = [UInt8](data)
        guard bytes.count >= 10 else {
            throw PmdError.parse("data frame too short (\(bytes.count) bytes)")
        }
        guard bytes[0] == measurement.rawValue else {
            throw PmdError.parse("expected measurement \(measurement.name), got \(bytes[0])")
        }
        var ts: UInt64 = 0
        for b in 0..<8 { ts |= UInt64(bytes[1 + b]) << (8 * UInt64(b)) }
        return (ts, bytes[9], Array(bytes[10...]))
    }

    public static func frameMeasurementType(_ data: Data) -> UInt8? {
        data.first
    }

    // MARK: PPI

    public struct PpiSample {
        public let hr: Int
        public let ppiMs: Int
        public let errorMs: Int
        public let blocker: Bool
        public let skinContact: Bool
        public let skinContactSupported: Bool

        /// `false` when the device flagged the beat, or the interval is physiologically implausible.
        public var ok: Bool { !blocker && ppiMs >= ppiMinMs && ppiMs <= ppiMaxMs }
    }

    /// Parse a PPI data frame.
    ///
    /// Each 6-byte sample is `[hr:uint8][ppiMs:uint16 LE][errorMs:uint16 LE][flags]` where flags
    /// bit0 = blocker (interval unreliable), bit1 = skin contact detected, bit2 = skin contact
    /// supported.
    ///
    /// Field order/widths and bits 0–1 are confirmed against Polar's PMD PDF (Table 22, "PPi Data,
    /// TYPE0") and polar-python's `PPIData._data_from_raw_type_0`, which agree exactly on real H10
    /// and Verity Sense hardware. Bit 2 is an UNRESOLVED disagreement: the PDF's prose says
    /// "bit 2: 1 if sensor contact is not supported" (1 = NOT supported), while polar-python's
    /// hardware-tested code treats bit 2 truthy as "supported". We keep the tested polarity, since
    /// the PDF's prose has known OCR/wording artifacts elsewhere in the same document, and flag the
    /// conflict here rather than silently trusting one source.
    public static func parsePpiFrame(_ data: Data) throws -> (timestampNs: UInt64, samples: [PpiSample]) {
        let (ts, _, payload) = try splitFrame(data, expecting: .ppi)
        guard payload.count % 6 == 0 else {
            throw PmdError.parse("PPI payload not a multiple of 6 bytes (\(payload.count))")
        }
        var samples: [PpiSample] = []
        samples.reserveCapacity(payload.count / 6)
        for off in stride(from: 0, to: payload.count, by: 6) {
            let flags = payload[off + 5]
            samples.append(PpiSample(
                hr: Int(payload[off]),
                ppiMs: Int(payload[off + 1]) | (Int(payload[off + 2]) << 8),
                errorMs: Int(payload[off + 3]) | (Int(payload[off + 4]) << 8),
                blocker: flags & 0x01 != 0,
                skinContact: flags & 0x02 != 0,
                skinContactSupported: flags & 0x04 != 0))
        }
        return (ts, samples)
    }

    // MARK: ACC

    public struct AccSample {
        public let x: Int
        public let y: Int
        public let z: Int
    }

    /// Parse an ACC frame, handling both the uncompressed 16-bit layout and Polar's delta format.
    ///
    /// Delta layout: `[reference sample: 3 × int16 LE][ (deltaBits:uint8, sampleCount:uint8) then
    /// packed signed deltas ]*`. Deltas are bit-packed at `deltaBits` per channel value, three
    /// channels per sample, and are cumulative against the running reference.
    public static func parseAccFrame(_ data: Data) throws -> (timestampNs: UInt64, samples: [AccSample]) {
        let (ts, frameType, payload) = try splitFrame(data, expecting: .acc)
        let raw = try decodeTriaxial(payload: payload, frameType: frameType)
        return (ts, raw.map { AccSample(x: $0.0, y: $0.1, z: $0.2) })
    }

    /// Shared triaxial decoder for ACC and GYRO, which use identical framing.
    ///
    /// Delta layout: `[reference: 3 × int16 LE][ (deltaBits:u8, sampleCount:u8) then packed signed
    /// deltas ]*`, deltas cumulative against the running reference.
    static func decodeTriaxial(payload: [UInt8], frameType: UInt8) throws -> [(Int, Int, Int)] {
        let compressed = frameType & pmdFrameTypeCompressedBit != 0

        if !compressed {
            // Only the 16-bit uncompressed layout (low bits == 0x01) is implemented. The 8-bit and
            // 24-bit layouts are rejected rather than guessed at — see correction (2): a literal
            // frame type of 0x02 is the 24-bit RAW layout, not a delta frame.
            guard frameType & 0x7F == 0x01 else {
                throw PmdError.parse(String(format:
                    "unsupported uncompressed ACC layout 0x%02X (only 16-bit is implemented)", frameType))
            }
            guard payload.count % 6 == 0 else {
                throw PmdError.parse("uncompressed payload not a multiple of 6 bytes")
            }
            var out: [(Int, Int, Int)] = []
            for off in stride(from: 0, to: payload.count, by: 6) {
                out.append((int16LE(payload, off), int16LE(payload, off + 2),
                            int16LE(payload, off + 4)))
            }
            return out
        }

        guard payload.count >= 6 else { throw PmdError.parse("delta frame missing reference sample") }
        var ref = [int16LE(payload, 0), int16LE(payload, 2), int16LE(payload, 4)]
        var out: [(Int, Int, Int)] = [(ref[0], ref[1], ref[2])]
        var i = 6
        while i + 2 <= payload.count {
            let deltaBits = Int(payload[i])
            let sampleCount = Int(payload[i + 1])
            i += 2
            guard deltaBits > 0, sampleCount > 0 else { break }
            let totalBits = deltaBits * 3 * sampleCount
            let totalBytes = (totalBits + 7) / 8
            guard i + totalBytes <= payload.count else {
                throw PmdError.parse("truncated delta block (need \(totalBytes) bytes)")
            }
            var bitOffset = 0
            let block = Array(payload[i..<(i + totalBytes)])
            for _ in 0..<sampleCount {
                for ch in 0..<3 {
                    let raw = readBits(block, bitOffset: bitOffset, count: deltaBits)
                    bitOffset += deltaBits
                    ref[ch] += signExtend(raw, bits: deltaBits)
                }
                out.append((ref[0], ref[1], ref[2]))
            }
            i += totalBytes
        }
        return out
    }

    // MARK: - Bit helpers

    static func int16LE(_ bytes: [UInt8], _ offset: Int) -> Int {
        Int(Int16(bitPattern: UInt16(bytes[offset]) | (UInt16(bytes[offset + 1]) << 8)))
    }

    static func readBits(_ bytes: [UInt8], bitOffset: Int, count: Int) -> Int {
        var value = 0
        for i in 0..<count {
            let bit = bitOffset + i
            let byte = bit >> 3
            guard byte < bytes.count else { break }
            if bytes[byte] & (1 << UInt8(bit & 7)) != 0 { value |= 1 << i }
        }
        return value
    }

    static func signExtend(_ value: Int, bits: Int) -> Int {
        guard bits > 0, bits < 64 else { return value }
        let signBit = 1 << (bits - 1)
        return (value & signBit) != 0 ? value - (1 << bits) : value
    }

    // MARK: Gyroscope

    public struct GyroSample {
        /// deg/s per axis.
        public let x: Double
        public let y: Double
        public let z: Double

        public var magnitude: Double { (x * x + y * y + z * z).squareRoot() }
    }

    /// Parse a gyroscope frame. Same framing and delta-compression scheme as ACC, so the raw decode is
    /// shared; only the scaling differs.
    public static func parseGyroFrame(_ data: Data,
                                      rangeDps: Int = 2000,
                                      resolutionBits: Int = 16) throws -> (timestampNs: UInt64,
                                                                           samples: [GyroSample]) {
        let (ts, frameType, payload) = try splitFrame(data, expecting: .gyro)
        let raw = try decodeTriaxial(payload: payload, frameType: frameType)
        let scale = Double(rangeDps) / Double(1 << (resolutionBits - 1))
        return (ts, raw.map { GyroSample(x: Double($0.0) * scale,
                                         y: Double($0.1) * scale,
                                         z: Double($0.2) * scale) })
    }

    /// Peak-to-peak gyroscope magnitude over a window, in deg/s — an arm-swing amplitude proxy.
    ///
    /// Tracked because a *falling* swing amplitude through a long run is a genuine fatigue signature.
    /// It is not a gait measurement: from the upper arm this describes arm mechanics, not what the
    /// foot is doing, and ground contact time or vertical oscillation cannot be inferred from it.
    public static func gyroPeakToPeak(_ samples: [GyroSample]) -> Double? {
        guard samples.count >= 2 else { return nil }
        let mags = samples.map(\.magnitude)
        return (mags.max() ?? 0) - (mags.min() ?? 0)
    }

    // MARK: - Actigraphy

    /// Convert raw ACC samples to magnitudes in g.
    ///
    /// `resolutionBits` and `rangeG` must match what the stream was started with — the raw counts
    /// are meaningless without them, and mismatching them silently rescales every magnitude.
    public static func accMagnitudesG(_ samples: [AccSample],
                                      resolutionBits: Int = 16, rangeG: Int = 8) -> [Double] {
        let full = Double(1 << (resolutionBits - 1))
        let scale = Double(rangeG) / full
        return samples.map { s in
            let x = Double(s.x) * scale, y = Double(s.y) * scale, z = Double(s.z) * scale
            return (x * x + y * y + z * z).squareRoot()
        }
    }

    /// Zero-crossing-mode actigraphy counts for one epoch.
    ///
    /// These constants MUST match `scripts/reduce_motion_activity.py` in the SleepController so the
    /// counts remain directly comparable with the data its sleep-staging model was trained on.
    public static let zcmThresholdG = 0.01
    public static let minEpochSamples = 5

    public static func actigraphyCounts(_ magnitudesG: [Double]) -> Int? {
        guard magnitudesG.count >= minEpochSamples else { return nil }
        let mean = magnitudesG.reduce(0, +) / Double(magnitudesG.count)
        var crossings = 0
        var above = magnitudesG[0] > mean + zcmThresholdG
        for m in magnitudesG.dropFirst() {
            let nowAbove = m > mean + zcmThresholdG
            if nowAbove != above { crossings += 1; above = nowAbove }
        }
        return crossings
    }

    // MARK: - Warm-up state

    public enum WarmupState: String {
        case streaming, warmingUp, stalled, sdkModeSuspect
    }

    /// Classify a quiet PMD stream.
    ///
    /// PPI legitimately produces nothing for ~25 s after START, so a stream that has delivered no
    /// frames is only `stalled` once the grace period has elapsed, and only `sdkModeSuspect` past
    /// `sdkModeSuspectSeconds`. **Nothing may reconnect or warn while the state is `warmingUp`.**
    public static func warmupState(elapsed: TimeInterval, framesSeen: Int,
                                   grace: TimeInterval = pmdStartupGraceSeconds,
                                   sdkSuspect: TimeInterval = sdkModeSuspectSeconds) -> WarmupState {
        if framesSeen > 0 { return .streaming }
        if elapsed >= max(sdkSuspect, grace) { return .sdkModeSuspect }
        if elapsed < max(grace, ppiFirstSampleSeconds) { return .warmingUp }
        return .stalled
    }

    // MARK: - Standard Heart Rate Service (0x180D)

    public struct HeartRateMeasurement {
        public let bpm: Int
        public let rrIntervalsMs: [Double]
        public let sensorContact: Bool?
        public let energyExpended: Int?
    }

    /// Parse a 0x2A37 Heart Rate Measurement notification.
    ///
    /// Polar reports RR intervals in 1/1024-second units; they are converted to milliseconds here,
    /// once, so nothing downstream has to remember to.
    public static func parseHeartRateMeasurement(_ data: Data) throws -> HeartRateMeasurement {
        let bytes = [UInt8](data)
        guard bytes.count >= 2 else { throw PmdError.parse("HR measurement too short") }
        let flags = bytes[0]
        let sixteenBit = flags & 0x01 != 0
        let contactSupported = flags & 0x04 != 0
        let contactDetected = flags & 0x02 != 0
        let hasEnergy = flags & 0x08 != 0
        let hasRR = flags & 0x10 != 0

        var i = 1
        let bpm: Int
        if sixteenBit {
            guard bytes.count >= 3 else { throw PmdError.parse("16-bit HR truncated") }
            bpm = Int(bytes[1]) | (Int(bytes[2]) << 8); i = 3
        } else {
            bpm = Int(bytes[1]); i = 2
        }

        var energy: Int?
        if hasEnergy {
            guard i + 2 <= bytes.count else { throw PmdError.parse("energy field truncated") }
            energy = Int(bytes[i]) | (Int(bytes[i + 1]) << 8); i += 2
        }

        var rr: [Double] = []
        if hasRR {
            while i + 2 <= bytes.count {
                let raw = Int(bytes[i]) | (Int(bytes[i + 1]) << 8)
                rr.append(Double(raw) * 1000.0 / 1024.0)   // 1/1024 s → ms
                i += 2
            }
        }
        return HeartRateMeasurement(bpm: bpm, rrIntervalsMs: rr,
                                    sensorContact: contactSupported ? contactDetected : nil,
                                    energyExpended: energy)
    }
}
