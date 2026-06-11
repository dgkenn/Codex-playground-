# Desktop on/off switch for the Kalshi bot

A literal double-click launcher. **Open it = bot trades. Close the window = bot stops**
(every resting order is cancelled on the way out by the dead-man).

## Which file
- **Mac / Linux:** `Kalshi-Bot.command`
- **Windows:** `Kalshi-Bot.bat`

Download the one for your OS to your Desktop.

## One-time setup (≈2 minutes)
1. **Python 3** — install from [python.org](https://python.org) if you don't have it.
2. **Your Kalshi key** — the launcher's first run makes a `~/.kalshi` folder and opens it.
   Put two things there:
   - `key.pem` — your Kalshi RSA private key.
   - `env` (Mac/Linux) or `env.bat` (Windows) — your key id + key path:
     ```
     # Mac/Linux  (~/.kalshi/env)
     export KALSHI_API_KEY_ID=YOUR_KEY_ID
     export KALSHI_PRIVATE_KEY_PATH=$HOME/.kalshi/key.pem
     ```
     ```
     :: Windows  (%USERPROFILE%\.kalshi\env.bat)
     set KALSHI_API_KEY_ID=YOUR_KEY_ID
     set KALSHI_PRIVATE_KEY_PATH=%USERPROFILE%\.kalshi\key.pem
     ```
   - *(optional, phone alerts while you're away)* add `TELEGRAM_BOT_TOKEN` and
     `TELEGRAM_CHAT_ID` to the same file — you'll get a ping if the bot trips a safety
     stop or a trial strategy crosses the 2-sigma bar.
3. Double-click the launcher again. It pulls the latest bot code, runs a safety
   preflight, and starts trading.

> **Mac note:** the first time, macOS may block it — right-click the file → **Open** →
> **Open** to approve it once.

## What it does each run
- Pulls the latest validated strategy from the repo (so you're always on current code).
- Runs the safety **preflight** (auth, latency, market, kill-sentinel). NO-GO ⇒ it won't trade.
- Trades with the same conservative caps as everywhere else: **$5 max notional, $3 sticky
  loss-limit**, post-only, strict box-pairing, dead-man cancel-all.
- **Close the window to stop.** The bot catches the close, cancels all resting orders, and
  exits clean. A loss-limit trip also stops it and writes a sticky sentinel (delete
  `~/kalshi-bot/.kalshi_killed_btc15m` to re-arm).

## This vs the cloud switch
- **This launcher** = runs on *your* machine, on while the window is open. Best when your
  computer is on and you want hands-on control.
- **`LIVE_SWITCH` + GitHub Actions** (see `../SWITCH.md`) = runs in the cloud even when your
  machine is off. Best for always-on. The two are independent; don't run both at once
  (the live workflow is a singleton, but two *separate* hosts would double-quote).
