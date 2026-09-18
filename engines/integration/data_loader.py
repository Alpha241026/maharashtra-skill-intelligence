"""Data loader module for ingesting standardized datasets with provenance metadata."""

from pathlib import Path
from typing import Optional, Union
import pandas as pd
from datetime import datetime

from .normalizer import (
    normalize_district,
    normalize_trade_name,
    normalize_sector,
    safe_numeric_conversion,
)

# Default dataset locations
DEFAULT_ITI_PATH = Path("data/processed/iti/maharashtra_iti_trade_supply_2026.csv")
DEFAULT_NCS_PATH = Path("data/processed/training/ncs_maharashtra_job_listings_snapshot_2026.csv")
DEFAULT_EMP_PATH = Path("data/processed/training/employment_demand_indicators_2026.csv")
DEFAULT_REF_PATH = Path("data/processed/training/official_trade_skills_reference.csv")
DEFAULT_MSSDS_PATH = Path("data/processed/mssds/mssds_2023_projection_merged.csv")


def _add_provenance(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Add provenance tracking metadata columns."""
    df["dataset_source"] = source_name
    df["loaded_at"] = datetime.now().isoformat()
    return df


def load_iti_supply(file_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Load ITI trade supply dataset."""
    path = Path(file_path or DEFAULT_ITI_PATH)
    if not path.exists():
        raise FileNotFoundError(f"ITI dataset file not found at: {path}")

    df = pd.read_csv(path)

    # Preserve raw input fields
    df["raw_district"] = df["district"]
    df["raw_trade_name"] = df["trade_name"]

    # Normalized fields
    df["normalized_district"] = df["district"].astype(str).apply(normalize_district)
    df["normalized_trade"] = df["trade_name"].astype(str).apply(normalize_trade_name)

    # Safe numeric conversion
    df["intake"] = safe_numeric_conversion(df["intake"], default_val=0.0)

    return _add_provenance(df, path.name)


def load_ncs_job_listings(file_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Load NCS job listings snapshot dataset."""
    path = Path(file_path or DEFAULT_NCS_PATH)
    if not path.exists():
        raise FileNotFoundError(f"NCS job listings dataset file not found at: {path}")

    df = pd.read_csv(path)

    # Preserve raw input fields
    df["raw_district"] = df["district"]
    df["raw_job_title"] = df["job_title"]

    # Normalized fields
    df["normalized_district"] = df["district"].astype(str).apply(normalize_district)
    df["normalized_job_or_skill"] = df["job_title"].astype(str).apply(normalize_trade_name)

    # Safe numeric conversions
    df["salary_min_inr_year"] = safe_numeric_conversion(df["salary_min_inr_year"])
    df["salary_max_inr_year"] = safe_numeric_conversion(df["salary_max_inr_year"])

    return _add_provenance(df, path.name)


def load_employment_indicators(file_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Load employment demand indicators dataset."""
    path = Path(file_path or DEFAULT_EMP_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Employment indicators dataset file not found at: {path}")

    df = pd.read_csv(path)

    df["raw_geography"] = df["geography"]
    df["normalized_district"] = df["geography"].astype(str).apply(normalize_district)
    df["value"] = safe_numeric_conversion(df["value"])

    return _add_provenance(df, path.name)


def load_official_trade_reference(file_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Load official trade reference dataset as authoritative vocabulary."""
    path = Path(file_path or DEFAULT_REF_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Official trade reference file not found at: {path}")

    df = pd.read_csv(path)

    df["raw_trade"] = df["trade"]
    df["normalized_trade"] = df["trade"].astype(str).apply(normalize_trade_name)

    return _add_provenance(df, path.name)


def load_mssds_projections(file_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Load MSSDS projection dataset."""
    path = Path(file_path or DEFAULT_MSSDS_PATH)
    if not path.exists():
        raise FileNotFoundError(f"MSSDS projections file not found at: {path}")

    df = pd.read_csv(path)

    # Preserve raw input fields
    df["raw_district"] = df["district"]
    df["raw_sector"] = df["sector"]

    # Normalized fields
    df["normalized_district"] = df["district"].astype(str).apply(normalize_district)
    df["normalized_sector"] = df["sector"].astype(str).apply(normalize_sector)

    # Safe numeric conversions
    for col in ["mssds_trained", "dsdp_training", "projected_training", "organization_count", "dsdp"]:
        if col in df.columns:
            df[col] = safe_numeric_conversion(df[col], default_val=0.0)

    return _add_provenance(df, path.name)
