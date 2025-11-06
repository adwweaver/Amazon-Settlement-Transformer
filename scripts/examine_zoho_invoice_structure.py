#!/usr/bin/env python3
"""
Examine actual Zoho invoice structure to understand how to properly match invoices.
This helps determine if 1:1 matching is possible or if invoices are grouped differently.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks


def examine_zoho_invoices():
    """Examine actual invoice structure in Zoho."""
    zoho = ZohoBooks()
    
    # Get invoices for one settlement to see structure
    settlement_id = '24288684721'
    
    print("=" * 80)
    print(f"EXAMINING ZOHO INVOICES FOR SETTLEMENT {settlement_id}")
    print("=" * 80)
    
    try:
        result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200')
        
        if result.get('code') != 0:
            print(f"Error: {result}")
            return
        
        invoices = result.get('invoices', [])
        print(f"\nFound {len(invoices)} invoices in Zoho for settlement {settlement_id}\n")
        
        # Examine first few invoices in detail
        for i, inv in enumerate(invoices[:5], 1):
            print(f"Invoice #{i}:")
            print(f"  Invoice ID: {inv.get('invoice_id')}")
            print(f"  Invoice Number: {inv.get('invoice_number')}")
            print(f"  Reference Number: {inv.get('reference_number')}")
            print(f"  Date: {inv.get('date')}")
            print(f"  Total: ${inv.get('total', 0):.2f}")
            print(f"  Line Items Count: {len(inv.get('line_items', []))}")
            
            # Show line items
            line_items = inv.get('line_items', [])
            if line_items:
                print(f"  Line Items:")
                for j, item in enumerate(line_items[:3], 1):  # Show first 3
                    item_name = item.get('name', '')
                    item_id = item.get('item_id', '')
                    quantity = item.get('quantity', 0)
                    rate = item.get('rate', 0)
                    print(f"    {j}. {item_name} (Item ID: {item_id}) - Qty: {quantity}, Rate: ${rate:.2f}")
                if len(line_items) > 3:
                    print(f"    ... and {len(line_items) - 3} more items")
            else:
                print(f"  No line items")
            
            print()
        
        # Summary
        print("\n" + "=" * 80)
        print("ANALYSIS")
        print("=" * 80)
        
        total_line_items = sum(len(inv.get('line_items', [])) for inv in invoices)
        print(f"\nTotal invoices: {len(invoices)}")
        print(f"Total line items across all invoices: {total_line_items}")
        print(f"Average line items per invoice: {total_line_items / len(invoices) if invoices else 0:.1f}")
        
        # Check if invoices are multi-line or single-line
        single_line = sum(1 for inv in invoices if len(inv.get('line_items', [])) == 1)
        multi_line = len(invoices) - single_line
        
        print(f"\nInvoice Types:")
        print(f"  Single-line invoices: {single_line}")
        print(f"  Multi-line invoices: {multi_line}")
        
        # Check if we can match by line item SKU/item_id
        print(f"\nCan we match by line items?")
        print(f"  - Line items have 'item_id' field: {all('item_id' in item for inv in invoices for item in inv.get('line_items', []))}")
        print(f"  - Line items have 'name' field: {all('name' in item for inv in invoices for item in inv.get('line_items', []))}")
        
    except Exception as e:
        print(f"Error examining invoices: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    examine_zoho_invoices()



