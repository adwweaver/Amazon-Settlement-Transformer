#!/usr/bin/env python3
"""
Post remaining payments for all settlements, checking invoice balances first.

This script will:
1. Find all settlements with payment files
2. Check invoice balances before posting
3. Skip already-paid invoices
4. Post payments for unpaid invoices
5. Generate a summary report

Usage:
    python scripts/post_remaining_payments.py --confirm
"""

import argparse
import time
import logging
from pathlib import Path
import pandas as pd
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from sync_settlement import post_settlement_complete

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_settlements_with_payments():
    """Find all settlements that have payment files"""
    output_dir = Path("outputs")
    settlements = []
    
    if not output_dir.exists():
        return settlements
    
    for item in output_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            payment_file = item / f"Payment_{item.name}.csv"
            if payment_file.exists():
                settlements.append(item.name)
    
    return sorted(settlements)


def main():
    parser = argparse.ArgumentParser(description='Post remaining payments for all settlements')
    parser.add_argument('--confirm', action='store_true', help='Actually post (default is dry-run)')
    parser.add_argument('--settlement', help='Process only this settlement ID')
    args = parser.parse_args()
    
    dry_run = not args.confirm
    
    settlements = find_settlements_with_payments()
    
    if args.settlement:
        if args.settlement in settlements:
            settlements = [args.settlement]
        else:
            print(f"Error: Settlement {args.settlement} not found")
            return
    
    if not settlements:
        print("No settlements with payment files found.")
        return
    
    print("="*80)
    print(f"POSTING REMAINING PAYMENTS ({'DRY RUN' if dry_run else 'LIVE MODE'})")
    print("="*80)
    print(f"Settlements: {len(settlements)}")
    print(f"Mode: {'DRY RUN - No data will be posted' if dry_run else 'LIVE - Data will be posted'}")
    print("="*80)
    
    zoho = ZohoBooks()
    
    all_results = []
    total_posted = 0
    total_skipped = 0
    total_failed = 0
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"\n{'='*80}")
        print(f"Settlement {i}/{len(settlements)}: {settlement_id}")
        print(f"{'='*80}")
        
        # Post only payments (skip journals and invoices)
        results = post_settlement_complete(
            settlement_id,
            post_journal=False,
            post_invoices=False,
            post_payments=True,
            dry_run=dry_run,
            override=False
        )
        
        payment_count = results['payments']['count']
        total_posted += payment_count
        
        if results['payments']['error']:
            total_failed += 1
        
        all_results.append({
            'settlement_id': settlement_id,
            'payments_posted': payment_count,
            'status': 'SUCCESS' if payment_count > 0 else 'FAILED',
            'error': results['payments'].get('error', '')
        })
        
        print(f"\n[SUMMARY] Settlement {settlement_id}: {payment_count} payment(s) posted")
        
        # Delay between settlements to avoid rate limits
        if i < len(settlements):
            print(f"[PAUSE] Waiting 10 seconds before next settlement...")
            time.sleep(10)
    
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Total Settlements Processed: {len(settlements)}")
    print(f"Total Payments Posted: {total_posted}")
    print(f"Successful Settlements: {len(settlements) - total_failed}")
    print(f"Failed Settlements: {total_failed}")
    print("="*80)
    
    # Save summary to CSV
    summary_df = pd.DataFrame(all_results)
    summary_file = Path("outputs") / f"Payment_Posting_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"\nSummary saved to: {summary_file}")


if __name__ == "__main__":
    main()

