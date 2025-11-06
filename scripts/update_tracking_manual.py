#!/usr/bin/env python3
"""
Manually update tracking file with Zoho IDs provided by user.

Usage:
  python scripts/update_tracking_manual.py --csv manual_tracking_updates.csv
  OR
  python scripts/update_tracking_manual.py --settlement 23874397121 --invoice AMZN6751437 --zoho-id 73985000000191046
"""

import argparse
import csv
from pathlib import Path
import pandas as pd
from datetime import datetime


def update_from_csv(csv_file: Path):
    """Update tracking from CSV file with columns: settlement_id, record_type, local_identifier, zoho_id"""
    from paths import get_zoho_tracking_path
    tracking_file = get_zoho_tracking_path()
    
    if not tracking_file.exists():
        print(f"[ERROR] Tracking file not found: {tracking_file}")
        return
    
    # Load tracking file
    df_tracking = pd.read_csv(tracking_file)
    
    # Load updates
    df_updates = pd.read_csv(csv_file)
    
    required_cols = ['settlement_id', 'record_type', 'local_identifier', 'zoho_id']
    if not all(col in df_updates.columns for col in required_cols):
        print(f"[ERROR] CSV must have columns: {', '.join(required_cols)}")
        return
    
    updated_count = 0
    new_count = 0
    
    for idx, update in df_updates.iterrows():
        settlement_id = str(update['settlement_id'])
        record_type = str(update['record_type']).upper()
        local_identifier = str(update['local_identifier'])
        zoho_id = str(update['zoho_id'])
        
        # Find matching record
        mask = (
            (df_tracking['settlement_id'] == settlement_id) &
            (df_tracking['record_type'] == record_type) &
            (df_tracking['local_identifier'] == local_identifier)
        )
        
        if mask.any():
            # Update existing
            df_tracking.loc[mask, 'zoho_id'] = zoho_id
            df_tracking.loc[mask, 'status'] = 'POSTED'
            updated_count += 1
        else:
            # Add new record
            new_record = {
                'settlement_id': settlement_id,
                'record_type': record_type,
                'local_identifier': local_identifier,
                'zoho_id': zoho_id,
                'zoho_number': local_identifier if record_type == 'INVOICE' else '',
                'reference_number': settlement_id,
                'status': 'POSTED',
                'created_date': datetime.now().isoformat()
            }
            df_tracking = pd.concat([df_tracking, pd.DataFrame([new_record])], ignore_index=True)
            new_count += 1
    
    # Save
    df_tracking.to_csv(tracking_file, index=False, encoding='utf-8-sig')
    print(f"[SUCCESS] Updated {updated_count} records, added {new_count} new records")
    print(f"Tracking file saved: {tracking_file}")


def update_single(settlement_id: str, record_type: str, local_identifier: str, zoho_id: str):
    """Update a single tracking record"""
    from paths import get_zoho_tracking_path
    tracking_file = get_zoho_tracking_path()
    
    if not tracking_file.exists():
        print(f"[ERROR] Tracking file not found: {tracking_file}")
        return
    
    df = pd.read_csv(tracking_file)
    
    record_type = record_type.upper()
    
    # Find matching record
    mask = (
        (df['settlement_id'] == settlement_id) &
        (df['record_type'] == record_type) &
        (df['local_identifier'] == local_identifier)
    )
    
    if mask.any():
        df.loc[mask, 'zoho_id'] = zoho_id
        df.loc[mask, 'status'] = 'POSTED'
        print(f"[SUCCESS] Updated tracking for {record_type} {local_identifier}")
    else:
        # Add new record
        new_record = {
            'settlement_id': settlement_id,
            'record_type': record_type,
            'local_identifier': local_identifier,
            'zoho_id': zoho_id,
            'zoho_number': local_identifier if record_type == 'INVOICE' else '',
            'reference_number': settlement_id,
            'status': 'POSTED',
            'created_date': datetime.now().isoformat()
        }
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        print(f"[SUCCESS] Added new tracking record for {record_type} {local_identifier}")
    
    df.to_csv(tracking_file, index=False, encoding='utf-8-sig')
    print(f"Tracking file saved: {tracking_file}")


def main():
    parser = argparse.ArgumentParser(description='Manually update Zoho tracking with IDs')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--csv', help='CSV file with tracking updates (columns: settlement_id, record_type, local_identifier, zoho_id)')
    group.add_argument('--single', action='store_true', help='Update single record')
    
    parser.add_argument('--settlement', help='Settlement ID (for --single)')
    parser.add_argument('--type', choices=['INVOICE', 'PAYMENT', 'JOURNAL'], help='Record type (for --single)')
    parser.add_argument('--identifier', help='Local identifier (invoice number, payment ref, etc.) (for --single)')
    parser.add_argument('--zoho-id', help='Zoho transaction ID (for --single)')
    
    args = parser.parse_args()
    
    if args.csv:
        update_from_csv(Path(args.csv))
    elif args.single:
        if not all([args.settlement, args.type, args.identifier, args.zoho_id]):
            print("[ERROR] --settlement, --type, --identifier, and --zoho-id are required for --single")
            return
        update_single(args.settlement, args.type, args.identifier, args.zoho_id)


if __name__ == '__main__':
    main()

