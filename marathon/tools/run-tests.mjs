// Every test in the project, one command, one honest exit code.
//
//   node run-tests.mjs            build, then every module suite (in parallel)
//   node run-tests.mjs --page     ...and the browser suite (about ten minutes)
//   node run-tests.mjs --py       ...and the Python engine's tests
//   node run-tests.mjs --all      all of it
//
// Why this exists: the suites were being run by hand, one by one, with `; echo exit $?` tacked on
// -- and twice a browser-suite failure read as a pass because the echo's exit code was the one
// reported. A failure here is a non-zero exit and a list of what failed, every time.

import { spawn } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { cpus } from 'node:os';

const here = dirname(fileURLToPath(import.meta.url));
const args = new Set(process.argv.slice(2));
const all = args.has('--all');

function run(cmd, argv, { cwd = here, quiet = true } = {}) {
  return new Promise(resolve => {
    const t0 = Date.now();
    const p = spawn(cmd, argv, { cwd, stdio: quiet ? ['ignore', 'pipe', 'pipe'] : 'inherit' });
    let out = '';
    if (quiet) { p.stdout.on('data', d => { out += d; }); p.stderr.on('data', d => { out += d; }); }
    p.on('close', code => resolve({ code, out, ms: Date.now() - t0 }));
    p.on('error', e => resolve({ code: 127, out: String(e), ms: Date.now() - t0 }));
  });
}

const failed = [];
let ran = 0;
const step = async (name, promise) => {
  const r = await promise;
  ran += 1;
  const ok = r.code === 0;
  console.log(`${ok ? '  ok ' : ' FAIL'}  ${name} (${(r.ms / 1000).toFixed(1)} s)`);
  if (!ok) { failed.push(name); console.log(r.out.split('\n').slice(-25).map(l => `        ${l}`).join('\n')); }
};

await step('build (parse, undeclared names, boot)', run('node', ['build-coach.mjs']));

const suites = readdirSync(join(here, 'tests'))
  .filter(f => /(-test|-parity|-sim)\.mjs$/.test(f) && f !== 'page-test.mjs')
  .sort();
const limit = Math.max(2, Math.min(8, cpus().length));
const queue = [...suites];
await Promise.all(Array.from({ length: limit }, async () => {
  while (queue.length) {
    const f = queue.shift();
    await step(f, run('node', [join('tests', f)]));
  }
}));

if (all || args.has('--py')) {
  await step('engine (pytest)', run('python3', ['-m', 'pytest', '-q'], { cwd: join(here, '..', 'engine') }));
}
if (all || args.has('--page')) {
  await step('page-test.mjs (browser)', run('node', [join('tests', 'page-test.mjs')]));
}

console.log(failed.length ? `\n${failed.length} of ${ran} failed: ${failed.join(', ')}` : `\nAll ${ran} passed.`);
process.exit(failed.length ? 1 : 0);
