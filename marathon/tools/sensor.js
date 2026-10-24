// Reading the Polar Verity Sense from a browser.
//
// Safari has no Web Bluetooth and is not getting it, so on an iPhone this only runs inside a browser
// that adds it — Bluefy is the usual one. Everywhere else (Chrome, Edge, Android) it just works. The
// coach detects which it has and degrades to GPS-only rather than failing, because a coach that
// needs a permission it might not get is not a coach.
//
// Protocol details are ported from PolarPMD.swift, itself ported from hardware-tested Python. Three
// of them are wrong in most third-party implementations and are called out where they occur.
//
// The heart-rate staleness rule is the important one and it is not a protocol detail at all: a
// heart rate that stopped arriving must never be reported as current. The armband logger learned
// this the hard way — without the check it wrote its last reading every second for the rest of the
// session, producing a flat, plausible, entirely fabricated trace.

// Full 128-bit UUIDs, not the short aliases.
//
// It was `'heart_rate'` and `'battery_service'`, which the spec allows and Chrome accepts. Third-
// party WebBLE browsers frequently do not, and the failure is quiet in the worst way: the device
// picker appears and works, the GATT connection succeeds, and then the service lookup throws — so
// from the outside it looks as though selecting the armband simply did nothing.
//
// Bluefy is the only route to the armband from an iPhone, so the canonical form is the correct one
// to ship. It costs nothing on browsers that accepted the alias.
import { PSFTP_SERVICE, PsFtpClient } from './polar-offline.js';

export const HR_SERVICE = '0000180d-0000-1000-8000-00805f9b34fb';
export const HR_CHAR = '00002a37-0000-1000-8000-00805f9b34fb';
export const BATTERY_SERVICE = '0000180f-0000-1000-8000-00805f9b34fb';
export const BATTERY_CHAR = '00002a19-0000-1000-8000-00805f9b34fb';
export const PMD_SERVICE = 'fb005c80-02e7-f387-1cad-8acd2d8df0c8';
export const PMD_CONTROL = 'fb005c81-02e7-f387-1cad-8acd2d8df0c8';
export const PMD_DATA = 'fb005c82-02e7-f387-1cad-8acd2d8df0c8';

const MEAS_ACC = 0x02, OP_START = 0x02;
/// Pulse-to-pulse intervals: beat-by-beat timing from the optical sensor, computed on the band.
export const MEAS_PPI = 0x03;
const OP_GET_SETTINGS = 0x01, OP_STOP = 0x03;
const SETTING = { sampleRate: 0x00, resolution: 0x01, range: 0x02, channels: 0x04 };
/// CHANNELS is a ONE-byte setting. Encoding it as uint16 writes an extra byte into every START
/// command and misaligns the parse of every field after it.
const SETTING_WIDTH = { 0x00: 2, 0x01: 2, 0x02: 2, 0x04: 1, 0x05: 4 };
/// 52 Hz, 16-bit, +/-8 G, ordered RANGE -> SAMPLE_RATE -> RESOLUTION to reproduce Polar's own
/// verified byte sequence exactly.
const ACC_SETTINGS = [[SETTING.range, 8], [SETTING.sampleRate, 52], [SETTING.resolution, 16]];
/// Compression is signalled SOLELY by bit 7 of the frame-type byte. The low seven bits are an
/// independent raw-layout id, so treating a literal frame type of 0x02 as "delta compressed"
/// collides with the 24-bit uncompressed layout.
const COMPRESSED_BIT = 0x80;

/// The band's answers on the PMD control point: [0xF0, op, measurement, status, more, settings...].
/// Polar's measurement-data specification; the status codes are what make a refusal diagnosable.
export const PMD_STATUS = ['success', 'invalid op code', 'invalid measurement type', 'not supported',
  'invalid length', 'invalid parameter', 'already in that state', 'invalid resolution',
  'invalid sample rate', 'invalid range', 'invalid MTU', 'invalid number of channels',
  'invalid state', 'device in charger'];

/** Parse one control-point answer, or null if it is not one. */
export function parsePmdResponse(view) {
  if (!view || view.byteLength < 4 || view.getUint8(0) !== 0xF0) return null;
  const op = view.getUint8(1), meas = view.getUint8(2), status = view.getUint8(3);
  const settings = {};
  if (op === OP_GET_SETTINGS && status === 0) {
    let off = 5;                                   // byte 4 says whether more frames follow
    while (off + 2 <= view.byteLength) {
      const id = view.getUint8(off), count = view.getUint8(off + 1);
      off += 2;
      const w = SETTING_WIDTH[id];
      if (!w) break;
      const vals = [];
      for (let i = 0; i < count && off + w <= view.byteLength; i++) {
        let v = 0;
        for (let b = 0; b < w; b++) v += view.getUint8(off + b) * 2 ** (8 * b);
        vals.push(v); off += w;
      }
      settings[id] = vals;
    }
  }
  // `raw` for callers that parse the answer themselves (polar-offline.js reads its parameters).
  const raw = new Uint8Array(view.buffer, view.byteOffset, view.byteLength).slice();
  return { op, meas, status, statusText: PMD_STATUS[status] || `status ${status}`, settings, raw };
}

/**
 * The start settings, chosen from what the band says it supports: 52 Hz, 16-bit, +/-8 g, 3 channels
 * where offered. Every setting the band lists is included -- leaving one out (CHANNELS, which the
 * first version omitted) is a start the band can refuse.
 */
export function chooseAccSettings(settings) {
  const pick = (id, want) => {
    const v = settings[id];
    return v.includes(want) ? want : v[0];
  };
  const out = [];
  if (settings[SETTING.range] && settings[SETTING.range].length) out.push([SETTING.range, pick(SETTING.range, 8)]);
  if (settings[SETTING.sampleRate] && settings[SETTING.sampleRate].length) out.push([SETTING.sampleRate, pick(SETTING.sampleRate, 52)]);
  if (settings[SETTING.resolution] && settings[SETTING.resolution].length) out.push([SETTING.resolution, pick(SETTING.resolution, 16)]);
  if (settings[SETTING.channels] && settings[SETTING.channels].length) out.push([SETTING.channels, pick(SETTING.channels, 3)]);
  return out.length ? out : [...ACC_SETTINGS, [SETTING.channels, 3]];
}

