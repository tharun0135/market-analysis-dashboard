"""
DataFetcher: Handles all market data retrieval via yfinance.
Supports historical OHLCV data and basic ticker info.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class DataFetchError(Exception):
    """Raised when market data cannot be retrieved."""


class DataFetcher:
    """
    Fetches historical and live market data from Yahoo Finance.

    Attributes
    ----------
    ticker : str
        The stock/index ticker symbol (e.g. "^NSEI", "AAPL").
    """

    # Map friendly names → Yahoo Finance tickers
    TICKER_MAP: dict[str, str] = {
        "nifty50": "^NSEI",
        "sensex": "^BSESN",
        "apple": "AAPL",
        "microsoft": "MSFT",
        "google": "GOOGL",
        "amazon": "AMZN",
        "tesla": "TSLA",
        "meta": "META",
        "nvidia": "NVDA",
        "reliance": "RELIANCE.NS",  # Double check there are no hidden spaces
        "tcs": "TCS.NS",
        "infosys": "INFY.NS",
    }

    def __init__(self, ticker: str) -> None:
        """
        Parameters
        ----------
        ticker : str
            Ticker symbol or friendly name from TICKER_MAP.
        """
        self.ticker: str = self.TICKER_MAP.get(ticker.lower(), ticker.upper())
        self._yf_ticker: yf.Ticker = yf.Ticker(self.ticker)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_historical(
        self,
        period: str = "1y",
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Download OHLCV data.

        Parameters
        ----------
        period : str
            Shorthand period string – "1mo", "3mo", "6mo", "1y", "2y", "5y".
            Ignored when *start* is provided.
        interval : str
            Bar size – "1d", "1wk", "1mo".
        start : str | None
            ISO date string "YYYY-MM-DD".
        end : str | None
            ISO date string "YYYY-MM-DD". Defaults to today.

        Returns
        -------
        pd.DataFrame
            Columns: Open, High, Low, Close, Volume.
        """
        try:
            if start:
                df: pd.DataFrame = self._yf_ticker.history(
                    start=start, end=end or datetime.today().strftime("%Y-%m-%d"),
                    interval=interval,
                )
            else:
                df = self._yf_ticker.history(period=period, interval=interval)

            if df.empty:
                raise DataFetchError(
                    f"No data returned for ticker '{self.ticker}'. "
                    "Check the symbol and try again."
                )

            df.index = pd.to_datetime(df.index)
            df.index = df.index.tz_localize(None)  # strip tz for simplicity
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            logger.info(
                "Fetched %d rows for %s (%s)", len(df), self.ticker, period or f"{start}→{end}"
            )
            return df

        except Exception as exc:
            raise DataFetchError(str(exc)) from exc

    def fetch_info(self) -> dict:
        """Return basic metadata about the ticker (name, sector, currency…)."""
        try:
            info = self._yf_ticker.info
            return {
                "symbol": self.ticker,
                "name": info.get("longName", self.ticker),
                "sector": info.get("sector", "N/A"),
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange", "N/A"),
                "market_cap": info.get("marketCap"),
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch info for %s: %s", self.ticker, exc)
            return {"symbol": self.ticker, "name": self.ticker}

    @classmethod
    def available_tickers(cls) -> list[dict[str, str]]:
        """Return the curated list of supported tickers."""
        return [{"label": k.title(), "value": k} for k in cls.TICKER_MAP]
