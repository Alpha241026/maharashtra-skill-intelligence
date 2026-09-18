"""Semantic matching module using SentenceTransformers and embedding similarity."""

import csv
import json
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import numpy as np
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from .text_processor import TextProcessor


class TaxonomyItem(BaseModel):
    """Schema for a skill or trade in the taxonomy."""
    canonical_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)


class CandidateMatch(BaseModel):
    """Structured response for a skill match candidate."""
    canonical_name: str
    confidence: float
    match_type: str  # e.g., 'exact', 'alias_exact', 'semantic'
    category: Optional[str] = None


class SemanticMatcher:
    """Semantic matcher using lightweight pretrained sentence embeddings."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        text_processor: Optional[TextProcessor] = None,
    ):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.text_processor = text_processor or TextProcessor()
        self.taxonomy: List[TaxonomyItem] = []
        self._taxonomy_embeddings: Optional[np.ndarray] = None
        self._mapping_index: List[Dict[str, Any]] = []

    def load_taxonomy(self, items: List[Union[TaxonomyItem, Dict[str, Any]]]) -> None:
        """Load taxonomy items directly from objects or dicts and build index."""
        self.taxonomy = []
        for item in items:
            if isinstance(item, dict):
                self.taxonomy.append(TaxonomyItem(**item))
            elif isinstance(item, TaxonomyItem):
                self.taxonomy.append(item)
            else:
                raise ValueError(f"Invalid taxonomy item type: {type(item)}")

        self._build_index()

    def load_taxonomy_from_json(self, file_path: Union[str, Path]) -> None:
        """Load taxonomy from a JSON file."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON taxonomy root must be a list of items.")
        self.load_taxonomy(data)

    def load_taxonomy_from_csv(self, file_path: Union[str, Path]) -> None:
        """Load taxonomy from a CSV file (expects columns: canonical_name, category, description, aliases)."""
        path = Path(file_path)
        items = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                aliases_raw = row.get("aliases", "")
                aliases = [a.strip() for a in aliases_raw.split(";") if a.strip()] if aliases_raw else []
                items.append({
                    "canonical_name": row["canonical_name"].strip(),
                    "category": row.get("category", "").strip() or None,
                    "description": row.get("description", "").strip() or None,
                    "aliases": aliases,
                })
        self.load_taxonomy(items)

    def _build_index(self) -> None:
        """Build text representations and precompute embeddings for quick retrieval."""
        self._mapping_index = []
        corpus_texts = []

        for item in self.taxonomy:
            # Entry for canonical name
            corpus_texts.append(self.text_processor.clean_text(item.canonical_name))
            self._mapping_index.append({
                "canonical_name": item.canonical_name,
                "match_type": "semantic",
                "category": item.category,
                "raw_text": item.canonical_name,
            })

            # Entry for description if available
            if item.description:
                corpus_texts.append(self.text_processor.clean_text(item.description))
                self._mapping_index.append({
                    "canonical_name": item.canonical_name,
                    "match_type": "semantic_description",
                    "category": item.category,
                    "raw_text": item.description,
                })

            # Entries for aliases
            for alias in item.aliases:
                corpus_texts.append(self.text_processor.clean_text(alias))
                self._mapping_index.append({
                    "canonical_name": item.canonical_name,
                    "match_type": "semantic_alias",
                    "category": item.category,
                    "raw_text": alias,
                })

        if corpus_texts:
            self._taxonomy_embeddings = self.model.encode(
                corpus_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        else:
            self._taxonomy_embeddings = None

    def match(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.0,
    ) -> List[CandidateMatch]:
        """Match query text against loaded taxonomy using exact and semantic search."""
        if not self.taxonomy or self._taxonomy_embeddings is None:
            return []

        cleaned_query = self.text_processor.clean_text(query)
        if not cleaned_query:
            return []

        # Step 1: Check exact or alias-exact match
        for item in self.taxonomy:
            if cleaned_query == self.text_processor.clean_text(item.canonical_name):
                return [CandidateMatch(
                    canonical_name=item.canonical_name,
                    confidence=1.0,
                    match_type="exact",
                    category=item.category,
                )]
            for alias in item.aliases:
                if cleaned_query == self.text_processor.clean_text(alias):
                    return [CandidateMatch(
                        canonical_name=item.canonical_name,
                        confidence=0.98,
                        match_type="alias_exact",
                        category=item.category,
                    )]

        # Step 2: Vector semantic similarity search
        query_embedding = self.model.encode(
            [cleaned_query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        similarities = np.dot(self._taxonomy_embeddings, query_embedding)

        # Deduplicate matches per canonical_name keeping highest score
        best_canonical_matches: Dict[str, Dict[str, Any]] = {}
        for idx, score in enumerate(similarities):
            if score < threshold:
                continue

            entry = self._mapping_index[idx]
            canonical = entry["canonical_name"]
            score_val = float(np.round(score, 4))

            if canonical not in best_canonical_matches or score_val > best_canonical_matches[canonical]["confidence"]:
                best_canonical_matches[canonical] = {
                    "canonical_name": canonical,
                    "confidence": score_val,
                    "match_type": entry["match_type"],
                    "category": entry["category"],
                }

        sorted_matches = sorted(
            best_canonical_matches.values(),
            key=lambda x: x["confidence"],
            reverse=True,
        )

        return [CandidateMatch(**m) for m in sorted_matches[:top_k]]
