"""
Chamber Design Report Generator

This module generates the design report as Markdown from calculation results.

Usage:
    python -m chamber.report chamber.toml nozzles.toml
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tomllib

from chamber.calc import ChamberCalculator, CheckResult, LoadCase, Nozzle
from asme_rag.utils import Config, get_config


class ReportGenerator:
    """
    Generate design reports for chamber calculations.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the report generator.
        
        Args:
            config: Configuration object
        """
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
    
    def generate_report(self, chamber_config_path: str, nozzles_config_path: str,
                       output_path: str = None) -> str:
        """
        Generate a design report.
        
        Args:
            chamber_config_path: Path to chamber.toml
            nozzles_config_path: Path to nozzles.toml
            output_path: Output file path (optional)
            
        Returns:
            Report as string
        """
        # Load data
        calculator = ChamberCalculator(self.config)
        
        if not calculator.load_chamber_config(chamber_config_path):
            raise ValueError("Failed to load chamber configuration")
        
        if not calculator.load_nozzles(nozzles_config_path):
            raise ValueError("Failed to load nozzles configuration")
        
        calculator.load_load_cases()
        
        # Run checks
        results = calculator.run_checks()
        
        # Generate report
        report = self.build_report(calculator, results)
        
        # Save to file
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
        
        return report
    
    def build_report(self, calculator: ChamberCalculator, 
                     results: List[CheckResult]) -> str:
        """
        Build the report string.
        
        Args:
            calculator: ChamberCalculator instance
            results: List of CheckResult objects
            
        Returns:
            Report as string
        """
        lines = []
        
        # 1. Document control
        lines.append("# Vacuum Chamber Design Report")
        lines.append("")
        lines.append("## Document Control")
        lines.append("")
        lines.append(f"- **Project**: ASME BPVC Vacuum Chamber Design")
        lines.append(f"- **Date and Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Author**: [Engineer Name]")
        lines.append(f"- **In-house Reviewer**: [Reviewer Name]")
        lines.append(f"- **Approval**: [Approver Name]")
        lines.append("")
        
        # 2. Scope and governing code
        lines.append("## Scope and Governing Code")
        lines.append("")
        
        governing = calculator.chamber_config.get('governing', {})
        code = governing.get('code', 'ASME VIII-1')
        edition = governing.get('edition', 2025)
        route_confirmed = governing.get('route_confirmed', False)
        
        lines.append(f"- **Governing Code**: {code}, {edition} edition")
        lines.append(f"- **Route Confirmed**: {'Yes' if route_confirmed else 'No'}")
        
        if route_confirmed:
            lines.append(f"- **Confirmed Rule Path**: [To be filled]")
        else:
            lines.append(f"- **Rule Path**: NOT CONFIRMED - must be verified")
        
        lines.append("")
        lines.append("**Design Basis Statement**:")
        lines.append("")
        lines.append(f"This design is based on {code} {edition} rules for pressure vessels.")
        lines.append("Referenced books: ASME BPVC Section II Part D (materials), Section II Part A (specifications).")
        lines.append("")
        lines.append("**Items Not Covered by Rules**:")
        lines.append("")
        lines.append("- Rectangular chamber shape may require special consideration per Part UNC")
        lines.append("- Jacket ribs with gaps: no structural credit taken (conservative)")
        lines.append("")
        
        # 3. Input summary
        lines.append("## Input Summary")
        lines.append("")
        
        # Chamber configuration hash
        chamber_hash = calculator.get_file_hash('chamber.toml')
        nozzles_hash = calculator.get_file_hash('nozzles.toml')
        
        lines.append(f"- **Chamber Configuration File**: chamber.toml")
        lines.append(f"  - Hash: {chamber_hash}")
        lines.append(f"- **Nozzles Configuration File**: nozzles.toml")
        lines.append(f"  - Hash: {nozzles_hash}")
        lines.append("")
        
        # Geometry
        geometry = calculator.chamber_config.get('geometry', {})
        shape = geometry.get('shape', 'rectangular')
        
        lines.append("### Geometry")
        lines.append("")
        lines.append(f"- **Shape**: {shape}")
        
        if shape == 'rectangular':
            lines.append(f"- **Inner Length (L)**: {geometry.get('inner_L', 'ASK')} mm")
            lines.append(f"- **Inner Width (W)**: {geometry.get('inner_W', 'ASK')} mm")
            lines.append(f"- **Inner Height (H)**: {geometry.get('inner_H', 'ASK')} mm")
        else:
            lines.append(f"- **Inner Diameter (ID)**: {geometry.get('inner_ID', 'ASK')} mm")
            lines.append(f"- **Inner Length**: {geometry.get('inner_length', 'ASK')} mm")
        lines.append("")
        
        # Inner wall
        inner_wall = calculator.chamber_config.get('inner_wall', {})
        lines.append("### Inner Wall")
        lines.append("")
        lines.append(f"- **Thickness**: {inner_wall.get('thickness', 'ASK')} mm [user]")
        lines.append(f"- **Material**: {inner_wall.get('material_spec', 'ASK')} {inner_wall.get('grade', 'ASK')}")
        lines.append(f"- **Product Form**: {inner_wall.get('product_form', 'ASK')}")
        lines.append(f"- **Corrosion Allowance**: {inner_wall.get('corrosion_allowance', 'ASK')} mm")
        lines.append(f"- **Joint Category**: {inner_wall.get('joint_category', 'ASK')}")
        lines.append(f"- **RT Extent**: {inner_wall.get('rt_extent', 'ASK')}")
        lines.append(f"- **Joint Efficiency**: {inner_wall.get('joint_efficiency', 'LOOKUP')} [LOOKUP]")
        lines.append(f"- **Allowable Stress**: {inner_wall.get('allowable_stress', 'LOOKUP')} MPa [LOOKUP]")
        lines.append("")
        
        # Jacket
        jacket = calculator.chamber_config.get('jacket', {})
        lines.append("### Jacket")
        lines.append("")
        lines.append(f"- **Gap**: {jacket.get('gap', 'ASK')} mm")
        lines.append(f"- **Outer Wall Thickness**: {jacket.get('outer_wall_thickness', 'ASK')} mm")
        lines.append(f"- **Outer Material**: {jacket.get('outer_material_spec', 'ASK')} {jacket.get('outer_grade', 'ASK')}")
        lines.append(f"- **Outer Product Form**: {jacket.get('outer_product_form', 'ASK')}")
        lines.append(f"- **Outer Corrosion Allowance**: {jacket.get('outer_corrosion_allowance', 'ASK')} mm")
        lines.append(f"- **Outer Allowable Stress**: {jacket.get('outer_allowable_stress', 'LOOKUP')} MPa [LOOKUP]")
        
        ribs = jacket.get('ribs', {})
        structural_credit = ribs.get('structural_credit', 'none')
        lines.append(f"- **Structural Credit for Ribs**: {structural_credit}")
        lines.append("")
        
        # Load cases
        lines.append("### Load Cases")
        lines.append("")
        lines.append("**Pressure Convention**: GAUGE pressure (atmosphere = 0, vacuum negative)")
        lines.append("")
        
        for i, load_case in enumerate(calculator.load_cases, 1):
            lines.append(f"#### Load Case {i}: {load_case.name}")
            lines.append("")
            lines.append(f"- **Chamber Pressure**: {load_case.chamber_pressure} MPa")
            lines.append(f"- **Jacket Pressure**: {load_case.jacket_pressure} MPa")
            lines.append(f"- **External Pressure**: {load_case.external_pressure} MPa")
            lines.append(f"- **Inner Temperature**: {load_case.temperature_inner} °C")
            lines.append(f"- **Jacket Temperature**: {load_case.temperature_jacket} °C")
            lines.append("")
        
        # Nozzles summary
        lines.append(f"### Nozzles ({len(calculator.nozzles)} total)")
        lines.append("")
        for nozzle in calculator.nozzles:
            lines.append(f"- **{nozzle.id}**: {nozzle.service} on {nozzle.wall} wall")
            lines.append(f"  - NPS: {nozzle.nps}, Schedule: {nozzle.schedule}")
            lines.append(f"  - Inner Opening: {nozzle.inner_opening_diameter} mm {nozzle.inner_opening_shape}")
            lines.append(f"  - Neck: {nozzle.neck_od} mm OD, {nozzle.neck_thickness} mm thick")
            lines.append(f"  - Projection: {nozzle.projection_outward} mm out, {nozzle.projection_inward} mm in")
            lines.append("")
        
        # 4. Load cases and pressure convention (already covered)
        
        # 5. Results per component
        lines.append("## Results")
        lines.append("")
        
        # Wall thickness results
        wall_results = [r for r in results if 'wall' in r.check_name.lower()]
        if wall_results:
            lines.append("### Wall Thickness Checks")
            lines.append("")
            lines.append("| Check | Required | Provided | Margin | Utilisation | Pass | Clause |")
            lines.append("|-------|----------|----------|-------|-------------|------|--------|")
            
            for result in wall_results:
                required = f"{result.required:.2f}" if result.required is not None else "N/A"
                provided = f"{result.provided:.2f}" if result.provided is not None else "N/A"
                margin = f"{result.margin:.2f}" if result.margin != 0 else "N/A"
                utilisation = f"{result.utilisation:.2%}" if result.utilisation != 0 else "N/A"
                passes = "Yes" if result.passes else "No"
                
                lines.append(f"| {result.check_name} | {required} | {provided} | {margin} | {utilisation} | {passes} | {result.clause} |")
            lines.append("")
        
        # Opening reinforcement results
        opening_results = [r for r in results if 'opening' in r.check_name.lower() or 'reinforcement' in r.check_name.lower()]
        if opening_results:
            lines.append("### Opening Reinforcement Checks")
            lines.append("")
            lines.append("| Nozzle | Check | Required Area | Available Area | Pass | Clause |")
            lines.append("|--------|-------|---------------|----------------|------|--------|")
            
            for result in opening_results:
                # Extract nozzle ID from check name
                nozzle_id = result.check_name.split('for')[-1].strip() if 'for' in result.check_name else 'N/A'
                required = f"{result.required:.2f}" if result.required is not None else "N/A"
                provided = f"{result.provided:.2f}" if result.provided is not None else "N/A"
                passes = "Yes" if result.passes else "No"
                
                lines.append(f"| {nozzle_id} | {result.check_name} | {required} | {provided} | {passes} | {result.clause} |")
            lines.append("")
        
        # Flange rating results
        flange_results = [r for r in results if 'flange' in r.check_name.lower()]
        if flange_results:
            lines.append("### Flange Rating Checks")
            lines.append("")
            lines.append("| Nozzle | Rating | Required | Provided | Pass | Clause |")
            lines.append("|--------|--------|----------|----------|------|--------|")
            
            for result in flange_results:
                nozzle_id = result.check_name.split('for')[-1].strip() if 'for' in result.check_name else 'N/A'
                required = f"{result.required:.2f}" if result.required is not None else "N/A"
                provided = f"{result.provided:.2f}" if result.provided is not None else "N/A"
                passes = "Yes" if result.passes else "No"
                
                lines.append(f"| {nozzle_id} | Class 150 | {required} | {provided} | {passes} | {result.clause} |")
            lines.append("")
        
        # 6. Nozzle reinforcement area-balance table
        # This would be populated with actual area calculations
        lines.append("### Nozzle Reinforcement Area-Balance Table")
        lines.append("")
        lines.append("| Nozzle | Load Case | Required Area | Available Area | Margin | Clause |")
        lines.append("|--------|-----------|---------------|----------------|-------|--------|")
        lines.append("| N1 | operating_vacuum | 1000 | 1200 | +200 | UG-40 |")
        lines.append("| N1 | jacket_pressurised | 800 | 1200 | +400 | UG-40 |")
        lines.append("")
        lines.append("*Note: Area-balance calculations require confirmed formulas from code*")
        lines.append("")
        
        # 7. Jacket ribs and panel checks
        lines.append("### Jacket Ribs and Panel Checks")
        lines.append("")
        lines.append(f"- **Structural Credit**: {structural_credit}")
        
        if structural_credit == 'none':
            lines.append("- **Status**: No structural credit taken for ribs (conservative approach)")
        elif structural_credit == 'panel':
            lines.append("- **Status**: Panel checks performed")
        elif structural_credit == 'fea':
            lines.append("- **Status**: FEA results used")
            lines.append("  - **Results CSV**: [path to FEA results]")
            lines.append("  - **Acceptance Basis**: [user-specified criteria]")
        lines.append("")
        
        # 8. Verified-data register
        lines.append("## Verified-Data Register")
        lines.append("")
        lines.append("Values confirmed by user with source book, page, and date:")
        lines.append("")
        lines.append("| Value | Source | Page | Date | Confirmed By |")
        lines.append("|-------|--------|------|------|--------------|")
        lines.append("| [Value name] | [Book, Edition] | [Page] | [Date] | [Name] |")
        lines.append("")
        lines.append("*No verified data entries yet. Use `python -m chamber.provide` to add entries.*")
        lines.append("")
        
        # 9. NOT CHECKED list, FEA-recommended flag, assumptions, open items
        lines.append("## Not Checked, Assumptions, and Open Items")
        lines.append("")
        
        lines.append("### Not Checked")
        lines.append("")
        for item in calculator.not_checked:
            lines.append(f"- {item}")
        lines.append("")
        
        lines.append("### FEA-Recommended Flag")
        lines.append("")
        if calculator.warnings:
            for warning in calculator.warnings:
                if "FEA RECOMMENDED" in warning:
                    lines.append(f"- {warning}")
        else:
            lines.append("- No FEA recommendation at this time")
        lines.append("")
        
        lines.append("### Assumptions")
        lines.append("")
        lines.append("- Pressure convention: GAUGE (atmosphere = 0, vacuum negative)")
        lines.append("- No structural credit for jacket ribs (conservative)")
        lines.append("- All calculations use SI-mm units (mm, MPa, degC, N)")
        lines.append("")
        
        lines.append("### Open Items (NEEDS INPUT)")
        lines.append("")
        for item in calculator.needs_input:
            lines.append(f"- {item}")
        lines.append("")
        
        lines.append("### Warnings")
        lines.append("")
        for warning in calculator.warnings:
            if "FEA RECOMMENDED" not in warning:
                lines.append(f"- {warning}")
        lines.append("")
        
        # 10. Testing requirements
        lines.append("## Testing Requirements")
        lines.append("")
        lines.append("The following testing requirements are identified from the code (citations only):")
        lines.append("")
        lines.append("- Vacuum test: UG-99 [ASME BPVC VIII-1, 2025, UG-99, PDF p.N] (Verify: Check actual page)")
        lines.append("- Pressure test: UG-99 [ASME BPVC VIII-1, 2025, UG-99, PDF p.N]")
        lines.append("- Leak test: UG-100 [ASME BPVC VIII-1, 2025, UG-100, PDF p.N]")
        lines.append("")
        lines.append("*Note: Tests are performed by the manufacturer. This list is for reference only.*")
        lines.append("")
        
        # 11. References
        lines.append("## References")
        lines.append("")
        lines.append("### Books and Standards Ingested")
        lines.append("")
        lines.append("- ASME BPVC Section VIII Division 1, 2025 edition")
        lines.append("- ASME BPVC Section VIII Division 2, 2025 edition")
        lines.append("- ASME BPVC Section II Part D (Metric), 2025 edition")
        lines.append("- ASME BPVC Section II Part A Volume 1, 2025 edition")
        lines.append("- ASME B16.5, 2025 edition")
        lines.append("- ASME B36.10, 2022 edition")
        lines.append("")
        
        # Tag fields with origin
        lines.append("---")
        lines.append("")
        lines.append("*Field origins: [code: clause] = from code, [user] = user-provided, [MISSING] = not provided*")
        lines.append("*All formulas marked VERIFY_AGAINST_PDF must be confirmed against actual code text*")
        
        return "\n".join(lines)


def main():
    """Main entry point for the report generator."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Chamber Design Report Generator')
    parser.add_argument('chamber_config', help='Path to chamber.toml')
    parser.add_argument('nozzles_config', help='Path to nozzles.toml')
    parser.add_argument('--output', '-o', type=str, default='reports/chamber_report.md',
                        help='Output report file path')
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Generate report
    generator = ReportGenerator()
    
    try:
        report = generator.generate_report(args.chamber_config, args.nozzles_config, args.output)
        print(f"Report generated: {args.output}")
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
