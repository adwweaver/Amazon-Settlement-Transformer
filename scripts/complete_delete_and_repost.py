#!/usr/bin/env python3
"""
Complete process to delete payments/invoices and re-post correctly.

Order:
1. Delete all payments (bulk delete if possible)
2. Delete all invoices (reference_number filter for Amazon settlements)
3. Post all invoices with correct AMZN format (reference_number = settlement_id)
4. Update tracking file with invoice IDs
5. Post all payments (all same date = deposit_date, amounts match invoices)
6. Update tracking file with payment IDs
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


def delete_all_payments_bulk(zoho: ZohoBooks, settlements: list) -> dict:
    """Delete all Amazon payments using bulk delete API."""
    print("="*80)
    print("STEP 1: DELETING ALL AMAZON PAYMENTS")
    print("="*80)
    
    all_payment_ids = []
    
    for settlement_id in settlements:
        print(f"\nSettlement: {settlement_id}")
        print(f"  Querying payments...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [SKIP] Could not query: {api_result.get('message', 'Unknown error')}")
                continue
            
            payments = api_result.get('customerpayments', [])
            print(f"  Found {len(payments)} payment(s)")
            
            payment_ids = [str(p.get('payment_id', '')).strip() for p in payments if p.get('payment_id')]
            all_payment_ids.extend(payment_ids)
            
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    if not all_payment_ids:
        print(f"\n[INFO] No payments found to delete")
        return {'total': 0, 'deleted': 0, 'failed': 0}
    
    print(f"\nTotal payment IDs found: {len(all_payment_ids)}")
    print(f"Deleting payments in bulk (max 100 per request)...")
    
    deleted = 0
    failed = 0
    
    # Bulk delete in batches of 100
    batch_size = 100
    for i in range(0, len(all_payment_ids), batch_size):
        batch = all_payment_ids[i:i+batch_size]
        batch_ids = ','.join(batch)
        
        print(f"  Deleting batch {i//batch_size + 1} ({len(batch)} payments)...")
        time.sleep(5)
        
        try:
            delete_result = zoho._api_request('DELETE', f'customerpayments?payment_id={batch_ids}&bulk_delete=true')
            
            if delete_result.get('code') == 0:
                deleted += len(batch)
                print(f"    [OK] Deleted {len(batch)} payment(s)")
            else:
                failed += len(batch)
                print(f"    [FAIL] {delete_result.get('message', 'Unknown error')}")
                
                # Fall back to individual deletion
                print(f"    [FALLBACK] Trying individual deletion...")
                for payment_id in batch:
                    try:
                        ind_result = zoho._api_request('DELETE', f'customerpayments/{payment_id}')
                        if ind_result.get('code') == 0:
                            deleted += 1
                            failed -= 1
                        time.sleep(0.3)
                    except:
                        pass
        except Exception as e:
            print(f"    [ERROR] {e}")
            failed += len(batch)
        
        if i + batch_size < len(all_payment_ids):
            print(f"  [PAUSE] Waiting 10 seconds...")
            time.sleep(10)
    
    print(f"\n{'='*80}")
    print(f"PAYMENT DELETION SUMMARY")
    print(f"{'='*80}")
    print(f"Total: {len(all_payment_ids)}")
    print(f"Deleted: {deleted}")
    print(f"Failed: {failed}")
    
    return {'total': len(all_payment_ids), 'deleted': deleted, 'failed': failed}


def delete_all_invoices(zoho: ZohoBooks, settlements: list) -> dict:
    """Delete all Amazon invoices."""
    print("\n" + "="*80)
    print("STEP 2: DELETING ALL AMAZON INVOICES")
    print("="*80)
    
    all_invoice_ids = []
    
    for settlement_id in settlements:
        print(f"\nSettlement: {settlement_id}")
        print(f"  Querying invoices...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [SKIP] Could not query: {api_result.get('message', 'Unknown error')}")
                continue
            
            invoices = api_result.get('invoices', [])
            print(f"  Found {len(invoices)} invoice(s)")
            
            invoice_ids = [str(inv.get('invoice_id', '')).strip() for inv in invoices if inv.get('invoice_id')]
            all_invoice_ids.extend(invoice_ids)
            
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    if not all_invoice_ids:
        print(f"\n[INFO] No invoices found to delete")
        return {'total': 0, 'deleted': 0, 'failed': 0}
    
    print(f"\nTotal invoice IDs found: {len(all_invoice_ids)}")
    print(f"Deleting invoices individually (200 max per batch due to API limits)...")
    
    deleted = 0
    failed = 0
    
    # Delete in batches with delays
    batch_size = 200
    for i in range(0, len(all_invoice_ids), batch_size):
        batch = all_invoice_ids[i:i+batch_size]
        
        print(f"  Deleting batch {i//batch_size + 1} ({len(batch)} invoices)...")
        
        for invoice_id in batch:
            try:
                delete_result = zoho._api_request('DELETE', f'invoices/{invoice_id}')
                if delete_result.get('code') == 0:
                    deleted += 1
                    if deleted % 50 == 0:
                        print(f"    [OK] Deleted {deleted} invoice(s)...")
                else:
                    failed += 1
                    if failed <= 5:
                        print(f"    [FAIL] {invoice_id}: {delete_result.get('message', 'Unknown error')}")
                time.sleep(0.3)
            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"    [ERROR] {e}")
        
        if i + batch_size < len(all_invoice_ids):
            print(f"  [PAUSE] Waiting 10 seconds...")
            time.sleep(10)
    
    print(f"\n{'='*80}")
    print(f"INVOICE DELETION SUMMARY")
    print(f"{'='*80}")
    print(f"Total: {len(all_invoice_ids)}")
    print(f"Deleted: {deleted}")
    print(f"Failed: {failed}")
    
    return {'total': len(all_invoice_ids), 'deleted': deleted, 'failed': failed}


def verify_and_post_invoices(zoho: ZohoBooks, settlements: list) -> dict:
    """Post all invoices with correct AMZN format and reference_number."""
    print("\n" + "="*80)
    print("STEP 3: POSTING INVOICES WITH CORRECT FORMAT")
    print("="*80)
    print("Note: Using ignore_auto_number_generation=true and reference_number=settlement_id")
    
    results = {}
    total_posted = 0
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements)}: {settlement_id}")
        print(f"{'='*80}")
        
        invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
        if not invoice_file.exists():
            print(f"  [SKIP] No invoice file")
            continue
        
        # Check how many invoices we need
        try:
            df = pd.read_csv(invoice_file)
            invoice_count = len(df['Invoice Number'].unique())
            print(f"  Local invoices: {invoice_count}")
        except:
            print(f"  [SKIP] Could not read invoice file")
            continue
        
        print(f"  Posting invoices...")
        print(f"  Waiting 10 seconds for rate limits...")
        time.sleep(10)
        
        try:
            result = post_settlement_complete(
                settlement_id,
                post_journal=False,
                post_invoices=True,
                post_payments=False,
                dry_run=False,
                override=True
            )
            
            if result['invoices']['posted']:
                count = result['invoices']['count']
                total_posted += count
                print(f"  [SUCCESS] Posted {count} invoice(s)")
                results[settlement_id] = {'posted': count, 'status': 'SUCCESS'}
            else:
                error = result['invoices'].get('error', 'Unknown error')
                print(f"  [FAILED] {error}")
                results[settlement_id] = {'posted': 0, 'status': 'FAILED', 'error': error}
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results[settlement_id] = {'posted': 0, 'status': 'ERROR', 'error': str(e)}
        
        if i < len(settlements):
            print(f"  [PAUSE] Waiting 15 seconds...")
            time.sleep(15)
    
    print(f"\n{'='*80}")
    print(f"INVOICE POSTING SUMMARY")
    print(f"{'='*80}")
    print(f"Total posted: {total_posted}")
    
    return results


def verify_invoice_matching(zoho: ZohoBooks, settlements: list):
    """Verify invoices are correctly matched to settlements by reference_number."""
    print("\n" + "="*80)
    print("STEP 4: VERIFYING INVOICE MATCHING TO SETTLEMENTS")
    print("="*80)
    
    tracking_file = get_zoho_tracking_path()
    
    for settlement_id in settlements:
        print(f"\nSettlement: {settlement_id}")
        
        # Query Zoho for invoices
        print(f"  Querying Zoho (waiting 5s)...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [ERROR] Could not query: {api_result.get('message', 'Unknown error')}")
                continue
            
            zoho_invoices = api_result.get('invoices', [])
            print(f"  Found {len(zoho_invoices)} invoice(s) in Zoho")
            
            # Check that all have correct reference_number
            matched = 0
            for inv in zoho_invoices:
                ref_num = str(inv.get('reference_number', '')).strip()
                inv_num = str(inv.get('invoice_number', '')).strip()
                inv_id = str(inv.get('invoice_id', '')).strip()
                
                if ref_num == settlement_id:
                    matched += 1
                else:
                    print(f"    [WARN] Invoice {inv_num} (ID: {inv_id}) has wrong reference_number: {ref_num}")
            
            print(f"  [OK] {matched}/{len(zoho_invoices)} invoices correctly matched by reference_number")
            
            # Update tracking file
            if tracking_file.exists():
                try:
                    df_track = pd.read_csv(tracking_file)
                    df_track['settlement_id'] = df_track['settlement_id'].astype(str)
                    
                    for inv in zoho_invoices:
                        inv_num = str(inv.get('invoice_number', '')).strip()
                        inv_id = str(inv.get('invoice_id', '')).strip()
                        
                        # Update or create tracking record
                        mask = (
                            (df_track['settlement_id'] == str(settlement_id)) &
                            (df_track['record_type'] == 'INVOICE') &
                            (df_track['local_identifier'] == inv_num)
                        )
                        
                        if mask.any():
                            df_track.loc[mask, 'zoho_id'] = inv_id
                            df_track.loc[mask, 'status'] = 'POSTED'
                        else:
                            # Add new record
                            new_row = pd.DataFrame([{
                                'settlement_id': str(settlement_id),
                                'record_type': 'INVOICE',
                                'local_identifier': inv_num,
                                'zoho_id': inv_id,
                                'status': 'POSTED',
                                'posted_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                            }])
                            df_track = pd.concat([df_track, new_row], ignore_index=True)
                    
                    df_track.to_csv(tracking_file, index=False)
                    print(f"  [OK] Updated tracking file")
                except Exception as e:
                    print(f"  [ERROR] Could not update tracking: {e}")
            
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        time.sleep(5)
    
    print(f"\n{'='*80}")
    print("VERIFICATION COMPLETE")
    print(f"{'='*80}")


def post_all_payments(zoho: ZohoBooks, settlements: list) -> dict:
    """Post all payments - all same date (deposit_date) and amounts match invoices."""
    print("\n" + "="*80)
    print("STEP 5: POSTING PAYMENTS")
    print("="*80)
    print("Note: All payments use same date (deposit_date from source) and match invoice amounts")
    
    results = {}
    total_posted = 0
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements)}: {settlement_id}")
        print(f"{'='*80}")
        
        payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
        if not payment_file.exists():
            print(f"  [SKIP] No payment file")
            continue
        
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
                total_posted += count
                print(f"  [SUCCESS] Posted {count} payment(s)")
                results[settlement_id] = {'posted': count, 'status': 'SUCCESS'}
            else:
                error = result['payments'].get('error', 'Unknown error')
                print(f"  [FAILED] {error}")
                results[settlement_id] = {'posted': 0, 'status': 'FAILED', 'error': error}
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results[settlement_id] = {'posted': 0, 'status': 'ERROR', 'error': str(e)}
        
        if i < len(settlements):
            print(f"  [PAUSE] Waiting 15 seconds...")
            time.sleep(15)
    
    print(f"\n{'='*80}")
    print(f"PAYMENT POSTING SUMMARY")
    print(f"{'='*80}")
    print(f"Total posted: {total_posted}")
    
    return results


def update_payment_tracking(zoho: ZohoBooks, settlements: list):
    """Update tracking file with payment IDs."""
    print("\n" + "="*80)
    print("STEP 6: UPDATING PAYMENT TRACKING")
    print("="*80)
    
    tracking_file = get_zoho_tracking_path()
    
    for settlement_id in settlements:
        print(f"\nSettlement: {settlement_id}")
        
        print(f"  Querying Zoho (waiting 5s)...")
        time.sleep(5)
        
        try:
            api_result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
            
            if api_result.get('code') != 0:
                print(f"  [SKIP] Could not query: {api_result.get('message', 'Unknown error')}")
                continue
            
            payments = api_result.get('customerpayments', [])
            print(f"  Found {len(payments)} payment(s) in Zoho")
            
            # Update tracking file
            if tracking_file.exists():
                try:
                    df_track = pd.read_csv(tracking_file)
                    df_track['settlement_id'] = df_track['settlement_id'].astype(str)
                    
                    for payment in payments:
                        pay_id = str(payment.get('payment_id', '')).strip()
                        ref_num = str(payment.get('reference_number', '')).strip()
                        amount = payment.get('amount', 0)
                        
                        # Match by reference_number and amount
                        mask = (
                            (df_track['settlement_id'] == str(settlement_id)) &
                            (df_track['record_type'] == 'PAYMENT') &
                            (df_track['zoho_id'].isna() | (df_track['zoho_id'] == ''))
                        )
                        
                        if mask.any():
                            # Update first unmatched payment for this settlement
                            idx = mask.idxmax() if mask.any() else None
                            if idx is not None:
                                df_track.loc[idx, 'zoho_id'] = pay_id
                                df_track.loc[idx, 'status'] = 'POSTED'
                        else:
                            # Add new record
                            new_row = pd.DataFrame([{
                                'settlement_id': str(settlement_id),
                                'record_type': 'PAYMENT',
                                'local_identifier': ref_num or f"PAYMENT_{settlement_id}_{amount}",
                                'zoho_id': pay_id,
                                'status': 'POSTED',
                                'posted_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                            }])
                            df_track = pd.concat([df_track, new_row], ignore_index=True)
                    
                    df_track.to_csv(tracking_file, index=False)
                    print(f"  [OK] Updated tracking file")
                except Exception as e:
                    print(f"  [ERROR] Could not update tracking: {e}")
            
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        time.sleep(5)
    
    print(f"\n{'='*80}")
    print("TRACKING UPDATE COMPLETE")
    print(f"{'='*80}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Complete delete and re-post process')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    print("="*80)
    print("COMPLETE DELETE AND RE-POST PROCESS")
    print("="*80)
    print("\nThis will:")
    print("1. Delete all Amazon payments (bulk delete)")
    print("2. Delete all Amazon invoices")
    print("3. Post all invoices with correct AMZN format (reference_number = settlement_id)")
    print("4. Verify invoice matching and update tracking")
    print("5. Post all payments (same date = deposit_date, amounts match invoices)")
    print("6. Update payment tracking")
    print("\n" + "="*80)
    
    if not args.confirm:
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
    else:
        print("\n[AUTO-CONFIRMED] Proceeding...")
    
    zoho = ZohoBooks()
    settlements = find_local_settlements()
    
    print(f"\nFound {len(settlements)} settlement(s) to process")
    
    # Step 1: Delete payments
    payment_deletion = delete_all_payments_bulk(zoho, settlements)
    
    # Step 2: Delete invoices
    print(f"\n[PAUSE] Waiting 30 seconds before deleting invoices...")
    time.sleep(30)
    
    invoice_deletion = delete_all_invoices(zoho, settlements)
    
    # Step 3: Post invoices
    print(f"\n[PAUSE] Waiting 30 seconds before posting invoices...")
    time.sleep(30)
    
    invoice_posting = verify_and_post_invoices(zoho, settlements)
    
    # Step 4: Verify invoice matching
    print(f"\n[PAUSE] Waiting 30 seconds before verifying invoices...")
    time.sleep(30)
    
    verify_invoice_matching(zoho, settlements)
    
    # Step 5: Post payments
    print(f"\n[PAUSE] Waiting 30 seconds before posting payments...")
    time.sleep(30)
    
    payment_posting = post_all_payments(zoho, settlements)
    
    # Step 6: Update payment tracking
    print(f"\n[PAUSE] Waiting 30 seconds before updating payment tracking...")
    time.sleep(30)
    
    update_payment_tracking(zoho, settlements)
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"\nDeletion:")
    print(f"  Payments: {payment_deletion['deleted']}/{payment_deletion['total']}")
    print(f"  Invoices: {invoice_deletion['deleted']}/{invoice_deletion['total']}")
    
    total_invoices = sum(r.get('posted', 0) for r in invoice_posting.values())
    total_payments = sum(r.get('posted', 0) for r in payment_posting.values())
    
    print(f"\nPosting:")
    print(f"  Invoices: {total_invoices}")
    print(f"  Payments: {total_payments}")
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()



