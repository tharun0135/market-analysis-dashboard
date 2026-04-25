"""
Strategy: Abstract base class for all trading strategies.
BacktestResult: Serialisable result container.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from portfolio import Portfolio

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """
    Aggregated output of a single backtest run.

    Contains equity curve, per-trade log, and performance metrics.
    """

    strategy_name: str
    ticker: str
    start_date: str
    end_date: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    annualised_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    calmar_ratio: float
    win_rate_pct: float
    num_trades: int
    realised_pnl: float
    unrealised_pnl: float
    equity_curve: list[dict]      
    trades: list[dict]            
    signals: list[dict]           
    benchmark_return_pct: float = 0.0  

    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "ticker": self.ticker,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "final_equity": self.final_equity,
            "total_return_pct": round(self.total_return_pct, 4),
            "annualised_return_pct": round(self.annualised_return_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "num_trades": self.num_trades,
            "realised_pnl": round(self.realised_pnl, 2),
            "unrealised_pnl": round(self.unrealised_pnl, 2),
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "signals": self.signals,
            "benchmark_return_pct": round(self.benchmark_return_pct, 4),
        }


class Strategy(ABC):
    """
    Abstract base class every trading strategy must implement.

    Subclasses override :meth:`generate_signals` to produce a signal
    column on the price DataFrame, and may override :meth:`name`.

    The :meth:`run` method drives the event loop and returns a
    :class:`BacktestResult`.
    """

    def __init__(self, initial_cash: float = 100_000.0, commission_pct: float = 0.001) -> None:
        self.initial_cash = initial_cash
        self.commission_pct = commission_pct

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add indicator columns and a *signal* column to *df*.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV data with DatetimeIndex.

        Returns
        -------
        pd.DataFrame
            Same DataFrame with additional columns including ``signal``
            (1 = buy, -1 = sell, 0 = hold).
        """

    def run(self, df: pd.DataFrame, ticker: str = "ASSET") -> BacktestResult:
        """
        Execute the strategy on historical data.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV DataFrame.
        ticker : str
            Ticker label used in the result.

        Returns
        -------
        BacktestResult
        """
        df = self.generate_signals(df.copy())
        portfolio = Portfolio(
            initial_cash=self.initial_cash,
            commission_pct=self.commission_pct,
            ticker=ticker,
        )

        equity_curve: list[dict] = []
        signals_log: list[dict] = []
        in_position: bool = False

        for date, row in df.iterrows():
            price: float = float(row["Close"])
            signal: int = int(row.get("signal", 0))

            # --- Execute trades ---
            if signal == 1 and not in_position:
                try:
                    portfolio.buy(date=date, price=price)  # type: ignore[arg-type]
                    in_position = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Buy failed on %s: %s", date, exc)

            elif signal == -1 and in_position:
                try:
                    portfolio.sell(date=date, price=price)  # type: ignore[arg-type]
                    in_position = False
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Sell failed on %s: %s", date, exc)

            # --- Record equity snapshot ---
            eq = portfolio.equity(price)
            equity_curve.append({
                "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
                "equity": round(eq, 2),
                "price": round(price, 4),
                "cash": round(portfolio.cash, 2),
            })

            sig_row = {"date": date.isoformat() if hasattr(date, "isoformat") else str(date),
                       "signal": signal, "price": round(price, 4)}
            for col in df.columns:
                if col not in ("Open", "High", "Low", "Close", "Volume", "signal"):
                    val = row[col]
                    sig_row[col] = round(float(val), 4) if pd.notna(val) else None
            signals_log.append(sig_row)

        last_price = float(df["Close"].iloc[-1])
        final_equity = portfolio.equity(last_price)
        snap = portfolio.snapshot(last_price)

        # --- Performance metrics ---
        equity_series = pd.Series([e["equity"] for e in equity_curve])
        metrics = self._compute_metrics(equity_series, self.initial_cash)

        benchmark_ret = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100

        return BacktestResult(
            strategy_name=self.name,
            ticker=ticker,
            start_date=str(df.index[0])[:10],
            end_date=str(df.index[-1])[:10],
            initial_cash=self.initial_cash,
            final_equity=round(final_equity, 2),
            total_return_pct=snap["total_return_pct"],
            annualised_return_pct=metrics["annualised_return_pct"],
            max_drawdown_pct=metrics["max_drawdown_pct"],
            sharpe_ratio=metrics["sharpe_ratio"],
            calmar_ratio=metrics["calmar_ratio"],
            win_rate_pct=snap["win_rate_pct"],
            num_trades=snap["num_trades"],
            realised_pnl=snap["realised_pnl"],
            unrealised_pnl=snap["unrealised_pnl"],
            equity_curve=equity_curve,
            trades=portfolio.trade_log(),
            signals=signals_log,
            benchmark_return_pct=round(float(benchmark_ret), 4),
        )


    @staticmethod
    def _compute_metrics(equity: pd.Series, initial: float) -> dict:
        daily_ret = equity.pct_change().dropna()
        trading_days = 252

        total_days = len(equity)
        years = total_days / trading_days if total_days > 0 else 1

        total_ret = (equity.iloc[-1] / initial - 1) if initial else 0
        ann_ret = ((1 + total_ret) ** (1 / years) - 1) * 100 if years > 0 else 0.0

        # Max drawdown
        roll_max = equity.cummax()
        drawdown = (equity - roll_max) / roll_max
        max_dd = float(drawdown.min()) * 100

        # Sharpe (annualised, risk-free ≈ 0)
        if daily_ret.std() > 0:
            sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(trading_days)
        else:
            sharpe = 0.0

        # Calmar
        calmar = ann_ret / abs(max_dd) if abs(max_dd) > 0 else 0.0

        return {
            "annualised_return_pct": round(ann_ret, 4),
            "max_drawdown_pct": round(max_dd, 4),
            "sharpe_ratio": round(float(sharpe), 4),
            "calmar_ratio": round(calmar, 4),
        }