/// A heart rate older than this is a memory, not a measurement. The band sends at about 1 Hz, so
/// five seconds is four missed notifications — comfortably past noise.
export const STALE_HR_MS = 5000;

/// How often the battery is re-read while connected.
///
/// It was read exactly once, at connect, and then never again -- so the number on screen was however
/// full the band had been when it was paired, and it stayed that way while the band went flat. A
/// battery died halfway through a session and nothing anywhere said it was going to. A read is one
/// short GATT operation; five minutes is often enough to catch a fall and rare enough to be free.
export const BATTERY_POLL_MS = 5 * 60 * 1000;

/// Below this the band should be charged before a session rather than during one.
///
/// The Verity Sense runs about 20 hours from full, so 20% is roughly four hours -- comfortably more
/// than any session in this plan, and little enough that it will not survive the week. It is a
/// "charge it tonight" line, not a "stop now" one, which is why it warns before a run rather than
/// interrupting one.
export const BATTERY_LOW_PCT = 20;

/// How long a connect step may take before it is called a failure.
///
/// Web Bluetooth has no timeout of its own, and third-party WebBLE bridges are the ones most likely
/// to leave a promise pending forever — the band is off, or another app holds it, and the bridge
/// simply never answers. A pending promise shows as "connecting" until the page is closed, which is
/// the same "nothing happened" the full UUIDs already had to be fixed for. Better a wrong-but-loud
/// verdict at twenty seconds than a right-but-silent one at never.
export const CONNECT_TIMEOUT_MS = 20000;

/// How long the device picker may stay open before it is called a failure.
///
/// Longer than the connect budget because a person is choosing from a list, and being cut off
/// mid-tap would be its own bug. Bounded anyway: an unbounded wait is exactly what left the panel
/// reading "asking for the device" indefinitely with nothing to act on.
export const PICKER_TIMEOUT_MS = 75000;

/// How many times to try opening the GATT link before giving up.
///
/// A first-attempt failure is routine rather than exceptional on iOS WebBLE bridges: the radio is
/// still tearing down a previous link, or the peripheral is mid-advertisement. Retrying is what a
/// native app does silently, and it is the difference between "armband unusable" and a two-second
/// pause nobody notices.
export const GATT_ATTEMPTS = 3;
export const GATT_RETRY_MS = 800;

/// How long the extras (battery, accelerometer) may take, each, before they are given up on. They
/// run AFTER heart rate is streaming and can never fail the connection: a motion-sensor start that
/// hung used to take the whole connect down with it, heart rate included.
export const EXTRA_TIMEOUT_MS = 5000;

/// The accelerometer is a conversation (ask for settings, start, maybe stop and start again), so it
/// gets longer than the other extras.
export const ACC_TIMEOUT_MS = 12000;

/// How long `autoConnect` keeps looking for the armband before handing back to the Connect button.
export const AUTO_CONNECT_WINDOW_MS = 120000;

/// Between looks, while waiting for the armband to be switched on or to come free.
export const AUTO_CONNECT_RETRY_MS = 4000;

/// One look for the band, while waiting for it, gets this long before the next. Shorter than a full
/// connect budget: a band that is off or held elsewhere never answers, and a 20 s hang per look
/// would mean six looks in two minutes instead of a dozen.
export const LOOK_TIMEOUT_MS = 10000;

/// In a reconnect loop, after this many failures on the same device object, ask the browser for the
/// remembered devices again: an object the bridge has silently invalidated fails for ever, and a
/// fresh one from getDevices connects.
export const REACQUIRE_AFTER = 3;

/// Where the last armband that actually streamed is remembered, so it is preferred among several
/// remembered entries (a band that was reset or re-permitted can appear twice).
export const ARMBAND_KEY = 'band.armband';

/// Heart rate that was flowing and has stopped for this long, while the link still says connected,
/// is a stalled stream: the link is torn down and rebuilt rather than left looking connected.
export const HR_STALL_MS = 20000;
/// After the band reports 0 bpm -- it has lost the pulse, or has just been switched on -- its next
/// readings climb from nowhere while the optical algorithm re-acquires (24 October: 82, 86, 89, 93...
/// mid-run, against a true rate near 140). The engine distrusts the first 30 s of a PPG stream for
/// the same reason (signal_quality.PPG_WARMUP_S); so does this.
export const HR_ACQUIRE_MS = 30000;
/// Link losses within this window that make the accelerometer stream the suspect (see _linkLost).
export const SHED_WINDOW_MS = 10 * 60 * 1000;
export const SHED_AFTER_LOSSES = 2;
/// Per attempt while reconnecting mid-run. The loop around it retries; one attempt hanging for the
/// full first-connect timeout was most of a 40-second gap.
export const RECONNECT_ATTEMPT_MS = 8000;

/**
 * Turn anything that was thrown into something a person can read.
 *
 * This exists because of a diagnostics line that said, in full: `failed at "connecting": Error —
 * undefined`. The connect had rejected with a value that was not an Error — no `name`, no `message`
 * — and the report faithfully printed both missing fields. The single most important field in the
 * whole report was the word "undefined", which is worse than useless: it looks like information.
 *
 * Bridges reject with strings, with bare `undefined`, with plain objects, and with DOMExceptions
 * whose useful content is in non-enumerable properties. All of them end up here.
 */
export function describeError(e) {
  if (e === undefined) return 'the connection was rejected with no reason at all (undefined)';
  if (e === null) return 'the connection was rejected with null';
  if (typeof e === 'string') return e || '(empty string)';
  if (typeof e !== 'object') return `${typeof e}: ${String(e)}`;

  const bits = [];
  if (e.name) bits.push(String(e.name));
  if (e.message) bits.push(String(e.message));
  if (e.code != null) bits.push(`code ${e.code}`);
  if (!bits.length) {
    // Nothing standard on it. Take whatever it does carry rather than reporting a blank.
    try {
      const own = Object.getOwnPropertyNames(e)
        .filter(k => typeof e[k] !== 'function')
        .slice(0, 8)
        .map(k => `${k}=${String(e[k])}`);
      if (own.length) bits.push(own.join(', '));
    } catch { /* exotic object; fall through to String() */ }
  }
  if (!bits.length) {
    const s = String(e);
    bits.push(s === '[object Object]' ? 'an object carrying no readable properties' : s);
  }
  return bits.join(': ');
}

