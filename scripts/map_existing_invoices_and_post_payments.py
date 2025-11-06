#!/usr/bin/env python3
"""
Map existing invoices in Zoho (by reference_number) to local invoice numbers,
then post payments using the correct Zoho invoice IDs.
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


def map_invoices_from_zoho(zoho: ZohoBooks, settlement_id: str, local_invoice_file: Path) -> dict:
    """
    Query Zoho for invoices and match them to local invoice numbers.
    Since Zoho auto-generated invoice numbers, we'll match by:
    1. Reference number (settlement_id)
    2. Amount and date (if needed)
    """
    invoice_map = {}
    
    print(f"\n  Mapping invoices for settlement {settlement_id}...")
    print(f"  Waiting 10 seconds before query...")
    time.sleep(10)
    
    try:
        # Query by reference_number
        api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        
        if api_result.get('code') != 0:
            print(f"  [ERROR] Could not query invoices: {api_result}")
            return invoice_map
        
        zoho_invoices = api_result.get('invoices', [])
        print(f"  Found {len(zoho_invoices)} invoice(s) in Zoho")
        
        # Load local invoices to match
        if local_invoice_file.exists():
            try:
                df_local = pd.read_csv(local_invoice_file)
                
                # Group local invoices by invoice number
                local_invoice_groups = {}
                for inv_num in df_local['Invoice Number'].unique():
                    group = df_local[df_local['Invoice Number'] == inv_num]
                    local_invoice_groups[inv_num] = {
                        'total': group['Invoice Line Amount'].sum(),
                        'date': str(group.iloc[0]['Invoice Date']),
                        'line_count': len(group)
                    }
                
                # Match Zoho invoices to local invoices by amount and date
                for zoho_inv in zoho_invoices:
                    zoho_id = str(zoho_inv.get('invoice_id', '')).strip()
                    zoho_total = float(zoho_inv.get('total', 0))
                    zoho_date = str(zoho_inv.get('date', ''))
                    
                    # Try to match by amount and date
                    best_match = None
                    best_match_score = 0
                    
                    for local_inv_num, local_data in local_invoice_groups.items():
                        local_total = float(local_data['total'])
                        local_date = str(local_data['date'])
                        
                        # Calculate match score
                        score = 0
                        if abs(zoho_total - local_total) < 0.01:  # Amount matches
                            score += 10
                        if zoho_date == local_date:  # Date matches
                            score += 5
                        
                        if score > best_match_score:
                            best_match_score = score
                            best_match = local_inv_num
                    
                    # If we found a good match, add to map
                    if best_match and best_match_score >= 10:  # At least amount must match
                        invoice_map[best_match] = zoho_id
                        print(f"    Mapped {best_match} -> {zoho_id} (Total: ${zoho_total}, Score: {best_match_score})")
                    
            except Exception as e:
                print(f"  [ERROR] Error matching invoices: {e}")
        else:
            print(f"  [WARN] Local invoice file not found, using all Zoho invoices")
            # If we can't match, just use reference_number for all
            # This won't work for payments, but at least we'll know what exists
        
        print(f"  Mapped {len(invoice_map)} invoice(s)")
        return invoice_map
        
    except Exception as e:
        print(f"  [ERROR] Error querying invoices: {e}")
        return invoice_map


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
    print("MAPPING EXISTING INVOICES AND POSTING PAYMENTS")
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
    
    # Process each settlement
    for i, settlement_id in enumerate(settlements_needing_payments, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements_needing_payments)}: {settlement_id}")
        print(f"{'='*80}")
        
        invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
        
        # Step 1: Map invoices from Zoho
        invoice_map = map_invoices_from_zoho(zoho, settlement_id, invoice_file)
        
        if not invoice_map:
            print(f"  [WARN] No invoices mapped - cannot post payments")
            continue
        
        # Step 2: Update tracking file
        print(f"  Updating tracking file...")
        update_tracking_file(settlement_id, invoice_map)
        
        # Step 3: Post payments
        print(f"  Posting payments...")
        print(f"  Waiting 20 seconds before posting...")
        time.sleep(20)
        
        try:
            results = post_settlement_complete(
                settlement_id,
                post_journal=False,
                post_invoices=False,  # Don't try to post invoices - they already exist
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
        if i < len(settlements_needing_payments):
            print(f"\n  [PAUSE] Waiting 30 seconds before next settlement...")
            time.sleep(30)
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()



