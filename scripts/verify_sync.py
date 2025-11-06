"""
Verification & Reconciliation Script
Pulls data from Zoho Books and compares against local settlement data
"""

import pandas as pd
from pathlib import Path
import logging
from zoho_sync import ZohoBooks
from datetime import datetime
import sys

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def load_local_settlement_summary():
    """Load and summarize all local settlement data"""
    settlements = {}
    
    # List of all settlements
    settlement_ids = [
        '23874396421',
        '23874397121', 
        '24288684721',
        '24391894961',
        '24495221541',
        '24596907561'
    ]
    
    for settlement_id in settlement_ids:
        output_dir = Path(f'outputs/{settlement_id}')
        
        if not output_dir.exists():
            continue
            
        settlement_data = {
            'settlement_id': settlement_id,
            'journal_lines': 0,
            'journal_debits': 0.0,
            'journal_credits': 0.0,
            'invoice_count': 0,
            'invoice_total': 0.0,
            'payment_count': 0,
            'payment_total': 0.0
        }
        
        # Read journal
        journal_file = output_dir / f'{settlement_id}_journal.csv'
        if journal_file.exists():
            try:
                journal_df = pd.read_csv(journal_file)
                settlement_data['journal_lines'] = len(journal_df)
                # Handle potential NaN values
                settlement_data['journal_debits'] = journal_df['Debit'].fillna(0).sum()
                settlement_data['journal_credits'] = journal_df['Credit'].fillna(0).sum()
            except Exception as e:
                logger.warning(f"Could not read journal file for {settlement_id}: {e}")
        
        # Read invoices
        invoice_file = output_dir / f'{settlement_id}_invoice.csv'
        if invoice_file.exists():
            try:
                invoice_df = pd.read_csv(invoice_file)
                # Group by invoice number to get unique invoices
                if 'Invoice Number' in invoice_df.columns and 'Amount' in invoice_df.columns:
                    unique_invoices = invoice_df.groupby('Invoice Number')['Amount'].sum()
                    settlement_data['invoice_count'] = len(unique_invoices)
                    settlement_data['invoice_total'] = unique_invoices.sum()
            except Exception as e:
                logger.warning(f"Could not read invoice file for {settlement_id}: {e}")
        
        # Read payments
        payment_file = output_dir / f'{settlement_id}_payment.csv'
        if payment_file.exists():
            try:
                payment_df = pd.read_csv(payment_file)
                settlement_data['payment_count'] = len(payment_df)
                if 'Payment Amount' in payment_df.columns:
                    settlement_data['payment_total'] = payment_df['Payment Amount'].fillna(0).sum()
            except Exception as e:
                logger.warning(f"Could not read payment file for {settlement_id}: {e}")
        
        settlements[settlement_id] = settlement_data
    
    return settlements


def get_zoho_journals(zoho, start_date='2024-01-01'):
    """Get all journals from Zoho Books with pagination"""
    logger.info("\n🔍 Fetching journals from Zoho Books...")
    
    all_journals = []
    page = 1
    per_page = 200
    
    try:
        while True:
            # Get journals with pagination
            response = zoho._api_request('GET', f'journals?page={page}&per_page={per_page}', {})
            
            if response.get('code') == 0:
                journals = response.get('journals', [])
                
                if not journals:
                    break
                
                # Filter for our Amazon settlement journals
                settlement_journals = [
                    j for j in journals 
                    if j.get('reference_number', '').startswith('AMZ-SETTLE-')
                ]
                
                all_journals.extend(settlement_journals)
                
                # Check if there are more pages
                page_context = response.get('page_context', {})
                if not page_context.get('has_more_page', False):
                    break
                
                page += 1
            else:
                logger.error(f"Failed to get journals: {response}")
                break
        
        return all_journals
    except Exception as e:
        logger.error(f"Error fetching journals: {e}")
        return []


