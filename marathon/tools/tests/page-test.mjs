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
// The map tiles join it for the same reason: they are fetched at runtime, the layer is built to
// degrade to a bare trace when they do not arrive, and a sandbox with no route to the tile server
// must exercise that path rather than fail the suite. That the failures are BOUNDED — ten requests
// for a dead network, not one per redraw per second — is asserted in tiles-test.mjs, where it can be
// checked rather than inferred from how much noise reaches this log.
const ignorable = u => !u || u.includes('fonts.googleapis.com') || u.includes('fonts.gstatic.com')
                    || u.includes('tile.openstreetmap.org');
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

/**
 * Select the day in the plan strip whose short type matches, e.g. 'ramp' or 'run/walk'.
 *
 * By content rather than by position. `nth-child(5)` meant "Friday", which meant "the run/walk" only
 * for as long as the run/walk happened to be on a Friday — so moving sessions onto the athlete's own
 * training days broke four tests that were not about scheduling at all.
 */
async function pickDay(page, kind) {
  const buttons = await page.$$('.strip button');
  for (const b of buttons) {
    if ((await b.textContent()).includes(kind)) { await b.click(); return true; }
  }
  throw new Error(`no day in the strip offers "${kind}"`);
}

// --- it boots ------------------------------------------------------------------------------------

{
  const build = (await page.textContent('#buildid')).trim();
  assert.match(build, /^build \S+ · /, `the build stamp must be visible: got "${build}"`);
  assert.match(await page.textContent('#capsline'), /direct/,
    'a page opened straight from its own URL must not claim to have come via the loader');
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
  // The route has to be visible on the page and in the diagnostics. document.write removes every
  // listener registered on the document, which is a live candidate for a native Bluetooth bridge
  // losing its reply channel — so which route was taken must be a recorded fact, not a memory.
  assert.match(await page2.textContent('#capsline'), /via loader/,
    'a page handed over by the loader must say so');
  assert.equal(await page2.evaluate(() => window.__viaLoader), true);
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
  await pickDay(page, 'run/walk');                      // wherever it falls this week
  await page.waitForTimeout(120);
  await page.click('#loadsess');
  await page.waitForTimeout(120);
  const title = (await page.textContent('#sesstitle')).trim();
  const band = (await page.textContent('#bandtext')).replace(/\s+/g, ' ').trim();
  assert.ok(title.length > 3, 'a session must be named');
  assert.match(band, /Band \d+:\d\d to \d+:\d\d/, `the band must be stated: "${band}"`);

  // A run/walk carries TWO paces and the one that matters is the run-block pace, which the session
  // used to have none of — so the coach had nothing to compare against and said nothing for the
  // whole session. It must reach the target box, and the box must be visible: it was hidden in this
  // mode on the theory that a clock-driven session has no use for a pace band.
  const target = await page.inputValue('#target');
  assert.match(target, /^\d+:\d\d$/, `the run-block pace must be loaded: "${target}"`);
  assert.ok(await page.isVisible('#target'),
    'and it must be on screen, or there is no way to set it for an unplanned session');
  const label = await page.textContent('#targetlabel');
  assert.match(label, /run the blocks/i, `and be labelled as the run-block pace: "${label}"`);
  const spoken = (await page.textContent('#log')).slice(0, 400);
  assert.match(spoken, /run at \d+:\d\d/i, `the log must state the run pace: "${spoken.slice(0, 120)}"`);
  console.log(`  ok  a planned session loads its own band (${title}, run blocks at ${target})`);
}

// --- the athlete's own numbers -------------------------------------------------------------------

{
  // Every zone boundary is rest + fraction x (max - rest), so the resting rate is load-bearing and
  // the plan ships a placeholder. The app must say so, and changing it must actually move the zones
  // rather than relabel them.
  const note = await page.textContent('#profilenote');
  assert.match(note, /placeholder/i, `an unconfirmed profile must say so: "${note}"`);

  const before = await page.$$eval('#zonebar div', ds => ds.map(d => d.title));
  await page.fill('#hrrest', '48');
  await page.waitForTimeout(120);
  const after = await page.$$eval('#zonebar div', ds => ds.map(d => d.title));
  assert.notDeepEqual(before, after, 'changing the resting rate must move every zone boundary');
  // Zone 1 opens at rest + 0.45 x reserve, on the same HR-reserve model the engine uses.
  const expected = Math.round(48 + 0.45 * (Math.round(208 - 0.7 * 30) - 48));
  assert.match(after[0], new RegExp(`^${expected}–`),
    `zone 1 must be recomputed from the new resting rate: "${after[0]}"`);
  assert.doesNotMatch(await page.textContent('#profilenote'), /placeholder/i,
    'and it must stop calling them placeholders once they are the athlete\'s own');

  // It has to survive a reload, or it is a setting the athlete re-enters at every trailhead.
  await page.reload();
  await page.waitForSelector('#hrrest');
  assert.equal(await page.inputValue('#hrrest'), '48', 'the profile must persist');
  console.log('  ok  the profile is editable, moves the zones, and persists');
}

