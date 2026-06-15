#!/usr/bin/env python3
"""sports_arb_econ.py -- arbitrage/middle economics for (a) cross-US-book sure betting
and (b) Kalshi-vs-sportsbook locks, for SPORTS_ARB.md.

No paid feed needed. This is a CLOSED-FORM cost model, not a live scanner: it computes,
for each structure, the gross edge a price divergence must show before it clears the full
friction stack (both spreads + Kalshi quadratic fee + book vig), and the realistic net.

Kalshi taker fee per contract (dollars): ceil(0.07 * P * (1-P) * 100) / 100, maker = 0.
A buy-and-hold-to-settlement Kalshi position pays the taker fee ONCE (settlement is free).

Run: python3 sports_arb_econ.py
"""
from __future__ import annotations
import math


def kalshi_taker_fee(p: float) -> float:
    """Kalshi taker fee per $1 contract, in dollars, at YES price p (0..1)."""
    return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def american_to_decimal(a: int) -> float:
    return 1 + (a / 100.0 if a > 0 else 100.0 / -a)


def decimal_to_imp(dec: float) -> float:
    return 1.0 / dec


# ---------------------------------------------------------------------------
# (a) CROSS-BOOK 2-WAY ARBITRAGE
# ---------------------------------------------------------------------------
def cross_book_arb(dec_a: float, dec_b: float) -> dict:
    """Two opposite outcomes at two books, decimal odds dec_a, dec_b.
    Arb exists iff 1/dec_a + 1/dec_b < 1. Return the arb % and stake split."""
    inv = 1.0 / dec_a + 1.0 / dec_b
    arb_pct = (1.0 / inv - 1.0) * 100.0  # guaranteed return on total stake
    return dict(inv_sum=inv, arb=inv < 1.0, return_pct=arb_pct)


# ---------------------------------------------------------------------------
# (b) KALSHI vs SPORTSBOOK lock / middle
# ---------------------------------------------------------------------------
def kalshi_vs_book_lock(p_book_fair: float, kalshi_yes_ask: float) -> dict:
    """Buy YES on Kalshi at `kalshi_yes_ask` (cents/100), where a de-vigged book fair
    prob for the same event is `p_book_fair`. You'd hedge the other side at the book.
    The *gross* edge if you could trade both at fair = p_book_fair - kalshi_yes_ask.
    Net must beat Kalshi taker fee at that price (book side assumed taken at its line)."""
    fee = kalshi_taker_fee(kalshi_yes_ask)
    gross = p_book_fair - kalshi_yes_ask
    net = gross - fee
    return dict(gross_cents=gross * 100, fee_cents=fee * 100, net_cents=net * 100,
                clears=net > 0)


def hurdle_table():
    print("=" * 72)
    print("KALSHI TAKER FEE by price (per $1 contract) -- the un-bannable leg's cost")
    print("=" * 72)
    print(f"{'YES price':>10} {'fee (c)':>9} {'fee bps':>9}")
    for p in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
        f = kalshi_taker_fee(p)
        print(f"{p*100:>9.0f}c {f*100:>8.2f}c {f/p*1e4:>8.0f}")
    print("\nNote: fee peaks at 0.50 (1.75c) and shrinks toward the tails (~0.7-1.1c).")


def cross_book_demo():
    print("\n" + "=" * 72)
    print("(a) CROSS-BOOK ARB: does a 2-way line pair lock a profit?")
    print("=" * 72)
    # Typical mainline -110/-110 at one book = no arb (4.5% hold). Need books to disagree.
    cases = [
        ("Both books -110 (mainline, same)", -110, -110),
        ("Book A +102 / Book B -100 (mild disagree)", 102, -100),
        ("Book A +105 / Book B -102 (real small arb)", 105, -102),
        ("Book A +115 / Book B -105 (juicy/rare)", 115, -105),
    ]
    print(f"{'scenario':<42} {'1/da+1/db':>10} {'arb?':>5} {'ret%':>7}")
    for name, a, b in cases:
        da, db = american_to_decimal(a), american_to_decimal(b)
        r = cross_book_arb(da, db)
        print(f"{name:<42} {r['inv_sum']:>10.4f} {str(r['arb']):>5} {r['return_pct']:>6.2f}%")
    print("\nReality: most arbs are 0.5-2.5%/turnover; >3% is rare/stale/limited-stake.")