def get_zoho_invoices(zoho, customer_id):
    """Get all invoices for Amazon.ca customer with pagination"""
    logger.info("\n🔍 Fetching invoices from Zoho Books...")
    
    all_invoices = []
    page = 1
    per_page = 200
    
    try:
        while True:
            # Get invoices for specific customer with pagination
            response = zoho._api_request('GET', f'invoices?customer_id={customer_id}&page={page}&per_page={per_page}', {})
            
            if response.get('code') == 0:
                invoices = response.get('invoices', [])
                
                if not invoices:
                    break
                
                # Filter for our Amazon invoices (AMZN prefix)
                amazon_invoices = [
                    i for i in invoices 
                    if i.get('invoice_number', '').startswith('AMZN')
                ]
                
                all_invoices.extend(amazon_invoices)
                
                # Check if there are more pages
                page_context = response.get('page_context', {})
                if not page_context.get('has_more_page', False):
                    break
                
                page += 1
            else:
                logger.error(f"Failed to get invoices: {response}")
                break
        
        return all_invoices
    except Exception as e:
        logger.error(f"Error fetching invoices: {e}")
        return []


def get_zoho_payments(zoho, customer_id):
    """Get all payments (customer payments) for Amazon.ca with pagination"""
    logger.info("\n🔍 Fetching payments from Zoho Books...")
    
    all_payments = []
    page = 1
    per_page = 200
    
    try:
        while True:
            # Get customer payments with pagination
            response = zoho._api_request('GET', f'customerpayments?customer_id={customer_id}&page={page}&per_page={per_page}', {})
            
            if response.get('code') == 0:
                payments = response.get('customerpayments', [])
                
                if not payments:
                    break
                
                all_payments.extend(payments)
                
                # Check if there are more pages
                page_context = response.get('page_context', {})
                if not page_context.get('has_more_page', False):
                    break
                
                page += 1
            else:
                logger.error(f"Failed to get payments: {response}")
                break
        
        return all_payments
    except Exception as e:
        logger.error(f"Error fetching payments: {e}")
        return []