/** Reject if `promise` has not settled within `ms`, naming the step that stalled. */
export function withTimeout(promise, ms, what) {
  let timer;
  return Promise.race([
    promise.finally(() => clearTimeout(timer)),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`timed out after ${ms / 1000}s while ${what}`)), ms);
    }),
  ]);
}

export function startCommand(measurement, settings) {
  const bytes = [OP_START, measurement];
  for (const [id, value] of settings) {
    bytes.push(id, 0x01);
    for (let i = 0; i < SETTING_WIDTH[id]; i++) bytes.push((value >> (8 * i)) & 0xff);
  }
  return new Uint8Array(bytes);
}

export function parseHeartRate(view) {
  const flags = view.getUint8(0);
  const wide = (flags & 0x01) !== 0;
  let off = 1;
  const hr = wide ? view.getUint16(off, true) : view.getUint8(off);
  off += wide ? 2 : 1;
  if (flags & 0x08) off += 2;                      // energy expended, skipped
  const rr = [];
  if (flags & 0x10) {
    while (off + 1 < view.byteLength) {
      // RR is in 1/1024 s units, not milliseconds. Getting this wrong scales every interval by 2.3%
      // and quietly corrupts every HRV number downstream.
      rr.push(view.getUint16(off, true) * 1000 / 1024);
      off += 2;
    }
  }
  return { hr, rr };
}

function readSigned(view, offset, bytes) {
  let v = 0;
  for (let i = 0; i < bytes; i++) v |= view.getUint8(offset + i) << (8 * i);
  const sign = 1 << (8 * bytes - 1);
  return (v & sign) ? v - (1 << (8 * bytes)) : v;
}

function readSignedBits(view, byteOffset, bitPos, bits) {
  let v = 0;
  for (let i = 0; i < bits; i++) {
    const p = bitPos + i;
    v |= ((view.getUint8(byteOffset + (p >> 3)) >> (p & 7)) & 1) << i;
  }
  const sign = 1 << (bits - 1);
  return (v & sign) ? v - (1 << bits) : v;
}

export function parseAccFrame(view) {
  if (view.getUint8(0) !== MEAS_ACC) return null;
  const frameType = view.getUint8(9);
  const compressed = (frameType & COMPRESSED_BIT) !== 0;
  const layout = frameType & 0x7f;
  const samples = [];
  let off = 10;

  if (!compressed) {
    const bytesPer = layout === 0 ? 1 : layout === 1 ? 2 : 3;
    while (off + bytesPer * 3 <= view.byteLength) {
      const xyz = [];
      for (let c = 0; c < 3; c++) { xyz.push(readSigned(view, off, bytesPer)); off += bytesPer; }
      samples.push(xyz);
    }
    return samples;
  }

  if (layout !== 0x01) return samples;             // only the 16-bit reference layout is emitted
  const current = [];
  for (let c = 0; c < 3; c++) { current.push(readSigned(view, off, 2)); off += 2; }
  samples.push(current.slice());

  while (off + 2 <= view.byteLength) {
    const bits = view.getUint8(off), count = view.getUint8(off + 1);
    off += 2;
    if (!bits || !count) break;
    const need = Math.ceil(bits * 3 * count / 8);
    if (off + need > view.byteLength) break;
    let bitPos = 0;
    for (let s = 0; s < count; s++) {
      for (let c = 0; c < 3; c++) { current[c] += readSignedBits(view, off, bitPos, bits); bitPos += bits; }
      samples.push(current.slice());
    }
    off += need;
  }
  return samples;
}

/**
 * One PPI frame (measurement 3, frame type 0, uncompressed): six bytes per beat -- heart rate, the
 * interval in ms, the band's own error estimate in ms, and flags (bit 0 blocker = movement during
 * the beat; bit 1 skin contact; bit 2 skin contact supported). The layout is Polar SDK PpiData.kt.
 * Null for any other measurement or frame type.
 */
export function parsePpiFrame(view) {
  if (view.byteLength < 10 || (view.getUint8(0) & 0x3f) !== MEAS_PPI || view.getUint8(9) !== 0) return null;
  const out = [];
  for (let off = 10; off + 6 <= view.byteLength; off += 6) {
    const flags = view.getUint8(off + 5);
    out.push({ hr: view.getUint8(off), ppiMs: view.getUint16(off + 1, true),
               errMs: view.getUint16(off + 3, true), blocker: (flags & 1) === 1,
               skinContact: (flags & 2) === 2, skinSupported: (flags & 4) === 4 });
  }
  return out;
}

/** Raw counts at +/-8 G, 16-bit, to g. */
export const accMagnitude = ([x, y, z]) =>
  Math.hypot(x * 8 / 32768, y * 8 / 32768, z * 8 / 32768);

/** Whether this browser can talk to the armband at all. */
export const bluetoothAvailable = () =>
  typeof navigator !== 'undefined' && !!navigator.bluetooth;

/**
 * A connected Verity Sense.
 *
 * `hrAt` is the load-bearing field: callers must consult `hrFresh()` rather than reading `hr`
 * directly, or a band that has gone out of range keeps reporting its last value forever.
 */
