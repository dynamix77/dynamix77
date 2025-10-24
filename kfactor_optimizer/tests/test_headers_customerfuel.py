"""
Unit tests for CustomerFuel header normalization.

Tests fuzzy header matching against actual Ignite export headers.
"""

import pytest
import pandas as pd
from io import StringIO
import tempfile

from kopt import io


def test_ignite_customerfuel_headers_full():
    """Test normalization with exact Ignite CustomerFuel export headers."""

    # Exact header row from Ignite export
    csv_data = """,Customer Number,Customer Code,Customer Fuel Unique ID,Customer Location Unique ID,Customer Type,Customer Fuel Type,Zone - Fuel,Usable Size,Optimum Delivery - Fuel,K Factor,Previous K Factor,Previous K Factor (2nd),Last DDay,Next DDay,Run Out DDay,Allow Smart K,Smart K Predictability,Smart K Previous Predictability,Recalc K Factor,Baseload,Estimated Delivery - Fuel,Currently in Tank,% Full,Salesperson - Fuel Acct,Customer Segment,Automatic Delivery,K Factor - Winter,K Factor - Summer,K Factor - Fall,K Factor - Spring,PIDCustomerFuel1
,101,CUST001,1001,5001,Residential,Oil,Zone1,275,180,0.55,0.52,0.50,2024-01-15,2024-02-20,2024-03-01,Yes,0.85,0.82,0.54,50,175,165,60,Smith,Premium,Yes,0.65,0.35,0.50,0.45,PID001
,102,CUST002,1002,5002,Commercial,Propane,Zone2,500,300,0.48,0.46,0.44,2024-01-10,2024-02-15,2024-02-25,No,0.70,0.68,0.47,75,290,300,60,Jones,Standard,Yes,0.58,0.30,0.45,0.40,PID002
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        # Load using the CustomerFuel loader
        df = io.load_customer_fuel(temp_path)

        # Assert required fields present
        assert 'CustomerFuelID' in df.columns, "CustomerFuelID not found"
        assert 'CustomerID' in df.columns, "CustomerID not found"
        assert 'FuelType' in df.columns, "FuelType not found"

        # Assert core K-factor fields
        assert 'CurrentK' in df.columns, "CurrentK (K Factor) not found"
        assert 'PreviousK' in df.columns, "PreviousK not found"
        assert 'PreviousK2' in df.columns, "PreviousK2 (Previous K Factor 2nd) not found"

        # Assert seasonal K fields
        assert 'WinterK' in df.columns, "WinterK not found"
        assert 'SummerK' in df.columns, "SummerK not found"
        assert 'FallK' in df.columns, "FallK not found"
        assert 'SpringK' in df.columns, "SpringK not found"

        # Assert tank fields
        assert 'UsableSize' in df.columns, "UsableSize not found"
        assert 'OptimumDelivery' in df.columns, "OptimumDelivery not found"
        assert 'PercentFull' in df.columns, "PercentFull (% Full) not found"
        assert 'CurrentlyInTank' in df.columns, "CurrentlyInTank not found"

        # Assert delivery fields
        assert 'AutoDelivery' in df.columns, "AutoDelivery not found"

        # Assert SmartK fields
        assert 'SmartKActive' in df.columns, "SmartKActive (Allow Smart K) not found"
        assert 'SmartKPredictability' in df.columns, "SmartKPredictability not found"
        assert 'SmartKPrevPredictability' in df.columns, "SmartKPrevPredictability not found"

        # Assert date fields
        assert 'LastDDay' in df.columns, "LastDDay not found"
        assert 'NextDDay' in df.columns, "NextDDay not found"
        assert 'RunOutDDay' in df.columns, "RunOutDDay not found"

        # Assert context fields
        assert 'CustomerCode' in df.columns, "CustomerCode not found"
        assert 'LocationNumber' in df.columns, "LocationNumber not found"
        assert 'CustomerType' in df.columns, "CustomerType not found"
        assert 'FuelZone' in df.columns, "FuelZone (Zone - Fuel) not found"
        assert 'BaseLoad' in df.columns, "BaseLoad not found"
        assert 'EstimatedDelivery' in df.columns, "EstimatedDelivery not found"
        assert 'Salesperson' in df.columns, "Salesperson not found"
        assert 'CustomerSegment' in df.columns, "CustomerSegment not found"
        assert 'RecalcK' in df.columns, "RecalcK not found"

        # Verify data values (first row)
        assert df.loc[0, 'CustomerID'] == 101
        assert df.loc[0, 'CustomerCode'] == 'CUST001'
        assert df.loc[0, 'CustomerFuelID'] == 1001
        assert df.loc[0, 'FuelType'] == 'Oil'
        assert df.loc[0, 'CurrentK'] == 0.55
        assert df.loc[0, 'PreviousK'] == 0.52
        assert df.loc[0, 'PreviousK2'] == 0.50
        assert df.loc[0, 'WinterK'] == 0.65
        assert df.loc[0, 'SummerK'] == 0.35
        assert df.loc[0, 'FallK'] == 0.50
        assert df.loc[0, 'SpringK'] == 0.45
        assert df.loc[0, 'UsableSize'] == 275
        assert df.loc[0, 'OptimumDelivery'] == 180
        assert df.loc[0, 'PercentFull'] == 60
        assert df.loc[0, 'AutoDelivery'] == True

        # Verify second row
        assert df.loc[1, 'CustomerID'] == 102
        assert df.loc[1, 'FuelType'] == 'Propane'
        assert df.loc[1, 'CurrentK'] == 0.48

    finally:
        import os
        os.unlink(temp_path)


def test_minimal_required_fields():
    """Test with only required fields (CustomerFuelID, CustomerID, FuelType)."""

    csv_data = """Customer Fuel Unique ID,Customer Number,Customer Fuel Type
