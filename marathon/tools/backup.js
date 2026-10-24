// Backup and restore: everything the app knows about the athlete, in one file.
//
// Why this exists
// ---------------
// All of it lives in this browser's storage on one phone: the ladder rung, the measured ceilings,
// thirty-odd days of morning checks, the benchmarks, the pain log, the last eight runs. Clearing
// the browser's data, a new phone, or Bluefy being reinstalled would lose weeks of adaptation the
// plan can't rebuild from anything else. The session archive also keeps only eight runs, so a
// backup now and then is the only long record outside the chat.
//
// What goes in: every key the app owns (they all start `band.`), as the exact strings stored, so a
// restore puts back the same bytes and nothing has to know each key's shape. What stays out: the
// remembered armband (a Bluetooth id belongs to one phone's pairing) and the backup bookkeeping.
//
// A restore replaces rather than merges: half of two histories is worse than either. It keeps the
// previous contents in memory and puts them back if the browser refuses a write part-way through.

export const BACKUP_FORMAT = 'band-backup';
export const BACKUP_VERSION = 1;
export const KEY_PREFIX = 'band.';
export const LAST_BACKUP_KEY = 'band.backup.last';
/// Never copied out or overwritten on restore: they describe this phone, not the athlete.
export const LOCAL_ONLY = ['band.armband', LAST_BACKUP_KEY];
/// A reminder is due when the last backup is older than this and something new has been saved.
export const REMIND_DAYS = 7;

function ownKeys(storage) {
  const out = [];
  const n = storage.length || 0;
  for (let i = 0; i < n; i++) {
    const k = storage.key(i);
    if (k && k.startsWith(KEY_PREFIX) && !LOCAL_ONLY.includes(k)) out.push(k);
  }
  return out.sort();
}

/** Everything the app stores, as `{format, version, at, build, keys: {name: string}}`. */
export function snapshot(storage, { now = Date.now(), build = '' } = {}) {
  const keys = {};
  for (const k of ownKeys(storage)) {
    const v = storage.getItem(k);
    if (v != null) keys[k] = v;
  }
  return { format: BACKUP_FORMAT, version: BACKUP_VERSION, at: new Date(now).toISOString(), build, keys };
}

/** A file name with the date in it, so several backups sort and don't overwrite each other. */
export function backupName(now = Date.now()) {
  return `band-backup-${new Date(now).toISOString().slice(0, 10)}.json`;
}

/** What a backup holds, in words a person can check before replacing their data with it. */
export function describeBackup(b) {
  const ks = Object.keys(b.keys);
  const sessions = ks.filter(k => /^band\.session\.(?!index$|active$)/.test(k)).length;
  const count = k => { try { const v = JSON.parse(b.keys[k] || '[]'); return Array.isArray(v) ? v.length : 0; } catch { return 0; } };
  const kb = Math.round(ks.reduce((s, k) => s + k.length + b.keys[k].length, 0) / 1024);
  return { at: b.at, settings: ks.length, sessions, checks: count('band.checks.v1'),
           benchmarks: count('band.benchmarks'), kb };
}

/**
 * Read a backup file's text. `{ok: true, backup}` or `{ok: false, error}`: anything that isn't a
 * backup this version can read is refused whole, before storage is touched.
 */
export function parseBackup(text) {
  let b;
  try { b = JSON.parse(text); } catch { return { ok: false, error: 'not a backup file (not JSON)' }; }
  if (!b || b.format !== BACKUP_FORMAT) return { ok: false, error: 'not a backup file from this app' };
  if (!(b.version >= 1) || b.version > BACKUP_VERSION) {
    return { ok: false, error: `backup version ${b.version} is newer than this app reads; update the app first` };
  }
  if (!b.keys || typeof b.keys !== 'object' || Array.isArray(b.keys)) return { ok: false, error: 'backup has no data' };
  for (const [k, v] of Object.entries(b.keys)) {
    if (!k.startsWith(KEY_PREFIX) || typeof v !== 'string') return { ok: false, error: `backup entry "${k}" is malformed` };
  }
  return { ok: true, backup: b };
}

/**
 * Replace the app's stored data with a backup's. Returns `{ok, written, removed}` or, if the
 * browser refused a write, `{ok: false, error}` with the previous contents put back.
 */
export function restore(storage, backup) {
  const before = snapshot(storage).keys;
  const incoming = Object.fromEntries(Object.entries(backup.keys).filter(([k]) => !LOCAL_ONLY.includes(k)));
  const stale = Object.keys(before).filter(k => !(k in incoming));
  try {
    // Remove first: the space they held is what the incoming sessions may need.
    for (const k of stale) storage.removeItem(k);
    for (const [k, v] of Object.entries(incoming)) storage.setItem(k, v);
  } catch (e) {
    for (const k of ownKeys(storage)) { try { storage.removeItem(k); } catch { /* best effort */ } }
    for (const [k, v] of Object.entries(before)) { try { storage.setItem(k, v); } catch { /* best effort */ } }
    return { ok: false, error: `the browser refused to store it (${e && e.name ? e.name : e}); nothing changed` };
  }
  return { ok: true, written: Object.keys(incoming).length, removed: stale.length };
}

/**
 * Whether to suggest a backup: never made one and there is something worth keeping, or the last
 * one is over a week old and a session has been saved since.
 */
export function backupDue({ lastAt, latestSessionAt, now = Date.now() }) {
  if (!latestSessionAt) return false;
  if (!lastAt) return true;
  return now - lastAt > REMIND_DAYS * 86400000 && latestSessionAt > lastAt;
}
