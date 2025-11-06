#!/usr/bin/env python3
"""
Deduplicate settlement_history.csv - keep most recent record for each settlement_id
"""

import pandas as pd
from pathlib import Path

def deduplicate_history():
    """Remove duplicate settlement records, keeping the most recent."""
    from paths import get_settlement_history_path
    history_file = get_settlement_history_path()
    
    if not history_file.exists():
        print(f"❌ File not found: {history_file}")
        return
    
    # Load history
    df = pd.read_csv(history_file)
    
    print(f"📊 Original: {len(df)} rows")
    print(f"🔢 Unique settlements: {df['settlement_id'].nunique()}")
    print("\nDuplicate counts:")
    print(df['settlement_id'].value_counts())
    
    # Sort by date_processed (most recent first), then keep first occurrence of each settlement_id
    df['date_processed'] = pd.to_datetime(df['date_processed'])
    df = df.sort_values('date_processed', ascending=False)
    df_deduped = df.drop_duplicates(subset='settlement_id', keep='first')
    
    # Sort by settlement_id for clean output
    df_deduped = df_deduped.sort_values('settlement_id')
    
    print(f"\n✅ After deduplication: {len(df_deduped)} rows")
    
    # Backup original
    backup_file = history_file.with_suffix('.csv.backup')
    df.to_csv(backup_file, index=False)
    print(f"💾 Backup saved: {backup_file}")
    
    # Save deduplicated
    df_deduped.to_csv(history_file, index=False)
    print(f"✅ Saved deduplicated history: {history_file}")
    
    print("\nRemaining settlements:")
    for _, row in df_deduped.iterrows():
        status = '✅' if row['zoho_synced'] else '⏳'
        journal_id = row['zoho_journal_id'] if pd.notna(row['zoho_journal_id']) else 'Not synced'
        print(f"  {status} {row['settlement_id']} - {journal_id}")

if __name__ == "__main__":
    deduplicate_history()
