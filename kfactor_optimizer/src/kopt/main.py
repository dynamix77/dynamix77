"""
K-Factor Optimizer CLI Entry Point

Production-grade tool to propose weekly K-factor updates for automatic-delivery customers.
"""

import argparse
import logging
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

from . import io, propose, report, risk as risk_module


def setup_logging(log_dir: Path, verbose: bool = False):
    """Configure logging to file and console."""

    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"optimizer_run_{timestamp}.log"

    # Configure root logger
    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return log_file


def main():
    """Main CLI entry point."""

    parser = argparse.ArgumentParser(
        description='K-Factor Optimizer for Ignite Fuel Delivery',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m kopt.main \\
    --customer-fuel "C:\\Users\\Jonathan\\Downloads\\03_CustomerFuel.csv" \\
    --deliveries    "C:\\Users\\Jonathan\\Downloads\\04_DeliveryTickets.csv" \\
    --degreedays    "C:\\Users\\Jonathan\\Downloads\\06_DegreeDayValues.csv" \\
    --outdir        "C:\\Users\\Jonathan\\Downloads\\KOpt_Out"
        """
    )

    parser.add_argument(
        '--customer-fuel',
        required=True,
        help='Path to CustomerFuel CSV (03_CustomerFuel.csv)'
    )

    parser.add_argument(
        '--deliveries',
        required=True,
        help='Path to DeliveryTickets CSV (04_DeliveryTickets.csv)'
    )

    parser.add_argument(
        '--degreedays',
        required=True,
        help='Path to DegreeDayValues CSV (06_DegreeDayValues.csv)'
    )

    parser.add_argument(
        '--outdir',
        required=True,
        help='Output directory for results'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup output directory
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    log_dir = outdir / 'logs'
    log_file = setup_logging(log_dir, args.verbose)

    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("K-FACTOR OPTIMIZER")
    logger.info("=" * 80)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Log file: {log_file}")

    try:
        # Load data
        logger.info("Loading input data...")
        customer_fuel = io.load_customer_fuel(args.customer_fuel)
        delivery_tickets = io.load_delivery_tickets(args.deliveries)
        degree_days = io.load_degree_days(args.degreedays)

        # Validate data quality
        logger.info("Validating data quality...")
        data_stats = io.validate_data_quality(customer_fuel, delivery_tickets, degree_days)

        logger.info("Data Quality Summary:")
        for key, value in data_stats.items():
            logger.info(f"  {key}: {value}")

        # Generate proposals
        logger.info("Generating K-factor proposals...")
        proposals = propose.generate_proposals(customer_fuel, delivery_tickets, degree_days)

        # Calculate risk metrics
        logger.info("Calculating risk metrics...")
        risk_metrics, proposals = risk_module.calculate_risk_metrics(
            proposals, customer_fuel, delivery_tickets, degree_days
        )

        logger.info("Risk Metrics:")
        for key, value in risk_metrics.items():
            logger.info(f"  {key}: {value}")

        # Save CSV output
        csv_path = outdir / "Apply_K_ThisWeek.csv"
        logger.info(f"Saving CSV output: {csv_path}")

        output_cols = [
            'CustomerFuelID', 'CustomerID', 'LocationNumber', 'FuelType',
            'CurrentKFactor_Before', 'ProposedKFactor', 'ChangePct',
            'ReasonCode', 'Method', 'SeasonTarget', 'Confidence', 'Notes'
        ]

        proposals[output_cols].to_csv(csv_path, index=False)

        # Generate HTML report
        html_path = outdir / "Optimizer_Report.html"
        logger.info(f"Generating HTML report: {html_path}")
        report.generate_html_report(proposals, data_stats, risk_metrics, str(html_path))

        # Save JSON log
        json_path = log_dir / f"optimizer_run_{datetime.now().strftime('%Y%m%d')}.json"
        logger.info(f"Saving JSON log: {json_path}")

        json_data = {
            'timestamp': datetime.now().isoformat(),
            'input_files': {
                'customer_fuel': args.customer_fuel,
                'deliveries': args.deliveries,
                'degreedays': args.degreedays,
            },
            'data_stats': data_stats,
            'risk_metrics': risk_metrics,
            'proposal_summary': {
                'total_customers': len(proposals),
                'with_changes': int((proposals['ChangePct'].notna() & (proposals['ChangePct'].abs() > 1)).sum()),
                'increases': int((proposals['ChangePct'] > 1).sum()),
                'decreases': int((proposals['ChangePct'] < -1).sum()),
                'avg_change_pct': float(proposals[proposals['ChangePct'].notna()]['ChangePct'].mean()),
            },
            'reason_code_breakdown': proposals['ReasonCode'].value_counts().to_dict(),
            'method_breakdown': proposals['Method'].value_counts().to_dict(),
        }

        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)

        # Summary
        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total customers processed: {len(proposals)}")
        logger.info(f"Proposals with changes: {json_data['proposal_summary']['with_changes']}")
        logger.info(f"Increases: {json_data['proposal_summary']['increases']}")
        logger.info(f"Decreases: {json_data['proposal_summary']['decreases']}")
        logger.info(f"Average change: {json_data['proposal_summary']['avg_change_pct']:.2f}%")
        logger.info("")
        logger.info(f"Output files:")
        logger.info(f"  CSV: {csv_path}")
        logger.info(f"  HTML Report: {html_path}")
        logger.info(f"  JSON Log: {json_path}")
        logger.info("")
        logger.info("SUCCESS - K-factor optimization complete!")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"FATAL ERROR: {e}", exc_info=True)
        logger.error("K-factor optimization failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
