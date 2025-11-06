#!/usr/bin/env python3
"""
Verify invoice IDs in tracking file match Zoho, fix any that don't, then post payments.
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


def verify_and_fix_invoice_ids(zoho: ZohoBooks, settlement_id: str) -> dict:
    """Verify invoice IDs in tracking file and fix if needed."""
    tracking_file = get_zoho_tracking_path()
    
    if not tracking_file.exists():
        print(f"  [ERROR] Tracking file not found")
        return {}
    
    df = pd.read_csv(tracking_file)
    df['settlement_id'] = df['settlement_id'].astype(str)
    
    # Get invoices for this settlement
    settlement_invoices = df[
        (df['settlement_id'] == str(settlement_id)) &
        (df['record_type'] == 'INVOICE')
    ].copy()
    
    if len(settlement_invoices) == 0:
        print(f"  [WARN] No invoices in tracking file for settlement {settlement_id}")
        return {}
    
    print(f"  Found {len(settlement_invoices)} invoice(s) in tracking file")
    
    invoice_map = {}
    updated_count = 0
    
    # Query Zoho for all invoices with this reference_number
    print(f"  Querying Zoho for invoices (reference_number={settlement_id})...")
    time.sleep(10)
    
    try:
        api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        
        if api_result.get('code') != 0:
            print(f"  [ERROR] Could not query Zoho: {api_result}")
            return {}
        
        zoho_invoices = api_result.get('invoices', [])
        print(f"  Found {len(zoho_invoices)} invoice(s) in Zoho")
        
        # Build map: invoice_number -> invoice_id from Zoho
        zoho_map = {}
        for zoho_inv in zoho_invoices:
            inv_num = str(zoho_inv.get('invoice_number', '')).strip()
            inv_id = str(zoho_inv.get('invoice_id', '')).strip()
            if inv_num and inv_id:
                zoho_map[inv_num] = inv_id
        
        # Now check each local invoice
        for idx, row in settlement_invoices.iterrows():
            local_inv_num = str(row['local_identifier']).strip()
            tracked_inv_id = row['zoho_id']
            
            # Convert tracked ID to string (handle NaN, float, etc.)
            if pd.isna(tracked_inv_id):
                tracked_inv_id = None
            elif isinstance(tracked_inv_id, float):
                tracked_inv_id = f"{tracked_inv_id:.0f}"
            else:
                tracked_inv_id = str(tracked_inv_id).strip()
            
            # Check if Zoho has this invoice_number
            if local_inv_num in zoho_map:
                correct_inv_id = zoho_map[local_inv_num]
                invoice_map[local_inv_num] = correct_inv_id
                
                # Update tracking file if ID is different
                if tracked_inv_id != correct_inv_id:
                    df.loc[idx, 'zoho_id'] = correct_inv_id
                    df.loc[idx, 'status'] = 'POSTED'
                    updated_count += 1
                    print(f"    Fixed {local_inv_num}: {tracked_inv_id} -> {correct_inv_id}")
                else:
                    print(f"    OK {local_inv_num}: {correct_inv_id}")
            else:
                print(f"    [WARN] Invoice {local_inv_num} not found in Zoho")
        
        # Save updated tracking file
        if updated_count > 0:
            df.to_csv(tracking_file, index=False)
            print(f"  Updated {updated_count} invoice ID(s) in tracking file")
        
        return invoice_map
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    print("="*80)
    print("VERIFY AND FIX INVOICE IDs, THEN POST PAYMENTS")
    print("="*80)
    
    settlements = find_local_settlements()
    
    # Get settlements needing payments
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
    
    # Process each settlement
    for i, settlement_id in enumerate(settlements_needing_payments, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements_needing_payments)}: {settlement_id}")
        print(f"{'='*80}")
        
        # Step 1: Verify and fix invoice IDs
        invoice_map = verify_and_fix_invoice_ids(zoho, settlement_id)
        
        # Check if we need to post invoices first
        invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
        needs_invoices = False
        local_invoice_count = 0
        
        if invoice_file.exists():
            try:
                df_local = pd.read_csv(invoice_file)
                local_invoice_count = len(df_local['Invoice Number'].unique())
                
                # Check how many invoices we have mapped
                local_invoice_nums = set(df_local['Invoice Number'].unique())
                mapped_count = len(set(invoice_map.keys()) & local_invoice_nums)
                
                if mapped_count < local_invoice_count:
                    needs_invoices = True
                    print(f"  [INFO] {mapped_count}/{local_invoice_count} invoices mapped - need to post missing invoices")
            except:
                pass
        
        # Step 2: Post missing invoices if needed
        if needs_invoices:
            print(f"\n  [INVOICES] Posting missing invoices...")
            print(f"  Waiting 20 seconds before posting...")
            time.sleep(20)
            
            try:
                inv_results = post_settlement_complete(
                    settlement_id,
                    post_journal=False,
                    post_invoices=True,
                    post_payments=False,
                    dry_run=False,
                    override=True
                )
                
                if inv_results['invoices']['posted']:
                    print(f"  [SUCCESS] Posted {inv_results['invoices']['count']} invoice(s)")
                    # Re-verify invoice IDs after posting
                    print(f"  Re-verifying invoice IDs...")
                    time.sleep(10)
                    invoice_map = verify_and_fix_invoice_ids(zoho, settlement_id)
                else:
                    error = inv_results['invoices'].get('error', 'Unknown error')
                    print(f"  [FAILED] {error}")
                    # Still try to post payments with what we have
            except Exception as e:
                print(f"  [ERROR] {e}")
        
        if not invoice_map:
            print(f"  [SKIP] No invoices mapped - cannot post payments")
            continue
        
        print(f"  Mapped {len(invoice_map)} invoice(s) for payment posting")
        
        # Step 3: Post payments
        print(f"\n  [PAYMENTS] Posting payments...")
        print(f"  Waiting 20 seconds before posting...")
        time.sleep(20)
        
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
                error = results['payments'].get('error', 'Unknown error')
                print(f"  [FAILED] {error}")
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        # Wait between settlements
        if i < len(settlements_needing_payments):
            print(f"\n  [PAUSE] Waiting 30 seconds before next settlement...")
            time.sleep(30)
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()

