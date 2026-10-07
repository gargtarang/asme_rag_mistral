"""
ASME RAG Vision Module

This module provides vision-based analysis of figures, charts, and tables
using the LM Studio vision model. It handles:
- Figure detection and description
- Chart value reading
- Table transcription
- Vision testing

All vision outputs are marked as UNVERIFIED until confirmed by the user.
"""

import os
import sys
import json
import logging
import base64
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from io import BytesIO
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from asme_rag.utils import Config, get_config
from asme_rag.storage import Storage


@dataclass
class FigureDescription:
    """Description of a figure from vision analysis."""
    
    figure_id: str
    doc_id: str
    page: int
    caption: str = ""
    figure_number: str = ""
    description: str = ""
    model_generated: bool = True
    verified: bool = False
    content_hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'figure_id': self.figure_id,
            'doc_id': self.doc_id,
            'page': self.page,
            'caption': self.caption,
            'figure_number': self.figure_number,
            'description': self.description,
            'model_generated': self.model_generated,
            'verified': self.verified,
            'content_hash': self.content_hash
        }


@dataclass
class VisionReading:
    """A reading from vision analysis."""
    
    value_name: str
    proposed_value: Any
    unit: str = ""
    uncertainty: float = 0.0
    stable: bool = True
    verified: bool = False
    source: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'value_name': self.value_name,
            'proposed_value': self.proposed_value,
            'unit': self.unit,
            'uncertainty': self.uncertainty,
            'stable': self.stable,
            'verified': self.verified,
            'source': self.source
        }


@dataclass
class VisionTestResult:
    """Result of a vision test case."""
    
    test_name: str
    status: str = "passed"
    time: float = 0.0
    error: str = ""
    value: Any = None
    expected_value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_name': self.test_name,
            'status': self.status,
            'time': self.time,
            'error': self.error,
            'value': self.value,
            'expected_value': self.expected_value
        }


