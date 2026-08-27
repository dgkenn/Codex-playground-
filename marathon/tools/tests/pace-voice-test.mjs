// The spoken pace channel, driven through the session that produced the complaint.
//
// The report: "I feel like the pacing tones never really came", "I couldn't tell if I was going too
// fast, too slow, or just right", and "I'm having a really hard time pacing, I'm not sure where I
// am." The first of those is measured against the tone channel here, so the claim that this module
// exists for a real gap is checked rather than asserted.

import assert from 'node:assert/strict';
import { PaceVoice, EVERY_S, SETTLE_S } from '../pace-voice.js';
import { PaceBandMonitor } from '../pace-monitor.js';

const MI = 1609.344;
/** Seconds per km to a mm:ss per mile string, which is how this athlete thinks. */
const perMile = secKm => {
  const s = secKm * MI / 1000;
  return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
};
const TARGET = 450;          // 12:04 per mile, the prescribed run-block pace

/** Drive a 7 x (2 min run / 2 min walk) session at `paceOf(rep)` and collect what is said. */
function session(voice, paceOf, { reps = 7, runS = 120, walkS = 120 } = {}) {
  const said = [];
  let t = 0;
  for (let rep = 0; rep < reps; rep++) {
    voice.begin(t);
    for (let i = 0; i < runS; i++, t++) {
      const ev = voice.update(t, paceOf(rep), { running: true, trusted: true });
      if (ev) said.push({ t, ...ev });
    }
    for (let i = 0; i < walkS; i++, t++) {
      const ev = voice.update(t, TARGET * 1.6, { running: false, trusted: true });
      if (ev) said.push({ t, ...ev, walk: true });
    }
  }
  return said;
}

{
  // The gap this module exists for, and it is not density -- it is that silence is ambiguous.
  //
  // Drive the SAME session through the tone channel twice: once run 20% too fast, once run exactly
  // on target. The second produces nothing at all. That is the tone channel working as designed --
  // inside the band there is nothing to say -- and it is also indistinguishable, in the ear, from a
  // dead app, a lost GPS fix or a phone that has locked itself. Twenty-eight minutes of silence is
  // the same sound as twenty-eight minutes of being right, and no amount of retuning fixes it,
  // because the thing missing is not a cue. It is the number.
  //
  //   "I'm having a really hard time pacing. I'm not sure where I am, like, exactly."
  const toneCount = mul => {
    const m = new PaceBandMonitor({ targetPaceSecKm: TARGET, tolerance: 0.04, ceilingOnly: true });
    let n = 0, t = 0;
    for (let rep = 0; rep < 7; rep++) {
      for (let i = 0; i < 120; i++, t++) {
        if (m.update(t, TARGET * mul, { paceTrusted: true, running: true })) n++;
      }
      for (let i = 0; i < 120; i++, t++) m.update(t, TARGET * 1.6, { paceTrusted: true, running: false });
    }
    return n;
  };
  const onTargetTones = toneCount(1.00);
  assert.equal(onTargetTones, 0, 'a correctly-run session is silent on the tone channel, by design');

  const voice = new PaceVoice({ targetSecKm: TARGET, tolerance: 0.04, ceilingOnly: true,
                                formatPace: perMile });
  const said = session(voice, () => TARGET);
  assert.ok(said.length >= 25,
    `and must NOT be silent on the spoken one: ${said.length} lines in 28 min`);
  assert.ok(said.every(s => /^\d+:\d\d\./.test(s.text)),
    `every one of which carries the number: ${JSON.stringify(said.slice(0, 2))}`);
  console.log(`  ok  a correctly-run 28 min session: ${onTargetTones} tones, `
            + `${said.length} spoken lines that each name the pace`);
}

{
  // "I'm not sure where I am, exactly." Every line carries the measured pace, so the number arrives
  // whether or not anything has changed -- which is the whole difference from a threshold cue.
  const voice = new PaceVoice({ targetSecKm: TARGET, tolerance: 0.04, formatPace: perMile });
  const said = session(voice, () => TARGET);
  assert.ok(said.length > 0, 'a correctly-run session must still be told where it is');
  for (const s of said) {
    assert.match(s.text, /^\d+:\d\d\. /, `every line must open with the pace: "${s.text}"`);
    assert.equal(s.kind, 'in');
    assert.match(s.text, /On pace\./);
  }
  console.log(`  ok  the number is spoken even when nothing is wrong (${said[0].text})`);
}

