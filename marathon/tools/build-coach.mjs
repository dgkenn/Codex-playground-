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
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

/**
 * A module, inlined into the one classic script block in its own scope: its body runs inside a
 * function, and only what it exports comes out as top-level names.
 *
 * It used to be pasted in bare, so every helper of every module shared one namespace with every
 * other and with the page: a `const` clash broke the parse (caught), and a FUNCTION clash silently
 * replaced one with the other (not caught -- selftest.js's `finish` became the page's session
 * `finish`). Scoped, a module's private names cannot meet anything; its exports still can, and the
 * duplicate check below counts those.
 */
function inline(path) {
  const src = readFileSync(join(here, path), 'utf8');
  const names = [...src.matchAll(/^export\s+(?:async\s+)?(?:const|let|var|function\*?|class)\s+([A-Za-z_$][\w$]*)/gm)]
    .map(m => m[1]);
  const body = src
    .replace(/^export\s+(const|let|var|function|class|async function)\s/gm, '$1 ')
    .replace(/^export\s*\{[^}]*\}\s*;?\s*$/gm, '')
    .replace(/^import\s[^;]+;\s*$/gm, '')
    .trim();
  return `/*<module ${path}>*/\nconst { ${names.join(', ')} } = (() => {\n${body}\n`
       + `return { ${names.join(', ')} };\n})();\n/*</module>*/`;
}

// A build stamp, so "reload and try again" can be verified rather than assumed.
//
// The loop is: something breaks on the phone, it gets fixed here, the fix is pushed, the page is
// reloaded. Without a visible build id the first question after every fix is "are you sure you have
// the new one", which is a question neither side can answer.
//
// The id is a hash of the page's own content, not the commit it was built from. A commit hash
// cannot work: the build has to happen before the commit that contains it, so the stamp always
// names the *previous* commit, and amending to fix that changes the hash again. A content hash is
// self-consistent — the same sources always produce the same id, and it can be checked here with
// `grep -o 'BUILD = [^;]*' docs/pace-coach.html` and compared against what the phone shows.
const built = new Date().toISOString().replace('T', ' ').slice(0, 16) + 'Z';

const parts = {
  MONITOR: inline('pace-monitor.js'),
  GEO: inline('geo.js'),
  SENSOR: inline('sensor.js'),
  HRMONITOR: inline('hr-monitor.js'),
  TONES: inline('tones.js'),
  RAMP: inline('ramp.js'),
  BTPROBE: inline('bt-probe.js'),
  SESSIONSTORE: inline('session-store.js'),
  RUNSTATS: inline('run-stats.js'),
  SESSIONFORMAT: inline('session-format.js'),
  TILES: inline('tiles.js'),
  PROGRESSION: inline('progression.js'),
  PACEVOICE: inline('pace-voice.js'),
  HRBLOCKS: inline('hr-blocks.js'),
  TERRAIN: inline('terrain.js'),
  FUSION: inline('fusion.js'),
  READINESS: inline('readiness.js'),
  POLAROFFLINE: inline('polar-offline.js'),
  BACKFILL: inline('backfill.js'),
  BENCHMARKS: inline('benchmarks.js'),
  SELFTEST: inline('selftest.js'),
  REMOTEBENCH: inline('remote-bench.js'),
  THRESHOLD: inline('threshold.js'),
  LOADWATCH: inline('load-watch.js'),
  PLAN: readFileSync(join(root, 'engine', 'app_plan.generated.json'), 'utf8').trim(),
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

// Hashed with the stamp still a placeholder, so the id depends on everything except itself.
const stamp = createHash('sha256').update(html).digest('hex').slice(0, 8);
if (!html.includes('/*{{BUILD}}*/')) throw new Error('template is missing the BUILD marker');
html = html.replace('/*{{BUILD}}*/', JSON.stringify({ id: stamp, at: built }));

// Does the thing that is about to ship actually parse?
//
// It did not. Inlining a module that declared its own `MI` alongside the page's `MI` produced two
// `const` of the same name in one scope, which is a SyntaxError — so the entire script failed at
// parse time and the page rendered as an empty shell. Nothing in the build noticed: the markers were
// all present, the file was written, the byte count looked right.
//
// Every module here is inlined into ONE scope, so every top-level name in every module shares a
// namespace with every other. That makes collisions a structural hazard of the design rather than a
// slip, and a build that cannot detect its own broken output is not a build.
const body = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));
try {
  new Function(body);
} catch (e) {
  throw new Error(`the assembled page does not parse: ${e.message}\n`
                + '  Most likely two inlined modules declare the same top-level name.');
}

