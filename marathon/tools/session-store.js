// Sessions that survive the page going away.
//
// Why this exists
// ---------------
// A run was lost. The page reloaded partway through — iOS reclaiming memory from a backgrounded tab
// is the usual reason, and it needs no user action at all — and the entire session went with it,
// because the samples lived in a variable and nowhere else. An hour of running, the one recording
// the whole plan was waiting on, gone silently.
//
// That is the same class of fault as the fabricated heart rate and the phantom GPS distance, and it
// is the worst of the three: those produced wrong data, this produces none. So the recording is now
// written to storage continuously while it happens, and what is found there on the next load is
// offered back rather than overwritten.
//
// Design notes
// ------------
// Writing every second would be wasteful and, on a phone, occasionally slow; writing at the end is
// what failed. Every few seconds is the compromise, plus an unconditional write when the page is
// hidden — which on iOS is the last moment anything is guaranteed to run.
//
// Storage is finite and shared. A long run is a few hundred kilobytes, so the archive is capped by
// both count and total size, and a quota error drops the oldest rather than failing the write that
// is trying to save the run in progress.

export const ACTIVE_KEY = 'band.session.active';
export const INDEX_KEY = 'band.session.index';
export const ITEM_PREFIX = 'band.session.';

/// How often the run in progress is written down. Six seconds of a session is an acceptable loss;
/// an hour is not.
export const AUTOSAVE_MS = 6000;

/// How many finished sessions to keep, and the ceiling on what they may occupy together. Both
/// matter: six three-hour runs would be several megabytes and would start evicting other origins'
/// data, or fail outright.
export const MAX_ARCHIVED = 8;
export const MAX_BYTES = 2_500_000;

/// An unfinished session older than this is stale rather than recoverable. Long enough to survive a
/// reload, a phone call, and finishing the run before looking at the phone again.
export const RECOVER_WINDOW_MS = 18 * 3600 * 1000;

const isQuotaError = e =>
  e && (e.name === 'QuotaExceededError' || e.name === 'NS_ERROR_DOM_QUOTA_REACHED' || e.code === 22);

/**
 * Persist sessions in a `Storage`.
 *
 * The storage is injected rather than reached for, so the behaviour that matters — eviction, quota
 * handling, recovery — can be tested against a fake instead of hoped about.
 */
export class SessionStore {
  constructor(storage) {
    this.storage = storage;
    this.lastSaveAt = 0;
    this.lastError = null;
  }

  _read(key) {
    try {
      const raw = this.storage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      // Corrupt or truncated JSON must not take the app down on load. A session that cannot be
      // parsed is a session that is gone; saying so is the whole job.
      this.lastError = e;
      return null;
    }
  }

  _write(key, value) {
    const text = JSON.stringify(value);
    try {
      this.storage.setItem(key, text);
      return true;
    } catch (e) {
      if (!isQuotaError(e)) { this.lastError = e; return false; }

      // Make room by dropping the oldest finished sessions, never the one in progress.
      for (let i = 0; i < MAX_ARCHIVED + 1; i++) {
        if (!this._evictOldest()) break;
        try { this.storage.setItem(key, text); return true; } catch (e2) {
          if (!isQuotaError(e2)) { this.lastError = e2; return false; }
        }
      }

      // Last resort: drop the previous in-progress session.
      //
      // This is the failure that actually happened. An earlier build wrote the whole per-second
      // recording to the active slot, filling storage with a few hundred kilobytes. Nothing had
      // ever been archived, so there was nothing for the loop above to evict — and every write
      // afterwards failed, from four seconds into the next run, for the whole session. Storage was
      // permanently bricked by one oversized leftover that eviction could not reach.
      //
      // Safe because the write in hand is REPLACING it: whatever is in the active slot is either
      // the same session or an abandoned one, and the run happening now matters more than either.
      if (key === ACTIVE_KEY) {
        try {
          this.storage.removeItem(ACTIVE_KEY);
          this.storage.setItem(key, text);
          return true;
        } catch (e3) {
          if (!isQuotaError(e3)) { this.lastError = e3; return false; }
        }
      }
      this.lastError = e;
      return false;
    }
  }

  index() {
    const idx = this._read(INDEX_KEY);
    return Array.isArray(idx) ? idx : [];
  }

  _setIndex(idx) { this._write(INDEX_KEY, idx); }

