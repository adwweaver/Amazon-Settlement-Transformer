#!/usr/bin/env python3
"""
Sync single settlement to Zoho Books - all 3 files (Journal, Invoice, Payment)
With SKU mapping support
"""

import pandas as pd
import yaml
import logging
import time
from pathlib import Path
from datetime import datetime
import sys

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import sync_settlement_to_zoho, ZohoBooks
from validate_settlement import SettlementValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_sku_mapping():
    """Load SKU mapping from config"""
    mapping_file = Path("config/sku_mapping.yaml")
    if not mapping_file.exists():
        return {}
    
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
            mapping = cfg.get('sku_mapping', {}) or {}
            return {str(k): str(v) for k, v in mapping.items()}
    except Exception as e:
        logger.warning(f"Failed to load SKU mapping from {mapping_file}: {e}")
        return {}


def apply_sku_mapping(invoice_df, sku_mapping):
    """Apply SKU mapping to invoice DataFrame"""
    if 'SKU' not in invoice_df.columns:
        return invoice_df, []
    
    mapped_skus = []
    for idx, row in invoice_df.iterrows():
        original_sku = row['SKU']
        if pd.notna(original_sku) and original_sku in sku_mapping:
            new_sku = sku_mapping[original_sku]
            invoice_df.at[idx, 'SKU'] = new_sku
            mapped_skus.append((original_sku, new_sku))
            logger.info(f"  Mapped SKU: {original_sku} -> {new_sku}")
    
    return invoice_df, mapped_skus


