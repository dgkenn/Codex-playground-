// The radio cannot be tested here. Everything that decides what a reading MEANS can be, and that is
// where the damage happens — a driver that fails to connect is obvious, one that fabricates is not.

import assert from 'node:assert/strict';
import { parseHeartRate, parseAccFrame, startCommand, accMagnitude,
         VeritySensor, STALE_HR_MS, withTimeout, PICKER_TIMEOUT_MS,
         describeError, GATT_ATTEMPTS, HR_STALL_MS, ARMBAND_KEY } from '../sensor.js';

const dv = bytes => new DataView(new Uint8Array(bytes).buffer);

/// The connect watchdog's budget, for the ordering assertion below.
const CONNECT_BUDGET_HINT = 20000;

// --- heart rate ----------------------------------------------------------------------------------

{
  // flags=0x00: 8-bit HR, no RR.
  assert.deepEqual(parseHeartRate(dv([0x00, 142])), { hr: 142, rr: [] });
  console.log('  ok  8-bit heart rate');
}
{
  // flags=0x01: 16-bit HR.
  assert.equal(parseHeartRate(dv([0x01, 0x2C, 0x01])).hr, 300);
  console.log('  ok  16-bit heart rate');
}
{
  // flags=0x10: RR present, in 1/1024 s units. 1024 -> exactly 1000 ms.
  const { hr, rr } = parseHeartRate(dv([0x10, 60, 0x00, 0x04, 0x00, 0x02]));
  assert.equal(hr, 60);
  assert.equal(rr.length, 2);
  assert.ok(Math.abs(rr[0] - 1000) < 0.001, `1024 units should be 1000 ms, got ${rr[0]}`);
  assert.ok(Math.abs(rr[1] - 500) < 0.001);
  console.log('  ok  RR intervals convert from 1/1024 s, not treated as milliseconds');
}
{
  // flags=0x18: energy expended present AND RR present. The energy field must be skipped or every
  // RR value afterwards is read from the wrong offset.
  const { hr, rr } = parseHeartRate(dv([0x18, 70, 0xFF, 0xFF, 0x00, 0x04]));
  assert.equal(hr, 70);
  assert.equal(rr.length, 1);
  assert.ok(Math.abs(rr[0] - 1000) < 0.001, 'energy-expended field was not skipped');
  console.log('  ok  the energy-expended field is skipped before RR');
}

// --- PMD command encoding ------------------------------------------------------------------------

{
  const cmd = startCommand(0x02, [[0x02, 8], [0x00, 52], [0x01, 16]]);
  assert.deepEqual([...cmd], [0x02, 0x02,
                              0x02, 0x01, 8, 0,       // RANGE, 2 bytes
                              0x00, 0x01, 52, 0,      // SAMPLE_RATE, 2 bytes
                              0x01, 0x01, 16, 0]);    // RESOLUTION, 2 bytes
  console.log('  ok  ACC start command matches Polar’s verified byte sequence');
}
{
  // CHANNELS is ONE byte. As uint16 it writes an extra byte and misaligns everything after it.
  const cmd = startCommand(0x02, [[0x04, 3]]);
  assert.deepEqual([...cmd], [0x02, 0x02, 0x04, 0x01, 3]);
  console.log('  ok  CHANNELS is encoded as one byte, not two');
}

// --- accelerometer frames ------------------------------------------------------------------------

{
  // frameType 0x01 with bit 7 clear = 16-bit UNCOMPRESSED, not delta. Running these through the
  // delta decoder is the classic third-party bug.
  const f = [0x02, 0,0,0,0,0,0,0,0, 0x01];
  const push = (x,y,z) => f.push(x & 0xff, (x>>8)&0xff, y & 0xff, (y>>8)&0xff, z & 0xff, (z>>8)&0xff);
  push(100, 200, 4096); push(110, 210, 4100);
  const s = parseAccFrame(dv(f));
  assert.equal(s.length, 2);
  assert.deepEqual(s[0], [100, 200, 4096]);
  console.log('  ok  frame type 0x01 parses as uncompressed, not delta');
}
{
  // Compression is bit 7 only: 0x81 = compressed, 16-bit reference layout.
  const f = [0x02, 0,0,0,0,0,0,0,0, 0x81,
             100,0, 200,0, 0,16,          // reference sample (100, 200, 4096)
             4, 2];                        // 4-bit deltas, 2 samples
  // Six 4-bit deltas of +1 -> three bytes 0x11 0x11 0x11
  f.push(0x11, 0x11, 0x11);
  const s = parseAccFrame(dv(f));
  assert.equal(s.length, 3, 'reference plus two delta samples');
  assert.deepEqual(s[0], [100, 200, 4096]);
  assert.deepEqual(s[1], [101, 201, 4097]);
  assert.deepEqual(s[2], [102, 202, 4098]);
  console.log('  ok  delta frames decode against the reference sample');
}
{
  assert.equal(parseAccFrame(dv([0x03, 0,0,0,0,0,0,0,0, 0x01])), null,
    'a PPI frame must not be parsed as accelerometer');
  console.log('  ok  a non-ACC measurement is refused');
}
{
  // Full scale is +/-8 G over 16 bits, so 4096 counts is 1 g.
  assert.ok(Math.abs(accMagnitude([0, 0, 4096]) - 1) < 0.01);
  console.log('  ok  accelerometer counts convert to g');
}

