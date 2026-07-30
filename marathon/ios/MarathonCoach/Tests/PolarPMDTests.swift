//
//  PolarPMDTests.swift
//  Protocol tests for the PMD codec, ported alongside the codec itself.
//
//  The three tests that matter most are the regression guards for corrections carried over from
//  `polar_pmd.py`. Each of those bugs was found against real hardware, each produced silently wrong
//  data rather than an error, and each would be easy to reintroduce in a rewrite:
//
//    • `testChannelsSettingUsesOneByteNotTwo`
//    • `testFrameType0x02WithoutCompressionBitIsNotDelta`
//    • `testPpiBlockerBitMarksSampleUnusable`
//
//  Note these cannot run in the Linux CI that runs the Python suite — they need Xcode. That is the
//  honest limitation of the port: the Python engine is verified continuously, the Swift port is
//  verified when built. The shared JSON fixtures in `Fixtures/` exist so the two can be shown to
//  agree rather than assumed to.
//

import XCTest
@testable import MarathonCoachCore

final class PolarPMDTests: XCTestCase {

    // MARK: - START command encoding

    func testPpiStartTakesNoSettings() throws {
        let cmd = try PmdCodec.buildStartCommand(.ppi)
        XCTAssertEqual([UInt8](cmd), [0x02, 0x03],
                       "PPI must be started with no setting TLVs — the device rejects any")
    }

    func testStopCommand() {
        XCTAssertEqual([UInt8](PmdCodec.buildStopCommand(.acc)), [0x03, 0x02])
    }

    /// Reproduces the byte sequence documented for a real Verity Sense ACC start at 25 Hz / 16-bit / 2 G.
    func testAccStartMatchesDocumentedByteSequence() throws {
        let cmd = try PmdCodec.buildStartCommand(.acc, settings: [
            (.range, [2]), (.sampleRate, [25]), (.resolution, [16]),
        ])
        XCTAssertEqual([UInt8](cmd), [
            0x02, 0x02,              // START, ACC
            0x02, 0x01, 0x02, 0x00,  // RANGE = 2 (uint16)
            0x00, 0x01, 0x19, 0x00,  // SAMPLE_RATE = 25 (uint16)
            0x01, 0x01, 0x10, 0x00,  // RESOLUTION = 16 (uint16)
        ])
    }

    /// REGRESSION. CHANNELS is a one-byte value. Encoding it as uint16 writes an extra byte into the
    /// command and misaligns the parse of every following TLV. Confirmed three independent ways:
    /// Polar's PMD PDF (Table 5), bleakheart, and polar-python's field_size table.
    func testChannelsSettingUsesOneByteNotTwo() throws {
        let cmd = try PmdCodec.buildStartCommand(.acc, settings: [(.channels, [3])])
        XCTAssertEqual([UInt8](cmd), [0x02, 0x02, 0x04, 0x01, 0x03],
                       "CHANNELS must emit exactly one value byte, with no padding byte")
    }

    func testFactorSettingIsFourBytes() throws {
        let cmd = try PmdCodec.buildStartCommand(.ppg, settings: [(.factor, [1])])
        XCTAssertEqual([UInt8](cmd), [0x02, 0x01, 0x05, 0x01, 0x01, 0x00, 0x00, 0x00])
    }

    func testOutOfRangeSettingThrows() {
        XCTAssertThrowsError(try PmdCodec.buildStartCommand(.acc, settings: [(.channels, [999])]),
                             "a value too wide for its field must be rejected, not truncated")
    }

    // MARK: - Control response parsing

    func testParseSuccessfulControlResponse() throws {
        let data = Data([0xF0, 0x02, 0x03, 0x00, 0x00])
        let r = try PmdCodec.parseControlResponse(data)
        XCTAssertTrue(r.isSuccess)
        XCTAssertEqual(r.measurement, PmdMeasurement.ppi.rawValue)
    }