{
  // The three directions have to be distinguishable as words, which was the second complaint: a
  // rising and a falling tone pair are not, at 160 steps a minute with music underneath.
  const mk = ceilingOnly => new PaceVoice({ targetSecKm: TARGET, tolerance: 0.04, ceilingOnly,
                                            formatPace: perMile });
  const fast = session(mk(false), () => TARGET * 0.8)[0];
  const slow = session(mk(false), () => TARGET * 1.2)[0];
  const on = session(mk(false), () => TARGET)[0];
  assert.match(fast.text, /Ease up\./);
  assert.match(slow.text, /Pick it up\./);
  assert.match(on.text, /On pace\./);
  assert.equal(new Set([fast.text, slow.text, on.text]).size, 3, 'and they must not collide');

  // On a ceiling-only session -- every easy run in this plan -- being under the band is not a fault,
  // so it must not be reported as one. It must also not be reported as "on pace", which would be a
  // lie about a number spoken in the same breath.
  const easy = session(mk(true), () => TARGET * 1.2)[0];
  assert.match(easy.text, /Easy\./);
  assert.doesNotMatch(easy.text, /Pick it up|On pace/);
  console.log(`  ok  the direction is a word, not a contour ("${fast.text}" / "${slow.text}")`);
}

{
  // Cadence: the first line waits for GPS to catch up with the change of pace, then it is regular.
  // Announcing at the instant a run block opens would report the walk that preceded it.
  const voice = new PaceVoice({ targetSecKm: TARGET, tolerance: 0.04, formatPace: perMile });
  const said = [];
  voice.begin(0);
  for (let t = 0; t < 300; t++) {
    const ev = voice.update(t, TARGET, { running: true, trusted: true });
    if (ev) said.push(t);
  }
  assert.ok(said[0] >= SETTLE_S, `the first line must wait out the settle: ${said[0]}s`);
  assert.ok(said[0] <= SETTLE_S + 3, `but not much longer than it: ${said[0]}s`);
  for (let i = 1; i < said.length; i++) {
    assert.equal(said[i] - said[i - 1], EVERY_S,
      `the cadence must be regular: ${JSON.stringify(said)}`);
  }
  console.log(`  ok  first line at ${said[0]}s, then every ${EVERY_S}s (${said.length} in 5 min)`);
}

{
  // Silence during walk breaks. A walk is the prescription, not a pace failure, and being told to
  // pick it up through a recovery break teaches you to stop listening.
  const voice = new PaceVoice({ targetSecKm: TARGET, tolerance: 0.04, formatPace: perMile });
  const said = session(voice, () => TARGET);
  assert.equal(said.filter(s => s.walk).length, 0, 'nothing may be said during a walk break');

  // And each block gets its own settle rather than inheriting the last one's clock -- otherwise the
  // first line of a block lands anywhere from immediately to a full cadence in, depending only on
  // where the walk happened to fall.
  const firsts = [];
  let seenBlock = -1;
  for (const s of said) {
    const block = Math.floor(s.t / 240);
    if (block !== seenBlock) { seenBlock = block; firsts.push(s.t - block * 240); }
  }
  assert.ok(firsts.every(f => f >= SETTLE_S && f <= SETTLE_S + 3),
    `every block must open with its own settle: ${JSON.stringify(firsts)}`);
  console.log(`  ok  walk breaks are silent, and each block settles on its own (${firsts.join(', ')}s)`);
}

{
  // No signal is said once, not once a second. Under trees the number genuinely cannot be reported,
  // and saying so is honest; repeating it sixty times a minute is its own fault.
  const voice = new PaceVoice({ targetSecKm: TARGET, tolerance: 0.04, formatPace: perMile });
  voice.begin(0);
  let lost = 0;
  for (let t = 0; t < 120; t++) {
    const ev = voice.update(t, null, { running: true, trusted: false });
    if (ev && ev.kind === 'lost') lost++;
  }
  assert.ok(lost >= 1 && lost <= 2, `a two-minute outage must be reported ${lost} times, not 120`);

  // And when it returns, the number comes back rather than staying quiet.
  let recovered = null;
  for (let t = 120; t < 200 && !recovered; t++) {
    recovered = voice.update(t, TARGET, { running: true, trusted: true });
  }
  assert.ok(recovered, 'the pace must be spoken again once the signal returns');
  assert.match(recovered.text, /^\d+:\d\d\./);
  console.log(`  ok  a signal outage is reported once and recovers (${lost} line, then "${recovered.text}")`);
}

{
  // Nothing to say without a target, and no crash for asking.
  const voice = new PaceVoice({ targetSecKm: null, formatPace: perMile });
  voice.begin(0);
  for (let t = 0; t < 60; t++) {
    assert.equal(voice.update(t, TARGET, { running: true, trusted: true }), null);
  }
  console.log('  ok  a session with no target says nothing rather than guessing');
}

console.log('\nAll pace-voice tests passed.');
