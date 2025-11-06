#!/usr/bin/env python3
"""
Reconcile outputs vs Zoho for settlements, invoices, and payments.

Outputs:
  - outputs/Settlements_Balance_Check.csv
  - outputs/Invoices_Detail_Recon.csv
  - outputs/Reconciliation_Summary_YTD.csv
"""

from pathlib import Path
import pandas as pd
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))
from zoho_sync import ZohoBooks


def list_invoices(zoho: ZohoBooks, date_from: str, date_to: str) -> list[dict]:
    base = f"invoices?date_start={date_from}&date_end={date_to}&per_page=200"
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
    return items


def list_payments(zoho: ZohoBooks, date_from: str, date_to: str) -> list[dict]:
    base = f"customerpayments?date_start={date_from}&date_end={date_to}&per_page=200"
    page = 1
    items = []
    while True:
        res = zoho._api_request('GET', f"{base}&page={page}")
        if res.get('code') != 0:
            break
        items.extend(res.get('customerpayments', []))
        ctx = res.get('page_context', {})
        if not ctx.get('has_more_page'):
            break
        page += 1
    return items


def check_settlement_balances(outputs_dir: Path) -> pd.DataFrame:
    rows = []
    for folder in outputs_dir.iterdir():
        if not folder.is_dir():
            continue
        sid = folder.name
        jf = folder / f"Journal_{sid}.csv"
        if jf.exists():
            df = pd.read_csv(jf)
            deb = pd.to_numeric(df.get('Debit', 0), errors='coerce').fillna(0).sum()
            cred = pd.to_numeric(df.get('Credit', 0), errors='coerce').fillna(0).sum()
            diff = round(deb - cred, 2)
            rows.append({
                'settlement_id': sid,
                'debits': round(float(deb), 2),
                'credits': round(float(cred), 2),
                'difference': diff,
                'balanced': abs(diff) < 0.01,
            })
    return pd.DataFrame(rows)


def expected_invoices(outputs_dir: Path) -> pd.DataFrame:
    rows = []
    for folder in outputs_dir.iterdir():
        if not folder.is_dir():
            continue
        sid = folder.name
        invf = folder / f"Invoice_{sid}.csv"
        if invf.exists():
            try:
                inv = pd.read_csv(invf)
                amt_col = None
                for c in ['Invoice Line Amount', 'amount', 'rate']:
                    if c in inv.columns:
                        amt_col = c; break
                total = pd.to_numeric(inv[amt_col], errors='coerce').fillna(0).sum() if amt_col else 0.0
                rows.append({'settlement_id': sid, 'expected_invoice_count': len(inv), 'expected_invoice_total': round(float(total), 2)})
            except Exception:
                pass
    return pd.DataFrame(rows)


def main():
    root = Path(__file__).parent.parent
    outputs_dir = root / 'outputs'

    # 1) Settlement balance check
    bal_df = check_settlement_balances(outputs_dir)
    bal_df.sort_values('settlement_id').to_csv(outputs_dir / 'Settlements_Balance_Check.csv', index=False)

    # 2) Expected invoice totals from outputs
    exp_df = expected_invoices(outputs_dir)

    # 3) Pull YTD Zoho invoices and payments
    start = f"{datetime.now().year}-01-01"
    end = datetime.now().strftime('%Y-%m-%d')
    zoho = ZohoBooks()
    invs = list_invoices(zoho, start, end)
    pays = list_payments(zoho, start, end)
    inv_total = round(sum(float(i.get('total', 0) or 0) for i in invs), 2)
    pay_total = round(sum(float(p.get('amount', 0) or 0) for p in pays), 2)

    # 4) Summary
    summary = pd.DataFrame([
        {'metric': 'expected_invoice_total', 'value': round(exp_df['expected_invoice_total'].sum(), 2)},
        {'metric': 'zoho_invoice_total_ytd', 'value': inv_total},
        {'metric': 'zoho_payment_total_ytd', 'value': pay_total},
        {'metric': 'all_settlements_balanced', 'value': bool(bal_df['balanced'].all() if not bal_df.empty else True)},
    ])
    summary.to_csv(outputs_dir / 'Reconciliation_Summary_YTD.csv', index=False)

    print(f"Saved: {outputs_dir / 'Settlements_Balance_Check.csv'}")
    print(f"Saved: {outputs_dir / 'Reconciliation_Summary_YTD.csv'}")


if __name__ == '__main__':
    main()






