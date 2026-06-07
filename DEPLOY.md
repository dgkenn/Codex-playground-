# Free deployment (Oracle Cloud Always-Free, ~$0)

Goal: run the PAPER bot 24/7 in Europe to measure FILL RATE, then a tiny-live pilot.
Everything here is free; the only real lever is latency/queue (paid colo is faster).

## 1. Server (free, Europe)
- Oracle Cloud **Always Free** ARM VM (4 vCPU/24GB), region **Frankfurt or Amsterdam**
  (closest free thing to colo). Ubuntu 22.04. (GCP $300/90d credit is a faster alt for live.)
- `ssh ubuntu@<ip>`; `sudo apt update && sudo apt install -y python3-venv python3-pip git tmux`

## 2. Get the bot
    git clone <this repo> && cd Codex-playground-
    ./run.sh setup                      # venv + requirements.txt
    cp .env.example .env && chmod 600 .env   # edit .env; NEVER commit it

## 3. Paper run (no keys, no money) — run for 2-4 weeks
    tmux new -s paper
    ./run.sh paper 1209600              # 14 days
    # detach: Ctrl-b d   | reattach: tmux attach -t paper
Monitor anytime:
    ./run.sh report                     # P&L, FILL RATE, markout (audit_report.py)
Decision: fill rate >50% -> queue is winnable, proceed. <30% -> need lower latency first.

## 4. Tiny-live pilot (only after paper looks good)
- Fund a **burner wallet** with $100-500 (only what you'll risk). Deposit wallet (POLY_1271) + pUSD + approvals.
- Put PRIVATE_KEY/DEPOSIT_WALLET_ADDRESS in .env; set I_UNDERSTAND_REAL_MONEY=yes.
- DRY-RUN first:  ./run.sh live                      (prints intended orders, places none)
- Arm tiny:       ./run.sh live --live --max-notional 25 --loss-limit 5
- WATCH: realized gross >=0, rebate received, fill rate. Kill-switch auto-cancels on loss/limits.

## 5. Free monitoring/alerts
- Logs: paper_trades.log + audit_*.jsonl on disk.
- Alerts: set TELEGRAM_BOT_TOKEN/CHAT_ID in .env -> notify.alert() pings you on kill-switch.
  Test: python notify.py
- (Optional) Grafana OSS + Prometheus on the same VM for dashboards (free).

## 6. Persistence / restarts
- tmux keeps it running across SSH disconnects. For reboots, use a systemd unit calling `run.sh paper`.
- State: audit_*.jsonl are append-only and re-loadable; live_trader cancels-all on exit.

## Free-stack trade-offs (what you give up vs paid)
latency ~5-10ms (Oracle) vs <3ms (colo) -> lower queue position; shared ARM CPU; .env keys
(use a burner wallet); ~99% uptime. Fine for a $100 fill-rate validation.
