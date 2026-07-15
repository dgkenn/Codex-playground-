# Settlement-logging plan: record realized money for every paper sleeve

**Status:** DRAFT (working-tree only; lead reviews + places + commits). Read-only market data;
no orders; no live-config edits.
**Date:** 2026-07-15
**Author:** sleeve-audit infra fix

---

## 1. The problem (and the exact trap it hid)

Most paper sleeves log **entry-side** metrics (CLV, pre-entry `edge`, fair-value vs mid) but
never durably recorded the **settlement** of each paper position. Without a settled ledger a
sleeve cannot be validated on **realized money** — precisely the trap that hid whether a sleeve
has an edge until we built the FAVLONG realized-money re-audit.

State on the `gha-data` branch as of this audit:

| Sleeve         | entry log present                     | settled file present            |
|----------------|---------------------------------------|---------------------------------|
| kalshi-longshot| `longshot/longshot_pending.json`      | `longshot/longshot_settled.csv` ✅ |
| tailbias       | `tailbias/tailbias_<date>.jsonl`      | `tailbias/tailbias_settled.csv` ✅ |
| **macro-paper**| `macro_paper_<date>.jsonl` + `macro_pending.json` | `macro_settled.jsonl` ❌ **MISSING** |
| **kxwti-paper**| `kxwti_paper_<date>.jsonl` + `kxwti_pending.json` | `kxwti_settled.csv` ❌ **MISSING** |

### Root cause (confirmed against the live Kalshi API, 2026-07-15)

Kalshi's per-market `status` field for a **resolved** market is the string **`"finalized"`**, NOT
`"settled"`. (`"settled"` is only a *query-filter* value for `GET /markets?status=settled`; it
never appears in a returned market object.) `kalshi_longshot_paper.py` documents this as its
"BUG-1" and checks `status == "finalized"`; `kalshi_tailbias_paper.py` was written correctly from
the start. But **`macro_paper.py` (line ~534) and `kxwti_paper.py` (line ~291) still gate
settlement on `status == "settled"`**, so their inline settle blocks never fire and their settled
files are never created — even though the markets *have* resolved.

Verified: the live `macro_pending.json` tickers (e.g. `KXCPIYOY-26JUN-*`, closed 2026-07-14)
return `market.status == "finalized"` with `result == "no"`. The macro settle block would have
skipped every one of them.

---

## 2. The fix: `settle_recorder.py` (reusable, decoupled, idempotent)

Rather than patch each fragile, entry-coupled inline settle block, we add a **standalone**
recorder that is immune to the status-string trap and can back-fill history:

- **Input:** a sleeve's entry-log path + `--sleeve {macro|kxwti|longshot|tailbias}` (+ `--venue kalshi`).
- **Resolution test (API ASSUMPTION A1):** a market is resolved iff `GET /markets/{ticker}` returns
  `market.result in ("yes","no")`. We do **not** gate on the `status` string — that is the bug.
- **P&L (API ASSUMPTION A3):** each sleeve's realized-P&L formula and fee treatment mirror that
  sleeve's own script exactly, so the ledger reproduces what a correct inline block would have written:
  - macro — taker binary buy: `pnl = win − entry_price − quad_fee(entry_price)`
  - kxwti — maker, zero fee: bid → `settle_yes − quote_price`; ask → `quote_price − settle_yes` (FILLED only)
  - longshot — maker sell YES, zero fee: `entry_sell_yes − settle_yes`
  - tailbias — buy favorite: `pnl_taker = settle_fav − taker_px − taker_fee_c/100`; `pnl_maker = settle_fav − maker_px`
- **Idempotent (A4):** keyed on `(ticker, entry_ts)`; already-recorded positions are skipped, so it
  is safe to run every workflow invocation — re-running never double-counts.
- **Output:** appends one row per settled position to a uniform `<sleeve>_settled.jsonl`. Every row
  carries `"date"` (settle date) and `"pnl"` (scored variant; taker for tailbias), so
  `python edge_verdicts.py score <sleeve>_settled.jsonl` works uniformly.
- **Read-only:** public Kalshi REST `GET /markets/{ticker}` only. No auth, no orders, no money.

Validated offline (all four P&L formulas, resting-quote skip, unresolved retry, idempotency) and
against the **live** API on the real macro pending file (resolved 4/4, `status=finalized`, correct
signed P&L).

---

## 3. Template wiring: kxwti-paper (highest-value / fastest to validate)

Wired as the template because **KXWTI settles daily**, so its ledger becomes a scoreable
day-clustered series within days — matching kxwti's pre-registered bar (≥14 forward days,
day-clustered t≥3, ≥80% positive days) fastest. (macro-paper is the same wiring but monthly
cadence, so its ledger fills slowly.)

The full step is in **`kxwti-paper.settle-step.yml.snippet`**. In one line, inside the existing
`gha-data` worktree step, after `python kxwti_paper.py /tmp/dw/gha_data`:

