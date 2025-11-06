#!/usr/bin/env python3
"""
Build comprehensive tracking maps linking local records to Zoho transaction IDs.
This provides bulletproof auditing by mapping every local record to its Zoho counterpart.

Usage:
  python scripts/build_tracking_maps.py --output database/zoho_tracking.csv
"""

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Set
import pandas as pd
from datetime import datetime

from zoho_sync import ZohoBooks


def query_zoho_for_settlement(zoho: ZohoBooks, settlement_id: str) -> Dict:
    """Query Zoho directly for all transactions related to a settlement."""
    tracking = {
        'journal_id': None,
        'invoice_map': {},
        'payment_map': {}
    }
    
    # Get journal
    try:
        journal_id = zoho.check_existing_journal(settlement_id)
        if journal_id:
            tracking['journal_id'] = journal_id
    except:
        pass
    
    # Get invoices
    try:
        result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            invoices = result.get('invoices', [])
            for inv in invoices:
                invoice_id = inv.get('invoice_id', '')
                invoice_number = inv.get('invoice_number', '')
                reference_number = inv.get('reference_number', '')
                
                # Map by invoice number and reference number
                if invoice_number and invoice_id:
                    tracking['invoice_map'][invoice_number] = invoice_id
                if reference_number and invoice_id:
                    tracking['invoice_map'][reference_number] = invoice_id
    except Exception as e:
        print(f"    Warning: Could not query invoices: {e}")
    
    # Get payments
    try:
        result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
        if result.get('code') == 0:
            payments = result.get('customerpayments', [])
            for pay in payments:
                payment_id = pay.get('payment_id', '')
                reference_number = pay.get('reference_number', '')
                
                # Map by reference number
                if reference_number and payment_id:
                    tracking['payment_map'][reference_number] = payment_id
    except Exception as e:
        print(f"    Warning: Could not query payments: {e}")
    
    return tracking


def build_local_mappings(settlement_id: str) -> Dict:
    """Build local invoice/payment mappings from CSV files."""
    output_dir = Path("outputs") / settlement_id
    
    local_mappings = {
        'invoices': {},
        'payments': {}
    }
    
    # Read invoice file
    invoice_file = output_dir / f"Invoice_{settlement_id}.csv"
    if invoice_file.exists():
        try:
            df = pd.read_csv(invoice_file)
            if 'Invoice Number' in df.columns:
                # Group by invoice number to get reference number
                for inv_num, group in df.groupby('Invoice Number'):
                    ref_num = group['Reference Number'].iloc[0] if 'Reference Number' in df.columns else settlement_id
                    local_mappings['invoices'][inv_num] = {
                        'reference_number': ref_num,
                        'local_invoice_number': inv_num
                    }
        except Exception as e:
            print(f"  Warning: Could not read invoice file: {e}")
    
    # Read payment file
    payment_file = output_dir / f"Payment_{settlement_id}.csv"
    if payment_file.exists():
        try:
            df = pd.read_csv(payment_file)
            if 'Reference Number' in df.columns:
                for ref_num, group in df.groupby('Reference Number'):
                    local_mappings['payments'][ref_num] = {
                        'reference_number': ref_num
                    }
        except Exception as e:
            print(f"  Warning: Could not read payment file: {e}")
    
    return local_mappings


