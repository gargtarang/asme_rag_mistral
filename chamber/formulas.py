"""
Chamber Design Formula Plugins

This module provides formula plugins for different ASME BPVC code rules.
Each formula is a plugin that can be selected based on the governing code and edition.

Formula plugins:
- Wall thickness calculations
- Opening reinforcement (nozzle reinforcement)
- External pressure calculations
- Jacket design
- Flange design

All formulas are STUBS that need to be filled from confirmed clause text.
Each stub is marked with VERIFY_AGAINST_PDF.
"""

import os
import sys
import math
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chamber.lookups import Lookups


@dataclass
class FormulaResult:
    """Result from a formula calculation."""
    
    value: float
    unit: str
    clause: str
    code: str
    edition: int
    description: str
    inputs: Dict[str, Any]
    passes: bool = True
    margin: float = 0.0
    utilisation: float = 0.0
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'value': self.value,
            'unit': self.unit,
            'clause': self.clause,
            'code': self.code,
            'edition': self.edition,
            'description': self.description,
            'inputs': self.inputs,
            'passes': self.passes,
            'margin': self.margin,
            'utilisation': self.utilisation,
            'notes': self.notes
        }


class FormulaPlugin:
    """Base class for formula plugins."""
    
    def __init__(self, code: str, edition: int, clause: str):
        """
        Initialize the formula plugin.
        
        Args:
            code: ASME code (e.g., "ASME VIII-1")
            edition: Edition year
            clause: Clause identifier
        """
        self.code = code
        self.edition = edition
        self.clause = clause
        self.logger = logging.getLogger(__name__)
    
    def calculate(self, inputs: Dict[str, Any]) -> FormulaResult:
        """
        Calculate using the formula.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            FormulaResult object
        """
        raise NotImplementedError("Subclasses must implement calculate()")


class WallThicknessFormula(FormulaPlugin):
    """
    Formula for wall thickness calculation.
    
    # VERIFY_AGAINST_PDF: This formula needs to be verified against the actual
    # ASME BPVC VIII-1 clause text for wall thickness under vacuum and pressure.
    
    Default implementation uses UG-22 and UG-27 as reference, but the actual
    formula must be confirmed from the PDF.
    """
    
    def __init__(self, code: str = "ASME VIII-1", edition: int = 2025, clause: str = "UG-22"):
        super().__init__(code, edition, clause)
    
    def calculate(self, inputs: Dict[str, Any]) -> FormulaResult:
        """
        Calculate required wall thickness.
        
        Args:
            inputs: Dictionary containing:
                - pressure: Design pressure (MPa, gauge)
                - radius: Inner radius (mm)
                - allowable_stress: Allowable stress (MPa)
                - joint_efficiency: Joint efficiency (0-1)
                - corrosion_allowance: Corrosion allowance (mm)
                
        Returns:
            FormulaResult with required thickness
        """
        # VERIFY_AGAINST_PDF: Formula implementation
        # This is a placeholder. The actual formula from ASME BPVC must be used.
        
        pressure = inputs.get('pressure', 0)
        radius = inputs.get('radius', 0)
        allowable_stress = inputs.get('allowable_stress', 0)
        joint_efficiency = inputs.get('joint_efficiency', 1.0)
        corrosion_allowance = inputs.get('corrosion_allowance', 0)
        
        # Placeholder calculation (for internal pressure)
        # t = (P * R) / (S * E - 0.6 * P) + CA
        # Where: P = pressure, R = radius, S = allowable stress, E = efficiency, CA = corrosion allowance
        
        if pressure > 0 and radius > 0 and allowable_stress > 0:
            # Internal pressure formula
            required_thickness = (pressure * radius) / (allowable_stress * joint_efficiency - 0.6 * pressure)
            required_thickness += corrosion_allowance
            
            return FormulaResult(
                value=required_thickness,
                unit="mm",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required wall thickness for internal pressure",
                inputs=inputs,
                passes=False,  # Will be determined by comparison
                notes="VERIFY_AGAINST_PDF: Formula needs confirmation from ASME BPVC VIII-1"
            )
        else:
            return FormulaResult(
                value=0,
                unit="mm",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required wall thickness",
                inputs=inputs,
                passes=False,
                notes="NEEDS INPUT: Missing required inputs for wall thickness calculation"
            )