// --- the staleness rule --------------------------------------------------------------------------

{
  const s = new VeritySensor();
  const t0 = 1_000_000;
  s.hr = 150; s.hrAt = t0;
  assert.equal(s.hrFresh(t0 + 1000), true);
  assert.equal(s.hrFresh(t0 + STALE_HR_MS + 1), false,
    'a heart rate that stopped arriving must not read as current');
  console.log('  ok  a stale heart rate is not reported as current');
}
{
  const s = new VeritySensor();
  s.accWindow = [0.30, 0.31, 0.29, 0.32, 0.30, 0.31];
  const sd = s.takeAccSd();
  assert.ok(sd > 0 && sd < 0.05, `movement sd ${sd}`);
  assert.equal(s.accWindow.length, 0, 'the window must be consumed, not re-averaged next second');
  assert.equal(s.takeAccSd(), null, 'too few samples yields null, not a fabricated zero');
  console.log('  ok  movement sd is computed then the window consumed');
}

// --- the connect watchdog ------------------------------------------------------------------------

{
  // A promise that never settles must become a named failure, not a permanent "connecting".
  const never = new Promise(() => {});
  const started = Date.now();
  await assert.rejects(
    withTimeout(never, 40, 'connecting to the band'),
    /timed out after 0.04s while connecting to the band/,
    'a hung GATT connect must fail loudly and say which step hung');
  assert.ok(Date.now() - started < 1000);
  console.log('  ok  a connect that never answers times out and names the step');
}
{
  // And the watchdog must not fire on a connect that succeeded, nor leave a timer holding the
  // process open — a stray handle here is a page that never settles down between runs.
  assert.equal(await withTimeout(Promise.resolve('server'), 5000, 'connecting'), 'server');
  await assert.rejects(withTimeout(Promise.reject(new Error('GATT busy')), 5000, 'connecting'),
                       /GATT busy/, 'a real error must survive the race unchanged');
  console.log('  ok  the watchdog passes success and real errors through untouched');
}

// --- choosing a device ---------------------------------------------------------------------------
//
// The reported failure: the picker appears, lists the armband, and `requestDevice` never settles
// when the row is tapped. The step stays on "asking for the device" for ever and nothing tells the
// difference between that and a slow connection. These cover the three answers to it.

// Node defines `navigator` as a getter-only global, so it is replaced by its property descriptor
// rather than by assignment, and restored the same way.
const fakeBluetooth = impl => {
  const prev = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator',
                        { value: { bluetooth: impl }, configurable: true, writable: true });
  return () => {
    if (prev) Object.defineProperty(globalThis, 'navigator', prev);
    else delete globalThis.navigator;
  };
};

{
  // A remembered device is used without opening the picker at all. This is the route around the
  // broken part: Bluefy offers to remember the permission, and a remembered device needs no tap.
  let pickerOpened = false;
  const restore = fakeBluetooth({
    getDevices: async () => [{ name: 'Polar Sense 16961D33' }],
    requestDevice: async () => { pickerOpened = true; return { name: 'nope' }; },
  });
  const s = new VeritySensor();
  const steps = [];
  s.onStep = m => steps.push(m);
  // _attach needs a GATT server; the point here is which device was chosen, so stop before that.
  s.device = null;
  const known = await s.remembered();
  assert.equal(known.length, 1);
  assert.equal(pickerOpened, false, 'a remembered device must not open the picker');
  restore();
  console.log('  ok  a remembered device is found without opening the picker');
}

