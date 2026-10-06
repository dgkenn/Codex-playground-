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
// So both halves are governed here: a walk ends when heart rate is back at the floor, at whatever
// speed that takes, and a run block is ended by the ceiling.
//
// ...but NOT ONLY by the ceiling, and the first version of this got that wrong. It ended a run block
// at the ceiling and at nothing else, so with heart rate sitting at 142 -- comfortably under it -- it
// called "run" at 3:00 and did not call a walk until 17:00. That is a fourteen-minute continuous run
// for someone whose longest recorded run is about two minutes. Heart rate protects the cardiovascular
// system and says nothing about the shins: how long a block runs is the dose for tendon and bone, it
// is what the run/walk ladder exists to ration, and it is the load that matters most in the first
// twenty weeks of running. Two different things limit a block, neither can stand in for the other,
// and so a block ends at whichever comes first:
//
//     the rung's block length   -- the tissue limit  (fixed by the plan, `runBlockS`)
//     the heart-rate ceiling    -- the cardiac limit (measured, `ceilingBpm`)
//
// Either can SHORTEN a block. Neither can lengthen one. The session is the rung's block count and no
// more, so its length is bounded by construction and a block cut short by the ceiling is not made up
// for later: carrying missed volume forward is how a hard week becomes a hard month.
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
  /// ...unless heart rate is not merely at the ceiling but far past it.
  ///
  /// The floor above exists so lag does not produce a stutter, and it is right for a block that
  /// drifts up to the ceiling. It is wrong for one that overshoots: at fifteen beats over, the
  /// question is no longer "has heart rate settled" but "why is it climbing this fast", and thirty
  /// seconds of grace at that rate is another ten beats. This athlete's recorded session reached 177
  /// against a 155 ceiling -- 22 over -- and the whole point of governance is that such a number
  /// ends the block rather than being waited out.
  hardOverBpm: 15,
  /// And never longer, however good the heart rate looks -- a bound against a session that silently
  /// becomes a continuous run, not a training decision.
  ///
  /// Was 900, and 900 was in direct conflict with the plan it serves: FOUNDATION's exit gate is
  /// "run 30 minutes continuously, comfortably, in Z2", and a cap that forces a walk at fifteen
  /// minutes means an athlete governed by heart rate could never demonstrate the one thing the gate
  /// asks for, however easy it felt. The top rung of the run-walk ladder is 30 min x 1 for exactly
  /// that reason. So the cap sits above the ladder's own top rung with room to spare: at forty
  /// minutes it still catches a runaway, and it no longer blocks the graduation it was written to
  /// notice. `summary().longestRunBlockS` is what actually reports that graduation.
  maxRunS: 2400,
  /// A walk shorter than this has not recovered anything regardless of what the number says.
  minWalkS: 45,
  /// How long past the prescribed walk a break may be extended while heart rate is still above the
  /// floor. The prescription (`walkS`) is what the walk is EXPECTED to take, not a minimum: rest ends
  /// when heart rate has recovered, so a quick recovery shortens it and a slow one lengthens it, up
  /// to this much more. At the usual two-minute walk this gives 3.5 minutes, which is where the cap
  /// sat before it was tied to the plan.
  walkExtraS: 90,
  /// The cap on a walk when the plan gave no walk length to measure against.
  ///
  /// After this long walking, go again even if the floor was never reached. Standing in the cold
  /// waiting for a number is worse training than a slightly hot block, and `recovered: false` on the
  /// block records that it happened so the session can be judged honestly afterwards.
  maxWalkS: 210,
  /// Consecutive walk breaks that fail to reach the floor before this many seconds. Two in a row is
  /// the session telling you it is over.
  stallWalkS: 180,
  /// The walk warm-up, which the plan states as five minutes and which is a minimum, not a target.
  ///
  /// It used to be a ceiling on a wait for the floor: "walk until heart rate is at the floor, or
  /// three minutes". At the start of a session heart rate is already under any floor, so on
  /// 6 October the warm-up ended at 45 s and the first block took heart rate from 103 to 152 in 85
  /// seconds -- a cold start, the steepest rise of the session. Five minutes of walking first, then
  /// the floor check (bounded by walkExtraS) for the case where getting there raised it.
  warmupS: 300,
  /// A block the ceiling ends on a climb at least this steep (mean grade over its last minute) is a
  /// HILL block: the heart rate did its job, but the block says nothing about whether the rung is
  /// comfortable on the flat, so the judge does not count it either way. See terrain.js for why
  /// nothing below 4% is trusted to be a hill at all.
  hillGrade: 0.04,
  /// Walk descents at least this steep, during the bone window. Heart rate falls on a downhill, so
  /// neither rail would ever end a block there, while the impact load on the shin rises with the
  /// gradient -- the one case where the heart-rate machinery is blind to exactly the tissue the first
  /// twenty weeks are protecting. Null turns it off (after the bone window).
  steepDownGrade: -0.07,
};

