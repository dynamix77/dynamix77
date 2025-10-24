"""
HTML report generation.

Creates human-readable reports with data coverage, outliers, proposed changes, and risk analysis.
"""

import pandas as pd
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def generate_html_report(proposals: pd.DataFrame,
                        data_stats: Dict,
                        risk_metrics: Dict,
                        output_path: str):
    """
    Generate comprehensive HTML report.

    Args:
        proposals: Proposal results with RiskScore and RiskTier
        data_stats: Data quality and coverage statistics
        risk_metrics: Risk analysis metrics
        output_path: Path to save HTML report
    """
    logger.info(f"Generating HTML report: {output_path}")

    html = generate_report_html(proposals, data_stats, risk_metrics)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"HTML report saved: {output_path}")


def generate_report_html(proposals: pd.DataFrame,
                        data_stats: Dict,
                        risk_metrics: Dict) -> str:
    """
    Generate HTML report content.

    Returns:
        HTML string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>K-Factor Optimizer Report - {timestamp}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 5px;
        }}
        h3 {{
            color: #7f8c8d;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric {{
            display: inline-block;
            background: #ecf0f1;
            padding: 15px 20px;
            margin: 10px;
            border-radius: 5px;
            min-width: 200px;
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: bold;
        }}
        .badge-high {{
            background-color: #e74c3c;
            color: white;
        }}
        .badge-medium {{
            background-color: #f39c12;
            color: white;
        }}
        .badge-low {{
            background-color: #2ecc71;
            color: white;
        }}
        .badge-confidence-high {{
            background-color: #27ae60;
            color: white;
        }}
        .badge-confidence-medium {{
            background-color: #f39c12;
            color: white;
        }}
        .badge-confidence-low {{
            background-color: #95a5a6;
            color: white;
        }}
        .increase {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .decrease {{
            color: #2ecc71;
            font-weight: bold;
        }}
        .no-change {{
            color: #95a5a6;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
        }}
        .info {{
            background-color: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 15px;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <h1>K-Factor Optimizer Report</h1>
    <p><strong>Generated:</strong> {timestamp}</p>

    {generate_executive_summary(proposals, data_stats, risk_metrics)}
    {generate_data_coverage_section(data_stats)}
    {generate_risk_analysis_section(proposals, risk_metrics)}
    {generate_top_changes_section(proposals)}
    {generate_rejected_changes_section(proposals)}
    {generate_method_breakdown_section(proposals)}

</body>
</html>
"""

    return html


def generate_executive_summary(proposals: pd.DataFrame,
                              data_stats: Dict,
                              risk_metrics: Dict) -> str:
    """Generate executive summary section."""

    total = len(proposals)
    with_changes = (proposals['ChangePct'].notna() & (proposals['ChangePct'].abs() > 1)).sum()
    increases = (proposals['ChangePct'] > 1).sum()
    decreases = (proposals['ChangePct'] < -1).sum()
    avg_change = proposals[proposals['ChangePct'].notna()]['ChangePct'].mean()

    return f"""
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="summary-grid">
            <div class="metric">
                <div class="metric-label">Total Customers</div>
                <div class="metric-value">{total}</div>
            </div>
            <div class="metric">
                <div class="metric-label">With Changes</div>
                <div class="metric-value">{with_changes}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Increases</div>
                <div class="metric-value increase">{increases}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Decreases</div>
                <div class="metric-value decrease">{decreases}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Avg Change</div>
                <div class="metric-value">{avg_change:.1f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">High Risk</div>
                <div class="metric-value">{risk_metrics.get('high_risk_count', 0)}</div>
            </div>
        </div>
    </div>
    """


