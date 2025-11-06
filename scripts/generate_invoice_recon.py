#!/usr/bin/env python3
"""
Builds detailed invoice reconciliation and a skipped-invoices report.

Outputs:
  - outputs/Invoices_Detail_Recon.csv
  - outputs/Skipped_Invoices.csv
"""

from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).parent))
from zoho_sync import ZohoBooks


def fetch_zoho_invoices(zoho: ZohoBooks, start: str, end: str) -> pd.DataFrame:
    base = f"invoices?date_start={start}&date_end={end}&per_page=200"
    page = 1
    items = []
    while True:
        res = zoho._api_request('GET', f"{base}&page={page}")
        if res.get('code') != 0:
            break
        items.extend(res.get('invoices', []))
        ctx = res.get('page_context', {})
        if not ctx.get('has_more_page'):
            break
        page += 1
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    # Normalize keys used in recon
    keep = ['invoice_id', 'invoice_number', 'total', 'customer_name', 'date', 'reference_number']
    df = df[[c for c in keep if c in df.columns]]
    df.rename(columns={'total': 'zoho_total'}, inplace=True)
    return df


def expected_from_outputs(outputs_dir: Path) -> pd.DataFrame:
    rows = []
    for folder in outputs_dir.iterdir():
        if not folder.is_dir():
            continue
        sid = folder.name
        invf = folder / f"Invoice_{sid}.csv"
        if not invf.exists():
            continue
        df = pd.read_csv(invf)
        # Use Invoice Number if present, else synthetic from Reference Number + row
        inv_num_col = 'Invoice Number' if 'Invoice Number' in df.columns else None
        amt_col = None
        for c in ['Invoice Line Amount', 'amount', 'rate']:
            if c in df.columns:
                amt_col = c; break
        df['_exp_amount'] = pd.to_numeric(df[amt_col], errors='coerce').fillna(0) if amt_col else 0
        if inv_num_col:
            grp = df.groupby(inv_num_col)['_exp_amount'].sum().reset_index()
            grp['settlement_id'] = sid
            grp.rename(columns={inv_num_col: 'invoice_number', '_exp_amount': 'expected_total'}, inplace=True)
            rows.append(grp)
        else:
            df['invoice_number'] = df['Reference Number'] if 'Reference Number' in df.columns else sid
            grp = df.groupby('invoice_number')['_exp_amount'].sum().reset_index()
            grp['settlement_id'] = sid
            grp.rename(columns={'_exp_amount': 'expected_total'}, inplace=True)
            rows.append(grp)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=['invoice_number','expected_total','settlement_id'])


def main():
    root = Path(__file__).parent.parent
    outputs_dir = root / 'outputs'
    # Date range heuristic from files (fallback to current year)
    start = f"{pd.Timestamp.now().year}-01-01"
    end = pd.Timestamp.now().strftime('%Y-%m-%d')

    zoho = ZohoBooks()
    zdf = fetch_zoho_invoices(zoho, start, end)
    edf = expected_from_outputs(outputs_dir)

    recon = edf.merge(zdf[['invoice_number','zoho_total']], on='invoice_number', how='left')
    recon['zoho_total'] = pd.to_numeric(recon['zoho_total'], errors='coerce')
    recon['expected_total'] = pd.to_numeric(recon['expected_total'], errors='coerce')
    recon['status'] = recon.apply(lambda r: 'missing_in_zoho' if pd.isna(r['zoho_total']) else ('mismatch' if abs((r['expected_total'] or 0) - (r['zoho_total'] or 0)) > 0.01 else 'match'), axis=1)
    recon.sort_values(['settlement_id','invoice_number']).to_csv(outputs_dir / 'Invoices_Detail_Recon.csv', index=False)

    # Skipped invoices (missing in Zoho)
    skipped = recon[recon['status'] == 'missing_in_zoho'][['settlement_id','invoice_number','expected_total']]
    skipped.to_csv(outputs_dir / 'Skipped_Invoices.csv', index=False)
    print(f"Saved: {outputs_dir / 'Invoices_Detail_Recon.csv'}")
    print(f"Saved: {outputs_dir / 'Skipped_Invoices.csv'}")


if __name__ == '__main__':
    main()






