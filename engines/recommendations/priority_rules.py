"""Priority rules evaluator for generating government-focused skill recommendations."""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class RecommendationConfig(BaseModel):
    """Configuration for recommendation rules and decision thresholds."""
    high_gap_threshold: float = 30.0
    moderate_gap_threshold: float = 10.0
    oversupply_threshold: float = -10.0
    high_growth_threshold: float = 20.0
    min_confidence_threshold: float = 0.5


class GovernmentRecommendation(BaseModel):
    """Structured, explainable recommendation for government policy action."""
    district: Optional[str] = None
    sector: Optional[str] = None
    trade: str
    priority: str  # 'High', 'Medium', 'Low', 'Insufficient Data'
    recommendation_type: str  # Capacity Expansion, Emerging Skill Pipeline, Capacity Realignment, Maintain Capacity, Resource Reallocation, Data Ingestion Required
    recommendation: str  # Actionable advice
    reason: str  # Transparent justification
    supporting_metrics: Dict[str, Any]
    confidence_score: float
    data_availability: Dict[str, Any]


class PriorityRulesEvaluator:
    """Rule engine applying deterministic government policy heuristics."""

    def __init__(self, config: Optional[RecommendationConfig] = None):
        self.config = config or RecommendationConfig()

    def evaluate(
        self,
        trade: str,
        district: Optional[str],
        sector: Optional[str],
        supply_score: float,
        current_demand_score: float,
        current_gap: float,
        priority_score: float,
        confidence_score: float,
        data_availability: Dict[str, Any],
        future_demand_score: Optional[float] = None,
        future_gap: Optional[float] = None,
        growth_trend: Optional[float] = None,
    ) -> GovernmentRecommendation:
        """Apply deterministic decision rules to generate structured recommendations."""
        cfg = self.config
        loc_str = f"in {district}" if district else "statewide"

        supporting_metrics = {
            "supply_score": supply_score,
            "current_demand_score": current_demand_score,
            "current_gap": current_gap,
            "priority_score": priority_score,
            "future_demand_score": future_demand_score,
            "future_gap": future_gap,
            "growth_trend": growth_trend,
        }

        # Rule 1: Insufficient Data Filter
        if confidence_score < cfg.min_confidence_threshold:
            return GovernmentRecommendation(
                district=district,
                sector=sector,
                trade=trade,
                priority="Insufficient Data",
                recommendation_type="Data Ingestion Required",
                recommendation=f"Collect further supply and demand data for {trade} {loc_str} before allocating government training resources.",
                reason=f"Confidence rating ({confidence_score}) is below the required operational threshold ({cfg.min_confidence_threshold}).",
                supporting_metrics=supporting_metrics,
                confidence_score=confidence_score,
                data_availability=data_availability,
            )

        # Rule 2: Severe Current Supply Gap (Capacity Expansion)
        if current_gap >= cfg.high_gap_threshold:
            return GovernmentRecommendation(
                district=district,
                sector=sector,
                trade=trade,
                priority="High",
                recommendation_type="Capacity Expansion",
                recommendation=f"Urgent ITI capacity expansion recommended for {trade} {loc_str}. Increase batch sizes and instructor allocations.",
                reason=f"Severe current supply shortage detected (Current Gap: {current_gap}, Demand Score: {current_demand_score}, Supply Score: {supply_score}).",
                supporting_metrics=supporting_metrics,
                confidence_score=confidence_score,
                data_availability=data_availability,
            )

        # Rule 3: Emerging Future Demand Gap (Future Opportunity / Pipeline)
        is_high_future_gap = future_gap is not None and future_gap >= cfg.high_gap_threshold
        is_high_growth = growth_trend is not None and growth_trend >= cfg.high_growth_threshold

        if current_gap < cfg.high_gap_threshold and (is_high_future_gap or is_high_growth):
            priority = "High" if (is_high_growth and growth_trend >= 30.0) or is_high_future_gap else "Medium"
            growth_str = f"{growth_trend}% growth" if growth_trend is not None else "high future demand projection"
            return GovernmentRecommendation(
                district=district,
                sector=sector,
                trade=trade,
                priority=priority,
                recommendation_type="Emerging Skill Pipeline",
                recommendation=f"Proactively introduce specialized vocational modules and updated curriculum for {trade} {loc_str}.",
                reason=f"Significant future demand opportunity identified ({growth_str}, Future Gap: {future_gap}).",
                supporting_metrics=supporting_metrics,
                confidence_score=confidence_score,
                data_availability=data_availability,
            )

        # Rule 4: Moderate Current Gap (Capacity Realignment)
        if current_gap >= cfg.moderate_gap_threshold:
            return GovernmentRecommendation(
                district=district,
                sector=sector,
                trade=trade,
                priority="Medium",
                recommendation_type="Capacity Realignment",
                recommendation=f"Gradual seat capacity enhancement and short-term upskilling programs suggested for {trade} {loc_str}.",
                reason=f"Moderate demand surplus over current training supply (Current Gap: {current_gap}).",
                supporting_metrics=supporting_metrics,
                confidence_score=confidence_score,
                data_availability=data_availability,
            )

        # Rule 5: Oversupply (Resource Reallocation)
        if current_gap <= cfg.oversupply_threshold:
            return GovernmentRecommendation(
                district=district,
                sector=sector,
                trade=trade,
                priority="Low",
                recommendation_type="Resource Reallocation",
                recommendation=f"Maintain intake and consider reallocating training seats from {trade} {loc_str} to higher shortage trades.",
                reason=f"Local training supply exceeds current market demand (Current Gap: {current_gap}, Supply Score: {supply_score}).",
                supporting_metrics=supporting_metrics,
                confidence_score=confidence_score,
                data_availability=data_availability,
            )

        # Rule 6: Balanced Case
        return GovernmentRecommendation(
            district=district,
            sector=sector,
            trade=trade,
            priority="Low",
            recommendation_type="Maintain Capacity",
            recommendation=f"Maintain existing ITI intake capacity and ongoing training standards for {trade} {loc_str}.",
            reason=f"Current supply and demand levels are well balanced (Current Gap: {current_gap}).",
            supporting_metrics=supporting_metrics,
            confidence_score=confidence_score,
            data_availability=data_availability,
        )
