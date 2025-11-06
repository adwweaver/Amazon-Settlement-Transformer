#!/usr/bin/env python3
"""
Retry deletion of failed invoices after ensuring all payments are deleted.

Usage:
  python scripts/retry_failed_deletions.py --confirm
"""

import argparse
import time
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from paths import get_sharepoint_base


def get_payments_for_invoice(zoho: ZohoBooks, invoice_id: str) -> list:
    """Get all payments linked to an invoice."""
    payments = []
    try:
        # Get invoice details to find linked payments
        result = zoho._api_request('GET', f'invoices/{invoice_id}')
        if result.get('code') == 0:
            invoice = result.get('invoice', {})
            # Check if invoice has payment info
            # Payments are usually linked via customerpayments endpoint
            # Try to find payments by invoice reference
            ref_num = invoice.get('reference_number', '')
            if ref_num:
                pay_result = zoho._api_request('GET', f'customerpayments?reference_number={ref_num}&per_page=200')
                if pay_result.get('code') == 0:
                    for pay in pay_result.get('customerpayments', []):
                        # Check if payment is linked to this invoice
                        invoice_number = pay.get('invoice_number', '')
                        if invoice_number:
                            payments.append({
                                'payment_id': pay.get('payment_id'),
                                'payment_number': pay.get('payment_number'),
                                'invoice_number': invoice_number
                            })
    except Exception as e:
        print(f"  Error checking payments for invoice {invoice_id}: {e}")
    
    return payments


def retry_failed_invoice_deletions(zoho: ZohoBooks, failed_file: Path, dry_run: bool = True) -> dict:
    """Retry deletion of failed invoices."""
    if not failed_file.exists():
        print(f"Failed deletions file not found: {failed_file}")
        return {'deleted': 0, 'failed': 0, 'errors': []}
    
    df = pd.read_csv(failed_file)
    invoice_failures = df[df['type'] == 'INVOICE']
    
    if invoice_failures.empty:
        print("No failed invoices to retry")
        return {'deleted': 0, 'failed': 0, 'errors': []}
    
    print(f"\nFound {len(invoice_failures)} failed invoices to retry")
    
    deleted = 0
    failed = 0
    errors = []
    
    for idx, row in invoice_failures.iterrows():
        invoice_id = row['id']
        invoice_num = row['number']
        error = row['error']
        
        print(f"\nRetrying invoice {invoice_num} (ID: {invoice_id})")
        print(f"  Original error: {error}")
        
        # Check if payments still exist
        payments = get_payments_for_invoice(zoho, invoice_id)
        if payments:
            print(f"  [WARN] Found {len(payments)} linked payments - attempting to delete...")
            for pay in payments:
                pay_id = pay['payment_id']
                if not dry_run:
                    try:
                        result = zoho._api_request('DELETE', f'customerpayments/{pay_id}')
                        if result.get('code') == 0:
                            print(f"  [OK] Deleted payment {pay['payment_number']} (ID: {pay_id})")
                        else:
                            print(f"  [FAIL] Could not delete payment {pay['payment_number']}: {result.get('message')}")
                    except Exception as e:
                        print(f"  [FAIL] Error deleting payment: {e}")
                    time.sleep(0.2)
        
        # Try to delete invoice again
        if dry_run:
            print(f"  [DRY RUN] Would retry deletion of invoice {invoice_num}")
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
                    errors.append({
                        'type': 'INVOICE',
                        'id': invoice_id,
                        'number': invoice_num,
                        'error': error_msg
                    })
                    failed += 1
                time.sleep(0.2)
            except Exception as e:
                print(f"  [FAIL] Invoice {invoice_num} (ID: {invoice_id}): {e}")
                errors.append({
                    'type': 'INVOICE',
                    'id': invoice_id,
                    'number': invoice_num,
                    'error': str(e)
                })
                failed += 1
    
    return {'deleted': deleted, 'failed': failed, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description='Retry deletion of failed invoices')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (default is dry-run)')
    args = parser.parse_args()
    
    dry_run = not args.confirm
    
    failed_file = get_sharepoint_base() / "failed_deletions.csv"
    
    print("=" * 80)
    if dry_run:
        print("DRY RUN - No deletions will be performed")
    else:
        print("LIVE MODE - DELETIONS WILL BE PERFORMED")
    print("=" * 80)
    
    zoho = ZohoBooks()
    
    results = retry_failed_invoice_deletions(zoho, failed_file, dry_run=dry_run)
    
    print("\n" + "=" * 80)
    print("RETRY SUMMARY")
    print("=" * 80)
    print(f"Deleted: {results['deleted']}")
    print(f"Failed: {results['failed']}")
    
    if results['errors']:
        print(f"\nFailed deletions ({len(results['errors'])}):")
        for err in results['errors']:
            print(f"  {err['type']} {err['number']} (ID: {err['id']}): {err['error']}")
        
        # Save updated errors
        if not dry_run:
            errors_df = pd.DataFrame(results['errors'])
            errors_df.to_csv(failed_file, index=False, encoding='utf-8-sig')
            print(f"\nUpdated failed_deletions.csv with remaining failures")


if __name__ == '__main__':
    main()



