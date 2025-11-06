#!/usr/bin/env python3
"""
Compare local settlement files against what's already in Zoho Books.

Shows:
- What's already posted (can skip)
- What needs to be posted
- Potential duplicates/issues

Usage:
  python scripts/compare_zoho_status.py --output zoho_comparison.csv
"""

import argparse
import csv
import pandas as pd
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime

from zoho_sync import ZohoBooks


def find_local_settlements() -> List[str]:
    """Find all settlement IDs from local output directories."""
    output_dir = Path("outputs")
    settlements = []
    
    if not output_dir.exists():
        return settlements
    
    for item in output_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            settlements.append(item.name)
    
    return sorted(settlements)


def get_local_files(settlement_id: str) -> Dict[str, Path]:
    """Get paths to local files for a settlement."""
    base_dir = Path("outputs") / settlement_id
    return {
        'journal': base_dir / f"Journal_{settlement_id}.csv",
        'invoice': base_dir / f"Invoice_{settlement_id}.csv",
        'payment': base_dir / f"Payment_{settlement_id}.csv"
    }


def check_journal_in_zoho(zoho: ZohoBooks, settlement_id: str) -> Dict:
    """Check if journal exists in Zoho by reference number."""
    try:
        journal_id = zoho.check_existing_journal(settlement_id)
        return {
            'exists': journal_id is not None,
            'journal_id': journal_id,
            'status': 'EXISTS' if journal_id else 'MISSING'
        }
    except Exception as e:
        return {
            'exists': False,
            'journal_id': None,
            'status': f'ERROR: {str(e)}'
        }


def count_local_lines(files: Dict[str, Path]) -> Dict[str, int]:
    """Count lines in local CSV files."""
    counts = {'journal': 0, 'invoice': 0, 'payment': 0}
    
    for file_type, file_path in files.items():
        if file_path.exists():
            try:
                df = pd.read_csv(file_path)
                counts[file_type] = len(df)
            except:
                counts[file_type] = 0
    
    return counts


def get_local_invoice_numbers(invoice_file: Path) -> Set[str]:
    """Extract invoice numbers from local invoice file."""
    if not invoice_file.exists():
        return set()
    
    try:
        df = pd.read_csv(invoice_file)
        if 'Invoice Number' in df.columns:
            return set(df['Invoice Number'].dropna().astype(str).unique())
        elif 'Reference Number' in df.columns:
            return set(df['Reference Number'].dropna().astype(str).unique())
    except:
        pass
    
    return set()


def check_invoices_in_zoho(zoho: ZohoBooks, invoice_numbers: Set[str], settlement_id: str) -> Dict:
    """Check which invoice numbers exist in Zoho."""
    if not invoice_numbers:
        return {
            'total': 0,
            'found': 0,
            'missing': 0,
            'status': 'NO_INVOICES'
        }
    
    found = 0
    missing = []
    
    # Try to search by reference number (settlement ID) first
    try:
        result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            zoho_invoices = result.get('invoices', [])
            found_invoice_refs = {inv.get('reference_number', '') for inv in zoho_invoices}
            # Check if any match our local invoice numbers
            for inv_num in invoice_numbers:
                if inv_num in found_invoice_refs or settlement_id in found_invoice_refs:
                    found += 1
                else:
                    missing.append(inv_num)
        else:
            # Can't query, mark all as missing
            missing = list(invoice_numbers)
            found = 0
    except Exception as e:
        # Query failed, assume we can't check
        return {
            'total': len(invoice_numbers),
            'found': 0,
            'missing': len(invoice_numbers),
            'missing_list': list(invoice_numbers),
            'status': f'QUERY_ERROR: {str(e)}'
        }
    
    return {
        'total': len(invoice_numbers),
        'found': found,
        'missing': len(missing),
        'missing_list': missing[:10] if len(missing) > 10 else missing,  # Limit to first 10
        'status': f'{found}/{len(invoice_numbers)} FOUND' if found > 0 else 'MISSING'
    }