{
  // A picker that never resolves must become a stated failure. Before this it was an await with no
  // timeout, which is indistinguishable from the app having died.
  const restore = fakeBluetooth({
    getDevices: async () => [],
    requestDevice: () => new Promise(() => {}),      // exactly the reported behaviour
  });
  const s = new VeritySensor();
  const started = Date.now();
  // Reach into the same helper the connect path uses, at a testable scale.
  await assert.rejects(
    withTimeout(navigator.bluetooth.requestDevice({}), 40, 'waiting for the device picker'),
    /timed out .* waiting for the device picker/,
    'a picker that never returns must fail loudly');
  assert.ok(Date.now() - started < 1000);
  assert.ok(PICKER_TIMEOUT_MS > CONNECT_BUDGET_HINT,
    'the picker budget must exceed the connect budget — a person is choosing from a list');
  restore();
  console.log('  ok  a picker that never returns times out instead of hanging for ever');
}

{
  // The diagnostics object is how a failure gets from the phone to the fix, so it has to carry the
  // fields that distinguish the failure modes: connected-but-silent, never-connected, and
  // connected-and-streaming are three different bugs.
  const s = new VeritySensor();
  const st = s.state();
  for (const k of ['step', 'connected', 'gattConnected', 'deviceName', 'hr', 'hrAgeMs',
                   'hrCount', 'rrCount', 'accFrames', 'lastError']) {
    assert.ok(k in st, `sensor diagnostics must report ${k}`);
  }
  assert.equal(st.hrCount, 0);
  assert.equal(st.lastError, null);
  console.log('  ok  the sensor reports enough state to tell the failure modes apart');
}

// --- reporting what went wrong -------------------------------------------------------------------

{
  // The line that made this necessary, in full: `failed at "connecting": Error — undefined`. The
  // bridge rejected with something that was not an Error, and printing `e.name` and `e.message`
  // produced a sentence that looked like a diagnosis and contained nothing. Every shape a bridge
  // has actually thrown is covered here, because the one that is not covered is the one that will
  // come back as "undefined" on a phone with no console.
  assert.match(describeError(undefined), /no reason at all/);
  assert.match(describeError(null), /null/);
  assert.equal(describeError('GATT operation failed'), 'GATT operation failed');
  assert.match(describeError(''), /empty string/);
  assert.equal(describeError(new Error('boom')), 'Error: boom');

  const dom = new Error('Connection failed');
  dom.name = 'NetworkError';
  dom.code = 19;
  assert.equal(describeError(dom), 'NetworkError: Connection failed: code 19');

  // A plain object with nothing standard on it must still yield its contents.
  assert.match(describeError({ reason: 'busy', peripheral: 'Polar' }),
               /reason=busy.*peripheral=Polar/);
  // And one with nothing at all must say so rather than printing "[object Object]".
  assert.match(describeError({}), /no readable properties/);
  assert.doesNotMatch(describeError({}), /\[object Object\]/);

  assert.match(describeError(42), /number: 42/);
  for (const v of [undefined, null, '', {}, 42, new Error('x'), Symbol.iterator]) {
    const out = describeError(v);
    assert.equal(typeof out, 'string');
    assert.ok(out.length > 0, `describeError(${String(v)}) produced nothing`);
    assert.doesNotMatch(out, /undefined$/, `describeError(${String(v)}) still ends in "undefined"`);
  }
  console.log('  ok  anything thrown becomes something readable, never "undefined"');
}

// --- opening the link ----------------------------------------------------------------------------

const fakeDevice = ({ failures = 0, connectedAfterReject = false, throwValue = undefined } = {}) => {
  let attempts = 0;
  const gatt = {
    connected: false,
    connect() {
      attempts += 1;
      if (attempts <= failures) {
        if (connectedAfterReject) gatt.connected = true;   // a bridge that lies about the outcome
        return Promise.reject(throwValue);
      }
      gatt.connected = true;
      return Promise.resolve(gatt);
    },
    disconnect() { gatt.connected = false; },
  };
  return { name: 'Polar Sense', gatt, get attempts() { return attempts; } };
};

