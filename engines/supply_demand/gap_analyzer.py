"""Gap analyzer module for supply-demand normalization, gap calculation, and priority scoring."""

from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field


class SupplyDemandConfig(BaseModel):
    """Configuration schema for column mapping, weights, and thresholds."""
    # Column mapping
    district_col: Optional[str] = "district"
    sector_col: Optional[str] = "sector"
    trade_col: str = "trade"
    supply_count_col: str = "supply_count"
    demand_count_col: str = "demand_count"
    future_demand_count_col: Optional[str] = "future_demand_count"

    # Configurable weights for priority scoring (must sum to > 0)
    weight_current_demand: float = 0.3
    weight_future_demand: float = 0.2
    weight_supply_shortage: float = 0.4
    weight_demand_growth: float = 0.1

    # Gap category thresholds (based on normalized gap = demand_score - supply_score)
    high_gap_threshold: float = 30.0
    moderate_gap_threshold: float = 10.0
    oversupply_threshold: float = -10.0


class SupplyDemandResult(BaseModel):
    """Structured, explainable result of supply-demand gap analysis."""
    district: Optional[str] = None
    sector: Optional[str] = None
    trade: str
    supply_count: Optional[float] = None
    demand_count: Optional[float] = None
    supply_score: float
    current_demand_score: float
    future_demand_score: Optional[float] = None
    current_gap: float
    future_gap: Optional[float] = None
    priority_score: float
    gap_category: str  # High Gap, Moderate Gap, Balanced, Oversupply, Unknown
    confidence_score: float
    data_availability: Dict[str, Any]


class GapAnalyzer:
    """Computes normalized supply/demand scores, gaps, priority scores, and categories."""

    def __init__(self, config: Optional[SupplyDemandConfig] = None):
        self.config = config or SupplyDemandConfig()

    def normalize_series(self, series: pd.Series) -> pd.Series:
        """Normalize numeric series to 0.0 - 100.0 range using min-max scaling."""
        valid_mask = series.notnull()
        if not valid_mask.any():
            return pd.Series(index=series.index, dtype=float)

        min_val = series[valid_mask].min()
        max_val = series[valid_mask].max()

        if max_val == min_val:
            res = pd.Series(index=series.index, dtype=float)
            res[valid_mask] = 50.0
            return res

        normalized = (series - min_val) / (max_val - min_val) * 100.0
        return normalized.round(2)

    def categorize_gap(self, gap_score: float, config: Optional[SupplyDemandConfig] = None) -> str:
        """Categorize current gap score into transparent categories."""
        cfg = config or self.config
        if np.isnan(gap_score):
            return "Unknown"
        if gap_score >= cfg.high_gap_threshold:
            return "High Gap"
        elif gap_score >= cfg.moderate_gap_threshold:
            return "Moderate Gap"
        elif gap_score <= cfg.oversupply_threshold:
            return "Oversupply"
        else:
            return "Balanced"

    def compute_priority_score(
        self,
        current_demand_score: float,
        supply_score: float,
        current_gap: float,
        future_demand_score: Optional[float] = None,
        future_gap: Optional[float] = None,
        config: Optional[SupplyDemandConfig] = None,
    ) -> float:
        """Calculate weighted priority score (0.0 to 100.0) dynamically handling missing future demand."""
        cfg = config or self.config

        if np.isnan(current_demand_score) or np.isnan(supply_score):
            return 0.0

        shortage_component = max(0.0, current_gap)
        
        w_cd = cfg.weight_current_demand
        w_ss = cfg.weight_supply_shortage
        w_fd = cfg.weight_future_demand if (future_demand_score is not None and not np.isnan(future_demand_score)) else 0.0
        w_dg = cfg.weight_demand_growth if (future_gap is not None and not np.isnan(future_gap)) else 0.0

        total_weight = w_cd + w_ss + w_fd + w_dg
        if total_weight <= 0:
            return 0.0

        score_acc = (w_cd * current_demand_score) + (w_ss * shortage_component)
        if w_fd > 0 and future_demand_score is not None:
            score_acc += w_fd * future_demand_score
        if w_dg > 0 and future_gap is not None:
            growth_component = max(0.0, future_gap)
            score_acc += w_dg * growth_component

        priority = score_acc / total_weight
        return float(np.round(np.clip(priority, 0.0, 100.0), 2))
