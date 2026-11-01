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

// =================================================================================================
// Lidar: the hills the 90 m model cannot see
//
// 1 November ended over the rail overpass on Dorchester Avenue: about 3.7 m of road rising to a deck
// near 8 m and dropping back, the descent at 3-5%. The 90 m model above read it as a 1% bump, because
// a 90 m cell is longer than the ramp. In the US the USGS 3DEP lidar is 1 m, served one point at a
// time by the Elevation Point Query Service (CORS-open, no key). So where it answers, elevation comes
// from it, sampled along the path actually run (an 8 m cell per point, kept on the phone so a route
// run again costs nothing), and the grade is fitted over 45 m instead of 100.
//
// It is a BARE-EARTH model: bridges are removed, so on a bridge it reads the ground underneath (the
// rail tracks, 2 m, under a deck at 8 m). PathGrade below repairs that.
// =================================================================================================

export const LIDAR_API = 'https://epqs.nationalmap.gov/v1/json';
export const LidarDefaults = {
  cellM: 8,
  /// Cells per stored block side: one localStorage entry per ~100 m square.
  blockCells: 12,
  maxInFlight: 2,
  retryAfterMs: 60000,
};
const M_PER_DEG = 111320;

export function lidarUrl(lat, lon) {
  return `${LIDAR_API}?x=${lon.toFixed(6)}&y=${lat.toFixed(6)}&wkid=4326&units=Meters&includeDate=false`;
}

/** Lidar elevation per 8 m cell, fetched on demand and remembered. `elevationAt` is null until known. */
export class LidarPath {
  constructor({ fetchJson, store = null, now = () => Date.now(), ...opts } = {}) {
    this.cfg = { ...LidarDefaults, ...opts };
    Object.assign(this, { fetchJson, store, now });
    this.blocks = new Map();       // block key -> {cellKey: elevation | null (no data)}
    this.pending = new Set();
    this.failedAt = new Map();
    this.requests = 0;
    this.noData = 0;
    this.lastError = null;
  }

  _cell(lat, lon) {
    const dLat = this.cfg.cellM / M_PER_DEG;
    // Longitude cells sized for the whole-degree band, so a cell's key never depends on the exact point.
    const dLon = dLat / Math.cos(Math.round(lat) * Math.PI / 180);
    return { i: Math.floor(lat / dLat), j: Math.floor(lon / dLon), dLat, dLon };
  }

  _block(i, j) {
    const n = this.cfg.blockCells, key = `lidar.v1.${Math.floor(i / n)}/${Math.floor(j / n)}`;
    if (!this.blocks.has(key)) {
      let obj = {};
      if (this.store) { try { obj = JSON.parse(this.store.getItem(key) || '{}') || {}; } catch { obj = {}; } }
      this.blocks.set(key, obj);
    }
    return { key, obj: this.blocks.get(key) };
  }

  /** Fetch the cell under this point if it is not known, not in flight, and not recently failed. */
  ensure(lat, lon) {
    if (lat == null || lon == null || !this.fetchJson) return;
    const c = this._cell(lat, lon), ck = `${c.i}/${c.j}`;
    const { key, obj } = this._block(c.i, c.j);
    if (ck in obj || this.pending.has(ck) || this.pending.size >= this.cfg.maxInFlight) return;
    const failed = this.failedAt.get(ck);
    if (failed != null && this.now() - failed < this.cfg.retryAfterMs) return;
    this.pending.add(ck);
    this.requests += 1;
    const lat0 = (c.i + 0.5) * c.dLat, lon0 = (c.j + 0.5) * c.dLon;
    let p;
    try { p = Promise.resolve(this.fetchJson(lidarUrl(lat0, lon0))); } catch (e) { p = Promise.reject(e); }
    p.then(json => {
      const v = Number(json && json.value);
      if (!Number.isFinite(v)) throw new Error('unexpected lidar response');
      // The service answers -1000000 outside its coverage: a fact about the place, kept as such.
      const val = v < -1000 ? null : Math.round(v * 100) / 100;
      if (val == null) this.noData += 1;
      obj[ck] = val;
      if (this.store) { try { this.store.setItem(key, JSON.stringify(obj)); } catch { /* full */ } }
    }).catch(e => {
      this.failedAt.set(ck, this.now());
      this.lastError = String(e && e.message || e);
    }).finally(() => { this.pending.delete(ck); });
  }