export class VeritySensor {
  constructor({ onLog = () => {}, onChange = () => {}, onStep = () => {}, store = null,
                onAcc = null } = {}) {
    this.onLog = onLog;
    /// Called with ([magnitude...], arrivalSeconds) for every accelerometer frame: the arm's motion,
    /// for counting steps (fusion.js). Magnitudes are in the band's own units; the consumer
    /// normalises them against gravity.
    this.onAcc = onAcc;
    this.accError = null;
    this.accSettings = null;
    this._pmdWaiter = null;
    this._onPmdControl = e => {
      const r = parsePmdResponse(e.target.value);
      if (r && this._pmdWaiter && r.op === this._pmdWaiter.op) {
        const w = this._pmdWaiter;
        this._pmdWaiter = null;
        w.resolve(r);
      }
    };
    /// localStorage-like, optional: remembers which band last streamed (see ARMBAND_KEY).
    this.store = store;
    /// What the browser last said it remembers. The page reads this to decide whether a Connect tap
    /// should go straight to the picker -- which has to happen inside the tap, before any await.
    this.lastKnown = null;
    this.onChange = onChange;
    // Named so a failure can say which step it stopped at. "Nothing happened" is not a diagnosis,
    // and on a phone there is no console to go and look in.
    this.onStep = onStep;
    this.step = 'idle';
    this.device = null;
    this.hr = null;
    this.hrAt = 0;
    this.rr = [];
    this.battery = null;
    this.batteryAt = 0;
    this.batteryChar = null;
    this.accWindow = [];
    this.accSd = null;
    this.connected = false;
    this.reconnecting = false;
    /// True while autoConnect is waiting for the band to appear.
    this.looking = false;
    this.hasAcc = false;
    /// The last thing that went wrong, kept rather than thrown away: on a phone there is no console
    /// and the diagnostics report is the only way a failure reaches anyone who can fix it.
    this.lastError = null;
    /// Counters, because "connected" and "actually sending data" are different states and only one
    /// of them is worth starting a run on.
    this.hrCount = 0;
    this.rrCount = 0;
    this.accFrames = 0;
    /// Link history, for the session record: why it dropped, and how long it took to come back.
    this.events = [];
    this._losses = [];
    this.accShed = false;
    this.hrZeros = 0;
    this.acquiringUntil = 0;
    /// Characteristic objects already listened to. A browser can hand back the SAME object after a
    /// reconnect, and adding a fresh listener each time made every frame arrive once per reconnect.
    this._wired = new WeakSet();
    this.ppiCount = 0;
    this.ppiOn = false;
    this.onPpi = null;
    this.connectedAt = 0;
    /// Set once this instance is finished with. Every background loop checks it, so a replaced
    /// sensor stops trying to reach the band -- before, each tap of Connect left the previous
    /// instance's reconnect loop running for ever, all of them competing for the same armband.
    this._disposed = false;
    this._listening = null;       // the device the disconnect listener is attached to
    this._onDisconnect = () => {
      if (this._disposed) return;
      this.connected = false;
      this._linkLost('disconnected');
      this.onChange();
      this.onLog('armband disconnected — retrying', 'bad');
      this._reconnect();
    };
    this._stallTimer = null;
  }

  /** Everything the diagnostics report needs to tell a silent band from a broken page. */
  state() {
    return {
      step: this.step,
      connected: this.connected,
      reconnecting: this.reconnecting,
      deviceName: this.device ? (this.device.name || '(unnamed)') : null,
      deviceId: this.device ? String(this.device.id || '').slice(0, 8) : null,
      gattConnected: !!(this.device && this.device.gatt && this.device.gatt.connected),
      hasAcc: this.hasAcc,
      accError: this.accError || null,
      accSettings: this.accSettings || null,
      battery: this.battery,
      batteryAgeS: this.batteryAt ? Math.round((Date.now() - this.batteryAt) / 1000) : null,
      batteryLow: this.battery != null && this.battery <= BATTERY_LOW_PCT,
      hr: this.hr,
      hrAgeMs: this.hrAt ? Date.now() - this.hrAt : null,
      hrCount: this.hrCount,
      rrCount: this.rrCount,
      accFrames: this.accFrames,
      accShed: this.accShed,
      hrZeros: this.hrZeros,
      linkEvents: this.events.slice(-20),
      connectedForS: this.connectedAt ? Math.round((Date.now() - this.connectedAt) / 1000) : null,
      lastError: this.lastError ? describeError(this.lastError) : null,
    };
  }

  hrFresh(now = Date.now()) {
    return this.hr != null && (now - this.hrAt) < STALE_HR_MS;
  }

  /**
   * Re-read the battery, at most every `BATTERY_POLL_MS` unless forced.
   *
   * Returns the percentage, or null if it could not be read. Never throws: a battery read failing
   * mid-run is not a reason to take anything else down, and a stale number is better than a crash.
   */
  async readBattery({ now = Date.now(), force = false } = {}) {
    if (!this.batteryChar) return this.battery;
    if (!force && this.batteryAt && now - this.batteryAt < BATTERY_POLL_MS) return this.battery;
    try {
      const v = await this.batteryChar.readValue();
      this.battery = v.getUint8(0);
      this.batteryAt = now;
      this.onChange();
    } catch (e) {
      this.lastError = e;
    }
    return this.battery;
  }

  /** SD of accelerometer magnitude over the last second, or null. Cleared each call. */
  takeAccSd() {
    if (this.accWindow.length < 5) { this.accWindow = []; return null; }
    const mean = this.accWindow.reduce((a, b) => a + b, 0) / this.accWindow.length;
    const sd = Math.sqrt(
      this.accWindow.reduce((a, b) => a + (b - mean) ** 2, 0) / this.accWindow.length);
    this.accWindow = [];
    this.accSd = sd;
    return sd;
  }

  _at(step) { this.step = step; this.onStep(step); }

  /**
   * Devices this browser has already been given permission for.
   *
   * Bluefy's picker offers "Allow this website to establish future background connections with
   * selected device", and when that is on the permission is remembered — so the device can be
   * reached again with no picker at all. That matters more than convenience here: on the device in
   * question the picker appears, lists the armband, and then `requestDevice` never settles when the
   * row is tapped. The promise stays pending for ever, the step stays at "asking for the device",
   * and nothing distinguishes it from a hang. Going through the remembered list skips the part that
   * is broken.
   *
   * `getDevices` is not universally implemented, so its absence is a normal outcome, not an error.
   */
  async remembered() {
    if (!navigator.bluetooth || !navigator.bluetooth.getDevices) { this.lastKnown = []; return []; }
    try {
      const list = await withTimeout(navigator.bluetooth.getDevices(), 5000, 'listing known devices');
      this.lastKnown = list || [];
      return this.lastKnown;
    } catch (e) {
      this.lastError = e;
      this.lastKnown = [];
      return [];
    }
  }

