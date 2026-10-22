// There is no band here, so the evidence that polar-offline.js speaks Polar's protocol is Polar's
// own unit-test vectors, replayed byte for byte. Each block names the SDK test it ports. Where a
// test needed adapting (the iOS and Android SDKs disagree on how a split recording is named), the
// block says so. The rest drives the PSFTP client against a fake band that frames its answers the
// way the SDK's test frames do.

import assert from 'node:assert/strict';
import {
  PSFTP_SERVICE, PSFTP_MTU_CHAR, PSFTP_D2H_CHAR, PSFTP_H2D_CHAR, OFFLINE_OPTIONAL_SERVICES,
  offlineHrStartCommand, offlineHrStopCommand, measurementStatusCommand, parseControlPointResponse,
  measurementState, parseMeasurementStatus, startOfflineHr, stopOfflineHr, offlineHrActive,
  pbDecode, encodeOperation, decodeDirectory, encodeSetSystemTime, encodeSetLocalTime,
  PFTP_COMMAND, PFTP_QUERY, PsFtpError, rfc60Request, rfc60Query, buildRfc76Frames, parseRfc76Frame,
  PsFtpClient, setDeviceTime, getDiskSpace,
  recordingType, groupRecordingFiles, parsePmdFilesTxt, listOfflineRecordings, subRecordingCounts,
  subRecordingPath, fetchRecordingFiles, removeOfflineRecord,
  parseOfflineMeta, parseOfflineFrames, parsePmdFrame, parseOfflineHrFrame, parseOfflineHrFile,
  fetchOfflineHr, removeRecordings,
} from '../polar-offline.js';

let passed = 0;
const ok = msg => { passed += 1; console.log(`  ok  ${msg}`); };
const hex = a => [...a].map(b => b.toString(16).padStart(2, '0')).join(' ');
const ascii = s => [...s].map(c => c.charCodeAt(0));

// --- fakes ---------------------------------------------------------------------------------------

/** A BluetoothRemoteGATTCharacteristic-like. */
class FakeChar {
  constructor(onWrite = null) { this.listeners = []; this.writes = []; this.onWrite = onWrite; this.notifying = false; }
  addEventListener(type, fn) { if (type === 'characteristicvaluechanged') this.listeners.push(fn); }
  removeEventListener(type, fn) { this.listeners = this.listeners.filter(f => f !== fn); }
  async startNotifications() { this.notifying = true; }
  async writeValueWithResponse(v) { const b = new Uint8Array(v); this.writes.push(b); if (this.onWrite) this.onWrite(b); }
  emit(bytes) {
    const dv = new DataView(new Uint8Array(bytes).buffer);
    for (const fn of this.listeners) fn({ target: { value: dv } });
  }
}

/**
 * A band's PSFTP side. Reassembles RFC76 packets independently of the module (so a framing bug
 * there is not mirrored here), decodes PbPFtpOperation by hand, and answers through `handler`:
 *   op -> Uint8Array (content), { error: code }, or null (success, no content).
 * Answers are framed with `devicePacket`-byte packets, header next|status|seq<<4 as in the SDK tests.
 */
class FakeBand {
  constructor(handler, { devicePacket = 20 } = {}) {
    this.handler = handler;
    this.devicePacket = devicePacket;
    this.log = [];                                 // { kind: 'request'|'query', ... }
    this.cancels = 0;
    this.rx = [];
    this.mtu = new FakeChar(b => this._onWrite(b));
    this.h2d = new FakeChar();
    this.d2h = new FakeChar();
  }
  _onWrite(pkt) {
    const status = (pkt[0] >> 1) & 3;
    if (status === 0) { this.cancels += 1; return; }    // [00 00 00]: stream cancel
    this.rx.push(...pkt.subarray(1));
    if (status !== 1) return;                      // more to come
    const msg = this.rx; this.rx = [];
    let op;
    if (msg[1] & 0x80) {
      op = { kind: 'query', id: msg[0] | ((msg[1] & 0x7F) << 8), params: Uint8Array.from(msg.slice(2)) };
    } else {
      const len = msg[0] | (msg[1] << 8), h = msg.slice(2, 2 + len);
      assert.equal(h[0], 0x08, 'PbPFtpOperation must start with field 1 (command)');
      assert.equal(h[2], 0x12, 'then field 2 (path)');
      op = { kind: 'request', command: h[1], path: String.fromCharCode(...h.slice(4, 4 + h[3])) };
    }
    this.log.push(op);
    setTimeout(() => this.answer(this.handler(op)), 0);
  }
  answer(r) {
    if (r && r.error) { this.mtu.emit([0x00, r.error & 0xFF, r.error >> 8]); return; }
    if (r == null) { this.mtu.emit([0x00, 0x00, 0x00]); return; }
    const room = this.devicePacket - 1;
    let off = 0, seq = 0, next = 0;
    do {
      const left = r.length - off, n = Math.min(left, room);
      this.mtu.emit([next | (left > room ? 0x06 : 0x02) | (seq << 4), ...r.subarray(off, off + n)]);
      off += n; seq = (seq + 1) & 15; next = 1;
    } while (off < r.length);
  }
  client(opts) { return new PsFtpClient({ mtu: this.mtu, d2h: this.d2h, h2d: this.h2d }, opts); }
}

/** A band whose files live in a map; directories are derived from the paths. */
function fileSystemBand(files, opts) {
  const fs = new Map(Object.entries(files));
  const band = new FakeBand(op => {
    if (op.kind !== 'request') return { error: 201 };
    if (op.command === PFTP_COMMAND.REMOVE) {
      const hit = [...fs.keys()].filter(p => p === op.path || p.startsWith(op.path.endsWith('/') ? op.path : op.path + '/'));
      if (!hit.length && !band.dirs().has(op.path)) return { error: 103 };
      for (const p of hit) fs.delete(p);
      band.removed.push(op.path);
      band.emptyDirs.delete(op.path);
      return null;
    }
    if (op.path.endsWith('/')) {
      if (!band.dirs().has(op.path)) return { error: 103 };
      const names = new Map();
      for (const [p, data] of fs) {
        if (!p.startsWith(op.path)) continue;
        const rest = p.slice(op.path.length), cut = rest.indexOf('/');
        names.set(cut < 0 ? rest : rest.slice(0, cut + 1), cut < 0 ? data.length : 0);
      }
      return directoryBytes([...names]);
    }
    return fs.has(op.path) ? fs.get(op.path) : { error: 103 };
  }, opts);
  band.removed = [];
  band.emptyDirs = new Set();
  band.dirs = () => {
    const d = new Set(['/', ...band.emptyDirs]);
    for (const p of fs.keys()) for (let i = p.indexOf('/', 1); i > 0; i = p.indexOf('/', i + 1)) d.add(p.slice(0, i + 1));
    if (fs.size || band.emptyDirs.size) d.add('/U/0/');
    return d;
  };
  band.fs = fs;
  return band;
}

