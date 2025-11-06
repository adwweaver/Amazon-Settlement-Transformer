"""
Test Zoho Sync with One Settlement (DRY RUN)
Tests the integration without posting real data
"""

import sys
import logging
import pandas as pd
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG to see API URLs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import sync_settlement_to_zoho

print("=" * 70)
print("ZOHO SYNC TEST - DRY RUN MODE")
print("=" * 70)
print()

# Use smallest settlement for testing (23874396421 with only 4 rows)
test_settlement_id = "23874396421"
journal_file = Path(__file__).parent.parent / 'outputs' / test_settlement_id / f'Journal_{test_settlement_id}.csv'

if not journal_file.exists():
    print(f"❌ Journal file not found: {journal_file}")
    print()
    print("Available settlements:")
    outputs_dir = Path(__file__).parent.parent / 'outputs'
    for settlement_dir in outputs_dir.iterdir():
        if settlement_dir.is_dir():
            print(f"  - {settlement_dir.name}")
    sys.exit(1)

print(f"📄 Loading journal data from: {journal_file.name}")
journal_df = pd.read_csv(journal_file)

print(f"   Records: {len(journal_df)}")
print(f"   Date Range: {journal_df['Date'].min()} to {journal_df['Date'].max()}")
print()

# Show GL account totals
print("=" * 70)
print("GL ACCOUNT TOTALS (What will be posted to Zoho)")
print("=" * 70)
print()

gl_summary = []
for account in journal_df['GL_Account'].unique():
    account_rows = journal_df[journal_df['GL_Account'] == account]
    debit_total = account_rows['Debit'].sum()
    credit_total = account_rows['Credit'].sum()
    net_amount = debit_total - credit_total
    
    gl_summary.append({
        'GL Account': account,
        'Debit': debit_total,
        'Credit': credit_total,
        'Net': net_amount
    })

summary_df = pd.DataFrame(gl_summary)
print(summary_df.to_string(index=False))
print()
print(f"Total Debit:  ${summary_df['Debit'].sum():,.2f}")
print(f"Total Credit: ${summary_df['Credit'].sum():,.2f}")
print(f"Difference:   ${(summary_df['Debit'].sum() - summary_df['Credit'].sum()):,.2f}")
print()

# Test sync
print("=" * 70)
print("POSTING TO ZOHO BOOKS - INDIVIDUAL LINE ITEMS")
print("=" * 70)
print()

# aggregate=False means each line in the journal file is posted separately
success, result = sync_settlement_to_zoho(test_settlement_id, journal_df, dry_run=False, aggregate=False)

print()
if success:
    print("✅ JOURNAL ENTRY POSTED TO ZOHO BOOKS")
    print(f"   Journal ID: {result}")
    print()
    print("=" * 70)
    print("VERIFY IN ZOHO BOOKS")
    print("=" * 70)
    print("1. Go to: https://books.zohocloud.ca/")
    print("2. Navigate to: Accountant → Manual Journals")
    print(f"3. Look for Reference Number: {test_settlement_id}")
    print(f"4. Journal ID: {result}")
    print()
    print("Expected to see:")
    print("  - Date: 2025-08-02")
    print("  - 4 line items (each transaction separate):")
    print("    * Amazon Account Fees (Credit): $32.09 - 'Subscription Fee'")
    print("    * Amazon.ca Clearing (Debit): $32.09 - 'Successful charge'")
    print("    * Amazon Inbound Freight Charges (Credit): $321.69 - 'Inbound Transportation Fee'")
    print("    * Amazon.ca Clearing (Debit): $321.69 - 'Bank Deposit on 2025-08-02'")
    print()
    print("If correct → Process remaining 5 settlements")
    print("If incorrect → Let me know what needs adjustment")
else:
    print(f"❌ POSTING FAILED: {result}")
    print()
    print("Check the error message and fix any issues before proceeding.")

print()
