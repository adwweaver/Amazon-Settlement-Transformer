"""
Sync All Settlements to Zoho Books
Processes unsynced settlements and updates tracking database
"""

import sys
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/zoho_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import sync_settlement_to_zoho

print("=" * 70)
print("ZOHO BOOKS BULK SYNC - PROCESS UNSYNCED SETTLEMENTS")
print("=" * 70)
print()

# Load settlement history
from paths import get_settlement_history_path
history_file = get_settlement_history_path()

if not history_file.exists():
    print(f"❌ Settlement history not found: {history_file}")
    sys.exit(1)

history_df = pd.read_csv(history_file)

# Add Zoho columns if they don't exist
if 'zoho_synced' not in history_df.columns:
    history_df['zoho_synced'] = False
if 'zoho_journal_id' not in history_df.columns:
    history_df['zoho_journal_id'] = None
if 'zoho_sync_date' not in history_df.columns:
    history_df['zoho_sync_date'] = None
if 'zoho_sync_status' not in history_df.columns:
    history_df['zoho_sync_status'] = 'pending'

print(f"📊 Total settlements in history: {len(history_df)}")
print()

# Filter unsynced settlements
unsynced = history_df[history_df['zoho_synced'] == False].copy()

if len(unsynced) == 0:
    print("✅ All settlements already synced to Zoho Books!")
    sys.exit(0)

print(f"📤 Settlements to sync: {len(unsynced)}")
print()

# Ask for confirmation
print("Settlements to be synced:")
for idx, row in unsynced.iterrows():
    settlement_id = row['settlement_id']
    deposit_date = row.get('deposit_date', 'Unknown')
    amount = row.get('bank_deposit_amount', 0)
    print(f"  - {settlement_id} | {deposit_date} | ${amount:,.2f}")

print()
response = input("Proceed with sync? (yes/no): ").strip().lower()

if response != 'yes':
    print("❌ Sync cancelled")
    sys.exit(0)

print()
print("=" * 70)
print("SYNCING SETTLEMENTS")
print("=" * 70)
print()

# Process each settlement
outputs_dir = Path(__file__).parent.parent / 'outputs'
success_count = 0
failed_count = 0

for idx, row in unsynced.iterrows():
    settlement_id = str(row['settlement_id'])
    
    print(f"Processing: {settlement_id}...")
    
    # Load journal file
    journal_file = outputs_dir / settlement_id / f'Journal_{settlement_id}.csv'
    
    if not journal_file.exists():
        logger.error(f"Journal file not found for {settlement_id}: {journal_file}")
        history_df.at[idx, 'zoho_sync_status'] = 'error: journal file not found'
        failed_count += 1
        continue
    
    try:
        journal_df = pd.read_csv(journal_file)
        
        # Sync to Zoho (individual line items, not aggregated)
        success, result = sync_settlement_to_zoho(
            settlement_id, 
            journal_df, 
            dry_run=False,  # REAL POSTING
            aggregate=False  # Individual line items
        )
        
        if success:
            # Update history
            history_df.at[idx, 'zoho_synced'] = True
            history_df.at[idx, 'zoho_journal_id'] = result
            history_df.at[idx, 'zoho_sync_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            history_df.at[idx, 'zoho_sync_status'] = 'success'
            
            print(f"  ✅ Synced - Journal ID: {result}")
            success_count += 1
        else:
            history_df.at[idx, 'zoho_sync_status'] = f'error: {result}'
            print(f"  ❌ Failed: {result}")
            failed_count += 1
    
    except Exception as e:
        logger.error(f"Error processing {settlement_id}: {e}")
        history_df.at[idx, 'zoho_sync_status'] = f'error: {str(e)}'
        print(f"  ❌ Error: {e}")
        failed_count += 1
    
    print()

# Save updated history
history_df.to_csv(history_file, index=False)

print("=" * 70)
print("SYNC COMPLETE")
print("=" * 70)
print(f"✅ Successfully synced: {success_count}")
print(f"❌ Failed: {failed_count}")
print(f"📊 Total processed: {success_count + failed_count}")
print()
print(f"📄 Updated tracking: {history_file}")
print()

if success_count > 0:
    print("=" * 70)
    print("VERIFY IN ZOHO BOOKS")
    print("=" * 70)
    print("1. Go to: https://books.zohocloud.ca/")
    print("2. Navigate to: Accountant → Manual Journals")
    print("3. Check for reference numbers:")
    for idx, row in unsynced.iterrows():
        if history_df.at[idx, 'zoho_synced']:
            settlement_id = row['settlement_id']
            journal_id = history_df.at[idx, 'zoho_journal_id']
            print(f"   - {settlement_id} → Journal ID: {journal_id}")
    print()

print("Next steps:")
print("  - Regenerate Dashboard to see Zoho sync status")
print("  - Run: python scripts/main.py --export-dashboard")
