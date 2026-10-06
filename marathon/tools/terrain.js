// Hills, from a terrain model rather than from GPS altitude.
//
// Why this exists
// ---------------
// The 6 October run went round a loop whose whole elevation range is six metres (4-10 m on the
// Copernicus 90 m terrain model). Over that run the app's live grade -- GPS altitude differenced over
// 40 m of travel -- read 3% or steeper a third of the time, and as much as 25%. That number fed the
// pace band, which is widened by the metabolic cost of the grade (Minetti), so on a flat street the
// band slid by up to a third: 12:04 a mile coached as "on pace" at 16 and over. GPS altitude is about
// three times worse than GPS position, and position is already a few metres; differenced over a
// short distance it is noise, and no amount of clamping turns it into a gradient.
//
// A terrain model does not have that problem. Its elevations are fixed numbers for fixed places, so a
// grade taken from them over 100 m of travel is a property of the road, not of the satellite geometry
// at that second. It is coarse -- 90 m cells, whole metres -- which is the right resolution for the
// question the plan asks ("is this a hill"), and the wrong one for kerbs and ramps, which do not
// matter. It is also a SURFACE model: in a city, 90 m cells average in some of the buildings, which
// is worth a metre or two of false relief: the 6 October loop, flat as a road, reads up to 3.9% from
// it in places. So the spoken cues wait for 5%, and the one rule that changes the session (walk a
// steep descent, see hr-blocks.js) waits for 7%.
//
// Where the numbers come from
// ---------------------------
// open-meteo.com's elevation API: free, no key, CORS-enabled, 100 points per request. Asked for the
// corners of a fixed grid (about 110 m), never for the runner's own positions, in blocks of 8x8 cells
// (about 900 m square, 81 points, one request). So what leaves the phone is "somewhere in this
// square kilometre", once per square, and every answer is kept on the phone: a route run twice costs
// nothing the second time and works without a signal.

export const TerrainDefaults = {
  /// Grid spacing. 0.001 deg of latitude is 111 m; 0.00135 deg of longitude is 111 m at 42 N, which is
  /// where this athlete runs, and within 10% of square anywhere from 35 to 48 degrees.
  cellLatDeg: 0.001,
  cellLonDeg: 0.00135,
  /// Cells per block side: (8 + 1)^2 = 81 grid points, inside the API's 100-per-request limit.
  blockCells: 8,
  /// After a failed request, leave that block alone for this long rather than hammering a dead
  /// connection once a second for the rest of the run.
  retryAfterMs: 60000,
};

export const ELEVATION_API = 'https://api.open-meteo.com/v1/elevation';

/** The request for a list of points, as the API wants it. */
export function elevationUrl(points) {
  const lat = points.map(p => p[0].toFixed(5)).join(',');
  const lon = points.map(p => p[1].toFixed(5)).join(',');
  return `${ELEVATION_API}?latitude=${lat}&longitude=${lon}`;
}

/**
 * Elevation anywhere inside the blocks fetched so far, interpolated between grid points.
 *
 * `fetchJson(url)` returns a promise of the parsed response; `store` is anything with
 * `getItem/setItem` (localStorage, or nothing). Nothing here throws: a block that cannot be had is a
 * block with no elevation, and a grade that cannot be measured is null, not zero.
 */
export class TerrainGrid {
  constructor({ fetchJson, store = null, now = () => Date.now(), ...opts } = {}) {
    this.cfg = { ...TerrainDefaults, ...opts };
    this.fetchJson = fetchJson;
    this.store = store;
    this.now = now;
    this.blocks = new Map();       // key -> Float64Array of (n+1)^2 elevations, row-major by lat
    this.pending = new Set();
    this.failedAt = new Map();
    this.requests = 0;
    this.lastError = null;
  }

  _cell(lat, lon) {
    return [lat / this.cfg.cellLatDeg, lon / this.cfg.cellLonDeg];
  }

  _blockOf(ci, cj) {
    const n = this.cfg.blockCells;
    return [Math.floor(ci / n), Math.floor(cj / n)];
  }

  _key(bi, bj) { return `${bi}/${bj}`; }

  /** The grid points of a block, south-west corner first, rows of increasing latitude. */
  _points(bi, bj) {
    const n = this.cfg.blockCells, pts = [];
    for (let r = 0; r <= n; r++) {
      for (let c = 0; c <= n; c++) {
        pts.push([(bi * n + r) * this.cfg.cellLatDeg, (bj * n + c) * this.cfg.cellLonDeg]);
      }
    }
    return pts;
  }

  _load(bi, bj) {
    const key = this._key(bi, bj);
    if (this.blocks.has(key)) return true;
    if (this.store) {
      try {
        const raw = this.store.getItem(`terrain.v1.${key}`);
        if (raw) {
          const arr = JSON.parse(raw);
          const n = this.cfg.blockCells;
          if (Array.isArray(arr) && arr.length === (n + 1) * (n + 1)) {
            this.blocks.set(key, Float64Array.from(arr));
            return true;
          }
        }
      } catch { /* corrupt or blocked: fetch it again */ }
    }
    return false;
  }

  _fetch(bi, bj) {
    const key = this._key(bi, bj);
    if (this._load(bi, bj) || this.pending.has(key) || !this.fetchJson) return;
    const failed = this.failedAt.get(key);
    if (failed != null && this.now() - failed < this.cfg.retryAfterMs) return;
    this.pending.add(key);
    this.requests += 1;
    let p;
    try { p = Promise.resolve(this.fetchJson(elevationUrl(this._points(bi, bj)))); }
    catch (e) { p = Promise.reject(e); }
    p.then(json => {
      const el = json && json.elevation;
      const n = this.cfg.blockCells;
      if (!Array.isArray(el) || el.length !== (n + 1) * (n + 1) || el.some(v => typeof v !== 'number')) {
        throw new Error('unexpected elevation response');
      }
      this.blocks.set(key, Float64Array.from(el));
      this.failedAt.delete(key);
      if (this.store) {
        try { this.store.setItem(`terrain.v1.${key}`, JSON.stringify(el)); } catch { /* full */ }
      }
    }).catch(e => {
      this.failedAt.set(key, this.now());
      this.lastError = String(e && e.message || e);
    }).finally(() => { this.pending.delete(key); });
  }

