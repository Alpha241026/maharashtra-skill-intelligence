"""Normalizer module for standardizing district, trade, and sector identifiers."""

import re
from typing import Optional
import pandas as pd


def normalize_district(district_str: Optional[str]) -> Optional[str]:
    """Normalize district name while preserving raw input in separate columns."""
    if not district_str or not isinstance(district_str, str):
        return None

    cleaned = district_str.strip().lower()
    if not cleaned:
        return None

    # Remove dist/district variations including dots
    cleaned = re.sub(r"\bdist(rict)?\.?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")

    if not cleaned:
        return None

    # Standardize known name aliases
    alias_map = {
        "aurangabad": "chhatrapati sambhajinagar",
        "osmanabad": "dharashiv",
        "mumbai city": "mumbai",
        "mumbai suburban": "mumbai suburban",
    }

    return alias_map.get(cleaned, cleaned)


def normalize_trade_name(trade_str: Optional[str]) -> Optional[str]:
    """Normalize trade name by stripping training framework suffixes (e.g. NSQF)."""
    if not trade_str or not isinstance(trade_str, str):
        return None

    cleaned = trade_str.strip().lower()
    if not cleaned:
        return None

    # Strip NSQF level and framework indicators
    cleaned = re.sub(r"\(\s*nsqf(\s*level\s*\d+)?\s*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(\s*cts\s*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(\s*cits\s*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"-?\s*nsqf(\s*level\s*\d+)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")

    return cleaned if cleaned else None


def normalize_sector(sector_str: Optional[str]) -> Optional[str]:
    """Normalize sector identifier without forcing unverified mappings."""
    if not sector_str or not isinstance(sector_str, str):
        return None

    cleaned = sector_str.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned if cleaned else None


def safe_numeric_conversion(series: pd.Series, default_val: Optional[float] = None) -> pd.Series:
    """Safely convert series to numeric float without discarding missing value awareness."""
    numeric_series = pd.to_numeric(series, errors="coerce")
    if default_val is not None:
        return numeric_series.fillna(default_val)
    return numeric_series