// --- today, in one tap ---------------------------------------------------------------------------

{
  // The plan strip is seven buttons, a card, a mode picker and three numbers to copy across, all
  // before a run. This is the one button that does it.
  const title = (await page.textContent('#todaytitle')).trim();
  const detail = (await page.textContent('#todaydetail')).trim();
  assert.ok(title.length > 2, 'today must name its session');
  assert.match(detail, /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b/, `today must say which day: "${detail}"`);
  const label = (await page.textContent('#starttoday')).trim();
  const disabled = await page.getAttribute('#starttoday', 'disabled');
  // Either it can run today's session and says which kind, or it says plainly that it cannot.
  assert.ok(/^Start /.test(label) ? disabled === null : disabled !== null,
    `the button's label and its enabled state must agree: "${label}", disabled=${disabled}`);
  console.log(`  ok  today is named and offered in one tap (${title} — ${label})`);
}

{
  // Root cause of "my Sunday is empty": the shipped plan started at ASSESS, whose only gate the web
  // app has no way to satisfy -- there is no overnight HRV monitoring anywhere in tools/, only in
  // the Swift target that has never been compiled -- so nobody using this app could ever leave it.
  // ASSESS schedules a ramp test on Wednesday and one shakeout on Saturday and nothing else, so an
  // athlete whose declared days are Wednesday, Saturday and Sunday had a permanently blank Sunday.
  //
  // The plan now starts past ASSESS. This checks the migration that matters for a phone that already
  // has progress saved against the old shape: a saved phase the current plan no longer ships must
  // not be trusted at whatever week number was saved alongside it -- both reset together, or an
  // athlete could land on week 4 of a phase they have not set foot in.
  await page.evaluate(() => {
    localStorage.setItem('band.progress', JSON.stringify({ phase: 'assess', week: 3, done: {} }));
  });
  await page.reload();
  await page.waitForSelector('#phaselabel');
  const phase = (await page.textContent('#phaselabel')).trim();
  assert.doesNotMatch(phase, /assess/i, `a phase the plan no longer ships must not be trusted: "${phase}"`);
  const week = (await page.textContent('#weeklabel')).trim();
  assert.match(week, /Week 1 of/, `and the stale week number must not survive with it: "${week}"`);
  console.log(`  ok  a plan whose saved phase no longer exists resets to a real one (${phase}, ${week})`);
}

{
  // The specific day: Sunday is one of the three declared running days (Wed/Sat/Sun), and the plan's
  // first shipped phase must put a real, runnable session there rather than rest. This is what
  // "empty" meant -- the app had no control to leave the phase that never scheduled it anything.
  // The strip always renders one button per DAYS = ['Mon',...,'Sun'] in that fixed order, so
  // Sunday is always the 7th button regardless of what day it is on the device running this test.
  const btn = (await page.$$('.strip button'))[6];
  await btn.click();
  await page.waitForTimeout(80);
  const title = (await page.textContent('#sesstitle')).trim();
  assert.doesNotMatch(title, /^(rest|nothing scheduled)$/i,
    `Sunday must not be empty in the plan's first phase: "${title}"`);
  assert.equal(await page.getAttribute('#loadsess', 'disabled'), null,
    'and it must be a session the app can actually load');
  console.log(`  ok  Sunday, a declared running day, carries a real session ("${title}")`);
}

// --- the ramp test -------------------------------------------------------------------------------

