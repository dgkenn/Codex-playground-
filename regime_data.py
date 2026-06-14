#!/usr/bin/env python3
"""
LONG-HISTORY DATA RECONSTRUCTION for the regime-robustness study.
==================================================================
Builds monthly TOTAL-RETURN series back to the 1970s for the Permanent-Portfolio /
risk-parity / 60-40 building blocks plus a simple trend/momentum proxy, so we can
test the static recommendation in the regimes the ETF-era (post-2007) sample never saw:
the 1970s stagflation bear, the 1970s-1981 bond BEAR (rising rates), 1994, 2008, 2022.

SOURCES (all free, fetched at runtime; staged NON-repo to /tmp/regime_data):
  - Robert Shiller "ie_data.xls" (Yale): monthly S&P 500 price P, dividend D, CPI, and
    the 10y rate (GS10), 1871-2023. -> S&P 500 TOTAL RETURN (price + reinvested divs) and CPI.
        http://www.econ.yale.edu/~shiller/data/ie_data.xls
  - FRED: GS10 (10y const-mat yield, monthly, 1953-), GS30 (30y, 1977-), TB3MS (3m T-bill,
    1934-), GS1 (1y), CPIAUCNS. -> cash return + bond-return reconstruction + extend rates past 2023.
        https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>
  - datahub "gold-prices" monthly (LBMA/Bundesbank-sourced), 1833-2026.
        https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv
  - Ken French Research Data Factors (Dartmouth/CRSP), monthly 1926-2026: RF = 1-month T-bill
    (the CASH sleeve, authoritative) and Mkt (= Mkt-RF + RF) to extend the equity TOTAL RETURN
    past Shiller's 2023-09 cutoff.
        https://mba.tuck.dartmouth.edu/.../F-F_Research_Data_Factors_CSV.zip

NOTE ON FRED: GS30/TB3MS/CPI/OECD are used as OPTIONAL enrichment if cached under
  /tmp/regime_data/fred/. When FRED is unreachable (it was during this build) the script falls
  back to: Shiller's own GS10 (1871-2023.09) for the 10y yield, a fixed +0.40pp term-premium
  proxy for the 30y, Shiller CPI for inflation, and Ken French RF for cash. The BOND series
  therefore END at Shiller's 2023-09 cutoff (so the common window is 1972-01..2023-09), which
  fully covers the five key regimes incl. 2022. Stocks/cash/gold individually extend to 2026.

BOND TOTAL-RETURN RECONSTRUCTION (stated method + limits, see REGIME_ROBUSTNESS.md):
  We do NOT have a clean constant-maturity 10y Treasury TR index back to 1972 for free.
  We reconstruct one from the GS10 yield using the standard closed-form approximation for a
  par bond of maturity m held one month and re-marked at the new yield:
      monthly TR ~= y_t/12  +  (-D * dy)  +  0.5*C*dy^2
  where y is the yield (decimal), dy is the monthly yield change, D is modified duration and
  C convexity of a par bond at yield y and maturity m. This is the well-known "yield + price"
  decomposition (cf. Swinkels 2019; the Damodaran / FRED-reconstruction approach). We build:
      UST10  : m=10y constant-maturity (GS10)  -> the "Treasuries" sleeve / 60-40 bonds
      UST30  : m=30y (GS30 from 1977; before 1977 proxy with GS10 + a long-rate spread) -> PP "long bond"
  LIMITS: approximation ignores roll-down and coupon-reinvestment timing; it is a duration/
  convexity mark-to-market, accurate enough to capture the REGIME pattern (does the long bond
  lose money when rates rise?), NOT to claim basis-point TR precision pre-1990.

CASH: TB3MS/12 monthly (3-month T-bill, the PP "cash" sleeve and the trend-overlay parking).

OUTPUT: /tmp/regime_data/monthly_tr.csv  (monthly TOTAL returns, decimal) with columns:
  STOCKS, UST10, UST30, GOLD, CASH, CPI_infl   (1972-01 .. latest common month)
and /tmp/regime_data/monthly_levels.csv (price/index levels for trend signals).
"""
import io
import numpy as np
import pandas as pd
import requests

DATA = "/tmp/regime_data"
H = {"User-Agent": "Mozilla/5.0 (regime-study)"}


def fred(series_id):
    import os, time
    cache = f"{DATA}/fred/{series_id}.csv"
    if os.path.exists(cache):
        df = pd.read_csv(cache)
    else:
        u = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        last = None
        for attempt in range(8):
            try:
                r = requests.get(u, timeout=30, headers=H)
                r.raise_for_status()
                os.makedirs(f"{DATA}/fred", exist_ok=True)
                open(cache, "w").write(r.text)
                df = pd.read_csv(io.StringIO(r.text))
                break
            except Exception as e:  # noqa
                last = e
                time.sleep(3 + 2 * attempt)
        else:
            raise last
    df.columns = ["date", series_id]
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")[series_id]
    return pd.to_numeric(df, errors="coerce")


