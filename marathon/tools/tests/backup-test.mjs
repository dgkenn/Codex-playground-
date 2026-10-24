// Backup and restore against a stand-in localStorage: what goes in, what stays out, a round trip
// that puts back the same bytes, bad files refused before anything is touched, and a refused write
// rolled back.

import assert from 'node:assert/strict';
import { snapshot, parseBackup, restore, backupName, describeBackup, backupDue, LAST_BACKUP_KEY } from '../backup.js';

/** Enough of localStorage: length/key/getItem/setItem/removeItem, optionally refusing big writes. */
function fakeStorage(init = {}, { maxValue = Infinity } = {}) {
  const m = new Map(Object.entries(init));
  return {
    get length() { return m.size; },
    key: i => [...m.keys()][i] ?? null,
    getItem: k => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => {
      if (String(v).length > maxValue) { const e = new Error('full'); e.name = 'QuotaExceededError'; throw e; }
      m.set(k, String(v));
    },
    removeItem: k => { m.delete(k); },
    dump: () => Object.fromEntries(m),
  };
}

const athlete = {
  'band.profile': '{"age":30,"hrRest":67,"confirmed":true}',
  'band.rung': '{"rung":7}',
  'band.checks.v1': '[{"at":1},{"at":2},{"at":3}]',
  'band.benchmarks': '[{"kind":"trial"}]',
  'band.session.index': '[{"id":"a"}]',
  'band.session.a': '{"t":[1,2,3]}',
  'band.armband': 'device-id-of-this-phone',
  [LAST_BACKUP_KEY]: '1700000000000',
  'other.site': 'not ours',
};

{
  const b = snapshot(fakeStorage(athlete), { now: Date.UTC(2026, 9, 24), build: 'abc' });
  assert.equal(b.format, 'band-backup');
  assert.equal(b.build, 'abc');
  assert.ok(!('band.armband' in b.keys), 'the paired band belongs to this phone');
  assert.ok(!(LAST_BACKUP_KEY in b.keys));
  assert.ok(!('other.site' in b.keys), "only the app's own keys");
  assert.equal(b.keys['band.rung'], '{"rung":7}', 'the exact stored string');
  assert.equal(backupName(Date.UTC(2026, 9, 24)), 'band-backup-2026-10-24.json');
  const d = describeBackup(b);
  assert.deepEqual([d.sessions, d.checks, d.benchmarks], [1, 3, 1]);
  console.log('  ok  a backup holds every band.* key verbatim, minus the paired armband');
}

{
  const text = JSON.stringify(snapshot(fakeStorage(athlete)));
  // A new phone, with its own armband and a stale setting the backup doesn't have.
  const fresh = fakeStorage({ 'band.armband': 'new-phone', 'band.unit': 'km', 'other.site': 'x' });
  const p = parseBackup(text);
  assert.ok(p.ok);
  const r = restore(fresh, p.backup);
  assert.ok(r.ok);
  assert.equal(r.removed, 1);
  const after = fresh.dump();
  assert.equal(after['band.armband'], 'new-phone', "the new phone's band is kept");
  assert.equal(after['band.unit'], undefined, 'replace, not merge');
  assert.equal(after['other.site'], 'x', 'other keys untouched');
  for (const k of Object.keys(p.backup.keys)) assert.equal(after[k], athlete[k]);
  console.log('  ok  restore replaces the app data exactly and leaves the phone-specific keys alone');
}

{
  assert.match(parseBackup('{oops').error, /not JSON/);
  assert.match(parseBackup('{"format":"x"}').error, /not a backup/);
  assert.match(parseBackup('{"format":"band-backup","version":9,"keys":{}}').error, /newer/);
  assert.match(parseBackup('{"format":"band-backup","version":1,"keys":{"evil":"1"}}').error, /malformed/);
  assert.match(parseBackup('{"format":"band-backup","version":1,"keys":{"band.x":3}}').error, /malformed/);
  console.log('  ok  bad files are refused before storage is touched');
}

{
  const before = { 'band.rung': '{"rung":2}', 'band.unit': 'mi' };
  const s = fakeStorage(before, { maxValue: 20 });
  const backup = { format: 'band-backup', version: 1, keys: { 'band.rung': '{"rung":9}', 'band.session.b': 'x'.repeat(100) } };
  const r = restore(s, backup);
  assert.equal(r.ok, false);
  assert.match(r.error, /QuotaExceededError/);
  assert.deepEqual(s.dump(), before, 'previous contents put back');
  console.log('  ok  a write the browser refuses rolls the restore back');
}

{
  const day = 86400000, now = 100 * day;
  assert.equal(backupDue({ lastAt: null, latestSessionAt: null, now }), false, 'nothing to keep yet');
  assert.equal(backupDue({ lastAt: null, latestSessionAt: now - day, now }), true);
  assert.equal(backupDue({ lastAt: now - 3 * day, latestSessionAt: now - day, now }), false);
  assert.equal(backupDue({ lastAt: now - 9 * day, latestSessionAt: now - day, now }), true);
  assert.equal(backupDue({ lastAt: now - 9 * day, latestSessionAt: now - 10 * day, now }), false, 'nothing new since');
  console.log('  ok  a reminder after a week, only if something new was saved');
}