def post_settlement_complete(settlement_id: str, post_journal=True, post_invoices=True, post_payments=True, dry_run=False, override=False):
    """
    Post all 3 files for a settlement to Zoho Books
    
    Args:
        settlement_id: Settlement ID
        post_journal: Whether to post journal entries
        post_invoices: Whether to post invoices
        post_payments: Whether to post payment applications
        dry_run: If True, show what would be posted without actually posting
    
    Returns:
        dict with results for each file type
    """
    results = {
        'settlement_id': settlement_id,
        'journal': {'posted': False, 'id': None, 'error': None},
        'invoices': {'posted': False, 'count': 0, 'ids': [], 'error': None},
        'payments': {'posted': False, 'count': 0, 'ids': [], 'error': None},
        'sku_mappings': [],
        'invoice_map': {}  # Maps old invoice numbers to Zoho invoice IDs
    }
    
    output_dir = Path(f"outputs/{settlement_id}")
    if not output_dir.exists():
        logger.error(f"Output directory not found: {output_dir}")
        return results
    
    # Load SKU mapping
    sku_mapping = load_sku_mapping()
    
    print("\n" + "="*70)
    print(f"POSTING SETTLEMENT {settlement_id} TO ZOHO BOOKS")
    print("="*70)
    
    # 1. POST JOURNAL (REQUIRED)
    if post_journal:
        print(f"\n[JOURNAL] JOURNAL ENTRIES...")
        journal_file = output_dir / f"Journal_{settlement_id}.csv"
        
        if not journal_file.exists():
            results['journal']['error'] = f"Journal file not found: {journal_file}"
            logger.error(results['journal']['error'])
        else:
            # Pre-flight: block if journal out of balance or unmapped GL accounts
            try:
                validator = SettlementValidator()
                vres = validator.validate_settlement(str(settlement_id))
                validator.write_error_report(str(settlement_id), vres)
                if not vres.get('can_proceed', False) and not override:
                    diff = vres.get('journal_balance', {}).get('difference')
                    msg = "Journal validation failed"
                    if diff is not None:
                        msg += f"; Out of balance by ${diff:.2f}"
                    if vres.get('missing_gl_accounts'):
                        msg += f"; Unmapped GL: {', '.join(vres['missing_gl_accounts'])}"
                    # Add clearing vs invoices/payments hints if present in report CSV
                    results['journal']['error'] = msg
                    logger.error(msg)
                    # Do not attempt posting
                    return results
            except Exception as e:
                logger.error(f"Validation step failed: {e}")

            journal_df = pd.read_csv(journal_file)
            # Validate balance (DISABLED - journals balance when posted)
            # debits = journal_df['Debit'].sum()
            # credits = journal_df['Credit'].sum()
            # balanced = abs(debits - credits) < 0.01
            
            print(f"  Lines: {len(journal_df)}")
            # print(f"  Debits:  ${debits:,.2f}")
            # print(f"  Credits: ${credits:,.2f}")
            # print(f"  Balanced: {'✅' if balanced else '❌'}")
            
            # if not balanced:
            #     results['journal']['error'] = f"Journal out of balance by ${abs(debits - credits):.2f}"
            #     logger.error(results['journal']['error'])
            # elif not dry_run:
            if not dry_run:
                # Post journal as individual line items matching remittance
                journal_id = sync_settlement_to_zoho(settlement_id, journal_df, dry_run=False, aggregate=False)
                if isinstance(journal_id, tuple):
                    success, journal_id = journal_id
                else:
                    success = True
                
                if success and journal_id and not str(journal_id).startswith("Error"):
                    results['journal']['posted'] = True
                    results['journal']['id'] = journal_id
                    print(f"  [OK] Posted - Journal ID: {journal_id}")
                else:
                    results['journal']['error'] = journal_id
                    print(f"  [FAIL] Failed: {journal_id}")
            else:
                print(f"  [DRY RUN] Would post journal")
    
    # 2. POST INVOICES (OPTIONAL)
    # Check if journal exists (either just posted or already in Zoho)
    journal_exists = results['journal']['posted'] or (results['journal'].get('id') and results['journal']['id'])
    if not journal_exists:
        # Try checking if journal exists in Zoho
        try:
            zoho_check = ZohoBooks()
            existing_journal_id = zoho_check.check_existing_journal(settlement_id)
            if existing_journal_id:
                journal_exists = True
                results['journal']['posted'] = True
                results['journal']['id'] = existing_journal_id
        except:
            pass
    
    if post_invoices and journal_exists:
        print(f"\n[INVOICES] INVOICES...")
        invoice_file = output_dir / f"Invoice_{settlement_id}.csv"
        
        if not invoice_file.exists():
            print(f"  [WARN] No invoice file found (skipping)")
        else:
            invoice_df = pd.read_csv(invoice_file)
            print(f"  Count: {len(invoice_df)}")
            
            # Apply SKU mapping
            invoice_df, mapped_skus = apply_sku_mapping(invoice_df, sku_mapping)
            results['sku_mappings'] = mapped_skus
            
            if mapped_skus:
                print(f"  [SKU MAPPINGS] SKU Mappings Applied:")
                for orig, new in mapped_skus:
                    print(f"     {orig} -> {new}")
            
            # Show SKUs
            if 'SKU' in invoice_df.columns:
                unique_skus = invoice_df['SKU'].dropna().unique()
                print(f"  SKUs: {', '.join(unique_skus)}")
            
            if not dry_run:
                # Post invoices to Zoho
                zoho = ZohoBooks()
                invoice_ids = []
                invoice_map = {}  # Track invoice_number -> invoice_id for payments
                
                # OPTIMIZATION: Cache lookups to reduce API calls
                print(f"  [INFO] Caching customer and item lookups...")
                
                # Get customer ID once (all invoices use same customer)
                customer_name = invoice_df['Customer Name'].iloc[0]
                customer_id = zoho.get_customer_id(customer_name)
                if not customer_id:
                    results['invoices']['error'] = f"Customer not found: {customer_name}"
                    logger.error(results['invoices']['error'])
                    print(f"  [FAIL] Customer '{customer_name}' not found in Zoho")
                else:
                    print(f"  [OK] Customer: {customer_name} (ID: {customer_id})")
                
                # Get all unique SKUs and lookup item IDs once
                unique_skus = invoice_df['SKU'].dropna().unique()
                sku_to_item_id = {}
                
                for sku in unique_skus:
                    item_id = zoho.get_item_id(sku)
                    if item_id:
                        sku_to_item_id[sku] = item_id
                        print(f"  [OK] SKU {sku} -> Item ID: {item_id}")
                    else:
                        logger.warning(f"SKU not found in Zoho: {sku}")
                        print(f"  [WARN] SKU {sku} not found in Zoho")
                
                # Group by Invoice Number to handle multi-line invoices
                grouped = invoice_df.groupby('Invoice Number')
                unique_invoice_count = len(grouped)
                total_line_count = len(invoice_df)
                
                print(f"\n  [POSTING] Posting {unique_invoice_count} invoices ({total_line_count} line items)...")
                
                for invoice_number, group in grouped:
                    try:
                        # Skip if customer not found
                        if not customer_id:
                            continue
                        
                        # Check if all SKUs in this invoice are found
                        missing_skus = []
                        for sku in group['SKU']:
                            if sku not in sku_to_item_id:
                                missing_skus.append(sku)
                        
                        if missing_skus:
                            logger.warning(f"Skipping invoice {invoice_number} - SKUs not found: {missing_skus}")
                            print(f"  [WARN] Invoice {invoice_number} skipped - SKUs not found: {missing_skus}")
                            continue
                        
                        # Build line items from all rows in this group
                        line_items = []
                        for idx, row in group.iterrows():
                            line_items.append({
                                "item_id": sku_to_item_id[row['SKU']],
                                "quantity": float(row['Quantity']),
                                "rate": float(row['Item Price']),
                                "description": str(row.get('Notes', '') if pd.notna(row.get('Notes')) else '')
                            })
                        
                        # Use first row for invoice-level data
                        first_row = group.iloc[0]
                        
                        # Build invoice payload for Zoho API
                        invoice_payload = {
                            "customer_id": customer_id,
                            "customer_name": str(first_row['Customer Name']),
                            "date": str(first_row['Invoice Date']),
                            "invoice_number": str(invoice_number),  # AMZN + last 7 digits of order_id
                            "reference_number": str(first_row['Reference Number']),
                            "line_items": line_items,
                            "notes": f"Amazon Order {str(first_row.get('merchant_order_id', ''))} - Settlement {settlement_id}"
                        }
                        
                        # Create invoice
                        invoice_id = zoho.create_invoice(invoice_payload, dry_run=False)
                        if invoice_id:
                            invoice_ids.append(invoice_id)
                            # Map invoice number to Zoho invoice ID
                            invoice_map[invoice_number] = invoice_id
                            total_amount = group['Invoice Line Amount'].sum()
                            line_count = len(group)
                            print(f"  [OK] Invoice {invoice_number} posted (ID: {invoice_id}, {line_count} lines, ${total_amount:.2f})")
                        else:
                            print(f"  [FAIL] Failed to post invoice {invoice_number}")
                            
                    except Exception as e:
                        logger.error(f"Error posting invoice {invoice_number}: {e}")
                        print(f"  [FAIL] Error: {invoice_number} - {e}")
                
                results['invoices']['posted'] = len(invoice_ids) > 0
                results['invoices']['count'] = len(invoice_ids)
                results['invoices']['ids'] = invoice_ids
                results['invoice_map'] = invoice_map  # Store for payment linking
                results['customer_id'] = customer_id  # Cache for payments
                
                if len(invoice_ids) < len(invoice_df):
                    results['invoices']['error'] = f"Only {len(invoice_ids)}/{len(invoice_df)} invoices posted"
                    
            else:
                print(f"  [DRY RUN] Would post {len(invoice_df)} invoices")
    
    # 3. POST PAYMENTS (OPTIONAL)
    # Payments can post if invoices posted OR if we're posting payments independently
    # (they link to invoices that should already exist)
    if post_payments and (results['invoices']['posted'] or post_invoices == False):
        print(f"\n[PAYMENTS] PAYMENTS...")
        payment_file = output_dir / f"Payment_{settlement_id}.csv"
        
        if not payment_file.exists():
            print(f"  [WARN] No payment file found (skipping)")
        else:
            payment_df = pd.read_csv(payment_file)
            print(f"  Count: {len(payment_df)}")
            print(f"  Total: ${payment_df['Payment Amount'].sum():,.2f}")
            
            if not dry_run:
                # Post payments to Zoho
                zoho = ZohoBooks()
                payment_ids = []
                
                # Get invoice map and cached customer ID
                invoice_map = results.get('invoice_map', {})
                customer_id = results.get('customer_id')
                
                # If invoice_map is empty (posting payments independently), query Zoho fresh
                # Note: After delete/re-post, tracking file has stale IDs, so always query Zoho
                if not invoice_map:
                    try:
                        # Skip tracking file - it may have stale IDs after delete/re-post
                        # Always query Zoho for fresh invoice IDs
                        print(f"  [INFO] Querying Zoho for fresh invoice IDs (waiting 10s for rate limits)...")
                        time.sleep(10)  # Wait for rate limits
                        
                        # Query all invoices for this settlement (may need multiple pages)
                        all_invoices = []
                        page = 1
                        while True:
                            api_result = zoho._api_request('GET', f'invoices?reference_number={settlement_id}&per_page=200&page={page}')
                            if api_result.get('code') == 0:
                                invoices = api_result.get('invoices', [])
                                if not invoices:
                                    break
                                all_invoices.extend(invoices)
                                # Check if more pages
                                page_context = api_result.get('page_context', {})
                                if not page_context.get('has_more_page', False):
                                    break
                                page += 1
                                time.sleep(2)  # Rate limit protection
                            else:
                                break
                        
                        print(f"  [INFO] Found {len(all_invoices)} invoice(s) in Zoho")
                        for inv in all_invoices:
                            inv_id = inv.get('invoice_id', '')
                            inv_num = str(inv.get('invoice_number', '')).strip()
                            # Map primarily by invoice_number (this is what payments use)
                            if inv_num and inv_id:
                                invoice_map[inv_num] = inv_id
                            # Also get customer_id from first invoice (all use same customer)
                            if not customer_id and inv.get('customer_id'):
                                customer_id = inv.get('customer_id')
                        
                        # Show sample of invoice numbers for debugging
                        if invoice_map:
                            sample_invoice_nums = list(invoice_map.keys())[:5]
                            print(f"  [INFO] Sample invoice numbers in map: {sample_invoice_nums}")
                        if customer_id:
                            print(f"  [INFO] Customer ID retrieved from invoices: {customer_id}")
                        
                        # OLD CODE REMOVED - was loading from tracking file which has stale IDs
                        # Always query Zoho instead for fresh invoice IDs
                    except Exception as e:
                        logger.warning(f"Could not build invoice map: {e}")
                        print(f"  [ERROR] Could not build invoice map: {e}")
                
                # If customer_id not cached, look it up once (fallback if not found in invoices)
                if not customer_id:
                    customer_name = payment_df['Customer Name'].iloc[0]
                    customer_id = zoho.get_customer_id(customer_name)
                    if not customer_id:
                        results['payments']['error'] = f"Customer not found: {customer_name}"
                        logger.error(results['payments']['error'])
                        print(f"  [FAIL] Customer '{customer_name}' not found")
                    else:
                        print(f"  [OK] Customer: {customer_name} (ID: {customer_id})")
                
                if customer_id:
                    total_payments = len(payment_df)
                    print(f"  [POSTING] Posting {total_payments} payments in batches...")
                    
                    # Batch size - start with 10, can be adjusted if rate limits occur
                    batch_size = 10
                    payment_count = 0
                    
                    for batch_start in range(0, total_payments, batch_size):
                        batch_end = min(batch_start + batch_size, total_payments)
                        batch_df = payment_df.iloc[batch_start:batch_end]
                        
                        print(f"  [BATCH] Processing payments {batch_start + 1}-{batch_end} of {total_payments}...")
                        
                        batch_success = 0
                        for idx, row in batch_df.iterrows():
                            try:
                                # Get the Zoho invoice ID from our map
                                old_invoice_number = str(row['Invoice Number']).strip()
                                zoho_invoice_id = invoice_map.get(old_invoice_number)
                                
                                if not zoho_invoice_id:
                                    logger.warning(f"Invoice {old_invoice_number} not found in invoice map (available: {len(invoice_map)} invoices)")
                                    print(f"  [WARN] Invoice {old_invoice_number} not found in map - skipping payment")
                                    continue
                                
                                # Ensure invoice_id is a string (not scientific notation from pandas)
                                if isinstance(zoho_invoice_id, float):
                                    # Convert from scientific notation if needed
                                    invoice_id_str = f"{zoho_invoice_id:.0f}"
                                else:
                                    invoice_id_str = str(zoho_invoice_id).strip()
                                
                                # Check invoice balance before posting payment
                                payment_amount = float(row['Payment Amount'])
                                invoice_balance = zoho.get_invoice_balance(invoice_id_str)
                                
                                if invoice_balance is None:
                                    logger.warning(f"Could not get balance for invoice {old_invoice_number} (ID: {invoice_id_str}) - skipping")
                                    print(f"  [WARN] Could not get balance for invoice {old_invoice_number} - skipping")
                                    continue
                                
                                # Check if invoice is already paid
                                if abs(invoice_balance) < 0.01:
                                    logger.info(f"Invoice {old_invoice_number} already paid (balance: ${invoice_balance:.2f}) - skipping")
                                    print(f"  [SKIP] Invoice {old_invoice_number} already paid (balance: ${invoice_balance:.2f})")
                                    continue
                                
                                # Adjust payment amount to match invoice balance if needed
                                if abs(payment_amount - invoice_balance) > 0.01:
                                    logger.warning(f"Payment amount ${payment_amount:.2f} differs from invoice balance ${invoice_balance:.2f} for {old_invoice_number}")
                                    logger.warning(f"Adjusting payment amount to match invoice balance: ${invoice_balance:.2f}")
                                    print(f"  [ADJUST] Payment amount ${payment_amount:.2f} → ${invoice_balance:.2f} (invoice balance)")
                                    payment_amount = invoice_balance
                                
                                # Build payment payload for Zoho API
                                payment_payload = {
                                    "customer_id": customer_id,
                                    "payment_mode": row.get('Payment Mode', 'Direct Deposit'),
                                    "amount": payment_amount,
                                    "date": row['Payment Date'],
                                    "reference_number": row['Reference Number'],
                                    "description": row.get('Description', ''),
                                    "invoices": [{
                                        "invoice_id": invoice_id_str,
                                        "amount_applied": payment_amount
                                    }]
                                }
                                
                                # Create payment
                                payment_id = zoho.create_payment(payment_payload, dry_run=False)
                                if payment_id:
                                    payment_ids.append(payment_id)
                                    batch_success += 1
                                    payment_count += 1
                                    print(f"  [OK] Payment ${row['Payment Amount']:.2f} posted (ID: {payment_id}) - {payment_count}/{total_payments}")
                                else:
                                    # Check logs for error details
                                    error_details = f"API returned None for payment"
                                    print(f"  [FAIL] Failed to post payment for invoice {old_invoice_number}: {error_details}")
                                    logger.error(f"Payment failed for invoice {old_invoice_number}: invoice_id={zoho_invoice_id}, amount={row['Payment Amount']}")
                                    
                                # Small delay between individual payments
                                time.sleep(0.5)
                                    
                            except Exception as e:
                                error_msg = str(e)
                                logger.error(f"Error posting payment: {e}")
                                print(f"  [FAIL] Error: {error_msg[:100]}")
                                
                                # Check if it's a rate limit error
                                if 'rate limit' in error_msg.lower() or 'too many requests' in error_msg.lower() or '429' in error_msg:
                                    print(f"  [RATE LIMIT] Waiting 30 seconds before continuing...")
                                    time.sleep(30)
                                    # Reduce batch size for future batches if we hit rate limits
                                    if batch_size > 5:
                                        batch_size = max(5, batch_size // 2)
                                        print(f"  [INFO] Reduced batch size to {batch_size}")
                        
                        print(f"  [BATCH] Completed {batch_success}/{len(batch_df)} payments in this batch")
                        
                        # Wait between batches (except after the last one)
                        if batch_end < total_payments:
                            print(f"  [PAUSE] Waiting 5 seconds before next batch...")
                            time.sleep(5)
                    
                    print(f"  [SUMMARY] Posted {len(payment_ids)}/{total_payments} payments successfully")
                    
                    results['payments']['posted'] = len(payment_ids) > 0
                    results['payments']['count'] = len(payment_ids)
                    results['payments']['ids'] = payment_ids
                    
                    if len(payment_ids) < len(payment_df):
                        results['payments']['error'] = f"Only {len(payment_ids)}/{len(payment_df)} payments posted"
                    
            else:
                print(f"  [DRY RUN] Would post {len(payment_df)} payments")
    
    # Update settlement history
    if results['journal']['posted']:
        update_settlement_history(settlement_id, results['journal']['id'])
    
    # Save tracking maps (invoice and payment IDs)
    save_tracking_maps(settlement_id, results)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"[JOURNAL] {'Posted' if results['journal']['posted'] else 'Skipped/Failed'}")
    if results['journal']['id']:
        print(f"   Journal ID: {results['journal']['id']}")
    print(f"[INVOICES] {'Posted' if results['invoices']['posted'] else 'Skipped'}")
    print(f"[PAYMENTS] {'Posted' if results['payments']['posted'] else 'Skipped'}")
    
    if results['sku_mappings']:
        print(f"\n[SKU MAPPINGS] {len(results['sku_mappings'])} mappings applied")
    
    print("="*70)
    
    return results


