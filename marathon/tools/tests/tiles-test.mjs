// The basemap: projection, tile selection, and the caching that keeps it off somebody's server.
//
// "The GPS shows some sort of path, but it doesn't actually show the map or the streets I'm
// running." A line in a void is unreadable — you cannot tell a loop of your block from a loop of the
// park. These check that the streets end up under the right part of the line, which is the only way
// a basemap can be wrong that still looks fine in a screenshot.

import assert from 'node:assert/strict';
import { lonToTileX, latToTileY, fitZoom, viewFor, boundsOf, tilesFor, tileUrl,
         TileLayer, TILE_PX, MIN_ZOOM, MAX_ZOOM } from '../tiles.js';

{
  // Against coordinates that can be checked by hand rather than against this file's own output.
  //
  // At zoom 0 the whole world is one tile, so the prime meridian is at x = 0.5 and the equator at
  // y = 0.5. At zoom 1 there are four tiles and Greenwich sits on the corner of all of them.
  assert.equal(lonToTileX(-180, 0), 0);
  assert.equal(lonToTileX(0, 0), 0.5);
  assert.equal(lonToTileX(180, 0), 1);
  assert.ok(Math.abs(latToTileY(0, 0) - 0.5) < 1e-12, 'the equator is the middle of the world');
  assert.equal(lonToTileX(0, 1), 1);

  // A published reference point: the OSM wiki's worked example puts Berlin (52.5163, 13.3777) in
  // tile 8800/5373 at zoom 14.
  assert.equal(Math.floor(lonToTileX(13.3777, 14)), 8800);
  assert.equal(Math.floor(latToTileY(52.5163, 14)), 5373);
  console.log('  ok  the projection agrees with the published tile numbering');
}

{
  // The route must land where the streets are. This is the failure a screenshot hides: a map that
  // renders beautifully with the trace a block away from the road it was run on.
  const path = [[42.3505, -71.1054], [42.3520, -71.1054], [42.3520, -71.1030]];
  const b = boundsOf(path);
  const view = viewFor(b, 320, 190);
  // The corners of the bounding box must sit inside the canvas, and the box must be centred in it.
  const left = view.x(b.minLon), right = view.x(b.maxLon);
  const top = view.y(b.maxLat), bottom = view.y(b.minLat);
  assert.ok(left > 0 && right < 320, `the route runs off the canvas: ${left} to ${right}`);
  assert.ok(top > 0 && bottom < 190, `vertically too: ${top} to ${bottom}`);
  assert.ok(Math.abs((left + right) / 2 - 160) < 1, 'and it must be centred horizontally');
  assert.ok(Math.abs((top + bottom) / 2 - 95) < 1, 'and vertically');
  // North is up and east is right, which a sign error would silently reverse.
  assert.ok(view.y(42.3520) < view.y(42.3505), 'a higher latitude must draw higher on the canvas');
  assert.ok(view.x(-71.1030) > view.x(-71.1054), 'and a higher longitude further right');
  console.log(`  ok  the route is centred, upright and inside the frame (zoom ${view.zoom})`);
}

{
  // Zoom must be the closest that still fits: a four-block run shown at city scale has streets on it
  // and is still useless.
  const short = boundsOf([[42.3505, -71.1054], [42.3515, -71.1044]]);   // ~130 m
  const long = boundsOf([[42.30, -71.20], [42.40, -71.00]]);            // ~17 km
  const zShort = fitZoom(short, 320, 190), zLong = fitZoom(long, 320, 190);
  assert.ok(zShort > zLong, `a short route must zoom in further: ${zShort} vs ${zLong}`);
  assert.ok(zShort <= MAX_ZOOM && zLong >= MIN_ZOOM, 'and both must stay inside what exists');
  // Whatever it picks must actually fit, or the route is cropped.
  const v = viewFor(short, 320, 190);
  assert.ok(v.x(short.maxLon) - v.x(short.minLon) <= 320, 'the chosen zoom must fit the width');
  console.log(`  ok  zoom is the closest that still fits (${zShort} for 130 m, ${zLong} for 17 km)`);
}

