# Longshot-maker harvest — END-TO-END OPERATOR RUNBOOK

The one validated +EV Kalshi edge. This is the complete, deployable system: signal → paper-validate →
go-live → monitor. Read top to bottom before risking money.

## What the edge is (one paragraph)
On Kalshi's **soft, zero-maker-fee categories** (Politics, Climate/Weather, Entertainment, Science),
recreational buyers overpay for cheap YES **longshots** (mid 0.02–0.20). You are the **maker on the NO
side**: rest a passive NO-buy at the touch; when a longshot buyer/seller trades against you, you collect
the overpriced premium and win whenever the longshot does **not** hit. Validated at **+0.97¢/contract,
~17σ, net of adverse selection AND fee** over 263k real fills (`KALSHI_MAKER_ADVSEL.md`). It is
queue-independent (no HFT war on these thin books), maker-fee-free, with no fast-pickoff toxicity.
**It is also capacity-capped at ~$30–150/month** and has **negative skew** (collect ~1¢ often, lose ~95¢
when a longshot hits) — so it is *side income*, not the $500/mo goal (that stays the portfolio route).

## The components (all committed)
| File | Role |
|---|---|
| `kalshi_longshot_paper.py` | forward paper-track: snapshot longshots, settle them, log realized P&L (live on `main` daily → `gha-data/longshot/`) |
| `kalshi_longshot_report.py` | the go-live readout: realized forward edge, fill proxy, by-category, exposure |
| `kalshi_longshot_bot.py` | the LIVE maker bot: scans + rests maker NO-buys with hard safety caps (DRY-RUN by default) |
| `kalshi_maker_advsel.py` / `KALSHI_MAKER_ADVSEL.md` | the edge proof (adverse-selection-survival) |
| `kalshi_longshot_risk.py`→`KALSHI_LONGSHOT_RISK.md` | sizing / drawdown / min-bankroll |

## Phase 1 — PAPER (now → ~4–6 weeks). No money.
The paper-track is already running daily on `main`. To inspect it:
```
git fetch origin gha-data && git checkout origin/gha-data -- gha_data/longshot/
python kalshi_longshot_report.py gha_data/longshot
```
**GO-LIVE GATE — do not skip:** only proceed to real money when the report shows, on settled paper
positions: (1) realized edge **positive**, (2) **t ≥ 2** vs zero, and (3) the **fill-proxy** (volume
traded after our snapshot) is non-trivial — i.e., your resting quotes would actually have been lifted.
If fills are ~0, the edge is real but unreachable and you stop here (capacity wall).

## Phase 2 — GO LIVE (tiny). Only after the gate passes.
1. Get a Kalshi API key (Settings → API). Save the RSA private key file; note the key id.
2. Set env:
   ```
   export KALSHI_API_KEY_ID=...           # your key id
   export KALSHI_PRIVATE_KEY_PATH=/path/to/kalshi_key.pem
   export LONGSHOT_LIVE=1                  # 0 = dry-run (default); 1 = place real orders
   export LONGSHOT_CLIP=1                  # contracts/leg — START AT 1 (negative skew)
   export LONGSHOT_MAX_THEME=5             # cap exposure per event-theme (correlation guard)
   export LONGSHOT_MAX_NOTIONAL=200        # cap total collateral $ (start small)
   export LONGSHOT_MAX_POS=120             # cap # simultaneous positions
   ```
3. **Always dry-run first** (`LONGSHOT_LIVE=0`) and read what it WOULD place:
   ```
   python kalshi_longshot_bot.py
   ```
4. Go live, run once daily (cron or GitHub Actions). The bot is **maker-only** (`post_only`) so it never
   crosses/pays taker fees, and every order has a **23h venue-side TTL** (a dead process can't leave
   orders working). It skips tickers you already hold/quote and respects all three caps.

## Sizing / risk (from `KALSHI_LONGSHOT_RISK.md`)
- **Min bankroll:** $1k is plenty at CLIP=1 (tiny tail). Want ~$3–5k to push toward $150/mo at larger clips
  and ride the occasional −$1k tail month.
- **Ruin is ~impossible** at sane clips (max loss/position ≈ $0.88; fills, not capital, are the constraint).
- **Smooth the negative skew:** hold ≥300 independent fills/mo across **many uncorrelated event-themes**
  (the `MAX_THEME` cap enforces this). The only real risk is a macro surprise hitting many political
  longshots at once — keep per-theme exposure low.
- **Scale clips ONLY** after live fills confirm the edge; do not chase size — capacity is ~$30–150/mo and
  pushing harder just deepens the tail without adding edge.

## Monitoring & kill-switch
- Daily: `python kalshi_longshot_report.py <state_dir>` (or check fills/positions via the API).
- **Kill:** set `LONGSHOT_LIVE=0` (stops new orders); existing orders self-expire via TTL within 23h, or
  cancel manually. There is no leverage and no naked directional exposure beyond the held NO positions.

## Honest expectations
This is a **real, low-risk, automatable ~$30–150/mo side income**, capacity-capped and non-scaling. It is
the genuine answer to "is there a way to make money on Kalshi" — yes, a small one. The $500/mo objective
remains the trend-overlaid all-weather + convex-barbell portfolio (`PROJECT_VERDICT.md`).