def generate_data_coverage_section(data_stats: Dict) -> str:
    """Generate data coverage section."""

    return f"""
    <div class="section">
        <h2>Data Coverage</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Customer Fuel Records</td>
                <td>{data_stats.get('customer_fuel_count', 0):,}</td>
            </tr>
            <tr>
                <td>Delivery Tickets</td>
                <td>{data_stats.get('delivery_ticket_count', 0):,}</td>
            </tr>
            <tr>
                <td>Degree Day Records</td>
                <td>{data_stats.get('degree_day_count', 0):,}</td>
            </tr>
            <tr>
                <td>Customers with Deliveries</td>
                <td>{data_stats.get('customers_with_deliveries', 0):,}</td>
            </tr>
            <tr>
                <td>Customers with Recent Deliveries (180 days)</td>
                <td>{data_stats.get('customers_with_recent_deliveries', 0):,}</td>
            </tr>
            <tr>
                <td>Avg Deliveries per Customer</td>
                <td>{data_stats.get('avg_deliveries_per_customer', 0):.1f}</td>
            </tr>
            <tr>
                <td>Degree Day Coverage (days)</td>
                <td>{data_stats.get('degree_day_coverage_days', 0):,}</td>
            </tr>
            <tr>
                <td>Degree Day Gaps</td>
                <td>{data_stats.get('degree_day_gaps', 0):,}</td>
            </tr>
        </table>
    </div>
    """


def generate_risk_analysis_section(proposals: pd.DataFrame,
                                  risk_metrics: Dict) -> str:
    """Generate risk analysis section."""

    high_risk = risk_metrics.get('high_risk_count', 0)
    medium_risk = risk_metrics.get('medium_risk_count', 0)
    low_risk = risk_metrics.get('low_risk_count', 0)
    avg_risk = risk_metrics.get('avg_risk_score', 0)

    return f"""
    <div class="section">
        <h2>Runout Risk Analysis</h2>
        <div class="summary-grid">
            <div class="metric">
                <div class="metric-label">High Risk (≥70)</div>
                <div class="metric-value" style="color: #e74c3c;">{high_risk}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Medium Risk (40-69)</div>
                <div class="metric-value" style="color: #f39c12;">{medium_risk}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Low Risk (<40)</div>
                <div class="metric-value" style="color: #2ecc71;">{low_risk}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Avg Risk Score</div>
                <div class="metric-value">{avg_risk:.1f}</div>
            </div>
        </div>

        <div class="info">
            <strong>Note:</strong> High-risk customers (score ≥70) receive priority for K-factor increases
            and are protected from decreases to prevent runouts.
        </div>
    </div>
    """


def generate_top_changes_section(proposals: pd.DataFrame) -> str:
    """Generate top increases and decreases section."""

    # Top 25 increases
    increases = proposals[proposals['ChangePct'] > 0].copy()
    increases = increases.sort_values('ChangePct', ascending=False).head(25)

    # Top 25 decreases
    decreases = proposals[proposals['ChangePct'] < 0].copy()
    decreases = decreases.sort_values('ChangePct').head(25)

    html = """
    <div class="section">
        <h2>Proposed Changes by Risk Tier</h2>

        <h3>Top 25 K-Factor Increases</h3>
        <table>
            <tr>
                <th>Customer ID</th>
                <th>Fuel Type</th>
                <th>Current K</th>
                <th>Proposed K</th>
                <th>Change %</th>
                <th>Risk</th>
                <th>Confidence</th>
                <th>Method</th>
            </tr>
    """

    for idx, row in increases.iterrows():
        risk_badge = f'<span class="badge badge-{row.get("RiskTier", "low").lower()}">{row.get("RiskTier", "Low")}</span>'
        conf_badge = f'<span class="badge badge-confidence-{row.get("Confidence", "low").lower()}">{row.get("Confidence", "Low")}</span>'

        html += f"""
            <tr>
                <td>{row['CustomerID']}</td>
                <td>{row['FuelType']}</td>
                <td>{row['CurrentKFactor_Before']:.4f}</td>
                <td>{row['ProposedKFactor']:.4f}</td>
                <td class="increase">+{row['ChangePct']:.1f}%</td>
                <td>{risk_badge}</td>
                <td>{conf_badge}</td>
                <td>{row['Method']}</td>
            </tr>
        """

    html += """
        </table>

        <h3>Top 25 K-Factor Decreases</h3>
        <table>
            <tr>
                <th>Customer ID</th>
                <th>Fuel Type</th>
                <th>Current K</th>
                <th>Proposed K</th>
                <th>Change %</th>
                <th>Risk</th>
                <th>Confidence</th>
                <th>Method</th>
            </tr>
    """

    for idx, row in decreases.iterrows():
        risk_badge = f'<span class="badge badge-{row.get("RiskTier", "low").lower()}">{row.get("RiskTier", "Low")}</span>'
        conf_badge = f'<span class="badge badge-confidence-{row.get("Confidence", "low").lower()}">{row.get("Confidence", "Low")}</span>'

        html += f"""
            <tr>
                <td>{row['CustomerID']}</td>
                <td>{row['FuelType']}</td>
                <td>{row['CurrentKFactor_Before']:.4f}</td>
                <td>{row['ProposedKFactor']:.4f}</td>
                <td class="decrease">{row['ChangePct']:.1f}%</td>
                <td>{risk_badge}</td>
                <td>{conf_badge}</td>
                <td>{row['Method']}</td>
            </tr>
        """

    html += """
        </table>
    </div>
    """

    return html


