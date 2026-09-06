// Run and walk decided by heart rate, not by a clock.
//
// Why this exists
// ---------------
// One session, recorded against Polar and read second by second:
//
//   * prescribed Z1/Z2 with a 155 bpm ceiling; peaked at **177**, which is 95% of his estimated
//     HRmax. The trace is clean -- no implausible beat-to-beat jumps, a smooth 46 bpm fall once he
//     eased -- so this is a real heart rate and not an optical sensor locking onto step cadence.
//   * 19% of the session was spent above that ceiling, and the mean pace while above it was
//     **16:59/mi** against a prescription of 12:04. He was not running too fast. He was running
//     SLOWER than asked and still over the line.
//   * heart rate ratcheted 137 -> 142 -> 149 -> 153 -> 160 -> 162 across the session while the pace
//     fell. Same pace at minute 8 and minute 19: 148 bpm and 177 bpm.
//
// Pace is an input the athlete controls. Heart rate is the output that decides what adapts. For a
// trained runner the two track each other closely enough that prescribing pace works; for this
// athlete they do not yet track at all, and building that relationship is what the training is FOR.
// So the plan was governing the one variable that was not controlling the physiology.
//
// The walk break turned out to be the larger fault. Of 1176 seconds spent walking, 384 were still
// above threshold -- more time above the ceiling walking than running. The plan prescribes a brisk
// 5.6 km/h walk on the reasoning that a stroll lets heart rate fall too far; at this athlete's
// fitness that walk is a second workout, heart rate never comes down, and every run block starts
// from a higher floor than the last. That is the ratchet. The one time he did walk slowly for two
// minutes his heart rate fell from 162 to 121.
//
// So both halves are governed here: run until the ceiling, walk until the floor, at whatever speed
// each of those takes.
//
// What it buys beyond not overcooking a session
// ---------------------------------------------
// 1. It is SIMPLER to obey. A pace target is a number to hold while tired; this is two words.
// 2. It auto-regulates. Heat, poor sleep, hills, the start of a cold: blocks shorten and walks
//    lengthen with no decision required and no honesty required about how you feel.
// 3. Every run->walk transition becomes a heart-rate recovery measurement. Six to ten a session,
//    three sessions a week. This athlete cannot collect overnight HRV -- no chest strap in bed, no
//    sleep tracking, and the engine's readiness module returns "unknown" forever without it -- but
//    HRR rises with fitness and falls with accumulated fatigue, and it comes free from equipment he
//    already owns.

/** Seconds without a fresh heart rate after which this controller stops trusting it. */
export const HR_STALE_S = 12;

export const HrBlockDefaults = {
  /// Never call a run block shorter than this even if heart rate is already at the ceiling.
  ///
  /// Heart rate lags effort by 20-30 s, so the first half-minute of a block reports the walk that
  /// preceded it. Without a floor on block length a session that starts with an elevated heart rate
  /// degenerates into run-two-seconds-walk-two-seconds, which is not a workout and is demoralising.
  minRunS: 30,
  /// And never longer, however good the heart rate looks. A block this long is no longer a run/walk
  /// session; the athlete has graduated and the ladder should say so rather than this silently
  /// turning into a continuous run.
  maxRunS: 900,
  /// A walk shorter than this has not recovered anything regardless of what the number says.
  minWalkS: 45,
  /// After this long walking, go again even if the floor was never reached. Standing in the cold
  /// waiting for a number is worse training than a slightly hot block, and `recovered: false` on the
  /// block records that it happened so the session can be judged honestly afterwards.
  maxWalkS: 210,
  /// Consecutive walk breaks that fail to reach the floor before this many seconds. Two in a row is
  /// the session telling you it is over.
  stallWalkS: 180,
  /// Walk at the start until heart rate settles, so the first block is not started mid-commute.
  warmupS: 180,
};

/** Phases this controller can be in. `warmup` is walking too. */
/// Named for this module rather than `Phase`, which is what it wants to be called: the built page
/// inlines every module into one scope, and `Phase` is a name the training plan will want too.
export const BlockPhase = { WARMUP: 'warmup', RUN: 'run', WALK: 'walk', DONE: 'done' };

