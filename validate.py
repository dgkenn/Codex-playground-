"""Validate the fair-value model on synthetic GBM windows BEFORE touching real data.

We generate many independent 15-minute windows of driftless geometric Brownian
motion with a known per-second sigma, ask the model for p_up at random instants
inside each window, and check that the predictions are calibrated against the
realized outcomes.

Pass criteria (printed PASS/FAIL):
  * expected calibration error (ECE) ~ 0.01  (model is well calibrated)
  * mean p_up at the window open ~ 0.50       (no opinion pre-window)
"""
from __future__ import annotations

import numpy as np

from fairvalue import fair_up

WINDOW_S = 900
SIGMA = 0.0004            # per-second vol of log spot (~1.2%/hour, realistic for BTC)
N_WINDOWS = 40_000
SEED = 7


def main():
    rng = np.random.default_rng(SEED)

    # Simulate each window as a single Brownian bridge sample: we only need the
    # increment from open->t and t->close, which are independent Gaussians.
    s0 = 100.0
    # Pick a random evaluation time t in each window (seconds since open).
    t = rng.integers(1, WINDOW_S, size=N_WINDOWS).astype(float)
    tau = WINDOW_S - t

    # log move open->t  and  t->close (driftless, var = sigma^2 * seconds)
    move_to_t = rng.normal(0.0, SIGMA * np.sqrt(t))
    move_to_close = rng.normal(0.0, SIGMA * np.sqrt(tau))

    st = s0 * np.exp(move_to_t)
    sclose = st * np.exp(move_to_close)
    outcome_up = (sclose > s0).astype(float)

    p = fair_up(st, s0, SIGMA, tau)

    # Expected calibration error over probability deciles.
    bins = np.linspace(0.0, 1.0, 11)
    idx = np.clip(np.digitize(p, bins) - 1, 0, 9)
    ece = 0.0
    for b in range(10):
        m = idx == b
        if not m.any():
            continue
        ece += (m.mean()) * abs(p[m].mean() - outcome_up[m].mean())

    # Mean p at the open: tau == WINDOW_S, st == s0 -> exactly 0.5.
    p_open = fair_up(np.full(2000, s0), s0, SIGMA, WINDOW_S)
    pre_window = float(np.mean(p_open))

    brier = float(np.mean((p - outcome_up) ** 2))

    print("=== validate.py : fair-value calibration on synthetic GBM ===")
    print(f"  windows                : {N_WINDOWS}")
    print(f"  sigma (per-second)     : {SIGMA}")
    print(f"  calibration error (ECE): {ece:.4f}   (target ~0.01)")
    print(f"  pre-window mean p_up   : {pre_window:.4f}   (target ~0.50)")
    print(f"  Brier score            : {brier:.4f}")

    ok_ece = ece < 0.02
    ok_pre = abs(pre_window - 0.50) < 0.01
    ok = ok_ece and ok_pre
    print(f"  RESULT: {'PASS' if ok else 'FAIL'}"
          f" (ECE {'ok' if ok_ece else 'BAD'}, pre-window {'ok' if ok_pre else 'BAD'})")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
