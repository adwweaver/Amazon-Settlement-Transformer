#!/usr/bin/env python3
"""
Post payments one settlement at a time with very long delays to avoid rate limits.
Queries Zoho for invoice IDs and updates tracking file.
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


def query_invoices_for_settlement(zoho: ZohoBooks, settlement_id: str) -> dict:
    """Query Zoho for invoices for one settlement with rate limit protection."""
    invoice_map = {}
    
    print(f"\n  Querying Zoho for invoices (settlement: {settlement_id})...")
    print(f"  Waiting 30 seconds before query...")
    time.sleep(30)  # Long wait before query
    
    try:
        # Query by reference_number
        api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        
        if api_result.get('code') == 0:
            invoices = api_result.get('invoices', [])
            print(f"  Found {len(invoices)} invoice(s) in Zoho")
            
            for inv in invoices:
                inv_num = str(inv.get('invoice_number', '')).strip()
                inv_id = str(inv.get('invoice_id', '')).strip()
                
                if inv_num and inv_id:
                    invoice_map[inv_num] = inv_id
                    print(f"    {inv_num} -> {inv_id}")
        
        return invoice_map
        
    except Exception as e:
        error_msg = str(e)
        if 'rate limit' in error_msg.lower() or 'too many requests' in error_msg.lower():
            print(f"  [RATE LIMIT] Still hitting rate limits. Error: {error_msg[:100]}")
            return {}
        else:
            print(f"  [ERROR] {error_msg}")
            return {}


def update_tracking_file(settlement_id: str, invoice_map: dict):
    """Update tracking file with invoice IDs."""
    tracking_file = get_zoho_tracking_path()
    
    if not tracking_file.exists():
        print(f"  [WARN] Tracking file not found")
        return
    
    try:
        df = pd.read_csv(tracking_file)
        df['settlement_id'] = df['settlement_id'].astype(str)
        
        updated = 0
        for inv_num, inv_id in invoice_map.items():
            mask = (
                (df['settlement_id'] == str(settlement_id)) &
                (df['record_type'] == 'INVOICE') &
                (df['local_identifier'] == inv_num)
            )
            if mask.any():
                df.loc[mask, 'zoho_id'] = inv_id
                df.loc[mask, 'status'] = 'POSTED'
                updated += 1
        
        df.to_csv(tracking_file, index=False)
        print(f"  Updated {updated} invoice record(s) in tracking file")
        
    except Exception as e:
        print(f"  [ERROR] Could not update tracking file: {e}")


def main():
    print("="*80)
    print("POSTING PAYMENTS (ONE SETTLEMENT AT A TIME WITH LONG DELAYS)")
    print("="*80)
    
    settlements = find_local_settlements()
    
    # Get settlements that need payments
    settlements_needing_payments = []
    for settlement_id in settlements:
        payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
        if payment_file.exists():
            try:
                df_pay = pd.read_csv(payment_file)
                if len(df_pay) > 0:
                    settlements_needing_payments.append(settlement_id)
            except:
                pass
    
    print(f"\nFound {len(settlements_needing_payments)} settlement(s) needing payments")
    
    if not settlements_needing_payments:
        print("No payments to post!")
        return
    
    zoho = ZohoBooks()
    
    # Process each settlement with very long delays
    for i, settlement_id in enumerate(settlements_needing_payments, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements_needing_payments)}: {settlement_id}")
        print(f"{'='*80}")
        
        # Step 1: Query invoices and update tracking
        print("\n[STEP 1] Querying invoices from Zoho...")
        invoice_map = query_invoices_for_settlement(zoho, settlement_id)
        
        if invoice_map:
            print(f"[STEP 2] Updating tracking file...")
            update_tracking_file(settlement_id, invoice_map)
            
            print(f"[STEP 3] Posting payments...")
            print(f"  Waiting 30 seconds before posting payments...")
            time.sleep(30)
            
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
        else:
            print(f"  [SKIP] No invoices found - cannot post payments")
        
        # Long wait between settlements
        if i < len(settlements_needing_payments):
            print(f"\n[PAUSE] Waiting 60 seconds before next settlement...")
            time.sleep(60)
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()