  /**
   * Remembered devices worth trying, best first: the band that last streamed (by id), then anything
   * named like a Polar band, then -- if there is exactly one remembered device -- that one.
   */
  candidates(known) {
    let last = null;
    try { last = JSON.parse((this.store && this.store.getItem(ARMBAND_KEY)) || 'null'); } catch { /* none */ }
    const out = [];
    const add = d => { if (d && !out.includes(d)) out.push(d); };
    if (last && last.id) add((known || []).find(d => d.id && d.id === last.id));
    for (const d of known || []) if (/polar|verity|sense/i.test(d.name || '')) add(d);
    if ((known || []).length === 1) add(known[0]);
    return out;
  }

  _rememberGood() {
    if (!this.store || !this.device) return;
    try {
      this.store.setItem(ARMBAND_KEY, JSON.stringify({ id: this.device.id || null,
                                                       name: this.device.name || null,
                                                       at: new Date().toISOString() }));
    } catch { /* storage blocked */ }
  }

  /**
   * Connect to the armband.
   *
   * `acceptAllDevices` is the fallback rather than the default: a name filter keeps the picker to
   * the armband. But a filter is also a thing that can fail to match — a device whose advertised
   * name differs from its display name will be listed and then not selectable — so it has to be
   * possible to try without one.
   */
  /** Open the picker and return whatever was chosen. */
  async _ask(acceptAll) {
    this._at('asking for the device');
    const options = acceptAll
      ? { acceptAllDevices: true }
      // Two filters, not one. A device may advertise its heart-rate service without a name the
      // prefix matches, or the reverse; either alone is a picker that shows nothing, or shows a row
      // that cannot be chosen.
      : { filters: [{ namePrefix: 'Polar' }, { services: [HR_SERVICE] }] };
    // PSFTP: the band's file service, for reading back what it recorded to its own memory
    // (polar-offline.js). A band remembered before this was added may need picking once more.
    options.optionalServices = [HR_SERVICE, BATTERY_SERVICE, PMD_SERVICE, PSFTP_SERVICE];

    // The picker is a human waiting to tap, so the budget is generous — but not unbounded. An
    // unbounded wait is what produced "asking for the device" and nothing else, for ever.
    return withTimeout(
      navigator.bluetooth.requestDevice(options), PICKER_TIMEOUT_MS,
      'waiting for the device picker (it never returned the device you tapped)');
  }

  async connect({ acceptAll = false, usePicker = true, skipRemembered = false } = {}) {
    this.lastError = null;
    this.device = null;

    // Straight to the picker when the page already knows nothing is remembered. The picker has to be
    // opened inside the tap: awaiting getDevices first can let the tap's permission lapse, and the
    // picker then refuses to open at all.
    if (!skipRemembered) {
      // Anything already permitted, first. No picker, no tap, and it survives a reload. Every
      // plausible entry is tried, the one that last streamed first: a stale entry (a band that was
      // reset, a permission granted twice) must not block a good one behind it.
      const list = this.candidates(await this.remembered());
      for (const d of list) {
        this.device = d;
        this._at(`remembered ${d.name || 'device'}`);
        try {
          return await this._finishConnect();
        } catch (e) {
          this.lastError = e;
          this.onLog(`the remembered device did not connect (${describeError(e)})`, 'bad');
          try { d.gatt.disconnect(); } catch { /* nothing open */ }
        }
      }
      if (!usePicker) {
        throw this.lastError || new Error('no remembered device, and the picker was not allowed');
      }
      if (list.length) this.onLog('asking for the armband again', 'bad');
    }

    this.device = await this._ask(acceptAll);
    if (!this.device) throw new Error('no device was chosen');
    return this._finishConnect();
  }

  async _finishConnect({ attempts = GATT_ATTEMPTS, timeoutMs = CONNECT_TIMEOUT_MS } = {}) {
    this._at(`selected ${this.device.name || 'device'}`);
    this._listen();
    const server = await this._openGatt({ attempts, timeoutMs });
    this._at('connected, looking for heart rate');
    await withTimeout(this._attachHr(server), CONNECT_TIMEOUT_MS, 'setting up heart-rate notifications');
    this.connected = true;
    this.connectedAt = Date.now();
    this._at('streaming');
    this._rememberGood();
    this.onChange();
    // Not awaited: heart rate is what a run needs, and it is already flowing.
    this._attachExtras(server);
    this._startStallWatch();
  }

  /** One disconnect listener, on the current device only. */
  _listen() {
    if (this._listening === this.device) return;
    if (this._listening) {
      try { this._listening.removeEventListener('gattserverdisconnected', this._onDisconnect); } catch { /* gone */ }
    }
    this.device.addEventListener('gattserverdisconnected', this._onDisconnect);
    this._listening = this.device;
  }

  /**
   * Connect to the remembered armband with no picker and no tap, waiting for it to appear.
   *
   * It is the only Bluetooth device this app ever talks to, so there is nothing to choose: once the
   * browser remembers it, switching the band on should be enough. Looks every few seconds for
   * `windowMs` (using the band's own advertisements to wake up early where the browser offers them),
   * one connection attempt per look so a band that is still booting is not hammered. Returns true
   * when streaming, false when there is no remembered band or it never appeared.
   */
  async autoConnect({ windowMs = AUTO_CONNECT_WINDOW_MS, retryMs = AUTO_CONNECT_RETRY_MS,
                      now = () => Date.now() } = {}) {
    let list = this.candidates(await this.remembered());
    if (!list.length) return false;
    this.device = list[0];
    const name = list[0].name || 'your armband';
    const until = now() + windowMs;
    let look = 0;
    this.looking = true;
    try {
      while (!this._disposed && now() < until) {
        look += 1;
        // Rotate through the plausible entries, and every few looks ask the browser again: the
        // device object itself can go stale while the band is perfectly fine.
        if (look > 1 && look % REACQUIRE_AFTER === 0) {
          const fresh = this.candidates(await this.remembered());
          if (fresh.length) list = fresh;
        }
        this.device = list[(look - 1) % list.length];
        try {
          if (look > 1) this._at(`looking for ${name} — is it switched on?`);
          await this._finishConnect({ attempts: 1, timeoutMs: LOOK_TIMEOUT_MS });
          return true;
        } catch (e) {
          this.lastError = e;
          try { this.device.gatt.disconnect(); } catch { /* nothing open */ }
        }
        if (this._disposed || now() >= until) break;
        await this._waitForAdvert(retryMs);
      }
    } finally {
      this.looking = false;
    }
    if (!this._disposed) this._at(`${name} not found`);
    return false;
  }

