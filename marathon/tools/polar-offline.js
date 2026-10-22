// Offline heart rate on the Polar Verity Sense: recorded in the band's own memory, fetched later.
//
// Why this exists: on an iPhone the coach page can be frozen by iOS mid-run, and every second it is
// frozen is a second of heart rate that never arrived. The band keeps measuring regardless. If it
// is also told to write that heart rate to a file, the gaps can be filled after the run.
//
// Why heart rate only: Polar's documentation (SdkOfflineRecordingExplained.md) says a data type
// cannot be streamed and recorded at the same time -- except heart rate, which streams through the
// standard Heart Rate Service rather than PMD. The page already streams the accelerometer over PMD,
// so offline ACC would be refused with "already in that state".
//
// Everything below is ported from Polar's own SDK (polar-ble-sdk, Android and iOS sources), and the
// tests replay the SDK's own byte vectors. Where Android and iOS disagree, the choice is named.
// There are two transports:
//   - PMD control point (already used by sensor.js) to start/stop the recording and ask its status.
//   - PSFTP ("Polar simple file transfer", RFC76 framing over GATT) to list, read and delete files.

// --- UUIDs ---------------------------------------------------------------------------------------

/// The file-transfer service. 0xFEEE is Polar's SIG-assigned 16-bit UUID; written out in full for
/// the same reason sensor.js does (third-party WebBLE bridges reject the short alias). It must be in
/// `optionalServices` at requestDevice time or getPrimaryService throws.
export const PSFTP_SERVICE = '0000feee-0000-1000-8000-00805f9b34fb';
/// Requests go out and responses come back on this one characteristic ("MTU" in Polar's naming).
export const PSFTP_MTU_CHAR = 'fb005c51-02e7-f387-1cad-8acd2d8df0c8';
/// Device-to-host notifications (unsolicited events). The SDK enables it; nothing here reads it.
export const PSFTP_D2H_CHAR = 'fb005c52-02e7-f387-1cad-8acd2d8df0c8';
/// Host-to-device notifications (e.g. INITIALIZE_SESSION).
export const PSFTP_H2D_CHAR = 'fb005c53-02e7-f387-1cad-8acd2d8df0c8';
/// Add these to requestDevice's optionalServices (PMD is already there in sensor.js).
export const OFFLINE_OPTIONAL_SERVICES = [PSFTP_SERVICE];

// --- PMD: start / stop / status ------------------------------------------------------------------

/// PmdMeasurementType.OFFLINE_HR. Only meaningful as an offline recording; the live HR is the BLE
/// Heart Rate Service, not PMD.
export const PMD_OFFLINE_HR = 14;
/// PmdRecordingType.OFFLINE.asBitField(): the high bit of the measurement byte in a START or
/// GET_SETTINGS request. STOP does NOT carry it -- both SDKs send STOP with the bare type.
export const PMD_OFFLINE_BIT = 0x80;
export const PMD_OP = { GET_SETTINGS: 0x01, START: 0x02, STOP: 0x03, GET_STATUS: 0x05 };

/// PmdControlPointResponseCode, the full list (sensor.js's list stops at 13; 14 "disk full" matters
/// here: it is what a start returns once free memory drops under Polar's "memory limit 1").
export const PMD_ERRORS = ['success', 'invalid op code', 'invalid measurement type', 'not supported',
  'invalid length', 'invalid parameter', 'already in that state', 'invalid resolution',
  'invalid sample rate', 'invalid range', 'invalid MTU', 'invalid number of channels',
  'invalid state', 'device in charger', 'disk full', 'invalid source measurement type',
  'invalid source measurement rate', 'invalid derived measurement settings group',
  'invalid derived measurement method'];
const PMD_ALREADY = 6;

/// REQUEST_MEASUREMENT_START for offline HR: [0x02, 0x80 | 14]. No settings: the SDK passes null
/// settings for HR (its requestOfflineRecordingSettings refuses HR outright, and Polar's sample app
/// and offline_measurement.pdf both say "for PPI and HR settings are set to null"), and no secret --
/// a secret would encrypt the file, and the parser here deliberately does not decrypt.
export const offlineHrStartCommand = () => new Uint8Array([PMD_OP.START, PMD_OFFLINE_BIT | PMD_OFFLINE_HR]);
/// STOP_MEASUREMENT: [0x03, 14]. BlePMDClient.stopMeasurement sends type.numVal, no offline bit.
export const offlineHrStopCommand = () => new Uint8Array([PMD_OP.STOP, PMD_OFFLINE_HR]);
/// GET_MEASUREMENT_STATUS takes no parameters.
export const measurementStatusCommand = () => new Uint8Array([PMD_OP.GET_STATUS]);

/// Anything a caller's `request` might resolve with, as bytes. sensor.js's `_pmdRequest` resolves
/// with a parsed object that has dropped the parameters, so the integration needs the raw value;
/// an object carrying it as `.raw` is accepted too.
function toBytes(v) {
  if (v instanceof Uint8Array) return v;
  if (v instanceof ArrayBuffer) return new Uint8Array(v);
  if (ArrayBuffer.isView(v)) return new Uint8Array(v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength));
  if (Array.isArray(v)) return new Uint8Array(v);
  if (v && v.raw != null) return toBytes(v.raw);
  if (v && v.value != null) return toBytes(v.value);
  throw new Error('expected the raw control-point answer as bytes');
}

/**
 * One PMD control-point answer: [0xF0, op, measurement, status, more, params...].
 * PmdControlPointResponse: parameters only on success, `more` only on success.
 */
export function parseControlPointResponse(raw) {
  const b = toBytes(raw);
  if (b.length < 4 || b[0] !== 0xF0) return null;
  const status = b[3];
  const ok = status === 0;
  return {
    op: b[1], meas: b[2], status, ok,
    statusText: PMD_ERRORS[status] || `unknown error ${status}`,
    more: ok && b.length > 4 && b[4] !== 0,
    params: ok && b.length > 5 ? b.slice(5) : new Uint8Array(0),
  };
}