{
  // Tile coverage: every pixel of the canvas must be covered, or the map has holes in it.
  const b = boundsOf([[42.3505, -71.1054], [42.3560, -71.0980]]);
  const view = viewFor(b, 320, 190);
  const tiles = tilesFor(view, 320, 190);
  assert.ok(tiles.length >= 1, 'a route must be covered by at least one tile');
  for (const [x, y] of [[0, 0], [319, 189], [160, 95]]) {
    const covering = tiles.filter(t => t.px <= x && x < t.px + TILE_PX
                                    && t.py <= y && y < t.py + TILE_PX);
    assert.equal(covering.length, 1, `pixel ${x},${y} is covered by ${covering.length} tiles`);
  }
  assert.match(tileUrl(tiles[0]), /^https:\/\/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png$/);
  console.log(`  ok  the canvas is covered exactly once by ${tiles.length} tiles`);
}

{
  // A run redraws the map every second. Without a cache that is a request per tile per second to a
  // service run on donations, which would be rate-limited inside a minute — the map would go blank
  // exactly when the run got interesting.
  let fetched = 0;
  const layer = new TileLayer({ loadImage: url => { fetched += 1; return Promise.resolve({ url }); } });
  const view = viewFor(boundsOf([[42.3505, -71.1054], [42.3530, -71.1020]]), 320, 190);
  const g = { drawImage() {} };
  for (let i = 0; i < 60; i++) layer.draw(g, view, 320, 190);
  await new Promise(r => setTimeout(r, 5));
  const once = fetched;
  for (let i = 0; i < 60; i++) layer.draw(g, view, 320, 190);
  assert.equal(fetched, once, `sixty more redraws must fetch nothing: ${fetched} vs ${once}`);
  assert.ok(once <= 12, `and one screen should not need ${once} tiles`);
  console.log(`  ok  120 redraws cost ${once} requests, not ${once * 120}`);
}

{
  // A failed tile must be remembered as failed. Retrying turns one dead network into sixty requests
  // a minute, and the phone this runs on spends real sessions with no signal at all.
  let attempts = 0;
  const layer = new TileLayer({ loadImage: () => { attempts += 1; return Promise.reject(new Error('x')); } });
  const view = viewFor(boundsOf([[42.3505, -71.1054], [42.3512, -71.1046]]), 320, 190);
  const g = { drawImage() { throw new Error('nothing to draw'); } };
  layer.draw(g, view, 320, 190);
  await new Promise(r => setTimeout(r, 5));
  const first = attempts;
  for (let i = 0; i < 30; i++) layer.draw(g, view, 320, 190);
  assert.equal(attempts, first, 'a failed tile must not be retried every redraw');
  assert.equal(layer.ready, false, 'and the layer must admit it has nothing');
  assert.ok(layer.state().failed > 0, 'and say so in its state');
  console.log(`  ok  a dead network costs ${first} requests, not ${first * 31}, and degrades quietly`);
}

{
  // Drawing must never throw. It runs inside the render loop that also does the coaching, and a map
  // that takes the page down has cost far more than it was worth.
  const layer = new TileLayer({ loadImage: () => Promise.resolve({}) });
  const view = viewFor(boundsOf([[42.35, -71.10], [42.36, -71.09]]), 320, 190);
  await layer.draw({ drawImage() {} }, view, 320, 190);
  await new Promise(r => setTimeout(r, 5));
  const painted = layer.draw({ drawImage() { throw new Error('broken image'); } }, view, 320, 190);
  assert.equal(painted, 0, 'a broken image paints nothing rather than throwing');

  // And a route with nothing in it must not produce a projection at all.
  assert.equal(boundsOf([]), null);
  assert.equal(boundsOf([[42.35, -71.10]]), null);
  console.log('  ok  a broken tile and an empty route are survivable');
}

{
  // A stationary start has zero extent, and zero extent divides by zero. The first fixes of every
  // session look exactly like this.
  const b = boundsOf([[42.3505, -71.1054], [42.3505, -71.1054]]);
  assert.ok(b.maxLat > b.minLat && b.maxLon > b.minLon, 'a standing start must still have a box');
  const view = viewFor(b, 320, 190);
  assert.ok(Number.isFinite(view.x(-71.1054)) && Number.isFinite(view.y(42.3505)),
    'and it must project to a real pixel');
  assert.ok(view.zoom <= MAX_ZOOM);
  console.log('  ok  a route that has not moved yet still has a map');
}

console.log('\nAll tile tests passed.');
