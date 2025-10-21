"""
Unit tests for cap enforcement.
"""

import pytest
import pandas as pd

from kopt import propose


def test_apply_caps_no_cap_needed():
    """Test that caps are not applied when change is within limits."""
    proposed_k = 0.54  # 8% increase
    previous_k = 0.50
    data_quality = 'Medium'
    risk_score = 30

    capped_k, was_capped, reason = propose.apply_caps(
        proposed_k, previous_k, data_quality, risk_score
    )

    assert capped_k == proposed_k
    assert not was_capped
    assert reason == ''


def test_apply_caps_increase_limit():
    """Test that increase cap is enforced."""
    proposed_k = 0.60  # 20% increase
    previous_k = 0.50
    data_quality = 'Medium'  # Max 10% increase
    risk_score = 30

    capped_k, was_capped, reason = propose.apply_caps(
        proposed_k, previous_k, data_quality, risk_score
    )

    assert capped_k < proposed_k
    assert capped_k == 0.55  # 10% increase
    assert was_capped
    assert 'INCREASE' in reason


def test_apply_caps_decrease_limit():
    """Test that decrease cap is enforced."""
    proposed_k = 0.20  # 60% decrease
    previous_k = 0.50
    data_quality = 'Medium'  # Max 50% decrease
    risk_score = 30

    capped_k, was_capped, reason = propose.apply_caps(
        proposed_k, previous_k, data_quality, risk_score
    )

    assert capped_k > proposed_k
    assert capped_k == 0.25  # 50% decrease
    assert was_capped
    assert 'DECREASE' in reason


def test_apply_caps_high_quality_data():
    """Test that high quality data allows larger changes."""
    proposed_k = 0.575  # 15% increase
    previous_k = 0.50
    data_quality = 'High'  # Max 15% increase
    risk_score = 30

    capped_k, was_capped, reason = propose.apply_caps(
        proposed_k, previous_k, data_quality, risk_score
    )

    assert capped_k == proposed_k
    assert not was_capped


def test_apply_caps_high_risk_allows_larger_increase():
    """Test that high risk allows larger increases."""
    proposed_k = 0.575  # 15% increase
    previous_k = 0.50
    data_quality = 'Medium'  # Normally max 10%, but high risk allows 15%
    risk_score = 80  # High risk

    capped_k, was_capped, reason = propose.apply_caps(
        proposed_k, previous_k, data_quality, risk_score
    )

    # High risk should allow 15% increase with medium quality
    assert capped_k == proposed_k
    assert not was_capped


def test_check_tank_sanity_pass():
    """Test tank sanity check that passes."""
    proposed_k = 0.50
    customer_fuel = pd.Series({
        'UsableSize': 500,
        'OptimumDelivery': 200,
    })

    is_sane, reason = propose.check_tank_sanity(
        proposed_k, customer_fuel, degree_days_per_delivery=400
    )

    # Estimated delivery: 0.50 * 400 = 200 gallons
    # Tank size: 500 gallons - OK
    # Optimum: 200 gallons - OK
    assert is_sane
    assert reason == ''


def test_check_tank_sanity_too_large():
    """Test tank sanity check for delivery too large."""
    proposed_k = 2.0  # Very high K
    customer_fuel = pd.Series({
        'UsableSize': 200,  # Small tank
        'OptimumDelivery': 150,
    })

    is_sane, reason = propose.check_tank_sanity(
        proposed_k, customer_fuel, degree_days_per_delivery=500
    )

    # Estimated delivery: 2.0 * 500 = 1000 gallons
    # Tank size: 200 gallons - FAIL
    assert not is_sane
    assert 'TOO_LARGE' in reason


def test_check_tank_sanity_too_small():
    """Test tank sanity check for delivery too small."""
    proposed_k = 0.02  # Very low K
    customer_fuel = pd.Series({
        'UsableSize': 500,
        'OptimumDelivery': 200,
    })

    is_sane, reason = propose.check_tank_sanity(
        proposed_k, customer_fuel, degree_days_per_delivery=400
    )

    # Estimated delivery: 0.02 * 400 = 8 gallons
    # Optimum: 200 gallons, 20% = 40 gallons
    # 8 < 40 - FAIL
    assert not is_sane
    assert 'TOO_SMALL' in reason


def test_assess_data_quality_high():
    """Test data quality assessment - high quality."""
    # Use recent dates (within last 180 days)
    now = pd.Timestamp.now()
    deliveries = pd.DataFrame({
        'DeliveryDate': [
            now - pd.Timedelta(days=30),
            now - pd.Timedelta(days=60),
            now - pd.Timedelta(days=90),
            now - pd.Timedelta(days=120)
        ],
        'Quantity': [200, 190, 200, 195],
        'IsFill': [True, True, True, True],
        'DDayQuality': ['Good', 'Good', 'Good', 'Good'],
    })

    customer_fuel = pd.Series({})

    quality = propose.assess_data_quality(deliveries, customer_fuel)

    assert quality == 'High'


def test_assess_data_quality_low():
    """Test data quality assessment - low quality."""
    deliveries = pd.DataFrame({
        'DeliveryDate': pd.to_datetime(['2024-01-01']),  # Old delivery
        'Quantity': [200],
        'IsFill': [False],
    })

    customer_fuel = pd.Series({})

    quality = propose.assess_data_quality(deliveries, customer_fuel)

    assert quality == 'Low'
