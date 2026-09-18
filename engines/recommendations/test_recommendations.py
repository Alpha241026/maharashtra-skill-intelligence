"""Unit tests for the Government Recommendation Component."""

import pytest
from engines.supply_demand import SupplyDemandResult
from engines.recommendations import (
    RecommendationEngine,
    RecommendationConfig,
    GovernmentRecommendation,
    PriorityRulesEvaluator,
)


@pytest.fixture
def engine():
    return RecommendationEngine()


def test_high_priority_gap(engine):
    """Test high-priority capacity expansion recommendation when current gap is severe."""
    sd_res = SupplyDemandResult(
        district="Nagpur",
        sector="Renewable Energy",
        trade="Solar PV Installer",
        supply_count=20.0,
        demand_count=500.0,
        supply_score=10.0,
        current_demand_score=85.0,
        current_gap=75.0,
        priority_score=88.0,
        gap_category="High Gap",
        confidence_score=1.0,
        data_availability={"has_supply": True, "has_current_demand": True, "has_future_demand": True},
    )

    recs = engine.generate_recommendations([sd_res])
    assert len(recs) == 1
    rec = recs[0]
    assert rec.priority == "High"
    assert rec.recommendation_type == "Capacity Expansion"
    assert "Urgent ITI capacity expansion" in rec.recommendation
    assert rec.supporting_metrics["current_gap"] == 75.0


def test_moderate_gap(engine):
    """Test moderate gap recommendation leading to capacity realignment."""
    sd_res = SupplyDemandResult(
        district="Pune",
        sector="Manufacturing",
        trade="CNC Machinist",
        supply_count=80.0,
        demand_count=120.0,
        supply_score=40.0,
        current_demand_score=55.0,
        current_gap=15.0,
        priority_score=45.0,
        gap_category="Moderate Gap",
        confidence_score=0.8,
        data_availability={"has_supply": True, "has_current_demand": True, "has_future_demand": False},
    )

    recs = engine.generate_recommendations([sd_res])
    assert len(recs) == 1
    rec = recs[0]
    assert rec.priority == "Medium"
    assert rec.recommendation_type == "Capacity Realignment"
    assert "Gradual seat capacity enhancement" in rec.recommendation


def test_balanced_case(engine):
    """Test balanced supply/demand scenario recommending maintaining capacity."""
    sd_res = SupplyDemandResult(
        district="Nashik",
        sector="Services",
        trade="Electrician",
        supply_count=100.0,
        demand_count=102.0,
        supply_score=50.0,
        current_demand_score=52.0,
        current_gap=2.0,
        priority_score=25.0,
        gap_category="Balanced",
        confidence_score=1.0,
        data_availability={"has_supply": True, "has_current_demand": True, "has_future_demand": True},
    )

    recs = engine.generate_recommendations([sd_res])
    assert len(recs) == 1
    rec = recs[0]
    assert rec.priority == "Low"
    assert rec.recommendation_type == "Maintain Capacity"
    assert "Maintain existing ITI intake capacity" in rec.recommendation


def test_future_demand_opportunity(engine):
    """Test future demand opportunity recommendation when growth trend is high despite low current gap."""
    sd_res = SupplyDemandResult(
        district="Chhatrapati Sambhajinagar",
        sector="Automation",
        trade="Robotics Technician",
        supply_count=50.0,
        demand_count=55.0,
        supply_score=50.0,
        current_demand_score=55.0,
        current_gap=5.0,
        future_demand_score=90.0,
        future_gap=40.0,
        priority_score=70.0,
        gap_category="Balanced",
        confidence_score=1.0,
        data_availability={"has_supply": True, "has_current_demand": True, "has_future_demand": True, "growth_trend": 35.0},
    )

    recs = engine.generate_recommendations([sd_res])
    assert len(recs) == 1
    rec = recs[0]
    assert rec.priority == "High"
    assert rec.recommendation_type == "Emerging Skill Pipeline"
    assert "Proactively introduce specialized vocational modules" in rec.recommendation


def test_insufficient_data(engine):
    """Test scenario where data confidence is below required threshold."""
    sd_res = SupplyDemandResult(
        district="Gadchiroli",
        sector="Mining",
        trade="Heavy Equipment Operator",
        supply_count=None,
        demand_count=50.0,
        supply_score=0.0,
        current_demand_score=20.0,
        current_gap=20.0,
        priority_score=10.0,
        gap_category="Moderate Gap",
        confidence_score=0.4,
        data_availability={"has_supply": False, "has_current_demand": True, "has_future_demand": False},
    )

    recs = engine.generate_recommendations([sd_res])
    assert len(recs) == 1
    rec = recs[0]
    assert rec.priority == "Insufficient Data"
    assert rec.recommendation_type == "Data Ingestion Required"
    assert "Collect further supply and demand data" in rec.recommendation
