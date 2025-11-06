#!/usr/bin/env python3
"""
Reverse previously posted aggregated journal for a settlement, then repost line-by-line.

Usage:
  python scripts/reverse_and_repost.py <settlement_id>
"""

import sys
import logging
import pandas as pd
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from zoho_sync import ZohoBooks
from zoho_sync import sync_settlement_to_zoho

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def compute_gl_totals(journal_csv: Path) -> dict:
    df = pd.read_csv(journal_csv)
    df['Debit'] = pd.to_numeric(df.get('Debit', 0), errors='coerce').fillna(0)
    df['Credit'] = pd.to_numeric(df.get('Credit', 0), errors='coerce').fillna(0)
    totals = {}
    for gl in df['GL_Account'].unique():
        sub = df[df['GL_Account'] == gl]
        net = float(sub['Debit'].sum() - sub['Credit'].sum())
        totals[gl] = round(net, 2)
    # Metadata for Zoho payload
    totals['settlement_id'] = str(df['Reference Number'].iloc[0] if 'Reference Number' in df.columns else df['settlement_id'].iloc[0])
    totals['notes'] = f"Reverse prior aggregated journal for {totals['settlement_id']}"
    totals['deposit_date'] = str(df['Date'].iloc[0]) if 'Date' in df.columns else None
    return totals


def reverse_then_repost_line_by_line(settlement_id: str) -> tuple[str, str]:
    outputs_dir = Path(__file__).parent.parent / 'outputs' / settlement_id
    journal_csv = outputs_dir / f"Journal_{settlement_id}.csv"
    if not journal_csv.exists():
        raise FileNotFoundError(f"Journal file not found: {journal_csv}")

    # 1) Reverse aggregated amounts by posting negative of net per GL
    gl_totals = compute_gl_totals(journal_csv)
    reverse_totals = {k: (-v if isinstance(v, (int, float)) else v) for k, v in gl_totals.items()}

    zoho = ZohoBooks()
    rev_id = zoho.create_journal_entry(settlement_id, reverse_totals, dry_run=False, individual_lines=False,
                                       reference_number=f"{settlement_id}-REV1", force=True)
    if not rev_id or str(rev_id).startswith('Error'):
        raise RuntimeError(f"Failed to create reversing journal for {settlement_id}: {rev_id}")

    # 2) Repost line-by-line
    journal_df = pd.read_csv(journal_csv)
    # Post line-by-line with force and original reference number (or append -D if desired)
    new_id = zoho.create_journal_entry(settlement_id, journal_df, dry_run=False, individual_lines=True,
                                       reference_number=settlement_id, force=True)
    ok = bool(new_id)
    if not ok:
        raise RuntimeError(f"Failed to repost line-by-line for {settlement_id}: {new_id}")

    return str(rev_id), str(new_id)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/reverse_and_repost.py <settlement_id>")
        sys.exit(1)

    sid = sys.argv[1]
    print("=" * 70)
    print(f"REVERSING AND REPOSTING SETTLEMENT {sid}")
    print("=" * 70)
    try:
        rev_id, new_id = reverse_then_repost_line_by_line(sid)
        print(f"✅ Reversing journal posted: {rev_id}")
        print(f"✅ New line-by-line journal posted: {new_id}")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Failed: {e}")
        sys.exit(1)