def kalshi_lock_demo():
    print("\n" + "=" * 72)
    print("(b) KALSHI-vs-BOOK LOCK: gross divergence vs Kalshi fee hurdle")
    print("=" * 72)
    print(f"{'p_book_fair':>11} {'k_ask':>7} {'gross':>7} {'fee':>6} {'net':>7} {'clears?':>8}")
    # Pair a de-vigged book fair prob with a Kalshi YES ask; vary the divergence.
    rows = [
        (0.55, 0.55),  # in line: no edge
        (0.55, 0.53),  # 2c gap
        (0.55, 0.51),  # 4c gap
        (0.55, 0.49),  # 6c gap
        (0.55, 0.45),  # 10c gap (illiquid only)
    ]
    for pf, ka in rows:
        r = kalshi_vs_book_lock(pf, ka)
        print(f"{pf*100:>10.0f}c {ka*100:>6.0f}c {r['gross_cents']:>6.1f}c "
              f"{r['fee_cents']:>5.2f}c {r['net_cents']:>6.1f}c {str(r['clears']):>8}")
    print("\nBut a LOCK also needs the BOOK leg taken at its (vigged) price + that side's")
    print("half-spread. A true risk-free lock requires: p_book_lay_price + k_ask < 1 - fees.")


def lock_with_book_vig():
    print("\n" + "=" * 72)
    print("(b') TRUE RISK-FREE LOCK incl. BOTH legs' real prices (not fair):")
    print("    Buy YES_team_A on Kalshi @ ka ; Bet team_B at book @ american odds ob.")
    print("    Lock iff   ka + book_stake_frac < 1, net of Kalshi fee.")
    print("=" * 72)
    # To cover $1 Kalshi YES_A payout you bet team_B at the book. If A wins: Kalshi pays
    # $1, book bet lost. If B wins: book pays, Kalshi YES_A = $0. Lock if total outlay < $1.
    # book_cost_per_$1_payout = 1/dec_b ; total cost = ka + (ka_payout_to_cover)/dec_b...
    # Simplest equivalent: implied prob you "buy" on each side must sum < 1 - fee.
    print(f"{'k_ask(A)':>9} {'book B':>8} {'imp_B':>7} {'sum':>7} {'fee':>6} {'lock?':>7} {'ret%':>7}")
    cases = [
        (0.55, -110),  # book B -110 => imp .524 ; sum 1.074 no
        (0.48, +110),  # book B +110 => imp .476 ; sum .956 -> lock pre-fee
        (0.45, +130),  # book B +130 => imp .435 ; sum .885 -> juicy
        (0.50, +105),  # book B +105 => imp .488 ; sum .988 -> marginal
    ]
    for ka, ob in cases:
        imp_b = decimal_to_imp(american_to_decimal(ob))
        s = ka + imp_b
        fee = kalshi_taker_fee(ka)
        lock = (s + fee) < 1.0
        ret = (1.0 / (s + fee) - 1.0) * 100 if lock else (1.0 - (s + fee)) * 100
        print(f"{ka*100:>8.0f}c {ob:>+8d} {imp_b:>7.3f} {s:>7.3f} {fee*100:>5.2f}c "
              f"{str(lock):>7} {ret:>6.2f}%")
    print("\nLock needs k_ask + book_implied + Kalshi_fee < 1.0 (book vig already in book_implied).")
    print("Because liquid Kalshi == sharp consensus (overround ~0), and the book carries 4-5%")
    print("vig, the sum is almost always > 1 on LIQUID games. Locks appear only when a book is")
    print("STALE/soft (off-market) -- the same soft-book pricing error that gets you LIMITED.")


if __name__ == "__main__":
    hurdle_table()
    cross_book_demo()
    kalshi_lock_demo()
    lock_with_book_vig()