/**
 * Decides when to run and when to walk, from heart rate.
 *
 * `ceilingBpm` is the aerobic ceiling -- the top of Z2, or better, the athlete's own measured first
 * ventilatory threshold (see threshold.js, which reads it off their sessions). `floorBpm` is where a
 * walk break has done its job.
 *
 * Falls back to the clock when heart rate is missing or stale, because an armband whose battery dies
 * mid-run must degrade to the session the athlete came out to do rather than to nothing. This has
 * happened to this athlete: one session lost heart rate halfway through, another had none at all.
 */
export class HrBlocks {
  constructor({ ceilingBpm, floorBpm, fallbackRunS, fallbackWalkS, reps = null, ...opts } = {}) {
    this.cfg = { ...HrBlockDefaults, ...opts };
    this.ceilingBpm = ceilingBpm;
    this.floorBpm = floorBpm;
    /// What to do when there is no heart rate: the prescribed clock session, unchanged.
    this.fallbackRunS = fallbackRunS;
    this.fallbackWalkS = fallbackWalkS;
    /// Optional cap on run blocks. Null means "until the athlete stops or stalls", which is what an
    /// HR-governed session naturally is -- the load is bounded by the ceiling, not by a rep count.
    this.reps = reps;

    this.phase = BlockPhase.WARMUP;
    this.phaseStartT = null;
    this.rep = 0;
    /// Completed blocks: {kind, startT, endT, peakHr, endHr, recovered, governedBy}.
    this.blocks = [];
    /// One entry per run->walk transition: {atT, peakHr, hr60, hrr60}. The autonomic series.
    this.recoveries = [];
    this.stalls = 0;
    this._peakHr = null;
    this._lastFreshT = null;
    this._pending = [];          // recoveries still waiting for their 60-second reading
  }

  /** True while heart rate is recent enough to govern with. */
  hrLive(tS) {
    return this._lastFreshT != null && tS - this._lastFreshT <= HR_STALE_S;
  }

  /** Seconds spent in the current phase. */
  elapsed(tS) { return this.phaseStartT == null ? 0 : tS - this.phaseStartT; }

  /**
   * Feed one second.
   *
   * Returns null when nothing changes, or `{phase, previous, reason, rep, block}` at a transition.
   * `reason` is the athlete-facing explanation and is deliberately short enough to speak.
   */
  update(tS, hrBpm, { hrFresh = true } = {}) {
    if (this.phase === BlockPhase.DONE) return null;
    if (this.phaseStartT == null) this.phaseStartT = tS;

    const hr = (hrFresh && hrBpm != null && hrBpm > 0) ? hrBpm : null;
    if (hr != null) this._lastFreshT = tS;
    if (hr != null && (this._peakHr == null || hr > this._peakHr)) this._peakHr = hr;
    this._resolveRecoveries(tS, hr);

    const live = this.hrLive(tS) && this.ceilingBpm != null && this.floorBpm != null;
    const el = this.elapsed(tS);

    if (this.phase === BlockPhase.WARMUP) {
      // Long enough to have settled, and either at the floor or out of patience. A warm-up that
      // waits forever for a floor the athlete cannot reach while walking is a session that never
      // starts, which is the same failure as a coach that never speaks.
      const ready = live ? (hr <= this.floorBpm || el >= this.cfg.warmupS)
                         : el >= Math.min(this.cfg.warmupS, this.fallbackWalkS ?? this.cfg.warmupS);
      if (el >= this.cfg.minWalkS && ready) return this._to(BlockPhase.RUN, tS, 'warm-up done', live);
      return null;
    }

    if (this.phase === BlockPhase.RUN) {
      if (live) {
        if (el >= this.cfg.minRunS && hr >= this.ceilingBpm) {
          return this._to(BlockPhase.WALK, tS, 'ceiling', true);
        }
        if (el >= this.cfg.maxRunS) return this._to(BlockPhase.WALK, tS, 'long enough', true);
        return null;
      }
      // No heart rate: the clock the athlete was prescribed.
      if (this.fallbackRunS && el >= this.fallbackRunS) {
        return this._to(BlockPhase.WALK, tS, 'time', false);
      }
      return null;
    }

    // Walking.
    if (live) {
      if (el >= this.cfg.minWalkS && hr <= this.floorBpm) {
        this.stalls = 0;
        return this._to(BlockPhase.RUN, tS, 'recovered', true);
      }
      if (el >= this.cfg.maxWalkS) {
        // Went again without recovering. Recorded, counted, and if it keeps happening the session
        // is over -- that is the auto-regulation, and it is the honest reading of a body that is no
        // longer clearing the load between blocks.
        this.stalls += 1;
        if (this.stalls >= 2) return this._to(BlockPhase.DONE, tS, 'not recovering', true);
        return this._to(BlockPhase.RUN, tS, 'going again', true);
      }
      return null;
    }
    if (this.fallbackWalkS && el >= this.fallbackWalkS) return this._to(BlockPhase.RUN, tS, 'time', false);
    return null;
  }

