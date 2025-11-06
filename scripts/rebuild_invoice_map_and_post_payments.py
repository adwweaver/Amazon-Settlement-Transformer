#!/usr/bin/env python3
"""
Rebuild invoice map from Zoho and post all missing payments.
This queries Zoho for actual invoices to build a correct invoice map.
"""

import time
from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from sync_settlement import post_settlement_complete
from post_all_settlements import find_local_settlements
from paths import get_zoho_tracking_path


def rebuild_invoice_map_from_zoho(zoho: ZohoBooks, settlement_id: str) -> dict:
    """Query Zoho for all invoices for a settlement and build invoice map."""
    invoice_map = {}
    
    print(f"  [INFO] Querying Zoho for invoices (settlement: {settlement_id})...")
    
    page = 1
    per_page = 200
    all_invoices = []
    
    while True:
        try:
            # Query by reference_number (settlement_id)
            api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page={per_page}&page={page}')
            
            if api_result.get('code') != 0:
                break
            
            invoices = api_result.get('invoices', [])
            if not invoices:
                break
            
            all_invoices.extend(invoices)
            
            # Check for more pages
            page_context = api_result.get('page_context', {})
            if not page_context.get('has_more_page', False):
                break
            
            page += 1
            time.sleep(2)  # Rate limit protection
            
        except Exception as e:
            print(f"  [ERROR] Error querying invoices: {e}")
            break
    
    print(f"  [INFO] Found {len(all_invoices)} invoice(s) in Zoho")
    
    # Build invoice map: invoice_number -> invoice_id
    for inv in all_invoices:
        inv_num = str(inv.get('invoice_number', '')).strip()
        inv_id = str(inv.get('invoice_id', '')).strip()
        
        if inv_num and inv_id:
            invoice_map[inv_num] = inv_id
            print(f"  [INFO] Mapped {inv_num} -> {inv_id}")
    
    return invoice_map


def main():
    print("="*80)
    print("REBUILDING INVOICE MAP AND POSTING ALL PAYMENTS")
    print("="*80)
    
    settlements = find_local_settlements()
    print(f"\nFound {len(settlements)} settlement(s)")
    
    zoho = ZohoBooks()
    
    # Get settlements that need payments
    settlements_needing_payments = []
    
    for settlement_id in settlements:
        payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
        if payment_file.exists():
            try:
                df_pay = pd.read_csv(payment_file)
                if len(df_pay) > 0:
                    settlements_needing_payments.append(settlement_id)
                    print(f"  [FOUND] Settlement {settlement_id}: {len(df_pay)} payment(s) needed")
            except:
                pass
    
    print(f"\n{len(settlements_needing_payments)} settlement(s) need payments posted")
    
    if not settlements_needing_payments:
        print("\nNo payments to post!")
        return
    
    print("\nWaiting 30 seconds before starting...")
    time.sleep(30)
    
    # Process each settlement
    for settlement_id in settlements_needing_payments:
        print(f"\n{'='*80}")
        print(f"Settlement: {settlement_id}")
        print(f"{'='*80}")
        
        # Rebuild invoice map from Zoho
        invoice_map = rebuild_invoice_map_from_zoho(zoho, settlement_id)
        
        if not invoice_map:
            print(f"  [WARN] No invoices found in Zoho for settlement {settlement_id}")
            print("  [INFO] Skipping payments - invoices must exist first")
            continue
        
        print(f"  [INFO] Invoice map built: {len(invoice_map)} invoice(s)")
        
        # Update tracking file with invoice map
        tracking_file = get_zoho_tracking_path()
        if tracking_file.exists():
            try:
                df_tracking = pd.read_csv(tracking_file)
                df_tracking['settlement_id'] = df_tracking['settlement_id'].astype(str)
                
                # Update invoice records with zoho_id from map
                for inv_num, inv_id in invoice_map.items():
                    mask = (
                        (df_tracking['settlement_id'] == str(settlement_id)) &
                        (df_tracking['record_type'] == 'INVOICE') &
                        (df_tracking['local_identifier'] == inv_num)
                    )
                    if mask.any():
                        df_tracking.loc[mask, 'zoho_id'] = inv_id
                        df_tracking.loc[mask, 'status'] = 'POSTED'
                
                df_tracking.to_csv(tracking_file, index=False)
                print(f"  [INFO] Updated tracking file with invoice IDs")
            except Exception as e:
                print(f"  [WARN] Could not update tracking file: {e}")
        
        # Now post payments (they should be able to find invoices now)
        print(f"\n  [PAYMENTS] Posting payments...")
        try:
            results = post_settlement_complete(
                settlement_id,
                post_journal=False,
                post_invoices=False,
                post_payments=True,
                dry_run=False,
                override=True
            )
            
            if results['payments']['posted']:
                print(f"  [SUCCESS] Posted {results['payments']['count']} payment(s)")
            else:
                print(f"  [FAILED] {results['payments'].get('error', 'Unknown error')}")
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Wait between settlements
        if settlements_needing_payments.index(settlement_id) < len(settlements_needing_payments) - 1:
            print(f"  [PAUSE] Waiting 20 seconds before next settlement...")
            time.sleep(20)
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()



