// Run statistics, including a parity check against the Python the definitions come from.
//
// The risk with a statistics module is not that it crashes — it is that it quietly computes
// something slightly different from the engine and then both numbers get shown to the same person
// under the same name. So efficiency factor and decoupling are checked against
// `marathon_engine.physiology` by execution, not by reading.
//
// The rest is about the failure modes that make a statistic a lie: a distance interpolated across a
// dropout, a decoupling figure computed over a run too short to have any, a recovery heart rate
// invented from a recording that stopped.

import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { runStats, efficiencyFactor, decoupling, trimp, splits, longestRunBlock,
         progress, METRES_PER_MILE, JOG_MS,
         jogThreshold, GAIT_TRANSITION_MS } from '../run-stats.js';

const here = dirname(fileURLToPath(import.meta.url));
const ENGINE = join(here, '..', '..', 'engine');

/** A run at a constant speed and heart rate, with optional drift. */
function steady(n, { speed = 2.8, hr = 140, hrDrift = 0, from = 0 } = {}) {
  return Array.from({ length: n }, (_, i) => ({
    t_s: from + i,
    speed_m_s: speed,
    hr_bpm: Math.round(hr + hrDrift * (i / Math.max(1, n - 1))),
    grade: 0,
  }));
}

// --- parity with the engine ----------------------------------------------------------------------

{
  const cases = [[2.8, 140], [3.5, 165], [1.9, 118], [4.4, 178]];
  const py = execFileSync('python3', ['-c', `
import sys, json
sys.path.insert(0, ${JSON.stringify(ENGINE)})
from marathon_engine.physiology import efficiency_factor, decoupling
cases = json.loads(sys.argv[1])
print(json.dumps({
  "ef": [efficiency_factor(s, h) for s, h in cases],
  "dec": decoupling([(2.8, 140.0)] * 60, [(2.8, 148.0)] * 60),
}))
`, JSON.stringify(cases)], { encoding: 'utf8' });
  const want = JSON.parse(py);

  cases.forEach(([s, h], i) => {
    const got = efficiencyFactor(s, h);
    assert.ok(Math.abs(got - want.ef[i]) < 1e-9,
      `efficiency factor disagrees with the engine at ${s} m/s, ${h} bpm: ${got} vs ${want.ef[i]}`);
  });
  const gotDec = decoupling(Array(60).fill([2.8, 140]), Array(60).fill([2.8, 148]));
  assert.ok(Math.abs(gotDec - want.dec) < 1e-9,
    `decoupling disagrees with the engine: ${gotDec} vs ${want.dec}`);
  console.log(`  ok  efficiency factor and decoupling match the engine exactly (${cases.length} cases)`);
}

// --- the numbers that answer "am I getting fitter" ------------------------------------------------

{
  // The same pace at a lower heart rate must read as an improvement in both directions: efficiency
  // factor up, beats per mile down. If those two ever disagree, one of them is wrong.
  const before = runStats(steady(1200, { speed: 2.8, hr: 150 }), { unit: 'mi' });
  const after = runStats(steady(1200, { speed: 2.8, hr: 140 }), { unit: 'mi' });
  assert.ok(after.efficiencyFactor > before.efficiencyFactor,
    'a lower heart rate at the same pace must raise EF');
  assert.ok(after.beatsPerUnit < before.beatsPerUnit,
    'and must lower the beats it cost per mile');
  // 2.8 m/s at 140 bpm: 10.08 km/h, so 140/10.08 = 13.9 beats per km, 22.4 per mile.
  assert.ok(Math.abs(after.beatsPerUnit - 22.4) < 0.2, `beats per mile ${after.beatsPerUnit}`);
  console.log(`  ok  fitness moves EF up and beats-per-mile down together `
            + `(${before.beatsPerUnit.toFixed(1)} -> ${after.beatsPerUnit.toFixed(1)} beats/mi)`);
}

