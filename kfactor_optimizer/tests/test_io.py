"""
Unit tests for io module.
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile

from kopt import io


def test_normalize_column_names():
    """Test column name normalization."""
    df = pd.DataFrame({
        'customer_fuel_id': [1, 2],
        'K Factor': [0.5, 0.6],
        'Usable Size': [275, 500]
    })

    normalized = io.normalize_column_names(df, io.CUSTOMER_FUEL_MAPPINGS)

    assert 'CustomerFuelID' in normalized.columns
    assert 'CurrentK' in normalized.columns
    assert 'UsableSize' in normalized.columns


def test_load_customer_fuel_basic(tmp_path):
    """Test basic customer fuel loading."""
    csv_file = tmp_path / "customer_fuel.csv"

    data = {
        'CustomerFuelID': [1, 2, 3],
        'CustomerID': [101, 102, 103],
        'FuelType': ['Oil', 'Oil', 'Propane'],
        'CurrentK': [0.5, 0.6, 0.4],
        'UsableSize': [275, 500, 300],
        'AutoDelivery': [True, True, False],
    }

    pd.DataFrame(data).to_csv(csv_file, index=False)

    df = io.load_customer_fuel(str(csv_file))

    assert len(df) == 3
    assert 'CustomerFuelID' in df.columns
    assert 'CurrentK' in df.columns
    assert df['CurrentK'].dtype == float


def test_load_delivery_tickets_basic(tmp_path):
    """Test basic delivery ticket loading."""
    csv_file = tmp_path / "deliveries.csv"

    data = {
        'TicketID': [1, 2, 3],
        'CustomerFuelID': [1, 1, 2],
        'DeliveryDate': ['2024-01-15', '2024-02-20', '2024-01-10'],
        'Quantity': [200, 180, 250],
        'IsFill': [True, False, True],
    }

    pd.DataFrame(data).to_csv(csv_file, index=False)

    df = io.load_delivery_tickets(str(csv_file))

    assert len(df) == 3
    assert df['DeliveryDate'].dtype == 'datetime64[ns]'
    assert pd.api.types.is_numeric_dtype(df['Quantity'])


def test_load_degree_days_basic(tmp_path):
    """Test basic degree day loading."""
    csv_file = tmp_path / "degree_days.csv"

    dates = pd.date_range('2024-01-01', periods=10, freq='D')
    data = {
        'Date': dates.strftime('%Y-%m-%d'),
        'HDD': [20, 18, 22, 15, 10, 8, 5, 3, 12, 16],
    }

    pd.DataFrame(data).to_csv(csv_file, index=False)

    df = io.load_degree_days(str(csv_file))

    assert len(df) == 10
    assert df['Date'].dtype == 'datetime64[ns]'
    assert pd.api.types.is_numeric_dtype(df['HDD'])


def test_validate_data_quality():
    """Test data quality validation."""
    customer_fuel = pd.DataFrame({
        'CustomerFuelID': [1, 2, 3],
        'CustomerID': [101, 102, 103],
        'FuelType': ['Oil', 'Oil', 'Oil'],
    })

    delivery_tickets = pd.DataFrame({
        'CustomerFuelID': [1, 1, 2],
        'DeliveryDate': pd.to_datetime(['2024-01-15', '2024-02-20', '2024-01-10']),
        'Quantity': [200, 180, 250],
    })

    degree_days = pd.DataFrame({
        'Date': pd.date_range('2024-01-01', periods=30, freq='D'),
        'HDD': [15] * 30,
    })

    stats = io.validate_data_quality(customer_fuel, delivery_tickets, degree_days)

    assert stats['customer_fuel_count'] == 3
    assert stats['delivery_ticket_count'] == 3
    assert stats['customers_with_deliveries'] == 2
    assert stats['degree_day_coverage_days'] == 29
