// A Bluetooth probe: what is actually there, and what actually happens.
//
// Why this exists
// ---------------
// The connect failed and the report said `Error — undefined`. That was fixed, but fixing the
// rendering of a reason does not produce a reason, and the next report will say whatever the bridge
// chooses to say, which may still be nothing. Guessing from the outside has now cost several rounds:
// short UUIDs, then a name filter, then another app holding the radio — each plausible, none
// demonstrated.
//
// So this stops guessing and takes an inventory. It walks the connection one step at a time, times
// every step, and records what came back — including what came back when nothing came back. It looks
// at the API surface the browser actually provides rather than the one the specification describes,
// enumerates every service and characteristic the peripheral really exposes, and watches for a
// disconnect after a connection that appeared to succeed.
//
// The output is meant to be pasted into a chat window by someone standing in a kitchen holding a
// phone. It is a report, not a fix.

/** Anything, rendered readably. Duplicated deliberately: a probe must not depend on what it probes. */
export function inspect(v, depth = 0) {
  if (v === undefined) return '<undefined>';
  if (v === null) return '<null>';
  const t = typeof v;
  if (t === 'string') return v === '' ? '<empty string>' : v;
  if (t === 'number' || t === 'boolean' || t === 'bigint') return String(v);
  if (t === 'symbol' || t === 'function') return `<${t}>`;

  const out = {};
  // Own property names catches the non-enumerable fields DOMException hides its content in, which
  // a JSON.stringify of the same object renders as `{}`.
  let keys = [];
  try { keys = Object.getOwnPropertyNames(v); } catch { /* proxy */ }
  for (const k of keys.slice(0, 12)) {
    try {
      const val = v[k];
      if (typeof val === 'function') continue;
      out[k] = depth < 1 && val && typeof val === 'object' ? inspect(val, depth + 1) : String(val);
    } catch (e) { out[k] = `<threw on read: ${e && e.message}>`; }
  }
  // The standard trio, which are usually on the prototype rather than own.
  for (const k of ['name', 'message', 'code']) {
    try { if (v[k] != null && out[k] === undefined) out[k] = String(v[k]); } catch { /* ignore */ }
  }
  let ctor = '';
  try { ctor = (v.constructor && v.constructor.name) || ''; } catch { /* ignore */ }

  if (!Object.keys(out).length) {
    const s = String(v);
    return s === '[object Object]' ? `<${ctor || 'object'} with no readable properties>` : s;
  }
  return (ctor ? ctor + ' ' : '') + JSON.stringify(out);
}

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

/**
 * Run one step, recording how long it took and what came back either way.
 *
 * A step that throws does not stop the probe. The interesting reports are the ones where an early
 * step fails and the later ones still say something useful about why.
 */