/** Phases this controller can be in. `warmup` is walking too. */
/// Named for this module rather than `Phase`, which is what it wants to be called: the built page
/// inlines every module into one scope, and `Phase` is a name the training plan will want too.
///
/// `cooldown` exists because two unrecovered walks used to mean `done`, and that was wrong: for this
/// athlete walking IS training. A body that stops clearing the load between run blocks is telling you
/// the RUNNING is over, not that the recording should stop -- it should keep walking, and keep
/// recording, until the athlete ends the session. `done` is reserved for the two real endings: the
/// plan's own rep count being satisfied, or the athlete stopping the app.
export const BlockPhase = { WARMUP: 'warmup', RUN: 'run', WALK: 'walk', COOLDOWN: 'cooldown', DONE: 'done' };

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
  constructor({ ceilingBpm, floorBpm, runBlockS = null, walkS = null, reps = null,
                fallbackRunS = null, fallbackWalkS = null, ...opts } = {}) {
    this.cfg = { ...HrBlockDefaults, ...opts };
    this.ceilingBpm = ceilingBpm;
    this.floorBpm = floorBpm;
    /// How long a run block is allowed to be: the rung's own length. This is the TISSUE limit, and it
    /// is also the clock the session falls back to with no heart rate -- the same number, because
    /// "the session the athlete came out to do" and "the longest a block may run" are the same
    /// prescription. Null means no rung cap, so only the heart-rate ceiling (and `maxRunS`) ends one.
    this.runBlockS = runBlockS ?? fallbackRunS;
    /// How long a walk is EXPECTED to take. Not a minimum -- rest ends at recovery -- but it fixes the
    /// cap (see walkExtraS) and is the clock walk when there is no heart rate.
    this.walkS = walkS ?? fallbackWalkS;
    this.fallbackRunS = this.runBlockS;
    this.fallbackWalkS = this.walkS;
    /// The number of run blocks in the session. The session ends when the last one does, so its
    /// length is bounded by construction: reps x (block + walk + extension), and no more. Null means
    /// no block count, which suits only a session the athlete ends themselves.
    ///
    /// There used to be a `targetRunningS` here instead -- "keep going until N minutes have been run
    /// under the ceiling" -- and it is what let a session run 14 minutes straight. A target is a
    /// ratchet that can only be met by running more; a block count cannot be met by running longer.
    this.reps = reps;

    this.phase = BlockPhase.WARMUP;
    this.phaseStartT = null;
    this.rep = 0;
    /// Completed blocks: {kind, startT, endT, peakHr, endHr, recovered, governedBy}.
    this.blocks = [];
    /// One entry per run->walk (or run->cool-down) transition: {atT, peakHr, toFloorS, hrr60}.
    this.recoveries = [];
    this._trace = null;          // [secondsIntoWalk, hr] for the walk in progress
    this._runGrades = [];        // [t, grade] for the run block in progress
    this._heldS = 0;             // seconds of the current walk held on a steep descent
    this.stalls = 0;
    this._peakHr = null;
    this._lastFreshT = null;
    this._runUnderCeilingS = 0;  // seconds inside run blocks where HR was at or below the ceiling
    this._runOverCeilingS = 0;   // seconds inside run blocks where HR was above it
    /// Which of the three real endings this session had -- 'reps' (the plan's own block count was
    /// reached), 'stall' (the body stopped clearing the load) or 'athlete' (the session was stopped).
    /// Set once, at the moment it becomes known, so `summary()` can tell "the plan's own end was
    /// reached" apart from "the body stopped clearing the load" apart from "the athlete ended it" --
    /// facts that all look identical from the block list alone.
    this._endedBy = null;
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
  update(tS, hrBpm, { hrFresh = true, grade = null } = {}) {
    if (this.phase === BlockPhase.DONE) return null;
    if (this.phaseStartT == null) this.phaseStartT = tS;

    const hr = (hrFresh && hrBpm != null && hrBpm > 0) ? hrBpm : null;
    if (hr != null) this._lastFreshT = tS;
    if (hr != null && (this._peakHr == null || hr > this._peakHr)) this._peakHr = hr;
    if (this._trace && hr != null) this._trace.push([tS - this._trace.startT, hr]);
    if (this.phase === BlockPhase.RUN && grade != null) this._runGrades.push([tS, grade]);
    const steepDown = this.cfg.steepDownGrade != null && grade != null && grade <= this.cfg.steepDownGrade;

    // What the judge needs: not just how much running happened, but how much of it was actually
    // under the ceiling it was governed by. A block that ends AT the ceiling can still have spent
    // most of its seconds comfortably below it, or almost none -- the two sessions look identical in
    // `runningS` and are not identical at all.
    if (this.phase === BlockPhase.RUN && hr != null && this.ceilingBpm != null) {
      if (hr <= this.ceilingBpm) this._runUnderCeilingS += 1;
      else this._runOverCeilingS += 1;
    }

    if (this.phase === BlockPhase.COOLDOWN) {
      // Walking is training for this athlete, so a cool-down keeps recording -- it just never calls
      // another run block. Pending recoveries (the walk-to-run transition that led here) still
      // resolve above, so the session's last HRR60 reading is not lost.
      return null;
    }

    const live = this.hrLive(tS) && this.ceilingBpm != null && this.floorBpm != null;
    const el = this.elapsed(tS);

    if (this.phase === BlockPhase.WARMUP) {
      // Long enough to have settled, and either at the floor or out of patience. A warm-up that
      // waits forever for a floor the athlete cannot reach while walking is a session that never
      // starts, which is the same failure as a coach that never speaks.
      if (el < this.cfg.warmupS || steepDown) return null;
      const ready = !live || hr <= this.floorBpm || el >= this.cfg.warmupS + this.cfg.walkExtraS;
      return ready ? this._to(BlockPhase.RUN, tS, 'warm-up done', live) : null;
    }

    if (this.phase === BlockPhase.RUN) {
      // A steep descent ends the block whatever the heart rate says -- it will be saying "fine".
      // Not counted as a cut by the ceiling, and not counted against the rung (see hillGrade).
      if (steepDown) return this._endRun(tS, 'steep downhill', live);
      if (live) {
        // The rung's own length first: a block that has run its full length is done however the
        // heart rate looks, and it counts as FULL even if it touches the ceiling on the last second --
        // the dose the tissue was meant to get was delivered. This is the limit the first version
        // lacked entirely.
        if (this.runBlockS != null && el >= this.runBlockS) {
          return this._endRun(tS, 'full', true);
        }
        // Far over the ceiling ends the block immediately; at or just over it waits out minRunS so
        // heart-rate lag cannot produce a stutter. See hardOverBpm.
        if (hr >= this.ceilingBpm + this.cfg.hardOverBpm) {
          return this._endRun(tS, 'well over the ceiling', true);
        }
        if (el >= this.cfg.minRunS && hr >= this.ceilingBpm) {
          return this._endRun(tS, 'ceiling', true);
        }
        if (el >= this.cfg.maxRunS) return this._endRun(tS, 'long enough', true);
        return null;
      }
      // No heart rate: the clock the athlete was prescribed.
      if (this.runBlockS && el >= this.runBlockS) return this._endRun(tS, 'time', false);
      return null;
    }

    // Walking. Held while the descent is still steep -- the next block does not start halfway down
    // the hill that ended the last one -- and the held seconds do not count toward the walk cap, so a
    // long descent cannot turn into an "unrecovered" walk and a stall.
    if (steepDown) { this._heldS += 1; return null; }
    const walkEl = el - this._heldS;
    if (live) {
      if (el >= this.cfg.minWalkS && hr <= this.floorBpm) {
        this.stalls = 0;
        return this._to(BlockPhase.RUN, tS, 'recovered', true);
      }
      // The cap follows the plan's own walk: expected length plus a bounded extension, not a fixed
      // number that happens to agree with a two-minute walk.
      const walkCap = this.walkS != null ? this.walkS + this.cfg.walkExtraS : this.cfg.maxWalkS;
      if (walkEl >= walkCap) {
        // Went again without recovering. Recorded, counted, and if it keeps happening the session
        // is over -- that is the auto-regulation, and it is the honest reading of a body that is no
        // longer clearing the load between blocks.
        this.stalls += 1;
        if (this.stalls >= 2) {
          // Not the end of the recording -- the end of the RUNNING. Walking is training for this
          // athlete, so what a clock-governed session would call "done" here becomes a cool-down:
          // still walking, still recording, no more run blocks called.
          this._endedBy = 'stall';
          return this._to(BlockPhase.COOLDOWN, tS, 'not recovering', true);
        }
        return this._to(BlockPhase.RUN, tS, 'going again', true);
      }
      return null;
    }
    if (this.fallbackWalkS && walkEl >= this.fallbackWalkS) return this._to(BlockPhase.RUN, tS, 'time', false);
    return null;
  }

  /** End the session wherever it is, closing the open block. */
  finish(tS) {
    if (this.phase === BlockPhase.DONE) return;
    // If nothing set this already (a stall, or the plan's own rep count), then this call is the
    // reason: the athlete ended it. Closing the still-open block reads `this.phase`, which is
    // `cooldown` when a stall got here first -- so a session that stalled and was then stopped is
    // still recorded as `kind: 'cooldown'`, correctly, with no special-casing needed here.
    if (this._endedBy == null) this._endedBy = 'athlete';
    this._close(tS);
    this._closeRecovery();
    this.phase = BlockPhase.DONE;
  }

  /**
   * A run block is over. If it was the last one the plan asked for, the running is finished and the
   * session becomes a cool-down; otherwise a walk begins.
   *
   * The block's own reason ('full', 'ceiling', ...) is recorded either way, because whether the LAST
   * block reached full length is exactly what the judge needs to know.
   */
  _endRun(tS, reason, governedByHr) {
    if (this.reps != null && this.rep >= this.reps) {
      this._endedBy = 'reps';
      return this._to(BlockPhase.COOLDOWN, tS, 'blocks done', governedByHr, reason);
    }
    return this._to(BlockPhase.WALK, tS, reason, governedByHr);
  }

  _to(next, tS, reason, governedByHr, closeReason = reason) {
    const previous = this.phase;
    const block = this._close(tS, governedByHr, closeReason);
    // A walk ending closes the recovery it was measuring; a run ending starts the next one.
    if (previous === BlockPhase.WALK) this._closeRecovery();
    if (previous === BlockPhase.RUN) {
      this._trace = [];
      this._trace.startT = tS;
    }
    this.phase = next;
    this.phaseStartT = tS;
    this._peakHr = null;
    this._runGrades = [];
    this._heldS = 0;
    if (next === BlockPhase.RUN) this.rep += 1;
    return { phase: next, previous, reason, rep: this.rep, block };
  }

  _close(tS, governedByHr = null, reason = null) {
    if (this.phaseStartT == null || tS <= this.phaseStartT) return null;
    const block = {
      kind: this.phase, startT: this.phaseStartT, endT: tS, durationS: tS - this.phaseStartT,
      peakHr: this._peakHr,
      // Why it ended, kept on the block: 'full' / 'ceiling' / 'well over the ceiling' for a run,
      // 'recovered' / 'going again' for a walk. The judge reads these, not the durations.
      reason,
      // A run block that reached the rung's full length: the unit progression is counted in.
      full: this.phase === BlockPhase.RUN ? reason === 'full' : null,
      // Mean grade over the block's last minute, from the terrain model; null with no terrain. A
      // block the ceiling ended on a climb is a hill block, which the judge sets aside.
      climb: this.phase === BlockPhase.RUN ? this._climb(tS) : null,
      // A walk that ended because the clock ran out did not recover; one that reached the floor did.
      recovered: this.phase === BlockPhase.WALK ? reason === 'recovered' : null,
      governedBy: governedByHr == null ? null : (governedByHr ? 'hr' : 'clock'),
    };
    this.blocks.push(block);
    return block;
  }

  _climb(tS) {
    const last = this._runGrades.filter(([t]) => t > tS - 60).map(([, g]) => g);
    return last.length ? last.reduce((a, b) => a + b, 0) / last.length : null;
  }

  /**
   * Read the recovery off the walk that just ended (or the cool-down, at the end).
   *
   * Two numbers, because the first version's one was wrong. It took the run block's peak and the
   * heart rate 60 s after the block ENDED, and read it whatever was happening by then. But heart rate
   * keeps rising for 15-30 s after the legs stop (on 6 October: +5 to +10 bpm, peaking 16-28 s into
   * the walk), and half the walks were over inside 60 s, so the "60 s later" reading usually came
   * from the next run block. Median HRR60: 8 bpm, which measured nothing.
   *
   *   toFloorS -- seconds from the end of the block to heart rate at the floor. Every block ends at
   *               the same ceiling, so this is the same test every time: 150 down to 133. It is
   *               available on nearly every walk, and it is the number that gets shorter with fitness
   *               and longer with fatigue.
   *   hrr60    -- the classical number, done properly: from the walk's own peak to 60 s after that
   *               peak, and only when the walk lasted that long. Often null under this protocol, which
   *               is the honest answer.
   */
  _closeRecovery() {
    const tr = this._trace;
    this._trace = null;
    if (!tr || !tr.length) return;
    const early = tr.filter(([s]) => s <= 60);
    const peak = early.reduce((m, x) => (m == null || x[1] > m[1] ? x : m), null);
    const floorAt = tr.find(([, h]) => h <= this.floorBpm);
    let hrr60 = null;
    if (peak) {
      const later = tr.find(([s]) => s >= peak[0] + 60);
      if (later) hrr60 = peak[1] - later[1];
    }
    this.recoveries.push({ atT: tr.startT, peakHr: peak ? peak[1] : null,
                           toFloorS: floorAt ? floorAt[0] : null, hrr60 });
  }

  /** What the session amounted to, for the progression decision and for the athlete. */
  summary() {
    const runs = this.blocks.filter(b => b.kind === BlockPhase.RUN);
    const walks = this.blocks.filter(b => b.kind === BlockPhase.WALK);
    const cooldowns = this.blocks.filter(b => b.kind === BlockPhase.COOLDOWN);
    const isCut = b => b.reason === 'ceiling' || b.reason === 'well over the ceiling';
    const isHill = b => isCut(b) && b.climb != null && b.climb >= this.cfg.hillGrade;
    const med = xs => (xs.length ? xs.slice().sort((a, b) => a - b)[Math.floor(xs.length / 2)] : null);
    const hrr = this.recoveries.map(r => r.hrr60).filter(v => v != null);
    const toFloor = this.recoveries.map(r => r.toFloorS).filter(v => v != null);
    return {
      runBlocks: runs.length,
      // The progression unit: blocks that ran their full length, out of the blocks planned. A block
      // cut short by the ceiling is the heart saying the load was enough for today; it is neither
      // counted as a failure nor made up for later.
      blocksPlanned: this.reps,
      blocksFull: runs.filter(b => b.full).length,
      blocksCut: runs.filter(b => b.reason === 'ceiling' || b.reason === 'well over the ceiling').length,
      runBlockTargetS: this.runBlockS,
      // How long running took to reach the ceiling, median over the blocks the ceiling cut. While the
      // heart rate rather than the rung is what ends the blocks this IS the fitness number: the same
      // effort, from the same floor to the same ceiling, taking longer is the aerobic base growing.
      // Hill blocks are left out: a block that met the ceiling on a climb measures the climb.
      toCeilingMedianS: med(runs.filter(b => isCut(b) && !isHill(b)).map(b => b.durationS)),
      // Blocks the terrain decided rather than the athlete: cut by the ceiling on a climb, or ended at
      // the top of a steep descent. The judge sets both aside.
      blocksHill: runs.filter(isHill).length,
      blocksSteepDown: runs.filter(b => b.reason === 'steep downhill').length,
      runningS: runs.reduce((a, b) => a + b.durationS, 0),
      longestRunBlockS: runs.reduce((a, b) => Math.max(a, b.durationS), 0),
      walkS: walks.reduce((a, b) => a + b.durationS, 0),
      cooldownS: cooldowns.reduce((a, b) => a + b.durationS, 0),
      unrecoveredWalks: walks.filter(b => b.recovered === false).length,
      // The autonomic number. Median rather than mean: one bad optical reading in a walk break
      // should not move a session-level statistic that gets trended across weeks.
      hrr60Median: med(hrr),
      // Seconds from the ceiling back down to the floor, median over the session's walks. The
      // recovery number the judge trends -- see _closeRecovery.
      toFloorMedianS: med(toFloor),
      recoveries: this.recoveries.length,
      // Whether this session is evidence at all. A session run on the clock because the armband was
      // flat says nothing about fitness, and must not be allowed to advance or retreat the ladder.
      governedBy: this.blocks.some(b => b.governedBy === 'hr') ? 'hr' : 'clock',
      stalls: this.stalls,
      // What the judge needs to tell "the body ended this" from "the plan's own end" from "the
      // athlete stopped" -- three different verdicts, identical block lists.
      endedBy: this._endedBy,
      // Seconds actually spent under governance inside run blocks, split by which side of the
      // ceiling they were on. `runningS` alone cannot tell a block that grazed the ceiling once from
      // one that spent half its length over it.
      runningUnderCeilingS: this._runUnderCeilingS,
      runningOverCeilingS: this._runOverCeilingS,
    };
  }
}
