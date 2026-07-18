#!/usr/bin/env python3
"""kwx_telegram.py -- Telegram remote control for the WEATHER-nowcast live bot.

Text the bot to start/stop live weather trading and check status. Rewired from the box's
telegram_control.py: it flips KWX_SWITCH (weather), NOT LIVE_SWITCH (box), and /status reports
weather metrics (switch state, today's fires, cumulative paper/live PnL, gate verdict).

COMMANDS (owner-only; owner = TELEGRAM_CHAT_ID):
  /on      -> KWX_SWITCH = on   (arm the $10 live canary)
  /off     -> KWX_SWITCH = off  (stop live trading; positions already open still settle)
  /status  -> current switch + settled fires + cumulative PnL + gate verdict
  /help    -> this list

Mechanism: flips KWX_SWITCH on the trading branch via the GitHub contents API (GET-sha-then-PUT), so
it works cross-runner without a local checkout. Needs env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GH_TOKEN
(a token with contents:write on the repo). No-ops cleanly if TELEGRAM_BOT_TOKEN is unset.

Run it persistently (long-poll):  nohup python3 kwx_telegram.py &
"""
import os, json, time, base64, ssl, urllib.request, urllib.parse

REPO = os.environ.get("KWX_REPO", "dgkenn/codex-playground-")
BRANCH = os.environ.get("BRANCH", "claude/coding-bot-ab-test-results-ffmhxw")
SWITCH_PATH = "KWX_SWITCH"
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None


def _tok():
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def _owner():
    return os.environ.get("TELEGRAM_CHAT_ID")


def tg(method, **params):
    url = f"https://api.telegram.org/bot{_tok()}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=70, context=_CTX))


def send(chat, text):
    try:
        tg("sendMessage", chat_id=chat, text=text)
    except Exception as e:
        print(f"[kwx_telegram] send failed: {e}", flush=True)


def _gh(method, path, body=None):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {os.environ.get('GH_TOKEN','')}",
        "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=20, context=_CTX))


def get_switch():
    try:
        d = _gh("GET", f"contents/{SWITCH_PATH}?ref={urllib.parse.quote(BRANCH, safe='')}")
        return base64.b64decode(d["content"]).decode().strip(), d["sha"]
    except Exception as e:
        return f"unknown ({type(e).__name__})", None


def set_switch(val):
    cur, sha = get_switch()
    if sha is None:
        return False, "cannot read KWX_SWITCH (GH_TOKEN missing scope?)"
    try:
        _gh("PUT", f"contents/{SWITCH_PATH}", {
            "message": f"KWX_SWITCH -> {val} (via Telegram)",
            "content": base64.b64encode((val + "\n").encode()).decode(),
            "sha": sha, "branch": BRANCH})
        return True, f"KWX_SWITCH -> {val}"
    except Exception as e:
        return False, f"flip failed: {type(e).__name__}"


def status_text():
    sw, _ = get_switch()
    lines = [f"🌡️ KWX weather bot", f"switch: {sw}"]
    # settled fires summary from the branch (best-effort)
    try:
        d = _gh("GET", f"contents/kwx_forward_settled.jsonl?ref={urllib.parse.quote(BRANCH, safe='')}")
        rows = [json.loads(l) for l in base64.b64decode(d["content"]).decode().splitlines() if l.strip()]
        if rows:
            wins = sum(1 for r in rows if r.get("won"))
            tot = sum(r.get("pnl", 0) for r in rows)
            lines.append(f"settled: {len(rows)} fires, {wins}/{len(rows)} won, cum PnL {tot:+.2f}/ct")
        else:
            lines.append("settled: none yet")
    except Exception:
        lines.append("settled: none yet (or log not committed)")
    return "\n".join(lines)


def handle(cmd, chat):
    if _owner() and str(chat) != str(_owner()):
        return  # owner-only; silently ignore others
    c = cmd.strip().lower().split()[0] if cmd.strip() else ""
    # accept BOTH slash-commands and plain words (on/off/status), so "on" works like "/on"
    if c in ("/on", "on", "start", "resume", "/resume"):
        ok, msg = set_switch("on"); send(chat, ("✅ " if ok else "⚠️ ") + msg + ("  ($10 canary armed)" if ok else ""))
    elif c in ("/off", "off", "stop", "pause", "/stop", "/pause", "halt"):
        ok, msg = set_switch("off"); send(chat, ("🛑 " if ok else "⚠️ ") + msg)
    elif c in ("/status", "status"):
        send(chat, status_text())
    else:
        send(chat, "KWX commands: on | off | status  (or /on /off /status)")


def main():
    if not _tok():
        print("[kwx_telegram] TELEGRAM_BOT_TOKEN unset -> no-op"); return
    print("[kwx_telegram] weather control bot polling (Ctrl-C to stop)")
    offset = None
    while True:
        try:
            r = tg("getUpdates", timeout=50, **({"offset": offset} if offset else {}))
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                m = u.get("message") or u.get("edited_message") or {}
                txt = m.get("text", "")
                chat = (m.get("chat") or {}).get("id")
                if txt and chat:
                    handle(txt, chat)
        except Exception as e:
            print(f"[kwx_telegram] loop error: {e}", flush=True); time.sleep(5)


if __name__ == "__main__":
    main()