/// Protobuf encoders for the test side (independent of the module's encoder).
function varint(n) { const o = []; do { let b = n % 128; n = Math.floor(n / 128); if (n) b |= 0x80; o.push(b); } while (n); return o; }
function directoryBytes(entries) {
  const out = [];
  for (const [name, size] of entries) {
    const nb = ascii(name);
    // PbPFtpEntry with a `created` PbSystemDateTime the decoder must skip over.
    const created = [0x0A, 0x06, 0x08, 0xE6, 0x0F, 0x10, 0x01, 0x18, 0x01, 0x12, 0x02, 0x08, 0x00, 0x18, 0x01];
    const e = [0x0A, ...varint(nb.length), ...nb, 0x10, ...varint(size), 0x1A, ...varint(created.length), ...created];
    out.push(0x0A, ...varint(e.length), ...e);
  }
  return new Uint8Array(out);
}
/// Read a protobuf varint as a signed 64-bit BigInt (for int32 negatives).
function varintBig(bytes, o) {
  let v = 0n, shift = 0n, b;
  do { b = bytes[o++]; v |= BigInt(b & 0x7F) << shift; shift += 7n; } while (b & 0x80);
  return BigInt.asIntN(64, v);
}

// --- SDK vectors: offline files ------------------------------------------------------------------

/// OfflineRecordingDataTest.HrOfflineMockData.hrOfflineFrame, verbatim.
const HR_FILE = [
  0x00,
  0x2b, 0x4c, 0x7c, 0x3d, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x08, 0xfb, 0xce, 0x14,
  0x32, 0x30, 0x32, 0x32, 0x2d, 0x31, 0x32, 0x2d, 0x30, 0x37, 0x20, 0x30, 0x37, 0x3a, 0x30, 0x34, 0x3a, 0x32, 0x38, 0x00,
  0x00,
  0x00,
  0x13, 0x00,
  0x0e,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00,
  0x00, 0xFF, 0x32, 0x32, 0x33, 0x33, 0x34, 0x35, 0x55,
];
/// OfflineRecordingDataTest.offlineFrameWithoutData, verbatim.
const HEADER_ONLY_FILE = [
  0x00,
  0x2b, 0x4c, 0x7c, 0x3d, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xed, 0xb7, 0x3b, 0x5e,
  0x32, 0x30, 0x31, 0x37, 0x2d, 0x30, 0x31, 0x2d, 0x30, 0x31, 0x20, 0x31, 0x30, 0x3a, 0x32, 0x36, 0x3a, 0x32, 0x37, 0x00,
  0x00,
  0x00,
];
/// MockAccOfflineRecordingData.accOfflineFrame, the metadata block (its first 56 bytes) only.
const ACC_META = [
  0x00,
  0x2B, 0x4C, 0x7C, 0x3D, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x79, 0xC3, 0x5F,
  0x32, 0x30, 0x31, 0x37, 0x2D, 0x30, 0x31, 0x2D, 0x31, 0x39, 0x20, 0x30, 0x38, 0x3A, 0x33, 0x32, 0x3A, 0x35, 0x32, 0x00,
  0x0F,
  0x00, 0x01, 0x34, 0x00,
  0x01, 0x01, 0x10, 0x00,
  0x02, 0x01, 0x08, 0x00,
  0x04, 0x01, 0x03,
  0x00,
  0xE4, 0x00,
];
/// MockTemperatureOfflineRecordingData.temperatureDataMock, verbatim (signed bytes as in Kotlin).
const TEMP_FILE = [0, 43, 76, 124, 61, 1, 0, 0, 0, 0, 0, 0, 0, -89, -40, -1, -78, 50, 48,
  50, 50, 45, 48, 49, 45, 48, 50, 32, 49, 55, 58, 50, 53, 58, 50, 57, 0, 11, 0, 1, 4, 0,
  1, 1, 32, 0, 4, 1, 1, 0, 42, 0, 12, -101, 61, -62, 15, 109, 16, 0, 0, 0, 0, 48, -93, 65,
  0, 48, -93, 65, 0, 32, -93, 65, 0, 32, -93, 65, 0, 48, -93, 65, 0, 48, -93, 65, 0, 48,
  -93, 65, 0, 32, -93, 65].map(b => b & 0xFF);
/// MockEncryptedOfflineRecordingDataAcc.securedOfflineData, first bytes (strategy 0x02 = AES-128).
const ENCRYPTED_PREFIX = [0x02, 0xaa, 0xc7, 0x79, 0x8f, 0x77, 0x19, 0xce, 0xa5, 0x60];

{
  // OfflineRecordingDataTest `parse Hr from offline recording data`.
  const r = parseOfflineHrFile(HR_FILE);
  assert.equal(r.samples.length, 9);
  assert.equal(r.samples[0].hr, 0);
  assert.equal(r.samples[1].hr, 255);
  assert.equal(r.samples[2].hr, 50);
  assert.equal(r.samples.at(-1).hr, 85);
  assert.deepEqual(r.samples.map(s => s.hr), [0, 255, 50, 50, 51, 51, 52, 53, 85]);
  assert.equal(r.startTime, '2022-12-07 07:04:28');
  assert.equal(r.samples[0].t, Date.UTC(2022, 11, 7, 7, 4, 28));
  assert.equal(r.samples[8].t - r.samples[0].t, 8000);
  assert.deepEqual(r.errors, []);
  assert.equal(r.truncated, false);
  ok('SDK HR offline file: 9 samples 0,255,50…85, start time read as UTC, 1 s apart');
}
{
  // OfflineRecordingDataTest `parse offline recording data containing only header`.
  const r = parseOfflineHrFile(HEADER_ONLY_FILE);
  assert.equal(r.samples.length, 0);
  assert.equal(r.startTime, '2017-01-01 10:26:27');
  ok('SDK header-only file: zero samples, no error');
}
{
  // OfflineRecordingDataTest `header parsing`, `start time parsing`, `settings parsing` (ACC file).
  const m = parseOfflineMeta(ACC_META);
  assert.equal(m.header.magic, 0x3D7C4C2B);
  assert.equal(m.header.version, 0x01);
  assert.equal(m.header.free, 0x00);
  assert.equal(m.header.eswHash, 0x5FC37904);
  assert.equal(m.startMs, Date.parse('2017-01-19T08:32:52Z'));   // the iOS test's expected date
  assert.equal(m.firstPacketSize, 0xE4);
  assert.equal(m.metaLength, 56);
  // Settings as (type, count, value LE) with the SDK's field sizes: rate/resolution/range 2, channels 1.
  const width = { 0: 2, 1: 2, 2: 2, 4: 1 }, got = {};
  for (let o = 0; o < m.settings.length;) {
    const t = m.settings[o], w = width[t];
    got[t] = m.settings[o + 2] | (w === 2 ? m.settings[o + 3] << 8 : 0);
    o += 2 + w;
  }
  assert.deepEqual(got, { 0: 0x34, 1: 0x10, 2: 0x08, 4: 0x03 });
  ok('SDK ACC file metadata: header fields, 2017-01-19T08:32:52Z, 52 Hz/16 bit/8 g/3 ch, first packet 228');
}
{
  // OfflineRecordingDataTest `temperature offline recording data`: a different settings length
  // (11) and a non-zero frame timestamp, so the frame walk is not tuned to the HR file alone.
  const m = parseOfflineMeta(TEMP_FILE);
  assert.equal(m.startTime, '2022-01-02 17:25:29');
  assert.equal(m.settings.length, 11);
  assert.equal(m.firstPacketSize, 42);
  const { frames, truncated } = parseOfflineFrames(TEMP_FILE);
  assert.equal(frames.length, 1);
  assert.equal(truncated, false);
  assert.equal(frames[0].type, 12);                          // TEMPERATURE
  assert.equal(frames[0].frameType, 0);
  assert.equal(frames[0].timestamp, 0x0000106D0FC23D9Bn);
  const c = frames[0].content, dv = new DataView(c.buffer, c.byteOffset, c.byteLength);
  assert.equal(c.length / 4, 8);                             // the SDK test expects 8 samples
  assert.equal(Math.fround(dv.getFloat32(0, true)), Math.fround(20.398438));
  ok('SDK temperature file: 11-byte settings, one 42-byte frame, timestamp, 8 samples, 20.398438');
}
{
  // An encrypted file (the SDK's AES-128 ACC vector) must say so rather than parse garbage.
  assert.throws(() => parseOfflineHrFile(ENCRYPTED_PREFIX), /encrypted \(AES-128\)/);
  assert.throws(() => parseOfflineHrFile([]), /empty/);
  const bad = [...HR_FILE]; bad[1] = 0x2c;
  assert.throws(() => parseOfflineHrFile(bad), /wrong signature/);
  ok('encrypted, empty and wrong-signature files are refused with a reason');
}
{
  // A file fetched mid-write: whole frames kept, the partial one dropped and flagged.
  const r = parseOfflineHrFile(HR_FILE.slice(0, HR_FILE.length - 3));
  assert.equal(r.samples.length, 0);
  assert.equal(r.truncated, true);
  // Two frames, the second sized by its own 2-byte prefix; then cut inside a third.
  const frame2 = [0x0e, 0, 0, 0, 0, 0, 0, 0, 0, 0x01, 72, 86, 71, 81, 64, 82];
  const two = [...HR_FILE, frame2.length, 0, ...frame2];
  const r2 = parseOfflineHrFile(two);
  assert.deepEqual(r2.samples.map(s => s.hr), [0, 255, 50, 50, 51, 51, 52, 53, 85, 72, 81]);
  assert.equal(r2.samples[10].t - r2.samples[0].t, 10000);
  assert.equal(r2.samples[9].ppgQuality, 86);
  assert.equal(parseOfflineHrFile([...two, 16, 0, 0x0e, 0, 0]).truncated, true);
  ok('multi-frame files continue the clock; a truncated tail is flagged, not fatal');
}

