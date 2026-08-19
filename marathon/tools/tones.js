// The earcons, rendered to WAV and played as media rather than through Web Audio.
//
// Why not Web Audio
// -----------------
// It was Web Audio, and on an iPhone the tones were silent while the spoken splits worked. That
// split is the whole diagnosis: iOS treats an `AudioContext` as *ambient* audio, which the hardware
// silent switch mutes, while `speechSynthesis` and `<audio>` playback go through the media path,
// which it does not. So the failure was not the gesture handling, the oscillators, or the envelope —
// it was the category the platform had put the sound in, and nothing inside the Web Audio API can
// change that.
//
// Playing an `HTMLAudioElement` moves the sound onto the media path. The tones then behave like the
// voice: audible with the ring switch either way, and mixed against music by the same rules.
//
// The samples are synthesised at load time into WAV blobs rather than shipped as files, for the same
// reason they were synthesised before: every constant here — pitch, duration, the gap inside a pair,
// the envelope — will want adjusting once heard through AirPods at 160 steps per minute with music
// underneath, and a number in a source file can be adjusted where a rendered asset cannot.

export const RATE = 44100;

/// Pitches sit above most music's vocal range so they are audible without being loud, and far enough
/// apart that the rise/fall contour survives compression and wind noise.
export const PITCH = { low: 587.33, mid: 740.0, high: 880.0 };
const PIP = 0.09, GAP = 0.055, FADE = 0.008;

/// Contour carries the meaning: falling means back off, rising means more. The same mapping as
/// almost every other interface a person has used, which is the point — nothing to learn.
export const RECIPES = {
  ease:     [[PITCH.high, PIP], [0, GAP], [PITCH.low, PIP]],
  lift:     [[PITCH.low, PIP], [0, GAP], [PITCH.high, PIP]],
  in_band:  [[PITCH.mid, PIP * 1.3]],
  attend:   [[PITCH.low, PIP * 0.6], [0, GAP * 0.7], [PITCH.mid, PIP * 0.6],
             [0, GAP * 0.7], [PITCH.high, PIP * 0.6]],
  // Deliberately unlike the others — low, dull, doubled — so a degradation notice is never mistaken
  // for a pace instruction.
  degraded: [[220.0, PIP * 1.2], [0, GAP], [220.0, PIP * 1.2]],
};

/** Render `[frequency, seconds]` segments to mono float samples. Frequency 0 is silence. */
export function renderSamples(segments, rate = RATE) {
  const total = segments.reduce((a, [, d]) => a + d, 0);
  const out = new Float32Array(Math.max(1, Math.round(total * rate)));
  let index = 0;
  for (const [freq, dur] of segments) {
    const n = Math.round(dur * rate);
    const fade = Math.max(1, Math.round(FADE * rate));
    for (let i = 0; i < n && index + i < out.length; i++) {
      if (freq <= 0) continue;
      // Raised-cosine envelope at both ends. Without it the discontinuity where the burst starts and
      // stops is audible as a click, and the click is louder and more startling than the tone.
      let env = 1;
      if (i < fade) env = 0.5 * (1 - Math.cos(Math.PI * i / fade));
      else if (i > n - fade) env = 0.5 * (1 - Math.cos(Math.PI * (n - i) / fade));
      out[index + i] = Math.sin(2 * Math.PI * freq * i / rate) * env;
    }
    index += n;
  }
  return out;
}

/** Wrap float samples in a 16-bit PCM WAV container. */
export function wavBytes(samples, rate = RATE) {
  const n = samples.length;
  const buf = new ArrayBuffer(44 + n * 2);
  const v = new DataView(buf);
  const ascii = (off, s) => { for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i)); };

  ascii(0, 'RIFF');
  v.setUint32(4, 36 + n * 2, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  v.setUint32(16, 16, true);          // PCM chunk size
  v.setUint16(20, 1, true);           // format: PCM
  v.setUint16(22, 1, true);           // channels: mono
  v.setUint32(24, rate, true);
  v.setUint32(28, rate * 2, true);    // byte rate
  v.setUint16(32, 2, true);           // block align
  v.setUint16(34, 16, true);          // bits per sample
  ascii(36, 'data');
  v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Uint8Array(buf);
}

export function wavDataUri(segments, rate = RATE) {
  const bytes = wavBytes(renderSamples(segments, rate), rate);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return 'data:audio/wav;base64,' + btoa(bin);
}

/**
 * Plays the vocabulary through the media path.
 *
 * Two elements per sound, alternated, so a tone arriving while the previous one is still finishing
 * does not cut it off mid-envelope — which sounds like a fault rather than a cue.
 */
export class Tones {
  constructor({ volume = 0.65 } = {}) {
    this.volume = volume;
    this.pool = {};
    this.unlocked = false;
    this.lastError = null;
    for (const [name, recipe] of Object.entries(RECIPES)) {
      const uri = wavDataUri(recipe);
      this.pool[name] = [new Audio(uri), new Audio(uri)];
      for (const a of this.pool[name]) { a.preload = 'auto'; a.volume = volume; }
    }
    this.turn = {};
  }

  setVolume(v) {
    this.volume = v;
    for (const list of Object.values(this.pool)) for (const a of list) a.volume = v;
  }

  /**
   * Must be called from inside a user gesture, once.
   *
   * iOS refuses to play media that no tap asked for, and the refusal is permanent for that element
   * until a gesture arrives. Playing every element muted and immediately pausing marks them all as
   * user-initiated, so a tone forty minutes later — which no tap asked for — is allowed.
   */
  unlock() {
    if (this.unlocked) return Promise.resolve(true);
    const all = Object.values(this.pool).flat();
    return Promise.all(all.map(a => {
      a.muted = true;
      const p = a.play();
      return (p && p.then ? p : Promise.resolve())
        .then(() => { a.pause(); a.currentTime = 0; a.muted = false; })
        .catch(e => { this.lastError = e; a.muted = false; });
    })).then(() => { this.unlocked = true; return true; });
  }

  play(name) {
    const list = this.pool[name];
    if (!list) return Promise.resolve(false);
    const i = (this.turn[name] = ((this.turn[name] || 0) + 1) % list.length);
    const a = list[i];
    try { a.currentTime = 0; } catch { /* not yet loaded; play from wherever it is */ }
    const p = a.play();
    return (p && p.then ? p : Promise.resolve())
      .then(() => true)
      .catch(e => { this.lastError = e; return false; });
  }
}