/// PmdActiveMeasurement: the top two bits of each status byte; the low six are the type.
export const MEASUREMENT_STATE = ['none', 'online', 'offline', 'online+offline'];
export const measurementState = byte => MEASUREMENT_STATE[(byte & 0xC0) >> 6];

/** GET_MEASUREMENT_STATUS parameters -> { [type]: 'none' | 'online' | 'offline' | 'online+offline' }. */
export function parseMeasurementStatus(params) {
  const out = {};
  for (const p of toBytes(params)) out[p & 0x3F] = measurementState(p);
  return out;
}

async function pmdCommand(pmd, cmd) {
  const r = parseControlPointResponse(await pmd.request(cmd));
  if (!r) throw new Error('the band sent something that is not a control-point answer');
  if (r.op !== cmd[0]) throw new Error(`answer was for op ${r.op}, not ${cmd[0]}`);
  return r;
}

/**
 * Start recording heart rate to the band's memory.
 *
 * `pmd` is anything with `request(bytes) -> Promise<raw answer bytes>` that writes WITH response to
 * the PMD control point (the SDK does) and resolves with the matching 0xF0 notification.
 *
 * "Already in that state" is returned as `{ already: true }` rather than thrown: the SDK throws, but
 * the case that matters here is a page that iOS killed and reloaded mid-run, and the recording it
 * started before is exactly the one to keep.
 */
export async function startOfflineHr(pmd) {
  const r = await pmdCommand(pmd, offlineHrStartCommand());
  if (r.status === PMD_ALREADY) return { started: false, already: true };
  if (!r.ok) {
    const why = r.status === 14 ? ' -- free memory is under the 2 MB start limit; delete old recordings'
      : r.status === 12 ? ' -- SDK mode on, first-time setup not done, or another operation running' : '';
    throw new Error(`the band refused to start offline heart rate (${r.statusText})${why}`);
  }
  return { started: true, already: false };
}

/** Per-type measurement state, straight from the band. */
export async function readMeasurementStatus(pmd) {
  const r = await pmdCommand(pmd, measurementStatusCommand());
  if (!r.ok) throw new Error(`measurement status refused (${r.statusText})`);
  return parseMeasurementStatus(r.params);
}

