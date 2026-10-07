"""
Chamber Design Input Wizard

This module provides an interactive wizard for creating chamber.toml and nozzles.toml
files. It asks one value at a time with explanations.

Usage:
    python -m chamber.init
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tomli_w


class InputWizard:
    """
    Interactive input wizard for chamber design.
    """
    
    def __init__(self):
        """Initialize the wizard."""
        self.logger = logging.getLogger(__name__)
        self.chamber_config = self.get_default_chamber_config()
        self.nozzles_config = self.get_default_nozzles_config()
        self.current_section = ""
    
    def get_default_chamber_config(self) -> Dict[str, Any]:
        """Get default chamber configuration."""
        return {
            'schema_version': 1,
            'governing': {
                'code': 'ASME VIII-1',
                'edition': 2025,
                'route_confirmed': False
            },
            'geometry': {
                'shape': 'rectangular',
                'inner_L': 'ASK',
                'inner_W': 'ASK',
                'inner_H': 'ASK',
                'inner_ID': 'ASK',
                'inner_length': 'ASK'
            },
            'inner_wall': {
                'thickness': 'ASK',
                'material_spec': 'SA-240',
                'grade': '304L',
                'product_form': 'plate',
                'corrosion_allowance': 'ASK',
                'joint_category': 'ASK',
                'rt_extent': 'ASK',
                'joint_efficiency': 'LOOKUP',
                'allowable_stress': 'LOOKUP'
            },
            'jacket': {
                'gap': 'ASK',
                'outer_wall_thickness': 'ASK',
                'outer_material_spec': 'SA-240',
                'outer_grade': '304L',
                'outer_product_form': 'plate',
                'outer_corrosion_allowance': 'ASK',
                'outer_allowable_stress': 'LOOKUP',
                'ribs': {
                    'structural_credit': 'none',
                    'drawing_note': '',
                    'plug_weld_check': False
                }
            },
            'stiffeners': {
                'present': 'ASK',
                'pitch': 'ASK',
                'section': 'ASK'
            },
            'load_cases': [],
            'verified_data': {
                'allowables_csv': 'data/verified/allowables.csv',
                'ext_pressure_csv': 'data/verified/ext_pressure_charts.csv',
                'verified_by_user': False
            },
            'output': {
                'markdown_report': 'reports/chamber_report.md',
                'cite': True
            }
        }
    
    def get_default_nozzles_config(self) -> Dict[str, Any]:
        """Get default nozzles configuration."""
        return {
            'schema_version': 1,
            'flange_defaults': {
                'standard': 'B16.5',
                'rating_class': 150,
                'material_spec': 'ASK',
                'grade': '304L',
                'product_form': 'ASK',
                'material_group': 'ASK',
                'flange_type': 'ASK',
                'facing': 'ASK'
            },
            'spacing': {
                'datum': 'ASK',
                'min_edge_distance': 'LOOKUP',
                'check_reinforcement_overlap': True
            },
            'nozzle': []
        }
    
    def run(self):
        """Run the interactive wizard."""
        print("=" * 70)
        print("ASME BPVC Vacuum Chamber Design Assistant - Input Wizard")
        print("=" * 70)
        print("\nThis wizard will guide you through creating the input files.")
        print("Enter 'skip' to leave a value blank (you can fill it later).")
        print("Enter 'help' for more information about a field.\n")
        
        # Main menu
        while True:
            print("\nMain Menu:")
            print("  1. Governing code and edition")
            print("  2. Chamber geometry")
            print("  3. Inner wall properties")
            print("  4. Jacket properties")
            print("  5. Stiffeners")
            print("  6. Load cases")
            print("  7. Nozzles")
            print("  8. Flange defaults")
            print("  9. Save and exit")
            print("  0. Exit without saving")
            
            choice = input("\nSelect a section (0-9): ").strip()
            
            if choice == '1':
                self.edit_governing()
            elif choice == '2':
                self.edit_geometry()
            elif choice == '3':
                self.edit_inner_wall()
            elif choice == '4':
                self.edit_jacket()
            elif choice == '5':
                self.edit_stiffeners()
            elif choice == '6':
                self.edit_load_cases()
            elif choice == '7':
                self.edit_nozzles()
            elif choice == '8':
                self.edit_flange_defaults()
            elif choice == '9':
                if self.save_config():
                    print("\nConfiguration saved successfully!")
                    print(f"  chamber.toml: {self.chamber_config.get('output', {}).get('markdown_report', 'chamber.toml')}")
                    print(f"  nozzles.toml: nozzles.toml")
                break
            elif choice == '0':
                print("\nExiting without saving.")
                break
            else:
                print("Invalid choice. Please enter a number between 0 and 9.")
    
    def edit_governing(self):
        """Edit governing code and edition."""
        self.current_section = "Governing Code"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        governing = self.chamber_config.get('governing', {})
        
        code = self.get_input(
            "Code",
            governing.get('code', 'ASME VIII-1'),
            "The governing code (e.g., ASME VIII-1, ASME VIII-2)",
            ['ASME VIII-1', 'ASME VIII-2']
        )
        governing['code'] = code
        
        edition = self.get_input(
            "Edition",
            str(governing.get('edition', 2025)),
            "The edition year of the code",
            ['2025', '2023', '2021', '2019']
        )
        governing['edition'] = int(edition) if edition.isdigit() else 2025
        
        route_confirmed = self.get_boolean_input(
            "Route confirmed",
            governing.get('route_confirmed', False),
            "Has the rule path been confirmed?"
        )
        governing['route_confirmed'] = route_confirmed
        
        self.chamber_config['governing'] = governing
    
    def edit_geometry(self):
        """Edit chamber geometry."""
        self.current_section = "Chamber Geometry"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        geometry = self.chamber_config.get('geometry', {})
        
        shape = self.get_input(
            "Shape",
            geometry.get('shape', 'rectangular'),
            "The shape of the chamber",
            ['rectangular', 'circular']
        )
        geometry['shape'] = shape
        
        if shape == 'rectangular':
            geometry['inner_L'] = self.get_input(
                "Inner length (L)",
                geometry.get('inner_L', 'ASK'),
                "Length of the chamber (mm)",
                None,
                'float'
            )
            geometry['inner_W'] = self.get_input(
                "Inner width (W)",
                geometry.get('inner_W', 'ASK'),
                "Width of the chamber (mm)",
                None,
                'float'
            )
            geometry['inner_H'] = self.get_input(
                "Inner height (H)",
                geometry.get('inner_H', 'ASK'),
                "Height of the chamber (mm)",
                None,
                'float'
            )
        else:  # circular
            geometry['inner_ID'] = self.get_input(
                "Inner diameter (ID)",
                geometry.get('inner_ID', 'ASK'),
                "Inner diameter of the chamber (mm)",
                None,
                'float'
            )
            geometry['inner_length'] = self.get_input(
                "Inner length",
                geometry.get('inner_length', 'ASK'),
                "Length of the cylindrical chamber (mm)",
                None,
                'float'
            )
        
        self.chamber_config['geometry'] = geometry
    
    def edit_inner_wall(self):
        """Edit inner wall properties."""
        self.current_section = "Inner Wall Properties"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        inner_wall = self.chamber_config.get('inner_wall', {})
        
        inner_wall['thickness'] = self.get_input(
            "Thickness",
            inner_wall.get('thickness', 'ASK'),
            "Nominal thickness of the inner wall (mm)",
            None,
            'float'
        )
        
        inner_wall['material_spec'] = self.get_input(
            "Material specification",
            inner_wall.get('material_spec', 'SA-240'),
            "Material specification (e.g., SA-240 for 304L plate)",
            ['SA-240', 'SA-249', 'SA-312']
        )
        
        inner_wall['grade'] = self.get_input(
            "Grade",
            inner_wall.get('grade', '304L'),
            "Material grade (e.g., 304L, 316L)",
            ['304L', '316L', '304', '316']
        )
        
        inner_wall['product_form'] = self.get_input(
            "Product form",
            inner_wall.get('product_form', 'plate'),
            "Product form",
            ['plate', 'sheet', 'strip']
        )
        
        inner_wall['corrosion_allowance'] = self.get_input(
            "Corrosion allowance",
            inner_wall.get('corrosion_allowance', 'ASK'),
            "Corrosion allowance (mm)",
            None,
            'float'
        )
        
        inner_wall['joint_category'] = self.get_input(
            "Joint category",
            inner_wall.get('joint_category', 'ASK'),
            "Joint category from the drawing",
            None
        )
        
        inner_wall['rt_extent'] = self.get_input(
            "RT extent",
            inner_wall.get('rt_extent', 'ASK'),
            "Radiographic testing extent (full, spot, none)",
            ['full', 'spot', 'none']
        )
        
        inner_wall['joint_efficiency'] = self.get_input(
            "Joint efficiency",
            inner_wall.get('joint_efficiency', 'LOOKUP'),
            "Joint efficiency factor (0-1). Can be LOOKUP to retrieve from code.",
            None,
            'float'
        )
        
        inner_wall['allowable_stress'] = self.get_input(
            "Allowable stress",
            inner_wall.get('allowable_stress', 'LOOKUP'),
            "Allowable stress (MPa). Can be LOOKUP to retrieve from Section II-D.",
            None,
            'float'
        )
        
        self.chamber_config['inner_wall'] = inner_wall
    
    def edit_jacket(self):
        """Edit jacket properties."""
        self.current_section = "Jacket Properties"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        jacket = self.chamber_config.get('jacket', {})
        
        jacket['gap'] = self.get_input(
            "Gap",
            jacket.get('gap', 'ASK'),
            "Gap between inner wall and jacket (mm)",
            None,
            'float'
        )
        
        jacket['outer_wall_thickness'] = self.get_input(
            "Outer wall thickness",
            jacket.get('outer_wall_thickness', 'ASK'),
            "Nominal thickness of the jacket outer wall (mm)",
            None,
            'float'
        )
        
        jacket['outer_material_spec'] = self.get_input(
            "Outer material specification",
            jacket.get('outer_material_spec', 'SA-240'),
            "Material specification for jacket outer wall",
            ['SA-240', 'SA-249']
        )
        
        jacket['outer_grade'] = self.get_input(
            "Outer grade",
            jacket.get('outer_grade', '304L'),
            "Material grade for jacket outer wall",
            ['304L', '316L']
        )
        
        jacket['outer_product_form'] = self.get_input(
            "Outer product form",
            jacket.get('outer_product_form', 'plate'),
            "Product form for jacket outer wall",
            ['plate', 'sheet']
        )
        
        jacket['outer_corrosion_allowance'] = self.get_input(
            "Outer corrosion allowance",
            jacket.get('outer_corrosion_allowance', 'ASK'),
            "Corrosion allowance for jacket (mm)",
            None,
            'float'
        )
        
        jacket['outer_allowable_stress'] = self.get_input(
            "Outer allowable stress",
            jacket.get('outer_allowable_stress', 'LOOKUP'),
            "Allowable stress for jacket (MPa)",
            None,
            'float'
        )
        
        # Edit ribs
        self.edit_ribs(jacket)
        
        self.chamber_config['jacket'] = jacket
    
    def edit_ribs(self, jacket: Dict[str, Any]):
        """Edit jacket ribs properties."""
        ribs = jacket.get('ribs', {})
        
        structural_credit = self.get_input(
            "Structural credit",
            ribs.get('structural_credit', 'none'),
            "Whether to take structural credit for ribs (none, panel, fea)",
            ['none', 'panel', 'fea']
        )
        ribs['structural_credit'] = structural_credit
        
        if structural_credit == 'panel':
            ribs['drawing_note'] = self.get_input(
                "Drawing note",
                ribs.get('drawing_note', ''),
                "Label for the report (from drawing)",
                None
            )
            ribs['plug_weld_check'] = self.get_boolean_input(
                "Plug weld check",
                ribs.get('plug_weld_check', False),
                "Whether to check plug weld strength"
            )
        elif structural_credit == 'fea':
            ribs['results_csv'] = self.get_input(
                "FEA results CSV",
                ribs.get('results_csv', 'data/verified/fea_results.csv'),
                "Path to FEA results CSV file",
                None
            )
            ribs['acceptance_basis'] = self.get_input(
                "Acceptance basis",
                ribs.get('acceptance_basis', 'ASK'),
                "The code criteria for FEA results",
                None
            )
        
        jacket['ribs'] = ribs
    
    def edit_stiffeners(self):
        """Edit stiffeners."""
        self.current_section = "Stiffeners"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        stiffeners = self.chamber_config.get('stiffeners', {})
        
        stiffeners['present'] = self.get_boolean_input(
            "Present",
            stiffeners.get('present', 'ASK'),
            "Whether external stiffeners are present"
        )
        
        if stiffeners['present']:
            stiffeners['pitch'] = self.get_input(
                "Pitch",
                stiffeners.get('pitch', 'ASK'),
                "Pitch between stiffeners (mm)",
                None,
                'float'
            )
            stiffeners['section'] = self.get_input(
                "Section",
                stiffeners.get('section', 'ASK'),
                "Section size (e.g., 100x10 flat bar)",
                None
            )
        
        self.chamber_config['stiffeners'] = stiffeners
    
    def edit_load_cases(self):
        """Edit load cases."""
        self.current_section = "Load Cases"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        load_cases = self.chamber_config.get('load_cases', [])
        
        while True:
            print("\nLoad Cases:")
            for i, lc in enumerate(load_cases, 1):
                print(f"  {i}. {lc.get('name', 'unnamed')}")
            
            print("\nOptions:")
            print("  a. Add new load case")
            print("  e. Edit existing load case")
            print("  d. Delete load case")
            print("  b. Back to main menu")
            
            choice = input("\nSelect option: ").strip().lower()
            
            if choice == 'a':
                self.add_load_case(load_cases)
            elif choice == 'e':
                self.edit_existing_load_case(load_cases)
            elif choice == 'd':
                self.delete_load_case(load_cases)
            elif choice == 'b':
                self.chamber_config['load_cases'] = load_cases
                break
            else:
                print("Invalid choice.")
    
    def add_load_case(self, load_cases: List[Dict[str, Any]]):
        """Add a new load case."""
        load_case = {}
        
        load_case['name'] = self.get_input(
            "Name",
            '',
            "Name of the load case (e.g., operating_vacuum)",
            None
        )
        
        load_case['chamber_pressure'] = self.get_input(
            "Chamber pressure",
            0.0,
            "Chamber pressure in MPa (gauge). Negative for vacuum.",
            None,
            'float'
        )
        
        load_case['jacket_pressure'] = self.get_input(
            "Jacket pressure",
            'ASK',
            "Jacket pressure in MPa (gauge)",
            None,
            'float'
        )
        
        load_case['external_pressure'] = self.get_input(
            "External pressure",
            0.0,
            "External pressure in MPa (gauge)",
            None,
            'float'
        )
        
        load_case['temperature_inner'] = self.get_input(
            "Inner temperature",
            'ASK',
            "Inner wall temperature in degC",
            None,
            'float'
        )
        
        load_case['temperature_jacket'] = self.get_input(
            "Jacket temperature",
            'ASK',
            "Jacket water temperature in degC",
            None,
            'float'
        )
        
        load_cases.append(load_case)
    
    def edit_existing_load_case(self, load_cases: List[Dict[str, Any]]):
        """Edit an existing load case."""
        if not load_cases:
            print("No load cases to edit.")
            return
        
        print("\nSelect load case to edit:")
        for i, lc in enumerate(load_cases, 1):
            print(f"  {i}. {lc.get('name', 'unnamed')}")
        
        try:
            choice = int(input("\nLoad case number: ").strip())
            if 1 <= choice <= len(load_cases):
                load_case = load_cases[choice - 1]
                
                load_case['name'] = self.get_input(
                    "Name",
                    load_case.get('name', ''),
                    "Name of the load case",
                    None
                )
                
                load_case['chamber_pressure'] = self.get_input(
                    "Chamber pressure",
                    load_case.get('chamber_pressure', 0.0),
                    "Chamber pressure in MPa (gauge)",
                    None,
                    'float'
                )
                
                load_case['jacket_pressure'] = self.get_input(
                    "Jacket pressure",
                    load_case.get('jacket_pressure', 'ASK'),
                    "Jacket pressure in MPa (gauge)",
                    None,
                    'float'
                )
                
                load_case['external_pressure'] = self.get_input(
                    "External pressure",
                    load_case.get('external_pressure', 0.0),
                    "External pressure in MPa (gauge)",
                    None,
                    'float'
                )
                
                load_case['temperature_inner'] = self.get_input(
                    "Inner temperature",
                    load_case.get('temperature_inner', 'ASK'),
                    "Inner wall temperature in degC",
                    None,
                    'float'
                )
                
                load_case['temperature_jacket'] = self.get_input(
                    "Jacket temperature",
                    load_case.get('temperature_jacket', 'ASK'),
                    "Jacket water temperature in degC",
                    None,
                    'float'
                )
        except ValueError:
            print("Invalid selection.")
    
    def delete_load_case(self, load_cases: List[Dict[str, Any]]):
        """Delete a load case."""
        if not load_cases:
            print("No load cases to delete.")
            return
        
        print("\nSelect load case to delete:")
        for i, lc in enumerate(load_cases, 1):
            print(f"  {i}. {lc.get('name', 'unnamed')}")
        
        try:
            choice = int(input("\nLoad case number: ").strip())
            if 1 <= choice <= len(load_cases):
                del load_cases[choice - 1]
        except ValueError:
            print("Invalid selection.")
    
    def edit_nozzles(self):
        """Edit nozzles."""
        self.current_section = "Nozzles"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        nozzles = self.nozzles_config.get('nozzle', [])
        
        while True:
            print("\nNozzles:")
            for i, nozzle in enumerate(nozzles, 1):
                print(f"  {i}. {nozzle.get('id', 'unnamed')}")
            
            print("\nOptions:")
            print("  a. Add new nozzle")
            print("  e. Edit existing nozzle")
            print("  d. Delete nozzle")
            print("  b. Back to main menu")
            
            choice = input("\nSelect option: ").strip().lower()
            
            if choice == 'a':
                self.add_nozzle(nozzles)
            elif choice == 'e':
                self.edit_existing_nozzle(nozzles)
            elif choice == 'd':
                self.delete_nozzle(nozzles)
            elif choice == 'b':
                self.nozzles_config['nozzle'] = nozzles
                break
            else:
                print("Invalid choice.")
    
    def add_nozzle(self, nozzles: List[Dict[str, Any]]):
        """Add a new nozzle."""
        nozzle = {}
        
        nozzle['id'] = self.get_input(
            "ID",
            '',
            "Unique identifier for the nozzle (e.g., N1, N2)",
            None
        )
        
        nozzle['service'] = self.get_input(
            "Service",
            'ASK',
            "Service description (e.g., vacuum, water, instrument)",
            None
        )
        
        nozzle['nps'] = self.get_input(
            "NPS",
            'ASK',
            "Nominal Pipe Size",
            None
        )
        
        nozzle['schedule'] = self.get_input(
            "Schedule",
            'ASK',
            "Pipe schedule",
            ['40', '80', '160', 'custom']
        )
        
        nozzle['wall'] = self.get_input(
            "Wall",
            'ASK',
            "Which wall the nozzle is on",
            ['front', 'back', 'left', 'right', 'top', 'bottom', 'shell', 'head']
        )
        
        nozzle['x'] = self.get_input(
            "X position",
            'ASK',
            "X position from datum (mm)",
            None,
            'float'
        )
        
        nozzle['y'] = self.get_input(
            "Y position",
            'ASK',
            "Y position from datum (mm)",
            None,
            'float'
        )
        
        nozzle['projection_outward'] = self.get_input(
            "Projection outward",
            'ASK',
            "Projection outward from outer jacket surface (mm)",
            None,
            'float'
        )
        
        nozzle['projection_inward'] = self.get_input(
            "Projection inward",
            'ASK',
            "Projection inward into chamber (mm)",
            None,
            'float'
        )
        
        # Inner wall opening
        inner_opening = {}
        inner_opening['shape'] = self.get_input(
            "Inner opening shape",
            'circular',
            "Shape of opening in inner wall",
            ['circular', 'oval', 'slot']
        )
        inner_opening['diameter'] = self.get_input(
            "Inner opening diameter",
            'ASK',
            "Diameter of opening in inner wall (mm)",
            None,
            'float'
        )
        inner_opening['neck_to_wall_weld_type'] = self.get_input(
            "Neck to wall weld type",
            'ASK',
            "Type of weld between neck and inner wall",
            None
        )
        inner_opening['neck_to_wall_weld_size'] = self.get_input(
            "Neck to wall weld size",
            'ASK',
            "Size of weld between neck and inner wall (mm)",
            None,
            'float'
        )
        nozzle['inner_wall_opening'] = inner_opening
        
        # Jacket penetration
        jacket_penetration = {}
        jacket_penetration['closure_type'] = self.get_input(
            "Closure type",
            'ASK',
            "Type of closure around nozzle in jacket",
            ['ring', 'sleeve', 'other']
        )
        jacket_penetration['opening_diameter_outer_wall'] = self.get_input(
            "Outer wall opening diameter",
            'ASK',
            "Diameter of opening in jacket outer wall (mm)",
            None,
            'float'
        )
        jacket_penetration['neck_to_outer_wall_weld_type'] = self.get_input(
            "Neck to outer wall weld type",
            'ASK',
            "Type of weld between neck and outer wall",
            None
        )
        jacket_penetration['neck_to_outer_wall_weld_size'] = self.get_input(
            "Neck to outer wall weld size",
            'ASK',
            "Size of weld between neck and outer wall (mm)",
            None,
            'float'
        )
        nozzle['jacket_penetration'] = jacket_penetration
        
        # Pad
        pad = {}
        pad['present'] = self.get_boolean_input(
            "Pad present",
            False,
            "Whether a reinforcement pad is present"
        )
        if pad['present']:
            pad['thickness'] = self.get_input(
                "Pad thickness",
                'ASK',
                "Thickness of reinforcement pad (mm)",
                None,
                'float'
            )
            pad['outer_dimension'] = self.get_input(
                "Pad outer dimension",
                'ASK',
                "Outer dimension of pad (mm)",
                None,
                'float'
            )
            pad['material_spec'] = self.get_input(
                "Pad material specification",
                'ASK',
                "Material specification for pad",
                None
            )
        nozzle['pad'] = pad
        
        # External loads
        external_loads = {}
        external_loads['present'] = self.get_boolean_input(
            "External loads present",
            False,
            "Whether external loads are applied to the nozzle"
        )
        if external_loads['present']:
            external_loads['note'] = self.get_input(
                "External loads note",
                'ASK',
                "Description of external loads",
                None
            )
        nozzle['external_loads'] = external_loads
        
        # Flange rating check
        nozzle['flange_rating_check'] = self.get_boolean_input(
            "Flange rating check",
            False,
            "Whether to check flange rating"
        )
        
        nozzles.append(nozzle)
    
    def edit_existing_nozzle(self, nozzles: List[Dict[str, Any]]):
        """Edit an existing nozzle."""
        if not nozzles:
            print("No nozzles to edit.")
            return
        
        print("\nSelect nozzle to edit:")
        for i, nozzle in enumerate(nozzles, 1):
            print(f"  {i}. {nozzle.get('id', 'unnamed')}")
        
        try:
            choice = int(input("\nNozzle number: ").strip())
            if 1 <= choice <= len(nozzles):
                nozzle = nozzles[choice - 1]
                
                nozzle['id'] = self.get_input(
                    "ID",
                    nozzle.get('id', ''),
                    "Unique identifier for the nozzle",
                    None
                )
                
                nozzle['service'] = self.get_input(
                    "Service",
                    nozzle.get('service', 'ASK'),
                    "Service description",
                    None
                )
                
                nozzle['nps'] = self.get_input(
                    "NPS",
                    nozzle.get('nps', 'ASK'),
                    "Nominal Pipe Size",
                    None
                )
        except ValueError:
            print("Invalid selection.")
    
    def delete_nozzle(self, nozzles: List[Dict[str, Any]]):
        """Delete a nozzle."""
        if not nozzles:
            print("No nozzles to delete.")
            return
        
        print("\nSelect nozzle to delete:")
        for i, nozzle in enumerate(nozzles, 1):
            print(f"  {i}. {nozzle.get('id', 'unnamed')}")
        
        try:
            choice = int(input("\nNozzle number: ").strip())
            if 1 <= choice <= len(nozzles):
                del nozzles[choice - 1]
        except ValueError:
            print("Invalid selection.")
    
    def edit_flange_defaults(self):
        """Edit flange defaults."""
        self.current_section = "Flange Defaults"
        print(f"\n{self.current_section}")
        print("-" * 40)
        
        flange_defaults = self.nozzles_config.get('flange_defaults', {})
        
        flange_defaults['standard'] = self.get_input(
            "Standard",
            flange_defaults.get('standard', 'B16.5'),
            "Flange standard",
            ['B16.5']
        )
        
        flange_defaults['rating_class'] = self.get_input(
            "Rating class",
            str(flange_defaults.get('rating_class', 150)),
            "Flange rating class",
            ['150', '300', '600', '900', '1500', '2500']
        )
        flange_defaults['rating_class'] = int(flange_defaults['rating_class'])
        
        flange_defaults['material_spec'] = self.get_input(
            "Material specification",
            flange_defaults.get('material_spec', 'ASK'),
            "Flange material specification",
            None
        )
        
        flange_defaults['grade'] = self.get_input(
            "Grade",
            flange_defaults.get('grade', '304L'),
            "Flange material grade",
            ['304L', '316L']
        )
        
        flange_defaults['product_form'] = self.get_input(
            "Product form",
            flange_defaults.get('product_form', 'ASK'),
            "Flange product form",
            ['forging', 'plate', 'bar']
        )
        
        flange_defaults['material_group'] = self.get_input(
            "Material group",
            flange_defaults.get('material_group', 'ASK'),
            "B16.5 material group",
            None
        )
        
        flange_defaults['flange_type'] = self.get_input(
            "Flange type",
            flange_defaults.get('flange_type', 'ASK'),
            "Type of flange",
            ['weld neck', 'slip-on', 'blind']
        )
        
        flange_defaults['facing'] = self.get_input(
            "Facing",
            flange_defaults.get('facing', 'ASK'),
            "Flange facing type",
            ['RF', 'FF']
        )
        
        self.nozzles_config['flange_defaults'] = flange_defaults
    
    def get_input(self, name: str, default: Any, description: str, 
                 options: Optional[List[str]] = None, 
                 input_type: Optional[str] = None) -> Any:
        """
        Get input from user with validation.
        
        Args:
            name: Input name
            default: Default value
            description: Description of the input
            options: List of valid options (for dropdown-like selection)
            input_type: Type of input (int, float, str)
            
        Returns:
            User input value
        """
        while True:
            print(f"\n{name}:")
            print(f"  Description: {description}")
            if options:
                print(f"  Options: {', '.join(options)}")
            print(f"  Current: {default}")
            print(f"  Enter value or 'skip' to leave as default, 'help' for more info")
            
            user_input = input("  > ").strip()
            
            if user_input.lower() == 'skip':
                return default
            
            if user_input.lower() == 'help':
                print(f"\n{description}")
                if options:
                    print(f"Valid options: {', '.join(options)}")
                continue
            
            if not user_input:
                return default
            
            # Validate against options
            if options and user_input not in options:
                print(f"Invalid option. Please choose from: {', '.join(options)}")
                continue
            
            # Convert to appropriate type
            if input_type == 'int':
                try:
                    return int(user_input)
                except ValueError:
                    print("Please enter a valid integer.")
                    continue
            
            if input_type == 'float':
                try:
                    return float(user_input)
                except ValueError:
                    print("Please enter a valid number.")
                    continue
            
            return user_input
    
    def get_boolean_input(self, name: str, default: bool, description: str) -> bool:
        """
        Get boolean input from user.
        
        Args:
            name: Input name
            default: Default value
            description: Description of the input
            
        Returns:
            Boolean value
        """
        while True:
            print(f"\n{name}:")
            print(f"  Description: {description}")
            print(f"  Current: {'Yes' if default else 'No'}")
            print(f"  Enter 'y' or 'n', or 'skip' to keep current")
            
            user_input = input("  > ").strip().lower()
            
            if user_input == 'skip':
                return default
            
            if user_input in ['y', 'yes', 't', 'true', '1']:
                return True
            
            if user_input in ['n', 'no', 'f', 'false', '0']:
                return False
            
            print("Please enter 'y' or 'n'.")
    
    def save_config(self) -> bool:
        """Save configuration to files."""
        try:
            # Save chamber.toml
            chamber_path = self.chamber_config.get('output', {}).get('markdown_report', 'chamber.toml')
            chamber_path = chamber_path.replace('reports/chamber_report.md', 'chamber.toml')
            
            with open('chamber.toml', 'wb') as f:
                tomli_w.dump(self.chamber_config, f)
            
            # Save nozzles.toml
            with open('nozzles.toml', 'wb') as f:
                tomli_w.dump(self.nozzles_config, f)
            
            return True
        except Exception as e:
            print(f"Failed to save configuration: {str(e)}")
            return False


def main():
    """Main entry point for the input wizard."""
    print("Starting ASME BPVC Vacuum Chamber Design Assistant - Input Wizard\n")
    
    wizard = InputWizard()
    wizard.run()


if __name__ == '__main__':
    main()
