#!/usr/bin/env python3
"""
Create 1:1 mapping report of local invoices/payments vs Zoho.
Shows exactly what's in local, what's in Zoho, and the gaps.

Usage:
  python scripts/create_1to1_mapping.py --output invoice_payment_mapping.csv
"""

import argparse
import pandas as pd
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime

from zoho_sync import ZohoBooks


def get_local_invoices(settlement_id: str) -> pd.DataFrame:
    """Get all local invoices for a settlement."""
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    
    if not invoice_file.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(invoice_file)
        
        # Group by invoice number to get invoice-level data
        invoices = []
        if 'Invoice Number' in df.columns:
            for inv_num, group in df.groupby('Invoice Number'):
                first_row = group.iloc[0]
                invoices.append({
                    'settlement_id': settlement_id,
                    'local_invoice_number': str(inv_num),
                    'invoice_date': str(first_row.get('Invoice Date', '')),
                    'reference_number': str(first_row.get('Reference Number', settlement_id)),
                    'customer_name': str(first_row.get('Customer Name', '')),
                    'total_amount': float(group['Invoice Line Amount'].sum()),
                    'line_count': len(group),
                    'skus': ', '.join(group['SKU'].dropna().unique().astype(str)),
                    'status': 'LOCAL_ONLY',
                    'zoho_invoice_id': '',
                    'zoho_invoice_number': '',
                    'match_method': ''
                })
        
        return pd.DataFrame(invoices)
    except Exception as e:
        print(f"  Error reading local invoices for {settlement_id}: {e}")
        return pd.DataFrame()


def get_local_payments(settlement_id: str) -> pd.DataFrame:
    """Get all local payments for a settlement."""
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    
    if not payment_file.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(payment_file)
        
        payments = []
        if 'Invoice Number' in df.columns:
            for idx, row in df.iterrows():
                payments.append({
                    'settlement_id': settlement_id,
                    'local_invoice_number': str(row['Invoice Number']),
                    'payment_date': str(row.get('Payment Date', '')),
                    'reference_number': str(row.get('Reference Number', settlement_id)),
                    'payment_amount': float(row.get('Payment Amount', 0)),
                    'payment_mode': str(row.get('Payment Mode', '')),
                    'status': 'LOCAL_ONLY',
                    'zoho_payment_id': '',
                    'zoho_payment_number': '',
                    'match_method': ''
                })
        
        return pd.DataFrame(payments)
    except Exception as e:
        print(f"  Error reading local payments for {settlement_id}: {e}")
        return pd.DataFrame()


def get_zoho_invoices_by_settlement(zoho: ZohoBooks, settlement_id: str) -> Dict[str, Dict]:
    """Get all invoices from Zoho for a settlement, return invoice_number -> invoice_data map."""
    invoice_map = {}
    
    try:
        result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            invoices = result.get('invoices', [])
            for inv in invoices:
                invoice_id = inv.get('invoice_id', '')
                invoice_number = inv.get('invoice_number', '')
                reference_number = inv.get('reference_number', '')
                total = float(inv.get('total', 0))
                date = inv.get('date', '')
                
                # Store by multiple keys for matching
                invoice_data = {
                    'invoice_id': invoice_id,
                    'invoice_number': invoice_number,
                    'reference_number': reference_number,
                    'total': total,
                    'date': date,
                    'invoice': inv
                }
                
                # Map by invoice number
                if invoice_number:
                    invoice_map[invoice_number] = invoice_data
                
                # Map by reference number if different
                if reference_number and reference_number != invoice_number:
                    invoice_map[reference_number] = invoice_data
    except Exception as e:
        print(f"  Error querying Zoho invoices: {e}")
    
    return invoice_map


