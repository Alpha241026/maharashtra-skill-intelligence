"""Text processing utilities for skill intelligence."""

import re
from typing import List


class TextProcessor:
    """Handles text cleaning, normalization, and preprocessing for skill text."""

    def __init__(self, lowercase: bool = True, remove_special_chars: bool = False):
        self.lowercase = lowercase
        self.remove_special_chars = remove_special_chars

    def clean_text(self, text: str) -> str:
        """Clean and normalize input text string."""
        if not text:
            return ""

        cleaned = text.strip()
        if self.lowercase:
            cleaned = cleaned.lower()

        if self.remove_special_chars:
            cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def process_batch(self, texts: List[str]) -> List[str]:
        """Normalize a list of text strings."""
        return [self.clean_text(t) for t in texts]