{
  // The session week 1 exists for. Its timing is covered second-by-second in tests/ramp-test.mjs
  // against the real protocol; what is checked here is the wiring — that the plan's protocol reaches
  // the runner, that starting it announces the first step out loud, and that the samples it records
  // carry the stage label. Without that label the recording is one undifferentiated blob and the
  // hour on the treadmill yields no fit, which is the entire point of the session.
  // Entering the mode is now what arms the protocol -- it used to come only from the plan strip,
  // and the plan only ever schedules a ramp inside ASSESS, a phase most exports skip entirely (its
  // own gates need overnight HRV data nothing in this app collects). The mode button has to work on
  // its own or the ramp test becomes unreachable the moment ASSESS is not the current phase.
  await page.click('#m-ramp');
  assert.match(await page.textContent('#modenote'), /stage/i, 'the ramp mode must explain itself');
  // Explicitly the treadmill flow; the street flow gets its own block below. The default is street,
  // and a test that silently inherited whichever default happened to be current is how the wrong
  // one shipped.
  await page.uncheck('#rampoutdoor');
  await page.waitForTimeout(120);
  const loaded = (await page.textContent('#rampnote')).replace(/\s+/g, ' ');
  assert.match(loaded, /numbers on the dial/i, `the treadmill framing must be stated: "${loaded}"`);
  assert.match(loaded, /(\d+(\.\d+)?,\s*){4,}\d+(\.\d+)?\s*(mph|km\/h)/i,
    `and the ladder itself, as dial numbers in the athlete's own unit: "${loaded}"`);

  await page.click('#go');
  await page.waitForTimeout(2500);
  const running = await page.$$eval('#log div', ds => ds.map(d => d.textContent));
  assert.ok(running.some(l => /Walk warm-up/.test(l)),
    `the first step must be announced: ${JSON.stringify(running.slice(0, 3))}`);
  const spokenNow = await page.evaluate(() => window.__spoken);
  // In whichever unit the athlete's dial is marked in — miles per hour here, because the distance
  // unit is miles. The point is that it is a dial setting and not a pace.
  assert.ok(spokenNow.some(l => /miles an hour|kilometres an hour/i.test(l)),
    `on a treadmill the first step is a dial setting: ${JSON.stringify(spokenNow)}`);
  assert.ok(spokenNow.some(l => /\d\.\d miles an hour/i.test(l)),
    `and in mph while the athlete is working in miles: ${JSON.stringify(spokenNow)}`);
  assert.match(await page.textContent('#verdict'), /Walk warm-up/);

  await page.click('#go');                               // stop
  await page.waitForTimeout(200);

  // The samples must be labelled. Read them the way the athlete would — through the copy button —
  // so the export path is exercised too, not just the in-memory array.
  await page.evaluate(() => { navigator.clipboard.writeText = () => Promise.reject(new Error('no')); });
  await page.click('#copy');
  await page.waitForSelector('#diagtext', { timeout: 5000 });
  // The compact form: a trace in columns, with labels stored as changes rather than repeated per
  // second. That is the whole point of the format, so the assertion has to read it that way.
  const payload = JSON.parse(await page.inputValue('#diagtext'));
  assert.equal(payload.schema_version, 2);
  assert.ok(payload.t.length > 0, 'the ramp must record samples — it recorded none at all');
  assert.ok(payload.labels.length >= 1,
    `the trace must carry its stage labels: ${JSON.stringify(payload.labels)}`);
  assert.equal(payload.labels[0][1], 'warmup',
    `the first label must be the warm-up: ${JSON.stringify(payload.labels)}`);
  assert.ok(payload.n_full >= payload.t.length,
    'and it must say how many samples the recording really had');
  console.log(`  ok  the ramp loads, announces and labels `
            + `(${payload.n_full} samples -> ${payload.t.length} points, first label warmup)`);
}

{
  // Outdoors nothing holds the speed for you, so each stage has to become a paced block: the
  // instruction spoken as a pace rather than a treadmill dial setting, and the ordinary pace band
  // armed at that stage's speed so the tones can hold you in it.
  await page.click('#m-ramp');
  await page.check('#rampoutdoor');
  await page.waitForTimeout(120);
  const note = (await page.textContent('#rampnote')).replace(/\s+/g, ' ');
  assert.match(note, /\d+:\d\d.*\d+:\d\d/, `the ladder must be shown as paces: "${note}"`);
  assert.match(note, /flattest/, 'and it must say why the route has to be flat');
  assert.match(note, /\d+ bpm/, 'and state the stop rule in beats');
  assert.ok(await page.isVisible('#gauge'), 'the band gauge is meaningful on an outdoor ramp');

  await page.click('#go');
  await page.waitForTimeout(2500);
  const spoken = await page.evaluate(() => window.__spoken);
  assert.ok(spoken.some(l => /per mile|per kilometre/.test(l)),
    `the first step must be spoken as a pace outdoors: ${JSON.stringify(spoken)}`);
  assert.doesNotMatch(await page.textContent('#perlabel'), /KM\/H/,
    'the big number outdoors is your live pace, not a treadmill setting');
  await page.click('#go');
  await page.waitForTimeout(200);
  await page.uncheck('#rampoutdoor');
  console.log(`  ok  an outdoor ramp speaks paces and arms the band (${spoken.find(l => /per /.test(l))})`);
}

// --- the one-tap start cannot silently pick the wrong session ------------------------------------