def get_zoho_payments_by_settlement(zoho: ZohoBooks, settlement_id: str) -> Dict[str, Dict]:
    """Get all payments from Zoho for a settlement."""
    payment_map = {}
    
    try:
        result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            payments = result.get('customerpayments', [])
            for pay in payments:
                payment_id = pay.get('payment_id', '')
                reference_number = pay.get('reference_number', '')
                invoice_number = pay.get('invoice_number', '')
                amount = float(pay.get('amount', 0))
                
                payment_data = {
                    'payment_id': payment_id,
                    'reference_number': reference_number,
                    'invoice_number': invoice_number,
                    'amount': amount,
                    'payment': pay
                }
                
                # Map by invoice number (for linking to invoices)
                if invoice_number:
                    payment_map[invoice_number] = payment_data
                if reference_number:
                    payment_map[reference_number] = payment_data
    except Exception as e:
        print(f"  Error querying Zoho payments: {e}")
    
    return payment_map


def match_invoices(local_df: pd.DataFrame, zoho_map: Dict[str, Dict], settlement_id: str) -> pd.DataFrame:
    """Match local invoices to Zoho invoices."""
    if local_df.empty:
        return local_df
    
    for idx, row in local_df.iterrows():
        local_inv_num = row['local_invoice_number']
        local_ref = row['reference_number']
        local_amount = row['total_amount']
        
        # Try to find match in Zoho
        zoho_inv = None
        match_method = ''
        
        # Try by invoice number first
        if local_inv_num in zoho_map:
            zoho_inv = zoho_map[local_inv_num]
            match_method = 'INVOICE_NUMBER'
        # Try by reference number
        elif local_ref in zoho_map:
            zoho_inv = zoho_map[local_ref]
            match_method = 'REFERENCE_NUMBER'
        # Try by amount and settlement (fuzzy match)
        else:
            for zoho_key, zoho_data in zoho_map.items():
                if abs(zoho_data['total'] - local_amount) < 0.01:
                    zoho_inv = zoho_data
                    match_method = 'AMOUNT_MATCH'
                    break
        
        if zoho_inv:
            local_df.at[idx, 'status'] = 'MATCHED'
            local_df.at[idx, 'zoho_invoice_id'] = zoho_inv['invoice_id']
            local_df.at[idx, 'zoho_invoice_number'] = zoho_inv['invoice_number']
            local_df.at[idx, 'match_method'] = match_method
        else:
            local_df.at[idx, 'status'] = 'NOT_IN_ZOHO'
    
    return local_df


def match_payments(local_df: pd.DataFrame, zoho_map: Dict[str, Dict], invoice_map: Dict[str, Dict], settlement_id: str) -> pd.DataFrame:
    """Match local payments to Zoho payments."""
    if local_df.empty:
        return local_df
    
    for idx, row in local_df.iterrows():
        local_inv_num = row['local_invoice_number']
        local_amount = row['payment_amount']
        
        # Try to find payment in Zoho by invoice number
        zoho_payment = None
        match_method = ''
        
        if local_inv_num in zoho_map:
            zoho_payment = zoho_map[local_inv_num]
            match_method = 'INVOICE_NUMBER'
        # Try by amount if invoice linked
        elif local_inv_num in invoice_map:
            for zoho_key, zoho_data in zoho_map.items():
                if abs(zoho_data['amount'] - local_amount) < 0.01:
                    zoho_payment = zoho_data
                    match_method = 'AMOUNT_MATCH'
                    break
        
        if zoho_payment:
            local_df.at[idx, 'status'] = 'MATCHED'
            local_df.at[idx, 'zoho_payment_id'] = zoho_payment['payment_id']
            local_df.at[idx, 'zoho_payment_number'] = zoho_payment.get('payment_number', '')
            local_df.at[idx, 'match_method'] = match_method
        else:
            local_df.at[idx, 'status'] = 'NOT_IN_ZOHO'
    
    return local_df


