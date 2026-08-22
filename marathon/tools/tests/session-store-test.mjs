// Session storage, driven against a fake Storage that can be made to run out of room.
//
// The bug being fixed is a lost run: the page reloaded mid-session and an hour of recording went
// with it. Every case here is a way that could still happen — a write that silently fails, a quota
// error that aborts the save instead of making room, a recovery offered from a session so old it is
// meaningless, a duplicate left behind when a recovered run is finished.

import assert from 'node:assert/strict';
import { SessionStore, AUTOSAVE_MS, MAX_ARCHIVED, RECOVER_WINDOW_MS,
         ACTIVE_KEY, INDEX_KEY, pointCount, hasHeartRate } from '../session-store.js';

/** localStorage, with an optional ceiling so quota behaviour can be exercised rather than assumed. */
class FakeStorage {
  constructor(limitBytes = Infinity) { this.map = new Map(); this.limit = limitBytes; }
  get size() { let n = 0; for (const [k, v] of this.map) n += k.length + v.length; return n; }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null; }
  removeItem(k) { this.map.delete(k); }
  setItem(k, v) {
    const prev = this.map.get(k);
    this.map.set(k, v);
    if (this.size > this.limit) {
      if (prev === undefined) this.map.delete(k); else this.map.set(k, prev);
      const e = new Error('quota'); e.name = 'QuotaExceededError'; throw e;
    }
  }
}

const session = (n, { startedAt = '2026-08-19T18:00:00.000Z', hr = true, mode = 'ramp' } = {}) => ({
  schema_version: 1,
  started_at: startedAt,
  mode,
  samples: Array.from({ length: n }, (_, i) => ({
    t_s: i, hr_bpm: hr ? 120 + (i % 7) : null, speed_m_s: 2.5, grade: 0, label: 'stage_1',
  })),
  route: [],
});

// --- the run in progress -------------------------------------------------------------------------

{
  const st = new SessionStore(new FakeStorage());
  assert.equal(st.saveActive(session(10), { now: 1000 }), true);
  // Rate limited: a write per second would be wasteful, and occasionally slow on a phone.
  assert.equal(st.saveActive(session(11), { now: 1000 + AUTOSAVE_MS - 1 }), false);
  assert.equal(st.saveActive(session(12), { now: 1000 + AUTOSAVE_MS }), true);
  // But the moments where there may be no next chance are never skipped.
  assert.equal(st.saveActive(session(13), { now: 1000 + AUTOSAVE_MS + 1, force: true }), true);
  assert.equal(st.recoverable({ now: 1000 + AUTOSAVE_MS + 2 }).samples.length, 13);
  console.log('  ok  the run in progress is written periodically, and always when forced');
}

{
  const st = new SessionStore(new FakeStorage());
  st.saveActive(session(500), { now: 0, force: true });
  const found = st.recoverable({ now: 60_000 });
  assert.ok(found, 'a session from a minute ago must be offered back');
  assert.equal(found.samples.length, 500);

  // Old enough to be a different day's run rather than the one just interrupted.
  assert.equal(st.recoverable({ now: RECOVER_WINDOW_MS + 1 }), null);
  console.log('  ok  a recent unfinished session is recoverable and a stale one is not');
}

{
  const st = new SessionStore(new FakeStorage());
  // Nothing worth recovering: no session, an empty one, and one already finished.
  assert.equal(st.recoverable(), null);
  st.saveActive(session(0), { now: 0, force: true });
  assert.equal(st.recoverable({ now: 1 }), null, 'an empty recording is not a recovery');
  st.saveActive({ ...session(10), finished: true }, { now: 0, force: true });
  assert.equal(st.recoverable({ now: 1 }), null, 'a finished session must not be offered as lost');
  console.log('  ok  empty and finished sessions are not offered as recoveries');
}

// --- finishing -----------------------------------------------------------------------------------

