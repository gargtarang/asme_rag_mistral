"""
ASME RAG Cross-Reference Expansion Module

This module provides cross-reference expansion functionality for ASME documents.
It handles:
- Reference detection and parsing
- Depth-limited expansion (max depth = 1)
- Reference pack generation
- Rule map generation

The hard maximum depth is 1 (as specified in the requirements).
"""

import os
import sys
import re
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import Config, get_config, MAX_XREF_DEPTH
from asme_rag.storage import Storage


@dataclass
class Reference:
    """A cross-reference between documents or clauses."""
    
    from_chunk_id: str
    from_clause_id: str
    kind: str  # clause, table, figure, appendix, book, footnote, note
    target: str
    target_clause_id: Optional[str] = None
    target_doc_id: Optional[str] = None
    certainty: str = "certain"  # certain / fuzzy
    status: str = "resolved"  # resolved / unresolved
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'from_chunk_id': self.from_chunk_id,
            'from_clause_id': self.from_clause_id,
            'kind': self.kind,
            'target': self.target,
            'target_clause_id': self.target_clause_id,
            'target_doc_id': self.target_doc_id,
            'certainty': self.certainty,
            'status': self.status
        }


@dataclass
class ReferenceItem:
    """An item in the reference pack."""
    
    clause_id: str
    doc_id: str
    code: str
    division: str
    edition: int
    pdf_page: int
    type: str
    text: str
    level: int = 0  # 0 = anchor, 1 = referenced
    reason: str = ""
    why_included: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'clause_id': self.clause_id,
            'doc_id': self.doc_id,
            'code': self.code,
            'division': self.division,
            'edition': self.edition,
            'pdf_page': self.pdf_page,
            'type': self.type,
            'text': self.text,
            'level': self.level,
            'reason': self.reason,
            'why_included': self.why_included
        }