def create_tracking_records(settlements: List[str], zoho: ZohoBooks, output_file: Path):
    """Create comprehensive tracking CSV by querying Zoho and local files."""
    records = []
    
    print(f"\n[2] Querying Zoho for {len(settlements)} settlements...")
    
    for settlement_id in settlements:
        print(f"  Settlement {settlement_id}:")
        
        # Query Zoho
        zoho_data = query_zoho_for_settlement(zoho, settlement_id)
        
        # Get local mappings
        local_mappings = build_local_mappings(settlement_id)
        
        journal_id = zoho_data.get('journal_id')
        invoice_map = zoho_data.get('invoice_map', {})
        payment_map = zoho_data.get('payment_map', {})
        
        # Journal record
        records.append({
            'settlement_id': settlement_id,
            'record_type': 'JOURNAL',
            'local_identifier': settlement_id,
            'zoho_id': journal_id or '',
            'zoho_number': '',
            'reference_number': settlement_id,
            'status': 'POSTED' if journal_id else 'NOT_POSTED',
            'created_date': datetime.now().isoformat()
        })
        
        # Invoice records
        matched_invoices = 0
        for inv_num, inv_data in local_mappings['invoices'].items():
            # Try multiple ways to find Zoho invoice ID
            zoho_invoice_id = (
                invoice_map.get(inv_num) or
                invoice_map.get(inv_data.get('reference_number', '')) or
                ''
            )
            
            if zoho_invoice_id:
                matched_invoices += 1
            
            records.append({
                'settlement_id': settlement_id,
                'record_type': 'INVOICE',
                'local_identifier': inv_num,
                'zoho_id': zoho_invoice_id,
                'zoho_number': inv_num,
                'reference_number': inv_data.get('reference_number', settlement_id),
                'status': 'POSTED' if zoho_invoice_id else 'NOT_POSTED',
                'created_date': datetime.now().isoformat()
            })
        
        # Payment records
        matched_payments = 0
        for ref_num, pay_data in local_mappings['payments'].items():
            zoho_payment_id = payment_map.get(ref_num, '')
            
            if zoho_payment_id:
                matched_payments += 1
            
            records.append({
                'settlement_id': settlement_id,
                'record_type': 'PAYMENT',
                'local_identifier': ref_num,
                'zoho_id': zoho_payment_id,
                'zoho_number': '',
                'reference_number': ref_num,
                'status': 'POSTED' if zoho_payment_id else 'NOT_POSTED',
                'created_date': datetime.now().isoformat()
            })
        
        print(f"    Journal: {'POSTED' if journal_id else 'NOT_POSTED'}")
        print(f"    Invoices: {matched_invoices}/{len(local_mappings['invoices'])} matched")
        print(f"    Payments: {matched_payments}/{len(local_mappings['payments'])} matched")
    
    # Write CSV
    if records:
        df = pd.DataFrame(records)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n[SUCCESS] Created tracking file: {output_file}")
        print(f"  Total records: {len(records)}")
        
        summary = df.groupby(['record_type', 'status']).size().unstack(fill_value=0)
        print("\nSummary:")
        print(summary)
    else:
        print("[WARNING] No records to track")


def find_local_settlements() -> List[str]:
    """Find all settlement IDs from local output directories."""
    output_dir = Path("outputs")
    settlements = []
    
    if not output_dir.exists():
        return settlements
    
    for item in output_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            settlements.append(item.name)
    
    return sorted(settlements)


def main():
    from paths import get_zoho_tracking_path
    parser = argparse.ArgumentParser(description='Build comprehensive Zoho tracking maps')
    parser.add_argument('--output', default=None, help='Output tracking CSV (defaults to SharePoint location)')
    args = parser.parse_args()
    
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = get_zoho_tracking_path()
    
    print("=" * 80)
    print("BUILDING ZOHO TRACKING MAPS")
    print("=" * 80)
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Find local settlements
    print("\n[1] Finding local settlements...")
    settlements = find_local_settlements()
    print(f"  Found {len(settlements)} settlements")
    
    if not settlements:
        print("[ERROR] No local settlements found")
        return
    
    # Query Zoho and create tracking records
    zoho = ZohoBooks()
    create_tracking_records(settlements, zoho, output_file)
    
    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print(f"Tracking file: {output_file}")
    print("\nThis file provides complete audit trail linking:")
    print("  - Local invoice numbers -> Zoho invoice IDs")
    print("  - Local payment references -> Zoho payment IDs")
    print("  - Settlement IDs -> Zoho journal IDs")


if __name__ == '__main__':
    main()
