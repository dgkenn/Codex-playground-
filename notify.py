"""Free Telegram alerts (no-op if env not set). Never raises into the trading loop."""
import os, requests
def alert(msg: str):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN"); chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": msg[:4000]}, timeout=8)
        return True
    except Exception:
        return False
if __name__ == "__main__":
    print("alert sent" if alert("pmkit notify test") else "TELEGRAM_* not set (no-op)")
