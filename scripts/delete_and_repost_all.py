#!/usr/bin/env python3
"""
Delete all Amazon payments and invoices, then re-post them in correct order.

Deletion Order:
1. Payments (must be deleted first)
2. Invoices (can only be deleted after payments are removed)

Posting Order:
1. Invoices (must exist before payments can be posted)
2. Payments (depend on invoices)

All invoices will use correct AMZN format with ignore_auto_number_generation=true
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


def delete_all_amazon_payments(zoho: ZohoBooks) -> dict:
    """Delete all Amazon payments from Zoho (must be done first)."""
    print("="*80)
    print("STEP 1: DELETING ALL AMAZON PAYMENTS")
    print("="*80)
    
    settlements = find_local_settlements()
    
    all_payment_ids = []
    deleted_count = 0
    failed_count = 0
    
    for settlement_id in settlements:
        print(f"\nSettlement: {settlement_id}")
        
        # Query for payments by reference_number
        print(f"  Querying payments...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [SKIP] Could not query: {api_result.get('message', 'Unknown error')}")
                continue
            
            payments = api_result.get('customerpayments', [])
            print(f"  Found {len(payments)} payment(s)")
            
            if len(payments) == 0:
                print(f"  [SKIP] No payments to delete")
                continue
            
            # Collect payment IDs
            payment_ids = [str(p.get('payment_id', '')).strip() for p in payments if p.get('payment_id')]
            all_payment_ids.extend(payment_ids)
            
            # Delete in batches of 10
            batch_size = 10
            for i in range(0, len(payment_ids), batch_size):
                batch = payment_ids[i:i+batch_size]
                print(f"  Deleting batch {i//batch_size + 1} ({len(batch)} payments)...")
                
                for payment_id in batch:
                    try:
                        delete_result = zoho._api_request('DELETE', f'customerpayments/{payment_id}')
                        if delete_result.get('code') == 0:
                            deleted_count += 1
                            print(f"    [OK] Deleted payment {payment_id}")
                        else:
                            failed_count += 1
                            print(f"    [FAIL] Could not delete {payment_id}: {delete_result.get('message', 'Unknown error')}")
                        time.sleep(0.5)  # Small delay between deletions
                    except Exception as e:
                        failed_count += 1
                        print(f"    [ERROR] {e}")
                
                # Wait between batches
                if i + batch_size < len(payment_ids):
                    print(f"  [PAUSE] Waiting 5 seconds before next batch...")
                    time.sleep(5)
            
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        # Wait between settlements
        if settlement_id != settlements[-1]:
            print(f"  [PAUSE] Waiting 10 seconds before next settlement...")
            time.sleep(10)
    
    print(f"\n{'='*80}")
    print(f"PAYMENT DELETION SUMMARY")
    print(f"{'='*80}")
    print(f"Total payment IDs found: {len(all_payment_ids)}")
    print(f"Successfully deleted: {deleted_count}")
    print(f"Failed: {failed_count}")
    
    return {'total': len(all_payment_ids), 'deleted': deleted_count, 'failed': failed_count}


def delete_all_amazon_invoices(zoho: ZohoBooks) -> dict:
    """Delete all Amazon invoices from Zoho (after payments are deleted)."""
    print("\n" + "="*80)
    print("STEP 2: DELETING ALL AMAZON INVOICES")
    print("="*80)
    
    settlements = find_local_settlements()
    
    all_invoice_ids = []
    deleted_count = 0
    failed_count = 0
    
    for settlement_id in settlements:
        print(f"\nSettlement: {settlement_id}")
        
        # Query for invoices by reference_number
        print(f"  Querying invoices...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [SKIP] Could not query: {api_result.get('message', 'Unknown error')}")
                continue
            
            invoices = api_result.get('invoices', [])
            print(f"  Found {len(invoices)} invoice(s)")
            
            if len(invoices) == 0:
                print(f"  [SKIP] No invoices to delete")
                continue
            
            # Collect invoice IDs
            invoice_ids = [str(inv.get('invoice_id', '')).strip() for inv in invoices if inv.get('invoice_id')]
            all_invoice_ids.extend(invoice_ids)
            
            # Delete in batches of 200 (Zoho limit)
            batch_size = 200
            for i in range(0, len(invoice_ids), batch_size):
                batch = invoice_ids[i:i+batch_size]
                print(f"  Deleting batch {i//batch_size + 1} ({len(batch)} invoices)...")
                
                for invoice_id in batch:
                    try:
                        delete_result = zoho._api_request('DELETE', f'invoices/{invoice_id}')
                        if delete_result.get('code') == 0:
                            deleted_count += 1
                            if deleted_count % 10 == 0:
                                print(f"    [OK] Deleted {deleted_count} invoice(s)...")
                        else:
                            failed_count += 1
                            if failed_count <= 5:  # Show first 5 failures
                                print(f"    [FAIL] Could not delete {invoice_id}: {delete_result.get('message', 'Unknown error')}")
                        time.sleep(0.3)  # Small delay between deletions
                    except Exception as e:
                        failed_count += 1
                        if failed_count <= 5:
                            print(f"    [ERROR] {e}")
                
                # Wait between batches
                if i + batch_size < len(invoice_ids):
                    print(f"  [PAUSE] Waiting 10 seconds before next batch...")
                    time.sleep(10)
            
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        # Wait between settlements
        if settlement_id != settlements[-1]:
            print(f"  [PAUSE] Waiting 10 seconds before next settlement...")
            time.sleep(10)
    
    print(f"\n{'='*80}")
    print(f"INVOICE DELETION SUMMARY")
    print(f"{'='*80}")
    print(f"Total invoice IDs found: {len(all_invoice_ids)}")
    print(f"Successfully deleted: {deleted_count}")
    print(f"Failed: {failed_count}")
    
    return {'total': len(all_invoice_ids), 'deleted': deleted_count, 'failed': failed_count}


def post_all_invoices(zoho: ZohoBooks, settlements: list) -> dict:
    """Post all invoices with correct AMZN format."""
    print("\n" + "="*80)
    print("STEP 3: POSTING ALL INVOICES (WITH CORRECT AMZN FORMAT)")
    print("="*80)
    print("Note: Using ignore_auto_number_generation=true for correct invoice numbers")
    
    results = {}
    total_posted = 0
    total_failed = 0
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements)}: {settlement_id}")
        print(f"{'='*80}")
        
        # Check if journal exists first
        invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
        if not invoice_file.exists():
            print(f"  [SKIP] No invoice file")
            continue
        
        # Post invoices
        print(f"  Posting invoices...")
        print(f"  Waiting 10 seconds for rate limits...")
        time.sleep(10)
        
        try:
            result = post_settlement_complete(
                settlement_id,
                post_journal=False,  # Assume journals already exist
                post_invoices=True,
                post_payments=False,  # Payments come next
                dry_run=False,
                override=True  # Skip validation warnings
            )
            
            if result['invoices']['posted']:
                count = result['invoices']['count']
                total_posted += count
                print(f"  [SUCCESS] Posted {count} invoice(s)")
                results[settlement_id] = {'posted': count, 'status': 'SUCCESS'}
            else:
                error = result['invoices'].get('error', 'Unknown error')
                total_failed += 1
                print(f"  [FAILED] {error}")
                results[settlement_id] = {'posted': 0, 'status': 'FAILED', 'error': error}
        except Exception as e:
            total_failed += 1
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results[settlement_id] = {'posted': 0, 'status': 'ERROR', 'error': str(e)}
        
        # Wait between settlements
        if i < len(settlements):
            print(f"  [PAUSE] Waiting 15 seconds before next settlement...")
            time.sleep(15)
    
    print(f"\n{'='*80}")
    print(f"INVOICE POSTING SUMMARY")
    print(f"{'='*80}")
    print(f"Total invoices posted: {total_posted}")
    print(f"Failed settlements: {total_failed}")
    
    return results


def post_all_payments(zoho: ZohoBooks, settlements: list) -> dict:
    """Post all payments (after invoices are posted)."""
    print("\n" + "="*80)
    print("STEP 4: POSTING ALL PAYMENTS")
    print("="*80)
    
    results = {}
    total_posted = 0
    total_failed = 0
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements)}: {settlement_id}")
        print(f"{'='*80}")
        
        # Check if payment file exists
        payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
        if not payment_file.exists():
            print(f"  [SKIP] No payment file")
            continue
        
        # Post payments
        print(f"  Posting payments...")
        print(f"  Waiting 10 seconds for rate limits...")
        time.sleep(10)
        
        try:
            result = post_settlement_complete(
                settlement_id,
                post_journal=False,
                post_invoices=False,  # Invoices already posted
                post_payments=True,
                dry_run=False,
                override=True
            )
            
            if result['payments']['posted']:
                count = result['payments']['count']
                total_posted += count
                print(f"  [SUCCESS] Posted {count} payment(s)")
                results[settlement_id] = {'posted': count, 'status': 'SUCCESS'}
            else:
                error = result['payments'].get('error', 'Unknown error')
                total_failed += 1
                print(f"  [FAILED] {error}")
                results[settlement_id] = {'posted': 0, 'status': 'FAILED', 'error': error}
        except Exception as e:
            total_failed += 1
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results[settlement_id] = {'posted': 0, 'status': 'ERROR', 'error': str(e)}
        
        # Wait between settlements
        if i < len(settlements):
            print(f"  [PAUSE] Waiting 15 seconds before next settlement...")
            time.sleep(15)
    
    print(f"\n{'='*80}")
    print(f"PAYMENT POSTING SUMMARY")
    print(f"{'='*80}")
    print(f"Total payments posted: {total_posted}")
    print(f"Failed settlements: {total_failed}")
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Delete and re-post all Amazon invoices and payments')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    print("="*80)
    print("DELETE AND RE-POST ALL AMAZON INVOICES AND PAYMENTS")
    print("="*80)
    print("\nThis will:")
    print("1. Delete all Amazon payments (must be first)")
    print("2. Delete all Amazon invoices (after payments)")
    print("3. Post all invoices with correct AMZN format")
    print("4. Post all payments (after invoices)")
    print("\n" + "="*80)
    
    if not args.confirm:
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
    else:
        print("\n[AUTO-CONFIRMED] Proceeding with deletion and re-posting...")
    
    zoho = ZohoBooks()
    settlements = find_local_settlements()
    
    print(f"\nFound {len(settlements)} settlement(s) to process")
    
    # Step 1: Delete payments
    payment_deletion = delete_all_amazon_payments(zoho)
    
    if payment_deletion['failed'] > 0:
        print(f"\n[WARNING] {payment_deletion['failed']} payment deletion(s) failed")
        print("Continuing anyway...")
    
    # Step 2: Delete invoices
    invoice_deletion = delete_all_amazon_invoices(zoho)
    
    if invoice_deletion['failed'] > 0:
        print(f"\n[WARNING] {invoice_deletion['failed']} invoice deletion(s) failed")
        print("Continuing anyway...")
    
    # Step 3: Post invoices
    print(f"\n[PAUSE] Waiting 30 seconds before posting invoices...")
    time.sleep(30)
    
    invoice_posting = post_all_invoices(zoho, settlements)
    
    # Step 4: Post payments
    print(f"\n[PAUSE] Waiting 30 seconds before posting payments...")
    time.sleep(30)
    
    payment_posting = post_all_payments(zoho, settlements)
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"\nDeletion:")
    print(f"  Payments deleted: {payment_deletion['deleted']}/{payment_deletion['total']}")
    print(f"  Invoices deleted: {invoice_deletion['deleted']}/{invoice_deletion['total']}")
    
    total_invoices_posted = sum(r.get('posted', 0) for r in invoice_posting.values())
    total_payments_posted = sum(r.get('posted', 0) for r in payment_posting.values())
    
    print(f"\nPosting:")
    print(f"  Invoices posted: {total_invoices_posted}")
    print(f"  Payments posted: {total_payments_posted}")
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()

