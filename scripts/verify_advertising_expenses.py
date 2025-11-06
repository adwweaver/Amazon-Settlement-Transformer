#!/usr/bin/env python3
"""
Verify advertising expenses and check if all journal entries have been entered.

Usage:
  python scripts/verify_advertising_expenses.py
"""

import pandas as pd
from pathlib import Path
from typing import Dict
import sys
import os

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from paths import get_settlement_history_path
from zoho_sync import ZohoBooks


def analyze_local_journals() -> Dict:
    """Analyze advertising expenses from local journal files."""
    output_dir = Path("outputs")
    results = {}
    
    settlements = [d.name for d in output_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    
    total_advertising = 0
    
    for settlement_id in sorted(settlements):
        journal_file = output_dir / settlement_id / f"Journal_{settlement_id}.csv"
        
        if not journal_file.exists():
            continue
        
        try:
            df = pd.read_csv(journal_file)
            
            # Find advertising expense lines
            advertising_mask = df['GL_Account'] == 'Amazon Advertising Expense'
            
            if advertising_mask.any():
                advertising_df = df[advertising_mask]
                # Sum debits (expenses are debits in journal, but credits when posted to Zoho)
                # Check both debit and credit columns
                settlement_advertising = advertising_df['Debit'].sum() if 'Debit' in advertising_df.columns else advertising_df['Credit'].sum()
                
                results[settlement_id] = {
                    'local_advertising': settlement_advertising,
                    'line_count': len(advertising_df),
                    'journal_lines': len(df),
                    'posted': False
                }
                
                total_advertising += settlement_advertising
            else:
                results[settlement_id] = {
                    'local_advertising': 0,
                    'line_count': 0,
                    'journal_lines': len(df),
                    'posted': False
                }
        except Exception as e:
            print(f"  Error reading {settlement_id}: {e}")
            results[settlement_id] = {
                'local_advertising': 0,
                'line_count': 0,
                'journal_lines': 0,
                'posted': False,
                'error': str(e)
            }
    
    return results, total_advertising


def check_zoho_journals(zoho: ZohoBooks, settlements: list) -> Dict:
    """Check what's actually posted in Zoho Books."""
    zoho_results = {}
    
    print("\nChecking Zoho Books for posted journals...")
    
    for settlement_id in settlements:
        try:
            journal_id = zoho.check_existing_journal(settlement_id)
            if journal_id:
                # Get journal details
                result = zoho._api_request('GET', f'journals/{journal_id}')
                if result.get('code') == 0:
                    journal = result.get('journal', {})
                    line_items = journal.get('line_items', [])
                    
                    # Find advertising expense lines
                    advertising_total = 0
                    advertising_lines = []
                    
                    for line in line_items:
                        account_name = line.get('account_name', '')
                        if 'Advertising' in account_name or account_name == 'Amazon Advertising Expense':
                            # Advertising expenses are credits
                            credit = float(line.get('credit', 0))
                            advertising_total += credit
                            advertising_lines.append(line)
                    
                    zoho_results[settlement_id] = {
                        'journal_id': journal_id,
                        'zoho_advertising': advertising_total,
                        'advertising_line_count': len(advertising_lines),
                        'total_line_count': len(line_items),
                        'posted': True
                    }
                else:
                    zoho_results[settlement_id] = {
                        'journal_id': journal_id,
                        'zoho_advertising': 0,
                        'posted': True,
                        'error': 'Could not retrieve journal details'
                    }
            else:
                zoho_results[settlement_id] = {
                    'journal_id': None,
                    'zoho_advertising': 0,
                    'posted': False
                }
        except Exception as e:
            print(f"  Error checking {settlement_id}: {e}")
            zoho_results[settlement_id] = {
                'journal_id': None,
                'zoho_advertising': 0,
                'posted': False,
                'error': str(e)
            }
    
    return zoho_results


def check_settlement_history() -> pd.DataFrame:
    """Check settlement history for posted status."""
    history_file = get_settlement_history_path()
    
    if not history_file.exists():
        return pd.DataFrame()
    
    df = pd.read_csv(history_file)
    df['gl_Amazon_Advertising_Expense'] = pd.to_numeric(
        df['gl_Amazon_Advertising_Expense'], 
        errors='coerce'
    ).fillna(0)
    
    return df


def main():
    print("=" * 80)
    print("ADVERTISING EXPENSE VERIFICATION")
    print("=" * 80)
    
    # Analyze local journals
    print("\n[1] Analyzing local journal files...")
    local_results, local_total = analyze_local_journals()
    
    print(f"  Found {len(local_results)} settlements with journals")
    print(f"  Total Advertising Expense (Local): ${local_total:,.2f}")
    
    for sid, data in local_results.items():
        if data['local_advertising'] > 0:
            print(f"    Settlement {sid}: ${data['local_advertising']:,.2f} ({data['line_count']} lines)")
    
    # Check settlement history
    print("\n[2] Checking settlement history...")
    history_df = check_settlement_history()
    
    if not history_df.empty:
        # Get latest entry for each settlement
        latest = history_df.groupby('settlement_id').last()
        posted = latest[latest['zoho_synced'] == True]
        
        if 'gl_Amazon_Advertising_Expense' in latest.columns:
            history_total = latest['gl_Amazon_Advertising_Expense'].sum()
            posted_total = posted['gl_Amazon_Advertising_Expense'].sum()
            
            print(f"  History Total Advertising: ${history_total:,.2f}")
            print(f"  Posted Settlements Advertising: ${posted_total:,.2f}")
            print(f"  Posted Settlements: {len(posted)}/{len(latest)}")
            
            print("\n  Per Settlement (History):")
            for sid in sorted(latest.index):
                adv = latest.loc[sid, 'gl_Amazon_Advertising_Expense']
                synced = latest.loc[sid, 'zoho_synced']
                if adv != 0:
                    status = "POSTED" if synced else "NOT POSTED"
                    print(f"    {sid}: ${adv:,.2f} ({status})")
    
    # Check Zoho Books
    print("\n[3] Checking Zoho Books...")
    zoho = ZohoBooks()
    settlements = list(local_results.keys())
    zoho_results = check_zoho_journals(zoho, settlements)
    
    zoho_total = sum(r.get('zoho_advertising', 0) for r in zoho_results.values())
    print(f"  Total Advertising Expense (Zoho): ${zoho_total:,.2f}")
    
    print("\n  Per Settlement (Zoho):")
    for sid in sorted(zoho_results.keys()):
        data = zoho_results[sid]
        if data.get('zoho_advertising', 0) > 0 or data.get('posted'):
            status = "POSTED" if data.get('posted') else "NOT POSTED"
            journal_id = data.get('journal_id', 'N/A')
            zoho_adv = data.get('zoho_advertising', 0)
            print(f"    {sid}: ${zoho_adv:,.2f} (Journal: {journal_id}) [{status}]")
    
    # Compare
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    
    print(f"\nLocal Total:    ${local_total:,.2f}")
    print(f"Zoho Total:     ${zoho_total:,.2f}")
    print(f"Difference:     ${local_total - zoho_total:,.2f}")
    
    if history_total > 0:
        print(f"History Total:  ${history_total:,.2f}")
        print(f"History vs Local: ${history_total - local_total:,.2f}")
    
    # Identify missing
    print("\n" + "=" * 80)
    print("MISSING JOURNAL ENTRIES")
    print("=" * 80)
    
    missing = []
    for sid in sorted(local_results.keys()):
        local_data = local_results.get(sid, {})
        zoho_data = zoho_results.get(sid, {})
        
        local_adv = local_data.get('local_advertising', 0)
        zoho_adv = zoho_data.get('zoho_advertising', 0)
        posted = zoho_data.get('posted', False)
        
        if local_adv > 0 and (not posted or abs(local_adv - zoho_adv) > 0.01):
            missing.append({
                'settlement_id': sid,
                'local_advertising': local_adv,
                'zoho_advertising': zoho_adv,
                'posted': posted,
                'missing': local_adv - zoho_adv if posted else local_adv
            })
    
    if missing:
        print(f"\nFound {len(missing)} settlements with missing/mismatched advertising expenses:")
        for m in missing:
            if m['posted']:
                print(f"  {m['settlement_id']}: Local ${m['local_advertising']:,.2f} vs Zoho ${m['zoho_advertising']:,.2f} (Difference: ${m['missing']:,.2f})")
            else:
                print(f"  {m['settlement_id']}: ${m['local_advertising']:,.2f} NOT POSTED")
    else:
        print("\nAll advertising expenses appear to be posted correctly!")
    
    # Check for settlements that might have advertising but aren't in our data
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if abs(local_total - zoho_total) > 1.0:
        print(f"\n⚠️  WARNING: Significant discrepancy between local (${local_total:,.2f}) and Zoho (${zoho_total:,.2f})")
        print("   Possible causes:")
        print("   1. Missing settlements not processed yet")
        print("   2. Journal entries not fully posted to Zoho")
        print("   3. Advertising expenses posted separately outside this system")
        print("   4. Data entry errors")
    else:
        print("\n[OK] Advertising expenses match between local and Zoho")


if __name__ == '__main__':
    main()

