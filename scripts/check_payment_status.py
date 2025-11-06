#!/usr/bin/env python3
"""Quick script to check which settlements have invoices and payments."""

import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from paths import get_zoho_tracking_path
from post_all_settlements import find_local_settlements

print("Checking settlement status...")
print("="*80)

# Get settlements from tracking
tracking_file = get_zoho_tracking_path()
if tracking_file.exists():
    df = pd.read_csv(tracking_file)
    invoice_settlements = set(df[df['record_type']=='INVOICE']['settlement_id'].unique())
    print(f"\nSettlements with invoices in tracking: {sorted(invoice_settlements)}")
else:
    invoice_settlements = set()
    print("\nNo tracking file found")

# Get all local settlements
all_settlements = find_local_settlements()
print(f"\nAll local settlements: {sorted(all_settlements)}")

# Check which have payment files
print("\nChecking payment files:")
for settlement_id in sorted(all_settlements):
    payment_file = Path("outputs") / settlement_id / f"Payment_{settlement_id}.csv"
    has_payment_file = payment_file.exists()
    has_invoices = settlement_id in invoice_settlements
    print(f"  {settlement_id}: payment_file={has_payment_file}, invoices_tracked={has_invoices}")
    if has_payment_file and has_invoices:
        try:
            df_pay = pd.read_csv(payment_file)
            print(f"    -> {len(df_pay)} payments in file")
        except:
            print(f"    -> Could not read payment file")