class ExternalPressureFormula(FormulaPlugin):
    """
    Formula for external pressure (vacuum) wall thickness.
    
    # VERIFY_AGAINST_PDF: This formula needs to be verified against
    # ASME BPVC VIII-1 UG-28 or UG-37 for vacuum design.
    """
    
    def __init__(self, code: str = "ASME VIII-1", edition: int = 2025, clause: str = "UG-37"):
        super().__init__(code, edition, clause)
    
    def calculate(self, inputs: Dict[str, Any]) -> FormulaResult:
        """
        Calculate required wall thickness for external pressure.
        
        Args:
            inputs: Dictionary containing:
                - external_pressure: External pressure (MPa, gauge - negative for vacuum)
                - radius: Outer radius (mm)
                - length: Length of cylindrical shell (mm)
                - allowable_stress: Allowable stress (MPa)
                - elastic_modulus: Elastic modulus (MPa)
                
        Returns:
            FormulaResult with required thickness
        """
        # VERIFY_AGAINST_PDF: Formula implementation
        
        external_pressure = inputs.get('external_pressure', 0)
        radius = inputs.get('radius', 0)
        length = inputs.get('length', 0)
        allowable_stress = inputs.get('allowable_stress', 0)
        elastic_modulus = inputs.get('elastic_modulus', 0)
        
        # Placeholder: External pressure requires charts from Section II-D
        # This is a simplified placeholder
        
        if external_pressure < 0:  # Vacuum
            # For vacuum, the pressure is negative
            # The actual calculation requires external pressure charts
            # This is a conservative estimate
            required_thickness = abs(external_pressure) * radius / (allowable_stress * 1000)
            
            return FormulaResult(
                value=required_thickness,
                unit="mm",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required wall thickness for external pressure (vacuum)",
                inputs=inputs,
                passes=False,
                notes="VERIFY_AGAINST_PDF: Requires external pressure charts from Section II-D"
            )
        else:
            return FormulaResult(
                value=0,
                unit="mm",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required wall thickness for external pressure",
                inputs=inputs,
                passes=False,
                notes="NEEDS INPUT: External pressure calculation requires chart lookup"
            )


class OpeningReinforcementFormula(FormulaPlugin):
    """
    Formula for opening reinforcement (nozzle reinforcement).
    
    # VERIFY_AGAINST_PDF: This formula needs to be verified against
    # ASME BPVC VIII-1 UG-37 through UG-45 for opening reinforcement rules.
    
    The actual rules may have changed in 2025 edition.
    """
    
    def __init__(self, code: str = "ASME VIII-1", edition: int = 2025, clause: str = "UG-37"):
        super().__init__(code, edition, clause)
    
    def calculate(self, inputs: Dict[str, Any]) -> FormulaResult:
        """
        Calculate required reinforcement area for an opening.
        
        Args:
            inputs: Dictionary containing:
                - opening_diameter: Diameter of opening (mm)
                - wall_thickness: Wall thickness (mm)
                - pressure: Design pressure (MPa)
                - allowable_stress: Allowable stress (MPa)
                - nozzle_neck_thickness: Nozzle neck thickness (mm)
                - nozzle_neck_od: Nozzle neck OD (mm)
                - weld_size: Weld size (mm)
                
        Returns:
            FormulaResult with required reinforcement area
        """
        # VERIFY_AGAINST_PDF: Formula implementation
        
        opening_diameter = inputs.get('opening_diameter', 0)
        wall_thickness = inputs.get('wall_thickness', 0)
        pressure = inputs.get('pressure', 0)
        allowable_stress = inputs.get('allowable_stress', 0)
        
        # Placeholder: UG-37 area replacement method
        # A = 0.5 * d * t * (1 - f)
        # Where: d = opening diameter, t = wall thickness, f = reinforcement factor
        
        if opening_diameter > 0 and wall_thickness > 0:
            # Simplified area calculation
            required_area = 0.5 * opening_diameter * wall_thickness
            
            return FormulaResult(
                value=required_area,
                unit="mm²",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required reinforcement area for opening",
                inputs=inputs,
                passes=False,
                notes="VERIFY_AGAINST_PDF: Formula needs confirmation from ASME BPVC VIII-1 UG-37"
            )
        else:
            return FormulaResult(
                value=0,
                unit="mm²",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required reinforcement area",
                inputs=inputs,
                passes=False,
                notes="NEEDS INPUT: Missing required inputs for opening reinforcement"
            )


