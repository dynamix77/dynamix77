# K-Factor Optimizer for Ignite Fuel Delivery

Production-grade tool to propose weekly K-factor updates for automatic-delivery customers. Optimizes to reduce runouts without over-servicing while honoring Ignite's business rules.

## Overview

The K-Factor Optimizer analyzes historical delivery data, degree days, and customer fuel records to propose optimal K-factor (gallons per degree day) updates. It uses robust statistical methods, seasonal adjustments, and risk scoring to ensure safe and efficient fuel delivery scheduling.

### Key Features

- **Robust K-Factor Calculation**: Winsorized weighted median from historical fill-ups
- **SmartK Blending**: Combines seasonal forecasts with classical calculations
- **Risk-Based Adjustments**: Prioritizes runout prevention for high-risk customers
- **Seasonal Intelligence**: Adapts to Winter/Spring/Summer/Fall usage patterns
- **Comprehensive Guardrails**: Enforces caps, tank sanity checks, and data quality filters
- **Production-Ready Outputs**: CSV for batch import + HTML report + JSON logs

## Prerequisites

- Python 3.9 or higher
- pip (Python package installer)

## Installation

1. Navigate to the project directory:

```bash
cd kfactor_optimizer
```

2. Install dependencies:

```bash
pip install -e .
```

Or install with development dependencies (for running tests):

```bash
pip install -e ".[dev]"
```

## Usage

### Basic Usage

Run the optimizer with three Ignite export files:

```bash
python -m kopt.main \
  --customer-fuel "C:\Users\Jonathan\Downloads\03_CustomerFuel.csv" \
  --deliveries    "C:\Users\Jonathan\Downloads\04_DeliveryTickets.csv" \
  --degreedays    "C:\Users\Jonathan\Downloads\06_DegreeDayValues.csv" \
  --outdir        "C:\Users\Jonathan\Downloads\KOpt_Out"
```

**Windows Command Prompt (use `^` for line continuation):**

```cmd
python -m kopt.main ^
  --customer-fuel "C:\Users\Jonathan\Downloads\03_CustomerFuel.csv" ^
  --deliveries    "C:\Users\Jonathan\Downloads\04_DeliveryTickets.csv" ^
  --degreedays    "C:\Users\Jonathan\Downloads\06_DegreeDayValues.csv" ^
  --outdir        "C:\Users\Jonathan\Downloads\KOpt_Out"
```

### Command-Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--customer-fuel` | Yes | Path to CustomerFuel CSV (03_CustomerFuel.csv) |
| `--deliveries` | Yes | Path to DeliveryTickets CSV (04_DeliveryTickets.csv) |
| `--degreedays` | Yes | Path to DegreeDayValues CSV (06_DegreeDayValues.csv) |
| `--outdir` | Yes | Output directory for results |
| `--verbose` | No | Enable verbose logging (debug mode) |

### Example Output

The tool generates three output files in the specified directory:

1. **Apply_K_ThisWeek.csv** - Ready to import into Ignite
2. **Optimizer_Report.html** - Human-readable analysis report
3. **logs/optimizer_run_YYYYMMDD.json** - Machine-readable decision log

## Input File Requirements

### CustomerFuel CSV (03_CustomerFuel.csv)

Expected columns (column names are flexible - tool normalizes variations):

- **CustomerFuelID** - Unique identifier for customer fuel record
- **CustomerID** - Customer identifier
- **LocationNumber** - Location/account number
- **FuelType** - Fuel product type (Oil, Propane, etc.)
- **CurrentK** / **KFactor** - Current K-factor value
- **PreviousK** - Previous K-factor value
- **WinterK**, **SpringK**, **SummerK**, **FallK** - Seasonal K-factors
- **UsableSize** - Tank usable capacity (gallons)
- **PercentFull** - Current tank level percentage
- **OptimumDelivery** - Target delivery quantity
- **NextDDay** - Next scheduled delivery date
- **RunOutDDay** - Estimated runout date
- **AllowSmartK** / **SmartKActive** - SmartK eligibility flags
- **AutoDelivery** - Automatic delivery flag (only auto customers are processed)

### DeliveryTickets CSV (04_DeliveryTickets.csv)

Expected columns:

