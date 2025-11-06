#!/usr/bin/env python3
"""
Reset Zoho Books for Amazon integration: delete Payments → Invoices → Journals.

Sources deletions from logs/zoho_api_transactions.log or an explicit list.

Usage:
  python scripts/reset_zoho.py --settlements 23874397121 24288684721 --dry-run
  python scripts/reset_zoho.py --all --confirm
"""

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

from zoho_sync import ZohoBooks


def parse_transaction_log(log_path: Path, settlements: List[str] = None) -> Dict[str, Dict[str, List[str]]]:
    """Parse transaction log and collect IDs per type by settlement reference.

    Returns: { settlement_id: { 'invoices': [ids], 'payments': [ids], 'journals': [ids] } }
    """
    results: Dict[str, Dict[str, List[str]]] = {}
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
        if status != 'SUCCESS' or http_code not in ('200', '201'):
            continue
        # Only consider create (POST) or successful GETs that returned entities? We need created IDs only
        if method not in ('POST', 'DELETE'):
            continue
        # Filter to settlements of interest if provided
        if settlements and reference not in settlements:
            continue

        bucket = None
        if typ == 'INVOICE' and method == 'POST':
            bucket = 'invoices'
        elif typ == 'PAYMENT' and method == 'POST':
            bucket = 'payments'
        elif typ == 'JOURNAL' and method == 'POST':
            bucket = 'journals'
        else:
            continue

        if reference not in results:
            results[reference] = {'invoices': [], 'payments': [], 'journals': []}
        results[reference][bucket].append(obj_id)

    return results


def delete_for_settlement(zoho: ZohoBooks, obj_ids: Dict[str, List[str]], dry_run: bool = True) -> Tuple[int, int, int]:
    """Delete in the correct order. Returns counts deleted (payments, invoices, journals)."""
    deleted_payments = deleted_invoices = deleted_journals = 0

    # Payments first
    for pid in obj_ids.get('payments', []):
        if dry_run:
            print(f"[DRY RUN] Would delete payment {pid}")
        else:
            if zoho.delete_payment(pid):
                deleted_payments += 1

    # Invoices next
    for iid in obj_ids.get('invoices', []):
        if dry_run:
            print(f"[DRY RUN] Would delete invoice {iid}")
        else:
            if zoho.delete_invoice(iid):
                deleted_invoices += 1

    # Journals last
    for jid in obj_ids.get('journals', []):
        if dry_run:
            print(f"[DRY RUN] Would delete journal {jid}")
        else:
            if zoho.delete_journal(jid):
                deleted_journals += 1

    return deleted_payments, deleted_invoices, deleted_journals


def main():
    parser = argparse.ArgumentParser(description='Reset Zoho Books (Amazon) by deleting payments, invoices, and journals.')
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--settlements', nargs='+', help='Specific settlement IDs to reset')
    scope.add_argument('--all', action='store_true', help='Reset all settlements found in the transaction log')
    parser.add_argument('--confirm', action='store_true', help='Actually perform deletions (default is dry-run)')
    parser.add_argument('--log', default=str(Path('logs') / 'zoho_api_transactions.log'), help='Path to transaction log')
    args = parser.parse_args()

    dry_run = not args.confirm
    log_path = Path(args.log)

    # Determine settlements
    settlements: List[str]
    if args.settlements:
        settlements = [str(s) for s in args.settlements]
    else:
        settlements = None  # parse all references found

    # Parse log
    per_settlement = parse_transaction_log(log_path, settlements)
    if args.all and not per_settlement:
        # Parse entire log without filtering
        per_settlement = parse_transaction_log(log_path, settlements=None)

    if not per_settlement:
        print("No created invoices/payments/journals found in log for given scope.")
        return

    print("Targets to reset:")
    for sid, buckets in per_settlement.items():
        print(f"  Settlement {sid}: {len(buckets['payments'])} payments, {len(buckets['invoices'])} invoices, {len(buckets['journals'])} journals")

    zoho = ZohoBooks()

    total_p = total_i = total_j = 0
    for sid, buckets in per_settlement.items():
        p, i, j = delete_for_settlement(zoho, buckets, dry_run=dry_run)
        total_p += p
        total_i += i
        total_j += j

    if dry_run:
        print("\nDRY RUN complete. Re-run with --confirm to execute deletions.")
    else:
        print(f"\nDeleted: {total_p} payments, {total_i} invoices, {total_j} journals.")


if __name__ == '__main__':
    main()





