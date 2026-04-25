# Trading Strategy Backtester

A production-grade Python backtesting engine for testing trading strategies on historical and near-live market data. Built with strict OOP principles, full type hints, and a FastAPI backend powering an interactive web dashboard.

---

## Architecture

```
trading_backtest/
├── backend/
│   ├── api/
│   │   └── server.py          # FastAPI REST API
│   ├── core/
│   │   ├── data_fetcher.py    # DataFetcher class (yfinance)
│   │   ├── portfolio.py       # Portfolio, Trade, Position dataclasses
│   │   └── strategy.py        # Abstract Strategy base + BacktestResult
│   ├── strategies/
│   │   └── implementations.py # MovingAverageCrossover, RSI, Bollinger, MACD
│   └── tests/
│       └── test_backtest.py   # 24 pytest unit tests
└── README.md
```

### Class Design (OOP Hierarchy)

```
Strategy (ABC)
├── MovingAverageCrossover   — SMA/EMA golden/death cross
├── RSIStrategy              — Oversold/overbought momentum
├── BollingerBandStrategy    — Mean-reversion on band touches
└── MACDStrategy             — Signal-line crossover
```

---

## System Requirements

| Component | Requirement |
|---|---|
| Python | ≥ 3.11 |
| OS | Linux / macOS / Windows |
| RAM | ≥ 2 GB |
| Internet | Required (Yahoo Finance API) |

---

## Dependencies & APIs

| Library | Purpose |
|---|---|
| `yfinance` | Historical OHLCV data from Yahoo Finance |
| `pandas` | Time-series DataFrame operations |
| `numpy` | Vectorised indicator math |
| `fastapi` | REST API backend |
| `uvicorn` | ASGI server |
| `pydantic` | Request/response validation |
| `pytest` | Unit testing |

**Data API**: Yahoo Finance (free, no key required). Supports global tickers including NSE/BSE Indian markets.

---

## Installation & Running

```bash
# 1. Clone the repo
git clone https://github.com/yourname/trading-backtest
cd trading-backtest

# 2. Install dependencies
pip install yfinance fastapi uvicorn pandas numpy pytest httpx

# 3. Run tests
pytest backend/tests/ -v

# 4. Start the API server
python -m uvicorn backend.api.server:app --reload --port 8000

# 5. Open the dashboard
# Open frontend/dashboard.html in your browser
# OR visit the Claude artifact dashboard above
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tickers` | List of supported tickers |
| GET | `/strategies` | Strategy registry with parameter schemas |
| GET | `/ticker/{ticker}/ohlcv` | Raw OHLCV data |
| GET | `/ticker/{ticker}/info` | Ticker metadata |
| POST | `/backtest` | Run a full backtest, returns all metrics |
| GET | `/health` | Health check |

### Example POST `/backtest`
```json
{
  "ticker": "^NSEI",
  "strategy_id": "ma_crossover",
  "period": "2y",
  "initial_cash": 100000,
  "commission_pct": 0.001,
  "params": {
    "short_window": 20,
    "long_window": 50,
    "ma_type": "EMA"
  }
}
```

---

## Strategies

### 1. Moving Average Crossover
- **Buy**: Short-term MA crosses above long-term MA (golden cross)
- **Sell**: Short-term MA crosses below long-term MA (death cross)
- **Params**: `short_window`, `long_window`, `ma_type` (SMA/EMA)

### 2. RSI Strategy
- **Buy**: RSI drops below oversold threshold (default 30)
- **Sell**: RSI rises above overbought threshold (default 70)
- **Params**: `period`, `oversold_threshold`, `overbought_threshold`

### 3. Bollinger Bands
- **Buy**: Price touches/breaks lower band (oversold)
- **Sell**: Price touches/breaks upper band (overbought)
- **Params**: `period`, `num_std`

### 4. MACD
- **Buy**: MACD line crosses above signal line
- **Sell**: MACD line crosses below signal line
- **Params**: `fast`, `slow`, `signal_period`

---

## Performance Metrics

| Metric | Formula |
|---|---|
| Total Return % | `(final_equity / initial_cash - 1) × 100` |
| Annualised Return | `((1 + total_ret)^(1/years) - 1) × 100` |
| Max Drawdown | `min((equity - rolling_max) / rolling_max)` |
| Sharpe Ratio | `mean(daily_ret) / std(daily_ret) × √252` |
| Calmar Ratio | `annualised_return / abs(max_drawdown)` |
| Win Rate | `winning_sells / total_sells × 100` |

---

## Git Workflow (Simulated PR Flow)

```bash
# Feature branch 1: data ingestion
git checkout -b feature/data-ingestion
git add backend/core/data_fetcher.py
git commit -m "feat(data): add DataFetcher with yfinance integration and ticker map"
git push origin feature/data-ingestion
# → Open PR → Review → Merge

# Feature branch 2: portfolio tracking
git checkout -b feature/portfolio-tracking
git add backend/core/portfolio.py
git commit -m "feat(portfolio): implement Portfolio with trade log, P&L, and win-rate"
git push origin feature/portfolio-tracking
# → Open PR → Review → Merge

# Feature branch 3: strategy engine
git checkout -b feature/strategy-engine
git add backend/core/strategy.py backend/strategies/
git commit -m "feat(strategy): abstract Strategy base + 4 concrete implementations"
# → Merge

# Feature branch 4: REST API
git checkout -b feature/api
git add backend/api/server.py
git commit -m "feat(api): FastAPI server exposing /backtest, /tickers, /strategies"
# → Merge

# Feature branch 5: tests
git checkout -b feature/tests
git add backend/tests/
git commit -m "test: add 24 unit tests covering Portfolio math and all strategies"
# → Merge
```

---

## Extending with a New Strategy

```python
# backend/strategies/implementations.py

class MyStrategy(Strategy):
    def __init__(self, my_param: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.my_param = my_param

    @property
    def name(self) -> str:
        return f"My Strategy ({self.my_param})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df["signal"] = 0
        # ... your indicator logic ...
        # Set df.loc[condition, "signal"] = 1 for buy
        # Set df.loc[condition, "signal"] = -1 for sell
        return df

# Register it:
STRATEGY_REGISTRY["my_strategy"] = MyStrategy
```

---

## Limitations & Disclaimer

- **No lookahead bias protection**: Ensure indicators only use data available at signal time.
- **Simplified execution**: Market orders at Close price; no slippage model.
- **No fractional shares** accounting for all instruments.
- This is a **paper trading / analysis tool only**. It does not connect to any broker or place real orders.

---

## Roadmap

- [ ] Walk-forward optimisation
- [ ] Multi-asset portfolio mode
- [ ] Monte Carlo simulation
- [ ] Zerodha Kite / broker WebSocket for live price feeds
- [ ] Parameter optimisation grid search
- [ ] Risk metrics: VaR, CVaR, beta
