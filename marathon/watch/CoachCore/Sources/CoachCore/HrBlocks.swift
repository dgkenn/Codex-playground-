// Run and walk decided by heart rate, not by a clock. A port of marathon/tools/hr-blocks.js, which
// carries the full reasoning behind every number here; this file keeps the rules and the history
// that set them short.
//
// A session is a walk warm-up, then run blocks that end at the heart-rate ceiling or the rung's block
// length, each followed by a walk that ends when heart rate is back at the floor (or has levelled
// just above it), then a cool-down. Blocks the ceiling cut short are made up with up to three extra
// ones until the rung's running is done. Decisions use the heart rate `lagS` seconds ahead of the
// reading, because optical sensors report about 10 s late (measured on this athlete's runs).
//
// Not ported yet: hills (set-aside hill blocks, walking steep descents) and page-freeze shifts, which
// a watch workout does not have.

import Foundation

public enum BlockPhase: String, Codable, Sendable {
    case warmup, run, walk, cooldown, done
}

public struct HrBlockConfig: Sendable {
    /// Never call a run block shorter than this: heart rate lags effort.
    public var minRunS: Double = 30
    /// ...unless heart rate is this far over the ceiling.
    public var hardOverBpm: Double = 15
    /// A bound against a block silently becoming a continuous run.
    public var maxRunS: Double = 2400
    /// A walk shorter than this has not recovered anything.
    public var minWalkS: Double = 45
    /// How far past the prescribed walk a break may run while heart rate is above the floor.
    public var walkExtraS: Double = 90
    /// The walk cap when the plan gave no walk length.
    public var maxWalkS: Double = 210
    /// The walk warm-up, a minimum.
    public var warmupS: Double = 300
    /// Blocks past the plan's count to make up running the ceiling cut short.
    public var extraBlocks: Int = 3
    /// A walk levelled within this of the floor (flat to plateauRangeBpm over plateauS) is over.
    public var plateauBpm: Double = 3
    public var plateauS: Double = 30
    public var plateauRangeBpm: Double = 2
    /// The sensor's reporting delay: decisions use the reading carried this far ahead on its trend.
    public var lagS: Double = 0
    public var trendS: Double = 12
    public var maxTrendBpmS: Double = 1.5
    /// Seconds without a fresh reading before heart rate is not trusted.
    public var hrStaleS: Double = 12

    public init() {}
}

/// A change of phase: what to tell the athlete.
public struct BlockTransition: Equatable, Sendable {
    public let phase: BlockPhase
    public let previous: BlockPhase
    public let reason: String
    public let rep: Int
}

public struct Block: Codable, Equatable, Sendable {
    public let kind: BlockPhase
    public let startT: Double
    public let endT: Double
    public let reason: String
    public let peakHr: Double?
    public var durationS: Double { endT - startT }
    public var full: Bool { kind == .run && reason == "full" }
    public var cut: Bool { kind == .run && (reason == "ceiling" || reason == "well over the ceiling") }
}

public struct HrBlockSummary: Codable, Equatable, Sendable {
    public let runBlocks: Int
    public let blocksPlanned: Int?
    public let blocksFull: Int
    public let blocksCut: Int
    public let runningS: Double
    public let runningTargetS: Double?
    public let longestRunBlockS: Double
    public let walkS: Double
    public let peakRunHr: Double?
    public let ceilingBpm: Double
    public let floorBpm: Double
    public let endedBy: String?
}

public final class HrBlocks {
    public let cfg: HrBlockConfig
    public let ceilingBpm: Double
    public let floorBpm: Double
    public let runBlockS: Double?
    public let walkS: Double?
    public let reps: Int?
    public let runningTargetS: Double?

    public private(set) var phase: BlockPhase = .warmup
    public private(set) var phaseStartT: Double?
    public private(set) var rep = 0
    public private(set) var blocks: [Block] = []
    /// The last reading carried `lagS` ahead (see `ahead`), for the display and the voice.
    public private(set) var hrAhead: Double?

    private var lastFreshT: Double?
    private var peakHr: Double?
    private var recent: [(t: Double, hr: Double)] = []
    private var trace: [(s: Double, hr: Double)] = []
    private var stalls = 0
    private var endedBy: String?

    public init(ceilingBpm: Double, floorBpm: Double, runBlockS: Double? = nil, walkS: Double? = nil,
                reps: Int? = nil, runningTargetS: Double? = nil, config: HrBlockConfig = HrBlockConfig()) {
        self.ceilingBpm = ceilingBpm
        self.floorBpm = floorBpm
        self.runBlockS = runBlockS
        self.walkS = walkS
        self.reps = reps
        self.runningTargetS = runningTargetS
        self.cfg = config
    }

    public func elapsed(_ t: Double) -> Double { phaseStartT.map { t - $0 } ?? 0 }

    public func hrLive(_ t: Double) -> Bool {
        guard let last = lastFreshT else { return false }
        return t - last <= cfg.hrStaleS
    }