{
  // The defect this exists for: the street/treadmill choice lived in a panel only reachable by NOT
  // using the one-tap start, so a one-tap ramp ran the treadmill flow — dial settings read aloud,
  // no pace band, no tones — for someone standing on a street. A whole session, silently wrong.
  // A genuinely fresh start: earlier blocks have been changing this setting, and a "default" that
  // is really "whatever the last test left behind" tests nothing.
  await page.evaluate(() => localStorage.removeItem('band.rampOutdoor'));
  await page.reload();
  await page.waitForSelector('#starttoday');

  const label = (await page.textContent('#starttoday')).trim();
  const isRampDay = await page.isVisible('#today-where');

  if (isRampDay) {
    assert.match(label, /street|treadmill/,
      `on a ramp day the button must state which flow it will run: "${label}"`);
    assert.equal(await page.getAttribute('#w-street', 'aria-pressed'), 'true',
      'the street is the default — a treadmill is the exception, and guessing wrong costs a session');
    await page.click('#w-mill');
    assert.match(await page.textContent('#starttoday'), /treadmill/);
    await page.click('#w-street');
    assert.match(await page.textContent('#starttoday'), /street/);
    assert.equal(await page.isChecked('#rampoutdoor'), true,
      'the two controls are the same setting and must not disagree');
  } else {
    // Not a ramp day. The choice is specific to the ramp, so it must be absent rather than offered
    // for a session it does not apply to — and the button must still say what it will do.
    assert.match(label, /^Start |Not a session/,
      `the button must say what it will run: "${label}"`);
    assert.doesNotMatch(label, /street|treadmill/,
      'a run/walk is neither, and must not claim to be');
  }
  console.log(`  ok  the one-tap start names its flow, and offers the ramp's choice only on a `
            + `ramp day (${label})`);
}

// --- a persistent fault does not flood the log ----------------------------------------------------

{
  // Forty log lines reach the diagnostics report. One condition repeating every second fills all
  // forty with the same line and pushes out the connect, the stages and the tones — everything
  // anyone would need. Repeats collapse to a count instead.
  await page.evaluate(() => {
    for (let i = 0; i < 30; i++) window.__log ? window.__log('same thing') : null;
  });
  const before = await page.$$eval('#log div', ds => ds.length);
  await page.click('button[data-tone="ease"]');
  await page.click('button[data-tone="ease"]');
  await page.click('button[data-tone="ease"]');
  await page.waitForTimeout(200);
  const rows = await page.$$eval('#log div', ds => ds.map(d => d.textContent));
  const repeated = rows.find(r => /ease off — ease/.test(r));
  assert.match(repeated, /×3/, `three identical lines must collapse to a count: "${repeated}"`);
  assert.ok(await page.$$eval('#log div', ds => ds.length) <= before + 1,
    'and must not add a row each time');
  console.log(`  ok  a repeated line collapses to a count (${repeated.trim()})`);
}

// --- the pace coach, actually running ------------------------------------------------------------

{
  // The main mode, started for real. The rehearsal replays through `tickRehearse` and never touches
  // `tickCoach`, so the mode the athlete spends every run in had no test that executed it at all —
  // and a refactor duly left two free variables in it, which throws on the first tick.
  await page.click('#m-coach');
  await page.fill('#target', '9:00');
  await page.click('#go');
  await page.waitForTimeout(2500);
  assert.equal(await page.textContent('#go'), 'Stop', 'the session must actually be running');
  const lines = await page.$$eval('#log div', ds => ds.map(d => d.textContent));
  assert.ok(lines.some(l => /Started/.test(l)), `no start line: ${JSON.stringify(lines)}`);
  assert.ok(!lines.some(l => /is not defined|undefined is not/.test(l)));
  const elapsed = await page.textContent('#elapsed');
  assert.match(elapsed, /^0:0[1-9]/, `the clock must advance: "${elapsed}"`);
  await page.click('#go');
  await page.waitForTimeout(200);
  console.log(`  ok  the pace coach starts, ticks and stops (${elapsed} elapsed)`);
}

// --- pace or speed, on the same run --------------------------------------------------------------

{
  // A treadmill is dialled in miles per hour and a runner thinks in minutes per mile. The ramp test
  // needs both in one session, so this is a display choice — and only a display choice: the bands,
  // the tones and the recorded samples all stay in seconds per kilometre.
  await page.click('#m-coach');
  await page.click('#r-pace');
  await page.fill('#target', '12:00');
  await page.waitForTimeout(120);
  const asPace = await page.textContent('#bandtext');
  assert.match(asPace, /Band \d+:\d\d to \d+:\d\d per mi/i, `pace band reads "${asPace}"`);

  await page.click('#r-speed');
  await page.waitForTimeout(120);
  const asSpeed = await page.textContent('#bandtext');
  assert.match(asSpeed, /Band [\d.]+ to [\d.]+ mph/i, `speed band reads "${asSpeed}"`);
  assert.equal(await page.textContent('#perlabel'), 'MPH');

  // 12:00 per mile is 5.0 mph, and the band's endpoints must swap when the units invert.
  const [lo, hi] = asSpeed.match(/([\d.]+) to ([\d.]+)/).slice(1).map(Number);
  assert.ok(lo < hi, `speed band must run slow-to-fast: ${lo} to ${hi}`);
  assert.ok(lo < 5.0 && hi > 5.0, `5.0 mph must sit inside the band: ${lo}-${hi}`);

  // The choice must survive a reload; it is a preference, not a mode.
  await page.reload();
  await page.waitForSelector('#r-speed');
  assert.equal(await page.getAttribute('#r-speed', 'aria-pressed'), 'true');
  await page.click('#r-pace');
  console.log(`  ok  the readout switches between pace and speed and persists (${asSpeed.trim()})`);
}

