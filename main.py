"""
Main pipeline orchestration.
Coordinates all stages: extraction, structure, normalization, diffing.
"""

import logging
import time
import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from extractor import extract_pdf, ExtractionError
from normalizer import normalize_pdf_content
from structure import reconstruct_structure
from diff_engine import compute_diff
from models import DiffResult
from config import LoggingConfig

# Configure logging
logging.basicConfig(
    level=getattr(logging, LoggingConfig.LOG_LEVEL),
    format=LoggingConfig.LOG_FORMAT,
    handlers=[
        logging.FileHandler(LoggingConfig.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class PDFDiffPipeline:
    """Main pipeline for PDF diffing."""
    
    def __init__(self):
        self.timing = {}
    
    def run(
        self,
        pdf_a_path: str,
        pdf_b_path: str,
        min_confidence: int = 60
    ) -> DiffResult:
        """
        Run the complete PDF diff pipeline.
        
        Args:
            pdf_a_path: Path to first PDF
            pdf_b_path: Path to second PDF
            min_confidence: Minimum confidence threshold (0-100)
            
        Returns:
            DiffResult object
        """
        logger.info("="*70)
        logger.info(f"PDF Diff Pipeline Starting")
        logger.info(f"  Document A: {pdf_a_path}")
        logger.info(f"  Document B: {pdf_b_path}")
        logger.info("="*70)
        
        start_time = time.time()
        
        try:
            # Stage 1: Extraction
            logger.info("\n[Stage 1/5] Text Extraction")
            blocks_a, meta_a = self._stage_extraction(pdf_a_path)
            blocks_b, meta_b = self._stage_extraction(pdf_b_path)
            
            # Stage 2: Normalization
            logger.info("\n[Stage 2/5] Normalization")
            blocks_a = self._stage_normalization(blocks_a)
            blocks_b = self._stage_normalization(blocks_b)
            
            # Stage 3: Structure Reconstruction
            logger.info("\n[Stage 3/5] Structure Reconstruction")
            doc_a = self._stage_structure(blocks_a, meta_a['total_pages'])
            doc_b = self._stage_structure(blocks_b, meta_b['total_pages'])
            
            # Stage 4: Diffing
            logger.info("\n[Stage 4/5] Diff Computation")
            diff_result = self._stage_diffing(doc_a, doc_b)
            
            # Stage 5: Filtering & Output
            logger.info("\n[Stage 5/5] Results Processing")
            self._stage_output(diff_result, min_confidence)
            
            # Timing
            total_time = (time.time() - start_time) * 1000  # Convert to ms
            diff_result.processing_time_ms = total_time
            diff_result.document_a_path = pdf_a_path
            diff_result.document_b_path = pdf_b_path
            
            # Summary
            logger.info("\n" + "="*70)
            logger.info(f"Pipeline Complete in {total_time:.1f}ms")
            logger.info(f"  Total changes: {len(diff_result.changes)}")
            logger.info(f"  Avg confidence: {diff_result.processing_time_ms:.1f}%")
            logger.info("="*70)
            
            return diff_result
        
        except ExtractionError as e:
            logger.error(f"Extraction failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            raise
    
    def _stage_extraction(self, pdf_path: str):
        """Stage 1: Extract text blocks with metadata."""
        stage_start = time.time()
        
        try:
            blocks, metadata = extract_pdf(pdf_path)
            stage_time = (time.time() - stage_start) * 1000
            
            logger.info(f"  ✓ Extracted {len(blocks)} text blocks from {pdf_path}")
            logger.info(f"    Pages: {metadata.get('total_pages', '?')}")
            logger.info(f"    Time: {stage_time:.1f}ms")
            logger.debug(f"    Metadata: {metadata}")
            
            self.timing['extraction'] = stage_time
            return blocks, metadata
        
        except ExtractionError as e:
            logger.error(f"  ✗ Extraction failed: {e}")
            raise
    
    def _stage_normalization(self, blocks):
        """Stage 2: Normalize text content."""
        stage_start = time.time()
        
        before_count = len(blocks)
        blocks = normalize_pdf_content(blocks)
        after_count = len(blocks)
        
        stage_time = (time.time() - stage_start) * 1000
        
        logger.info(f"  ✓ Normalized {before_count} → {after_count} blocks")
        logger.info(f"    Time: {stage_time:.1f}ms")
        
        self.timing['normalization'] = stage_time
        return blocks
    
    def _stage_structure(self, blocks, total_pages):
        """Stage 3: Reconstruct document structure."""
        stage_start = time.time()
        
        doc = reconstruct_structure(blocks, total_pages)
        
        stage_time = (time.time() - stage_start) * 1000
        
        logger.info(f"  ✓ Reconstructed structure")
        logger.info(f"    Paragraphs: {len(doc.paragraphs)}")
        logger.info(f"    Headings: {sum(1 for p in doc.paragraphs if p.is_heading)}")
        logger.info(f"    Time: {stage_time:.1f}ms")
        
        self.timing['structure'] = stage_time
        return doc
    
    def _stage_diffing(self, doc_a, doc_b):
        """Stage 4: Compute diff."""
        stage_start = time.time()
        
        result = compute_diff(doc_a, doc_b)
        
        stage_time = (time.time() - stage_start) * 1000
        
        from models import ChangeType
        change_summary = {}
        for change_type in ChangeType:
            count = sum(1 for c in result.changes if c.change_type == change_type)
            if count > 0:
                change_summary[change_type.value] = count
        
        logger.info(f"  ✓ Diff computation complete")
        logger.info(f"    Changes detected:")
        for change_type, count in change_summary.items():
            logger.info(f"      {change_type}: {count}")
        logger.info(f"    Time: {stage_time:.1f}ms")
        
        self.timing['diffing'] = stage_time
        return result
    
    def _stage_output(self, diff_result, min_confidence):
        """Stage 5: Process and filter results."""
        stage_start = time.time()
        
        # Filter by confidence
        original_count = len(diff_result.changes)
        diff_result.changes = [
            c for c in diff_result.changes
            if c.confidence >= min_confidence
        ]
        filtered_count = len(diff_result.changes)
        
        stage_time = (time.time() - stage_start) * 1000
        
        logger.info(f"  ✓ Output processing complete")
        logger.info(f"    Filtered: {original_count} → {filtered_count} "
                   f"(confidence ≥ {min_confidence}%)")
        logger.info(f"    Time: {stage_time:.1f}ms")
        
        self.timing['output'] = stage_time
    
    def print_timing_report(self):
        """Print execution timing report."""
        logger.info("\nTiming Report:")
        logger.info("-" * 40)
        total = sum(self.timing.values())
        for stage, time_ms in self.timing.items():
            percentage = (time_ms / total * 100) if total > 0 else 0
            logger.info(f"  {stage:20s}: {time_ms:8.1f}ms ({percentage:5.1f}%)")
        logger.info("-" * 40)
        logger.info(f"  {'TOTAL':20s}: {total:8.1f}ms")


def _validate_pdf_files(pdf_a: str, pdf_b: str) -> bool:
    """Validate that PDF files exist and are readable."""
    errors = []
    
    for pdf_path, label in [(pdf_a, "Document A"), (pdf_b, "Document B")]:
        path = Path(pdf_path)
        
        if not path.exists():
            errors.append(f"  ✗ {label} not found: {pdf_path}")
        elif not path.is_file():
            errors.append(f"  ✗ {label} is not a file: {pdf_path}")
        elif not path.suffix.lower() == '.pdf':
            errors.append(f"  ✗ {label} is not a PDF: {pdf_path}")
        elif path.stat().st_size == 0:
            errors.append(f"  ✗ {label} is empty: {pdf_path}")
    
    if errors:
        print("\n❌ File Validation Failed:")
        print("\n".join(errors))
        print("\nPlease check file paths and try again.")
        return False
    
    return True


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="PDF Diff: Detect structural and semantic changes in PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py doc1.pdf doc2.pdf
  python main.py doc1.pdf doc2.pdf --min-confidence 75 --format json
  python main.py doc1.pdf doc2.pdf --output diff_result.json
        """
    )
    
    parser.add_argument('pdf_a', help='First PDF file')
    parser.add_argument('pdf_b', help='Second PDF file')
    parser.add_argument(
        '--min-confidence',
        type=int,
        default=60,
        help='Minimum confidence threshold (0-100, default: 60)'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'text', 'html'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--output',
        help='Save output to file (default: stdout)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose logging'
    )
    
    args = parser.parse_args()
    
    # Validate files first
    if not _validate_pdf_files(args.pdf_a, args.pdf_b):
        return 1
    
    # Run pipeline
    pipeline = PDFDiffPipeline()
    
    try:
        result = pipeline.run(args.pdf_a, args.pdf_b, args.min_confidence)
        pipeline.print_timing_report()
        
        # Check if extraction was successful
        if result.pages_processed_a == 0 or result.pages_processed_b == 0:
            print("\n⚠️  WARNING: No text content extracted from PDFs")
            print("   Possible causes:")
            print("   1. PDFs contain only scanned images (need OCR)")
            print("   2. PDFs are encrypted or password-protected")
            print("   3. PDFs have no selectable text")
            print("\n   To use OCR on scanned PDFs, install Tesseract:")
            print("   Ubuntu/Debian: sudo apt-get install tesseract-ocr")
            print("   macOS: brew install tesseract")
            print("   Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            return 1
        
        # Check if any changes were found
        if len(result.changes) == 0:
            print("\n✅ Comparison complete: No differences found between documents")
            return 0
        
        # Format output
        if args.format == 'json':
            output = result.to_json()
        elif args.format == 'html':
            output = _format_html(result)
        else:  # text
            output = _format_text(result)
        
        # Write output
        if args.output:
            Path(args.output).write_text(output)
            print(f"\n✅ Results saved to: {args.output}")
        else:
            print("\n" + output)
        
        return 0
    
    except ExtractionError as e:
        print(f"\n❌ PDF Extraction Error: {e}")
        print("   Check that PDF files are valid and not corrupted.")
        return 1
    
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        if args.verbose:
            print("\n   Full error details:")
            import traceback
            traceback.print_exc()
        else:
            print("\n   Run with --verbose for detailed error information")
        return 1


def _format_text(result: DiffResult) -> str:
    """Format diff result as plain text."""
    lines = []
    lines.append("PDF Diff Results")
    lines.append("=" * 70)
    lines.append(f"Document A: {result.document_a_path}")
    lines.append(f"Document B: {result.document_b_path}")
    lines.append(f"Processing time: {result.processing_time_ms:.1f}ms")
    lines.append(f"Total changes: {len(result.changes)}")
    lines.append("")
    
    for i, change in enumerate(result.changes, 1):
        lines.append(f"Change {i}: {change.change_type.value} (Confidence: {change.confidence:.1f}%)")
        if change.paragraph_a:
            lines.append(f"  Before: {change.paragraph_a.text[:80]}...")
        if change.paragraph_b:
            lines.append(f"  After:  {change.paragraph_b.text[:80]}...")
        lines.append("")
    
    return "\n".join(lines)


def _format_html(result: DiffResult) -> str:
    """Format diff result as HTML."""
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<title>PDF Diff Results</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 20px; }",
        ".change { margin: 15px 0; padding: 10px; border-left: 4px solid #ccc; }",
        ".added { border-color: #28a745; background: #d4edda; }",
        ".deleted { border-color: #dc3545; background: #f8d7da; }",
        ".modified { border-color: #ffc107; background: #fff3cd; }",
        ".confidence { font-weight: bold; }",
        "pre { background: #f5f5f5; padding: 10px; overflow-x: auto; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>PDF Diff Results</h1>",
        f"<p>Document A: {result.document_a_path}</p>",
        f"<p>Document B: {result.document_b_path}</p>",
        f"<p>Processing time: {result.processing_time_ms:.1f}ms</p>",
        f"<p>Total changes: {len(result.changes)}</p>",
        "<hr>",
    ]
    
    for i, change in enumerate(result.changes, 1):
        change_class = change.change_type.value.lower()
        html_lines.append(f'<div class="change {change_class}">')
        html_lines.append(f"<p><strong>Change {i}: {change.change_type.value}</strong> ")
        html_lines.append(f'<span class="confidence">(Confidence: {change.confidence:.1f}%)</span></p>')
        
        if change.paragraph_a:
            html_lines.append(f"<p><strong>Before:</strong></p>")
            html_lines.append(f"<pre>{change.paragraph_a.text}</pre>")
        
        if change.paragraph_b:
            html_lines.append(f"<p><strong>After:</strong></p>")
            html_lines.append(f"<pre>{change.paragraph_b.text}</pre>")
        
        html_lines.append("</div>")
    
    html_lines.extend([
        "</body>",
        "</html>"
    ])
    
    return "\n".join(html_lines)


if __name__ == '__main__':
    sys.exit(main())
