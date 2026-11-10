"""
scripts/generate_html_report.py
===============================
Generates a polished, standalone, interactive HTML report of the
Nifty 500 Donchian Breakout Portfolio Backtest with Chart.js equity curve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest import PortfolioBacktester
from src.config import load_config


def generate_html_report(output_path: str = "backtest_report_2026.html", start_date: str = "2026-01-01", title_suffix: str = "2026 Backtest Report (Turtle System 2 + Stage 2 Filter)") -> str:
    cfg = load_config()
    backtester = PortfolioBacktester(
        initial_capital=cfg.capital.total_capital,
        position_size=cfg.capital.position_size,
        max_positions=cfg.capital.max_positions,
        max_per_sector=cfg.capital.max_per_sector,
        within_52w_pct=cfg.filters.within_52w_high_pct,
        entry_len=cfg.strategy.entry_len,
        exit_len=cfg.strategy.exit_len,
        use_market_regime=cfg.market_regime.enabled,
        index_ema_len=cfg.market_regime.ema_len,
        max_loss_pct=8.0,
        sizing_mode=cfg.capital.sizing_mode,
        risk_per_trade_pct=cfg.capital.risk_per_trade_pct,
        max_position_size_pct=cfg.capital.max_position_size_pct,
        use_stage_2=getattr(cfg.filters, "stage_2_trend_enabled", True),
        start_date=start_date,
    )

    stock_dfs = backtester.load_universe_data()
    res = backtester.run(stock_dfs)

    # Prepare Chart Data
    eq_df = res["equity_df"].reset_index()
    dates = [d.strftime("%Y-%m-%d") for d in eq_df["date"]]
    equity_vals = [round(v, 2) for v in eq_df["equity"]]
    drawdown_vals = [round(v, 2) for v in eq_df["drawdown"]]

    # Prepare Monthly Data
    monthly_labels = []
    monthly_returns = []
    for dt, row in res["monthly_df"].iterrows():
        monthly_labels.append(dt.strftime("%b %Y"))
        monthly_returns.append(round(row["return_pct"], 2))

    # Prepare Trade Rows
    trade_rows_html = []
    for t in sorted(res["closed_trades"], key=lambda x: x.pnl, reverse=True):
        badge = "badge-success" if t.pnl >= 0 else "badge-danger"
        pnl_sign = "+" if t.pnl >= 0 else ""
        row = f"""
        <tr>
            <td><strong>{t.symbol}</strong></td>
            <td>{t.entry_date}</td>
            <td>{t.exit_date}</td>
            <td>₹{t.entry_price:,.2f}</td>
            <td>₹{t.exit_price:,.2f}</td>
            <td>{t.quantity}</td>
            <td>₹{t.invested:,.2f}</td>
            <td class="{badge}">{pnl_sign}₹{t.pnl:,.2f}</td>
            <td class="{badge}">{pnl_sign}{t.pnl_pct:.2f}%</td>
            <td>{t.holding_days} days</td>
            <td><small>{t.exit_reason}</small></td>
        </tr>
        """
        trade_rows_html.append(row)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nifty 500 Donchian Breakout — 2026 Backtest Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
            --border-color: #334155;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        }}
        body {{
            background-color: var(--bg-primary);
            color: var(--text-primary);
            padding: 24px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header h1 {{
            font-size: 26px;
            font-weight: 700;
            color: #fff;
        }}
        .header p {{
            color: var(--text-secondary);
            font-size: 14px;
            margin-top: 4px;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
        }}
        .kpi-label {{
            font-size: 13px;
            text-transform: uppercase;
            color: var(--text-secondary);
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .kpi-value {{
            font-size: 24px;
            font-weight: 700;
            margin-top: 8px;
        }}
        .kpi-subtext {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        .text-green {{ color: var(--accent-green); }}
        .text-red {{ color: var(--accent-red); }}
        .text-blue {{ color: var(--accent-blue); }}
        .chart-section {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .chart-header {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
            color: #fff;
        }}
        .table-section {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th {{
            background-color: #0f172a;
            color: var(--text-secondary);
            font-weight: 600;
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-color);
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 12px 14px;
            border-bottom: 1px solid #283548;
        }}
        tr:hover {{
            background-color: rgba(255, 255, 255, 0.02);
        }}
        .badge-success {{
            color: var(--accent-green);
            font-weight: 600;
        }}
        .badge-danger {{
            color: var(--accent-red);
            font-weight: 600;
        }}
        .rules-badge {{
            display: inline-block;
            background: #334155;
            color: #e2e8f0;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            margin-right: 6px;
            margin-top: 6px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div>
                <h1>Nifty 500 — {title_suffix}</h1>
                <p>Simulated Period: {res['start_date']} to {res['end_date']} | Universe: Nifty 500 Stocks | Sizing: 1.25% Risk / Trade (Max 15% Cap, 10 Slots)</p>
                <div style="margin-top: 10px;">
                    <span class="rules-badge">Strategy: 50D High Breakout</span>
                    <span class="rules-badge">Filter: ≤10% of 52W High</span>
                    <span class="rules-badge">Stage 2: Price > 50 EMA > 200 SMA</span>
                    <span class="rules-badge">Exit: 20D Low Channel</span>
                    <span class="rules-badge">Hard Stop: -8.0%</span>
                    <span class="rules-badge">Regime: Nifty 500 ≥ 50 EMA</span>
                    <span class="rules-badge">Diversification: Max 2/Sector</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 13px; color: var(--text-secondary);">FINAL PORTFOLIO VALUE</div>
                <div style="font-size: 28px; font-weight: 800; color: var(--accent-green);">₹{res['ending_equity']:,.2f}</div>
                <div style="font-size: 13px; color: var(--accent-green);">+{res['total_return_pct']:.2f}% Net Return</div>
            </div>
        </div>

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Initial Capital</div>
                <div class="kpi-value">₹{res['initial_capital']:,.2f}</div>
                <div class="kpi-subtext">Starting cash (10 slots)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Net Profit</div>
                <div class="kpi-value text-green">+₹{res['net_profit']:,.2f}</div>
                <div class="kpi-subtext">Total portfolio earnings</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Sharpe Ratio</div>
                <div class="kpi-value text-blue">{res.get('sharpe_ratio', 0.0):.2f}</div>
                <div class="kpi-subtext">Annualized excess return (Rf=6.5%)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Sortino / Calmar</div>
                <div class="kpi-value">{res.get('sortino_ratio', 0.0):.2f} / {res.get('calmar_ratio', 0.0):.2f}</div>
                <div class="kpi-subtext">Downside & DD risk-adjusted ratios</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Max Drawdown</div>
                <div class="kpi-value text-red">{res['max_drawdown_pct']:.2f}%</div>
                <div class="kpi-subtext">-₹{res['max_drawdown_amount']:,.2f} peak-to-trough</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Profit Factor</div>
                <div class="kpi-value text-blue">{res['profit_factor']:.2f}</div>
                <div class="kpi-subtext">Gross Win / Gross Loss</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Win Rate</div>
                <div class="kpi-value">{res['win_rate']:.1f}%</div>
                <div class="kpi-subtext">{res['winning_trades']} Wins / {res['losing_trades']} Losses</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Avg Winner / Loser</div>
                <div class="kpi-value"><span class="text-green">+{res['avg_win_pct']:.1f}%</span> / <span class="text-red">{res['avg_loss_pct']:.1f}%</span></div>
                <div class="kpi-subtext">Win/Loss Payout: <strong>{(abs(res['avg_win_pct']/res['avg_loss_pct'])):.2f}x</strong></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Avg Holding Time</div>
                <div class="kpi-value">{res['avg_holding_days']:.1f} Days</div>
                <div class="kpi-subtext">Swing trend duration</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Best Trade</div>
                <div class="kpi-value text-green">+{res['best_trade'].pnl_pct:.1f}%</div>
                <div class="kpi-subtext">{res['best_trade'].symbol} (+₹{res['best_trade'].pnl:,.0f})</div>
            </div>
        </div>

        <!-- Equity Curve Chart -->
        <div class="chart-section">
            <div class="chart-header">📈 Portfolio Equity Curve (2026 YTD)</div>
            <div style="position: relative; height: 350px;">
                <canvas id="equityChart"></canvas>
            </div>
        </div>

        <!-- Monthly Performance & Drawdown -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 24px;">
            <div class="chart-section">
                <div class="chart-header">📅 Monthly Returns (%)</div>
                <div style="position: relative; height: 260px;">
                    <canvas id="monthlyChart"></canvas>
                </div>
            </div>
            <div class="chart-section">
                <div class="chart-header">🌊 Portfolio Drawdown (%)</div>
                <div style="position: relative; height: 260px;">
                    <canvas id="drawdownChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Trade History Table -->
        <div class="table-section">
            <div class="chart-header">📋 All Closed Trades ({len(res['closed_trades'])} Trades)</div>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Entry Date</th>
                        <th>Exit Date</th>
                        <th>Entry Px</th>
                        <th>Exit Px</th>
                        <th>Qty</th>
                        <th>Invested</th>
                        <th>Net P&L</th>
                        <th>Return (%)</th>
                        <th>Holding</th>
                        <th>Exit Trigger</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(trade_rows_html)}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const dates = {json.dumps(dates)};
        const equity = {json.dumps(equity_vals)};
        const drawdowns = {json.dumps(drawdown_vals)};
        const monthlyLabels = {json.dumps(monthly_labels)};
        const monthlyReturns = {json.dumps(monthly_returns)};

        // 1. Equity Curve
        new Chart(document.getElementById('equityChart'), {{
            type: 'line',
            data: {{
                labels: dates,
                datasets: [{{
                    label: 'Portfolio Equity (₹)',
                    data: equity,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{ grid: {{ color: '#1e293b' }}, ticks: {{ color: '#94a3b8', maxTicksLimit: 12 }} }},
                    y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
                }},
                plugins: {{ legend: {{ labels: {{ color: '#fff' }} }} }}
            }}
        }});

        // 2. Monthly Returns Bar Chart
        new Chart(document.getElementById('monthlyChart'), {{
            type: 'bar',
            data: {{
                labels: monthlyLabels,
                datasets: [{{
                    label: 'Monthly Return (%)',
                    data: monthlyReturns,
                    backgroundColor: monthlyReturns.map(v => v >= 0 ? '#10b981' : '#ef4444'),
                    borderRadius: 4,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8' }} }},
                    y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
                }},
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});

        // 3. Drawdown Chart
        new Chart(document.getElementById('drawdownChart'), {{
            type: 'line',
            data: {{
                labels: dates,
                datasets: [{{
                    label: 'Drawdown (%)',
                    data: drawdowns,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    fill: true,
                    borderWidth: 1.5,
                    pointRadius: 0,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{ grid: {{ color: '#1e293b' }}, ticks: {{ color: '#94a3b8', maxTicksLimit: 8 }} }},
                    y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
                }},
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});
    </script>
</body>
</html>
"""

    out_file = Path(output_path)
    out_file.write_text(html_content, encoding="utf-8")
    print(f"✅ Interactive HTML report generated at: {out_file.resolve()}")
    return str(out_file.resolve())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Backtest HTML Dashboard")
    parser.add_argument("--start", default="2026-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--out", default="backtest_report_2026.html", help="Output HTML file path")
    parser.add_argument("--title", default="2026 Portfolio Backtest (with Nifty 500 Regime Filter)", help="Report title")
    args = parser.parse_args()

    generate_html_report(output_path=args.out, start_date=args.start, title_suffix=args.title)