// --- SDK vectors: offline HR frames (OfflineHrDataTest) ------------------------------------------

{
  const header = [0x0E, 0x00, 0x94, 0x35, 0x77, 0x00, 0x00, 0x00, 0x00, 0x00];
  const content = [0x00, 0xFF, 0x32, 0x32, 0x33, 0x33, 0x34, 0x35, 0x7F];
  const f = parsePmdFrame([...header, ...content]);
  assert.equal(f.timestamp, 0x77359400n);
  const s = parseOfflineHrFrame(f);
  assert.equal(s.length, 9);
  assert.equal(s[0].hr, 0);
  assert.equal(s[1].hr, 255);
  assert.equal(s.at(-1).hr, 127);
  ok('OfflineHrDataTest type 0: 9 samples 0, 255 … 127');
}
{
  const f = parsePmdFrame([0x0E, 0x00, 0x94, 0x35, 0x77, 0x00, 0x00, 0x00, 0x00, 0x80]);
  assert.throws(() => parseOfflineHrFrame(f), { message: 'Offline HR compressed frame type TYPE_0 is not supported' });
  const f1 = parsePmdFrame([0x14, 0, 0, 0, 0, 0, 0, 0, 0, 0x81]);
  assert.throws(() => parseOfflineHrFrame(f1), { message: 'Offline HR compressed frame type TYPE_1 is not supported' });
  ok('OfflineHrDataTest: compressed type 0 and type 1 throw the SDK’s messages');
}
{
  const f = parsePmdFrame([0x14, 0, 0, 0, 0, 0, 0, 0, 0, 0x1, 72, 86, 71, 81, 64, 82]);
  const s = parseOfflineHrFrame(f);
  assert.equal(s.length, 2);
  assert.deepEqual(s[0], { hr: 72, ppgQuality: 86, correctedHr: 71 });
  assert.deepEqual(s[1], { hr: 81, ppgQuality: 64, correctedHr: 82 });
  ok('OfflineHrDataTest type 1: hr / PPG quality / corrected hr triples');
}
{
  const h = t => [0x0E, 0, 0, 0, 0, 0, 0, 0, 0x01, t];
  assert.throws(() => parseOfflineHrFrame(parsePmdFrame(h(0x00))), /TYPE_0 dataContent is empty/);
  assert.throws(() => parseOfflineHrFrame(parsePmdFrame(h(0x01))), /TYPE_1 dataContent size 0/);
  assert.throws(() => parseOfflineHrFrame(parsePmdFrame([...h(0x01), 0x48, 0x56, 0x47, 0x51])), /size 4 is not/);
  assert.throws(() => parsePmdFrame([0x0E, 0, 0]), /too short/);
  ok('OfflineHrDataTest bounds: empty type 0/1 and a non-multiple of 3 are rejected');
}
{
  // The SDK skips a frame it cannot parse and carries on; so does the file parser.
  const badFrame = [0x0e, 0, 0, 0, 0, 0, 0, 0, 0, 0x81, 1, 2, 3];
  const r = parseOfflineHrFile([...HR_FILE, badFrame.length, 0, ...badFrame]);
  assert.equal(r.samples.length, 9);
  assert.equal(r.errors.length, 1);
  ok('a bad frame is skipped and reported, the good ones kept');
}

// --- SDK vectors: PMD control point --------------------------------------------------------------

{
  assert.deepEqual([...offlineHrStartCommand()], [0x02, 0x8E]);
  assert.deepEqual([...offlineHrStopCommand()], [0x03, 0x0E]);
  assert.deepEqual([...measurementStatusCommand()], [0x05]);
  // BlePmdClientTest `offline recording type sets high bit`: OFFLINE.asBitField() | ACC = 0x82.
  assert.equal(0x80 | 2, 0x82);
  ok('offline HR start is [02 8E] (offline bit | 14), stop is [03 0E] (no bit), status is [05]');
}
{
  // BlePmdClientControlPointResponseTest.
  let r = parseControlPointResponse([0xF0, 0x01, 0x02, 0x00, 0x00, 0xFF, 0xFF, 0xFF]);
  assert.equal(r.op, 1); assert.equal(r.meas, 2); assert.equal(r.status, 0); assert.equal(r.more, false);
  assert.deepEqual([...r.params], [0xFF, 0xFF, 0xFF]);
  r = parseControlPointResponse([0xF0, 0x02, 0x0F, 0x11, 0x00]);
  assert.equal(r.statusText, 'invalid derived measurement settings group'); assert.equal(r.params.length, 0);
  r = parseControlPointResponse([0xF0, 0x02, 0x0F, 0x7F, 0x00]);
  assert.match(r.statusText, /unknown error 127/);
  r = parseControlPointResponse([0xF0, 0x01, 0x06, 0x07, 0x00]);
  assert.equal(r.ok, false); assert.equal(r.statusText, 'invalid resolution'); assert.equal(r.params.length, 0);
  assert.equal(parseControlPointResponse([0x01, 0x02]), null);
  ok('BlePmdClientControlPointResponseTest: success, codes 17 / unknown / 7, params only on success');
}
{
  // PmdActiveMeasurementTest.
  assert.equal(measurementState(0x80), 'offline'); assert.equal(measurementState(0xBF), 'offline');
  assert.equal(measurementState(0x40), 'online'); assert.equal(measurementState(0x7F), 'online');
  assert.equal(measurementState(0xC0), 'online+offline'); assert.equal(measurementState(0xFF), 'online+offline');
  assert.equal(measurementState(0x00), 'none'); assert.equal(measurementState(0x3F), 'none');
  assert.deepEqual(parseMeasurementStatus([0x02, 0x8E, 0x41]), { 2: 'none', 14: 'offline', 1: 'online' });
  ok('PmdActiveMeasurementTest: top two bits are the state, low six the type');
}

