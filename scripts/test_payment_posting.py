#!/usr/bin/env python3
"""
Test payment posting with a single settlement to verify the fix.

Usage:
    python scripts/test_payment_posting.py <settlement_id>
    
Example:
    python scripts/test_payment_posting.py 24596907561
"""

import sys
import logging
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sync_settlement import post_settlement_complete

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_payment_posting.py <settlement_id>")
        print("Example: python scripts/test_payment_posting.py 24596907561")
        sys.exit(1)
    
    settlement_id = sys.argv[1]
    
    print("="*80)
    print(f"TESTING PAYMENT POSTING FOR SETTLEMENT: {settlement_id}")
    print("="*80)
    print()
    print("This will post ONLY payments for this settlement.")
    print("Journals and invoices will be skipped.")
    print()
    
    # Post only payments
    results = post_settlement_complete(
        settlement_id,
        post_journal=False,
        post_invoices=False,
        post_payments=True,
        dry_run=False,
        override=False
    )
    
    print()
    print("="*80)
    print("TEST RESULTS")
    print("="*80)
    print(f"Settlement ID: {settlement_id}")
    print(f"Payments Posted: {results['payments']['count']}")
    print(f"Payment IDs: {results['payments']['ids'][:10]}...")  # Show first 10
    if results['payments']['error']:
        print(f"Error: {results['payments']['error']}")
    print()
    
    if results['payments']['posted']:
        print("✅ PAYMENT POSTING TEST SUCCESSFUL!")
        print(f"   Posted {results['payments']['count']} payment(s)")
    else:
        print("❌ PAYMENT POSTING TEST FAILED")
        print(f"   Error: {results['payments'].get('error', 'Unknown error')}")
        print()
        print("Check logs/zoho_sync.log and logs/payment_errors.log for details")
        sys.exit(1)


if __name__ == "__main__":
    main()






