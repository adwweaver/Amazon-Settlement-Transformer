#!/usr/bin/env python3
"""
Query Zoho Books for invoices and payments by date range and customers,
then write a CSV with totals for reconciliation.

Usage:
  python scripts/generate_zoho_audit_report.py --from 2025-10-01 --to 2025-10-31 --customer "Amazon.ca"
"""

import argparse
from pathlib import Path
import pandas as pd
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent))
from zoho_sync import ZohoBooks


def list_invoices(zoho: ZohoBooks, customer_name: str | None, date_from: str, date_to: str) -> list[dict]:
	cust_id = None
	if customer_name:
		cust_id = zoho.get_customer_id(customer_name)
	base = f"invoices?date_start={date_from}&date_end={date_to}&per_page=200"
	if cust_id:
		base += f"&customer_id={cust_id}"
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


def list_payments(zoho: ZohoBooks, customer_name: str | None, date_from: str, date_to: str) -> list[dict]:
	cust_id = None
	if customer_name:
		cust_id = zoho.get_customer_id(customer_name)
	base = f"customerpayments?date_start={date_from}&date_end={date_to}&per_page=200"
	if cust_id:
		base += f"&customer_id={cust_id}"
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


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument('--from', dest='date_from', required=True)
	ap.add_argument('--to', dest='date_to', required=True)
	ap.add_argument('--customer', dest='customer', default=None)
	args = ap.parse_args()

	zoho = ZohoBooks()
	invs = list_invoices(zoho, args.customer, args.date_from, args.date_to)
	pays = list_payments(zoho, args.customer, args.date_from, args.date_to)

	inv_total = sum(float(i.get('total', 0) or 0) for i in invs)
	pay_total = sum(float(p.get('amount', 0) or 0) for p in pays)

	rows = [
		{"type": "invoice", "count": len(invs), "total": round(inv_total, 2)},
		{"type": "payment", "count": len(pays), "total": round(pay_total, 2)},
	]
	report = pd.DataFrame(rows)
	out = Path(__file__).parent.parent / 'outputs' / 'Zoho_Audit_Summary.csv'
	report.to_csv(out, index=False)
	print(f"Saved: {out}")
	print(report.to_string(index=False))


if __name__ == '__main__':
	main()
