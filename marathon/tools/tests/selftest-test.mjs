// The armband self-test, against a stand-in band: every step reported with its result, a failing
// step named in the summary rather than stopping the rest.

import assert from 'node:assert/strict';
import { runSelfTest } from '../selftest.js';

function fakeSensor({ fileFails = false, hrStops = false } = {}) {
  const s = {
    connected: true, device: { name: 'Polar Sense 16961D33', gatt: { connected: true } },
    hrCount: 0, hrZeros: 0, hr: 72, accFrames: 0, hasAcc: true, accShed: false, accSettings: 'rate=52',
    battery: 88,
    async readBattery() { return this.battery; },
    async pmdPort() { return { request: async b => ({ raw: new Uint8Array([0xF0, b[0], 0, 0, 0]) }) }; },
    async _resubscribeHr() {},
    async fileClient() { if (fileFails) throw new Error('SecurityError: service not allowed'); return {}; },
    async startPpi(cb) { this._ppi = setInterval(() => cb([{ ppiMs: 980, blocker: false }]), 5); },
    async stopPpi() { clearInterval(this._ppi); },
  };
  const tick = setInterval(() => { if (!hrStops) s.hrCount += 1; s.accFrames += 4; }, 10);
  s.stop = () => clearInterval(tick);
  return s;
}
let recording = false;
const offline = {
  offlineHrActive: async () => recording,
  startOfflineHr: async () => { recording = true; return { started: true }; },
  stopOfflineHr: async () => { recording = false; },
  listOfflineRecordings: async () => [{ type: 'HR' }, { type: 'HR' }],
  getDiskSpace: async () => ({ freeBytes: 3 * 1024 * 1024 }),
};

{
  const sensor = fakeSensor();
  const seen = [];
  const r = await runSelfTest({ sensor, offline, scale: 0.01, onStep: st => seen.push(st.name) });
  sensor.stop();
  assert.equal(r.ok, true, JSON.stringify(r.steps, null, 1));
  assert.deepEqual(seen, ['link', 'heart rate stream', 'battery', 'motion stream', 'control point',
                          'heart rate re-subscribe', 'band memory recording', 'file service',
                          'beat-to-beat intervals', 'link still up']);
  assert.match(r.steps.find(x => x.name === 'file service').detail, /2 recordings on the band \(HR\), 3072 kB free/);
  assert.match(r.steps.find(x => x.name === 'band memory recording').detail, /recording confirmed, stop confirmed/);
  assert.equal(recording, false, 'the test recording was stopped');
  console.log(`  ok  every step runs and reports (${r.summary})`);
}

{
  // A failing step is named; the rest still run.
  const sensor = fakeSensor({ fileFails: true });
  const r = await runSelfTest({ sensor, offline, scale: 0.01, withPpi: false });
  sensor.stop();
  assert.equal(r.ok, false);
  assert.match(r.summary, /failed: file service/);
  assert.match(r.steps.find(x => x.name === 'file service').detail, /SecurityError/);
  assert.ok(r.steps.find(x => x.name === 'link still up').ok, 'later steps still ran');
  console.log(`  ok  a failing step is named and the rest still run (${r.summary})`);
}

{
  // Not connected: one step, and it says what to do.
  const r = await runSelfTest({ sensor: { connected: false }, offline });
  assert.equal(r.steps.length, 1);
  assert.match(r.steps[0].detail, /connect the armband first/);
  console.log('  ok  with no armband it stops at once and says what to do');
}

console.log('\nAll self-test tests passed.');
