"""
Concrete strategy implementations.

Available strategies
--------------------
- MovingAverageCrossover  : Classic SMA/EMA crossover
- RSIStrategy             : Buy oversold, sell overbought
- BollingerBandStrategy   : Mean-reversion using Bollinger Bands
- MACDStrategy            : MACD signal-line crossover
"""

from __future__ import annotations

import pandas as pd
from strategy import Strategy  

# 1. Moving Average Crossover

class MovingAverageCrossover(Strategy):

    def __init__(
        self,
        short_window: int = 20,
        long_window: int = 50,
        ma_type: str = "SMA",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window.")

        self.short_window = short_window
        self.long_window = long_window
        self.ma_type = ma_type.upper()

    @property
    def name(self) -> str:
        return f"MA Crossover ({self.ma_type} {self.short_window}/{self.long_window})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]

        if self.ma_type == "EMA":
            df["short_ma"] = close.ewm(span=self.short_window, adjust=False).mean()
            df["long_ma"] = close.ewm(span=self.long_window, adjust=False).mean()
        else:
            df["short_ma"] = close.rolling(self.short_window).mean()
            df["long_ma"] = close.rolling(self.long_window).mean()

        df["signal"] = 0

        prev_above = df["short_ma"].shift(1) >= df["long_ma"].shift(1)
        curr_above = df["short_ma"] >= df["long_ma"]

        df.loc[~prev_above & curr_above, "signal"] = 1
        df.loc[prev_above & ~curr_above, "signal"] = -1

        return df


# 2. RSI Strategy

class RSIStrategy(Strategy):

    def __init__(
        self,
        period: int = 14,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.period = period
        self.oversold = oversold_threshold
        self.overbought = overbought_threshold

    @property
    def name(self) -> str:
        return f"RSI ({self.period}) [{self.oversold}/{self.overbought}]"

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, float("nan"))
        return 100 - (100 / (1 + rs))

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df["rsi"] = self._compute_rsi(df["Close"], self.period)
        df["signal"] = 0

        prev = df["rsi"].shift(1)

        df.loc[(prev >= self.oversold) & (df["rsi"] < self.oversold), "signal"] = 1
        df.loc[(prev <= self.overbought) & (df["rsi"] > self.overbought), "signal"] = -1

        return df


# 3. Bollinger Bands

class BollingerBandStrategy(Strategy):

    def __init__(self, period: int = 20, num_std: float = 2.0, **kwargs):
        super().__init__(**kwargs)
        self.period = period
        self.num_std = num_std

    @property
    def name(self) -> str:
        return f"Bollinger ({self.period}, {self.num_std})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]

        mid = close.rolling(self.period).mean()
        std = close.rolling(self.period).std()

        df["bb_mid"] = mid
        df["bb_upper"] = mid + self.num_std * std
        df["bb_lower"] = mid - self.num_std * std

        df["signal"] = 0

        prev_close = close.shift(1)

        df.loc[(prev_close >= df["bb_lower"].shift(1)) & (close < df["bb_lower"]), "signal"] = 1
        df.loc[(prev_close <= df["bb_upper"].shift(1)) & (close > df["bb_upper"]), "signal"] = -1

        return df


# 4. MACD

class MACDStrategy(Strategy):

    def __init__(self, fast: int = 12, slow: int = 26, signal_period: int = 9, **kwargs):
        super().__init__(**kwargs)
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period

    @property
    def name(self) -> str:
        return f"MACD ({self.fast}/{self.slow}/{self.signal_period})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]

        macd = close.ewm(span=self.fast).mean() - close.ewm(span=self.slow).mean()
        signal = macd.ewm(span=self.signal_period).mean()

        df["macd"] = macd
        df["macd_signal"] = signal
        df["macd_hist"] = macd - signal

        df["signal"] = 0

        prev_macd = macd.shift(1)
        prev_sig = signal.shift(1)

        df.loc[(prev_macd <= prev_sig) & (macd > signal), "signal"] = 1
        df.loc[(prev_macd >= prev_sig) & (macd < signal), "signal"] = -1

        return df


# Registry + Factory

STRATEGY_REGISTRY = {
    "ma_crossover": MovingAverageCrossover,
    "rsi": RSIStrategy,
    "bollinger": BollingerBandStrategy,
    "macd": MACDStrategy,
}


def build_strategy(strategy_id: str, params: dict) -> Strategy:
    cls = STRATEGY_REGISTRY.get(strategy_id)
    if cls is None:
        raise ValueError(f"Unknown strategy '{strategy_id}'")
    return cls(**params)