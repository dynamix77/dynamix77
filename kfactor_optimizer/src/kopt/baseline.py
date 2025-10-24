"""
Robust baseline K-factor calculation.

Implements winsorized weighted median approach for calculating stable K-factors.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


def winsorize(values: np.ndarray, lower: float = 0.1, upper: float = 0.9) -> np.ndarray:
    """
    Winsorize values by capping at percentiles.

    Args:
        values: Array of values
        lower: Lower percentile (0-1)
        upper: Upper percentile (0-1)

    Returns:
        Winsorized array
    """
    if len(values) == 0:
        return values

    lower_val = np.percentile(values, lower * 100)
    upper_val = np.percentile(values, upper * 100)

    return np.clip(values, lower_val, upper_val)


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """
    Calculate weighted median.

    Args:
        values: Array of values
        weights: Array of weights (same length as values)

    Returns:
        Weighted median value
    """
    if len(values) == 0:
        return np.nan

    if len(values) != len(weights):
        raise ValueError("Values and weights must have same length")

    # Sort by values
    sorted_idx = np.argsort(values)
    sorted_values = values[sorted_idx]
    sorted_weights = weights[sorted_idx]

    # Normalize weights
    weight_sum = sorted_weights.sum()
    if weight_sum == 0:
        return np.nan

    cumulative_weight = np.cumsum(sorted_weights) / weight_sum

    # Find median
    median_idx = np.searchsorted(cumulative_weight, 0.5)
    return sorted_values[median_idx]


def calculate_k_factors_from_fills(deliveries: pd.DataFrame,
                                   min_fills: int = 3,
                                   max_fills: int = 6) -> List[Tuple[float, float, str]]:
    """
    Calculate individual K-factors from fill-up deliveries.

    Args:
        deliveries: DataFrame with delivery history (must have DDaysSinceLast, Quantity, IsFill)
        min_fills: Minimum number of fills required
        max_fills: Maximum number of fills to use

    Returns:
        List of (k_factor, weight, quality) tuples
    """
    k_factors = []

    # Filter to fills only
    if 'IsFill' in deliveries.columns:
        fills = deliveries[deliveries['IsFill'] == True].copy()
    else:
        # Assume all are potential fills, filter by quality
        fills = deliveries.copy()

    # Must have DDaysSinceLast and Quantity
    fills = fills[fills['DDaysSinceLast'].notna() & (fills['DDaysSinceLast'] > 0)]
    fills = fills[fills['Quantity'].notna() & (fills['Quantity'] > 0)]

    if len(fills) < min_fills:
        logger.debug(f"Insufficient fills: {len(fills)} < {min_fills}")
        return k_factors

    # Take most recent fills up to max_fills
    fills = fills.sort_values('DeliveryDate', ascending=False).head(max_fills)

    # Calculate K for each fill
    for idx, row in fills.iterrows():
        k = row['Quantity'] / row['DDaysSinceLast']

        # Weight: newer deliveries get higher weight
        age_days = (pd.Timestamp.now() - row['DeliveryDate']).days
        weight = np.exp(-age_days / 365.0)  # Exponential decay with 1-year half-life

        # Quality based on data quality
        quality = row.get('DDayQuality', 'Unknown')

        k_factors.append((k, weight, quality))

    return k_factors


def calculate_robust_baseline_k(deliveries: pd.DataFrame,
                                min_fills: int = 3,
                                max_fills: int = 6) -> Tuple[Optional[float], str, dict]:
    """
    Calculate robust baseline K-factor using winsorized weighted median.

    Args:
        deliveries: DataFrame with delivery history
        min_fills: Minimum number of fills required
        max_fills: Maximum number of fills to use

    Returns:
        Tuple of (baseline_k, confidence, metadata_dict)
    """
    # Calculate individual K-factors
    k_factors = calculate_k_factors_from_fills(deliveries, min_fills, max_fills)

    if len(k_factors) == 0:
        return None, 'Insufficient', {'reason': 'No valid fills', 'fill_count': 0}

    # Extract values, weights, and quality
    k_values = np.array([k for k, w, q in k_factors])
    k_weights = np.array([w for k, w, q in k_factors])
    k_quality = [q for k, w, q in k_factors]

    # Winsorize K values
    k_winsorized = winsorize(k_values, lower=0.1, upper=0.9)

    # Calculate weighted median
    baseline_k = weighted_median(k_winsorized, k_weights)

    # Determine confidence
    good_quality_count = sum(1 for q in k_quality if q == 'Good')
    confidence = 'Low'

    if len(k_factors) >= 4 and good_quality_count >= 3:
        confidence = 'High'
    elif len(k_factors) >= 3 and good_quality_count >= 2:
        confidence = 'Medium'

    # Metadata
    metadata = {
        'fill_count': len(k_factors),
        'good_quality_count': good_quality_count,
        'k_min': k_values.min(),
        'k_max': k_values.max(),
        'k_mean': k_values.mean(),
        'k_median': np.median(k_values),
        'k_std': k_values.std(),
    }

    logger.debug(f"Baseline K: {baseline_k:.4f}, Confidence: {confidence}, Fills: {len(k_factors)}")

    return baseline_k, confidence, metadata


def calculate_classical_k(last_delivery: pd.Series,
                         recent_deliveries: pd.DataFrame) -> Tuple[Optional[float], str]:
    """
    Calculate classical K-factor from most recent delivery.

    Args:
        last_delivery: Most recent delivery record
        recent_deliveries: Recent delivery history for context

    Returns:
        Tuple of (classical_k, quality)
    """
    # Must have degree days and quantity
    if pd.isna(last_delivery.get('DDaysSinceLast')) or last_delivery['DDaysSinceLast'] <= 0:
        return None, 'Missing'

    if pd.isna(last_delivery['Quantity']) or last_delivery['Quantity'] <= 0:
        return None, 'Missing'

    # Calculate K
    k_classical = last_delivery['Quantity'] / last_delivery['DDaysSinceLast']

    # Quality based on delivery characteristics
    quality = last_delivery.get('DDayQuality', 'Unknown')

    # Adjust quality if not a fill
    if 'IsFill' in last_delivery.index and not last_delivery['IsFill']:
        if quality == 'Good':
            quality = 'Medium'
        elif quality == 'Medium':
            quality = 'Low'

    return k_classical, quality


def get_seasonal_k_target(customer_fuel: pd.Series, season: str) -> Optional[float]:
    """
    Get seasonal K-factor target for a customer.

    Args:
        customer_fuel: Customer fuel record
        season: Season name (Winter, Spring, Summer, Fall)

    Returns:
        Seasonal K value or None
    """
    season_field = f"{season}K"

    if season_field in customer_fuel.index:
        k_value = customer_fuel[season_field]
        if pd.notna(k_value) and k_value > 0:
            return k_value

    return None


def calculate_seasonal_adjustment(current_k: float,
                                 seasonal_target: float,
                                 max_adjustment: float = 0.10) -> Tuple[float, float]:
    """
    Calculate seasonal adjustment to nudge K toward seasonal target.

    Args:
        current_k: Current K-factor
        seasonal_target: Target seasonal K-factor
        max_adjustment: Maximum adjustment as fraction (default 10%)

    Returns:
        Tuple of (adjusted_k, adjustment_pct)
    """
    if seasonal_target <= 0:
        return current_k, 0.0

    # Calculate difference
    diff_pct = (seasonal_target - current_k) / current_k

    # Cap adjustment
    if abs(diff_pct) <= max_adjustment:
        adjusted_k = seasonal_target
        adjustment_pct = diff_pct
    else:
        # Nudge by max_adjustment toward target
        direction = 1 if diff_pct > 0 else -1
        adjusted_k = current_k * (1 + direction * max_adjustment)
        adjustment_pct = direction * max_adjustment

    return adjusted_k, adjustment_pct


def check_historical_stability(deliveries: pd.DataFrame) -> Tuple[bool, dict]:
    """
    Check if K-factor has been historically stable.

    Args:
        deliveries: DataFrame with delivery history

    Returns:
        Tuple of (is_stable, metrics_dict)
    """
    # Need at least 3 deliveries
    if len(deliveries) < 3:
        return False, {'reason': 'Insufficient deliveries'}

    # Calculate K for each delivery
    deliveries = deliveries[deliveries['DDaysSinceLast'].notna() & (deliveries['DDaysSinceLast'] > 0)]
    deliveries = deliveries[deliveries['Quantity'].notna() & (deliveries['Quantity'] > 0)]

    if len(deliveries) < 3:
        return False, {'reason': 'Insufficient valid deliveries'}

    k_values = deliveries['Quantity'] / deliveries['DDaysSinceLast']

    # Calculate coefficient of variation
    k_mean = k_values.mean()
    k_std = k_values.std()
    cv = k_std / k_mean if k_mean > 0 else float('inf')

    # Stable if CV < 0.3 (30%)
    is_stable = cv < 0.3

    metrics = {
        'cv': cv,
        'k_mean': k_mean,
        'k_std': k_std,
        'delivery_count': len(deliveries),
    }

    return is_stable, metrics


def drift_toward_baseline(current_k: float,
                         baseline_k: float,
                         max_drift: float = 0.05) -> float:
    """
    Drift current K toward baseline by a small amount.

    Used when no recent delivery data is available.

    Args:
        current_k: Current K-factor
        baseline_k: Baseline K-factor
        max_drift: Maximum drift as fraction (default 5%)

    Returns:
        Adjusted K-factor
    """
    if baseline_k <= 0 or current_k <= 0:
        return current_k

    diff_pct = (baseline_k - current_k) / current_k

    if abs(diff_pct) <= max_drift:
        return baseline_k
    else:
        direction = 1 if diff_pct > 0 else -1
        return current_k * (1 + direction * max_drift)
