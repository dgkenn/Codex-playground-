// The armband self-test: every feature built on the link, tried once on the real band.
//
// Why this exists
// ---------------
// Most of what the app now asks of the Verity Sense was written against Polar's SDK source and its
// test vectors, with no band in reach: the motion stream's rate through Bluefy, the heart-rate
// re-subscription repair, the band recording to its own memory, the file service that reads that
// recording back (and whether Bluefy lets a page use it at all), beat-to-beat intervals. The
// Bluetooth probe (bt-probe.js) walks the CONNECTION; this walks what is built on it, on the live
// connection the app itself uses, and writes down what happened at each step with its timing.
//
// About a minute and a quarter, band on the arm, sitting still (the beat-to-beat step needs rest).
// Nothing is deleted from the band; a short memory recording is started and stopped, which the next
// read-back clears with everything else. Never during a run.

const pause = ms => new Promise(r => setTimeout(r, ms));

/**
 * Run the steps. `sensor` is a connected VeritySensor; `offline` is polar-offline.js's
 * `{offlineHrActive, startOfflineHr, stopOfflineHr, listOfflineRecordings, getDiskSpace}`;
 * `onStep(step)` is called as each finishes. Timings are scaled by `scale` (tests run it fast).
 * Returns `{ok, steps:[{name, ok, ms, detail}], summary}`.
 */
export async function runSelfTest({ sensor, offline, onStep = () => {}, scale = 1, withPpi = true }) {
  const steps = [];
  const step = async (name, fn) => {
    const t0 = Date.now();
    let ok = false, detail = null;
    try { const r = await fn(); ok = r.ok !== false; detail = r.detail ?? r; }
    catch (e) { detail = e && e.message ? e.message : String(e); }
    const s = { name, ok, ms: Date.now() - t0, detail };
    steps.push(s);
    try { onStep(s); } catch { /* the page's problem */ }
    return s;
  };

  await step('link', async () => {
    const up = !!(sensor && sensor.connected && sensor.device && sensor.device.gatt && sensor.device.gatt.connected);
    return { ok: up, detail: up ? `connected to ${sensor.device.name || 'the band'}` : 'not connected — connect the armband first' };
  });
  if (!steps[0].ok) return outcome(steps);

  await step('heart rate stream', async () => {
    const n0 = sensor.hrCount, z0 = sensor.hrZeros || 0;
    await pause(10000 * scale);
    const n = sensor.hrCount - n0, hz = n / (10 * scale);
    return { ok: n > 0 && hz >= 0.5, detail: `${n} readings in 10 s (${hz.toFixed(1)} a second), ${sensor.hrZeros - z0} zero, now ${sensor.hr ?? '—'} bpm` };
  });

  await step('battery', async () => {
    const t = Date.now();
    const b = await sensor.readBattery({ force: true });
    return { ok: b != null, detail: b != null ? `${b}% (read in ${Date.now() - t} ms)` : 'could not read' };
  });

  await step('motion stream', async () => {
    if (sensor.accShed) return { ok: false, detail: `stopped by the link supervisor: ${sensor.accError}` };
    if (!sensor.hasAcc) return { ok: false, detail: `not streaming: ${sensor.accError || 'never started'}` };
    const f0 = sensor.accFrames;
    await pause(5000 * scale);
    const f = sensor.accFrames - f0;
    return { ok: f > 0, detail: `${f} frames in 5 s (${(f / (5 * scale)).toFixed(1)} a second), settings ${sensor.accSettings || '—'}` };
  });

  let port = null;
  await step('control point', async () => {
    port = await sensor.pmdPort();
    const t = Date.now();
    const raw = (await port.request([0x05])).raw;
    return { ok: !!raw && raw[0] === 0xF0 && raw[3] === 0,
             detail: `status answered in ${Date.now() - t} ms: ${Array.from(raw || []).map(b => b.toString(16).padStart(2, '0')).join(' ')}` };
  });

  await step('heart rate re-subscribe', async () => {
    const n0 = sensor.hrCount;
    const t = Date.now();
    await sensor._resubscribeHr();
    const deadline = Date.now() + 8000 * scale;
    while (sensor.hrCount === n0 && Date.now() < deadline) await pause(100 * scale);
    const back = sensor.hrCount > n0;
    return { ok: back && sensor.connected, detail: back ? `stream back ${Date.now() - t} ms after switching it off and on` : 'no reading within 8 s afterwards' };
  });

  await step('band memory recording', async () => {
    if (!port) throw new Error('no control point');
    const was = await offline.offlineHrActive(port);
    if (was) return { ok: true, detail: 'already recording (left running by a run) — left alone' };
    const r = await offline.startOfflineHr(port);
    await pause(3000 * scale);
    const on = await offline.offlineHrActive(port);
    await offline.stopOfflineHr(port);
    const off = !(await offline.offlineHrActive(port));
    return { ok: on && off, detail: `start ${r.started ? 'accepted' : 'already on'}, recording ${on ? 'confirmed' : 'NOT confirmed'}, stop ${off ? 'confirmed' : 'NOT confirmed'}` };
  });

  await step('file service', async () => {
    const files = await sensor.fileClient();
    const list = await offline.listOfflineRecordings(files);
    let disk = null;
    try { disk = await offline.getDiskSpace(files); } catch { /* optional */ }
    const kinds = [...new Set(list.map(e => e.type))].join(', ') || 'none';
    return { detail: `${list.length} recording${list.length === 1 ? '' : 's'} on the band (${kinds})`
                     + (disk ? `, ${Math.round((disk.free || disk.freeBytes || 0) / 1024)} kB free` : '') };
  });

  if (withPpi) {
    await step('beat-to-beat intervals', async () => {
      const beats = [];
      await sensor.startPpi(b => beats.push(...b));
      const deadline = Date.now() + 40000 * scale;
      while (beats.length < 10 && Date.now() < deadline) await pause(250 * scale);
      await sensor.stopPpi();
      const moved = beats.filter(b => b.blocker).length;
      return { ok: beats.length > 0,
               detail: beats.length ? `${beats.length} beats, ${moved} flagged as moved, first ${beats[0].ppiMs} ms`
                                    : 'nothing in 40 s (the band sends the first after about 25 s, at rest)' };
    });
  }

  await step('link still up', async () => ({ ok: sensor.connected, detail: sensor.connected ? 'yes' : 'the link dropped during the test' }));
  return outcome(steps);
}

function outcome(steps) {
  const bad = steps.filter(s => !s.ok);
  return {
    ok: !bad.length,
    steps,
    summary: bad.length ? `${steps.length - bad.length} of ${steps.length} passed; failed: ${bad.map(s => s.name).join(', ')}`
                        : `all ${steps.length} passed`,
  };
}
