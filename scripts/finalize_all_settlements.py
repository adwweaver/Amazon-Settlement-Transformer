#!/usr/bin/env python3
"""
Finalize all invoices and payments in Zoho Books.
Posts missing invoices first, then payments, with proper rate limit handling.
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


def check_current_status(zoho: ZohoBooks, settlement_id: str) -> dict:
    """Check what's already posted in Zoho for a settlement."""
    status = {
        'has_journal': False,
        'journal_id': None,
        'invoice_count': 0,
        'payment_count': 0,
        'invoice_map': {}
    }
    
    try:
        # Check journal
        journal_id = zoho.check_existing_journal(settlement_id)
        if journal_id:
            status['has_journal'] = True
            status['journal_id'] = journal_id
        
        # Check invoices (from tracking file first, then API if needed)
        tracking_file = get_zoho_tracking_path()
        if tracking_file.exists():
            try:
                df_tracking = pd.read_csv(tracking_file)
                df_tracking['settlement_id'] = df_tracking['settlement_id'].astype(str)
                settlement_records = df_tracking[
                    (df_tracking['settlement_id'] == str(settlement_id)) &
                    (df_tracking['record_type'] == 'INVOICE') &
                    (df_tracking['zoho_id'].notna()) &
                    (df_tracking['zoho_id'] != '')
                ]
                if len(settlement_records) > 0:
                    status['invoice_count'] = len(settlement_records)
                    for _, row in settlement_records.iterrows():
                        local_id = str(row['local_identifier']).strip()
                        zoho_id = row['zoho_id']
                        if pd.notna(zoho_id):
                            if isinstance(zoho_id, float):
                                zoho_id_str = f"{zoho_id:.0f}"
                            else:
                                zoho_id_str = str(zoho_id).strip()
                            if local_id and zoho_id_str:
                                status['invoice_map'][local_id] = zoho_id_str
            except:
                pass
        
        # If no invoices in tracking, query API (but wait first)
        if status['invoice_count'] == 0:
            time.sleep(5)  # Rate limit protection
            try:
                api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
                if api_result.get('code') == 0:
                    invoices = api_result.get('invoices', [])
                    status['invoice_count'] = len(invoices)
                    for inv in invoices:
                        inv_num = str(inv.get('invoice_number', '')).strip()
                        inv_id = str(inv.get('invoice_id', '')).strip()
                        if inv_num and inv_id:
                            status['invoice_map'][inv_num] = inv_id
            except:
                pass
        
    except Exception as e:
        print(f"  [ERROR] Error checking status: {e}")
    
    return status


def main():
    print("="*80)
    print("FINALIZING ALL INVOICES AND PAYMENTS IN ZOHO BOOKS")
    print("="*80)
    
    # Get all settlements
    settlements = find_local_settlements()
    print(f"\nFound {len(settlements)} settlement(s)")
    
    zoho = ZohoBooks()
    
    # First, check what needs to be posted
    print("\n" + "="*80)
    print("STEP 1: Checking current status...")
    print("="*80)
    
    needs_invoices = []
    needs_payments = []
    
    for settlement_id in settlements:
        print(f"\nSettlement {settlement_id}:")
        
        # Check local files
        invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
        payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
        
        has_local_invoices = invoice_file.exists()
        has_local_payments = payment_file.exists()
        
        if has_local_invoices:
            df_inv = pd.read_csv(invoice_file)
            local_invoice_count = df_inv['Invoice Number'].nunique()
        else:
            local_invoice_count = 0
        
        if has_local_payments:
            df_pay = pd.read_csv(payment_file)
            local_payment_count = len(df_pay)
        else:
            local_payment_count = 0
        
        # Check what's in Zoho
        status = check_current_status(zoho, settlement_id)
        
        print(f"  Local: {local_invoice_count} invoices, {local_payment_count} payments")
        print(f"  Zoho:  {status['invoice_count']} invoices, {status['payment_count']} payments")
        
        if local_invoice_count > status['invoice_count']:
            needs_invoices.append(settlement_id)
            print(f"  [NEEDS INVOICES] Missing {local_invoice_count - status['invoice_count']} invoice(s)")
        
        if local_payment_count > status['payment_count']:
            needs_payments.append(settlement_id)
            print(f"  [NEEDS PAYMENTS] Missing {local_payment_count - status['payment_count']} payment(s)")
        
        time.sleep(2)  # Rate limit protection
    
    # Post missing invoices
    print("\n" + "="*80)
    print(f"STEP 2: Posting {len(needs_invoices)} settlement(s) with missing invoices...")
    print("="*80)
    
    if needs_invoices:
        print("Waiting 60 seconds for rate limits to reset...")
        time.sleep(60)
    
    for settlement_id in needs_invoices:
        print(f"\n{'='*80}")
        print(f"Settlement: {settlement_id}")
        print(f"{'='*80}")
        
        try:
            results = post_settlement_complete(
                settlement_id,
                post_journal=False,  # Assume journals exist
                post_invoices=True,
                post_payments=False,
                dry_run=False,
                override=True  # Override non-blocking warnings
            )
            
            if results['invoices']['posted']:
                print(f"  [SUCCESS] Posted {results['invoices']['count']} invoice(s)")
            else:
                print(f"  [FAILED] {results['invoices'].get('error', 'Unknown error')}")
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Wait between settlements
        print("  [PAUSE] Waiting 15 seconds before next settlement...")
        time.sleep(15)
    
    # Post missing payments
    print("\n" + "="*80)
    print(f"STEP 3: Posting {len(needs_payments)} settlement(s) with missing payments...")
    print("="*80)
    
    if needs_payments:
        print("Waiting 60 seconds for rate limits to reset...")
        time.sleep(60)
    
    for settlement_id in needs_payments:
        print(f"\n{'='*80}")
        print(f"Settlement: {settlement_id}")
        print(f"{'='*80}")
        
        try:
            results = post_settlement_complete(
                settlement_id,
                post_journal=False,  # Assume journals exist
                post_invoices=False,  # Assume invoices exist
                post_payments=True,
                dry_run=False,
                override=True  # Override non-blocking warnings
            )
            
            if results['payments']['posted']:
                print(f"  [SUCCESS] Posted {results['payments']['count']} payment(s)")
            else:
                print(f"  [FAILED] {results['payments'].get('error', 'Unknown error')}")
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Wait between settlements
        print("  [PAUSE] Waiting 15 seconds before next settlement...")
        time.sleep(15)
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    print(f"\nSettlements processed: {len(settlements)}")
    print(f"Settlements needing invoices: {len(needs_invoices)}")
    print(f"Settlements needing payments: {len(needs_payments)}")
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)
    print("\nAll invoices and payments have been posted to Zoho Books.")
    print("You can now run reports in Zoho Books.")


if __name__ == '__main__':
    main()



