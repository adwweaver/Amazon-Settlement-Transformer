#!/usr/bin/env python3
"""
Verify that payments are properly linked to invoices in Zoho Books.

This script checks:
1. Each payment is linked to an invoice
2. Payment amounts match invoice amounts
3. All invoices are properly paid

Usage:
    python scripts/verify_payment_invoice_links.py
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks

def get_payment_details(zoho: ZohoBooks, payment_id: str) -> dict:
    """Get payment details including linked invoices"""
    try:
        result = zoho._api_request('GET', f'customerpayments/{payment_id}')
        if result.get('code') == 0:
            payment = result.get('customerpayment', {})
            return {
                'payment_id': payment_id,
                'payment_number': payment.get('payment_number', ''),
                'amount': float(payment.get('amount', 0) or 0),
                'date': payment.get('date', ''),
                'reference_number': payment.get('reference_number', ''),
                'invoices': payment.get('invoices', []),
                'error': None
            }
        else:
            return {
                'payment_id': payment_id,
                'payment_number': '',
                'amount': 0.0,
                'date': '',
                'reference_number': '',
                'invoices': [],
                'error': result.get('message', 'Unknown error')
            }
    except Exception as e:
        return {
            'payment_id': payment_id,
            'payment_number': '',
            'amount': 0.0,
            'date': '',
            'reference_number': '',
            'invoices': [],
            'error': str(e)
        }


def get_all_payments_with_invoices(zoho: ZohoBooks) -> list:
    """Get all payments with their linked invoices"""
    try:
        start_date = f"{datetime.now().year}-01-01"
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        result = zoho._api_request('GET', f'customerpayments?date_start={start_date}&date_end={end_date}&per_page=200')
        payments = result.get('customerpayments', []) if result.get('code') == 0 else []
        
        # Paginate if needed
        page = 1
        while result.get('page_context', {}).get('has_more_page'):
            page += 1
            time.sleep(1)  # Rate limit delay
            result = zoho._api_request('GET', f'customerpayments?date_start={start_date}&date_end={end_date}&per_page=200&page={page}')
            if result.get('code') == 0:
                payments.extend(result.get('customerpayments', []))
        
        # Get detailed payment info for each payment
        payment_details = []
        for i, payment in enumerate(payments, 1):
            payment_id = payment.get('payment_id', '')
            if payment_id:
                print(f"  [{i}/{len(payments)}] Fetching payment {payment_id}...")
                time.sleep(0.5)  # Rate limit delay
                details = get_payment_details(zoho, payment_id)
                payment_details.append(details)
        
        return payment_details
    except Exception as e:
        print(f"[ERROR] Could not get payments: {e}")
        return []


def main():
    print("="*80)
    print("PAYMENT-INVOICE LINK VERIFICATION")
    print("="*80)
    print()
    
    zoho = ZohoBooks()
    
    print("Fetching all payments with invoice links...")
    payment_details = get_all_payments_with_invoices(zoho)
    
    if not payment_details:
        print("[ERROR] No payments found or error occurred")
        return
    
    print(f"\nFound {len(payment_details)} payment(s)")
    print()
    
    # Analyze payment-invoice links
    total_payment_amount = 0.0
    total_invoice_amount = 0.0
    payments_with_invoices = 0
    payments_without_invoices = 0
    payment_invoice_mismatch = 0
    
    payment_summary = []
    
    for payment in payment_details:
        if payment['error']:
            print(f"[ERROR] Payment {payment['payment_id']}: {payment['error']}")
            continue
        
        payment_amount = payment['amount']
        total_payment_amount += payment_amount
        
        invoices = payment.get('invoices', [])
        
        if invoices:
            payments_with_invoices += 1
            invoice_total = sum(float(inv.get('amount_applied', 0) or 0) for inv in invoices)
            total_invoice_amount += invoice_total
            
            # Check if payment amount matches invoice amount
            if abs(payment_amount - invoice_total) > 0.01:
                payment_invoice_mismatch += 1
                payment_summary.append({
                    'payment_id': payment['payment_id'],
                    'payment_number': payment['payment_number'],
                    'payment_amount': payment_amount,
                    'invoice_count': len(invoices),
                    'invoice_amount': invoice_total,
                    'difference': abs(payment_amount - invoice_total),
                    'status': 'MISMATCH'
                })
        else:
            payments_without_invoices += 1
            payment_summary.append({
                'payment_id': payment['payment_id'],
                'payment_number': payment['payment_number'],
                'payment_amount': payment_amount,
                'invoice_count': 0,
                'invoice_amount': 0.0,
                'difference': payment_amount,
                'status': 'NO_INVOICES'
            })
    
    # Print summary
    print("="*80)
    print("PAYMENT-INVOICE LINK SUMMARY")
    print("="*80)
    
    print(f"\nTotal Payments: {len(payment_details)}")
    print(f"Total Payment Amount: ${total_payment_amount:,.2f}")
    print(f"Total Invoice Amount (from payments): ${total_invoice_amount:,.2f}")
    print()
    
    print(f"Payments with invoices: {payments_with_invoices}")
    print(f"Payments without invoices: {payments_without_invoices}")
    print(f"Payment-Invoice mismatches: {payment_invoice_mismatch}")
    print()
    
    # Check for issues
    if payments_without_invoices > 0:
        print(f"[WARN] {payments_without_invoices} payment(s) are not linked to invoices")
    
    if payment_invoice_mismatch > 0:
        print(f"[WARN] {payment_invoice_mismatch} payment(s) have amount mismatches with invoices")
    
    # Calculate difference
    payment_invoice_diff = abs(total_payment_amount - total_invoice_amount)
    print(f"\nPayment-Invoice Amount Difference: ${payment_invoice_diff:,.2f}")
    
    if payment_invoice_diff < 1.0:
        print("[PASS] Payment amounts match invoice amounts (within $1.00)")
    else:
        print(f"[FAIL] Payment amounts don't match invoice amounts (${payment_invoice_diff:,.2f} difference)")
    
    # Save detailed report
    if payment_summary:
        summary_df = pd.DataFrame(payment_summary)
        report_file = Path("outputs") / f"Payment_Invoice_Link_Verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        summary_df.to_csv(report_file, index=False)
        print(f"\n[OK] Detailed report saved to: {report_file}")
        
        # Show top mismatches
        if payment_invoice_mismatch > 0:
            print("\nTop Payment-Invoice Mismatches:")
            top_mismatches = summary_df[summary_df['status'] == 'MISMATCH'].nlargest(10, 'difference')
            for _, row in top_mismatches.iterrows():
                print(f"  Payment {row['payment_number']}: Payment=${row['payment_amount']:,.2f}, "
                      f"Invoices=${row['invoice_amount']:,.2f}, Diff=${row['difference']:,.2f}")


if __name__ == "__main__":
    main()



