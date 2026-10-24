// The remote bench: tests on the real armband, driven from somewhere else, through the phone.
//
// Why this exists
// ---------------
// The band talks to one thing, the phone, over Bluetooth; the person writing the code works from a
// machine with no radio anywhere near it. Everything the app asks of the band beyond heart rate
// (the motion stream, the band's own memory, the file service, beat-to-beat intervals) was written
// against Polar's SDK and its test vectors. The phone already holds the connection, so it can be the
// bench: a command arrives, the page runs it on the band, the result goes back.
//
// The channel is ntfy.sh, a plain publish/subscribe relay over HTTPS with CORS: the page listens on
// `<topic>-cmd` and answers on `<topic>-out`. The topic is a long random name in the link that turns
// the bench on, and it is the only key -- so it is treated as one: never shown in full, never
// stored, and the bench is off unless the athlete taps Allow on the banner. What goes through the
// relay is test results (heart rate, battery, timings), not location, and ntfy.sh keeps messages
// for hours, not forever.
//
// Commands are a fixed list (see the page's handlers). There is no "run this code": anyone who
// learned the topic could only ask the band what the app already shows. Nothing that deletes
// recordings or enters Polar's SDK mode is on the list. It switches itself off after half an hour.

export const RELAY = 'https://ntfy.sh';
/// Under ntfy's 4096-byte message limit, with room for the envelope.
export const CHUNK = 3500;
export const BENCH_MINUTES = 30;

/** The topic in a `#bench=<topic>` link, or null. At least 20 characters of [A-Za-z0-9_-]. */
export function benchTopic(hash) {
  const m = /(?:^#|&)bench=([A-Za-z0-9_-]{20,64})(?:&|$)/.exec(hash || '');
  return m ? m[1] : null;
}

/** A reply split to fit the relay: `[{id, part, of, data}]`, `data` slices of the JSON text. */
export function chunkReply(id, obj, size = CHUNK) {
  const text = JSON.stringify(obj);
  const of = Math.max(1, Math.ceil(text.length / size));
  return Array.from({ length: of }, (_, i) => ({ id, part: i + 1, of, data: text.slice(i * size, (i + 1) * size) }));
}

/** Put chunked replies back together: `{[id]: object}` for every id with all its parts. */
export function joinReplies(parts) {
  const by = new Map();
  for (const p of parts) {
    if (!p || p.id == null) continue;
    if (!by.has(p.id)) by.set(p.id, []);
    by.get(p.id).push(p);
  }
  const out = {};
  for (const [id, ps] of by) {
    const of = ps[0].of;
    const seen = new Map(ps.map(p => [p.part, p.data]));
    if (seen.size < of) continue;
    try { out[id] = JSON.parse(Array.from({ length: of }, (_, i) => seen.get(i + 1)).join('')); } catch { /* corrupt */ }
  }
  return out;
}

/**
 * The page's end. `handlers` is `{name: async (args) => result}`; `fetchFn` is fetch. Listens by
 * polling every `idleMs` (6 s): inside the relay's per-visitor request limit, and nothing a phone
 * browser lacks (a streamed response body is not something to rely on in a Bluetooth bridge).
 */
export class RemoteBench {
  constructor({ topic, handlers, fetchFn = (...a) => fetch(...a), onStatus = () => {}, onCommand = () => {},
                minutes = BENCH_MINUTES, now = () => Date.now(), pollWaitS = 0, idleMs = 6000 }) {
    Object.assign(this, { topic, handlers, fetchFn, onStatus, onCommand, minutes, now, pollWaitS, idleMs });
    this.on = false;
    this.since = null;
    this.handled = new Set();
    this.busy = Promise.resolve();
  }

  async start() {
    if (this.on) return;
    this.on = true;
    this.until = this.now() + this.minutes * 60000;
    // Everything from the moment it started, by timestamp, until the first message gives an id:
    // `since=now` would drop a command published between two polls.
    this.since = String(Math.floor(this.now() / 1000));
    this.onStatus('on');
    await this.send({ id: 'hello', ok: true, result: { ready: true, commands: Object.keys(this.handlers) } });
    this._loop();
  }

  stop(why = 'stopped') {
    if (!this.on) return;
    this.on = false;
    if (this._abort) try { this._abort.abort(); } catch { /* gone */ }
    this.onStatus(why);
  }

  async send(reply) {
    for (const part of chunkReply(reply.id, reply)) {
      await this.fetchFn(`${RELAY}/${this.topic}-out`, { method: 'POST', body: JSON.stringify(part) });
    }
  }

  async _loop() {
    while (this.on) {
      if (this.now() > this.until) { this.stop('expired'); break; }
      try {
        this._abort = typeof globalThis.AbortController === 'function' ? new globalThis.AbortController() : null;
        // no-store: the same poll URL repeats until a message moves `since`, and a cached empty
        // answer would hide every command after it.
        const r = await this.fetchFn(`${RELAY}/${this.topic}-cmd/json?poll=1&since=${encodeURIComponent(this.since)}`,
                                     { cache: 'no-store', ...(this._abort ? { signal: this._abort.signal } : {}) });
        const text = await r.text();
        for (const line of text.split('\n')) {
          if (!line.trim()) continue;
          let ev; try { ev = JSON.parse(line); } catch { continue; }
          if (ev.event !== 'message' || !ev.id) continue;
          this.since = ev.id;
          if (this.handled.has(ev.id)) continue;
          this.handled.add(ev.id);
          let cmd; try { cmd = JSON.parse(ev.message); } catch { continue; }
          this.busy = this.busy.then(() => this._run(cmd));
        }
        await new Promise(res => setTimeout(res, this.idleMs));
      } catch {
        if (!this.on) break;
        await new Promise(res => setTimeout(res, 5000));
      }
    }
  }

  async _run(cmd) {
    if (!this.on || !cmd || typeof cmd.cmd !== 'string') return;
    const id = cmd.id || String(this.now());
    const h = Object.prototype.hasOwnProperty.call(this.handlers, cmd.cmd) ? this.handlers[cmd.cmd] : null;
    this.onCommand(cmd.cmd);
    const t0 = this.now();
    let reply;
    if (!h) reply = { id, ok: false, error: `unknown command "${cmd.cmd}"`, commands: Object.keys(this.handlers) };
    else {
      try { reply = { id, ok: true, cmd: cmd.cmd, ms: 0, result: await h(cmd.args || {}) }; }
      catch (e) { reply = { id, ok: false, cmd: cmd.cmd, error: e && e.message ? e.message : String(e) }; }
    }
    reply.ms = this.now() - t0;
    try { await this.send(reply); } catch { /* the relay will be retried by the next command */ }
  }
}
