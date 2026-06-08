# Free co-location & deployment (Oracle Cloud Always-Free, ~$0) — the sub-10ms path

Polymarket's CLOB matching engine runs in **AWS eu-west-2 (London)**. The whole latency game is to sit
next to it for free, so order POSTs drop from ~150ms (transatlantic) to single-digit ms. Co-location is
~90% of the win; the code (`coincurve`, `--presign`, `netfast`, in-region RTDS) takes it to sub-10ms.

> Correction vs the old version of this doc: target **London (UK South)**, NOT Frankfurt/Amsterdam —
> the CLOB is in London (eu-west-2), confirmed; Frankfurt adds ~10ms each way for nothing.

## 1. Free server, ranked (closest-to-London first)

| Option | Region | Cost | Net to CLOB | Notes |
|---|---|---|---|---|
| **Oracle Cloud Always Free** | **UK South (London)** | **free forever** | **~1–3ms** | ARM Ampere A1: 4 OCPU/24GB/200GB/4Gbps. *Best.* Same metro as eu-west-2. |
| AWS Free Tier | **eu-west-2** | free **12 mo** | **<1–2ms** | t4g.micro; same AWS region as the matcher (lowest without paid colo). Set a teardown reminder. |
| Fly.io | **lhr** | free allowance | ~1–3ms | fastest to stand up. |
| GCP Always Free | us-only | free | ~80ms ❌ | always-free is US-region only → transatlantic. Not usable. |
| GitHub Actions | Azure, unpinned | free | varies ❌ | fine for the *paper collector* (already running) + a free latency datapoint; not the live maker. |

**Recommended: Oracle Cloud Always Free, UK South (London)** — always free (not a 12-month clock),
big enough for everything, London metro. AWS eu-west-2 free-tier shaves ~1ms more (same region as the
matcher) but expires after a year.

## 2. Stand it up (~10 min)
1. Oracle Cloud account → home region **UK South (London)**.
2. Compute → Create Instance → **VM.Standard.A1.Flex** (Ampere ARM), Ubuntu 22.04, 1–2 OCPU. Add SSH key.
   (If "out of capacity", retry — A1 in London frees up regularly.)
3. `ssh ubuntu@<ip>` then:
   ```bash
   git clone <this-repo> pmkit && cd pmkit && bash deploy/setup.sh
   ```
   `setup.sh` installs deps (incl. **coincurve** for <1ms signing) and runs `latency.py` — read the verdict.

## 3. Verify you're actually co-located (BEFORE funding)
```bash
python3 latency.py 20
```
Read **CLOB POST TTFB**, not ping (ping hits a Cloudflare edge and lies — we measured 0.3ms TCP but
167ms TTFB from the US). Acceptance:
- **< 10ms median, < 20ms p95** → co-located, sub-10ms reachable. ✅
- 20–80ms → near-region (still helps, not eu-west-2).
- > 80ms → transatlantic; **move the box**, no code fixes this.

`live_trader.py` prints a one-line colo verdict (`clob_selfcheck`) on every (re)start.

## 4. The sub-10ms budget (co-located box)
`signal_in (RTDS in-region ~1-5ms) + sign (<1ms) + order POST (~1-10ms) + match (operator)`

| Lever | Status | Effect |
|---|---|---|
| Co-locate eu-west-2/London | this doc | 167ms → ~1–10ms POST |
| In-region RTDS signal (Chainlink+Binance) | **done** | no transatlantic signal hop, zero basis risk |
| `coincurve` signer | `setup.sh`/`requirements` | EIP-712 sign several-ms → **<1ms** (eth_account auto-uses it) |
| Warm keep-alive + NODELAY | **done** (`netfast.fast_session`) | hot request = 1 origin RTT, not 3 |
| **Pre-signed orders** | **done** (`--presign`) | new rung = pure POST (signing off the fire path) |
| Pre-minted box inventory | `--box-arb` split is setup-only | never on-chain in the loop (Polygon ~2s = 200× budget) |

## 5. Paper run first (no keys, no money) — 1–2 weeks
    tmux new -s paper
    ./run.sh paper 1209600              # 14 days   (detach Ctrl-b d; ./run.sh report for P&L/fill rate)
Decision: fill rate >50% → queue winnable, proceed. <30% → need lower latency first (recheck §3).

## 6. Tiny-live pilot (only after paper + a passing latency self-test)
- Fund a **burner wallet** ($100–500). Put PRIVATE_KEY/DEPOSIT_WALLET_ADDRESS in a **gitignored .env on
  the box only** (chmod 600; NEVER commit). `I_UNDERSTAND_REAL_MONEY=yes`.
- DRY-RUN on this exact box first:  `python3 live_trader.py --presign --duration 120`  (places nothing)
- **Verify `--presign` behaves** (fills/cancels) on the burner before scaling — it touches the money path.
- Arm tiny:  `python3 live_trader.py --live --presign --max-notional 25 --loss-limit 5`
- Persist:  `deploy/pmkit.service` (systemd, auto-restart; `journalctl -u pmkit -f` shows the colo verdict).

## 7. Reaching the floor (sub-10ms → sub-ms)
Same AZ as the matcher (AWS eu-west-2 placement group) > London metro; busy-poll the order socket; pin
the loop to a core; pre-sign a deeper ladder during idle; persistent HTTP/2; optimize **p99 not mean**.
Honest prize: the BTC-15m dynamic fee (peak ~3.15% @ p=0.5) caps latency-arb to ~0, so sub-ms mainly
buys **maker queue priority** + **faster quote pulls** (less adverse selection) — real, but the
risk-free-money game (illiquid + negRisk complete sets) is breadth+capital, not speed (see BOXARB.md).

## Free monitoring / persistence
- Alerts: TELEGRAM_BOT_TOKEN/CHAT_ID in .env → `notify.alert()` on kill-switch (`python notify.py` to test).
- tmux across SSH drops; `deploy/pmkit.service` across reboots. audit_*.jsonl are append-only/re-loadable;
  live_trader cancels-all on exit.
