#!/usr/bin/env python3
"""
Check current status of invoices and payments in Zoho vs local files.
"""

import time
from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from post_all_settlements import find_local_settlements
from paths import get_zoho_tracking_path


def check_settlement_status(zoho: ZohoBooks, settlement_id: str):
    """Check status of a single settlement."""
    
    # Load local files
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    
    local_invoice_count = 0
    local_payment_count = 0
    
    if invoice_file.exists():
        try:
            df_inv = pd.read_csv(invoice_file)
            local_invoice_count = len(df_inv['Invoice Number'].unique())
        except:
            pass
    
    if payment_file.exists():
        try:
            df_pay = pd.read_csv(payment_file)
            local_payment_count = len(df_pay)
        except:
            pass
    
    # Check tracking file
    tracking_file = get_zoho_tracking_path()
    zoho_invoice_count = 0
    zoho_payment_count = 0
    
    if tracking_file.exists():
        try:
            df_track = pd.read_csv(tracking_file)
            df_track['settlement_id'] = df_track['settlement_id'].astype(str)
            
            settlement_track = df_track[df_track['settlement_id'] == str(settlement_id)]
            
            invoices_track = settlement_track[settlement_track['record_type'] == 'INVOICE']
            zoho_invoice_count = len(invoices_track[invoices_track['zoho_id'].notna() & (invoices_track['zoho_id'] != '')])
            
            payments_track = settlement_track[settlement_track['record_type'] == 'PAYMENT']
            zoho_payment_count = len(payments_track[payments_track['zoho_id'].notna() & (payments_track['zoho_id'] != '')])
        except Exception as e:
            print(f"    [ERROR] Could not read tracking: {e}")
    
    # Query Zoho to verify (but use delays to avoid rate limits)
    print(f"  Querying Zoho (waiting 5s for rate limits)...")
    time.sleep(5)
    
    try:
        # Get invoices by reference_number
        inv_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        zoho_invoices_api = 0
        if inv_result.get('code') == 0:
            zoho_invoices_api = len(inv_result.get('invoices', []))
        
        # Get payments by reference_number
        pay_result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
        zoho_payments_api = 0
        if pay_result.get('code') == 0:
            zoho_payments_api = len(pay_result.get('customerpayments', []))
        
        return {
            'settlement_id': settlement_id,
            'local_invoices': local_invoice_count,
            'local_payments': local_payment_count,
            'zoho_invoices_tracking': zoho_invoice_count,
            'zoho_payments_tracking': zoho_payment_count,
            'zoho_invoices_api': zoho_invoices_api,
            'zoho_payments_api': zoho_payments_api,
            'invoices_missing': max(0, local_invoice_count - zoho_invoices_api),
            'payments_missing': max(0, local_payment_count - zoho_payments_api),
            'invoices_extra': max(0, zoho_invoices_api - local_invoice_count),
            'payments_extra': max(0, zoho_payments_api - local_payment_count),
        }
    except Exception as e:
        print(f"    [ERROR] API query failed: {e}")
        return {
            'settlement_id': settlement_id,
            'local_invoices': local_invoice_count,
            'local_payments': local_payment_count,
            'zoho_invoices_tracking': zoho_invoice_count,
            'zoho_payments_tracking': zoho_payment_count,
            'zoho_invoices_api': None,
            'zoho_payments_api': None,
            'invoices_missing': None,
            'payments_missing': None,
            'invoices_extra': None,
            'payments_extra': None,
        }


def main():
    print("="*80)
    print("CURRENT STATUS: INVOICES AND PAYMENTS")
    print("="*80)
    
    settlements = find_local_settlements()
    zoho = ZohoBooks()
    
    all_status = []
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"\n{i}/{len(settlements)}: Settlement {settlement_id}")
        status = check_settlement_status(zoho, settlement_id)
        all_status.append(status)
        
        # Print summary
        print(f"  Local:  {status['local_invoices']} invoices, {status['local_payments']} payments")
        if status['zoho_invoices_api'] is not None:
            print(f"  Zoho:  {status['zoho_invoices_api']} invoices, {status['zoho_payments_api']} payments")
            if status['invoices_missing'] > 0:
                print(f"  [MISSING] {status['invoices_missing']} invoice(s) not in Zoho")
            if status['payments_missing'] > 0:
                print(f"  [MISSING] {status['payments_missing']} payment(s) not in Zoho")
            if status['invoices_extra'] > 0:
                print(f"  [EXTRA] {status['invoices_extra']} invoice(s) in Zoho not in local")
            if status['payments_extra'] > 0:
                print(f"  [EXTRA] {status['payments_extra']} payment(s) in Zoho not in local")
        else:
            print(f"  [ERROR] Could not query Zoho API")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total_local_inv = sum(s['local_invoices'] for s in all_status)
    total_local_pay = sum(s['local_payments'] for s in all_status)
    total_zoho_inv = sum(s['zoho_invoices_api'] or 0 for s in all_status)
    total_zoho_pay = sum(s['zoho_payments_api'] or 0 for s in all_status)
    total_missing_inv = sum(s['invoices_missing'] or 0 for s in all_status)
    total_missing_pay = sum(s['payments_missing'] or 0 for s in all_status)
    
    print(f"Total Local:  {total_local_inv} invoices, {total_local_pay} payments")
    print(f"Total Zoho:   {total_zoho_inv} invoices, {total_zoho_pay} payments")
    print(f"Missing:      {total_missing_inv} invoices, {total_missing_pay} payments")
    
    # Determine if we need to start from scratch
    print("\n" + "="*80)
    print("ASSESSMENT")
    print("="*80)
    
    if total_missing_inv == 0 and total_missing_pay == 0:
        print("✅ ALL INVOICES AND PAYMENTS ARE POSTED!")
        print("   Status: Complete - everything is synced")
    elif total_missing_inv > 0 and total_zoho_inv > 0:
        print("⚠️  PARTIAL: Some invoices missing, but some exist")
        print(f"   Missing: {total_missing_inv} invoices, {total_missing_pay} payments")
        print("   Action: Post missing invoices/payments")
    elif total_missing_inv == total_local_inv:
        print("❌ NO INVOICES POSTED")
        print("   Action: Need to post all invoices and payments")
    else:
        print("⚠️  MIXED STATUS")
        print(f"   Posted: {total_zoho_inv}/{total_local_inv} invoices, {total_zoho_pay}/{total_local_pay} payments")
        print(f"   Missing: {total_missing_inv} invoices, {total_missing_pay} payments")
    
    # Check if we need to start from scratch
    # Criteria: More than 50% missing OR invoices have wrong numbers
    if total_missing_inv > total_local_inv * 0.5:
        print("\n⚠️  CONSIDER: Starting from scratch may be easier")
        print("   Reason: More than 50% of invoices are missing")
    else:
        print("\n✅ RECOMMENDATION: Continue posting missing items")
        print("   Reason: Most invoices exist, just need to fill gaps")


if __name__ == '__main__':
    main()



