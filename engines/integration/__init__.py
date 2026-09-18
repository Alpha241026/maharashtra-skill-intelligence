"""Data integration engine package."""

from .data_loader import (
    load_iti_supply,
    load_ncs_job_listings,
    load_employment_indicators,
    load_official_trade_reference,
    load_mssds_projections,
)
from .normalizer import (
    normalize_district,
    normalize_trade_name,
    normalize_sector,
    safe_numeric_conversion,
)
from .pipeline import IntegrationPipeline
from .trade_mapper import TradeMapper, TradeMappingResult
from .mssds_intelligence import compute_mssds_district_sector_intelligence, MSSDSIntelligenceResult

__all__ = [
    "load_iti_supply",
    "load_ncs_job_listings",
    "load_employment_indicators",
    "load_official_trade_reference",
    "load_mssds_projections",
    "normalize_district",
    "normalize_trade_name",
    "normalize_sector",
    "safe_numeric_conversion",
    "IntegrationPipeline",
    "TradeMapper",
    "TradeMappingResult",
    "compute_mssds_district_sector_intelligence",
    "MSSDSIntelligenceResult",
]
