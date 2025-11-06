#!/usr/bin/env python3
"""
Generate final summary from transaction log and posting results.

Usage:
  python scripts/generate_summary_from_log.py --output posting_status_summary.csv
"""

import argparse
import csv
from pathlib import Path
from collections import defaultdict
import pandas as pd


def parse_transaction_log(log_file: Path) -> dict:
    """Parse transaction log to count what was posted."""
    posted = defaultdict(lambda: {'journals': 0, 'invoices': 0, 'payments': 0})
    
    if not log_file.exists():
        return posted
    
    with open(log_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='|')
        for row in reader:
            if row.get('status') == 'SUCCESS' and row.get('http_code') == '201':
                ref = row.get('reference', '')
                trans_type = row.get('type', '')
                
                if ref and ref != 'N/A':
                    if trans_type == 'JOURNAL':
                        posted[ref]['journals'] += 1
                    elif trans_type == 'INVOICE':
                        posted[ref]['invoices'] += 1
                    elif trans_type == 'PAYMENT':
                        posted[ref]['payments'] += 1
    
    return posted


def find_local_counts() -> dict:
    """Find local file counts for each settlement."""
    output_dir = Path("outputs")
    counts = {}
    
    if not output_dir.exists():
        return counts
    
    for item in output_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            settlement_id = item.name
            counts[settlement_id] = {
                'journal_lines': 0,
                'invoice_count': 0,
                'payment_count': 0
            }
            
            journal_file = item / f"Journal_{settlement_id}.csv"
            invoice_file = item / f"Invoice_{settlement_id}.csv"
            payment_file = item / f"Payment_{settlement_id}.csv"
            
            if journal_file.exists():
                try:
                    df = pd.read_csv(journal_file)
                    counts[settlement_id]['journal_lines'] = len(df)
                except:
                    pass
            
            if invoice_file.exists():
                try:
                    df = pd.read_csv(invoice_file)
                    if 'Invoice Number' in df.columns:
                        counts[settlement_id]['invoice_count'] = df['Invoice Number'].nunique()
                    else:
                        counts[settlement_id]['invoice_count'] = len(df)
                except:
                    pass
            
            if payment_file.exists():
                try:
                    df = pd.read_csv(payment_file)
                    counts[settlement_id]['payment_count'] = len(df)
                except:
                    pass
    
    return counts


def main():
    parser = argparse.ArgumentParser(description='Generate posting status summary from logs')
    parser.add_argument('--log', default='logs/zoho_api_transactions.log', help='Transaction log file')
    parser.add_argument('--output', default='posting_status_summary.csv', help='Output CSV file')
    args = parser.parse_args()
    
    log_file = Path(args.log)
    output_file = Path(args.output)
    
    print("=" * 80)
    print("GENERATING POSTING STATUS SUMMARY")
    print("=" * 80)
    
    # Parse transaction log
    posted = parse_transaction_log(log_file)
    
    # Get local counts
    local_counts = find_local_counts()
    
    # Combine data
    results = []
    
    for settlement_id in sorted(local_counts.keys()):
        local = local_counts[settlement_id]
        posted_data = posted.get(settlement_id, {})
        
        journal_posted = posted_data.get('journals', 0)
        invoices_posted = posted_data.get('invoices', 0)
        payments_posted = posted_data.get('payments', 0)
        
        journal_status = 'POSTED' if journal_posted > 0 else 'NOT_POSTED'
        invoice_status = 'COMPLETE' if invoices_posted >= local['invoice_count'] else f'PARTIAL ({invoices_posted}/{local["invoice_count"]})' if invoices_posted > 0 else 'NOT_POSTED'
        payment_status = 'COMPLETE' if payments_posted >= local['payment_count'] else f'PARTIAL ({payments_posted}/{local["payment_count"]})' if payments_posted > 0 else 'NOT_POSTED'
        
        results.append({
            'Settlement_ID': settlement_id,
            'Journal_Local_Lines': local['journal_lines'],
            'Journal_Posted': 'YES' if journal_posted > 0 else 'NO',
            'Journal_Status': journal_status,
            'Invoice_Local_Count': local['invoice_count'],
            'Invoice_Posted_Count': invoices_posted,
            'Invoice_Missing': max(0, local['invoice_count'] - invoices_posted),
            'Invoice_Status': invoice_status,
            'Payment_Local_Count': local['payment_count'],
            'Payment_Posted_Count': payments_posted,
            'Payment_Missing': max(0, local['payment_count'] - payments_posted),
            'Payment_Status': payment_status
        })
        
        print(f"\n{settlement_id}:")
        print(f"  Journal: {journal_status}")
        print(f"  Invoices: {invoice_status}")
        print(f"  Payments: {payment_status}")
    
    # Write CSV
    if results:
        df = pd.DataFrame(results)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print("\n" + "=" * 80)
        print("SUMMARY TOTALS")
        print("=" * 80)
        
        total_settlements = len(results)
        journals_posted = sum(1 for r in results if r['Journal_Posted'] == 'YES')
        invoices_complete = sum(1 for r in results if r['Invoice_Status'] == 'COMPLETE')
        payments_complete = sum(1 for r in results if r['Payment_Status'] == 'COMPLETE')
        
        total_invoices_missing = sum(r['Invoice_Missing'] for r in results)
        total_payments_missing = sum(r['Payment_Missing'] for r in results)
        
        print(f"Total Settlements: {total_settlements}")
        print(f"Journals Posted: {journals_posted}/{total_settlements}")
        print(f"Invoices Complete: {invoices_complete}/{total_settlements}")
        print(f"Payments Complete: {payments_complete}/{total_settlements}")
        print(f"Total Invoices Missing: {total_invoices_missing}")
        print(f"Total Payments Missing: {total_payments_missing}")
        
        print(f"\nDetailed report saved to: {output_file}")


if __name__ == '__main__':
    main()



