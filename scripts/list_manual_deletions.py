#!/usr/bin/env python3
"""
Generate list of Zoho IDs that need manual deletion after automated cleanup fails.

Usage:
  python scripts/list_manual_deletions.py --output manual_deletions.csv
"""

import argparse
import csv
from pathlib import Path
from typing import Dict, List

from zoho_sync import ZohoBooks


def parse_transaction_log(log_path: Path, settlements: List[str] = None) -> Dict[str, List[str]]:
    """Parse transaction log and collect all IDs per type."""
    results: Dict[str, List[str]] = {'invoices': [], 'payments': [], 'journals': []}
    if not log_path.exists():
        return results

    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Skip header if present
    start_idx = 1 if lines and lines[0].startswith('timestamp|') else 0

    for line in lines[start_idx:]:
        parts = line.strip().split('|')
        if len(parts) < 9:
            continue
        _, method, typ, endpoint, reference, _amount, status, http_code, obj_id = parts[:9]
        
        # Only count successful POSTs (creates)
        if method != 'POST' or status != 'SUCCESS' or http_code not in ('200', '201'):
            continue
        
        # Filter to settlements if provided
        if settlements and reference not in settlements:
            continue
        
        # Collect IDs
        if typ == 'INVOICE' and obj_id and obj_id != 'N/A':
            results['invoices'].append(obj_id)
        elif typ == 'PAYMENT' and obj_id and obj_id != 'N/A':
            results['payments'].append(obj_id)
        elif typ == 'JOURNAL' and obj_id and obj_id != 'N/A':
            results['journals'].append(obj_id)

    return results


def check_and_delete_remaining(zoho: ZohoBooks, all_ids: Dict[str, List[str]], output_file: Path):
    """Try to delete remaining items and generate list of those that fail."""
    manual_deletions = []
    
    print("Checking and attempting to delete remaining items...")
    
    # Try payments first (they might be blocking invoices)
    print("\n=== PAYMENTS ===")
    for pid in all_ids['payments']:
        try:
            if zoho.delete_payment(pid):
                print(f"  [OK] Deleted payment {pid}")
            else:
                manual_deletions.append({
                    'Type': 'PAYMENT',
                    'ID': pid,
                    'Status': 'Delete failed - requires manual deletion'
                })
                print(f"  [FAIL] Payment {pid} - needs manual deletion")
        except Exception as e:
            manual_deletions.append({
                'Type': 'PAYMENT',
                'ID': pid,
                'Status': f'Error: {str(e)}'
            })
            print(f"  [FAIL] Payment {pid} - Error: {e}")
    
    # Try invoices next
    print("\n=== INVOICES ===")
    for iid in all_ids['invoices']:
        try:
            if zoho.delete_invoice(iid):
                print(f"  [OK] Deleted invoice {iid}")
            else:
                manual_deletions.append({
                    'Type': 'INVOICE',
                    'ID': iid,
                    'Status': 'Delete failed - requires manual deletion'
                })
                print(f"  [FAIL] Invoice {iid} - needs manual deletion")
        except Exception as e:
            manual_deletions.append({
                'Type': 'INVOICE',
                'ID': iid,
                'Status': f'Error: {str(e)}'
            })
            print(f"  [FAIL] Invoice {iid} - Error: {e}")
    
    # Try journals last
    print("\n=== JOURNALS ===")
    for jid in all_ids['journals']:
        try:
            if zoho.delete_journal(jid):
                print(f"  [OK] Deleted journal {jid}")
            else:
                manual_deletions.append({
                    'Type': 'JOURNAL',
                    'ID': jid,
                    'Status': 'Delete failed - requires manual deletion'
                })
                print(f"  [FAIL] Journal {jid} - needs manual deletion")
        except Exception as e:
            manual_deletions.append({
                'Type': 'JOURNAL',
                'ID': jid,
                'Status': f'Error: {str(e)}'
            })
            print(f"  [FAIL] Journal {jid} - Error: {e}")
    
    # Write CSV output
    if manual_deletions:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['Type', 'ID', 'Status'])
            writer.writeheader()
            writer.writerows(manual_deletions)
        
        print(f"\n[SUCCESS] Generated manual deletion list: {output_file}")
        print(f"   Total items requiring manual deletion: {len(manual_deletions)}")
        print(f"\n   Breakdown:")
        breakdown = {}
        for item in manual_deletions:
            breakdown[item['Type']] = breakdown.get(item['Type'], 0) + 1
        for typ, count in breakdown.items():
            print(f"     {typ}: {count}")
    else:
        print("\n[SUCCESS] All items deleted successfully! No manual deletion needed.")
        if output_file.exists():
            output_file.unlink()


def main():
    parser = argparse.ArgumentParser(description='List Zoho IDs requiring manual deletion')
    parser.add_argument('--settlements', nargs='+', help='Specific settlement IDs to check')
    parser.add_argument('--all', action='store_true', help='Check all settlements')
    parser.add_argument('--output', default='manual_deletions.csv', help='Output CSV file')
    parser.add_argument('--log', default=str(Path('logs') / 'zoho_api_transactions.log'), help='Transaction log path')
    args = parser.parse_args()
    
    if not args.all and not args.settlements:
        parser.error("Must specify --all or --settlements")
    
    log_path = Path(args.log)
    output_file = Path(args.output)
    
    # Parse transaction log
    settlements = [str(s) for s in args.settlements] if args.settlements else None
    all_ids = parse_transaction_log(log_path, settlements)
    
    print(f"Found in transaction log:")
    print(f"  Payments: {len(all_ids['payments'])}")
    print(f"  Invoices: {len(all_ids['invoices'])}")
    print(f"  Journals: {len(all_ids['journals'])}")
    
    # Check and attempt deletions
    zoho = ZohoBooks()
    check_and_delete_remaining(zoho, all_ids, output_file)


if __name__ == '__main__':
    main()