{
  // Two failures then success. A first-attempt failure is routine on iOS bridges, and giving up on
  // it is the difference between "armband unusable" and a pause nobody notices.
  const s = new VeritySensor();
  s.device = fakeDevice({ failures: 2 });
  const server = await s._openGatt();
  assert.equal(server.connected, true);
  assert.equal(s.device.attempts, 3, 'it must retry rather than fail on the first attempt');
  console.log('  ok  a connection that fails twice still succeeds on the third attempt');
}

{
  // The reported failure: rejected with `undefined`, every time. It must end as a stated failure
  // that names what to do, not as the word "undefined".
  const s = new VeritySensor();
  s.device = fakeDevice({ failures: 99 });
  await assert.rejects(s._openGatt(), err => {
    assert.match(err.message, new RegExp(`after ${GATT_ATTEMPTS} attempts`));
    assert.match(err.message, /no reason at all/, 'it must describe the valueless rejection');
    assert.match(err.message, /Polar Flow/, 'and say the most likely cause');
    assert.doesNotMatch(err.message, /undefined\./);
    return true;
  });
  assert.equal(s.device.attempts, GATT_ATTEMPTS);
  console.log(`  ok  ${GATT_ATTEMPTS} failed attempts produce a stated cause, not "undefined"`);
}

{
  // `gatt.connected` outranks the promise: some bridges reject while the link is actually up, and
  // treating that as a failure throws away a working connection.
  const s = new VeritySensor();
  s.device = fakeDevice({ failures: 99, connectedAfterReject: true });
  const server = await s._openGatt();
  assert.equal(server.connected, true);
  assert.equal(s.device.attempts, 1, 'it must not retry a link that is already up');
  console.log('  ok  a rejection is not believed when the link is demonstrably connected');
}

{
  // Already connected: no attempt at all.
  const s = new VeritySensor();
  const dev = fakeDevice();
  dev.gatt.connected = true;
  s.device = dev;
  await s._openGatt();
  assert.equal(dev.attempts, 0);
  assert.equal(s.step, 'already connected');
  console.log('  ok  an existing link is reused rather than reopened');
}

{
  // A device with no GATT at all must be named as such, not dereferenced into a TypeError.
  const s = new VeritySensor();
  s.device = { name: 'Polar Sense' };
  await assert.rejects(s._openGatt(), /no GATT server/);
  console.log('  ok  a device with no GATT server is reported rather than crashed on');
}

{
  // A remembered entry that no longer works must not block the picker. The permission outlives the
  // pairing, so a band that has been reset is still in the list — and without this fallback that one
  // stale entry is a permanent dead end with no way to clear it from a phone.
  let pickerOpened = false;
  const good = fakeDevice();
  good.addEventListener = () => {};
  good.gatt.getPrimaryService = async () => { throw new Error('stop here'); };
  const stale = fakeDevice({ failures: 99 });
  stale.addEventListener = () => {};

  const restore = fakeBluetooth({
    getDevices: async () => [stale],
    requestDevice: async () => { pickerOpened = true; return good; },
  });
  const s = new VeritySensor();
  // _attach will fail on the fake (no real services); what is being checked is that the picker was
  // reached at all after the remembered device failed to connect.
  await s.connect().catch(() => {});
  assert.equal(pickerOpened, true,
    'a remembered device that will not connect must fall through to the picker');
  assert.ok(stale.attempts >= GATT_ATTEMPTS, 'and only after genuinely trying it');
  restore();
  console.log('  ok  a stale remembered device falls through to the picker instead of blocking it');
}


// --- making connection easy: one link, heart rate first, find the band without a picker ------------

/** A band that connects after `failLooks` refused attempts; PMD can be made to hang for ever. */
function fakeBand({ failLooks = 0, hangPmd = false, name = 'Polar Sense 16961D33' } = {}) {
  const listeners = {};
  let looks = 0;
  const hrChar = { async startNotifications() { return this; }, addEventListener() {} };
  const server = {
    getPrimaryService: async id => {
      if (/180d/.test(id)) return { getCharacteristic: async () => hrChar };
      if (/fb005c80/.test(id) && hangPmd) return new Promise(() => {});
      throw new Error('not present');
    },
  };
  const gatt = {
    connected: false,
    connect() {
      looks += 1;
      if (looks <= failLooks) return Promise.reject(new Error('GATT operation failed'));
      gatt.connected = true; return Promise.resolve(server);
    },
    disconnect() { gatt.connected = false; },
    getPrimaryService: (...a) => server.getPrimaryService(...a),
  };
  return {
    name, gatt, get looks() { return looks; },
    addEventListener(t, f) { (listeners[t] ||= []).push(f); },
    removeEventListener(t, f) { listeners[t] = (listeners[t] || []).filter(x => x !== f); },
    listenerCount: t => (listeners[t] || []).length,
  };
}

