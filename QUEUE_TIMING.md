# Queue-timing experiment — beat the mechanical ladder-MM to the new price level

## The thesis (from FINGERPRINT.md)
The dominant counterparty is a MECHANICAL ladder-MM: fixed per-level size (265 YES/250 NO), ~1.2s
heartbeat, cancel/add~=1.0, and **74% of its quotes are still stale 3s after a >0.1% spot move.**
Every prior analysis says QUEUE POSITION is the first-order edge (directional prediction is dead,
7 nulls). So the one new actionable item: when the touch is about to move, re-quote to the new level
FASTER than the MM's 1.2s heartbeat -> front-of-queue at the right price.

## The flaw it fixes
The trader's reshape guard waits **2.0s** before re-quoting an off-target rung ("don't churn"). That
is SLOWER than the MM's 1.2s cycle -- we were forfeiting the priority. The experiment bypasses the
2s guard WHEN MICROPRICE CONFIRMS the move is real (|microprice - mid| >= margin), so we don't churn
on noise but DO jump when the touch is genuinely shifting.

## Implementation (flagged, default OFF -- not in the durable GHA bot)
`--qtime-mp-margin X` (default 0.0=off). On an off-target rung, if |mp - mid| >= X, reshape NOW
instead of at age>=2s. Telemetry: per-window `qtime=` count in the OPS line; cancel reason
`reshape_qtime`. Threshold note: on a 1c-spread book |mp-mid| maxes ~0.005, so X must be SUB-CENT
(experiment uses 0.003).

## Measurement (single-trader constraint: can't A/B two live traders on one account)
Run the LOCAL loop with the flag ON; the durable GHA bot stays baseline (off). Compare to the frozen
baseline: **5s markout ~= -0.5c/fill, fill p90 ~3s, reject ~0**. SUCCESS = the 5s markout curve moves
toward 0/positive AND fill-rate holds AND qtime-requotes actually fire (qtime>0/window) without a
reject storm. FAIL = markout worse or churn (rejects) spikes -> revert (flag off). Decision after
~a day of fills (a few hundred markout-scored).
RISK: low -- same prices, same $5 cap, only TIMING changes; the reject-cooldown breaker caps churn.
