#!/usr/bin/env python3
"""telegram_control.py -- text "on" / "off" / "status" to your Telegram bot to control live trading.

Long-polls the Telegram getUpdates API and flips LIVE_SWITCH (via live_switch.sh), which the
supervisor / desktop launcher reads to start or stop the bot. Authorized to a SINGLE owner chat:
TELEGRAM_CHAT_ID if set, else trust-on-first-use -- the first chat to message the bot is bound as
owner and saved to ~/.kalshi/env (so settlement + 2-sigma alerts know where to go too).

OPERATOR COMMANDS (/status /pause /resume /help): these are the money-moving levers, so they are
gated independently of the legacy trust-on-first-use "owner" binding above -- they REQUIRE
TELEGRAM_CHAT_ID to be set and matching (both compared as str), and are silently ignored otherwise
(see _strict_authorized). /pause and /resume flip LIVE_SWITCH durably via the GitHub contents API,
replicating (not importing) the GET-sha-then-PUT pattern from kalshi_trader.remote_switch_kill --
this file must stay import-free of the trader. Commands are rate-limited to one per RATE_LIMIT_S
seconds. If TELEGRAM_BOT_TOKEN is unset, main() no-ops immediately -- unchanged from before, so
collect.yml (which backgrounds this script on every collect leg) is never broken by a missing
secret.

Run it alongside the supervisor:  nohup python3 telegram_control.py &   (the launcher does this).
"""
import base64
import glob
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ENVF = os.path.expanduser("~/.kalshi/env")
ASSET = os.environ.get("ASSET", "btc")
RATE_LIMIT_S = 10.0


def _token():
    t = os.environ.get("TELEGRAM_BOT_TOKEN")
    if t:
        return t
    for f in ("~/.kalshi/telegram", "~/.kalshi/env"):
        p = os.path.expanduser(f)
        if os.path.exists(p):
            for ln in open(p):
                if "TELEGRAM_BOT_TOKEN" in ln and "=" in ln:
                    return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def api(tok, method, **params):
    url = f"https://api.telegram.org/bot{tok}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=70))


def send(tok, chat, text):
    try:
        api(tok, "sendMessage", chat_id=chat, text=text)
    except Exception:
        pass


def save_chat_id(cid):
    """Persist the owner chat id to ~/.kalshi/env so notify (alerts/settlements) reaches it."""
    try:
        os.makedirs(os.path.dirname(ENVF), exist_ok=True)
        lines = [l for l in open(ENVF)] if os.path.exists(ENVF) else []
        lines = [l for l in lines if "TELEGRAM_CHAT_ID" not in l]
        lines.append(f"export TELEGRAM_CHAT_ID={cid}\n")
        open(ENVF, "w").writelines(lines)
        os.chmod(ENVF, 0o600)
    except Exception:
        pass


def switch(cmd):
    try:
        subprocess.run(["bash", os.path.join(HERE, "live_switch.sh"), cmd], cwd=HERE, timeout=60)
    except Exception:
        pass
    # also drive the LONGSHOT bot's kill-switch (kalshi_longshot_bot.py honors LONGSHOT_SWITCH=off)
    try:
        open(os.path.join(HERE, "LONGSHOT_SWITCH"), "w").write("off" if cmd == "off" else "on")
    except Exception:
        pass


# --- GitHub Actions fast-path: dispatch a live run on "on", cancel it on "off" (the <1-min levers) ---
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY", "dgkenn/Codex-playground-")
BRANCH = os.environ.get("BRANCH", "claude/polymarket-bot-live-ready-vw7ut5")


def _gh(method, path, body=None):
    """Minimal GitHub API call with the runner token. Returns parsed JSON or None."""
    if not GH_TOKEN:
        return None
    url = f"https://api.github.com/repos/{REPO}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r) if r.status in (200, 201) else {}
    except Exception:
        return None


def dispatch_live():
    """Start a live run NOW (don't wait for the 25-min cron) -> ON within ~1-2 min (GHA cold start)."""
    r = _gh("POST", "actions/workflows/live.yml/dispatches", {"ref": BRANCH})
    return r is not None


def cancel_live():
    """Cancel any in-progress live run NOW -> SIGTERM to the runner -> trader dead-man cancels all
    orders within seconds. Belt-and-suspenders with the trader's own remote-switch self-poll."""
    n = 0
    for st in ("in_progress", "queued"):
        d = _gh("GET", f"actions/workflows/live.yml/runs?status={st}&per_page=10")
        for run in (d or {}).get("workflow_runs", []):
            if _gh("POST", f"actions/runs/{run['id']}/cancel") is not None:
                n += 1
    return n


def cur_switch():
    try:
        return open(os.path.join(HERE, "LIVE_SWITCH")).read().strip()
    except Exception:
        return "off"


