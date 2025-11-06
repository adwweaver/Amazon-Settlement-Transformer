# Zoho Books API Integration - Setup Checklist

## 🔐 API Credentials Needed

✅ **Connection Found:** `amz_remit_api` (Zoho Books with full access)

### Required Information:

### 1. OAuth 2.0 Credentials (for Python Direct Access)
Since you have the Zoho connection in Creator/Flow, I need to create a matching Python connection:

- **Client ID**: `___________________________`
- **Client Secret**: `___________________________`
- **Refresh Token**: `___________________________`
  
**How to get these:**
1. Go to: https://api-console.zoho.com/
2. Click "Add Client" → "Server-based Applications"
3. Client Name: `Amazon Remittance Python`
4. Homepage URL: `http://localhost`
5. Authorized Redirect URI: `http://localhost:8080`
6. Click "Create"
7. Copy Client ID and Client Secret
8. Click "Generate Code" → Select scope: `ZohoBooks.fullaccess.all`
9. Use the code to generate Refresh Token (I'll provide script for this)

### 2. Organization Details
- **Organization ID**: `___________________________`
  - Found in: Zoho Books → Settings → Organization Profile → Organization ID
  
- **Data Center**: [ ] US | [ ] EU | [ ] IN | [ ] AU | [ ] CA | [ ] JP
  - (Check your Zoho Books URL: `books.zoho.com` = US, `books.zoho.eu` = EU, etc.)

### 3. Alternatively: Use Existing Connection via Zoho Creator
If you prefer to use your existing `amz_remit_api` connection:
- **Do you have Zoho Creator?** [ ] Yes [ ] No
- **Creator App Name** (if exists): `___________________________`
- I can build a Creator function that Python calls, which then uses your connection

---

## 📊 Chart of Accounts Mapping

### Current Amazon GL Accounts → Zoho Books Account IDs

Please provide the **Account ID** (number) from Zoho Books for each:

| Amazon GL Account | Zoho Account ID | Zoho Account Name | Account Type |
|-------------------|----------------|-------------------|--------------|
| Amazon.ca Clearing | _____________ | _________________ | Bank/Asset |
| Amazon.ca Revenue | _____________ | _________________ | Income |
| Amazon FBA Fulfillment Fees | _____________ | _________________ | Expense |
| Amazon Advertising Expense | _____________ | _________________ | Expense |
| Amazon FBA Storage Fees | _____________ | _________________ | Expense |
| Amazon FBA Inbound Freight | _____________ | _________________ | Expense |
| Amazon Account Fees | _____________ | _________________ | Expense |
| Amazon Unclassified | _____________ | _________________ | Expense |

**How to find Account IDs in Zoho Books:**
1. Go to: Accountant → Chart of Accounts
2. Click on an account name
3. Look at the URL: `https://books.zoho.com/app/.../chartofaccounts/{ACCOUNT_ID}`
4. Or use API: `GET /chartofaccounts` to list all accounts with IDs

---

## 🧪 Testing Strategy (Avoid Duplicates!)

### Phase 1: Read-Only Testing ✅ SAFE
- Test API authentication
- Query existing journal entries
- Validate GL account mapping
- **NO DATA POSTED**

### Phase 2: Sandbox/Test Settlement 🟡 CAUTION
- Use **ONE small settlement** (e.g., 23874396421 with only 4 rows)
- Add `[TEST]` prefix to reference number: `[TEST] 23874396421`
- Post to Zoho Books in **DRAFT** mode (not finalized)
- Manual review in Zoho before marking as posted
- If incorrect → Delete test entry and refine

### Phase 3: Single Production Settlement 🟠 CAREFUL
- Choose one previously processed settlement
- Add tracking field to `settlement_history.csv`: `zoho_synced = False`
- Only sync settlements where `zoho_synced == False`
- After successful sync → mark `zoho_synced = True`
- **Idempotency check**: Before posting, query Zoho for existing entries with same reference number

### Phase 4: Bulk Processing 🔴 PRODUCTION
- Process all 6 settlements (or new ones)
- Automated sync with duplicate prevention
- Error logging and retry logic

---

## 🛡️ Duplicate Prevention Mechanisms

### 1. Local Tracking in settlement_history.csv
Add columns:
```csv
zoho_journal_id,zoho_sync_status,zoho_sync_timestamp,zoho_sync_error
```

### 2. Pre-Flight Check Before Posting
```python
def check_existing_journal_entry(settlement_id):
    """Query Zoho Books for existing entry"""
    response = zoho_books.journal_entries.list(
        reference_number=settlement_id
    )
    if response['journal_entries']:
        return response['journal_entries'][0]['journal_entry_id']
    return None

# Before creating new entry:
existing_id = check_existing_journal_entry(settlement_id)
if existing_id:
    print(f"⚠️  Settlement {settlement_id} already in Zoho (ID: {existing_id})")
    return existing_id  # Skip creation
```

### 3. Dry-Run Mode
```python
# Config flag for testing
DRY_RUN = True  # Set to False only after validation

if DRY_RUN:
    print(f"[DRY RUN] Would create journal entry: {json.dumps(journal_entry, indent=2)}")
    return "DRY_RUN_ID"
else:
    return zoho_books.journal_entries.create(journal_entry)
```

### 4. Manual Approval Gate
```python
# For first few runs, require confirmation
if not AUTO_APPROVE:
    print("\n📄 Journal Entry to Post:")
    print(json.dumps(journal_entry, indent=2))
    response = input("\n✅ Post to Zoho Books? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Sync cancelled by user")
        return None
```

---

## 🏗️ Missing SKUs

You mentioned needing to build a couple SKUs. Please provide:

### SKU Details Needed:
1. **SKU Code/Number**: `_______________`
   - Description: `_______________________________`
   - Product Category: `_______________________________`
   - GL Account for Revenue: `_______________________________`
   - Unit Price: `_______________________________`

2. **SKU Code/Number**: `_______________`
   - Description: `_______________________________`
   - Product Category: `_______________________________`
   - GL Account for Revenue: `_______________________________`
   - Unit Price: `_______________________________`

**Questions:**
- Should I create these SKUs in Zoho Books via API?
- Or do you prefer to create them manually in Zoho first?
- Are these for specific Amazon products, or fee/charge types?

---

## 📋 Next Steps (Once You Provide Info Above)

1. ✅ I'll create `scripts/zoho_config.py` with your credentials (gitignored)
2. ✅ Build `scripts/zoho_sync.py` with authentication + duplicate prevention
3. ✅ Test authentication (read-only, no posting)
4. ✅ Create test journal entry with `[TEST]` prefix in DRAFT mode
5. ✅ You review test entry in Zoho Books web interface
6. ✅ If good → Delete test and proceed to single production settlement
7. ✅ Validate first production entry manually
8. ✅ Enable automated sync for future settlements

---

## 🔒 Security Notes

- Store credentials in `config/zoho_credentials.yaml` (add to .gitignore)
- Never commit API keys to git
- Use environment variables for production deployment
- Refresh token expires after 6 months (I'll add renewal logic)

---

## ❓ Questions for You

1. **Do you already have a Zoho API app created?**
   - If yes, just need Client ID/Secret
   - If no, I can guide you through creating one

2. **What permission level do you want for the integration?**
   - Full access (read + write journal entries)
   - Or read-only for now?

3. **Should journal entries be created in DRAFT or directly as POSTED?**
   - DRAFT = requires manual approval in Zoho
   - POSTED = automatic, but harder to undo

4. **Preferred testing approach:**
   - [ ] I'll test in my Zoho sandbox first
   - [ ] Test in production with `[TEST]` prefix entries
   - [ ] Start directly with dry-run mode (no actual posting)

5. **For the missing SKUs:**
   - Are these Amazon product SKUs or internal tracking codes?
   - Should they be created as Items in Zoho Books?

---

**Please fill in the details above and I'll build the integration with all safety checks in place!**