1001,101,Oil
1002,102,Propane
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        df = io.load_customer_fuel(temp_path)

        # Required fields must be present
        assert 'CustomerFuelID' in df.columns
        assert 'CustomerID' in df.columns
        assert 'FuelType' in df.columns

        # Verify values
        assert df.loc[0, 'CustomerFuelID'] == 1001
        assert df.loc[0, 'CustomerID'] == 101
        assert df.loc[0, 'FuelType'] == 'Oil'

    finally:
        import os
        os.unlink(temp_path)


def test_missing_required_field_raises_error():
    """Test that missing required field raises clear ValueError."""

    # Missing FuelType
    csv_data = """Customer Fuel Unique ID,Customer Number
1001,101
1002,102
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="Missing required columns"):
            io.load_customer_fuel(temp_path)

    finally:
        import os
        os.unlink(temp_path)


def test_fallback_id_pidcustomerfuel1():
    """Test fallback CustomerFuelID from PIDCustomerFuel1."""

    # Using PIDCustomerFuel1 as ID (when Customer Fuel Unique ID missing)
    csv_data = """PIDCustomerFuel1,Customer Number,Customer Fuel Type
PID001,101,Oil
PID002,102,Propane
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        df = io.load_customer_fuel(temp_path)

        assert 'CustomerFuelID' in df.columns
        assert df.loc[0, 'CustomerFuelID'] == 'PID001'
        assert df.loc[1, 'CustomerFuelID'] == 'PID002'

    finally:
        import os
        os.unlink(temp_path)


def test_seasonal_k_factors_with_hyphens():
    """Test seasonal K-factor headers with hyphens and spaces."""

    csv_data = """Customer Fuel Unique ID,Customer Number,Customer Fuel Type,K Factor - Winter,K Factor - Summer,K Factor - Fall,K Factor - Spring
1001,101,Oil,0.65,0.35,0.50,0.45
1002,102,Propane,0.58,0.30,0.45,0.40
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        df = io.load_customer_fuel(temp_path)

        assert 'WinterK' in df.columns
        assert 'SummerK' in df.columns
        assert 'FallK' in df.columns
        assert 'SpringK' in df.columns

        assert df.loc[0, 'WinterK'] == 0.65
        assert df.loc[0, 'SummerK'] == 0.35
        assert df.loc[0, 'FallK'] == 0.50
        assert df.loc[0, 'SpringK'] == 0.45

    finally:
        import os
        os.unlink(temp_path)


def test_percent_full_with_special_char():
    """Test '% Full' header with percent sign."""

    csv_data = """Customer Fuel Unique ID,Customer Number,Customer Fuel Type,% Full
1001,101,Oil,60
1002,102,Propane,45
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        df = io.load_customer_fuel(temp_path)

        assert 'PercentFull' in df.columns
        assert df.loc[0, 'PercentFull'] == 60
        assert df.loc[1, 'PercentFull'] == 45

    finally:
        import os
        os.unlink(temp_path)


def test_fuel_suffix_fields():
    """Test fields with ' - Fuel' suffix."""

    csv_data = """Customer Fuel Unique ID,Customer Number,Customer Fuel Type,Zone - Fuel,Optimum Delivery - Fuel,Estimated Delivery - Fuel,Salesperson - Fuel Acct
1001,101,Oil,Zone1,180,175,Smith
1002,102,Propane,Zone2,300,290,Jones
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        df = io.load_customer_fuel(temp_path)

        assert 'FuelZone' in df.columns
        assert 'OptimumDelivery' in df.columns
        assert 'EstimatedDelivery' in df.columns
        assert 'Salesperson' in df.columns

        assert df.loc[0, 'FuelZone'] == 'Zone1'
        assert df.loc[0, 'OptimumDelivery'] == 180
        assert df.loc[0, 'EstimatedDelivery'] == 175
        assert df.loc[0, 'Salesperson'] == 'Smith'

    finally:
        import os
        os.unlink(temp_path)


def test_empty_first_column_ignored():
    """Test that empty first column (common in exports) is ignored."""

    # Note the leading comma (empty column)
    csv_data = """,Customer Fuel Unique ID,Customer Number,Customer Fuel Type
,1001,101,Oil
,1002,102,Propane
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name

    try:
        df = io.load_customer_fuel(temp_path)

        # Should still work despite empty column
        assert 'CustomerFuelID' in df.columns
        assert 'CustomerID' in df.columns
        assert 'FuelType' in df.columns

    finally:
        import os
        os.unlink(temp_path)


def test_normalize_header_function():
    """Test the _normalize_header helper directly."""

    # Test various header formats
    assert io._normalize_header('Customer Fuel Unique ID') == 'customer fuel unique id'
    assert io._normalize_header('K Factor - Winter') == 'k factor winter'  # Dash removed, spaces collapsed
    assert io._normalize_header('% Full') == 'full'  # Percent sign and space removed
    assert io._normalize_header('  Usable Size  ') == 'usable size'  # Trim whitespace
    assert io._normalize_header('Zone - Fuel') == 'zone fuel'  # Dash removed, spaces collapsed
    assert io._normalize_header('PIDCustomerFuel1') == 'pidcustomerfuel1'
