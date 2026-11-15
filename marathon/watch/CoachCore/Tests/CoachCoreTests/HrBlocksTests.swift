// The same behaviours as marathon/tools/tests/hr-blocks-test.mjs, against the Swift port.

import XCTest
@testable import CoachCore

final class HrBlocksTests: XCTestCase {
    let ceil = 150.0, floor = 125.0

    /// Drive the controller for `seconds`, `hrAt(t, phase)` supplying heart rate; returns transitions.
    @discardableResult
    func drive(_ b: HrBlocks, _ seconds: Int, from: Int = 0,
               _ hrAt: (Double, BlockPhase) -> Double?) -> [(t: Double, tr: BlockTransition)] {
        var out: [(Double, BlockTransition)] = []
        for i in from..<(from + seconds) {
            let t = Double(i)
            if let tr = b.update(t: t, hr: hrAt(t, b.phase)) { out.append((t, tr)) }
        }
        return out
    }

    func testWarmupIsFiveMinutesEvenWhenHeartRateIsLow() {
        let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 120, walkS: 120, reps: 7)
        let evs = drive(b, 400) { _, _ in 100 }
        XCTAssertEqual(evs.first { $0.tr.phase == .run }?.t, 300)
    }

    func testBlockEndsAtCeilingAndWalkEndsAtFloor() {
        let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 180, walkS: 120, reps: 2)
        var hr = 110.0
        let evs = drive(b, 1500) { _, phase in
            hr += ((phase == .run ? 170 : 100) - hr) / 30
            return hr
        }
        let firstWalk = evs.first { $0.tr.phase == .walk }
        XCTAssertEqual(firstWalk?.tr.reason, "ceiling")
        let back = evs.first { $0.tr.phase == .run && $0.tr.reason == "recovered" }
        XCTAssertNotNil(back, "the walk ends when heart rate is back at the floor")
        XCTAssertGreaterThanOrEqual(b.summary().blocksCut, 1)
    }

    func testFullBlocksNeedNoExtras() {
        let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 120, walkS: 120, reps: 3, runningTargetS: 360)
        drive(b, 3000) { _, phase in phase == .run ? 140 : 110 }
        XCTAssertEqual(b.phase, .cooldown)
        XCTAssertEqual(b.summary().runBlocks, 3)
        XCTAssertEqual(b.summary().blocksFull, 3)
    }

    func testCutBlocksAreMadeUpToTheWholePlannedRunning() {
        // 26 October: blocks cut at ~95 s. Extra blocks run until all 840 s are done (at most 3).
        let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 120, walkS: 120, reps: 7, runningTargetS: 840)
        drive(b, 6000) { t, phase in
            guard phase == .run, let start = b.phaseStartT else { return 110 }
            return t - start >= 95 ? 150 : 140
        }
        let s = b.summary()
        XCTAssertGreaterThanOrEqual(s.runningS, 840)
        XCTAssertEqual(s.runBlocks, 9)
        XCTAssertLessThanOrEqual(s.longestRunBlockS, 120)
    }

    func testLagAheadEndsTheBlockOnTheTrueCrossing() {
        // The sensor reports 10 s late; true heart rate climbs 0.4 bpm/s from 125: it crosses 150 at
        // 62 s, the reading at 72 s.
        func run(lag: Double) -> Double {
            var cfg = HrBlockConfig(); cfg.lagS = lag
            let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 180, walkS: 120, reps: 1, config: cfg)
            var start: Double?
            let evs = drive(b, 700) { t, phase in
                if phase == .run && start == nil { start = t }
                guard phase == .run, let s = start else { return 120 }
                return (125 + 0.4 * max(0, t - s - 10)).rounded()
            }
            return evs.first { $0.tr.previous == .run }!.t - start!
        }
        let raw = run(lag: 0), ahead = run(lag: 10)
        XCTAssert((72...74).contains(raw), "on the reading: \(raw)")
        XCTAssert((60...66).contains(ahead), "carried ahead: \(ahead)")
    }

    func testWalkLevelledJustAboveFloorEnds() {
        func walkLength(level: Double) -> Double {
            let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 60, walkS: 120, reps: 3)
            var walkT: Double?
            let evs = drive(b, 900) { t, phase in
                guard phase == .walk else { walkT = nil; return phase == .run ? 140 : 110 }
                if walkT == nil { walkT = t }
                return max(level, 150 - (t - walkT!))
            }
            let w = evs.first { $0.tr.phase == .walk }!.t
            return evs.first { $0.tr.phase == .run && $0.t > w }!.t - w
        }
        XCTAssert((45...60).contains(walkLength(level: floor + 2)))
        XCTAssertEqual(walkLength(level: floor + 6), 120 + 90)
    }

    func testTwoUnrecoveredWalksEndTheRunning() {
        let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 60, walkS: 60, reps: 8)
        drive(b, 3000) { _, phase in phase == .run ? 140 : 145 }
        XCTAssertEqual(b.phase, .cooldown)
        XCTAssertEqual(b.summary().endedBy, "stall")
    }

    func testNoHeartRateFallsBackToTheClock() {
        let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 60, walkS: 60, reps: 2)
        let evs = drive(b, 800) { _, _ in nil }
        XCTAssertEqual(evs.first { $0.tr.phase == .walk }?.tr.reason, "time")
        XCTAssertEqual(b.phase, .cooldown)
    }

    func testSummaryCarriesThePeakInsideRunBlocks() {
        let b = HrBlocks(ceilingBpm: ceil, floorBpm: floor, runBlockS: 60, walkS: 60, reps: 2)
        drive(b, 900) { _, phase in phase == .run ? 138 : phase == .walk ? 145 : 110 }
        XCTAssertEqual(b.summary().peakRunHr, 138)
    }
}
