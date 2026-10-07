"""
ASME RAG PDF Parser

This module provides functionality to parse ASME PDFs into structured text blocks
using PyMuPDF. It handles:
- Column-aware reading order
- Header/footer detection and removal
- Watermark removal
- Bold and superscript flag preservation
- Figure and table detection
- Memory-efficient processing

The parser is designed to work with ASME BPVC PDFs and related standards.
"""

import os
import sys
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import fitz  # PyMuPDF
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import Config, get_config


@dataclass
class TextBlock:
    """A block of text from a PDF page."""
    
    # Position and size
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    
    # Text content
    text: str = ""
    
    # Formatting
    font_name: str = ""
    font_size: float = 0.0
    is_bold: bool = False
    is_superscript: bool = False
    is_italic: bool = False
    
    # Type
    type: str = "text"  # text, header, footer, watermark, figure, table
    
    # Metadata
    page: int = 0
    block_id: str = ""
    
    def __post_init__(self):
        if not self.block_id:
            self.block_id = f"page{self.page}_x{self.x}_y{self.y}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'text': self.text,
            'font_name': self.font_name,
            'font_size': self.font_size,
            'is_bold': self.is_bold,
            'is_superscript': self.is_superscript,
            'is_italic': self.is_italic,
            'type': self.type,
            'page': self.page,
            'block_id': self.block_id
        }


@dataclass
class FigureBlock:
    """A figure or image block from a PDF page."""
    
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    page: int = 0
    caption: str = ""
    figure_number: str = ""
    block_id: str = ""
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    
    def __post_init__(self):
        if not self.block_id:
            self.block_id = f"fig_page{self.page}_x{self.x}_y{self.y}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'page': self.page,
            'caption': self.caption,
            'figure_number': self.figure_number,
            'block_id': self.block_id,
            'bbox': self.bbox
        }


@dataclass
class PageData:
    """Data extracted from a single PDF page."""
    
    page_number: int = 0
    width: float = 0.0
    height: float = 0.0
    blocks: List[TextBlock] = field(default_factory=list)
    figures: List[FigureBlock] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'page_number': self.page_number,
            'width': self.width,
            'height': self.height,
            'blocks': [b.to_dict() for b in self.blocks],
            'figures': [f.to_dict() for f in self.figures]
        }


