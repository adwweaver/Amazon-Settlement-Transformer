#!/usr/bin/env python3
"""
Query Zoho for actual invoice IDs and map them to local invoice numbers.
Then update tracking file and post payments.
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


def query_and_map_invoices(zoho: ZohoBooks, settlement_id: str) -> dict:
    """Query Zoho and match invoices to local invoice numbers by amount/date."""
    invoice_map = {}
    
    print(f"  Querying Zoho for invoices (settlement: {settlement_id})...")
    time.sleep(10)
    
    try:
        api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        
        if api_result.get('code') != 0:
            print(f"  [ERROR] Could not query: {api_result}")
            return invoice_map
        
        zoho_invoices = api_result.get('invoices', [])
        print(f"  Found {len(zoho_invoices)} invoice(s) in Zoho")
        
        # Load local invoices
        invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
        if not invoice_file.exists():
            print(f"  [WARN] Local invoice file not found")
            return invoice_map
        
        df_local = pd.read_csv(invoice_file)
        
        # Group local invoices by invoice number
        local_invoice_groups = {}
        for inv_num in df_local['Invoice Number'].unique():
            group = df_local[df_local['Invoice Number'] == inv_num]
            local_invoice_groups[inv_num] = {
                'total': float(group['Invoice Line Amount'].sum()),
                'date': str(group.iloc[0]['Invoice Date']),
                'line_count': len(group)
            }
        
        # Match Zoho invoices to local by amount and date
        unmatched_zoho = []
        matched_count = 0
        
        for zoho_inv in zoho_invoices:
            zoho_id = str(zoho_inv.get('invoice_id', '')).strip()
            zoho_total = float(zoho_inv.get('total', 0))
            zoho_date = str(zoho_inv.get('date', ''))
            zoho_inv_num = str(zoho_inv.get('invoice_number', '')).strip()
            
            # Find best match
            best_match = None
            best_score = 0
            
            for local_inv_num, local_data in local_invoice_groups.items():
                local_total = local_data['total']
                local_date = local_data['date']
                
                score = 0
                if abs(zoho_total - local_total) < 0.01:
                    score += 10
                if zoho_date == local_date:
                    score += 5
                
                if score > best_score:
                    best_score = score
                    best_match = local_inv_num
            
            if best_match and best_score >= 10:
                invoice_map[best_match] = zoho_id
                matched_count += 1
                print(f"    Matched {best_match} -> {zoho_id} (${zoho_total}, {zoho_date})")
            else:
                unmatched_zoho.append({
                    'zoho_id': zoho_id,
                    'zoho_number': zoho_inv_num,
                    'total': zoho_total,
                    'date': zoho_date
                })
        
        if unmatched_zoho:
            print(f"  [WARN] {len(unmatched_zoho)} invoice(s) in Zoho couldn't be matched")
        
        print(f"  Mapped {matched_count} invoice(s)")
        return invoice_map
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        return invoice_map


def update_tracking_with_correct_ids(settlement_id: str, invoice_map: dict):
    """Update tracking file with correct invoice IDs."""
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
                old_id = df.loc[mask, 'zoho_id'].iloc[0] if mask.any() else None
                df.loc[mask, 'zoho_id'] = inv_id
                df.loc[mask, 'status'] = 'POSTED'
                updated += 1
                if pd.notna(old_id) and str(old_id) != str(inv_id):
                    print(f"    Updated {inv_num}: {old_id} -> {inv_id}")
        
        df.to_csv(tracking_file, index=False)
        print(f"  Updated {updated} invoice record(s) in tracking file")
        
    except Exception as e:
        print(f"  [ERROR] Could not update tracking: {e}")


def main():
    print("="*80)
    print("GET CORRECT INVOICE IDs AND POST PAYMENTS")
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
        
        # Step 1: Query and map invoices
        invoice_map = query_and_map_invoices(zoho, settlement_id)
        
        if not invoice_map:
            print(f"  [SKIP] No invoices mapped - cannot post payments")
            continue
        
        # Step 2: Update tracking file
        update_tracking_with_correct_ids(settlement_id, invoice_map)
        
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
        
        # Wait between settlements
        if i < len(settlements_needing_payments):
            print(f"\n  [PAUSE] Waiting 30 seconds before next settlement...")
            time.sleep(30)
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()



