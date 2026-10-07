"""
Chamber Design Package

This package provides deterministic design-check calculator and report generation
for double-walled (jacketed), water-cooled vacuum chambers.

Main modules:
- calc: Main calculation engine
- report: Report generation
- init: Interactive input wizard
- provide: Value input for verified data
- formulas: Formula plugins for different code rules
- lookups: Data lookup functions
"""

__version__ = "0.1.0"
__author__ = "ASME BPVC Design Assistant"

from . import calc
from . import report
from . import init
from . import provide
from . import formulas
from . import lookups

# Make modules available at package level
__all__ = ['calc', 'report', 'init', 'provide', 'formulas', 'lookups']
