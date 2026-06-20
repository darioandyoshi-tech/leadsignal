"""Fetch stock daily data from yfinance.

Supports NASDAQ-100 and S&P 500 universes. S&P 500 constituents are pulled
from a public source so the list stays current; a curated NASDAQ-100 list is
kept as a fallback / lightweight option.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
import yfinance as yf
import pandas as pd
import httpx


NASDAQ100_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "TSLA", "GOOGL", "GOOG", "AVGO", "PEP",
    "COST", "CSCO", "TMUS", "ADBE", "NFLX", "AMD", "INTC", "QCOM", "AMGN", "INTU",
    "CMCSA", "TXN", "HON", "AMAT", "PANW", "MU", "BKNG", "ISRG", "VRTX", "LRCX",
    "REGN", "SBUX", "ADP", "MDLZ", "SNPS", "KLAC", "CDNS", "GILD", "ABNB", "MELI",
    "CSX", "PYPL", "MAR", "FTNT", "CHTR", "MRNA", "KDP", "ORLY", "AZN", "BIIB",
    "DXCM", "KHC", "AEP", "XEL", "EXC", "PCAR", "MCHP", "ODFL", "CTSH", "MNST",
    "FAST", "ROST", "EA", "VRSK", "PAYX", "CRWD", "DDOG", "ZS", "OKTA", "DOCU",
    "PLTR", "NTAP", "SWKS", "TTWO", "TEAM", "MDB", "CDW", "SIRI", "DLTR", "VRSN",
    "INCY", "BIDU", "JD", "PDD", "MRVL", "NTES", "LULU", "WDAY", "ILMN", "ULTA",
    "ENPH", "ALGN", "RMBS", "SPSC", "CPRT", "AXON", "GEHC", "RIVN", "DDOG", "CCEP"
]

# Curated fallback S&P 500 list (snapshot, used only if remote sources fail)
SP500_FALLBACK_TICKERS = sorted(set([
    "A", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM",
    "ADP", "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM",
    "ALB", "ALGN", "ALK", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP",
    "AMT", "AMZN", "ANET", "ANSS", "AON", "AOS", "APA", "APD", "APH", "APTV",
    "ARE", "ATO", "ATVI", "AVB", "AVGO", "AVY", "AWK", "AXON", "AXP", "AZO",
    "BA", "BAC", "BALL", "BAX", "BBWI", "BBY", "BDX", "BEN", "BG", "BIIB",
    "BIO", "BK", "BKNG", "BKR", "BLDR", "BLK", "BMY", "BR", "BRK.B", "BRO",
    "BSX", "BWA", "BX", "BXP", "C", "CAG", "CAH", "CARR", "CAT", "CB",
    "CBOE", "CBRE", "CCI", "CCL", "CDAY", "CDNS", "CDW", "CE", "CEG", "CF",
    "CFG", "CHD", "CHRW", "CHTR", "CI", "CINF", "CL", "CLX", "CMA", "CMCSA",
    "CME", "CMG", "CMI", "CMS", "CNC", "CNP", "COF", "COO", "COP", "COR",
    "COST", "CPAY", "CPB", "CPRT", "CPT", "CRL", "CRM", "CSCO", "CSGP", "CSX",
    "CTAS", "CTLT", "CTRA", "CTSH", "CTVA", "CVS", "CVX", "CZR", "D", "DAL",
    "DD", "DE", "DFS", "DG", "DGX", "DHI", "DHR", "DIS", "DLR", "DLTR",
    "DOV", "DOW", "DPZ", "DRI", "DTE", "DUK", "DVA", "DVN", "DXCM", "EA",
    "EBAY", "ECL", "ED", "EFX", "EG", "EIX", "EL", "ELV", "EMN", "EMR",
    "ENPH", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ES", "ESS", "ETN", "ETR",
    "EW", "EXC", "EXPD", "EXPE", "EXR", "F", "FANG", "FAST", "FCX", "FDS",
    "FDX", "FE", "FI", "FICO", "FIS", "FITB", "FLEX", "FLT", "FMC", "FOX",
    "FOXA", "FRT", "FSLR", "FTNT", "FTV", "GD", "GE", "GEHC", "GEV", "GILD",
    "GIS", "GL", "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN",
    "GS", "GWW", "HAL", "HAS", "HBAN", "HCA", "HD", "HES", "HIG", "HII",
    "HLT", "HOLX", "HON", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUBB",
    "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY", "INTC",
    "INTU", "INVH", "IP", "IPG", "IQV", "IR", "IRM", "ISRG", "IT", "ITW",
    "IVZ", "J", "JBHT", "JBL", "JCI", "JKHY", "JNJ", "JNPR", "JPM", "K",
    "KDP", "KEY", "KEYS", "KHC", "KIM", "KKR", "KLAC", "KMB", "KMI", "KMX",
    "KO", "KR", "KVUE", "L", "LDOS", "LEN", "LH", "LHX", "LIN", "LKQ",
    "LLY", "LMT", "LNT", "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB",
    "LYV", "M", "MA", "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO",
    "MDLZ", "MDT", "MET", "META", "MGM", "MHK", "MKC", "MKTX", "MLM", "MMC",
    "MMM", "MNST", "MO", "MOH", "MOS", "MPC", "MPWR", "MRK", "MRO", "MS",
    "MSCI", "MSFT", "MSI", "MTB", "MTCH", "MTD", "MU", "NCLH", "NDAQ", "NDSN",
    "NEE", "NEM", "NFLX", "NI", "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP",
    "NTRS", "NUE", "NVDA", "NVR", "NXPI", "O", "ODFL", "OKE", "OMC", "ON",
    "ORCL", "ORLY", "OXY", "PANW", "PARA", "PAYC", "PAYX", "PCAR", "PCG", "PEAK",
    "PENN", "PEP", "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD",
    "PLTR", "PM", "PNC", "PNR", "PNW", "POOL", "PPG", "PPL", "PRU", "PSA",
    "PSX", "PTC", "PWR", "PXD", "PYPL", "QCOM", "RCL", "REG", "REGN", "RF",
    "RHI", "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RRC", "RSG",
    "RTX", "RVTY", "SBAC", "SBUX", "SCHW", "SHW", "SJM", "SNA", "SNPS", "SO",
    "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX", "STZ", "SWK", "SWKS",
    "SYF", "SYK", "SYY", "T", "TAP", "TDG", "TDY", "TECH", "TEL", "TER",
    "TFC", "TFX", "TGT", "TJX", "TMO", "TMUS", "TPR", "TRGP", "TRMB", "TROW",
    "TRV", "TSCO", "TSLA", "TSN", "TT", "TTWO", "TXN", "TXT", "TYL", "UAL",
    "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB", "V", "VFC",
    "VICI", "VLO", "VMC", "VRSK", "VRSN", "VRT", "VRTX", "VST", "VTR", "VTRS",
    "VZ", "WAB", "WAT", "WBA", "WDC", "WEC", "WELL", "WFC", "WHR", "WM",
    "WMB", "WMT", "WRB", "WST", "WTW", "WYNN", "XEL", "XOM", "XYL", "YUM",
    "ZBH", "ZBRA", "ZBH", "ZION", "ZM", "ZTS",
]))


def fetch_sp500_symbols() -> List[str]:
    """Return current S&P 500 symbols from public sources with fallback.

    Priority:
      1. Wikipedia S&P 500 constituents table (most current)
      2. datasets/s-and-p-500-companies CSV on GitHub
      3. Curated local fallback list
    """
    # Try Wikipedia first
    try:
        import io
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        r = httpx.get(url, timeout=30, headers={"User-Agent": "LeadSignal/1.0"})
        if r.status_code == 200:
            tables = pd.read_html(io.StringIO(r.text))
            for table in tables:
                if "Symbol" in table.columns and len(table) > 400:
                    symbols = sorted(set(table["Symbol"].dropna().astype(str).tolist()))
                    if len(symbols) >= 400:
                        return symbols
    except Exception as exc:
        print(f"WARN fetch_sp500_symbols wikipedia: {exc}")

    # GitHub CSV fallback
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        r = httpx.get(url, timeout=30)
        if r.status_code == 200:
            import csv
            rows = list(csv.DictReader(io.StringIO(r.text)))
            symbols = sorted({row["Symbol"] for row in rows})
            if len(symbols) >= 400:
                return symbols
    except Exception as exc:
        print(f"WARN fetch_sp500_symbols csv: {exc}")

    print("WARN fetch_sp500_symbols: using local fallback list")
    return SP500_FALLBACK_TICKERS


class NASDAQ100Fetcher:
    def __init__(self, tickers: Optional[List[str]] = None, lookback_days: int = 120, universe: str = "sp500"):
        if tickers:
            self.tickers = tickers
        elif universe.lower() in ("sp500", "s&p500", "snp500"):
            self.tickers = fetch_sp500_symbols()
        elif universe.lower() in ("nasdaq100", "ndx"):
            self.tickers = NASDAQ100_TICKERS
        else:
            self.tickers = fetch_sp500_symbols()
        self.universe = universe
        self.lookback_days = lookback_days

    def fetch(self, period: Optional[str] = None, universe: Optional[str] = None) -> pd.DataFrame:
        """Return a DataFrame of OHLCV snapshots indexed by [symbol, date]."""
        # Allow runtime universe override
        if universe and universe.lower() in ("sp500", "s&p500", "snp500", "nasdaq100", "ndx"):
            if universe.lower() in ("sp500", "s&p500", "snp500"):
                tickers = fetch_sp500_symbols()
            else:
                tickers = NASDAQ100_TICKERS
        else:
            tickers = self.tickers
        end = datetime.utcnow().date()
        start = end - timedelta(days=self.lookback_days)
        dfs = []
        for symbol in tickers:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start, end=end + timedelta(days=1), auto_adjust=True)
                if hist.empty:
                    continue
                hist = hist.reset_index()
                hist["symbol"] = symbol
                hist = hist.rename(columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                })
                hist["date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
                dfs.append(hist[["symbol", "date", "open", "high", "low", "close", "volume"]])
            except Exception as exc:
                print(f"WARN fetch {symbol}: {exc}")
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)
