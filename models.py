"""
Data models for the PDF Diff pipeline.
Defines core structures used throughout the system.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class ChangeType(Enum):
    """Types of changes detected between documents."""
    ADDED = "ADDED"
    DELETED = "DELETED"
    MODIFIED = "MODIFIED"
    MOVED = "MOVED"
    UNCHANGED = "UNCHANGED"


@dataclass
class TextBlock:
    """Represents a single text block extracted from a PDF."""
    text: str
    x: float
    y: float
    width: float
    height: float
    font: str
    size: float
    bold: bool
    italic: bool
    color: int  # RGB encoded as integer
    page: int
    flags: int
    confidence: float = 1.0  # For OCR text
    
    def __hash__(self):
        return hash((self.text, self.page, round(self.x), round(self.y)))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['confidence'] = round(d['confidence'], 2)
        return d


@dataclass
class Paragraph:
    """Represents a logical paragraph reconstructed from text blocks."""
    text: str
    blocks: List[TextBlock]
    is_heading: bool = False
    heading_level: int = 0  # 1-6 for H1-H6 equivalent
    page: int = 0
    position_on_page: float = 0.0  # Relative position (0-1) on page
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'is_heading': self.is_heading,
            'heading_level': self.heading_level,
            'page': self.page,
            'position_on_page': round(self.position_on_page, 3),
            'block_count': len(self.blocks)
        }


@dataclass
class Document:
    """Represents a complete PDF document structure."""
    paragraphs: List[Paragraph]
    total_pages: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_pages': self.total_pages,
            'total_paragraphs': len(self.paragraphs),
            'metadata': self.metadata
        }


@dataclass
class WordLevelChange:
    """Represents a change at word level."""
    operation: str  # "insert", "delete", "replace"
    before: Optional[str]
    after: Optional[str]
    position: int  # Word position in sentence


@dataclass
class SentenceChange:
    """Represents changes within a sentence."""
    before: str
    after: str
    word_changes: List[WordLevelChange]
    change_type: ChangeType


@dataclass
class ParagraphChange:
    """Represents changes between two paragraphs."""
    change_type: ChangeType
    paragraph_a: Optional[Paragraph]  # None if ADDED
    paragraph_b: Optional[Paragraph]  # None if DELETED
    similarity_score: float  # 0-1
    block_similarity: float  # How well blocks matched
    text_match_percentage: float  # Percentage of matching characters
    confidence: float  # 0-100 final confidence score
    sentence_changes: List[SentenceChange] = field(default_factory=list)
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    page_before: int = 0
    page_after: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'change_type': self.change_type.value,
            'confidence': round(self.confidence, 1),
            'similarity_score': round(self.similarity_score, 3),
            'text_match_percentage': round(self.text_match_percentage, 1),
            'before': self.paragraph_a.text if self.paragraph_a else None,
            'after': self.paragraph_b.text if self.paragraph_b else None,
            'page_before': self.page_before,
            'page_after': self.page_after,
            'sentence_changes_count': len(self.sentence_changes)
        }


@dataclass
class DiffResult:
    """Complete diff result between two documents."""
    changes: List[ParagraphChange]
    document_a_path: str
    document_b_path: str
    total_changes: int = 0
    changes_by_type: Dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    processing_time_ms: float = 0.0
    pages_processed_a: int = 0
    pages_processed_b: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        changes_by_type = {}
        for change_type in ChangeType:
            count = sum(1 for c in self.changes if c.change_type == change_type)
            if count > 0:
                changes_by_type[change_type.value] = count
        
        avg_conf = (
            sum(c.confidence for c in self.changes) / len(self.changes)
            if self.changes else 0.0
        )
        
        return {
            'document_a': self.document_a_path,
            'document_b': self.document_b_path,
            'total_changes': len(self.changes),
            'changes_by_type': changes_by_type,
            'avg_confidence': round(avg_conf, 1),
            'processing_time_ms': round(self.processing_time_ms, 2),
            'pages_processed': {
                'document_a': self.pages_processed_a,
                'document_b': self.pages_processed_b
            }
        }
    
    def to_json(self, indent=2) -> str:
        """Serialize to JSON."""
        def default_serializer(obj):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            return str(obj)
        
        return json.dumps(
            {
                'metadata': self.to_dict(),
                'changes': [c.to_dict() for c in self.changes]
            },
            default=default_serializer,
            indent=indent
        )
