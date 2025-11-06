#!/usr/bin/env python3
"""
Delete all Amazon invoices and payments from Zoho Books.
Payments must be deleted first, then invoices.

Usage:
  python scripts/delete_all_amazon_invoices_payments.py --confirm
"""

import argparse
import time
from pathlib import Path
from typing import List, Dict
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks


def get_all_amazon_payments(zoho: ZohoBooks, customer_id: str = None) -> List[Dict]:
    """Get all Amazon payments from Zoho Books."""
    all_payments = []
    page = 1
    per_page = 200
    
    print("Fetching all Amazon payments from Zoho...")
    
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
            
            # Filter for Amazon payments (by customer name or reference)
            for pay in payments:
                customer_name = pay.get('customer_name', '')
                reference_number = pay.get('reference_number', '')
                
                # Check if it's an Amazon payment
                if 'amazon' in customer_name.lower() or (reference_number and reference_number.isdigit()):
                    all_payments.append({
                        'payment_id': pay.get('payment_id', ''),
                        'payment_number': pay.get('payment_number', ''),
                        'reference_number': reference_number,
                        'customer_name': customer_name,
                        'amount': pay.get('amount', 0),
                        'date': pay.get('date', '')
                    })
            
            # Check for more pages
            page_info = result.get('page_context', {})
            if not page_info.get('has_more_page', False):
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"Error fetching payments: {e}")
            break
    
    print(f"  Found {len(all_payments)} Amazon payments")
    return all_payments


def get_all_amazon_invoices(zoho: ZohoBooks, customer_id: str = None) -> List[Dict]:
    """Get all Amazon invoices from Zoho Books."""
    all_invoices = []
    page = 1
    per_page = 200
    
    print("Fetching all Amazon invoices from Zoho...")
    
    while True:
        try:
            if customer_id:
                result = zoho._api_request('GET', f'invoices?customer_id={customer_id}&per_page={per_page}&page={page}')
            else:
                result = zoho._api_request('GET', f'invoices?per_page={per_page}&page={page}')
            
            if result.get('code') != 0:
                break
            
            invoices = result.get('invoices', [])
            if not invoices:
                break
            
            # Filter for Amazon invoices (by customer name or reference)
            for inv in invoices:
                customer_name = inv.get('customer_name', '')
                reference_number = inv.get('reference_number', '')
                
                # Check if it's an Amazon invoice
                if 'amazon' in customer_name.lower() or (reference_number and reference_number.isdigit()):
                    all_invoices.append({
                        'invoice_id': inv.get('invoice_id', ''),
                        'invoice_number': inv.get('invoice_number', ''),
                        'reference_number': reference_number,
                        'customer_name': customer_name,
                        'total': inv.get('total', 0),
                        'date': inv.get('date', '')
                    })
            
            # Check for more pages
            page_info = result.get('page_context', {})
            if not page_info.get('has_more_page', False):
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"Error fetching invoices: {e}")
            break
    
    print(f"  Found {len(all_invoices)} Amazon invoices")
    return all_invoices


