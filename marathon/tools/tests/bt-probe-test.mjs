// The probe, driven through every failure it exists to tell apart.
//
// A diagnostic that only works when things work is not a diagnostic. Each case below is a real shape
// the connection has taken or could take, and the assertion is always the same in spirit: the report
// must distinguish this from the others, and must never contain the word "undefined" where a reason
// belongs.

import assert from 'node:assert/strict';
import { probeBluetooth, inspect, apiSurface } from '../bt-probe.js';

const HR = '0000180d-0000-1000-8000-00805f9b34fb';
const HR_CHAR = '00002a37-0000-1000-8000-00805f9b34fb';

// --- rendering whatever was thrown ---------------------------------------------------------------

{
  // The case that started all of this: a rejection carrying no value. It has to read as a finding.
  assert.equal(inspect(undefined), '<undefined>');
  assert.equal(inspect(null), '<null>');
  assert.equal(inspect(''), '<empty string>');
  assert.equal(inspect('GATT failed'), 'GATT failed');
  assert.match(inspect(new Error('boom')), /Error.*boom/);

  // DOMException keeps its content on the prototype, so a JSON.stringify of it renders `{}`.
  const dom = Object.create({ name: 'NetworkError', message: 'Connection failed', code: 19 });
  assert.match(inspect(dom), /NetworkError/);
  assert.match(inspect(dom), /Connection failed/);

  assert.match(inspect({}), /no readable properties/);
  assert.doesNotMatch(inspect({}), /\[object Object\]/);

  // A getter that throws must not take the probe down with it.
  const hostile = {};
  Object.defineProperty(hostile, 'boom', { get() { throw new Error('nope'); }, enumerable: true });
  assert.match(inspect(hostile), /threw on read/);
  console.log('  ok  anything thrown renders as something, including nothing');
}

{
  const surface = apiSurface({ requestDevice() {}, getDevices() {} });
  assert.equal(surface.requestDevice, 'function');
  assert.equal(surface.getDevices, 'function');
  assert.equal(surface.requestLEScan, 'undefined',
    'the report must show what is missing, not only what is present');
  assert.equal(apiSurface(null), null);
  console.log('  ok  the API surface reports what the browser lacks as well as what it has');
}

// --- a peripheral to probe -----------------------------------------------------------------------

function makeDevice({
  connect = 'ok',            // 'ok' | 'reject-undefined' | 'reject-error' | 'hang' | 'reject-but-connected'
  services = [HR],
  notifyThrows = false,
  packets = 0,
  dropAfterMs = null,
} = {}) {
  const listeners = {};
  const chListeners = [];
  const gatt = {
    connected: false,
    connect() {
      if (connect === 'ok' || connect === 'reject-but-connected') gatt.connected = true;
      if (connect === 'ok') return Promise.resolve(gatt);
      if (connect === 'hang') return new Promise(() => {});
      if (connect === 'reject-error') return Promise.reject(new Error('GATT operation failed'));
      return Promise.reject(undefined);
    },
    disconnect() { gatt.connected = false; },
    async getPrimaryServices() {
      return services.map(uuid => ({
        uuid,
        async getCharacteristics() {
          return uuid === HR
            ? [{ uuid: HR_CHAR, properties: { notify: true, read: true } }]
            : [{ uuid: uuid.replace('80', '81'), properties: { write: true } }];
        },
      }));
    },
    async getPrimaryService(uuid) {
      if (!services.includes(uuid)) throw new Error(`no service ${uuid}`);
      return {
        async getCharacteristic() {
          return {
            uuid: HR_CHAR,
            async startNotifications() {
              if (notifyThrows) throw new Error('notifications refused');
              for (let i = 0; i < packets; i++) {
                setTimeout(() => {
                  const view = new DataView(new Uint8Array([0x00, 60 + i]).buffer);
                  chListeners.forEach(fn => fn({ target: { value: view } }));
                }, 5 * (i + 1));
              }
              return true;
            },
            addEventListener(_n, fn) { chListeners.push(fn); },
          };
        },
      };
    },
  };
  const device = {
    name: 'Polar Sense 16961D33',
    id: 'abcdef0123456789',
    gatt,
    addEventListener(n, fn) { (listeners[n] = listeners[n] || []).push(fn); },
  };
  if (dropAfterMs != null) {
    setTimeout(() => {
      gatt.connected = false;
      (listeners.gattserverdisconnected || []).forEach(fn => fn());
    }, dropAfterMs);
  }
  return device;
}

const bt = { requestDevice() {}, getAvailability: async () => true, getDevices: async () => [] };
const run = (device, extra = {}) =>
  probeBluetooth({ bluetooth: bt, chooseDevice: async () => device, watchAfterMs: 60, ...extra });

// --- the failures it has to tell apart -----------------------------------------------------------

