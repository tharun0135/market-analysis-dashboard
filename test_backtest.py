"""
Unit tests for the Trading Strategy Backtester.
Run with: pytest backend/tests/ -v
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from portfolio import (
    Portfolio,
    InsufficientFundsError,
    InsufficientSharesError,
)

from implementations import (
    MovingAverageCrossover,
    RSIStrategy,
    BollingerBandStrategy,
    MACDStrategy,
    build_strategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_price_series(
    n: int = 200,
    start_price: float = 100.0,
    trend: float = 0.001,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame for testing."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(trend, 0.015, n)
    prices = start_price * np.cumprod(1 + returns)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    df = pd.DataFrame(
        {
            "Open": prices * (1 - 0.002),
            "High": prices * (1 + 0.005),
            "Low": prices * (1 - 0.005),
            "Close": prices,
            "Volume": rng.integers(1_000_000, 5_000_000, n),
        },
        index=dates,
    )
    return df


# ---------------------------------------------------------------------------
# Portfolio tests
# ---------------------------------------------------------------------------


class TestPortfolio:
    def test_initial_state(self):
        p = Portfolio(initial_cash=50_000.0)
        assert p.cash == 50_000.0
        assert p.equity(100.0) == 50_000.0

    def test_buy_reduces_cash(self):
        p = Portfolio(initial_cash=10_000.0, commission_pct=0.0)
        p.buy(date=datetime.today(), price=100.0, quantity=50)
        assert abs(p.cash - 5_000.0) < 0.01

    def test_sell_increases_cash(self):
        p = Portfolio(initial_cash=10_000.0, commission_pct=0.0)
        p.buy(date=datetime.today(), price=100.0, quantity=50)
        p.sell(date=datetime.today(), price=120.0, quantity=50)
        assert abs(p.cash - (10_000.0 - 5_000.0 + 6_000.0)) < 0.01

    def test_realised_pnl_positive(self):
        p = Portfolio(initial_cash=10_000.0, commission_pct=0.0)
        p.buy(date=datetime.today(), price=100.0, quantity=10)
        p.sell(date=datetime.today(), price=150.0, quantity=10)
        assert abs(p.realised_pnl() - 500.0) < 0.01

    def test_realised_pnl_negative(self):
        p = Portfolio(initial_cash=10_000.0, commission_pct=0.0)
        p.buy(date=datetime.today(), price=100.0, quantity=10)
        p.sell(date=datetime.today(), price=80.0, quantity=10)
        assert p.realised_pnl() < 0

    def test_insufficient_funds_raises(self):
        p = Portfolio(initial_cash=100.0)
        with pytest.raises(InsufficientFundsError):
            p.buy(date=datetime.today(), price=200.0, quantity=10)

    def test_insufficient_shares_raises(self):
        p = Portfolio(initial_cash=10_000.0)
        p.buy(date=datetime.today(), price=100.0, quantity=5)
        with pytest.raises(InsufficientSharesError):
            p.sell(date=datetime.today(), price=100.0, quantity=100)

    def test_commission_reduces_returns(self):
        p_no_comm = Portfolio(initial_cash=10_000.0, commission_pct=0.0)
        p_comm = Portfolio(initial_cash=10_000.0, commission_pct=0.01)
        for p in (p_no_comm, p_comm):
            p.buy(date=datetime.today(), price=100.0, quantity=50)
            p.sell(date=datetime.today(), price=120.0, quantity=50)
        assert p_no_comm.cash > p_comm.cash

    def test_win_rate_calculation(self):
        p = Portfolio(initial_cash=100_000.0, commission_pct=0.0)
        now = datetime.today()
        # 2 wins, 1 loss
        for buy_px, sell_px in [(100, 120), (100, 90), (100, 130)]:
            p.buy(date=now, price=buy_px, quantity=10)
            p.sell(date=now, price=sell_px, quantity=10)
        assert abs(p.win_rate() - 200 / 3) < 0.01

    def test_reset_restores_state(self):
        p = Portfolio(initial_cash=10_000.0)
        p.buy(date=datetime.today(), price=100.0, quantity=10)
        p.reset()
        assert p.cash == 10_000.0
        assert p._position.quantity == 0.0

    def test_trade_log_structure(self):
        p = Portfolio(initial_cash=10_000.0, commission_pct=0.0)
        p.buy(date=datetime.today(), price=100.0, quantity=5)
        log = p.trade_log()
        assert len(log) == 1
        assert log[0]["action"] == "BUY"
        assert "date" in log[0] and "price" in log[0]


# ---------------------------------------------------------------------------
# Strategy tests
# ---------------------------------------------------------------------------


class TestMovingAverageCrossover:
    def test_signals_generated(self):
        df = make_price_series(200)
        strat = MovingAverageCrossover(short_window=10, long_window=30)
        df_sig = strat.generate_signals(df.copy())
        assert "signal" in df_sig.columns
        assert "short_ma" in df_sig.columns
        assert "long_ma" in df_sig.columns

    def test_signal_values_valid(self):
        df = make_price_series(200)
        strat = MovingAverageCrossover(short_window=10, long_window=30)
        df_sig = strat.generate_signals(df.copy())
        assert set(df_sig["signal"].unique()).issubset({-1, 0, 1})

    def test_short_gt_long_raises(self):
        with pytest.raises(ValueError):
            MovingAverageCrossover(short_window=50, long_window=20)

    def test_full_backtest_runs(self):
        df = make_price_series(300)
        strat = MovingAverageCrossover(short_window=20, long_window=50, initial_cash=100_000)
        result = strat.run(df, ticker="TEST")
        assert result.initial_cash == 100_000
        assert len(result.equity_curve) == len(df)


class TestRSIStrategy:
    def test_rsi_bounds(self):
        df = make_price_series(200)
        strat = RSIStrategy(period=14)
        df_sig = strat.generate_signals(df.copy())
        rsi = df_sig["rsi"].dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_signals_valid(self):
        df = make_price_series(200)
        strat = RSIStrategy()
        df_sig = strat.generate_signals(df.copy())
        assert set(df_sig["signal"].unique()).issubset({-1, 0, 1})


class TestBollingerBandStrategy:
    def test_bands_ordered(self):
        df = make_price_series(200)
        strat = BollingerBandStrategy(period=20, num_std=2.0)
        df_sig = strat.generate_signals(df.copy())
        valid = df_sig.dropna()
        assert (valid["bb_upper"] >= valid["bb_mid"]).all()
        assert (valid["bb_mid"] >= valid["bb_lower"]).all()


class TestMACDStrategy:
    def test_macd_columns_present(self):
        df = make_price_series(200)
        strat = MACDStrategy()
        df_sig = strat.generate_signals(df.copy())
        for col in ("macd", "macd_signal", "macd_hist"):
            assert col in df_sig.columns


class TestStrategyFactory:
    def test_build_known_strategy(self):
        s = build_strategy("rsi", {"period": 14})
        assert isinstance(s, RSIStrategy)

    def test_build_unknown_raises(self):
        with pytest.raises(ValueError):
            build_strategy("nonexistent", {})


# ---------------------------------------------------------------------------
# Backtest result metrics
# ---------------------------------------------------------------------------


class TestBacktestMetrics:
    def test_benchmark_computed(self):
        df = make_price_series(300)
        strat = MovingAverageCrossover(short_window=20, long_window=50, initial_cash=100_000)
        result = strat.run(df)
        assert result.benchmark_return_pct != 0.0

    def test_max_drawdown_non_positive(self):
        df = make_price_series(300)
        strat = MovingAverageCrossover(short_window=20, long_window=50, initial_cash=100_000)
        result = strat.run(df)
        assert result.max_drawdown_pct <= 0.0

    def test_equity_curve_length_matches_data(self):
        df = make_price_series(250)
        strat = RSIStrategy(initial_cash=50_000)
        result = strat.run(df)
        assert len(result.equity_curve) == len(df)
