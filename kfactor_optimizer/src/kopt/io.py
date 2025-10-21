"""
Data loading and validation for K-factor optimizer.

Handles CSV import with schema normalization and validation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


# Column name mappings: variations → canonical names
CUSTOMER_FUEL_MAPPINGS = {
    'CustomerFuelID': ['CustomerFuelID', 'customer_fuel_id', 'FuelID'],
    'CustomerID': ['CustomerID', 'customer_id', 'CustID'],
    'LocationNumber': ['LocationNumber', 'location_number', 'Location', 'LocNum'],
    'FuelType': ['FuelType', 'fuel_type', 'Product'],
    'CurrentK': ['CurrentK', 'CurrentKFactor', 'Current K Factor', 'K Factor', 'KFactor'],
    'PreviousK': ['PreviousK', 'PreviousKFactor', 'Previous K Factor', 'PrevK'],
    'WinterK': ['WinterK', 'Winter K Factor', 'WinterKFactor'],
    'SpringK': ['SpringK', 'Spring K Factor', 'SpringKFactor'],
    'SummerK': ['SummerK', 'Summer K Factor', 'SummerKFactor'],
    'FallK': ['FallK', 'Fall K Factor', 'FallKFactor'],
    'UsableSize': ['UsableSize', 'Usable Size', 'TankSize', 'Tank Size'],
    'PercentFull': ['PercentFull', 'Percent Full', 'PctFull', '%Full'],
    'OptimumDelivery': ['OptimumDelivery', 'Optimum Delivery', 'OptDelivery'],
    'NextDDay': ['NextDDay', 'NextDeliveryDay', 'Next DDay'],
    'RunOutDDay': ['RunOutDDay', 'RunOut DDay', 'RunoutDay'],
    'AllowSmartK': ['AllowSmartK', 'Allow Smart K', 'SmartKAllowed'],
    'SmartKActive': ['SmartKActive', 'Smart K Active', 'SmartK'],
    'AutoDelivery': ['AutoDelivery', 'Auto Delivery', 'Automatic', 'IsAuto'],
}

DELIVERY_TICKET_MAPPINGS = {
    'TicketID': ['TicketID', 'ticket_id', 'DeliveryID', 'ID'],
    'CustomerFuelID': ['CustomerFuelID', 'customer_fuel_id', 'FuelID'],
    'CustomerID': ['CustomerID', 'customer_id', 'CustID'],
    'DeliveryDate': ['DeliveryDate', 'delivery_date', 'Date', 'TicketDate'],
    'Quantity': ['Quantity', 'quantity', 'Gallons', 'Amount', 'Delivered'],
    'TicketDDay': ['TicketDDay', 'Ticket DDay', 'DegreeDays', 'DDays'],
    'IsFill': ['IsFill', 'is_fill', 'Fill', 'FillUp'],
}

DEGREE_DAY_MAPPINGS = {
    'Date': ['Date', 'date', 'Day'],
    'Area': ['Area', 'area', 'Zone', 'Location'],
    'HDD': ['HDD', 'hdd', 'HeatingDegreeDays', 'DegreeDays', 'DegreeDay'],
}


def normalize_column_names(df: pd.DataFrame, mappings: Dict[str, List[str]]) -> pd.DataFrame:
    """
    Normalize DataFrame column names to canonical form.

    Args:
        df: Input DataFrame
        mappings: Dict mapping canonical names to possible variations

    Returns:
        DataFrame with normalized column names
    """
    rename_map = {}

    for canonical, variations in mappings.items():
        for col in df.columns:
            if col in variations:
                rename_map[col] = canonical
                break

    normalized = df.rename(columns=rename_map)

    # Log any missing canonical columns
    missing = set(mappings.keys()) - set(normalized.columns)
    if missing:
        logger.warning(f"Missing expected columns after normalization: {missing}")

    return normalized


def load_customer_fuel(path: str) -> pd.DataFrame:
    """
    Load and validate CustomerFuel CSV.

    Args:
        path: Path to CustomerFuel CSV

    Returns:
        DataFrame with normalized columns
    """
    logger.info(f"Loading CustomerFuel from {path}")

    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} customer fuel records")

    # Normalize column names
    df = normalize_column_names(df, CUSTOMER_FUEL_MAPPINGS)

    # Required columns
    required = ['CustomerFuelID', 'CustomerID', 'FuelType']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in CustomerFuel: {missing}")

    # Convert numeric columns
    numeric_cols = ['CurrentK', 'PreviousK', 'WinterK', 'SpringK', 'SummerK', 'FallK',
                    'UsableSize', 'PercentFull', 'OptimumDelivery']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Convert boolean columns
    bool_cols = ['AllowSmartK', 'SmartKActive', 'AutoDelivery']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    # Date columns
    date_cols = ['NextDDay', 'RunOutDDay']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Filter to automatic delivery customers only
    if 'AutoDelivery' in df.columns:
        auto_count = df['AutoDelivery'].sum()
        logger.info(f"Found {auto_count} automatic delivery customers")

    logger.info(f"CustomerFuel loaded successfully: {len(df)} records")
    return df


def load_delivery_tickets(path: str) -> pd.DataFrame:
    """
    Load and validate DeliveryTickets CSV.

    Args:
        path: Path to DeliveryTickets CSV

    Returns:
        DataFrame with normalized columns
    """
    logger.info(f"Loading DeliveryTickets from {path}")

    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} delivery tickets")

    # Normalize column names
    df = normalize_column_names(df, DELIVERY_TICKET_MAPPINGS)

    # Required columns
    required = ['CustomerFuelID', 'DeliveryDate', 'Quantity']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in DeliveryTickets: {missing}")

    # Convert date
    df['DeliveryDate'] = pd.to_datetime(df['DeliveryDate'], errors='coerce')

    # Convert numeric columns
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
    if 'TicketDDay' in df.columns:
        df['TicketDDay'] = pd.to_numeric(df['TicketDDay'], errors='coerce')

    # Convert boolean
    if 'IsFill' in df.columns:
        df['IsFill'] = df['IsFill'].fillna(False).astype(bool)

    # Drop invalid records
    invalid = df['DeliveryDate'].isna() | df['Quantity'].isna() | (df['Quantity'] <= 0)
    if invalid.sum() > 0:
        logger.warning(f"Dropping {invalid.sum()} invalid delivery records")
        df = df[~invalid]

    # Sort by date
    df = df.sort_values(['CustomerFuelID', 'DeliveryDate'])

    logger.info(f"DeliveryTickets loaded successfully: {len(df)} records")
    return df


def load_degree_days(path: str) -> pd.DataFrame:
    """
    Load and validate DegreeDayValues CSV.

    Args:
        path: Path to DegreeDayValues CSV

    Returns:
        DataFrame with normalized columns
    """
    logger.info(f"Loading DegreeDayValues from {path}")

    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} degree day records")

    # Normalize column names
    df = normalize_column_names(df, DEGREE_DAY_MAPPINGS)

    # Required columns
    required = ['Date', 'HDD']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in DegreeDayValues: {missing}")

    # Convert date
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    # Convert numeric
    df['HDD'] = pd.to_numeric(df['HDD'], errors='coerce')

    # Drop invalid records
    invalid = df['Date'].isna() | df['HDD'].isna()
    if invalid.sum() > 0:
        logger.warning(f"Dropping {invalid.sum()} invalid degree day records")
        df = df[~invalid]

    # Sort by date
    df = df.sort_values(['Date'])

    # Check for gaps
    if 'Area' in df.columns:
        for area in df['Area'].unique():
            area_df = df[df['Area'] == area].copy()
            date_range = pd.date_range(area_df['Date'].min(), area_df['Date'].max())
            missing_dates = set(date_range) - set(area_df['Date'])
            if missing_dates:
                logger.warning(f"Area {area}: {len(missing_dates)} missing dates in degree day series")
    else:
        date_range = pd.date_range(df['Date'].min(), df['Date'].max())
        missing_dates = set(date_range) - set(df['Date'])
        if missing_dates:
            logger.warning(f"{len(missing_dates)} missing dates in degree day series")

    logger.info(f"DegreeDayValues loaded successfully: {len(df)} records")
    return df


def validate_data_quality(customer_fuel: pd.DataFrame,
                         delivery_tickets: pd.DataFrame,
                         degree_days: pd.DataFrame) -> Dict[str, any]:
    """
    Validate overall data quality and return statistics.

    Returns:
        Dict with validation metrics
    """
    stats = {
        'customer_fuel_count': len(customer_fuel),
        'delivery_ticket_count': len(delivery_tickets),
        'degree_day_count': len(degree_days),
        'customers_with_deliveries': 0,
        'customers_with_recent_deliveries': 0,
        'avg_deliveries_per_customer': 0,
        'degree_day_coverage_days': 0,
        'degree_day_gaps': 0,
    }

    # Delivery coverage
    if len(delivery_tickets) > 0:
        delivery_counts = delivery_tickets.groupby('CustomerFuelID').size()
        stats['customers_with_deliveries'] = len(delivery_counts)
        stats['avg_deliveries_per_customer'] = delivery_counts.mean()

        # Recent deliveries (last 180 days)
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=180)
        recent = delivery_tickets[delivery_tickets['DeliveryDate'] >= cutoff]
        stats['customers_with_recent_deliveries'] = recent['CustomerFuelID'].nunique()

    # Degree day coverage
    if len(degree_days) > 0:
        date_range = (degree_days['Date'].max() - degree_days['Date'].min()).days
        stats['degree_day_coverage_days'] = date_range

        # Approximate gaps (assuming one area)
        expected_records = date_range + 1
        stats['degree_day_gaps'] = expected_records - len(degree_days)

    return stats
