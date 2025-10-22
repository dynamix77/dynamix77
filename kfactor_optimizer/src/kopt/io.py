"""
Data loading and validation for K-factor optimizer.

Handles CSV import with schema normalization and validation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Set
import logging
import re

logger = logging.getLogger(__name__)


def _normalize_header(header: str) -> str:
    """
    Normalize a single header string for fuzzy matching.

    Converts to lowercase, strips leading/trailing whitespace,
    and removes special characters (keeping only alphanumeric and spaces).

    Args:
        header: Raw header string

    Returns:
        Normalized header string
    """
    # Strip whitespace
    normalized = header.strip()
    # Convert to lowercase
    normalized = normalized.lower()
    # Remove special chars except spaces (keep alphanumeric + spaces)
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    # Collapse multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    # Final strip
    normalized = normalized.strip()
    return normalized


# Column name mappings: variations → canonical names
# Now includes both exact matches and normalized synonyms
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

# Extended synonym map for Ignite export headers (normalized form → canonical name)
# This maps normalized lowercase strings to internal canonical field names
CUSTOMER_FUEL_SYNONYMS = {
    # CustomerFuelID mappings
    'customer fuel unique id': 'CustomerFuelID',
    'pidcustomerfuel1': 'CustomerFuelID',
    'customerfuelid': 'CustomerFuelID',
    'customer fuel id': 'CustomerFuelID',
    'fuelid': 'CustomerFuelID',

    # CustomerID mappings
    'customer number': 'CustomerID',
    'customerid': 'CustomerID',
    'customer id': 'CustomerID',
    'custid': 'CustomerID',

    # Optional context field
    'customer code': 'CustomerCode',
    'customercode': 'CustomerCode',

    # LocationNumber mappings
    'customer location unique id': 'LocationNumber',
    'locationnumber': 'LocationNumber',
    'location number': 'LocationNumber',
    'location': 'LocationNumber',
    'locnum': 'LocationNumber',

    # FuelType mappings
    'customer fuel type': 'FuelType',
    'fueltype': 'FuelType',
    'fuel type': 'FuelType',
    'product': 'FuelType',

    # K Factor mappings
    'k factor': 'CurrentK',
    'kfactor': 'CurrentK',
    'currentk': 'CurrentK',
    'currentkfactor': 'CurrentK',
    'current k factor': 'CurrentK',

    'previous k factor': 'PreviousK',
    'previousk': 'PreviousK',
    'previouskfactor': 'PreviousK',
    'prevk': 'PreviousK',

    'previous k factor 2nd': 'PreviousK2',
    'previousk2': 'PreviousK2',

    # Seasonal K factors
    'k factor  winter': 'WinterK',
    'k factor winter': 'WinterK',
    'winterk': 'WinterK',
    'winter k factor': 'WinterK',
    'winterkfactor': 'WinterK',

    'k factor  summer': 'SummerK',
    'k factor summer': 'SummerK',
    'summerk': 'SummerK',
    'summer k factor': 'SummerK',
    'summerkfactor': 'SummerK',

    'k factor  fall': 'FallK',
    'k factor fall': 'FallK',
    'fallk': 'FallK',
    'fall k factor': 'FallK',
    'fallkfactor': 'FallK',

    'k factor  spring': 'SpringK',
    'k factor spring': 'SpringK',
    'springk': 'SpringK',
    'spring k factor': 'SpringK',
    'springkfactor': 'SpringK',

    # Tank and delivery fields
    'usable size': 'UsableSize',
    'usablesize': 'UsableSize',
    'tanksize': 'UsableSize',
    'tank size': 'UsableSize',

    'optimum delivery  fuel': 'OptimumDelivery',
    'optimum delivery fuel': 'OptimumDelivery',
    'optimumdelivery': 'OptimumDelivery',
    'optimum delivery': 'OptimumDelivery',
    'optdelivery': 'OptimumDelivery',

    'currently in tank': 'CurrentlyInTank',
    'currentlyintank': 'CurrentlyInTank',

    ' full': 'PercentFull',
    'full': 'PercentFull',
    'percentfull': 'PercentFull',
    'percent full': 'PercentFull',
    'pctfull': 'PercentFull',

    # Delivery mode
    'automatic delivery': 'AutoDelivery',
    'autodelivery': 'AutoDelivery',
    'auto delivery': 'AutoDelivery',
    'automatic': 'AutoDelivery',
    'isauto': 'AutoDelivery',

    # SmartK fields
    'allow smart k': 'SmartKActive',
    'allowsmartk': 'SmartKActive',
    'smartkactive': 'SmartKActive',
    'smart k active': 'SmartKActive',
    'smartk': 'SmartKActive',
    'smartkallowed': 'SmartKActive',

    'smart k predictability': 'SmartKPredictability',
    'smartkpredictability': 'SmartKPredictability',

    'smart k previous predictability': 'SmartKPrevPredictability',
    'smartkprevpredictability': 'SmartKPrevPredictability',

    'recalc k factor': 'RecalcK',
    'recalck': 'RecalcK',
    'recalckfactor': 'RecalcK',

    # Date fields
    'last dday': 'LastDDay',
    'lastdday': 'LastDDay',

    'next dday': 'NextDDay',
    'nextdday': 'NextDDay',
    'nextdeliveryday': 'NextDDay',
    'next delivery day': 'NextDDay',

    'run out dday': 'RunOutDDay',
    'runoutdday': 'RunOutDDay',
    'runout dday': 'RunOutDDay',
    'runoutday': 'RunOutDDay',

    # Additional context fields
    'customer type': 'CustomerType',
    'customertype': 'CustomerType',

    'zone  fuel': 'FuelZone',
    'zone fuel': 'FuelZone',
    'zonefuel': 'FuelZone',
    'fuel zone': 'FuelZone',
    'fuelzone': 'FuelZone',

    'baseload': 'BaseLoad',
    'base load': 'BaseLoad',

    'estimated delivery  fuel': 'EstimatedDelivery',
    'estimated delivery fuel': 'EstimatedDelivery',
    'estimateddelivery': 'EstimatedDelivery',
    'estimated delivery': 'EstimatedDelivery',

    'salesperson  fuel acct': 'Salesperson',
    'salesperson fuel acct': 'Salesperson',
    'salesperson': 'Salesperson',

    'customer segment': 'CustomerSegment',
    'customersegment': 'CustomerSegment',
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


def normalize_column_names(df: pd.DataFrame,
                          mappings: Dict[str, List[str]],
                          synonyms: Dict[str, str] = None) -> pd.DataFrame:
    """
    Normalize DataFrame column names to canonical form.

    Uses a two-pass approach:
    1. Exact match against variations list
    2. Fuzzy match via normalized synonym map

    Args:
        df: Input DataFrame
        mappings: Dict mapping canonical names to possible variations (exact match)
        synonyms: Optional dict mapping normalized strings to canonical names (fuzzy match)

    Returns:
        DataFrame with normalized column names
    """
    rename_map = {}
    recognized_columns: Set[str] = set()

    # Pass 1: Exact match using original mappings (backwards compatible)
    for canonical, variations in mappings.items():
        for col in df.columns:
            if col in variations:
                rename_map[col] = canonical
                recognized_columns.add(col)
                break

    # Pass 2: Fuzzy match using synonym map (if provided)
    if synonyms:
        for col in df.columns:
            if col in recognized_columns:
                continue  # Already matched in pass 1

            # Normalize the column name
            normalized = _normalize_header(col)

            # Check if normalized form exists in synonym map
            if normalized in synonyms:
                canonical = synonyms[normalized]
                rename_map[col] = canonical
                recognized_columns.add(col)

    # Apply renaming
    normalized = df.rename(columns=rename_map)

    # Log unrecognized input columns (excluding empty/unnamed columns)
    unrecognized = []
    for col in df.columns:
        # Skip empty or unnamed columns (common in exports)
        if col and not col.startswith('Unnamed:') and col.strip():
            if col not in recognized_columns:
                unrecognized.append(col)

    if unrecognized:
        logger.warning(f"Unrecognized input columns (not mapped): {unrecognized}")

    # Log any expected canonical columns still missing after normalization
    expected_fields = set(mappings.keys())
    missing = expected_fields - set(normalized.columns)
    if missing:
        logger.warning(f"Expected fields not found in input: {missing}")

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

    # Normalize column names using both exact and fuzzy matching
    df = normalize_column_names(df, CUSTOMER_FUEL_MAPPINGS, CUSTOMER_FUEL_SYNONYMS)

    # Required columns
    required = ['CustomerFuelID', 'CustomerID', 'FuelType']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in CustomerFuel: {missing}")

    # Convert numeric columns
    numeric_cols = ['CurrentK', 'PreviousK', 'PreviousK2', 'WinterK', 'SpringK', 'SummerK', 'FallK',
                    'UsableSize', 'PercentFull', 'OptimumDelivery', 'CurrentlyInTank',
                    'SmartKPredictability', 'SmartKPrevPredictability', 'BaseLoad',
                    'EstimatedDelivery', 'RecalcK']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Convert boolean columns
    bool_cols = ['AllowSmartK', 'SmartKActive', 'AutoDelivery']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    # Date columns
    date_cols = ['LastDDay', 'NextDDay', 'RunOutDDay']
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
