"""
FastAPI backend for the Trading Strategy Backtester.
Run with: uvicorn backend.api.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Optional


from implementations import build_strategy
from data_fetcher import DataFetcher, DataFetchError
from portfolio import Portfolio
from strategy import Strategy

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Trading Strategy Backtester API",
    description="Backtest trading strategies on historical market data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class BacktestRequest(BaseModel):
    ticker: str = Field("AAPL", description="Ticker symbol or friendly name")
    strategy_id: str = Field("ma_crossover", description="Strategy registry key")
    period: str = Field("1y", description="Data period e.g. 1y, 2y, 5y")
    interval: str = Field("1d", description="Bar interval: 1d, 1wk")
    initial_cash: float = Field(100_000.0, gt=0)
    commission_pct: float = Field(0.001, ge=0, le=0.05)
    params: dict[str, Any] = Field(default_factory=dict, description="Strategy-specific params")
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD override")
    end_date: Optional[str] = Field(None, description="YYYY-MM-DD override")

@app.get("/")
def root():
    return {"message": "Trading Backtester API", "version": "1.0.0"}


@app.get("/tickers")
def list_tickers():
    """Return curated list of supported tickers."""
    return DataFetcher.available_tickers()


@app.get("/strategies")
def list_strategies():
    """Return all registered strategy IDs and their parameter signatures."""
    info = {
        "ma_crossover": {
            "label": "Moving Average Crossover",
            "params": {
                "short_window": {"type": "int", "default": 20, "min": 2, "max": 200},
                "long_window": {"type": "int", "default": 50, "min": 5, "max": 500},
                "ma_type": {"type": "select", "options": ["SMA", "EMA"], "default": "SMA"},
            },
        },
        "rsi": {
            "label": "RSI (Relative Strength Index)",
            "params": {
                "period": {"type": "int", "default": 14, "min": 2, "max": 100},
                "oversold_threshold": {"type": "float", "default": 30.0, "min": 5, "max": 49},
                "overbought_threshold": {"type": "float", "default": 70.0, "min": 51, "max": 95},
            },
        },
        "bollinger": {
            "label": "Bollinger Bands",
            "params": {
                "period": {"type": "int", "default": 20, "min": 5, "max": 200},
                "num_std": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0},
            },
        },
        "macd": {
            "label": "MACD",
            "params": {
                "fast": {"type": "int", "default": 12, "min": 2, "max": 100},
                "slow": {"type": "int", "default": 26, "min": 5, "max": 200},
                "signal_period": {"type": "int", "default": 9, "min": 2, "max": 50},
            },
        },
    }
    return info


@app.get("/ticker/{ticker}/info")
def ticker_info(ticker: str):
    """Return metadata for a given ticker."""
    try:
        fetcher = DataFetcher(ticker)
        return fetcher.fetch_info()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/ticker/{ticker}/ohlcv")
def ticker_ohlcv(ticker: str, period: str = "1y", interval: str = "1d"):
    """Return raw OHLCV data for charting."""
    try:
        fetcher = DataFetcher(ticker)
        df = fetcher.fetch_historical(period=period, interval=interval)
        records = []
        for date, row in df.iterrows():
            records.append({
                "date": date.isoformat()[:10],
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            })
        return {"ticker": ticker, "data": records}
    except DataFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/backtest")
def run_backtest(req: BacktestRequest):
    """Run a full backtest and return results."""
    try:
        # Fetch data
        fetcher = DataFetcher(req.ticker)
        df = fetcher.fetch_historical(
            period=req.period,
            interval=req.interval,
            start=req.start_date,
            end=req.end_date,
        )

        # Build strategy
        strategy_params = {
            "initial_cash": req.initial_cash,
            "commission_pct": req.commission_pct,
            **req.params,
        }
        strategy = build_strategy(req.strategy_id, strategy_params)

        # Run
        result = strategy.run(df, ticker=fetcher.ticker)
        return result.to_dict()

    except DataFetchError as exc:
        raise HTTPException(status_code=400, detail=f"Data error: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during backtest")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}