class JacketFormula(FormulaPlugin):
    """
    Formula for jacket wall thickness.
    
    # VERIFY_AGAINST_PDF: This formula needs to be verified against
    # ASME BPVC VIII-1 Part UJV for jacketed vessels.
    """
    
    def __init__(self, code: str = "ASME VIII-1", edition: int = 2025, clause: str = "UJV-1"):
        super().__init__(code, edition, clause)
    
    def calculate(self, inputs: Dict[str, Any]) -> FormulaResult:
        """
        Calculate jacket wall thickness.
        
        Args:
            inputs: Dictionary containing:
                - jacket_pressure: Jacket design pressure (MPa)
                - jacket_radius: Jacket radius (mm)
                - allowable_stress: Allowable stress (MPa)
                - joint_efficiency: Joint efficiency (0-1)
                - corrosion_allowance: Corrosion allowance (mm)
                
        Returns:
            FormulaResult with required jacket thickness
        """
        # VERIFY_AGAINST_PDF: Formula implementation
        
        jacket_pressure = inputs.get('jacket_pressure', 0)
        jacket_radius = inputs.get('jacket_radius', 0)
        allowable_stress = inputs.get('allowable_stress', 0)
        joint_efficiency = inputs.get('joint_efficiency', 1.0)
        corrosion_allowance = inputs.get('corrosion_allowance', 0)
        
        if jacket_pressure > 0 and jacket_radius > 0 and allowable_stress > 0:
            # Similar to internal pressure formula
            required_thickness = (jacket_pressure * jacket_radius) / (allowable_stress * joint_efficiency - 0.6 * jacket_pressure)
            required_thickness += corrosion_allowance
            
            return FormulaResult(
                value=required_thickness,
                unit="mm",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required jacket wall thickness",
                inputs=inputs,
                passes=False,
                notes="VERIFY_AGAINST_PDF: Formula needs confirmation from ASME BPVC VIII-1 Part UJV"
            )
        else:
            return FormulaResult(
                value=0,
                unit="mm",
                clause=self.clause,
                code=self.code,
                edition=self.edition,
                description="Required jacket wall thickness",
                inputs=inputs,
                passes=False,
                notes="NEEDS INPUT: Missing required inputs for jacket thickness calculation"
            )


class FormulaManager:
    """
    Manager for formula plugins.
    
    Selects and runs the appropriate formula based on the governing code,
    edition, and component type.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the formula manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.formulas = {
            'wall_thickness': {
                'ASME VIII-1': {
                    2025: WallThicknessFormula("ASME VIII-1", 2025, "UG-22")
                }
            },
            'external_pressure': {
                'ASME VIII-1': {
                    2025: ExternalPressureFormula("ASME VIII-1", 2025, "UG-37")
                }
            },
            'opening_reinforcement': {
                'ASME VIII-1': {
                    2025: OpeningReinforcementFormula("ASME VIII-1", 2025, "UG-37")
                }
            },
            'jacket': {
                'ASME VIII-1': {
                    2025: JacketFormula("ASME VIII-1", 2025, "UJV-1")
                }
            }
        }
        self.logger = logging.getLogger(__name__)
    
    def get_formula(self, check_type: str, code: str, edition: int) -> Optional[FormulaPlugin]:
        """
        Get the appropriate formula plugin.
        
        Args:
            check_type: Type of check (wall_thickness, external_pressure, etc.)
            code: Governing code
            edition: Edition year
            
        Returns:
            FormulaPlugin instance or None
        """
        try:
            return self.formulas[check_type][code][edition]
        except KeyError:
            self.logger.warning(f"No formula found for {check_type}, {code}, {edition}")
            return None
    
    def calculate(self, check_type: str, code: str, edition: int, 
                 inputs: Dict[str, Any]) -> Optional[FormulaResult]:
        """
        Run a calculation using the appropriate formula.
        
        Args:
            check_type: Type of check
            code: Governing code
            edition: Edition year
            inputs: Input values
            
        Returns:
            FormulaResult or None
        """
        formula = self.get_formula(check_type, code, edition)
        if formula:
            return formula.calculate(inputs)
        return None


# Test function for the module
if __name__ == '__main__':
    print("Testing formula plugins...")
    
    # Test wall thickness formula
    formula = WallThicknessFormula()
    inputs = {
        'pressure': 0.5,
        'radius': 500,
        'allowable_stress': 150,
        'joint_efficiency': 0.85,
        'corrosion_allowance': 1
    }
    result = formula.calculate(inputs)
    print(f"Wall thickness: {result.value:.2f} mm")
    print(f"  Notes: {result.notes}")
    
    # Test external pressure formula
    formula = ExternalPressureFormula()
    inputs = {
        'external_pressure': -0.101,
        'radius': 500,
        'allowable_stress': 150
    }
    result = formula.calculate(inputs)
    print(f"External pressure thickness: {result.value:.2f} mm")
    print(f"  Notes: {result.notes}")
    
    # Test opening reinforcement formula
    formula = OpeningReinforcementFormula()
    inputs = {
        'opening_diameter': 100,
        'wall_thickness': 10,
        'pressure': 0.5
    }
    result = formula.calculate(inputs)
    print(f"Opening reinforcement area: {result.value:.2f} mm²")
    print(f"  Notes: {result.notes}")
    
    # Test formula manager
    manager = FormulaManager()
    result = manager.calculate('wall_thickness', 'ASME VIII-1', 2025, inputs)
    print(f"Manager wall thickness: {result.value:.2f} mm")
    
    print("\nFormula plugin tests completed!")
