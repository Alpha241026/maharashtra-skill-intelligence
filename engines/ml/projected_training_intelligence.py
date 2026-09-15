"""Inference layer for ProjectedTrainingModel providing district-sector demand predictions."""

from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import pandas as pd
import numpy as np

from engines.ml.projected_training_model import (
    ProjectedTrainingModel,
    DEFAULT_DATA_PATH,
    DEFAULT_MODEL_PATH,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _assign_demand_band(predicted_val: float) -> str:
    """Assign demand band based on predicted_projected_training value."""
    if predicted_val >= 500.0:
        return "High"
    elif predicted_val >= 100.0:
        return "Moderate"
    else:
        return "Low"


def _clean_val(val: Any) -> Any:
    """Convert numpy/pandas types and NaNs to standard JSON types."""
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer, np.int64)):
        return int(val)
    if isinstance(val, (np.floating, np.float64)):
        return float(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    return val


class ProjectedTrainingIntelligence:
    """Inference engine leveraging ProjectedTrainingModel for district-sector training projections."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        data_path: Optional[Union[str, Path]] = None,
    ):
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.data_path = Path(data_path) if data_path else DEFAULT_DATA_PATH

        self.model = ProjectedTrainingModel()
        if self.model_path.exists():
            self.model.load(self.model_path)

        self._data_df: Optional[pd.DataFrame] = None

    def _get_data(self) -> pd.DataFrame:
        if self._data_df is None:
            if not self.data_path.exists():
                raise FileNotFoundError(f"Data file not found at {self.data_path}")
            self._data_df = pd.read_csv(self.data_path)
        return self._data_df

    def predict_district_sector(
        self,
        district: str,
        sector: str,
        record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Predict projected training demand for a given district and sector.
        Reads from data file if record is not explicitly provided.
        """
        if record is None:
            df = self._get_data()
            match = df[
                (df["district"].astype(str).str.lower() == district.lower())
                & (df["sector"].astype(str).str.lower() == sector.lower())
            ]

            if match.empty or not bool(match.iloc[0].get("projection_available", False)):
                return {
                    "district": district,
                    "sector": sector,
                    "status": "insufficient_data",
                    "predicted_projected_training": None,
                    "demand_band": None,
                    "evidence_confidence": None,
                    "top_feature_importances": [],
                }
            input_df = match.head(1).copy()
        else:
            required_keys = ["district", "sector"]
            if not all(k in record for k in required_keys):
                return {
                    "district": district,
                    "sector": sector,
                    "status": "insufficient_data",
                    "predicted_projected_training": None,
                    "demand_band": None,
                    "evidence_confidence": None,
                    "top_feature_importances": [],
                }
            input_df = pd.DataFrame([record])

        row = input_df.iloc[0]

        if not self.model.is_fitted:
            return {
                "district": str(row.get("district", district)),
                "sector": str(row.get("sector", sector)),
                "status": "insufficient_data",
                "predicted_projected_training": None,
                "demand_band": None,
                "evidence_confidence": _clean_val(row.get("evidence_confidence")),
                "top_feature_importances": [],
            }

        predicted_val = float(self.model.predict(input_df)[0])
        demand_band = _assign_demand_band(predicted_val)

        importance_info = self.model.get_feature_importance()
        top_features = importance_info.get("feature_importances", [])[:5]

        return {
            "district": str(row.get("district", district)),
            "sector": str(row.get("sector", sector)),
            "status": "success",
            "predicted_projected_training": round(predicted_val, 2),
            "demand_band": demand_band,
            "evidence_confidence": _clean_val(row.get("evidence_confidence")),
            "top_feature_importances": top_features,
        }
