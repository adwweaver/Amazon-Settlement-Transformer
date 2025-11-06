#!/usr/bin/env python3
"""
Check if invoice numbers in Zoho match our expected format (AMZN + last 7 digits of order_id).
"""

import time
from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from post_all_settlements import find_local_settlements


def get_expected_invoice_number(order_id: str) -> str:
    """Get expected invoice number from order_id."""
    if pd.isna(order_id) or not order_id:
        return None
    
    order_id_str = str(order_id).strip()
    if len(order_id_str) >= 7:
        last_7 = order_id_str[-7:]
        return f"AMZN{last_7}"
    else:
        return None


def check_invoice_numbers():
    """Check invoice numbers for all settlements."""
    print("="*80)
    print("CHECKING INVOICE NUMBERS IN ZOHO")
    print("="*80)
    
    settlements = find_local_settlements()
    zoho = ZohoBooks()
    
    all_results = []
    total_checked = 0
    total_correct = 0
    total_incorrect = 0
    total_not_found = 0
    
    for settlement_id in settlements:
        print(f"\n{'='*80}")
        print(f"Settlement: {settlement_id}")
        print(f"{'='*80}")
        
        # Load local invoice file
        invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
        if not invoice_file.exists():
            print(f"  [SKIP] No local invoice file")
            continue
        
        df_local = pd.read_csv(invoice_file)
        
        # Get unique invoices with their order_ids
        invoice_groups = df_local.groupby('Invoice Number')
        
        print(f"  Found {len(invoice_groups)} unique invoice(s) in local file")
        
        # Query Zoho for invoices
        print(f"  Querying Zoho (waiting 5s for rate limits)...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [ERROR] Could not query Zoho: {api_result}")
                continue
            
            zoho_invoices = api_result.get('invoices', [])
            print(f"  Found {len(zoho_invoices)} invoice(s) in Zoho")
            
            # Build map of Zoho invoice numbers to invoice data
            zoho_invoice_map = {}
            for zoho_inv in zoho_invoices:
                inv_num = str(zoho_inv.get('invoice_number', '')).strip()
                zoho_invoice_map[inv_num] = zoho_inv
            
            # Check each local invoice
            for local_inv_num, group in invoice_groups:
                # Get order_id from first row (all rows in a group have same invoice number)
                first_row = group.iloc[0]
                order_id = first_row.get('merchant_order_id', '') or first_row.get('Order ID', '')
                
                expected_inv_num = get_expected_invoice_number(order_id)
                
                if not expected_inv_num:
                    print(f"    [WARN] Invoice {local_inv_num}: Cannot determine expected number (order_id: {order_id})")
                    total_not_found += 1
                    all_results.append({
                        'settlement_id': settlement_id,
                        'local_invoice_number': local_inv_num,
                        'order_id': str(order_id),
                        'expected_invoice_number': None,
                        'zoho_invoice_number': None,
                        'status': 'CANNOT_DETERMINE',
                        'match': False
                    })
                    continue
                
                # Check if this invoice exists in Zoho
                if local_inv_num in zoho_invoice_map:
                    zoho_inv = zoho_invoice_map[local_inv_num]
                    zoho_inv_num = str(zoho_inv.get('invoice_number', '')).strip()
                    zoho_inv_id = str(zoho_inv.get('invoice_id', '')).strip()
                    
                    is_correct = (local_inv_num == expected_inv_num)
                    matches_zoho = (local_inv_num == zoho_inv_num)
                    
                    if is_correct and matches_zoho:
                        status = 'CORRECT'
                        total_correct += 1
                        match = True
                        print(f"    ✅ {local_inv_num}: Correct (Zoho: {zoho_inv_num})")
                    elif matches_zoho:
                        status = 'WRONG_FORMAT'
                        total_incorrect += 1
                        match = False
                        print(f"    ❌ {local_inv_num}: Wrong format (Expected: {expected_inv_num}, Zoho: {zoho_inv_num})")
                    else:
                        status = 'MISMATCH'
                        total_incorrect += 1
                        match = False
                        print(f"    ⚠️  {local_inv_num}: Mismatch (Expected: {expected_inv_num}, Zoho: {zoho_inv_num})")
                    
                    all_results.append({
                        'settlement_id': settlement_id,
                        'local_invoice_number': local_inv_num,
                        'order_id': str(order_id),
                        'expected_invoice_number': expected_inv_num,
                        'zoho_invoice_number': zoho_inv_num,
                        'zoho_invoice_id': zoho_inv_id,
                        'status': status,
                        'match': match
                    })
                    total_checked += 1
                else:
                    # Check if expected format exists in Zoho
                    if expected_inv_num in zoho_invoice_map:
                        zoho_inv = zoho_invoice_map[expected_inv_num]
                        zoho_inv_num = str(zoho_inv.get('invoice_number', '')).strip()
                        zoho_inv_id = str(zoho_inv.get('invoice_id', '')).strip()
                        
                        status = 'EXISTS_WITH_CORRECT_NUMBER'
                        match = False
                        print(f"    [FOUND] {local_inv_num}: Not found, but {expected_inv_num} exists in Zoho (ID: {zoho_inv_id})")
                        all_results.append({
                            'settlement_id': settlement_id,
                            'local_invoice_number': local_inv_num,
                            'order_id': str(order_id),
                            'expected_invoice_number': expected_inv_num,
                            'zoho_invoice_number': zoho_inv_num,
                            'zoho_invoice_id': zoho_inv_id,
                            'status': status,
                            'match': False
                        })
                        total_checked += 1
                    else:
                        status = 'NOT_IN_ZOHO'
                        total_not_found += 1
                        print(f"    [MISSING] {local_inv_num}: Not in Zoho (Expected: {expected_inv_num})")
                        all_results.append({
                            'settlement_id': settlement_id,
                            'local_invoice_number': local_inv_num,
                            'order_id': str(order_id),
                            'expected_invoice_number': expected_inv_num,
                            'zoho_invoice_number': None,
                            'zoho_invoice_id': None,
                            'status': status,
                            'match': False
                        })
            
            # Check for extra invoices in Zoho
            local_inv_nums = set(invoice_groups.groups.keys())
            zoho_inv_nums = set(zoho_invoice_map.keys())
            extra_in_zoho = zoho_inv_nums - local_inv_nums
            
            if extra_in_zoho:
                print(f"  [WARN] {len(extra_in_zoho)} invoice(s) in Zoho but not in local file:")
                for extra_inv in list(extra_in_zoho)[:10]:  # Show first 10
                    print(f"    - {extra_inv}")
                if len(extra_in_zoho) > 10:
                    print(f"    ... and {len(extra_in_zoho) - 10} more")
            
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
    print(f"Total checked: {total_checked}")
    print(f"[OK] Correct format: {total_correct}")
    print(f"[WRONG] Wrong format: {total_incorrect}")
    print(f"[MISSING] Not in Zoho: {total_not_found}")
    
    if total_checked > 0:
        correct_pct = (total_correct / total_checked) * 100
        print(f"\nCorrect percentage: {correct_pct:.1f}%")
    
    # Save results to CSV
    if all_results:
        output_file = Path("outputs") / "invoice_number_check.csv"
        df_results = pd.DataFrame(all_results)
        df_results.to_csv(output_file, index=False)
        print(f"\nResults saved to: {output_file}")
    
    return all_results


if __name__ == '__main__':
    check_invoice_numbers()