class PDFParser:
    """
    PDF parser for ASME documents using PyMuPDF.
    
    This parser extracts text blocks with formatting information and
    detects figures and tables. It handles column layout and removes
    headers, footers, and watermarks.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the PDF parser.
        
        Args:
            config: Configuration object
        """
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # Compile regex patterns for stripping
        self.strip_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.strip_patterns
        ]
        
        # Compile patterns for detection
        self.figure_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.figure_patterns
        ]
        
        self.table_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.table_patterns
        ]
    
    def parse(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse a PDF file and return structured data.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing parsed data with pages, blocks, figures
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.logger.info(f"Parsing PDF: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            self.logger.error(f"Failed to open PDF {pdf_path}: {str(e)}")
            raise
        
        try:
            pages = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_data = self.parse_page(page, page_num + 1)
                pages.append(page_data.to_dict())
                
                # Progress logging
                if (page_num + 1) % 10 == 0:
                    self.logger.info(f"  Parsed {page_num + 1}/{len(doc)} pages")
            
            result = {
                'pdf_path': pdf_path,
                'total_pages': len(doc),
                'pages': pages
            }
            
            self.logger.info(f"Completed parsing: {len(pages)} pages")
            return result
            
        finally:
            doc.close()
    
    def parse_page(self, page: fitz.Page, page_num: int) -> PageData:
        """
        Parse a single PDF page.
        
        Args:
            page: PyMuPDF page object
            page_num: 1-based page number
            
        Returns:
            PageData object with blocks and figures
        """
        page_data = PageData(page_number=page_num)
        page_data.width = page.rect.width
        page_data.height = page.rect.height
        
        # Get page blocks with dict format for detailed analysis
        blocks = page.get_text("dict")["blocks"]
        
        # Process text blocks
        text_blocks = []
        for block in blocks:
            if block["type"] == 0:  # Text block
                text_blocks.extend(self.process_text_block(block, page_num))
            elif block["type"] == 1:  # Image block
                # Process as potential figure
                figures = self.process_image_block(block, page_num)
                page_data.figures.extend(figures)
        
        # Sort blocks by reading order
        text_blocks = self.sort_blocks_by_reading_order(text_blocks)
        
        # Detect and remove headers/footers/watermarks
        cleaned_blocks = self.remove_headers_footers_watermarks(text_blocks)
        
        # Detect figures from text (captions)
        figure_blocks = self.detect_figures_from_text(cleaned_blocks, page_num)
        page_data.figures.extend(figure_blocks)
        
        # Remove figure captions from text blocks
        cleaned_blocks = self.remove_figure_captions(cleaned_blocks, figure_blocks)
        
        page_data.blocks = cleaned_blocks
        
        return page_data
    
    def process_text_block(self, block: Dict[str, Any], page_num: int) -> List[TextBlock]:
        """
        Process a text block from PyMuPDF dict output.
        
        Args:
            block: Text block from PyMuPDF
            page_num: Page number
            
        Returns:
            List of TextBlock objects
        """
        blocks = []
        
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text_block = TextBlock(
                    x=span["bbox"][0],
                    y=span["bbox"][1],
                    width=span["bbox"][2] - span["bbox"][0],
                    height=span["bbox"][3] - span["bbox"][1],
                    text=span["text"],
                    font_name=span.get("font", ""),
                    font_size=span.get("size", 0.0),
                    is_bold="bold" in span.get("font", "").lower(),
                    is_superscript=span.get("flags", 0) & 0x20 != 0,  # SUPSCRIPT flag
                    is_italic="italic" in span.get("font", "").lower(),
                    type="text",
                    page=page_num
                )
                blocks.append(text_block)
        
        return blocks
    
    def process_image_block(self, block: Dict[str, Any], page_num: int) -> List[FigureBlock]:
        """
        Process an image block as a potential figure.
        
        Args:
            block: Image block from PyMuPDF
            page_num: Page number
            
        Returns:
            List of FigureBlock objects
        """
        figures = []
        
        bbox = block.get("bbox", (0, 0, 0, 0))
        
        # Create figure block
        figure = FigureBlock(
            x=bbox[0],
            y=bbox[1],
            width=bbox[2] - bbox[0],
            height=bbox[3] - bbox[1],
            page=page_num,
            bbox=bbox
        )
        
        figures.append(figure)
        
        return figures
    
    def sort_blocks_by_reading_order(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Sort text blocks by reading order (top-to-bottom, left-to-right).
        
        Handles column layout by detecting column structure.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Sorted list of text blocks
        """
        if not blocks:
            return blocks
        
        # Detect columns
        columns = self.detect_columns(blocks)
        
        if len(columns) > 1:
            # Multi-column layout
            sorted_blocks = []
            
            for column in columns:
                # Sort blocks within column by Y position
                column_blocks = [b for b in blocks if column[0] <= b.x < column[1]]
                column_blocks.sort(key=lambda b: (b.y, b.x))
                sorted_blocks.extend(column_blocks)
            
            return sorted_blocks
        else:
            # Single column - sort by Y then X
            return sorted(blocks, key=lambda b: (b.y, b.x))
    
    def detect_columns(self, blocks: List[TextBlock]) -> List[Tuple[float, float]]:
        """
        Detect column boundaries in the page.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            List of (start_x, end_x) tuples for each column
        """
        if not blocks:
            return [(0, float('inf'))]
        
        # Get all X positions
        x_positions = [b.x for b in blocks]
        
        # Find gaps between columns
        x_positions.sort()
        gaps = []
        
        for i in range(1, len(x_positions)):
            gap = x_positions[i] - x_positions[i-1]
            if gap > self.config.column_gap_threshold:
                gaps.append((x_positions[i-1], x_positions[i]))
        
        # If no significant gaps, single column
        if not gaps:
            return [(0, float('inf'))]
        
        # Determine column boundaries
        columns = []
        start = 0
        
        for gap_start, gap_end in gaps:
            # End of previous column is at the gap
            columns.append((start, (gap_start + gap_end) / 2))
            start = (gap_start + gap_end) / 2
        
        # Add last column
        columns.append((start, float('inf')))
        
        return columns
    
    def remove_headers_footers_watermarks(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Remove header, footer, and watermark blocks.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Cleaned list of text blocks
        """
        if not blocks:
            return blocks
        
        page_height = max(b.y + b.height for b in blocks)
        cleaned_blocks = []
        
        for block in blocks:
            # Check if block is a header (top of page)
            is_header = block.y < page_height * self.config.header_footer_threshold
            
            # Check if block is a footer (bottom of page)
            is_footer = (block.y + block.height) > page_height * (1 - self.config.header_footer_threshold)
            
            # Check if block is a watermark (diagonal text)
            is_watermark = self.is_watermark(block)
            
            # Check if block matches strip patterns
            is_stripped = any(
                pattern.search(block.text)
                for pattern in self.strip_patterns
            )
            
            if not (is_header or is_footer or is_watermark or is_stripped):
                cleaned_blocks.append(block)
        
        return cleaned_blocks
    
    def is_watermark(self, block: TextBlock) -> bool:
        """
        Check if a text block is a watermark (diagonal or rotated text).
        
        Args:
            block: Text block to check
            
        Returns:
            True if block appears to be a watermark
        """
        # Check if text is diagonal (width and height both significant)
        is_diagonal = (block.width > block.height * 0.5 and 
                      block.height > block.width * 0.5)
        
        # Check if text is very large (watermarks are often large)
        is_large = block.font_size > 50
        
        # Check if text is rotated
        is_rotated = abs(block.width - block.height) > min(block.width, block.height) * 2
        
        return is_diagonal or is_large or is_rotated
    
    def detect_figures_from_text(self, blocks: List[TextBlock], page_num: int) -> List[FigureBlock]:
        """
        Detect figure captions in text blocks and create figure entries.
        
        Args:
            blocks: List of text blocks
            page_num: Page number
            
        Returns:
            List of FigureBlock objects
        """
        figures = []
        
        for block in blocks:
            text = block.text.strip()
            
            # Check if text matches figure caption patterns
            for pattern in self.figure_patterns:
                match = pattern.search(text)
                if match:
                    figure_number = match.group(0)
                    
                    # Create figure block
                    figure = FigureBlock(
                        x=block.x,
                        y=block.y,
                        width=block.width,
                        height=block.height,
                        page=page_num,
                        caption=text,
                        figure_number=figure_number,
                        bbox=(block.x, block.y, block.x + block.width, block.y + block.height)
                    )
                    
                    figures.append(figure)
                    break
        
        return figures
    
    def remove_figure_captions(self, blocks: List[TextBlock], figures: List[FigureBlock]) -> List[TextBlock]:
        """
        Remove figure caption blocks from text blocks.
        
        Args:
            blocks: List of text blocks
            figures: List of figure blocks
            
        Returns:
            Cleaned list of text blocks
        """
        figure_captions = {f.caption.strip() for f in figures if f.caption}
        
        cleaned_blocks = []
        for block in blocks:
            if block.text.strip() not in figure_captions:
                cleaned_blocks.append(block)
        
        return cleaned_blocks
    
    def blocks_from_dict(self, page_dict: Dict[str, Any]) -> List[TextBlock]:
        """
        Create TextBlock objects from a PyMuPDF dict output.
        
        This is a pure function for testing without PDF files.
        
        Args:
            page_dict: Dictionary from PyMuPDF get_text("dict")
            
        Returns:
            List of TextBlock objects
        """
        blocks = []
        
        if "blocks" not in page_dict:
            return blocks
        
        for block in page_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_block = TextBlock(
                            x=span["bbox"][0],
                            y=span["bbox"][1],
                            width=span["bbox"][2] - span["bbox"][0],
                            height=span["bbox"][3] - span["bbox"][1],
                            text=span["text"],
                            font_name=span.get("font", ""),
                            font_size=span.get("size", 0.0),
                            is_bold="bold" in span.get("font", "").lower(),
                            is_superscript=span.get("flags", 0) & 0x20 != 0,
                            is_italic="italic" in span.get("font", "").lower(),
                            type="text"
                        )
                        blocks.append(text_block)
        
        return blocks


def create_synthetic_page() -> Dict[str, Any]:
    """
    Create a synthetic page dictionary for testing.
    
    This creates a page with two columns, header, footer, and some text.
    
    Returns:
        Dictionary simulating PyMuPDF get_text("dict") output
    """
    return {
        "blocks": [
            # Header
            {
                "type": 0,
                "bbox": (50, 20, 550, 40),
                "lines": [
                    {
                        "spans": [
                            {
                                "bbox": (50, 20, 550, 40),
                                "text": "ASME BPVC VIII-1, 2025 Edition",
                                "font": "Helvetica-Bold",
                                "size": 12.0,
                                "flags": 0
                            }
                        ]
                    }
                ]
            },
            # Left column
            {
                "type": 0,
                "bbox": (50, 60, 250, 300),
                "lines": [
                    {
                        "spans": [
                            {
                                "bbox": (50, 60, 250, 80),
                                "text": "UG-37 Design",
                                "font": "Helvetica-Bold",
                                "size": 14.0,
                                "flags": 0
                            }
                        ]
                    },
                    {
                        "spans": [
                            {
                                "bbox": (50, 90, 250, 200),
                                "text": "The rules in this paragraph apply to vessels under vacuum.",
                                "font": "Helvetica",
                                "size": 10.0,
                                "flags": 0
                            }
                        ]
                    }
                ]
            },
            # Right column
            {
                "type": 0,
                "bbox": (300, 60, 550, 300),
                "lines": [
                    {
                        "spans": [
                            {
                                "bbox": (300, 60, 550, 80),
                                "text": "UG-38 External Pressure",
                                "font": "Helvetica-Bold",
                                "size": 14.0,
                                "flags": 0
                            }
                        ]
                    },
                    {
                        "spans": [
                            {
                                "bbox": (300, 90, 550, 200),
                                "text": "For vessels under external pressure, see Part UNC.",
                                "font": "Helvetica",
                                "size": 10.0,
                                "flags": 0
                            }
                        ]
                    }
                ]
            },
            # Footer
            {
                "type": 0,
                "bbox": (50, 750, 550, 780),
                "lines": [
                    {
                        "spans": [
                            {
                                "bbox": (50, 750, 550, 780),
                                "text": "Page 123 | Copyright ASME 2025",
                                "font": "Helvetica",
                                "size": 8.0,
                                "flags": 0
                            }
                        ]
                    }
                ]
            },
            # Watermark (diagonal)
            {
                "type": 0,
                "bbox": (200, 400, 400, 600),
                "lines": [
                    {
                        "spans": [
                            {
                                "bbox": (200, 400, 400, 600),
                                "text": "CONFIDENTIAL",
                                "font": "Helvetica",
                                "size": 60.0,
                                "flags": 0
                            }
                        ]
                    }
                ]
            },
            # Figure caption
            {
                "type": 0,
                "bbox": (50, 320, 250, 340),
                "lines": [
                    {
                        "spans": [
                            {
                                "bbox": (50, 320, 250, 340),
                                "text": "Fig. 1 Pressure-Volume Relationship",
                                "font": "Helvetica",
                                "size": 9.0,
                                "flags": 0
                            }
                        ]
                    }
                ]
            }
        ]
    }


# Test function for the module
if __name__ == '__main__':
    # Test with synthetic data
    from asme_rag.utils import get_config
    
    config = get_config()
    parser = PDFParser(config)
    
    # Test blocks_from_dict
    synthetic_page = create_synthetic_page()
    blocks = parser.blocks_from_dict(synthetic_page)
    
    print(f"Extracted {len(blocks)} text blocks from synthetic page")
    
    # Test sorting
    sorted_blocks = parser.sort_blocks_by_reading_order(blocks)
    print(f"Sorted blocks: {len(sorted_blocks)}")
    
    # Test header/footer removal
    cleaned_blocks = parser.remove_headers_footers_watermarks(sorted_blocks)
    print(f"Cleaned blocks (no headers/footers/watermarks): {len(cleaned_blocks)}")
    
    # Test figure detection
    figures = parser.detect_figures_from_text(sorted_blocks, 1)
    print(f"Detected figures: {len(figures)}")
    
    # Test figure caption removal
    final_blocks = parser.remove_figure_captions(sorted_blocks, figures)
    print(f"Final blocks (no figure captions): {len(final_blocks)}")
    
    print("\nPDF Parser tests completed successfully!")