/** True while the band is writing heart rate to its memory. */
export async function offlineHrActive(pmd) {
  const s = (await readMeasurementStatus(pmd))[PMD_OFFLINE_HR];
  return s === 'offline' || s === 'online+offline';
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/**
 * Stop the recording, then (as both SDKs do) poll the status until the band says it has stopped:
 * Android polls every 200 ms for up to 5 s and throws on timeout. The file can still be appearing
 * for a while after that -- Polar says up to five minutes -- so a fetch straight after a stop can
 * legitimately find nothing yet.
 */
export async function stopOfflineHr(pmd, { wait = true, pollMs = 200, timeoutMs = 5000 } = {}) {
  const r = await pmdCommand(pmd, offlineHrStopCommand());
  if (!r.ok && r.status !== PMD_ALREADY) {
    throw new Error(`the band refused to stop offline heart rate (${r.statusText})`);
  }
  if (!wait) return;
  const until = Date.now() + timeoutMs;
  for (;;) {
    const s = (await readMeasurementStatus(pmd))[PMD_OFFLINE_HR] || 'none';
    if (s === 'none') return;
    if (Date.now() >= until) throw new Error('offline heart rate still reported active 5 s after stop');
    await sleep(pollMs);
  }
}

// --- Minimal protobuf ----------------------------------------------------------------------------
// Only what PSFTP needs: PbPFtpOperation, PbPFtpDirectory/Entry, the time queries and disk space.
// Arithmetic rather than bitwise for anything that can pass 2^31 (file sizes are uint64).

function pushVarint(out, n) {
  if (n < 0) {
    // int32/int64 negatives are sign-extended to 64 bits: always ten bytes.
    let v = BigInt.asUintN(64, BigInt(n));
    do { let b = Number(v & 0x7Fn); v >>= 7n; if (v) b |= 0x80; out.push(b); } while (v);
    return;
  }
  do { let b = n % 128; n = Math.floor(n / 128); if (n) b |= 0x80; out.push(b); } while (n);
}
const pbVarint = (out, field, n) => { pushVarint(out, field << 3); pushVarint(out, n); };
const pbBytes = (out, field, bytes) => { pushVarint(out, (field << 3) | 2); pushVarint(out, bytes.length); for (const b of bytes) out.push(b); };

/** { field: [values] }, values are numbers for varints and Uint8Arrays for length-delimited. */
export function pbDecode(bytes) {
  const b = toBytes(bytes), out = {};
  let o = 0;
  const varint = () => {
    let v = 0, mul = 1, byte;
    do {
      if (o >= b.length) throw new Error('truncated protobuf varint');
      byte = b[o++];
      v += (byte & 0x7F) * mul; mul *= 128;
    } while (byte & 0x80);
    return v;
  };
  while (o < b.length) {
    const key = varint(), field = Math.floor(key / 8), wire = key & 7;
    let val;
    if (wire === 0) val = varint();
    else if (wire === 2) { const n = varint(); if (o + n > b.length) throw new Error('truncated protobuf field'); val = b.subarray(o, o + n); o += n; }
    else if (wire === 1) { o += 8; continue; }
    else if (wire === 5) { o += 4; continue; }
    else throw new Error(`unsupported protobuf wire type ${wire}`);
    (out[field] || (out[field] = [])).push(val);
  }
  return out;
}

export const PFTP_COMMAND = { GET: 0, PUT: 1, MERGE: 2, REMOVE: 3 };
/// PbPFtpQuery ids used here.
export const PFTP_QUERY = { SET_SYSTEM_TIME: 1, SET_LOCAL_TIME: 3, GET_LOCAL_TIME: 4, GET_DISK_SPACE: 5 };
/// PbPFtpHostToDevNotification ids.
export const PFTP_NOTIFICATION = { START_SYNC: 0, STOP_SYNC: 1, RESET: 2, INITIALIZE_SESSION: 8, TERMINATE_SESSION: 9 };

/// PbPFtpOperation { required Command command = 1; required string path = 2; }. proto2 required
/// fields are always written, so GET (0) still appears as 08 00.
export function encodeOperation(command, path) {
  const out = [];
  pbVarint(out, 1, command);
  pbBytes(out, 2, new TextEncoder().encode(path));
  return new Uint8Array(out);
}

/** PbPFtpDirectory -> [{ name, size }]. Directories are the names ending in '/'. */
export function decodeDirectory(bytes) {
  const td = new TextDecoder();
  return (pbDecode(bytes)[1] || []).map(e => {
    const f = pbDecode(e);
    return { name: f[1] ? td.decode(f[1][0]) : '', size: f[2] ? f[2][0] : 0 };
  });
}

/// PbDate { year=1, month=2, day=3 } and PbTime { hour=1, minute=2, seconds=3, millis=4 }, from the
/// UTC fields of `d` -- so callers shift `d` to whichever wall clock they mean first.
function pbDateTime(d) {
  const date = [], time = [];
  pbVarint(date, 1, d.getUTCFullYear()); pbVarint(date, 2, d.getUTCMonth() + 1); pbVarint(date, 3, d.getUTCDate());
  pbVarint(time, 1, d.getUTCHours()); pbVarint(time, 2, d.getUTCMinutes());
  pbVarint(time, 3, d.getUTCSeconds()); pbVarint(time, 4, d.getUTCMilliseconds());
  return [date, time];
}

/// PbPFtpSetSystemTimeParams { date=1, time=2 (UTC), trusted=3 } -- PolarTimeUtils sets trusted.
export function encodeSetSystemTime(date) {
  const [d, t] = pbDateTime(date), out = [];
  pbBytes(out, 1, d); pbBytes(out, 2, t); pbVarint(out, 3, 1);
  return new Uint8Array(out);
}

/// PbPFtpSetLocalTimeParams { date=1, time=2 (wall clock), tz_offset=3 (minutes east of UTC) }.
/// The offset defaults to the phone's, as the SDK uses the system default zone.
export function encodeSetLocalTime(date, tzOffsetMin = -date.getTimezoneOffset()) {
  const [d, t] = pbDateTime(new Date(date.getTime() + tzOffsetMin * 60000)), out = [];
  pbBytes(out, 1, d); pbBytes(out, 2, t); pbVarint(out, 3, tzOffsetMin);
  return new Uint8Array(out);
}

// --- PSFTP framing: RFC60 header, RFC76 air packets ----------------------------------------------

/// PbPFtpError. 103 and 202 are the two this feature actually meets.
export const PFTP_ERRORS = { 0: 'OPERATION_SUCCEEDED', 1: 'REBOOTING', 2: 'TRY_AGAIN',
  100: 'UNIDENTIFIED_HOST_ERROR', 101: 'INVALID_COMMAND', 102: 'INVALID_PARAMETER',
  103: 'NO_SUCH_FILE_OR_DIRECTORY', 104: 'DIRECTORY_EXISTS', 105: 'FILE_EXISTS',
  106: 'OPERATION_NOT_PERMITTED', 107: 'NO_SUCH_USER', 108: 'TIMEOUT',
  200: 'UNIDENTIFIED_DEVICE_ERROR', 201: 'NOT_IMPLEMENTED', 202: 'SYSTEM_BUSY', 203: 'INVALID_CONTENT',
  204: 'CHECKSUM_FAILURE', 205: 'DISK_FULL', 206: 'PREREQUISITE_NOT_MET', 207: 'INSUFFICIENT_BUFFER',
  208: 'WAIT_FOR_IDLING', 209: 'BATTERY_TOO_LOW', 303: 'AIR_PACKET_LOST' };
export const NO_SUCH_FILE = 103, SYSTEM_BUSY = 202, AIR_PACKET_LOST = 303;

export class PsFtpError extends Error {
  constructor(code, detail = '') {
    const name = PFTP_ERRORS[code] || 'UNKNOWN';
    const hint = code === SYSTEM_BUSY
      ? ' -- the band refuses file transfer while in its own recording or swimming mode; it must be in'
        + ' sensor mode (heart symbol lit)' : '';
    super(`PSFTP error ${code} (${name})${detail ? ': ' + detail : ''}${hint}`);
    this.name = 'PsFtpError';
    this.code = code;
    this.errorName = name;
  }
}

export const RFC76_STATUS = { ERROR_OR_RESPONSE: 0, LAST: 1, MORE: 3 };

/// RFC60 request: 2-byte little-endian header length (15 bits; bit 15 clear = request), the
/// protobuf header, then data (only for writes, which this module does not do).
export function rfc60Request(header) {
  const h = toBytes(header);
  const out = new Uint8Array(2 + h.length);
  out[0] = h.length & 0xFF; out[1] = (h.length & 0x7F00) >> 8;
  out.set(h, 2);
  return out;
}

/// RFC60 query: the id with bit 15 set, then optional protobuf parameters.
export function rfc60Query(id, params) {
  const p = params ? toBytes(params) : new Uint8Array(0);
  const out = new Uint8Array(2 + p.length);
  out[0] = id & 0xFF; out[1] = ((id & 0x7F00) >> 8) | 0x80;
  out.set(p, 2);
  return out;
}

/**
 * Split a message into RFC76 air packets of at most `packetSize` bytes, exactly as
 * BlePsFtpUtils.buildRfc76MessageFrameAll: header byte = next(bit 0) | status(bits 1-2: 0x06 MORE,
 * 0x02 LAST) | sequence(bits 4-7, ring of 16, from 0). A payload that exactly fills the last packet
 * is LAST, not MORE followed by an empty packet.
 */
export function buildRfc76Frames(message, packetSize = 20) {
  const data = toBytes(message), room = packetSize - 1, frames = [];
  let off = 0, seq = 0, next = 0;
  do {
    const left = data.length - off;
    const n = Math.min(left, room);
    const frame = new Uint8Array(n + 1);
    frame[0] = next | (left > room ? 0x06 : 0x02) | (seq << 4);
    frame.set(data.subarray(off, off + n), 1);
    frames.push(frame);
    off += n; seq = (seq + 1) & 0x0F; next = 1;
  } while (off < data.length);
  return frames;
}

/**
 * One received air packet. Status 0 carries a 16-bit little-endian error code instead of payload.
 * The error is decoded as iOS does (low | high << 8); Android's version masks the high byte away,
 * which only matters for codes above 255.
 */
export function parseRfc76Frame(packet) {
  const p = toBytes(packet);
  if (!p.length) throw new Error('empty RFC76 frame');
  const f = { next: p[0] & 0x01, status: (p[0] >> 1) & 0x03, seq: (p[0] >> 4) & 0x0F, error: 0, payload: null };
  if (f.status === RFC76_STATUS.ERROR_OR_RESPONSE) f.error = p.length >= 3 ? p[1] | (p[2] << 8) : 0;
  else f.payload = p.slice(1);
  return f;
}

/// Per-packet wait, as the SDK's PROTOCOL_TIMEOUT_SECONDS. Long because the band may be busy with
/// flash; it bounds every wait so a bridge that drops a notification cannot hang the page for ever.
export const PSFTP_TIMEOUT_MS = 90000;

function concat(chunks) {
  const out = new Uint8Array(chunks.reduce((n, c) => n + c.length, 0));
  let o = 0;
  for (const c of chunks) { out.set(c, o); o += c.length; }
  return out;
}

/**
 * PSFTP over Web Bluetooth.
 *
 * `chars` are BluetoothRemoteGATTCharacteristic-likes: `mtu` (required), `d2h` and `h2d` (optional).
 *
 * Packet size: the SDK uses ATT MTU - 3 (iOS asks CoreBluetooth for it). Web Bluetooth does not
 * expose the MTU, so the default is 20, the size every link supports. It only limits what the PAGE
 * writes -- requests are a path, two or three packets -- while downloads arrive at whatever size
 * the band chose, so there is nothing to gain from guessing higher and a silent truncation to lose.
 *
 * Write type: iOS's client writes every request packet WITH response and waits for each; Android's
 * writes them without. With-response is the default because Bluefy sits on CoreBluetooth, where an
 * unacknowledged write can be dropped when its buffer is full.
 *
 * One operation at a time, as the SDK's operation mutex: responses carry no request id, so two
 * overlapping requests would read each other's packets.
 */
export class PsFtpClient {
  constructor({ mtu, d2h = null, h2d = null }, { packetSize = 20, withResponse = true,
                                                 timeoutMs = PSFTP_TIMEOUT_MS } = {}) {
    if (!mtu) throw new Error('PSFTP needs its MTU characteristic');
    this.mtu = mtu; this.d2h = d2h; this.h2d = h2d;
    this.packetSize = packetSize;
    this.withResponse = withResponse;
    this.timeoutMs = timeoutMs;
    this._inbox = [];
    this._waiter = null;
    this._chain = Promise.resolve();
    this._onPacket = e => {
      const v = e.target.value;
      // Copied at once: some bridges reuse the DataView's buffer for the next notification.
      const bytes = new Uint8Array(v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength));
      if (!bytes.length) return;                  // the SDK drops zero-length packets too
      if (this._waiter) { const w = this._waiter; this._waiter = null; w.resolve(bytes); }
      else this._inbox.push(bytes);
    };
  }

  /** Look the service up on a connected GATT server and open the client. */
  static async fromServer(server, options) {
    const svc = await server.getPrimaryService(PSFTP_SERVICE);
    // One at a time: flaky bridges are where parallel GATT discovery goes wrong.
    const mtu = await svc.getCharacteristic(PSFTP_MTU_CHAR);
    let d2h = null, h2d = null;
    try { d2h = await svc.getCharacteristic(PSFTP_D2H_CHAR); } catch { /* optional */ }
    try { h2d = await svc.getCharacteristic(PSFTP_H2D_CHAR); } catch { /* optional */ }
    const client = new PsFtpClient({ mtu, d2h, h2d }, options);
    await client.open();
    return client;
  }

  /** Subscribe. The SDK enables MTU and D2H notifications on connect and waits for both. */
  async open() {
    this.mtu.addEventListener('characteristicvaluechanged', this._onPacket);
    await this.mtu.startNotifications();
    if (this.d2h) { try { await this.d2h.startNotifications(); } catch { /* not needed for requests */ } }
  }

  /** Stop listening and fail whatever is waiting -- e.g. on disconnect. */
  close(reason = new Error('PSFTP closed')) {
    try { this.mtu.removeEventListener('characteristicvaluechanged', this._onPacket); } catch { /* gone */ }
    if (this._waiter) { const w = this._waiter; this._waiter = null; w.reject(reason); }
    this._inbox.length = 0;
  }

  _write(ch, bytes) {
    if (this.withResponse && typeof ch.writeValueWithResponse === 'function') return ch.writeValueWithResponse(bytes);
    if (!this.withResponse && typeof ch.writeValueWithoutResponse === 'function') return ch.writeValueWithoutResponse(bytes);
    return ch.writeValue(bytes);
  }

  _nextPacket() {
    if (this._inbox.length) return Promise.resolve(this._inbox.shift());
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._waiter = null;
        reject(new PsFtpError(108, `no packet from the band within ${this.timeoutMs / 1000} s`));
      }, this.timeoutMs);
      this._waiter = {
        resolve: v => { clearTimeout(timer); resolve(v); },
        reject: e => { clearTimeout(timer); reject(e); },
      };
    });
  }

  _serial(fn) {
    const run = this._chain.then(fn, fn);
    this._chain = run.catch(() => {});
    return run;
  }

  async _exchange(message) {
    this._inbox.length = 0;                       // resetMtuPipe: stale packets never count
    for (const frame of buildRfc76Frames(message, this.packetSize)) await this._write(this.mtu, frame);
    return this._readResponse();
  }

  /**
   * Reassemble one response (BlePsFtpClient.suspendReadResponse). Sequence numbers restart at 0
   * for every response; a gap means a lost air packet, and if the band is still sending, a cancel
   * packet [00 00 00] tells it to stop before the error is raised.
   */
  async _readResponse() {
    const chunks = [];
    let seq = 0, first = true, status;
    do {
      const f = parseRfc76Frame(await this._nextPacket());
      if (f.seq !== seq) {
        if (f.status === RFC76_STATUS.MORE) {
          try { await this._write(this.mtu, new Uint8Array(3)); } catch { /* best effort */ }
        }
        this._inbox.length = 0;
        throw new PsFtpError(AIR_PACKET_LOST, `expected packet ${seq}, got ${f.seq}`);
      }
      seq = (seq + 1) & 0x0F;
      if (f.next !== (first ? 0 : 1)) throw new PsFtpError(200, 'stream out of sync');
      first = false;
      status = f.status;
      if (status === RFC76_STATUS.LAST || status === RFC76_STATUS.MORE) chunks.push(f.payload);
      else if (status === RFC76_STATUS.ERROR_OR_RESPONSE) {
        if (f.error) throw new PsFtpError(f.error);
        return concat(chunks);                     // e.g. a REMOVE: success, no content
      } else throw new PsFtpError(200, 'undefined RFC76 status');
    } while (status === RFC76_STATUS.MORE);
    return concat(chunks);
  }

  /** Raw request with a protobuf PbPFtpOperation header. */
  request(header) { return this._serial(() => this._exchange(rfc60Request(header))); }
  /** PbPFtpQuery with optional protobuf parameters. */
  query(id, params) { return this._serial(() => this._exchange(rfc60Query(id, params))); }
  get(path) { return this.request(encodeOperation(PFTP_COMMAND.GET, path)); }
  remove(path) { return this.request(encodeOperation(PFTP_COMMAND.REMOVE, path)); }

  /**
   * Host-to-device notification (one-byte id + parameters, RFC76-framed on H2D). Polar's
   * offline_measurement.pdf sends INITIALIZE_SESSION before reading a file; the current SDK's
   * offline-recording path does not, so nothing here calls it -- it is here in case hardware says
   * otherwise.
   */
  sendNotification(id, params) {
    if (!this.h2d) return Promise.reject(new Error('no H2D characteristic'));
    const p = params ? toBytes(params) : new Uint8Array(0);
    const msg = new Uint8Array(1 + p.length);
    msg[0] = id; msg.set(p, 1);
    return this._serial(async () => {
      for (const frame of buildRfc76Frames(msg, this.packetSize)) await this._write(this.h2d, frame);
    });
  }
}