{
  const st = new SessionStore(new FakeStorage());
  st.saveActive(session(120), { now: 0, force: true });
  const entry = st.archive(session(120), { now: 1000 });
  assert.ok(entry);
  assert.equal(entry.samples, 120);
  assert.equal(entry.minutes, 2);
  assert.equal(entry.hasHr, true);
  assert.equal(st.index().length, 1);
  // The in-progress slot must be cleared, or the next load offers to recover a session that has
  // already been filed — and the athlete ends up with two copies of one run.
  assert.equal(st.recoverable({ now: 1001 }), null);
  assert.equal(st.get(entry.id).samples.length, 120);
  console.log('  ok  finishing files the session and clears the in-progress slot');
}

{
  // Recovering and then finishing must not leave two entries for one run. The id comes from the
  // start time for exactly this reason.
  const st = new SessionStore(new FakeStorage());
  st.archive(session(100), { now: 1000 });
  st.archive(session(160), { now: 2000 });
  assert.equal(st.index().length, 1, 'the same run finished twice is one entry, not two');
  assert.equal(st.get(st.index()[0].id).samples.length, 160, 'and it is the longer, later version');
  console.log('  ok  finishing the same run twice updates one entry rather than duplicating it');
}

// --- the archive ---------------------------------------------------------------------------------

{
  const st = new SessionStore(new FakeStorage());
  for (let i = 0; i < MAX_ARCHIVED + 4; i++) {
    st.archive(session(60, { startedAt: `2026-08-${String(i + 1).padStart(2, '0')}T10:00:00.000Z` }),
               { now: i * 1000 });
  }
  assert.equal(st.index().length, MAX_ARCHIVED, 'the archive must be bounded');
  // Newest first, and the evicted ones must actually be gone rather than orphaned in storage.
  assert.equal(st.index()[0].at, '2026-08-12T10:00:00.000Z');
  const st2 = st;
  for (const e of st2.index()) assert.ok(st2.get(e.id), `${e.id} is indexed but missing`);
  console.log(`  ok  the archive keeps the newest ${MAX_ARCHIVED} and drops the rest cleanly`);
}

{
  // The important quota case: storage is nearly full and a run is in progress. Making room must
  // come out of the finished archive, never out of the save that is trying to preserve the run.
  const storage = new FakeStorage();
  const st = new SessionStore(storage);
  for (let i = 0; i < 4; i++) {
    st.archive(session(200, { startedAt: `2026-08-0${i + 1}T10:00:00.000Z` }), { now: i * 1000 });
  }
  const before = st.index().length;
  // The ceiling is set from what the archive actually occupies rather than guessed, so the next
  // write is genuinely too big to fit. A fixture that happens to leave room tests nothing.
  storage.limit = storage.size + 2000;
  const saved = st.saveActive(session(600), { now: 99_000, force: true });
  assert.equal(saved, true, 'the run in progress must be saved even when storage is full');
  assert.ok(st.index().length < before, 'and room must be made by evicting finished sessions');
  assert.equal(st.recoverable({ now: 99_001 }).samples.length, 600);
  console.log(`  ok  a full disk evicts old sessions rather than losing the live one `
            + `(${before} -> ${st.index().length} archived)`);
}

{
  // Corrupt storage must not take the page down on load. A session that cannot be parsed is gone;
  // throwing on startup would take everything else with it.
  const storage = new FakeStorage();
  storage.setItem(ACTIVE_KEY, '{not json');
  storage.setItem(INDEX_KEY, 'also not json');
  const st = new SessionStore(storage);
  assert.equal(st.recoverable(), null);
  assert.deepEqual(st.index(), []);
  assert.ok(st.lastError, 'and it must be recorded rather than swallowed');
  console.log('  ok  corrupt storage yields nothing instead of throwing on load');
}

{
  const st = new SessionStore(new FakeStorage());
  const e = st.archive(session(90), { now: 0 });
  assert.ok(st.bytes() > 0);
  st.remove(e.id);
  assert.deepEqual(st.index(), []);
  assert.equal(st.get(e.id), null);
  assert.equal(st.bytes(), 0);
  console.log('  ok  a session can be removed, and removing it reclaims its space');
}

