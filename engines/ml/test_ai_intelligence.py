"""Unit tests for AI Intelligence Engine."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from engines.ml.ai_intelligence import AIIntelligenceEngine
from engines.ml.opportunity_model import OpportunityModel, DEFAULT_DATA_PATH, DEFAULT_MODEL_PATH


@pytest.fixture
def mock_data_and_model(tmp_path):
    data_file = tmp_path / "mssds_district_sector_intelligence.csv"
    model_file = tmp_path / "opportunity_model.joblib"

    df = pd.DataFrame({
        "district": ["Pune", "Mumbai Suburban"],
        "sector": ["Automotive", "BFSI"],
        "industry_size": [9300.0, 15000.0],
        "organization_count": [30.0, 100.0],
        "candidate_aspiration": [281.0, 500.0],
        "mssds_trained_2022_23": [10.0, 50.0],
        "dsdp_training": [5.0, 20.0],
        "projected_training": [100.0, 300.0],
        "projection_available": [True, True],
        "evidence_confidence": [0.67, 0.83],
        "training_pressure_score": [15.0, np.nan],
        "industry_opportunity_score": [43.88, 82.18],
        "source": ["mssds_2023_projection_merged.csv", "mssds_2023_projection_merged.csv"],
    })
    df.to_csv(data_file, index=False)

    model = OpportunityModel(random_state=42, n_estimators=10)
    model.train(df, test_size=0.5)
    model.save(model_file)

    return data_file, model_file


def test_ai_intelligence_valid_district_sector(mock_data_and_model):
    data_file, model_file = mock_data_and_model
    engine = AIIntelligenceEngine(model_path=model_file, data_path=data_file)

    res = engine.analyze_district_sector("Pune", "Automotive")

    assert res["status"] == "success"
    assert res["district"] == "Pune"
    assert res["sector"] == "Automotive"
    assert isinstance(res["predicted_opportunity_score"], float)
    assert res["opportunity_band"] in ["High", "Moderate", "Low"]
    assert res["training_pressure_score"] == 15.0
    assert res["evidence_confidence"] == 0.67
    assert res["projection_available"] is True
    assert res["source"] == "mssds_2023_projection_merged.csv"
    assert len(res["top_feature_importances"]) <= 3
    if len(res["top_feature_importances"]) > 0:
        assert "feature" in res["top_feature_importances"][0]
        assert "importance" in res["top_feature_importances"][0]


def test_ai_intelligence_missing_district_sector(mock_data_and_model):
    data_file, model_file = mock_data_and_model
    engine = AIIntelligenceEngine(model_path=model_file, data_path=data_file)

    res = engine.analyze_district_sector("NonExistentDistrict", "NonExistentSector")

    assert res["status"] == "insufficient_data"
    assert res["district"] == "NonExistentDistrict"
    assert res["sector"] == "NonExistentSector"
    assert res["predicted_opportunity_score"] is None
    assert res["opportunity_band"] is None
    assert res["training_pressure_score"] is None
    assert res["evidence_confidence"] is None
    assert res["projection_available"] is None
    assert res["top_feature_importances"] == []
    assert res["source"] is None


def test_ai_intelligence_output_structure_and_types(mock_data_and_model):
    data_file, model_file = mock_data_and_model
    engine = AIIntelligenceEngine(model_path=model_file, data_path=data_file)

    res = engine.analyze_district_sector("mumbai suburban", "bfsi")

    required_keys = [
        "district",
        "sector",
        "status",
        "predicted_opportunity_score",
        "opportunity_band",
        "training_pressure_score",
        "evidence_confidence",
        "projection_available",
        "top_feature_importances",
        "source",
    ]
    for key in required_keys:
        assert key in res