// --- Device time ---------------------------------------------------------------------------------

/**
 * Set the band's clock, as BDBleApiImpl.setLocalTime: SET_SYSTEM_TIME (UTC, trusted) first with
 * its error ignored, then SET_LOCAL_TIME (wall clock + offset). The SDK never does this on its
 * own before a recording; it is a separate API call the app makes.
 *
 * Polar's known issue 3 for the Verity Sense: a time change does not reach the PMD stream
 * timestamps until the band is power-cycled. Whether the offline file's start time is affected the
 * same way is not documented.
 */
export async function setDeviceTime(psftp, date = new Date(), { tzOffsetMin = -date.getTimezoneOffset() } = {}) {
  try { await psftp.query(PFTP_QUERY.SET_SYSTEM_TIME, encodeSetSystemTime(date)); } catch { /* as the SDK */ }
  await psftp.query(PFTP_QUERY.SET_LOCAL_TIME, encodeSetLocalTime(date, tzOffsetMin));
}

/** Free and total memory (PbPFtpDiskSpaceResult: fragment size x fragment counts). */
export async function getDiskSpace(psftp) {
  const f = pbDecode(await psftp.query(PFTP_QUERY.GET_DISK_SPACE));
  const size = f[1] ? f[1][0] : 0, total = f[2] ? f[2][0] : 0, free = f[3] ? f[3][0] : 0;
  return { totalBytes: size * total, freeBytes: size * free };
}

