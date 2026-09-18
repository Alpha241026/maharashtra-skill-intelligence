"""SkillIntelligenceEngine orchestrating text processing and semantic matching."""

from pathlib import Path
from typing import List, Union, Dict, Any, Optional

from .text_processor import TextProcessor
from .semantic_matcher import SemanticMatcher, CandidateMatch, TaxonomyItem


class SkillIntelligenceEngine:
    """Core AI engine for matching and identifying skills/trades against a loaded taxonomy."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        text_processor: Optional[TextProcessor] = None,
    ):
        self.text_processor = text_processor or TextProcessor()
        self.matcher = SemanticMatcher(
            model_name=model_name,
            text_processor=self.text_processor,
        )

    def load_taxonomy(self, taxonomy_source: Union[List[Union[TaxonomyItem, Dict[str, Any]]], str, Path]) -> None:
        """Load taxonomy from list of dicts/objects, JSON file path, or CSV file path."""
        if isinstance(taxonomy_source, (str, Path)):
            path = Path(taxonomy_source)
            if path.suffix.lower() == ".json":
                self.matcher.load_taxonomy_from_json(path)
            elif path.suffix.lower() == ".csv":
                self.matcher.load_taxonomy_from_csv(path)
            else:
                raise ValueError(f"Unsupported file extension: {path.suffix}. Expected .json or .csv")
        elif isinstance(taxonomy_source, list):
            self.matcher.load_taxonomy(taxonomy_source)
        else:
            raise ValueError(f"Unsupported taxonomy source type: {type(taxonomy_source)}")

    def match_skill(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.0,
    ) -> List[CandidateMatch]:
        """Process input text and return structured candidate skill/trade matches."""
        cleaned_query = self.text_processor.clean_text(query)
        if not cleaned_query:
            return []

        return self.matcher.match(
            query=cleaned_query,
            top_k=top_k,
            threshold=threshold,
        )
