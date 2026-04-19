"""
Multi-level diff engine with confidence scoring.
Performs block-level, sentence-level, and word-level diffing.
OPTIMIZED VERSION - Fast similarity filtering
"""

import logging
from typing import List, Tuple, Dict, Optional
from difflib import SequenceMatcher, unified_diff
import re

from models import (
    Paragraph, Document, ParagraphChange, SentenceChange, 
    WordLevelChange, ChangeType, DiffResult
)
from config import DiffConfig

logger = logging.getLogger(__name__)


class SentenceTokenizer:
    """Tokenize text into sentences, handling abbreviations and edge cases."""
    
    def __init__(self):
        # Build abbreviation pattern
        abbrev_pattern = '|'.join(re.escape(abbr) for abbr in DiffConfig.ABBREVIATIONS)
        self.abbrev_regex = re.compile(f'(?:{abbrev_pattern})\\.', re.IGNORECASE)
    
    def tokenize(self, text: str) -> List[str]:
        """
        Split text into sentences.
        Handles abbreviations, decimal numbers, citations.
        """
        if not text:
            return []
        
        # Replace abbreviations with placeholder to protect them
        placeholder_map = {}
        counter = 0
        
        def replace_abbrev(match):
            nonlocal counter
            placeholder = f"__ABBREV_{counter}__"
            placeholder_map[placeholder] = match.group()
            counter += 1
            return placeholder
        
        protected = self.abbrev_regex.sub(replace_abbrev, text)
        
        # Split on sentence boundaries
        # Handle: ". " "? " "! "
        sentences = re.split(r'(?<=[.!?])\s+', protected)
        
        # Restore abbreviations and clean up
        restored = []
        for sentence in sentences:
            for placeholder, abbrev in placeholder_map.items():
                sentence = sentence.replace(placeholder, abbrev)
            
            sentence = sentence.strip()
            if sentence:
                restored.append(sentence)
        
        return restored