// --- Listing, fetching, removing recordings ------------------------------------------------------
// Layout: /U/0/<YYYYMMDD>/R/<HHMMSS>/<TYPE>[n].REC. A long recording is split into TYPE0.REC,
// TYPE1.REC, ...; older firmware writes a single TYPE.REC. Entries are grouped as Android does,
// one per recording with the index removed (".../HR.REC") and the parts' sizes summed.

const FILE_TYPES = { ACC: 'ACC', GYRO: 'GYRO', MAG: 'MAG', PPG: 'PPG', PPI: 'PPI', HR: 'HR',
                     TEMP: 'TEMP', SKINTEMP: 'SKINTEMP' };

/// "HR0.REC" -> "HR" (mapOfflineRecordingFileNameToMeasurementType), or null if unknown.
export function recordingType(fileName) {
  return FILE_TYPES[fileName.split('.')[0].replace(/\d+/g, '')] || null;
}

/**
 * Directory date + time. The SDK makes a LocalDateTime (no zone) and iOS reads it in the phone's
 * zone; Polar's offline_measurement.pdf calls HHMMSS "local time at which the recording was
 * started". So: a Date in the phone's local zone, or null if the digits are not a real time.
 */
export function recordingDate(yyyymmdd, hhmmss) {
  const m = /^(\d{4})(\d{2})(\d{2})$/.exec(yyyymmdd), t = /^(\d{2})(\d{2})(\d{2})$/.exec(hhmmss);
  if (!m || !t) return null;
  const [y, mo, d, h, mi, s] = [m[1], m[2], m[3], t[1], t[2], t[3]].map(Number);
  // Checked as digits, not by round-tripping the Date: a time inside a DST spring-forward gap is
  // shifted an hour by the Date constructor, and rejecting it would hide a real recording.
  const days = new Date(Date.UTC(y, mo, 0)).getUTCDate();
  if (mo < 1 || mo > 12 || d < 1 || d > days || h > 23 || mi > 59 || s > 59) return null;
  return new Date(y, mo - 1, d, h, mi, s);
}

