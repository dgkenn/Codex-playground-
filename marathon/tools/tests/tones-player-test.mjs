// The player, not the encoder.
//
// The encoder tests prove the WAV is well formed. That was never the failure on the phone — the
// failure was always about *when* something is allowed to play, and it presented identically to a
// broken file: a button that does nothing. So the ordering rules get their own suite, driven by a
// fake audio element that records what was asked of it.

import assert from 'node:assert/strict';

// A stand-in for HTMLAudioElement with the three behaviours that matter on iOS.
//
//   1. `play()` returns a promise.
//   2. It rejects unless the call is inside a user gesture — until this element has been played once
//      inside one, after which the element is unlocked for good. That per-element latch is the whole
//      reason `unlock()` exists.
//   3. `volume` is inert. iOS accepts the assignment and ignores it, so the fake does too; a fake
//      that honoured it would let a broken volume control pass its own tests.
const plays = [];
let inGesture = false;
/** Run `fn` as though it were the body of a tap handler. Only its synchronous part counts. */
const tap = fn => { inGesture = true; try { return fn(); } finally { inGesture = false; } };

class FakeAudio {
  constructor(src) { this.src = src; this.paused = true; this.currentTime = 0; this.readyState = 4; }
  set volume(_v) { /* iOS ignores this; so does the fake, on purpose */ }
  get volume() { return 1; }
  play() {
    if (!inGesture && !this.unlockedElement) {
      return Promise.reject(new Error('NotAllowedError: user gesture required'));
    }
    if (inGesture) this.unlockedElement = true;
    this.paused = false;
    plays.push(this.src);
    return Promise.resolve();
  }
  pause() { this.paused = true; }
}
globalThis.Audio = FakeAudio;

const { Tones, RECIPES, SILENCE, wavDataUri } = await import('../tones.js');

const silentUri = wavDataUri(SILENCE);
const reset = () => { plays.length = 0; };

// --- the unlock ordering -------------------------------------------------------------------------

{
  // Before any tap, every element holds silence. If it held the real tone, an accidental early play
  // would be inaudible and the whole subsystem would look broken while behaving correctly.
  const t = new Tones();
  for (const list of Object.values(t.pool)) {
    for (const a of list) assert.equal(a.src, silentUri, 'elements must start holding silence');
  }
  assert.equal(t.unlocked, false);
  console.log('  ok  elements hold silence until a tap unlocks them');
}

{
  // Unlock plays each element once — that is what marks it user-initiated — and only then swaps in
  // the real sounds. Every play during unlock must be the silent buffer, or the unlock is audible.
  reset();
  const t = new Tones();
  await tap(() => t.unlock());
  const count = Object.values(t.pool).flat().length;
  assert.equal(plays.length, count, 'every element must be played once to unlock it');
  assert.ok(plays.every(src => src === silentUri), 'the unlock must be inaudible');
  assert.equal(t.unlocked, true);
  for (const [name, list] of Object.entries(t.pool)) {
    for (const a of list) {
      assert.notEqual(a.src, silentUri, `${name} must hold its real sound after unlocking`);
      assert.equal(a.paused, true, 'the unlock buffer must be paused, not left running');
    }
  }
  console.log('  ok  unlock plays silence on every element, then loads the real sounds');
}

// --- the first tap -------------------------------------------------------------------------------

{
  // This is the reported bug in miniature. The first tap on a tone button is also the tap that
  // unlocks, and unlocking is asynchronous — so a naive `play()` fires before the elements are ready
  // and is dropped. It must queue behind the unlock instead.
  reset();
  const t = new Tones();
  // Both calls in one handler, which is how the button is actually wired.
  const [unlocking, playing] = tap(() => [t.unlock(), t.play('ease')]);
  await unlocking;
  const played = await playing;
  assert.equal(played, true, 'the first tap must be heard, not swallowed by the unlock race');
  const easeUri = wavDataUri(RECIPES.ease, undefined, t.volume);
  assert.ok(plays.includes(easeUri), 'and what it played must be the real earcon, not silence');
  console.log('  ok  the first tap queues behind the unlock instead of being dropped');
}

{
  // With no unlock in flight at all, a play is refused with a reason rather than silently doing
  // nothing — "nothing happened" is the one outcome that cannot be diagnosed from a phone.
  reset();
  const t = new Tones();
  assert.equal(await t.play('lift'), false);
  assert.match(t.state().lastError, /not unlocked/);
  assert.equal(plays.length, 0);
  console.log('  ok  a play before any tap is refused with a stated reason');
}

// --- volume --------------------------------------------------------------------------------------

{
  const t = new Tones({ volume: 0.65 });
  await tap(() => t.unlock());
  const loud = t.pool.in_band[0].src;
  t.setVolume(0.3);
  const quiet = t.pool.in_band[0].src;
  assert.notEqual(loud, quiet, 'changing the volume must change the audio itself, not a property');
  assert.ok(quiet.length < loud.length * 1.05);
  assert.equal(t.unlocked, true, 'the unlock must survive the src swap');
  reset();
  assert.equal(await t.play('in_band'), true, 'and the element must still play afterwards');
  assert.equal(plays[0], quiet, 'at the new volume');
  console.log('  ok  volume re-renders the audio and the unlock survives it');
}

// --- diagnostics ---------------------------------------------------------------------------------

{
  // The report is how a fault gets from the phone to the fix, so the fields have to be there.
  const t = new Tones();
  const s = t.state();
  for (const k of ['unlocked', 'volume', 'readyState', 'paused', 'mediaError', 'lastError']) {
    assert.ok(k in s, `diagnostics must report ${k}`);
  }
  assert.equal(s.unlocked, false);
  console.log('  ok  the diagnostics report carries the whole tone state');
}

console.log('\nAll tone player tests passed.');