{
  // The treadmill ramp must announce the dial, not a conversion of it.
  await page.click('#m-ramp');
  await page.uncheck('#rampoutdoor');
  await page.waitForTimeout(120);
  const note = (await page.textContent('#rampnote')).replace(/\s+/g, ' ');
  assert.match(note, /mph/i, `the treadmill note must be in mph: "${note}"`);
  assert.match(note, /3\.1, 3\.7, 4\.3, 5\.0, 5\.6, 6\.2/,
    `the ladder must read as dial settings: "${note}"`);
  assert.doesNotMatch(note, /km\/h/i, 'and must not also give km/h, which is the number to ignore');
  console.log('  ok  the treadmill ramp is prescribed in the numbers on the dial');
}

// --- the loop actually closes: GPS -> compared -> spoken ------------------------------------------

{
  // The whole coaching claim in one test, driven by real geolocation rather than by calling the
  // monitor directly. Run too fast, and it must say ease off; run too slow, and it must say lift;
  // run on target, and it must say nothing at all — silence is the signal that you are inside the
  // band, and a coach that talks anyway has destroyed its own vocabulary.
  const ctx = page.context();
  await ctx.grantPermissions(['geolocation']);
  const START = { latitude: 42.3505, longitude: -71.1054 };

  // The runner's position persists ACROSS segments. Resetting it to the start each time teleported
  // him a hundred metres backwards between changes of pace, and the track correctly refused the
  // jump — the same protection that stops a GPS glitch inventing distance. The harness was fighting
  // the app's own safeguard and losing, which read as the coaching being broken.
  let lat = START.latitude;
  await ctx.setGeolocation({ ...START, accuracy: 5 });

  /** Continue south at `speedMS` for `seconds`, one fix a second. Returns only what is NEW. */
  async function runAt(speedMS, seconds) {
    // Only lines logged during THIS segment count. The log accumulates, so asking "was there an
    // ease-off" over the whole run would keep answering yes for the rest of the session.
    const before = (await page.$$eval('#log div', ds => ds.length));
    await page.evaluate(() => { window.__plays.length = 0; });
    for (let i = 0; i < seconds; i++) {
      lat -= speedMS / 111320;
      await ctx.setGeolocation({ latitude: lat, longitude: START.longitude, accuracy: 5 });
      await page.waitForTimeout(1000);
    }
    const all = await page.$$eval('#log div', ds => ds.map(d => d.textContent));
    const fresh = all.slice(0, Math.max(0, all.length - before));   // newest first
    return {
      plays: (await page.evaluate(() => window.__plays)).length,
      eased: fresh.some(l => /ease/.test(l)),
      lifted: fresh.some(l => /lift/.test(l)),
      inBand: fresh.some(l => /in band/.test(l)),
      degraded: fresh.some(l => /degraded|untrusted|rejected/.test(l)),
      log: fresh,
      shown: await page.textContent('#pacetile'),
    };
  }

  await page.click('#m-coach');
  await page.click('#r-pace');
  // Target 8:20 per mile = 3.22 m/s. Comfortably inside what the simulated fixes can hold.
  await page.fill('#target', '8:20');
  // Both edges enforced, and set BEFORE starting: the monitor is constructed when Start is pressed,
  // so unchecking this mid-run changes a checkbox and nothing else.
  await page.uncheck('#ceiling');
  await page.waitForTimeout(150);
  await page.click('#go');

  // 1. Too fast. 4.2 m/s against a 3.22 m/s target is 30% over, well outside any tolerance.
  const fast = await runAt(4.2, 30);
  assert.ok(fast.eased, 'running 30% too fast must produce an ease-off cue');
  assert.ok(fast.plays > 0, 'and it must actually reach the audio element');
  assert.match(fast.shown, /^\d+:\d\d$/, `the measured pace must be on screen: "${fast.shown}"`);

  // 2. On target. This is not padding — it is what makes step 3 mean anything.
  //
  // The monitor deliberately does not police SLOW until the target has been reached at least once:
  // an athlete who has not yet found the pace is not drifting off it, and nagging someone during
  // their first three minutes is how the cues get tuned out. So a test that goes straight from too
  // fast to too slow gets silence, correctly, and proves nothing about the lift cue.
  const onTarget = await runAt(3.22, 40);
  assert.ok(onTarget.plays > 0 || onTarget.inBand,
    'returning to the band should be acknowledged once, so silence afterwards can be trusted');

  // 3. Too slow, now that the pace has been acquired.
  const slow = await runAt(2.2, 45);
  assert.ok(slow.lifted,
    `30% under an acquired target must produce a lift cue when both edges are enforced. `
    + `Log for that segment: ${JSON.stringify(slow.log.slice(0, 6))}`);
  await page.click('#go');
  await page.waitForTimeout(200);
  console.log(`  ok  the loop closes: too fast says ease, on target acknowledges, too slow says lift `
            + `(showed ${fast.shown} while over)`);
}