class MultiLevelDiffEngine:
    """Perform multi-level diffing: block, sentence, word."""
    
    def __init__(self):
        self.tokenizer = SentenceTokenizer()
    
    def diff(self, doc_a: Document, doc_b: Document) -> DiffResult:
        """
        Compute diff between two documents.
        
        Returns:
            DiffResult object with all changes and metadata
        """
        logger.info(
            f"Computing diff: {len(doc_a.paragraphs)} vs "
            f"{len(doc_b.paragraphs)} paragraphs"
        )
        
        # Level 1: Block alignment
        changes = self._block_level_alignment(doc_a.paragraphs, doc_b.paragraphs)
        
        # Level 2 & 3: Sentence and word level for modified blocks
        for change in changes:
            if change.change_type == ChangeType.MODIFIED:
                self._sentence_and_word_level_diff(change)
        
        # Build result
        result = DiffResult(
            changes=changes,
            document_a_path="",
            document_b_path="",
            pages_processed_a=doc_a.total_pages,
            pages_processed_b=doc_b.total_pages
        )
        
        logger.info(f"Found {len(changes)} changes")
        return result
    
    def _quick_filter(self, text_a: str, text_b: str, min_overlap: float = 0.3) -> bool:
        """
        Quick filter: check word overlap before expensive similarity calculation.
        Returns True if worth comparing further.
        """
        if not text_a or not text_b:
            return False
        
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        
        if not words_a or not words_b:
            return False
        
        # Check word overlap
        overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
        return overlap > min_overlap
    
    def _block_level_alignment(
        self, 
        para_a: List[Paragraph], 
        para_b: List[Paragraph]
    ) -> List[ParagraphChange]:
        """
        Align paragraphs between documents using optimized similarity-based matching.
        
        Algorithm:
        1. Quick filter by word overlap (fast)
        2. Compute similarity only for promising pairs
        3. Greedy matching with early termination
        4. Output: ADDED, DELETED, MODIFIED, or UNCHANGED
        """
        changes = []
        matched_a = set()
        matched_b = set()
        
        # Compute pairwise similarities only for candidates that pass quick filter
        similarity_matrix = []
        
        logger.info(f"Filtering candidates (quick word overlap check)...")
        
        for i, para_a_item in enumerate(para_a):
            # For each paragraph in A, find top N similar paragraphs in B
            candidates = []
            
            for j, para_b_item in enumerate(para_b):
                if j in matched_b:
                    continue
                
                # Quick filter: word overlap
                if not self._quick_filter(para_a_item.text, para_b_item.text, min_overlap=0.2):
                    continue
                
                # Expensive similarity only for promising candidates
                sim = self._paragraph_similarity(para_a_item, para_b_item)
                candidates.append((sim, i, j))
            
            # Only keep top 5 candidates per paragraph A
            candidates.sort(key=lambda x: x[0], reverse=True)
            for sim, idx_a, idx_b in candidates[:5]:
                similarity_matrix.append((sim, idx_a, idx_b))
        
        # Sort all by similarity descending
        similarity_matrix.sort(key=lambda x: x[0], reverse=True)
        
        # Greedy matching
        similarity_threshold = getattr(DiffConfig, 'PARAGRAPH_SIMILARITY_THRESHOLD', 0.5)
        
        for similarity, idx_a, idx_b in similarity_matrix:
            # Skip if already matched
            if idx_a in matched_a or idx_b in matched_b:
                continue
            if similarity < similarity_threshold:
                break  # Early termination
            
            matched_a.add(idx_a)
            matched_b.add(idx_b)
            
            para_a_item = para_a[idx_a]
            para_b_item = para_b[idx_b]
            
            # Check if truly unchanged or modified
            if para_a_item.text == para_b_item.text:
                change_type = ChangeType.UNCHANGED
            else:
                change_type = ChangeType.MODIFIED
            
            change = ParagraphChange(
                change_type=change_type,
                paragraph_a=para_a_item,
                paragraph_b=para_b_item,
                similarity_score=similarity,
                block_similarity=similarity,
                text_match_percentage=similarity * 100,
                confidence=self._compute_confidence(
                    similarity, similarity, 1.0, 1.0
                ),
                page_before=para_a_item.page,
                page_after=para_b_item.page
            )
            changes.append(change)
        
        # Process unmatched paragraphs in A (deletions)
        for i, para in enumerate(para_a):
            if i not in matched_a:
                change = ParagraphChange(
                    change_type=ChangeType.DELETED,
                    paragraph_a=para,
                    paragraph_b=None,
                    similarity_score=0.0,
                    block_similarity=0.0,
                    text_match_percentage=0.0,
                    confidence=0.0,
                    page_before=para.page,
                    page_after=-1
                )
                changes.append(change)
        
        # Process unmatched paragraphs in B (additions)
        for i, para in enumerate(para_b):
            if i not in matched_b:
                change = ParagraphChange(
                    change_type=ChangeType.ADDED,
                    paragraph_a=None,
                    paragraph_b=para,
                    similarity_score=0.0,
                    block_similarity=0.0,
                    text_match_percentage=0.0,
                    confidence=0.0,
                    page_before=-1,
                    page_after=para.page
                )
                changes.append(change)
        
        return changes
    
    def _paragraph_similarity(self, para_a: Paragraph, para_b: Paragraph) -> float:
        """
        Compute similarity between two paragraphs.
        Combines text similarity and layout proximity.
        """
        # Text similarity (character-based)
        char_match = SequenceMatcher(None, para_a.text, para_b.text).ratio()
        
        # Layout proximity
        position_delta = abs(para_a.position_on_page - para_b.position_on_page)
        layout_proximity = max(0.0, 1.0 - position_delta)
        
        # Weighted combination
        similarity = (
            char_match * DiffConfig.CHAR_MATCH_WEIGHT +
            layout_proximity * DiffConfig.LAYOUT_PROXIMITY_WEIGHT
        )
        
        return min(1.0, similarity)
    
    def _sentence_and_word_level_diff(self, change: ParagraphChange):
        """
        Perform sentence and word level diff for a modified paragraph.
        """
        para_a = change.paragraph_a
        para_b = change.paragraph_b
        
        if not para_a or not para_b:
            return
        
        # Tokenize into sentences
        sents_a = self.tokenizer.tokenize(para_a.text)
        sents_b = self.tokenizer.tokenize(para_b.text)
        
        if not sents_a or not sents_b:
            return
        
        # Align sentences
        sent_matcher = SequenceMatcher(None, sents_a, sents_b, autojunk=False)
        
        # Process aligned sentences
        for block in sent_matcher.get_matching_blocks():
            if block.size == 0:
                continue
            
            for i in range(block.size):
                sent_a = sents_a[block.a + i]
                sent_b = sents_b[block.b + i]
                
                if sent_a != sent_b:
                    # Compute word-level changes
                    word_changes = self._word_level_diff(sent_a, sent_b)
                    
                    sent_change = SentenceChange(
                        before=sent_a,
                        after=sent_b,
                        word_changes=word_changes,
                        change_type=ChangeType.MODIFIED
                    )
                    change.sentence_changes.append(sent_change)
    
    def _word_level_diff(self, sent_a: str, sent_b: str) -> List[WordLevelChange]:
        """
        Perform word-level diff using Myers' algorithm (via SequenceMatcher).
        """
        words_a = sent_a.split()
        words_b = sent_b.split()
        
        changes = []
        matcher = SequenceMatcher(None, words_a, words_b)
        
        opcodes = matcher.get_opcodes()
        
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'delete':
                for i in range(i1, i2):
                    changes.append(WordLevelChange(
                        operation='delete',
                        before=words_a[i],
                        after=None,
                        position=i
                    ))
            elif tag == 'insert':
                for j in range(j1, j2):
                    changes.append(WordLevelChange(
                        operation='insert',
                        before=None,
                        after=words_b[j],
                        position=j
                    ))
            elif tag == 'replace':
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    changes.append(WordLevelChange(
                        operation='replace',
                        before=words_a[i],
                        after=words_b[j],
                        position=i
                    ))
        
        return changes
    
    def _compute_confidence(
        self,
        block_similarity: float,
        text_match_pct: float,
        layout_consistency: float,
        context_consistency: float
    ) -> float:
        """
        Compute confidence score (0-100) for a detected change.
        
        Based on:
        - Block similarity (35%)
        - Text match percentage (35%)
        - Layout consistency (20%)
        - Context consistency (10%)
        """
        confidence = (
            (block_similarity * 100) * DiffConfig.CONFIDENCE_BLOCK_SIMILARITY_WEIGHT +
            (text_match_pct) * DiffConfig.CONFIDENCE_TEXT_MATCH_WEIGHT +
            (layout_consistency * 100) * DiffConfig.CONFIDENCE_LAYOUT_CONSISTENCY_WEIGHT +
            (context_consistency * 100) * DiffConfig.CONFIDENCE_CONTEXT_CONSISTENCY_WEIGHT
        )
        
        return min(100.0, max(0.0, confidence))


def compute_diff(doc_a: Document, doc_b: Document) -> DiffResult:
    """Convenience function to compute diff between two documents."""
    engine = MultiLevelDiffEngine()
    return engine.diff(doc_a, doc_b)