{
  // Decoupling: heart rate drifting up at a fixed pace is the signal. It must be positive, and it
  // must not be computed at all on a run too short for drift to mean anything.
  const long = runStats(steady(2400, { speed: 2.8, hr: 140, hrDrift: 14 }), {});
  assert.ok(long.decouplingPct > 4 && long.decouplingPct < 12,
    `drift of 14 bpm over 40 min should read a few percent, got ${long.decouplingPct}`);

  const flat = runStats(steady(2400, { speed: 2.8, hr: 140 }), {});
  assert.ok(Math.abs(flat.decouplingPct) < 0.5, `no drift must read ~0, got ${flat.decouplingPct}`);

  const short = runStats(steady(600, { speed: 2.8, hr: 140, hrDrift: 14 }), {});
  assert.equal(short.decouplingPct, null,
    'ten minutes is too short for decoupling to mean anything and must report nothing');
  console.log(`  ok  decoupling reports drift, reports zero, and refuses short runs `
            + `(${long.decouplingPct.toFixed(1)}%)`);
}

{
  // The compliance number. An athlete who reaches 180 bpm in four minutes does not need a faster
  // plan; he needs the easy runs to be easy, and this is the only figure that says whether they
  // were.
  const zones = [{ low: 114, high: 134 }, { low: 134, high: 151 }, { low: 151, high: 162 },
                 { low: 162, high: 174 }, { low: 174, high: 194 }];
  const half = [...steady(600, { hr: 145 }), ...steady(600, { hr: 168, from: 600 })];
  const st = runStats(half, { zones });
  assert.ok(Math.abs(st.pctAtOrBelowEasy - 50) < 2, `half the run was easy, got ${st.pctAtOrBelowEasy}`);
  assert.equal(st.easyCeilingBpm, 151);
  assert.equal(st.timeAboveEasyS, 600);
  assert.equal(st.zoneSecs[1], 600, 'ten minutes in Z2');
  assert.equal(st.zoneSecs[3], 600, 'and ten in Z4');
  console.log('  ok  time in zone and the easy-ceiling compliance figure are computed from the athlete\'s own zones');
}

{
  // Capacity, measured. This is what the run-walk ladder is entered on, so a self-reported number
  // would quietly set the whole plan's starting point.
  const walk = steady(120, { speed: 1.4, hr: 100 });
  const run = steady(280, { speed: 2.8, hr: 150, from: 120 });
  const walk2 = steady(120, { speed: 1.4, hr: 120, from: 400 });
  const run2 = steady(100, { speed: 2.8, hr: 155, from: 520 });
  const st = runStats([...walk, ...run, ...walk2, ...run2], {});
  assert.ok(Math.abs(st.longestRunBlockS - 280) <= 2,
    `the longest block was 280 s, got ${st.longestRunBlockS}`);
  assert.ok(st.runningS >= 375 && st.runningS <= 385, `running seconds ${st.runningS}`);
  console.log(`  ok  the longest continuous block is measured, not asked for (${st.longestRunBlockS}s)`);
}

{
  // A gap in the recording must be a gap in the distance. Interpolating across it invents metres
  // that were never run, which is the same class of fault as a heart rate held over a dropout.
  const before = steady(300, { speed: 3.0 });
  const after = steady(300, { speed: 3.0, from: 900 });   // ten minutes missing
  const st = runStats([...before, ...after], {});
  assert.ok(st.distanceM < 1900,
    `600 s of running at 3 m/s is ~1800 m; ${st.distanceM} m means the gap was filled in`);
  assert.ok(st.distanceM > 1700, `and it must not lose the running that did happen: ${st.distanceM}`);
  console.log(`  ok  a dropout leaves a hole in the distance rather than being interpolated (${st.distanceM} m)`);
}

