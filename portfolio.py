"""
Portfolio: Tracks simulated cash, holdings, and full transaction history.
All monetary values are in the instrument's native currency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# Data containers


@dataclass
class Trade:
    """Represents a single buy or sell execution."""

    date: datetime
    action: str          # "BUY" | "SELL"
    ticker: str
    quantity: float
    price: float
    commission: float
    pnl: float = 0.0     # realised P&L (populated on SELL)

    @property
    def gross_value(self) -> float:
        return self.quantity * self.price

    @property
    def net_value(self) -> float:
        return self.gross_value + self.commission 


@dataclass
class Position:
    """Open position in a single instrument."""

    ticker: str
    quantity: float = 0.0
    avg_cost: float = 0.0   # weighted average entry price

    @property
    def market_value(self) -> float:
        return self.quantity * self.avg_cost

    def update_on_buy(self, quantity: float, price: float) -> None:
        total_cost = self.avg_cost * self.quantity + price * quantity
        self.quantity += quantity
        self.avg_cost = total_cost / self.quantity if self.quantity else 0.0

    def reduce_on_sell(self, quantity: float) -> float:
        """Returns cost basis of the units sold (for P&L calc)."""
        cost_basis = self.avg_cost * quantity
        self.quantity -= quantity
        if self.quantity <= 0:
            self.quantity = 0.0
            self.avg_cost = 0.0
        return cost_basis


# Portfolio


class InsufficientFundsError(Exception):
    """Raised when a buy order exceeds available cash."""


class InsufficientSharesError(Exception):
    """Raised when a sell order exceeds current holdings."""


class Portfolio:
    """
    Simulated brokerage account.

    Parameters
    ----------
    initial_cash : float
        Starting cash balance.
    commission_pct : float
        Round-trip commission as a fraction of trade value (default 0.1 %).
    ticker : str
        The instrument being traded (used for position tracking).
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission_pct: float = 0.001,
        ticker: str = "ASSET",
    ) -> None:
        self.initial_cash: float = initial_cash
        self.cash: float = initial_cash
        self.commission_pct: float = commission_pct
        self.ticker: str = ticker

        self._position: Position = Position(ticker=ticker)
        self._trades: list[Trade] = []

    # Core order methods

    def buy(self, date: datetime, price: float, quantity: Optional[float] = None) -> Trade:
        """
        Execute a market buy.

        Parameters
        ----------
        date : datetime
        price : float
            Fill price per unit.
        quantity : float | None
            Number of units. If *None*, spends all available cash.
        """
        if quantity is None:
            quantity = self.cash / (price * (1 + self.commission_pct) + 1e-9)

        commission = -price * quantity * self.commission_pct
        total_cost = price * quantity - commission  # cost goes up

        if total_cost > self.cash:
            raise InsufficientFundsError(
                f"Need {total_cost:.2f} but only {self.cash:.2f} available."
            )

        self.cash -= total_cost
        self._position.update_on_buy(quantity, price)

        trade = Trade(
            date=date, action="BUY", ticker=self.ticker,
            quantity=quantity, price=price, commission=commission,
        )
        self._trades.append(trade)
        logger.debug("BUY  %s  qty=%.4f  price=%.2f  cash=%.2f", self.ticker, quantity, price, self.cash)
        return trade

    def sell(self, date: datetime, price: float, quantity: Optional[float] = None) -> Trade:
        """
        Execute a market sell.

        Parameters
        ----------
        quantity : float | None
            Number of units. If *None*, liquidates the entire position.
        """
        held = self._position.quantity
        if quantity is None:
            quantity = held

        if quantity > held + 1e-9:
            raise InsufficientSharesError(
                f"Trying to sell {quantity:.4f} but only holding {held:.4f}."
            )

        commission = -price * quantity * self.commission_pct
        cost_basis = self._position.reduce_on_sell(quantity)
        proceeds = price * quantity + commission  # proceeds go down by commission
        realised_pnl = proceeds - cost_basis

        self.cash += proceeds

        trade = Trade(
            date=date, action="SELL", ticker=self.ticker,
            quantity=quantity, price=price, commission=commission, pnl=realised_pnl,
        )
        self._trades.append(trade)
        logger.debug("SELL %s  qty=%.4f  price=%.2f  pnl=%.2f  cash=%.2f",
                     self.ticker, quantity, price, realised_pnl, self.cash)
        return trade

    # Metrics

    def equity(self, current_price: float) -> float:
        """Total portfolio value = cash + mark-to-market position."""
        return self.cash + self._position.quantity * current_price

    def total_return_pct(self, current_price: float) -> float:
        return (self.equity(current_price) / self.initial_cash - 1) * 100

    def realised_pnl(self) -> float:
        return sum(t.pnl for t in self._trades if t.action == "SELL")

    def unrealised_pnl(self, current_price: float) -> float:
        if self._position.quantity == 0:
            return 0.0
        return (current_price - self._position.avg_cost) * self._position.quantity

    def num_trades(self) -> int:
        return len(self._trades)

    def win_rate(self) -> float:
        sells = [t for t in self._trades if t.action == "SELL"]
        if not sells:
            return 0.0
        wins = sum(1 for t in sells if t.pnl > 0)
        return wins / len(sells) * 100

    # Serialisation helpers

    def trade_log(self) -> list[dict]:
        return [
            {
                "date": t.date.isoformat(),
                "action": t.action,
                "ticker": t.ticker,
                "quantity": round(t.quantity, 4),
                "price": round(t.price, 2),
                "commission": round(t.commission, 2),
                "pnl": round(t.pnl, 2),
                "gross_value": round(t.gross_value, 2),
            }
            for t in self._trades
        ]

    def snapshot(self, current_price: float) -> dict:
        return {
            "initial_cash": round(self.initial_cash, 2),
            "cash": round(self.cash, 2),
            "position_qty": round(self._position.quantity, 4),
            "position_avg_cost": round(self._position.avg_cost, 2),
            "equity": round(self.equity(current_price), 2),
            "total_return_pct": round(self.total_return_pct(current_price), 4),
            "realised_pnl": round(self.realised_pnl(), 2),
            "unrealised_pnl": round(self.unrealised_pnl(current_price), 2),
            "num_trades": self.num_trades(),
            "win_rate_pct": round(self.win_rate(), 2),
        }

    def reset(self) -> None:
        """Restore to initial state (useful for re-running strategies)."""
        self.cash = self.initial_cash
        self._position = Position(ticker=self.ticker)
        self._trades = []