    func testParseErrorResponseNamesTheError() throws {
        let data = Data([0xF0, 0x02, 0x02, 0x0D, 0x00])   // 13 = device in charger
        let r = try PmdCodec.parseControlResponse(data)
        XCTAssertFalse(r.isSuccess)
        XCTAssertEqual(r.errorName, "device in charger")
    }

    func testAlreadyInStateIsDistinguishable() throws {
        let r = try PmdCodec.parseControlResponse(Data([0xF0, 0x02, 0x03, 0x06, 0x00]))
        XCTAssertEqual(r.errorCode, 6, "'already in state' is benign and must be identifiable")
    }

    /// Mixed setting widths in one response — the case the one-byte CHANNELS bug corrupted.
    func testParseResponseWithMixedWidthSettings() throws {
        let data = Data([0xF0, 0x01, 0x02, 0x00, 0x00,
                         0x04, 0x01, 0x03,              // CHANNELS = 3 (1 byte)
                         0x00, 0x01, 0x34, 0x00,        // SAMPLE_RATE = 52 (2 bytes)
                         0x01, 0x01, 0x10, 0x00])       // RESOLUTION = 16 (2 bytes)
        let r = try PmdCodec.parseControlResponse(data)
        XCTAssertEqual(r.settings[PmdSetting.channels.rawValue], [3])
        XCTAssertEqual(r.settings[PmdSetting.sampleRate.rawValue], [52],
                       "a setting after CHANNELS must still parse — this is what the width bug broke")
        XCTAssertEqual(r.settings[PmdSetting.resolution.rawValue], [16])
    }

    func testShortControlResponseThrows() {
        XCTAssertThrowsError(try PmdCodec.parseControlResponse(Data([0xF0, 0x02])))
    }

    func testWrongHeaderThrows() {
        XCTAssertThrowsError(try PmdCodec.parseControlResponse(Data([0xAA, 0x02, 0x03, 0x00, 0x00])))
    }

    // MARK: - PPI frames

    private func ppiFrame(hr: UInt8, ppiMs: UInt16, errorMs: UInt16, flags: UInt8) -> Data {
        var d = Data([PmdMeasurement.ppi.rawValue])
        d.append(Data(repeating: 0, count: 8))       // timestamp
        d.append(0x00)                               // frame type
        d.append(hr)
        d.append(UInt8(ppiMs & 0xFF)); d.append(UInt8(ppiMs >> 8))
        d.append(UInt8(errorMs & 0xFF)); d.append(UInt8(errorMs >> 8))
        d.append(flags)
        return d
    }

    func testParsePpiSample() throws {
        let (_, samples) = try PmdCodec.parsePpiFrame(
            ppiFrame(hr: 60, ppiMs: 1000, errorMs: 5, flags: 0x02))
        XCTAssertEqual(samples.count, 1)
        XCTAssertEqual(samples[0].hr, 60)
        XCTAssertEqual(samples[0].ppiMs, 1000)
        XCTAssertEqual(samples[0].errorMs, 5)
        XCTAssertTrue(samples[0].skinContact)
        XCTAssertTrue(samples[0].ok)
    }

    /// REGRESSION. The device's own verdict on a beat overrides anything we could infer from it.
    func testPpiBlockerBitMarksSampleUnusable() throws {
        let (_, samples) = try PmdCodec.parsePpiFrame(
            ppiFrame(hr: 60, ppiMs: 1000, errorMs: 5, flags: 0x01))
        XCTAssertTrue(samples[0].blocker)
        XCTAssertFalse(samples[0].ok, "a blocker-flagged interval must never be treated as usable")
    }

    func testPpiImplausibleIntervalIsNotOk() throws {
        for ms: UInt16 in [100, 3000] {
            let (_, s) = try PmdCodec.parsePpiFrame(
                ppiFrame(hr: 60, ppiMs: ms, errorMs: 0, flags: 0))
            XCTAssertFalse(s[0].ok, "\(ms) ms is outside the plausible 250–2500 ms window")
        }
    }