{
  // Recovery heart rate is only real if the recording kept going after stopping.
  const run = steady(600, { speed: 2.8, hr: 160 });
  const stopped = Array.from({ length: 90 }, (_, i) => ({
    t_s: 600 + i, speed_m_s: 0, hr_bpm: Math.round(160 - i * 0.45), grade: 0,
  }));
  const st = runStats([...run, ...stopped], {});
  assert.ok(st.hrr60 >= 22 && st.hrr60 <= 32, `HRR60 should be ~27 bpm, got ${st.hrr60}`);

  const noTail = runStats(run, {});
  assert.equal(noTail.hrr60, null, 'a recording that stopped at the run must not invent a recovery');
  console.log(`  ok  recovery heart rate is measured when it exists and absent when it does not (${st.hrr60} bpm)`);
}

{
  // Load. Ten minutes hard must cost far more than ten minutes easy, which is the entire reason for
  // not using duration as a proxy.
  const easy = trimp(10, 130, 55, 187);
  const hard = trimp(10, 175, 55, 187);
  assert.ok(hard > easy * 2.5, `hard ${hard.toFixed(1)} vs easy ${easy.toFixed(1)} is not exponential`);
  assert.equal(trimp(10, 50, 55, 187), 0, 'below resting costs nothing rather than going negative');
  assert.equal(trimp(10, 150, 187, 187), null, 'an impossible reserve reports nothing');
  console.log(`  ok  training load weights intensity exponentially (${easy.toFixed(1)} vs ${hard.toFixed(1)})`);
}

// --- splits and pacing ---------------------------------------------------------------------------

{
  const st = splits(steady(1800, { speed: 2.8 }), 1000);
  assert.ok(st.length >= 5, `${st.length} kilometre splits from 5 km`);
  for (const s of st) {
    assert.ok(Math.abs(s.paceSecKm - 1000 / 2.8) < 3,
      `a constant 2.8 m/s must give constant splits, got ${s.paceSecKm}`);
  }
  console.log(`  ok  splits fall where the distance says (${st.length} of them, even)`);
}

{
  // Pacing evenness: the habit the tones exist to break.
  const even = runStats(steady(600, { speed: 2.8 }), {});
  const ragged = runStats(Array.from({ length: 600 }, (_, i) => ({
    t_s: i, speed_m_s: i % 60 < 30 ? 3.4 : 2.2, hr_bpm: 150, grade: 0,
  })), {});
  assert.ok(even.paceCv < 0.01, `a constant pace must read as even, got ${even.paceCv}`);
  assert.ok(ragged.paceCv > 0.1, `a surging run must read as ragged, got ${ragged.paceCv}`);
  console.log(`  ok  pacing evenness separates a held pace from a chased one `
            + `(${(even.paceCv * 100).toFixed(1)}% vs ${(ragged.paceCv * 100).toFixed(0)}%)`);
}

// --- degrading honestly --------------------------------------------------------------------------

{
  // No heart rate at all: everything that needs it must be absent rather than zero. A zero here
  // would plot as a data point and read as a catastrophic result.
  const gpsOnly = runStats(steady(1800, { speed: 2.8 }).map(s => ({ ...s, hr_bpm: null })), {});
  for (const k of ['avgHr', 'efficiencyFactor', 'beatsPerUnit', 'decouplingPct', 'hrr60']) {
    assert.equal(gpsOnly[k], null, `${k} must be absent without heart rate, not zero`);
  }
  assert.ok(gpsOnly.distanceM > 4900, 'but the distance still counts');
  assert.ok(gpsOnly.longestRunBlockS > 1700, 'and so does the continuous block');
  assert.equal(gpsOnly.hrCoveragePct, 0);
  console.log('  ok  without heart rate the HR statistics are absent, not zero');
}

{
  assert.equal(runStats([], {}), null);
  assert.equal(runStats(null, {}), null);
  const one = runStats([{ t_s: 0, speed_m_s: null, hr_bpm: null, grade: null }], {});
  assert.ok(one, 'a single useless sample must still produce a report rather than throwing');
  assert.equal(one.distanceM, 0);
  console.log('  ok  an empty or useless recording reports nothing rather than throwing');
}

