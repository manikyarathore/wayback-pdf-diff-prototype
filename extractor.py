"""
Enhanced PDF text extraction with full spatial metadata.
Supports multiple extraction libraries with fallback handling.
"""

import logging
from typing import List, Optional, Tuple
from pathlib import Path
import time

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTTextBox, LTChar
    PDFMINER_AVAILABLE = True
except ImportError:
    PDFMINER_AVAILABLE = False

from models import TextBlock
from config import ExtractionConfig

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Custom exception for extraction failures."""
    pass


class PDFExtractor:
    """Extract text blocks with spatial metadata from PDFs."""
    
    def __init__(self, use_fallback: bool = True):
        self.use_fallback = use_fallback
        self.extraction_log = []
    
    def extract(self, pdf_path: str) -> Tuple[List[TextBlock], dict]:
        """
        Extract text blocks from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple of (text_blocks, metadata)
            
        Raises:
            ExtractionError: If extraction fails
        """
        pdf_path = Path(pdf_path)
        
        # Validation
        if not pdf_path.exists():
            raise ExtractionError(f"PDF file not found: {pdf_path}")
        
        if pdf_path.suffix.lower() != '.pdf':
            raise ExtractionError(f"File is not a PDF: {pdf_path}")
        
        # Check file size
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if file_size_mb > ExtractionConfig.MAX_PDF_SIZE_MB:
            raise ExtractionError(
                f"PDF too large: {file_size_mb:.1f}MB "
                f"(max: {ExtractionConfig.MAX_PDF_SIZE_MB}MB)"
            )
        
        logger.info(f"Extracting: {pdf_path} ({file_size_mb:.1f}MB)")
        
        # Try primary extractor
        if ExtractionConfig.PRIMARY_EXTRACTOR == "pymupdf" and PYMUPDF_AVAILABLE:
            try:
                blocks, metadata = self._extract_pymupdf(pdf_path)
                logger.info(f"Successfully extracted {len(blocks)} text blocks (PyMuPDF)")
                return blocks, metadata
            except Exception as e:
                logger.warning(f"PyMuPDF extraction failed: {e}")
                if not self.use_fallback:
                    raise ExtractionError(f"PyMuPDF extraction failed: {e}")
        
        # Try fallback extractors
        if self.use_fallback:
            if PDFMINER_AVAILABLE:
                try:
                    blocks, metadata = self._extract_pdfminer(pdf_path)
                    logger.info(f"Fallback: extracted {len(blocks)} blocks (pdfminer)")
                    return blocks, metadata
                except Exception as e:
                    logger.warning(f"pdfminer extraction failed: {e}")
        
        raise ExtractionError(
            f"All extraction methods failed for {pdf_path}. "
            f"Ensure PyMuPDF or pdfminer is installed."
        )
    
    def _extract_pymupdf(self, pdf_path: Path) -> Tuple[List[TextBlock], dict]:
        """Extract using PyMuPDF (fitz)."""
        if not PYMUPDF_AVAILABLE:
            raise ExtractionError("PyMuPDF not installed")
        
        blocks = []
        doc = fitz.open(str(pdf_path))
        
        try:
            metadata = {
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'creator': doc.metadata.get('creator', ''),
                'total_pages': doc.page_count,
                'pdf_version': str(doc.metadata.get('version', '')),
                'is_encrypted': doc.is_pdf and hasattr(doc, 'is_encrypted') and doc.is_encrypted,
            }
            
            for page_num in range(doc.page_count):
                try:
                    page = doc[page_num]
                    blocks.extend(self._extract_page_pymupdf(page, page_num))
                except Exception as e:
                    logger.warning(f"Failed to extract page {page_num}: {e}")
                    # Continue with next page
                    continue
            
            return blocks, metadata
        
        finally:
            doc.close()
    
    def _extract_page_pymupdf(self, page, page_num: int) -> List[TextBlock]:
        """Extract text blocks from a single PyMuPDF page."""
        blocks = []
        
        try:
            # Use dict format for more reliable extraction
            text_dict = page.get_text("dict")
        except Exception as e:
            logger.warning(f"Failed to get text dict from page {page_num}: {e}")
            return blocks
        
        if "blocks" not in text_dict:
            return blocks
        
        for block_item in text_dict["blocks"]:
            # Only process text blocks (type 0)
            if block_item.get("type") != 0:
                continue
            
            # Extract all lines from this block
            for line in block_item.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    
                    # Extract spatial data
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    x0, y0, x1, y1 = bbox
                    
                    # Extract font info
                    font_name = span.get("font", "Unknown")
                    if isinstance(font_name, dict):
                        font_name = font_name.get("name", "Unknown")
                    
                    size = float(span.get("size", 12))
                    flags = int(span.get("flags", 0))
                    
                    # Detect bold/italic from font name
                    bold = "bold" in font_name.lower()
                    italic = "italic" in font_name.lower()
                    
                    # Extract color
                    color = 0  # Default to black
                    color_val = span.get("color")
                    if color_val:
                        if isinstance(color_val, (list, tuple)) and len(color_val) >= 3:
                            try:
                                r = int(color_val[0] * 255) if isinstance(color_val[0], float) else int(color_val[0])
                                g = int(color_val[1] * 255) if isinstance(color_val[1], float) else int(color_val[1])
                                b = int(color_val[2] * 255) if isinstance(color_val[2], float) else int(color_val[2])
                                color = (r << 16) | (g << 8) | b
                            except (ValueError, TypeError):
                                pass
                    
                    # Create TextBlock
                    text_block = TextBlock(
                        text=text,
                        x=x0,
                        y=y0,
                        width=max(0, x1 - x0),
                        height=max(0, y1 - y0),
                        font=font_name,
                        size=size,
                        bold=bold,
                        italic=italic,
                        color=color,
                        page=page_num,
                        flags=flags,
                        confidence=1.0
                    )
                    
                    blocks.append(text_block)
        
        return blocks
    
    def _extract_pdfminer(self, pdf_path: Path) -> Tuple[List[TextBlock], dict]:
        """Extract using pdfminer (fallback method)."""
        if not PDFMINER_AVAILABLE:
            raise ExtractionError("pdfminer not installed")
        
        blocks = []
        laparams = LAParams()
        page_count = 0
        
        try:
            for page_num, page_layout in enumerate(extract_pages(str(pdf_path), laparams=laparams)):
                page_count += 1
                blocks.extend(self._extract_page_pdfminer(page_layout, page_num))
            
            metadata = {
                'total_pages': page_count,
                'extraction_method': 'pdfminer',
                'is_encrypted': False,  # pdfminer doesn't support encrypted PDFs
            }
            
            return blocks, metadata
        
        except Exception as e:
            raise ExtractionError(f"pdfminer extraction failed: {e}")
    
    def _extract_page_pdfminer(self, page_layout, page_num: int) -> List[TextBlock]:
        """Extract text blocks from a single pdfminer page."""
        blocks = []
        
        def extract_from_object(obj, page_num):
            """Recursively extract text from pdfminer layout objects."""
            local_blocks = []
            
            if isinstance(obj, LTTextBox):
                text = obj.get_text().strip()
                if text:
                    # pdfminer gives us less detailed font info
                    x0, y0, x1, y1 = obj.bbox
                    
                    # Try to extract font from first character
                    font_name = "Unknown"
                    size = 12.0
                    bold = False
                    italic = False
                    
                    for line in obj:
                        for element in line:
                            if isinstance(element, LTChar):
                                font_name = element.fontname or "Unknown"
                                size = element.height
                                bold = "bold" in font_name.lower()
                                italic = "italic" in font_name.lower()
                                break
                        if font_name != "Unknown":
                            break
                    
                    block = TextBlock(
                        text=text,
                        x=x0,
                        y=y0,
                        width=x1 - x0,
                        height=y1 - y0,
                        font=font_name,
                        size=size,
                        bold=bold,
                        italic=italic,
                        color=0,  # pdfminer doesn't extract color easily
                        page=page_num,
                        flags=0,
                        confidence=0.85  # Lower confidence for pdfminer
                    )
                    local_blocks.append(block)
            
            # Recursively process child objects
            if hasattr(obj, '__iter__'):
                for child in obj:
                    local_blocks.extend(extract_from_object(child, page_num))
            
            return local_blocks
        
        return extract_from_object(page_layout, page_num)


def extract_pdf(pdf_path: str, use_fallback: bool = True) -> Tuple[List[TextBlock], dict]:
    """
    Convenience function to extract PDF blocks.
    
    Args:
        pdf_path: Path to PDF file
        use_fallback: Use fallback extractors if primary fails
        
    Returns:
        Tuple of (text_blocks, metadata)
    """
    extractor = PDFExtractor(use_fallback=use_fallback)
    return extractor.extract(pdf_path)