  _evictOldest() {
    const idx = this.index();
    if (!idx.length) return false;
    const oldest = idx[idx.length - 1];
    try { this.storage.removeItem(ITEM_PREFIX + oldest.id); } catch { /* already gone */ }
    this._setIndex(idx.slice(0, -1));
    return true;
  }

  // --- the run in progress -----------------------------------------------------------------------

  /**
   * Write the run in progress, at most every `AUTOSAVE_MS` unless forced.
   *
   * `force` is for the moments where there may not be another chance: the page being hidden, or the
   * session ending.
   */
  saveActive(session, { now = Date.now(), force = false } = {}) {
    // The first write is never rate-limited. `lastSaveAt` starts at zero, so on a clock measured in
    // milliseconds since 1970 the comparison happens to be true — but on a test clock, or a page
    // opened at the epoch, the opening write of a session would be the one that gets skipped.
    const first = this.lastSaveAt === 0;
    if (!force && !first && now - this.lastSaveAt < AUTOSAVE_MS) return false;
    this.lastSaveAt = now;
    return this._write(ACTIVE_KEY, { ...session, savedAt: now });
  }

  /** The unfinished session, if there is a recent one worth offering back. */
  recoverable({ now = Date.now() } = {}) {
    const s = this._read(ACTIVE_KEY);
    if (!s || !s.samples || !s.samples.length) return null;
    if (s.finished) return null;
    if (now - (s.savedAt || 0) > RECOVER_WINDOW_MS) return null;
    return s;
  }

  clearActive() {
    try { this.storage.removeItem(ACTIVE_KEY); } catch { /* already gone */ }
  }

  // --- finished sessions -------------------------------------------------------------------------

  /**
   * File a finished session and clear the in-progress slot.
   *
   * The id is derived from the start time rather than generated, so finishing the same session twice
   * — which a recovery followed by a stop will do — updates one entry instead of leaving two copies
   * of the same run in a list where they are indistinguishable.
   */
  archive(session, { now = Date.now() } = {}) {
    const id = String(session.started_at || session.startedAt || now).replace(/[^0-9A-Za-z]/g, '');
    const entry = {
      id,
      at: session.started_at || new Date(now).toISOString(),
      title: session.title || 'Session',
      mode: session.mode || 'coach',
      samples: (session.samples || []).length,
      minutes: Math.round(((session.samples || []).length) / 60),
      hasHr: (session.samples || []).some(x => x.hr_bpm != null),
      // The statistics live in the index as well as in the session, so a trend can be drawn without
      // parsing every archived run — and so they survive the eviction of the samples they came from.
      // They are computed once, at the end of the run, against the profile in force at that moment;
      // recomputing later would silently restate history every time a setting moved.
      stats: session.stats || null,
    };
    if (!this._write(ITEM_PREFIX + id, session)) return null;

    const idx = [entry, ...this.index().filter(e => e.id !== id)].slice(0, MAX_ARCHIVED);
    this._setIndex(idx);
    this.clearActive();
    this._trimToSize();
    return entry;
  }

  get(id) { return this._read(ITEM_PREFIX + id); }

  remove(id) {
    try { this.storage.removeItem(ITEM_PREFIX + id); } catch { /* already gone */ }
    this._setIndex(this.index().filter(e => e.id !== id));
  }

  /** Total bytes the archive occupies, and the eviction that keeps it under the ceiling. */
  bytes() {
    let total = 0;
    for (const e of this.index()) {
      const raw = (() => { try { return this.storage.getItem(ITEM_PREFIX + e.id); } catch { return null; } })();
      total += raw ? raw.length : 0;
    }
    return total;
  }

  /** Every key this store owns, with its size. For the diagnostics report and the export button. */
  inventory() {
    const out = [];
    for (const key of [ACTIVE_KEY, INDEX_KEY, ...this.index().map(e => ITEM_PREFIX + e.id)]) {
      let raw = null;
      try { raw = this.storage.getItem(key); } catch { /* unreadable */ }
      if (raw != null) out.push({ key, bytes: raw.length });
    }
    return out;
  }

  /** Remove everything this store owns. The only way back from a wedged storage, on a phone. */
  clear() {
    for (const e of this.index()) {
      try { this.storage.removeItem(ITEM_PREFIX + e.id); } catch { /* already gone */ }
    }
    try { this.storage.removeItem(INDEX_KEY); } catch { /* already gone */ }
    this.clearActive();
  }

  _trimToSize() {
    let guard = MAX_ARCHIVED + 1;
    while (this.bytes() > MAX_BYTES && guard-- > 0) {
      if (!this._evictOldest()) break;
    }
  }
}
