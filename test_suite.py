"""
Test suite for PDF Diff pipeline.
Unit and integration tests for all components.
"""

import unittest
import logging
from pathlib import Path
from models import TextBlock, Paragraph, Document, ChangeType
from structure import StructureReconstructor
from diff_engine import MultiLevelDiffEngine, SentenceTokenizer
from normalizer import TextNormalizer, FormattingAwareSimilarity

logger = logging.getLogger(__name__)


class TestTextNormalizer(unittest.TestCase):
    """Test text normalization."""
    
    def setUp(self):
        self.normalizer = TextNormalizer()
    
    def test_whitespace_normalization(self):
        """Test collapsing multiple spaces."""
        text = "Hello    world  test"
        normalized = self.normalizer._normalize_text(text)
        self.assertEqual(normalized, "Hello world test")
    
    def test_unicode_normalization(self):
        """Test Unicode NFC normalization."""
        text = "café"  # Composed form
        normalized = self.normalizer._normalize_text(text)
        self.assertEqual(normalized, "café")
    
    def test_ligature_expansion(self):
        """Test ligature expansion."""
        text = "ﬁnally ﬂoat"
        normalized = self.normalizer._normalize_text(text)
        self.assertIn("fi", normalized)
        self.assertIn("fl", normalized)
    
    def test_page_number_removal(self):
        """Test page number detection and removal."""
        text = "This is content\n42\nMore content"
        normalized = self.normalizer._normalize_text(text)
        self.assertNotIn("42", normalized)
    
    def test_empty_string(self):
        """Test empty string handling."""
        normalized = self.normalizer._normalize_text("")
        self.assertEqual(normalized, "")


class TestStructureReconstructor(unittest.TestCase):
    """Test structure reconstruction."""
    
    def setUp(self):
        self.reconstructor = StructureReconstructor()
    
    def test_y_axis_clustering(self):
        """Test Y-axis proximity clustering."""
        # Create blocks at similar Y coordinates
        blocks = [
            TextBlock("Hello", 10, 100, 50, 12, "Arial", 12, False, False, 0, 0, 0),
            TextBlock("World", 70, 101, 50, 12, "Arial", 12, False, False, 0, 0, 0),
            TextBlock("Next", 10, 200, 50, 12, "Arial", 12, False, False, 0, 0, 0),
        ]
        
        rows = self.reconstructor._cluster_into_rows(blocks)
        
        # First two should be in same row (Y difference < threshold)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), 2)
        self.assertEqual(len(rows[1]), 1)
    
    def test_heading_detection(self):
        """Test heading detection."""
        # Large, bold text = heading
        heading_block = TextBlock(
            "Title", 10, 100, 100, 20, "Arial Bold", 18, True, False, 0, 0, 0
        )
        
        is_heading, level = self.reconstructor._detect_heading([heading_block])
        self.assertTrue(is_heading)
        self.assertGreater(level, 0)
    
    def test_block_merging_with_spacing(self):
        """Test merging blocks with space inference."""
        blocks = [
            TextBlock("Hello", 10, 100, 40, 12, "Arial", 12, False, False, 0, 0, 0),
            TextBlock("World", 100, 100, 40, 12, "Arial", 12, False, False, 0, 0, 0),
        ]
        
        merged = self.reconstructor._merge_blocks_with_spacing(blocks)
        self.assertIn(" ", merged)
        self.assertEqual(merged, "Hello World")
    
    def test_reconstruct_empty_document(self):
        """Test reconstruction with empty block list."""
        doc = self.reconstructor.reconstruct([], 0)
        self.assertEqual(len(doc.paragraphs), 0)
        self.assertEqual(doc.total_pages, 0)


class TestSentenceTokenizer(unittest.TestCase):
    """Test sentence tokenization."""
    
    def setUp(self):
        self.tokenizer = SentenceTokenizer()
    
    def test_basic_sentence_split(self):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence. Third."
        sentences = self.tokenizer.tokenize(text)
        self.assertEqual(len(sentences), 3)
    
    def test_abbreviation_handling(self):
        """Test abbreviation handling (e.g., Mr., Dr.)."""
        text = "Dr. Smith said hello. Then Mr. Jones left."
        sentences = self.tokenizer.tokenize(text)
        # Should be 2 sentences, not 4
        self.assertEqual(len(sentences), 2)
    
    def test_decimal_handling(self):
        """Test decimal number handling."""
        text = "Version 3.14 is released. Check 9.8 support."
        sentences = self.tokenizer.tokenize(text)
        self.assertEqual(len(sentences), 2)
    
    def test_multiple_punctuation(self):
        """Test multiple punctuation marks."""
        text = "Really? Yes! Definitely."
        sentences = self.tokenizer.tokenize(text)
        self.assertEqual(len(sentences), 3)
    
    def test_empty_text(self):
        """Test empty text handling."""
        sentences = self.tokenizer.tokenize("")
        self.assertEqual(len(sentences), 0)


