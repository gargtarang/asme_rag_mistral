"""
Chamber Design Lookup Functions

This module provides data lookup functions for:
- Allowable stress values (from Section II-D)
- Pipe dimensions (from B36.10)
- Flange ratings and dimensions (from B16.5)
- Material specifications (from Section II-A)

All lookups return CANDIDATE values with citations.
Values must be confirmed by the user before use.
"""

import os
import sys
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import Config, get_config
from asme_rag.rag import RAGSystem
from asme_rag.storage import Storage


@dataclass
class LookupResult:
    """Result from a data lookup."""
    
    value: Any
    citation: str
    source: str
    pdf_page: int
    table_number: str = ""
    table_notes: str = ""
    verified: bool = False
    candidate: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'value': self.value,
            'citation': self.citation,
            'source': self.source,
            'pdf_page': self.pdf_page,
            'table_number': self.table_number,
            'table_notes': self.table_notes,
            'verified': self.verified,
            'candidate': self.candidate
        }


class Lookups:
    """
    Data lookup functions for chamber design.
    
    Provides:
    - allowable_lookup: Allowable stress from Section II-D
    - pipe_lookup: Pipe dimensions from B36.10
    - flange_lookup: Flange ratings from B16.5
    - material_spec_lookup: Material specifications from Section II-A
    """
    
    def __init__(self, config: Optional[Config] = None, storage: Optional[Storage] = None):
        """
        Initialize the lookups.
        
        Args:
            config: Configuration object
            storage: Storage instance
        """
        self.config = config or get_config()
        self.storage = storage or Storage(self.config)
        self.rag_system = RAGSystem(self.config, self.storage)
        self.logger = logging.getLogger(__name__)
    
    def allowable_lookup(self, spec: str, grade: str, product_form: str, 
                        temperature: float) -> List[LookupResult]:
        """
        Look up allowable stress for a material.
        
        Args:
            spec: Material specification (e.g., "SA-240")
            grade: Material grade (e.g., "304L")
            product_form: Product form (e.g., "plate")
            temperature: Design temperature in degC
            
        Returns:
            List of LookupResult objects (may contain multiple values with notes)
        """
        results = []
        
        # Search for the material in Section II-D
        query = f"{spec} {grade} {product_form}"
        filters = {
            'division': 'II-D',
            'type': 'table'
        }
        
        chunks = self.storage.search_chunks(query, filters)
        
        if not chunks:
            # Try without product form
            query = f"{spec} {grade}"
            chunks = self.storage.search_chunks(query, filters)
        
        if not chunks:
            # Try just the grade
            query = grade
            chunks = self.storage.search_chunks(query, filters)
        
        # Process chunks to find stress values
        for chunk in chunks:
            text = chunk.get('text', '')
            
            # Look for stress values in the text
            stress_values = self.extract_stress_values(text, temperature)
            
            for value, table_number, table_notes in stress_values:
                result = LookupResult(
                    value=value,
                    citation=f"[{chunk.get('code')}, {chunk.get('edition')}, {chunk.get('clause_id')}, PDF p.{chunk.get('pdf_page')}]",
                    source=f"{chunk.get('code')} {chunk.get('division')}",
                    pdf_page=chunk.get('pdf_page', 0),
                    table_number=table_number or chunk.get('clause_id', ''),
                    table_notes=table_notes,
                    verified=False,
                    candidate=True
                )
                results.append(result)
        
        if not results:
            # Return a NEEDS INPUT message
            result = LookupResult(
                value=None,
                citation="",
                source="",
                pdf_page=0,
                table_number="",
                table_notes="NEEDS INPUT: Allowable stress not found for "
                           f"{spec} {grade} {product_form} at {temperature}°C. "
                           f"Check Section II-D tables.",
                verified=False,
                candidate=False
            )
            results.append(result)
        
        return results
    
    def extract_stress_values(self, text: str, temperature: float) -> List[Tuple[float, str, str]]:
        """
        Extract stress values from text for a given temperature.
        
        Args:
            text: Text to search
            temperature: Design temperature
            
        Returns:
            List of (value, table_number, table_notes) tuples
        """
        values = []
        
        # Look for table patterns
        table_patterns = [
            r'Table\s+([A-Z0-9-]+)',
            r'TABLE\s+([A-Z0-9-]+)',
        ]
        
        # Look for stress value patterns
        stress_patterns = [
            r'(\d+\.?\d*)\s*MPa',
            r'(\d+\.?\d*)\s*ksi',
            r'(\d+\.?\d*)',
        ]
        
        # Find all stress values
        for stress_pattern in stress_patterns:
            for match in re.finditer(stress_pattern, text):
                try:
                    value = float(match.group(1))
                    
                    # Check if this is at our temperature or if we need interpolation
                    # For now, just return all values
                    table_number = ""
                    table_notes = ""
                    
                    # Look for table number nearby
                    for table_pattern in table_patterns:
                        table_match = re.search(table_pattern, text[:match.start()])
                        if table_match:
                            table_number = table_match.group(1)
                    
                    values.append((value, table_number, table_notes))
                except ValueError:
                    continue
        
        return values
    
    def pipe_lookup(self, nps: str, schedule: str) -> List[LookupResult]:
        """
        Look up pipe dimensions from B36.10.
        
        Args:
            nps: Nominal Pipe Size (e.g., "2", "6")
            schedule: Schedule (e.g., "40", "80", "160")
            
        Returns:
            List of LookupResult objects with OD and wall thickness
        """
        results = []
        
        # Search in B36.10
        query = f"{nps} {schedule}"
        filters = {
            'code': 'ASME B36.10'
        }
        
        chunks = self.storage.search_chunks(query, filters)
        
        if not chunks:
            # Try without schedule
            query = nps
            chunks = self.storage.search_chunks(query, filters)
        
        # Process chunks to find dimensions
        for chunk in chunks:
            text = chunk.get('text', '')
            
            # Look for dimensions
            dimensions = self.extract_pipe_dimensions(text)
            
            for od, wall in dimensions:
                result = LookupResult(
                    value={'nps': nps, 'schedule': schedule, 'od': od, 'wall': wall},
                    citation=f"[{chunk.get('code')}, {chunk.get('edition')}, {chunk.get('clause_id')}, PDF p.{chunk.get('pdf_page')}]",
                    source=f"{chunk.get('code')} {chunk.get('division')}",
                    pdf_page=chunk.get('pdf_page', 0),
                    table_number=chunk.get('clause_id', ''),
                    table_notes="",
                    verified=False,
                    candidate=True
                )
                results.append(result)
        
        if not results:
            result = LookupResult(
                value=None,
                citation="",
                source="",
                pdf_page=0,
                table_number="",
                table_notes=f"NEEDS INPUT: Pipe dimensions not found for NPS {nps} Schedule {schedule}. "
                           f"Check ASME B36.10 tables.",
                verified=False,
                candidate=False
            )
            results.append(result)
        
        return results
    
    def extract_pipe_dimensions(self, text: str) -> List[Tuple[float, float]]:
        """
        Extract pipe OD and wall thickness from text.
        
        Args:
            text: Text to search
            
        Returns:
            List of (OD, wall) tuples in mm
        """
        dimensions = []
        
        # Look for patterns like "OD: 60.3 mm, Wall: 3.9 mm"
        patterns = [
            r'OD[\s:]+([\d.]+)\s*mm[\s,;]+[Ww]all[\s:]+([\d.]+)\s*mm',
            r'([\d.]+)\s*×\s*([\d.]+)',
            r'Outside\s+Diameter[\s:]+([\d.]+)\s*mm[\s,;]+[Tt]hickness[\s:]+([\d.]+)\s*mm',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                try:
                    od = float(match.group(1))
                    wall = float(match.group(2))
                    dimensions.append((od, wall))
                except (ValueError, IndexError):
                    continue
        
        return dimensions
    
    def flange_lookup(self, standard: str, rating_class: int, nps: str, 
                     material_group: str, temperature: float) -> List[LookupResult]:
        """
        Look up flange rating and dimensions from B16.5.
        
        Args:
            standard: Flange standard (e.g., "B16.5")
            rating_class: Rating class (e.g., 150)
            nps: Nominal Pipe Size
            material_group: Material group (e.g., "1.1")
            temperature: Design temperature in degC
            
        Returns:
            List of LookupResult objects with rating and dimensions
        """
        results = []
        
        # Search in B16.5
        query = f"Class {rating_class} {nps} {material_group}"
        filters = {
            'code': f'ASME {standard}'
        }
        
        chunks = self.storage.search_chunks(query, filters)
        
        if not chunks:
            # Try without material group
            query = f"Class {rating_class} {nps}"
            chunks = self.storage.search_chunks(query, filters)
        
        # Process chunks to find ratings and dimensions
        for chunk in chunks:
            text = chunk.get('text', '')
            
            # Look for pressure rating
            rating = self.extract_flange_rating(text, temperature)
            
            # Look for dimensions
            dimensions = self.extract_flange_dimensions(text)
            
            for rating_value in rating:
                for dim_dict in dimensions:
                    result = LookupResult(
                        value={'rating': rating_value, 'dimensions': dim_dict},
                        citation=f"[{chunk.get('code')}, {chunk.get('edition')}, {chunk.get('clause_id')}, PDF p.{chunk.get('pdf_page')}]",
                        source=f"{chunk.get('code')} {chunk.get('division')}",
                        pdf_page=chunk.get('pdf_page', 0),
                        table_number=chunk.get('clause_id', ''),
                        table_notes="",
                        verified=False,
                        candidate=True
                    )
                    results.append(result)
        
        if not results:
            result = LookupResult(
                value=None,
                citation="",
                source="",
                pdf_page=0,
                table_number="",
                table_notes=f"NEEDS INPUT: Flange data not found for {standard} Class {rating_class} "
                           f"NPS {nps} Material Group {material_group} at {temperature}°C. "
                           f"Check ASME B16.5 tables.",
                verified=False,
                candidate=False
            )
            results.append(result)
        
        return results
    
    def extract_flange_rating(self, text: str, temperature: float) -> List[float]:
        """
        Extract flange pressure rating from text.
        
        Args:
            text: Text to search
            temperature: Design temperature
            
        Returns:
            List of pressure ratings in MPa
        """
        ratings = []
        
        # Look for pressure patterns
        patterns = [
            r'(\d+\.?\d*)\s*MPa',
            r'(\d+\.?\d*)\s*bar',
            r'(\d+\.?\d*)\s*psi',
            r'(\d+\.?\d*)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                try:
                    value = float(match.group(1))
                    
                    # Convert to MPa if needed
                    # This is a simplification - actual conversion depends on context
                    ratings.append(value)
                except ValueError:
                    continue
        
        return ratings
    
    def extract_flange_dimensions(self, text: str) -> List[Dict[str, float]]:
        """
        Extract flange dimensions from text.
        
        Args:
            text: Text to search
            
        Returns:
            List of dimension dictionaries
        """
        dimensions = []
        
        # Look for dimension patterns
        # This is a placeholder - actual implementation would need to parse B16.5 tables
        patterns = [
            r'OD[\s:]+([\d.]+)\s*mm',
            r'ID[\s:]+([\d.]+)\s*mm',
            r'Thickness[\s:]+([\d.]+)\s*mm',
        ]
        
        dim_dict = {}
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                try:
                    key = pattern.split('[')[1].split(']')[0].replace('\s:', '').strip()
                    value = float(match.group(1))
                    dim_dict[key] = value
                except (ValueError, IndexError):
                    continue
        
        if dim_dict:
            dimensions.append(dim_dict)
        
        return dimensions
    
    def material_spec_lookup(self, grade: str) -> List[LookupResult]:
        """
        Look up material specifications for a grade.
        
        Args:
            grade: Material grade (e.g., "304L")
            
        Returns:
            List of LookupResult objects with specifications
        """
        results = []
        
        # Use the RAG system to find materials
        materials = self.rag_system.find_materials(grade)
        
        for material in materials:
            result = LookupResult(
                value={
                    'spec': material.get('spec', ''),
                    'product_form': material.get('product_form', ''),
                    'code': material.get('code', ''),
                    'division': material.get('division', ''),
                    'edition': material.get('edition', 0)
                },
                citation=f"[{material.get('code')}, {material.get('edition')}, {material.get('clause_id')}, PDF p.{material.get('pdf_page')}]",
                source=f"{material.get('code')} {material.get('division')}",
                pdf_page=material.get('pdf_page', 0),
                table_number=material.get('clause_id', ''),
                table_notes="",
                verified=False,
                candidate=True
            )
            results.append(result)
        
        if not results:
            result = LookupResult(
                value=None,
                citation="",
                source="",
                pdf_page=0,
                table_number="",
                table_notes=f"NEEDS INPUT: Material specifications not found for grade {grade}. "
                           f"Check Section II-A Volume 1.",
                verified=False,
                candidate=False
            )
            results.append(result)
        
        return results


# Test function for the module
if __name__ == '__main__':
    from asme_rag.utils import get_config
    from asme_rag.storage import Storage
    
    config = get_config()
    storage = Storage(config)
    lookups = Lookups(config, storage)
    
    print("Testing lookup functions...")
    
    # Test allowable lookup (will not find anything without actual data)
    results = lookups.allowable_lookup("SA-240", "304L", "plate", 100)
    print(f"Allowable lookup: {len(results)} results")
    for result in results:
        print(f"  {result.table_notes[:100] if result.table_notes else result.value}")
    
    # Test pipe lookup
    results = lookups.pipe_lookup("2", "40")
    print(f"Pipe lookup: {len(results)} results")
    for result in results:
        print(f"  {result.table_notes[:100] if result.table_notes else result.value}")
    
    # Test flange lookup
    results = lookups.flange_lookup("B16.5", 150, "2", "1.1", 100)
    print(f"Flange lookup: {len(results)} results")
    for result in results:
        print(f"  {result.table_notes[:100] if result.table_notes else result.value}")
    
    # Test material spec lookup
    results = lookups.material_spec_lookup("304L")
    print(f"Material spec lookup: {len(results)} results")
    for result in results:
        print(f"  {result.table_notes[:100] if result.table_notes else result.value}")
    
    print("\nLookup function tests completed!")
