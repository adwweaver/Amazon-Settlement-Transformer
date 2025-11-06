#!/usr/bin/env python3
"""
Post missing payments for settlements where invoices were already posted.
This script attempts to get customer_id from existing invoices to avoid rate limits.
"""

import time
from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from sync_settlement import post_settlement_complete

def main():
    # Get all settlements with invoices posted
    from post_all_settlements import find_local_settlements
    
    all_settlements = find_local_settlements()
    
    print("="*80)
    print("POSTING MISSING PAYMENTS")
    print("="*80)
    print(f"Checking {len(all_settlements)} settlements...")
    
    zoho = ZohoBooks()
    
    settlements_needing_payments = []
    
    # First, identify which settlements need payments using local files only (no API calls)
    print("\nIdentifying settlements needing payments (using local files only)...")
    from paths import get_zoho_tracking_path
    
    tracking_file = get_zoho_tracking_path()
    has_tracking = False
    tracking_invoices = set()
    
    if tracking_file.exists():
        try:
            df_tracking = pd.read_csv(tracking_file)
            # Get all settlement IDs that have invoices posted (convert to string for comparison)
            settlement_invoices = df_tracking[
                (df_tracking['record_type'] == 'INVOICE') &
                (df_tracking['zoho_id'].notna()) &
                (df_tracking['zoho_id'] != '')
            ]
            tracking_invoices = set(str(sid) for sid in settlement_invoices['settlement_id'].unique())
            has_tracking = True
            print(f"  [INFO] Tracking file shows {len(tracking_invoices)} settlements with invoices")
        except Exception as e:
            print(f"  [WARN] Could not read tracking file: {e}")
    
    for settlement_id in all_settlements:
        payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
        if payment_file.exists():
            try:
                payment_df = pd.read_csv(payment_file)
                if len(payment_df) > 0:
                    # If we have tracking, only post payments for settlements that have invoices
                    # Otherwise, assume invoices exist (since we just posted them)
                    if has_tracking:
                        if settlement_id in tracking_invoices:
                            settlements_needing_payments.append(settlement_id)
                            print(f"  [FOUND] Settlement {settlement_id}: {len(payment_df)} payment(s) needed")
                    else:
                        # No tracking file - assume invoices exist if we have payment file
                        settlements_needing_payments.append(settlement_id)
                        print(f"  [FOUND] Settlement {settlement_id}: {len(payment_df)} payment(s) needed")
            except Exception as e:
                print(f"  [WARN] Could not read payment file for {settlement_id}: {e}")
    
    print(f"\n{len(settlements_needing_payments)} settlement(s) need payments posted")
    print("Waiting 60 seconds for rate limits to reset before posting...")
    time.sleep(60)
    
    for settlement_id in settlements_needing_payments:
        print(f"\n{'='*80}")
        print(f"Settlement: {settlement_id}")
        print(f"{'='*80}")
        
        # Post payments directly (invoice map will be built from tracking file)
        print(f"  [PAYMENTS] Posting payments (using tracking file for invoice map)...")
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
                print(f"  [SUCCESS] {results['payments']['count']} payment(s) posted")
            else:
                print(f"  [FAILED] {results['payments'].get('error', 'Unknown error')}")
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Wait between settlements (longer wait to avoid rate limits)
        if settlements_needing_payments.index(settlement_id) < len(settlements_needing_payments) - 1:
            print(f"  [PAUSE] Waiting 20 seconds before next settlement...")
            time.sleep(20)
    
    print(f"\n{'='*80}")
    print("COMPLETE")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()