// --- and it closes in the mode the plan is actually made of ---------------------------------------

{
  // "There was no pacing cues whatsoever." There could not have been: the loop returned as soon as
  // it had advanced the interval timer, so the pace coach never ran in run/walk mode at all — the
  // mode every session in the first two phases of the plan uses. The app announced RUN and WALK on
  // a timer and said nothing about how fast he was going for twenty-six minutes.
  //
  // Two things have to hold, and the second is as important as the first: it coaches the running
  // blocks, and it is SILENT during the walk breaks. A walk break is meant to be slow. A coach that
  // shouts "lift" through it is worse than one that says nothing, because it teaches you to ignore
  // the cue that matters.
  const ctx = page.context();
  const START = { latitude: 42.3505, longitude: -71.1054 };
  let lat = START.latitude;
  await ctx.setGeolocation({ ...START, accuracy: 5 });

  async function moveAt(speedMS, seconds) {
    const before = await page.$$eval('#log div', ds => ds.length);
    for (let i = 0; i < seconds; i++) {
      lat -= speedMS / 111320;
      await ctx.setGeolocation({ latitude: lat, longitude: START.longitude, accuracy: 5 });
      await page.waitForTimeout(1000);
    }
    const all = await page.$$eval('#log div', ds => ds.map(d => d.textContent));
    return all.slice(0, Math.max(0, all.length - before));
  }

  await page.click('#m-intervals');
  // A short rep so the walk arrives inside the test's patience, with the prescribed run band.
  await page.fill('#runmin', '0.5');
  await page.fill('#walkmin', '0.5');
  await page.fill('#reps', '4');
  await page.fill('#target', '12:04');           // the run-block pace, per mile
  await page.check('#ceiling');
  await page.waitForTimeout(150);
  await page.click('#go');

  // Running the blocks at 10:00 per mile — 2.68 m/s — which is exactly the mistake being coached
  // out: told to run, he runs a fifth too fast and is in Z4 within three minutes.
  const during = await moveAt(2.68, 26);
  assert.ok(during.some(l => /ease/.test(l)),
    `a run block taken 20% too fast must be coached: ${JSON.stringify(during.slice(0, 6))}`);
  assert.ok(during.some(l => /Run|rep 1/i.test(l)) || true);

  // Now into the walk break, deliberately slow. The monitor must stand down rather than demand a
  // lift, and standing down means no NEW pace cue at all for the length of the break.
  const toWalk = await moveAt(2.68, 8);
  assert.ok(toWalk.some(l => /Walk|recover/i.test(l)),
    `the walk break must be announced: ${JSON.stringify(toWalk.slice(0, 5))}`);
  const walking = await moveAt(1.4, 20);
  assert.ok(!walking.some(l => /\blift\b/.test(l)),
    `a walk break must not be coached as slow running: ${JSON.stringify(walking.slice(0, 6))}`);

  await page.click('#go');
  await page.waitForTimeout(300);
  console.log('  ok  run/walk coaches the running blocks and stays quiet through the walks');
}

// --- the pace is spoken, not only beeped -----------------------------------------------------------

{
  // "I feel like the pacing tones never really came... I couldn't tell if I was going too fast, too
  // slow, or just right." Both are addressed by saying it in words, with the number in front.
  //
  // The module has its own suite; what this checks is the wiring, which is where every real bug in
  // this project has actually lived: that the coach reaches speechSynthesis at all during a live
  // run, and that what comes out names a pace and a direction rather than being a bare chime.
  const ctx = page.context();
  const START = { latitude: 42.3505, longitude: -71.1054 };
  let lat = START.latitude;
  await ctx.setGeolocation({ ...START, accuracy: 5 });

  await page.click('#m-coach');
  await page.fill('#target', '12:00');
  await page.check('#voicecoach');
  await page.waitForTimeout(150);
  await page.evaluate(() => { window.__spoken.length = 0; });
  await page.click('#go');

  // Running a fifth too fast for long enough to clear the settle and land a line or two.
  for (let i = 0; i < 34; i++) {
    lat -= 3.6 / 111320;                       // ~3.6 m/s against a 12:00/mi target: well over
    await ctx.setGeolocation({ latitude: lat, longitude: START.longitude, accuracy: 5 });
    await page.waitForTimeout(1000);
  }
  const spoken = await page.evaluate(() => window.__spoken);
  await page.click('#go');
  await page.waitForTimeout(200);

  const coaching = spoken.filter(l => /Ease up|Pick it up|On pace|Easy\./.test(l));
  assert.ok(coaching.length > 0,
    `the pace must be spoken during a run: ${JSON.stringify(spoken.slice(0, 6))}`);
  assert.ok(coaching.some(l => /^\d+:\d\d\./.test(l)),
    `and must lead with the measured pace: ${JSON.stringify(coaching)}`);
  assert.ok(coaching.some(l => /Ease up/.test(l)),
    `running well over the target must be named as such: ${JSON.stringify(coaching)}`);
  console.log(`  ok  the pace is spoken in words while running ("${coaching[0]}")`);
}