  /** Wait until the band advertises (where the browser can tell us) or `ms` passes. */
  async _waitForAdvert(ms) {
    const d = this.device;
    if (!d || typeof d.watchAdvertisements !== 'function') {
      await new Promise(r => setTimeout(r, ms));
      return;
    }
    await new Promise(resolve => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        try { d.removeEventListener('advertisementreceived', finish); } catch { /* fine */ }
        resolve();
      };
      d.addEventListener('advertisementreceived', finish);
      Promise.resolve().then(() => d.watchAdvertisements()).catch(() => {});
      setTimeout(finish, ms);
    });
  }

  /** A heart-rate stream that stops while the link claims to be up: rebuild the link. */
  _startStallWatch() {
    if (this._stallTimer || typeof setInterval !== 'function') return;
    this._stallTimer = setInterval(() => this.checkStall(), 5000);
    if (this._stallTimer && this._stallTimer.unref) this._stallTimer.unref();
  }

  /** Returns true when it acted. Exposed for testing; the interval above calls it. */
  checkStall(now = Date.now()) {
    if (this._disposed || !this.connected || this.reconnecting) return false;
    // Measured from the later of the last reading and the last (re)connect, so a rebuilt link gets a
    // fresh twenty seconds rather than being torn down again five seconds later.
    const last = Math.max(this.hrAt, this.connectedAt || 0);
    if (!this.hrCount || now - last < HR_STALL_MS) return false;
    this.onLog(`no heart rate for ${Math.round((now - last) / 1000)} s while connected — `
               + 'reconnecting', 'bad');
    this.connected = false;
    this._linkLost('stalled', now);
    this.onChange();
    try { this.device.gatt.disconnect(); } catch { /* already down */ }
    this._reconnect();
    return true;
  }

  _event(kind, detail = null, at = Date.now()) {
    this.events.push({ at, kind, ...(detail ? { detail } : {}) });
    if (this.events.length > 200) this.events.splice(0, this.events.length - 200);
  }

  /**
   * The link went. Recorded, and if it keeps going while the accelerometer is streaming, the
   * accelerometer is stopped for the rest of this connection's life: it is the one thing on the link
   * that is optional. On 24 October -- the first run with it streaming at 52 Hz -- the link dropped
   * nine times in 26 minutes, against twice on 22 October without it. That is not proof, but heart
   * rate is the signal the session is governed by, and arm steps are a refinement of pace that the
   * phone's own motion and GPS already cover.
   */
  _linkLost(kind, now = Date.now()) {
    this._event(kind, null, now);
    this._losses = this._losses.filter(t => now - t < SHED_WINDOW_MS);
    this._losses.push(now);
    if (!this.accShed && this.hasAcc && this._losses.length >= SHED_AFTER_LOSSES) {
      this.accShed = true;
      this.hasAcc = false;
      this.accError = 'stopped after repeated link losses, to keep heart rate';
      this._event('acc-shed', null, now);
      this.onLog('the armband link keeps dropping — stopping its motion stream to keep heart rate', 'bad');
    }
  }

  /** Finished with: stop every loop, release the band, forget the device. */
  dispose() {
    this._disposed = true;
    // Stop the accelerometer stream so the next connection does not find it "already on".
    if (this._pmdControl) {
      const c = this._pmdControl;
      const send = cmd => Promise.resolve(typeof c.writeValueWithResponse === 'function'
        ? c.writeValueWithResponse(cmd) : c.writeValue(cmd));
      try {
        // In sequence: a second write before the first is answered is refused as "operation in progress".
        send(new Uint8Array([OP_STOP, MEAS_ACC])).catch(() => {})
          .then(() => (this.ppiOn ? send(new Uint8Array([OP_STOP, MEAS_PPI])) : null)).catch(() => {});
      } catch { /* gone */ }
      this._pmdControl = null;
      this._pmd = null;
      this._psftp = null;
      this.ppiOn = false;
      this.onPpi = null;
    }
    if (this._stallTimer) { clearInterval(this._stallTimer); this._stallTimer = null; }
    if (this._listening) {
      try { this._listening.removeEventListener('gattserverdisconnected', this._onDisconnect); } catch { /* gone */ }
      this._listening = null;
    }
    try { this.device?.gatt?.disconnect(); } catch { /* already gone */ }
    this.device = null;
    this.connected = false;
    this.reconnecting = false;
    this.onChange();
  }

  /**
   * Open the GATT link, retrying, and tolerating a bridge that lies about the outcome.
   *
   * Two behaviours here are specific to what actually happened rather than to the specification:
   *
   *   - A rejection is not proof of failure. Some bridges reject the promise while the link is up;
   *     `gatt.connected` is the ground truth, so it is checked before the attempt is written off.
   *   - A failed attempt leaves state behind. Disconnecting before retrying is what makes the second
   *     attempt a fresh one rather than the first one's wreckage.
   */
  async _openGatt({ attempts = GATT_ATTEMPTS, timeoutMs = CONNECT_TIMEOUT_MS } = {}) {
    const gatt = this.device.gatt;
    if (!gatt) {
      throw new Error('the browser gave back a device with no GATT server, which means it cannot '
                    + 'open a connection to it at all');
    }
    if (gatt.connected) {
      this._at('already connected');
      return gatt;
    }

    let last = null;
    for (let attempt = 1; attempt <= attempts; attempt++) {
      this._at(attempt === 1 ? 'connecting' : `connecting — attempt ${attempt} of ${attempts}`);
      try {
        return await withTimeout(gatt.connect(), timeoutMs,
                                 'opening the connection to the band');
      } catch (e) {
        last = e;
        this.lastError = e;
        // `gatt.connected` outranks the promise. If the link is up, the rejection was noise.
        if (gatt.connected) {
          this.onLog('the connect call reported an error but the link is up — continuing', 'on');
          return gatt;
        }
        if (attempts > 1) this.onLog(`attempt ${attempt} of ${attempts} failed: ${describeError(e)}`, 'bad');
        try { gatt.disconnect(); } catch { /* nothing to tear down */ }
        if (attempt < attempts) {
          await new Promise(r => setTimeout(r, GATT_RETRY_MS * attempt));
        }
      }
    }
    throw new Error(`could not open a connection after ${attempts} attempt${attempts === 1 ? '' : 's'}. `
                  + `Last: ${describeError(last)}. `
                  + 'The usual cause is another app holding the band — force-quit Polar Flow. '
                  + 'Otherwise press the band\'s button once to wake it and try again.');
  }

  async _reconnect() {
    if (this.reconnecting || !this.device) return;
    this.reconnecting = true;
    let delay = 1000;
    let failures = 0;
    while (!this._disposed && this.device && !this.device.gatt.connected) {
      await new Promise(r => setTimeout(r, delay));
      if (this._disposed || !this.device) break;
      // Every few failures, a fresh device object from the browser's remembered list. The one in
      // hand can have been invalidated by the bridge while the band itself is fine and in range.
      if (failures && failures % REACQUIRE_AFTER === 0) {
        const fresh = this.candidates(await this.remembered())[0];
        if (fresh && fresh !== this.device && !this._disposed) {
          this.device = fresh;
          this._listen();
          this.onLog('trying the armband afresh', 'dim');
        }
      }
      try {
        // Timed out here too, or one hung attempt ends the retry loop permanently. One short attempt
        // per turn of this loop: the loop is the retry, and a 20 s x 3 attempt inside it was most of
        // a 40-second gap.
        const server = await this._openGatt({ attempts: 1, timeoutMs: RECONNECT_ATTEMPT_MS });
        await withTimeout(this._attachHr(server), CONNECT_TIMEOUT_MS, 'resubscribing');
        this.connected = true;
        this.connectedAt = Date.now();
        const lost = [...this.events].reverse().find(e => e.kind === 'disconnected' || e.kind === 'stalled');
        this._event('reconnected', lost ? { afterMs: this.connectedAt - lost.at, attempts: failures + 1 } : null);
        this.onChange();
        this.onLog('armband reconnected', 'on');
        this._rememberGood();
        this._attachExtras(server);
        break;
      } catch {
        failures += 1;
        // Backs off to 8 s and stays there. Retrying every second for an hour drains the battery
        // for nothing — the band is either back in range or it is not.
        delay = Math.min(delay * 2, 8000);
      }
    }
    this.reconnecting = false;
  }

  async _attachHr(server) {
    let hrService;
    try {
      hrService = await server.getPrimaryService(HR_SERVICE);
    } catch (e) {
      // Name the step. Without this the whole connect reads as "nothing happened".
      throw new Error(`heart-rate service not found (${describeError(e)}). `
                    + 'The band may be in a mode that does not expose it — press its button once '
                    + 'so the heart symbol is lit, then reconnect.');
    }
    const hrChar = await hrService.getCharacteristic(HR_CHAR);
    this._at('subscribing to heart rate');
    await hrChar.startNotifications();
    if (this._wired.has(hrChar)) return;
    this._wired.add(hrChar);
    hrChar.addEventListener('characteristicvaluechanged', e => this._onHr(parseHeartRate(e.target.value)));
  }

  /**
   * One heart-rate notification. Zero is not a heart rate -- it is the band saying it has none -- and
   * it was being recorded as one (two 0 bpm samples on 24 October). It starts the re-acquisition
   * window instead: readings in the next HR_ACQUIRE_MS are counted but not believed.
   */
  _onHr({ hr, rr }, now = Date.now()) {
    this.hrCount += 1;
    if (!(hr > 0)) {
      this.hrZeros += 1;
      if (now >= this.acquiringUntil) this._event('hr-zero', null, now);
      this.acquiringUntil = now + HR_ACQUIRE_MS;
      this.onChange();
      return;
    }
    if (now < this.acquiringUntil) { this.onChange(); return; }
    this.hr = hr;
    this.hrAt = now;
    if (rr.length) { this.rr.push(...rr); this.rrCount += rr.length; }
    if (this.rr.length > 600) this.rr.splice(0, this.rr.length - 600);
    this.onChange();
  }

  /**
   * Battery and accelerometer: best-effort, each with its own short timeout, never able to fail the
   * connection. Heart rate is already streaming by the time this runs.
   */
  async _attachExtras(server) {
    try {
      await withTimeout(this._attachBattery(server), EXTRA_TIMEOUT_MS, 'reading the battery');
    } catch { /* optional */ }
    if (this.accShed) { this.onChange(); return; }
    try {
      await withTimeout(this._attachAcc(server), ACC_TIMEOUT_MS, 'starting the accelerometer');
      this.hasAcc = true;
      this.accError = null;
    } catch (e) {
      this.hasAcc = false;
      // Kept for the diagnostics: "no accelerometer" alone cannot tell a band that refuses raw
      // motion outside Polar's SDK mode from a bridge that cannot write the start command.
      this.accError = describeError(e);
    }
    this.onChange();
  }

  async _attachBattery(server) {
    const bs = await server.getPrimaryService(BATTERY_SERVICE);
    // Kept, not discarded after the first read. Re-reading needs the characteristic, and going
    // back through getPrimaryService every five minutes during a run is work the radio does not
    // need to do.
    this.batteryChar = await bs.getCharacteristic(BATTERY_CHAR);
    await this.readBattery();
  }

  /** Write a PMD request and wait for the band's answer to it. */
  _pmdRequest(control, bytes, timeoutMs = 3000) {
    const cmd = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    return withTimeout(new Promise((resolve, reject) => {
      this._pmdWaiter = { op: cmd[0], resolve };
      const w = typeof control.writeValueWithResponse === 'function'
        ? control.writeValueWithResponse(cmd) : control.writeValue(cmd);
      Promise.resolve(w).catch(reject);
    }), timeoutMs, `the band's answer to the ${['', 'settings', 'start', 'stop'][cmd[0]] || ''} request`);
  }

  // Accelerometer is best-effort. Without it the heart rate still works; what is lost is the
  // movement evidence the not-worn and frozen detectors need, and the arm's step count.
  //
  // Normal mode streams it (52 Hz, +/-8 g, per Polar's Verity Sense documentation); SDK mode is NOT
  // used, because it switches off every on-device algorithm, heart rate included. The sequence is
  // Polar's own: ask which settings the band supports, start with exactly those, and if the band
  // says it is already streaming (an earlier connection left it on), stop and start again. A bridge
  // that passes on no answers at all still gets a blind start, judged by whether frames arrive.
  /**
   * The measurement service's two characteristics, subscribed once per connection. Every stream
   * shares the one data characteristic, so its listener routes each frame by measurement type.
   */
  async _pmdChannel(server) {
    if (this._pmd && this._pmd.server === server) return this._pmd;
    const pmd = await server.getPrimaryService(PMD_SERVICE);
    const control = await pmd.getCharacteristic(PMD_CONTROL);
    const data = await pmd.getCharacteristic(PMD_DATA);
    await control.startNotifications();
    control.addEventListener('characteristicvaluechanged', this._onPmdControl);
    await data.startNotifications();
    if (!this._wired.has(data)) {
      this._wired.add(data);
      data.addEventListener('characteristicvaluechanged', e => this._onPmdData(e.target.value));
    }
    this._pmdControl = control;
    this._pmd = { server, control, data };
    return this._pmd;
  }

  /** A frame on the shared measurement channel, routed by its measurement type. */
  _onPmdData(v) {
    const samples = parseAccFrame(v);
    if (samples) {
      if (this.accShed) return;                         // stopped by _linkLost; stragglers ignored
      this.accFrames += 1;
      const mags = samples.map(accMagnitude);
      for (const m of mags) this.accWindow.push(m);
      if (this.onAcc) { try { this.onAcc(mags, Date.now() / 1000); } catch { /* consumer's problem */ } }
      return;
    }
    const beats = parsePpiFrame(v);
    if (beats) {
      this.ppiCount += beats.length;
      if (this.onPpi) { try { this.onPpi(beats, Date.now() / 1000); } catch { /* consumer's problem */ } }
    }
  }

  async _attachAcc(server) {
    this._pmd = null;                                   // a new connection: subscribe afresh
    const { control } = await this._pmdChannel(server);

    let settings, answered = true;
    try {
      const r = await this._pmdRequest(control, [OP_GET_SETTINGS, MEAS_ACC]);
      if (r.status !== 0) throw new Error(`the band refused the accelerometer settings request (${r.statusText})`);
      settings = chooseAccSettings(r.settings);
    } catch (e) {
      if (/refused/.test(e.message)) throw e;
      answered = false;
      settings = [...ACC_SETTINGS, [SETTING.channels, 3]];
    }
    this.accSettings = settings.map(([id, v]) => `${['rate', 'bits', 'range', '', 'channels'][id] || id}=${v}`).join(' ');

    if (answered) {
      let r = await this._pmdRequest(control, startCommand(MEAS_ACC, settings));
      if (r.status === 6) {
        await this._pmdRequest(control, [OP_STOP, MEAS_ACC]).catch(() => null);
        r = await this._pmdRequest(control, startCommand(MEAS_ACC, settings));
      }
      if (r.status !== 0) throw new Error(`the band refused to start the accelerometer (${r.statusText})`);
    } else {
      const cmd = startCommand(MEAS_ACC, settings);
      if (typeof control.writeValueWithResponse === 'function') await control.writeValueWithResponse(cmd);
      else await control.writeValue(cmd);
      const before = this.accFrames;
      await new Promise(r => setTimeout(r, 3000));
      if (this.accFrames === before) {
        throw new Error('the accelerometer was started blind (no answers from the bridge) and sent nothing');
      }
    }
  }

  /**
   * Beat-to-beat intervals, for a resting HRV check. Polar is explicit that PPI "cannot be measured
   * accurately during activity" and "should only be used at complete rest", and while it streams the
   * band updates its heart rate only every five seconds -- so this is for lying still, never for a
   * run. The first beats arrive about 25 s after the start. `onPpi(beats, arrivalSeconds)`.
   */
  async startPpi(onPpi) {
    if (!this.connected || !this.device || !this.device.gatt) throw new Error('the armband is not connected');
    // The channel the accelerometer opened on this connection when there is one (it is subscribed
    // already); otherwise open it now.
    const { control } = this._pmd || await this._pmdChannel(this.device.gatt);
    this.onPpi = onPpi;
    let r = await this._pmdRequest(control, [OP_START, MEAS_PPI]);
    if (r.status === 6) {                               // left on by an earlier check
      await this._pmdRequest(control, [OP_STOP, MEAS_PPI]).catch(() => null);
      r = await this._pmdRequest(control, [OP_START, MEAS_PPI]);
    }
    if (r.status !== 0) {
      this.onPpi = null;
      throw new Error(`the band refused to start beat-to-beat intervals (${r.statusText})`);
    }
    this.ppiOn = true;
  }

  async stopPpi() {
    this.onPpi = null;
    if (!this.ppiOn) return;
    this.ppiOn = false;
    if (this._pmd) await this._pmdRequest(this._pmd.control, [OP_STOP, MEAS_PPI]).catch(() => null);
  }

  /**
   * The measurement control point as polar-offline.js wants it: `request(bytes)` resolving with the
   * band's answer (its `raw` bytes carried). Null when not connected.
   */
  async pmdPort() {
    if (!this.connected || !this.device || !this.device.gatt) return null;
    const { control } = this._pmd || await this._pmdChannel(this.device.gatt);
    return { request: bytes => this._pmdRequest(control, bytes, 5000) };
  }

  /** The band's file service (PSFTP), one client per connection. */
  async fileClient() {
    if (!this.connected || !this.device || !this.device.gatt) return null;
    const server = this._pmd ? this._pmd.server : this.device.gatt;
    if (!this._psftp || this._psftp.server !== server) {
      this._psftp = { server, client: await PsFtpClient.fromServer(server) };
    }
    return this._psftp.client;
  }

  /** The athlete's Disconnect. Same as dispose: nothing should keep trying after it. */
  disconnect() { this.dispose(); }
}
