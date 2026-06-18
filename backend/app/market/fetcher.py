"""Fetch NASDAQ-100 daily data from yfinance."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
import yfinance as yf
import pandas as pd


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


class NASDAQ100Fetcher:
    def __init__(self, tickers: Optional[List[str]] = None, lookback_days: int = 120):
        self.tickers = tickers or NASDAQ100_TICKERS
        self.lookback_days = lookback_days

    def fetch(self, period: Optional[str] = None) -> pd.DataFrame:
        """Return a DataFrame of OHLCV snapshots indexed by [symbol, date]."""
        end = datetime.utcnow().date()
        start = end - timedelta(days=self.lookback_days)
        dfs = []
        for symbol in self.tickers:
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
