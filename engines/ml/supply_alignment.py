"""Supply vs Predicted Demand Alignment Layer for comparing ITI capacity against ML projected training demand."""

from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import pandas as pd
import numpy as np

from engines.ml.projected_training_intelligence import ProjectedTrainingIntelligence

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ITI_PATH = PROJECT_ROOT / "data" / "processed" / "iti" / "maharashtra_iti_trade_supply_2026.csv"
DEFAULT_MSSDS_PATH = PROJECT_ROOT / "data" / "outputs" / "mssds_district_sector_intelligence.csv"


class SupplyAlignmentEngine:
    """Calculates alignment between ML-predicted projected training demand and ITI intake capacity."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        data_path: Optional[Union[str, Path]] = None,
        iti_path: Optional[Union[str, Path]] = None,
    ):
        self.data_path = Path(data_path) if data_path else DEFAULT_MSSDS_PATH
        self.iti_path = Path(iti_path) if iti_path else DEFAULT_ITI_PATH

        self.intel_engine = ProjectedTrainingIntelligence(
            model_path=model_path,
            data_path=self.data_path,
        )

        self._iti_df: Optional[pd.DataFrame] = None
        self._mssds_df: Optional[pd.DataFrame] = None

    def _get_iti_data(self) -> pd.DataFrame:
        if self._iti_df is None:
            if not self.iti_path.exists():
                raise FileNotFoundError(f"ITI dataset file not found at {self.iti_path}")
            self._iti_df = pd.read_csv(self.iti_path)
        return self._iti_df

    def _get_mssds_data(self) -> pd.DataFrame:
        if self._mssds_df is None:
            if not self.data_path.exists():
                raise FileNotFoundError(f"MSSDS intelligence dataset file not found at {self.data_path}")
            self._mssds_df = pd.read_csv(self.data_path)
        return self._mssds_df

    def analyze_district_alignment(self, district: str) -> Dict[str, Any]:
        """
        Compare ML-predicted projected training demand with ITI intake capacity for a district.
        
        Returns JSON-serializable alignment analysis.
        """
        mssds_df = self._get_mssds_data()
        iti_df = self._get_iti_data()

        # Match MSSDS records for district
        mssds_match = mssds_df[
            mssds_df["district"].astype(str).str.lower() == district.lower()
        ].copy()

        # Match ITI supply records for district
        iti_match = iti_df[
            iti_df["district"].astype(str).str.lower() == district.lower()
        ].copy()

        # Insufficient data check
        if mssds_match.empty or iti_match.empty:
            return {
                "district": district,
                "status": "insufficient_data",
                "note": "Comparison between ML-estimated projected training demand and ITI intake capacity.",
                "predicted_total_training_demand": None,
                "total_iti_capacity": None,
                "alignment_gap": None,
                "alignment_status": None,
                "sectors_analyzed": 0,
                "evidence_confidence": None,
            }

        # Filter MSSDS for records where projection_available is True
        valid_sectors_df = mssds_match[mssds_match["projection_available"] == True]

        if valid_sectors_df.empty:
            return {
                "district": str(mssds_match["district"].iloc[0]),
                "status": "insufficient_data",
                "note": "Comparison between ML-estimated projected training demand and ITI intake capacity.",
                "predicted_total_training_demand": None,
                "total_iti_capacity": None,
                "alignment_gap": None,
                "alignment_status": None,
                "sectors_analyzed": 0,
                "evidence_confidence": None,
            }

        matched_district_name = str(mssds_match["district"].iloc[0])

        # Evaluate predictions across valid sectors
        total_predicted_demand = 0.0
        conf_list: List[float] = []
        sectors_analyzed: List[str] = []

        for idx, row in valid_sectors_df.iterrows():
            sec = str(row["sector"])
            intel = self.intel_engine.predict_district_sector(matched_district_name, sec)
            if intel["status"] == "success" and intel.get("predicted_projected_training") is not None:
                total_predicted_demand += float(intel["predicted_projected_training"])
                sectors_analyzed.append(sec)
                if intel.get("evidence_confidence") is not None:
                    conf_list.append(float(intel["evidence_confidence"]))

        if not sectors_analyzed:
            return {
                "district": matched_district_name,
                "status": "insufficient_data",
                "note": "Comparison between ML-estimated projected training demand and ITI intake capacity.",
                "predicted_total_training_demand": None,
                "total_iti_capacity": None,
                "alignment_gap": None,
                "alignment_status": None,
                "sectors_analyzed": 0,
                "evidence_confidence": None,
            }

        # Calculate district total ITI intake capacity
        total_iti_capacity = float(pd.to_numeric(iti_match["intake"], errors="coerce").fillna(0).sum())

        # Alignment gap = ML predicted demand - ITI capacity
        alignment_gap = total_predicted_demand - total_iti_capacity

        if alignment_gap > 0:
            alignment_status = "Potential shortage"
        elif alignment_gap < 0:
            alignment_status = "Potential surplus"
        else:
            alignment_status = "Approximately aligned"

        avg_confidence = float(np.mean(conf_list)) if conf_list else None

        return {
            "district": matched_district_name,
            "status": "success",
            "note": "Comparison between ML-estimated projected training demand and ITI intake capacity.",
            "predicted_total_training_demand": round(total_predicted_demand, 2),
            "total_iti_capacity": round(total_iti_capacity, 2),
            "alignment_gap": round(alignment_gap, 2),
            "alignment_status": alignment_status,
            "sectors_analyzed": len(sectors_analyzed),
            "evidence_confidence": round(avg_confidence, 2) if avg_confidence is not None else None,
        }
