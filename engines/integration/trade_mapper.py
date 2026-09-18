"""Trade mapper module using SkillIntelligenceEngine for mapping NCS job listings to official ITI trade vocabulary."""

from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import pandas as pd
from pydantic import BaseModel

from engines.skill_intelligence import SkillIntelligenceEngine, TaxonomyItem
from .normalizer import normalize_trade_name
from .data_loader import load_official_trade_reference


class TradeMappingResult(BaseModel):
    """Structured mapping result connecting an NCS job entry to an official ITI trade."""
    original_job_title: str
    original_skills_required: Optional[str] = None
    normalized_job_title: Optional[str] = None
    matched_trade: Optional[str] = None
    match_similarity: float
    match_type: str
    mapping_confidence: float
    mapping_status: str  # 'matched', 'ambiguous', 'unmatched'


class TradeMapper:
    """Maps job listings to official ITI trade vocabulary using semantic embeddings."""

    def __init__(
        self,
        ref_file_path: Optional[Union[str, Path]] = None,
        model_name: str = "all-MiniLM-L6-v2",
        match_threshold: float = 0.50,
        ambiguity_margin: float = 0.05,
    ):
        self.match_threshold = match_threshold
        self.ambiguity_margin = ambiguity_margin
        self.engine = SkillIntelligenceEngine(model_name=model_name)
        self.official_vocab_df = load_official_trade_reference(ref_file_path)
        self._load_vocabulary()

    def _load_vocabulary(self) -> None:
        """Load official trade reference items into SkillIntelligenceEngine taxonomy."""
        items = []
        for _, row in self.official_vocab_df.iterrows():
            trade_name = str(row["trade"])
            summary = str(row["competency_summary"]) if pd.notnull(row.get("competency_summary")) else None
            items.append(
                TaxonomyItem(
                    canonical_name=trade_name,
                    description=summary,
                )
            )
        self.engine.load_taxonomy(items)

    def map_job_record(
        self,
        job_title: str,
        skills_required: Optional[str] = None,
    ) -> TradeMappingResult:
        """Map a single job record (job_title + skills_required) to official ITI trade vocabulary."""
        norm_title = normalize_trade_name(job_title)

        # Combine job title and skills for rich semantic context
        combined_text = f"{job_title} {skills_required or ''}".strip()

        matches = self.engine.match_skill(combined_text, top_k=3, threshold=0.0)

        if not matches:
            return TradeMappingResult(
                original_job_title=job_title,
                original_skills_required=skills_required,
                normalized_job_title=norm_title,
                matched_trade=None,
                match_similarity=0.0,
                match_type="unmatched",
                mapping_confidence=0.0,
                mapping_status="unmatched",
            )

        top_match = matches[0]
        top_sim = top_match.confidence

        # Exact match bypass
        if top_match.match_type in ["exact", "alias_exact"]:
            return TradeMappingResult(
                original_job_title=job_title,
                original_skills_required=skills_required,
                normalized_job_title=norm_title,
                matched_trade=top_match.canonical_name,
                match_similarity=top_sim,
                match_type=top_match.match_type,
                mapping_confidence=1.0,
                mapping_status="matched",
            )

        # Below threshold filter
        if top_sim < self.match_threshold:
            return TradeMappingResult(
                original_job_title=job_title,
                original_skills_required=skills_required,
                normalized_job_title=norm_title,
                matched_trade=None,
                match_similarity=top_sim,
                match_type="below_threshold",
                mapping_confidence=top_sim,
                mapping_status="unmatched",
            )

        # Ambiguity check between top 2 matches
        if len(matches) >= 2:
            second_sim = matches[1].confidence
            if (top_sim - second_sim) < self.ambiguity_margin:
                return TradeMappingResult(
                    original_job_title=job_title,
                    original_skills_required=skills_required,
                    normalized_job_title=norm_title,
                    matched_trade=top_match.canonical_name,
                    match_similarity=top_sim,
                    match_type="ambiguous_semantic",
                    mapping_confidence=round(top_sim * 0.7, 2),
                    mapping_status="ambiguous",
                )

        return TradeMappingResult(
            original_job_title=job_title,
            original_skills_required=skills_required,
            normalized_job_title=norm_title,
            matched_trade=top_match.canonical_name,
            match_similarity=top_sim,
            match_type=top_match.match_type,
            mapping_confidence=top_sim,
            mapping_status="matched",
        )

    def map_ncs_dataframe(self, ncs_df: pd.DataFrame) -> pd.DataFrame:
        """Map an entire NCS job listings DataFrame producing a structured mapping DataFrame."""
        results = []
        for _, row in ncs_df.iterrows():
            title = str(row["job_title"])
            skills = str(row["skills_required"]) if pd.notnull(row.get("skills_required")) else None
            res = self.map_job_record(title, skills)
            res_dict = res.model_dump()
            res_dict["district"] = row.get("district")
            results.append(res_dict)

        return pd.DataFrame(results)
