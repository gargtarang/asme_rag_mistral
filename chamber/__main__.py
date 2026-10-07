"""
Chamber Design Main Entry Point

This module allows running the package as: python -m chamber <command>
"""

import sys
import os

# Add the parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chamber.calc import main as calc_main

if __name__ == '__main__':
    calc_main()