/// A file path -> an entry, or null for anything that is not a recording (logged and skipped by the
/// SDK).
function entryFromPath(path, size) {
  const c = path.split('/');
  if (c.length < 7) return null;
  const type = recordingType(c[6]);
  const date = recordingDate(c[3], c[5]);
  if (!type || !date) return null;
  return { path, size, type, date };
}

/// PolarOfflineRecordingUtils.listOfflineRecordingsV1 over [[path, size]] already found.
export function groupRecordingFiles(files) {
  const groups = new Map();
  for (const [path, size] of files) {
    const e = entryFromPath(path, size);
    if (!e || !(size > 0)) continue;              // empty parts are ignored, as the SDK does
    const key = path.replace(/\d+\.REC$/, '.REC');
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  }
  return [...groups].map(([key, parts]) => ({ path: key, size: parts.reduce((n, p) => n + p.size, 0),
                                              type: parts[0].type, date: parts[0].date }));
}

/// listOfflineRecordingsV2: "/PMDFILES.TXT", one "<size> <path>" per line, maintained by newer
/// firmware so one GET replaces walking the whole tree.
export function parsePmdFilesTxt(bytes) {
  const text = typeof bytes === 'string' ? bytes : new TextDecoder().decode(toBytes(bytes));
  const groups = new Map();
  for (const raw of text.split(/\r?\n|\r/)) {
    const parts = raw.trim().split(' ');
    if (parts.length < 2 || !parts[1].endsWith('.REC') || !/^-?\d+$/.test(parts[0])) continue;
    const size = Number(parts[0]);
    if (size <= 0) continue;
    const path = parts[1].replace(/(\w*?)\d+\.REC$/, '$1.REC');
    const e = entryFromPath(path, size);
    if (!e) continue;
    const key = `${path}|${e.date.getTime()}`;
    if (groups.has(key)) groups.get(key).size += size;
    else groups.set(key, e);
  }
  return [...groups.values()];
}

/**
 * PolarFileUtils.fetchRecursively: GET each directory, keep the names `condition` accepts, recurse
 * into the ones ending '/'. A directory that has vanished (103) is simply empty.
 */
export async function fetchRecursively(psftp, path, condition = () => true) {
  let dir;
  try {
    dir = decodeDirectory(await psftp.get(path));
  } catch (e) {
    if (e && e.code === NO_SUCH_FILE) return [];
    throw e;
  }
  const out = [];
  for (const { name, size } of dir) {
    if (!condition(name)) continue;
    if (name.endsWith('/')) out.push(...await fetchRecursively(psftp, path + name, condition));
    else out.push([path + name, size]);
  }
  return out;
}

const isRecordingDirPart = n => /^\d{8}\/$/.test(n) || n === 'R/' || /^\d{6}\/$/.test(n) || n.includes('.REC');

/**
 * Every recording on the band, as `{ path, type, date, size }`.
 *
 * As the SDK: try /PMDFILES.TXT first and use it if it has any content; on any error (older
 * firmware has no such file: 103) walk /U/0/ instead.
 */
export async function listOfflineRecordings(psftp) {
  let txt = null;
  try { txt = await psftp.get('/PMDFILES.TXT'); } catch { txt = null; }
  if (txt && txt.length) return parsePmdFilesTxt(txt);
  return groupRecordingFiles(await fetchRecursively(psftp, '/U/0/', isRecordingDirPart));
}

const dirOf = path => path.substring(0, path.lastIndexOf('/') + 1);

/**
 * getSubRecordingAndOtherFilesCount: in the recording's directory, how many files are parts of this
 * recording ("HR" + digit + ".") and how many are anything else. A missing directory is [0, 0].
 */
export async function subRecordingCounts(psftp, entry) {
  let dir;
  try {
    dir = decodeDirectory(await psftp.get(dirOf(entry.path)));
  } catch (e) {
    if (e && e.code === NO_SUCH_FILE) return [0, 0];
    throw e;
  }
  const name = entry.path.substring(entry.path.lastIndexOf('/') + 1);
  const prefix = name.includes('.REC') ? name.substring(0, name.indexOf('.REC')) : name;
  const parts = dir.filter(e => e.name.startsWith(prefix) && /\d\./.test(e.name)).length;
  return [parts, dir.length - parts];
}

/// getSubRecordingPath: ".../HR.REC", 2 -> ".../HR2.REC".
export function subRecordingPath(path, index) {
  const p = /\.REC$/.test(path) ? path.replace(/(\.REC)$/, `${index}.REC`)
                                : path.replace(/\d(?=\D*$)/, String(index));
  return p.trim() ? p : path;
}

/**
 * The raw file(s) of one recording, in order: the single file if it is not split, else parts
 * 0..n-1 (fetchSingleOfflineRecord / fetchSubRecordings).
 */
export async function fetchRecordingFiles(psftp, entry) {
  const [parts] = await subRecordingCounts(psftp, entry);
  if (!parts) return [await psftp.get(entry.path)];
  const files = [];
  for (let i = 0; i < parts; i++) files.push(await psftp.get(subRecordingPath(entry.path, i)));
  return files;
}

async function isDirectoryEmpty(psftp, dir) {
  try {
    return decodeDirectory(await psftp.get(dir.endsWith('/') ? dir : dir + '/')).length === 0;
  } catch (e) {
    if (e && e.code === NO_SUCH_FILE) return false;   // Android: gone already, nothing to remove
    throw e;
  }
}

