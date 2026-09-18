"""Recommendation Engine generating government-focused skill intelligence recommendations."""

from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel

from engines.supply_demand import SupplyDemandResult
from engines.labour_market import DemandAnalysisResult
from .priority_rules import PriorityRulesEvaluator, RecommendationConfig, GovernmentRecommendation


class RecommendationEngine:
    """Core AI engine for producing explainable government policy recommendations."""

    def __init__(self, config: Optional[RecommendationConfig] = None):
        self.config = config or RecommendationConfig()
        self.evaluator = PriorityRulesEvaluator(self.config)

    def generate_recommendations(
        self,
        supply_demand_results: List[SupplyDemandResult],
        demand_analysis_results: Optional[List[DemandAnalysisResult]] = None,
        config: Optional[RecommendationConfig] = None,
    ) -> List[GovernmentRecommendation]:
        """
        Generate actionable recommendations from SupplyDemandResult and DemandAnalysisResult objects.

        Inputs:
            supply_demand_results: List of processed supply-demand gap results.
            demand_analysis_results: Optional list of labour market demand results (providing growth trends).
            config: Optional rule configuration override.
        """
        evaluator = PriorityRulesEvaluator(config or self.config)

        # Index growth trends from demand_analysis_results if provided
        growth_lookup: Dict[str, float] = {}
        if demand_analysis_results:
            for item in demand_analysis_results:
                if item.growth_trend is not None:
                    growth_lookup[item.entity_name] = item.growth_trend

        recommendations = []
        for sd_res in supply_demand_results:
            growth_trend = (
                sd_res.data_availability.get("growth_trend")
                or growth_lookup.get(sd_res.trade)
            )

            rec = evaluator.evaluate(
                trade=sd_res.trade,
                district=sd_res.district,
                sector=sd_res.sector,
                supply_score=sd_res.supply_score,
                current_demand_score=sd_res.current_demand_score,
                current_gap=sd_res.current_gap,
                priority_score=sd_res.priority_score,
                confidence_score=sd_res.confidence_score,
                data_availability=sd_res.data_availability,
                future_demand_score=sd_res.future_demand_score,
                future_gap=sd_res.future_gap,
                growth_trend=growth_trend,
            )
            recommendations.append(rec)

        return self.rank_recommendations(recommendations)

    def rank_recommendations(
        self, recommendations: List[GovernmentRecommendation]
    ) -> List[GovernmentRecommendation]:
        """Rank recommendations by priority level (High > Medium > Low > Insufficient Data) and priority score."""
        priority_order = {
            "High": 0,
            "Medium": 1,
            "Low": 2,
            "Insufficient Data": 3,
        }

        def sorting_key(rec: GovernmentRecommendation):
            p_rank = priority_order.get(rec.priority, 99)
            p_score = rec.supporting_metrics.get("priority_score", 0.0)
            return (p_rank, -p_score)

        return sorted(recommendations, key=sorting_key)
