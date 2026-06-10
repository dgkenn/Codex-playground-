# PILOT.md — live deploy runbook (real money, your infra)

> _Historical — superseded by the gating validation + 4-day multi-asset data. Kept for provenance; where this disagrees with current docs, **README.md / GATING.md / INSIGHTS_4DAY.md win**._

Offline research is complete (`FINDINGS.md`). The architecture is specced (`LIVE_DESIGN.md`).
This is the operational runbook to deploy the two validated capacity levers SMALL and measure
the one input the whole edifice rests on: **queue-weighted capture rate**. Everything below runs
on YOUR machine with YOUR key — never in the research sandbox.

## 0. Safety checklist (do every item before `--live`)
- [ ] **Burner wallet**, funded with only what you'll risk (start ~$100–300). Never your main key.
- [ ] `PRIVATE_KEY`, `DEPOSIT_WALLET_ADDRESS`, `POLYGON_RPC` in `.env` (already gitignored — verify
      `git check-ignore .env` prints `.env`). NEVER commit keys.
- [ ] USDC + a little MATIC (gas for mint/merge) in the burner on Polygon.
- [ ] Telegram alerts on (optional): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- [ ] Confirm DRY-RUN first (below) prints sane layered quotes before adding `--live`.
- [ ] Kill-switches set: `--loss-limit` (hard $ stop) and the rolling-markout cutout are on by default.

## 1. Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # + web3 for mint/merge, py-clob-client-v2 for orders
cp .env.example .env                      # then fill in your burner key (NEVER commit)
```

## 2. DRY-RUN sanity (places nothing)
```bash
python live_trader.py --duration 120 --cap 25 --post 5
```
Expect: layered post-only quotes (BUY ≤ bid, SELL ≥ ask), "overlay OFF until next open" on a
mid-window join then ON at the next window, microprice anchor active. No orders sent.

## 3. Step 1 — ONE book, smallest size (the capture-rate measurement)
```bash
I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live \
  --cap 25 --post 5 --max-notional 25 --loss-limit 5 --layers 3
```
Run ≥ a few hours. The ONLY goal is to measure capture and queue position, not P&L.
```bash
python audit_report.py            # paper metrics
# live: inspect live_markout.jsonl (per-fill markout) and reprice_log.jsonl (queue, cancels)
```
**GO / NO-GO (queue-weighted, per LIVE_DESIGN #3 — raw fill rate misleads):**
- **GO (scale up):** capture > ~40% AND markout at +5s ≥ ~0 AND front-of-queue fills dominate.
- **HOLD (fix latency first):** capture < ~30% → you're losing the queue; the edge can't pay.
  Reduce cancel latency / colocate before adding size (see LIVE_DESIGN #7). Do NOT add capital.
- **STOP:** sustained negative markout → adverse selection is winning; pull back, re-check.

## 4. Step 2 — turn on mint/merge (collateral efficiency)
Already wired (`collateral.py`, merge-at-rollover). Needs `web3` + MATIC. Confirm merges fire in
the log when matched inventory accumulates; this is what lets you raise size on fixed capital.

## 5. Step 3 — climb the cap frontier (only if Step 1 is GO)
Raise `--cap` 25 → 50 → 100 … watching that **live** capture and markout hold. The offline cap
frontier (`cap_tail.py`) is an UPPER bound; the real ceiling is where your own size moves the
book (LIVE_DESIGN #6). Stop when per-share markout starts bending down — that's the impact-cap.

## 6. Step 4 — second book (ETH 15m) — the fill-parity test
Add ETH 15m. This is the LIVE test of the assumption √N rests on (alt fill rates match BTC) and
the first use of the **portfolio-level delta cap** (one factor budget across books, LIVE_DESIGN
#1). If ETH capture ≈ BTC capture, breadth pays ~√N; if not, the multi-market math doesn't hold —
size it down to its measured capture.

## 7. What to build live (specced, online-only — see LIVE_DESIGN.md)
The pilot should converge these from real fills, not run fixed params:
- **#2 online κ-learner** — deploy a learner, don't pre-fit (offline κ is provably wrong).
- **#3 queue-position P&L** — make the objective queue-weighted capture.
- **#4 microprice repricing** — target is implemented; tune its weights live.
- **#1 factor controller** — when ≥2 books, cap on factor inventory, not per book.

## Reminders
- Hold-to-resolution beats auto-flatten (FINDINGS); don't add a flatten leg — mint/merge handles
  collateral, the cap+skew handle delta.
- Every needless cancel forfeits queue position (≈ half-spread ≈ your whole edge). Layer, don't churn.
- The edge is structural and thin: it pays for being bigger/broader/faster, not smarter. Scale and
  execution are the levers; there is no signal to add.