def print_reconciliation_report(local_data, zoho_journals, zoho_invoices, zoho_payments):
    """Print detailed reconciliation report"""
    
    print("\n" + "="*80)
    print("RECONCILIATION REPORT - LOCAL vs ZOHO BOOKS")
    print("="*80)
    
    # Summary totals
    print("\n📊 OVERALL SUMMARY")
    print("-" * 80)
    
    local_journal_total = sum(s['journal_debits'] for s in local_data.values())
    local_invoice_total = sum(s['invoice_total'] for s in local_data.values())
    local_payment_total = sum(s['payment_total'] for s in local_data.values())
    local_invoice_count = sum(s['invoice_count'] for s in local_data.values())
    local_payment_count = sum(s['payment_count'] for s in local_data.values())
    
    zoho_journal_total = sum(j.get('total', 0) for j in zoho_journals)
    zoho_invoice_total = sum(float(i.get('total', 0)) for i in zoho_invoices)
    zoho_payment_total = sum(float(p.get('amount', 0)) for p in zoho_payments)
    
    print(f"\nJournals:")
    print(f"  Local:  {len(local_data)} settlements, ${local_journal_total:,.2f} (debits)")
    print(f"  Zoho:   {len(zoho_journals)} journals, ${zoho_journal_total:,.2f}")
    print(f"  Match:  {'✅' if len(zoho_journals) == len(local_data) else '❌'}")
    
    print(f"\nInvoices:")
    print(f"  Local:  {local_invoice_count} invoices, ${local_invoice_total:,.2f}")
    print(f"  Zoho:   {len(zoho_invoices)} invoices, ${zoho_invoice_total:,.2f}")
    print(f"  Match:  {'✅' if abs(zoho_invoice_total - local_invoice_total) < 1.0 else '❌'}")
    
    print(f"\nPayments:")
    print(f"  Local:  {local_payment_count} payments, ${local_payment_total:,.2f}")
    print(f"  Zoho:   {len(zoho_payments)} payments, ${zoho_payment_total:,.2f}")
    print(f"  Match:  {'✅' if abs(zoho_payment_total - local_payment_total) < 1.0 else '❌'}")
    
    # Per-settlement detail
    print("\n" + "="*80)
    print("SETTLEMENT-BY-SETTLEMENT DETAIL")
    print("="*80)
    
    for settlement_id, data in sorted(local_data.items()):
        print(f"\n📦 Settlement {settlement_id}")
        print("-" * 80)
        
        # Find matching journal in Zoho
        matching_journal = next(
            (j for j in zoho_journals if j.get('reference_number') == f'AMZ-SETTLE-{settlement_id}'),
            None
        )
        
        if matching_journal:
            journal_status = "✅ Found in Zoho"
            journal_id = matching_journal.get('journal_id')
            zoho_journal_total = matching_journal.get('total', 0)
        else:
            journal_status = "❌ NOT FOUND in Zoho"
            journal_id = "N/A"
            zoho_journal_total = 0
        
        print(f"  Journal:  {journal_status}")
        print(f"    Local:  {data['journal_lines']} lines, ${data['journal_debits']:,.2f} debits")
        if matching_journal:
            print(f"    Zoho:   ID {journal_id}, ${zoho_journal_total:,.2f}")
            print(f"    Balanced: {'✅' if abs(data['journal_debits'] - data['journal_credits']) < 0.01 else '❌'}")
        
        print(f"\n  Invoices: {data['invoice_count']} invoices, ${data['invoice_total']:,.2f}")
        print(f"  Payments: {data['payment_count']} payments, ${data['payment_total']:,.2f}")
    
    print("\n" + "="*80)
    print("RECONCILIATION CHECKSUMS")
    print("="*80)
    
    # Key checksums
    journal_match = abs(len(zoho_journals) - len(local_data)) == 0
    invoice_amount_match = abs(zoho_invoice_total - local_invoice_total) < 1.0
    payment_amount_match = abs(zoho_payment_total - local_payment_total) < 1.0
    
    print(f"\n✅ Journal count matches:        {'PASS' if journal_match else 'FAIL'}")
    print(f"✅ Invoice totals match (±$1):   {'PASS' if invoice_amount_match else 'FAIL'}")
    print(f"✅ Payment totals match (±$1):   {'PASS' if payment_amount_match else 'FAIL'}")
    
    if journal_match and invoice_amount_match and payment_amount_match:
        print("\n🎉 ALL CHECKSUMS PASSED - Data is in sync!")
    else:
        print("\n⚠️  CHECKSUMS FAILED - Review discrepancies above")
    
    print("\n" + "="*80)


def main():
    """Main verification routine"""
    print("="*80)
    print("AMAZON SETTLEMENT SYNC VERIFICATION")
    print("="*80)
    
    # Load local data
    logger.info("\n📂 Loading local settlement data...")
    local_data = load_local_settlement_summary()
    logger.info(f"✅ Loaded {len(local_data)} settlements from local files")
    
    # Connect to Zoho
    logger.info("\n🔐 Connecting to Zoho Books API...")
    zoho = ZohoBooks()
    
    # Get Amazon.ca customer ID
    customer_id = zoho.get_customer_id("Amazon.ca")
    logger.info(f"✅ Found Amazon.ca customer (ID: {customer_id})")
    
    # Fetch Zoho data
    zoho_journals = get_zoho_journals(zoho)
    zoho_invoices = get_zoho_invoices(zoho, customer_id)
    zoho_payments = get_zoho_payments(zoho, customer_id)
    
    logger.info(f"✅ Retrieved {len(zoho_journals)} journals from Zoho")
    logger.info(f"✅ Retrieved {len(zoho_invoices)} invoices from Zoho")
    logger.info(f"✅ Retrieved {len(zoho_payments)} payments from Zoho")
    
    # Generate reconciliation report
    print_reconciliation_report(local_data, zoho_journals, zoho_invoices, zoho_payments)


if __name__ == "__main__":
    main()
