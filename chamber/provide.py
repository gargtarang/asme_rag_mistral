"""
Chamber Design Value Input

This module allows the user to provide confirmed values for use in calculations.
Values are stored in verified-data CSV files with source, page, and date.

Usage:
    python -m chamber.provide key=value --source "book p.N"
    python -m chamber.provide key=value --source "book p.N" --date 2025-01-01
"""

import os
import sys
import csv
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ValueProvider:
    """
    Store confirmed values from the user.
    """
    
    def __init__(self):
        """Initialize the value provider."""
        self.logger = logging.getLogger(__name__)
        self.verified_data_dir = 'data/verified'
        
        # Ensure directory exists
        os.makedirs(self.verified_data_dir, exist_ok=True)
    
    def provide_value(self, key: str, value: Any, source: str, 
                     date: Optional[str] = None) -> bool:
        """
        Store a confirmed value.
        
        Args:
            key: Value key (e.g., "allowable_stress_SA240_304L_100C")
            value: Value to store
            source: Source reference (e.g., "ASME BPVC II-D 2025 p.123")
            date: Date of confirmation (optional, defaults to today)
            
        Returns:
            True if stored successfully
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Parse the key to determine which CSV file to use
        key_lower = key.lower()
        
        if 'allowable' in key_lower or 'stress' in key_lower:
            csv_file = os.path.join(self.verified_data_dir, 'allowables.csv')
            headers = ['key', 'value', 'unit', 'material_spec', 'grade', 'product_form', 'temperature', 'source', 'page', 'date', 'notes']
        elif 'ext_pressure' in key_lower or 'external' in key_lower:
            csv_file = os.path.join(self.verified_data_dir, 'ext_pressure_charts.csv')
            headers = ['key', 'value', 'unit', 'material_spec', 'grade', 'temperature', 'chart_number', 'source', 'page', 'date', 'notes']
        elif 'fea' in key_lower:
            csv_file = os.path.join(self.verified_data_dir, 'fea_results.csv')
            headers = ['result_id', 'load_case', 'location', 'quantity', 'value', 'unit', 'source_note', 'date']
        else:
            csv_file = os.path.join(self.verified_data_dir, 'other_verified.csv')
            headers = ['key', 'value', 'unit', 'source', 'page', 'date', 'notes']
        
        # Check if file exists and has header
        file_exists = os.path.exists(csv_file)
        
        try:
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                
                # Write header if file doesn't exist
                if not file_exists:
                    writer.writeheader()
                
                # Parse key to extract metadata
                metadata = self.parse_key(key)
                
                # Create row
                row = {
                    'key': key,
                    'value': value,
                    'source': source,
                    'date': date,
                    'notes': ''
                }
                
                # Add metadata to row
                row.update(metadata)
                
                # Add unit if not in metadata
                if 'unit' not in row:
                    row['unit'] = ''
                
                # Add page if not in metadata
                if 'page' not in row and 'PDF p.' in source:
                    # Extract page number from source
                    import re
                    match = re.search(r'PDF\s+p\.(\d+)', source)
                    if match:
                        row['page'] = match.group(1)
                
                # Write row
                writer.writerow(row)
            
            self.logger.info(f"Stored value: {key} = {value} from {source}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store value: {str(e)}")
            return False
    
    def parse_key(self, key: str) -> Dict[str, str]:
        """
        Parse a key to extract metadata.
        
        Args:
            key: Value key
            
        Returns:
            Dictionary of metadata
        """
        metadata = {}
        
        # Try to extract components from key
        parts = key.split('_')
        
        for part in parts:
            if part in ['MPa', 'mm', 'degC', 'N', 'kN']:
                metadata['unit'] = part
            elif part in ['SA240', 'SA249', 'SA312']:
                metadata['material_spec'] = f"SA-{part[2:]}"
            elif part in ['304L', '316L', '304', '316']:
                metadata['grade'] = part
            elif part.replace('.', '').isdigit():
                metadata['temperature'] = part
        
        return metadata
    
    def list_values(self, csv_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List stored values.
        
        Args:
            csv_file: Specific CSV file to list (optional)
            
        Returns:
            List of value dictionaries
        """
        values = []
        
        if csv_file:
            files = [csv_file]
        else:
            files = [
                os.path.join(self.verified_data_dir, 'allowables.csv'),
                os.path.join(self.verified_data_dir, 'ext_pressure_charts.csv'),
                os.path.join(self.verified_data_dir, 'fea_results.csv'),
                os.path.join(self.verified_data_dir, 'other_verified.csv')
            ]
        
        for file_path in files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            row['_file'] = os.path.basename(file_path)
                            values.append(row)
                except Exception as e:
                    self.logger.warning(f"Failed to read {file_path}: {str(e)}")
        
        return values


def main():
    """Main entry point for the value provider."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Provide confirmed values for chamber design')
    parser.add_argument('key', help='Value key (e.g., allowable_stress_SA240_304L_100C)')
    parser.add_argument('value', help='Value to store')
    parser.add_argument('--source', '-s', required=True, help='Source reference (e.g., "ASME BPVC II-D 2025 p.123")')
    parser.add_argument('--date', '-d', help='Date of confirmation (YYYY-MM-DD)')
    parser.add_argument('--list', '-l', action='store_true', help='List stored values')
    
    args = parser.parse_args()
    
    provider = ValueProvider()
    
    if args.list:
        values = provider.list_values()
        print("\nStored Values:")
        print("=" * 80)
        for value in values:
            file_name = value.get('_file', 'unknown')
            key = value.get('key', value.get('result_id', 'unknown'))
            val = value.get('value', 'unknown')
            source = value.get('source', 'unknown')
            date = value.get('date', 'unknown')
            print(f"  [{file_name}] {key} = {val} (source: {source}, date: {date})")
        print(f"\nTotal: {len(values)} values")
    else:
        success = provider.provide_value(args.key, args.value, args.source, args.date)
        if success:
            print(f"Stored: {args.key} = {args.value} from {args.source}")
        else:
            print(f"Failed to store value")
            sys.exit(1)


if __name__ == '__main__':
    main()
