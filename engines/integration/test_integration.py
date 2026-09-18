"""Unit tests for Data Integration Component."""

import tempfile
from pathlib import Path
import pandas as pd
import pytest

from engines.integration import (
    normalize_district,
    normalize_trade_name,
    normalize_sector,
    safe_numeric_conversion,
    load_iti_supply,
    load_ncs_job_listings,
    load_mssds_projections,
    IntegrationPipeline,
)


def test_district_normalization():
    """Test district name normalization and alias resolution."""
    assert normalize_district("PUNE District") == "pune"
    assert normalize_district("Dist. Nagpur") == "nagpur"
    assert normalize_district("Aurangabad") == "chhatrapati sambhajinagar"
    assert normalize_district("Mumbai City") == "mumbai"
    assert normalize_district(None) is None
    assert normalize_district("") is None


def test_trade_normalization():
    """Test trade name normalization and framework suffix stripping."""
    assert normalize_trade_name("Electrician (NSQF)") == "electrician"
    assert normalize_trade_name("Welder (NSQF LEVEL 4)") == "welder"
    assert normalize_trade_name("Fitter (CTS)") == "fitter"
    assert normalize_trade_name(None) is None


def test_numeric_conversion():
    """Test safe numeric conversion with default value handling."""
    series = pd.Series(["100", "invalid", None, 50])
    result_with_default = safe_numeric_conversion(series, default_val=0.0)
    assert result_with_default.iloc[0] == 100.0
    assert result_with_default.iloc[1] == 0.0
    assert result_with_default.iloc[2] == 0.0
    assert result_with_default.iloc[3] == 50.0

    result_preserve_nan = safe_numeric_conversion(series, default_val=None)
    assert pd.isna(result_preserve_nan.iloc[1])


def test_iti_aggregation():
    """Test ITI supply aggregation by district + normalized_trade."""
    pipeline = IntegrationPipeline()
    toy_iti_df = pd.DataFrame([
        {
            "admission_year": 2026,
            "source_region": "Pune",
            "district": "Pune Dist.",
            "taluka": "Haveli",
            "iti_type": "Govt",
            "iti_name": "Govt ITI Aundh",
            "trade_name": "Electrician (NSQF)",
            "intake": 60,
            "raw_district": "Pune Dist.",
            "raw_trade_name": "Electrician (NSQF)",
            "normalized_district": "pune",
            "normalized_trade": "electrician",
            "dataset_source": "test_source",
        },
        {
            "admission_year": 2026,
            "source_region": "Pune",
            "district": "Pune",
            "taluka": "Haveli",
            "iti_type": "Govt",
            "iti_name": "Govt ITI Karvenagar",
            "trade_name": "Electrician",
            "intake": 40,
            "raw_district": "Pune",
            "raw_trade_name": "Electrician",
            "normalized_district": "pune",
            "normalized_trade": "electrician",
            "dataset_source": "test_source",
        },
    ])

    agg_table = pipeline.create_normalized_iti_supply(toy_iti_df)
    assert len(agg_table) == 1
    row = agg_table.iloc[0]
    assert row["normalized_district"] == "pune"
    assert row["normalized_trade"] == "electrician"
    assert row["total_intake"] == 100
    assert row["number_of_ITIs"] == 2


def test_ncs_aggregation():
    """Test NCS job listings aggregation by district + normalized_job_or_skill."""
    pipeline = IntegrationPipeline()
    toy_ncs_df = pd.DataFrame([
        {
            "record_type": "Job",
            "job_title": "Fitter (CTS)",
            "district": "Nagpur",
            "raw_district": "Nagpur",
            "raw_job_title": "Fitter (CTS)",
            "normalized_district": "nagpur",
            "normalized_job_or_skill": "fitter",
            "dataset_source": "ncs_test",
        },
        {
            "record_type": "Job",
            "job_title": "Fitter",
            "district": "Nagpur",
            "raw_district": "Nagpur",
            "raw_job_title": "Fitter",
            "normalized_district": "nagpur",
            "normalized_job_or_skill": "fitter",
            "dataset_source": "ncs_test",
        },
    ])

    agg_table = pipeline.create_normalized_ncs_demand(toy_ncs_df)
    assert len(agg_table) == 1
    row = agg_table.iloc[0]
    assert row["normalized_district"] == "nagpur"
    assert row["normalized_job_or_skill"] == "fitter"
    assert row["listing_count"] == 2


def test_mssds_loading_and_aggregation():
    """Test MSSDS projections loading and sector aggregation."""
    pipeline = IntegrationPipeline()
    toy_mssds_df = pd.DataFrame([
        {
            "district": "Nashik",
            "sector": "Automotive",
            "mssds_trained": 200,
            "projected_training": 300,
            "organization_count": 10,
            "raw_district": "Nashik",
            "raw_sector": "Automotive",
            "normalized_district": "nashik",
            "normalized_sector": "automotive",
            "dataset_source": "mssds_test",
        },
        {
            "district": "Nashik",
            "sector": "Automotive",
            "mssds_trained": 150,
            "projected_training": 200,
            "organization_count": 5,
            "raw_district": "Nashik",
            "raw_sector": "Automotive",
            "normalized_district": "nashik",
            "normalized_sector": "automotive",
            "dataset_source": "mssds_test",
        },
    ])

    agg_table = pipeline.create_normalized_mssds_table(toy_mssds_df)
    assert len(agg_table) == 1
    row = agg_table.iloc[0]
    assert row["normalized_district"] == "nashik"
    assert row["normalized_sector"] == "automotive"
    assert row["current_training"] == 350
    assert row["projected_training"] == 500


def test_missing_value_handling():
    """Test dataset loaders and pipeline behavior with missing values."""
    toy_df = pd.DataFrame([
        {
            "district": None,
            "trade_name": "Welder",
            "intake": None,
            "raw_district": None,
            "raw_trade_name": "Welder",
            "normalized_district": None,
            "normalized_trade": "welder",
            "dataset_source": "test",
            "iti_name": "ITI 1",
        }
    ])
    pipeline = IntegrationPipeline()
    agg = pipeline.create_normalized_iti_supply(toy_df)
    assert len(agg) == 1
    assert pd.isna(agg.iloc[0]["normalized_district"])


def test_ncs_filtering_only_matched():
    """Test that create_normalized_ncs_demand includes ONLY records with mapping_status == 'matched'."""
    pipeline = IntegrationPipeline()
    toy_ncs_df = pd.DataFrame([
        {
            "original_job_title": "Electrician",
            "matched_trade": "Electrician",
            "mapping_status": "matched",
            "normalized_district": "pune",
            "raw_district": "Pune",
            "dataset_source": "test",
        },
        {
            "original_job_title": "Packing Work From Home",
            "matched_trade": None,
            "mapping_status": "unmatched",
            "normalized_district": "pune",
            "raw_district": "Pune",
            "dataset_source": "test",
        },
        {
            "original_job_title": "Technician Helper",
            "matched_trade": "Mechanic Motor Vehicle",
            "mapping_status": "ambiguous",
            "normalized_district": "pune",
            "raw_district": "Pune",
            "dataset_source": "test",
        },
    ])

    agg = pipeline.create_normalized_ncs_demand(toy_ncs_df, only_matched=True)
    assert len(agg) == 1
    assert agg.iloc[0]["normalized_trade"] == "electrician"
    assert agg.iloc[0]["listing_count"] == 1