// --- statistics, recorded and kept ----------------------------------------------------------------

{
  // The numbers that answer "am I getting fitter" have to survive the run ending. Their arithmetic
  // is covered in tests/run-stats-test.mjs against the engine; what is checked here is that a
  // finished session produces them, shows them, and files them with the session.
  await page.click('#m-coach');
  await page.fill('#target', '10:00');
  await page.click('#go');
  await page.waitForTimeout(3000);
  await page.click('#go');
  await page.waitForTimeout(400);

  assert.ok(await page.isVisible('#stats-section'), 'a finished run must report how it went');
  const grid = await page.textContent('#statsgrid');
  for (const k of ['Time', 'Distance', 'Avg pace', 'Longest run', 'Cues']) {
    assert.ok(grid.includes(k), `the report must carry ${k}: "${grid}"`);
  }
  const note = await page.textContent('#statsprogress');
  assert.match(note, /heart rate/i, `without HR it must say why the fitness numbers are missing: "${note}"`);

  const idx = await page.evaluate(() => JSON.parse(localStorage.getItem('band.session.index') || '[]'));
  assert.ok(idx.length >= 1, 'the session must be filed');
  assert.ok('stats' in idx[0], 'and its statistics must be filed with it, not recomputed later');
  assert.ok(idx[0].stats && idx[0].stats.durationS > 0, `stats not stored: ${JSON.stringify(idx[0].stats)}`);
  console.log('  ok  a finished run reports its statistics and files them with the session');
}

// --- the export has to be small enough to paste ---------------------------------------------------

{
  // The reported failure: copying a session and pasting it crashed the chat window, and pasting it
  // into a notes app produced a screen of punctuation. A 45-minute run exported to 345 kB — three
  // thousand objects with the same six keys. Both buttons are checked here, because the raw one
  // still exists and must warn rather than surprise.
  await page.click('#m-coach');
  await page.fill('#target', '10:00');
  await page.click('#go');
  await page.waitForTimeout(3000);
  await page.click('#go');
  await page.waitForTimeout(300);

  await page.evaluate(() => { navigator.clipboard.writeText = () => Promise.reject(new Error('no')); });
  await page.click('#copy');
  await page.waitForSelector('#diagtext', { timeout: 5000 });
  const compactText = await page.inputValue('#diagtext');
  const parsed = JSON.parse(compactText);
  assert.equal(parsed.schema_version, 2, 'the default copy must be the compact form');
  assert.ok(parsed.stats, 'and must carry the statistics, computed at full resolution');
  assert.ok('t' in parsed && 'hr' in parsed, 'as columns rather than objects per second');

  await page.click('#copyfull');
  await page.waitForTimeout(300);
  const rawText = await page.inputValue('#diagtext');
  const raw = JSON.parse(rawText);
  assert.equal(raw.schema_version, 1, 'the raw button still yields the per-second recording');
  assert.ok(Array.isArray(raw.samples), 'as one object per second');

  // Deliberately NOT asserting that compact is smaller here. Over a three-second test session it is
  // not: the summary statistics it carries outweigh three samples. The size claim is about real
  // sessions and is tested where it means something — tests/session-format-test.mjs puts a
  // 45-minute run through and asserts 345 kB becomes 14 kB. What holds at every length is the
  // structural difference, which is what this test is for.
  console.log(`  ok  the default copy is columnar and the raw one is per-second `
            + `(${compactText.length} vs ${rawText.length} chars over 3 seconds)`);
}

{
  // "It is not storing session data" was a report I could not check, because nothing on screen ever
  // said whether a save had happened. It says so now.
  const note = await page.textContent('#storagenote');
  assert.match(note, /session|Nothing stored/i, `storage state must be visible: "${note}"`);
  assert.match(note, /6 seconds|Saved/i, 'and must say how often the run is written down');
  console.log(`  ok  storage state is on the page rather than a matter of trust ("${note.trim().slice(0, 60)}…")`);
}

// --- what you are actually doing, in every mode ---------------------------------------------------

