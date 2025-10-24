"""
Degree day aggregation and gap detection.

Handles summing degree days between deliveries and detecting data quality issues.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def aggregate_degree_days(start_date: pd.Timestamp,
                          end_date: pd.Timestamp,
                          degree_days: pd.DataFrame,
                          area: Optional[str] = None) -> Tuple[float, bool, int]:
    """
    Sum degree days between two dates.

    Args:
        start_date: Start date (exclusive)
        end_date: End date (inclusive)
        degree_days: DataFrame with Date, HDD, and optionally Area columns
        area: Optional area filter

    Returns:
        Tuple of (total_hdd, has_gaps, gap_days)
    """
    # Filter by area if provided
    if area and 'Area' in degree_days.columns:
        dd = degree_days[degree_days['Area'] == area].copy()
    else:
        dd = degree_days.copy()

    # Filter date range
    dd = dd[(dd['Date'] > start_date) & (dd['Date'] <= end_date)]

    if len(dd) == 0:
        logger.warning(f"No degree days found between {start_date.date()} and {end_date.date()}")
        return 0.0, True, (end_date - start_date).days

    # Sum HDD
    total_hdd = dd['HDD'].sum()

    # Check for gaps (missing dates)
    expected_days = (end_date - start_date).days
    actual_days = len(dd)
    gap_days = expected_days - actual_days
    has_gaps = gap_days > 3  # Allow up to 3 missing days

    if has_gaps:
        logger.debug(f"Gap detected: {gap_days} missing days between {start_date.date()} and {end_date.date()}")

    return total_hdd, has_gaps, gap_days


def calculate_delivery_ddays(delivery_tickets: pd.DataFrame,
                             degree_days: pd.DataFrame,
                             customer_fuel: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Calculate degree days since last delivery for each ticket.

    Args:
        delivery_tickets: DataFrame with delivery history
        degree_days: DataFrame with degree day values
        customer_fuel: Optional DataFrame to map customers to areas

    Returns:
        delivery_tickets with added columns: DDaysSinceLast, DDayGaps, DDayQuality
    """
    logger.info("Calculating degree days for delivery tickets")

    result = delivery_tickets.copy()
    result['DDaysSinceLast'] = np.nan
    result['DDayGaps'] = 0
    result['DDayQuality'] = 'Unknown'

    # Determine area mapping if available
    area_map = {}
    if customer_fuel is not None and 'Area' in customer_fuel.columns:
        area_map = customer_fuel.set_index('CustomerFuelID')['Area'].to_dict()

    # Group by customer
    for customer_id, group in result.groupby('CustomerFuelID'):
        group = group.sort_values('DeliveryDate')

        area = area_map.get(customer_id)

        for idx in range(1, len(group)):
            current_row = group.iloc[idx]
            prev_row = group.iloc[idx - 1]

            start_date = prev_row['DeliveryDate']
            end_date = current_row['DeliveryDate']

            # Calculate degree days
            total_hdd, has_gaps, gap_days = aggregate_degree_days(
                start_date, end_date, degree_days, area
            )

            # Update result
            result_idx = current_row.name
            result.loc[result_idx, 'DDaysSinceLast'] = total_hdd
            result.loc[result_idx, 'DDayGaps'] = gap_days

            # Determine quality
            if total_hdd == 0:
                quality = 'Missing'
            elif has_gaps:
                quality = 'Low'
            else:
                quality = 'Good'
            result.loc[result_idx, 'DDayQuality'] = quality

    # Summary
    quality_counts = result['DDayQuality'].value_counts()
    logger.info(f"Degree day quality distribution: {quality_counts.to_dict()}")

    return result


def get_current_season(date: pd.Timestamp) -> str:
    """
    Determine current season based on date.

    Args:
        date: Date to check

    Returns:
        Season name: Winter, Spring, Summer, or Fall
    """
    month = date.month

    if month in [12, 1, 2]:
        return 'Winter'
    elif month in [3, 4, 5]:
        return 'Spring'
    elif month in [6, 7, 8]:
        return 'Summer'
    else:  # 9, 10, 11
        return 'Fall'


def get_next_season(season: str) -> str:
    """
    Get the next season.

    Args:
        season: Current season

    Returns:
        Next season name
    """
    seasons = ['Winter', 'Spring', 'Summer', 'Fall']
    idx = seasons.index(season)
    return seasons[(idx + 1) % 4]


def days_to_season_transition(date: pd.Timestamp) -> int:
    """
    Calculate days until next season transition.

    Args:
        date: Current date

    Returns:
        Days until next season starts
    """
    year = date.year
    month = date.month
    day = date.day

    # Season transition dates (approximate)
    transitions = [
        pd.Timestamp(year, 3, 1),   # Spring
        pd.Timestamp(year, 6, 1),   # Summer
        pd.Timestamp(year, 9, 1),   # Fall
        pd.Timestamp(year, 12, 1),  # Winter
    ]

    # Handle year wrap
    if month >= 12:
        transitions.append(pd.Timestamp(year + 1, 3, 1))

    # Find next transition
    for transition in transitions:
        if date < transition:
            return (transition - date).days

    # If we're past all transitions, return days to next March
    next_spring = pd.Timestamp(year + 1, 3, 1)
    return (next_spring - date).days


def interpolate_missing_degree_days(degree_days: pd.DataFrame) -> pd.DataFrame:
    """
    Interpolate missing degree day values for small gaps.

    Args:
        degree_days: DataFrame with Date and HDD columns

    Returns:
        DataFrame with interpolated values
    """
    logger.info("Interpolating missing degree day values")

    # Create full date range
    date_range = pd.date_range(
        degree_days['Date'].min(),
        degree_days['Date'].max(),
        freq='D'
    )

    # Handle areas if present
    if 'Area' in degree_days.columns:
        result_frames = []
        for area in degree_days['Area'].unique():
            area_df = degree_days[degree_days['Area'] == area].copy()
            full_df = pd.DataFrame({'Date': date_range, 'Area': area})
            merged = full_df.merge(area_df, on=['Date', 'Area'], how='left')
            merged['HDD'] = merged['HDD'].interpolate(method='linear', limit=3)
            result_frames.append(merged)
        result = pd.concat(result_frames, ignore_index=True)
    else:
        full_df = pd.DataFrame({'Date': date_range})
        merged = full_df.merge(degree_days, on='Date', how='left')
        merged['HDD'] = merged['HDD'].interpolate(method='linear', limit=3)
        result = merged

    # Fill any remaining NaNs with 0 (summer days)
    result['HDD'] = result['HDD'].fillna(0)

    interpolated = result['HDD'].notna().sum() - len(degree_days)
    logger.info(f"Interpolated {interpolated} missing degree day values")

    return result


def calculate_hdd_since_date(reference_date: pd.Timestamp,
                            current_date: pd.Timestamp,
                            degree_days: pd.DataFrame,
                            area: Optional[str] = None) -> Tuple[float, str]:
    """
    Calculate HDD accumulated since a reference date.

    Args:
        reference_date: Starting date
        current_date: Current date
        degree_days: DataFrame with degree day values
        area: Optional area filter

    Returns:
        Tuple of (total_hdd, quality_flag)
    """
    total_hdd, has_gaps, gap_days = aggregate_degree_days(
        reference_date, current_date, degree_days, area
    )

    if total_hdd == 0:
        quality = 'Missing'
    elif has_gaps:
        quality = 'Low'
    else:
        quality = 'Good'

    return total_hdd, quality