{
  // A motion-sensor start that never answers used to fail the whole connect after 20 s, heart rate
  // included. Heart rate must be streaming regardless.
  const s = new VeritySensor();
  s.device = fakeBand({ hangPmd: true });
  const t0 = Date.now();
  await s._finishConnect();
  assert.equal(s.connected, true, 'connected on heart rate alone');
  assert.ok(Date.now() - t0 < 1000, 'without waiting on the accelerometer');
  s.dispose();
  console.log('  ok  a hanging accelerometer cannot fail the connection; heart rate connects first');
}

{
  // One disconnect listener per device, however many times the connection is (re)built.
  const s = new VeritySensor();
  const band = fakeBand();
  s.device = band;
  await s._finishConnect();
  band.gatt.connected = false;
  await s._finishConnect();
  assert.equal(band.listenerCount('gattserverdisconnected'), 1);
  s.dispose();
  assert.equal(band.listenerCount('gattserverdisconnected'), 0, 'dispose removes it');
  assert.equal(band.gatt.connected, false, 'and releases the band');
  console.log('  ok  one disconnect listener per band, removed on dispose');
}

{
  // A disposed sensor stops trying: the old instance's reconnect loop used to run for ever after the
  // next Connect tap, competing with the new one for the same band.
  const s = new VeritySensor();
  const band = fakeBand({ failLooks: 1000 });
  s.device = band;
  s._reconnect();
  await new Promise(r => setTimeout(r, 50));
  s.dispose();
  const after = band.looks;
  await new Promise(r => setTimeout(r, 1300));
  assert.equal(band.looks, after, `no attempts after dispose (${after} -> ${band.looks})`);
  console.log('  ok  a replaced sensor stops reaching for the band');
}

{
  // Hands-free: the remembered band, switched on a little late, is found and connected without a
  // picker or a tap. One attempt per look, not a burst.
  const band = fakeBand({ failLooks: 2 });
  const restore = fakeBluetooth({ getDevices: async () => [band],
                                  requestDevice: async () => { throw new Error('picker must not open'); } });
  const s = new VeritySensor();
  const ok = await s.autoConnect({ windowMs: 2000, retryMs: 20 });
  assert.equal(ok, true);
  assert.equal(s.connected, true);
  assert.equal(band.looks, 3, 'one connect per look');
  s.dispose();
  // Nothing remembered: false straight away, and no picker.
  const r2 = fakeBluetooth({ getDevices: async () => [], requestDevice: async () => { throw new Error('no picker'); } });
  assert.equal(await new VeritySensor().autoConnect({ windowMs: 100, retryMs: 10 }), false);
  r2();
  // A band that never comes: false at the end of the window.
  const never = fakeBand({ failLooks: 1e9 });
  const r3 = fakeBluetooth({ getDevices: async () => [never] });
  const t0 = Date.now();
  assert.equal(await new VeritySensor().autoConnect({ windowMs: 150, retryMs: 20 }), false);
  assert.ok(Date.now() - t0 < 1000);
  r3(); restore();
  console.log('  ok  the remembered band is found and connected with no picker, retrying until it appears');
}

{
  // A stream that stops while the link claims to be up is rebuilt, not left looking connected.
  const s = new VeritySensor();
  const band = fakeBand();
  s.device = band;
  await s._finishConnect();
  s.hrCount = 10; s.hrAt = 1000; s.connectedAt = 500;
  assert.equal(s.checkStall(1000 + HR_STALL_MS - 1), false, 'not yet');
  assert.equal(s.checkStall(1000 + HR_STALL_MS + 1), true, 'stalled: reconnect');
  // Just reconnected: a fresh twenty seconds, not an immediate second teardown.
  s.connected = true; s.reconnecting = false; s.connectedAt = 1000 + HR_STALL_MS + 2000;
  assert.equal(s.checkStall(1000 + HR_STALL_MS + 7000), false, 'a rebuilt link is not torn down again at once');
  s.connected = false;
  assert.equal(s.connected, false);
  s.dispose();
  // Never streamed (band on a table): no churn.
  const t = new VeritySensor();
  t.device = fakeBand(); await t._finishConnect();
  assert.equal(t.checkStall(Date.now() + 60000), false, 'a band that never read is not "stalled"');
  t.dispose();
  console.log('  ok  a stalled heart-rate stream is rebuilt; a band that never read is left alone');
}


