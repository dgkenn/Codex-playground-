// The remote bench against a stand-in relay: commands in, replies out, chunked and reassembled,
// unknown commands refused, the bench switching itself off.

import assert from 'node:assert/strict';
import { RemoteBench, benchTopic, chunkReply, joinReplies } from '../remote-bench.js';

{
  assert.equal(benchTopic('#bench=abcdefghijklmnopqrstu'), 'abcdefghijklmnopqrstu');
  assert.equal(benchTopic('#x=1&bench=abcdefghijklmnopqrstu&y=2'), 'abcdefghijklmnopqrstu');
  assert.equal(benchTopic('#bench=short'), null, 'a short topic is not a key');
  assert.equal(benchTopic('#bench=bad/../topic-with-slashes!'), null);
  assert.equal(benchTopic(''), null);
  const big = { beats: Array.from({ length: 2000 }, (_, i) => i) };
  const parts = chunkReply('c1', big, 500);
  assert.ok(parts.length > 10);
  assert.deepEqual(joinReplies([...parts].reverse()).c1, big, 'reassembled in any order');
  assert.equal(joinReplies(parts.slice(1)).c1, undefined, 'not until every part is there');
  console.log(`  ok  topics are validated; a large reply is split into ${parts.length} parts and put back together`);
}

/** A relay: commands queued for the page, everything the page published collected. */
function fakeRelay() {
  const cmds = [], published = [];
  let n = 0;
  const fetchFn = async (url, opts = {}) => {
    if (opts.method === 'POST') { published.push(JSON.parse(opts.body)); return { text: async () => '' }; }
    const since = decodeURIComponent(/since=([^&]+)/.exec(url)[1]);
    const idx = since === 'now' ? 0 : cmds.findIndex(c => c.id === since) + 1;
    const fresh = cmds.slice(idx);
    if (!fresh.length) await new Promise(r => setTimeout(r, 20));
    return { text: async () => fresh.map(c => JSON.stringify({ event: 'message', id: c.id, message: JSON.stringify(c.body) })).join('\n') };
  };
  return { fetchFn, published, push: body => cmds.push({ id: `m${++n}`, body }) };
}

{
  const relay = fakeRelay();
  const states = [];
  const bench = new RemoteBench({
    topic: 'abcdefghijklmnopqrstu', fetchFn: relay.fetchFn, onStatus: s => states.push(s), pollWaitS: 0, idleMs: 10,
    handlers: { ping: async () => ({ pong: true }), boom: async () => { throw new Error('band said no'); } },
  });
  await bench.start();
  relay.push({ id: 'a', cmd: 'ping' });
  relay.push({ id: 'b', cmd: 'boom' });
  relay.push({ id: 'c', cmd: 'eval', args: { code: 'alert(1)' } });
  await new Promise(r => setTimeout(r, 200));
  const replies = joinReplies(relay.published);
  assert.equal(replies.hello.result.ready, true, 'the page says it is listening');
  assert.deepEqual(replies.a.result, { pong: true });
  assert.equal(replies.b.ok, false);
  assert.match(replies.b.error, /band said no/);
  assert.equal(replies.c.ok, false, 'no command outside the list');
  assert.match(replies.c.error, /unknown command "eval"/);
  // Each command once, however many times the relay hands it back.
  assert.equal(relay.published.filter(p => p.id === 'a').length, 1);
  bench.stop();
  assert.deepEqual(states, ['on', 'stopped']);
  console.log('  ok  commands run once each and answer; errors are reported; anything off the list is refused');
}

{
  // Half an hour and it switches itself off.
  const relay = fakeRelay();
  let t = 0;
  const states = [];
  const bench = new RemoteBench({ topic: 'abcdefghijklmnopqrstu', fetchFn: relay.fetchFn, handlers: {},
                                  now: () => t, onStatus: s => states.push(s), pollWaitS: 0, idleMs: 10 });
  await bench.start();
  t = 31 * 60000;
  await new Promise(r => setTimeout(r, 100));
  assert.equal(bench.on, false);
  assert.ok(states.includes('expired'));
  console.log('  ok  the bench switches itself off after half an hour');
}

console.log('\nAll remote-bench tests passed.');
