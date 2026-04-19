"""
Text normalization module.
Reduces false positives by normalizing formatting artifacts.
"""

import logging
import re
import unicodedata
from typing import List, Set, Tuple
from models import TextBlock, Paragraph
from config import NormalizationConfig

logger = logging.getLogger(__name__)


class TextNormalizer:
    """Normalize text to reduce false positives from formatting changes."""
    
    def __init__(self):
        self.page_number_patterns = [
            re.compile(pattern) for pattern in NormalizationConfig.PAGE_NUMBER_PATTERNS
        ]
    
    def normalize_blocks(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """Normalize a list of text blocks."""
        # Filter header/footer blocks
        if NormalizationConfig.ENABLE_HEADER_FOOTER_REMOVAL:
            blocks = self._remove_headers_footers(blocks)
        
        # Normalize text content
        normalized = []
        for block in blocks:
            block.text = self._normalize_text(block.text)
            if block.text.strip():  # Only keep non-empty
                normalized.append(block)
        
        return normalized
    
    def normalize_paragraphs(self, paragraphs: List[Paragraph]) -> List[Paragraph]:
        """Normalize a list of paragraphs."""
        normalized = []
        for para in paragraphs:
            para.text = self._normalize_text(para.text)
            if para.text.strip():
                normalized.append(para)
        return normalized
    
    def _remove_headers_footers(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """Remove blocks in header and footer regions."""
        if not blocks:
            return blocks
        
        # Get page boundaries
        pages = {}
        for block in blocks:
            if block.page not in pages:
                pages[block.page] = {'min_y': float('inf'), 'max_y': float('-inf')}
            pages[block.page]['min_y'] = min(pages[block.page]['min_y'], block.y)
            pages[block.page]['max_y'] = max(pages[block.page]['max_y'], block.y + block.height)
        
        # Filter blocks
        filtered = []
        for block in blocks:
            page_info = pages[block.page]
            page_height = page_info['max_y'] - page_info['min_y']
            
            # Check if in header (top 5%)
            is_header = (block.y - page_info['min_y']) < (page_height * NormalizationConfig.HEADER_FOOTER_PERCENTAGE / 100)
            
            # Check if in footer (bottom 5%)
            is_footer = (page_info['max_y'] - (block.y + block.height)) < (page_height * NormalizationConfig.HEADER_FOOTER_PERCENTAGE / 100)
            
            if not (is_header or is_footer):
                filtered.append(block)
        
        logger.debug(f"Removed {len(blocks) - len(filtered)} header/footer blocks")
        return filtered
    
    def _normalize_text(self, text: str) -> str:
        """Normalize a single text string."""
        if not text:
            return text
        
        # Unicode normalization
        if NormalizationConfig.UNICODE_NORMALIZATION_FORM:
            text = unicodedata.normalize(
                NormalizationConfig.UNICODE_NORMALIZATION_FORM,
                text
            )
        
        # Expand ligatures
        if NormalizationConfig.EXPAND_LIGATURES:
            for ligature, expansion in NormalizationConfig.LIGATURES.items():
                text = text.replace(ligature, expansion)
        
        # Remove page numbers
        if NormalizationConfig.REMOVE_PAGE_NUMBERS:
            text = self._remove_page_numbers(text)
        
        # Whitespace normalization
        if NormalizationConfig.NORMALIZE_WHITESPACE:
            # Collapse multiple spaces
            text = re.sub(r' +', ' ', text)
            # Strip leading/trailing
            text = text.strip()
        
        if NormalizationConfig.NORMALIZE_NEWLINES:
            # Replace various newline styles
            text = text.replace('\r\n', '\n')
            text = text.replace('\r', '\n')
            # Collapse multiple newlines
            text = re.sub(r'\n+', '\n', text)
        
        return text
    
    def _remove_page_numbers(self, text: str) -> str:
        """Remove common page number patterns."""
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            is_page_number = False
            stripped = line.strip()
            
            for pattern in self.page_number_patterns:
                if pattern.match(stripped):
                    is_page_number = True
                    break
            
            if not is_page_number:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)


class FormattingAwareSimilarity:
    """
    Compute similarity ignoring formatting-only changes.
    """
    
    @staticmethod
    def similarity_ignoring_formatting(text_a: str, text_b: str) -> float:
        """
        Compute similarity between two texts, ignoring formatting.
        Returns 0-1 score.
        """
        if not text_a or not text_b:
            return 1.0 if text_a == text_b else 0.0
        
        # Normalize both texts
        normalizer = TextNormalizer()
        norm_a = normalizer._normalize_text(text_a)
        norm_b = normalizer._normalize_text(text_b)
        
        # Use simple character-based similarity
        from difflib import SequenceMatcher
        return SequenceMatcher(None, norm_a, norm_b).ratio()
    
    @staticmethod
    def is_formatting_only_change(text_a: str, text_b: str, threshold: float = 0.95) -> bool:
        """
        Determine if change is formatting-only.
        Returns True if similarity > threshold.
        """
        similarity = FormattingAwareSimilarity.similarity_ignoring_formatting(text_a, text_b)
        return similarity > threshold


def normalize_pdf_content(blocks: List[TextBlock]) -> List[TextBlock]:
    """Convenience function to normalize PDF text blocks."""
    normalizer = TextNormalizer()
    return normalizer.normalize_blocks(blocks)
