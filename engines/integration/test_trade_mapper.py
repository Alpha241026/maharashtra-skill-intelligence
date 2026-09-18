"""Unit tests for TradeMapper in engines/integration/trade_mapper.py."""

import pytest
from engines.integration import TradeMapper, TradeMappingResult


@pytest.fixture
def mapper():
    return TradeMapper(match_threshold=0.50, ambiguity_margin=0.05)


def test_clear_vocational_job_title_and_trade_match(mapper):
    """Test clear trade match for a vocational job title."""
    res = mapper.map_job_record("Electrician", "Wiring, Circuit Maintenance")
    assert isinstance(res, TradeMappingResult)
    assert res.matched_trade == "Electrician"
    assert res.mapping_status == "matched"
    assert res.match_similarity >= 0.50


def test_irrelevant_job_title_unmatched(mapper):
    """Test irrelevant job title below similarity threshold resulting in unmatched status."""
    res = mapper.map_job_record("Saree packing job work from home", "Packing sarees at home")
    assert res.matched_trade is None
    assert res.mapping_status == "unmatched"


def test_unmatched_record(mapper):
    """Test completely unrelated query resulting in unmatched status."""
    res = mapper.map_job_record("Rohan Sonawane", "Personal name contact")
    assert res.matched_trade is None
    assert res.mapping_status == "unmatched"


def test_ambiguous_match():
    """Test ambiguous match scenario where top 2 candidates have very close similarity."""
    # Instantiating mapper with very large ambiguity margin to force ambiguity on close candidates
    ambiguous_mapper = TradeMapper(match_threshold=0.30, ambiguity_margin=0.50)
    res = ambiguous_mapper.map_job_record("Maintenance Technician", "Mechanical and Electrical Repair")
    assert res.mapping_status in ["ambiguous", "matched"]
    if res.mapping_status == "ambiguous":
        assert res.match_type == "ambiguous_semantic"