/** A PMD control point that answers from a script, like sensor.js's _pmdRequest would. */
function fakePmd(answers) {
  const sent = [];
  return { sent, async request(cmd) { sent.push([...cmd]); const a = answers.shift(); return typeof a === 'function' ? a(cmd) : a; } };
}

{
  let pmd = fakePmd([[0xF0, 0x02, 0x8E, 0x00, 0x00]]);
  assert.deepEqual(await startOfflineHr(pmd), { started: true, already: false });
  assert.deepEqual(pmd.sent, [[0x02, 0x8E]]);
  pmd = fakePmd([new DataView(new Uint8Array([0xF0, 0x02, 0x8E, 0x06, 0x00]).buffer)]);
  assert.deepEqual(await startOfflineHr(pmd), { started: false, already: true });
  pmd = fakePmd([{ raw: [0xF0, 0x02, 0x8E, 0x0E, 0x00] }]);
  await assert.rejects(startOfflineHr(pmd), /disk full.*2 MB/);
  pmd = fakePmd([[0xF0, 0x02, 0x8E, 0x0C, 0x00]]);
  await assert.rejects(startOfflineHr(pmd), /invalid state.*SDK mode/);
  ok('startOfflineHr: success, "already recording" kept, disk full / invalid state explained');
}
{
  let pmd = fakePmd([[0xF0, 0x05, 0x00, 0x00, 0x00, 0x02, 0x8E]]);
  assert.equal(await offlineHrActive(pmd), true);
  pmd = fakePmd([[0xF0, 0x05, 0x00, 0x00, 0x00, 0x42, 0x0E]]);
  assert.equal(await offlineHrActive(pmd), false);
  pmd = fakePmd([[0xF0, 0x05, 0x00, 0x00, 0x00, 0x42]]);
  assert.equal(await offlineHrActive(pmd), false);
  ok('offlineHrActive reads type 14 from GET_MEASUREMENT_STATUS');
}
{
  const pmd = fakePmd([[0xF0, 0x03, 0x0E, 0x00, 0x00],
                       [0xF0, 0x05, 0x00, 0x00, 0x00, 0x8E],
                       [0xF0, 0x05, 0x00, 0x00, 0x00, 0x0E]]);
  await stopOfflineHr(pmd, { pollMs: 1 });
  assert.deepEqual(pmd.sent, [[0x03, 0x0E], [0x05], [0x05]]);
  const stuck = fakePmd([[0xF0, 0x03, 0x0E, 0x00, 0x00], ...Array(50).fill([0xF0, 0x05, 0, 0, 0, 0x8E])]);
  await assert.rejects(stopOfflineHr(stuck, { pollMs: 1, timeoutMs: 20 }), /still reported active/);
  ok('stopOfflineHr: STOP then poll status until inactive, as waitForMeasurementInactive');
}

// --- protobuf ------------------------------------------------------------------------------------

{
  // PbPFtpOperation{GET, "/U/0/"}: 08 00 | 12 05 "/U/0/". proto2 writes the required GET (0).
  assert.equal(hex(encodeOperation(PFTP_COMMAND.GET, '/U/0/')), '08 00 12 05 2f 55 2f 30 2f');
  assert.equal(hex(encodeOperation(PFTP_COMMAND.REMOVE, '/A')), '08 03 12 02 2f 41');
  const big = 5 * 2 ** 32 + 7;
  assert.deepEqual(decodeDirectory(directoryBytes([['20250730/', 0], ['HR0.REC', 500050], ['X', big]])),
                   [{ name: '20250730/', size: 0 }, { name: 'HR0.REC', size: 500050 }, { name: 'X', size: big }]);
  ok('PbPFtpOperation encodes as protobuf; PbPFtpDirectory decodes, skipping timestamps, uint64 sizes');
}
{
  // PolarTimeUtilsTest `calendar conversion from GMT+1 to pbSystemTime`: 11:59:01.999 at +01:00.
  const f = pbDecode(encodeSetSystemTime(new Date(Date.UTC(2022, 0, 1, 10, 59, 1, 999))));
  const d = pbDecode(f[1][0]), t = pbDecode(f[2][0]);
  assert.deepEqual([d[1][0], d[2][0], d[3][0]], [2022, 1, 1]);
  assert.deepEqual([t[1][0], t[2][0], t[3][0], t[4][0]], [10, 59, 1, 999]);
  assert.equal(f[3][0], 1);                                  // trusted
  ok('PolarTimeUtilsTest: SET_SYSTEM_TIME carries UTC fields and trusted=true');
}
{
  // PolarTimeUtilsTest SetLocalTime vectors: GMT+1, GMT-1, GMT-12, GMT+14.
  const cases = [
    [Date.UTC(2022, 0, 1, 10, 59, 1, 0), 60, [11, 59, 1, 0]],
    [Date.UTC(2022, 0, 1, 12, 59, 1, 499), -60, [11, 59, 1, 499]],
    [Date.UTC(2022, 0, 1, 23, 59, 1, 999), -720, [11, 59, 1, 999]],
    [Date.UTC(2022, 0, 1, 9, 59, 1, 1), 840, [23, 59, 1, 1]],
  ];
  for (const [ms, tz, hmsm] of cases) {
    const bytes = encodeSetLocalTime(new Date(ms), tz), f = pbDecode(bytes);
    const d = pbDecode(f[1][0]), t = pbDecode(f[2][0]);
    assert.deepEqual([d[1][0], d[2][0], d[3][0]], [2022, 1, 1], `date for tz ${tz}`);
    assert.deepEqual([t[1][0], t[2][0], t[3][0], t[4][0]], hmsm, `time for tz ${tz}`);
    const at = bytes.lastIndexOf(0x18);                      // field 3, varint: the int32 offset
    assert.equal(varintBig(bytes, at + 1), BigInt(tz), `tz ${tz}`);
  }
  // A negative int32 is ten bytes on the wire, sign-extended.
  assert.equal(hex(encodeSetLocalTime(new Date(0), -60).slice(-11)), '18 c4 ff ff ff ff ff ff ff ff 01');
  ok('PolarTimeUtilsTest: SET_LOCAL_TIME wall clock + tz offset for +1, -1, -12, +14 (int32 sign-extended)');
}

// --- SDK vectors: RFC76 / RFC60 ------------------------------------------------------------------

