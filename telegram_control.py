#!/usr/bin/env python3
"""telegram_control.py -- text "on" / "off" / "status" to your Telegram bot to control live trading.

Long-polls the Telegram getUpdates API and flips LIVE_SWITCH (via live_switch.sh), which the
supervisor / desktop launcher reads to start or stop the bot. Authorized to a SINGLE owner chat:
TELEGRAM_CHAT_ID if set, else trust-on-first-use -- the first chat to message the bot is bound as
owner and saved to ~/.kalshi/env (so settlement + 2-sigma alerts know where to go too).

Run it alongside the supervisor:  nohup python3 telegram_control.py &   (the launcher does this).
"""
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENVF = os.path.expanduser("~/.kalshi/env")
ASSET = os.environ.get("ASSET", "btc")


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


def main():
    tok = _token()
    if not tok:
        print("telegram_control: no TELEGRAM_BOT_TOKEN -- set it in ~/.kalshi/env"); return
    owner = os.environ.get("TELEGRAM_CHAT_ID") or None
    offset = None
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
            if owner is None:                       # trust-on-first-use: bind the first messager
                owner = chat; save_chat_id(chat)
                send(tok, chat, "Bound. You are the owner of this bot.\n"
                                "Text:  on  /  off  /  status")
            if chat != str(owner):
                send(tok, chat, "not authorized"); continue
            if text in ("on", "/on", "start"):
                switch("on")                              # flip the durable switch (source of truth)
                started = dispatch_live()                 # ...AND start a run now (don't wait for cron)
                send(tok, chat, f"✅ live bot ON ({ASSET})" +
                     ("\n🟢 starting a live run now (~1-2 min to first quote)" if started
                      else "\n(switch set; next cron/watchdog will start it)"))
            elif text in ("off", "/off", "stop"):
                switch("off")                             # flip switch off (blocks restart)
                n = cancel_live()                         # ...AND kill the running run now (<1 min)
                send(tok, chat, "\U0001f6d1 live bot OFF" +
                     (f"\n🔴 cancelling {n} running cycle(s); orders flatten within seconds" if n
                      else "\n(no active run; a running trader will also self-stop within ~20s)"))
            elif text in ("status", "/status"):
                killed = os.path.exists(os.path.join(HERE, f".kalshi_killed_{ASSET}15m"))
                send(tok, chat, f"switch: {cur_switch()}" + ("  (kill sentinel set)" if killed else ""))
            else:
                send(tok, chat, "commands:  on  |  off  |  status")


if __name__ == "__main__":
    main()
