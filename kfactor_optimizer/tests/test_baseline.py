"""
Unit tests for baseline module.
"""

import pytest
import pandas as pd
import numpy as np

from kopt import baseline


def test_winsorize():
    """Test winsorization."""
    values = np.array([1, 2, 3, 4, 5, 100])  # 100 is outlier

    winsorized = baseline.winsorize(values, lower=0.1, upper=0.9)

    # 100 should be capped
    assert winsorized.max() < 100
    assert winsorized.min() >= 1


def test_weighted_median():
    """Test weighted median calculation."""
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    weights = np.array([1.0, 1.0, 1.0, 1.0, 1.0])

    median = baseline.weighted_median(values, weights)

    assert median == 3.0


def test_weighted_median_biased():
    """Test weighted median with bias."""
    values = np.array([1.0, 2.0, 3.0])
    weights = np.array([0.1, 0.1, 0.8])  # Heavily weight 3.0

    median = baseline.weighted_median(values, weights)

    assert median == 3.0


def test_calculate_robust_baseline_k():
    """Test robust baseline K calculation."""
    deliveries = pd.DataFrame({
        'DeliveryDate': pd.to_datetime([
            '2024-01-15', '2024-02-20', '2024-03-25', '2024-04-30'
        ]),
        'Quantity': [200, 180, 190, 195],
        'DDaysSinceLast': [400, 350, 380, 390],
        'IsFill': [True, True, True, True],
        'DDayQuality': ['Good', 'Good', 'Good', 'Good'],
    })

    baseline_k, confidence, metadata = baseline.calculate_robust_baseline_k(deliveries)

    assert baseline_k is not None
    assert baseline_k > 0
    assert confidence in ['Low', 'Medium', 'High']
    assert metadata['fill_count'] == 4


def test_calculate_robust_baseline_k_insufficient_data():
    """Test baseline K with insufficient data."""
    deliveries = pd.DataFrame({
        'DeliveryDate': pd.to_datetime(['2024-01-15']),
        'Quantity': [200],
        'DDaysSinceLast': [400],
        'IsFill': [True],
    })

    baseline_k, confidence, metadata = baseline.calculate_robust_baseline_k(deliveries)

    assert baseline_k is None
    assert confidence == 'Insufficient'


def test_calculate_classical_k():
    """Test classical K calculation."""
    last_delivery = pd.Series({
        'DeliveryDate': pd.Timestamp('2024-03-15'),
        'Quantity': 200,
        'DDaysSinceLast': 400,
        'IsFill': True,
        'DDayQuality': 'Good',
    })

    recent_deliveries = pd.DataFrame()

    k_classical, quality = baseline.calculate_classical_k(last_delivery, recent_deliveries)

    assert k_classical == 0.5  # 200 / 400
    assert quality == 'Good'


def test_calculate_classical_k_missing_data():
    """Test classical K with missing data."""
    last_delivery = pd.Series({
        'DeliveryDate': pd.Timestamp('2024-03-15'),
        'Quantity': 200,
        'DDaysSinceLast': np.nan,
    })

    recent_deliveries = pd.DataFrame()

    k_classical, quality = baseline.calculate_classical_k(last_delivery, recent_deliveries)

    assert k_classical is None
    assert quality == 'Missing'


def test_get_seasonal_k_target():
    """Test seasonal K target retrieval."""
    customer_fuel = pd.Series({
        'WinterK': 0.6,
        'SpringK': 0.4,
        'SummerK': 0.2,
        'FallK': 0.5,
    })

    winter_k = baseline.get_seasonal_k_target(customer_fuel, 'Winter')
    assert winter_k == 0.6

    summer_k = baseline.get_seasonal_k_target(customer_fuel, 'Summer')
    assert summer_k == 0.2


def test_calculate_seasonal_adjustment():
    """Test seasonal adjustment calculation."""
    current_k = 0.4
    seasonal_target = 0.5

    adjusted_k, adjustment_pct = baseline.calculate_seasonal_adjustment(
        current_k, seasonal_target, max_adjustment=0.10
    )

    # Should nudge toward target
    assert adjusted_k > current_k
    assert adjusted_k <= current_k * 1.10  # Max 10% increase


def test_drift_toward_baseline():
    """Test baseline drift."""
    current_k = 0.5
    baseline_k = 0.55

    drifted_k = baseline.drift_toward_baseline(current_k, baseline_k, max_drift=0.05)

    # Should move toward baseline
    assert drifted_k > current_k
    assert drifted_k <= current_k * 1.05  # Max 5% drift
