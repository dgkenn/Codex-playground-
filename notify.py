"""Free Telegram alerts (no-op if env not set). Never raises into the trading loop.

LATENCY: alert() is fire-and-forget -- the HTTP POST runs on a daemon thread so a slow/unreachable
Telegram API (timeout 8s) can never stall the trading loop (the TAKER-fill alarm, for example, fires
on the housekeeping path while orders rest). Use alert_sync() only where blocking is acceptable and
the delivery outcome matters (CLI test)."""
import os
import threading

import requests


def alert_sync(msg: str) -> bool:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN"); chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": msg[:4000]}, timeout=8)
        return True
    except Exception:
        return False


def alert(msg: str) -> bool:
    """Queue the alert on a daemon thread and return immediately (False only if env unset)."""
    if not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        return False
    threading.Thread(target=alert_sync, args=(msg,), daemon=True).start()
    return True


if __name__ == "__main__":
    print("alert sent" if alert_sync("pmkit notify test") else "TELEGRAM_* not set (no-op)")
