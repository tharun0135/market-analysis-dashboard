#!/usr/bin/env python3
"""
V1 — The MVP Script
====================
Pulls one year of historical stock data and prints it to the terminal.
This was the seed that grew into the full backtesting system.

Run with: python v1_mvp.py
"""

import sys

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("Install dependencies: pip install yfinance pandas")
    sys.exit(1)


def fetch_and_print(ticker: str = "AAPL", period: str = "1y") -> None:
    """Pull OHLCV data and print a summary to stdout."""
    print(f"\n{'='*60}")
    print(f"  Fetching {period} of data for: {ticker}")
    print(f"{'='*60}\n")

    stock = yf.Ticker(ticker)
    df = stock.history(period=period)

    if df.empty:
        print(f"ERROR: No data found for ticker '{ticker}'")
        return

    df = df[["Open", "High", "Low", "Close", "Volume"]]

    print("--- First 5 trading days ---")
    print(df.head().to_string())
    print("\n--- Last 5 trading days ---")
    print(df.tail().to_string())

    print(f"\n--- Summary Statistics ({len(df)} trading days) ---")
    print(f"  Start price : {df['Close'].iloc[0]:.2f}")
    print(f"  End price   : {df['Close'].iloc[-1]:.2f}")
    total_return = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100
    print(f"  Total return: {total_return:+.2f}%")
    print(f"  52-week high: {df['High'].max():.2f}")
    print(f"  52-week low : {df['Low'].min():.2f}")
    avg_vol = df['Volume'].mean()
    print(f"  Avg volume  : {avg_vol:,.0f}")


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    period = sys.argv[2] if len(sys.argv) > 2 else "1y"
    fetch_and_print(ticker, period)
