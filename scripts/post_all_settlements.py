#!/usr/bin/env python3
"""
Post all settlements: journals, missing invoices, and missing payments.

Usage:
  python scripts/post_all_settlements.py --dry-run
  python scripts/post_all_settlements.py --confirm
"""

import argparse
import time
from pathlib import Path
import pandas as pd
from datetime import datetime

from zoho_sync import ZohoBooks
from sync_settlement import post_settlement_complete, load_sku_mapping
from validate_settlement import SettlementValidator


def find_local_settlements() -> list:
    """Find all settlement IDs from local output directories."""
    output_dir = Path("outputs")
    settlements = []
    
    if not output_dir.exists():
        return settlements
    
    for item in output_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            settlements.append(item.name)
    
    return sorted(settlements)


def check_local_files(settlement_id: str) -> dict:
    """Check what local invoices/payments exist (since we deleted everything, post all)."""
    result = {
        'has_invoices': False,
        'has_payments': False,
        'invoice_count': 0,
        'payment_count': 0
    }
    
    # Read local files
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    
    if invoice_file.exists():
        try:
            df_inv = pd.read_csv(invoice_file)
            if 'Invoice Number' in df_inv.columns:
                result['invoice_count'] = df_inv['Invoice Number'].nunique()
                result['has_invoices'] = result['invoice_count'] > 0
        except Exception as e:
            print(f"  Warning: Could not read invoice file: {e}")
    
    if payment_file.exists():
        try:
            df_pay = pd.read_csv(payment_file)
            result['payment_count'] = len(df_pay)
            result['has_payments'] = result['payment_count'] > 0
        except Exception as e:
            print(f"  Warning: Could not read payment file: {e}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Post all settlements to Zoho Books')
    parser.add_argument('--confirm', action='store_true', help='Actually post (default is dry-run)')
    parser.add_argument('--output', default='posting_summary.csv', help='Summary output CSV')
    args = parser.parse_args()
    
    dry_run = not args.confirm
    output_file = Path(args.output)
    
    settlements = find_local_settlements()
    
    if not settlements:
        print("No local settlements found.")
        return
    
    print("=" * 80)
    print(f"POSTING ALL SETTLEMENTS ({'DRY RUN' if dry_run else 'LIVE MODE'})")
    print("=" * 80)
    print(f"Settlements: {len(settlements)}")
    print(f"Mode: {'DRY RUN - No data will be posted' if dry_run else 'LIVE - Data will be posted'}")
    print("=" * 80)
    
    zoho = ZohoBooks()
    sku_mapping = load_sku_mapping()
    validator = SettlementValidator()
    
    all_results = []
    
    for settlement_id in settlements:
        print(f"\n{'='*80}")
        print(f"Settlement: {settlement_id}")
        print(f"{'='*80}")
        
        # Validate first (check for blocking errors only)
        only_warnings = False
        has_blocking_errors = False
        clearing_mismatch_only = False
        try:
            val_result = validator.validate_settlement(settlement_id)
            validator.write_error_report(settlement_id, val_result)
            
            # Check for truly blocking errors (journal imbalance, unmapped GL)
            # Clearing mismatches and SKU warnings can be overridden
            errors = val_result.get('errors', [])
            blocking_errors = [
                err for err in errors 
                if 'Journal out of balance' in err or 'Unmapped GL' in err
            ]
            has_blocking_errors = len(blocking_errors) > 0
            only_warnings = not has_blocking_errors and len(val_result.get('warnings', [])) > 0
            clearing_mismatch_only = not has_blocking_errors and any('Clearing vs' in err for err in errors)
            
            if has_blocking_errors and not dry_run:
                print(f"  [SKIP] Validation failed - cannot proceed (blocking errors)")
                print(f"    Blocking Errors: {blocking_errors}")
                all_results.append({
                    'settlement_id': settlement_id,
                    'journal_status': 'SKIPPED (validation failed)',
                    'invoice_status': 'SKIPPED',
                    'payment_status': 'SKIPPED',
                    'journal_id': '',
                    'invoices_posted': 0,
                    'payments_posted': 0,
                    'errors': '; '.join(blocking_errors)
                })
                continue
            elif clearing_mismatch_only or only_warnings:
                print(f"  [INFO] Validation issues (will override): {len(errors) + len(val_result.get('warnings', []))} issue(s)")
                if clearing_mismatch_only:
                    print(f"    Clearing mismatch detected (non-blocking)")
                # Continue with override
        except Exception as e:
            print(f"  [WARNING] Validation error (continuing anyway): {e}")
        
        # Check local files (post all since we just deleted everything)
        local_files = check_local_files(settlement_id)
        
        # Post journal (always needed)
        print(f"\n  [1] JOURNAL:")
        journal_status = "EXISTS"
        journal_id = None
        
        try:
            existing_journal = zoho.check_existing_journal(settlement_id)
            if existing_journal:
                print(f"    Journal already exists (ID: {existing_journal})")
                journal_id = existing_journal
            else:
                print(f"    Posting journal...")
                # Use sync_settlement function
                results = post_settlement_complete(
                    settlement_id,
                    post_journal=True,
                    post_invoices=False,
                    post_payments=False,
                    dry_run=dry_run,
                    override=(only_warnings or clearing_mismatch_only) if not dry_run else False
                )
                
                if results['journal']['posted']:
                    journal_status = "POSTED"
                    journal_id = results['journal'].get('id')
                    print(f"    [SUCCESS] Journal posted (ID: {journal_id})")
                else:
                    journal_status = f"FAILED: {results['journal'].get('error', 'Unknown error')}"
                    print(f"    [FAILED] {journal_status}")
        except Exception as e:
            journal_status = f"ERROR: {str(e)}"
            print(f"    [ERROR] {journal_status}")
        
        # Post invoices (post all since we just deleted everything)
        print(f"\n  [2] INVOICES:")
        invoice_count = 0
        invoice_status = "NONE_TO_POST"
        invoice_map_result = {}
        
        if local_files['has_invoices']:
            print(f"    {local_files['invoice_count']} invoice(s) to post")
            
            if not dry_run:
                results = post_settlement_complete(
                    settlement_id,
                    post_journal=False,
                    post_invoices=True,
                    post_payments=False,
                    dry_run=False,
                    override=only_warnings or clearing_mismatch_only
                )
                
                if results['invoices']['posted']:
                    invoice_count = results['invoices']['count']
                    invoice_map_result = results.get('invoice_map', {})
                    invoice_status = f"POSTED ({invoice_count})"
                    print(f"    [SUCCESS] {invoice_count} invoice(s) posted")
                    
                    # Show invoice number tracking
                    if invoice_map_result:
                        print(f"    [TRACKING] Invoice numbers mapped:")
                        for inv_num, inv_id in list(invoice_map_result.items())[:5]:  # Show first 5
                            print(f"      {inv_num} -> Zoho ID: {inv_id}")
                        if len(invoice_map_result) > 5:
                            print(f"      ... and {len(invoice_map_result) - 5} more")
                else:
                    invoice_status = f"FAILED: {results['invoices'].get('error', 'Unknown error')}"
                    print(f"    [FAILED] {invoice_status}")
            else:
                invoice_status = f"WOULD_POST ({local_files['invoice_count']})"
                print(f"    [DRY RUN] Would post {local_files['invoice_count']} invoice(s)")
        else:
            print(f"    No invoices to post")
        
        # Post payments (post all that correspond to posted invoices)
        print(f"\n  [3] PAYMENTS:")
        payment_count = 0
        payment_status = "NONE_TO_POST"
        
        if local_files['has_payments']:
            print(f"    {local_files['payment_count']} payment(s) to post")
            
            if not dry_run:
                # Post payments (they will link to invoices via invoice_map)
                results = post_settlement_complete(
                    settlement_id,
                    post_journal=False,
                    post_invoices=False,
                    post_payments=True,
                    dry_run=False,
                    override=only_warnings or clearing_mismatch_only
                )
                
                if results['payments']['posted']:
                    payment_count = results['payments']['count']
                    payment_status = f"POSTED ({payment_count})"
                    print(f"    [SUCCESS] {payment_count} payment(s) posted")
                    
                    # Verify payment alignment with invoices
                    if invoice_map_result:
                        print(f"    [VERIFY] Payments linked to {len(invoice_map_result)} invoice(s)")
                else:
                    payment_status = f"FAILED: {results['payments'].get('error', 'Unknown error')}"
                    print(f"    [FAILED] {payment_status}")
            else:
                payment_status = f"WOULD_POST ({local_files['payment_count']})"
                print(f"    [DRY RUN] Would post {local_files['payment_count']} payment(s)")
        else:
            print(f"    No payments to post")
        
        all_results.append({
            'settlement_id': settlement_id,
            'journal_status': journal_status,
            'invoice_status': invoice_status,
            'payment_status': payment_status,
            'journal_id': str(journal_id) if journal_id else '',
            'invoices_posted': invoice_count,
            'payments_posted': payment_count,
            'errors': ''
        })
        
        # Longer delay to avoid rate limits (especially after deletions)
        if not dry_run:
            time.sleep(10)  # Longer delay after posting to allow rate limits to reset
    
    # Generate summary CSV
    if all_results:
        df = pd.DataFrame(all_results)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Results saved to: {output_file}")
        print(f"\nTotals:")
        print(f"  Journals: {sum(1 for r in all_results if 'POSTED' in r['journal_status'] or 'EXISTS' in r['journal_status'])} posted/existing")
        print(f"  Invoices: {sum(r['invoices_posted'] for r in all_results)} posted")
        print(f"  Payments: {sum(r['payments_posted'] for r in all_results)} posted")
        
        if dry_run:
            print(f"\n[DRY RUN MODE] - No data was posted")
            print(f"Re-run with --confirm to actually post")
        else:
            print(f"\n[COMPLETE] - All settlements processed")


if __name__ == '__main__':
    main()