// Does any top-level name appear twice?
//
// A duplicated `const` is a syntax error and the check above catches it. A duplicated FUNCTION is
// not: in a classic script the later declaration silently replaces the earlier one. selftest.js
// declared a helper `finish`, the page declares the `finish` that ends a session, and the page's
// won -- so the self-test would have ended the session and reported nothing. One scope for every
// module makes this a standing hazard, so every top-level declaration is counted.
{
  const seen = new Map();
  const add = (name, i) => seen.set(name, [...(seen.get(name) || []), i + 1]);
  let inModule = false;
  body.split('\n').forEach((line, i) => {
    // A scoped module contributes its exports (the destructuring line) and nothing else.
    if (line.startsWith('/*<module ')) { inModule = true; return; }
    if (line.startsWith('/*</module>*/')) { inModule = false; return; }
    const ex = /^const \{ ([^}]*) \} = \(\(\) => \{$/.exec(line);
    if (ex) { ex[1].split(',').map(x => x.trim()).filter(Boolean).forEach(n => add(n, i)); return; }
    if (inModule) return;
    const m = /^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(|^(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)\b/.exec(line);
    if (m) add(m[1] || m[2], i);
  });
  const dup = [...seen].filter(([, at]) => at.length > 1);
  if (dup.length) {
    throw new Error('the assembled page declares a top-level name more than once (the later silently wins):\n'
                  + dup.map(([n, at]) => `  ${n} at lines ${at.join(', ')}`).join('\n'));
  }
}

// Does it reference a name nothing ever declared?
//
// It did. `tickCoach` read `govern` in a plain boolean expression, and no version of the function's
// signature after the run/walk governance change actually declared it — a parameter dropped in one
// edit while the body that reads it survived. `new Function(body)` above does not catch this: parsing
// a script never evaluates it, and reading an undeclared name is a runtime ReferenceError, not a
// syntax error. It hid behind `&&` short-circuiting besides — the branch that reaches `govern` is
// only live once an armband is connected and reporting a fresh heart rate, a condition no test and
// no manual click-through without real Bluetooth had ever created.
//
// This is exactly what a linter's `no-undef` rule is for: it does not need to know what the code
// means, only that every name it reads was declared somewhere reachable. Soft-fails when eslint is
// not on the machine, the same way the browser suite skips without playwright-core — the build must
// not depend on a tool this project has never asked anyone to install permanently.
try {
  const { execFileSync } = await import('node:child_process');
  const out = execFileSync(
    'eslint',
    ['--no-config-lookup', '-c', join(here, 'eslint.no-undef.config.mjs'), '--stdin',
     '--stdin-filename=page.js'],
    { input: body, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
  );
  void out;
} catch (e) {
  if (e.code === 'ENOENT') {
    console.warn('  (skipping the undeclared-name check: eslint is not installed)');
  } else if (typeof e.status === 'number') {
    throw new Error(`the assembled page references a name nothing declared:\n${e.stdout}`);
  } else {
    throw e;
  }
}

// Does it actually START?
//
// Parsing and declared names are not enough. Every module and the page share one scope, and a
// top-level `const` read by something the first render calls -- before the line that declares it --
// is a ReferenceError at load, which neither check above can see: twice in October (the ladder's
// bridge steps, then the niggle log, which failed silently into an empty log). So the page is loaded
// in a headless browser before anything ships, and any error during the first second fails the
// build. Skipped, like the lint, when the browser is not on the machine; `--no-smoke` skips it.
if (!process.argv.includes('--no-smoke')) {
  let chromium = null;
  try { ({ chromium } = await import('playwright-core')); } catch { /* not installed */ }
  if (!chromium) {
    console.warn('  (skipping the boot check: playwright-core is not installed)');
  } else {
    const { existsSync, readdirSync, mkdtempSync, rmSync } = await import('node:fs');
    const { tmpdir } = await import('node:os');
    const pw = '/opt/pw-browsers';
    const dir = existsSync(pw) && readdirSync(pw).find(d => /^chromium-\d+$/.test(d));
    const exe = dir && join(pw, dir, 'chrome-linux', 'chrome');
    const tmp = mkdtempSync(join(tmpdir(), 'coach-boot-'));
    const file = join(tmp, 'pace-coach.html');
    writeFileSync(file, html);
    const browser = await chromium.launch({ executablePath: exe && existsSync(exe) ? exe : undefined, args: ['--no-sandbox'] });
    const errors = [];
    try {
      const page = await browser.newPage();
      page.on('pageerror', e => errors.push(e.message));
      await page.goto('file://' + file, { waitUntil: 'load' });
      await page.waitForTimeout(1000);
    } finally {
      await browser.close();
      rmSync(tmp, { recursive: true, force: true });
    }
    if (errors.length) {
      throw new Error(`the assembled page throws while starting:\n  ${errors.join('\n  ')}\n`
                    + '  A top-level const read before its declaration is the usual cause.');
    }
  }
}

// Both docs folders, because they serve different routes and had already drifted apart:
// `marathon/docs` is what the githack URL points at, and the repo-root `docs` is the only folder
// GitHub Pages can serve from ("deploy from a branch" offers root or /docs, nothing else). A stale
// copy in either is a page that silently serves an old build, which is the exact failure the build
// stamp exists to catch — better not to create it in the first place.
//
// `index.html` is the loader, `pace-coach.html` is the app. The split exists because githack caches
// hard and ignores query strings: the entry point has to be a file that never changes, or a fix
// pushed here does not reach the phone. See `loader.html` for the whole argument.
const repoRoot = join(root, '..');
const loader = readFileSync(join(here, 'loader.html'), 'utf8');

const targets = [
  [join(root, 'docs', 'pace-coach.html'), html],
  [join(repoRoot, 'docs', 'pace-coach.html'), html],
  [join(here, 'pace-coach-hosted.html'), html],
  [join(root, 'docs', 'index.html'), loader],
  [join(repoRoot, 'docs', 'index.html'), loader],
];
for (const [path, body] of targets) writeFileSync(path, body);

console.log(`app ${(html.length / 1024).toFixed(0)} kB (build ${stamp}), `
          + `loader ${(loader.length / 1024).toFixed(1)} kB ->`);
for (const [path] of targets) console.log(`  ${path.replace(root + '/', '')}`);
