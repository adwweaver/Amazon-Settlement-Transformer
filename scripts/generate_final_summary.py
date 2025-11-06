#!/usr/bin/env python3
"""
Generate comprehensive summary of Zoho posting status:
- What's been posted
- What needs to be added
- What needs to be changed/deleted

Usage:
  python scripts/generate_final_summary.py --output final_summary.csv
"""

import argparse
from pathlib import Path
import pandas as pd
from typing import Dict, List

from zoho_sync import ZohoBooks
from compare_zoho_status import find_local_settlements, get_local_files, count_local_lines, check_journal_in_zoho


def main():
    parser = argparse.ArgumentParser(description='Generate final posting summary')
    parser.add_argument('--output', default='final_summary.csv', help='Output CSV file')
    args = parser.parse_args()
    
    output_file = Path(args.output)
    zoho = ZohoBooks()
    
    settlements = find_local_settlements()
    
    if not settlements:
        print("No local settlements found.")
        return
    
    print("=" * 80)
    print("GENERATING FINAL SUMMARY")
    print("=" * 80)
    print(f"Checking {len(settlements)} settlements...")
    print()
    
    results = []
    
    for settlement_id in settlements:
        print(f"Settlement {settlement_id}:")
        
        files = get_local_files(settlement_id)
        local_counts = count_local_lines(files)
        journal_status = check_journal_in_zoho(zoho, settlement_id)
        
        # Check invoices in Zoho
        invoice_file = files['invoice']
        local_invoice_count = local_counts['invoice']
        zoho_invoice_count = 0
        
        if invoice_file.exists() and local_invoice_count > 0:
            try:
                api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
                if api_result.get('code') == 0:
                    zoho_invoices = api_result.get('invoices', [])
                    zoho_invoice_count = len(zoho_invoices)
            except:
                pass
        
        # Check payments
        payment_file = files['payment']
        local_payment_count = local_counts['payment']
        
        result = {
            'Settlement_ID': settlement_id,
            'Journal_Local_Lines': local_counts['journal'],
            'Journal_In_Zoho': 'YES' if journal_status['exists'] else 'NO',
            'Journal_Zoho_ID': journal_status.get('journal_id', ''),
            'Journal_Status': 'POSTED' if journal_status['exists'] else 'NEEDS_POSTING',
            'Invoice_Local_Count': local_invoice_count,
            'Invoice_In_Zoho_Count': zoho_invoice_count,
            'Invoice_Missing': max(0, local_invoice_count - zoho_invoice_count),
            'Invoice_Status': 'COMPLETE' if zoho_invoice_count >= local_invoice_count else f'MISSING {local_invoice_count - zoho_invoice_count}',
            'Payment_Local_Count': local_payment_count,
            'Payment_Status': 'CHECK_REQUIRED',  # Payments harder to check individually
            'Actions_Needed': _determine_actions(journal_status, local_invoice_count, zoho_invoice_count)
        }
        
        results.append(result)
        
        print(f"  Journal: {result['Journal_Status']}")
        print(f"  Invoices: {result['Invoice_Status']}")
        print(f"  Payments: {local_payment_count} local")
        print(f"  Actions: {result['Actions_Needed']}")
        print()
    
    # Write CSV
    if results:
        df = pd.DataFrame(results)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        journals_posted = sum(1 for r in results if r['Journal_In_Zoho'] == 'YES')
        invoices_complete = sum(1 for r in results if r['Invoice_Missing'] == 0)
        total_missing_invoices = sum(r['Invoice_Missing'] for r in results)
        
        print(f"Total Settlements: {len(results)}")
        print(f"Journals Posted: {journals_posted}/{len(results)}")
        print(f"Invoices Complete: {invoices_complete}/{len(results)}")
        print(f"Total Missing Invoices: {total_missing_invoices}")
        
        print(f"\nDetailed report saved to: {output_file}")
        
        # Action summary
        print("\n" + "=" * 80)
        print("ACTION ITEMS")
        print("=" * 80)
        for r in results:
            if r['Actions_Needed'] != 'NONE':
                print(f"{r['Settlement_ID']}: {r['Actions_Needed']}")


def _determine_actions(journal_status: Dict, local_invoice_count: int, zoho_invoice_count: int) -> str:
    """Determine what actions are needed for this settlement."""
    actions = []
    
    if not journal_status['exists']:
        actions.append("POST JOURNAL")
    
    if local_invoice_count > 0:
        missing = local_invoice_count - zoho_invoice_count
        if missing > 0:
            actions.append(f"POST {missing} INVOICES")
    
    # Payments always need checking (harder to verify)
    if local_invoice_count > 0:
        actions.append("VERIFY PAYMENTS")
    
    return ', '.join(actions) if actions else 'NONE'


if __name__ == '__main__':
    main()



