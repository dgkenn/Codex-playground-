// The WAV encoder, which is the part that can be wrong silently. A malformed header plays as
// nothing at all, which is indistinguishable on a phone from the bug this replaces.

import assert from 'node:assert/strict';
import { renderSamples, wavBytes, RECIPES, RATE, PITCH } from '../tones.js';

const str = (b, off, len) => String.fromCharCode(...b.slice(off, off + len));
const u32 = (b, off) => b[off] | (b[off+1] << 8) | (b[off+2] << 16) | (b[off+3] << 24);
const u16 = (b, off) => b[off] | (b[off+1] << 8);

{
  const b = wavBytes(renderSamples(RECIPES.in_band));
  assert.equal(str(b, 0, 4), 'RIFF');
  assert.equal(str(b, 8, 4), 'WAVE');
  assert.equal(str(b, 12, 4), 'fmt ');
  assert.equal(str(b, 36, 4), 'data');
  assert.equal(u16(b, 20), 1, 'format must be PCM');
  assert.equal(u16(b, 22), 1, 'mono');
  assert.equal(u32(b, 24), RATE);
  assert.equal(u16(b, 34), 16, '16-bit');
  assert.equal(u32(b, 4), b.length - 8, 'RIFF size must be the file length minus 8');
  assert.equal(u32(b, 40), b.length - 44, 'data size must be the payload length');
  console.log('  ok  WAV header is well formed and self-consistent');
}

{
  // Every earcon must contain actual sound. An all-zero buffer plays as silence, which is exactly
  // the failure being fixed and would look identical on the phone.
  for (const [name, recipe] of Object.entries(RECIPES)) {
    const s = renderSamples(recipe);
    const peak = Math.max(...Array.from(s, Math.abs));
    assert.ok(peak > 0.5, `${name} peaks at ${peak.toFixed(3)} — that is silence`);
    assert.ok(s.length > 0.05 * RATE, `${name} is only ${(s.length / RATE).toFixed(3)}s long`);
    assert.ok(s.length < 0.6 * RATE, `${name} is ${(s.length / RATE).toFixed(2)}s — too long to be a pip`);
  }
  console.log('  ok  all five earcons contain audible sound of a sensible length');
}

{
  // The envelope exists to kill the click, so the ends must actually be near zero.
  const s = renderSamples(RECIPES.in_band);
  assert.ok(Math.abs(s[0]) < 0.02, `starts at ${s[0].toFixed(3)} — that clicks`);
  assert.ok(Math.abs(s[s.length - 1]) < 0.05, `ends at ${s[s.length-1].toFixed(3)} — that clicks`);
  console.log('  ok  the envelope brings both ends to near silence');
}

{
  // The contour carries the meaning, so it must actually be there: ease falls, lift rises.
  const dominant = seg => {
    const s = renderSamples([seg]);
    // Zero-crossing count over the steady middle is a good enough frequency estimate here.
    const mid = s.slice(Math.floor(s.length * 0.25), Math.floor(s.length * 0.75));
    let cross = 0;
    for (let i = 1; i < mid.length; i++) if ((mid[i-1] < 0) !== (mid[i] < 0)) cross++;
    return cross / 2 / (mid.length / RATE);
  };
  const easeFirst = dominant(RECIPES.ease[0]), easeLast = dominant(RECIPES.ease[2]);
  const liftFirst = dominant(RECIPES.lift[0]), liftLast = dominant(RECIPES.lift[2]);
  assert.ok(easeFirst > easeLast + 100, `ease should fall: ${easeFirst|0} -> ${easeLast|0} Hz`);
  assert.ok(liftLast > liftFirst + 100, `lift should rise: ${liftFirst|0} -> ${liftLast|0} Hz`);
  console.log(`  ok  ease falls ${easeFirst|0}->${easeLast|0} Hz, lift rises ${liftFirst|0}->${liftLast|0} Hz`);
}

{
  // Silence segments must really be silent, or the gap inside a pair is not a gap.
  const s = renderSamples([[PITCH.mid, 0.05], [0, 0.05], [PITCH.mid, 0.05]]);
  const gapStart = Math.floor(0.06 * RATE), gapEnd = Math.floor(0.09 * RATE);
  const gapPeak = Math.max(...Array.from(s.slice(gapStart, gapEnd), Math.abs));
  assert.equal(gapPeak, 0, `the gap is not silent: peak ${gapPeak}`);
  console.log('  ok  the gap inside a two-pip pattern is silence');
}

{
  // Clipping check: a sample outside [-1, 1] wraps to the opposite sign as a 16-bit int, which is
  // heard as a harsh crack rather than a tone.
  for (const recipe of Object.values(RECIPES)) {
    for (const v of renderSamples(recipe)) assert.ok(v >= -1 && v <= 1, `sample out of range: ${v}`);
  }
  console.log('  ok  nothing clips');
}

console.log('\nAll tone tests passed.');