// --- progress across sessions ---------------------------------------------------------------------

{
  const older = runStats(steady(1800, { speed: 2.8, hr: 155 }), { unit: 'mi' });
  const newer = runStats(steady(1800, { speed: 2.8, hr: 146 }), { unit: 'mi' });
  const p = progress([newer, older]);
  assert.ok(p.efficiencyFactor.delta > 0, 'EF must be shown as risen');
  assert.ok(p.beatsPerUnit.delta < 0, 'and cardiac cost as fallen');
  assert.equal(p.sessions, 2);

  // One session is not a trend, and neither is a pile of runs with no heart rate.
  assert.equal(progress([newer]), null);
  assert.equal(progress([{ efficiencyFactor: null }, { efficiencyFactor: null }]), null);
  console.log(`  ok  progress compares like with like and refuses a single session `
            + `(${p.beatsPerUnit.delta.toFixed(1)} beats/mi)`);
}

// --- the boundary between walking and running ------------------------------------------------------

{
  // A real session, and the bug it exposed. The plan prescribes 12:00-12:30 per mile for this
  // athlete; the fixed threshold was 12:00 per mile. So a run/walk executed exactly as asked came
  // back reading 23 seconds of running in 26 minutes — and that statistic is what the run-walk
  // ladder is entered on, so the plan was about to conclude he could not run at all.
  // Both speeds are measured rather than assumed. The Polar trace of 22 August puts his jog blocks
  // at 7.7-8.3 km/h and his walking below 6.5; the 4.4 mph this fixture used to claim he ran at is
  // 7.08 km/h, which is not a speed that appears anywhere in his recording.
  const target = 12.5 * 60 / 1.609344;             // 12:30 per mile, in seconds per km
  const runSpeed = 8.0 / 3.6;                      // 8.0 km/h, the middle of his measured jog blocks
  const walkSpeed = 5.5 / 3.6;                     // 5.5 km/h, the middle of his measured walking

  const samples = [];
  for (let rep = 0; rep < 4; rep++) {
    for (let i = 0; i < 120; i++) {
      samples.push({ t_s: samples.length, speed_m_s: runSpeed, hr_bpm: null, grade: 0, label: 'run' });
    }
    for (let i = 0; i < 120; i++) {
      samples.push({ t_s: samples.length, speed_m_s: walkSpeed, hr_bpm: null, grade: 0, label: 'walk' });
    }
  }

  const fixed = runStats(samples, {});
  assert.ok(fixed.longestRunBlockS < 5,
    `the fixed threshold should indeed miss this run entirely: ${fixed.longestRunBlockS}s`);

  const aware = runStats(samples, { targetPaceSecKm: target });
  assert.ok(Math.abs(aware.longestRunBlockS - 120) <= 2,
    `a two-minute interval at the prescribed pace must read as two minutes: ${aware.longestRunBlockS}s`);
  assert.ok(aware.runningS >= 470 && aware.runningS <= 490,
    `four two-minute intervals is eight minutes of running: ${aware.runningS}s`);
  // The boundary has to separate the two, which means sitting between them — above the walk breaks
  // so they are not counted as running, and below the running so it is.
  assert.ok(aware.jogThresholdMS > walkSpeed,
    `the boundary (${aware.jogThresholdMS.toFixed(2)}) must be above the walk (${walkSpeed.toFixed(2)})`);
  assert.ok(aware.jogThresholdMS < runSpeed,
    `and below the running (${runSpeed.toFixed(2)})`);
  console.log(`  ok  the walk/run boundary comes from the session's own target `
            + `(${fixed.longestRunBlockS}s -> ${aware.longestRunBlockS}s for the same run)`);
}