class TestDiffEngine(unittest.TestCase):
    """Test diff engine."""
    
    def setUp(self):
        self.engine = MultiLevelDiffEngine()
    
    def test_identical_documents(self):
        """Test diffing identical documents."""
        para = Paragraph(
            text="Same content",
            blocks=[],
            page=0,
            position_on_page=0.5
        )
        
        doc_a = Document(paragraphs=[para], total_pages=1)
        doc_b = Document(paragraphs=[para], total_pages=1)
        
        result = self.engine.diff(doc_a, doc_b)
        
        # Should have one UNCHANGED change
        unchanged = [c for c in result.changes if c.change_type == ChangeType.UNCHANGED]
        self.assertGreater(len(unchanged), 0)
    
    def test_added_paragraph(self):
        """Test detection of added paragraphs."""
        para_a = Paragraph(
            text="Original",
            blocks=[],
            page=0,
            position_on_page=0.5
        )
        
        para_b = Paragraph(
            text="Original",
            blocks=[],
            page=0,
            position_on_page=0.5
        )
        
        para_added = Paragraph(
            text="New content",
            blocks=[],
            page=1,
            position_on_page=0.6
        )
        
        doc_a = Document(paragraphs=[para_a], total_pages=1)
        doc_b = Document(paragraphs=[para_b, para_added], total_pages=2)
        
        result = self.engine.diff(doc_a, doc_b)
        
        # Should have one ADDED change
        added = [c for c in result.changes if c.change_type == ChangeType.ADDED]
        self.assertEqual(len(added), 1)
    
    def test_deleted_paragraph(self):
        """Test detection of deleted paragraphs."""
        para_a = Paragraph(
            text="Original",
            blocks=[],
            page=0,
            position_on_page=0.5
        )
        
        para_deleted = Paragraph(
            text="To be deleted",
            blocks=[],
            page=0,
            position_on_page=0.4
        )
        
        para_b = Paragraph(
            text="Original",
            blocks=[],
            page=0,
            position_on_page=0.5
        )
        
        doc_a = Document(paragraphs=[para_deleted, para_a], total_pages=1)
        doc_b = Document(paragraphs=[para_b], total_pages=1)
        
        result = self.engine.diff(doc_a, doc_b)
        
        # Should have one DELETED change
        deleted = [c for c in result.changes if c.change_type == ChangeType.DELETED]
        self.assertEqual(len(deleted), 1)
    
    def test_modified_paragraph(self):
        """Test detection of modified paragraphs."""
        para_a = Paragraph(
            text="Original content here",
            blocks=[],
            page=0,
            position_on_page=0.5
        )
        
        para_b = Paragraph(
            text="Modified content here",
            blocks=[],
            page=0,
            position_on_page=0.5
        )
        
        doc_a = Document(paragraphs=[para_a], total_pages=1)
        doc_b = Document(paragraphs=[para_b], total_pages=1)
        
        result = self.engine.diff(doc_a, doc_b)
        
        # Should have one MODIFIED change
        modified = [c for c in result.changes if c.change_type == ChangeType.MODIFIED]
        self.assertGreater(len(modified), 0)


class TestFormattingAwareSimilarity(unittest.TestCase):
    """Test formatting-aware similarity."""
    
    def test_identical_text(self):
        """Test identical text has high similarity."""
        text = "Hello world"
        similarity = FormattingAwareSimilarity.similarity_ignoring_formatting(text, text)
        self.assertEqual(similarity, 1.0)
    
    def test_whitespace_difference(self):
        """Test whitespace differences ignored."""
        text1 = "Hello   world"
        text2 = "Hello world"
        similarity = FormattingAwareSimilarity.similarity_ignoring_formatting(text1, text2)
        self.assertGreater(similarity, 0.9)
    
    def test_formatting_only_detection(self):
        """Test detection of formatting-only changes."""
        text1 = "Hello world"
        text2 = "Hello world"  # Same content, different formatting
        
        is_formatting_only = FormattingAwareSimilarity.is_formatting_only_change(
            text1, text2, threshold=0.95
        )
        self.assertTrue(is_formatting_only)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_end_to_end_with_mock_pdfs(self):
        """Test complete pipeline with mock data."""
        # Create mock text blocks
        blocks_a = [
            TextBlock("Introduction", 10, 50, 100, 20, "Arial Bold", 16, True, False, 0, 0, 0),
            TextBlock("This is the first paragraph.", 10, 80, 200, 12, "Arial", 12, False, False, 0, 0, 0),
            TextBlock("This is the second paragraph.", 10, 100, 200, 12, "Arial", 12, False, False, 0, 0, 0),
        ]
        
        blocks_b = [
            TextBlock("Introduction", 10, 50, 100, 20, "Arial Bold", 16, True, False, 0, 0, 0),
            TextBlock("This is the first paragraph (modified).", 10, 80, 200, 12, "Arial", 12, False, False, 0, 0, 0),
            TextBlock("This is the second paragraph.", 10, 100, 200, 12, "Arial", 12, False, False, 0, 0, 0),
            TextBlock("New paragraph added here.", 10, 120, 200, 12, "Arial", 12, False, False, 0, 0, 0),
        ]
        
        # Run through pipeline
        reconstructor = StructureReconstructor()
        doc_a = reconstructor.reconstruct(blocks_a, 1)
        doc_b = reconstructor.reconstruct(blocks_b, 1)
        
        engine = MultiLevelDiffEngine()
        result = engine.diff(doc_a, doc_b)
        
        # Verify results
        self.assertGreater(len(result.changes), 0)
        
        # Should have at least one change detected
        has_modified = any(c.change_type == ChangeType.MODIFIED for c in result.changes)
        has_added = any(c.change_type == ChangeType.ADDED for c in result.changes)
        
        self.assertTrue(has_modified or has_added)


def run_tests():
    """Run all tests."""
    logging.basicConfig(level=logging.WARNING)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestTextNormalizer))
    suite.addTests(loader.loadTestsFromTestCase(TestStructureReconstructor))
    suite.addTests(loader.loadTestsFromTestCase(TestSentenceTokenizer))
    suite.addTests(loader.loadTestsFromTestCase(TestDiffEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestFormattingAwareSimilarity))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit(run_tests())
