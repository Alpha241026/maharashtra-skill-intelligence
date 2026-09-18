"""Unit tests for the Supply-Demand Intelligence Component."""

import pandas as pd
import pytest
from engines.supply_demand import SupplyDemandEngine, SupplyDemandConfig, SupplyDemandResult


@pytest.fixture
def base_config():
    return SupplyDemandConfig(
        district_col="district",
        sector_col="sector",
        trade_col="trade",
        supply_count_col="supply_count",
        demand_count_col="demand_count",
        future_demand_count_col="future_demand_count",
    )


def test_balanced_supply_demand(base_config):
    """Test scenario where supply roughly equals demand."""
    supply_df = pd.DataFrame([
        {"district": "Pune", "sector": "Automotive", "trade": "CNC Operator", "supply_count": 100},
    ])
    demand_df = pd.DataFrame([
        {"district": "Pune", "sector": "Automotive", "trade": "CNC Operator", "demand_count": 100, "future_demand_count": 100},
    ])

    engine = SupplyDemandEngine(config=base_config)
    results = engine.analyze(supply_df, demand_df)

    assert len(results) == 1
    res = results[0]
    assert isinstance(res, SupplyDemandResult)
    assert res.trade == "CNC Operator"
    assert res.current_gap == 0.0
    assert res.gap_category == "Balanced"


def test_high_demand_low_supply(base_config):
    """Test scenario with high demand and low supply resulting in High Gap."""
    supply_df = pd.DataFrame([
        {"district": "Nagpur", "sector": "Renewable", "trade": "Solar Technician", "supply_count": 10},
        {"district": "Nagpur", "sector": "Renewable", "trade": "Wind Technician", "supply_count": 50},
    ])
    demand_df = pd.DataFrame([
        {"district": "Nagpur", "sector": "Renewable", "trade": "Solar Technician", "demand_count": 500, "future_demand_count": 700},
        {"district": "Nagpur", "sector": "Renewable", "trade": "Wind Technician", "demand_count": 50, "future_demand_count": 60},
    ])

    engine = SupplyDemandEngine(config=base_config)
    results = engine.analyze(supply_df, demand_df)

    solar_res = next(r for r in results if r.trade == "Solar Technician")
    assert solar_res.current_gap > 30.0
    assert solar_res.gap_category == "High Gap"
    assert solar_res.priority_score > 50.0


def test_oversupply(base_config):
    """Test scenario where supply far exceeds demand."""
    supply_df = pd.DataFrame([
        {"district": "Nashik", "sector": "Traditional", "trade": "Handicraft Weaver", "supply_count": 500},
        {"district": "Nashik", "sector": "Traditional", "trade": "Potter", "supply_count": 50},
    ])
    demand_df = pd.DataFrame([
        {"district": "Nashik", "sector": "Traditional", "trade": "Handicraft Weaver", "demand_count": 20},
        {"district": "Nashik", "sector": "Traditional", "trade": "Potter", "demand_count": 50},
    ])

    engine = SupplyDemandEngine(config=base_config)
    results = engine.analyze(supply_df, demand_df)

    weaver_res = next(r for r in results if r.trade == "Handicraft Weaver")
    assert weaver_res.current_gap < -10.0
    assert weaver_res.gap_category == "Oversupply"


def test_missing_future_demand(base_config):
    """Test scenario where future demand dataset column is missing/None."""
    supply_df = pd.DataFrame([
        {"district": "Thane", "sector": "IT", "trade": "Network Technician", "supply_count": 150},
    ])
    demand_df = pd.DataFrame([
        {"district": "Thane", "sector": "IT", "trade": "Network Technician", "demand_count": 200},
    ])

    engine = SupplyDemandEngine(config=base_config)
    results = engine.analyze(supply_df, demand_df)

    assert len(results) == 1
    res = results[0]
    assert res.future_demand_score is None
    assert res.future_gap is None
    assert res.data_availability["has_future_demand"] is False
    assert res.confidence_score == 0.8


def test_missing_values_handling(base_config):
    """Test handling of NaN missing values in supply or demand datasets."""
    supply_df = pd.DataFrame([
        {"district": "Aurangabad", "sector": "Services", "trade": "Electrician", "supply_count": None},
        {"district": "Aurangabad", "sector": "Services", "trade": "Plumber", "supply_count": 80},
    ])
    demand_df = pd.DataFrame([
        {"district": "Aurangabad", "sector": "Services", "trade": "Electrician", "demand_count": 300},
        {"district": "Aurangabad", "sector": "Services", "trade": "Mechanic", "demand_count": 100},
    ])

    engine = SupplyDemandEngine(config=base_config)
    results = engine.analyze(supply_df, demand_df)

    elec_res = next(r for r in results if r.trade == "Electrician")
    assert elec_res.supply_count is None
    assert elec_res.demand_count == 300
    assert elec_res.data_availability["has_supply"] is False
    assert elec_res.confidence_score == 0.4

    mech_res = next(r for r in results if r.trade == "Mechanic")
    assert mech_res.supply_count is None
    assert mech_res.demand_count == 100
    assert mech_res.data_availability["has_supply"] is False