    func testPpiBoundaryValuesAreOk() throws {
        for ms: UInt16 in [250, 2500] {
            let (_, s) = try PmdCodec.parsePpiFrame(
                ppiFrame(hr: 60, ppiMs: ms, errorMs: 0, flags: 0))
            XCTAssertTrue(s[0].ok, "\(ms) ms is inclusive of the window bound")
        }
    }

    func testPpiPayloadNotMultipleOfSixThrows() {
        var d = Data([PmdMeasurement.ppi.rawValue])
        d.append(Data(repeating: 0, count: 8))
        d.append(0x00)
        d.append(Data([1, 2, 3]))
        XCTAssertThrowsError(try PmdCodec.parsePpiFrame(d))
    }

    func testPpiFrameWithWrongMeasurementTypeThrows() {
        var d = Data([PmdMeasurement.acc.rawValue])
        d.append(Data(repeating: 0, count: 8))
        d.append(0x00)
        XCTAssertThrowsError(try PmdCodec.parsePpiFrame(d))
    }

    // MARK: - ACC frames

    func testParseUncompressedAccFrame() throws {
        var d = Data([PmdMeasurement.acc.rawValue])
        d.append(Data(repeating: 0, count: 8))
        d.append(0x01)                                       // uncompressed 16-bit layout
        d.append(Data([0x10, 0x00, 0x20, 0x00, 0xF0, 0xFF]))  // x=16, y=32, z=-16
        let (_, samples) = try PmdCodec.parseAccFrame(d)
        XCTAssertEqual(samples.count, 1)
        XCTAssertEqual(samples[0].x, 16)
        XCTAssertEqual(samples[0].y, 32)
        XCTAssertEqual(samples[0].z, -16, "z must sign-extend from int16")
    }

    /// REGRESSION. Compression is bit 7 and only bit 7. The low bits are an independent raw-layout
    /// id where 0x02 means the 24-bit UNCOMPRESSED layout. An earlier version treated a literal 0x02
    /// as "delta", which fed raw frames through the delta decoder and produced plausible garbage.
    func testFrameType0x02WithoutCompressionBitIsNotDelta() {
        var d = Data([PmdMeasurement.acc.rawValue])
        d.append(Data(repeating: 0, count: 8))
        d.append(0x02)                                        // 24-bit RAW, not compressed
        d.append(Data(repeating: 0, count: 9))
        XCTAssertThrowsError(try PmdCodec.parseAccFrame(d),
                             "0x02 is an unsupported raw layout and must be rejected, not decoded "
                             + "as a delta frame")
    }

    func testCompressedFrameTypeIsRecognised() throws {
        var d = Data([PmdMeasurement.acc.rawValue])
        d.append(Data(repeating: 0, count: 8))
        d.append(0x80)                                        // compression bit set
        d.append(Data([0x64, 0x00, 0x00, 0x00, 0x00, 0x00]))  // reference x=100
        d.append(Data([0x04, 0x01]))                          // 4 bits/value, 1 sample
        d.append(Data([0x11, 0x00]))                          // deltas
        let (_, samples) = try PmdCodec.parseAccFrame(d)
        XCTAssertEqual(samples.count, 2, "reference sample plus one delta sample")
        XCTAssertEqual(samples[0].x, 100)
    }

    func testDeltaFrameMissingReferenceThrows() {
        var d = Data([PmdMeasurement.acc.rawValue])
        d.append(Data(repeating: 0, count: 8))
        d.append(0x80)
        d.append(Data([0x01, 0x02]))
        XCTAssertThrowsError(try PmdCodec.parseAccFrame(d))
    }

    // MARK: - Magnitudes and actigraphy

    func testAccMagnitudeScaling() {
        // At 16-bit / ±8 G, full scale (32768) is 8 G.
        let m = PmdCodec.accMagnitudesG([PmdCodec.AccSample(x: 4096, y: 0, z: 0)],
                                        resolutionBits: 16, rangeG: 8)
        XCTAssertEqual(m[0], 1.0, accuracy: 0.001)
    }

    func testActigraphyNeedsMinimumSamples() {
        XCTAssertNil(PmdCodec.actigraphyCounts([1.0, 1.0]))
    }

