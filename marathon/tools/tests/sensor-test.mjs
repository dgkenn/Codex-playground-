// The radio cannot be tested here. Everything that decides what a reading MEANS can be, and that is
// where the damage happens — a driver that fails to connect is obvious, one that fabricates is not.

import assert from 'node:assert/strict';
import { parseHeartRate, parseAccFrame, startCommand, accMagnitude,
         VeritySensor, STALE_HR_MS } from '../sensor.js';

const dv = bytes => new DataView(new Uint8Array(bytes).buffer);

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

console.log('\nAll sensor tests passed.');
