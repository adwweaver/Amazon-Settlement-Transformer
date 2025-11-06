#!/usr/bin/env python3
"""Check if a specific invoice exists in Zoho."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks

zoho = ZohoBooks()

# Check for settlement 23874397121 invoices
settlement_id = "23874397121"
invoice_number = "AMZN6751437"

print(f"Checking for invoice {invoice_number} in settlement {settlement_id}...")

# Try by reference_number
try:
    result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
    if result.get('code') == 0:
        invoices = result.get('invoices', [])
        print(f"\nFound {len(invoices)} invoice(s) for settlement {settlement_id}:")
        for inv in invoices:
            inv_num = inv.get('invoice_number', '')
            inv_id = inv.get('invoice_id', '')
            ref_num = inv.get('reference_number', '')
            total = inv.get('total', 0)
            print(f"  Invoice Number: {inv_num}")
            print(f"  Invoice ID: {inv_id}")
            print(f"  Reference Number: {ref_num}")
            print(f"  Total: ${total}")
            print(f"  Matches {invoice_number}: {inv_num == invoice_number}")
            print()
except Exception as e:
    print(f"Error: {e}")