// --- redundancy: every route has a second route -----------------------------------------------------

const memStore = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)) }; };

{
  // The band that last streamed is tried first, by id, ahead of anything else that looks like one.
  const store = memStore();
  store.setItem(ARMBAND_KEY, JSON.stringify({ id: 'B' }));
  const s = new VeritySensor({ store });
  const a = { id: 'A', name: 'Polar Sense 1' }, b = { id: 'B', name: 'Polar Sense 2' }, x = { id: 'X', name: 'Speaker' };
  assert.deepEqual(s.candidates([a, x, b]).map(d => d.id), ['B', 'A']);
  assert.deepEqual(new VeritySensor().candidates([x]).map(d => d.id), ['X'], 'a single remembered device is tried whatever its name');
  assert.deepEqual(new VeritySensor().candidates([x, { id: 'Y', name: 'Watch' }]), [], 'never a stranger among several');
  console.log('  ok  remembered devices are tried best first: last streamed, then Polar-named');
}

{
  // A stale remembered entry must not block a good one behind it: both are tried before the picker.
  const dead = { ...fakeBand({ failLooks: 1e9, name: 'Polar Sense OLD' }), id: 'old' };
  const good = { ...fakeBand({ name: 'Polar Sense NEW' }), id: 'new' };
  let picker = false;
  const restore = fakeBluetooth({ getDevices: async () => [dead, good],
                                  requestDevice: async () => { picker = true; throw new Error('no'); } });
  const store = memStore();
  const s = new VeritySensor({ store });
  await s.connect();
  assert.equal(s.connected, true); assert.equal(picker, false);
  assert.equal(JSON.parse(store.getItem(ARMBAND_KEY)).id, 'new', 'and the one that worked is remembered');
  s.dispose(); restore();
  console.log('  ok  every remembered entry is tried before the picker, and the one that streamed is remembered');
}

{
  // When the page knows nothing is remembered, Connect goes straight to the picker -- called inside the
  // tap, before any await, so the tap's permission cannot lapse on the way.
  let calledSync = false, listed = false;
  const band = fakeBand();
  const restore = fakeBluetooth({ getDevices: async () => { listed = true; return []; },
                                  requestDevice: () => { calledSync = true; return Promise.resolve(band); } });
  const s = new VeritySensor();
  const p = s.connect({ skipRemembered: true });
  assert.equal(calledSync, true, 'the picker is opened synchronously within the call');
  await p;
  assert.equal(listed, false, 'and the remembered list was not consulted first');
  assert.equal(s.connected, true);
  s.dispose(); restore();
  console.log('  ok  with nothing remembered, the picker opens inside the tap itself');
}

{
  // Looking rotates across the plausible entries: a dead first entry does not stop the second.
  const dead = { ...fakeBand({ failLooks: 1e9, name: 'Polar Sense OLD' }), id: 'old' };
  const good = { ...fakeBand({ name: 'Polar Sense NEW' }), id: 'new' };
  const restore = fakeBluetooth({ getDevices: async () => [dead, good] });
  const s = new VeritySensor();
  assert.equal(await s.autoConnect({ windowMs: 2000, retryMs: 10 }), true);
  assert.equal(s.device.id, 'new');
  s.dispose(); restore();
  console.log('  ok  looking for the band rotates across remembered entries');
}

{
  // Mid-run: the device object goes stale (connects fail for ever) while the band is fine. After a
  // few failures the loop asks the browser again, gets a fresh object, and reconnects.
  const stale = { ...fakeBand({ failLooks: 1e9 }), id: 'band' };
  const fresh = { ...fakeBand(), id: 'band' };
  const restore = fakeBluetooth({ getDevices: async () => [fresh] });
  const s = new VeritySensor();
  s.device = stale;
  const t0 = Date.now();
  await s._reconnect();
  assert.equal(s.connected, true, 'reconnected through a fresh device object');
  assert.equal(s.device, fresh);
  s.dispose(); restore();
  console.log(`  ok  a reconnect loop re-acquires a stale device object (${Math.round((Date.now() - t0) / 1000)} s)`);
}

console.log('\nAll sensor tests passed.');
