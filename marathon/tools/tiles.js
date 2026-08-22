// A basemap under the route.
//
// Why this exists
// ---------------
// "The GPS shows some sort of path on the app, but it doesn't actually show the map or the streets
// that I'm running." Exactly right: the canvas drew a line in a void, scaled to its own bounding
// box, with no north, no scale and nothing underneath. A shape like that is unreadable — you cannot
// tell a loop of your own block from a loop of the park, and after the run you cannot tell where the
// slow mile was. The line is the interesting part only when there is something to read it against.
//
// So: OpenStreetMap raster tiles, drawn under the trace, in the standard Web Mercator scheme every
// slippy map uses.
//
// What this deliberately is not
// -----------------------------
// Not a map library. Leaflet is 40 kB before plugins and would have to be inlined into a page that
// is already 300 kB and must parse in one scope; and none of what it provides — panning, markers,
// layers, gestures — is wanted here. What is wanted is streets behind a polyline, which is a
// projection, a division and an image draw.
//
// Tiles are fetched from tile.openstreetmap.org. That is somebody else's server run on donations, so:
// tiles are cached for the life of the page, never re-requested after a failure, and a run redraws
// the same dozen tiles it already holds rather than fetching per frame. A single runner's session is
// well within the usage policy; a redraw loop that forgot its cache would not be.
//
// Everything here is pure except `TileLayer.draw`, and the image loader is injected, so the
// projection can be checked against known coordinates without a network.

/// The tile server. Zoom, x, y.
export const OSM_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
export const TILE_PX = 256;
export const ATTRIBUTION = '© OpenStreetMap';

/// Zoom bounds. Below 12 a run is a dot; above 18 the tiles stop existing in most places, and a
/// request for one that does not exist is a 404 charged to someone else's bandwidth.
export const MIN_ZOOM = 12;
export const MAX_ZOOM = 18;

/** Longitude to tile x, at a given zoom. Fractional: the whole point is sub-tile positioning. */
export function lonToTileX(lon, z) {
  return (lon + 180) / 360 * Math.pow(2, z);
}

/** Latitude to tile y, at a given zoom. The Mercator part. */
export function latToTileY(lat, z) {
  const r = lat * Math.PI / 180;
  return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * Math.pow(2, z);
}

/**
 * The largest zoom at which the whole route still fits the canvas, clamped to what exists.
 *
 * Largest rather than smallest: a run of four blocks wants street names, and picking the zoom that
 * merely fits would show a city. `padding` keeps the trace off the edge of the frame.
 */
export function fitZoom(bounds, widthPx, heightPx, { padding = 24 } = {}) {
  const w = Math.max(1, widthPx - padding * 2), h = Math.max(1, heightPx - padding * 2);
  for (let z = MAX_ZOOM; z > MIN_ZOOM; z--) {
    const dx = Math.abs(lonToTileX(bounds.maxLon, z) - lonToTileX(bounds.minLon, z)) * TILE_PX;
    const dy = Math.abs(latToTileY(bounds.minLat, z) - latToTileY(bounds.maxLat, z)) * TILE_PX;
    if (dx <= w && dy <= h) return z;
  }
  return MIN_ZOOM;
}

/**
 * A projection from lat/lon to canvas pixels, centred on the route.
 *
 * Returned as a closure rather than a matrix because everything that draws needs the same one — the
 * trace, the start dot, the current position — and two of them computed separately is how a route
 * ends up a few pixels off the road it was run on.
 */
export function viewFor(bounds, widthPx, heightPx, opts = {}) {
  const z = opts.zoom || fitZoom(bounds, widthPx, heightPx, opts);
  const scale = Math.pow(2, z) * TILE_PX;
  const cx = (lonToTileX(bounds.minLon, z) + lonToTileX(bounds.maxLon, z)) / 2 * TILE_PX;
  const cy = (latToTileY(bounds.minLat, z) + latToTileY(bounds.maxLat, z)) / 2 * TILE_PX;
  const originX = cx - widthPx / 2, originY = cy - heightPx / 2;
  return {
    zoom: z,
    scale,
    originX,
    originY,
    x: lon => lonToTileX(lon, z) * TILE_PX - originX,
    y: lat => latToTileY(lat, z) * TILE_PX - originY,
  };
}

/** The bounding box of a path of `[lat, lon, ...]`, or null if there is not enough of one. */
export function boundsOf(path) {
  if (!path || path.length < 2) return null;
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  for (const p of path) {
    if (p[0] < minLat) minLat = p[0];
    if (p[0] > maxLat) maxLat = p[0];
    if (p[1] < minLon) minLon = p[1];
    if (p[1] > maxLon) maxLon = p[1];
  }
  // A route that has not left one spot has zero extent, and a zero-extent box divides by zero
  // downstream. Give it about fifty metres so the first fixes of a session still draw something.
  const padLat = Math.max(0, 0.0005 - (maxLat - minLat)) / 2;
  const padLon = Math.max(0, 0.0007 - (maxLon - minLon)) / 2;
  return {
    minLat: minLat - padLat, maxLat: maxLat + padLat,
    minLon: minLon - padLon, maxLon: maxLon + padLon,
  };
}

