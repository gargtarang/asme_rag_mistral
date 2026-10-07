"""
ASME RAG Chunker Module

This module provides functionality to split parsed PDF text into meaningful chunks
with proper metadata. It handles:
- Clause boundary detection
- Long clause splitting
- Profile-specific chunking (code_book, materials_data, material_specs, standard)
- Metadata preservation
"""

import os
import sys
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import Config, get_config, ChunkMetadata
from asme_rag.pdf_parser import TextBlock, PageData


@dataclass
class Chunk:
    """A chunk of text with metadata."""
    
    text: str
    metadata: ChunkMetadata
    
    def __post_init__(self):
        if not self.metadata.text:
            self.metadata.text = self.text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'text': self.text,
            'metadata': self.metadata.to_dict()
        }


class Chunker:
    """
    Chunker for ASME documents.
    
    Splits parsed text into meaningful chunks based on document profile.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the chunker.
        
        Args:
            config: Configuration object
        """
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # Compile clause patterns
        self.clause_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.clause_patterns
        ]
        
        # Profile-specific configurations
        self.profile_configs = {
            'code_book': {
                'chunk_size': self.config.target_chunk_size,
                'min_chunk_size': self.config.min_chunk_size,
                'max_chunk_size': self.config.max_chunk_size,
                'overlap': self.config.chunk_overlap,
                'split_at_clauses': True
            },
            'materials_data': {
                'chunk_size': self.config.target_chunk_size * 2,  # Larger for tables
                'min_chunk_size': self.config.min_chunk_size,
                'max_chunk_size': self.config.max_chunk_size * 2,
                'overlap': self.config.chunk_overlap,
                'split_at_clauses': False,
                'table_centric': True
            },
            'material_specs': {
                'chunk_size': self.config.target_chunk_size,
                'min_chunk_size': self.config.min_chunk_size,
                'max_chunk_size': self.config.max_chunk_size,
                'overlap': self.config.chunk_overlap,
                'split_at_clauses': True
            },
            'standard': {
                'chunk_size': self.config.target_chunk_size,
                'min_chunk_size': self.config.min_chunk_size,
                'max_chunk_size': self.config.max_chunk_size,
                'overlap': self.config.chunk_overlap,
                'split_at_clauses': False,
                'table_centric': True
            }
        }
    
    def chunk(self, parsed_data: Dict[str, Any], doc: Dict[str, Any]) -> List[ChunkMetadata]:
        """
        Chunk parsed data from a document.
        
        Args:
            parsed_data: Parsed PDF data from pdf_parser
            doc: Document metadata
            
        Returns:
            List of ChunkMetadata objects
        """
        doc_id = doc.get('id', 'unknown')
        code = doc.get('code', 'unknown')
        division = doc.get('division', '')
        edition = doc.get('edition', 0)
        parser_profile = doc.get('parser_profile', 'code_book')
        chunker_profile = doc.get('chunker_profile', parser_profile)
        
        self.logger.info(f"Chunking document {doc_id} with profile {chunker_profile}")
        
        chunks = []
        
        # Get profile configuration
        profile_config = self.profile_configs.get(chunker_profile, self.profile_configs['code_book'])
        
        # Process each page
        pages = parsed_data.get('pages', [])
        for page_data_dict in pages:
            page_data = self._from_dict(page_data_dict)
            page_chunks = self.chunk_page(page_data, doc, profile_config)
            chunks.extend(page_chunks)
        
        self.logger.info(f"Created {len(chunks)} chunks for {doc_id}")
        return chunks
    
    def _from_dict(self, data: Dict[str, Any]) -> PageData:
        """Convert dictionary to PageData object."""
        page_data = PageData(
            page_number=data.get('page_number', 0),
            width=data.get('width', 0),
            height=data.get('height', 0)
        )
        
        for block_dict in data.get('blocks', []):
            block = TextBlock(
                x=block_dict.get('x', 0),
                y=block_dict.get('y', 0),
                width=block_dict.get('width', 0),
                height=block_dict.get('height', 0),
                text=block_dict.get('text', ''),
                font_name=block_dict.get('font_name', ''),
                font_size=block_dict.get('font_size', 0),
                is_bold=block_dict.get('is_bold', False),
                is_superscript=block_dict.get('is_superscript', False),
                is_italic=block_dict.get('is_italic', False),
                type=block_dict.get('type', 'text'),
                page=block_dict.get('page', 0),
                block_id=block_dict.get('block_id', '')
            )
            page_data.blocks.append(block)
        
        for figure_dict in data.get('figures', []):
            # Figures are handled separately
            pass
        
        return page_data
    
    def chunk_page(self, page_data: PageData, doc: Dict[str, Any], 
                   profile_config: Dict[str, Any]) -> List[ChunkMetadata]:
        """
        Chunk a single page.
        
        Args:
            page_data: Page data
            doc: Document metadata
            profile_config: Profile configuration
            
        Returns:
            List of ChunkMetadata objects
        """
        chunks = []
        
        # Group blocks by clause/section
        clause_groups = self.group_blocks_by_clause(page_data.blocks)
        
        for clause_id, blocks in clause_groups.items():
            # Combine text from all blocks in this clause
            full_text = self.combine_blocks_text(blocks)
            
            # Determine chunk type
            chunk_type = self.detect_chunk_type(blocks, clause_id)
            
            # Create metadata
            metadata = ChunkMetadata(
                doc_id=doc.get('id', 'unknown'),
                code=doc.get('code', 'unknown'),
                division=doc.get('division', ''),
                edition=doc.get('edition', 0),
                part_or_subsection=self.extract_part(clause_id),
                clause_id=clause_id,
                pdf_page=page_data.page_number,
                type=chunk_type,
                model_generated=False,
                verified=False,
                status=self.detect_status(clause_id),
                heading_path=self.extract_heading_path(blocks),
                bold_flags=self.extract_bold_flags(blocks),
                text=full_text
            )
            
            # Check if text is too long and needs splitting
            if len(full_text) > profile_config['max_chunk_size']:
                # Split long clauses at sub-paragraph boundaries
                sub_chunks = self.split_long_text(full_text, metadata, profile_config)
                chunks.extend(sub_chunks)
            else:
                chunks.append(metadata)
        
        return chunks
    
    def group_blocks_by_clause(self, blocks: List[TextBlock]) -> Dict[str, List[TextBlock]]:
        """
        Group text blocks by clause/section.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Dictionary mapping clause ID to list of blocks
        """
        groups = {}
        current_clause = None
        
        for block in blocks:
            # Check if this block starts a new clause
            clause_id = self.detect_clause_id(block.text)
            
            if clause_id:
                current_clause = clause_id
            
            if current_clause is None:
                current_clause = "_unknown_"
            
            if current_clause not in groups:
                groups[current_clause] = []
            
            groups[current_clause].append(block)
        
        return groups
    
    def detect_clause_id(self, text: str) -> Optional[str]:
        """
        Detect clause ID from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Detected clause ID or None
        """
        text = text.strip()
        
        for pattern in self.clause_patterns:
            match = pattern.match(text)
            if match:
                return match.group(0)
        
        # Check for common ASME clause patterns
        asme_patterns = [
            r'^UG-\d+',
            r'^UW-\d+',
            r'^UNF-\d+',
            r'^UNC-\d+',
            r'^UJV-\d+',
            r'^Appendix\s+\d+',
            r'^Part\s+[A-Z]+',
            r'^Subsection\s+[A-Z]+',
            r'^Paragraph\s+[A-Z0-9]+',
            r'^\d+\.\d+',
            r'^\d+\.\d+\.\d+'
        ]
        
        for pattern in asme_patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def combine_blocks_text(self, blocks: List[TextBlock]) -> str:
        """
        Combine text from multiple blocks.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Combined text
        """
        texts = [block.text for block in blocks if block.text.strip()]
        return ' '.join(texts)
    
    def detect_chunk_type(self, blocks: List[TextBlock], clause_id: str) -> str:
        """
        Detect the type of chunk.
        
        Args:
            blocks: List of text blocks
            clause_id: Clause identifier
            
        Returns:
            Chunk type string
        """
        # Check if this is a table
        for block in blocks:
            if any(pattern.search(block.text) for pattern in self.config.table_patterns):
                return "table"
        
        # Check if this is a figure caption
        for block in blocks:
            if any(pattern.search(block.text) for pattern in self.config.figure_patterns):
                return "figure_caption"
        
        # Check if this is an equation
        for block in blocks:
            if self.is_equation(block.text):
                return "equation"
        
        # Check if this is a footnote (superscript)
        if any(block.is_superscript for block in blocks):
            return "footnote"
        
        # Check if this is a note
        if clause_id and (clause_id.upper().startswith('NOTE') or 
                         'note' in clause_id.lower()):
            return "note"
        
        return "text"
    
    def is_equation(self, text: str) -> bool:
        """
        Check if text appears to be an equation.
        
        Args:
            text: Text to check
            
        Returns:
            True if text appears to be an equation
        """
        # Look for common equation patterns
        equation_patterns = [
            r'=[^=]+=',  # Contains equals sign
            r'\\frac',  # LaTeX fraction
            r'\\sum',   # LaTeX sum
            r'\\int',   # LaTeX integral
            r'\\sqrt',  # LaTeX square root
            r'[αβγδ∂∫√≤≥≈≠]',  # Common math symbols
            r'\d+\.?\d*\s*[×•*]\s*\d+\.?\d*'  # Number multiplication
        ]
        
        for pattern in equation_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def extract_part(self, clause_id: str) -> str:
        """
        Extract part or subsection from clause ID.
        
        Args:
            clause_id: Clause identifier
            
        Returns:
            Part or subsection name
        """
        if not clause_id:
            return ""
        
        # Extract part from clause ID
        parts = clause_id.split('-')
        if len(parts) >= 2:
            prefix = parts[0]
            if prefix in ['UG', 'UW', 'UNF', 'UNC', 'UJV']:
                return f"Part {prefix}"
        
        # Check for Appendix
        if clause_id.upper().startswith('APPENDIX'):
            return clause_id
        
        # Check for Part
        if clause_id.upper().startswith('PART'):
            return clause_id
        
        # Check for Subsection
        if clause_id.upper().startswith('SUBSECTION'):
            return clause_id
        
        return ""
    
    def detect_status(self, clause_id: str) -> str:
        """
        Detect the status of a clause (mandatory/non-mandatory/supplementary).
        
        Args:
            clause_id: Clause identifier
            
        Returns:
            Status string
        """
        if not clause_id:
            return "mandatory"
        
        # Non-mandatory appendices
        if clause_id.upper().startswith('APPENDIX') and not clause_id.upper().startswith('APPENDIX MANDATORY'):
            return "non-mandatory"
        
        # Supplementary
        if 'ANNEX' in clause_id.upper() or 'SUPPLEMENT' in clause_id.upper():
            return "supplementary"
        
        return "mandatory"
    
    def extract_heading_path(self, blocks: List[TextBlock]) -> str:
        """
        Extract the heading path from blocks.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Heading path string
        """
        headings = []
        
        for block in blocks:
            if block.is_bold and block.font_size > 10:  # Bold and larger font
                heading = block.text.strip()
                if heading:
                    headings.append(heading)
        
        return ' > '.join(headings) if headings else ""
    
    def extract_bold_flags(self, blocks: List[TextBlock]) -> str:
        """
        Extract bold flags from blocks.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            String indicating bold text positions
        """
        bold_positions = []
        
        for i, block in enumerate(blocks):
            if block.is_bold:
                bold_positions.append(str(i))
        
        return ','.join(bold_positions) if bold_positions else ""
    
    def split_long_text(self, text: str, metadata: ChunkMetadata, 
                       profile_config: Dict[str, Any]) -> List[ChunkMetadata]:
        """
        Split long text at sub-paragraph boundaries.
        
        Args:
            text: Text to split
            metadata: Original metadata
            profile_config: Profile configuration
            
        Returns:
            List of ChunkMetadata objects for sub-chunks
        """
        chunks = []
        
        # Split at sentence boundaries that are followed by a newline or period
        # Try to split at paragraph breaks first
        paragraphs = re.split(r'\n\n+', text)
        
        if len(paragraphs) > 1:
            # Split into paragraphs
            for i, para in enumerate(paragraphs):
                if para.strip():
                    sub_metadata = ChunkMetadata(
                        doc_id=metadata.doc_id,
                        code=metadata.code,
                        division=metadata.division,
                        edition=metadata.edition,
                        part_or_subsection=metadata.part_or_subsection,
                        clause_id=f"{metadata.clause_id}_{i+1}" if len(paragraphs) > 1 else metadata.clause_id,
                        pdf_page=metadata.pdf_page,
                        type=metadata.type,
                        model_generated=metadata.model_generated,
                        verified=metadata.verified,
                        status=metadata.status,
                        heading_path=metadata.heading_path,
                        bold_flags=metadata.bold_flags,
                        text=para.strip()
                    )
                    chunks.append(sub_metadata)
        else:
            # If no paragraph breaks, split at sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', text)
            
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < profile_config['max_chunk_size']:
                    current_chunk += (" " + sentence if current_chunk else sentence)
                else:
                    if current_chunk.strip():
                        sub_metadata = ChunkMetadata(
                            doc_id=metadata.doc_id,
                            code=metadata.code,
                            division=metadata.division,
                            edition=metadata.edition,
                            part_or_subsection=metadata.part_or_subsection,
                            clause_id=metadata.clause_id,
                            pdf_page=metadata.pdf_page,
                            type=metadata.type,
                            model_generated=metadata.model_generated,
                            verified=metadata.verified,
                            status=metadata.status,
                            heading_path=metadata.heading_path,
                            bold_flags=metadata.bold_flags,
                            text=current_chunk.strip()
                        )
                        chunks.append(sub_metadata)
                    current_chunk = sentence
            
            # Add remaining text
            if current_chunk.strip():
                sub_metadata = ChunkMetadata(
                    doc_id=metadata.doc_id,
                    code=metadata.code,
                    division=metadata.division,
                    edition=metadata.edition,
                    part_or_subsection=metadata.part_or_subsection,
                    clause_id=metadata.clause_id,
                    pdf_page=metadata.pdf_page,
                    type=metadata.type,
                    model_generated=metadata.model_generated,
                    verified=metadata.verified,
                    status=metadata.status,
                    heading_path=metadata.heading_path,
                    bold_flags=metadata.bold_flags,
                    text=current_chunk.strip()
                )
                chunks.append(sub_metadata)
        
        return chunks if chunks else [metadata]
    
    def chunk_materials_data(self, parsed_data: Dict[str, Any], doc: Dict[str, Any]) -> List[ChunkMetadata]:
        """
        Special chunking for materials data (Section II-D).
        
        Args:
            parsed_data: Parsed PDF data
            doc: Document metadata
            
        Returns:
            List of ChunkMetadata objects
        """
        chunks = []
        
        pages = parsed_data.get('pages', [])
        for page_data_dict in pages:
            page_data = self._from_dict(page_data_dict)
            
            # Detect tables in the page
            tables = self.detect_tables(page_data.blocks)
            
            for table in tables:
                # Each table is a chunk
                table_chunk = ChunkMetadata(
                    doc_id=doc.get('id', 'unknown'),
                    code=doc.get('code', 'unknown'),
                    division=doc.get('division', ''),
                    edition=doc.get('edition', 0),
                    part_or_subsection="",
                    clause_id=table.get('table_number', f"table_{page_data.page_number}"),
                    pdf_page=page_data.page_number,
                    type="table",
                    model_generated=False,
                    verified=False,
                    status="mandatory",
                    text=table.get('text', '')
                )
                chunks.append(table_chunk)
            
            # Handle non-table text
            non_table_blocks = [b for b in page_data.blocks if not self.is_table_block(b)]
            
            if non_table_blocks:
                # Group remaining text
                clause_groups = self.group_blocks_by_clause(non_table_blocks)
                
                for clause_id, blocks in clause_groups.items():
                    full_text = self.combine_blocks_text(blocks)
                    chunk_type = self.detect_chunk_type(blocks, clause_id)
                    
                    metadata = ChunkMetadata(
                        doc_id=doc.get('id', 'unknown'),
                        code=doc.get('code', 'unknown'),
                        division=doc.get('division', ''),
                        edition=doc.get('edition', 0),
                        part_or_subsection=self.extract_part(clause_id),
                        clause_id=clause_id,
                        pdf_page=page_data.page_number,
                        type=chunk_type,
                        model_generated=False,
                        verified=False,
                        status=self.detect_status(clause_id),
                        heading_path=self.extract_heading_path(blocks),
                        bold_flags=self.extract_bold_flags(blocks),
                        text=full_text
                    )
                    
                    chunks.append(metadata)
        
        return chunks
    
    def detect_tables(self, blocks: List[TextBlock]) -> List[Dict[str, Any]]:
        """
        Detect tables in text blocks.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            List of table dictionaries
        """
        tables = []
        current_table = None
        
        for block in blocks:
            # Check if this block is part of a table
            if self.is_table_block(block):
                if current_table is None:
                    current_table = {
                        'blocks': [],
                        'text': '',
                        'table_number': self.detect_table_number(block.text)
                    }
                
                current_table['blocks'].append(block)
                current_table['text'] += (" " + block.text if current_table['text'] else block.text)
            else:
                if current_table is not None:
                    tables.append(current_table)
                    current_table = None
        
        # Don't forget the last table
        if current_table is not None:
            tables.append(current_table)
        
        return tables
    
    def is_table_block(self, block: TextBlock) -> bool:
        """
        Check if a block is part of a table.
        
        Args:
            block: Text block
            
        Returns:
            True if block appears to be part of a table
        """
        # Check if text matches table patterns
        for pattern in self.config.table_patterns:
            if pattern.search(block.text):
                return True
        
        # Check for table-like formatting (small font, aligned text)
        if block.font_size < 9 and len(block.text.strip()) > 10:
            return True
        
        # Check for numeric data patterns
        numeric_patterns = [
            r'^\d+\.\d+\s+\d+\.\d+',
            r'^\d+\s+\d+\s+\d+',
            r'^[\d.]+\s+[\d.]+\s+[\d.]+'
        ]
        
        for pattern in numeric_patterns:
            if re.match(pattern, block.text.strip()):
                return True
        
        return False
    
    def detect_table_number(self, text: str) -> str:
        """
        Detect table number from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Table number string
        """
        for pattern in self.config.table_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0)
        
        return ""


# Test function for the module
if __name__ == '__main__':
    from asme_rag.utils import get_config
    from asme_rag.pdf_parser import create_synthetic_page
    
    config = get_config()
    chunker = Chunker(config)
    
    # Test with synthetic data
    synthetic_data = {
        'pdf_path': 'test.pdf',
        'total_pages': 1,
        'pages': [create_synthetic_page()]
    }
    
    doc = {
        'id': 'test_doc',
        'code': 'ASME BPVC',
        'division': 'VIII-1',
        'edition': 2025,
        'parser_profile': 'code_book',
        'chunker_profile': 'code_book'
    }
    
    chunks = chunker.chunk(synthetic_data, doc)
    
    print(f"Created {len(chunks)} chunks from synthetic data")
    
    for i, chunk in enumerate(chunks, 1):
        print(f"\nChunk {i}:")
        print(f"  Clause: {chunk.clause_id}")
        print(f"  Type: {chunk.type}")
        print(f"  Text: {chunk.text[:100]}...")
        print(f"  Page: {chunk.pdf_page}")
    
    print("\nChunker module tests completed successfully!")