# ---------------------------------------------------------------------------
# GitHub contents API: GET-sha-then-PUT, replicated from kalshi_trader.remote_switch_kill (NOT
# imported -- this file must stay dependency-free of the trader). Used by /pause and /resume for a
# direct, stateless flip of LIVE_SWITCH that doesn't depend on this process's local git checkout
# state (unlike switch()/live_switch.sh, which commits+pushes from the local worktree and is what
# the legacy on/off text commands still use, untouched).
# ---------------------------------------------------------------------------

def _gh_contents_get(path="LIVE_SWITCH"):
    """GET a file's sha + base64 content via the GitHub contents API. None on any failure or if
    GH_TOKEN is unset."""
    if not GH_TOKEN:
        return None
    ref = urllib.parse.quote(BRANCH, safe="")
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={ref}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r) if r.status == 200 else None
    except Exception:
        return None


def _gh_contents_put(path, content_bytes, message, sha):
    """PUT new content using the sha from _gh_contents_get. True on 200/201, False otherwise."""
    if not GH_TOKEN:
        return False
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    body = {
        "message": message[:200],
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "sha": sha,
        "branch": BRANCH,
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT", headers={
        "Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 201)
    except Exception:
        return False


def _last_live_switch_commit_message():
    """Message of the most recent commit that touched LIVE_SWITCH on $BRANCH, or None if unknown
    (no GH_TOKEN, or the API call failed) -- callers must treat None as 'can't tell', never as
    'clean', since /resume's refusal check depends on this."""
    if not GH_TOKEN:
        return None
    path = f"commits?path=LIVE_SWITCH&sha={urllib.parse.quote(BRANCH, safe='')}&per_page=1"
    d = _gh("GET", path)
    if not isinstance(d, list) or not d:
        return None
    try:
        return (d[0].get("commit") or {}).get("message") or ""
    except Exception:
        return None


def _live_switch_state():
    """Best-effort current LIVE_SWITCH: contents API (fresh, cross-runner truth) if GH_TOKEN is
    set, else the locally checked-out branch's committed content (git, no network), else the raw
    working-tree file."""
    d = _gh_contents_get("LIVE_SWITCH")
    if d and d.get("content"):
        try:
            val = base64.b64decode(d["content"]).decode().strip()
            if val:
                return val
        except Exception:
            pass
    try:
        out = subprocess.run(["git", "show", "HEAD:LIVE_SWITCH"], cwd=HERE,
                              capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return cur_switch()


def _iso_age_s(iso_ts):
    """Seconds elapsed since a GitHub-style UTC timestamp ("...Z"), or None if unparseable."""
    try:
        dt = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _fmt_age(s):
    if s is None:
        return "n/a"
    s = max(0, int(s))
    if s < 90:
        return f"{s}s"
    m = s // 60
    if m < 90:
        return f"{m}m"
    h = m // 60
    if h < 48:
        return f"{h}h{m % 60}m"
    d = h // 24
    return f"{d}d{h % 24}h"


def _last_live_run_age_s():
    """Age (seconds) of the most recent live.yml run (any status), or None if no GH_TOKEN or no
    runs found."""
    if not GH_TOKEN:
        return None
    d = _gh("GET", "actions/workflows/live.yml/runs?per_page=1")
    runs = (d or {}).get("workflow_runs") or []
    if not runs:
        return None
    ts = runs[0].get("created_at")
    return _iso_age_s(ts) if ts else None


def _latest_equity_balance():
    """Dollar balance from the last row of the newest gha_data/equity_*.jsonl, or None if no such
    file is reachable locally (e.g. a fresh GHA checkout that just wiped gha_data/)."""
    paths = sorted(glob.glob(os.path.join(HERE, "gha_data", "equity_*.jsonl")))
    if not paths:
        return None
    try:
        last = None
        with open(paths[-1]) as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    last = ln
        if not last:
            return None
        cents = json.loads(last).get("balance_cents")
        return None if cents is None else int(cents) / 100.0
    except Exception:
        return None


def _collection_freshness_s():
    """Age (seconds) of the newest file anywhere under gha_data/, or None if unreachable/empty."""
    base = os.path.join(HERE, "gha_data")
    newest = None
    try:
        for root, _dirs, files in os.walk(base):
            for f in files:
                try:
                    mt = os.path.getmtime(os.path.join(root, f))
                except Exception:
                    continue
                if newest is None or mt > newest:
                    newest = mt
    except Exception:
        return None
    return None if newest is None else time.time() - newest


def _format_status():
    """Operator status reply. Each item is independently try/except'd so one unreachable source
    (no GH_TOKEN, no gha_data yet, ...) never blanks the whole reply -- degrade gracefully."""
    lines = []
    try:
        sw = _live_switch_state()
        killed = os.path.exists(os.path.join(HERE, f".kalshi_killed_{ASSET}15m"))
        lines.append(f"LIVE_SWITCH: {sw}" + ("  (kill sentinel present)" if killed else ""))
    except Exception as e:
        lines.append(f"LIVE_SWITCH: error ({type(e).__name__})")
    try:
        bal = _latest_equity_balance()
        lines.append(f"equity: ${bal:,.2f}" if bal is not None else "equity: n/a")
    except Exception as e:
        lines.append(f"equity: error ({type(e).__name__})")
    try:
        age = _last_live_run_age_s()
        if age is not None:
            lines.append(f"last live run: {_fmt_age(age)} ago")
        else:
            lines.append("last live run: n/a" + ("" if GH_TOKEN else " (no GH_TOKEN)"))
    except Exception as e:
        lines.append(f"last live run: error ({type(e).__name__})")
    try:
        fresh = _collection_freshness_s()
        lines.append(f"collection: {_fmt_age(fresh)} old" if fresh is not None else "collection: n/a")
    except Exception as e:
        lines.append(f"collection: error ({type(e).__name__})")
    return "\n".join(lines)


def _strict_authorized(chat):
    """Independent of the legacy trust-on-first-use 'owner' binding above: the operator commands
    (/status /pause /resume /help) require TELEGRAM_CHAT_ID to be explicitly configured and to
    match this chat, both compared as str. No env or a mismatch -> False; callers must ignore
    silently (no reply) per the security requirement -- these are the money-moving levers."""
    want = os.environ.get("TELEGRAM_CHAT_ID")
    return bool(want) and str(chat) == str(want)


def _cmd_pause(tok, chat):
    d = _gh_contents_get("LIVE_SWITCH")
    if not d or not d.get("sha"):
        send(tok, chat, "pause FAILED: couldn't read LIVE_SWITCH via the GitHub contents API "
                         "(no GH_TOKEN, or the GET failed). LIVE_SWITCH is UNCHANGED -- "
                         "use ./live_switch.sh off on the host if this is urgent.")
        return
    if _gh_contents_put("LIVE_SWITCH", b"off", "telegram: /pause (operator off)", d["sha"]):
        send(tok, chat, "\U0001f6d1 paused -- LIVE_SWITCH -> off (durable commit confirmed).\n"
                         "Resume with /resume when ready.")
    else:
        send(tok, chat, "pause FAILED: the PUT to the contents API did not succeed. "
                         "LIVE_SWITCH may still be ON -- verify manually (./live_switch.sh off).")


def _cmd_resume(tok, chat):
    """Flip LIVE_SWITCH=on, UNLESS the last commit that touched it looks like an automated kill
    (loss-limit / guardian sentinel trip), in which case refuse and point at live_switch.sh, which
    clears the kill sentinel(s) properly (a raw contents-API flip here would not)."""
    msg = _last_live_switch_commit_message()
    if msg:
        norm = msg.lower().replace("_", "-")   # kill messages use loss_limit / toxic_markout
        if "loss-limit" in norm or "guardian" in norm:
            send(tok, chat,
                 "resume REFUSED: the last LIVE_SWITCH change looks like an automated kill "
                 f"(commit: {msg[:180]!r}). Use ./live_switch.sh on on the host/runner -- it "
                 "clears the kill sentinel(s) properly. Flipping the switch here would NOT clear "
                 "those sentinels, and the bot may re-kill itself immediately or leave the "
                 "underlying loss condition unaddressed.")
            return
    d = _gh_contents_get("LIVE_SWITCH")
    if not d or not d.get("sha"):
        send(tok, chat, "resume FAILED: couldn't read LIVE_SWITCH via the GitHub contents API "
                         "(no GH_TOKEN, or the GET failed). LIVE_SWITCH is UNCHANGED -- "
                         "use ./live_switch.sh on on the host if this is urgent.")
        return
    if _gh_contents_put("LIVE_SWITCH", b"on", "telegram: /resume (operator on)", d["sha"]):
        send(tok, chat, "✅ resumed -- LIVE_SWITCH -> on (durable commit confirmed).\n"
                         "Note: this does NOT clear local kill sentinels on any runner/VM -- if "
                         "trading doesn't restart, run ./live_switch.sh on there too.")
    else:
        send(tok, chat, "resume FAILED: the PUT to the contents API did not succeed. "
                         "Verify manually (./live_switch.sh on).")


HELP_TEXT = (
    "commands:\n"
    "  on | off | status   -- legacy switch text triggers\n"
    "  /status  -- LIVE_SWITCH state, equity, last live run age, collection freshness\n"
    "  /pause   -- LIVE_SWITCH -> off (durable, GitHub contents API)\n"
    "  /resume  -- LIVE_SWITCH -> on; refuses if the last kill looks automated "
    "(loss-limit/guardian) -- use ./live_switch.sh on on the host in that case\n"
    "  /help    -- this message"
)


def handle_message(tok, owner, chat, text, last_cmd_ts, now=None):
    """Process one incoming Telegram message. Returns (owner, last_cmd_ts), possibly updated.
    Factored out of main()'s poll loop so it's unit-testable without getUpdates."""
    now = now if now is not None else time.time()
    if owner is None:                       # trust-on-first-use: bind the first messager
        owner = chat
        save_chat_id(chat)
        send(tok, chat, "Bound. You are the owner of this bot.\n"
                        "Text:  on  /  off  /  status   (or /help for the full list)")
    if chat != str(owner):
        send(tok, chat, "not authorized")
        return owner, last_cmd_ts
    if text in ("on", "/on", "start"):
        switch("on")                              # flip the durable switch (source of truth)
        started = dispatch_live()                 # ...AND start a run now (don't wait for cron)
        if started:
            eta = ("✅ live bot ON ({a})\n"
                   "\U0001f7e2 run dispatched -- ETA to first quote ~60-90s "
                   "(GitHub spins up a runner + installs deps). I'll send a "
                   "'\U0001f7e2 live session armed' ping the moment it's actually trading; "
                   "if preflight gates it you'll get a \U0001f7e1 instead.").format(a=ASSET)
        else:
            eta = ("✅ live bot ON ({a})\n"
                   "switch set, but I couldn't dispatch a run right now -- it auto-starts "
                   "on the next scheduler tick, ETA ≤25 min. You'll get a \U0001f7e2 ping when "
                   "it's trading.").format(a=ASSET)
        send(tok, chat, eta)
    elif text in ("off", "/off", "stop"):
        switch("off")                             # flip switch off (blocks restart)
        n = cancel_live()                         # ...AND kill the running run now (<1 min)
        send(tok, chat, "\U0001f6d1 live bot OFF" +
             (f"\n\U0001f534 ETA to flat: ~10-30s (cancelling {n} running cycle(s); orders flatten "
              f"on the runner's stop signal)" if n
              else "\n\U0001f534 ETA to flat: ≤20s -- no GHA run active, but any running trader "
                   "self-stops on its next switch poll (every 20s)."))
    elif text in ("status", "/status"):
        if _strict_authorized(chat):
            if now - last_cmd_ts >= RATE_LIMIT_S:
                last_cmd_ts = now
                send(tok, chat, _format_status())
            # else: rate-limited, drop silently
        else:
            killed = os.path.exists(os.path.join(HERE, f".kalshi_killed_{ASSET}15m"))
            send(tok, chat, f"switch: {cur_switch()}" + ("  (kill sentinel set)" if killed else ""))
    elif text == "/pause":
        if _strict_authorized(chat) and now - last_cmd_ts >= RATE_LIMIT_S:
            last_cmd_ts = now
            _cmd_pause(tok, chat)
        # else: unauthorized (no TELEGRAM_CHAT_ID configured / mismatch) or rate-limited -> ignore
        # silently. This is a money-moving lever; never a hint of a reply to the wrong chat.
    elif text == "/resume":
        if _strict_authorized(chat) and now - last_cmd_ts >= RATE_LIMIT_S:
            last_cmd_ts = now
            _cmd_resume(tok, chat)
        # else: ignore silently, same rationale as /pause.
    elif text == "/help":
        if _strict_authorized(chat):
            if now - last_cmd_ts >= RATE_LIMIT_S:
                last_cmd_ts = now
                send(tok, chat, HELP_TEXT)
        else:
            send(tok, chat, "commands:  on  |  off  |  status")
    else:
        send(tok, chat, "commands:  on  |  off  |  status")
    return owner, last_cmd_ts


def main():
    tok = _token()
    if not tok:
        print("telegram_control: no TELEGRAM_BOT_TOKEN -- set it in ~/.kalshi/env"); return
    owner = os.environ.get("TELEGRAM_CHAT_ID") or None
    offset = None
    last_cmd_ts = 0.0
    print(f"telegram_control: polling (owner={'set' if owner else 'trust-on-first-use'})")
    while True:
        try:
            params = {"timeout": 60}
            if offset:
                params["offset"] = offset
            d = api(tok, "getUpdates", **params)
        except Exception:
            time.sleep(5); continue
        for u in d.get("result", []):
            offset = u["update_id"] + 1
            m = u.get("message") or u.get("edited_message") or {}
            chat = str((m.get("chat") or {}).get("id") or "")
            text = (m.get("text") or "").strip().lower()
            if not chat:
                continue
            owner, last_cmd_ts = handle_message(tok, owner, chat, text, last_cmd_ts)


if __name__ == "__main__":
    main()
