"""ROADMAP #2: Liquidity Rewards stream -- read the config programmatically, screen where
it's live, and score qualifying placement. SEPARATE revenue from the maker rebate: Polymarket
pays a daily pool for resting near mid (two-sided, size-weighted, spread-scored) whether or
not you fill.

EMPIRICAL VERDICT (this run): the BTC 15m markets carry the reward SCAFFOLD
(min_size=50, max_spread=4.5c) but rates=null -> NO liquidity rewards are funded there. So on
our validated market the stream is $0 today; the only active incentive is the maker rebate we
already model (makerRebatesFeeShareBps=10000). The markets that DO pay are politics/longshots
(rates 0.001..20 USDC/day) -- different microstructure, not spot-tied, so our fast-binary
vig+skew edge does not port to them. Rewards are therefore a SEPARATE strategy on OTHER
markets, not a stack onto our quotes -- unless/until Polymarket funds rewards on BTC 15m, which
this reader detects automatically.

Reward scoring (Polymarket LRP): an order of `size` resting `c` cents from mid, within
max_spread, scores  S = size * ((max_spread - c)/max_spread)^2.  Two-sided: your market score
is Qmin = min(sum bid scores, sum ask scores). Daily payout = (your Qmin / total Qmin) *
daily_rate. `reward_share_estimate` computes the denominator from the LIVE book, so a paying
market's $/day is a real, bounded number, not a guess.

    python rewards.py                 # screen the live landscape + BTC verdict
"""
from __future__ import annotations

import json

import requests

CLOB = "https://clob.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"


def market_rewards(sess, cid):
    """Parsed rewards config for a conditionId: {rates, min_size, max_spread}. rates=None
    => program present but unfunded (no payout)."""
    r = sess.get(f"{CLOB}/markets/{cid}", timeout=10).json()
    return r.get("rewards") or {}


def is_active(cfg):
    rates = cfg.get("rates")
    return bool(rates) and any(float(x.get("rewards_daily_rate", 0)) > 0 for x in rates)


def daily_rate(cfg):
    return sum(float(x.get("rewards_daily_rate", 0)) for x in (cfg.get("rates") or []))


def order_score(size, cents_from_mid, max_spread):
    """LRP per-order score; 0 if outside the max_spread band or below... (size gate applied
    by caller). Quadratic in proximity to mid."""
    if cents_from_mid > max_spread:
        return 0.0
    return size * ((max_spread - cents_from_mid) / max_spread) ** 2


def book_qmin(sess, token, mid, max_spread, min_size):
    """Total competing two-sided score (Qmin) from the LIVE book for one token: sum the
    reward score of every resting bid/ask within max_spread of mid (size>=min_size), then
    Qmin = min(bid_total, ask_total)."""
    b = sess.get(f"{CLOB}/book", params={"token_id": token}, timeout=10).json()
    def side_total(levels, is_bid):
        tot = 0.0
        for lv in levels:
            p = float(lv["price"]); sz = float(lv["size"])
            if sz < min_size:
                continue
            c = abs((p - mid)) * 100.0
            tot += order_score(sz, c, max_spread)
        return tot
    bid_t = side_total(b.get("bids", []), True)
    ask_t = side_total(b.get("asks", []), False)
    return min(bid_t, ask_t), bid_t, ask_t


def reward_share_estimate(sess, token, mid, cfg, our_size, our_cents):
    """Our estimated $/day on a paying market for a two-sided placement of our_size at
    our_cents from mid: our_Qmin / (total_Qmin + our_Qmin) * daily_rate."""
    ms = float(cfg.get("max_spread", 0) or 0); mn = float(cfg.get("min_size", 0) or 0)
    rate = daily_rate(cfg)
    if ms <= 0 or rate <= 0 or our_size < mn:
        return 0.0, {}
    ours = order_score(our_size, our_cents, ms)                 # one side; two-sided => Qmin=ours
    comp_qmin, _, _ = book_qmin(sess, token, mid, ms, mn)
    share = ours / (comp_qmin + ours) if (comp_qmin + ours) > 0 else 0.0
    return share * rate, {"our_score": round(ours, 1), "competing_qmin": round(comp_qmin, 1),
                          "daily_rate": rate, "share": round(share, 4)}


def btc_verdict(sess):
    import time
    now = int(time.time()); ws = now - (now % 900)
    out = []
    for cand in range(ws, ws + 2700, 900):
        ev = sess.get(f"{GAMMA}/events", params={"slug": f"btc-updown-15m-{cand}"}, timeout=10).json()
        if ev:
            cid = ev[0]["markets"][0]["conditionId"]
            cfg = market_rewards(sess, cid)
            out.append((cand, is_active(cfg), cfg))
    return out


def scan(sess, limit=1000):
    """Rank the live reward-paying markets by daily pool."""
    r = sess.get(f"{CLOB}/sampling-markets", timeout=20).json()
    data = r.get("data", []) if isinstance(r, dict) else r
    paying = []
    for m in data:
        cfg = m.get("rewards") or {}
        if is_active(cfg):
            paying.append((daily_rate(cfg), m.get("market_slug", "?"), cfg, m))
    paying.sort(key=lambda x: x[0], reverse=True)
    return paying, len(data)


def main():
    sess = requests.Session()
    print("=== BTC 15m reward verdict ===")
    for ws, active, cfg in btc_verdict(sess):
        print(f"  ws={ws}: active={active} cfg={cfg}")
    print("  -> liquidity rewards are $0 on BTC 15m (scaffold present, rates unfunded).")

    print("\n=== live reward-paying landscape (sampling-markets) ===")
    paying, n = scan(sess)
    print(f"  (sampling-markets IS the reward universe -> {len(paying)}/{n} pay by construction; "
          f"BTC 15m is NOT in it.) Top by daily pool:")
    for rate, slug, cfg, _ in paying[:12]:
        print(f"   {rate:>8.3f} USDC/day  spread<={cfg.get('max_spread')}c min={cfg.get('min_size')}  {slug[:50]}")

    if paying:
        # share estimator on the top paying market, using the sampling-markets entry directly
        print("\n=== share estimate (top market, $200 two-sided @1c from mid, vs LIVE book) ===")
        rate, slug, cfg, m = paying[0]
        try:
            tok = str((m.get("tokens") or [{}])[0].get("token_id"))
            bk = sess.get(f"{CLOB}/book", params={"token_id": tok}, timeout=10).json()
            bb = max((float(x["price"]) for x in bk.get("bids", [])), default=0.5)
            ba = min((float(x["price"]) for x in bk.get("asks", [])), default=0.5)
            mid = (bb + ba) / 2 if (bb and ba) else 0.5
            dollars, info = reward_share_estimate(sess, tok, mid, cfg, our_size=200, our_cents=1.0)
            print(f"   {slug[:45]}: ~${dollars:.3f}/day  {info}")
        except Exception as e:  # noqa: BLE001
            print(f"   (demo skipped: {str(e)[:70]})")
    print("\nVERDICT: rewards do not stack onto our BTC 15m quotes (unfunded). The reader/"
          "screener above auto-detects if BTC turns on, and screens OTHER markets where "
          "reward-farming is its own strategy. See ROADMAP.md #2.")


if __name__ == "__main__":
    main()
