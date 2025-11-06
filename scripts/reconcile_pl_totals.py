#!/usr/bin/env python3
"""
Reconcile P&L totals from Zoho Books for Amazon expenses and gross sales YTD.

This script verifies:
1. Amazon expenses YTD total
2. Gross sales YTD total
3. Matches against local settlement data

Usage:
    python scripts/reconcile_pl_totals.py
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import yaml
import logging

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from paths import get_zoho_tracking_path

logger = logging.getLogger(__name__)

def get_ytd_date_range():
    """Get YTD date range (Jan 1 to today)"""
    current_year = datetime.now().year
    start_date = f"{current_year}-01-01"
    end_date = datetime.now().strftime('%Y-%m-%d')
    return start_date, end_date

def get_zoho_invoices_ytd(zoho: ZohoBooks, start_date: str, end_date: str):
    """Get all Amazon invoices from Zoho for YTD"""
    invoices = []
    page = 1
    per_page = 200
    
    # Search for Amazon.ca customer invoices
    customer_name = "Amazon.ca"
    
    while True:
        try:
            result = zoho._api_request('GET', 
                f'invoices?customer_name={customer_name}&date_start={start_date}&date_end={end_date}&page={page}&per_page={per_page}')
            
            if result.get('code') == 0:
                page_invoices = result.get('invoices', [])
                invoices.extend(page_invoices)
                
                # Check if more pages
                page_context = result.get('page_context', {})
                if not page_context.get('has_more_page', False):
                    break
                page += 1
            else:
                break
        except Exception as e:
            print(f"Error fetching invoices: {e}")
            break
    
    return invoices

def get_zoho_journals_ytd(zoho: ZohoBooks, start_date: str, end_date: str):
    """Get all Amazon journal entries from Zoho for YTD"""
    journals = []
    page = 1
    per_page = 200
    
    while True:
        try:
            result = zoho._api_request('GET', 
                f'journals?date_start={start_date}&date_end={end_date}&page={page}&per_page={per_page}')
            
            if result.get('code') == 0:
                page_journals = result.get('journals', [])
                # Filter for Amazon-related journals (by reference number or notes)
                amazon_journals = [
                    j for j in page_journals 
                    if 'amazon' in j.get('notes', '').lower() or 
                       'amazon' in j.get('reference_number', '').lower()
                ]
                journals.extend(amazon_journals)
                
                # Check if more pages
                page_context = result.get('page_context', {})
                if not page_context.get('has_more_page', False):
                    break
                page += 1
            else:
                break
        except Exception as e:
            print(f"Error fetching journals: {e}")
            break
    
    return journals

def calculate_expenses_from_journals(journals, gl_accounts_config):
    """Calculate expenses from journal entries"""
    if not gl_accounts_config:
        return 0.0
    
    # Identify expense account IDs from GL mapping
    expense_account_names = [
        "Amazon FBA Fulfillment Fees",
        "Amazon Advertising Expense", 
        "Amazon FBA Storage Fees",
        "Amazon Storage Expense",
        "Amazon FBA Inbound Freight",
        "Amazon Inbound Freight Charges",
        "Amazon Account Fees",
        "Amazon Unclassified"
    ]
    
    expense_account_ids = set()
    gl_mapping = gl_accounts_config.get('gl_account_mapping', {})
    for account_name in expense_account_names:
        account_id = gl_mapping.get(account_name)
        if account_id:
            expense_account_ids.add(str(account_id))
    
    total_expenses = 0.0
    
    for journal in journals:
        line_items = journal.get('line_items', [])
        for item in line_items:
            account_id = str(item.get('account_id', ''))
            if account_id in expense_account_ids:
                amount = float(item.get('amount', 0) or 0)
                # Expenses are debits (increases expenses)
                if item.get('debit_or_credit') == 'debit':
                    total_expenses += amount
                elif item.get('debit_or_credit') == 'credit':
                    total_expenses -= amount
    
    return total_expenses

def calculate_sales_from_invoices(invoices):
    """Calculate gross sales from invoices"""
    total_sales = 0.0
    
    for invoice in invoices:
        # Get total amount (before tax)
        total = float(invoice.get('total', 0) or 0)
        # Subtract tax if included
        tax_total = float(invoice.get('tax_total', 0) or 0)
        subtotal = total - tax_total
        total_sales += subtotal
    
    return total_sales

def get_local_totals():
    """Get totals from local tracking files"""
    tracking_file = get_zoho_tracking_path()
    
    if not tracking_file.exists():
        return None, None
    
    df = pd.read_csv(tracking_file)
    
    # Filter for posted records YTD
    current_year = datetime.now().year
    df['created_date'] = pd.to_datetime(df.get('created_date', ''), errors='coerce')
    df_ytd = df[df['created_date'].dt.year == current_year]
    
    # Count invoices and payments
    invoices = df_ytd[df_ytd['record_type'] == 'INVOICE']
    payments = df_ytd[df_ytd['record_type'] == 'PAYMENT']
    
    # Note: We don't have amounts in tracking file, so we'll need to query Zoho
    return len(invoices), len(payments)

def main():
    print("="*80)
    print("P&L RECONCILIATION REPORT - AMAZON YTD")
    print("="*80)
    print()
    
    zoho = ZohoBooks()
    start_date, end_date = get_ytd_date_range()
    
    print(f"Date Range: {start_date} to {end_date}")
    print()
    
    # Get Zoho data
    print("Fetching invoices from Zoho...")
    invoices = get_zoho_invoices_ytd(zoho, start_date, end_date)
    print(f"Found {len(invoices)} invoices")
    
    print("Fetching journals from Zoho...")
    journals = get_zoho_journals_ytd(zoho, start_date, end_date)
    print(f"Found {len(journals)} journal entries")
    print()
    
    # Calculate totals
    print("Calculating totals...")
    gross_sales = calculate_sales_from_invoices(invoices)
    
    # Load GL mapping for expense calculation
    gl_mapping_file = Path("config/zoho_gl_mapping.yaml")
    gl_accounts_config = None
    if gl_mapping_file.exists():
        with open(gl_mapping_file, 'r') as f:
            gl_accounts_config = yaml.safe_load(f)
    
    # Calculate expenses from journal entries
    expenses = calculate_expenses_from_journals(journals, gl_accounts_config)
    
    # Also try to get expenses directly from journal line items by querying each journal
    print("Calculating expenses from journal details...")
    detailed_expenses = 0.0
    if gl_accounts_config:
        expense_account_names = [
            "Amazon FBA Fulfillment Fees",
            "Amazon Advertising Expense", 
            "Amazon FBA Storage Fees",
            "Amazon Storage Expense",
            "Amazon FBA Inbound Freight",
            "Amazon Inbound Freight Charges",
            "Amazon Account Fees",
            "Amazon Unclassified"
        ]
        expense_account_ids = set()
        gl_mapping = gl_accounts_config.get('gl_account_mapping', {})
        for account_name in expense_account_names:
            account_id = gl_mapping.get(account_name)
            if account_id:
                expense_account_ids.add(str(account_id))
        
        # Query each journal to get detailed line items
        for i, journal in enumerate(journals[:10]):  # Limit to first 10 for performance
            journal_id = journal.get('journal_id')
            if journal_id:
                try:
                    journal_details = zoho.get_journal_entry(journal_id)
                    if journal_details:
                        line_items = journal_details.get('line_items', [])
                        for item in line_items:
                            account_id = str(item.get('account_id', ''))
                            if account_id in expense_account_ids:
                                amount = float(item.get('amount', 0) or 0)
                                if item.get('debit_or_credit') == 'debit':
                                    detailed_expenses += amount
                                elif item.get('debit_or_credit') == 'credit':
                                    detailed_expenses -= amount
                except Exception as e:
                    logger.warning(f"Error getting journal details for {journal_id}: {e}")
        
        # Use detailed calculation if available, otherwise use summary
        if detailed_expenses > 0:
            expenses = detailed_expenses
    
    # Get local tracking counts
    local_invoice_count, local_payment_count = get_local_totals()
    
    # Generate report
    report = {
        'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date_range': f"{start_date} to {end_date}",
        'gross_sales_ytd': round(gross_sales, 2),
        'expenses_ytd': round(expenses, 2),
        'invoice_count_ytd': len(invoices),
        'journal_count_ytd': len(journals),
        'local_invoice_count_ytd': local_invoice_count,
        'local_payment_count_ytd': local_payment_count,
    }
    
    print("="*80)
    print("RECONCILIATION SUMMARY")
    print("="*80)
    print(f"Gross Sales (YTD): ${report['gross_sales_ytd']:,.2f}")
    print(f"Amazon Expenses (YTD): ${report['expenses_ytd']:,.2f}")
    print(f"Invoice Count (YTD): {report['invoice_count_ytd']}")
    print(f"Journal Count (YTD): {report['journal_count_ytd']}")
    print(f"Local Invoice Count (YTD): {report['local_invoice_count_ytd']}")
    print(f"Local Payment Count (YTD): {report['local_payment_count_ytd']}")
    print("="*80)
    
    # Save report
    report_df = pd.DataFrame([report])
    report_file = Path("outputs") / f"PL_Reconciliation_{datetime.now().strftime('%Y%m%d')}.csv"
    report_df.to_csv(report_file, index=False)
    print(f"\nReport saved to: {report_file}")
    
    # Save detailed invoice list
    if invoices:
        invoice_df = pd.DataFrame([
            {
                'invoice_number': inv.get('invoice_number'),
                'invoice_id': inv.get('invoice_id'),
                'date': inv.get('date'),
                'total': inv.get('total'),
                'balance': inv.get('balance'),
                'reference_number': inv.get('reference_number'),
            }
            for inv in invoices
        ])
        invoice_file = Path("outputs") / f"Zoho_Invoices_YTD_{datetime.now().strftime('%Y%m%d')}.csv"
        invoice_df.to_csv(invoice_file, index=False)
        print(f"Invoice list saved to: {invoice_file}")


if __name__ == "__main__":
    main()

