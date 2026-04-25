set -e

echo "  Trading Strategy Backtester — API Server"

PYTHON="python.exe"

echo ""
echo "[1/3] Installing dependencies..."
$PYTHON -m pip install --upgrade pip
$PYTHON -m pip install yfinance fastapi uvicorn pandas numpy pytest

echo ""
echo "[2/3] Skipping tests (not found)..."

echo ""
echo "[3/3] Starting API server on http://localhost:8000"
echo "      Press Ctrl+C to stop"
echo ""

$PYTHON -m uvicorn server:app --reload --host 0.0.0.0 --port 8000