def generate_rejected_changes_section(proposals: pd.DataFrame) -> str:
    """Generate rejected/skipped changes section."""

    # Filter to problematic reason codes
    rejected_codes = [
        'INSUFFICIENT_DATA',
        'TANK_SANITY_TOO_LARGE',
        'TANK_SANITY_TOO_SMALL',
        'HIGH_RISK_NO_DECREASE',
        'ERROR'
    ]

    rejected = proposals[proposals['ReasonCode'].isin(rejected_codes)].copy()

    if len(rejected) == 0:
        return """
        <div class="section">
            <h2>Rejected Changes</h2>
            <p>No rejected changes - all proposals passed validation checks.</p>
        </div>
        """

    # Count by reason
    reason_counts = rejected['ReasonCode'].value_counts()

    html = """
    <div class="section">
        <h2>Rejected Changes & Why</h2>
        <p>The following customers were skipped or had changes rejected due to data quality or safety checks:</p>

        <h3>Summary by Reason</h3>
        <table>
            <tr>
                <th>Reason Code</th>
                <th>Count</th>
                <th>Description</th>
            </tr>
    """

    reason_descriptions = {
        'INSUFFICIENT_DATA': 'Not enough delivery history to calculate reliable K-factor',
        'TANK_SANITY_TOO_LARGE': 'Proposed K would result in delivery exceeding tank size',
        'TANK_SANITY_TOO_SMALL': 'Proposed K would result in unrealistically small delivery',
        'HIGH_RISK_NO_DECREASE': 'K-factor decrease rejected for high-risk customer to prevent runout',
        'ERROR': 'Processing error occurred',
    }

    for reason, count in reason_counts.items():
        desc = reason_descriptions.get(reason, 'Unknown reason')
        html += f"""
            <tr>
                <td><code>{reason}</code></td>
                <td>{count}</td>
                <td>{desc}</td>
            </tr>
        """

    html += """
        </table>

        <h3>Details (First 50)</h3>
        <table>
            <tr>
                <th>Customer ID</th>
                <th>Fuel Type</th>
                <th>Reason Code</th>
                <th>Notes</th>
            </tr>
    """

    for idx, row in rejected.head(50).iterrows():
        html += f"""
            <tr>
                <td>{row['CustomerID']}</td>
                <td>{row['FuelType']}</td>
                <td><code>{row['ReasonCode']}</code></td>
                <td>{row.get('Notes', '')}</td>
            </tr>
        """

    html += """
        </table>
    </div>
    """

    return html


def generate_method_breakdown_section(proposals: pd.DataFrame) -> str:
    """Generate method breakdown section."""

    method_counts = proposals['Method'].value_counts()

    html = """
    <div class="section">
        <h2>Calculation Method Breakdown</h2>
        <table>
            <tr>
                <th>Method</th>
                <th>Count</th>
                <th>Description</th>
            </tr>
    """

    method_descriptions = {
        'Classical': 'K-factor calculated from most recent delivery (Gallons ÷ Degree Days)',
        'SmartKBlend': 'Blended SmartK seasonal forecast with classical calculation',
        'Baseline': 'Robust baseline K from historical fill-ups (winsorized weighted median)',
        'BaselineDrift': 'Drifted current K toward baseline (no recent delivery data)',
        'Unknown': 'Method could not be determined',
    }

    for method, count in method_counts.items():
        desc = method_descriptions.get(method, 'Unknown method')
        html += f"""
            <tr>
                <td><strong>{method}</strong></td>
                <td>{count}</td>
                <td>{desc}</td>
            </tr>
        """

    html += """
        </table>
    </div>
    """

    return html
