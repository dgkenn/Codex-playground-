// The ramp test's clock, driven a second at a time through the real protocol from the engine.
//
// What makes this worth testing rather than eyeballing: the failure modes are all silent. A stage
// that fires twice, a final-minute warning that never comes, a label that is empty — none of them
// look wrong while you are on the treadmill, and all of them are only discovered afterwards when the
// recording turns out to be unanalysable and the hour has to be run again.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { RampRunner, RampEvent } from '../ramp.js';

const here = dirname(fileURLToPath(import.meta.url));
const plan = JSON.parse(readFileSync(join(here, '..', '..', 'engine', 'app_plan.generated.json'), 'utf8'));

const rampSession = plan.phases
  .flatMap(p => p.weeks).flatMap(w => w.sessions)
  .find(s => s.ramp);

{
  assert.ok(rampSession, 'the plan must ship a machine-readable ramp protocol');
  const steps = rampSession.ramp.steps;
  assert.ok(steps.length >= 6, `only ${steps.length} steps`);
  assert.equal(steps[0].kind, 'warmup', 'a ramp must open with a warm-up, not with a stage');
  const stages = steps.filter(s => s.kind === 'stage');
  assert.ok(stages.length >= 5, `only ${stages.length} stages — too few to fit a line through`);
  for (let i = 1; i < stages.length; i++) {
    assert.ok(stages[i].speed_kmh > stages[i - 1].speed_kmh,
      `stage ${i + 1} is not faster than stage ${i}`);
  }
  assert.ok(steps.some(s => s.kind === 'steady'),
    'the steady block is the most informative part of the session and must be in the protocol');
  console.log(`  ok  the plan ships ${stages.length} rising stages plus warm-up and steady block`);
}

// --- the whole hour, one second at a time --------------------------------------------------------

function run(steps, { stopAfterS = 100000 } = {}) {
  const r = new RampRunner(steps);
  const events = [];
  const labels = [];
  for (let t = 0; t <= stopAfterS && !r.done; t++) {
    const e = r.update(t);
    if (e) events.push({ t, ...e });
    labels.push(r.label);
  }
  return { runner: r, events, labels };
}

{
  const { runner, events, labels } = run(rampSession.ramp.steps);
  const starts = events.filter(e => e.kind === RampEvent.STEP);
  const finals = events.filter(e => e.kind === RampEvent.FINAL_MINUTE);
  const done = events.filter(e => e.kind === RampEvent.DONE);

  assert.equal(starts.length, rampSession.ramp.steps.length,
    'every step must be announced exactly once');
  assert.equal(done.length, 1, 'the protocol must end exactly once');
  assert.ok(runner.done);

  // Boundaries must land where the protocol says, not a second early or late — the analysis windows
  // are cut from these timestamps.
  let expected = 0;
  rampSession.ramp.steps.forEach((step, i) => {
    assert.equal(starts[i].t, expected, `${step.label} started at ${starts[i].t}s, expected ${expected}`);
    expected += Math.round(step.minutes * 60);
  });
  console.log(`  ok  all ${starts.length} steps fire once, on the second, in order`);

  const stages = rampSession.ramp.steps.filter(s => s.kind === 'stage');
  assert.equal(finals.length, stages.length,
    `${finals.length} final-minute warnings for ${stages.length} stages`);
  for (const f of finals) {
    assert.equal(f.step.kind, 'stage', 'only stages have a measured final minute');
  }
  console.log(`  ok  each of the ${stages.length} stages gets exactly one final-minute warning`);

  // The labels are the whole point: without them the recording is one undifferentiated blob.
  const seen = [...new Set(labels)].filter(Boolean);
  for (const s of stages) assert.ok(seen.includes(`stage_${s.index}`), `no samples labelled stage_${s.index}`);
  assert.ok(seen.includes('warmup') && seen.includes('steady'), `labels seen: ${seen.join(', ')}`);
  assert.equal(labels.filter(l => l === 'stage_1').length, 240,
    'stage 1 must be labelled for its full four minutes');
  console.log(`  ok  every second is labelled with its stage (${seen.join(', ')})`);
}

// --- the ways it could go wrong ------------------------------------------------------------------

{
  // A zero-length step must not run the rest of the protocol inside one tick. This is the shape of
  // bug that announces six stages simultaneously and then sits silent for an hour.
  const { events } = run([
    { kind: 'warmup', label: 'W', minutes: 0 },
    { kind: 'stage', label: 'S1', index: 1, minutes: 0 },
    { kind: 'steady', label: 'St', minutes: 0.05 },
  ]);
  const byTime = {};
  for (const e of events.filter(x => x.kind === RampEvent.STEP)) {
    byTime[e.t] = (byTime[e.t] || 0) + 1;
  }
  for (const [t, n] of Object.entries(byTime)) {
    assert.equal(n, 1, `${n} steps announced at t=${t}s — a zero-length step ran away`);
  }
  console.log('  ok  a zero-length step advances one boundary per tick, not all of them at once');
}

{
  // Before the first tick there is no step, so there is no label — an empty string, not the last
  // one, and not "stage_undefined".
  const r = new RampRunner(rampSession.ramp.steps);
  assert.equal(r.label, '');
  assert.equal(r.step, null);
  assert.equal(r.remaining(0), 0);
  console.log('  ok  nothing is labelled before the protocol starts');
}

{
  // An empty protocol ends immediately rather than looping. It should not be possible to load one,
  // but "should not be possible" is how a treadmill session becomes a blank screen.
  const r = new RampRunner([]);
  assert.deepEqual(r.update(0), { kind: RampEvent.DONE });
  assert.equal(r.update(1), null, 'a finished protocol must stay finished');
  assert.equal(r.totalS(), 0);
  console.log('  ok  an empty protocol finishes instead of looping');
}

{
  // The total has to match the plan's own arithmetic, or the card promises an hour and the session
  // runs for forty minutes.
  const r = new RampRunner(rampSession.ramp.steps);
  assert.equal(r.totalS(), Math.round(rampSession.ramp.total_min * 60),
    'the runner and the plan must agree on how long this takes');
  assert.equal(rampSession.minutes, Math.round(rampSession.ramp.total_min),
    'and so must the session card — it used to say 35 minutes for a 59 minute protocol');
  console.log(`  ok  runner, protocol and session card agree on ${rampSession.minutes} minutes`);
}

console.log('\nAll ramp tests passed.');