class CrossReferenceExpander:
    """
    Cross-reference expander for ASME documents.
    
    Provides:
    - Reference detection from text
    - Depth-limited expansion (max depth = 1)
    - Reference pack generation
    - Rule map generation
    """
    
    def __init__(self, config: Optional[Config] = None, storage: Optional[Storage] = None):
        """
        Initialize the cross-reference expander.
        
        Args:
            config: Configuration object
            storage: Storage instance
        """
        self.config = config or get_config()
        self.storage = storage or Storage(self.config)
        self.logger = logging.getLogger(__name__)
        
        # Compile reference patterns
        self.xref_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.xref_patterns
        ]
        
        # Additional patterns for cross-references
        self.additional_patterns = [
            re.compile(r'see\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'See\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'refer\s+to\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'Refer\s+to\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'per\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'Per\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'as\s+per\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'As\s+per\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'pursuant\s+to\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'Pursuant\s+to\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'in\s+accordance\s+with\s+([A-Z]+-\d+)', re.IGNORECASE),
            re.compile(r'In\s+accordance\s+with\s+([A-Z]+-\d+)', re.IGNORECASE),
            # Book references
            re.compile(r'Section\s+([IVXLCDM]+)', re.IGNORECASE),
            re.compile(r'Part\s+([A-Z]+)', re.IGNORECASE),
            re.compile(r'Appendix\s+(\d+)', re.IGNORECASE),
            # Figure and table references
            re.compile(r'Figure\s+(\d+)', re.IGNORECASE),
            re.compile(r'Fig\.?\s*(\d+)', re.IGNORECASE),
            re.compile(r'Table\s+([A-Z0-9]+)', re.IGNORECASE),
            # Range references
            re.compile(r'([A-Z]+-\d+)\s+through\s+([A-Z]+-\d+)', re.IGNORECASE),
        ]
        
        # Patterns for footnotes
        self.footnote_patterns = [
            re.compile(r'\[\d+\]', re.IGNORECASE),
            re.compile(r'\*', re.IGNORECASE),
        ]
    
    def expand(self, clause_id: str, doc_id: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Expand cross-references for a clause.
        
        Args:
            clause_id: Clause identifier to expand
            doc_id: Optional document ID to limit search
            
        Returns:
            Dictionary with levels as keys and lists of items as values
        """
        # Level 0: anchor clauses
        level_0 = self.get_anchor_clauses(clause_id, doc_id)
        
        # Level 1: everything the anchors directly refer to
        level_1 = []
        unresolved = []
        
        for anchor in level_0:
            refs = self.get_references_from_clause(anchor.clause_id, anchor.doc_id)
            for ref in refs:
                if ref.status == 'resolved':
                    # Get the target chunk
                    target_chunk = self.get_chunk_by_clause(ref.target_clause_id or ref.target, 
                                                           ref.target_doc_id or anchor.doc_id)
                    if target_chunk:
                        level_1.append(target_chunk)
                    else:
                        # Target exists but not in our database
                        unresolved.append(f"NOT INGESTED: {ref.target_doc_id or anchor.doc_id}, {ref.target_clause_id or ref.target}")
                else:
                    unresolved.append(f"NOT INGESTED: {ref.target_doc_id or anchor.doc_id}, {ref.target_clause_id or ref.target}")
        
        # Get further references (not expanded)
        further_refs = self.get_further_references(level_1)
        
        return {
            'Level 0 (Anchor clauses)': [self.format_clause(c) for c in level_0],
            'Level 1 (Direct references)': [self.format_clause(c) for c in level_1],
            'Further references (not expanded)': further_refs,
            'Unresolved': unresolved
        }
    
    def get_anchor_clauses(self, clause_id: str, doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get anchor clauses for expansion.
        
        Args:
            clause_id: Clause identifier
            doc_id: Optional document ID
            
        Returns:
            List of chunk dictionaries
        """
        if doc_id:
            chunks = self.storage.get_chunks_by_clause(clause_id)
            chunks = [c for c in chunks if c.get('doc_id') == doc_id]
        else:
            chunks = self.storage.get_chunks_by_clause(clause_id)
        
        return chunks
    
    def get_references_from_clause(self, clause_id: str, doc_id: str) -> List[Reference]:
        """
        Get references from a clause.
        
        Args:
            clause_id: Clause identifier
            doc_id: Document ID
            
        Returns:
            List of Reference objects
        """
        references = []
        
        # Get chunks for this clause
        chunks = self.storage.get_chunks_by_clause(clause_id)
        chunks = [c for c in chunks if c.get('doc_id') == doc_id]
        
        for chunk in chunks:
            text = chunk.get('text', '')
            chunk_id = chunk.get('chunk_id', '')
            
            # Parse references from text
            refs = self.parse_references(text, chunk_id, clause_id, doc_id)
            references.extend(refs)
        
        return references
    
    def parse_references(self, text: str, from_chunk_id: str, from_clause_id: str, 
                        from_doc_id: str) -> List[Reference]:
        """
        Parse references from text.
        
        Args:
            text: Text to parse
            from_chunk_id: Source chunk ID
            from_clause_id: Source clause ID
            from_doc_id: Source document ID
            
        Returns:
            List of Reference objects
        """
        references = []
        
        # Check all patterns
        all_patterns = self.xref_patterns + self.additional_patterns
        
        for pattern in all_patterns:
            for match in pattern.finditer(text):
                target = match.group(1) if match.groups() else match.group(0)
                
                # Determine kind
                kind = self.determine_reference_kind(target, text)
                
                # Check if this is a range
                if 'through' in text.lower() and len(match.groups()) >= 2:
                    start_target = match.group(1)
                    end_target = match.group(2)
                    
                    # Create references for the range
                    ref = Reference(
                        from_chunk_id=from_chunk_id,
                        from_clause_id=from_clause_id,
                        kind='range',
                        target=f"{start_target} through {end_target}",
                        target_clause_id=start_target,
                        target_doc_id=from_doc_id,
                        certainty='certain',
                        status='resolved'
                    )
                    references.append(ref)
                else:
                    ref = Reference(
                        from_chunk_id=from_chunk_id,
                        from_clause_id=from_clause_id,
                        kind=kind,
                        target=target,
                        target_clause_id=target if kind in ['clause', 'paragraph'] else None,
                        target_doc_id=from_doc_id,
                        certainty='certain',
                        status=self.check_reference_resolved(target, from_doc_id)
                    )
                    references.append(ref)
        
        # Check for footnotes
        footnote_refs = self.parse_footnotes(text, from_chunk_id, from_clause_id, from_doc_id)
        references.extend(footnote_refs)
        
        return references
    
    def determine_reference_kind(self, target: str, context: str) -> str:
        """
        Determine the kind of reference.
        
        Args:
            target: Target identifier
            context: Context text
            
        Returns:
            Reference kind string
        """
        target_upper = target.upper()
        context_lower = context.lower()
        
        # Check for clause/paragraph
        if re.match(r'^[A-Z]+-\d+$', target_upper):
            return 'clause'
        
        # Check for appendix
        if target_upper.startswith('APPENDIX') or 'APPENDIX' in target_upper:
            return 'appendix'
        
        # Check for part
        if target_upper.startswith('PART') or 'PART' in target_upper:
            return 'part'
        
        # Check for section
        if target_upper.startswith('SECTION') or 'SECTION' in target_upper:
            return 'book'
        
        # Check for figure
        if (target_upper.startswith('FIG') or target_upper.startswith('FIGURE') or
            'FIG' in target_upper or 'FIGURE' in target_upper):
            return 'figure'
        
        # Check for table
        if (target_upper.startswith('TABLE') or 'TABLE' in target_upper or
            'T-' in target_upper):
            return 'table'
        
        # Check for division
        if re.match(r'^[IVXLCDM]+$', target_upper):
            return 'division'
        
        # Default to clause
        return 'clause'
    
    def check_reference_resolved(self, target: str, from_doc_id: str) -> str:
        """
        Check if a reference can be resolved.
        
        Args:
            target: Target identifier
            from_doc_id: Source document ID
            
        Returns:
            Status ('resolved' or 'unresolved')
        """
        # Check if target is in the same document
        target_clause_chunks = self.storage.get_chunks_by_clause(target)
        for chunk in target_clause_chunks:
            if chunk.get('doc_id') == from_doc_id:
                return 'resolved'
        
        # Check if target document is ingested
        target_doc_id = self.get_doc_id_for_reference(target)
        if target_doc_id:
            for doc in self.config.documents:
                if doc.get('id') == target_doc_id:
                    return 'resolved'
        
        return 'unresolved'
    
    def get_doc_id_for_reference(self, target: str) -> Optional[str]:
        """
        Get document ID for a reference target.
        
        Args:
            target: Target identifier
            
        Returns:
            Document ID or None
        """
        target_upper = target.upper()
        
        # Map reference to document
        ref_mappings = {
            'VIII-1': 'viii1_2025',
            'VIII-2': 'viii2_2025',
            'SECTION II-D': 'iid_metric_2025',
            'II-D': 'iid_metric_2025',
            'SECTION II-A': 'iia_v1_2025',
            'II-A': 'iia_v1_2025',
            'B16.5': 'b16_5_2025',
            'B36.10': 'b36_10_2022',
        }
        
        for ref_text, doc_id in ref_mappings.items():
            if ref_text in target_upper:
                return doc_id
        
        return None
    
    def get_chunk_by_clause(self, clause_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a chunk by clause ID and document ID.
        
        Args:
            clause_id: Clause identifier
            doc_id: Document ID
            
        Returns:
            Chunk dictionary or None
        """
        chunks = self.storage.get_chunks_by_clause(clause_id)
        for chunk in chunks:
            if chunk.get('doc_id') == doc_id:
                return chunk
        return None
    
    def get_further_references(self, level_1_chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Get further references from level 1 chunks (not expanded).
        
        Args:
            level_1_chunks: List of level 1 chunk dictionaries
            
        Returns:
            List of further reference strings
        """
        further_refs = []
        seen_refs = set()
        
        for chunk in level_1_chunks:
            text = chunk.get('text', '')
            refs = self.parse_references(
                text, 
                chunk.get('chunk_id', ''), 
                chunk.get('clause_id', ''), 
                chunk.get('doc_id', '')
            )
            
            for ref in refs:
                ref_str = f"{ref.target} ({ref.kind})"
                if ref_str not in seen_refs:
                    seen_refs.add(ref_str)
                    further_refs.append(ref_str)
        
        return further_refs
    
    def format_clause(self, chunk: Dict[str, Any]) -> str:
        """
        Format a clause for display.
        
        Args:
            chunk: Chunk dictionary
            
        Returns:
            Formatted string
        """
        code = chunk.get('code', 'unknown')
        edition = chunk.get('edition', 0)
        clause_id = chunk.get('clause_id', 'unknown')
        page = chunk.get('pdf_page', 0)
        type_ = chunk.get('type', 'text')
        
        return f"[{code}, {edition}, {clause_id}, PDF p.{page}] ({type_})"
    
    def generate_rulemap(self, topic: str) -> Dict[str, List[str]]:
        """
        Generate a rule map for a design topic.
        
        Args:
            topic: Design topic
            
        Returns:
            Dictionary with rule map sections
        """
        rulemap = {
            'Governing clauses': [],
            'Direct references': [],
            'Inputs required': [],
            'Tables and charts needed': [],
            'Cross-book first hops': [],
            'NEEDS INPUT': []
        }
        
        # Search for the topic
        results = self.storage.search_chunks(topic)
        
        if not results:
            rulemap['NEEDS INPUT'].append(f"No clauses found for topic: {topic}")
            return rulemap
        
        # Process results
        governing_clauses = []
        for result in results:
            governing_clauses.append(self.format_clause(result))
        
        rulemap['Governing clauses'] = governing_clauses
        
        # Get references for each governing clause
        all_refs = set()
        for result in results:
            refs = self.get_references_from_clause(
                result.get('clause_id', ''),
                result.get('doc_id', '')
            )
            
            for ref in refs:
                ref_str = f"{ref.target} ({ref.kind})"
                if ref_str not in all_refs:
                    all_refs.add(ref_str)
                    
                    if ref.status == 'resolved':
                        rulemap['Direct references'].append(ref_str)
                    else:
                        rulemap['Cross-book first hops'].append(f"NOT INGESTED: {ref_str}")
        
        # Identify tables and charts
        for result in results:
            if result.get('type') in ['table', 'figure_caption']:
                ref_str = f"{result.get('clause_id')} (p.{result.get('pdf_page')})"
                if ref_str not in rulemap['Tables and charts needed']:
                    rulemap['Tables and charts needed'].append(ref_str)
        
        # Check for missing information
        if not governing_clauses:
            rulemap['NEEDS INPUT'].append(f"No governing clauses found for: {topic}")
        
        if not all_refs:
            rulemap['NEEDS INPUT'].append(f"No references found for: {topic}")
        
        return rulemap
    
    def parse_footnotes(self, text: str, from_chunk_id: str, from_clause_id: str, 
                       from_doc_id: str) -> List[Reference]:
        """
        Parse footnote references from text.
        
        Args:
            text: Text to parse
            from_chunk_id: Source chunk ID
            from_clause_id: Source clause ID
            from_doc_id: Source document ID
            
        Returns:
            List of Reference objects for footnotes
        """
        footnotes = []
        
        for pattern in self.footnote_patterns:
            for match in pattern.finditer(text):
                footnote_num = match.group(0)
                
                ref = Reference(
                    from_chunk_id=from_chunk_id,
                    from_clause_id=from_clause_id,
                    kind='footnote',
                    target=footnote_num,
                    target_clause_id=None,
                    target_doc_id=from_doc_id,
                    certainty='fuzzy',
                    status='resolved'  # Footnotes are part of the same document
                )
                footnotes.append(ref)
        
        return footnotes


# Test function for the module
if __name__ == '__main__':
    from asme_rag.utils import get_config
    from asme_rag.storage import Storage
    
    config = get_config()
    storage = Storage(config)
    xref_expander = CrossReferenceExpander(config, storage)
    
    print("Testing cross-reference expansion...")
    
    # Test reference parsing
    test_text = "See UG-37 for design rules. Refer to Part UNC for non-circular vessels. " \
                "See Figure 1 and Table 2-1. [1]"
    
    refs = xref_expander.parse_references(
        test_text, "test_chunk", "test_clause", "viii1_2025"
    )
    
    print(f"Parsed {len(refs)} references from test text")
    for ref in refs:
        print(f"  {ref.kind}: {ref.target} ({ref.status})")
    
    # Test reference kind detection
    kinds = [
        ("UG-37", "clause"),
        ("Appendix 1", "appendix"),
        ("Part UNC", "part"),
        ("Section II-D", "book"),
        ("Figure 1", "figure"),
        ("Table 2-1", "table")
    ]
    
    print("\nTesting reference kind detection:")
    for target, expected_kind in kinds:
        actual_kind = xref_expander.determine_reference_kind(target, f"see {target}")
        status = "OK" if actual_kind == expected_kind else "FAIL"
        print(f"  {target} -> {actual_kind} (expected {expected_kind}) [{status}]")
    
    print("\nCross-reference expansion tests completed!")
