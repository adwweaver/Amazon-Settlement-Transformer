#!/usr/bin/env python3
"""
Analyze tracking map to identify gaps and items that need action.
Provides clear breakdown of invoices/payments to create/edit/delete.

Usage:
  python scripts/analyze_tracking_gaps.py --output action_items.csv
"""

import argparse
from pathlib import Path
import pandas as pd
from typing import Dict, List
from collections import defaultdict

from zoho_sync import ZohoBooks


def get_zoho_invoices_by_settlement(zoho: ZohoBooks, settlement_id: str) -> Dict[str, str]:
    """Get all invoices from Zoho for a settlement, return invoice_number -> invoice_id map"""
    invoice_map = {}
    
    try:
        result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            invoices = result.get('invoices', [])
            for inv in invoices:
                invoice_id = inv.get('invoice_id', '')
                invoice_number = inv.get('invoice_number', '')
                reference_number = inv.get('reference_number', '')
                
                # Map by invoice number
                if invoice_number and invoice_id:
                    invoice_map[invoice_number] = invoice_id
                # Also map by reference number if different
                if reference_number and reference_number != invoice_number:
                    invoice_map[reference_number] = invoice_id
    except Exception as e:
        print(f"  Error querying Zoho invoices: {e}")
    
    return invoice_map


def get_zoho_payments_by_settlement(zoho: ZohoBooks, settlement_id: str) -> Dict[str, str]:
    """Get all payments from Zoho for a settlement, return reference_number -> payment_id map"""
    payment_map = {}
    
    try:
        result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            payments = result.get('customerpayments', [])
            for pay in payments:
                payment_id = pay.get('payment_id', '')
                reference_number = pay.get('reference_number', '')
                invoice_number = pay.get('invoice_number', '')  # Payment may have invoice number
                
                # Map by reference number
                if reference_number and payment_id:
                    payment_map[reference_number] = payment_id
                # Also map by invoice number if different
                if invoice_number and invoice_number != reference_number:
                    payment_map[invoice_number] = payment_id
    except Exception as e:
        print(f"  Error querying Zoho payments: {e}")
    
    return payment_map


def get_local_invoices(settlement_id: str) -> List[Dict]:
    """Get local invoices from CSV file"""
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    invoices = []
    
    if invoice_file.exists():
        try:
            df = pd.read_csv(invoice_file)
            if 'Invoice Number' in df.columns:
                for inv_num, group in df.groupby('Invoice Number'):
                    first_row = group.iloc[0]
                    invoices.append({
                        'invoice_number': str(inv_num),
                        'reference_number': str(first_row.get('Reference Number', settlement_id)),
                        'amount': float(group['Invoice Line Amount'].sum()),
                        'line_count': len(group),
                        'date': str(first_row.get('Invoice Date', ''))
                    })
        except Exception as e:
            print(f"  Error reading local invoice file: {e}")
    
    return invoices


def get_local_payments(settlement_id: str) -> List[Dict]:
    """Get local payments from CSV file"""
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    payments = []
    
    if payment_file.exists():
        try:
            df = pd.read_csv(payment_file)
            if 'Invoice Number' in df.columns:
                for idx, row in df.iterrows():
                    payments.append({
                        'invoice_number': str(row['Invoice Number']),
                        'reference_number': str(row.get('Reference Number', settlement_id)),
                        'amount': float(row.get('Payment Amount', 0)),
                        'date': str(row.get('Payment Date', ''))
                    })
        except Exception as e:
            print(f"  Error reading local payment file: {e}")
    
    return payments


