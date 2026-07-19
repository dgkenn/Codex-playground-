#!/usr/bin/env python3
"""sizing.py -- TAIL-FIRST position sizing for the multi-strategy bot (node MULTISTRAT-PROGRAM).

The edges are SHORT-VOL RISK PREMIA: steady small wins, rare correlated blow-ups. So sizing must be
tail-first, not mean-first. Given a bankroll and the open paper positions per sleeve, this proposes
per-position contract sizes under hard nested caps:
  - per-TRADE worst-case loss <= RISK_PER_TRADE * bankroll
  - per-EVENT worst-case loss <= EVENT_CAP * bankroll   (bucket events: only one outcome prints, but cap anyway)
  - per-SLEEVE deployed risk    <= SLEEVE_CAP * bankroll  (scaled by risk-parity weight from portfolio.py)
  - per-WEEK aggregate worst-case (if EVERY open short printed at once) <= WEEKLY_BUDGET * bankroll
and scales within those caps by fractional-Kelly on the edge estimate. Selling a longshot YES at price p:
worst-case loss/contract = (1 - p) (it prints); premium kept = p (it doesn't). PROPOSE-ONLY: outputs
proposed sizes; it NEVER places an order or touches live capital without operator authorization.

Usage: python sizing.py [bankroll]   (default 1000 paper units)
"""
import json, os, sys
from collections import defaultdict

# confirmed live sleeves -> (open_positions_jsonl, entry_price_field, event_field, kelly_frac, edge_per_ct)
# edge_per_ct = backtest mean PnL/contract at realistic fills (crypto 0.090, econ 0.069). Kelly frac deliberately low.
SLEEVES = {
    "pmkt_shortvol": ("pmkt_shortvol_positions.jsonl", "sell_price", "market_id", 0.25, 0.090),
    "pmkt_econ":     ("pmkt_econ_positions.jsonl",     "sell_price", "event",     0.20, 0.069),
    "pmkt_biz":      ("pmkt_biz_positions.jsonl",      "sell_price", "event",     0.10, 0.050),  # smallest: marginal + capacity-ltd
}
RISK_PER_TRADE = 0.005    # <=0.5% of bankroll worst-case on any single short
EVENT_CAP      = 0.010    # <=1% per event
SLEEVE_CAP     = 0.15     # <=15% deployed worst-case risk per sleeve (econ scaled lower via its kelly_frac)
WEEKLY_BUDGET  = 0.20     # <=20% of bankroll if EVERY open short printed simultaneously (the corr-blowup guard)


def _load(fn):
    out = []
    if os.path.exists(fn):
        with open(fn) as f:
            for l in f:
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    return out


def _settled_ids():
    done = set()
    for s in ("pmkt_shortvol_settled.jsonl", "pmkt_econ_settled.jsonl"):
        for r in _load(s):
            done.add(r.get("market_id"))
    return done


def main():
    bankroll = float(sys.argv[1]) if len(sys.argv) > 1 else 1000.0
    done = _settled_ids()
    print(f"TAIL-FIRST SIZING PROPOSAL  (bankroll={bankroll:.0f}, PROPOSE-ONLY, no orders)")
    print(f"caps: trade<= {RISK_PER_TRADE:.1%}  event<= {EVENT_CAP:.1%}  sleeve<= {SLEEVE_CAP:.0%}  "
          f"week-if-all-print<= {WEEKLY_BUDGET:.0%}\n")
    grand_wc = 0.0
    grand_prem = 0.0
    for sname, (posf, pf, evf, kfrac, edge) in SLEEVES.items():
        opens = [p for p in _load(posf) if p.get("market_id") not in done]
        if not opens:
            print(f"[{sname}] no open positions")
            continue
        sleeve_risk_cap = SLEEVE_CAP * bankroll
        per_event_risk = defaultdict(float)
        rows = []
        sleeve_wc = 0.0
        for p in opens:
            price = float(p[pf])
            wc_per_ct = (1.0 - price)                 # worst-case $ loss per contract if it prints
            if wc_per_ct <= 0:
                continue
            # fractional-Kelly notional target from the edge (edge/variance proxy ~ edge/(p(1-p)))
            kelly_ct = kfrac * (edge / (price * (1 - price))) * (bankroll / max(wc_per_ct, 0.01))
            # nested hard caps (contracts)
            cap_trade = (RISK_PER_TRADE * bankroll) / wc_per_ct
            cap_event = (EVENT_CAP * bankroll - per_event_risk[p.get(evf)]) / wc_per_ct
            cap_sleeve = (sleeve_risk_cap - sleeve_wc) / wc_per_ct
            size = max(0, int(min(kelly_ct, cap_trade, cap_event, max(cap_sleeve, 0))))
            if size <= 0:
                continue
            wc = size * wc_per_ct
            per_event_risk[p.get(evf)] += wc
            sleeve_wc += wc
            rows.append((p.get("question", p.get("market_id"))[:48], price, size, wc, size * price))
        prem = sum(r[4] for r in rows)
        print(f"[{sname}] {len(rows)} sized positions | worst-case risk=${sleeve_wc:.2f} "
              f"({sleeve_wc/bankroll:.1%}) | premium collected=${prem:.2f}")
        for q, price, size, wc, pr in rows[:8]:
            print(f"    sell {size:4d} @ {price:.2f}  wc_loss=${wc:6.2f}  prem=${pr:6.2f}  {q}")
        if len(rows) > 8:
            print(f"    ... +{len(rows)-8} more")
        grand_wc += sleeve_wc
        grand_prem += prem
    print(f"\nPORTFOLIO: worst-case-if-all-print=${grand_wc:.2f} ({grand_wc/bankroll:.1%} of bankroll) "
          f"vs WEEKLY_BUDGET {WEEKLY_BUDGET:.0%}  |  premium at risk=${grand_prem:.2f}")
    if grand_wc > WEEKLY_BUDGET * bankroll:
        print("  ** exceeds weekly budget -> scale all sizes down pro-rata before deploying **")
    print("  (uncorrelated sleeves => simultaneous all-print is unlikely; this is the conservative bound.)")


if __name__ == "__main__":
    main()
