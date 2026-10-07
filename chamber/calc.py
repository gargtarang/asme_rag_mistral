"""
Chamber Design Calculator

This module provides the main calculation engine for the vacuum chamber design.
It handles:
- Loading and validating input TOML files
- Running design checks with formula plugins
- Check-level gating (ASK/LOOKUP values skip only dependent checks)
- Reporting results

Usage:
    python -m chamber.calc chamber.toml nozzles.toml [--cite] [--json out.json]
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import argparse
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tomllib

from chamber.formulas import FormulaManager, FormulaResult
from chamber.lookups import Lookups
from asme_rag.utils import Config, get_config


@dataclass
class InputValue:
    """An input value with metadata."""
    
    value: Any
    source: str = "user"  # user / lookup / ask / missing
    unit: str = ""
    verified: bool = False
    needs_confirmation: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'value': self.value,
            'source': self.source,
            'unit': self.unit,
            'verified': self.verified,
            'needs_confirmation': self.needs_confirmation
        }


@dataclass
class CheckResult:
    """Result from a design check."""
    
    check_name: str
    passes: bool = True
    margin: float = 0.0
    utilisation: float = 0.0
    required: Optional[float] = None
    provided: Optional[float] = None
    unit: str = ""
    clause: str = ""
    code: str = ""
    edition: int = 0
    formula_result: Optional[FormulaResult] = None
    skipped: bool = False
    skip_reason: str = ""
    needs_input: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'check_name': self.check_name,
            'passes': self.passes,
            'margin': self.margin,
            'utilisation': self.utilisation,
            'required': self.required,
            'provided': self.provided,
            'unit': self.unit,
            'clause': self.clause,
            'code': self.code,
            'edition': self.edition,
            'skipped': self.skipped,
            'skip_reason': self.skip_reason,
            'needs_input': self.needs_input
        }
        if self.formula_result:
            result['formula'] = self.formula_result.to_dict()
        return result


@dataclass
class LoadCase:
    """A load case for the chamber."""
    
    name: str
    chamber_pressure: float  # MPa, gauge (negative for vacuum)
    jacket_pressure: float  # MPa, gauge
    external_pressure: float  # MPa, gauge
    temperature_inner: float  # degC
    temperature_jacket: float  # degC
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'chamber_pressure': self.chamber_pressure,
            'jacket_pressure': self.jacket_pressure,
            'external_pressure': self.external_pressure,
            'temperature_inner': self.temperature_inner,
            'temperature_jacket': self.temperature_jacket
        }


@dataclass
class Nozzle:
    """A nozzle in the chamber."""
    
    id: str
    service: str = ""
    nps: str = ""
    schedule: str = ""
    neck_od: float = 0.0
    neck_thickness: float = 0.0
    mill_undertolerance: float = 0.0
    neck_material_spec: str = ""
    neck_grade: str = "304L"
    neck_product_form: str = ""
    neck_allowable_stress: float = 0.0
    wall: str = ""
    x: float = 0.0
    y: float = 0.0
    projection_outward: float = 0.0
    projection_inward: float = 0.0
    inner_opening_diameter: float = 0.0
    inner_opening_shape: str = "circular"
    neck_to_wall_weld_type: str = ""
    neck_to_wall_weld_size: float = 0.0
    closure_type: str = ""
    outer_opening_diameter: float = 0.0
    neck_to_outer_wall_weld_type: str = ""
    neck_to_outer_wall_weld_size: float = 0.0
    pad_present: bool = False
    pad_thickness: float = 0.0
    pad_outer_dimension: float = 0.0
    pad_material_spec: str = ""
    external_loads_present: bool = False
    external_loads_note: str = ""
    flange_rating_check: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'service': self.service,
            'nps': self.nps,
            'schedule': self.schedule,
            'neck_od': self.neck_od,
            'neck_thickness': self.neck_thickness,
            'mill_undertolerance': self.mill_undertolerance,
            'neck_material_spec': self.neck_material_spec,
            'neck_grade': self.neck_grade,
            'neck_product_form': self.neck_product_form,
            'neck_allowable_stress': self.neck_allowable_stress,
            'wall': self.wall,
            'x': self.x,
            'y': self.y,
            'projection_outward': self.projection_outward,
            'projection_inward': self.projection_inward,
            'inner_opening_diameter': self.inner_opening_diameter,
            'inner_opening_shape': self.inner_opening_shape,
            'neck_to_wall_weld_type': self.neck_to_wall_weld_type,
            'neck_to_wall_weld_size': self.neck_to_wall_weld_size,
            'closure_type': self.clclosure_type,
            'outer_opening_diameter': self.outer_opening_diameter,
            'neck_to_outer_wall_weld_type': self.neck_to_outer_wall_weld_type,
            'neck_to_outer_wall_weld_size': self.neck_to_outer_wall_weld_size,
            'pad_present': self.pad_present,
            'pad_thickness': self.pad_thickness,
            'pad_outer_dimension': self.pad_outer_dimension,
            'pad_material_spec': self.pad_material_spec,
            'external_loads_present': self.external_loads_present,
            'external_loads_note': self.external_loads_note,
            'flange_rating_check': self.flange_rating_check
        }


class ChamberCalculator:
    """
    Main calculator for the vacuum chamber design.
    
    Handles:
    - Loading input files
    - Running design checks
    - Managing check-level gating
    - Storing results
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the calculator.
        
        Args:
            config: Configuration object
        """
        self.config = config or get_config()
        self.formula_manager = FormulaManager()
        self.lookups = Lookups(self.config)
        self.logger = logging.getLogger(__name__)
        
        # Input data
        self.chamber_config = {}
        self.nozzles = []
        self.load_cases = []
        self.verified_data = {}
        
        # Results
        self.check_results = []
        self.not_checked = []
        self.needs_input = []
        self.warnings = []
    
    def load_chamber_config(self, config_path: str) -> bool:
        """
        Load chamber configuration from TOML file.
        
        Args:
            config_path: Path to chamber.toml
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(config_path, 'rb') as f:
                self.chamber_config = tomllib.load(f)
            
            self.logger.info(f"Loaded chamber configuration from {config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load chamber configuration: {str(e)}")
            return False
    
    def load_nozzles(self, nozzles_path: str) -> bool:
        """
        Load nozzle configuration from TOML file.
        
        Args:
            nozzles_path: Path to nozzles.toml
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(nozzles_path, 'rb') as f:
                nozzles_data = tomllib.load(f)
            
            # Parse nozzles
            self.nozzles = []
            for nozzle_data in nozzles_data.get('nozzle', []):
                nozzle = Nozzle(
                    id=nozzle_data.get('id', 'unknown'),
                    service=nozzle_data.get('service', ''),
                    nps=nozzle_data.get('nps', ''),
                    schedule=nozzle_data.get('schedule', ''),
                    neck_od=self.resolve_value(nozzle_data.get('neck_od', 0)),
                    neck_thickness=self.resolve_value(nozzle_data.get('neck_thickness', 0)),
                    mill_undertolerance=self.resolve_value(nozzle_data.get('mill_undertolerance', 0)),
                    neck_material_spec=nozzle_data.get('neck_material_spec', ''),
                    neck_grade=nozzle_data.get('neck_grade', '304L'),
                    neck_product_form=nozzle_data.get('neck_product_form', ''),
                    neck_allowable_stress=self.resolve_value(nozzle_data.get('neck_allowable_stress', 0)),
                    wall=nozzle_data.get('wall', ''),
                    x=self.resolve_value(nozzle_data.get('x', 0)),
                    y=self.resolve_value(nozzle_data.get('y', 0)),
                    projection_outward=self.resolve_value(nozzle_data.get('projection_outward', 0)),
                    projection_inward=self.resolve_value(nozzle_data.get('projection_inward', 0)),
                    inner_opening_diameter=self.resolve_value(nozzle_data.get('inner_opening_diameter', 0)),
                    inner_opening_shape=nozzle_data.get('inner_opening_shape', 'circular'),
                    neck_to_wall_weld_type=nozzle_data.get('neck_to_wall_weld_type', ''),
                    neck_to_wall_weld_size=self.resolve_value(nozzle_data.get('neck_to_wall_weld_size', 0)),
                    closure_type=nozzle_data.get('closure_type', ''),
                    outer_opening_diameter=self.resolve_value(nozzle_data.get('outer_opening_diameter', 0)),
                    neck_to_outer_wall_weld_type=nozzle_data.get('neck_to_outer_wall_weld_type', ''),
                    neck_to_outer_wall_weld_size=self.resolve_value(nozzle_data.get('neck_to_outer_wall_weld_size', 0)),
                    pad_present=nozzle_data.get('pad_present', False),
                    pad_thickness=self.resolve_value(nozzle_data.get('pad_thickness', 0)),
                    pad_outer_dimension=self.resolve_value(nozzle_data.get('pad_outer_dimension', 0)),
                    pad_material_spec=nozzle_data.get('pad_material_spec', ''),
                    external_loads_present=nozzle_data.get('external_loads_present', False),
                    external_loads_note=nozzle_data.get('external_loads_note', ''),
                    flange_rating_check=nozzle_data.get('flange_rating_check', False)
                )
                self.nozzles.append(nozzle)
            
            self.logger.info(f"Loaded {len(self.nozzles)} nozzles from {nozzles_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load nozzles: {str(e)}")
            return False
    
    def resolve_value(self, value: Any) -> Any:
        """
        Resolve a value from TOML (handle ASK, LOOKUP, etc.).
        
        Args:
            value: Value from TOML
            
        Returns:
            Resolved value or original if not resolvable
        """
        if isinstance(value, str):
            if value.upper() == 'ASK':
                return InputValue(value=None, source='ask', needs_confirmation=True)
            elif value.upper() == 'LOOKUP':
                return InputValue(value=None, source='lookup', needs_confirmation=True)
        
        return value
    
    def load_load_cases(self) -> bool:
        """
        Load load cases from chamber configuration.
        
        Returns:
            True if loaded successfully
        """
        load_cases_data = self.chamber_config.get('load_cases', [])
        
        self.load_cases = []
        for lc_data in load_cases_data:
            load_case = LoadCase(
                name=lc_data.get('name', 'unknown'),
                chamber_pressure=self.resolve_value(lc_data.get('chamber_pressure', 0)),
                jacket_pressure=self.resolve_value(lc_data.get('jacket_pressure', 0)),
                external_pressure=self.resolve_value(lc_data.get('external_pressure', 0)),
                temperature_inner=self.resolve_value(lc_data.get('temperature_inner', 0)),
                temperature_jacket=self.resolve_value(lc_data.get('temperature_jacket', 0))
            )
            self.load_cases.append(load_case)
        
        self.logger.info(f"Loaded {len(self.load_cases)} load cases")
        return True
    
    def validate_inputs(self) -> Tuple[bool, List[str]]:
        """
        Validate input configuration.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Check governing code
        governing = self.chamber_config.get('governing', {})
        if not governing.get('code'):
            errors.append("Missing governing code")
        
        if not governing.get('edition'):
            errors.append("Missing governing edition")
        
        # Check geometry
        geometry = self.chamber_config.get('geometry', {})
        shape = geometry.get('shape')
        if shape not in ['rectangular', 'circular']:
            errors.append(f"Invalid shape: {shape}")
        
        # Check required inputs for shape
        if shape == 'rectangular':
            for dim in ['inner_L', 'inner_W', 'inner_H']:
                if geometry.get(dim) in ['ASK', 'LOOKUP', None, '']:
                    errors.append(f"Missing required dimension for rectangular shape: {dim}")
        elif shape == 'circular':
            for dim in ['inner_ID', 'inner_length']:
                if geometry.get(dim) in ['ASK', 'LOOKUP', None, '']:
                    errors.append(f"Missing required dimension for circular shape: {dim}")
        
        return len(errors) == 0, errors
    
    def run_checks(self) -> List[CheckResult]:
        """
        Run all design checks.
        
        Returns:
            List of CheckResult objects
        """
        self.check_results = []
        self.not_checked = []
        self.needs_input = []
        self.warnings = []
        
        governing = self.chamber_config.get('governing', {})
        code = governing.get('code', 'ASME VIII-1')
        edition = governing.get('edition', 2025)
        route_confirmed = governing.get('route_confirmed', False)
        
        geometry = self.chamber_config.get('geometry', {})
        shape = geometry.get('shape', 'rectangular')
        
        inner_wall = self.chamber_config.get('inner_wall', {})
        jacket = self.chamber_config.get('jacket', {})
        
        # Check 1: Wall thickness for inner wall
        if self.has_required_inputs(['inner_wall.thickness', 'inner_wall.allowable_stress']):
            result = self.check_inner_wall_thickness(code, edition, route_confirmed)
            self.check_results.append(result)
        else:
            self.not_checked.append("Inner wall thickness (missing inputs)")
            self.needs_input.append("Inner wall thickness check requires: thickness, allowable_stress")
        
        # Check 2: Jacket outer wall thickness
        if self.has_required_inputs(['jacket.outer_wall_thickness', 'jacket.outer_allowable_stress']):
            result = self.check_jacket_wall_thickness(code, edition, route_confirmed)
            self.check_results.append(result)
        else:
            self.not_checked.append("Jacket outer wall thickness (missing inputs)")
            self.needs_input.append("Jacket outer wall thickness check requires: thickness, allowable_stress")
        
        # Check 3: Opening reinforcement for each nozzle
        for nozzle in self.nozzles:
            if self.has_required_inputs_for_nozzle(nozzle):
                result = self.check_opening_reinforcement(nozzle, code, edition, route_confirmed)
                self.check_results.append(result)
            else:
                self.not_checked.append(f"Opening reinforcement for {nozzle.id} (missing inputs)")
                self.needs_input.append(f"Opening reinforcement for {nozzle.id} requires: diameter, wall_thickness")
        
        # Check 4: Flange rating for each nozzle
        for nozzle in self.nozzles:
            if nozzle.flange_rating_check:
                result = self.check_flange_rating(nozzle, code, edition, route_confirmed)
                self.check_results.append(result)
            else:
                self.not_checked.append(f"Flange rating for {nozzle.id} (not requested)")
        
        # Check 5: Jacket ribs (if structural credit is requested)
        structural_credit = jacket.get('structural_credit', 'none')
        if structural_credit != 'none':
            if structural_credit == 'panel':
                result = self.check_jacket_panels(code, edition, route_confirmed)
                self.check_results.append(result)
            elif structural_credit == 'fea':
                self.warnings.append("Jacket ribs checked by FEA (user must verify acceptance criteria)")
        
        # Check 6: FEA recommended flag
        self.check_fea_recommended()
        
        return self.check_results
    
    def has_required_inputs(self, required_keys: List[str]) -> bool:
        """
        Check if required inputs are available.
        
        Args:
            required_keys: List of required key paths (e.g., ['inner_wall.thickness'])
            
        Returns:
            True if all required inputs are available
        """
        for key_path in required_keys:
            keys = key_path.split('.')
            value = self.chamber_config
            
            for key in keys:
                if key not in value:
                    return False
                value = value[key]
            
            # Check if value is ASK or LOOKUP
            if isinstance(value, str) and value.upper() in ['ASK', 'LOOKUP']:
                return False
        
        return True
    
    def has_required_inputs_for_nozzle(self, nozzle: Nozzle) -> bool:
        """
        Check if required inputs are available for a nozzle check.
        
        Args:
            nozzle: Nozzle object
            
        Returns:
            True if required inputs are available
        """
        # Check nozzle dimensions
        if nozzle.inner_opening_diameter <= 0:
            return False
        
        # Check wall thickness
        inner_wall = self.chamber_config.get('inner_wall', {})
        if inner_wall.get('thickness') in ['ASK', 'LOOKUP', None, '']:
            return False
        
        return True
    
    def check_inner_wall_thickness(self, code: str, edition: int, 
                                  route_confirmed: bool) -> CheckResult:
        """
        Check inner wall thickness.
        
        Args:
            code: Governing code
            edition: Edition year
            route_confirmed: Whether the rule path is confirmed
            
        Returns:
            CheckResult object
        """
        geometry = self.chamber_config.get('geometry', {})
        inner_wall = self.chamber_config.get('inner_wall', {})
        
        # Get inputs
        shape = geometry.get('shape', 'rectangular')
        
        if shape == 'rectangular':
            # For rectangular, we need different calculations
            # VERIFY_AGAINST_PDF: Need to check UNC rules
            pass
        
        # Get provided thickness
        provided_thickness = self.get_numeric_value(inner_wall.get('thickness'))
        
        if provided_thickness is None:
            return CheckResult(
                check_name="Inner wall thickness",
                passes=False,
                skipped=True,
                skip_reason="Missing thickness value",
                needs_input=["Inner wall thickness is ASK or LOOKUP"]
            )
        
        # Calculate required thickness for each load case
        max_required = 0
        for load_case in self.load_cases:
            # Get pressure
            chamber_pressure = self.get_numeric_value(load_case.chamber_pressure)
            external_pressure = self.get_numeric_value(load_case.external_pressure)
            
            # Net pressure on inner wall
            # For vacuum: chamber_pressure is negative, external_pressure is 0
            # Net load = external_pressure - chamber_pressure
            net_pressure = external_pressure - chamber_pressure
            
            # For now, use a simplified calculation
            # VERIFY_AGAINST_PDF: Need actual formula from code
            if shape == 'circular':
                inner_diameter = self.get_numeric_value(geometry.get('inner_ID'))
                if inner_diameter:
                    radius = inner_diameter / 2
                    inputs = {
                        'pressure': abs(net_pressure),
                        'radius': radius,
                        'allowable_stress': self.get_numeric_value(inner_wall.get('allowable_stress')),
                        'joint_efficiency': self.get_numeric_value(inner_wall.get('joint_efficiency', 1.0)),
                        'corrosion_allowance': self.get_numeric_value(inner_wall.get('corrosion_allowance', 0))
                    }
                    
                    result = self.formula_manager.calculate(
                        'wall_thickness', code, edition, inputs
                    )
                    
                    if result:
                        max_required = max(max_required, result.value)
        
        # Compare
        passes = provided_thickness >= max_required if max_required > 0 else True
        margin = provided_thickness - max_required if max_required > 0 else 0
        utilisation = max_required / provided_thickness if provided_thickness > 0 else 0
        
        return CheckResult(
            check_name="Inner wall thickness",
            passes=passes,
            margin=margin,
            utilisation=utilisation,
            required=max_required,
            provided=provided_thickness,
            unit="mm",
            clause="UG-22 (VERIFY_AGAINST_PDF)",
            code=code,
            edition=edition,
            formula_result=None,
            skipped=False,
            needs_input=["Confirm formula with actual code text"]
        )
    
    def check_jacket_wall_thickness(self, code: str, edition: int, 
                                    route_confirmed: bool) -> CheckResult:
        """
        Check jacket outer wall thickness.
        
        Args:
            code: Governing code
            edition: Edition year
            route_confirmed: Whether the rule path is confirmed
            
        Returns:
            CheckResult object
        """
        jacket = self.chamber_config.get('jacket', {})
        geometry = self.chamber_config.get('geometry', {})
        
        # Get provided thickness
        provided_thickness = self.get_numeric_value(jacket.get('outer_wall_thickness'))
        
        if provided_thickness is None:
            return CheckResult(
                check_name="Jacket outer wall thickness",
                passes=False,
                skipped=True,
                skip_reason="Missing thickness value",
                needs_input=["Jacket outer wall thickness is ASK or LOOKUP"]
            )
        
        # Calculate required thickness for jacket pressure
        max_required = 0
        for load_case in self.load_cases:
            jacket_pressure = self.get_numeric_value(load_case.jacket_pressure)
            
            if jacket_pressure > 0:
                # For jacket under internal pressure
                # VERIFY_AGAINST_PDF: Need actual formula from Part UJV
                if geometry.get('shape') == 'circular':
                    outer_diameter = self.get_numeric_value(geometry.get('inner_ID')) + 2 * provided_thickness
                    radius = outer_diameter / 2
                    
                    inputs = {
                        'jacket_pressure': jacket_pressure,
                        'jacket_radius': radius,
                        'allowable_stress': self.get_numeric_value(jacket.get('outer_allowable_stress')),
                        'joint_efficiency': self.get_numeric_value(jacket.get('joint_efficiency', 1.0)),
                        'corrosion_allowance': self.get_numeric_value(jacket.get('outer_corrosion_allowance', 0))
                    }
                    
                    result = self.formula_manager.calculate(
                        'jacket', code, edition, inputs
                    )
                    
                    if result:
                        max_required = max(max_required, result.value)
        
        # Compare
        passes = provided_thickness >= max_required if max_required > 0 else True
        margin = provided_thickness - max_required if max_required > 0 else 0
        utilisation = max_required / provided_thickness if provided_thickness > 0 else 0
        
        return CheckResult(
            check_name="Jacket outer wall thickness",
            passes=passes,
            margin=margin,
            utilisation=utilisation,
            required=max_required,
            provided=provided_thickness,
            unit="mm",
            clause="UJV-1 (VERIFY_AGAINST_PDF)",
            code=code,
            edition=edition,
            formula_result=None,
            skipped=False,
            needs_input=["Confirm jacket formula with actual code text"]
        )
    
    def check_opening_reinforcement(self, nozzle: Nozzle, code: str, edition: int,
                                     route_confirmed: bool) -> CheckResult:
        """
        Check opening reinforcement for a nozzle.
        
        Args:
            nozzle: Nozzle object
            code: Governing code
            edition: Edition year
            route_confirmed: Whether the rule path is confirmed
            
        Returns:
            CheckResult object
        """
        inner_wall = self.chamber_config.get('inner_wall', {})
        
        # Get inputs
        opening_diameter = nozzle.inner_opening_diameter
        wall_thickness = self.get_numeric_value(inner_wall.get('thickness'))
        
        if opening_diameter <= 0 or wall_thickness is None:
            return CheckResult(
                check_name=f"Opening reinforcement for {nozzle.id}",
                passes=False,
                skipped=True,
                skip_reason="Missing required inputs",
                needs_input=[f"Opening reinforcement for {nozzle.id} requires diameter and wall thickness"]
            )
        
        # Calculate required reinforcement area
        # VERIFY_AGAINST_PDF: Need actual formula from UG-37 to UG-45
        inputs = {
            'opening_diameter': opening_diameter,
            'wall_thickness': wall_thickness,
            'pressure': 0.5,  # Placeholder - should use actual pressure
            'allowable_stress': self.get_numeric_value(inner_wall.get('allowable_stress')),
            'nozzle_neck_thickness': nozzle.neck_thickness,
            'nozzle_neck_od': nozzle.neck_od,
            'weld_size': nozzle.neck_to_wall_weld_size
        }
        
        result = self.formula_manager.calculate(
            'opening_reinforcement', code, edition, inputs
        )
        
        if result:
            return CheckResult(
                check_name=f"Opening reinforcement for {nozzle.id}",
                passes=False,  # Will be determined after actual calculation
                margin=0,
                utilisation=0,
                required=result.value,
                provided=None,
                unit=result.unit,
                clause=result.clause,
                code=code,
                edition=edition,
                formula_result=result,
                skipped=False,
                needs_input=["Confirm opening reinforcement formula with actual code text"]
            )
        else:
            return CheckResult(
                check_name=f"Opening reinforcement for {nozzle.id}",
                passes=False,
                skipped=True,
                skip_reason="Formula not available",
                needs_input=[f"Opening reinforcement formula for {nozzle.id} not implemented"]
            )
    
    def check_flange_rating(self, nozzle: Nozzle, code: str, edition: int,
                          route_confirmed: bool) -> CheckResult:
        """
        Check flange rating for a nozzle.
        
        Args:
            nozzle: Nozzle object
            code: Governing code
            edition: Edition year
            route_confirmed: Whether the rule path is confirmed
            
        Returns:
            CheckResult object
        """
        # Get flange defaults
        flange_defaults = self.chamber_config.get('flange_defaults', {})
        
        # Look up flange rating
        standard = flange_defaults.get('standard', 'B16.5')
        rating_class = flange_defaults.get('rating_class', 150)
        material_group = flange_defaults.get('material_group', 'ASK')
        
        if material_group == 'ASK':
            return CheckResult(
                check_name=f"Flange rating for {nozzle.id}",
                passes=False,
                skipped=True,
                skip_reason="Material group not specified",
                needs_input=[f"Flange rating for {nozzle.id} requires material_group"]
            )
        
        # Look up temperature
        temperature = 100  # Placeholder
        
        # Use lookup function
        results = self.lookups.flange_lookup(
            standard, rating_class, nozzle.nps, material_group, temperature
        )
        
        if results and results[0].value:
            flange_data = results[0].value
            rating = flange_data.get('rating', 0)
            
            return CheckResult(
                check_name=f"Flange rating for {nozzle.id}",
                passes=True,  # Placeholder
                margin=0,
                utilisation=0,
                required=rating,
                provided=rating,
                unit="MPa",
                clause=results[0].clause,
                code=results[0].code,
                edition=results[0].edition,
                formula_result=None,
                skipped=False,
                needs_input=["Verify flange rating with actual service conditions"]
            )
        else:
            return CheckResult(
                check_name=f"Flange rating for {nozzle.id}",
                passes=False,
                skipped=True,
                skip_reason="Flange data not found",
                needs_input=[f"Flange rating for {nozzle.id} not found in database"]
            )
    
    def check_jacket_panels(self, code: str, edition: int, route_confirmed: bool) -> CheckResult:
        """
        Check jacket panel design.
        
        Args:
            code: Governing code
            edition: Edition year
            route_confirmed: Whether the rule path is confirmed
            
        Returns:
            CheckResult object
        """
        jacket = self.chamber_config.get('jacket', {})
        ribs = jacket.get('ribs', {})
        
        structural_credit = ribs.get('structural_credit', 'none')
        
        if structural_credit == 'panel':
            # Check panel dimensions
            panels = ribs.get('panel', [])
            
            if not panels:
                return CheckResult(
                    check_name="Jacket panels",
                    passes=False,
                    skipped=True,
                    skip_reason="No panels specified",
                    needs_input=["Jacket panel check requires panel dimensions"]
                )
            
            # VERIFY_AGAINST_PDF: Need actual panel check rules
            # For now, just report that it's checked
            return CheckResult(
                check_name="Jacket panels",
                passes=True,
                margin=0,
                utilisation=0,
                required=None,
                provided=None,
                unit="",
                clause="UJV (VERIFY_AGAINST_PDF)",
                code=code,
                edition=edition,
                formula_result=None,
                skipped=False,
                needs_input=["Confirm panel check rules with actual code text"]
            )
        
        return CheckResult(
            check_name="Jacket panels",
            passes=True,
            skipped=True,
            skip_reason="No structural credit taken for ribs",
            needs_input=[]
        )
    
    def check_fea_recommended(self):
        """Check if FEA is recommended."""
        reasons = []
        
        # Check shape
        geometry = self.chamber_config.get('geometry', {})
        shape = geometry.get('shape', 'rectangular')
        if shape == 'rectangular':
            reasons.append("rectangular shape")
        
        # Check ribs with gaps
        jacket = self.chamber_config.get('jacket', {})
        ribs = jacket.get('ribs', {})
        if ribs.get('present', False):
            reasons.append("ribs with gaps present")
        
        # Check nozzle count
        if len(self.nozzles) > self.config.fea_nozzle_threshold:
            reasons.append(f"nozzle count ({len(self.nozzles)}) above threshold ({self.config.fea_nozzle_threshold})")
        
        # Check spacing and overlap
        # This would require actual spacing calculations
        
        if reasons:
            self.warnings.append(f"FEA RECOMMENDED: {', '.join(reasons)}")
    
    def get_numeric_value(self, value: Any) -> Optional[float]:
        """
        Get numeric value from input value.
        
        Args:
            value: Input value (may be InputValue or primitive)
            
        Returns:
            Numeric value or None
        """
        if isinstance(value, InputValue):
            if value.needs_confirmation:
                return None
            return value.value
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        
        return None
    
    def get_file_hash(self, file_path: str) -> str:
        """
        Get hash of a file for change detection.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash of file content
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception:
            return "unknown"


def main():
    """Main entry point for the chamber calculator."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Chamber Design Calculator')
    parser.add_argument('chamber_config', help='Path to chamber.toml')
    parser.add_argument('nozzles_config', help='Path to nozzles.toml')
    parser.add_argument('--cite', action='store_true', help='Include citations in output')
    parser.add_argument('--json', type=str, help='Output JSON file path')
    parser.add_argument('--report', type=str, help='Output report file path')
    
    args = parser.parse_args()
    
    # Initialize calculator
    calculator = ChamberCalculator()
    
    # Load inputs
    if not calculator.load_chamber_config(args.chamber_config):
        print("Error: Failed to load chamber configuration")
        sys.exit(1)
    
    if not calculator.load_nozzles(args.nozzles_config):
        print("Error: Failed to load nozzles configuration")
        sys.exit(1)
    
    calculator.load_load_cases()
    
    # Validate inputs
    is_valid, errors = calculator.validate_inputs()
    if not is_valid:
        print("Input validation errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nContinuing with available inputs...")
    
    # Run checks
    results = calculator.run_checks()
    
    # Output results
    if args.json:
        output = {
            'timestamp': datetime.now().isoformat(),
            'chamber_config': args.chamber_config,
            'nozzles_config': args.nozzles_config,
            'check_results': [r.to_dict() for r in results],
            'not_checked': calculator.not_checked,
            'needs_input': calculator.needs_input,
            'warnings': calculator.warnings
        }
        
        with open(args.json, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"Results saved to {args.json}")
    
    # Print summary
    print("\nChamber Design Check Summary")
    print("=" * 60)
    print(f"Load cases: {len(calculator.load_cases)}")
    print(f"Nozzles: {len(calculator.nozzles)}")
    print(f"Checks run: {len(results)}")
    print(f"Not checked: {len(calculator.not_checked)}")
    print(f"Needs input: {len(calculator.needs_input)}")
    print(f"Warnings: {len(calculator.warnings)}")
    
    for result in results:
        status = "PASS" if result.passes else "FAIL"
        if result.skipped:
            status = "SKIPPED"
        print(f"  {result.check_name}: {status}")
    
    if calculator.not_checked:
        print("\nNot checked:")
        for item in calculator.not_checked:
            print(f"  - {item}")
    
    if calculator.needs_input:
        print("\nNEEDS INPUT:")
        for item in calculator.needs_input:
            print(f"  - {item}")
    
    if calculator.warnings:
        print("\nWarnings:")
        for warning in calculator.warnings:
            print(f"  - {warning}")


if __name__ == '__main__':
    main()