def analyze_settlement(zoho: ZohoBooks, settlement_id: str) -> Dict:
    """Analyze a single settlement for gaps"""
    print(f"  Analyzing settlement {settlement_id}...")
    
    # Get data from both sources
    zoho_invoices = get_zoho_invoices_by_settlement(zoho, settlement_id)
    zoho_payments = get_zoho_payments_by_settlement(zoho, settlement_id)
    local_invoices = get_local_invoices(settlement_id)
    local_payments = get_local_payments(settlement_id)
    
    # Build comparison
    local_invoice_nums = {inv['invoice_number'] for inv in local_invoices}
    zoho_invoice_nums = set(zoho_invoices.keys())
    
    # Identify gaps
    missing_in_zoho = local_invoice_nums - zoho_invoice_nums
    extra_in_zoho = zoho_invoice_nums - local_invoice_nums
    matched_invoices = local_invoice_nums & zoho_invoice_nums
    
    # For payments, match by invoice number
    local_payment_refs = {pay['invoice_number'] for pay in local_payments}
    zoho_payment_refs = set(zoho_payments.keys())
    
    missing_payments = local_payment_refs - zoho_payment_refs
    extra_payments = zoho_payment_refs - local_payment_refs
    matched_payments = local_payment_refs & zoho_payment_refs
    
    return {
        'settlement_id': settlement_id,
        'local_invoices': local_invoices,
        'zoho_invoices': zoho_invoices,
        'local_payments': local_payments,
        'zoho_payments': zoho_payments,
        'missing_in_zoho_invoices': missing_in_zoho,
        'extra_in_zoho_invoices': extra_in_zoho,
        'matched_invoices': matched_invoices,
        'missing_in_zoho_payments': missing_payments,
        'extra_in_zoho_payments': extra_payments,
        'matched_payments': matched_payments
    }


def create_action_items(analysis_results: List[Dict], output_file: Path):
    """Create CSV with action items"""
    action_items = []
    
    for result in analysis_results:
        settlement_id = result['settlement_id']
        
        # Missing invoices (need to CREATE in Zoho)
        for inv_num in result['missing_in_zoho_invoices']:
            inv_data = next((inv for inv in result['local_invoices'] if inv['invoice_number'] == inv_num), None)
            if inv_data:
                action_items.append({
                    'settlement_id': settlement_id,
                    'record_type': 'INVOICE',
                    'action': 'CREATE',
                    'local_identifier': inv_num,
                    'zoho_id': '',
                    'amount': inv_data['amount'],
                    'line_count': inv_data['line_count'],
                    'date': inv_data['date'],
                    'notes': f'Invoice {inv_num} exists locally but not in Zoho'
                })
        
        # Extra invoices in Zoho (need to DELETE or VERIFY)
        for inv_num in result['extra_in_zoho_invoices']:
            zoho_id = result['zoho_invoices'].get(inv_num, '')
            action_items.append({
                'settlement_id': settlement_id,
                'record_type': 'INVOICE',
                'action': 'VERIFY/DELETE',
                'local_identifier': inv_num,
                'zoho_id': zoho_id,
                'amount': '',
                'line_count': '',
                'date': '',
                'notes': f'Invoice {inv_num} exists in Zoho but not in local files - verify if should exist'
            })
        
        # Matched invoices (need to UPDATE tracking)
        for inv_num in result['matched_invoices']:
            zoho_id = result['zoho_invoices'].get(inv_num, '')
            inv_data = next((inv for inv in result['local_invoices'] if inv['invoice_number'] == inv_num), None)
            action_items.append({
                'settlement_id': settlement_id,
                'record_type': 'INVOICE',
                'action': 'UPDATE_TRACKING',
                'local_identifier': inv_num,
                'zoho_id': zoho_id,
                'amount': inv_data['amount'] if inv_data else '',
                'line_count': inv_data['line_count'] if inv_data else '',
                'date': inv_data['date'] if inv_data else '',
                'notes': f'Invoice {inv_num} exists in both - update tracking with Zoho ID {zoho_id}'
            })
        
        # Missing payments (need to CREATE in Zoho)
        for inv_num in result['missing_in_zoho_payments']:
            pay_data = next((pay for pay in result['local_payments'] if pay['invoice_number'] == inv_num), None)
            if pay_data:
                action_items.append({
                    'settlement_id': settlement_id,
                    'record_type': 'PAYMENT',
                    'action': 'CREATE',
                    'local_identifier': inv_num,
                    'zoho_id': '',
                    'amount': pay_data['amount'],
                    'line_count': '',
                    'date': pay_data['date'],
                    'notes': f'Payment for invoice {inv_num} exists locally but not in Zoho'
                })
        
        # Matched payments (need to UPDATE tracking)
        for inv_num in result['matched_payments']:
            zoho_id = result['zoho_payments'].get(inv_num, '')
            pay_data = next((pay for pay in result['local_payments'] if pay['invoice_number'] == inv_num), None)
            action_items.append({
                'settlement_id': settlement_id,
                'record_type': 'PAYMENT',
                'action': 'UPDATE_TRACKING',
                'local_identifier': inv_num,
                'zoho_id': zoho_id,
                'amount': pay_data['amount'] if pay_data else '',
                'line_count': '',
                'date': pay_data['date'] if pay_data else '',
                'notes': f'Payment for invoice {inv_num} exists in both - update tracking with Zoho ID {zoho_id}'
            })
    
    # Write CSV
    if action_items:
        df = pd.DataFrame(action_items)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print("\n" + "=" * 80)
        print("ACTION ITEMS SUMMARY")
        print("=" * 80)
        
        summary = df.groupby(['record_type', 'action']).size().unstack(fill_value=0)
        print("\nBreakdown:")
        print(summary)
        
        print(f"\n[SUCCESS] Action items saved to: {output_file}")
        
        # Detailed breakdown
        print("\n" + "=" * 80)
        print("DETAILED BREAKDOWN")
        print("=" * 80)
        
        create_count = len(df[df['action'] == 'CREATE'])
        update_count = len(df[df['action'] == 'UPDATE_TRACKING'])
        verify_count = len(df[df['action'] == 'VERIFY/DELETE'])
        
        if create_count > 0:
            print(f"\n[CREATE] {create_count} items need to be created in Zoho:")
            create_items = df[df['action'] == 'CREATE']
            for record_type in ['INVOICE', 'PAYMENT']:
                items = create_items[create_items['record_type'] == record_type]
                if len(items) > 0:
                    total_amount = items['amount'].sum() if 'amount' in items.columns else 0
                    print(f"  {record_type}: {len(items)} items (${total_amount:,.2f} total)")
        
        if update_count > 0:
            print(f"\n[UPDATE_TRACKING] {update_count} items need tracking updated:")
            print("  These exist in both local and Zoho - need to manually update zoho_tracking.csv")
            print("  with Zoho IDs provided in the action_items.csv file")
        
        if verify_count > 0:
            print(f"\n[VERIFY/DELETE] {verify_count} items in Zoho but not in local files:")
            print("  These may need to be deleted if they shouldn't exist")
    else:
        print("[SUCCESS] No action items needed - everything is in sync!")


