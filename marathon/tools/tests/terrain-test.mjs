// Grade from a terrain model, and the cues that come from it.

import assert from 'node:assert/strict';
import { TerrainGrid, GradeTrack, HillCues, elevationUrl, TerrainDefaults } from '../terrain.js';

const tick = () => new Promise(r => setTimeout(r, 0));

/** A fake API whose world is a plane: elevation = f(lat, lon). Counts requests. */
function fakeApi(f) {
  const api = { calls: 0, urls: [] };
  api.fetchJson = async url => {
    api.calls += 1; api.urls.push(url);
    const q = new URL(url).searchParams;
    const la = q.get('latitude').split(',').map(Number), lo = q.get('longitude').split(',').map(Number);
    assert.ok(la.length <= 100, 'the API takes at most 100 points per request');
    return { elevation: la.map((x, i) => f(x, lo[i])) };
  };
  return api;
}

/** A street running north from (42.325, -71.0569), `m` metres along it. */
const north = (m) => [42.325 + m / 111195, -71.0569];

{
  // A 5% climb northwards: 5 m per 100 m. The grade must read 5%, measured over 100 m of travel.
  const api = fakeApi((lat) => (lat - 42.325) * 111195 * 0.05);
  const grid = new TerrainGrid({ fetchJson: api.fetchJson });
  grid.ensure(...north(0));
  await tick(); await tick();
  const g = new GradeTrack();
  for (let m = 0; m <= 300; m += 5) { grid.ensure(...north(m)); g.add(m, grid.elevationAt(...north(m))); }
  assert.ok(Math.abs(g.grade - 0.05) < 0.002, `a 5% road reads 5%: ${g.grade}`);
  console.log(`  ok  a 5% climb reads ${(g.grade * 100).toFixed(1)}% from the terrain grid (${api.calls} request(s))`);
}

{
  // Requests are for grid corners, never the runner's own position, and one per ~900 m block.
  const api = fakeApi(() => 7);
  const grid = new TerrainGrid({ fetchJson: api.fetchJson });
  for (let m = 0; m < 600; m += 3) grid.ensure(42.32537 + m / 111195, -71.05612);
  await tick(); await tick();
  const q = new URL(api.urls[0]).searchParams;
  const lats = q.get('latitude').split(',').map(Number);
  assert.ok(lats.every(x => Math.abs(x / TerrainDefaults.cellLatDeg - Math.round(x / TerrainDefaults.cellLatDeg)) < 1e-6),
    'only grid points leave the phone');
  assert.ok(api.calls <= 4, `a 600 m stretch is a handful of requests, not one per fix: ${api.calls}`);
  console.log(`  ok  only ~110 m grid corners are requested, ${api.calls} request(s) for 600 m`);
}

{
  // Cached: a second session over the same ground makes no request at all.
  const store = new Map();
  const st = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  const a = fakeApi(() => 12);
  const g1 = new TerrainGrid({ fetchJson: a.fetchJson, store: st });
  g1.ensure(...north(0)); await tick(); await tick();
  const b = fakeApi(() => 99);
  const g2 = new TerrainGrid({ fetchJson: b.fetchJson, store: st });
  g2.ensure(...north(0));
  assert.equal(b.calls, 0, 'a cached block is not fetched again');
  assert.equal(Math.round(g2.elevationAt(...north(0))), 12);
  console.log('  ok  terrain is cached on the phone: a repeat route makes no request');
}

{
  // No signal: nothing throws, the grade is null (unknown), not 0 (flat), and the block is not
  // re-requested every second.
  let calls = 0, now = 0;
  const grid = new TerrainGrid({ fetchJson: async () => { calls += 1; throw new Error('offline'); },
                                 now: () => now });
  for (let i = 0; i < 30; i++) { grid.ensure(...north(i)); await tick(); now += 1000; }
  assert.equal(grid.elevationAt(...north(0)), null);
  assert.ok(calls <= 1, `a failed block is left alone for a minute: ${calls} calls in 30 s`);
  const g = new GradeTrack();
  g.add(0, null); g.add(100, null);
  assert.equal(g.grade, null, 'no elevations means no grade, not a flat one');
  console.log('  ok  offline: no throw, grade unknown rather than zero, no request storm');
}

{
  // The 6 October loop, from its real terrain profile: 4-10 m over 2.75 km. The GPS grade on that
  // run read >= 3% a third of the time. The terrain grade must not call any of it a hill.
  const profile = [[0, 8], [122, 6], [216, 5], [324, 6], [443, 8], [581, 5], [693, 8], [867, 10],
                   [1028, 5], [1129, 5], [1283, 7], [1401, 7], [1508, 7], [1619, 8], [1715, 5],
                   [1849, 8], [1965, 10], [2094, 5], [2216, 6], [2324, 8], [2422, 5], [2522, 5],
                   [2623, 7], [2723, 8]];
  const elev = d => {
    for (let i = 1; i < profile.length; i++) {
      if (d <= profile[i][0]) {
        const [d0, e0] = profile[i - 1], [d1, e1] = profile[i];
        return e0 + (e1 - e0) * (d - d0) / (d1 - d0);
      }
    }
    return profile[profile.length - 1][1];
  };
  const g = new GradeTrack(), cues = new HillCues();
  let maxAbs = 0, said = 0;
  for (let d = 0; d <= 2720; d += 3) {
    g.add(d, elev(d));
    if (g.grade != null) maxAbs = Math.max(maxAbs, Math.abs(g.grade));
    if (cues.update(g.grade)) said += 1;
  }
  assert.ok(maxAbs < 0.05, `a flat loop never reads as a climb: max |grade| ${(maxAbs * 100).toFixed(1)}%`);
  assert.equal(said, 0, 'and no hill is announced on it');
  console.log(`  ok  the 6 Oct loop reads flat from terrain (max ${(maxAbs * 100).toFixed(1)}%), no hill cues`);
}

{
  // Cues: once per climb and once per descent, with hysteresis, and only while running.
  const c = new HillCues();
  const seq = [0, 0.02, 0.055, 0.06, 0.045, 0.055, 0.01, 0, -0.055, -0.06, -0.04, -0.055, 0];
  const out = seq.map(x => c.update(x)).filter(Boolean).map(x => x.kind);
  assert.deepEqual(out, ['up', 'down'], `one line per hill: ${JSON.stringify(out)}`);
  const w = new HillCues();
  assert.equal(w.update(0.06, { running: false }), null, 'walking up a hill is not coached');
  console.log('  ok  one cue per climb or descent, none for wobble around the threshold or while walking');
}

assert.match(elevationUrl([[42.3, -71.05]]), /^https:\/\/api\.open-meteo\.com\/v1\/elevation\?latitude=42\.30000&longitude=-71\.05000$/);
console.log('\nAll terrain tests passed.');
