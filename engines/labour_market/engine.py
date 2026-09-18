"""Labour Market Intelligence Engine orchestrating demand and trend analyses."""

from typing import List, Optional, Dict, Any
import pandas as pd
from pydantic import BaseModel

from .demand_analyzer import DemandAnalyzer, ColumnConfig
from .trend_analyzer import TrendAnalyzer


class DemandAnalysisResult(BaseModel):
    """Structured, transparent result for labour market demand analysis."""
    entity_name: str
    current_demand_score: float
    future_demand_score: Optional[float] = None
    growth_trend: Optional[float] = None  # Percentage growth
    demand_category: str  # Very High, High, Moderate, Low
    confidence_score: float  # 0.0 to 1.0
    data_availability: Dict[str, Any]


class LabourMarketEngine:
    """Core AI engine for Labour Market Intelligence."""

    def __init__(self, config: Optional[ColumnConfig] = None):
        self.config = config or ColumnConfig()
        self.demand_analyzer = DemandAnalyzer(self.config)
        self.trend_analyzer = TrendAnalyzer(self.config)

    def analyze_demand(
        self,
        df: pd.DataFrame,
        config: Optional[ColumnConfig] = None,
    ) -> List[DemandAnalysisResult]:
        """Perform demand, trend, and projection analysis on standardized DataFrame."""
        cfg = config or self.config

        if df.empty:
            return []

        if cfg.entity_col not in df.columns:
            raise KeyError(f"Entity column '{cfg.entity_col}' not present in DataFrame.")
        if cfg.demand_count_col not in df.columns:
            raise KeyError(f"Demand count column '{cfg.demand_count_col}' not present in DataFrame.")

        # Handle recent snapshot versus full time series
        if cfg.time_col and cfg.time_col in df.columns:
            latest_time = df[cfg.time_col].max()
            recent_df = df[df[cfg.time_col] == latest_time].copy()
        else:
            recent_df = df.copy()

        # Group recent snapshot by entity
        agg_cols = {cfg.demand_count_col: "sum"}
        if cfg.future_demand_col and cfg.future_demand_col in recent_df.columns:
            agg_cols[cfg.future_demand_col] = "sum"

        aggregated = recent_df.groupby(cfg.entity_col, as_index=False).agg(agg_cols)

        # Calculate current demand score
        aggregated["current_score"] = self.demand_analyzer.calculate_current_demand_score(
            aggregated, config=cfg
        )

        # Calculate future demand score if available
        future_scores = self.trend_analyzer.compute_future_demand_score(
            aggregated, config=cfg
        )
        if not future_scores.empty:
            aggregated["future_score"] = future_scores
        else:
            aggregated["future_score"] = None

        results = []
        for _, row in aggregated.iterrows():
            entity_name = str(row[cfg.entity_col])
            current_score = float(row["current_score"])
            future_score = float(row["future_score"]) if pd.notnull(row.get("future_score")) else None
            demand_category = self.demand_analyzer.categorize_demand(current_score)

            growth_trend, confidence, data_avail = self.trend_analyzer.compute_trend(
                df, entity_name, config=cfg
            )

            results.append(
                DemandAnalysisResult(
                    entity_name=entity_name,
                    current_demand_score=current_score,
                    future_demand_score=future_score,
                    growth_trend=growth_trend,
                    demand_category=demand_category,
                    confidence_score=confidence,
                    data_availability=data_avail,
                )
            )

        return results

    def aggregate_by_category(
        self,
        df: pd.DataFrame,
        group_by_col: str,
        config: Optional[ColumnConfig] = None,
    ) -> pd.DataFrame:
        """Aggregate demand metrics by sector, trade, or skill-level."""
        cfg = config or self.config
        if group_by_col not in df.columns:
            raise KeyError(f"Group column '{group_by_col}' not found in DataFrame.")

        agg_dict: Dict[str, Any] = {cfg.demand_count_col: "sum"}
        if cfg.future_demand_col and cfg.future_demand_col in df.columns:
            agg_dict[cfg.future_demand_col] = "sum"

        result = df.groupby(group_by_col, as_index=False).agg(agg_dict)
        result["demand_score"] = self.demand_analyzer.calculate_current_demand_score(
            result, config=ColumnConfig(entity_col=group_by_col, demand_count_col=cfg.demand_count_col)
        )
        return result