def create_extra_zoho_records(zoho_invoices: Dict, zoho_payments: Dict, local_invoices: Set[str], local_payments: Set[str], settlement_id: str) -> pd.DataFrame:
    """Create records for items in Zoho that aren't in local files."""
    extra_records = []
    
    # Find invoices in Zoho not in local
    for zoho_key, zoho_data in zoho_invoices.items():
        if zoho_key not in local_invoices:
            extra_records.append({
                'settlement_id': settlement_id,
                'record_type': 'INVOICE',
                'local_invoice_number': '',
                'zoho_invoice_id': zoho_data['invoice_id'],
                'zoho_invoice_number': zoho_data['invoice_number'],
                'invoice_date': zoho_data['date'],
                'total_amount': zoho_data['total'],
                'status': 'IN_ZOHO_ONLY',
                'match_method': ''
            })
    
    # Find payments in Zoho not in local
    for zoho_key, zoho_data in zoho_payments.items():
        if zoho_key not in local_payments:
            extra_records.append({
                'settlement_id': settlement_id,
                'record_type': 'PAYMENT',
                'local_invoice_number': '',
                'zoho_payment_id': zoho_data['payment_id'],
                'zoho_payment_number': '',
                'payment_amount': zoho_data['amount'],
                'status': 'IN_ZOHO_ONLY',
                'match_method': ''
            })
    
    return pd.DataFrame(extra_records)