{
  // BlePsFtpUtilsTest `process first frame of sequence more to come`.
  let d = [0x06, 0x0A, 0x06, 0x08, 0x02, 0x10, 0x04, 0x18, 0x03, 0x12, 0x06, 0x08, 0x00, 0x10, 0x09, 0x18, 0x05, 0x1A, 0x06, 0x08];
  let f = parseRfc76Frame(d);
  assert.equal(f.next, 0); assert.equal(f.status, 3); assert.equal(f.seq, 0);
  assert.deepEqual([...f.payload], d.slice(1));
  // `process middle frame of sequence more to come`.
  d = [0x97, 0x22, 0x0A, 0x03, 0x47, 0x50, 0x53, 0x1A, 0x1B, 0x08, 0x01, 0x10, 0x00, 0x18, 0x00, 0x22, 0x13, 0x61, 0x32, 0x30];
  f = parseRfc76Frame(d);
  assert.equal(f.next, 1); assert.equal(f.status, 3); assert.equal(f.seq, 9);
  assert.deepEqual([...f.payload], d.slice(1));
  // `process last frame of sequence no more data`.
  d = [0xC3, 0x5A, 0x48, 0x5F, 0x4A, 0x41, 0x10, 0x09];
  f = parseRfc76Frame(d);
  assert.equal(f.next, 1); assert.equal(f.status, 1); assert.equal(f.seq, 12);
  assert.deepEqual([...f.payload], d.slice(1));
  // Error frames: 16-bit little-endian code.
  assert.equal(parseRfc76Frame([0x00, 103, 0x00]).error, 103);
  assert.equal(parseRfc76Frame([0x00, 0x2F, 0x01]).error, 303);
  ok('BlePsFtpUtilsTest: first / middle / last frame headers; error frames carry a 16-bit code');
}
{
  // buildRfc76MessageFrame: MORE = 0x06, LAST = 0x02, next bit after the first, sequence << 4.
  const msg = rfc60Request(encodeOperation(PFTP_COMMAND.GET, '/U/0/'));
  assert.equal(hex(msg), '09 00 08 00 12 05 2f 55 2f 30 2f');
  assert.deepEqual(buildRfc76Frames(msg, 5).map(hex), ['06 09 00 08 00', '17 12 05 2f 55', '23 2f 30 2f']);
  assert.deepEqual(buildRfc76Frames(msg, 20).map(hex), ['02 ' + hex(msg)]);
  // Exactly filling the last packet is LAST, not MORE plus an empty packet.
  assert.deepEqual(buildRfc76Frames([1, 2, 3, 4, 5, 6, 7, 8], 5).map(hex), ['06 01 02 03 04', '13 05 06 07 08']);
  assert.deepEqual(buildRfc76Frames([], 20).map(hex), ['02']);
  // 17 packets: the sequence number wraps 15 -> 0.
  const many = buildRfc76Frames(new Uint8Array(17), 2);
  assert.deepEqual(many.map(f => f[0] >> 4), [...Array(16).keys(), 0]);
  // RFC60: request = LE length with bit 15 clear; query = id with bit 15 set.
  assert.deepEqual([...rfc60Query(3, [0xAA])], [0x03, 0x80, 0xAA]);
  assert.deepEqual([...rfc60Query(5)], [0x05, 0x80]);
  ok('RFC76 framing and RFC60 headers as BlePsFtpUtils builds them (incl. sequence wrap)');
}

// --- PSFTP client (BlePsFtpClientTest + iOS BlePsFtpClientTest) ----------------------------------

