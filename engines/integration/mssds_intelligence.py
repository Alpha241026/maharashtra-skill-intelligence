"""MSSDS District-Sector Intelligence Layer for analyzing industry opportunity and training pressure metrics."""

from pathlib import Path
from typing import Optional, Union, Dict, Any, List
import pandas as pd
import numpy as np
from pydantic import BaseModel

from .data_loader import load_mssds_projections, DEFAULT_MSSDS_PATH
from .normalizer import safe_numeric_conversion, normalize_district, normalize_sector


class MSSDSIntelligenceResult(BaseModel):
    """Structured district-sector intelligence result from MSSDS data."""
    district: str
    sector: str
    normalized_district: Optional[str] = None
    normalized_sector: Optional[str] = None
    industry_opportunity_score: Optional[float] = None  # 0.0 - 100.0
    training_pressure_score: Optional[float] = None      # 0.0 - 100.0 (null if invalid/missing)
    evidence_confidence: float                           # 0.0 - 1.0
    projection_available: bool
    industry_size: Optional[float] = None
    organization_count: Optional[float] = None
    candidate_aspiration: Optional[float] = None
    mssds_trained_2022_23: Optional[float] = None
    dsdp_training: Optional[float] = None
    projected_training: Optional[float] = None
    source: str


def compute_mssds_district_sector_intelligence(
    mssds_df: Optional[pd.DataFrame] = None,
    file_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    Produce structured district-sector intelligence results from MSSDS projection data.

    Calculates:
    1. industry_opportunity_score (0-100): weighted combination of normalized industry_size (0.40),
       organization_count (0.25), and candidate_aspiration (0.35). Missing values are excluded
       without treating them as zero.
    2. training_pressure_score (0-100): projected / (existing + projected) * 100 when both existing
       training evidence and projected_training are valid; null otherwise.
    3. evidence_confidence (0-1): data completeness score based on available key fields.
    """
    if mssds_df is None:
        raw_df = pd.read_csv(file_path or DEFAULT_MSSDS_PATH)
    else:
        raw_df = mssds_df.copy()

    if raw_df.empty:
        return pd.DataFrame(columns=[
            "district", "sector", "normalized_district", "normalized_sector",
            "industry_opportunity_score", "training_pressure_score", "evidence_confidence",
            "projection_available", "industry_size", "organization_count", "candidate_aspiration",
            "mssds_trained_2022_23", "dsdp_training", "projected_training", "source"
        ])

    df = raw_df.copy()

    # Safe numeric conversion preserving NaNs
    numeric_cols = [
        "industry_size", "organization_count", "candidate_aspiration",
        "mssds_trained_2022_23", "dsdp_training", "mssds_trained", "projected_training"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = safe_numeric_conversion(df[col], default_val=None)
        else:
            df[col] = np.nan

    # Min-max normalization helper ignoring NaNs (0.0 to 1.0 scale)
    def _normalize_series(series: pd.Series) -> pd.Series:
        valid_s = series.dropna()
        if valid_s.empty:
            return pd.Series(np.nan, index=series.index)
        min_val, max_val = float(valid_s.min()), float(valid_s.max())
        if min_val == max_val:
            res = series.copy()
            res[res.notna()] = 1.0 if max_val > 0 else 0.0
            return res
        return (series - min_val) / (max_val - min_val)

    norm_ind = _normalize_series(df["industry_size"])
    norm_org = _normalize_series(df["organization_count"])
    norm_asp = _normalize_series(df["candidate_aspiration"])

    weights = {"ind": 0.40, "org": 0.25, "asp": 0.35}

    opp_scores: List[Optional[float]] = []
    tp_scores: List[Optional[float]] = []
    confidence_scores: List[float] = []

    key_evidence_cols = [
        "industry_size", "organization_count", "candidate_aspiration",
        "mssds_trained_2022_23", "dsdp_training", "projected_training"
    ]

    for i in range(len(df)):
        row = df.iloc[i]

        # 1. Industry Opportunity Score
        vals = {
            "ind": norm_ind.iloc[i],
            "org": norm_org.iloc[i],
            "asp": norm_asp.iloc[i],
        }
        available_keys = [k for k, v in vals.items() if pd.notna(v)]

        if not available_keys:
            opp_score = None
        else:
            weighted_sum = sum(vals[k] * weights[k] for k in available_keys)
            weight_sum = sum(weights[k] for k in available_keys)
            opp_score = round((weighted_sum / weight_sum) * 100.0, 2)

        opp_scores.append(opp_score)

        # 2. Training Pressure Score
        proj_val = row.get("projected_training")
        
        # Hierarchy for existing_training:
        # 1. mssds_trained_2022_23 when available
        # 2. otherwise mssds_trained when available
        # 3. otherwise null
        existing_training = None
        if pd.notna(row.get("mssds_trained_2022_23")):
            existing_training = float(row.get("mssds_trained_2022_23"))
        elif pd.notna(row.get("mssds_trained")):
            existing_training = float(row.get("mssds_trained"))

        if pd.notna(proj_val) and existing_training is not None:
            proj_float = float(proj_val)
            denominator = existing_training + proj_float
            if denominator > 0:
                tp_score = round((proj_float / denominator) * 100.0, 2)
            else:
                tp_score = None
        else:
            tp_score = None

        tp_scores.append(tp_score)

        # 3. Evidence Confidence
        present_count = sum(1 for col in key_evidence_cols if col in df.columns and pd.notna(row.get(col)))
        conf = round(present_count / float(len(key_evidence_cols)), 2)
        confidence_scores.append(conf)

    df["district"] = df["district"] if "district" in df.columns else "Unknown"
    df["sector"] = df["sector"] if "sector" in df.columns else "Unknown"
    df["normalized_district"] = df["district"].astype(str).apply(normalize_district)
    df["normalized_sector"] = df["sector"].astype(str).apply(normalize_sector)

    df["industry_opportunity_score"] = opp_scores
    df["training_pressure_score"] = tp_scores
    df["evidence_confidence"] = confidence_scores

    if "projection_available" in df.columns:
        df["projection_available"] = df["projection_available"].apply(
            lambda v: True if (pd.notna(v) and str(v).lower() in ["true", "1", "yes"]) else False
        )
    else:
        df["projection_available"] = df["projected_training"].notna()

    df["source"] = df.get("dataset_source", Path(file_path or DEFAULT_MSSDS_PATH).name)

    output_cols = [
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
        "normalized_district",
        "normalized_sector",
    ]

    for c in output_cols:
        if c not in df.columns:
            df[c] = np.nan

    return df[output_cols]
