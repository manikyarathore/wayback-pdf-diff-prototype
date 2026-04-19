"""
Document structure reconstruction.
Converts flat text blocks into hierarchical document structure via spatial analysis.
"""

import logging
from typing import List, Tuple, Dict
from models import TextBlock, Paragraph, Document
from config import StructureConfig

logger = logging.getLogger(__name__)


class StructureReconstructor:
    """Reconstruct logical document structure from text blocks."""
    
    def __init__(self, y_threshold: float = StructureConfig.Y_PROXIMITY_THRESHOLD_PX):
        self.y_threshold = y_threshold
        self.adaptive_threshold = StructureConfig.ADAPTIVE_THRESHOLD_ENABLED
    
    def reconstruct(self, blocks: List[TextBlock], total_pages: int) -> Document:
        """
        Reconstruct document structure from text blocks.
        
        Args:
            blocks: List of extracted text blocks
            total_pages: Total number of pages in document
            
        Returns:
            Document object with reconstructed structure
        """
        if not blocks:
            logger.warning("No text blocks to reconstruct")
            return Document(paragraphs=[], total_pages=total_pages)
        
        logger.info(f"Reconstructing structure from {len(blocks)} blocks")
        
        # Step 1: Sort blocks by page, then by Y coordinate
        sorted_blocks = sorted(blocks, key=lambda b: (b.page, b.y))
        
        # Step 2: Group blocks into rows using Y-proximity clustering
        rows = self._cluster_into_rows(sorted_blocks)
        logger.debug(f"Clustered into {len(rows)} rows")
        
        # Step 3: Merge blocks within rows (left-to-right)
        paragraphs = self._merge_rows_into_paragraphs(rows, total_pages)
        logger.debug(f"Merged into {len(paragraphs)} paragraphs")
        
        # Step 4: Build hierarchical structure
        document = Document(
            paragraphs=paragraphs,
            total_pages=total_pages,
            metadata={
                'reconstruction_method': 'y-axis-clustering',
                'y_threshold': self.y_threshold,
                'total_blocks_processed': len(blocks)
            }
        )
        
        return document
    
    def _cluster_into_rows(self, blocks: List[TextBlock]) -> List[List[TextBlock]]:
        """
        Cluster text blocks into rows using Y-axis proximity.
        
        Algorithm:
        1. Sort by page, then Y coordinate
        2. Group blocks with Y coordinates within threshold
        3. Within each group, sort by X coordinate (left-to-right)
        """
        rows = []
        current_row = []
        current_y = None
        current_page = None
        
        for block in blocks:
            # New page: start fresh
            if block.page != current_page:
                if current_row:
                    rows.append(current_row)
                current_row = [block]
                current_y = block.y
                current_page = block.page
                continue
            
            # Adaptive threshold based on font size
            threshold = self.y_threshold
            if self.adaptive_threshold:
                threshold = block.size * StructureConfig.ADAPTIVE_THRESHOLD_SCALE
            
            # Same row?
            if abs(block.y - current_y) <= threshold:
                current_row.append(block)
            else:
                # New row
                if current_row:
                    rows.append(current_row)
                current_row = [block]
                current_y = block.y
        
        # Don't forget last row
        if current_row:
            rows.append(current_row)
        
        # Sort within each row by X coordinate (left-to-right)
        if StructureConfig.X_SORT_ENABLED:
            for row in rows:
                row.sort(key=lambda b: b.x)
        
        return rows
    
    def _merge_rows_into_paragraphs(
        self, rows: List[List[TextBlock]], total_pages: int
    ) -> List[Paragraph]:
        """
        Merge blocks within rows into logical paragraphs.
        Detects headings, handles spacing, builds paragraph objects.
        """
        paragraphs = []
        
        for row in rows:
            if not row:
                continue
            
            # Merge text with space inference
            merged_text = self._merge_blocks_with_spacing(row)
            if not merged_text.strip():
                continue
            
            # Detect if this is a heading
            is_heading, heading_level = self._detect_heading(row)
            
            # Calculate position
            page = row[0].page
            min_y = min(b.y for b in row)
            page_height = max(b.y + b.height for b in row) - min(b.y for b in row)
            position_on_page = min_y / page_height if page_height > 0 else 0.0
            
            # Create paragraph
            para = Paragraph(
                text=merged_text,
                blocks=row,
                is_heading=is_heading,
                heading_level=heading_level,
                page=page,
                position_on_page=position_on_page
            )
            
            paragraphs.append(para)
        
        logger.debug(
            f"Created {len(paragraphs)} paragraphs "
            f"({sum(1 for p in paragraphs if p.is_heading)} headings)"
        )
        
        return paragraphs
    
    def _merge_blocks_with_spacing(self, blocks: List[TextBlock]) -> str:
        """
        Merge blocks in a row with intelligent space handling.
        """
        if not blocks:
            return ""
        
        # Sort by X coordinate
        sorted_blocks = sorted(blocks, key=lambda b: b.x)
        
        merged_parts = []
        for i, block in enumerate(sorted_blocks):
            merged_parts.append(block.text)
            
            # Add space between blocks if there's a gap
            if i < len(sorted_blocks) - 1:
                next_block = sorted_blocks[i + 1]
                gap = next_block.x - (block.x + block.width)
                
                if gap > StructureConfig.HORIZONTAL_GAP_THRESHOLD_PX:
                    merged_parts.append(" ")
                elif gap > 0:
                    merged_parts.append(" ")
                # If gap is negative or zero, no space (overlapping or adjacent)
        
        return "".join(merged_parts).strip()
    
    def _detect_heading(self, blocks: List[TextBlock]) -> Tuple[bool, int]:
        """
        Detect if row is a heading based on font characteristics.
        
        Returns:
            Tuple of (is_heading, heading_level)
        """
        if not blocks:
            return False, 0
        
        # Check size threshold
        avg_size = sum(b.size for b in blocks) / len(blocks)
        is_large = avg_size >= StructureConfig.HEADING_SIZE_THRESHOLD_PT
        
        # Check bold requirement
        has_bold = any(b.bold for b in blocks) if StructureConfig.HEADING_REQUIRES_BOLD else True
        
        if is_large and has_bold:
            # Estimate heading level (1-6) based on size
            # Assume normal text is ~12pt
            size_delta = avg_size - 12
            if size_delta >= 10:
                heading_level = 1
            elif size_delta >= 6:
                heading_level = 2
            elif size_delta >= 4:
                heading_level = 3
            else:
                heading_level = 4
            
            return True, min(heading_level, 6)  # Cap at H6
        
        return False, 0


