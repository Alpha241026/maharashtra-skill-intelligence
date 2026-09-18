"""Script executing the complete AI/ML intelligence pipeline on real Maharashtra datasets."""

import json
import sys
from pathlib import Path

# Ensure project root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from engines.integration import (
    IntegrationPipeline,
    load_iti_supply,
    load_ncs_job_listings,
    load_employment_indicators,
    load_mssds_projections,
    load_official_trade_reference,
)
from engines.skill_intelligence import SkillIntelligenceEngine, TaxonomyItem
from engines.labour_market import LabourMarketEngine, ColumnConfig
from engines.supply_demand import SupplyDemandEngine, SupplyDemandConfig
from engines.recommendations import RecommendationEngine, GovernmentRecommendation


def main():
    output_dir = PROJECT_ROOT / "data" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] Loading real processed datasets through engines.integration...")
    pipeline = IntegrationPipeline()
    integrated = pipeline.run_pipeline()

    raw_iti = load_iti_supply()
    raw_ncs = load_ncs_job_listings()
    raw_emp = load_employment_indicators()
    raw_ref = load_official_trade_reference()
    raw_mssds = load_mssds_projections()

    source_records_count = (
        len(raw_iti) + len(raw_ncs) + len(raw_emp) + len(raw_ref) + len(raw_mssds)
    )

    vocab_df = integrated["trade_vocabulary"]
    iti_df = integrated["iti_supply"]
    ncs_df = integrated["ncs_demand"]
    ncs_mapping_full = integrated["ncs_mapping_full"]
    mssds_df = integrated["mssds_summary"]

    print("[2/5] Exporting Skill/Trade Intelligence Engine mapping results...")
    skill_intelligence_df = ncs_mapping_full.copy()
    skill_intelligence_df.to_csv(output_dir / "skill_intelligence_results.csv", index=False)

    print("[3/5] Running Labour Market Intelligence Engine...")
    labour_config = ColumnConfig(
        entity_col="normalized_trade",
        demand_count_col="listing_count",
    )
    labour_engine = LabourMarketEngine(config=labour_config)
    labour_analysis = labour_engine.analyze_demand(ncs_df) if not ncs_df.empty else []

    labour_results = []
    for res in labour_analysis:
        labour_results.append({
            "entity_name": res.entity_name,
            "demand_signal_type": "NCS Job Listings Snapshot",
            "current_demand_score": res.current_demand_score,
            "future_demand_score": res.future_demand_score,
            "growth_trend": res.growth_trend,
            "demand_category": res.demand_category,
            "confidence_score": res.confidence_score,
            "data_availability": str(res.data_availability),
        })
    labour_market_df = pd.DataFrame(labour_results)
    labour_market_df.to_csv(output_dir / "labour_market_results.csv", index=False)

    print("[4/5] Running Supply-Demand Intelligence Engine...")
    supply_input = iti_df.copy()
    # ncs_df contains ONLY matched NCS records (or is empty if none matched)
    ncs_mapped = ncs_df.copy()

    sd_config = SupplyDemandConfig(
        district_col="normalized_district",
        sector_col=None,
        trade_col="normalized_trade",
        supply_count_col="total_intake",
        demand_count_col="listing_count",
        future_demand_count_col=None,
    )
    sd_engine = SupplyDemandEngine(config=sd_config)
    sd_results = sd_engine.analyze(supply_input, ncs_mapped)

    sd_rows = []
    gap_category_counts = {"High Gap": 0, "Moderate Gap": 0, "Balanced": 0, "Oversupply": 0, "Unknown": 0}
    for res in sd_results:
        sd_rows.append(res.model_dump())
        cat = res.gap_category
        gap_category_counts[cat] = gap_category_counts.get(cat, 0) + 1

    supply_demand_df = pd.DataFrame(sd_rows)
    supply_demand_df.to_csv(output_dir / "supply_demand_results.csv", index=False)

    print("[5/5] Running Government Recommendation Engine...")
    rec_engine = RecommendationEngine()
    recommendations = rec_engine.generate_recommendations(sd_results, labour_analysis)

    rec_rows = []
    insufficient_data_count = 0
    for rec in recommendations:
        rec_rows.append(rec.model_dump())
        if rec.priority == "Insufficient Data":
            insufficient_data_count += 1

    recommendations_df = pd.DataFrame(rec_rows)
    recommendations_df.to_csv(output_dir / "government_recommendations.csv", index=False)

    # Compute summary statistics
    ncs_matched_count = len(ncs_mapping_full[ncs_mapping_full["mapping_status"] == "matched"]) if "mapping_status" in ncs_mapping_full.columns else 0
    ncs_ambiguous_count = len(ncs_mapping_full[ncs_mapping_full["mapping_status"] == "ambiguous"]) if "mapping_status" in ncs_mapping_full.columns else 0
    ncs_unmatched_count = len(ncs_mapping_full[ncs_mapping_full["mapping_status"] == "unmatched"]) if "mapping_status" in ncs_mapping_full.columns else 0

    districts = set(iti_df["normalized_district"].dropna())
    if not ncs_df.empty and "normalized_district" in ncs_df.columns:
        districts = districts.union(set(ncs_df["normalized_district"].dropna()))

    trades = set(iti_df["normalized_trade"].dropna())
    if not ncs_df.empty and "normalized_trade" in ncs_df.columns:
        trades = trades.union(set(ncs_df["normalized_trade"].dropna()))

    sectors = set(mssds_df["normalized_sector"].dropna())

    mssds_intel = integrated["mssds_intelligence"]
    mssds_intel.to_csv(output_dir / "mssds_district_sector_intelligence.csv", index=False)

    summary = {
        "number_of_source_records_processed": source_records_count,
        "number_of_normalized_trades": len(trades),
        "number_of_districts": len(districts),
        "number_of_sectors": len(sectors),
        "number_of_demand_signals": len(ncs_mapping_full),
        "number_of_matched_ncs_demand_signals": ncs_matched_count,
        "number_of_ambiguous_ncs_demand_signals": ncs_ambiguous_count,
        "number_of_unmatched_ncs_demand_signals": ncs_unmatched_count,
        "number_of_mssds_intelligence_records": len(mssds_intel),
        "number_of_supply_records": len(iti_df),
        "number_of_supply_demand_comparisons": len(sd_results),
        "number_of_high_gap_cases": gap_category_counts.get("High Gap", 0),
        "number_of_moderate_gap_cases": gap_category_counts.get("Moderate Gap", 0),
        "number_of_balanced_cases": gap_category_counts.get("Balanced", 0),
        "number_of_oversupply_cases": gap_category_counts.get("Oversupply", 0),
        "number_of_government_recommendations": len(recommendations),
        "unmatched_insufficient_data_counts": insufficient_data_count,
        "supply_demand_status": "insufficient_trade_level_demand_data",
        "demand_data_source_note": "NCS Job Listings Snapshot is treated strictly as a supporting demand signal/snapshot, not total labour-market demand.",
    }

    with open(output_dir / "pipeline_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Pipeline execution completed successfully!")
    print(f"Summary generated at: {output_dir / 'pipeline_summary.json'}")



if __name__ == "__main__":
    main()
