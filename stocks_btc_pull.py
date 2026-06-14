"""Pull daily + hourly data for the stocks->BTC lead-lag study.

Staged to /tmp/spbtc_data (NON-repo). yfinance daily (full) and hourly (~730d cap).
"""
import os
import time
import pandas as pd
import yfinance as yf

OUT = "/tmp/spbtc_data"
os.makedirs(OUT, exist_ok=True)

UNIVERSE = [
    "BTC-USD",
    # crypto proxies
    "MSTR", "COIN", "RIOT", "MARA", "CLSK", "IBIT", "GBTC",
    # tech / risk-on
    "QQQ", "SOXX", "ARKK", "SPY", "IWM",
    # macro
    "UUP", "TLT", "GLD", "HYG", "^VIX",
]


def fetch(tickers, period, interval, fname):
    for attempt in range(4):
        try:
            df = yf.download(
                tickers, period=period, interval=interval,
                auto_adjust=True, progress=False, threads=True,
            )
            if df is None or len(df) == 0:
                raise RuntimeError("empty")
            # Use Close panel
            close = df["Close"].copy()
            close.to_csv(os.path.join(OUT, fname))
            print(f"{fname}: {close.shape} {close.index.min()} -> {close.index.max()}")
            print("  cols:", list(close.columns))
            return close
        except Exception as e:
            print(f"attempt {attempt} {fname} failed: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed {fname}")


if __name__ == "__main__":
    # Daily full history
    fetch(UNIVERSE, period="max", interval="1d", fname="daily_close.csv")
    # Hourly ~730d
    fetch(UNIVERSE, period="730d", interval="1h", fname="hourly_close.csv")

    # For the overnight-gap test we need BTC OHLC-ish aligned to NY session.
    # Pull BTC-USD daily separately already in daily; also pull BTC hourly above.
    # SPY/QQQ open->close needs intraday opens. Pull OHLC for equities + BTC hourly.
    for attempt in range(4):
        try:
            ohlc = yf.download(
                ["SPY", "QQQ", "BTC-USD"], period="730d", interval="1h",
                auto_adjust=True, progress=False,
            )
            ohlc.to_csv(os.path.join(OUT, "hourly_ohlc.csv"))
            print("hourly_ohlc:", ohlc.shape)
            break
        except Exception as e:
            print(f"ohlc attempt {attempt}: {e}")
            time.sleep(2 ** attempt)
    print("DONE")
