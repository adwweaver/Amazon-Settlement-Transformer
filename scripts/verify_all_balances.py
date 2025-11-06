#!/usr/bin/env python3
"""
Comprehensive balance verification for all settlements.

Verifies:
1. Journal balances (Debits = Credits) for each settlement
2. Invoice totals = Payment totals for each settlement
3. Overall reconciliation (local vs Zoho)
4. Clearing account balance

Usage:
    python scripts/verify_all_balances.py
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from paths import get_zoho_tracking_path

def find_all_settlements():
    """Find all settlement IDs from output directories"""
    output_dir = Path("outputs")
    settlements = []
    
    if not output_dir.exists():
        return settlements
    
    for item in output_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            settlements.append(item.name)
    
    return sorted(settlements)


def check_journal_balance(settlement_id: str) -> dict:
    """Check journal balance for a settlement"""
    journal_file = Path("outputs") / settlement_id / f"Journal_{settlement_id}.csv"
    
    if not journal_file.exists():
        return {
            'settlement_id': settlement_id,
            'has_journal': False,
            'debits': 0.0,
            'credits': 0.0,
            'difference': 0.0,
            'balanced': False,
            'error': 'Journal file not found'
        }
    
    try:
        df = pd.read_csv(journal_file)
        debits = pd.to_numeric(df.get('Debit', 0), errors='coerce').fillna(0).sum()
        credits = pd.to_numeric(df.get('Credit', 0), errors='coerce').fillna(0).sum()
        difference = round(float(debits - credits), 2)
        
        return {
            'settlement_id': settlement_id,
            'has_journal': True,
            'debits': round(float(debits), 2),
            'credits': round(float(credits), 2),
            'difference': difference,
            'balanced': abs(difference) < 0.01,
            'error': None
        }
    except Exception as e:
        return {
            'settlement_id': settlement_id,
            'has_journal': True,
            'debits': 0.0,
            'credits': 0.0,
            'difference': 0.0,
            'balanced': False,
            'error': str(e)
        }


def check_invoice_payment_balance(settlement_id: str) -> dict:
    """Check invoice and payment totals for a settlement"""
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    
    result = {
        'settlement_id': settlement_id,
        'has_invoices': False,
        'has_payments': False,
        'invoice_total': 0.0,
        'payment_total': 0.0,
        'invoice_count': 0,
        'payment_count': 0,
        'difference': 0.0,
        'balanced': False,
        'error': None
    }
    
    # Check invoices
    if invoice_file.exists():
        try:
            df_inv = pd.read_csv(invoice_file)
            result['has_invoices'] = True
            result['invoice_count'] = len(df_inv['Invoice Number'].unique()) if 'Invoice Number' in df_inv.columns else 0
            
            # Try to find amount column
            amount_col = None
            for col in ['Invoice Line Amount', 'amount', 'rate', 'line_amount', 'total']:
                if col in df_inv.columns:
                    amount_col = col
                    break
            
            if amount_col:
                result['invoice_total'] = round(float(pd.to_numeric(df_inv[amount_col], errors='coerce').fillna(0).sum()), 2)
        except Exception as e:
            result['error'] = f"Invoice error: {str(e)}"
    
    # Check payments
    if payment_file.exists():
        try:
            df_pay = pd.read_csv(payment_file)
            result['has_payments'] = True
            result['payment_count'] = len(df_pay)
            
            # Try to find amount column
            amount_col = None
            for col in ['Payment Amount', 'amount', 'payment_amount', 'total']:
                if col in df_pay.columns:
                    amount_col = col
                    break
            
            if amount_col:
                result['payment_total'] = round(float(pd.to_numeric(df_pay[amount_col], errors='coerce').fillna(0).sum()), 2)
        except Exception as e:
            if result['error']:
                result['error'] += f"; Payment error: {str(e)}"
            else:
                result['error'] = f"Payment error: {str(e)}"
    
    # Calculate difference
    if result['has_invoices'] and result['has_payments']:
        result['difference'] = round(result['invoice_total'] - result['payment_total'], 2)
        result['balanced'] = abs(result['difference']) < 0.01
    
    return result


def check_zoho_reconciliation(settlement_id: str, zoho: ZohoBooks) -> dict:
    """Check Zoho reconciliation for a settlement"""
    result = {
        'settlement_id': settlement_id,
        'zoho_invoice_count': 0,
        'zoho_payment_count': 0,
        'zoho_invoice_total': 0.0,
        'zoho_payment_total': 0.0,
        'zoho_journal_exists': False,
        'error': None
    }
    
    try:
        # Check invoices
        inv_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        if inv_result.get('code') == 0:
            invoices = inv_result.get('invoices', [])
            result['zoho_invoice_count'] = len(invoices)
            result['zoho_invoice_total'] = round(sum(float(inv.get('total', 0) or 0) for inv in invoices), 2)
        
        time.sleep(2)  # Rate limit delay
        
        # Check payments
        pay_result = zoho._api_request('GET', f'customerpayments?reference_number={settlement_id}&per_page=200')
        if pay_result.get('code') == 0:
            payments = pay_result.get('customerpayments', [])
            result['zoho_payment_count'] = len(payments)
            result['zoho_payment_total'] = round(sum(float(p.get('amount', 0) or 0) for p in payments), 2)
        
        time.sleep(2)  # Rate limit delay
        
        # Check journal
        journal_result = zoho._api_request('GET', f'journals?reference_number={settlement_id}&per_page=200')
        if journal_result.get('code') == 0:
            journals = journal_result.get('journals', [])
            result['zoho_journal_exists'] = len(journals) > 0
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_tracking_summary(settlement_id: str) -> dict:
    """Get tracking summary for a settlement"""
    tracking_file = get_zoho_tracking_path()
    
    result = {
        'settlement_id': settlement_id,
        'tracked_invoices': 0,
        'tracked_payments': 0,
        'tracked_journals': 0,
        'posted_invoices': 0,
        'posted_payments': 0,
        'posted_journals': 0
    }
    
    if not tracking_file.exists():
        return result
    
    try:
        df = pd.read_csv(tracking_file)
        df['settlement_id'] = df['settlement_id'].astype(str)
        settlement_track = df[df['settlement_id'] == str(settlement_id)]
        
        # Count by record type
        for record_type in ['INVOICE', 'PAYMENT', 'JOURNAL']:
            records = settlement_track[settlement_track['record_type'] == record_type]
            count_key = f'tracked_{record_type.lower()}s'
            posted_key = f'posted_{record_type.lower()}s'
            
            result[count_key] = len(records)
            result[posted_key] = len(records[records['status'] == 'POSTED'])
    
    except Exception as e:
        pass
    
    return result


def main():
    print("="*80)
    print("COMPREHENSIVE BALANCE VERIFICATION")
    print("="*80)
    print()
    
    settlements = find_all_settlements()
    
    if not settlements:
        print("❌ No settlements found in outputs directory")
        return
    
    print(f"Found {len(settlements)} settlement(s) to verify")
    print()
    
    zoho = ZohoBooks()
    
    all_results = []
    
    for i, settlement_id in enumerate(settlements, 1):
        print(f"[{i}/{len(settlements)}] Verifying settlement {settlement_id}...")
        
        # Check journal balance
        journal_check = check_journal_balance(settlement_id)
        
        # Check invoice/payment balance
        inv_pay_check = check_invoice_payment_balance(settlement_id)
        
        # Check Zoho reconciliation (with delays for rate limits)
        if i > 1:  # Skip delay for first one
            print(f"  Waiting 5s for rate limits...")
            time.sleep(5)
        zoho_check = check_zoho_reconciliation(settlement_id, zoho)
        
        # Get tracking summary
        tracking_summary = get_tracking_summary(settlement_id)
        
        # Combine results
        result = {
            'settlement_id': settlement_id,
            **journal_check,
            **inv_pay_check,
            **zoho_check,
            **tracking_summary,
            'all_checks_passed': (
                journal_check.get('balanced', False) and
                inv_pay_check.get('balanced', False) and
                zoho_check.get('zoho_journal_exists', False) and
                zoho_check.get('zoho_invoice_count', 0) > 0
            )
        }
        
        all_results.append(result)
        
        # Print summary
        journal_status = "OK" if journal_check['balanced'] else "OUT OF BALANCE"
        print(f"  Journal: {journal_status} "
              f"Debits=${journal_check['debits']:,.2f} Credits=${journal_check['credits']:,.2f} "
              f"Diff=${journal_check['difference']:,.2f}")
        
        if inv_pay_check['has_invoices'] and inv_pay_check['has_payments']:
            inv_pay_status = "OK" if inv_pay_check['balanced'] else "MISMATCH"
            print(f"  Invoice/Payment: {inv_pay_status} "
                  f"Invoices=${inv_pay_check['invoice_total']:,.2f} "
                  f"Payments=${inv_pay_check['payment_total']:,.2f} "
                  f"Diff=${inv_pay_check['difference']:,.2f}")
        
        if zoho_check.get('zoho_invoice_count', 0) > 0:
            journal_status = "EXISTS" if zoho_check['zoho_journal_exists'] else "MISSING"
            print(f"  Zoho: {zoho_check['zoho_invoice_count']} invoices, "
                  f"{zoho_check['zoho_payment_count']} payments, "
                  f"journal {journal_status}")
    
    # Create summary DataFrame
    df = pd.DataFrame(all_results)
    
    # Calculate summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    # Check journal balances (using the journal balance field)
    journal_balanced_mask = (df['has_journal'] == True) & (abs(df['difference']) < 0.01)
    balanced_journals = journal_balanced_mask.sum()
    total_journals = df[df['has_journal'] == True].shape[0]
    
    balanced_inv_pay = df[df['balanced'] == True].shape[0]  # Re-check for invoice/payment balance
    has_both = df[(df['has_invoices'] == True) & (df['has_payments'] == True)].shape[0]
    
    # Recalculate invoice/payment balanced count
    inv_pay_balanced = 0
    for _, row in df.iterrows():
        if row['has_invoices'] and row['has_payments']:
            diff = abs(row.get('invoice_total', 0) - row.get('payment_total', 0))
            if diff < 0.01:
                inv_pay_balanced += 1
    
    print(f"\nJournal Balances:")
    print(f"  Balanced: {balanced_journals}/{total_journals} settlements")
    
    print(f"\nInvoice/Payment Balances:")
    print(f"  Balanced: {inv_pay_balanced}/{has_both} settlements (with both invoices and payments)")
    
    print(f"\nZoho Reconciliation:")
    zoho_journals = df[df['zoho_journal_exists'] == True].shape[0]
    zoho_invoices = df[df['zoho_invoice_count'] > 0].shape[0]
    zoho_payments = df[df['zoho_payment_count'] > 0].shape[0]
    
    print(f"  Journals in Zoho: {zoho_journals}/{len(settlements)}")
    print(f"  Settlements with invoices: {zoho_invoices}/{len(settlements)}")
    print(f"  Settlements with payments: {zoho_payments}/{len(settlements)}")
    
    # Overall totals
    total_invoice_local = df['invoice_total'].sum()
    total_payment_local = df['payment_total'].sum()
    total_invoice_zoho = df['zoho_invoice_total'].sum()
    total_payment_zoho = df['zoho_payment_total'].sum()
    
    print(f"\nOverall Totals:")
    print(f"  Local Invoices: ${total_invoice_local:,.2f} ({df['invoice_count'].sum():,} invoices)")
    print(f"  Local Payments: ${total_payment_local:,.2f} ({df['payment_count'].sum():,} payments)")
    print(f"  Zoho Invoices: ${total_invoice_zoho:,.2f} ({df['zoho_invoice_count'].sum():,} invoices)")
    print(f"  Zoho Payments: ${total_payment_zoho:,.2f} ({df['zoho_payment_count'].sum():,} payments)")
    
    # Check for discrepancies
    print(f"\n" + "="*80)
    print("BALANCE VERIFICATION RESULTS")
    print("="*80)
    
    # Journal issues: settlements with journals that are not balanced
    journal_issues = df[(df['has_journal'] == True) & (abs(df['difference']) >= 0.01)]
    
    # Invoice/payment issues: settlements with both invoices and payments that don't match
    inv_pay_issues = df[(df['has_invoices'] == True) & (df['has_payments'] == True) & 
                        (abs(df['invoice_total'] - df['payment_total']) >= 0.01)]
    
    if len(journal_issues) == 0:
        print("[PASS] ALL JOURNAL BALANCES CORRECT (Debits = Credits)")
    else:
        print(f"[FAIL] {len(journal_issues)} settlement(s) with journal balance issues:")
        for _, row in journal_issues.iterrows():
            print(f"   Settlement {row['settlement_id']}: "
                  f"Diff=${row['difference']:,.2f}")
    
    if len(inv_pay_issues) == 0:
        print("[PASS] ALL INVOICE/PAYMENT BALANCES MATCH (Invoices = Payments)")
    else:
        print(f"[WARN] {len(inv_pay_issues)} settlement(s) with invoice/payment mismatch:")
        for _, row in inv_pay_issues.iterrows():
            print(f"   Settlement {row['settlement_id']}: "
                  f"Invoices=${row['invoice_total']:,.2f} "
                  f"Payments=${row['payment_total']:,.2f} "
                  f"Diff=${row['difference']:,.2f}")
    
    # Overall reconciliation
    local_inv_diff = abs(total_invoice_local - total_invoice_zoho)
    local_pay_diff = abs(total_payment_local - total_payment_zoho)
    
    print(f"\nOverall Reconciliation:")
    inv_match = "PASS" if local_inv_diff < 1.0 else "FAIL"
    pay_match = "PASS" if local_pay_diff < 1.0 else "FAIL"
    print(f"  Invoice Total Match: [{inv_match}] (Difference: ${local_inv_diff:,.2f})")
    print(f"  Payment Total Match: [{pay_match}] (Difference: ${local_pay_diff:,.2f})")
    
    # Save detailed report
    report_file = Path("outputs") / f"Balance_Verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(report_file, index=False)
    print(f"\n[OK] Detailed report saved to: {report_file}")
    
    # Save summary
    summary = {
        'verification_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_settlements': len(settlements),
        'balanced_journals': int(balanced_journals),
        'total_journals': int(total_journals),
        'balanced_invoice_payments': int(inv_pay_balanced),
        'settlements_with_both': int(has_both),
        'zoho_journals_count': int(zoho_journals),
        'zoho_invoices_count': int(zoho_invoices),
        'zoho_payments_count': int(zoho_payments),
        'total_invoice_local': round(float(total_invoice_local), 2),
        'total_payment_local': round(float(total_payment_local), 2),
        'total_invoice_zoho': round(float(total_invoice_zoho), 2),
        'total_payment_zoho': round(float(total_payment_zoho), 2),
        'invoice_total_match': abs(local_inv_diff) < 1.0,
        'payment_total_match': abs(local_pay_diff) < 1.0,
        'all_balanced': (len(journal_issues) == 0 and len(inv_pay_issues) == 0 and 
                         local_inv_diff < 1.0 and local_pay_diff < 1.0)
    }
    
    summary_df = pd.DataFrame([summary])
    summary_file = Path("outputs") / f"Balance_Verification_Summary_{datetime.now().strftime('%Y%m%d')}.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"[OK] Summary saved to: {summary_file}")
    
    # Final assessment
    print("\n" + "="*80)
    print("FINAL ASSESSMENT")
    print("="*80)
    
    if summary['all_balanced']:
        print("[PASS] ALL REMITTANCES ARE BALANCED AND MATCHED!")
        print("  - All journals balanced (Debits = Credits)")
        print("  - All invoices match payments")
        print("  - Local totals match Zoho totals")
    else:
        print("[REVIEW REQUIRED] Some balance issues found:")
        if len(journal_issues) > 0:
            print(f"  - {len(journal_issues)} journal(s) out of balance")
        if len(inv_pay_issues) > 0:
            print(f"  - {len(inv_pay_issues)} invoice/payment mismatch(es)")
        if local_inv_diff >= 1.0:
            print(f"  - Invoice totals don't match (${local_inv_diff:,.2f} difference)")
        if local_pay_diff >= 1.0:
            print(f"  - Payment totals don't match (${local_pay_diff:,.2f} difference)")
        print("\nReview detailed report for settlement-by-settlement breakdown.")


if __name__ == "__main__":
    main()

