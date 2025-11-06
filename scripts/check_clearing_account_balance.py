#!/usr/bin/env python3
"""
Check Amazon.ca Clearing Account balance in Zoho Books.

This script verifies that:
1. All invoices are fully paid (balance = 0)
2. Clearing account balance = $0.00 (if invoices = payments)
3. Invoice totals match payment totals

Usage:
    python scripts/check_clearing_account_balance.py
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
import yaml

def get_account_balance(zoho: ZohoBooks, account_id: str) -> dict:
    """Get account balance from Zoho Books"""
    try:
        # Get account details
        result = zoho._api_request('GET', f'chartofaccounts/{account_id}')
        if result.get('code') == 0:
            account = result.get('chart_of_account', {})
            return {
                'account_id': account_id,
                'account_name': account.get('account_name', 'Unknown'),
                'account_type': account.get('account_type', 'Unknown'),
                'balance': float(account.get('balance', 0) or 0),
                'error': None
            }
        else:
            return {
                'account_id': account_id,
                'account_name': 'Unknown',
                'account_type': 'Unknown',
                'balance': 0.0,
                'error': result.get('message', 'Unknown error')
            }
    except Exception as e:
        return {
            'account_id': account_id,
            'account_name': 'Unknown',
            'account_type': 'Unknown',
            'balance': 0.0,
            'error': str(e)
        }


def get_all_invoices_balance(zoho: ZohoBooks, settlement_id: str = None) -> dict:
    """Get total invoice balance for a settlement or all settlements"""
    try:
        if settlement_id:
            # Get invoices for specific settlement
            result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
            invoices = result.get('invoices', []) if result.get('code') == 0 else []
        else:
            # Get all invoices (this might be slow, so use date range)
            # For now, get YTD invoices
            start_date = f"{datetime.now().year}-01-01"
            end_date = datetime.now().strftime('%Y-%m-%d')
            result = zoho._api_request('GET', f'invoices?date_start={start_date}&date_end={end_date}&per_page=200')
            invoices = result.get('invoices', []) if result.get('code') == 0 else []
            
            # Paginate if needed
            page = 1
            while result.get('page_context', {}).get('has_more_page'):
                page += 1
                time.sleep(1)  # Rate limit delay
                result = zoho._api_request('GET', f'invoices?date_start={start_date}&date_end={end_date}&per_page=200&page={page}')
                if result.get('code') == 0:
                    invoices.extend(result.get('invoices', []))
        
        total_balance = 0.0
        total_amount = 0.0
        total_paid = 0.0
        unpaid_count = 0
        
        for inv in invoices:
            total = float(inv.get('total', 0) or 0)
            balance = float(inv.get('balance', 0) or 0)
            if balance == 0 or balance == '':
                # Try to calculate from payments
                payments = float(inv.get('payments', 0) or 0)
                balance = total - payments
            
            total_amount += total
            total_paid += (total - balance)
            total_balance += float(balance) if balance else 0.0
            
            if abs(float(balance) if balance else 0.0) >= 0.01:
                unpaid_count += 1
        
        return {
            'invoice_count': len(invoices),
            'total_amount': round(total_amount, 2),
            'total_paid': round(total_paid, 2),
            'total_balance': round(total_balance, 2),
            'unpaid_count': unpaid_count,
            'error': None
        }
    except Exception as e:
        return {
            'invoice_count': 0,
            'total_amount': 0.0,
            'total_paid': 0.0,
            'total_balance': 0.0,
            'unpaid_count': 0,
            'error': str(e)
        }


def get_all_payments_total(zoho: ZohoBooks, settlement_id: str = None) -> dict:
    """Get total payments for a settlement or all settlements"""
    try:
        if settlement_id:
            # Get payments for specific settlement
            result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
            payments = result.get('customerpayments', []) if result.get('code') == 0 else []
        else:
            # Get all payments (YTD)
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
        
        total_amount = 0.0
        for pay in payments:
            total_amount += float(pay.get('amount', 0) or 0)
        
        return {
            'payment_count': len(payments),
            'total_amount': round(total_amount, 2),
            'error': None
        }
    except Exception as e:
        return {
            'payment_count': 0,
            'total_amount': 0.0,
            'error': str(e)
        }


def main():
    print("="*80)
    print("AMAZON.CA CLEARING ACCOUNT BALANCE CHECK")
    print("="*80)
    print()
    
    # Load GL mapping to get clearing account ID
    mapping_file = Path(__file__).parent.parent / 'config' / 'zoho_gl_mapping.yaml'
    with open(mapping_file, 'r') as f:
        mapping_config = yaml.safe_load(f)
        clearing_account_id = mapping_config['gl_account_mapping'].get('Amazon.ca Clearing')
    
    if not clearing_account_id:
        print("[ERROR] Clearing account ID not found in mapping file")
        return
    
    print(f"Clearing Account ID: {clearing_account_id}")
    print()
    
    zoho = ZohoBooks()
    
    # Get clearing account balance
    print("Fetching clearing account balance from Zoho...")
    account_info = get_account_balance(zoho, clearing_account_id)
    
    if account_info['error']:
        print(f"[ERROR] Could not get account balance: {account_info['error']}")
        return
    
    print(f"Account Name: {account_info['account_name']}")
    print(f"Account Type: {account_info['account_type']}")
    print(f"Current Balance: ${account_info['balance']:,.2f}")
    print()
    
    # Get invoice balances
    print("Fetching invoice balances from Zoho...")
    invoice_summary = get_all_invoices_balance(zoho)
    
    if invoice_summary['error']:
        print(f"[ERROR] Could not get invoice balances: {invoice_summary['error']}")
    else:
        print(f"Invoice Count: {invoice_summary['invoice_count']}")
        print(f"Total Invoice Amount: ${invoice_summary['total_amount']:,.2f}")
        print(f"Total Paid: ${invoice_summary['total_paid']:,.2f}")
        print(f"Total Outstanding Balance: ${invoice_summary['total_balance']:,.2f}")
        print(f"Unpaid Invoices: {invoice_summary['unpaid_count']}")
        print()
    
    # Get payment totals
    print("Fetching payment totals from Zoho...")
    payment_summary = get_all_payments_total(zoho)
    
    if payment_summary['error']:
        print(f"[ERROR] Could not get payment totals: {payment_summary['error']}")
    else:
        print(f"Payment Count: {payment_summary['payment_count']}")
        print(f"Total Payment Amount: ${payment_summary['total_amount']:,.2f}")
        print()
    
    # Calculate differences
    print("="*80)
    print("BALANCE VERIFICATION")
    print("="*80)
    
    clearing_balance = account_info['balance']
    invoice_balance = invoice_summary.get('total_balance', 0.0)
    invoice_total = invoice_summary.get('total_amount', 0.0)
    payment_total = payment_summary.get('total_amount', 0.0)
    
    print(f"\nClearing Account Balance: ${clearing_balance:,.2f}")
    print(f"Invoice Outstanding Balance: ${invoice_balance:,.2f}")
    print(f"Invoice Total: ${invoice_total:,.2f}")
    print(f"Payment Total: ${payment_total:,.2f}")
    print()
    
    # Check if invoices = payments
    inv_pay_diff = abs(invoice_total - payment_total)
    print(f"Invoice/Payment Difference: ${inv_pay_diff:,.2f}")
    
    if inv_pay_diff < 1.0:
        print("[PASS] Invoice totals match payment totals (within $1.00)")
    else:
        print(f"[FAIL] Invoice totals don't match payment totals (${inv_pay_diff:,.2f} difference)")
    
    # Check if clearing account is balanced
    if abs(clearing_balance) < 0.01:
        print("[PASS] Clearing account balance is $0.00")
    else:
        print(f"[FAIL] Clearing account balance is NOT zero (${clearing_balance:,.2f})")
    
    # Check if all invoices are paid
    if invoice_summary.get('unpaid_count', 0) == 0:
        print("[PASS] All invoices are fully paid")
    else:
        print(f"[WARN] {invoice_summary.get('unpaid_count', 0)} invoice(s) still have outstanding balance")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    all_balanced = (
        abs(clearing_balance) < 0.01 and
        invoice_summary.get('unpaid_count', 0) == 0 and
        inv_pay_diff < 1.0
    )
    
    if all_balanced:
        print("\n[PASS] ALL REMITTANCES ARE BALANCED AND MATCHED!")
        print("  - Clearing account balance = $0.00")
        print("  - All invoices fully paid")
        print("  - Invoice totals = Payment totals")
    else:
        print("\n[REVIEW REQUIRED] Some balance issues found:")
        if abs(clearing_balance) >= 0.01:
            print(f"  - Clearing account balance: ${clearing_balance:,.2f} (should be $0.00)")
        if invoice_summary.get('unpaid_count', 0) > 0:
            print(f"  - {invoice_summary.get('unpaid_count', 0)} unpaid invoice(s) with ${invoice_balance:,.2f} outstanding")
        if inv_pay_diff >= 1.0:
            print(f"  - Invoice/Payment difference: ${inv_pay_diff:,.2f}")
    
    # Save report
    report_data = {
        'check_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'clearing_account_id': clearing_account_id,
        'clearing_account_name': account_info['account_name'],
        'clearing_balance': round(float(clearing_balance), 2),
        'invoice_count': invoice_summary.get('invoice_count', 0),
        'invoice_total': round(float(invoice_total), 2),
        'invoice_balance': round(float(invoice_balance), 2),
        'unpaid_invoice_count': invoice_summary.get('unpaid_count', 0),
        'payment_count': payment_summary.get('payment_count', 0),
        'payment_total': round(float(payment_total), 2),
        'invoice_payment_difference': round(float(inv_pay_diff), 2),
        'all_balanced': all_balanced
    }
    
    report_df = pd.DataFrame([report_data])
    report_file = Path("outputs") / f"Clearing_Account_Balance_Check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    report_df.to_csv(report_file, index=False)
    print(f"\n[OK] Report saved to: {report_file}")


if __name__ == "__main__":
    main()



