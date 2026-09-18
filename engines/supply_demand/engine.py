"""SupplyDemandEngine orchestrating supply-demand gap analysis and priority scoring."""

from typing import List, Optional, Union, Dict, Any
import pandas as pd
import numpy as np

from .gap_analyzer import GapAnalyzer, SupplyDemandConfig, SupplyDemandResult


class SupplyDemandEngine:
    """Core AI engine for comparing standardized supply and demand data."""

    def __init__(self, config: Optional[SupplyDemandConfig] = None):
        self.config = config or SupplyDemandConfig()
        self.analyzer = GapAnalyzer(self.config)

    def analyze(
        self,
        supply_df: pd.DataFrame,
        demand_df: pd.DataFrame,
        config: Optional[SupplyDemandConfig] = None,
    ) -> List[SupplyDemandResult]:
        """
        Analyze supply and demand DataFrames to calculate gaps, priority scores, and categories.

        Inputs:
            supply_df: Standardized supply dataset.
            demand_df: Standardized demand dataset.
            config: Optional custom configuration override.
        """
        cfg = config or self.config

        if supply_df.empty and demand_df.empty:
            return []

        # Determine merge keys dynamically based on column availability
        possible_keys = [cfg.district_col, cfg.sector_col, cfg.trade_col]
        join_keys = [
            k for k in possible_keys
            if k and k in supply_df.columns and k in demand_df.columns
        ]

        if not join_keys:
            # Fallback to trade_col if present in both
            if cfg.trade_col in supply_df.columns and cfg.trade_col in demand_df.columns:
                join_keys = [cfg.trade_col]
            else:
                raise KeyError(
                    f"No matching join columns found. Minimum required join column: '{cfg.trade_col}'"
                )

        # Merge datasets using outer join to preserve distinct supply/demand entities without inventing data
        merged = pd.merge(
            supply_df,
            demand_df,
            on=join_keys,
            how="outer",
            suffixes=("_supply", "_demand"),
        )

        if merged.empty:
            return []

        # Resolve column names after merge if overlap occurs
        supply_col = cfg.supply_count_col
        if supply_col not in merged.columns and f"{supply_col}_supply" in merged.columns:
            supply_col = f"{supply_col}_supply"

        demand_col = cfg.demand_count_col
        if demand_col not in merged.columns and f"{demand_col}_demand" in merged.columns:
            demand_col = f"{demand_col}_demand"

        future_col = cfg.future_demand_count_col
        if future_col and future_col not in merged.columns and f"{future_col}_demand" in merged.columns:
            future_col = f"{future_col}_demand"

        # Calculate normalized scores (fill NA with 0 only for normalization calculation)
        supply_counts = merged[supply_col] if supply_col in merged.columns else pd.Series(index=merged.index, dtype=float)
        demand_counts = merged[demand_col] if demand_col in merged.columns else pd.Series(index=merged.index, dtype=float)
        future_counts = (
            merged[future_col]
            if future_col and future_col in merged.columns
            else pd.Series(index=merged.index, dtype=float)
        )

        supply_scores = self.analyzer.normalize_series(supply_counts.fillna(0))
        current_demand_scores = self.analyzer.normalize_series(demand_counts.fillna(0))
        future_demand_scores = (
            self.analyzer.normalize_series(future_counts.fillna(0))
            if future_counts.notnull().any()
            else pd.Series(index=merged.index, dtype=float)
        )

        results = []
        for idx, row in merged.iterrows():
            # Key location identifiers
            district = str(row[cfg.district_col]) if cfg.district_col and cfg.district_col in row and pd.notnull(row[cfg.district_col]) else None
            sector = str(row[cfg.sector_col]) if cfg.sector_col and cfg.sector_col in row and pd.notnull(row[cfg.sector_col]) else None
            trade = str(row[cfg.trade_col]) if cfg.trade_col in row and pd.notnull(row[cfg.trade_col]) else "Unknown"

            # Raw values (preserve None/NaN if missing in input)
            raw_supply = float(supply_counts.iloc[idx]) if pd.notnull(supply_counts.iloc[idx]) else None
            raw_demand = float(demand_counts.iloc[idx]) if pd.notnull(demand_counts.iloc[idx]) else None

            # Normalized scores
            sup_score = float(supply_scores.iloc[idx]) if pd.notnull(supply_scores.iloc[idx]) else 0.0
            dem_score = float(current_demand_scores.iloc[idx]) if pd.notnull(current_demand_scores.iloc[idx]) else 0.0

            fut_score: Optional[float] = None
            if not future_demand_scores.empty and pd.notnull(future_demand_scores.iloc[idx]):
                fut_score = float(future_demand_scores.iloc[idx])

            # Current and Future Gap computation
            current_gap = float(np.round(dem_score - sup_score, 2))
            future_gap: Optional[float] = None
            if fut_score is not None:
                future_gap = float(np.round(fut_score - sup_score, 2))

            # Priority scoring
            priority_score = self.analyzer.compute_priority_score(
                current_demand_score=dem_score,
                supply_score=sup_score,
                current_gap=current_gap,
                future_demand_score=fut_score,
                future_gap=future_gap,
                config=cfg,
            )

            # Categorization
            gap_category = self.analyzer.categorize_gap(current_gap, config=cfg)

            # Confidence & data availability calculation
            has_supply = raw_supply is not None
            has_demand = raw_demand is not None
            has_future = (
                future_col in row
                and pd.notnull(row[future_col])
                if future_col
                else False
            )

            if has_supply and has_demand and has_future:
                confidence = 1.0
            elif has_supply and has_demand:
                confidence = 0.8
            elif has_supply or has_demand:
                confidence = 0.4
            else:
                confidence = 0.0

            data_avail = {
                "has_supply": has_supply,
                "has_current_demand": has_demand,
                "has_future_demand": has_future,
            }

            results.append(
                SupplyDemandResult(
                    district=district,
                    sector=sector,
                    trade=trade,
                    supply_count=raw_supply,
                    demand_count=raw_demand,
                    supply_score=sup_score,
                    current_demand_score=dem_score,
                    future_demand_score=fut_score,
                    current_gap=current_gap,
                    future_gap=future_gap,
                    priority_score=priority_score,
                    gap_category=gap_category,
                    confidence_score=confidence,
                    data_availability=data_avail,
                )
            )

        return results