{
  // BlePsFtpClientTest `test psftp client request`: the device answers [0x02, 0x22].
  const reqData = [0x01, 0x38, 0x6C, 0x31, 0x72, 0xA4, 0xD3, 0x23, 0x0D, 0x7F];
  const mtu = new FakeChar(() => setTimeout(() => mtu.emit([0x02, 0x22]), 0));
  const c = new PsFtpClient({ mtu });
  await c.open();
  assert.equal(mtu.notifying, true);
  const r = await c.request(reqData);
  assert.deepEqual([...r], [0x22]);
  assert.deepEqual(mtu.writes.map(hex), buildRfc76Frames(rfc60Request(reqData), 20).map(hex));
  ok('BlePsFtpClientTest request: framed request on the MTU characteristic, payload 0x22 back');
}
{
  // BlePsFtpClientTest `test psftp client read response`: 13 frames, sequence 0..12.
  const frames = [
    [0x06, 0x0A, 0x06, 0x08, 0x02, 0x10, 0x04, 0x18, 0x03, 0x12, 0x06, 0x08, 0x00, 0x10, 0x09, 0x18, 0x05, 0x1A, 0x06, 0x08],
    [0x17, 0x02, 0x10, 0x00, 0x18, 0x07, 0x32, 0x08, 0x41, 0x31, 0x34, 0x37, 0x38, 0x43, 0x32, 0x43, 0x3A, 0x0E, 0x50, 0x6F],
    [0x27, 0x50, 0x6F, 0x6C, 0x61, 0x72, 0x20, 0x49, 0x4E, 0x57, 0x33, 0x4E, 0x5F, 0x42, 0x0B, 0x30, 0x30, 0x37, 0x38, 0x35],
    [0x37, 0x30, 0x30, 0x37, 0x38, 0x35, 0x36, 0x4A, 0x06, 0x43, 0x6F, 0x70, 0x70, 0x65, 0x72, 0x52, 0x06, 0x55, 0x6E, 0x69],
    [0x47, 0x55, 0x6E, 0x69, 0x5A, 0x10, 0x41, 0x30, 0x39, 0x45, 0x31, 0x41, 0x46, 0x46, 0x46, 0x45, 0x41, 0x31, 0x34, 0x37],
    [0x57, 0x41, 0x30, 0x62, 0x14, 0xC1, 0xA8, 0x78, 0xD5, 0x02, 0x4B, 0x46, 0x1D, 0xC6, 0x6D, 0x38, 0xED, 0x0E, 0x53, 0xB5],
    [0x67, 0xC1, 0xA8, 0x78, 0xD5, 0x02, 0x6A, 0x06, 0x08, 0x03, 0x10, 0x0B, 0x18, 0x00, 0x72, 0x10, 0x0A, 0x06, 0x42, 0x6C],
    [0x77, 0x42, 0x6C, 0x65, 0x41, 0x1A, 0x06, 0x08, 0x09, 0x10, 0x00, 0x18, 0x00, 0x72, 0x17, 0x0A, 0x0D, 0x42, 0x6C, 0x65],
    [0x87, 0x42, 0x6C, 0x65, 0x42, 0x6F, 0x6F, 0x74, 0x6C, 0x6F, 0x61, 0x1A, 0x06, 0x08, 0x04, 0x10, 0x01, 0x18, 0x00, 0x72],
    [0x97, 0x22, 0x0A, 0x03, 0x47, 0x50, 0x53, 0x1A, 0x1B, 0x08, 0x01, 0x10, 0x00, 0x18, 0x00, 0x22, 0x13, 0x61, 0x32, 0x30],
    [0xA7, 0x61, 0x32, 0x30, 0x30, 0x32, 0x30, 0x5F, 0x66, 0x34, 0x64, 0x33, 0x38, 0x36, 0x38, 0x5F, 0x31, 0x78, 0x01, 0x82],
    [0xB7, 0x82, 0x08, 0x0A, 0x06, 0x08, 0x03, 0x10, 0x00, 0x18, 0x02, 0x8A, 0x01, 0x0D, 0x0A, 0x09, 0x5A, 0x48, 0x5F, 0x4A],
    [0xC3, 0x5A, 0x48, 0x5F, 0x4A, 0x41, 0x10, 0x09],
  ];
  const mtu = new FakeChar(() => setTimeout(() => { for (const f of frames) mtu.emit(f); }, 0));
  const c = new PsFtpClient({ mtu });
  await c.open();
  const r = await c.get('/DEVICE.BPB');
  assert.deepEqual([...r], frames.flatMap(f => f.slice(1)));
  ok('BlePsFtpClientTest read response: 13 SDK frames reassembled exactly');
}
{
  // iOS testRequest_whenResponseSequenceNumberMismatches_throwsAirPacketLostError, then
  // _afterAirPacketLostError_subsequentRequestSucceeds and _stalePacketsDoNotPoisonNextRequest.
  const answers = [[0x12, 0x00], [0x00, 0x00, 0x00]];
  const mtu = new FakeChar(b => { if ((b[0] >> 1) & 3) setTimeout(() => mtu.emit(answers.shift()), 0); });
  const c = new PsFtpClient({ mtu });
  await c.open();
  await assert.rejects(c.request([0x00]), e => e instanceof PsFtpError && e.code === 303);
  mtu.emit([0x02, 0xBA, 0xD0]);                              // stale frames arriving late
  mtu.emit([0x02, 0xBA, 0xD1]);
  const r = await c.request([0x00]);
  assert.equal(r.length, 0);
  ok('iOS BlePsFtpClientTest: sequence mismatch -> 303; next request recovers despite stale packets');
}
{
  // A mismatch in the middle of a MORE stream sends the cancel packet [00 00 00], as the SDK.
  const mtu = new FakeChar(b => { if ((b[0] >> 1) & 3) setTimeout(() => { mtu.emit([0x06, 1]); mtu.emit([0x27, 2]); }, 0); });
  const c = new PsFtpClient({ mtu });
  await c.open();
  await assert.rejects(c.request([0x00]), e => e.code === 303);
  assert.equal(hex(mtu.writes.at(-1)), '00 00 00');
  ok('lost air packet mid-stream: stream cancelled with [00 00 00] before the error');
}
{
  const band = new FakeBand(op => (op.path === '/busy' ? { error: 202 } : { error: 103 }));
  const c = band.client();
  await c.open();
  await assert.rejects(c.get('/nope'), e => e.code === 103 && /NO_SUCH_FILE_OR_DIRECTORY/.test(e.message));
  await assert.rejects(c.get('/busy'), e => e.code === 202 && /sensor mode/.test(e.message));
  const silent = new PsFtpClient({ mtu: new FakeChar() }, { timeoutMs: 20 });
  await silent.open();
  await assert.rejects(silent.get('/x'), e => e.code === 108);
  ok('error frames become PsFtpError (103, 202 with the sensor-mode hint); silence times out');
}
{
  // Device sends 3-byte packets: a 60-byte file is 20 packets, so the sequence wraps mid-response.
  const band = new FakeBand(() => Uint8Array.from(HR_FILE), { devicePacket: 4 });
  const c = band.client();
  await c.open();
  const [a, b] = await Promise.all([c.get('/U/0/A/HR.REC'), c.get('/U/0/B/HR.REC')]);
  assert.deepEqual([...a], HR_FILE);
  assert.deepEqual([...b], HR_FILE);
  assert.deepEqual(band.log.map(o => o.path), ['/U/0/A/HR.REC', '/U/0/B/HR.REC']);
  ok('long responses survive the sequence wrap; concurrent calls are serialised, not interleaved');
}
{
  // fromServer: service and characteristics looked up by the full UUIDs, notifications on.
  const band = new FakeBand(() => null);
  const chars = { [PSFTP_MTU_CHAR]: band.mtu, [PSFTP_D2H_CHAR]: band.d2h, [PSFTP_H2D_CHAR]: band.h2d };
  const asked = [];
  const server = { async getPrimaryService(u) { asked.push(u); return { async getCharacteristic(c) { asked.push(c); return chars[c]; } }; } };
  const c = await PsFtpClient.fromServer(server);
  assert.deepEqual(asked, [PSFTP_SERVICE, PSFTP_MTU_CHAR, PSFTP_D2H_CHAR, PSFTP_H2D_CHAR]);
  assert.equal(band.mtu.notifying && band.d2h.notifying, true);
  assert.deepEqual(OFFLINE_OPTIONAL_SERVICES, ['0000feee-0000-1000-8000-00805f9b34fb']);
  await c.sendNotification(8);
  assert.deepEqual(band.h2d.writes.map(hex), ['02 08']);
  ok('fromServer uses the BlePsFtpUtils UUIDs; H2D notification INITIALIZE_SESSION is [02 08]');
}
{
  // setLocalTime: SET_SYSTEM_TIME (1) then SET_LOCAL_TIME (3); a system-time failure is ignored.
  const band = new FakeBand(op => (op.id === PFTP_QUERY.SET_SYSTEM_TIME ? { error: 201 } : null));
  const c = band.client();
  await c.open();
  const when = new Date(Date.UTC(2026, 9, 22, 6, 30, 0, 250));
  await setDeviceTime(c, when, { tzOffsetMin: -240 });
  assert.deepEqual(band.log.map(o => o.id), [1, 3]);
  assert.equal(hex(band.log[0].params), hex(encodeSetSystemTime(when)));
  assert.equal(hex(band.log[1].params), hex(encodeSetLocalTime(when, -240)));
  const t = pbDecode(pbDecode(band.log[1].params)[2][0]);
  assert.deepEqual([t[1][0], t[2][0], t[3][0], t[4][0]], [2, 30, 0, 250]);   // 06:30Z at -04:00
  // GET_DISK_SPACE: fragment size x counts.
  const disk = new FakeBand(() => new Uint8Array([0x08, ...varint(4096), 0x10, ...varint(1000), 0x18, ...varint(500)]));
  const dc = disk.client();
  await dc.open();
  assert.deepEqual(await getDiskSpace(dc), { totalBytes: 4096000, freeBytes: 2048000 });
  assert.equal(disk.log[0].id, 5);
  ok('setDeviceTime sends system then local time (as BDBleApiImpl); getDiskSpace decodes fragments');
}

// --- SDK vectors: listing (PolarOfflineRecordingUtilsTest) ---------------------------------------

