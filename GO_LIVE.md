# Go-Live Harness — everything needed to take the maker live

One page, in order. Every money step is gated by a check that fails loudly. The thin rebate edge means a
single mistake (a cross, a disconnect, a missing rebate) can erase weeks of gains — so the harness is built
to make those mistakes structurally hard. Detailed colo guide: `DEPLOY.md`. Gap analysis: `PAPER_VS_LIVE.md`.

```
setup ──▶ preflight (GO/NO-GO) ──▶ dryrun ──▶ pilot ($20) ──▶ reconcile (real go/no-go) ──▶ scale
```

## 0. Account & wallet (you do this once, off-box)
- Create the Polymarket account and complete KYC **for a jurisdiction where you're permitted to trade**
  (confirmed). Deposit only a **pilot amount** to a **dedicated burner wallet** — never your main wallet.
- The bot only ever needs that burner's `PRIVATE_KEY` + the Polymarket `DEPOSIT_WALLET_ADDRESS`.

## 1. Provision the box (co-located = the whole point)
A free Oracle Cloud / AWS box in **London (eu-west-2)** — same region as the CLOB matcher.
```bash
ssh user@box
git clone <repo> pmkit && cd pmkit
bash deploy/setup.sh            # installs deps + prints the latency colo verdict
```
`setup.sh` verifies `coincurve` (sub-ms signing) and the exact CLOB client `live_trader` needs
(`py_clob_client_v2`). If it says MISSING, fix that before arming — the bot can't place orders without it.

## 2. Secrets (on the box only — never in git, never in this repo)
```bash
cp .env.example .env && chmod 600 .env && nano .env
```
Set `PRIVATE_KEY`, `DEPOSIT_WALLET_ADDRESS`, **`SIGNATURE_TYPE`** (must match how the account was
created: `POLY_PROXY` for email/Magic login — the default — or `POLY_GNOSIS_SAFE` for a browser-wallet
account; wrong type = every order fails signature validation), optional `TELEGRAM_BOT_TOKEN`/`CHAT_ID`.
Leave `I_UNDERSTAND_REAL_MONEY=no` until you've passed preflight + dry-run. `.env` is gitignored; keys
never leave the box. Keep values on their own line (no inline comments — systemd doesn't strip them).

## 3. Preflight gate — the single GO/NO-GO
```bash
./run.sh preflight              # = python go_live.py
```
Runs **9 checks**: secrets present + `chmod 600`; roster valid; paper edge still net+gross positive;
live SDK importable; fast signing; **CLOB latency (must be single-digit ms / co-located)**; market
discovery; **post-only guard self-test**; risk-rail defaults. Secrets are checked for *presence only* —
values are never printed. **Do not proceed unless it prints `VERDICT: GO`.**

## 4. Dry-run on this exact box (places nothing)
```bash
./run.sh dryrun 120             # live_trader --presign --duration 120, no --live
```
Confirms market discovery, the colo verdict, the post-only guard, and that the dead-man arms — on the real
machine, with zero risk.

## 5. Tiny live pilot ($20–25, hard loss cap)
Set `I_UNDERSTAND_REAL_MONEY=yes` in `.env`, then:
```bash
./run.sh pilot 7200             # --live --presign --max-notional 25 --loss-limit 5
```
The pilot's job is **not** "make money" — it's to confirm the three things paper can't: the rebate is real,
we actually fill, and live adverse selection isn't worse than paper (`PAPER_VS_LIVE.md` A1/A2/A4).

## 6. Reconcile — the real go/no-go
```bash
./run.sh reconcile              # = python pilot_reconcile.py
```
Prints fill rate, **maker integrity (alarms on any TAKER fill)**, live-vs-paper markout (Welch t),
**predicted rebate (then confirm the ACTUAL credit hit the wallet)**, and per-window net t-stat → a
`GO / NO-GO / INSUFFICIENT` verdict. Net confidence is **scale-invariant** — more *windows* confirm the
edge, not bigger clips.

## 7. Run it persistently
```bash
sudo cp deploy/pmkit.service /etc/systemd/system/   # edit User/paths/args first
sudo systemctl daemon-reload && sudo systemctl enable --now pmkit
journalctl -u pmkit -f                               # watch the [latency] colo verdict each (re)start
```
Defaults to DRY-RUN; to go live, add `--live` to `ExecStart` and `Environment=I_UNDERSTAND_REAL_MONEY=yes`.

## Safety rails (all wired in `live_trader.py`; audited line-by-line — `LIVE_READINESS_AUDIT.md`)
- **Post-only, twice** — `would_cross` refuses any marketable order locally AND every POST carries the
  venue's `post_only=True` flag (closes the stale-book race; a reject is requoted, never crossed).
- **Own-order-excluded microprice** — we don't contaminate our own toxicity signal.
- **Dead-man switch** — `atexit` + SIGTERM/SIGINT cancel-all on *any* exit; book-staleness watchdog
  (`--deadman-s`) cancels-all if we'd be quoting blind; error-storm trip after 5 consecutive failures;
  every non-rollover cancel-all is backstopped by a venue-side scoped cancel (covers lost bookkeeping).
- **Startup + continuous reconciliation** — live start refuses to quote until a venue `cancel_all`
  clears any predecessor's leftovers (SIGKILL/OOM never runs handlers); every 5s, any open order the
  venue has that we don't recognize is cancelled.
- **Kill-switches, sticky** — `--loss-limit` reads a real ledger (per-window cash+positions settled at
  resolution, open window marked to mid) + rolling-markout-toxic kill; both cancel-all, write a
  `.pmkit_killed_*` sentinel, and exit — a systemd restart will NOT re-arm until the operator deletes it.
- **Caps** — `--max-notional` bounds AGGREGATE exposure (open buy notional + token cost), `--cap`,
  `--skew`, `--max-rungs` bound inventory; sells only rest what session inventory funds.
- **Alerts** — `notify.alert()` → Telegram on start, every kill, every dead-man trip, any TAKER fill,
  and any `live_multi` child restart.

## Box hardening (general security — recommended)
- SSH **key-only** auth (disable passwords); `ufw` allow only SSH out/in you need; `fail2ban`.
- Dedicated burner wallet funded only to pilot size; rotate API creds if ever exposed.
- A VPN for the box's general outbound security is fine; **do not** use it to access from a jurisdiction
  where you're restricted — that risks the account/funds being frozen (see `PAPER_VS_LIVE.md`).

## Queue priority (get filled first, on the right side)
`QUEUE_PRIORITY.md` documents the 5 levers and their flags: `--improve` (price-improve into a wide spread,
toxicity-gated), `--min-rest-s` (don't churn earned priority), `--presign-depth` (win the new-level race),
`--max-queue-ahead` (don't bury yourself), and p95/p99 latency gating + a live regression monitor. Validate
each in DRY-RUN; the `reconcile` markout check is the referee that the extra fills are benign, not toxic.

## Scale-up rule
Increase the bankroll only after `reconcile` is GO over several clean sessions **and the actual rebate
credit is confirmed**. Then add breadth (more `--asset`/`--tenor-min` instances) before adding size —
breadth raises both volume and risk-adjusted return; size alone doesn't improve confidence.
```bash
python live_multi.py            # one live_trader per market (breadth), each with its own caps
```