async function removeIgnoringMissing(psftp, path) {
  try { await psftp.remove(path); } catch (e) { if (!e || e.code !== NO_SUCH_FILE) throw e; }
}

/**
 * removeOfflineRecord (Android's sequence). If the recording's directory holds nothing else, the
 * whole directory goes; otherwise its part files one by one. Then each parent up to /U/0 is removed
 * if it is now empty.
 *
 * Two deliberate differences from Android: directories are removed with a trailing '/' (as iOS and
 * as Android's own first REMOVE), and errors are thrown instead of logged and swallowed -- the
 * caller has to know whether the band's memory was actually freed.
 */
export async function removeOfflineRecord(psftp, entry) {
  const [parts, others] = await subRecordingCounts(psftp, entry);
  if (others === 0) await removeIgnoringMissing(psftp, dirOf(entry.path));
  else if (parts === 0 || /(\D+)(\d+)\.REC/.test(entry.path)) await removeIgnoringMissing(psftp, entry.path);
  else {
    for (let i = 0; i < parts; i++) {
      await removeIgnoringMissing(psftp, entry.path.replace(/(\d*.REC)$/, `${i}.REC`));
    }
  }
  const dirs = [];
  for (let d = entry.path.substring(0, entry.path.lastIndexOf('/'));
       d.startsWith('/U/0/') && d !== '/U/0'; d = d.substring(0, d.lastIndexOf('/'))) dirs.push(d);
  for (const d of dirs) if (await isDirectoryEmpty(psftp, d)) await removeIgnoringMissing(psftp, d + '/');
}

// --- Offline file parsing ------------------------------------------------------------------------

const OFFLINE_MAGIC = 0x3D7C4C2B;
const SECURITY = ['none', 'XOR', 'AES-128', 'AES-256'];

const u16 = (b, o) => b[o] | (b[o + 1] << 8);
const u32 = (b, o) => (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16)) + b[o + 3] * 0x1000000;
function u64(b, o) {
  let v = 0n;
  for (let i = 7; i >= 0; i--) v = (v << 8n) | BigInt(b[o + i]);
  return v;
}

function refuseEncrypted(code) {
  throw new Error(`this offline recording is encrypted (${SECURITY[code] || `strategy ${code}`}); `
    + 'only recordings started without a secret can be read here');
}

/**
 * The metadata block (OfflineRecordingData.parseMetaData), unencrypted files only:
 *
 *   [0]        file security strategy (0 none, 1 XOR, 2 AES-128, 3 AES-256)
 *   [1..16]    header: magic 0x3D7C4C2B, version, free, ESW hash -- four uint32 LE
 *   [17..36]   start time, ASCII "YYYY-MM-DD HH:MM:SS" + NUL
 *   [37]       settings length n, then n bytes of PMD settings (none for HR)
 *   then       payload security info: length byte (0 = none), strategy byte if non-zero
 *   then       size of the first data packet, uint16 LE (missing in an empty file -> 0)
 *
 * startMs: the SDK parses the start time as UTC ("Z" appended; its doc comment says "in UTC
 * time"), so this is that instant in ms since 1970. See fetchOfflineHr for the caveat.
 */
export function parseOfflineMeta(fileBytes) {
  const b = toBytes(fileBytes);
  if (!b.length) throw new Error('offline recording file is empty');
  if (b[0] !== 0) refuseEncrypted(b[0]);
  if (b.length < 39) throw new Error('offline recording file is shorter than its own header');
  const header = { magic: u32(b, 1), version: u32(b, 5), free: u32(b, 9), eswHash: u32(b, 13) };
  if (header.magic !== OFFLINE_MAGIC) throw new Error('not a Polar offline recording (wrong signature)');
  const startTime = String.fromCharCode(...b.subarray(17, 36)).replace(/\0+$/, '');
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(startTime);
  if (!m) throw new Error(`offline recording start time is unreadable: ${JSON.stringify(startTime)}`);
  const startMs = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
  let o = 37;
  const settingsLen = b[o++];
  const settings = b.slice(o, o + settingsLen);
  o += settingsLen;
  const infoLen = b[o++];
  if (infoLen) { const strategy = b[o++]; if (strategy !== 0) refuseEncrypted(strategy); }
  const firstPacketSize = o + 2 <= b.length ? u16(b, o) : 0;
  o += 2;
  return { header, startTime, startMs, settings, firstPacketSize, metaLength: o };
}

/**
 * The PMD data frames after the metadata (OfflineRecordingData.parseData): the first frame is
 * `firstPacketSize` long, every later one is preceded by its own uint16 LE size. Each frame is
 *   [0] measurement type (low 6 bits)   [1..8] timestamp, uint64 LE   [9] frame type   [10..] data
 * with bit 7 of the frame type meaning "compressed" (PmdDataFrame).
 *
 * A file cut short mid-frame (fetched while still being written) keeps the whole frames and sets
 * `truncated`; the SDK would throw away the lot.
 */
export function parsePmdFrame(bytes) {
  const f = toBytes(bytes);
  if (f.length < 10) throw new Error(`PMD data frame is too short: ${f.length} bytes`);
  return { type: f[0] & 0x3F, timestamp: u64(f, 1), frameType: f[9] & 0x7F,
           compressed: (f[9] & 0x80) !== 0, content: f.subarray(10) };
}

export function parseOfflineFrames(fileBytes, meta = parseOfflineMeta(fileBytes)) {
  const b = toBytes(fileBytes);
  const frames = [];
  let off = meta.metaLength, size = meta.firstPacketSize, truncated = false;
  while (off < b.length) {
    if (off + size > b.length) { truncated = true; break; }
    frames.push(parsePmdFrame(b.subarray(off, off + size)));
    off += size;
    if (off < b.length) {
      if (off + 2 > b.length) { truncated = true; break; }
      size = u16(b, off); off += 2;
    }
  }
  return { frames, truncated };
}