{
  // ...but deriving it from the target has an opposite failure, and this is it.
  //
  // A run/walk session's target pace is the average of running and walking, so it is slow. Eight
  // tenths of 14:00 per mile is 5.5 km/h, which is a brisk walk — and the 22 August session came
  // back claiming 8:24 of running against Polar's own trace showing 2.6 minutes above 7 km/h.
  // Three times too generous, in the number the run-walk ladder is advanced on.
  const slowTarget = 14 * 60 / 1.609344;           // 14:00 per mile: a walk/jog average
  assert.ok(jogThreshold(slowTarget) >= GAIT_TRANSITION_MS,
    `a slow target must not push the boundary below the gait transition: `
    + `${jogThreshold(slowTarget).toFixed(2)} m/s`);

  const brisk = 5.5 / 3.6;                         // his actual walking speed
  const samples = Array.from({ length: 600 }, (_, i) =>
    ({ t_s: i, speed_m_s: brisk, hr_bpm: 120, grade: 0, label: 'walk' }));
  const stats = runStats(samples, { targetPaceSecKm: slowTarget });
  assert.equal(stats.longestRunBlockS, 0,
    `ten minutes of brisk walking is not a run block: ${stats.longestRunBlockS}s`);
  assert.equal(stats.runningS, 0, `nor any running at all: ${stats.runningS}s`);
  assert.ok(stats.movingS >= 590, 'though it is certainly moving time');
  console.log(`  ok  a slow target cannot push the boundary down into walking `
            + `(${(jogThreshold(slowTarget) * 3.6).toFixed(1)} km/h floor)`);
}

{
  // Two distances that disagree is a fact about the GPS, not a number to quietly choose between.
  const samples = Array.from({ length: 600 }, (_, i) => ({
    t_s: i, speed_m_s: 2.0, hr_bpm: null, grade: 0,
  }));
  const st = runStats(samples, { trackDistanceM: 1500 });     // position says 1500, speed says 1200
  assert.equal(st.trackDistanceM, 1500);
  assert.equal(st.distanceDisagreementPct, 25);
  assert.equal(runStats(samples, {}).distanceDisagreementPct, null,
    'and with only one measurement there is nothing to disagree about');
  console.log('  ok  a disagreement between the two distances is reported rather than resolved');
}

{
  // The armband ran flat halfway through a session. What must survive that is everything the run
  // itself can answer for -- distance, pace, moving time, the continuous block the ladder advances
  // on -- plus whatever heart rate was recorded before the battery went, reported as covering half
  // the session rather than quietly averaged as though it covered all of it.
  //
  // The failure this guards against is the tempting one: treating a null heart rate as a zero, or
  // dividing a real sum by the wrong denominator. Either turns a half-recorded session into a
  // confident wrong number, which is worse than the gap it papers over.
  const samples = Array.from({ length: 1200 }, (_, i) => ({
    t_s: i, speed_m_s: 2.3, grade: 0, label: 'run', hr_bpm: i < 600 ? 140 : null,
  }));
  const s = runStats(samples, { unit: 'mi', targetPaceSecKm: 450, hrRest: 67, hrMax: 187 });

  assert.ok(s.distance > 1.6 && s.distance < 1.8, `the distance must survive: ${s.distance}`);
  assert.equal(s.runningS, 1200, 'and every second of running');
  assert.equal(s.longestRunBlockS, 1200, 'and the block length the ladder is advanced on');
  assert.equal(s.hrCoveragePct, 50, `coverage must be reported honestly: ${s.hrCoveragePct}%`);
  assert.equal(s.avgHr, 140, 'the average must come from the half that has a heart rate...');
  assert.ok(s.efficiencyFactor > 0, '...and the derived numbers must still compute');
  console.log(`  ok  a band that dies halfway still yields the run `
            + `(${s.distance.toFixed(2)} mi, ${s.hrCoveragePct}% HR coverage, avg ${s.avgHr})`);
}

console.log('\nAll run-stats tests passed.');