```yaml
python settle_recorder.py /tmp/dw/gha_data/kxwti_pending.json \
    --sleeve kxwti --venue kalshi \
    --out /tmp/dw/gha_data/kxwti_settled.jsonl || true
```

`kxwti_paper.py` writes `kxwti_pending.json` (the durable entry log of FILLED maker quotes);
`settle_recorder` reads it, resolves each market read-only, appends new rows to
`kxwti_settled.jsonl`; the existing `git add gha_data/` + push commits the ledger. `settle_recorder.py`
is stdlib-only and already checked out at `$GITHUB_WORKSPACE` on `$BRANCH`, so no new setup step.

---

## 4. Extending to the other sleeves (one row each)

Add the same step to each sleeve's workflow (in its `/tmp/dw` worktree, after the entry script,
before `git add`). Entry-log path and `--sleeve` are the only things that change:

| Sleeve   | workflow                     | entry log (in `/tmp/dw/gha_data...`)      | command tail                                  |
|----------|------------------------------|-------------------------------------------|-----------------------------------------------|
| kxwti    | `kxwti-paper.yml`            | `gha_data/kxwti_pending.json`             | `--sleeve kxwti --out gha_data/kxwti_settled.jsonl` |
| macro    | `macro-paper.yml`            | `gha_data/macro_pending.json`             | `--sleeve macro --out gha_data/macro_settled.jsonl` |
| longshot | `kalshi-longshot.yml`        | `gha_data/longshot/longshot_pending.json` | `--sleeve longshot --out gha_data/longshot/longshot_settled.jsonl` |
| tailbias | `tailbias-paper.yml`         | `gha_data/tailbias/tailbias_<date>.jsonl` OR `tailbias_pending.json` | `--sleeve tailbias --out gha_data/tailbias/tailbias_settled.jsonl` |

Notes:
- **longshot & tailbias** already produce `*_settled.csv` from their (correct) inline blocks. The
  recorder's `*_settled.jsonl` is a **parallel, uniform, independently-verifiable** ledger — run it
  as a cross-check first; once trusted it can replace the inline CSV path. No harm running both
  (recorder is read-only + idempotent).
- **macro & kxwti** have no working settled file today, so the recorder is the primary fix. Two
  paths, do BOTH ideally:
  1. **Immediate back-fill (no workflow change):** locally check out `gha-data` and run the
     recorder over the existing pending files to create the ledgers now (their markets are already
     finalized). Lead commits the resulting `*_settled.jsonl` to `gha-data`.
  2. **Ongoing:** add the workflow step so every future run records settlements.
- **Also worth fixing at the source** (separate, optional change to the entry scripts on `$BRANCH`):
  change `status == "settled"` → `status == "finalized"` (or gate on `result in ("yes","no")`) in
  `macro_paper.py` line ~534 and `kxwti_paper.py` line ~291, so their inline blocks work too. The
  recorder makes this non-urgent but it removes the latent bug.
- **Entry-log choice:** prefer the `*_pending.json` file where present (it carries side + entry
  price + entry ts per open position). For tailbias, `tailbias_pending.json` empties out quickly
  (15-min markets finalize fast), so its durable entry log is the daily `tailbias_<date>.jsonl`
  tape — the recorder auto-detects JSON-array vs JSONL and reads either.

---

## 5. Re-audit on realized money (the payoff)

Once `<sleeve>_settled.jsonl` accrues, each sleeve can be re-audited on **realized money** with the
same machinery used for FAVLONG:

- `python edge_verdicts.py score gha_data/<sleeve>_settled.jsonl` (uniform `date`+`pnl` columns).
- **Day-clustered t** (one mean-P&L-per-day observation, t across day-means, `sqrt(n_days)` SE) so
  correlated same-day rungs/windows don't inflate significance — the exact discipline in each
  sleeve's pre-registered bar (macro uses an event-count bar instead; kxwti/longshot/tailbias use
  ≥14 forward days + day-clustered t≥3 + ≥80% positive days).
- Per-asset / per-series sign checks where applicable (tailbias per BTC/ETH/XRP; macro per
  CPI/core-CPI/FOMC).

No sleeve advances toward any live step until its realized-money ledger clears its own
pre-registered bar. Recording settlement is the precondition that makes that judgment possible at all.

---

## API assumptions (re-verify if Kalshi changes the API)

- **A1** resolved ⇔ `market.result ∈ {yes,no}` (NOT `status=="settled"`; live status is `"finalized"`).
- **A2** binary payout: YES pays \$1 on `result=="yes"` else \$0 (symmetric for NO); `settle_yes ∈ {0,1}`.
- **A3** per-sleeve P&L/fees mirror each sleeve's own script (see §2).
- **A4** idempotency key `(ticker, entry_ts)`; entry_ts = snapshot ts (`ts` / `snap_ts`).
- **A5** only `--venue kalshi` implemented (all four sleeves are Kalshi). A Polymarket adapter
  would resolve via gamma-api `conditionId → outcomePrices`; currently stubbed with a clear error.