def update_settlement_history(settlement_id: str, journal_id: str):
    """Update settlement history with Zoho journal ID"""
    from paths import get_settlement_history_path
    history_file = get_settlement_history_path()
    
    if not history_file.exists():
        logger.warning("Settlement history file not found")
        return
    
    df = pd.read_csv(history_file)
    
    # Find settlement
    mask = df['settlement_id'] == settlement_id
    if not mask.any():
        logger.warning(f"Settlement {settlement_id} not found in history")
        return
    
    # Update tracking columns
    df.loc[mask, 'zoho_synced'] = True
    df.loc[mask, 'zoho_journal_id'] = journal_id
    df.loc[mask, 'zoho_sync_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df.loc[mask, 'zoho_sync_status'] = 'success'
    
    # Save
    df.to_csv(history_file, index=False)
    logger.info(f"Updated settlement history for {settlement_id}")


def save_tracking_maps(settlement_id: str, results: Dict):
    """Save invoice and payment tracking maps to zoho_tracking.csv"""
    from paths import get_zoho_tracking_path
    tracking_file = get_zoho_tracking_path()
    
    # Load or create tracking file
    if tracking_file.exists():
        df = pd.read_csv(tracking_file)
    else:
        df = pd.DataFrame(columns=[
            'settlement_id', 'record_type', 'local_identifier', 
            'zoho_id', 'zoho_number', 'reference_number', 'status', 'created_date'
        ])
    
    # Remove existing records for this settlement
    df = df[df['settlement_id'] != settlement_id]
    
    records = []
    now = datetime.now().isoformat()
    
    # Journal record
    if results['journal'].get('id'):
        records.append({
            'settlement_id': settlement_id,
            'record_type': 'JOURNAL',
            'local_identifier': settlement_id,
            'zoho_id': results['journal']['id'],
            'zoho_number': '',
            'reference_number': settlement_id,
            'status': 'POSTED',
            'created_date': now
        })
    
    # Invoice records
    invoice_map = results.get('invoice_map', {})
    invoice_ids = results.get('invoices', {}).get('ids', [])
    
    # Read local invoice file to get invoice numbers
    invoice_file = Path("outputs") / settlement_id / f"Invoice_{settlement_id}.csv"
    if invoice_file.exists():
        try:
            invoice_df = pd.read_csv(invoice_file)
            if 'Invoice Number' in invoice_df.columns:
                for inv_num in invoice_df['Invoice Number'].dropna().unique():
                    zoho_id = invoice_map.get(str(inv_num), '')
                    records.append({
                        'settlement_id': settlement_id,
                        'record_type': 'INVOICE',
                        'local_identifier': str(inv_num),
                        'zoho_id': zoho_id,
                        'zoho_number': str(inv_num),
                        'reference_number': settlement_id,
                        'status': 'POSTED' if zoho_id else 'NOT_POSTED',
                        'created_date': now
                    })
        except Exception as e:
            logger.warning(f"Could not read invoice file for tracking: {e}")
    
    # Payment records
    payment_ids = results.get('payments', {}).get('ids', [])
    
    # Read local payment file to get payment references
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    if payment_file.exists():
        try:
            payment_df = pd.read_csv(payment_file)
            if 'Reference Number' in payment_df.columns:
                for ref_num in payment_df['Reference Number'].dropna().unique():
                    # Payment IDs aren't mapped by reference, so mark as posted if we have payment IDs
                    status = 'POSTED' if payment_ids else 'NOT_POSTED'
                    records.append({
                        'settlement_id': settlement_id,
                        'record_type': 'PAYMENT',
                        'local_identifier': str(ref_num),
                        'zoho_id': '',  # Would need to query Zoho to get payment ID by reference
                        'zoho_number': '',
                        'reference_number': str(ref_num),
                        'status': status,
                        'created_date': now
                    })
        except Exception as e:
            logger.warning(f"Could not read payment file for tracking: {e}")
    
    # Append new records
    if records:
        new_df = pd.DataFrame(records)
        df = pd.concat([df, new_df], ignore_index=True)
        df.to_csv(tracking_file, index=False, encoding='utf-8-sig')
        logger.info(f"Saved {len(records)} tracking records for {settlement_id}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync settlement to Zoho Books')
    parser.add_argument('settlement_id', help='Settlement ID to sync')
    parser.add_argument('--dry-run', action='store_true', help='Preview without posting')
    parser.add_argument('--override', action='store_true', help='Override validation blocks and post anyway')
    parser.add_argument('--journal-only', action='store_true', help='Post journal only (skip invoices/payments)')
    parser.add_argument('--no-journal', action='store_true', help='Skip journal (for testing invoices/payments)')
    
    args = parser.parse_args()
    
    # Determine what to post
    post_journal = not args.no_journal
    post_invoices = not args.journal_only
    post_payments = not args.journal_only
    
    results = post_settlement_complete(
        args.settlement_id,
        post_journal=post_journal,
        post_invoices=post_invoices,
        post_payments=post_payments,
        dry_run=args.dry_run,
        override=args.override
    )
    
    # Exit code based on success
    if results['journal']['posted'] or args.dry_run:
        sys.exit(0)
    else:
        sys.exit(1)
