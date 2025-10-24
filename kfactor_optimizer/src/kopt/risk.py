"""
Customer runout risk scoring.

Calculates risk scores (0-100) based on multiple factors.
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def calculate_days_since_last_fill(deliveries: pd.DataFrame) -> float:
    """
    Calculate days since last fill-up delivery.

    Args:
        deliveries: Delivery history

    Returns:
        Days since last fill, or NaN if no fills
    """
    if len(deliveries) == 0:
        return np.nan

    # Find last fill
    if 'IsFill' in deliveries.columns:
        fills = deliveries[deliveries['IsFill'] == True]
        if len(fills) > 0:
            last_fill_date = fills['DeliveryDate'].max()
            days_since = (pd.Timestamp.now() - last_fill_date).days
            return days_since

    # If no IsFill column or no fills, use last delivery
    last_delivery_date = deliveries['DeliveryDate'].max()
    days_since = (pd.Timestamp.now() - last_delivery_date).days
    return days_since


def estimate_days_to_empty(customer_fuel: pd.Series,
                          deliveries: pd.DataFrame,
                          degree_days: pd.DataFrame) -> float:
    """
    Estimate days until tank runs empty.

    Args:
        customer_fuel: Customer fuel record
        deliveries: Delivery history
        degree_days: Degree day data

    Returns:
        Estimated days to empty, or NaN if cannot estimate
    """
    # Need current level and K-factor
    percent_full = customer_fuel.get('PercentFull')
    usable_size = customer_fuel.get('UsableSize')
    current_k = customer_fuel.get('CurrentK')

    if pd.isna(percent_full) or pd.isna(usable_size) or pd.isna(current_k):
        return np.nan

    if percent_full <= 0 or usable_size <= 0 or current_k <= 0:
        return np.nan

    # Current gallons in tank
    current_gallons = usable_size * (percent_full / 100)

    # Estimate daily consumption (rough approximation)
    # Winter months: ~15 HDD/day, shoulder: ~5, summer: ~0
    current_month = pd.Timestamp.now().month
    if current_month in [12, 1, 2]:
        avg_hdd_per_day = 15
    elif current_month in [3, 4, 5, 10, 11]:
        avg_hdd_per_day = 5
    else:
        avg_hdd_per_day = 0.5

    daily_consumption = current_k * avg_hdd_per_day

    if daily_consumption <= 0:
        return 999  # Not consuming (summer)

    days_to_empty = current_gallons / daily_consumption

    return max(0, days_to_empty)


def calculate_usage_variance(deliveries: pd.DataFrame) -> float:
    """
    Calculate variance in usage patterns.

    Higher variance = higher risk (unpredictable usage).

    Args:
        deliveries: Delivery history

    Returns:
        Coefficient of variation for inter-delivery degree days
    """
    if len(deliveries) < 3:
        return 0

    # Get degree days between deliveries
    if 'DDaysSinceLast' not in deliveries.columns:
        return 0

    ddays = deliveries['DDaysSinceLast'].dropna()

    if len(ddays) < 2:
        return 0

    cv = ddays.std() / ddays.mean() if ddays.mean() > 0 else 0

    return cv


def calculate_risk_score(customer_fuel: pd.Series,
                        deliveries: pd.DataFrame,
                        degree_days: pd.DataFrame) -> int:
    """
    Calculate overall runout risk score (0-100).

    Higher score = higher risk of runout.

    Factors:
    - Days since last fill (0-30 points)
    - Days to empty (0-30 points)
    - Usage variance (0-15 points)
    - Winter season penalty (0-10 points)
    - Small tank penalty (0-10 points)
    - Low monitor reading if available (0-5 points)

    Args:
        customer_fuel: Customer fuel record
        deliveries: Delivery history
        degree_days: Degree day data

    Returns:
        Risk score (0-100)
    """
    risk_score = 0
    features = {}

    # Feature 1: Days since last fill (0-30 points)
    days_since_fill = calculate_days_since_last_fill(deliveries)
    features['days_since_fill'] = days_since_fill

    if not pd.isna(days_since_fill):
        if days_since_fill > 60:
            risk_score += 30
        elif days_since_fill > 45:
            risk_score += 20
        elif days_since_fill > 30:
            risk_score += 10
        elif days_since_fill > 21:
            risk_score += 5

    # Feature 2: Days to empty (0-30 points)
    days_to_empty = estimate_days_to_empty(customer_fuel, deliveries, degree_days)
    features['days_to_empty'] = days_to_empty

    if not pd.isna(days_to_empty):
        if days_to_empty < 7:
            risk_score += 30
        elif days_to_empty < 14:
            risk_score += 20
        elif days_to_empty < 21:
            risk_score += 10
        elif days_to_empty < 30:
            risk_score += 5

    # Feature 3: RunOutDDay if available (0-20 points)
    runout_dday = customer_fuel.get('RunOutDDay')
    if pd.notna(runout_dday) and isinstance(runout_dday, pd.Timestamp):
        days_to_runout = (runout_dday - pd.Timestamp.now()).days
        features['days_to_runout'] = days_to_runout

        if days_to_runout < 7:
            risk_score += 20
        elif days_to_runout < 14:
            risk_score += 15
        elif days_to_runout < 21:
            risk_score += 10
        elif days_to_runout < 30:
            risk_score += 5

    # Feature 4: Usage variance (0-15 points)
    usage_cv = calculate_usage_variance(deliveries)
    features['usage_cv'] = usage_cv

    if usage_cv > 0.5:
        risk_score += 15
    elif usage_cv > 0.3:
        risk_score += 10
    elif usage_cv > 0.2:
        risk_score += 5

    # Feature 5: Winter season penalty (0-10 points)
    current_month = pd.Timestamp.now().month
    is_winter = current_month in [12, 1, 2]
    features['is_winter'] = is_winter

    if is_winter:
        risk_score += 10

    # Feature 6: Small tank penalty (0-10 points)
    usable_size = customer_fuel.get('UsableSize')
    features['usable_size'] = usable_size

    if pd.notna(usable_size):
        if usable_size < 200:
            risk_score += 10
        elif usable_size < 300:
            risk_score += 5

    # Feature 7: Low percent full (0-5 points)
    percent_full = customer_fuel.get('PercentFull')
    features['percent_full'] = percent_full

    if pd.notna(percent_full):
        if percent_full < 20:
            risk_score += 5
        elif percent_full < 30:
            risk_score += 3

    # Cap at 100
    risk_score = min(risk_score, 100)

    logger.debug(f"Customer {customer_fuel['CustomerFuelID']}: Risk score = {risk_score}, Features = {features}")

    return risk_score


def get_risk_tier(risk_score: int) -> str:
    """
    Get risk tier label.

    Args:
        risk_score: Risk score (0-100)

    Returns:
        Risk tier: 'High', 'Medium', or 'Low'
    """
    if risk_score >= 70:
        return 'High'
    elif risk_score >= 40:
        return 'Medium'
    else:
        return 'Low'


def calculate_risk_metrics(proposals: pd.DataFrame,
                          customer_fuel: pd.DataFrame,
                          deliveries: pd.DataFrame,
                          degree_days: pd.DataFrame) -> Dict:
    """
    Calculate aggregate risk metrics for reporting.

    Args:
        proposals: Proposal results
        customer_fuel: Customer fuel records
        deliveries: Delivery history
        degree_days: Degree day data

    Returns:
        Dict with risk metrics
    """
    # Add risk scores and tiers to proposals
    risk_scores = []
    risk_tiers = []

    for idx, row in proposals.iterrows():
        customer_fuel_id = row['CustomerFuelID']

        # Get customer fuel record
        cust = customer_fuel[customer_fuel['CustomerFuelID'] == customer_fuel_id]
        if len(cust) == 0:
            risk_scores.append(0)
            risk_tiers.append('Low')
            continue

        cust = cust.iloc[0]

        # Get deliveries
        cust_deliveries = deliveries[deliveries['CustomerFuelID'] == customer_fuel_id]

        # Calculate risk
        risk_score = calculate_risk_score(cust, cust_deliveries, degree_days)
        risk_tier = get_risk_tier(risk_score)

        risk_scores.append(risk_score)
        risk_tiers.append(risk_tier)

    proposals['RiskScore'] = risk_scores
    proposals['RiskTier'] = risk_tiers

    # Aggregate metrics
    metrics = {
        'high_risk_count': (proposals['RiskTier'] == 'High').sum(),
        'medium_risk_count': (proposals['RiskTier'] == 'Medium').sum(),
        'low_risk_count': (proposals['RiskTier'] == 'Low').sum(),
        'avg_risk_score': proposals['RiskScore'].mean(),
        'high_risk_with_increases': 0,
        'high_risk_with_decreases': 0,
    }

    # High risk customers with K changes
    high_risk = proposals[proposals['RiskTier'] == 'High']
    if len(high_risk) > 0:
        metrics['high_risk_with_increases'] = (high_risk['ChangePct'] > 0).sum()
        metrics['high_risk_with_decreases'] = (high_risk['ChangePct'] < 0).sum()

    return metrics, proposals
