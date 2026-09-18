"""Unit tests for Labour Market Intelligence Component."""

import pandas as pd
import pytest
from engines.labour_market import LabourMarketEngine, ColumnConfig, DemandAnalysisResult


@pytest.fixture
def static_toy_df():
    """Toy DataFrame simulating a single snapshot of skill demand counts."""
    return pd.DataFrame([
        {"skill_name": "Solar Installer", "job_vacancies": 500, "sector": "Renewable Energy"},
        {"skill_name": "Electrician", "job_vacancies": 300, "sector": "Construction"},
        {"skill_name": "CNC Operator", "job_vacancies": 100, "sector": "Manufacturing"},
        {"skill_name": "Basic Handyman", "job_vacancies": 20, "sector": "Services"},
    ])


@pytest.fixture
def time_series_toy_df():
    """Toy DataFrame simulating time-series data and future projections."""
    return pd.DataFrame([
        {"trade": "Welder", "year": 2024, "openings": 100, "projected_openings": 150, "industry": "Industrial"},
        {"trade": "Welder", "year": 2025, "openings": 130, "projected_openings": 180, "industry": "Industrial"},
        {"trade": "Fitter", "year": 2024, "openings": 200, "projected_openings": 210, "industry": "Industrial"},
        {"trade": "Fitter", "year": 2025, "openings": 180, "projected_openings": 190, "industry": "Industrial"},
    ])


def test_static_demand_scoring(static_toy_df):
    config = ColumnConfig(entity_col="skill_name", demand_count_col="job_vacancies")
    engine = LabourMarketEngine(config=config)

    results = engine.analyze_demand(static_toy_df)
    assert len(results) == 4
    
    # Highest demand skill should have score 100.0 and category 'Very High'
    solar_res = next(r for r in results if r.entity_name == "Solar Installer")
    assert solar_res.current_demand_score == 100.0
    assert solar_res.demand_category == "Very High"

    # Lowest demand skill should have score 0.0 and category 'Low'
    handyman_res = next(r for r in results if r.entity_name == "Basic Handyman")
    assert handyman_res.current_demand_score == 0.0
    assert handyman_res.demand_category == "Low"


def test_trend_and_future_projection(time_series_toy_df):
    config = ColumnConfig(
        entity_col="trade",
        demand_count_col="openings",
        time_col="year",
        future_demand_col="projected_openings",
    )
    engine = LabourMarketEngine(config=config)

    results = engine.analyze_demand(time_series_toy_df)
    assert len(results) == 2

    welder_res = next(r for r in results if r.entity_name == "Welder")
    # Growth from 100 to 130 = +30.0%
    assert welder_res.growth_trend == 30.0
    assert welder_res.future_demand_score is not None
    assert welder_res.confidence_score > 0.5
    assert welder_res.data_availability["has_time_series"] is True
    assert welder_res.data_availability["has_projections"] is True

    fitter_res = next(r for r in results if r.entity_name == "Fitter")
    # Growth from 200 to 180 = -10.0%
    assert fitter_res.growth_trend == -10.0


def test_sector_aggregation(static_toy_df):
    config = ColumnConfig(entity_col="skill_name", demand_count_col="job_vacancies")
    engine = LabourMarketEngine(config=config)

    sector_summary = engine.aggregate_by_category(static_toy_df, group_by_col="sector")
    assert "sector" in sector_summary.columns
    assert "job_vacancies" in sector_summary.columns
    assert "demand_score" in sector_summary.columns
    assert len(sector_summary) == 4