def main():
    parser = argparse.ArgumentParser(description='Compare local files with Zoho Books status')
    parser.add_argument('--settlement', help='Check specific settlement ID')
    parser.add_argument('--output', default='zoho_comparison.csv', help='Output CSV file')
    args = parser.parse_args()
    
    output_file = Path(args.output)
    zoho = ZohoBooks()
    
    # Get settlements to check
    if args.settlement:
        settlements = [args.settlement]
    else:
        settlements = find_local_settlements()
    
    if not settlements:
        print("No local settlements found.")
        return
    
    print(f"Checking {len(settlements)} settlements against Zoho Books...")
    print("=" * 80)
    
    results = []
    
    for settlement_id in settlements:
        print(f"\nSettlement {settlement_id}:")
        
        files = get_local_files(settlement_id)
        local_counts = count_local_lines(files)
        
        # Check journal
        journal_status = check_journal_in_zoho(zoho, settlement_id)
        
        # Check invoices
        invoice_numbers = get_local_invoice_numbers(files['invoice'])
        invoice_status = check_invoices_in_zoho(zoho, invoice_numbers, settlement_id)
        
        result = {
            'Settlement_ID': settlement_id,
            'Journal_Local_Lines': local_counts['journal'],
            'Journal_In_Zoho': 'YES' if journal_status['exists'] else 'NO',
            'Journal_Zoho_ID': journal_status.get('journal_id', ''),
            'Invoice_Local_Count': local_counts['invoice'],
            'Invoice_In_Zoho': invoice_status.get('status', 'UNKNOWN'),
            'Invoice_Found': invoice_status.get('found', 0),
            'Invoice_Missing': invoice_status.get('missing', 0),
            'Payment_Local_Count': local_counts['payment'],
            'Status': _determine_status(journal_status, invoice_status, local_counts)
        }
        
        results.append(result)
        
        # Print summary
        print(f"  Journal: {local_counts['journal']} lines locally, "
              f"{'EXISTS' if journal_status['exists'] else 'MISSING'} in Zoho")
        print(f"  Invoice: {local_counts['invoice']} lines locally, "
              f"{invoice_status.get('status', 'UNKNOWN')}")
        print(f"  Payment: {local_counts['payment']} lines locally")
        print(f"  Overall: {result['Status']}")
    
    # Write CSV
    if results:
        df = pd.DataFrame(results)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n[SUCCESS] Comparison saved to: {output_file}")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY:")
        print("=" * 80)
        total = len(results)
        journals_posted = sum(1 for r in results if r['Journal_In_Zoho'] == 'YES')
        invoices_partial = sum(1 for r in results if r['Invoice_Found'] > 0 and r['Invoice_Missing'] > 0)
        invoices_complete = sum(1 for r in results if 'FOUND' in r['Invoice_In_Zoho'] and r['Invoice_Missing'] == 0)
        completely_missing = sum(1 for r in results if r['Journal_In_Zoho'] == 'NO' and r['Invoice_Missing'] == r['Invoice_Local_Count'])
        
        print(f"Total Settlements: {total}")
        print(f"  Journals Posted: {journals_posted}")
        print(f"  Invoices Complete: {invoices_complete}")
        print(f"  Invoices Partial: {invoices_partial}")
        print(f"  Completely Missing: {completely_missing}")
        print(f"\nFull details in: {output_file}")


def _determine_status(journal_status: Dict, invoice_status: Dict, local_counts: Dict) -> str:
    """Determine overall status for a settlement."""
    journal_exists = journal_status['exists']
    invoice_count = local_counts['invoice']
    invoice_found = invoice_status.get('found', 0)
    invoice_missing = invoice_status.get('missing', 0)
    
    if invoice_count == 0:
        # No invoices to worry about
        if journal_exists:
            return "COMPLETE (journal only)"
        else:
            return "NEEDS JOURNAL"
    else:
        # Has invoices
        if journal_exists and invoice_found == invoice_count:
            return "COMPLETE"
        elif journal_exists and invoice_found > 0:
            return f"PARTIAL ({invoice_missing} invoices missing)"
        elif journal_exists:
            return "NEEDS INVOICES"
        else:
            return "NEEDS JOURNAL + INVOICES"


if __name__ == '__main__':
    main()