{
  // The statistics ride in the index, so a trend survives the eviction of the samples it came from
  // and can be drawn without parsing every archived run.
  const st = new SessionStore(new FakeStorage());
  const e = st.archive({ ...session(600), stats: { efficiencyFactor: 19.4, beatsPerUnit: 22.1 } },
                       { now: 0 });
  assert.equal(e.stats.efficiencyFactor, 19.4);
  assert.equal(st.index()[0].stats.beatsPerUnit, 22.1);
  // And a session with no statistics must carry null rather than being absent from the index.
  const e2 = st.archive(session(60, { startedAt: '2026-08-20T10:00:00.000Z' }), { now: 1000 });
  assert.equal(e2.stats, null);
  assert.equal(st.index().length, 2);
  console.log('  ok  statistics ride in the index and survive their samples');
}

{
  // The failure that actually happened on the phone. An earlier build filled the active slot with a
  // few hundred kilobytes; nothing had ever been archived, so eviction had nothing to reach; and
  // every save afterwards failed from four seconds into the next run. Storage was bricked by one
  // oversized leftover, permanently, with no way out from a phone.
  const storage = new FakeStorage();
  const st = new SessionStore(storage);
  st.saveActive(session(3000), { now: 0, force: true });      // the leftover
  assert.equal(st.index().length, 0, 'and nothing archived to evict');
  storage.limit = storage.size + 500;                          // no room for anything new

  const st2 = new SessionStore(storage);
  const saved = st2.saveActive(session(20), { now: 1000, force: true });
  assert.equal(saved, true,
    'a new run must displace the abandoned one rather than failing forever behind it');
  assert.equal(st2.recoverable({ now: 1001 }).samples.length, 20, 'and it must be the new run');
  console.log('  ok  an oversized abandoned session is displaced instead of bricking storage');
}

{
  // A phone offers no other way in, so the store has to be able to describe and empty itself.
  const st = new SessionStore(new FakeStorage());
  st.archive(session(100), { now: 0 });
  st.saveActive(session(50), { now: 1000, force: true });
  const inv = st.inventory();
  assert.ok(inv.length >= 2, `inventory listed ${inv.length} keys`);
  assert.ok(inv.every(x => x.bytes > 0), 'every listed key must report its size');
  st.clear();
  assert.deepEqual(st.index(), []);
  assert.equal(st.recoverable({ now: 1001 }), null);
  assert.equal(st.bytes(), 0);
  console.log('  ok  storage can be listed and emptied from the app itself');
}

{
  // Sessions are written COMPACT — columns, no `samples` field — and everything here used to reason
  // about `session.samples.length`. It therefore saw zero for every stored run: recovery decided
  // each one was empty and refused to offer it back, silently disabling the whole feature, and the
  // archive listed every session as 0 samples and no heart rate.
  const compactish = {
    schema_version: 2,
    started_at: '2026-08-22T16:01:11.216Z',
    t: [0, 5, 10, 15, 20], hr: [null, 132, 138, 141, null], spd: [12, 25, 26, 24, 0],
    n_full: 1556, labels: [[0, 'run']],
  };
  assert.equal(pointCount(compactish), 5);
  assert.equal(pointCount({ samples: [1, 2, 3] }), 3, 'and the per-second shape still counts');
  assert.equal(pointCount(null), 0);
  assert.equal(hasHeartRate(compactish), true);
  assert.equal(hasHeartRate({ ...compactish, hr: [null, null] }), false);
  assert.equal(hasHeartRate({ samples: [{ hr_bpm: 120 }] }), true);

  const st = new SessionStore(new FakeStorage());
  st.saveActive(compactish, { now: 0, force: true });
  const found = st.recoverable({ now: 1000 });
  assert.ok(found, 'a compact session must be offered back — this is the bug that disabled recovery');
  assert.equal(pointCount(found), 5);

  const e = st.archive(compactish, { now: 2000 });
  assert.equal(e.samples, 5);
  assert.equal(e.hasHr, true);
  // Minutes come from what the recording really spanned, not from how many points travelled.
  assert.equal(e.minutes, 26, `26 minutes of running, got ${e.minutes}`);
  console.log('  ok  a compact session is counted, recovered and listed like any other');
}

console.log('\nAll session-store tests passed.');
