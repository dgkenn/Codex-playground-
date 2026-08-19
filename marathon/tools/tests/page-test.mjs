// The artifact, in a real browser.
//
// The other suites test the modules. This one tests the thing that actually ships: the built page,
// loaded from disk, with its buttons clicked. It exists because every device bug so far has lived in
// the gap between "the module is correct" and "the page works" — an inlining collision, a tone
// played outside its gesture, a module script a WebView would not run. None of those could fail a
// module test, and all of them presented identically on the phone: nothing happens.
//
// It also runs the rehearsal end to end, which is the closest thing to a run that exists indoors.
//
//   npm i playwright-core        (once, anywhere on the path)
//   node tools/tests/page-test.mjs
//
// Skips rather than fails when playwright-core is absent, so the ordinary `node tests/*.mjs` sweep
// does not depend on a browser being installed.

import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createServer } from 'node:http';

const here = dirname(fileURLToPath(import.meta.url));
const APP = join(here, '..', '..', '..', 'docs', 'pace-coach.html');

let chromium;
try {
  ({ chromium } = await import('playwright-core'));
} catch {
  console.log('  --  skipped: playwright-core is not installed (npm i playwright-core)');
  process.exit(0);
}

/** Chromium ships with the image in this environment; fall back to whatever playwright resolves. */
function browserPath() {
  const root = '/opt/pw-browsers';
  if (!existsSync(root)) return undefined;
  const dir = readdirSync(root).find(d => /^chromium-\d+$/.test(d));
  const exe = dir && join(root, dir, 'chrome-linux', 'chrome');
  return exe && existsSync(exe) ? exe : undefined;
}

const browser = await chromium.launch({
  executablePath: browserPath(),
  // The gesture rules are enforced by the Tones class and covered by its own suite; here the point
  // is that the wiring reaches the audio element at all, so the policy is stood down.
  args: ['--autoplay-policy=no-user-gesture-required', '--no-sandbox'],
});
const page = await browser.newPage();

const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
// The webfont stylesheet is the page's only external request and is deliberately non-blocking, so a
// sandbox with no network to Google must not fail the suite — in either the request log or the
// console message the failed subresource also produces.
const ignorable = u => !u || u.includes('fonts.googleapis.com') || u.includes('fonts.gstatic.com');
page.on('console', m => {
  if (m.type() === 'error' && !ignorable(m.location()?.url)) errors.push('console: ' + m.text());
});
page.on('requestfailed', r => {
  if (!ignorable(r.url())) errors.push(`request failed: ${r.url()} (${r.failure()?.errorText})`);
});

// Record media playback and speech without touching the page's own code.
await page.addInitScript(() => {
  window.__plays = [];
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    window.__plays.push((this.src || '').length);
    return play.call(this);
  };
  window.__spoken = [];
  if (window.speechSynthesis) window.speechSynthesis.speak = u => window.__spoken.push(u.text);
});

await page.goto('file://' + APP, { waitUntil: 'load' });

// --- it boots ------------------------------------------------------------------------------------

{
  const build = (await page.textContent('#buildid')).trim();
  assert.match(build, /^build \S+ · /, `the build stamp must be visible: got "${build}"`);
  console.log(`  ok  the page boots and states its build (${build})`);
}

// --- the loader ----------------------------------------------------------------------------------

{
  // The entry point is a page that never changes, which fetches the app that does — see loader.html
  // for why. What has to hold: it retrieves the app, replaces itself with it, and the app's scripts
  // then actually run in the loader's own origin. If document.write left the page inert, everything
  // above would still pass and the URL the athlete opens would show a spinner forever.
  // Served over http rather than from a file. A `file://` page has an opaque origin and cannot
  // fetch at all, which is not the situation being tested — and is not the situation on the phone.
  const app = readFileSync(APP, 'utf8');
  const loaderHtml = readFileSync(join(here, '..', '..', '..', 'docs', 'index.html'), 'utf8');
  const server = createServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    res.end(loaderHtml);
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const origin = `http://127.0.0.1:${server.address().port}`;

  const page2 = await browser.newPage();
  let fetched = 0;
  await page2.route('**raw.githubusercontent.com/**', route => {
    fetched += 1;
    route.fulfill({
      status: 200, contentType: 'text/plain; charset=utf-8',
      headers: { 'access-control-allow-origin': '*' },
      body: app,
    });
  });
  page2.on('console', m => { if (m.type() === 'error') console.log('      loader console:', m.text()); });
  page2.on('pageerror', e => console.log('      loader error:', e.message));
  await page2.goto(origin + '/');
  await page2.waitForSelector('#buildid', { timeout: 15000 });
  assert.equal(fetched, 1, 'the loader must fetch the app exactly once');
  assert.equal(await page2.evaluate(() => location.origin), origin,
    'the app must run at the loader\'s own origin, or it loses Bluetooth and location');
  assert.match((await page2.textContent('#buildid')).trim(), /^build \S+ · /);
  assert.ok(await page2.$('button[data-tone="ease"]'), 'the written page must be interactive');
  await page2.close();
  console.log('  ok  the loader fetches the app and hands over to it in place');

  // --- and when it cannot -----------------------------------------------------------------------
  // A spinner at a trailhead with no signal is indistinguishable from the app being broken.
  const page3 = await browser.newPage();
  await page3.route('**raw.githubusercontent.com/**', route => route.abort('connectionfailed'));
  await page3.goto(origin + '/');
  await page3.waitForSelector('button', { timeout: 15000 });
  assert.match(await page3.textContent('h1'), /Could not load/);
  assert.equal((await page3.textContent('button')).trim(), 'Retry');
  await page3.close();
  await new Promise(r => server.close(r));
  console.log('  ok  a failed load reports the reason and offers a retry');
}

