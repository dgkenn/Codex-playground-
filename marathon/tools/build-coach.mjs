// Assembles the single-file coach from the modules that are individually tested.
//
// The hosted page has to be one file — an artifact is one file, and a phone at a trailhead should
// not be fetching a module graph over a mobile connection. But a hand-maintained copy of tested code
// is a copy that drifts, and the drift is silent: the tests keep passing against the module while
// the page ships something subtly different.
//
// So the page is generated. `pace-monitor.js`, `geo.js` and `sensor.js` are the sources of truth,
// each with its own test suite, and this inlines them verbatim between markers. The plan comes from
// the engine the same way. Nothing in the output is typed twice.
//
//   node tools/build-coach.mjs
//
// Then re-run the suites: the parity check extracts the monitor back OUT of the built page and
// compares it against the Python golden vectors, which is what makes "verbatim" a claim rather than
// an intention.

import { readFileSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

/** Strip ES module syntax so the source can sit inside one classic script block. */
function inline(path) {
  return readFileSync(join(here, path), 'utf8')
    .replace(/^export\s+(const|let|var|function|class|async function)\s/gm, '$1 ')
    .replace(/^export\s*\{[^}]*\}\s*;?\s*$/gm, '')
    .replace(/^import\s[^;]+;\s*$/gm, '')
    .trim();
}

// A build stamp, so "reload and try again" can be verified rather than assumed.
//
// The loop is: something breaks on the phone, it gets fixed here, the fix is pushed, the page is
// reloaded. Without a visible build id the first question after every fix is "are you sure you have
// the new one", which is a question neither side can answer.
let stamp;
try {
  stamp = execSync('git rev-parse --short HEAD', { cwd: root }).toString().trim();
} catch {
  stamp = 'local';
}
const built = new Date().toISOString().replace('T', ' ').slice(0, 16) + 'Z';

const parts = {
  MONITOR: inline('pace-monitor.js'),
  GEO: inline('geo.js'),
  SENSOR: inline('sensor.js'),
  HRMONITOR: inline('hr-monitor.js'),
  TONES: inline('tones.js'),
  PLAN: readFileSync(join(root, 'engine', 'app_plan.generated.json'), 'utf8').trim(),
  BUILD: JSON.stringify({ id: stamp, at: built }),
};

let html = readFileSync(join(here, 'coach-template.html'), 'utf8');

// Ship a classic script, not a module.
//
// Nothing forces `type="module"` any more — the build inlines every dependency, so there are no
// imports and no top-level await left. And the module type costs compatibility: module scripts are
// fetched with CORS semantics, run deferred, and are unreliable in third-party WebViews and in
// anything that injects a page with document.write. Bluefy, which is the only way to reach the
// armband from an iPhone, is exactly such a browser. Strict mode and an IIFE preserve the module's
// scoping and semantics without its delivery constraints.
html = html
  .replace('<script type="module">', "<script>\n(function () {\n'use strict';\n")
  .replace(/<\/script>\s*$/, '})();\n</script>\n');
for (const [key, value] of Object.entries(parts)) {
  const marker = `/*{{${key}}}*/`;
  if (!html.includes(marker)) throw new Error(`template is missing the ${key} marker`);
  html = html.replace(marker, value);
}

// Both docs folders, because they serve different routes and had already drifted apart:
// `marathon/docs` is what the githack URL points at, and the repo-root `docs` is the only folder
// GitHub Pages can serve from ("deploy from a branch" offers root or /docs, nothing else). A stale
// copy in either is a page that silently serves an old build, which is the exact failure the build
// stamp exists to catch — better not to create it in the first place.
const repoRoot = join(root, '..');
const targets = [
  join(root, 'docs', 'index.html'),
  join(root, 'docs', 'pace-coach.html'),
  join(repoRoot, 'docs', 'index.html'),
  join(repoRoot, 'docs', 'pace-coach.html'),
  join(here, 'pace-coach-hosted.html'),
];
for (const t of targets) writeFileSync(t, html);

console.log(`built ${(html.length / 1024).toFixed(0)} kB ->`);
for (const t of targets) console.log(`  ${t.replace(root + '/', '')}`);
