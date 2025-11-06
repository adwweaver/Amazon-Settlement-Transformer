#!/usr/bin/env python3
"""
Generate a consolidated report of posted invoices and payments per settlement.

Output: outputs/Posted_To_Zoho_Report.csv with columns:
  settlement_id, journal_id, invoice_count, invoice_total, payment_count, payment_total
"""

import pandas as pd
from pathlib import Path


def main():
    root = Path(__file__).parent.parent
    outputs_dir = root / 'outputs'
    from paths import get_settlement_history_path
    hist_file = get_settlement_history_path()

    history = None
    if hist_file.exists():
        try:
            history = pd.read_csv(hist_file, dtype={'settlement_id': str, 'zoho_journal_id': str})
        except Exception:
            history = None

    rows = []
    for folder in outputs_dir.iterdir():
        if not folder.is_dir():
            continue
        sid = folder.name

        inv_file = folder / f'Invoice_{sid}.csv'
        pay_file = folder / f'Payment_{sid}.csv'

        invoice_count = 0
        invoice_total = 0.0
        payment_count = 0
        payment_total = 0.0

        if inv_file.exists():
            try:
                inv = pd.read_csv(inv_file)
                invoice_count = len(inv)
                # Prefer Invoice Line Amount; fallback to rate/amount columns
                amt_col = None
                for c in ['Invoice Line Amount', 'amount', 'rate']:
                    if c in inv.columns:
                        amt_col = c
                        break
                if amt_col:
                    invoice_total = pd.to_numeric(inv[amt_col], errors='coerce').fillna(0).sum()
            except Exception:
                pass

        if pay_file.exists():
            try:
                pay = pd.read_csv(pay_file)
                payment_count = len(pay)
                amt_col = None
                for c in ['Payment Amount', 'amount']:
                    if c in pay.columns:
                        amt_col = c
                        break
                if amt_col:
                    payment_total = pd.to_numeric(pay[amt_col], errors='coerce').fillna(0).sum()
            except Exception:
                pass

        journal_id = ''
        if history is not None:
            match = history[history['settlement_id'] == sid]
            if not match.empty and 'zoho_journal_id' in match.columns:
                journal_id = str(match['zoho_journal_id'].iloc[0])

        rows.append({
            'settlement_id': sid,
            'journal_id': journal_id,
            'invoice_count': int(invoice_count),
            'invoice_total': round(float(invoice_total), 2),
            'payment_count': int(payment_count),
            'payment_total': round(float(payment_total), 2),
        })

    report = pd.DataFrame(rows).sort_values('settlement_id')
    out_file = outputs_dir / 'Posted_To_Zoho_Report.csv'
    report.to_csv(out_file, index=False)
    print(f"Saved: {out_file}")


if __name__ == '__main__':
    main()




