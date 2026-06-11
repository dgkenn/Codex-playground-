# 24/7 bot on a free Oracle Cloud VM

Runs the bot around the clock — independent of your laptop — on an **always-free** Oracle Cloud
instance in us-east (closest free region to Kalshi's NY servers, ~40-55ms). Same `LIVE_SWITCH`,
same Telegram on/off, same caps. About 15 minutes, one time.

## 1. Make the free VM (Oracle Cloud)
1. Sign up at <https://www.oracle.com/cloud/free/> (needs a card for identity; the **Always Free**
   tier never charges and never expires).
2. Console → **Compute → Instances → Create instance**:
   - **Image:** Canonical Ubuntu 22.04 (or 24.04).
   - **Shape:** any **Always Free-eligible** shape — `VM.Standard.E2.1.Micro` (x86) is simplest;
     the Ampere `A1.Flex` (1 OCPU / 6 GB) is also free and plenty.
   - **Region/AD:** pick a **US East** region at signup if offered.
   - **SSH keys:** let it generate one and **download the private key**, or paste your own public key.
3. Create. Note the instance's **public IP**.

## 2. Get in and copy your credentials up

**macOS / Linux:**
```bash
ssh -i <downloaded-key> ubuntu@<vm-ip>          # connect
ssh ubuntu@<vm-ip> 'mkdir -p ~/.kalshi && chmod 700 ~/.kalshi'
scp ~/.kalshi/key.pem ~/.kalshi/env ubuntu@<vm-ip>:~/.kalshi/
```

**Windows (PowerShell — ssh/scp are built in, no PuTTY needed):**
```powershell
# connect (use the key Oracle gave you):
ssh -i C:\Users\<you>\Downloads\<key>.key ubuntu@<vm-ip>

# from another PowerShell window, make the folder and copy your two cred files up:
ssh -i C:\Users\<you>\Downloads\<key>.key ubuntu@<vm-ip> "mkdir -p ~/.kalshi && chmod 700 ~/.kalshi"
scp -i C:\Users\<you>\Downloads\<key>.key C:\Users\<you>\.kalshi\key.pem C:\Users\<you>\.kalshi\env ubuntu@<vm-ip>:~/.kalshi/
```
(If your key.pem / env live elsewhere on the PC, point those paths at wherever they are.)
Your `~/.kalshi/env` should contain (the same one your laptop launcher uses):
```
export KALSHI_API_KEY_ID=YOUR_KEY_ID
export KALSHI_PRIVATE_KEY_PATH=/home/ubuntu/.kalshi/key.pem
export TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
export TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```
> Note the path uses `/home/ubuntu/...` on the VM (not your Mac's `$HOME`). Fix that one line after copying.

## 3. One command to install the 24/7 service
On the VM:
```bash
git clone -b claude/polymarket-bot-live-ready-vw7ut5 https://github.com/dgkenn/Codex-playground-.git ~/kalshi-bot
bash ~/kalshi-bot/deploy/vm_setup.sh
```
That installs deps and a **systemd service** (`kalshi-bot`) that runs `live_supervisor.sh` forever —
auto-restarts on crash and on reboot. It starts the trader, the data collector, and the Telegram
listener together.

## 4. Control it
- **On / off:** text the bot `on` / `off` (the VM listener handles it), or on the VM
  `cd ~/kalshi-bot && ./live_switch.sh on|off`.
- **Watch it:** `journalctl -u kalshi-bot -f`  or  `tail -f ~/kalshi-bot/overnight_data/trader.log`
- **Status:** `systemctl status kalshi-bot`

## Important: run it in ONE place at a time
The live workflow/desktop/VM all read the same `LIVE_SWITCH`. Two *separate hosts* trading at once
would double-quote real orders. Pick the VM as the always-on home and keep the desktop launcher for
hands-on sessions (don't run both live simultaneously). The data **collector** is safe to run
anywhere/everywhere (read-only).

## Security note
The VM holds your Kalshi key (0600, in `~/.kalshi`). Lock the instance's security list to your IP
for SSH (port 22), keep the OS updated (`sudo apt upgrade`), and that's the whole surface — the bot
only makes outbound HTTPS to Kalshi/Binance/Telegram.