    /// Feed one second. `hr` is nil when there is no fresh reading.
    @discardableResult
    public func update(t: Double, hr rawHr: Double?) -> BlockTransition? {
        if phase == .done { return nil }
        if phaseStartT == nil { phaseStartT = t }
        let hr = (rawHr ?? 0) > 0 ? rawHr : nil
        var hrAheadNow: Double?
        if let hr {
            lastFreshT = t
            recent.append((t, hr))
            recent.removeAll { $0.t < t - cfg.trendS }
            hrAheadNow = ahead(hr)
            if peakHr == nil || hr > peakHr! { peakHr = hr }
            if phase == .walk || phase == .cooldown {
                if let start = traceStartT { trace.append((t - start, hr)) }
            }
        }
        if phase == .cooldown { return nil }

        let live = hrLive(t)
        let el = elapsed(t)

        switch phase {
        case .warmup:
            if el < cfg.warmupS { return nil }
            let atFloor = hr != nil && (hrAheadNow ?? hr!) <= floorBpm
            if !live || atFloor || el >= cfg.warmupS + cfg.walkExtraS {
                return to(.run, t, "warm-up done")
            }
            return nil

        case .run:
            if live {
                if let rb = runBlockS, el >= rb { return endRun(t, "full") }
                if let hr, hr >= ceilingBpm + cfg.hardOverBpm { return endRun(t, "well over the ceiling") }
                if el >= cfg.minRunS, hr != nil, let a = hrAheadNow, a >= ceilingBpm { return endRun(t, "ceiling") }
                if el >= cfg.maxRunS { return endRun(t, "long enough") }
                return nil
            }
            if let rb = runBlockS, el >= rb { return endRun(t, "time") }
            return nil

        case .walk:
            if live {
                if el >= cfg.minWalkS, let hr, let a = hrAheadNow, a <= floorBpm || levelledNearFloor(hr) {
                    stalls = 0
                    return to(.run, t, "recovered")
                }
                let cap = walkS.map { $0 + cfg.walkExtraS } ?? cfg.maxWalkS
                if el >= cap {
                    stalls += 1
                    if stalls >= 2 {
                        endedBy = "stall"
                        return to(.cooldown, t, "not recovering")
                    }
                    return to(.run, t, "going again")
                }
                return nil
            }
            if let w = walkS, el >= w { return to(.run, t, "time") }
            return nil

        case .cooldown, .done:
            return nil
        }
    }

    /// End the session wherever it is.
    public func finish(t: Double) {
        if phase == .done { return }
        if endedBy == nil { endedBy = "athlete" }
        close(t, reason: phase == .cooldown ? "cool-down" : "stopped")
        phase = .done
    }

    public func summary() -> HrBlockSummary {
        let runs = blocks.filter { $0.kind == .run }
        let walks = blocks.filter { $0.kind == .walk }
        return HrBlockSummary(
            runBlocks: runs.count,
            blocksPlanned: reps,
            blocksFull: runs.filter(\.full).count,
            blocksCut: runs.filter(\.cut).count,
            runningS: runs.reduce(0) { $0 + $1.durationS },
            runningTargetS: runningTargetS,
            longestRunBlockS: runs.map(\.durationS).max() ?? 0,
            walkS: walks.reduce(0) { $0 + $1.durationS },
            peakRunHr: runs.compactMap(\.peakHr).max(),
            ceilingBpm: ceilingBpm,
            floorBpm: floorBpm,
            endedBy: endedBy)
    }

    /// The reading carried `lagS` ahead along its recent trend (least squares, clamped).
    func ahead(_ hr: Double) -> Double {
        defer { hrAhead = hrAheadValue }
        hrAheadValue = hr
        guard cfg.lagS > 0, recent.count >= 2, let first = recent.first, let last = recent.last,
              last.t - first.t >= cfg.trendS / 2 else { return hr }
        let n = Double(recent.count)
        let mt = recent.reduce(0) { $0 + $1.t } / n
        let mh = recent.reduce(0) { $0 + $1.hr } / n
        var sxy = 0.0, sxx = 0.0
        for p in recent { sxy += (p.t - mt) * (p.hr - mh); sxx += (p.t - mt) * (p.t - mt) }
        let slope = sxx > 0 ? max(-cfg.maxTrendBpmS, min(cfg.maxTrendBpmS, sxy / sxx)) : 0
        hrAheadValue = (hr + slope * cfg.lagS).rounded()
        return hrAheadValue
    }
    private var hrAheadValue: Double = 0

    // MARK: - transitions

    private var traceStartT: Double?

    private func levelledNearFloor(_ hr: Double) -> Bool {
        guard hr <= floorBpm + cfg.plateauBpm, let first = trace.first, let last = trace.last,
              last.s - first.s >= cfg.plateauS else { return false }
        let window = trace.filter { $0.s >= last.s - cfg.plateauS }.map(\.hr)
        guard let lo = window.min(), let hi = window.max() else { return false }
        return hi - lo <= cfg.plateauRangeBpm
    }

    private func endRun(_ t: Double, _ reason: String) -> BlockTransition {
        let ran = blocks.filter { $0.kind == .run }.reduce(0) { $0 + $1.durationS } + elapsed(t)
        let enough = runningTargetS.map { ran >= $0 } ?? true
        if let reps, (rep >= reps && enough) || rep >= reps + cfg.extraBlocks {
            endedBy = "reps"
            return to(.cooldown, t, "blocks done", closeReason: reason)
        }
        return to(.walk, t, reason)
    }

    private func to(_ next: BlockPhase, _ t: Double, _ reason: String, closeReason: String? = nil) -> BlockTransition {
        let previous = phase
        close(t, reason: closeReason ?? reason)
        if previous == .run {
            trace = []
            traceStartT = t
        }
        phase = next
        phaseStartT = t
        peakHr = nil
        if next == .run { rep += 1 }
        return BlockTransition(phase: next, previous: previous, reason: reason, rep: rep)
    }

    private func close(_ t: Double, reason: String) {
        guard let start = phaseStartT, t > start else { return }
        blocks.append(Block(kind: phase, startT: start, endT: t, reason: reason, peakHr: peakHr))
    }
}