class ColumnDetector:
    """Detect multi-column layouts in documents."""
    
    @staticmethod
    def detect_columns(blocks: List[TextBlock]) -> List[Tuple[float, float]]:
        """
        Detect column boundaries using X coordinate distribution.
        
        Returns:
            List of (left_x, right_x) tuples for each column
        """
        if not blocks:
            return []
        
        # Get X coordinates
        x_coords = sorted(set(round(b.x, 1) for b in blocks))
        
        if not x_coords:
            return []
        
        # Find gaps (potential column boundaries)
        gaps = []
        for i in range(len(x_coords) - 1):
            gap = x_coords[i + 1] - x_coords[i]
            if gap > StructureConfig.MIN_COLUMN_WIDTH:
                gaps.append((x_coords[i], x_coords[i + 1], gap))
        
        # If no significant gaps, assume single column
        if not gaps:
            return [(min(x_coords), max(x_coords))]
        
        # Sort by gap size
        gaps.sort(key=lambda x: x[2], reverse=True)
        
        # Take the largest gaps as column boundaries
        column_boundaries = [x[0] for x in gaps[:3]]  # Up to 3 columns
        column_boundaries.sort()
        
        # Create column ranges
        all_x = [min(x_coords)] + column_boundaries + [max(x_coords)]
        columns = []
        for i in range(len(all_x) - 1):
            columns.append((all_x[i], all_x[i + 1]))
        
        return columns


def reconstruct_structure(blocks: List[TextBlock], total_pages: int) -> Document:
    """Convenience function to reconstruct document structure."""
    reconstructor = StructureReconstructor()
    return reconstructor.reconstruct(blocks, total_pages)