def main():
    from paths import get_action_items_path
    parser = argparse.ArgumentParser(description='Analyze tracking gaps and generate action items')
    parser.add_argument('--output', default=None, help='Output CSV file (defaults to SharePoint location)')
    args = parser.parse_args()
    
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = get_action_items_path()
    
    print("=" * 80)
    print("ANALYZING TRACKING GAPS")
    print("=" * 80)
    
    # Find all settlements
    output_dir = Path("outputs")
    settlements = sorted([d.name for d in output_dir.iterdir() if d.is_dir() and d.name.isdigit()])
    
    if not settlements:
        print("[ERROR] No local settlements found")
        return
    
    print(f"\nFound {len(settlements)} settlements to analyze")
    
    # Analyze each settlement
    zoho = ZohoBooks()
    analysis_results = []
    
    for settlement_id in settlements:
        print(f"\nAnalyzing settlement {settlement_id}...")
        result = analyze_settlement(zoho, settlement_id)
        analysis_results.append(result)
        
        print(f"  Local invoices: {len(result['local_invoices'])}")
        print(f"  Zoho invoices: {len(result['zoho_invoices'])}")
        print(f"  Matched: {len(result['matched_invoices'])}")
        print(f"  Missing in Zoho: {len(result['missing_in_zoho_invoices'])}")
        print(f"  Extra in Zoho: {len(result['extra_in_zoho_invoices'])}")
        print(f"  Local payments: {len(result['local_payments'])}")
        print(f"  Zoho payments: {len(result['zoho_payments'])}")
        print(f"  Matched payments: {len(result['matched_payments'])}")
        print(f"  Missing payments: {len(result['missing_in_zoho_payments'])}")
    
    # Create action items
    create_action_items(analysis_results, output_file)


if __name__ == '__main__':
    main()

