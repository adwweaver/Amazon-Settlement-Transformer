#!/usr/bin/env python3
"""
Fix payment posting by ensuring invoice IDs are correct.

Issue: Payments failing because invoice IDs in tracking file don't match Zoho.
Solution: Query Zoho fresh for invoices after posting, update tracking, then post payments.
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


def refresh_invoice_tracking(zoho: ZohoBooks, settlement_id: str):
    """Query Zoho for invoices and update tracking file with correct IDs."""
    print(f"\nRefreshing invoice tracking for settlement {settlement_id}...")
    
    tracking_file = get_zoho_tracking_path()
    if not tracking_file.exists():
        print(f"  [ERROR] Tracking file not found")
        return {}
    
    # Query Zoho for invoices
    print(f"  Querying Zoho (waiting 5s for rate limits)...")
    time.sleep(5)
    
    try:
        api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        
        if api_result.get('code') != 0:
            print(f"  [ERROR] Could not query: {api_result.get('message', 'Unknown error')}")
            return {}
        
        zoho_invoices = api_result.get('invoices', [])
        print(f"  Found {len(zoho_invoices)} invoice(s) in Zoho")
        
        if len(zoho_invoices) == 0:
            print(f"  [WARN] No invoices found in Zoho")
            return {}
        
        # Build invoice map: invoice_number -> invoice_id
        invoice_map = {}
        for inv in zoho_invoices:
            inv_num = str(inv.get('invoice_number', '')).strip()
            inv_id = str(inv.get('invoice_id', '')).strip()
            if inv_num and inv_id:
                invoice_map[inv_num] = inv_id
                print(f"    Mapped {inv_num} -> {inv_id}")
        
        # Update tracking file
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
                old_id = df.loc[mask, 'zoho_id'].iloc[0] if mask.any() else None
                df.loc[mask, 'zoho_id'] = inv_id
                df.loc[mask, 'status'] = 'POSTED'
                updated += 1
                if pd.notna(old_id) and str(old_id) != str(inv_id):
                    print(f"    Updated {inv_num}: {old_id} -> {inv_id}")
        
        if updated > 0:
            df.to_csv(tracking_file, index=False)
            print(f"  [OK] Updated {updated} invoice record(s) in tracking file")
        
        return invoice_map
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    print("="*80)
    print("FIX PAYMENT POSTING - REFRESH INVOICE IDs")
    print("="*80)
    
    zoho = ZohoBooks()
    settlements = find_local_settlements()
    
    # Step 1: Refresh invoice tracking for all settlements
    print("\nSTEP 1: Refreshing invoice tracking from Zoho...")
    all_invoice_maps = {}
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"\n{i}/{len(settlements)}: Settlement {settlement_id}")
        invoice_map = refresh_invoice_tracking(zoho, settlement_id)
        all_invoice_maps[settlement_id] = invoice_map
        
        if i < len(settlements):
            print(f"  [PAUSE] Waiting 10 seconds...")
            time.sleep(10)
    
    # Step 2: Post payments now that invoice IDs are correct
    print("\n" + "="*80)
    print("STEP 2: POSTING PAYMENTS")
    print("="*80)
    
    for i, settlement_id in enumerate(settlements, 1):
        payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
        if not payment_file.exists():
            print(f"\n{i}/{len(settlements)}: Settlement {settlement_id} - [SKIP] No payment file")
            continue
        
        print(f"\n{i}/{len(settlements)}: Settlement {settlement_id}")
        print(f"  Posting payments...")
        print(f"  Waiting 10 seconds for rate limits...")
        time.sleep(10)
        
        try:
            result = post_settlement_complete(
                settlement_id,
                post_journal=False,
                post_invoices=False,
                post_payments=True,
                dry_run=False,
                override=True
            )
            
            if result['payments']['posted']:
                count = result['payments']['count']
                print(f"  [SUCCESS] Posted {count} payment(s)")
            else:
                error = result['payments'].get('error', 'Unknown error')
                print(f"  [FAILED] {error}")
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(settlements):
            print(f"  [PAUSE] Waiting 15 seconds...")
            time.sleep(15)
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()