/**
 * OfflineHrData.parseDataFromDataFrame. Raw only -- compressed HR is refused by the SDK too.
 *   type 0: one byte per sample, the heart rate
 *   type 1: three bytes per sample: heart rate, PPG quality, corrected heart rate
 */
export function parseOfflineHrFrame(frame) {
  const c = frame.content;
  if (frame.compressed) throw new Error(`Offline HR compressed frame type TYPE_${frame.frameType} is not supported`);
  if (frame.frameType === 0) {
    if (!c.length) throw new Error('Offline HR raw TYPE_0 dataContent is empty');
    return Array.from(c, hr => ({ hr, ppgQuality: 0, correctedHr: 0 }));
  }
  if (frame.frameType === 1) {
    if (!c.length || c.length % 3) {
      throw new Error(`Offline HR raw TYPE_1 dataContent size ${c.length} is not a non-zero multiple of 3`);
    }
    const out = [];
    for (let i = 0; i < c.length; i += 3) out.push({ hr: c[i], ppgQuality: c[i + 1], correctedHr: c[i + 2] });
    return out;
  }
  throw new Error(`Offline HR raw frame type TYPE_${frame.frameType} is not supported`);
}

/// The interval between offline HR samples. NOT stated anywhere in the SDK: it returns the samples
/// as a bare list with only the recording's start time, and the frame timestamps in Polar's own
/// test files are zero. 1 Hz is the Verity Sense's heart-rate rate everywhere else; confirm it on
/// hardware by comparing sample count with recording length.
export const OFFLINE_HR_INTERVAL_MS = 1000;

/**
 * One HR file -> samples. A frame that fails to parse is skipped and reported in `errors`, as the
 * SDK logs it and carries on.
 *
 * t (ms since 1970) = header start time read as UTC, as the SDK reads it, + (startIndex + i) s.
 * startIndex lets a split recording continue its first part's clock, as the SDK appends parts.
 * Frame timestamps (PMD clock: ns since 2000-01-01 on the band's clock) are kept in `frames` for
 * checking but not used: the SDK does not use them for HR, and Polar's time-system notes say HR
 * samples may carry zero.
 */
export function parseOfflineHrFile(fileBytes, { startIndex = 0, startMs = null } = {}) {
  const meta = parseOfflineMeta(fileBytes);
  const { frames, truncated } = parseOfflineFrames(fileBytes, meta);
  const t0 = startMs == null ? meta.startMs : startMs;
  const samples = [], errors = [];
  for (const f of frames) {
    try {
      for (const s of parseOfflineHrFrame(f)) {
        samples.push({ t: t0 + (startIndex + samples.length) * OFFLINE_HR_INTERVAL_MS, ...s });
      }
    } catch (e) { errors.push(e.message); }
  }
  return { startTime: meta.startTime, startMs: meta.startMs, header: meta.header, samples, errors, truncated,
           frames: frames.map(f => ({ timestamp: f.timestamp, frameType: f.frameType, bytes: f.content.length })) };
}

// --- The convenience layer the page uses ---------------------------------------------------------

/**
 * Every offline HR sample on the band, merged in time order: `{ samples: [{t, hr}], entries,
 * recordings }`. Pass `entries` to removeRecordings once the samples are safely stored.
 *
 * `since` (Date or ms) drops samples before it; recordings are not skipped by their start date,
 * because one that began before `since` can still run past it.
 *
 * Zero heart rates are dropped unless `keepZero`: zero is the band's "no reading", and a gap filler
 * that writes zeros into a trace is fabricating a cardiac arrest.
 *
 * Clock caveat, unverified without hardware: `t` treats the file's start time as UTC, as the SDK
 * does, while the directory name is documented as local time. `recordings[].dirMinusHeaderMs`
 * compares the two -- near zero means they agree; a whole number of hours means one of them is the
 * band's wall clock, and `t` is off by that much.
 *
 * SYSTEM_BUSY (202) means the band is in its own recording/swimming mode; 103 on a fresh
 * recording usually means the band has not written the file yet (up to five minutes, per Polar).
 * Polar recommends stopping the recording before reading it.
 */
export async function fetchOfflineHr(psftp, { since = null, keepZero = false } = {}) {
  const sinceMs = since == null ? -Infinity : +since;
  const entries = (await listOfflineRecordings(psftp)).filter(e => e.type === 'HR');
  const recordings = [], all = [];
  for (const entry of entries) {
    const files = await fetchRecordingFiles(psftp, entry);
    let startMs = null, index = 0;
    const info = { entry, startMs: null, count: 0, errors: [], truncated: false, dirMinusHeaderMs: null };
    for (const bytes of files) {
      const r = parseOfflineHrFile(bytes, { startIndex: index, startMs });
      if (startMs == null) { startMs = r.startMs; info.startMs = r.startMs; }
      index += r.samples.length;
      info.count += r.samples.length;
      info.errors.push(...r.errors);
      info.truncated = info.truncated || r.truncated;
      for (const s of r.samples) if ((keepZero || s.hr > 0) && s.t >= sinceMs) all.push(s);
    }
    if (startMs != null) info.dirMinusHeaderMs = entry.date.getTime() - startMs;
    recordings.push(info);
  }
  all.sort((a, b) => a.t - b.t);
  // Two recordings covering the same second (one restarted on top of another): keep the first.
  const samples = all.filter((s, i) => i === 0 || s.t !== all[i - 1].t);
  return { samples, entries, recordings };
}

/**
 * Delete recordings, e.g. after fetchOfflineHr's samples are stored. The band never deletes them
 * itself, and its limits are tight: under 2 MB free a new recording will not start, under 300 KB
 * a running one is stopped. Each entry is tried even if an earlier one fails.
 */
export async function removeRecordings(psftp, entries) {
  const results = [];
  for (const entry of entries) {
    try { await removeOfflineRecord(psftp, entry); results.push({ entry, ok: true }); }
    catch (error) { results.push({ entry, ok: false, error }); }
  }
  return results;
}