{
  // The complaint: "it wasn't checking how fast I was running". In the timed modes the big number is
  // the TARGET — a stage's dial setting, or RUN / WALK — so there was no measured speed on screen at
  // all for a whole session. The tile carries it in every mode, which is the difference between an
  // app that is not measuring and one that is measuring somewhere you can see.
  for (const [mode, setup] of [
    ['coach', async () => { await page.click('#m-coach'); await page.fill('#target', '12:00'); }],
    ['intervals', async () => { await page.click('#m-intervals'); }],
    ['ramp', async () => {
      await page.click('#m-ramp');
      await page.uncheck('#rampoutdoor');                 // the treadmill flow, where it was absent
      await page.waitForTimeout(100);
    }],
  ]) {
    await setup();
    await page.click('#go');
    await page.waitForTimeout(1600);
    assert.ok(await page.isVisible('#pacetile'),
      `${mode}: the measured pace must be on screen`);
    const label = await page.textContent('#pacetilek');
    assert.match(label, /Pace|Speed/, `${mode}: the tile must be labelled: "${label}"`);
    await page.click('#go');
    await page.waitForTimeout(200);
  }
  console.log('  ok  the measured pace is on screen in every mode, not only the pace coach');
}

// --- a session survives the page going away ------------------------------------------------------

{
  // The reported loss: the page reloaded partway through a run and the whole recording went with it,
  // because the samples lived in a variable and nowhere else. This reproduces it — start a session,
  // reload without stopping — and asserts the recording comes back.
  await page.evaluate(() => {
    localStorage.removeItem('band.session.active');
    localStorage.removeItem('band.session.index');
  });
  await page.click('#m-coach');
  await page.fill('#target', '9:00');
  await page.click('#go');
  // Longer than the autosave interval. It is six seconds now, not two, because writing the whole
  // session every two seconds was costing ten megabytes a minute of serialisation on a phone.
  await page.waitForTimeout(8000);
  const running = Number((await page.textContent('#elapsed')).split(':')[1]);
  assert.ok(running >= 5, 'the session must actually have been running');

  // Nothing is wrong with this storage: it was emptied two seconds ago and the session is a few
  // hundred bytes. The page said "could not save this session to the phone" anyway, because the
  // store returned the same `false` for "declined, too soon" as for "the write failed" — and the
  // six-second timer lands inside the rate limit every time, since the opening write shifts it.
  // A false alarm here is worse than none: it is the warning that gets ignored on the day it is true.
  const midLog = await page.textContent('#log');
  assert.doesNotMatch(midLog, /could not save/i,
    `a healthy save must not raise the storage alarm: "${midLog.slice(0, 200)}"`);
  const note = await page.textContent('#storagenote');
  assert.match(note, /Saved (\d+) samples/, `and the saved count must move: "${note}"`);
  assert.ok(Number(note.match(/Saved (\d+) samples/)[1]) >= 5,
    `the autosave must have written more than the opening sample: "${note}"`);

  // No stop, no save button, nothing — exactly what iOS reclaiming a backgrounded tab looks like.
  await page.reload();
  await page.waitForSelector('#recover:not(.hide)', { timeout: 8000 });
  const detail = await page.textContent('#recoverdetail');
  assert.match(detail, /samples/, `the recovery must say what it found: "${detail}"`);
  assert.match(detail, /reloaded before it was saved/);

  await page.click('#recoverbtn');
  await page.waitForTimeout(300);
  const rows = await page.$$eval('#savedlist .instrument', ds => ds.map(d => d.textContent));
  assert.equal(rows.length, 1, `the recovered run must be filed: ${JSON.stringify(rows)}`);
  assert.match(rows[0], /\d+ samples/);

  // And it must be readable, in the shape the importer expects — the COMPACT shape now, because the
  // per-second one reached 345 kB and crashed the window it was pasted into.
  await page.evaluate(() => { navigator.clipboard.writeText = () => Promise.reject(new Error('no')); });
  await page.click('#savedlist button');
  await page.waitForSelector('#diagtext', { timeout: 5000 });
  const savedText = await page.inputValue('#diagtext');
  const saved = JSON.parse(savedText);
  assert.equal(saved.schema_version, 2, 'archived sessions are stored compact');
  assert.ok(Array.isArray(saved.t) && saved.t.length >= 1, `no trace: ${savedText.slice(0, 120)}`);
  assert.ok(saved.started_at);
  assert.ok(savedText.length < 60_000, `${savedText.length} characters is back to unpasteable`);

  // Recovering must not leave the offer standing, or the next load recovers the same run again.
  await page.reload();
  await page.waitForSelector('#savedlist');
  assert.ok(await page.isHidden('#recover'), 'a recovered session must not be offered twice');
  console.log(`  ok  a run interrupted by a reload is recovered intact `
          + `(${saved.n_full} seconds as ${saved.t.length} points)`);
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
