"""
SmartK eligibility checking and confidence scoring.

Implements rule-based SmartK qualification and confidence model.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def check_smartk_eligibility(customer_fuel: pd.Series,
                            deliveries: pd.DataFrame) -> Tuple[bool, str]:
    """
    Check if customer is eligible for SmartK.

    Requirements:
    - AllowSmartK or SmartKActive flag set
    - At least 4 deliveries per year
    - At least 14 months of history
    - At least one fill-up in history

    Args:
        customer_fuel: Customer fuel record
        deliveries: Delivery history for customer

    Returns:
        Tuple of (is_eligible, reason)
    """
    # Check flags
    allow_smartk = customer_fuel.get('AllowSmartK', False)
    smartk_active = customer_fuel.get('SmartKActive', False)

    if not (allow_smartk or smartk_active):
        return False, 'SmartK not enabled'

    # Check delivery count
    if len(deliveries) == 0:
        return False, 'No delivery history'

    # Check history span
    date_range = (deliveries['DeliveryDate'].max() - deliveries['DeliveryDate'].min())
    history_months = date_range.days / 30.44

    if history_months < 14:
        return False, f'Insufficient history: {history_months:.1f} months'

    # Check deliveries per year
    deliveries_per_year = len(deliveries) / (history_months / 12)

    if deliveries_per_year < 4:
        return False, f'Too few deliveries: {deliveries_per_year:.1f}/year'

    # Check for at least one fill
    if 'IsFill' in deliveries.columns:
        fill_count = deliveries['IsFill'].sum()
        if fill_count == 0:
            return False, 'No fill-ups in history'

    return True, 'Eligible'


def calculate_smartk_confidence(deliveries: pd.DataFrame,
                               customer_fuel: pd.Series) -> Tuple[float, dict]:
    """
    Calculate SmartK confidence score (0-1).

    Based on:
    - Delivery frequency and consistency
    - Fill-up ratio
    - Data quality
    - History span
    - Usage pattern stability

    Args:
        deliveries: Delivery history
        customer_fuel: Customer fuel record

    Returns:
        Tuple of (confidence_score, feature_dict)
    """
    features = {}
    score = 0.0

    if len(deliveries) == 0:
        return 0.0, {'reason': 'No deliveries'}

    # Feature 1: History span (max 0.2)
    date_range = (deliveries['DeliveryDate'].max() - deliveries['DeliveryDate'].min())
    history_months = date_range.days / 30.44
    features['history_months'] = history_months

    if history_months >= 24:
        score += 0.2
    elif history_months >= 14:
        score += 0.1 * (history_months / 14)

    # Feature 2: Delivery frequency (max 0.2)
    deliveries_per_year = len(deliveries) / (history_months / 12) if history_months > 0 else 0
    features['deliveries_per_year'] = deliveries_per_year

    if deliveries_per_year >= 6:
        score += 0.2
    elif deliveries_per_year >= 4:
        score += 0.1 * (deliveries_per_year / 4)

    # Feature 3: Fill ratio (max 0.2)
    if 'IsFill' in deliveries.columns:
        fill_ratio = deliveries['IsFill'].sum() / len(deliveries)
        features['fill_ratio'] = fill_ratio

        if fill_ratio >= 0.8:
            score += 0.2
        else:
            score += 0.2 * fill_ratio
    else:
        # Assume moderate fill ratio if not tracked
        score += 0.1

    # Feature 4: Data quality (max 0.2)
    if 'DDayQuality' in deliveries.columns:
        good_quality_ratio = (deliveries['DDayQuality'] == 'Good').sum() / len(deliveries)
        features['good_quality_ratio'] = good_quality_ratio

        if good_quality_ratio >= 0.8:
            score += 0.2
        else:
            score += 0.2 * good_quality_ratio
    else:
        # Assume moderate quality if not tracked
        score += 0.1

    # Feature 5: Usage stability (max 0.2)
    deliveries_with_k = deliveries[
        deliveries['DDaysSinceLast'].notna() &
        (deliveries['DDaysSinceLast'] > 0) &
        deliveries['Quantity'].notna() &
        (deliveries['Quantity'] > 0)
    ]

    if len(deliveries_with_k) >= 3:
        k_values = deliveries_with_k['Quantity'] / deliveries_with_k['DDaysSinceLast']
        k_cv = k_values.std() / k_values.mean() if k_values.mean() > 0 else float('inf')
        features['k_cv'] = k_cv

        if k_cv <= 0.2:
            score += 0.2
        elif k_cv <= 0.4:
            score += 0.1 * (0.4 - k_cv) / 0.2
    else:
        # Insufficient data for stability check
        score += 0.05

    features['confidence_score'] = score

    return score, features


def estimate_smartk_forecast(deliveries: pd.DataFrame,
                            customer_fuel: pd.Series,
                            current_season: str) -> Tuple[Optional[float], float]:
    """
    Estimate SmartK forecast for consumption.

    This is a simplified heuristic model that predicts seasonal consumption
    based on historical patterns.

    Args:
        deliveries: Delivery history
        customer_fuel: Customer fuel record
        current_season: Current season name

    Returns:
        Tuple of (predicted_k, confidence)
    """
    # Need at least one year of data
    if len(deliveries) < 4:
        return None, 0.0

    # Filter to same season from previous year(s)
    deliveries = deliveries.copy()
    deliveries['Month'] = deliveries['DeliveryDate'].dt.month
    deliveries['Season'] = deliveries['DeliveryDate'].apply(_month_to_season)

    season_deliveries = deliveries[deliveries['Season'] == current_season]

    if len(season_deliveries) == 0:
        # Fall back to all deliveries
        season_deliveries = deliveries

    # Calculate K values
    valid = season_deliveries[
        season_deliveries['DDaysSinceLast'].notna() &
        (season_deliveries['DDaysSinceLast'] > 0) &
        season_deliveries['Quantity'].notna() &
        (season_deliveries['Quantity'] > 0)
    ]

    if len(valid) == 0:
        return None, 0.0

    k_values = valid['Quantity'] / valid['DDaysSinceLast']

    # Weight recent years more heavily
    now = pd.Timestamp.now()
    weights = []
    for date in valid['DeliveryDate']:
        age_years = (now - date).days / 365.25
        weight = np.exp(-age_years / 2.0)  # 2-year half-life
        weights.append(weight)

    weights = np.array(weights)
    weights = weights / weights.sum()

    # Weighted average
    predicted_k = (k_values * weights).sum()

    # Confidence based on sample size and consistency
    confidence = min(len(valid) / 6.0, 1.0) * 0.7  # Max 0.7 confidence

    # Reduce confidence if high variance
    k_cv = k_values.std() / k_values.mean() if k_values.mean() > 0 else float('inf')
    if k_cv > 0.3:
        confidence *= 0.7

    return predicted_k, confidence


def _month_to_season(date: pd.Timestamp) -> str:
    """Convert date to season."""
    month = date.month
    if month in [12, 1, 2]:
        return 'Winter'
    elif month in [3, 4, 5]:
        return 'Spring'
    elif month in [6, 7, 8]:
        return 'Summer'
    else:
        return 'Fall'


def blend_smartk_with_classical(k_classical: float,
                               k_smartk: float,
                               smartk_confidence: float) -> Tuple[float, float]:
    """
    Blend classical K with SmartK forecast.

    Args:
        k_classical: Classical K-factor
        k_smartk: SmartK predicted K-factor
        smartk_confidence: SmartK confidence (0-1)

    Returns:
        Tuple of (blended_k, blend_weight)
    """
    # Cap SmartK weight at 0.7 even if confidence is higher
    blend_weight = min(smartk_confidence, 0.7)

    blended_k = blend_weight * k_smartk + (1 - blend_weight) * k_classical

    return blended_k, blend_weight


def should_use_smartk(customer_fuel: pd.Series,
                     deliveries: pd.DataFrame,
                     min_confidence: float = 0.3) -> Tuple[bool, str, float]:
    """
    Determine if SmartK should be used for this customer.

    Args:
        customer_fuel: Customer fuel record
        deliveries: Delivery history
        min_confidence: Minimum confidence threshold

    Returns:
        Tuple of (use_smartk, reason, confidence)
    """
    # Check eligibility
    is_eligible, reason = check_smartk_eligibility(customer_fuel, deliveries)

    if not is_eligible:
        return False, reason, 0.0

    # Calculate confidence
    confidence, features = calculate_smartk_confidence(deliveries, customer_fuel)

    if confidence < min_confidence:
        return False, f'Low confidence: {confidence:.2f}', confidence

    return True, 'SmartK qualified', confidence