- **TicketID** - Unique ticket identifier
- **CustomerFuelID** - Links to CustomerFuel
- **DeliveryDate** - Date of delivery
- **Quantity** - Gallons delivered
- **IsFill** - Whether delivery was a fill-up (True/False)
- **TicketDDay** - Degree days at delivery (optional - calculated if missing)

### DegreeDayValues CSV (06_DegreeDayValues.csv)

Expected columns:

- **Date** - Calendar date
- **HDD** - Heating degree days for that date
- **Area** - Optional area/zone identifier

## Output Files

### 1. Apply_K_ThisWeek.csv

Ready-to-apply K-factor updates with columns:

- **CustomerFuelID** - Customer identifier
- **CustomerID** - Customer number
- **LocationNumber** - Account location
- **FuelType** - Fuel product
- **CurrentKFactor_Before** - K-factor before update
- **ProposedKFactor** - Recommended new K-factor
- **ChangePct** - Percentage change
- **ReasonCode** - Why this proposal was made
- **Method** - Calculation method (Classical, SmartKBlend, Baseline, etc.)
- **SeasonTarget** - Target season for this K-factor
- **Confidence** - Data quality confidence (High, Medium, Low)
- **Notes** - Additional context

### 2. Optimizer_Report.html

Comprehensive HTML report with:

- **Executive Summary** - Key metrics and change counts
- **Data Coverage** - Input data quality statistics
- **Runout Risk Analysis** - Risk distribution and high-risk customers
- **Top Changes** - Top 25 increases and decreases
- **Rejected Changes** - Skipped customers with explanations
- **Method Breakdown** - Distribution of calculation methods

### 3. logs/optimizer_run_YYYYMMDD.json

Machine-readable log containing:

- Run timestamp and input file paths
- Data quality statistics
- Risk metrics
- Proposal summary statistics
- Reason code breakdown
- Per-customer decision metadata (in full logs)

## Importing Results into Ignite

To apply the proposed K-factor updates:

1. Open the generated `Apply_K_ThisWeek.csv` in Excel or text editor

2. Review the proposals, focusing on:
   - **High-risk customers** (check Confidence and Notes)
   - **Large changes** (>20% increases or >40% decreases)
   - **Rejected changes** (ReasonCode indicates issues)

3. Filter to changes you want to apply (optional):
   - Remove rows with `ReasonCode` like `INSUFFICIENT_DATA` or `TANK_SANITY_*`
   - Review `Confidence=Low` proposals carefully

4. Use Ignite's **batch fuel record update** workflow:
   - In Ignite, navigate to your bulk update tool for CustomerFuel records
   - Import the CSV using `CustomerFuelID` as the key
   - Map `ProposedKFactor` to the `CurrentK` or `KFactor` field
   - Apply seasonal K-factors if `SeasonTarget` indicates a season change

5. Monitor results:
   - Check the HTML report for expected runout risk reductions
   - Review high-risk customers in the next week to ensure deliveries are scheduled

## Business Rules and Guardrails

### K-Factor Caps

- **Default**: ±10% increase, -50% decrease (Medium data quality)
- **High Quality**: ±15% increase, -60% decrease (≥3 recent fills, good degree day data)
- **High Risk**: Up to ±20% increase allowed (to prevent runouts)
- **Low Confidence**: Caps reduced by 50%

### Data Quality Tiers

- **High**: ≥3 recent fills (180 days), good degree day coverage
- **Medium**: ≥2 recent fills or good degree day data
- **Low**: Insufficient fills, gaps in degree day data, or old deliveries

### Risk Scoring (0-100)

Risk factors:

- Days since last fill (0-30 points)
- Days to empty / RunOutDDay (0-30 points)
- Usage variance / inconsistency (0-15 points)
- Winter season penalty (0-10 points)
- Small tank penalty (<200 gal: 0-10 points)
- Low tank level (0-5 points)

Risk tiers:

- **High**: ≥70 (aggressive K increases, no decreases)
- **Medium**: 40-69 (balanced approach)
- **Low**: <40 (conservative adjustments)

### Tank Sanity Checks

- Proposed K must not imply delivery > UsableSize
- Proposed K must not imply delivery < 20% of OptimumDelivery
- Failed checks result in `TANK_SANITY_*` ReasonCode and revert to current K