def delete_payments_batch(zoho: ZohoBooks, payments: List[Dict], batch_size: int = 100, dry_run: bool = True) -> Dict:
    """Delete payments in batches."""
    total = len(payments)
    deleted = 0
    failed = 0
    errors = []
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Deleting {total} payments in batches of {batch_size}...")
    
    for i in range(0, total, batch_size):
        batch = payments[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        print(f"\nBatch {batch_num}/{total_batches}: {len(batch)} payments")
        
        for pay in batch:
            payment_id = pay['payment_id']
            payment_num = pay.get('payment_number', 'N/A')
            ref = pay.get('reference_number', 'N/A')
            
            if dry_run:
                print(f"  [DRY RUN] Would delete payment {payment_num} (ID: {payment_id}, Ref: {ref})")
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
                        errors.append({
                            'type': 'PAYMENT',
                            'id': payment_id,
                            'number': payment_num,
                            'error': error_msg
                        })
                        failed += 1
                    
                    time.sleep(0.2)  # Small delay between deletions
                except Exception as e:
                    print(f"  [FAIL] Payment {payment_num} (ID: {payment_id}): {e}")
                    errors.append({
                        'type': 'PAYMENT',
                        'id': payment_id,
                        'number': payment_num,
                        'error': str(e)
                    })
                    failed += 1
        
        # Delay between batches
        if not dry_run and i + batch_size < total:
            print(f"  Waiting 2 seconds before next batch...")
            time.sleep(2)
    
    return {
        'total': total,
        'deleted': deleted,
        'failed': failed,
        'errors': errors
    }


def delete_invoices_batch(zoho: ZohoBooks, invoices: List[Dict], batch_size: int = 200, dry_run: bool = True) -> Dict:
    """Delete invoices in batches."""
    total = len(invoices)
    deleted = 0
    failed = 0
    errors = []
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Deleting {total} invoices in batches of {batch_size}...")
    
    for i in range(0, total, batch_size):
        batch = invoices[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        print(f"\nBatch {batch_num}/{total_batches}: {len(batch)} invoices")
        
        for inv in batch:
            invoice_id = inv['invoice_id']
            invoice_num = inv.get('invoice_number', 'N/A')
            ref = inv.get('reference_number', 'N/A')
            
            if dry_run:
                print(f"  [DRY RUN] Would delete invoice {invoice_num} (ID: {invoice_id}, Ref: {ref})")
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
                    
                    time.sleep(0.2)  # Small delay between deletions
                except Exception as e:
                    print(f"  [FAIL] Invoice {invoice_num} (ID: {invoice_id}): {e}")
                    errors.append({
                        'type': 'INVOICE',
                        'id': invoice_id,
                        'number': invoice_num,
                        'error': str(e)
                    })
                    failed += 1
        
        # Delay between batches
        if not dry_run and i + batch_size < total:
            print(f"  Waiting 2 seconds before next batch...")
            time.sleep(2)
    
    return {
        'total': total,
        'deleted': deleted,
        'failed': failed,
        'errors': errors
    }


def main():
    parser = argparse.ArgumentParser(description='Delete all Amazon invoices and payments from Zoho')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (default is dry-run)')
    parser.add_argument('--test-last-100', action='store_true', help='Test with last 100 payments only')
    args = parser.parse_args()
    
    dry_run = not args.confirm
    
    print("=" * 80)
    if dry_run:
        print("DRY RUN - No deletions will be performed")
    else:
        print("LIVE MODE - DELETIONS WILL BE PERFORMED")
    print("=" * 80)
    
    zoho = ZohoBooks()
    
    # Get Amazon customer ID
    customer_id = zoho.get_customer_id("Amazon.ca")
    if customer_id:
        print(f"\nAmazon.ca customer ID: {customer_id}")
    else:
        print("\nWarning: Amazon.ca customer not found - will search all payments/invoices")
    
    # STEP 1: Delete Payments First
    print("\n" + "=" * 80)
    print("STEP 1: DELETE PAYMENTS")
    print("=" * 80)
    
    all_payments = get_all_amazon_payments(zoho, customer_id)
    
    if not all_payments:
        print("\nNo Amazon payments found.")
    else:
        # Test with last 100 if requested
        if args.test_last_100:
            print("\n[TEST MODE] Testing with last 100 payments only...")
            all_payments = all_payments[-100:]
        
        payment_results = delete_payments_batch(zoho, all_payments, batch_size=100, dry_run=dry_run)
        
        print("\n" + "-" * 80)
        print("PAYMENT DELETION SUMMARY")
        print("-" * 80)
        print(f"Total: {payment_results['total']}")
        print(f"Deleted: {payment_results['deleted']}")
        print(f"Failed: {payment_results['failed']}")
        
        if payment_results['errors']:
            print(f"\nFailed deletions ({len(payment_results['errors'])}):")
            for err in payment_results['errors'][:10]:  # Show first 10
                print(f"  {err['type']} {err['number']} (ID: {err['id']}): {err['error']}")
            if len(payment_results['errors']) > 10:
                print(f"  ... and {len(payment_results['errors']) - 10} more")
    
    # STEP 2: Delete Invoices (only after payments are deleted)
    if not args.test_last_100:
        print("\n" + "=" * 80)
        print("STEP 2: DELETE INVOICES")
        print("=" * 80)
        
        all_invoices = get_all_amazon_invoices(zoho, customer_id)
        
        if not all_invoices:
            print("\nNo Amazon invoices found.")
        else:
            invoice_results = delete_invoices_batch(zoho, all_invoices, batch_size=200, dry_run=dry_run)
            
            print("\n" + "-" * 80)
            print("INVOICE DELETION SUMMARY")
            print("-" * 80)
            print(f"Total: {invoice_results['total']}")
            print(f"Deleted: {invoice_results['deleted']}")
            print(f"Failed: {invoice_results['failed']}")
            
            if invoice_results['errors']:
                print(f"\nFailed deletions ({len(invoice_results['errors'])}):")
                for err in invoice_results['errors'][:10]:  # Show first 10
                    print(f"  {err['type']} {err['number']} (ID: {err['id']}): {err['error']}")
                if len(invoice_results['errors']) > 10:
                    print(f"  ... and {len(invoice_results['errors']) - 10} more")
            
            # Save failed deletions to file
            if invoice_results['errors']:
                import pandas as pd
                errors_df = pd.DataFrame(invoice_results['errors'])
                from paths import get_sharepoint_base
                error_file = get_sharepoint_base() / "failed_deletions.csv"
                errors_df.to_csv(error_file, index=False, encoding='utf-8-sig')
                print(f"\nFailed deletions saved to: {error_file}")
    
    print("\n" + "=" * 80)
    if dry_run:
        print("DRY RUN COMPLETE - No changes made")
        print("\nTo actually delete, run with --confirm flag:")
        print("  python scripts/delete_all_amazon_invoices_payments.py --confirm")
    else:
        print("DELETION COMPLETE")
        print("\nNext steps:")
        print("  1. Verify deletions in Zoho Books")
        print("  2. Repost invoices and payments using sync_settlement.py")


if __name__ == '__main__':
    main()



