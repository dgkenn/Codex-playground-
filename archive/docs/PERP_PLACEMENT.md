# PERP_PLACEMENT.md — where each draft file goes, and how to test the collector

These files were written as **drafts on `claude/coding-bot-ab-test-results-ffmhxw` and NOT committed**
(per instruction). They are READ-ONLY market-data collection: no orders, no live-config edits, no
changes to `live.yml` / `LIVE_SWITCH` / `live_switch.sh`. The lead places them on the correct branches.

## What goes where (mirrors the collect.yml split exactly)

| File | Target branch | Why |
|---|---|---|
| `kalshi_perp_collect.py` | **`claude/polymarket-bot-live-ready-vw7ut5`** (the `$BRANCH` "bot"/code branch) | The workflow checks out CODE from `$BRANCH`; the collector must live there, next to `kalshi_collect.py` / `kalshi_ladder_collect.py`. |
| `.github/workflows/kalshi-perp-collect.yml` | **`main`** | GitHub fires `schedule`/`workflow_dispatch` **only from the default branch (main)**. Same reason `collect.yml` lives on main. It checks out the collector from `$BRANCH` and commits data to `gha-data`. |
| `perp_strategy_design.md` | `claude/polymarket-bot-live-ready-vw7ut5` (docs live with the code) | Design for the 3 paper edges to build once data lands. |
| `PERP_PLACEMENT.md` | either (informational) | This note. |

Data lands on the **`gha-data`** branch under `gha_data/<YYYY-MM-DD>/…` like every other collector
(the workflow date-partitions at commit time). Nothing is written to `main` or `$BRANCH` at runtime.

Output files per run (`r<run_id>` tag):
- `ticks_kalshi_perp_<asset>_r<id>.jsonl.gz` — one per discovered perp (all 16 crypto perps).
- `ticks_kalshi_perp_binmid_<asset>_r<id>.jsonl.gz` — aligned 15m-binary YES mid for btc/eth/sol/xrp.
- `registry_kalshi_perp_r<id>.json` — full raw schema of every discovered perp (learn the product).
- `HEARTBEAT_kalshi_perp_r<id>.json`; `NOTE_kalshi_perp_r<id>.json` iff nothing discovered (exit 0).

## Cron slot chosen

`1,21,41 * * * *` (three/hour, self-chain backstop). Dodges every existing schedule:
collect `:9,29,49`, live `:3,28,53`, box-shadow `:47`, favlong `:33`, sports-alert `:17`,
kalshi-longshot `:14,44`.

## The aligned binary mid — already-collected note

`collect.yml` already collects the *rich* `ticks_kalshi_<asset>15m` streams (mid+spot+book), but on a
**different cron minute** → not time-aligned to the perp polls. So `kalshi_perp_collect.py`
**additionally** snapshots the 15m-binary YES mid on the **same clock** as each perp poll
(`…perp_binmid_…`), which is what the perp↔binary basis edge (a) needs. The lead may instead choose to
join against `collect.yml`'s richer streams offline if approximate time-alignment is acceptable.

## How to test the collector once keys are available

The perp READ endpoints are **currently public** — no key needed (verified 2026-07-15). The collector
runs keyless today and signs requests only if a key is present (future-proofing).

**1. Smoke test, keyless, short run (works right now, no secrets):**
```bash
python kalshi_perp_collect.py 20 /tmp/perp_test smoke
ls /tmp/perp_test/
python - <<'PY'
import gzip, json, glob
f = sorted(glob.glob('/tmp/perp_test/ticks_kalshi_perp_btc_*.jsonl.gz'))[-1]
r = [json.loads(l) for l in gzip.open(f, 'rt')]
print('rows:', len(r)); print(json.dumps(r[-1], indent=2)[:1200])
PY
```
Expect: discovery logs 16 perps (`KXBTCPERP…`), per-asset gz files, and rows carrying
`bid/ask/mid/index/mark/last/open_interest/volume/contract_size` plus (on the first cycle and every
~30s) a `funding` block with `funding_rate` + `next_funding_time`, and a full `book` for btc/eth/sol/xrp.

**2. With a key (exercises the signed path):** set the same secrets `live.yml` uses —
`KALSHI_API_KEY_ID` and a PEM at `KALSHI_PRIVATE_KEY_PATH` (the workflow writes the
`KALSHI_PRIVATE_KEY` secret to a 0600 temp file and exports the path). Then:
```bash
export KALSHI_API_KEY_ID=...            # from kalshi.com account settings
export KALSHI_PRIVATE_KEY_PATH=/path/to/key.pem
python kalshi_perp_collect.py 20 /tmp/perp_test signed
```
Confirm `registry_*.json` shows `"authed": true` and rows are unchanged (signed reads return the same
public data — auth is additive, not required).

**3. Verify the CI path (no live impact):** merge the workflow to `main` and the collector to `$BRANCH`,
then trigger once via **workflow_dispatch** (Actions UI → "kalshi-perp-collect" → Run). Check the run
committed `gha_data/<today>/ticks_kalshi_perp_*` to the `gha-data` branch:
```bash
git fetch origin gha-data && git checkout origin/gha-data -- gha_data/
ls gha_data/$(date -u +%Y-%m-%d)/ticks_kalshi_perp_*
```
To STOP the chain: disable the workflow in the Actions UI (the self-dispatch then 403s and the chain
ends) — deleting the cron lines alone is not enough, same as `collect.yml`.

## Assumptions / risks the lead should confirm

- **Perp reads are public today.** If Kalshi gates `/margin/*` behind auth later, the wired secrets
  keep it working — but a keyless CI run would then collect nothing (it writes a `NOTE_…` and exits 0,
  never failing the workflow). Set the secrets to be safe.
- **Product re-scaled since `PERP_HEDGE.md`:** `contract_size` is now `0.0001 BTC` (was `0.01`). The
  collector reads `contract_size` every poll and never hardcodes it — but any sizing/capacity analysis
  must read it from the data, not from the old doc.
- **`funding_history` needs a `start_date`** (400 without it); the collector uses the
  `funding_rates/estimate` endpoint (clean `funding_rate` + `next_funding_time`) as the primary
  funding source, which is sufficient for a forward-accruing collector.
- **No orders, ever.** This collector only calls the read endpoints
  (`/margin/markets`, `/margin/markets/{t}/orderbook`, `/margin/funding_rates/estimate`) and the
  public 15m-binary `/markets` endpoint. It imports no trading code.