def get_shiller():
    import xlrd
    u = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
    r = requests.get(u, timeout=40, headers=H)
    r.raise_for_status()
    open(f"{DATA}/ie_data.xls", "wb").write(r.content)
    wb = xlrd.open_workbook(f"{DATA}/ie_data.xls")
    sh = wb.sheet_by_name("Data")
    rows = []
    for ri in range(8, sh.nrows):
        d = sh.cell_value(ri, 0)
        if d == "" or d is None:
            continue
        try:
            dt = float(d)
        except (ValueError, TypeError):
            continue
        yr = int(dt)
        mo = int(round((dt - yr) * 100))
        if mo < 1 or mo > 12:
            continue
        P = sh.cell_value(ri, 1)
        D = sh.cell_value(ri, 2)
        CPI = sh.cell_value(ri, 4)
        gs10 = sh.cell_value(ri, 6)
        def num(x):
            try:
                return float(x)
            except (ValueError, TypeError):
                return np.nan
        rows.append((pd.Timestamp(yr, mo, 1), num(P), num(D), num(CPI), num(gs10)))
    df = pd.DataFrame(rows, columns=["date", "P", "D", "CPI", "GS10"]).set_index("date")
    return df


def get_french():
    """Ken French Research Data Factors (monthly): Mkt-RF, SMB, HML, RF (1-month T-bill).
    Returns a DataFrame indexed by month-start with columns MktRF, RF (decimal monthly)."""
    import io as _io
    import zipfile
    u = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
    r = requests.get(u, timeout=40, headers=H)
    r.raise_for_status()
    z = zipfile.ZipFile(_io.BytesIO(r.content))
    txt = z.read(z.namelist()[0]).decode("latin1")
    open(f"{DATA}/ff_factors.csv", "w").write(txt)
    rows = []
    for L in txt.splitlines():
        s = L.strip()
        if len(s) >= 6 and s[:6].isdigit() and len(s.split(",")[0].strip()) == 6:
            parts = [p.strip() for p in s.split(",")]
            ym = parts[0]
            try:
                yr, mo = int(ym[:4]), int(ym[4:6])
                mkt = float(parts[1]) / 100.0
                rf = float(parts[4]) / 100.0
            except (ValueError, IndexError):
                continue
            rows.append((pd.Timestamp(yr, mo, 1), mkt, rf))
    df = pd.DataFrame(rows, columns=["date", "MktRF", "RF"]).set_index("date")
    return df


def get_gold():
    u = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"
    r = requests.get(u, timeout=30, headers=H)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df["date"] = pd.to_datetime(df["Date"] + "-01")
    return df.set_index("date")["Price"].astype(float)


def bond_tr_from_yield(yld_pct, maturity):
    """Monthly total return of a par bond of given maturity, reconstructed from a monthly
    constant-maturity yield series (percent). Returns a monthly-return Series (decimal).
    TR_t = y_{t-1}/12 + price_change(dy) ; price via modified duration + convexity of a par bond.
    """
    y = (yld_pct / 100.0).copy()
    y = y.dropna()
    out = pd.Series(index=y.index, dtype=float)
    yv = y.values
    idx = y.index
    for i in range(1, len(yv)):
        y0 = yv[i - 1]
        dy = yv[i] - yv[i - 1]
        m = maturity
        c = y0  # par bond coupon = yield
        # modified duration & convexity of a par bond, annual coupon approx, yield y0
        if y0 <= 0:
            D = m
            C = m * m
        else:
            # Macaulay duration of par bond: (1 - (1+y)^-m)/y ; modified = /(1+y)
            mac = (1 - (1 + y0) ** (-m)) / y0
            D = mac / (1 + y0)
            C = D * D  # convexity approx (positive); keeps the 0.5*C*dy^2 term modest
        carry = y0 / 12.0
        price_ret = -D * dy + 0.5 * C * dy * dy
        out.iloc[i] = carry + price_ret
    return out.dropna()


def fred_opt(series_id):
    """Return FRED series if cached, else None (graceful when FRED is unreachable)."""
    import os
    if os.path.exists(f"{DATA}/fred/{series_id}.csv"):
        try:
            return fred(series_id)
        except Exception:
            return None
    return None


