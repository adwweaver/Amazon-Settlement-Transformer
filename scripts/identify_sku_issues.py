#!/usr/bin/env python3
"""
Identify invoices with incorrect SKU mappings that need to be fixed.

Compares local invoice files with what's in Zoho to find invoices that have
SKUs requiring mapping (ALLT, CRML) that weren't applied.

Usage:
  python scripts/identify_sku_issues.py --output invoices_to_fix.csv
"""

import argparse
import csv
import pandas as pd
import yaml
from pathlib import Path
from typing import Dict, List, Set

from zoho_sync import ZohoBooks


def load_sku_mapping() -> Dict[str, str]:
    """Load SKU mapping configuration."""
    mapping_file = Path("config/sku_mapping.yaml")
    if not mapping_file.exists():
        return {}
    
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
            mapping = cfg.get('sku_mapping', {}) or {}
            return {str(k): str(v) for k, v in mapping.items()}
    except Exception as e:
        print(f"Warning: Failed to load SKU mapping: {e}")
        return {}


def find_problematic_invoices(settlement_id: str, sku_mapping: Dict[str, str]) -> List[Dict]:
    """Find invoices that have SKUs requiring mapping."""
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    
    if not invoice_file.exists():
        return []
    
    try:
        df = pd.read_csv(invoice_file)
        
        if 'SKU' not in df.columns:
            return []
        
        problematic = []
        mapped_skus = set(sku_mapping.keys())
        
        for idx, row in df.iterrows():
            original_sku = str(row.get('SKU', '')).strip()
            if original_sku in mapped_skus:
                # This SKU needs mapping - check if invoice was posted with wrong SKU
                invoice_num = str(row.get('Invoice Number', row.get('Reference Number', ''))).strip()
                if invoice_num:
                    problematic.append({
                        'settlement_id': settlement_id,
                        'invoice_number': invoice_num,
                        'sku_original': original_sku,
                        'sku_should_be': sku_mapping[original_sku],
                        'item_price': row.get('Item Price', 0),
                        'quantity': row.get('Quantity', 0),
                    })
        
        return problematic
        
    except Exception as e:
        print(f"Error processing {settlement_id}: {e}")
        return []


def get_zoho_invoice_ids(zoho: ZohoBooks, settlement_id: str) -> Dict[str, str]:
    """Get mapping of invoice reference numbers to Zoho invoice IDs."""
    try:
        result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            invoices = result.get('invoices', [])
            mapping = {}
            for inv in invoices:
                ref_num = inv.get('reference_number', '')
                inv_id = inv.get('invoice_id', '')
                if ref_num:
                    mapping[ref_num] = inv_id
            return mapping
    except Exception as e:
        print(f"Warning: Could not fetch invoices for {settlement_id}: {e}")
    
    return {}


def main():
    parser = argparse.ArgumentParser(description='Identify invoices with SKU mapping issues')
    parser.add_argument('--output', default='invoices_to_fix.csv', help='Output CSV file')
    parser.add_argument('--settlement', help='Check specific settlement ID')
    args = parser.parse_args()
    
    output_file = Path(args.output)
    zoho = ZohoBooks()
    
    # Load SKU mapping
    sku_mapping = load_sku_mapping()
    print(f"SKU Mappings:")
    for orig, mapped in sku_mapping.items():
        print(f"  {orig} -> {mapped}")
    print()
    
    # Find settlements
    if args.settlement:
        settlements = [args.settlement]
    else:
        output_dir = Path("outputs")
        settlements = sorted([d.name for d in output_dir.iterdir() 
                             if d.is_dir() and d.name.isdigit()])
    
    all_issues = []
    
    print(f"Checking {len(settlements)} settlements...")
    print("=" * 80)
    
    for settlement_id in settlements:
        print(f"\nSettlement {settlement_id}:")
        
        # Find problematic invoices in local files
        problematic = find_problematic_invoices(settlement_id, sku_mapping)
        
        if not problematic:
            print("  No SKU mapping issues found")
            continue
        
        print(f"  Found {len(problematic)} invoice line(s) with SKUs requiring mapping")
        
        # Get Zoho invoice IDs
        zoho_invoice_map = get_zoho_invoice_ids(zoho, settlement_id)
        
        # Match up with Zoho
        unique_invoices = {}
        for issue in problematic:
            inv_num = issue['invoice_number']
            if inv_num not in unique_invoices:
                unique_invoices[inv_num] = {
                    'settlement_id': settlement_id,
                    'invoice_number': inv_num,
                    'zoho_invoice_id': zoho_invoice_map.get(inv_num, 'NOT_FOUND'),
                    'problematic_skus': [],
                    'needs_fix': False
                }
            
            unique_invoices[inv_num]['problematic_skus'].append({
                'original': issue['sku_original'],
                'should_be': issue['sku_should_be'],
                'price': issue['item_price'],
                'quantity': issue['quantity']
            })
        
        # Check if invoice exists in Zoho and needs fix
        for inv_num, inv_info in unique_invoices.items():
            if inv_info['zoho_invoice_id'] != 'NOT_FOUND':
                inv_info['needs_fix'] = True
                all_issues.append(inv_info)
                print(f"    Invoice {inv_num} (Zoho ID: {inv_info['zoho_invoice_id']}) - NEEDS FIX")
                for sku_info in inv_info['problematic_skus']:
                    print(f"      SKU {sku_info['original']} should be {sku_info['should_be']}")
            else:
                print(f"    Invoice {inv_num} - NOT in Zoho (will post correctly)")
    
    # Write CSV
    if all_issues:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['settlement_id', 'invoice_number', 'zoho_invoice_id', 
                         'problematic_skus', 'needs_fix']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for issue in all_issues:
                # Convert list to string for CSV
                skus_str = '; '.join([
                    f"{s['original']}->{s['should_be']}" 
                    for s in issue['problematic_skus']
                ])
                
                writer.writerow({
                    'settlement_id': issue['settlement_id'],
                    'invoice_number': issue['invoice_number'],
                    'zoho_invoice_id': issue['zoho_invoice_id'],
                    'problematic_skus': skus_str,
                    'needs_fix': 'YES' if issue['needs_fix'] else 'NO'
                })
        
        print(f"\n[SUCCESS] Generated list: {output_file}")
        print(f"  Total invoices needing fix: {len(all_issues)}")
        print(f"\n  These invoices are in Zoho with incorrect SKUs and need deletion/re-upload")
    else:
        print(f"\n[SUCCESS] No invoices need fixing!")
        print(f"  All invoices either don't have SKU mapping issues or aren't in Zoho yet")


if __name__ == '__main__':
    main()



