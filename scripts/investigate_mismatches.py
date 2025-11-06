#!/usr/bin/env python3
"""
Investigate invoice/payment mismatches for specific settlements.

This script examines the mismatched settlements in detail to identify root causes.

Usage:
    python scripts/investigate_mismatches.py
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks

def investigate_settlement(settlement_id: str, zoho: ZohoBooks):
    """Investigate a specific settlement for mismatches"""
    print(f"\n{'='*80}")
    print(f"INVESTIGATING SETTLEMENT: {settlement_id}")
    print(f"{'='*80}")
    
    # Load local files
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    
    local_invoices_df = None
    local_payments_df = None
    
    if invoice_file.exists():
        local_invoices_df = pd.read_csv(invoice_file)
        print(f"\nLocal Invoices: {len(local_invoices_df)} records")
        if 'Invoice Number' in local_invoices_df.columns:
            unique_invoices = local_invoices_df['Invoice Number'].nunique()
            print(f"  Unique Invoice Numbers: {unique_invoices}")
            if 'Invoice Line Amount' in local_invoices_df.columns:
                total = local_invoices_df['Invoice Line Amount'].sum()
                print(f"  Total Invoice Amount: ${total:,.2f}")
    
    if payment_file.exists():
        local_payments_df = pd.read_csv(payment_file)
        print(f"\nLocal Payments: {len(local_payments_df)} records")
        if 'Payment Amount' in local_payments_df.columns:
            total = local_payments_df['Payment Amount'].sum()
            print(f"  Total Payment Amount: ${total:,.2f}")
            if 'Invoice Number' in local_payments_df.columns:
                unique_invoices = local_payments_df['Invoice Number'].nunique()
                print(f"  Unique Invoice Numbers in Payments: {unique_invoices}")
    
    # Query Zoho
    print(f"\nQuerying Zoho...")
    time.sleep(5)
    
    # Get invoices from Zoho
    inv_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
    zoho_invoices = inv_result.get('invoices', []) if inv_result.get('code') == 0 else []
    
    print(f"\nZoho Invoices: {len(zoho_invoices)}")
    if zoho_invoices:
        zoho_inv_total = sum(float(inv.get('total', 0) or 0) for inv in zoho_invoices)
        print(f"  Total Invoice Amount: ${zoho_inv_total:,.2f}")
        
        # Check invoice balances
        unpaid_invoices = []
        for inv in zoho_invoices:
            balance = float(inv.get('balance', 0) or 0)
            if balance == 0 or balance == '':
                total = float(inv.get('total', 0) or 0)
                payments = float(inv.get('payments', 0) or 0)
                balance = total - payments
            
            if abs(balance) >= 0.01:
                unpaid_invoices.append({
                    'invoice_number': inv.get('invoice_number', ''),
                    'invoice_id': inv.get('invoice_id', ''),
                    'total': float(inv.get('total', 0) or 0),
                    'balance': float(balance) if balance else 0.0,
                    'payments': float(inv.get('payments', 0) or 0)
                })
        
        if unpaid_invoices:
            print(f"  Unpaid Invoices: {len(unpaid_invoices)}")
            print(f"  Total Outstanding: ${sum(inv['balance'] for inv in unpaid_invoices):,.2f}")
    
    time.sleep(5)
    
    # Get payments from Zoho
    pay_result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
    zoho_payments = pay_result.get('customerpayments', []) if pay_result.get('code') == 0 else []
    
    print(f"\nZoho Payments: {len(zoho_payments)}")
    if zoho_payments:
        zoho_pay_total = sum(float(pay.get('amount', 0) or 0) for pay in zoho_payments)
        print(f"  Total Payment Amount: ${zoho_pay_total:,.2f}")
        
        # Check payment-invoice links
        payments_with_invoices = 0
        payments_without_invoices = 0
        
        for pay in zoho_payments:
            # Get detailed payment info to check invoice links
            payment_id = pay.get('payment_id', '')
            if payment_id:
                pay_details = zoho.get_payment_details(payment_id) if hasattr(zoho, 'get_payment_details') else None
                if pay_details and pay_details.get('invoices'):
                    payments_with_invoices += 1
                else:
                    payments_without_invoices += 1
        
        print(f"  Payments with invoice links: {payments_with_invoices}")
        print(f"  Payments without invoice links: {payments_without_invoices}")
    
    # Calculate differences
    print(f"\n{'='*80}")
    print("DIFFERENCES")
    print(f"{'='*80}")
    
    if local_invoices_df is not None and local_payments_df is not None:
        local_inv_total = local_invoices_df['Invoice Line Amount'].sum() if 'Invoice Line Amount' in local_invoices_df.columns else 0
        local_pay_total = local_payments_df['Payment Amount'].sum() if 'Payment Amount' in local_payments_df.columns else 0
        local_diff = local_inv_total - local_pay_total
        print(f"\nLocal Invoice/Payment Difference: ${local_diff:,.2f}")
    
    if zoho_invoices and zoho_payments:
        zoho_inv_total = sum(float(inv.get('total', 0) or 0) for inv in zoho_invoices)
        zoho_pay_total = sum(float(pay.get('amount', 0) or 0) for pay in zoho_payments)
        zoho_diff = zoho_inv_total - zoho_pay_total
        print(f"Zoho Invoice/Payment Difference: ${zoho_diff:,.2f}")
    
    if local_invoices_df is not None and zoho_invoices:
        local_inv_count = local_invoices_df['Invoice Number'].nunique() if 'Invoice Number' in local_invoices_df.columns else 0
        zoho_inv_count = len(zoho_invoices)
        print(f"\nInvoice Count Difference: Local={local_inv_count}, Zoho={zoho_inv_count}, Diff={local_inv_count - zoho_inv_count}")
    
    if local_payments_df is not None and zoho_payments:
        local_pay_count = len(local_payments_df)
        zoho_pay_count = len(zoho_payments)
        print(f"Payment Count Difference: Local={local_pay_count}, Zoho={zoho_pay_count}, Diff={local_pay_count - zoho_pay_count}")


def main():
    # Mismatched settlements from balance verification
    mismatched_settlements = [
        "24288684721",  # $15.25 difference
        "24495221541",  # $86.58 difference
        "24596907561"   # $8.42 difference
    ]
    
    print("="*80)
    print("INVESTIGATING INVOICE/PAYMENT MISMATCHES")
    print("="*80)
    print(f"\nSettlements to investigate: {', '.join(mismatched_settlements)}")
    
    zoho = ZohoBooks()
    
    for settlement_id in mismatched_settlements:
        investigate_settlement(settlement_id, zoho)
        time.sleep(5)  # Rate limit delay between settlements
    
    print(f"\n{'='*80}")
    print("INVESTIGATION COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()



