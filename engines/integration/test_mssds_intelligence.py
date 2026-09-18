"""Focused unit tests for MSSDS District-Sector Intelligence Layer."""

import pytest
import pandas as pd
import numpy as np

from engines.integration.mssds_intelligence import (
    compute_mssds_district_sector_intelligence,
    MSSDSIntelligenceResult,
)


def test_industry_opportunity_score_excludes_missing_values():
    """Verify that missing values are not treated as zero in industry opportunity score."""
    df = pd.DataFrame([
        {
            "district": "Pune",
            "sector": "Automotive",
            "industry_size": 100.0,
            "organization_count": np.nan,  # Missing
            "candidate_aspiration": 200.0,
            "projected_training": np.nan,
            "mssds_trained_2022_23": np.nan,
        },
        {
            "district": "Pune",
            "sector": "Electronics",
            "industry_size": 500.0,
            "organization_count": 50.0,
            "candidate_aspiration": 600.0,
            "projected_training": np.nan,
            "mssds_trained_2022_23": np.nan,
        },
    ])

    result = compute_mssds_district_sector_intelligence(df)
    assert len(result) == 2

    # Automotive row: industry_size norm=0.0 (wt 0.40), candidate_aspiration norm=0.0 (wt 0.35) -> 0.0
    row_auto = result.iloc[0]
    assert pd.notna(row_auto["industry_opportunity_score"])
    assert row_auto["industry_opportunity_score"] == 0.0

    # Electronics row: max for both -> score = 100.0
    row_elec = result.iloc[1]
    assert row_elec["industry_opportunity_score"] == 100.0


def test_training_pressure_score_calculation():
    """Verify training pressure score uses hierarchy (mssds_trained_2022_23 then mssds_trained) without summing dsdp_training."""
    df = pd.DataFrame([
        {
            "district": "Akola",
            "sector": "Agriculture",
            "mssds_trained_2022_23": 87.0,  # Preference 1
            "dsdp_training": 360.0,         # Separate signal, excluded from existing_training
            "projected_training": 120.0,
        },
        {
            "district": "Ahmednagar",
            "sector": "Agriculture",
            "mssds_trained_2022_23": np.nan,
            "mssds_trained": 240.0,          # Preference 2 fallback
            "projected_training": 50.0,
        },
        {
            "district": "Ahmednagar",
            "sector": "Green Jobs",
            "mssds_trained_2022_23": 100.0,
            "projected_training": 0.0,       # Zero projected -> valid 0.0 score
        },
        {
            "district": "Ahmednagar",
            "sector": "Construction",
            "mssds_trained_2022_23": np.nan,
            "mssds_trained": np.nan,
            "dsdp_training": 100.0,
            "projected_training": 320.0,     # Valid projected, but no hierarchy existing -> null
        },
        {
            "district": "Amravati",
            "sector": "Healthcare",
            "mssds_trained_2022_23": 100.0,
            "projected_training": np.nan,    # Missing projected -> null
        },
    ])

    result = compute_mssds_district_sector_intelligence(df)

    # Row 0: existing = 87.0, projected = 120 -> 120 / (87 + 120) * 100 = 57.97%
    assert pd.notna(result.iloc[0]["training_pressure_score"])
    assert round(result.iloc[0]["training_pressure_score"], 2) == 57.97

    # Row 1: existing = 240.0 (mssds_trained fallback), projected = 50 -> 50 / (240 + 50) * 100 = 17.24%
    assert pd.notna(result.iloc[1]["training_pressure_score"])
    assert round(result.iloc[1]["training_pressure_score"], 2) == 17.24

    # Row 2: existing = 100.0, projected = 0.0 -> valid 0.0
    assert pd.notna(result.iloc[2]["training_pressure_score"])
    assert result.iloc[2]["training_pressure_score"] == 0.0

    # Row 3: missing hierarchy existing training evidence (dsdp_training ignored) -> null
    assert pd.isna(result.iloc[3]["training_pressure_score"])

    # Row 4: missing projected_training -> null
    assert pd.isna(result.iloc[4]["training_pressure_score"])


def test_mssds_intelligence_required_columns_and_schema():
    """Verify that all required columns are present in output."""
    result = compute_mssds_district_sector_intelligence()
    expected_cols = [
        "district",
        "sector",
        "industry_opportunity_score",
        "training_pressure_score",
        "evidence_confidence",
        "projection_available",
        "industry_size",
        "organization_count",
        "candidate_aspiration",
        "mssds_trained_2022_23",
        "dsdp_training",
        "projected_training",
        "source",
    ]

    for col in expected_cols:
        assert col in result.columns, f"Missing required column: {col}"

    assert len(result) == 760


def test_pipeline_summary_and_mssds_export_keys():
    """Verify IntegrationPipeline produces mssds_intelligence key with 760 rows."""
    from engines.integration import IntegrationPipeline
    pipeline = IntegrationPipeline()
    res = pipeline.run_pipeline()
    assert "mssds_intelligence" in res
    assert len(res["mssds_intelligence"]) == 760

