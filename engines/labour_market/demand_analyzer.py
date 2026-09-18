"""Demand analyzer module for calculating current demand scores and categorizations."""

from typing import Optional
import pandas as pd
from pydantic import BaseModel


class ColumnConfig(BaseModel):
    """Configuration mapping for input DataFrame columns."""
    entity_col: str = "entity_name"
    demand_count_col: str = "demand_count"
    time_col: Optional[str] = None
    future_demand_col: Optional[str] = None
    weight_col: Optional[str] = None
    group_col: Optional[str] = None


class DemandAnalyzer:
    """Calculates transparent current demand scores and categorizes demand levels."""

    def __init__(self, config: Optional[ColumnConfig] = None):
        self.config = config or ColumnConfig()

    def calculate_current_demand_score(
        self,
        df: pd.DataFrame,
        config: Optional[ColumnConfig] = None,
    ) -> pd.Series:
        """Calculate normalized demand score (0.0 - 100.0) based on demand counts."""
        cfg = config or self.config
        if cfg.demand_count_col not in df.columns:
            raise KeyError(f"Column '{cfg.demand_count_col}' not found in DataFrame.")

        counts = df[cfg.demand_count_col].fillna(0).astype(float)
        if cfg.weight_col and cfg.weight_col in df.columns:
            weights = df[cfg.weight_col].fillna(1.0).astype(float)
            counts = counts * weights

        min_val = counts.min()
        max_val = counts.max()

        if max_val == min_val:
            return pd.Series(50.0, index=df.index)

        # Min-max normalization scaled to 0.0 - 100.0
        scores = ((counts - min_val) / (max_val - min_val)) * 100.0
        return scores.round(2)

    def categorize_demand(self, score: float) -> str:
        """Categorize demand score into transparent demand levels."""
        if score >= 75.0:
            return "Very High"
        elif score >= 50.0:
            return "High"
        elif score >= 25.0:
            return "Moderate"
        else:
            return "Low"
