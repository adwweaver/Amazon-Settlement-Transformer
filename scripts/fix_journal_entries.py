"""
CRITICAL FIX: Delete all journals from Zoho and regenerate with correct debit/credit logic

The original journals had expenses as CREDITS instead of DEBITS.
This script:
1. Deletes all existing Amazon settlement journals from Zoho Books
2. Regenerates local journal CSVs with corrected expense logic
3. Re-posts corrected journals to Zoho Books
"""

import logging
import sys
from pathlib import Path
from zoho_sync import ZohoBooks

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Settlement IDs to fix
SETTLEMENTS = [
    '23874396421',
    '23874397121',
    '24288684721',
    '24391894961',
    '24495221541',
    '24596907561'
]

def delete_all_journals(zoho):
    """Delete all Amazon settlement journals from Zoho Books"""
    logger.info("\n" + "="*80)
    logger.info("STEP 1: DELETE EXISTING JOURNALS FROM ZOHO")
    logger.info("="*80)
    
    deleted_count = 0
    
    for settlement_id in SETTLEMENTS:
        # Check if journal exists (using plain settlement ID as reference)
        existing_id = zoho.check_existing_journal(settlement_id)
        
        if existing_id:
            logger.info(f"\n🗑️  Deleting journal for settlement {settlement_id}")
            logger.info(f"   Reference: {settlement_id}")
            logger.info(f"   Journal ID: {existing_id}")
            
            try:
                # Delete the journal
                result = zoho._api_request('DELETE', f'journals/{existing_id}')
                
                if result.get('code') == 0:
                    logger.info(f"   ✅ Deleted successfully")
                    deleted_count += 1
                else:
                    logger.error(f"   ❌ Failed to delete: {result}")
            except Exception as e:
                logger.error(f"   ❌ Error deleting: {e}")
        else:
            logger.info(f"\n⏩ Settlement {settlement_id} - No journal found in Zoho")
    
    logger.info(f"\n📊 Deleted {deleted_count}/{len(SETTLEMENTS)} journals")
    return deleted_count


def regenerate_journals():
    """Regenerate all journal CSV files with corrected debit/credit logic"""
    logger.info("\n" + "="*80)
    logger.info("STEP 2: REGENERATE JOURNAL CSV FILES")
    logger.info("="*80)
    logger.info("\nℹ️  Run the main pipeline to regenerate journals:")
    logger.info("   python scripts/main.py")
    logger.info("\n⚠️  The exports.py file has been updated with correct expense logic.")
    logger.info("   Expenses will now be DEBITS (not credits).")
    return False


def repost_journals(zoho):
    """Re-post all journals to Zoho Books"""
    logger.info("\n" + "="*80)
    logger.info("STEP 3: RE-POST JOURNALS TO ZOHO")
    logger.info("="*80)
    logger.info("\nℹ️  Run sync for each settlement:")
    logger.info("   python scripts/sync_settlement.py <settlement_id>")
    logger.info("\n   Or run all at once:")
    for settlement_id in SETTLEMENTS:
        logger.info(f"   python scripts/sync_settlement.py {settlement_id}")
    return False


def main():
    print("="*80)
    print("CRITICAL FIX: CORRECT EXPENSE DEBIT/CREDIT LOGIC")
    print("="*80)
    print("\n⚠️  WARNING: This will delete ALL existing journals from Zoho Books!")
    print("   The journals will need to be regenerated and re-posted.\n")
    
    response = input("Do you want to proceed? (yes/no): ")
    
    if response.lower() != 'yes':
        print("\nOperation cancelled.")
        sys.exit(0)
    
    # Connect to Zoho
    logger.info("\n🔐 Connecting to Zoho Books...")
    zoho = ZohoBooks()
    
    # Step 1: Delete existing journals
    deleted_count = delete_all_journals(zoho)
    
    if deleted_count > 0:
        logger.info("\n✅ Step 1 complete: Journals deleted from Zoho")
    else:
        logger.info("\n⚠️  No journals found to delete")
    
    # Step 2: Instructions for regenerating
    regenerate_journals()
    
    # Step 3: Instructions for re-posting
    repost_journals(zoho)
    
    logger.info("\n" + "="*80)
    logger.info("NEXT STEPS")
    logger.info("="*80)
    logger.info("""
1. Regenerate journal CSV files:
   python scripts/main.py
   
2. Re-post journals to Zoho (one at a time or create batch script):
   python scripts/sync_settlement.py 23874396421
   python scripts/sync_settlement.py 23874397121
   python scripts/sync_settlement.py 24288684721
   python scripts/sync_settlement.py 24391894961
   python scripts/sync_settlement.py 24495221541
   python scripts/sync_settlement.py 24596907561

3. Verify with reconciliation report:
   python scripts/verify_sync.py
""")


if __name__ == "__main__":
    main()