{
  // listOfflineRecordingsV1 merges split REC files.
  const files = [['/U/0/20250730/R/101010/ACC0.REC', 500120], ['/U/0/20250730/R/101010/ACC1.REC', 500103],
                 ['/U/0/20250730/R/101010/ACC2.REC', 102325], ['/U/0/20250730/R/101010/HR0.REC', 500000],
                 ['/U/0/20250730/R/101010/HR1.REC', 500050], ['/U/0/20250730/R/101010/PPG0.REC', 300]];
  const e = groupRecordingFiles(files);
  const by = t => e.filter(x => x.path.includes(t));
  assert.equal(by('ACC').length, 1); assert.equal(by('ACC')[0].size, 500120 + 500103 + 102325);
  assert.equal(by('HR').length, 1); assert.equal(by('HR')[0].size, 500000 + 500050);
  assert.equal(by('PPG').length, 1); assert.equal(by('PPG')[0].size, 300);
  assert.equal(by('HR')[0].path, '/U/0/20250730/R/101010/HR.REC');
  assert.ok(e.every(x => x.path.endsWith('.REC')));
  // ... does not return empty files.
  files[2][1] = 0; files[4][1] = 0; files[5][1] = 0;
  const e2 = groupRecordingFiles(files);
  assert.equal(e2.find(x => x.type === 'ACC').size, 500120 + 500103);
  assert.equal(e2.find(x => x.type === 'HR').size, 500000);
  assert.equal(e2.filter(x => x.type === 'PPG').length, 0);
  ok('PolarOfflineRecordingUtilsTest V1: split parts merged, sizes summed, empty parts ignored');
}
{
  const txt = ['500120 /U/0/20250730/R/101010/ACC0.REC', '500103 /U/0/20250730/R/101010/ACC1.REC',
               '102325 /U/0/20250730/R/101010/ACC2.REC', '500000 /U/0/20250730/R/101010/HR0.REC',
               '500050 /U/0/20250730/R/101010/HR1.REC', '300 /U/0/20250730/R/101010/PPG0.REC'].join('\n');
  const e = parsePmdFilesTxt(new TextEncoder().encode(txt));
  assert.equal(e.find(x => x.type === 'ACC').size, 500120 + 500103 + 102325);
  assert.equal(e.find(x => x.type === 'HR').size, 500000 + 500050);
  assert.equal(e.find(x => x.type === 'HR').path, '/U/0/20250730/R/101010/HR.REC');
  assert.equal(e.find(x => x.type === 'PPG').size, 300);
  const e2 = parsePmdFilesTxt('500120 /U/0/20250730/R/101010/ACC0.REC\n500103 /U/0/20250730/R/101010/ACC1.REC\n'
    + '0 /U/0/20250730/R/101010/ACC2.REC\n500050 /U/0/20250730/R/101010/HR0.REC\n'
    + '0 /U/0/20250730/R/101010/HR1.REC\n0 /U/0/20250730/R/101010/PPG0.REC');
  assert.equal(e2.find(x => x.type === 'ACC').size, 500120 + 500103);
  assert.equal(e2.find(x => x.type === 'HR').size, 500050);
  assert.equal(e2.filter(x => x.type === 'PPG').length, 0);
  ok('PolarOfflineRecordingUtilsTest V2: PMDFILES.TXT merged and empty parts ignored');
}
{
  // ... maps all supported measurement types correctly (V1 and V2).
  const types = ['ACC', 'GYRO', 'MAG', 'PPG', 'PPI', 'HR', 'TEMP', 'SKINTEMP'];
  const lines = types.map((t, i) => `100 /U/0/20240101/R/12000${i}/${t}0.REC`);
  const v2 = parsePmdFilesTxt(lines.join('\n'));
  assert.equal(v2.length, 8);
  assert.deepEqual(new Set(v2.map(x => x.type)), new Set(types));
  const v1 = groupRecordingFiles(lines.map(l => [l.split(' ')[1], 100]));
  assert.deepEqual(new Set(v1.map(x => x.type)), new Set(types));
  assert.equal(recordingType('SKINTEMP3.REC'), 'SKINTEMP');
  assert.equal(recordingType('FOO0.REC'), null);
  ok('PolarOfflineRecordingUtilsTest: all eight file types map (V1 and V2)');
}
{
  // ... parses date and time correctly; separate entries for different dates; edge lines.
  const local = new Date(2023, 10, 15, 8, 30, 45).getTime();
  assert.equal(parsePmdFilesTxt('1024 /U/0/20231115/R/083045/HR0.REC\n')[0].date.getTime(), local);
  assert.equal(groupRecordingFiles([['/U/0/20231115/R/083045/HR0.REC', 1024]])[0].date.getTime(), local);
  const two = parsePmdFilesTxt('500 /U/0/20240101/R/080000/ACC0.REC\n500 /U/0/20240102/R/080000/ACC0.REC');
  assert.deepEqual(two.map(x => x.date.getTime()).sort(), [new Date(2024, 0, 1, 8).getTime(), new Date(2024, 0, 2, 8).getTime()]);
  assert.equal(groupRecordingFiles([['/U/0/20240101/R/080000/ACC0.REC', 500], ['/U/0/20240102/R/080000/ACC0.REC', 500]]).length, 2);
  assert.deepEqual(parsePmdFilesTxt(new Uint8Array(0)), []);
  assert.deepEqual(groupRecordingFiles([]), []);
  assert.equal(parsePmdFilesTxt('500 /U/0/20240101/R/080000/ACC0.TXT\n400 /U/0/20240101/R/080000/HR0.REC').length, 1);
  assert.equal(parsePmdFilesTxt('500\n400 /U/0/20240101/R/080000/HR0.REC').length, 1);
  assert.equal(parsePmdFilesTxt('NaN /U/0/20240101/R/080000/ACC0.REC\n400 /U/0/20240101/R/080000/HR0.REC').length, 1);
  assert.equal(parsePmdFilesTxt('12345 /U/0/20240101/R/080000/ACC0.REC\n')[0].size, 12345);
  assert.equal(groupRecordingFiles([['/U/0/20240101/R/080000/ACC0.REC', 12345]])[0].size, 12345);
  assert.equal(parsePmdFilesTxt('5 /U/0/20241301/R/080000/HR0.REC').length, 0);      // month 13
  // A time in a DST spring-forward gap is still a recording, not dropped.
  assert.equal(groupRecordingFiles([['/U/0/20250309/R/023000/HR0.REC', 9]]).length, 1);
  ok('PolarOfflineRecordingUtilsTest: dates (phone-local), per-date entries, bad lines skipped');
}

// --- listing / fetch / remove against a fake band (iOS PolarOfflineRecordingApiTests) ------------