{
  // The reported failure, exactly. The report must name it as a rejection with no value rather than
  // rendering the absence as the word "undefined".
  const r = await run(makeDevice({ connect: 'reject-undefined' }));
  const step = r.steps.find(s => s.step === 'open the connection');
  assert.equal(step.ok, false);
  assert.equal(step.threwType, 'undefined', 'the report must say the rejection carried no value');
  assert.equal(step.threw, '<undefined>');
  assert.equal(r.conclusion, 'the connection was refused');
  assert.equal(r.connectedAfterFailedPromise, false);
  console.log('  ok  a rejection with no value is recorded as exactly that');
}

{
  // The same symptom with the opposite cause: the promise rejects but the link is up. Treating this
  // as a failure throws away a working connection, so the report must call it out.
  const r = await run(makeDevice({ connect: 'reject-but-connected' }));
  assert.equal(r.connectedAfterFailedPromise, true);
  assert.match(r.conclusion, /misreporting/);
  console.log('  ok  a rejection with the link up is distinguished from a real refusal');
}

{
  // A connect that never answers must be bounded and timed, not waited on for ever.
  const started = Date.now();
  const r = await probeBluetooth({
    bluetooth: bt, watchAfterMs: 10,
    chooseDevice: async () => makeDevice({ connect: 'hang' }),
  });
  const step = r.steps.find(s => s.step === 'open the connection');
  assert.equal(step.ok, false);
  assert.match(step.threw, /no answer in 20s/);
  assert.ok(step.ms >= 19000, `gave up after ${step.ms}ms — the budget was not honoured`);
  assert.ok(Date.now() - started < 40000);
  console.log(`  ok  a connect that never answers is timed out and timed (${step.ms}ms)`);
}

{
  // Connected, subscribed, and silent. This is the band-on-a-table case, and it is a different
  // problem from every other one here while looking identical from the outside.
  const r = await run(makeDevice({ packets: 0 }));
  assert.equal(r.gattConnected, true);
  assert.equal(r.packets, 0);
  assert.match(r.conclusion, /sent nothing/);
  assert.equal(r.hasHeartRateService, true);
  console.log('  ok  connected-and-silent is its own conclusion');
}

{
  // Working. The probe must be able to say so plainly, with a count.
  const r = await run(makeDevice({ packets: 3 }), { watchAfterMs: 120 });
  assert.equal(r.packets, 3);
  assert.equal(r.lastHeartRate, 62);
  assert.match(r.conclusion, /^working/);
  assert.ok(r.firstPacketAtMs != null);
  console.log(`  ok  a working band reports as working (${r.conclusion})`);
}

{
  // The band in the wrong mode: connects, but exposes no heart-rate service. The service list is
  // what separates this from a UUID mistake, and it has to be in the report either way.
  const r = await run(makeDevice({ services: ['fb005c80-02e7-f387-1cad-8acd2d8df0c8'] }));
  assert.equal(r.hasHeartRateService, false);
  assert.equal(r.hasPolarPmd, true);
  assert.equal(r.services.length, 1);
  assert.match(r.conclusion, /could not be subscribed/);
  console.log('  ok  a missing heart-rate service is visible in the enumerated list');
}

{
  // A service that exists but refuses to notify.
  const r = await run(makeDevice({ notifyThrows: true }));
  assert.equal(r.hasHeartRateService, true);
  assert.match(r.conclusion, /could not be subscribed/);
  console.log('  ok  a service that will not notify is distinguished from one that is missing');
}

{
  // Connects, then drops. "Not connected" at the end looks the same as never having connected, and
  // the two need opposite fixes, so the disconnect is timestamped.
  const r = await run(makeDevice({ packets: 0, dropAfterMs: 20 }), { watchAfterMs: 120 });
  assert.equal(r.disconnectedDuringProbe, true);
  assert.equal(r.disconnects.length, 1);
  assert.ok(r.disconnects[0].atMs >= 0);
  console.log(`  ok  a link that drops is recorded with when (${r.disconnects[0].atMs}ms)`);
}

{
  // No Bluetooth at all, and no device chosen. Both must produce a report rather than an exception —
  // a probe that throws tells you nothing.
  const none = await probeBluetooth({ bluetooth: null, chooseDevice: async () => null });
  assert.match(none.fatal, /no navigator.bluetooth/);

  const cancelled = await probeBluetooth({
    bluetooth: bt,
    chooseDevice: async () => { throw new Error('User cancelled'); },
  });
  assert.equal(cancelled.conclusion, 'never got a device to connect to');
  assert.equal(cancelled.steps.find(s => s.step === 'choose a device').ok, false);
  console.log('  ok  no Bluetooth and no device both still produce a report');
}

{
  // Whether the page came through the loader has to be in the report. The loader replaces the
  // document, which removes every listener on it — a plausible cause of a native bridge losing its
  // reply channel, and not something to keep arguing about when it can simply be recorded.
  const r = await run(makeDevice({ packets: 1 }), { watchAfterMs: 60 });
  assert.equal(typeof r.viaLoader, 'boolean');
  assert.ok('api' in r && 'steps' in r && 'device' in r);
  assert.ok(r.steps.every(s => typeof s.ms === 'number'), 'every step must be timed');
  console.log('  ok  the report always carries the API surface, timings and the loader flag');
}

console.log('\nAll Bluetooth probe tests passed.');
