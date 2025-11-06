#!/usr/bin/env python3
"""
Check what invoice number formats are actually being used in Zoho.
"""

import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from post_all_settlements import find_local_settlements


def check_zoho_invoice_formats():
    """Check actual invoice number formats in Zoho."""
    print("="*80)
    print("CHECKING ACTUAL INVOICE NUMBER FORMATS IN ZOHO")
    print("="*80)
    
    settlements = find_local_settlements()
    zoho = ZohoBooks()
    
    all_formats = {}
    total_invoices = 0
    amzn_format_count = 0
    auto_generated_count = 0
    other_format_count = 0
    
    for settlement_id in settlements:
        print(f"\n{'='*80}")
        print(f"Settlement: {settlement_id}")
        print(f"{'='*80}")
        
        print(f"  Querying Zoho (waiting 5s for rate limits)...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [ERROR] Could not query: {api_result}")
                continue
            
            zoho_invoices = api_result.get('invoices', [])
            print(f"  Found {len(zoho_invoices)} invoice(s) in Zoho")
            
            if len(zoho_invoices) == 0:
                print(f"  [SKIP] No invoices")
                continue
            
            # Check invoice number formats
            amzn_invoices = []
            auto_invoices = []
            other_invoices = []
            
            for inv in zoho_invoices:  # Check ALL invoices
                inv_num = str(inv.get('invoice_number', '')).strip()
                inv_id = str(inv.get('invoice_id', '')).strip()
                total = inv.get('total', 0)
                
                if inv_num.startswith('AMZN') and len(inv_num) == 11:  # AMZN + 7 digits
                    amzn_invoices.append((inv_num, inv_id, total))
                    amzn_format_count += 1
                elif inv_num.startswith('INV-'):
                    auto_invoices.append((inv_num, inv_id, total))
                    auto_generated_count += 1
                else:
                    other_invoices.append((inv_num, inv_id, total))
                    other_format_count += 1
                
                total_invoices += 1
            
            # Print samples
            if amzn_invoices:
                print(f"  [AMZN FORMAT] {len(amzn_invoices)} invoice(s) with AMZN format (first 5):")
                for inv_num, inv_id, total in amzn_invoices[:5]:
                    print(f"    - {inv_num} (ID: {inv_id}, Total: ${total})")
            
            if auto_invoices:
                print(f"  [AUTO-GENERATED] {len(auto_invoices)} invoice(s) with auto-generated format (first 5):")
                for inv_num, inv_id, total in auto_invoices[:5]:
                    print(f"    - {inv_num} (ID: {inv_id}, Total: ${total})")
            
            if other_invoices:
                print(f"  [OTHER FORMAT] {len(other_invoices)} invoice(s) with other format (first 5):")
                for inv_num, inv_id, total in other_invoices[:5]:
                    print(f"    - {inv_num} (ID: {inv_id}, Total: ${total})")
            
            # Store format counts for summary
            all_formats[settlement_id] = {
                'total': len(zoho_invoices),
                'amzn': len(amzn_invoices),
                'auto': len(auto_invoices),
                'other': len(other_invoices)
            }
            
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        # Wait between settlements
        if settlement_id != settlements[-1]:
            print(f"  [PAUSE] Waiting 10 seconds...")
            time.sleep(10)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    total_all = sum(f['total'] for f in all_formats.values())
    total_amzn = sum(f['amzn'] for f in all_formats.values())
    total_auto = sum(f['auto'] for f in all_formats.values())
    total_other = sum(f['other'] for f in all_formats.values())
    
    print(f"\nTotal invoices checked: {total_all}")
    print(f"[AMZN FORMAT] {total_amzn} ({total_amzn/total_all*100 if total_all > 0 else 0:.1f}%)")
    print(f"[AUTO-GENERATED] {total_auto} ({total_auto/total_all*100 if total_all > 0 else 0:.1f}%)")
    print(f"[OTHER FORMAT] {total_other} ({total_other/total_all*100 if total_all > 0 else 0:.1f}%)")
    
    if total_auto > 0:
        print(f"\n[WARNING] {total_auto} invoice(s) have auto-generated numbers (INV-xxx)")
        print("These were likely created before we added ignore_auto_number_generation=true")
        print("They need to be deleted and re-posted with correct AMZN format")
    
    if total_amzn == total_all and total_all > 0:
        print(f"\n[SUCCESS] All invoices have correct AMZN format!")
    elif total_amzn > 0:
        print(f"\n[PARTIAL] {total_amzn}/{total_all} invoices have correct format")
        print(f"Recommendation: Delete and re-post {total_auto + total_other} invoices with wrong format")


if __name__ == '__main__':
    check_zoho_invoice_formats()