{
  // makeV1Mocks: no PMDFILES.TXT -> walk /U/0/ -> one HR.REC of 444 bytes.
  const band = fileSystemBand({ '/U/0/20250309/R/030000/HR.REC': new Uint8Array(444) });
  const c = band.client(); await c.open();
  const e = await listOfflineRecordings(c);
  assert.deepEqual(e.map(x => [x.path, x.size, x.type]), [['/U/0/20250309/R/030000/HR.REC', 444, 'HR']]);
  assert.deepEqual(band.log.map(o => o.path), ['/PMDFILES.TXT', '/U/0/', '/U/0/20250309/', '/U/0/20250309/R/',
                                               '/U/0/20250309/R/030000/']);
  ok('iOS V1 listing: PMDFILES.TXT missing -> recursive walk finds HR.REC (444 bytes)');
}
{
  // test_listOfflineRecordings_v2Path_emptyPmdFileTxt_fallsBackToV1WithNoEntries, and V1 zero size.
  let band = fileSystemBand({ '/PMDFILES.TXT': new Uint8Array(0) });
  band.emptyDirs.add('/U/0/');
  let c = band.client(); await c.open();
  assert.deepEqual(await listOfflineRecordings(c), []);
  band = fileSystemBand({ '/PMDFILES.TXT': new Uint8Array(0), '/U/0/20240615/R/103000/ACC.REC': new Uint8Array(0) });
  c = band.client(); await c.open();
  assert.deepEqual(await listOfflineRecordings(c), []);
  band = fileSystemBand({ '/PMDFILES.TXT': new Uint8Array(0), '/U/0/20240615/R/103000/ACC.REC': new Uint8Array(2048) });
  c = band.client(); await c.open();
  assert.deepEqual((await listOfflineRecordings(c)).map(x => [x.type, x.size]), [['ACC', 2048]]);
  ok('iOS: empty PMDFILES.TXT falls back to V1; zero-size files ignored; ACC.REC 2048 listed');
}
{
  // V2 path: PMDFILES.TXT present -> one GET, nothing walked.
  const band = fileSystemBand({ '/PMDFILES.TXT': new TextEncoder().encode('1024 /U/0/20240615/R/103000/HR0.REC\n') });
  const c = band.client(); await c.open();
  const e = await listOfflineRecordings(c);
  assert.deepEqual(e.map(x => [x.path, x.size]), [['/U/0/20240615/R/103000/HR.REC', 1024]]);
  assert.deepEqual(band.log.map(o => o.path), ['/PMDFILES.TXT']);
  ok('V2 listing: PMDFILES.TXT is used when present');
}
{
  // test_getSubRecordingCount_countsMatchingTypeFiles. ADAPTED: the iOS test names the entry
  // ".../ACC0.REC" (iOS lists by first part); this port lists as Android does (".../ACC.REC"), and
  // Android's prefix rule then counts the same two parts.
  const band = fileSystemBand({ '/U/0/20240615/R/103000/ACC0.REC': new Uint8Array(10),
                                '/U/0/20240615/R/103000/ACC1.REC': new Uint8Array(20),
                                '/U/0/20240615/R/103000/GYRO0.REC': new Uint8Array(30) });
  const c = band.client(); await c.open();
  assert.deepEqual(await subRecordingCounts(c, { path: '/U/0/20240615/R/103000/ACC.REC' }), [2, 1]);
  // test_getSubRecordingCount_directoryNotFound_returnsZero.
  assert.deepEqual(await subRecordingCounts(c, { path: '/U/0/20990101/R/000000/ACC.REC' }), [0, 0]);
  assert.equal(subRecordingPath('/U/0/20240615/R/103000/HR.REC', 2), '/U/0/20240615/R/103000/HR2.REC');
  ok('getSubRecordingCount: two ACC parts beside a GYRO file; missing directory -> 0');
}
{
  // test_getOfflineRecord_missingDataInSubrecording: directory 103, file empty -> error, not data.
  const band = new FakeBand(op => (op.path.endsWith('/') ? { error: 103 } : new Uint8Array(0)));
  const c = band.client(); await c.open();
  const files = await fetchRecordingFiles(c, { path: '/U/0/20240615/R/103000/HR.REC' });
  assert.deepEqual(band.log.map(o => o.path), ['/U/0/20240615/R/103000/', '/U/0/20240615/R/103000/HR.REC']);
  assert.throws(() => parseOfflineHrFile(files[0]), /empty/);
  ok('iOS missing-data case: unsplit path fetched directly; an empty file is an error, not zero samples');
}
{
  // test_removeOfflineRecord_removesSubrecordings_andDeletesEmptyParentDirectories. ADAPTED as
  // above (entry ".../ACC.REC"). Android's order: parts one by one (a GYRO file shares the
  // directory), then each parent removed once empty -- here the GYRO file is gone by then.
  const band = fileSystemBand({ '/U/0/20240615/R/103000/ACC0.REC': new Uint8Array(50),
                                '/U/0/20240615/R/103000/ACC1.REC': new Uint8Array(50),
                                '/U/0/20240615/R/103000/GYRO0.REC': new Uint8Array(50) });
  const c = band.client(); await c.open();
  await removeOfflineRecord(c, { path: '/U/0/20240615/R/103000/ACC.REC' });
  assert.deepEqual(band.removed, ['/U/0/20240615/R/103000/ACC0.REC', '/U/0/20240615/R/103000/ACC1.REC']);
  assert.ok(band.fs.has('/U/0/20240615/R/103000/GYRO0.REC'), 'the other recording is left alone');
  band.fs.delete('/U/0/20240615/R/103000/GYRO0.REC');
  for (const d of ['/U/0/20240615/R/103000/', '/U/0/20240615/R/', '/U/0/20240615/']) band.emptyDirs.add(d);
  band.fs.set('/U/0/20240615/R/103000/ACC0.REC', new Uint8Array(50));
  band.removed = [];
  await removeOfflineRecord(c, { path: '/U/0/20240615/R/103000/ACC.REC' });
  assert.deepEqual(band.removed, ['/U/0/20240615/R/103000/', '/U/0/20240615/R/', '/U/0/20240615/']);
  ok('removeOfflineRecord: parts removed beside another recording; a lone one takes its empty parents');
}

// --- end to end ----------------------------------------------------------------------------------

/** An HR file built from the SDK vector with a chosen start time and samples (type 1 frames). */
function hrFile(start, hrs) {
  const f = [...HR_FILE.slice(0, 17), ...ascii(start), 0, 0x00, 0x00];
  const frame = [0x0e, 0, 0, 0, 0, 0, 0, 0, 0, 0x01, ...hrs.flatMap(h => [h, 90, h])];
  return Uint8Array.from([...f, frame.length & 0xFF, frame.length >> 8, ...frame]);
}

{
  // A run whose HR recording was split in two parts, an older HR recording, and an ACC recording.
  const band = fileSystemBand({
    '/U/0/20261022/R/070000/HR0.REC': hrFile('2026-10-22 11:00:00', [140, 141, 0, 143]),
    '/U/0/20261022/R/070000/HR1.REC': hrFile('2026-10-22 11:00:04', [144, 145]),
    '/U/0/20261021/R/060000/HR.REC': hrFile('2026-10-21 10:00:00', [100, 101]),
    '/U/0/20261022/R/080000/ACC0.REC': Uint8Array.from(ACC_META),
  }, { devicePacket: 9 });
  const c = band.client(); await c.open();
  const { samples, entries, recordings } = await fetchOfflineHr(c);
  assert.deepEqual(entries.map(e => e.path).sort(), ['/U/0/20261021/R/060000/HR.REC', '/U/0/20261022/R/070000/HR.REC']);
  const base = Date.UTC(2026, 9, 22, 11, 0, 0), prev = Date.UTC(2026, 9, 21, 10, 0, 0);
  assert.deepEqual(samples.map(s => [s.t, s.hr]), [
    [prev, 100], [prev + 1000, 101],
    [base, 140], [base + 1000, 141], [base + 3000, 143], [base + 4000, 144], [base + 5000, 145]]);
  assert.ok(!band.log.some(o => o.path.includes('ACC0.REC')), 'ACC is never fetched');
  const run = recordings.find(r => r.entry.path.includes('070000'));
  assert.equal(run.count, 6);
  assert.equal(run.startMs, base);
  assert.equal(run.dirMinusHeaderMs, new Date(2026, 9, 22, 7, 0, 0).getTime() - base);
  // since, keepZero.
  const later = await fetchOfflineHr(c, { since: new Date(base + 2000), keepZero: true });
  assert.deepEqual(later.samples.map(s => s.hr), [0, 143, 144, 145]);
  // Then delete both HR recordings; the ACC one stays.
  const results = await removeRecordings(c, entries);
  assert.ok(results.every(r => r.ok));
  assert.deepEqual([...band.fs.keys()], ['/U/0/20261022/R/080000/ACC0.REC']);
  assert.deepEqual(await fetchOfflineHr(c).then(r => r.samples), []);
  ok('fetchOfflineHr: lists, picks HR, joins split parts on one clock, drops zeros, merges in time');
}
{
  // removeRecordings keeps going past a failure and reports it.
  const band = new FakeBand(op => (op.command === PFTP_COMMAND.REMOVE ? { error: 202 } : directoryBytes([])));
  const c = band.client(); await c.open();
  const r = await removeRecordings(c, [{ path: '/U/0/20260101/R/000000/HR.REC' }, { path: '/U/0/20260102/R/000000/HR.REC' }]);
  assert.deepEqual(r.map(x => [x.ok, x.error && x.error.code]), [[false, 202], [false, 202]]);
  ok('removeRecordings reports each failure (SYSTEM_BUSY) without stopping');
}

console.log(`\npolar-offline: ${passed} checks passed`);
