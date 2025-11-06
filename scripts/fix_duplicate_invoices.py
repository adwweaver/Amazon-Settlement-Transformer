"""
Fix duplicate invoices for settlement 24391894961
Delete the 4 incorrectly split invoices and recreate as 2 proper multi-line invoices
"""

import pandas as pd
import logging
from pathlib import Path
from zoho_sync import ZohoBooks

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_duplicate_invoices():
    """Delete 4 split invoices and recreate as 2 proper multi-line invoices"""
    
    settlement_id = "24391894961"
    
    # Invoice IDs to delete (the 4 split invoices)
    invoices_to_delete = [
        ('73985000000108347', 'AMZN2360215', 'SALTT30-MELN', 59.99),  # First split
        ('73985000000109216', 'AMZN2360215', 'SALTT30-ULTA', 59.99),  # Second split
        ('73985000000108363', 'AMZN6262637', 'SALTT15-FRUT', 34.99),  # First split
        ('73985000000109232', 'AMZN6262637', 'SALTT30-CLEN', 59.99),  # Second split
    ]
    
    print("=" * 70)
    print("FIXING DUPLICATE INVOICES FOR SETTLEMENT 24391894961")
    print("=" * 70)
    
    zoho = ZohoBooks()
    
    # Step 1: Delete the 4 incorrectly split invoices
    print("\n🗑️  STEP 1: Deleting 4 split invoices...")
    for invoice_id, invoice_num, sku, amount in invoices_to_delete:
        try:
            # First try to void/delete directly
            result = zoho.delete_invoice(invoice_id)
            if result:
                print(f"  ✅ Deleted invoice {invoice_id} ({invoice_num} - {sku} ${amount})")
            else:
                print(f"  ⚠️  Could not delete invoice {invoice_id} (may have payments) - continuing anyway")
        except Exception as e:
            error_msg = str(e)
            if "Payments have been recorded" in error_msg:
                print(f"  ⚠️  Invoice {invoice_id} has payments attached - will need manual cleanup")
            else:
                logger.error(f"Error deleting invoice {invoice_id}: {e}")
                print(f"  ❌ Error: {e}")
    
    # Step 2: Load invoice and payment data
    print("\n📄 STEP 2: Loading invoice and payment data...")
    output_dir = Path(__file__).parent.parent / 'outputs' / settlement_id
    invoice_df = pd.read_csv(output_dir / f"Invoice_{settlement_id}.csv")
    payment_df = pd.read_csv(output_dir / f"Payment_{settlement_id}.csv")
    
    # Filter to just our 2 invoices
    target_invoices = ['AMZN2360215', 'AMZN6262637']
    invoice_subset = invoice_df[invoice_df['Invoice Number'].isin(target_invoices)]
    payment_subset = payment_df[payment_df['Invoice Number'].isin(target_invoices)]
    
    print(f"  Found {len(invoice_subset)} invoice lines for {len(target_invoices)} invoices")
    print(f"  Found {len(payment_subset)} payments")
    
    # Step 3: Get customer and item IDs
    print("\n🔍 STEP 3: Looking up customer and items...")
    customer_id = zoho.get_customer_id("Amazon.ca")
    print(f"  ✅ Customer ID: {customer_id}")
    
    # SKU mappings
    sku_mapping = {
        'SALTT30-MELN': None,
        'SALTT30-ULTA': None,
        'SALTT15-FRUT': None,
        'SALTT30-CLEN': None,
    }
    
    for sku in sku_mapping.keys():
        item_id = zoho.get_item_id(sku)
        sku_mapping[sku] = item_id
        print(f"  ✅ {sku} → Item ID: {item_id}")
    
    # Step 4: Create 2 proper multi-line invoices
    print("\n📝 STEP 4: Creating 2 multi-line invoices...")
    invoice_map = {}
    
    for invoice_number in target_invoices:
        group = invoice_subset[invoice_subset['Invoice Number'] == invoice_number]
        
        # Build line items
        line_items = []
        for idx, row in group.iterrows():
            line_items.append({
                "item_id": sku_mapping[row['SKU']],
                "quantity": float(row['Quantity']),
                "rate": float(row['Item Price']),
                "description": str(row.get('Notes', ''))
            })
        
        first_row = group.iloc[0]
        total_amount = group['Invoice Line Amount'].sum()
        
        invoice_payload = {
            "customer_id": customer_id,
            "customer_name": str(first_row['Customer Name']),
            "date": str(first_row['Invoice Date']),
            "reference_number": str(first_row['Reference Number']),
            "line_items": line_items,
            "notes": f"Amazon Order {str(first_row.get('merchant_order_id', ''))} - Settlement {settlement_id}"
        }
        
        invoice_id = zoho.create_invoice(invoice_payload, dry_run=False)
        if invoice_id:
            invoice_map[invoice_number] = invoice_id
            print(f"  ✅ Invoice {invoice_number} created (ID: {invoice_id}, {len(line_items)} lines, ${total_amount:.2f})")
        else:
            print(f"  ❌ Failed to create invoice {invoice_number}")
            return
    
    # Step 5: Post payments
    print("\n💰 STEP 5: Posting payments...")
    for idx, row in payment_subset.iterrows():
        invoice_number = row['Invoice Number']
        zoho_invoice_id = invoice_map.get(invoice_number)
        
        if not zoho_invoice_id:
            print(f"  ⚠️  Invoice {invoice_number} not found in map")
            continue
        
        payment_payload = {
            "customer_id": customer_id,
            "customer_name": row['Customer Name'],
            "payment_mode": row.get('Payment Mode', 'Direct Deposit'),
            "amount": float(row['Payment Amount']),
            "date": row['Payment Date'],
            "reference_number": row['Reference Number'],
            "description": row.get('Description', ''),
            "invoices": [{
                "invoice_id": zoho_invoice_id,
                "amount_applied": float(row['Payment Amount'])
            }]
        }
        
        payment_id = zoho.create_payment(payment_payload, dry_run=False)
        if payment_id:
            print(f"  ✅ Payment ${row['Payment Amount']:.2f} posted for {invoice_number} (ID: {payment_id})")
        else:
            print(f"  ❌ Failed to post payment for {invoice_number}")
    
    print("\n" + "=" * 70)
    print("✅ CLEANUP COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    fix_duplicate_invoices()