  /** End the session wherever it is, closing the open block. */
  finish(tS) {
    if (this.phase === BlockPhase.DONE) return;
    this._close(tS);
    this.phase = BlockPhase.DONE;
  }

  _to(next, tS, reason, governedByHr) {
    const previous = this.phase;
    const block = this._close(tS, governedByHr, reason);
    if (previous === BlockPhase.RUN) {
      // A run block ending is a heart-rate recovery test starting. The reading it needs is 60 s
      // away, so it is parked and resolved later rather than guessed at now.
      this._pending.push({ atT: tS, peakHr: block ? block.peakHr : null, dueT: tS + 60 });
    }
    this.phase = next;
    this.phaseStartT = tS;
    this._peakHr = null;
    if (next === BlockPhase.RUN) {
      this.rep += 1;
      if (this.reps != null && this.rep > this.reps) {
        this.phase = BlockPhase.DONE;
        return { phase: BlockPhase.DONE, previous, reason: 'session complete', rep: this.rep - 1, block };
      }
    }
    return { phase: next, previous, reason, rep: this.rep, block };
  }

  _close(tS, governedByHr = null, reason = null) {
    if (this.phaseStartT == null || tS <= this.phaseStartT) return null;
    const block = {
      kind: this.phase, startT: this.phaseStartT, endT: tS, durationS: tS - this.phaseStartT,
      peakHr: this._peakHr,
      // A walk that ended because the clock ran out did not recover; one that reached the floor did.
      recovered: this.phase === BlockPhase.WALK ? reason === 'recovered' : null,
      governedBy: governedByHr == null ? null : (governedByHr ? 'hr' : 'clock'),
    };
    this.blocks.push(block);
    return block;
  }

  _resolveRecoveries(tS, hr) {
    if (hr == null) return;
    for (const p of this._pending) {
      if (p.done || tS < p.dueT) continue;
      p.done = true;
      if (p.peakHr != null) {
        this.recoveries.push({ atT: p.atT, peakHr: p.peakHr, hr60: hr, hrr60: p.peakHr - hr });
      }
    }
    this._pending = this._pending.filter(p => !p.done);
  }

  /** What the session amounted to, for the progression decision and for the athlete. */
  summary() {
    const runs = this.blocks.filter(b => b.kind === BlockPhase.RUN);
    const walks = this.blocks.filter(b => b.kind === BlockPhase.WALK);
    const hrr = this.recoveries.map(r => r.hrr60);
    return {
      runBlocks: runs.length,
      runningS: runs.reduce((a, b) => a + b.durationS, 0),
      longestRunBlockS: runs.reduce((a, b) => Math.max(a, b.durationS), 0),
      walkS: walks.reduce((a, b) => a + b.durationS, 0),
      unrecoveredWalks: walks.filter(b => b.recovered === false).length,
      // The autonomic number. Median rather than mean: one bad optical reading in a walk break
      // should not move a session-level statistic that gets trended across weeks.
      hrr60Median: hrr.length ? hrr.slice().sort((a, b) => a - b)[Math.floor(hrr.length / 2)] : null,
      recoveries: this.recoveries.length,
      // Whether this session is evidence at all. A session run on the clock because the armband was
      // flat says nothing about fitness, and must not be allowed to advance or retreat the ladder.
      governedBy: this.blocks.some(b => b.governedBy === 'hr') ? 'hr' : 'clock',
      stalls: this.stalls,
    };
  }
}
