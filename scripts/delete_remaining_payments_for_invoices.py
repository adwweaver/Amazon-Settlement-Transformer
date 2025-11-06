#!/usr/bin/env python3
"""
Find and delete remaining payments that are blocking invoice deletion.
Then retry deleting the failed invoices.

Usage:
  python scripts/delete_remaining_payments_for_invoices.py --confirm
"""

import argparse
import time
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from paths import get_sharepoint_base


def get_all_remaining_payments(zoho: ZohoBooks) -> list:
    """Get all remaining payments for Amazon customer."""
    all_payments = []
    page = 1
    per_page = 200
    
    customer_id = zoho.get_customer_id("Amazon.ca")
    
    print("Fetching all remaining Amazon payments...")
    
    while True:
        try:
            if customer_id:
                result = zoho._api_request('GET', f'customerpayments?customer_id={customer_id}&per_page={per_page}&page={page}')
            else:
                result = zoho._api_request('GET', f'customerpayments?per_page={per_page}&page={page}')
            
            if result.get('code') != 0:
                break
            
            payments = result.get('customerpayments', [])
            if not payments:
                break
            
            # Filter for Amazon payments
            for pay in payments:
                customer_name = pay.get('customer_name', '')
                reference_number = pay.get('reference_number', '')
                
                if 'amazon' in customer_name.lower() or (reference_number and reference_number.isdigit()):
                    all_payments.append({
                        'payment_id': pay.get('payment_id', ''),
                        'payment_number': pay.get('payment_number', ''),
                        'invoice_number': pay.get('invoice_number', ''),
                        'reference_number': reference_number,
                        'amount': pay.get('amount', 0)
                    })
            
            page_info = result.get('page_context', {})
            if not page_info.get('has_more_page', False):
                break
            
            page += 1
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error fetching payments: {e}")
            break
    
    print(f"  Found {len(all_payments)} remaining payments")
    return all_payments


def delete_payments(zoho: ZohoBooks, payments: list, dry_run: bool = True) -> dict:
    """Delete payments."""
    deleted = 0
    failed = 0
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Deleting {len(payments)} payments...")
    
    for pay in payments:
        payment_id = pay['payment_id']
        payment_num = pay.get('payment_number', 'N/A')
        invoice_num = pay.get('invoice_number', 'N/A')
        
        if dry_run:
            print(f"  [DRY RUN] Would delete payment {payment_num} (Invoice: {invoice_num}, ID: {payment_id})")
            deleted += 1
        else:
            try:
                result = zoho._api_request('DELETE', f'customerpayments/{payment_id}')
                
                if result.get('code') == 0:
                    print(f"  [OK] Deleted payment {payment_num} (ID: {payment_id})")
                    deleted += 1
                else:
                    error_msg = result.get('message', 'Unknown error')
                    print(f"  [FAIL] Payment {payment_num} (ID: {payment_id}): {error_msg}")
                    failed += 1
                
                time.sleep(0.2)
            except Exception as e:
                print(f"  [FAIL] Payment {payment_num} (ID: {payment_id}): {e}")
                failed += 1
    
    return {'deleted': deleted, 'failed': failed}


def retry_invoice_deletions(zoho: ZohoBooks, failed_file: Path, dry_run: bool = True) -> dict:
    """Retry deletion of failed invoices."""
    if not failed_file.exists():
        return {'deleted': 0, 'failed': 0}
    
    df = pd.read_csv(failed_file)
    invoice_failures = df[df['type'] == 'INVOICE']
    
    if invoice_failures.empty:
        print("No failed invoices to retry")
        return {'deleted': 0, 'failed': 0}
    
    print(f"\nRetrying deletion of {len(invoice_failures)} failed invoices...")
    
    deleted = 0
    failed = 0
    
    for idx, row in invoice_failures.iterrows():
        invoice_id = row['id']
        invoice_num = row['number']
        
        if dry_run:
            print(f"  [DRY RUN] Would retry deletion of invoice {invoice_num} (ID: {invoice_id})")
            deleted += 1
        else:
            try:
                result = zoho._api_request('DELETE', f'invoices/{invoice_id}')
                
                if result.get('code') == 0:
                    print(f"  [OK] Deleted invoice {invoice_num} (ID: {invoice_id})")
                    deleted += 1
                else:
                    error_msg = result.get('message', 'Unknown error')
                    print(f"  [FAIL] Invoice {invoice_num} (ID: {invoice_id}): {error_msg}")
                    failed += 1
                
                time.sleep(0.2)
            except Exception as e:
                print(f"  [FAIL] Invoice {invoice_num} (ID: {invoice_id}): {e}")
                failed += 1
    
    return {'deleted': deleted, 'failed': failed}


def main():
    parser = argparse.ArgumentParser(description='Delete remaining payments and retry invoice deletions')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (default is dry-run)')
    args = parser.parse_args()
    
    dry_run = not args.confirm
    
    print("=" * 80)
    if dry_run:
        print("DRY RUN - No deletions will be performed")
    else:
        print("LIVE MODE - DELETIONS WILL BE PERFORMED")
    print("=" * 80)
    
    zoho = ZohoBooks()
    failed_file = get_sharepoint_base() / "failed_deletions.csv"
    
    # STEP 1: Delete remaining payments
    print("\n" + "=" * 80)
    print("STEP 1: DELETE REMAINING PAYMENTS")
    print("=" * 80)
    
    remaining_payments = get_all_remaining_payments(zoho)
    
    if remaining_payments:
        payment_results = delete_payments(zoho, remaining_payments, dry_run=dry_run)
        print(f"\nPayment Deletion: {payment_results['deleted']} deleted, {payment_results['failed']} failed")
    else:
        print("\nNo remaining payments found")
    
    # STEP 2: Retry invoice deletions
    print("\n" + "=" * 80)
    print("STEP 2: RETRY INVOICE DELETIONS")
    print("=" * 80)
    
    invoice_results = retry_invoice_deletions(zoho, failed_file, dry_run=dry_run)
    print(f"\nInvoice Retry: {invoice_results['deleted']} deleted, {invoice_results['failed']} failed")
    
    print("\n" + "=" * 80)
    if dry_run:
        print("DRY RUN COMPLETE")
        print("\nTo actually delete, run with --confirm:")
        print("  python scripts/delete_remaining_payments_for_invoices.py --confirm")
    else:
        print("DELETION COMPLETE")
        if invoice_results['failed'] > 0:
            print(f"\n{invoice_results['failed']} invoices still failed - may need manual deletion in Zoho")


if __name__ == '__main__':
    main()



