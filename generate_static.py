import json
from data_fetcher import DataFetcher
from implementations import build_strategy

# 1. Define the parameters for your static report
TICKER = "nifty50"         # Change this to whatever ticker you want to report on
STRATEGY_ID = "ma_crossover"
PARAMS = {
    "initial_cash": 100000.0,
    "commission_pct": 0.001,
    "short_window": 20,
    "long_window": 50,
    "ma_type": "SMA"
}

def generate_static_report():
    print(f"Fetching data for {TICKER}...")
    fetcher = DataFetcher(TICKER)
    df = fetcher.fetch_historical(period="1y", interval="1d")

    print(f"Running strategy: {STRATEGY_ID}...")
    strategy = build_strategy(STRATEGY_ID, PARAMS)
    result = strategy.run(df, ticker=fetcher.ticker)
    
    # Convert result to JSON string to inject into HTML
    result_json = json.dumps(result.to_dict())

    # 2. Define the static HTML template
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Static Backtest Report - {fetcher.ticker}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-50 text-gray-800 font-sans min-h-screen">

    <div class="max-w-7xl mx-auto px-4 py-8">
        <header class="mb-8 border-b pb-4">
            <h1 class="text-3xl font-bold text-blue-600">Static Backtest Report</h1>
            <p class="text-gray-500 mt-1">Ticker: <span class="font-bold">{fetcher.ticker}</span> | Strategy: <span class="font-bold">{result.strategy_name}</span></p>
        </header>

        <div class="space-y-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4" id="metricsPanel">
                <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                    <p class="text-sm text-gray-500">Total Return</p>
                    <p class="text-2xl font-bold" id="metricReturn">--</p>
                </div>
                <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                    <p class="text-sm text-gray-500">Win Rate</p>
                    <p class="text-2xl font-bold" id="metricWinRate">--</p>
                </div>
                <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                    <p class="text-sm text-gray-500">Max Drawdown</p>
                    <p class="text-2xl font-bold text-red-500" id="metricDrawdown">--</p>
                </div>
                <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                    <p class="text-sm text-gray-500">Total Trades</p>
                    <p class="text-2xl font-bold" id="metricTrades">--</p>
                </div>
            </div>

            <div class="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                <h2 class="text-xl font-semibold mb-4">Equity Curve vs Asset Price</h2>
                <canvas id="equityChart" height="100"></canvas>
            </div>
        </div>
    </div>

    <script>
        // Inject the Python data directly into the Javascript
        const staticData = {result_json};

        function renderDashboard(data) {{
            const colorClass = data.total_return_pct >= 0 ? 'text-green-500' : 'text-red-500';
            document.getElementById('metricReturn').className = `text-2xl font-bold ${{colorClass}}`;
            document.getElementById('metricReturn').innerText = `${{data.total_return_pct.toFixed(2)}}%`;
            document.getElementById('metricWinRate').innerText = `${{data.win_rate_pct.toFixed(1)}}%`;
            document.getElementById('metricDrawdown').innerText = `${{data.max_drawdown_pct.toFixed(2)}}%`;
            document.getElementById('metricTrades').innerText = data.num_trades;

            const dates = data.equity_curve.map(d => d.date);
            const equity = data.equity_curve.map(d => d.equity);
            const price = data.equity_curve.map(d => d.price);

            const ctx = document.getElementById('equityChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: dates,
                    datasets: [
                        {{
                            label: 'Portfolio Equity (₹)',
                            data: equity,
                            borderColor: 'rgba(37, 99, 235, 1)', 
                            backgroundColor: 'rgba(37, 99, 235, 0.1)',
                            borderWidth: 2,
                            yAxisID: 'y',
                            fill: true,
                            pointRadius: 0
                        }},
                        {{
                            label: 'Asset Price (₹)',
                            data: price,
                            borderColor: 'rgba(156, 163, 175, 1)', 
                            borderWidth: 1.5,
                            borderDash: [5, 5],
                            yAxisID: 'y1',
                            pointRadius: 0
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    interaction: {{ mode: 'index', intersect: false }},
                    scales: {{
                        y: {{ type: 'linear', display: true, position: 'left', title: {{ display: true, text: 'Equity'}} }},
                        y1: {{ type: 'linear', display: true, position: 'right', grid: {{ drawOnChartArea: false }}, title: {{ display: true, text: 'Price'}} }}
                    }}
                }}
            }});
        }}

        // Call the render function immediately
        renderDashboard(staticData);
    </script>
</body>
</html>
"""

    # 3. Write the file
    with open("db.html", "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print("Successfully generated static db.html!")

if __name__ == "__main__":
    generate_static_report()