def main():
    import os
    os.makedirs(DATA, exist_ok=True)

    print("fetching Shiller ...")
    sh = get_shiller()
    print("  shiller", sh.index.min().date(), "->", sh.index.max().date())

    print("fetching gold ...")
    gold = get_gold()
    print("  gold", gold.index.min().date(), "->", gold.index.max().date())

    print("fetching Ken French (RF + Mkt) ...")
    ff = get_french()
    print("  french", ff.index.min().date(), "->", ff.index.max().date())

    # ---- FRED (optional enrichment; Shiller is the primary fallback) ----
    print("loading FRED (cached if available) ...")
    gs10_f = fred_opt("GS10")
    gs30 = fred_opt("GS30")
    tb3 = fred_opt("TB3MS")
    cpi_fred = fred_opt("CPIAUCNS")
    spx_oecd = fred_opt("SPASTT01USM661N")

    # GS10: prefer FRED, else Shiller's GS10 column (identical source lineage)
    if gs10_f is not None:
        gs10 = gs10_f
        print("  GS10: FRED")
    else:
        gs10 = sh["GS10"].dropna()
        print("  GS10: Shiller fallback (FRED unreachable)")

    # --- STOCKS: S&P 500 total return from Shiller (P + reinvested D) ---
    P = sh["P"].copy().sort_index()
    D = sh["D"].copy()
    last_sh = P.dropna().index.max()
    pr = P.pct_change()
    Dm = D.reindex(P.index)
    div_yield_monthly = (Dm / 12.0) / P.shift(1)  # D = trailing-12m $ div (annualized)
    stock_tr = (pr + div_yield_monthly)
    stock_tr.index = stock_tr.index.to_period("M").to_timestamp()
    stock_tr = stock_tr.dropna()
    # extend past Shiller's cutoff with Ken French total US market return (Mkt = MktRF + RF)
    last_sh_m = last_sh.to_period("M").to_timestamp()
    ff_mkt = (ff["MktRF"] + ff["RF"])
    add = ff_mkt[ff_mkt.index > last_sh_m]
    stock_tr = pd.concat([stock_tr, add])
    stock_tr.name = "STOCKS"
    print(f"  STOCKS: Shiller TR to {last_sh.date()}, extended with French Mkt ({len(add)} mo)")

    # --- BONDS: reconstruct UST10 & UST30 TR from yields ---
    gs10.index = gs10.index.to_period("M").to_timestamp()
    if gs30 is not None:
        gs30.index = gs30.index.to_period("M").to_timestamp()
        overlap = pd.concat([gs10, gs30], axis=1, join="inner").dropna()
        spread = (overlap.iloc[:, 1] - overlap.iloc[:, 0]).median()
        long_yld = gs30.reindex(gs10.index).fillna(gs10 + spread)
        print(f"  UST30: GS30 (FRED), pre-1977 proxy = GS10 + {spread:.2f}pp term premium")
    else:
        # No GS30: proxy long-bond yield = GS10 + a fixed ~0.40pp 10y->30y term premium
        spread = 0.40
        long_yld = gs10 + spread
        print(f"  UST30: GS30 unavailable -> proxy = GS10 + {spread:.2f}pp (fixed term premium)")
    ust10 = bond_tr_from_yield(gs10, 10.0); ust10.name = "UST10"
    ust30 = bond_tr_from_yield(long_yld, 30.0); ust30.name = "UST30"

    # --- GOLD TR (no income) ---
    gold_tr = gold.pct_change(); gold_tr.name = "GOLD"

    # --- CASH: Ken French 1-month T-bill (RF), authoritative monthly back to 1926 ---
    cash = ff["RF"].copy()
    cash.name = "CASH"
    print("  CASH: Ken French RF (1-month T-bill, Ibbotson/CRSP)")

    # --- CPI inflation: FRED CPIAUCNS, else Shiller CPI ---
    if cpi_fred is not None:
        cpi_fred.index = cpi_fred.index.to_period("M").to_timestamp()
        infl = cpi_fred.pct_change()
    else:
        infl = sh["CPI"].pct_change()
        infl.index = infl.index.to_period("M").to_timestamp()
    infl.name = "CPI_infl"

    stock_tr.index = stock_tr.index.to_period("M").to_timestamp()
    gold_tr.index = gold_tr.index.to_period("M").to_timestamp()
    tr = pd.concat([stock_tr, ust10, ust30, gold_tr, cash, infl], axis=1)
    tr = tr[tr.index >= "1972-01-01"].dropna(subset=["STOCKS", "UST10", "UST30", "GOLD", "CASH"])
    tr.to_csv(f"{DATA}/monthly_tr.csv")
    print("\nmonthly_tr:", tr.index.min().date(), "->", tr.index.max().date(), "n=", len(tr))
    print(tr.describe().round(4).T[["mean", "std", "min", "max"]])

    # levels for trend signals (cumulative TR)
    lvl = (1 + tr[["STOCKS", "UST10", "UST30", "GOLD"]]).cumprod()
    lvl.to_csv(f"{DATA}/monthly_levels.csv")
    print("\nsaved levels", lvl.shape)


if __name__ == "__main__":
    main()
