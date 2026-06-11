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
                switch("on"); send(tok, chat, f"✅ live bot ON ({ASSET})")
            elif text in ("off", "/off", "stop"):
                switch("off"); send(tok, chat, "\U0001f6d1 live bot OFF")
            elif text in ("status", "/status"):
                killed = os.path.exists(os.path.join(HERE, f".kalshi_killed_{ASSET}15m"))
                send(tok, chat, f"switch: {cur_switch()}" + ("  (kill sentinel set)" if killed else ""))
            else:
                send(tok, chat, "commands:  on  |  off  |  status")


if __name__ == "__main__":
    main()
