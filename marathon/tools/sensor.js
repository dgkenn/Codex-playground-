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
export const HR_SERVICE = '0000180d-0000-1000-8000-00805f9b34fb';
export const HR_CHAR = '00002a37-0000-1000-8000-00805f9b34fb';
export const BATTERY_SERVICE = '0000180f-0000-1000-8000-00805f9b34fb';
export const BATTERY_CHAR = '00002a19-0000-1000-8000-00805f9b34fb';
export const PMD_SERVICE = 'fb005c80-02e7-f387-1cad-8acd2d8df0c8';
export const PMD_CONTROL = 'fb005c81-02e7-f387-1cad-8acd2d8df0c8';
export const PMD_DATA = 'fb005c82-02e7-f387-1cad-8acd2d8df0c8';

const MEAS_ACC = 0x02, OP_START = 0x02;
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

/// A heart rate older than this is a memory, not a measurement. The band sends at about 1 Hz, so
/// five seconds is four missed notifications — comfortably past noise.
export const STALE_HR_MS = 5000;

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
  constructor({ onLog = () => {}, onChange = () => {}, onStep = () => {} } = {}) {
    this.onLog = onLog;
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
    this.accWindow = [];
    this.accSd = null;
    this.connected = false;
    this.reconnecting = false;
    this.hasAcc = false;
    /// The last thing that went wrong, kept rather than thrown away: on a phone there is no console
    /// and the diagnostics report is the only way a failure reaches anyone who can fix it.
    this.lastError = null;
    /// Counters, because "connected" and "actually sending data" are different states and only one
    /// of them is worth starting a run on.
    this.hrCount = 0;
    this.rrCount = 0;
    this.accFrames = 0;
    this.connectedAt = 0;
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
      battery: this.battery,
      hr: this.hr,
      hrAgeMs: this.hrAt ? Date.now() - this.hrAt : null,
      hrCount: this.hrCount,
      rrCount: this.rrCount,
      accFrames: this.accFrames,
      connectedForS: this.connectedAt ? Math.round((Date.now() - this.connectedAt) / 1000) : null,
      lastError: this.lastError ? describeError(this.lastError) : null,
    };
  }

  hrFresh(now = Date.now()) {
    return this.hr != null && (now - this.hrAt) < STALE_HR_MS;
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
    if (!navigator.bluetooth || !navigator.bluetooth.getDevices) return [];
    try {
      return await withTimeout(navigator.bluetooth.getDevices(), 5000, 'listing known devices');
    } catch (e) {
      this.lastError = e;
      return [];
    }
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
    options.optionalServices = [HR_SERVICE, BATTERY_SERVICE, PMD_SERVICE];

    // The picker is a human waiting to tap, so the budget is generous — but not unbounded. An
    // unbounded wait is what produced "asking for the device" and nothing else, for ever.
    return withTimeout(
      navigator.bluetooth.requestDevice(options), PICKER_TIMEOUT_MS,
      'waiting for the device picker (it never returned the device you tapped)');
  }

  async connect({ acceptAll = false, usePicker = true } = {}) {
    this.lastError = null;
    this.device = null;

    // Anything already permitted, first. No picker, no tap, and it survives a reload.
    const known = await this.remembered();
    const match = known.find(d => /polar|verity|sense/i.test(d.name || ''))
               || (known.length === 1 ? known[0] : null);

    if (match) {
      // A remembered device can be a stale entry — the permission outlives the pairing, and a band
      // that has since been reset or given to someone else is still in the list. So a failure here
      // falls through to the picker rather than ending the attempt: otherwise one bad entry blocks
      // the only other route in, permanently, with no way to clear it from a phone.
      this.device = match;
      this._at(`remembered ${match.name || 'device'}`);
      try {
        return await this._finishConnect();
      } catch (e) {
        this.lastError = e;
        if (!usePicker) throw e;
        this.onLog(`the remembered device did not connect (${describeError(e)}) — asking again`,
                   'bad');
      }
    } else if (!usePicker) {
      throw new Error('no remembered device, and the picker was not allowed');
    }

    this.device = await this._ask(acceptAll);
    if (!this.device) throw new Error('no device was chosen');
    return this._finishConnect();
  }

  async _finishConnect() {
    this._at(`selected ${this.device.name || 'device'}`);
    this.device.addEventListener('gattserverdisconnected', () => {
      this.connected = false;
      this.onChange();
      this.onLog('armband disconnected — retrying', 'bad');
      this._reconnect();
    });
    const server = await this._openGatt();
    this._at('connected, looking for heart rate');
    await withTimeout(this._attach(server), CONNECT_TIMEOUT_MS, 'setting up heart-rate notifications');
    this.connected = true;
    this.connectedAt = Date.now();
    this._at('streaming');
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
  async _openGatt() {
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
    for (let attempt = 1; attempt <= GATT_ATTEMPTS; attempt++) {
      this._at(attempt === 1 ? 'connecting' : `connecting — attempt ${attempt} of ${GATT_ATTEMPTS}`);
      try {
        return await withTimeout(gatt.connect(), CONNECT_TIMEOUT_MS,
                                 'opening the connection to the band');
      } catch (e) {
        last = e;
        this.lastError = e;
        // `gatt.connected` outranks the promise. If the link is up, the rejection was noise.
        if (gatt.connected) {
          this.onLog('the connect call reported an error but the link is up — continuing', 'on');
          return gatt;
        }
        this.onLog(`attempt ${attempt} of ${GATT_ATTEMPTS} failed: ${describeError(e)}`, 'bad');
        try { gatt.disconnect(); } catch { /* nothing to tear down */ }
        if (attempt < GATT_ATTEMPTS) {
          await new Promise(r => setTimeout(r, GATT_RETRY_MS * attempt));
        }
      }
    }
    throw new Error(`could not open a connection after ${GATT_ATTEMPTS} attempts. `
                  + `Last: ${describeError(last)}. `
                  + 'The usual cause is another app holding the band — force-quit Polar Flow. '
                  + 'Otherwise press the band\'s button once to wake it and try again.');
  }

  async _reconnect() {
    if (this.reconnecting || !this.device) return;
    this.reconnecting = true;
    let delay = 1000;
    while (this.device && !this.device.gatt.connected) {
      await new Promise(r => setTimeout(r, delay));
      try {
        // Timed out here too, or one hung attempt ends the retry loop permanently.
        const server = await this._openGatt();
        await withTimeout(this._attach(server), CONNECT_TIMEOUT_MS, 'resubscribing');
        this.connected = true;
        this.onChange();
        this.onLog('armband reconnected', 'on');
        break;
      } catch {
        // Backs off to 8 s and stays there. Retrying every second for an hour drains the battery
        // for nothing — the band is either back in range or it is not.
        delay = Math.min(delay * 2, 8000);
      }
    }
    this.reconnecting = false;
  }

  async _attach(server) {
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
    hrChar.addEventListener('characteristicvaluechanged', e => {
      const { hr, rr } = parseHeartRate(e.target.value);
      this.hr = hr;
      this.hrAt = Date.now();
      this.hrCount += 1;
      if (rr.length) { this.rr.push(...rr); this.rrCount += rr.length; }
      this.onChange();
    });

    try {
      const bs = await server.getPrimaryService(BATTERY_SERVICE);
      const v = await (await bs.getCharacteristic(BATTERY_CHAR)).readValue();
      this.battery = v.getUint8(0);
    } catch { /* optional; its absence is not a failure */ }

    // Accelerometer is best-effort. Without it the heart rate still works; what is lost is the
    // movement evidence the not-worn and frozen detectors need, and the app says so rather than
    // pretending the check ran.
    try {
      const pmd = await server.getPrimaryService(PMD_SERVICE);
      const control = await pmd.getCharacteristic(PMD_CONTROL);
      const data = await pmd.getCharacteristic(PMD_DATA);
      await control.startNotifications();
      await data.startNotifications();
      data.addEventListener('characteristicvaluechanged', e => {
        const samples = parseAccFrame(e.target.value);
        if (samples) {
          this.accFrames += 1;
          for (const s of samples) this.accWindow.push(accMagnitude(s));
        }
      });
      await control.writeValueWithResponse(startCommand(MEAS_ACC, ACC_SETTINGS));
      this.hasAcc = true;
    } catch {
      this.hasAcc = false;
    }
  }

  disconnect() {
    try { this.device?.gatt?.disconnect(); } catch { /* already gone */ }
    this.device = null;
    this.connected = false;
    this.onChange();
  }
}
