# Improving the longshot-maker harvest with the box A/B tester's validated lessons (2026-06-21)

The soft-market longshot harvest (`KALSHI_MAKER_VERDICT.md`) is **+0.97c/contract NAIVE** — we quote every
longshot and eat whatever flow comes. Its one proven weakness is **adverse selection**: the overall maker edge
died because favorites/mids get picked off (~2c drag), and even the surviving longshot band carries some toxic
fills. **The box A/B tester (`box_policy_ab.py`, 263k fills, 20k-fill markout studies, 3,383 windows) exists to
solve exactly this problem — counterparty avoidance — and its detectors are OOS-validated.** This is the richest
transferable asset we have. Below: the box's validated gates, mapped to the longshot harvest, ranked by
expected lift × ease of transfer.

## The core insight
Both are MAKER plays whose P&L = (premium harvested) − (adverse-selection paid). The box quantified that
**filtering the toxic ~10–40% of fills adds +0.4 to +2.9c/fill.** The longshot harvest currently does NONE of
this filtering. Porting even part of it should lift +0.97c → ~+1.5–2.5c AND potentially re-open the favorite/mid
bands (which were only killed by adverse selection — remove it and they may turn +EV).

## Ranked transferable improvements

### 1. TAKE-SIZE TAIL-TRIM (box t33: VALIDATED OOS +0.05–0.10c/fill, keeps ~92% volume) — EASIEST, do first
Box finding: fills from **large crossing takes (>100 contracts) are informed**; recreational flow is small.
Trimming the >100-contract takes is a clean, monotone add-on.
**Longshot transfer:** recreational longshot *buyers* are small (lottery tickets). A large order lifting your
NO / buying the YES longshot is a red flag (someone knows). **Rule: if a large take (> a size threshold, tuned
per market depth) hits the longshot, cancel/stand down rather than keep resting.** Cheap to implement off the
`/markets/{ticker}/trades` feed (has `count` + `taker_side`).

### 2. VPIN FLOW-TOXICITY GATE (box t32: VPIN>0.40 gate; combined detector OOS AUC 0.70 vs 0.62 alone)
Box finding: order-flow imbalance over equal-volume buckets (Easley–López de Prado–O'Hara VPIN) predicts toxic
fills; gating opens at VPIN>0.40 cut strand rate 0.268→0.214. The COMBINED informed-flow detector (VPIN +
take_n + …) hit AUC 0.70.
**Longshot transfer:** compute VPIN on each longshot's trade tape; **when toxicity spikes (one-sided buying
into the YES longshot = possible news), PULL or WIDEN the resting NO.** This is the single biggest lever —
it directly removes the informed-buyer fills that are the longshot's only real loss source. Reuse
`box_policy_ab._vpin` / `_vpin_at` verbatim on Kalshi `/trades`.

### 3. FACE-CONTRARIAN SELECTION (box t31: THE #1 gate, OOS +0.233c contrarian vs −0.182c momentum = +0.41c)
Box finding: quoting *against* the recent flow direction (`flow>=0` = flow supports your leg) was the best gate
of all, OOS-validated at +0.41c/fill spread.
**Longshot transfer:** this IS the favorite-longshot mechanism, refined. **Among candidate longshots, prioritize
those being bought on naive momentum/FOMO** (recreational pile-in you fade) and **deprioritize longshots where
flow is informed/one-directional-smart.** Score each longshot by recent flow sign; quote the contrarian ones.

### 4. TOXICITY-CONDITIONED EXIT (box t17: fitted tox score, +2.1c/fill settle / +2.9c markout vs hold-all)
Box finding: "stops are +EV only for the INFORMED subset." A fitted toxicity score sold the worst ~39% of
fills (mean −0.6c) while keeping the +0.5c good ones — a +2.1c/fill settle improvement over hold-all.
**Longshot transfer:** we currently HOLD every NO to settlement. Instead, **exit (buy the NO back / sell the
position) when a held longshot turns toxic** — i.e., the YES longshot is gaining *informed* steam toward
hitting. Don't exit on noise (see #6); exit on the toxicity signal. Biggest single P&L improvement in the box.

### 5. LOW-VOL / NEWS STAND-DOWN (box t20, Foucault 1999: pick-off risk rises with volatility)
Box finding: makers should stand down in high-vol regimes.
**Longshot transfer:** **don't quote a longshot when its event has fresh news / a pending catalyst** (the exact
moment a longshot can suddenly become live and pick you off). Gate on event-vol / time-to-known-catalyst.

### 6. DON'T PANIC ON NOISE (box: adverse pre-fill spot MEAN-REVERTS; sig_adv fits NEGATIVE)
Box finding: an adverse move right before a fill tends to mean-revert (same mechanism as "stops lose").
**Longshot transfer:** a longshot that ticks up on *noise* tends to revert — so the exit rule (#4) must key on
the *informed/toxicity* signal, NOT on raw price moving against you, or you'll stop out of good positions.

### 7. GROSS-VS-NET DISCIPLINE (the box's hardest-won meta-lesson)
The box A/B proved most "edge" was rebate harvesting, not real edge, until separated. The longshot harvest has
no rebate, so its number is already net — but the lesson stands: **every improvement above must be validated on
realized-P&L-to-settlement net of adverse selection (the `kalshi_maker_advsel.py` metric), not on quoted-price
EV** (the trap that nearly sold us the soft-market snapshot and the 15m artifact).

## Expected payoff & how to validate
- **Stacking #1+#2+#3 (the open-gates)** is the box's proven recipe and should lift the longshot net edge from
  +0.97c toward ~+1.5–2.5c AND likely re-open the 0.20–0.50 and favorite bands (adverse-selection-killed today).
- **#4 (toxic exit)** was the single biggest box lever (+2.1c/fill) — highest upside, most work (needs live
  position monitoring + the toxicity model refit on Kalshi data).
- **Validate forward** on the `kalshi_longshot_paper.py` track with gate variants A/B'd against the naive
  baseline, scored on realized P&L net of adverse selection — i.e., point the box's *methodology* (paired,
  net-of-toxicity, OOS) at the longshot strategy. This is the legitimate way to "use the A/B tester" here.

## Implementation order (lowest-risk first)
1. Add **take-size tail-trim** + a simple **one-sided-flow gate** to `kalshi_longshot_bot.py` (off `/trades`).
2. Port **VPIN** (`_vpin`/`_vpin_at`) and add the **VPIN open-gate**.
3. Add **face-contrarian scoring** to candidate ranking.
4. Build the **toxicity-exit** (refit the tox model on Kalshi longshot fills) — the big one, last.
Each step A/B'd forward on the paper-track, net of adverse selection, before going live.