/** Which tiles a view covers, as `{z, x, y, px, py}` in draw order. */
export function tilesFor(view, widthPx, heightPx) {
  const n = Math.pow(2, view.zoom);
  const x0 = Math.floor(view.originX / TILE_PX), y0 = Math.floor(view.originY / TILE_PX);
  const x1 = Math.floor((view.originX + widthPx) / TILE_PX);
  const y1 = Math.floor((view.originY + heightPx) / TILE_PX);
  const out = [];
  for (let x = x0; x <= x1; x++) {
    for (let y = y0; y <= y1; y++) {
      // y is not wrapped: above or below the Mercator limit there is no tile, and asking for one is
      // a 404 on someone else's server. x IS wrapped, because a route can legitimately cross the
      // antimeridian and the tile grid is a cylinder.
      if (y < 0 || y >= n) continue;
      out.push({ z: view.zoom, x: ((x % n) + n) % n, y, px: x * TILE_PX - view.originX,
                 py: y * TILE_PX - view.originY });
    }
  }
  return out;
}

export function tileUrl({ z, x, y }, template = OSM_URL) {
  return template.replace('{z}', z).replace('{x}', x).replace('{y}', y);
}

/**
 * Holds the tile images and draws them.
 *
 * The cache is the whole design. A canvas redraw happens every second while running, and every one
 * of them asks for the same tiles; without a cache that is a request per tile per second, which is
 * abusive to a donated service and would be rate-limited within a minute — the map would go blank
 * exactly when the run got interesting. So: one request per tile ever, failures remembered as
 * failures, and `draw` is synchronous over whatever has arrived.
 */
export class TileLayer {
  /**
   * `loadImage` is injected so the projection and the caching can be tested without a network, and
   * so a page with no network at all degrades to the bare trace rather than throwing.
   */
  constructor({ template = OSM_URL, loadImage = null, onLoad = null, maxTiles = 64 } = {}) {
    this.template = template;
    this.onLoad = onLoad;
    this.maxTiles = maxTiles;
    this.cache = new Map();          // url -> image | 'pending' | 'failed'
    this.requests = 0;
    this.failures = 0;
    this.loadImage = loadImage || (url => new Promise((resolve, reject) => {
      const img = new Image();
      // The tile servers send `access-control-allow-origin: *`. Asking for CORS keeps the canvas
      // untainted, which costs nothing here and keeps a future "save the map as an image" possible.
      img.crossOrigin = 'anonymous';
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('tile failed'));
      img.src = url;
    }));
  }

  /** Whether anything is drawable yet. Used to decide if the trace needs its own background. */
  get ready() {
    for (const v of this.cache.values()) if (v && v !== 'pending' && v !== 'failed') return true;
    return false;
  }

  _want(url) {
    const have = this.cache.get(url);
    if (have) return have === 'pending' || have === 'failed' ? null : have;
    if (this.cache.size >= this.maxTiles) return null;
    this.cache.set(url, 'pending');
    this.requests += 1;
    this.loadImage(url).then(img => {
      this.cache.set(url, img);
      if (this.onLoad) this.onLoad();
    }).catch(() => {
      // Remembered as failed, and never retried. A tile that 404s will 404 again, and a network that
      // is down will be down for the next redraw a second later; retrying turns one failure into
      // sixty a minute.
      this.cache.set(url, 'failed');
      this.failures += 1;
    });
    return null;
  }

  /**
   * Draw the basemap for `view` into a 2D context. Returns how many tiles were actually painted.
   *
   * Never throws and never waits: whatever has arrived is drawn, the rest is requested, and the
   * `onLoad` callback brings the caller back when there is more. A map that blocked the render loop
   * on a tile request would stall the coaching, which is the part that matters.
   */
  draw(g, view, widthPx, heightPx) {
    let painted = 0;
    for (const t of tilesFor(view, widthPx, heightPx)) {
      const img = this._want(tileUrl(t, this.template));
      if (!img) continue;
      try {
        g.drawImage(img, t.px, t.py, TILE_PX, TILE_PX);
        painted += 1;
      } catch { /* a broken image is not worth taking the page down for */ }
    }
    return painted;
  }

  state() {
    let loaded = 0, pending = 0;
    for (const v of this.cache.values()) {
      if (v === 'pending') pending += 1;
      else if (v !== 'failed') loaded += 1;
    }
    return { loaded, pending, failed: this.failures, requested: this.requests };
  }
}
