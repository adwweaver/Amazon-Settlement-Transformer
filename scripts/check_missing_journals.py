#!/usr/bin/env python3
"""
Check which journal entries are missing in Zoho Books.

Usage:
  python scripts/check_missing_journals.py
"""

import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from paths import get_settlement_history_path
from zoho_sync import ZohoBooks


def check_all_journals_in_zoho(zoho: ZohoBooks) -> dict:
    """Get all journal entries from Zoho Books."""
    all_journals = {}
    
    print("Fetching all journals from Zoho Books...")
    
    try:
        # Get all journals (paginated)
        page = 1
        per_page = 200
        
        while True:
            result = zoho._api_request('GET', f'journals?page={page}&per_page={per_page}')
            
            if result.get('code') != 0:
                break
            
            journals = result.get('journals', [])
            if not journals:
                break
            
            for journal in journals:
                journal_id = journal.get('journal_id', '')
                entry_number = journal.get('entry_number', '')
                reference_number = journal.get('reference_number', '')
                journal_date = journal.get('journal_date', '')
                
                # Store by both entry number and settlement ID if available
                all_journals[entry_number] = {
                    'journal_id': journal_id,
                    'entry_number': entry_number,
                    'reference_number': reference_number,
                    'date': journal_date,
                    'journal': journal
                }
                
                if reference_number and reference_number.isdigit():
                    all_journals[reference_number] = all_journals[entry_number]
            
            # Check if there's a next page
            page_info = result.get('page_context', {})
            has_more = page_info.get('has_more_page', False)
            
            if not has_more:
                break
            
            page += 1
        
        print(f"  Found {len(set(j.get('entry_number') for j in all_journals.values() if j.get('entry_number')))} unique journal entries")
        
    except Exception as e:
        print(f"  Error fetching journals: {e}")
    
    return all_journals


def analyze_missing_journals():
    """Analyze which journals are missing."""
    print("=" * 80)
    print("CHECKING MISSING JOURNAL ENTRIES")
    print("=" * 80)
    
    # Get local settlements
    output_dir = Path("outputs")
    local_settlements = sorted([d.name for d in output_dir.iterdir() if d.is_dir() and d.name.isdigit()])
    
    print(f"\n[1] Local Settlements: {len(local_settlements)}")
    for sid in local_settlements:
        print(f"    {sid}")
    
    # Get settlement history
    history_file = get_settlement_history_path()
    if history_file.exists():
        df_history = pd.read_csv(history_file)
        df_history['gl_Amazon_Advertising_Expense'] = pd.to_numeric(
            df_history['gl_Amazon_Advertising_Expense'], errors='coerce'
        ).fillna(0)
        
        # Get latest entry for each settlement
        latest = df_history.groupby('settlement_id').last()
        posted_settlements = latest[latest['zoho_synced'] == True]
        
        print(f"\n[2] Settlement History:")
        print(f"    Total settlements: {len(latest)}")
        print(f"    Posted to Zoho: {len(posted_settlements)}")
        
        print("\n    Posted Settlements:")
        for sid, row in posted_settlements.iterrows():
            journal_id = str(row.get('zoho_journal_id', 'N/A'))
            adv_exp = row.get('gl_Amazon_Advertising_Expense', 0)
            print(f"      {sid}: Journal ID {journal_id}, Advertising: ${adv_exp:,.2f}")
    
    # Get all journals from Zoho
    print(f"\n[3] Fetching journals from Zoho Books...")
    zoho = ZohoBooks()
    zoho_journals = check_all_journals_in_zoho(zoho)
    
    # Match by settlement ID
    print(f"\n[4] Matching local settlements to Zoho journals...")
    
    matched = []
    missing = []
    
    for settlement_id in local_settlements:
        # Check if journal exists by settlement ID
        if settlement_id in zoho_journals:
            journal_info = zoho_journals[settlement_id]
            matched.append({
                'settlement_id': settlement_id,
                'zoho_journal_id': journal_info['journal_id'],
                'entry_number': journal_info.get('entry_number', 'N/A'),
                'date': journal_info.get('date', ''),
                'status': 'FOUND'
            })
        else:
            # Check history to see if it was supposed to be posted
            if history_file.exists():
                settlement_history = df_history[df_history['settlement_id'] == settlement_id]
                if not settlement_history.empty:
                    latest_row = settlement_history.iloc[-1]
                    if latest_row.get('zoho_synced') == True:
                        journal_id = str(latest_row.get('zoho_journal_id', ''))
                        missing.append({
                            'settlement_id': settlement_id,
                            'zoho_journal_id': journal_id if journal_id != 'nan' else None,
                            'entry_number': 'NOT_FOUND',
                            'date': '',
                            'status': 'MISSING (was marked as posted)'
                        })
                    else:
                        missing.append({
                            'settlement_id': settlement_id,
                            'zoho_journal_id': None,
                            'entry_number': 'NOT_FOUND',
                            'date': '',
                            'status': 'NOT_POSTED'
                        })
                else:
                    missing.append({
                        'settlement_id': settlement_id,
                        'zoho_journal_id': None,
                        'entry_number': 'NOT_FOUND',
                        'date': '',
                        'status': 'NOT_IN_HISTORY'
                    })
            else:
                missing.append({
                    'settlement_id': settlement_id,
                    'zoho_journal_id': None,
                    'entry_number': 'NOT_FOUND',
                    'date': '',
                    'status': 'NOT_POSTED'
                })
    
    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    print(f"\n[MATCHED] {len(matched)} journals found in Zoho:")
    for m in matched:
        print(f"  Settlement {m['settlement_id']}: Entry #{m['entry_number']}, Journal ID {m['zoho_journal_id']}")
    
    print(f"\n[MISSING] {len(missing)} journals NOT found in Zoho:")
    for m in missing:
        status = m['status']
        journal_id = m['zoho_journal_id'] if m['zoho_journal_id'] else 'N/A'
        print(f"  Settlement {m['settlement_id']}: {status} (Journal ID in history: {journal_id})")
    
    # List all Zoho journals
    print(f"\n[ZOHO JOURNALS] All journal entries found in Zoho:")
    entry_numbers = sorted(set(j.get('entry_number') for j in zoho_journals.values() if j.get('entry_number')))
    for entry_num in entry_numbers:
        journal = next(j for j in zoho_journals.values() if j.get('entry_number') == entry_num)
        ref = journal.get('reference_number', 'N/A')
        print(f"  Entry #{entry_num}: Reference {ref}, Journal ID {journal['journal_id']}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Local Settlements: {len(local_settlements)}")
    print(f"Found in Zoho: {len(matched)}")
    print(f"Missing: {len(missing)}")
    print(f"Total Zoho Journals: {len(entry_numbers)}")
    
    if len(matched) < len(local_settlements):
        print(f"\n[WARNING] {len(missing)} journal entries are missing from Zoho!")
        print("Action: Post missing journal entries using sync_settlement.py")


if __name__ == '__main__':
    analyze_missing_journals()