// --- the tone buttons ----------------------------------------------------------------------------

{
  // The reported bug: every tone button did nothing. Each must reach a distinct piece of audio —
  // distinct, because five buttons all playing the same sound is the same failure one level down.
  const names = ['in_band', 'ease', 'lift', 'attend', 'degraded'];
  for (const n of names) await page.click(`button[data-tone="${n}"]`);
  await page.waitForTimeout(500);
  const plays = await page.evaluate(() => window.__plays);
  const unlockCount = 10;                       // five earcons, two elements each
  assert.ok(plays.length >= unlockCount + names.length,
    `expected the unlock plus five tones, saw ${plays.length} playbacks`);
  const tonePlays = plays.slice(unlockCount);
  assert.equal(new Set(tonePlays).size >= 4, true,
    'the tone buttons must play different sounds, not the same one five times');
  console.log(`  ok  all five tone buttons reach the audio element (${tonePlays.length} plays)`);
}

// --- the checks ----------------------------------------------------------------------------------

{
  await page.click('#preflight');
  await page.waitForTimeout(400);
  const checks = (await page.textContent('#checks')).replace(/\s+/g, ' ');
  for (const label of ['Sound', 'Voice', 'Armband', 'Location', 'Screen stays on']) {
    assert.ok(checks.includes(label), `preflight must report on ${label}: got "${checks}"`);
  }
  console.log('  ok  preflight reports on every subsystem');
}

// --- units and the plan --------------------------------------------------------------------------

{
  await page.click('#u-km');
  const km = await page.inputValue('#target');
  await page.click('#u-mi');
  const mi = await page.inputValue('#target');
  assert.notEqual(km, mi, 'switching units must re-express the target, not relabel it');
  assert.equal(await page.textContent('#perlabel'), '/ MI');
  // And a round trip must land back where it started. The box holds a rounded mm:ss, so re-parsing
  // it on each switch loses up to half a second every time and the error compounds with toggling.
  assert.equal(mi, '14:30', `a mile -> km -> mile round trip drifted to ${mi}`);
  for (let i = 0; i < 6; i++) { await page.click('#u-km'); await page.click('#u-mi'); }
  assert.equal(await page.inputValue('#target'), '14:30', 'and it must not drift with repetition');
  console.log(`  ok  the target converts with the unit (${km} per km = ${mi} per mile)`);
}

{
  // Loading a planned session must set the band from the plan, not leave the previous numbers.
  await page.click('.strip button:nth-child(5)');       // Friday of week one: the first run/walk
  await page.waitForTimeout(120);
  await page.click('#loadsess');
  await page.waitForTimeout(120);
  const title = (await page.textContent('#sesstitle')).trim();
  const band = (await page.textContent('#bandtext')).replace(/\s+/g, ' ').trim();
  assert.ok(title.length > 3, 'a session must be named');
  assert.match(band, /Band \d+:\d\d to \d+:\d\d/, `the band must be stated: "${band}"`);
  console.log(`  ok  a planned session loads its own band (${title})`);
}

// --- the whole coach, indoors --------------------------------------------------------------------

{
  await page.click('#m-rehearse');
  await page.click('#go');
  await page.waitForFunction(
    () => /Rehearsal complete/.test(document.getElementById('log').textContent),
    null, { timeout: 180000 });

  const lines = await page.$$eval('#log div', ds => ds.map(d => d.textContent).reverse());
  const summary = lines[lines.length - 1];

  // The scripted run starts 28% too fast and settles. That must produce a run of escalating
  // reminders and then an acknowledgement — not silence, and not a stream.
  const tones = lines.filter(l => /— (ease|lift|in band)/.test(l));
  assert.ok(tones.length >= 4, `a run that starts 28% fast must be coached: ${tones.length} tones`);
  assert.ok(tones.some(l => /in band/.test(l)),
    'coming back into the band must be acknowledged, or the athlete never learns they fixed it');

  // The rate is the number that says coaching from nagging, and it must be measured on the clock the
  // mode actually ran on. It was computed from the GPS sample count, which a rehearsal never fills:
  // four tones in thirty simulated minutes were reported as 240 a minute, over zero distance.
  const rate = Number(summary.match(/\(([\d.]+)\/min\)/)?.[1]);
  const dist = Number(summary.match(/([\d.]+) (mi|km)/)?.[1]);
  assert.ok(rate > 0 && rate < 1, `${rate} tones/min is not a plausible rate: "${summary}"`);
  assert.ok(dist > 1, `the rehearsal covered ${dist} — the simulated distance was not counted`);

  // The preflight's own "Voice check" is in here too; splits are the ones that name a split.
  const spoken = (await page.evaluate(() => window.__spoken))
    .filter(l => /^\d+ (mile|miles|K)\b/.test(l));
  assert.ok(spoken.length >= 2, `splits must be spoken: ${JSON.stringify(spoken)}`);
  for (const line of spoken) {
    assert.match(line, /^\d+ (mile|miles|K)\. \d+:\d\d\./, `malformed split: "${line}"`);
  }
  console.log(`  ok  the rehearsal runs end to end (${summary.trim()})`);
  console.log(`  ok  splits are spoken and well formed (${spoken.join(' | ')})`);
}

await browser.close();

if (errors.length) {
  console.error('\nPage errors:\n  ' + errors.join('\n  '));
  process.exit(1);
}
console.log('\nAll page tests passed.');