def main():
    parser = argparse.ArgumentParser(description='Create 1:1 mapping of invoices/payments')
    from paths import get_action_items_path
    parser.add_argument('--output', default=None, help='Output CSV file (defaults to SharePoint location)')
    args = parser.parse_args()
    
    if args.output:
        output_file = Path(args.output)
    else:
        sharepoint_base = Path(r"~\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL").expanduser()
        output_file = sharepoint_base / "invoice_payment_1to1_mapping.csv"
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("CREATING 1:1 INVOICE/PAYMENT MAPPING")
    print("=" * 80)
    
    # Find all settlements
    output_dir = Path("outputs")
    settlements = sorted([d.name for d in output_dir.iterdir() if d.is_dir() and d.name.isdigit()])
    
    print(f"\nFound {len(settlements)} settlements to map")
    
    # Query Zoho
    zoho = ZohoBooks()
    
    all_invoice_records = []
    all_payment_records = []
    all_extra_records = []
    
    for settlement_id in settlements:
        print(f"\nProcessing settlement {settlement_id}...")
        
        # Get local data
        local_invoices_df = get_local_invoices(settlement_id)
        local_payments_df = get_local_payments(settlement_id)
        
        print(f"  Local: {len(local_invoices_df)} invoices, {len(local_payments_df)} payments")
        
        # Get Zoho data
        zoho_invoices = get_zoho_invoices_by_settlement(zoho, settlement_id)
        zoho_payments = get_zoho_payments_by_settlement(zoho, settlement_id)
        
        print(f"  Zoho: {len(zoho_invoices)} invoices, {len(zoho_payments)} payments")
        
        # Match invoices
        if not local_invoices_df.empty:
            local_invoices_df = match_invoices(local_invoices_df, zoho_invoices, settlement_id)
            all_invoice_records.append(local_invoices_df)
        
        # Match payments
        if not local_payments_df.empty:
            local_payments_df = match_payments(local_payments_df, zoho_payments, zoho_invoices, settlement_id)
            all_payment_records.append(local_payments_df)
        
        # Find extra items in Zoho
        local_inv_nums = set(local_invoices_df['local_invoice_number'].unique()) if not local_invoices_df.empty else set()
        local_pay_inv_nums = set(local_payments_df['local_invoice_number'].unique()) if not local_payments_df.empty else set()
        
        extra_df = create_extra_zoho_records(zoho_invoices, zoho_payments, local_inv_nums, local_pay_inv_nums, settlement_id)
        if not extra_df.empty:
            all_extra_records.append(extra_df)
    
    # Combine all records
    print("\n" + "=" * 80)
    print("COMBINING RESULTS")
    print("=" * 80)
    
    # Combine invoices
    invoices_df = pd.concat(all_invoice_records, ignore_index=True) if all_invoice_records else pd.DataFrame()
    
    # Combine payments
    payments_df = pd.concat(all_payment_records, ignore_index=True) if all_payment_records else pd.DataFrame()
    
    # Combine extra records
    extra_df = pd.concat(all_extra_records, ignore_index=True) if all_extra_records else pd.DataFrame()
    
    # Create final mapping
    mapping_records = []
    
    # Add invoice records
    for idx, row in invoices_df.iterrows():
        mapping_records.append({
            'settlement_id': row['settlement_id'],
            'record_type': 'INVOICE',
            'local_invoice_number': row['local_invoice_number'],
            'local_amount': row['total_amount'],
            'local_date': row['invoice_date'],
            'local_line_count': row['line_count'],
            'local_skus': row['skus'],
            'status': row['status'],
            'zoho_invoice_id': row['zoho_invoice_id'],
            'zoho_invoice_number': row['zoho_invoice_number'],
            'match_method': row['match_method'],
            'action_needed': 'CREATE' if row['status'] == 'NOT_IN_ZOHO' else 'UPDATE_TRACKING' if row['status'] == 'MATCHED' else 'VERIFY'
        })
    
    # Add payment records
    for idx, row in payments_df.iterrows():
        mapping_records.append({
            'settlement_id': row['settlement_id'],
            'record_type': 'PAYMENT',
            'local_invoice_number': row['local_invoice_number'],
            'local_amount': row['payment_amount'],
            'local_date': row['payment_date'],
            'local_line_count': '',
            'local_skus': '',
            'status': row['status'],
            'zoho_payment_id': row.get('zoho_payment_id', ''),
            'zoho_payment_number': row.get('zoho_payment_number', ''),
            'match_method': row.get('match_method', ''),
            'action_needed': 'CREATE' if row['status'] == 'NOT_IN_ZOHO' else 'UPDATE_TRACKING' if row['status'] == 'MATCHED' else 'VERIFY'
        })
    
    # Add extra Zoho records
    for idx, row in extra_df.iterrows():
        if row['record_type'] == 'INVOICE':
            mapping_records.append({
                'settlement_id': row['settlement_id'],
                'record_type': 'INVOICE',
                'local_invoice_number': '',
                'local_amount': '',
                'local_date': '',
                'local_line_count': '',
                'local_skus': '',
                'status': 'IN_ZOHO_ONLY',
                'zoho_invoice_id': row['zoho_invoice_id'],
                'zoho_invoice_number': row['zoho_invoice_number'],
                'match_method': '',
                'action_needed': 'VERIFY/DELETE'
            })
        else:
            mapping_records.append({
                'settlement_id': row['settlement_id'],
                'record_type': 'PAYMENT',
                'local_invoice_number': '',
                'local_amount': '',
                'local_date': '',
                'local_line_count': '',
                'local_skus': '',
                'status': 'IN_ZOHO_ONLY',
                'zoho_payment_id': row.get('zoho_payment_id', ''),
                'zoho_payment_number': row.get('zoho_payment_number', ''),
                'match_method': '',
                'action_needed': 'VERIFY/DELETE'
            })
    
    # Create DataFrame and save
    mapping_df = pd.DataFrame(mapping_records)
    
    if not mapping_df.empty:
        mapping_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"\n[SUCCESS] 1:1 mapping saved to: {output_file}")
        print(f"  Total records: {len(mapping_df)}")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        summary = mapping_df.groupby(['record_type', 'status', 'action_needed']).size().unstack(fill_value=0)
        print("\nBreakdown by Status:")
        print(summary)
        
        # Action items summary
        action_summary = mapping_df.groupby('action_needed').size()
        print("\nAction Items:")
        for action, count in action_summary.items():
            print(f"  {action}: {count}")
        
        print(f"\n\nOpen the CSV file to see detailed 1:1 mapping:")
        print(f"  {output_file}")
    else:
        print("[WARNING] No mapping records to save")


if __name__ == '__main__':
    main()