  /** Metres, or null: not fetched yet, or no lidar here. */
  elevationAt(lat, lon) {
    if (lat == null || lon == null) return null;
    const c = this._cell(lat, lon);
    const v = this._block(c.i, c.j).obj[`${c.i}/${c.j}`];
    return v == null ? null : v;
  }

  status() {
    return { requests: this.requests, pending: this.pending.size, noData: this.noData,
             failures: this.failedAt.size, lastError: this.lastError };
  }
}

/// A step between two path samples steeper than this is not road: it is the edge of a bridge the
/// bare-earth model removed (a deck edge to the tracks below reads 30%+ over one sample). Real roads,
/// underpass ramps included, stay under about 10%.
export const BRIDGE_WALL = 0.15;
/// A bridge's far edge must come within this much path; past it, the drop is taken as real. The
/// Dorchester Avenue deck over the rail yard is about 170 m.
export const BRIDGE_MAX_M = 250;

/**
 * Bridge holes in a bare-earth profile, filled. `pts` is `[{d, e}]` in path order (e may be null).
 * A sharp drop and, within BRIDGE_MAX_M, a sharp rise back to within 1.5 m of the first edge: the
 * points between are replaced by the straight line from edge to edge (a deck). Returns
 * `{pts, open}`: `open` is true when the last stretch is a drop with no far edge yet -- the runner is
 * on a bridge whose end has not been sampled.
 */
export function repairBridges(pts) {
  const out = pts.map(p => ({ ...p }));
  const known = out.filter(p => p.e != null);
  let open = false;
  for (let a = 0; a < known.length - 1; a++) {
    const p = known[a], q = known[a + 1];
    if ((q.e - p.e) / Math.max(1, q.d - p.d) > -BRIDGE_WALL) continue;
    // A drop from p. Find the far edge: a rise steeper than the wall, back near p's height.
    let b = -1;
    for (let k = a + 1; k < known.length && known[k].d - p.d <= BRIDGE_MAX_M; k++) {
      const r = known[k - 1], s = known[k];
      if ((s.e - r.e) / Math.max(1, s.d - r.d) >= BRIDGE_WALL && s.e >= p.e - 1.5) { b = k; break; }
    }
    if (b < 0) {
      if (known[known.length - 1].d - p.d <= BRIDGE_MAX_M) {
        open = true;
        for (let k = a + 1; k < known.length; k++) known[k].e = p.e;   // on the deck: hold its height
      }
      break;
    }
    const s = known[b];
    for (let k = a + 1; k < b; k++) known[k].e = p.e + (s.e - p.e) * (known[k].d - p.d) / (s.d - p.d);
    a = b - 1;
  }
  return { pts: out, open };
}

/**
 * Grade from points along the path, with elevations looked up when they are known rather than when
 * the point was passed (a lidar answer arrives a second or two after the request). Least-squares
 * slope over the last `runM` of path with elevations, after bridge repair; null with less than
 * `minRunM` covered. `onBridge` says the last grade was taken on an unfinished bridge.
 */
export class PathGrade {
  constructor({ runM = 45, minRunM = 25, keepM = 300, maxGrade = 0.15 } = {}) {
    Object.assign(this, { runM, minRunM, keepM, maxGrade });
    this.pts = [];
    this.onBridge = false;
  }

  add(distM, lat, lon) {
    if (distM == null || lat == null || lon == null) return;
    const last = this.pts[this.pts.length - 1];
    if (last && distM < last.d) this.pts = [];
    this.pts.push({ d: distM, lat, lon });
    while (this.pts.length > 2 && distM - this.pts[0].d > this.keepM) this.pts.shift();
  }

  /** `elevationAt(lat, lon)` is the lidar lookup. */
  grade(elevationAt) {
    if (this.pts.length < 2) return null;
    const { pts, open } = repairBridges(this.pts.map(p => ({ d: p.d, e: elevationAt(p.lat, p.lon) })));
    this.onBridge = open;
    const end = pts[pts.length - 1].d;
    const win = pts.filter(p => p.e != null && end - p.d <= this.runM);
    if (win.length < 2 || win[win.length - 1].d - win[0].d < this.minRunM) return null;
    const md = win.reduce((s, p) => s + p.d, 0) / win.length, me = win.reduce((s, p) => s + p.e, 0) / win.length;
    let sde = 0, sdd = 0;
    for (const p of win) { sde += (p.d - md) * (p.e - me); sdd += (p.d - md) ** 2; }
    const g = sdd > 0 ? sde / sdd : 0;
    return Math.max(-this.maxGrade, Math.min(this.maxGrade, g));
  }
}
