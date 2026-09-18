"""Trend analyzer module for computing growth rates, projection scores, and data availability metrics."""

from typing import Optional, Tuple, Dict, Any
import pandas as pd
from .demand_analyzer import ColumnConfig


class TrendAnalyzer:
    """Analyzes historical demand trends and future demand projections."""

    def __init__(self, config: Optional[ColumnConfig] = None):
        self.config = config or ColumnConfig()

    def compute_trend(
        self,
        df: pd.DataFrame,
        entity_name: str,
        config: Optional[ColumnConfig] = None,
    ) -> Tuple[Optional[float], float, Dict[str, Any]]:
        """
        Compute percentage growth rate, confidence score, and data availability metadata for an entity.

        Returns:
            (growth_trend_pct, confidence_score, metadata_dict)
        """
        cfg = config or self.config

        entity_df = df[df[cfg.entity_col].astype(str) == str(entity_name)]
        if entity_df.empty:
            return None, 0.0, {"has_time_series": False, "has_projections": False, "data_points": 0}

        has_time = cfg.time_col is not None and cfg.time_col in entity_df.columns
        has_projection = cfg.future_demand_col is not None and cfg.future_demand_col in entity_df.columns

        growth_trend: Optional[float] = None
        confidence = 0.5  # Base confidence level
        data_points = len(entity_df)

        if has_time and data_points >= 2:
            sorted_df = entity_df.sort_values(by=cfg.time_col)
            initial_val = float(sorted_df[cfg.demand_count_col].iloc[0])
            final_val = float(sorted_df[cfg.demand_count_col].iloc[-1])

            if initial_val > 0:
                growth_trend = round(((final_val - initial_val) / initial_val) * 100.0, 2)
            else:
                growth_trend = 100.0 if final_val > 0 else 0.0

            # Confidence increases with number of observed time points up to 1.0
            confidence = min(1.0, round(0.5 + (min(data_points, 10) * 0.05), 2))

        metadata = {
            "has_time_series": has_time,
            "has_projections": has_projection,
            "data_points": data_points,
        }

        return growth_trend, confidence, metadata

    def compute_future_demand_score(
        self,
        df: pd.DataFrame,
        config: Optional[ColumnConfig] = None,
    ) -> pd.Series:
        """Calculate future demand score (0.0 - 100.0) if projection column is present."""
        cfg = config or self.config
        if not cfg.future_demand_col or cfg.future_demand_col not in df.columns:
            return pd.Series(index=df.index, dtype=float)

        proj = df[cfg.future_demand_col].fillna(0).astype(float)
        min_val = proj.min()
        max_val = proj.max()

        if max_val == min_val:
            return pd.Series(50.0, index=df.index)

        scores = ((proj - min_val) / (max_val - min_val)) * 100.0
        return scores.round(2)
