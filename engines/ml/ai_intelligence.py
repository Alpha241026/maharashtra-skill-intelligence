"""AI Intelligence Engine leveraging OpportunityModel for district-sector inference."""

from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import pandas as pd
import numpy as np

from engines.ml.opportunity_model import (
    OpportunityModel,
    DEFAULT_DATA_PATH,
    DEFAULT_MODEL_PATH,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _assign_opportunity_band(score: float) -> str:
    """Categorize predicted opportunity score into High/Moderate/Low band."""
    if score >= 30.0:
        return "High"
    elif score >= 10.0:
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


class AIIntelligenceEngine:
    """AI Intelligence Engine providing district-sector predictions and explanations."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        data_path: Optional[Union[str, Path]] = None,
    ):
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.data_path = Path(data_path) if data_path else DEFAULT_DATA_PATH

        self.model = OpportunityModel()
        if self.model_path.exists():
            self.model.load(self.model_path)

        self._data_df: Optional[pd.DataFrame] = None

    def _get_data(self) -> pd.DataFrame:
        if self._data_df is None:
            if not self.data_path.exists():
                raise FileNotFoundError(f"Data file not found at {self.data_path}")
            self._data_df = pd.read_csv(self.data_path)
        return self._data_df

    def analyze_district_sector(self, district: str, sector: str) -> Dict[str, Any]:
        """Retrieve record for district and sector, predict score, and return AI intelligence response."""
        df = self._get_data()

        match = df[
            (df["district"].astype(str).str.lower() == district.lower())
            & (df["sector"].astype(str).str.lower() == sector.lower())
        ]

        if match.empty:
            return {
                "district": district,
                "sector": sector,
                "status": "insufficient_data",
                "message": f"No data found for district '{district}' and sector '{sector}'.",
                "predicted_opportunity_score": None,
                "opportunity_band": None,
                "training_pressure_score": None,
                "evidence_confidence": None,
                "projection_available": None,
                "top_feature_importances": [],
                "source": None,
            }

        row = match.iloc[0]

        # Predict score if model is loaded/fitted
        if self.model.is_fitted:
            input_df = match.head(1).copy()
            pred_score = float(self.model.predict(input_df)[0])
            feature_imp_info = self.model.get_feature_importance()
            top_3_features = feature_imp_info.get("feature_importances", [])[:3]
        else:
            pred_score = float(row.get("industry_opportunity_score", 0.0)) if not pd.isna(row.get("industry_opportunity_score")) else 0.0
            top_3_features = []

        band = _assign_opportunity_band(pred_score)

        return {
            "district": str(row["district"]),
            "sector": str(row["sector"]),
            "status": "success",
            "predicted_opportunity_score": round(pred_score, 2),
            "opportunity_band": band,
            "training_pressure_score": _clean_val(row.get("training_pressure_score")),
            "evidence_confidence": _clean_val(row.get("evidence_confidence")),
            "projection_available": _clean_val(row.get("projection_available")),
            "top_feature_importances": top_3_features,
            "source": _clean_val(row.get("source")),
        }
