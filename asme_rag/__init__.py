"""
ASME RAG Package

This package provides retrieval-augmented question-answering over ASME PDFs
and related standards for pressure vessel design.

Main modules:
- pdf_parser: Parse ASME PDFs into structured text blocks
- chunker: Split text into meaningful chunks with metadata
- storage: SQLite storage with FTS5 for efficient retrieval
- rag: Retrieval and generation pipeline
- cli: Command-line interface
- vision: Vision-based figure and table analysis
- xref: Cross-reference expansion
"""

__version__ = "0.1.0"
__author__ = "ASME BPVC Design Assistant"

from . import cli
from . import pdf_parser
from . import chunker
from . import storage
from . import rag
from . import vision
from . import xref
from . import utils

# Make modules available at package level
__all__ = ['cli', 'pdf_parser', 'chunker', 'storage', 'rag', 'vision', 'xref', 'utils']
