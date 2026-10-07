"""
ASME RAG Main Entry Point

This module allows running the package as: python -m asme_rag <command>
"""

import sys
import os

# Add the parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.cli import main

if __name__ == '__main__':
    main()
