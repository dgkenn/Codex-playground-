# Bet sizing for the longshot-maker harvest — Sharpe-optimal analysis (2026-06-21)

Answers "have we fully investigated bet sizing for max Sharpe?" — now we have. Grounded in the optimized
band p∈[0.05,0.15): buy NO at ~0.90; per contract **+11.1% on collateral if the longshot misses (prob 0.954),
−100% if it hits (0.046)** — a +5.45c/contract edge with hard negative skew. MC in `kalshi_longshot_sizing.py`.

## The three findings (each proven by the sim)

### 1. Sharpe is set by DIVERSIFICATION, not bet size. Sharpe ≈ √(independent event-themes).
| independent themes | 5 | 20 | 50 | 100 | 200 | 400 |
|---|---|---|---|---|---|---|
| annualized Sharpe | 1.5 | 3.1 | 4.8 | 6.9 | 9.6 | 13.7 |

Spreading across more *uncorrelated* themes is the entire Sharpe lever. This is the single most important
sizing decision — and it's a *diversification* decision, not a *size* decision.

### 2. Sharpe is ~SCALE-INVARIANT in leverage. Bet size sets GROWTH & RUIN, not Sharpe.
At 100 themes, varying deployed fraction L: Sharpe stays ~6.8 across L=0.1→2.0, while CAGR goes 6%→213%.
**Multiplying every bet by a constant changes mean and vol together → same Sharpe.** So "size bets to maximize
Sharpe" is the wrong frame: size sets how fast you grow and how close to ruin, *not* your risk-adjusted ratio.

### 3. CORRELATION kills Sharpe. Clustering bets into few themes halves it.
| layout (themes × bets) | 100×1 | 50×2 | 20×5 | 10×10 | 4×25 |
|---|---|---|---|---|---|
| Sharpe | 6.8 | 6.3 | 5.2 | 4.2 | 3.1 |

Many bets in one theme = one correlated shock sinks them together. Cap bets per theme; treat same-day /
same-macro events as correlated.

## So how do you actually size it?
- **To MAX Sharpe: maximize the number of UNCORRELATED event-themes you quote, ~1–2 bets per theme.** Tight
  per-theme caps + breadth, not big clips. (Capacity bounds the achievable theme count — realistically 20–100
  on thin soft markets → Sharpe ~3–7, not 13.)
- **To set the SCALE: use fractional-Kelly, not Sharpe-max.** Sharpe is blind to the −90c tail; a Sharpe-maximizer
  would over-deploy. Deploy only **~25–50% of bankroll** in live collateral at once (rest in reserve) — half-Kelly,
  because (a) the model UNDERSTATES correlated-tail risk (it blows themes up independently; a real market-wide
  shock hits many at once), (b) Kelly for negative skew sits BELOW the Gaussian optimum. On Kalshi you can't lever
  (L≤1 = cash), so the lever is "fraction of bankroll deployed vs held in reserve."
- **Equal-weight tiny clips** (1 contract). Bigger clips don't raise Sharpe (finding 2) and just deepen the tail.

## Translated to the bot
| Knob | Sharpe-optimal | why |
|---|---|---|
| `LONGSHOT_MAX_THEME` | **lowered default 5 → 3** | tighter per-theme cap = more independent themes = higher Sharpe (finding 1/3) |
| `LONGSHOT_CLIP` | 1 (unchanged) | size is scale-invariant for Sharpe; tiny clips bound the tail |
| `LONGSHOT_MAX_NOTIONAL` | **set to ~25–50% of bankroll** | fractional-Kelly scale; keep reserve for the correlated tail |
| breadth | maximize distinct series quoted | the achievable-Sharpe driver |

## Honest caveats
- Sharpe 3–7 assumes the +5.45c edge holds forward (paper-track will confirm) AND bets are truly uncorrelated.
- The model understates correlated macro tails → use MORE reserve (lower deployed fraction) than it suggests.
- This is high Sharpe on a SMALL absolute book — the ~$30–150/mo capacity cap (`KALSHI_MAKER_CAPACITY.md`) is
  unchanged. Great risk-adjusted quality on a small sleeve; not a path to $500/mo.
