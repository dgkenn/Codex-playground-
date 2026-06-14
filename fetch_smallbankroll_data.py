#!/usr/bin/env python3
"""Stage data for the small-bankroll execution-realism study (NON-repo).

We need TWO price matrices:
  * ADJUSTED closes (auto_adjust=True, total-return)  -> signals + idealized
    fractional backtest (identical math to etf_momentum.py).
  * RAW closes (auto_adjust=False, "Close")           -> the ACTUAL share price
    you pay per share, used for whole-share rounding at each rebalance.

Both are saved to /tmp/etfsmall_data (NOT committed).
"""
import os
import sys
import time
import numpy as np
import pandas as pd

OUT = "/tmp/etfsmall_data"
os.makedirs(OUT, exist_ok=True)

SECTORS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB"]
STYLE = ["SPY", "QQQ", "IWM", "MTUM"]
INTL = ["EFA", "EEM", "EWJ", "EWZ", "EWG", "EWU", "FXI", "VGK"]
ASSETS = ["TLT", "IEF", "GLD", "DBC", "USO", "VNQ", "UUP", "SLV", "HYG", "LQD"]
CASH = ["BIL", "SHY"]
# cheaper-ETF substitution candidates (lower share price, ~same exposure)
CHEAPER = ["SCHB", "SCHX", "VTI", "SPLG", "VOO",  # broad/large (SPLG~$70 vs SPY~$600)
           "SCHF", "SCHE", "VEA", "VWO",          # intl dev/emer (cheap vs EFA/EEM)
           "SCHP", "VGIT", "VGLT", "BND",         # bonds cheap
           "IAU", "SGOL",                          # cheap gold (IAU~$60 vs GLD~$300)
           "VPU", "VDE", "VFH", "VHT", "VGT",     # vanguard sectors (often cheaper)
           "SGOV"]                                  # cheap T-bill cash (~$100)

ALL = sorted(set(SECTORS + STYLE + INTL + ASSETS + CASH + CHEAPER))


def fetch(auto_adjust, label):
    import yfinance as yf
    print(f"[fetch] {label} (auto_adjust={auto_adjust}) {len(ALL)} tickers ...")
    raw = yf.download(ALL, start="1998-01-01", auto_adjust=auto_adjust,
                      progress=False, threads=True)
    close = raw["Close"]
    close = close.dropna(how="all").sort_index()
    return close


def main():
    for attempt in range(4):
        try:
            adj = fetch(True, "adjusted")
            raw = fetch(False, "raw")
            break
        except Exception as e:
            print(f"[warn] attempt {attempt}: {e!r}", file=sys.stderr)
            time.sleep(2 ** attempt)
    else:
        print("[error] could not fetch", file=sys.stderr)
        return 1

    adj.to_csv(os.path.join(OUT, "adj_prices.csv"))
    raw.to_csv(os.path.join(OUT, "raw_prices.csv"))
    print(f"[ok] adj {adj.shape} {adj.index.min().date()}..{adj.index.max().date()}")
    print(f"[ok] raw {raw.shape}")
    # quick sanity: latest raw share prices for the core set
    core = sorted(set(SECTORS + STYLE + INTL + ASSETS))
    last = raw[core].ffill().iloc[-1].sort_values(ascending=False)
    print("\nLatest RAW share prices (core, high->low):")
    print(last.round(2).to_string())
    print("\nLatest RAW share prices (cheaper candidates):")
    ch = [c for c in CHEAPER if c in raw.columns]
    print(raw[ch].ffill().iloc[-1].sort_values(ascending=False).round(2).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