export async function timed(report, name, fn, timeoutMs = 20000) {
  const t0 = now();
  const entry = { step: name, ok: false, ms: 0 };
  report.steps.push(entry);
  let timer;
  try {
    const value = await Promise.race([
      Promise.resolve().then(fn),
      new Promise((_, rej) => { timer = setTimeout(() => rej(new Error(`no answer in ${timeoutMs / 1000}s`)), timeoutMs); }),
    ]);
    entry.ok = true;
    entry.ms = Math.round(now() - t0);
    return value;
  } catch (e) {
    entry.ms = Math.round(now() - t0);
    entry.threw = inspect(e);
    // The distinction that mattered and was invisible: a rejection with no value at all, versus one
    // carrying a reason. They mean different things and looked identical in the log.
    entry.threwType = e === undefined ? 'undefined'
                    : e === null ? 'null'
                    : (e && e.constructor && e.constructor.name) || typeof e;
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/** What this browser's Web Bluetooth actually implements, as opposed to what the spec says. */
export function apiSurface(bt) {
  if (!bt) return null;
  const names = ['requestDevice', 'getAvailability', 'getDevices', 'requestLEScan',
                 'addEventListener', 'onavailabilitychanged'];
  const surface = {};
  for (const n of names) {
    try { surface[n] = typeof bt[n]; } catch { surface[n] = '<threw>'; }
  }
  return surface;
}

/** Everything the peripheral exposes. This is where a wrong UUID or a wrong device mode shows up. */
export async function enumerateServices(server, report) {
  const found = [];
  const services = await timed(report, 'list every service', () => server.getPrimaryServices());
  for (const svc of services) {
    const entry = { uuid: svc.uuid, characteristics: [] };
    try {
      for (const ch of await svc.getCharacteristics()) {
        const p = ch.properties || {};
        entry.characteristics.push({
          uuid: ch.uuid,
          // Notify is the property that decides whether heart rate can stream at all.
          props: ['read', 'write', 'writeWithoutResponse', 'notify', 'indicate']
            .filter(k => p[k]).join('|') || 'none',
        });
      }
    } catch (e) {
      entry.characteristicsError = inspect(e);
    }
    found.push(entry);
  }
  return found;
}

/**
 * Walk the whole connection, recording everything.
 *
 * `chooseDevice` is injected so the probe can be driven by the picker, by a remembered device, or by
 * a fake in a test, without knowing which.
 */
export async function probeBluetooth({ chooseDevice, bluetooth, watchAfterMs = 12000,
                                       onLog = () => {} } = {}) {
  const report = {
    startedAt: new Date().toISOString(),
    steps: [],
    api: apiSurface(bluetooth),
    // Whether the page was handed over by the loader, which replaces the document — and in doing so
    // removes every event listener registered on it. If a browser's Bluetooth bridge routes its
    // native callbacks through such a listener, `requestDevice` would still work (the picker is
    // native) while a later `connect` reply would be orphaned. That is exactly the observed shape,
    // so it has to be in the report rather than assumed either way.
    viaLoader: typeof window !== 'undefined' && !!window.__viaLoader,
    disconnects: [],
  };
  const log = m => { onLog(m); };

  if (!bluetooth) {
    report.fatal = 'this browser has no navigator.bluetooth at all';
    return report;
  }

  try {
    report.availability = await timed(report, 'ask whether Bluetooth is available',
      () => (bluetooth.getAvailability ? bluetooth.getAvailability() : 'not implemented'), 5000);
  } catch { /* recorded in steps */ }

  try {
    const known = await timed(report, 'list remembered devices',
      () => (bluetooth.getDevices ? bluetooth.getDevices() : []), 5000);
    report.remembered = (known || []).map(d => ({ name: d.name || null, id: String(d.id || '').slice(0, 12) }));
  } catch { /* recorded in steps */ }

  let device;
  try {
    device = await timed(report, 'choose a device', () => chooseDevice(), 90000);
  } catch (e) {
    report.conclusion = 'never got a device to connect to';
    return report;
  }

  report.device = {
    name: device.name || null,
    id: String(device.id || '').slice(0, 12),
    hasGatt: !!device.gatt,
    alreadyConnected: !!(device.gatt && device.gatt.connected),
    // `watchAdvertisements` tells us whether the browser can see the band without connecting, which
    // separates "cannot reach the radio" from "cannot hold a link".
    canWatchAdvertisements: typeof device.watchAdvertisements === 'function',
  };
  log(`device: ${device.name || 'unnamed'}`);

  // Timed from here, so a link that drops immediately after being made is visibly different from one
  // that was never made. Those two produce the same "not connected" and need opposite fixes.
  const t0 = now();
  try {
    device.addEventListener('gattserverdisconnected', () => {
      report.disconnects.push({ atMs: Math.round(now() - t0) });
      log('disconnected');
    });
  } catch (e) { report.listenerError = inspect(e); }

  let server;
  try {
    server = await timed(report, 'open the connection', () => device.gatt.connect(), 20000);
  } catch (e) {
    // The single most important line in the whole report. A rejection carrying no value is a real
    // finding, not an absence of one, and it must be recorded as such.
    report.connectedAfterFailedPromise = !!(device.gatt && device.gatt.connected);
    report.conclusion = report.connectedAfterFailedPromise
      ? 'the connect call failed but the link is actually up — the browser is misreporting it'
      : 'the connection was refused';
    return report;
  }

  report.gattConnected = !!(device.gatt && device.gatt.connected);

  try {
    report.services = await enumerateServices(server, report);
    const uuids = report.services.map(s => s.uuid);
    report.hasHeartRateService = uuids.some(u => /0000180d/i.test(u));
    report.hasPolarPmd = uuids.some(u => /^fb005c80/i.test(u));
  } catch (e) {
    report.servicesError = inspect(e);
  }

  // Subscribe for real. A service that exists but will not notify is a different fault from one that
  // is missing, and only trying it tells them apart.
  try {
    const hr = await timed(report, 'subscribe to heart rate', async () => {
      const svc = await server.getPrimaryService('0000180d-0000-1000-8000-00805f9b34fb');
      const ch = await svc.getCharacteristic('00002a37-0000-1000-8000-00805f9b34fb');
      await ch.startNotifications();
      return ch;
    }, 15000);

    let packets = 0, firstAt = null, lastValue = null;
    hr.addEventListener('characteristicvaluechanged', e => {
      packets += 1;
      if (firstAt == null) firstAt = Math.round(now() - t0);
      try { lastValue = e.target.value.getUint8(1); } catch { /* flags say otherwise */ }
    });

    // Wait and watch. "Connected but silent" is its own failure and needs its own evidence.
    await new Promise(r => setTimeout(r, watchAfterMs));
    report.packets = packets;
    report.firstPacketAtMs = firstAt;
    report.lastHeartRate = lastValue;
    report.conclusion = packets > 0
      ? `working — ${packets} readings in ${watchAfterMs / 1000}s`
      : 'connected and subscribed, but the band sent nothing (it only reads through skin)';
  } catch (e) {
    report.conclusion = 'connected, but heart rate could not be subscribed to';
  }

  report.disconnectedDuringProbe = report.disconnects.length > 0;
  return report;
}