class VisionSystem:
    """
    Vision system for analyzing figures, charts, and tables.
    
    Uses LM Studio's vision model to:
    - Describe figures
    - Read values from charts
    - Transcribe tables
    """
    
    # Prompt for figure description
    FIGURE_DESCRIPTION_PROMPT = """
You are analyzing a figure from an ASME BPVC document.

Describe the figure in detail:
1. Figure type (chart, diagram, graph, etc.)
2. Axis labels, units, and printed ranges (if applicable)
3. Curve and legend labels
4. Notes and annotations
5. All printed text visible in the figure

IMPORTANT: Do NOT estimate values from curve positions. Only report text that is clearly visible.
If anything is unreadable, state that it is unreadable.

Your description will be used for search and reference, but all values must be verified by the user.

Output format:
Type: <figure type>
Axes: <axis descriptions>
Curves: <curve descriptions>
Notes: <notes>
Text: <all visible text>
"""
    
    # Prompt for chart reading
    CHART_READING_PROMPT = """
You are reading a value from a chart in an ASME BPVC document.

Input: {chart_inputs}
Curve/line: {curve}

Read the value for {value_name} from the chart at the specified inputs.

IMPORTANT:
- Only read values that are clearly visible
- If the value is between marked points, estimate and state the uncertainty
- If the value is unclear or the chart is unreadable, respond with "UNREADABLE"
- Your reading is a PROPOSAL and must be verified by the user

Output format:
PROPOSED (unverified): {value_name} = <value> (<unit>)
Uncertainty: <percentage>%

Do NOT make up values. Only read what is visible in the chart.
"""
    
    # Prompt for table transcription
    TABLE_TRANSCRIPTION_PROMPT = """
You are transcribing a table from an ASME BPVC document.

Transcribe the table as Markdown, preserving:
- All column headers
- All row values
- All notes and footnotes
- The exact formatting and structure

If the table is unreadable or garbled, state that it is unreadable.

Your transcription is a PROPOSAL and must be verified by the user.

Output format:
| Column1 | Column2 | ... |
|--------|--------|-----|
| value1 | value2 | ... |

Include all notes at the end.
"""
    
    def __init__(self, config: Optional[Config] = None, storage: Optional[Storage] = None):
        """
        Initialize the vision system.
        
        Args:
            config: Configuration object
            storage: Storage instance
        """
        self.config = config or get_config()
        self.storage = storage or Storage(self.config)
        self.logger = logging.getLogger(__name__)
        
        # Check if vision is enabled and available
        self.vision_enabled = (self.config.vision_enabled and 
                               self.check_vision_availability())
    
    def check_vision_availability(self) -> bool:
        """Check if vision is available."""
        if not self.config.vision_enabled:
            return False
        
        if not PIL_AVAILABLE:
            self.logger.warning("PIL not available, vision disabled")
            return False
        
        # Check if we can connect to LM Studio
        try:
            import requests
            try:
                response = requests.get(
                    f"{self.config.api_url}/models",
                    timeout=5
                )
                if response.status_code == 200:
                    models = response.json().get('data', [])
                    model_ids = [m.get('id', '') for m in models]
                    return self.config.vision_model in model_ids
            except:
                return False
        except ImportError:
            return False
        
        return False
    
    def describe_figures(self, doc_id: Optional[str] = None, 
                       page_num: Optional[int] = None) -> List[FigureDescription]:
        """
        Describe figures in PDFs.
        
        Args:
            doc_id: Optional document ID to filter
            page_num: Optional page number to filter
            
        Returns:
            List of FigureDescription objects
        """
        if not self.vision_enabled:
            self.logger.warning("Vision is disabled")
            return []
        
        descriptions = []
        
        # Get figures to describe
        if doc_id and page_num:
            # Get figures from specific page
            figures = self.storage.get_figures_by_page(doc_id, page_num)
        elif doc_id:
            # Get all figures from document
            cursor = self.storage.conn.cursor()
            cursor.execute("""
                SELECT * FROM figures 
                WHERE doc_id = ? 
                ORDER BY page, bbox_y, bbox_x
            """, (doc_id,))
            columns = [col[0] for col in cursor.description]
            figures = [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            # Get all figures
            cursor = self.storage.conn.cursor()
            cursor.execute("SELECT * FROM figures ORDER BY page, bbox_y, bbox_x")
            columns = [col[0] for col in cursor.description]
            figures = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Filter by resume flag
        if self.config.vision_resume:
            existing_hashes = set()
            cursor = self.storage.conn.cursor()
            cursor.execute("SELECT content_hash FROM figures WHERE model_generated = 1")
            existing_hashes = set(row[0] for row in cursor.fetchall() if row[0])
            
            figures = [f for f in figures if f.get('content_hash') not in existing_hashes]
        
        # Process each figure
        for figure in figures:
            if self.config.max_figures_per_run and len(descriptions) >= self.config.max_figures_per_run:
                break
            
            try:
                description = self.describe_figure(figure)
                if description:
                    descriptions.append(description)
                    
                    # Store the description
                    self.storage.store_figure(description.to_dict())
                    
            except Exception as e:
                self.logger.warning(f"Failed to describe figure {figure.get('figure_id')}: {str(e)}")
        
        return descriptions
    
    def describe_figure(self, figure: Dict[str, Any]) -> Optional[FigureDescription]:
        """
        Describe a single figure.
        
        Args:
            figure: Figure data dictionary
            
        Returns:
            FigureDescription object or None
        """
        # Get the PDF page
        doc_id = figure.get('doc_id')
        page_num = figure.get('page')
        bbox = (figure.get('bbox_x', 0), figure.get('bbox_y', 0),
               figure.get('bbox_x', 0) + figure.get('bbox_width', 0),
               figure.get('bbox_y', 0) + figure.get('bbox_height', 0))
        
        # Find the PDF file
        pdf_path = self.get_pdf_path(doc_id)
        if not pdf_path or not os.path.exists(pdf_path):
            self.logger.warning(f"PDF not found for figure: {doc_id}")
            return None
        
        # Render the figure region
        image_data = self.render_figure_region(pdf_path, page_num, bbox)
        if not image_data:
            return None
        
        # Send to vision model
        description_text = self.analyze_with_vision(
            image_data,
            self.FIGURE_DESCRIPTION_PROMPT
        )
        
        if not description_text:
            return None
        
        # Parse the description
        parsed = self.parse_figure_description(description_text)
        
        # Create figure description
        fig_desc = FigureDescription(
            figure_id=figure.get('figure_id', f"fig_{doc_id}_{page_num}"),
            doc_id=doc_id,
            page=page_num,
            caption=figure.get('caption', ''),
            figure_number=figure.get('figure_number', ''),
            description=description_text,
            model_generated=True,
            verified=False,
            content_hash=figure.get('content_hash', '')
        )
        
        return fig_desc
    
    def get_pdf_path(self, doc_id: str) -> Optional[str]:
        """Get the PDF path for a document ID."""
        for doc in self.config.documents:
            if doc.get('id') == doc_id:
                return doc.get('pdf_path')
        return None
    
    def render_figure_region(self, pdf_path: str, page_num: int, 
                           bbox: Tuple[float, float, float, float]) -> Optional[bytes]:
        """
        Render a figure region from a PDF page.
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-based)
            bbox: Bounding box (x0, y0, x1, y1)
            
        Returns:
            Rendered image as bytes or None
        """
        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            page = doc.load_page(page_num - 1)
            
            # Create a pixmap for the region
            rect = fitz.Rect(bbox)
            pix = page.get_pixmap(
                clip=rect,
                dpi=(self.config.render_dpi, self.config.render_dpi),
                alpha=False
            )
            
            # Convert to image
            img_bytes = pix.tobytes()
            
            doc.close()
            return img_bytes
            
        except Exception as e:
            self.logger.warning(f"Failed to render figure region: {str(e)}")
            return None
    
    def analyze_with_vision(self, image_data: bytes, prompt: str) -> Optional[str]:
        """
        Analyze an image using the vision model.
        
        Args:
            image_data: Image as bytes
            prompt: Prompt for the vision model
            
        Returns:
            Analysis result or None
        """
        if not self.vision_enabled:
            return None
        
        try:
            import requests
            import base64
            
            # Encode image as base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            image_url = f"data:image/png;base64,{image_base64}"
            
            # Prepare messages
            messages = [
                {
                    "role": "system",
                    "content": "You are a vision assistant for ASME BPVC documents. "
                               "Be precise and only report what you can clearly see."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": image_url
                        }
                    ]
                }
            ]
            
            # Prepare request
            url = f"{self.config.api_url}/chat/completions"
            payload = {
                "model": self.config.vision_model,
                "messages": messages,
                "temperature": 0.0,  # Deterministic for vision
                "max_tokens": self.config.max_tokens
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Send request with retries
            for attempt in range(self.config.repeat_reads):
                try:
                    response = requests.post(
                        url, json=payload, headers=headers,
                        timeout=self.config.vision_timeout_s
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        self.logger.warning(f"Vision request failed (attempt {attempt + 1}): {response.status_code}")
                        
                except Exception as e:
                    self.logger.warning(f"Vision request error (attempt {attempt + 1}): {str(e)}")
                
                if attempt < self.config.repeat_reads - 1:
                    time.sleep(0.5)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze with vision: {str(e)}")
            return None
    
    def parse_figure_description(self, description: str) -> Dict[str, Any]:
        """
        Parse a figure description into structured data.
        
        Args:
            description: Description text
            
        Returns:
            Parsed data dictionary
        """
        parsed = {}
        
        # Extract type
        type_match = re.search(r'Type:\s*(.+)', description)
        if type_match:
            parsed['type'] = type_match.group(1).strip()
        
        # Extract axes
        axes_match = re.search(r'Axes:\s*(.+)', description)
        if axes_match:
            parsed['axes'] = axes_match.group(1).strip()
        
        # Extract curves
        curves_match = re.search(r'Curves:\s*(.+)', description)
        if curves_match:
            parsed['curves'] = curves_match.group(1).strip()
        
        # Extract notes
        notes_match = re.search(r'Notes:\s*(.+)', description)
        if notes_match:
            parsed['notes'] = notes_match.group(1).strip()
        
        # Extract text
        text_match = re.search(r'Text:\s*(.+)', description)
        if text_match:
            parsed['text'] = text_match.group(1).strip()
        
        return parsed
    
    def read_figure(self, doc_id: str, figure_num: str, page_num: int,
                   chart_inputs: str, curve: str, value_name: str, 
                   unit: str) -> Optional[VisionReading]:
        """
        Read a value from a figure/chart.
        
        Args:
            doc_id: Document ID
            figure_num: Figure number
            page_num: Page number
            chart_inputs: Chart input values (comma-separated)
            curve: Curve/line to use
            value_name: Name of value to read
            unit: Unit of the value
            
        Returns:
            VisionReading object or None
        """
        if not self.vision_enabled:
            self.logger.warning("Vision is disabled")
            return None
        
        # Get the figure
        figures = self.storage.get_figures_by_page(doc_id, page_num)
        figure = None
        
        for fig in figures:
            if fig.get('figure_number') == figure_num:
                figure = fig
                break
        
        if not figure:
            self.logger.warning(f"Figure {figure_num} not found on page {page_num}")
            return None
        
        # Render the figure
        pdf_path = self.get_pdf_path(doc_id)
        if not pdf_path:
            return None
        
        bbox = (figure.get('bbox_x', 0), figure.get('bbox_y', 0),
               figure.get('bbox_x', 0) + figure.get('bbox_width', 0),
               figure.get('bbox_y', 0) + figure.get('bbox_height', 0))
        
        image_data = self.render_figure_region(pdf_path, page_num, bbox)
        if not image_data:
            return None
        
        # Prepare prompt
        prompt = self.CHART_READING_PROMPT.format(
            chart_inputs=chart_inputs,
            curve=curve,
            value_name=value_name
        )
        
        # Get readings from multiple attempts
        readings = []
        for attempt in range(self.config.repeat_reads):
            result = self.analyze_with_vision(image_data, prompt)
            if result:
                readings.append(result)
            time.sleep(0.1)
        
        if not readings:
            return None
        
        # Parse readings and check stability
        parsed_readings = []
        for reading in readings:
            parsed = self.parse_chart_reading(reading, value_name, unit)
            if parsed:
                parsed_readings.append(parsed)
        
        if not parsed_readings:
            return None
        
        # Check stability
        values = [r.proposed_value for r in parsed_readings if isinstance(r.proposed_value, (int, float))]
        if len(values) >= 2:
            mean_value = np.mean(values)
            std_value = np.std(values)
            cv = (std_value / mean_value * 100) if mean_value != 0 else 0
            
            stable = cv <= self.config.reading_tolerance_pct
        else:
            stable = True
            cv = 0.0
        
        # Return the first reading with stability info
        reading = parsed_readings[0]
        reading.stable = stable
        reading.uncertainty = cv
        
        return reading
    
    def parse_chart_reading(self, reading: str, value_name: str, unit: str) -> Optional[VisionReading]:
        """
        Parse a chart reading result.
        
        Args:
            reading: Reading text
            value_name: Expected value name
            unit: Expected unit
            
        Returns:
            VisionReading object or None
        """
        # Look for PROPOSED pattern
        proposed_match = re.search(
            r'PROPOSED\s*\(unverified\):\s*' + re.escape(value_name) + r'\s*=\s*([\d.]+)\s*\(([^)]+)\)',
            reading, re.IGNORECASE
        )
        
        if proposed_match:
            try:
                value = float(proposed_match.group(1))
                reading_unit = proposed_match.group(2)
                
                return VisionReading(
                    value_name=value_name,
                    proposed_value=value,
                    unit=reading_unit or unit,
                    uncertainty=0.0,
                    stable=True,
                    verified=False,
                    source="vision"
                )
            except ValueError:
                return None
        
        # Look for UNREADABLE
        if 'UNREADABLE' in reading.upper():
            return VisionReading(
                value_name=value_name,
                proposed_value=None,
                unit=unit,
                uncertainty=0.0,
                stable=True,
                verified=False,
                source="vision"
            )
        
        return None
    
    def transcribe_table(self, doc_id: str, page_num: int, 
                       table_num: Optional[str] = None) -> Optional[str]:
        """
        Transcribe a table from an image.
        
        Args:
            doc_id: Document ID
            page_num: Page number
            table_num: Optional table number
            
        Returns:
            Transcribed table as Markdown or None
        """
        if not self.vision_enabled:
            self.logger.warning("Vision is disabled")
            return None
        
        # Find the PDF
        pdf_path = self.get_pdf_path(doc_id)
        if not pdf_path or not os.path.exists(pdf_path):
            return None
        
        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            page = doc.load_page(page_num - 1)
            
            # Find table regions (this is simplified - in practice, we'd need better detection)
            # For now, just render the whole page
            pix = page.get_pixmap(
                dpi=(self.config.render_dpi, self.config.render_dpi),
                alpha=False
            )
            
            image_data = pix.tobytes()
            doc.close()
            
            if not image_data:
                return None
            
            # Analyze with vision
            result = self.analyze_with_vision(image_data, self.TABLE_TRANSCRIPTION_PROMPT)
            
            if result and '|' in result:  # Looks like Markdown table
                return result
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to transcribe table: {str(e)}")
            return None
    
    def run_tests(self) -> List[VisionTestResult]:
        """
        Run vision test cases.
        
        Returns:
            List of VisionTestResult objects
        """
        results = []
        
        # Load test cases
        try:
            import tomllib
            with open('tests/vision_cases.toml', 'rb') as f:
                test_data = tomllib.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load vision test cases: {str(e)}")
            return results
        
        test_cases = test_data.get('test_cases', [])
        
        for test_case in test_cases:
            start_time = time.time()
            
            try:
                # Run the test
                doc_id = test_case.get('doc')
                page_num = test_case.get('page')
                bbox = test_case.get('bbox')
                
                # Render the region
                pdf_path = self.get_pdf_path(doc_id)
                if not pdf_path:
                    results.append(VisionTestResult(
                        test_name=test_case.get('name', 'unknown'),
                        status='skipped',
                        error='PDF not found'
                    ))
                    continue
                
                # Use full page if no bbox
                if not bbox:
                    bbox = (0, 0, 1000, 1000)  # Default large bbox
                
                image_data = self.render_figure_region(pdf_path, page_num, bbox)
                if not image_data:
                    results.append(VisionTestResult(
                        test_name=test_case.get('name', 'unknown'),
                        status='failed',
                        error='Failed to render region'
                    ))
                    continue
                
                # Analyze
                result_text = self.analyze_with_vision(image_data, test_case.get('prompt', ''))
                
                if not result_text:
                    results.append(VisionTestResult(
                        test_name=test_case.get('name', 'unknown'),
                        status='failed',
                        error='No result from vision'
                    ))
                    continue
                
                # Parse the result
                expected_value = test_case.get('expected_value')
                if expected_value is not None:
                    # Try to extract the value
                    parsed = self.parse_test_result(result_text, test_case)
                    value = parsed.get('value')
                    
                    # Compare
                    if value is not None:
                        error = abs(float(value) - float(expected_value))
                        tolerance = test_case.get('tolerance', 5.0)
                        
                        if error <= tolerance:
                            status = 'passed'
                        else:
                            status = 'failed'
                    else:
                        status = 'failed'
                        error = 'Could not parse value'
                else:
                    status = 'passed'  # No expected value, just check if we got a result
                    value = result_text[:100]
                    error = ''
                
                elapsed = time.time() - start_time
                
                results.append(VisionTestResult(
                    test_name=test_case.get('name', 'unknown'),
                    status=status,
                    time=elapsed,
                    error=str(error) if isinstance(error, (int, float)) else error,
                    value=value,
                    expected_value=expected_value
                ))
                
            except Exception as e:
                elapsed = time.time() - start_time
                results.append(VisionTestResult(
                    test_name=test_case.get('name', 'unknown'),
                    status='error',
                    time=elapsed,
                    error=str(e)
                ))
        
        return results
    
    def parse_test_result(self, result: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a vision test result.
        
        Args:
            result: Vision result text
            test_case: Test case data
            
        Returns:
            Parsed result dictionary
        """
        parsed = {}
        
        # Try to extract based on test case type
        if test_case.get('type') == 'value':
            # Look for a numeric value
            match = re.search(r'[\d.]+', result)
            if match:
                parsed['value'] = match.group(0)
        
        return parsed


# Test function for the module
if __name__ == '__main__':
    from asme_rag.utils import get_config
    from asme_rag.storage import Storage
    
    config = get_config()
    storage = Storage(config)
    vision_system = VisionSystem(config, storage)
    
    print("Testing vision system...")
    
    # Check availability
    print(f"Vision enabled: {vision_system.vision_enabled}")
    print(f"Vision available: {vision_system.check_vision_availability()}")
    
    # Test with a simple image (if available)
    if vision_system.vision_enabled:
        # This would need actual PDF files to work
        print("Vision system is ready (requires actual PDF files for full testing)")
    else:
        print("Vision system not available (LM Studio or PIL not configured)")
    
    print("Vision system tests completed!")
