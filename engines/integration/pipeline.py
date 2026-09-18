"""Integration pipeline for producing normalized aggregation tables from loaded datasets."""

from typing import Dict, Any, Optional
import pandas as pd

from .data_loader import (
    load_iti_supply,
    load_ncs_job_listings,
    load_employment_indicators,
    load_official_trade_reference,
    load_mssds_projections,
)
from .normalizer import safe_numeric_conversion
from .trade_mapper import TradeMapper
from .mssds_intelligence import compute_mssds_district_sector_intelligence


class IntegrationPipeline:
    """Orchestrates dataset loading, normalization, and creation of aggregated supply/demand tables."""

    def __init__(self, trade_mapper: Optional[TradeMapper] = None):
        self.trade_reference: Optional[pd.DataFrame] = None
        self.trade_mapper: Optional[TradeMapper] = trade_mapper

    def load_trade_vocabulary(self, ref_file_path: Optional[str] = None) -> pd.DataFrame:
        """Load official trade reference as authoritative vocabulary."""
        self.trade_reference = load_official_trade_reference(ref_file_path)
        return self.trade_reference

    def create_normalized_iti_supply(self, iti_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Create normalized ITI supply table aggregated by:
        district + normalized_trade with total_intake and number_of_ITIs.
        """
        df = (iti_df if iti_df is not None else load_iti_supply()).copy()
        if df.empty:
            return pd.DataFrame(columns=["normalized_district", "normalized_trade", "total_intake", "number_of_ITIs", "dataset_source"])

        if "intake" in df.columns:
            df["intake"] = safe_numeric_conversion(df["intake"], default_val=0.0)
        else:
            df["intake"] = 0.0

        if "iti_name" not in df.columns:
            df["iti_name"] = "Unknown ITI"

        grouped = df.groupby(["normalized_district", "normalized_trade"], as_index=False, dropna=False).agg(
            total_intake=("intake", "sum"),
            number_of_ITIs=("iti_name", "nunique"),
            raw_districts=("raw_district", lambda x: list(set(x.dropna())) if hasattr(x, 'dropna') else []),
            raw_trade_names=("raw_trade_name", lambda x: list(set(x.dropna())) if hasattr(x, 'dropna') else []),
            dataset_source=("dataset_source", "first"),
        )
        return grouped

    def create_normalized_ncs_demand(
        self,
        ncs_df: Optional[pd.DataFrame] = None,
        only_matched: bool = True,
        trade_mapper: Optional[TradeMapper] = None,
    ) -> pd.DataFrame:
        """
        Create normalized NCS demand table aggregated by:
        district + normalized_trade with listing_count.
        If only_matched is True, only includes records where mapping_status == 'matched'.
        """
        df = (ncs_df if ncs_df is not None else load_ncs_job_listings()).copy()
        if df.empty:
            return pd.DataFrame(columns=["normalized_district", "normalized_trade", "listing_count", "dataset_source"])

        mapper = trade_mapper or self.trade_mapper
        if "mapping_status" not in df.columns and mapper is not None:
            mapped_df = mapper.map_ncs_dataframe(df)
            if "normalized_district" in df.columns:
                mapped_df["normalized_district"] = df["normalized_district"].values
            df = mapped_df

        if "mapping_status" in df.columns and only_matched:
            df = df[df["mapping_status"] == "matched"].copy()

        if df.empty:
            return pd.DataFrame(columns=["normalized_district", "normalized_trade", "listing_count", "dataset_source"])

        if "matched_trade" in df.columns and pd.notnull(df["matched_trade"]).any():
            df["normalized_trade"] = df["matched_trade"].astype(str).str.lower()
        elif "normalized_job_or_skill" in df.columns:
            df["normalized_trade"] = df["normalized_job_or_skill"]
        elif "normalized_trade" not in df.columns:
            df["normalized_trade"] = "unknown"

        if "job_title" not in df.columns:
            df["job_title"] = df.get("original_job_title", "Listing")

        agg_kwargs = {
            "listing_count": ("job_title", "count"),
        }
        if "raw_district" in df.columns:
            agg_kwargs["raw_districts"] = ("raw_district", lambda x: list(set(x.dropna())) if hasattr(x, 'dropna') else [])
        if "raw_job_title" in df.columns:
            agg_kwargs["raw_job_titles"] = ("raw_job_title", lambda x: list(set(x.dropna())) if hasattr(x, 'dropna') else [])
        if "dataset_source" in df.columns:
            agg_kwargs["dataset_source"] = ("dataset_source", "first")

        grouped = df.groupby(["normalized_district", "normalized_trade"], as_index=False, dropna=False).agg(**agg_kwargs)
        grouped["normalized_job_or_skill"] = grouped["normalized_trade"]
        return grouped

    def create_normalized_mssds_table(self, mssds_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Create normalized MSSDS table aggregated by:
        district + sector with current training and projected training fields.
        """
        df = (mssds_df if mssds_df is not None else load_mssds_projections()).copy()
        if df.empty:
            return pd.DataFrame(columns=["normalized_district", "normalized_sector", "current_training", "projected_training", "dataset_source"])

        current_col = "mssds_trained" if "mssds_trained" in df.columns else ("dsdp_training" if "dsdp_training" in df.columns else None)
        if current_col:
            df[current_col] = safe_numeric_conversion(df[current_col], default_val=0.0)
        else:
            current_col = "current_training"
            df[current_col] = 0.0

        if "projected_training" in df.columns:
            df["projected_training"] = safe_numeric_conversion(df["projected_training"], default_val=0.0)
        else:
            df["projected_training"] = 0.0

        if "organization_count" in df.columns:
            df["organization_count"] = safe_numeric_conversion(df["organization_count"], default_val=0.0)
        else:
            df["organization_count"] = 0.0

        grouped = df.groupby(["normalized_district", "normalized_sector"], as_index=False, dropna=False).agg(
            current_training=(current_col, "sum"),
            projected_training=("projected_training", "sum"),
            organization_count=("organization_count", "sum"),
            raw_districts=("raw_district", lambda x: list(set(x.dropna())) if hasattr(x, 'dropna') else []),
            raw_sectors=("raw_sector", lambda x: list(set(x.dropna())) if hasattr(x, 'dropna') else []),
            dataset_source=("dataset_source", "first"),
        )
        return grouped

    def create_mssds_district_sector_intelligence(self, mssds_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Create structured MSSDS district-sector intelligence layer."""
        return compute_mssds_district_sector_intelligence(mssds_df=mssds_df)

    def run_pipeline(self, trade_mapper: Optional[TradeMapper] = None) -> Dict[str, pd.DataFrame]:
        """Execute full pipeline returning normalized aggregation tables."""
        vocab = self.load_trade_vocabulary()
        iti_table = self.create_normalized_iti_supply()

        mapper = trade_mapper or self.trade_mapper or TradeMapper()
        raw_ncs = load_ncs_job_listings()
        ncs_mapping_full = mapper.map_ncs_dataframe(raw_ncs)

        if not ncs_mapping_full.empty and not raw_ncs.empty:
            ncs_mapping_full["normalized_district"] = raw_ncs["normalized_district"].values
            ncs_mapping_full["raw_district"] = raw_ncs["raw_district"].values
            ncs_mapping_full["raw_job_title"] = raw_ncs["raw_job_title"].values
            ncs_mapping_full["dataset_source"] = raw_ncs["dataset_source"].values

        matched_ncs = ncs_mapping_full[ncs_mapping_full["mapping_status"] == "matched"].copy()
        if not matched_ncs.empty:
            ncs_table = self.create_normalized_ncs_demand(matched_ncs, only_matched=True)
        else:
            ncs_table = pd.DataFrame(columns=["normalized_district", "normalized_trade", "listing_count", "dataset_source"])

        mssds_table = self.create_normalized_mssds_table()
        mssds_intel = self.create_mssds_district_sector_intelligence()

        return {
            "trade_vocabulary": vocab,
            "iti_supply": iti_table,
            "ncs_demand": ncs_table,
            "ncs_mapping_full": ncs_mapping_full,
            "mssds_summary": mssds_table,
            "mssds_intelligence": mssds_intel,
        }

