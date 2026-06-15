# Sports CLV / timing-lag collector -- setup & run-book

Forward data-collection harness for the **Kalshi-vs-sharp-line timing-lag test**
(part B of `kalshi_clv_lag.py`). It accrues, automatically, the aligned time-series
needed to measure whether Kalshi sports prices **lag** the sharp (Pinnacle) line --
which, if real, is a **maker-capturable edge** (rest at the post-move fair value;
0 maker fee + up to +$0.005/contract Liquidity Incentive rebate).

The collector (`sports_clv_collect.py`) and the workflow (`.github/workflows/sports-clv.yml`)
are **safe to merge with no key present**: with no `ODDS_API_KEY` the script prints its
design and exits 0, and the workflow no-ops (nothing to commit). It activates the moment
the operator adds the secret -- no code change required.

---

## 1. Get a free the-odds-api key (500 requests/month)

1. Go to <https://the-odds-api.com/> and click **Get API key** (free tier).
2. Confirm your email; the dashboard shows your key and remaining monthly quota.
3. Free tier = **500 requests/month**. The `eu` region returns **Pinnacle**, the sharp
   book we de-vig for the fair line. (Each `/v4/sports/{sport}/odds` call = 1 request.)

## 2. Add it as the `ODDS_API_KEY` GitHub repo secret

GitHub repo -> **Settings -> Secrets and variables -> Actions -> New repository secret**

- **Name:** `ODDS_API_KEY`
- **Value:** the key from step 1

That's it. The next scheduled `sports-clv` run will start collecting. Until the secret
exists, the workflow runs cleanly and commits nothing.

## 3. Cron cadence & quota math

The workflow runs **3x/day** at US game hours (UTC):

| cron (UTC) | approx US time |
|------------|----------------|
| `00 18 * * *` | afternoon / early-evening slate |
| `00 23 * * *` | primetime |
| `00 02 * * *` | west-coast late games |

Each run polls **4 leagues** (MLB / NHL / NBA / NFL) = 4 odds-API requests/run.

```
4 leagues x 3 runs/day x ~30 days = 360 requests/month  <  500 free budget
```

Comfortably under the free cap, with headroom for occasional manual `workflow_dispatch`
runs. Off-season leagues simply return no games (still ~1 cheap request each). The
collector logs the `x-requests-remaining` header every run so you can watch the budget.
**Kalshi requests are public / no-auth and do NOT count against the odds quota.**

To poll more densely (e.g. every 5 min, the ideal for a clean lag cross-correlation),
upgrade to the-odds-api paid tier and add more cron lines -- the collector code is
unchanged, it just runs more often.

## 4. Where the data lands

Rows are committed to the **`gha-data`** branch under:

```
gha_data/sports_clv/sports_clv.csv
```

The workflow appends to the existing CSV every run (idempotent append; history is never
rewritten). Pull it for analysis:

```bash
git fetch origin gha-data
git checkout origin/gha-data -- gha_data/sports_clv/
```

CSV columns: `ts_iso, ts_epoch, league, sport_key, game_id, home_team, away_team, team,
pinnacle_fair_prob, pinnacle_hold, kalshi_ticker, kalshi_mid`.

## 5. Run the lag analysis (once ~300-500 games accrue)

The proof bar (same as the weather / Polymarket studies): a positive **realized CLV**
vs Kalshi settlement, net of cost, **out-of-sample**, over **>=300-500 games / several
weeks**. With the free tier that's roughly **3-6 weeks of in-season collection**.

Once enough has accrued:

1. Pull the CSV (step 4).
2. For each game, build the aligned per-minute series: `pinnacle_fair_prob` (forward-filled
   between polls) and `kalshi_mid`. After settlement, `kalshi_clv_lag.py` pulls the Kalshi
   1-minute candlesticks for the dense Kalshi side; the CSV supplies the timestamped
   Pinnacle side.
3. Compute `d(pinnacle_fair)` and `d(kalshi_mid)` per step and **cross-correlate at lags
   0..15 min**:
   - peak at **lag > 0** => Kalshi *follows* Pinnacle => capturable maker lag.
   - peak at **lag <= 0** or flat => Kalshi leads/coincident => *no* capturable lag.
4. Validate with realized maker CLV vs settlement, net of cost, out-of-sample.

```bash
# the analysis substrate (Kalshi-only backtest A + lag-harness design B):
python kalshi_clv_lag.py
```

> Local manual test of the collector (no key needed -- prints design, exits 0):
> ```bash
> python sports_clv_collect.py
> ```
