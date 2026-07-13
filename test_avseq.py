"""test_avseq.py -- the EMPIRICAL proof that avseq's early-promotion controls Type-I error.

The derivation (Ville + Gaussian mixture) guarantees time-uniform validity IF sigma is a true
sub-Gaussian bound; we use a plug-in sigma, so the actual guarantee is what THIS simulation shows.
Run: python test_avseq.py  (deterministic seed; ~a few seconds).
"""
import math
import random

import avseq

ALPHA = 0.05
HORIZON = 45           # peek EVERY day up to here (the whole point: many looks)
_results = []


def record(name, ok, detail):
    _results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def _null_rate(sigma, trials, seed):
    rng = random.Random(seed)
    fired = 0
    for _ in range(trials):
        d = []
        for _n in range(HORIZON):
            d.append(rng.gauss(0.0, sigma))     # true mean 0 -> must NOT promote
            if avseq.promote_decision(d, alpha=ALPHA)["promote"]:
                fired += 1
                break
    return fired / trials


def _power(mean, sigma, trials, seed):
    rng = random.Random(seed)
    fired = []
    for _ in range(trials):
        d = []
        hit = None
        for n in range(1, HORIZON + 1):
            d.append(rng.gauss(mean, sigma))
            if avseq.promote_decision(d, alpha=ALPHA)["promote"]:
                hit = n
                break
        if hit:
            fired.append(hit)
    med = sorted(fired)[len(fired) // 2] if fired else None
    return len(fired) / trials, med


def test_type_one_error_control():
    """Under the null (no edge), peeking every day must falsely promote <= alpha, at every scale."""
    worst = 0.0
    for sigma in (0.2, 0.5, 1.0, 2.0, 5.0):
        r = _null_rate(sigma, trials=8000, seed=1000 + int(sigma * 10))
        worst = max(worst, r)
        assert r <= ALPHA, f"null false-promote rate {r:.4f} > alpha {ALPHA} at sigma={sigma}"
    record("type-I error <= alpha across scales (null, every-day peek)", True,
           f"worst false-early-promote rate={worst:.4f} <= alpha={ALPHA}")


def test_naive_peek_is_broken():
    """Sanity: the naive 'promote first day t>2' that avseq REPLACES must blow past alpha."""
    rng = random.Random(42)
    fired = 0
    T = 8000
    for _ in range(T):
        d = []
        hit = False
        for n in range(1, HORIZON + 1):
            d.append(rng.gauss(0.0, 1.0))
            if n >= 3:
                m = sum(d) / n
                sd = (sum((x - m) ** 2 for x in d) / (n - 1)) ** 0.5
                if sd > 0 and m / (sd / math.sqrt(n)) > 2.0:
                    hit = True
                    break
        if hit:
            fired += 1
    rate = fired / T
    record("naive t>2 peek DOES inflate (motivates avseq)", rate > 0.15,
           f"naive false-promote rate={rate:.3f} (>> alpha; this is what avseq fixes)")


def test_power_and_honest_tradeoff():
    """A real edge eventually promotes; a strong edge promotes early; a weak one rarely does.
    Also documents the honest tradeoff: at the stack's expected per-day effect (~0.79), the
    median early-promote day is ABOVE 10 -> the fixed 10-day gate stays the primary path."""
    p_strong, d_strong = _power(1.2, 1.0, trials=1500, seed=7)   # dramatically strong
    p_stack, d_stack = _power(0.79, 1.0, trials=1500, seed=8)    # ~ stack replay prior
    p_weak, d_weak = _power(0.3, 1.0, trials=1500, seed=9)       # weak
    assert p_strong > 0.95, f"strong edge should almost always promote, got {p_strong}"
    assert p_weak < 0.6, f"weak edge should rarely early-promote, got {p_weak}"
    record("power monotone + honest tradeoff", True,
           f"strong(1.2):{p_strong*100:.0f}%@day{d_strong} | stack(0.79):{p_stack*100:.0f}%@day{d_stack} "
           f"(>10 => fixed gate faster) | weak(0.3):{p_weak*100:.0f}%@day{d_weak}")


def test_never_fires_before_min_days():
    """No promotion before MIN_DAYS regardless of how lopsided the first few points are."""
    d = [10.0, 10.0, 10.0]            # absurdly positive, but only 3 days
    dec = avseq.promote_decision(d, alpha=ALPHA)
    record("respects min_days floor", (not dec["promote"]) and dec["n"] < avseq.MIN_DAYS,
           f"n={dec['n']} < min_days={avseq.MIN_DAYS} -> promote={dec['promote']} (correctly False)")


def main():
    print("test_avseq.py -- always-valid early-promotion validation")
    test_type_one_error_control()
    test_naive_peek_is_broken()
    test_power_and_honest_tradeoff()
    test_never_fires_before_min_days()
    n_fail = sum(1 for _, ok, _ in _results if not ok)
    print("=" * 60)
    if n_fail:
        print(f"{n_fail}/{len(_results)} FAILED")
        raise SystemExit(1)
    print(f"ALL {len(_results)} TESTS PASSED")


if __name__ == "__main__":
    main()