### Seasonal Adjustments

- If current season's K differs >15% from historical seasonal K, nudge by ≤10%
- Preview next season if within 21 days of season transition
- Seasonal K targets: Winter (Dec-Feb), Spring (Mar-May), Summer (Jun-Aug), Fall (Sep-Nov)

### SmartK Blending

Eligibility requirements:

- `AllowSmartK` or `SmartKActive` flag enabled
- ≥4 deliveries per year
- ≥14 months of history
- ≥1 fill-up in history

Confidence scoring based on:

- History span (24+ months = higher confidence)
- Delivery frequency (6+ per year = higher confidence)
- Fill ratio (80%+ fills = higher confidence)
- Data quality (good degree day coverage)
- Usage stability (low coefficient of variation)

Blending formula:

```
K_proposed = w * K_SmartK + (1-w) * K_Classical
```

where `w = min(SmartK_confidence, 0.7)` (capped at 70% weight)

## Running Tests

Run the test suite to validate the installation:

```bash
pytest
```

Run with coverage report:

```bash
pytest --cov=kopt --cov-report=html
```

Run specific test files:

```bash
pytest tests/test_io.py
pytest tests/test_baseline.py
pytest tests/test_caps.py
pytest tests/test_end_to_end.py
```

## Architecture

### Module Overview

- **io.py** - CSV loading, schema normalization, validation
- **dday.py** - Degree day aggregation, gap detection, seasonal logic
- **baseline.py** - Robust K-factor calculation (winsorized weighted median)
- **smartk.py** - SmartK eligibility, confidence scoring, seasonal forecasts
- **propose.py** - Core proposal engine (caps, sanity checks, risk integration)
- **risk.py** - Runout risk scoring (0-100 scale)
- **report.py** - HTML report generation
- **main.py** - CLI entry point and orchestration

### Data Flow

```
Input CSVs
    ↓
io.load_*() - Normalize and validate
    ↓
dday.calculate_delivery_ddays() - Aggregate degree days
    ↓
propose.generate_proposals() - For each customer:
    ├── baseline.calculate_robust_baseline_k()
    ├── baseline.calculate_classical_k()
    ├── smartk.should_use_smartk()
    ├── risk.calculate_risk_score()
    ├── propose.apply_caps()
    └── propose.check_tank_sanity()
    ↓
risk.calculate_risk_metrics() - Aggregate risk analysis
    ↓
Output CSVs + HTML + JSON logs
```

## Troubleshooting

### "Missing required columns" error

- Check that input CSVs have expected column names
- Tool accepts variations (e.g., "K Factor" vs "KFactor")
- See `CUSTOMER_FUEL_MAPPINGS` in `io.py` for recognized variations

### Low coverage (<95%)

- Check for customers with `INSUFFICIENT_DATA` in ReasonCode
- Ensure DeliveryTickets has recent deliveries (last 180 days)
- Verify degree day coverage matches delivery date ranges

### All proposals have "INSUFFICIENT_DATA"

- Deliveries may not be linked to CustomerFuelID correctly
- Check that CustomerFuelID values match between files
- Ensure delivery dates are within degree day coverage period

### SmartK not being used

- Verify `AllowSmartK` or `SmartKActive` flags are set
- Check eligibility criteria (≥4 deliveries/year, ≥14 months history)
- Review SmartK confidence scores in JSON logs

### Tank sanity check failures

- Review UsableSize and OptimumDelivery values in CustomerFuel
- Check for unrealistic K-factor changes
- Inspect `TANK_SANITY_*` ReasonCodes in output

## Support and Feedback

For issues, feature requests, or questions:

1. Review the HTML report for insights into data quality issues
2. Check the JSON logs for detailed per-customer decision traces
3. Run with `--verbose` flag for debug-level logging
4. Consult Ignite documentation for data export procedures

## License

Copyright © 2024 Fox Fuel. All rights reserved.

This tool is designed for internal use with Ignite fuel delivery management system.

## Version History

**v1.0.0** (2024-01-15)
- Initial production release
- Robust baseline K calculation
- SmartK blending support
- Risk-based adjustments
- Seasonal intelligence
- Comprehensive reporting