  /**
   * Make sure the block under this point is loaded or loading -- and the neighbouring one too when
   * the point is within a cell of its edge, so crossing into it does not open a gap in the grade.
   */
  ensure(lat, lon) {
    if (lat == null || lon == null) return;
    const [ci, cj] = this._cell(lat, lon);
    const n = this.cfg.blockCells;
    const [bi, bj] = this._blockOf(ci, cj);
    this._fetch(bi, bj);
    const ri = ci - bi * n, rj = cj - bj * n;
    const di = ri < 1 ? -1 : ri > n - 1 ? 1 : 0;
    const dj = rj < 1 ? -1 : rj > n - 1 ? 1 : 0;
    if (di) this._fetch(bi + di, bj);
    if (dj) this._fetch(bi, bj + dj);
    if (di && dj) this._fetch(bi + di, bj + dj);
  }

  /** Elevation in metres, bilinear between the four surrounding grid points; null if not loaded. */
  elevationAt(lat, lon) {
    if (lat == null || lon == null) return null;
    const [ci, cj] = this._cell(lat, lon);
    const n = this.cfg.blockCells;
    const [bi, bj] = this._blockOf(ci, cj);
    if (!this._load(bi, bj)) return null;
    const g = this.blocks.get(this._key(bi, bj));
    const ri = ci - bi * n, rj = cj - bj * n;
    const r0 = Math.min(n - 1, Math.floor(ri)), c0 = Math.min(n - 1, Math.floor(rj));
    const fr = ri - r0, fc = rj - c0;
    const at = (r, c) => g[r * (n + 1) + c];
    return at(r0, c0) * (1 - fr) * (1 - fc) + at(r0, c0 + 1) * (1 - fr) * fc
         + at(r0 + 1, c0) * fr * (1 - fc) + at(r0 + 1, c0 + 1) * fr * fc;
  }

  status() {
    return { blocks: this.blocks.size, pending: this.pending.size, requests: this.requests,
             failures: this.failedAt.size, lastError: this.lastError };
  }
}

/**
 * Grade over the last stretch of travel, from terrain elevations.
 *
 * Over 100 m, because the terrain model's cells are 90 m: a shorter run reads the step between two
 * cells as a ramp. Not reported until at least 60 m have been covered with elevations, and null --
 * not zero -- when it cannot be measured, so "flat" and "unknown" stay different things.
 */
export class GradeTrack {
  constructor({ runM = 100, minRunM = 60, maxGrade = 0.15 } = {}) {
    Object.assign(this, { runM, minRunM, maxGrade });
    this.pts = [];
  }

  add(distM, elevM) {
    if (distM == null || elevM == null || !Number.isFinite(elevM)) return;
    const last = this.pts[this.pts.length - 1];
    if (last && distM < last[0]) this.pts = [];          // the distance went backwards: a new session
    this.pts.push([distM, elevM]);
    while (this.pts.length > 2 && distM - this.pts[1][0] >= this.runM) this.pts.shift();
  }

  get grade() {
    if (this.pts.length < 2) return null;
    const [d1, e1] = this.pts[this.pts.length - 1];
    let base = this.pts[0];
    for (const p of this.pts) { if (d1 - p[0] >= this.runM) base = p; else break; }
    const run = d1 - base[0];
    if (run < this.minRunM) return null;
    const g = (e1 - base[1]) / run;
    return Math.max(-this.maxGrade, Math.min(this.maxGrade, g));
  }
}

/**
 * One spoken line when a climb or a descent starts, and nothing while it continues.
 *
 * Uphill the heart-rate ceiling already does the governing -- a climb ends a block sooner, which is
 * the right answer for the heart -- so the cue is about form and about letting the pace go, because
 * the instinct is to hold the flat pace up the hill and that is what drives the heart rate to the
 * ceiling in forty seconds. Downhill is the opposite case: heart rate falls, so nothing in the
 * heart-rate machinery would ever say anything, while the impact on the shins and the load on the
 * quads go up. Short quick steps is the standard answer and the one worth hearing at the top.
 *
 * Hysteresis on both edges so a grade wobbling around the threshold does not produce a line every
 * twenty metres.
 */
export class HillCues {
  constructor({ upGrade = 0.05, downGrade = -0.05, release = 0.02 } = {}) {
    Object.assign(this, { upGrade, downGrade, release });
    this.state = 'flat';
  }

  update(grade, { running = true } = {}) {
    if (grade == null) return null;
    let next = this.state;
    if (this.state === 'up' && grade < this.upGrade - this.release) next = 'flat';
    if (this.state === 'down' && grade > this.downGrade + this.release) next = 'flat';
    if (next === 'flat' || this.state === 'flat') {
      if (grade >= this.upGrade) next = 'up';
      else if (grade <= this.downGrade) next = 'down';
    }
    const entered = next !== this.state && next !== 'flat';
    this.state = next;
    if (!entered || !running) return null;
    return next === 'up'
      ? { kind: 'up', grade, text: 'Uphill. Shorter steps, and let the pace go. Heart rate decides.' }
      : { kind: 'down', grade, text: 'Downhill. Short, quick steps. Do not let it run away with you.' };
  }
}
