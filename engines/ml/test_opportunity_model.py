"""Tests for ML opportunity estimation model."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from engines.ml.opportunity_model import OpportunityModel, DEFAULT_DATA_PATH


def test_opportunity_model_training_and_evaluation(tmp_path):
    # Create synthetic dataset with target and features
    df = pd.DataFrame({
        "district": ["Pune", "Mumbai", "Thane", "Nagpur", "Nashik"] * 10,
        "sector": ["Automotive", "BFSI", "IT", "Agriculture", "Electronics"] * 10,
        "industry_size": [1000.0, 5000.0, np.nan, 200.0, 1500.0] * 10,
        "organization_count": [10, 50, 5, np.nan, 20] * 10,
        "candidate_aspiration": [500, 2000, 300, 100, np.nan] * 10,
        "mssds_trained_2022_23": [50, 100, np.nan, 10, 30] * 10,
        "dsdp_training": [10, 20, np.nan, 5, 10] * 10,
        "projected_training": [100, 200, np.nan, 20, 50] * 10,
        "projection_available": [True, True, False, True, True] * 10,
        "evidence_confidence": [0.8, 1.0, 0.3, 0.5, 0.7] * 10,
        "industry_opportunity_score": [25.0, 75.0, 10.0, 5.0, 30.0] * 10,
    })

    model = OpportunityModel(random_state=42, n_estimators=10)
    
    # Assert unfitted errors
    with pytest.raises(RuntimeError):
        model.predict(df)

    with pytest.raises(RuntimeError):
        model.evaluate(df)

    # Train model
    metrics = model.train(df, test_size=0.2)
    assert "mae" in metrics
    assert "r2" in metrics
    assert model.is_fitted

    # Predict
    preds = model.predict(df)
    assert len(preds) == len(df)
    assert not np.isnan(preds).any()

    # Evaluate
    eval_metrics = model.evaluate(df)
    assert "mae" in eval_metrics
    assert "r2" in eval_metrics

    # Save and Load
    model_file = tmp_path / "test_model.joblib"
    model.save(model_file)
    assert model_file.exists()

    new_model = OpportunityModel()
    new_model.load(model_file)
    assert new_model.is_fitted

    new_preds = new_model.predict(df)
    np.testing.assert_allclose(preds, new_preds)


@pytest.mark.skipif(not DEFAULT_DATA_PATH.exists(), reason="Real dataset not available")
def test_opportunity_model_real_data():
    model = OpportunityModel(random_state=42, n_estimators=20)
    metrics = model.train(test_size=0.2)
    assert metrics["mae"] >= 0.0
    assert metrics["r2"] <= 1.0


def test_opportunity_model_feature_importance():
    df = pd.DataFrame({
        "district": ["Pune", "Mumbai"] * 5,
        "sector": ["Automotive", "BFSI"] * 5,
        "industry_size": [1000.0, 5000.0] * 5,
        "organization_count": [10, 50] * 5,
        "candidate_aspiration": [500, 2000] * 5,
        "mssds_trained_2022_23": [50, 100] * 5,
        "dsdp_training": [10, 20] * 5,
        "projected_training": [100, 200] * 5,
        "projection_available": [True, True] * 5,
        "evidence_confidence": [0.8, 1.0] * 5,
        "industry_opportunity_score": [25.0, 75.0] * 5,
    })

    model = OpportunityModel(random_state=42, n_estimators=10)
    
    with pytest.raises(RuntimeError):
        model.get_feature_importance()

    model.train(df, test_size=0.2)
    importance_info = model.get_feature_importance()

    assert "total_features" in importance_info
    assert "feature_importances" in importance_info
    assert len(importance_info["feature_importances"]) == importance_info["total_features"]
    assert importance_info["total_features"] > 0

    first_item = importance_info["feature_importances"][0]
    assert "feature" in first_item
    assert "importance" in first_item
    assert isinstance(first_item["feature"], str)
    assert isinstance(first_item["importance"], float)