    func testActigraphyCountsCrossings() {
        let counts = PmdCodec.actigraphyCounts([1.0, 1.2, 1.0, 1.2, 1.0, 1.2])
        XCTAssertNotNil(counts)
        XCTAssertGreaterThan(counts!, 0)
    }

    func testStillnessProducesNoCrossings() {
        XCTAssertEqual(PmdCodec.actigraphyCounts(Array(repeating: 1.0, count: 20)), 0)
    }

    // MARK: - Warm-up state

    /// The rule that stops an integration reconnecting in a loop and never getting data.
    func testWarmupSilenceIsNotAFailure() {
        XCTAssertEqual(PmdCodec.warmupState(elapsed: 10, framesSeen: 0), .warmingUp)
        XCTAssertEqual(PmdCodec.warmupState(elapsed: 24, framesSeen: 0), .warmingUp,
                       "Polar documents ~25 s to the first PPI batch; this must not warn")
    }

    func testFramesSeenMeansStreaming() {
        XCTAssertEqual(PmdCodec.warmupState(elapsed: 5, framesSeen: 1), .streaming)
    }

    func testProlongedSilenceIsSdkModeSuspect() {
        XCTAssertEqual(PmdCodec.warmupState(elapsed: 200, framesSeen: 0), .sdkModeSuspect,
                       "the actionable diagnosis is 'power-cycle the band', not a generic timeout")
    }

    func testStalledBetweenGraceAndSdkSuspicion() {
        XCTAssertEqual(PmdCodec.warmupState(elapsed: 50, framesSeen: 0, grace: 40, sdkSuspect: 90),
                       .stalled)
    }

    // MARK: - Standard Heart Rate Service

    func testParseSimpleHeartRateMeasurement() throws {
        let m = try PmdCodec.parseHeartRateMeasurement(Data([0x00, 60]))
        XCTAssertEqual(m.bpm, 60)
        XCTAssertTrue(m.rrIntervalsMs.isEmpty)
        XCTAssertNil(m.sensorContact, "contact is nil when the device does not support reporting it")
    }

    func testParse16BitHeartRate() throws {
        let m = try PmdCodec.parseHeartRateMeasurement(Data([0x01, 0x2C, 0x01]))
        XCTAssertEqual(m.bpm, 300)
    }

    /// Polar reports RR in 1/1024 s. Converting once, here, means nothing downstream has to remember.
    func testRrIntervalsConvertFrom1024thsToMilliseconds() throws {
        // 1024 units = exactly 1000 ms.
        let m = try PmdCodec.parseHeartRateMeasurement(Data([0x10, 60, 0x00, 0x04]))
        XCTAssertEqual(m.rrIntervalsMs.count, 1)
        XCTAssertEqual(m.rrIntervalsMs[0], 1000.0, accuracy: 0.01)
    }

    func testMultipleRrIntervals() throws {
        let m = try PmdCodec.parseHeartRateMeasurement(
            Data([0x10, 60, 0x00, 0x04, 0x00, 0x04]))
        XCTAssertEqual(m.rrIntervalsMs.count, 2)
    }

    func testEnergyFieldIsSkippedCorrectlyBeforeRr() throws {
        // flags: 16-bit HR off, energy present (0x08), RR present (0x10)
        let m = try PmdCodec.parseHeartRateMeasurement(
            Data([0x18, 60, 0xE8, 0x03, 0x00, 0x04]))
        XCTAssertEqual(m.energyExpended, 1000)
        XCTAssertEqual(m.rrIntervalsMs.count, 1, "RR must parse after the energy field, not through it")
        XCTAssertEqual(m.rrIntervalsMs[0], 1000.0, accuracy: 0.01)
    }

    func testSensorContactReported() throws {
        let m = try PmdCodec.parseHeartRateMeasurement(Data([0x06, 60]))   // supported + detected
        XCTAssertEqual(m.sensorContact, true)
    }

    func testTruncatedHeartRateThrows() {
        XCTAssertThrowsError(try PmdCodec.parseHeartRateMeasurement(Data([0x00])))
    }
}
