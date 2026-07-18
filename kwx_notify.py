#!/usr/bin/env python3
"""kwx_notify.py -- free Telegram alerts for the WEATHER-nowcast bot. No-op if env not set; never raises
into the trading loop (fire-and-forget on a daemon thread). Reuses the box's TELEGRAM_BOT_TOKEN +
TELEGRAM_CHAT_ID secrets, but every message is WEATHER-relevant (fires, settlements, PnL, halts) -- the
box's BTC/box alerts are gone.

Alerts the weather bot emits (see wiring in kwx_runner / kwx_forward):
  FIRE      🌡️  bought a just-locked ladder rung
  SETTLE    ✅/❌ a paper/live fire resolved (win/loss + running day PnL)
  HALT      🛑  circuit breaker / kill switch tripped
  DAILY     📊  end-of-day summary (n, win%, PnL, gate verdict)
"""
import os, json, threading, ssl, urllib.request

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None


def _creds():
    return os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")


def alert_sync(msg: str) -> bool:
    tok, chat = _creds()
    if not tok or not chat:
        return False
    try:
        data = json.dumps({"chat_id": chat, "text": msg[:4000]}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                     data=data, headers={"Content-Type": "application/json"})
        r = urllib.request.urlopen(req, timeout=8, context=_CTX)
        return getattr(r, "status", 200) == 200
    except Exception as e:
        print(f"[kwx_notify] telegram send failed: {type(e).__name__}: {e}", flush=True)
        return False


def alert(msg: str) -> bool:
    """Queue on a daemon thread and return immediately (False only if env unset)."""
    tok, chat = _creds()
    if not (tok and chat):
        return False
    threading.Thread(target=alert_sync, args=(msg,), daemon=True).start()
    return True


if __name__ == "__main__":
    print("sent" if alert_sync("🌡️ kwx_notify test — weather bot alerts online")
          else "TELEGRAM_* not set (no-op)")
