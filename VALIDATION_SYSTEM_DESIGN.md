# Amazon Settlement → Zoho Books Integration System
## Validation, Approval & LLM-Assisted Workflow Design

---

## 🎯 SYSTEM OVERVIEW

### Current Status (As of Oct 30, 2025)
- ✅ **6 settlements processed** (Jun-Oct 2025, 2,116 transactions)
- ✅ **1 settlement in Zoho** (23874396421)
- ⏳ **5 settlements pending** (all validated, ready to sync)
- ✅ **All GL accounts mapped**
- ⚠️ **SKU verification now applies mapping + live Zoho check**

---

## 🛡️ VALIDATION GATES - "STOP SIGN" SYSTEM

### **Gate 1: Journal Balance** ❌ BLOCKING
**Rule:** Debits MUST equal Credits (tolerance: ±$0.01 for rounding)

**What happens if failed:**
- 🔴 **STOP** - Cannot proceed
- Error message: "Journal out of balance by $X.XX"
- **User actions:**
  1. Review raw settlement CSV for data issues
  2. Check transformation logic in `scripts/transform.py`
  3. Manually adjust journal entries if necessary
  4. **Override option:** Admin can force-approve with justification note

**Why it matters:** Unbalanced journals corrupt your books

---

### **Gate 2: GL Account Mapping** ❌ BLOCKING
**Rule:** Every GL account in journal must have Zoho Books Account ID mapping

**What happens if failed:**
- 🔴 **STOP** - Cannot proceed
- Error message: "Unmapped accounts: Amazon Combined Tax Charged, Amazon XYZ"
- **User actions:**
  1. **Automatic suggestion:** System searches Zoho for similar account names
  2. **LLM-assisted:** "This looks like a tax liability account. Suggested mapping: GST/HST Collected (ID: 73985...)"
  3. User confirms or corrects
  4. Mapping saved to `config/zoho_gl_mapping.yaml`
  5. Validation re-runs automatically

**Why it matters:** Unmapped accounts get skipped, causing imbalance

---

### **Gate 3: SKU Verification** ⚠️ WARNING
**Rule:** SKUs in invoices should exist in Zoho Books Items/Products (after applying local SKU mapping)

**What happens if failed:**
- ⚠️ **WARNING** - Can proceed with confirmation
- Warning message: "SKUs not found in Zoho after mapping: <list>"
- **User actions:**
  1. **Auto-check:** System queries Zoho Books Items API to verify SKU exists
  2. If missing:
     - **Option A:** Skip invoice posting (journal only)
     - **Option B:** Create SKU in Zoho Books first
     - **Option C:** LLM assists: "SALTT30-ALLT appears to be 'Sea Salt Toffee 30oz - All Toffee'. Similar to SALTT15-ALLT. Create with same category and tax rules?"
  3. User bulk-creates SKUs or proceeds without invoices

**Why it matters:** Missing SKUs prevent invoice creation, but journal can still post

---

### **Gate 4: Duplicate Detection** ⚠️ WARNING
**Rule:** Settlement ID should not already exist in Zoho Books

**What happens if detected:**
- ⚠️ **WARNING** - Settlement already exists
- Message: "Settlement 23874396421 already in Zoho (Journal ID: 73985000000099004)"
- **User actions:**
  1. **Skip** - Mark as synced in local database
  2. **Review** - Open Zoho to verify entry is correct
  3. **Delete & Re-post** - If original entry has errors (requires admin)

**Why it matters:** Prevents duplicate financial entries

---

### **Gate 5: Settlement Date Validation** ⚠️ WARNING
**Rule:** Settlement date should be within reasonable range (not future, not >2 years old)

**What happens if failed:**
- ⚠️ **WARNING** - Unusual date detected
- Message: "Settlement date is 3 months in the future. Proceed?"
- **User actions:**
  1. Confirm date is correct (Amazon sometimes updates dates)
  2. Adjust date if data error
  3. Proceed with confirmation

**Why it matters:** Catches data entry errors, wrong fiscal period postings

---

## 🤖 LLM-ASSISTED FEATURES

### **1. GL Account Mapping Assistant**
**Scenario:** New Amazon fee type appears: "Amazon Climate Pledge Fee"

**LLM Workflow:**
```
User: "Unknown GL account: Amazon Climate Pledge Fee"

LLM analyzes:
- Context: Appears in settlements as a credit (fee charged to merchant)
- Similar accounts: Amazon Account Fees, Amazon FBA Fees
- Amount pattern: Small ($0.50-$2.00), appears on most orders

LLM suggests:
"This appears to be a new Amazon operational fee. Recommended mapping:
  → Amazon Account Fees (ID: 73985000000058003)
  → Or create new account: 'Amazon Climate Fees' under Expenses

Rationale: Consistent with other Amazon service fees. Should be expensed."

User: "Create new account"
LLM: "I'll guide you:
  1. In Zoho Books → Accountant → Chart of Accounts → New Account
  2. Account Name: Amazon Climate Pledge Fees
  3. Account Type: Expense
  4. Parent: Amazon.ca Selling Expenses
  5. After creating, paste the Account ID here and I'll update the mapping."
```

---

### **2. SKU Creation Assistant**
**Scenario:** 18 SKUs in settlement, only 2 exist in Zoho

**LLM Workflow:**
```
User: "Missing SKUs: SALTT30-ALLT, SALTT30-FRUT, SALTT30-BLUE..."

LLM analyzes:
- Pattern recognition: SALTT[size]-[flavor]
- Existing SKU: SALTT15-ALLT (15oz All Toffee, $29.99, Sales Tax: GST+PST)

LLM suggests:
"These are 30oz variants of your existing Sea Salt Toffee line.
I can generate a bulk import CSV for Zoho Books Items with:

| SKU | Product Name | Description | Category | Price | Tax |
|-----|--------------|-------------|----------|-------|-----|
| SALTT30-ALLT | Sea Salt Toffee 30oz - All Toffee | Flagship blend | Toffee | $49.99 | GST+PST |
| SALTT30-FRUT | Sea Salt Toffee 30oz - Fruity | Fruit-forward blend | Toffee | $49.99 | GST+PST |
...

Should I:
  A) Generate bulk import CSV (paste into Zoho Books)
  B) Create via API (requires Items API access)
  C) Show you the Zoho manual entry steps"

User: "Generate CSV"
LLM: *creates CSV* "Here's your import file. Upload in Zoho Books → Items → Import → CSV"
```

---

### **3. Out-of-Balance Investigator**
**Scenario:** Journal shows $2,539.66 debits, $2,541.12 credits (diff: $1.46)

**LLM Workflow:**
```
System: "Journal out of balance by $1.46"

LLM investigates:
- Scans journal entries for rounding errors
- Checks for missing offsetting entries
- Looks for tax calculation discrepancies

LLM reports:
"I found the issue:
- Line 47: Amazon Combined Tax Charged shows $1.46 credit
- This tax was calculated on advertising fees ($11.23 * 13% = $1.46)
- But the offsetting debit is missing (should be Amazon.ca Clearing)

Recommended fix:
- Add line: Amazon.ca Clearing, Debit $1.46, Description: 'Tax adjustment'
- Or review if tax should be netted differently

Would you like me to:
  A) Auto-add the offsetting entry
  B) Show me the original Amazon CSV row
  C) Mark for manual review"
```

---

### **4. Multi-Settlement Batch Processor**
**Scenario:** User wants to sync all 5 pending settlements

**LLM Workflow:**
```
User: "Sync all pending settlements"

LLM pre-flight:
"Running validation on 5 settlements...

✅ 23874397121: Ready (1 SKU to verify)
✅ 24288684721: Ready (17 SKUs to verify)
✅ 24391894961: Ready (16 SKUs to verify)
✅ 24495221541: Ready (15 SKUs to verify)
✅ 24596907561: Ready (16 SKUs to verify)

⚠️ Total: 18 unique SKUs need verification

Options:
  1. Sync journals only (skip invoices) - FAST, SAFE
  2. Verify all SKUs first, then full sync - COMPLETE
  3. Sync one-by-one with review - CAREFUL

Recommendation: Option 1 for first run. You can add invoices later.

Proceed with journals-only sync? (yes/no)"

User: "yes"
LLM: "Syncing 5 settlements to Zoho Books..."
*Shows progress bar*
"✅ Complete: 5 journals posted, 0 invoices, 0 payments
 Total journal lines: 1,671
 Zoho Journal IDs: 739850000001xxxxx-xxxxxx

Next: Run Dashboard export to verify sync status"
```

---

## 📱 APP ARCHITECTURE - STREAMLIT WITH LLM BACKSTOP

### **Tech Stack**
- **Frontend:** Streamlit (Python web app)
- **Backend:** Existing Python scripts (main.py, zoho_sync.py, exports.py)
- **LLM:** OpenAI API (GPT-4) or Azure OpenAI for analysis/suggestions
- **Database:** SQLite (upgrade from CSV for better tracking)
- **File Storage:** Local filesystem + optional SharePoint sync

---

### **App Structure**

```
📱 AMAZON → ZOHO SETTLEMENT APP
├── 🏠 Home Dashboard
│   ├── Settlement Status Overview (synced/pending counts)
│   ├── Recent Activity Feed
│   └── Quick Actions (Upload CSV, Sync All, View Dashboard)
│
├── 📥 Upload & Process
│   ├── Drag-drop Amazon settlement CSV
│   ├── Real-time validation with progress bar
│   ├── Automatic GL extraction & journal generation
│   └── Output preview (journal, invoice, payment tabs)
│
├── ✅ Validation & Approval
│   ├── Settlement list with status indicators
│   ├── Click settlement → detailed validation report
│   ├── **LLM Assistant** panel (right sidebar)
│   │   - Explains each warning/error in plain English
│   │   - Suggests fixes with code snippets
│   │   - "Fix automatically" buttons
│   ├── Approve/Reject buttons with notes
│   └── Bulk operations (approve all, sync all)
│
├── 🔄 Sync to Zoho
│   ├── Select settlements to sync
│   ├── Choose what to post: Journals / Invoices / Payments
│   ├── Dry-run mode (preview without posting)
│   ├── Live sync with real-time status
│   ├── Error handling with retry logic
│   └── Confirmation emails/notifications
│
├── 📊 Dashboard & Reports
│   ├── Embedded Excel viewer (Dashboard_Summary.xlsx)
│   ├── GL Account Breakdown charts
│   ├── Settlement timeline view
│   ├── Zoho sync audit log
│   └── Export options (PDF, Excel, CSV)
│
├── ⚙️ Settings & Config
│   ├── GL Account Mapping editor
│   ├── SKU/Item Management
│   ├── Zoho credentials (OAuth refresh)
│   ├── Validation rules config
│   └── LLM settings (model, temperature)
│
└── 💬 LLM Chat (Global)
    ├── "Ask anything about your settlements"
    ├── Context-aware (knows current settlement, history)
    ├── Can execute actions: "Create SKU for SALTT30-BLUE"
    └── Learning mode: remembers user preferences
```

---

### **LLM Integration Points**

**1. Validation Analysis** (scripts/validate_settlement.py)
```python
def explain_validation_error(error_type, error_data):
    """LLM explains validation errors in plain English"""
    prompt = f"""
    A user is syncing Amazon settlements to Zoho Books.
    Validation error: {error_type}
    Data: {error_data}
    
    Explain:
    1. What this error means
    2. Why it matters
    3. How to fix it (step-by-step)
    4. Suggest automatic fixes if possible
    
    Be concise and actionable.
    """
    return openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a Zoho Books accounting expert."},
                  {"role": "user", "content": prompt}]
    )
```

**2. GL Account Suggestions** (scripts/zoho_sync.py)
```python
def suggest_gl_mapping(account_name, journal_context):
    """LLM suggests Zoho account for unmapped GL"""
    # Query Zoho for all accounts
    zoho_accounts = zoho_client.get_chart_of_accounts()
    
    prompt = f"""
    Amazon settlement has GL account: "{account_name}"
    Journal context: {journal_context}  # Debit/credit, amounts, description
    
    Available Zoho accounts:
    {zoho_accounts}
    
    Suggest the best matching Zoho account ID and explain why.
    If no good match, suggest creating a new account with details.
    """
    # LLM returns suggested mapping with reasoning
```

**3. SKU Bulk Creator** (scripts/zoho_items.py - NEW)
```python
def generate_sku_import(missing_skus, existing_skus_sample):
    """LLM generates bulk SKU import data"""
    prompt = f"""
    Generate Zoho Books Items import data for these SKUs:
    {missing_skus}
    
    Based on existing similar SKUs:
    {existing_skus_sample}
    
    For each SKU, provide:
    - Product Name
    - Description
    - Category
    - Unit Price (estimate from size/similar items)
    - Tax (GST+PST for Canada)
    - Account for Sales (same as existing)
    
    Output as CSV format.
    """
```

---

## 🔐 SECURITY & PERMISSIONS

### **User Roles**
1. **Viewer** - Can see settlements, dashboards (read-only)
2. **Processor** - Can upload, process, validate settlements
3. **Approver** - Can approve settlements for Zoho sync
4. **Admin** - Full access + override validation gates

### **Audit Trail**
Every action logged:
- Who uploaded settlement
- Who approved/rejected
- Who synced to Zoho
- What changes were made (GL mappings, SKUs)
- Override justifications

---

## 📁 FILES INVOLVED IN WORKFLOW

### **3 Files Per Settlement:**
1. **Journal CSV** - GL entries (REQUIRED)
   - Validated: Balance, GL mappings
   - Posted to: Zoho Books → Manual Journals
   
2. **Invoice CSV** - Customer invoices (OPTIONAL)
   - Validated: SKUs exist, customer exists
   - Posted to: Zoho Books → Invoices
   - Creates: Sales records, AR entries
   
3. **Payment CSV** - Payment applications (OPTIONAL)
   - Validated: Invoice exists, amounts match
   - Posted to: Zoho Books → Payments Received
   - Updates: Invoice paid status

### **Sync Options:**
- **Journal Only** (Default) - Fast, safe, balances books
- **Journal + Invoices** - Requires SKUs, creates sales records
- **Full Sync** - Journal + Invoices + Payments (complete workflow)

---

## 🚀 IMPLEMENTATION ROADMAP

### **Phase 1: Streamlit MVP** (1-2 weeks)
- [ ] Basic UI with upload & validation
- [ ] Settlement list with status indicators
- [ ] Manual approval workflow
- [ ] Sync journals only (existing scripts)
- [ ] Simple validation reports

### **Phase 2: LLM Integration** (2-3 weeks)
- [ ] OpenAI API integration
- [ ] GL mapping suggestions
- [ ] SKU creation assistant
- [ ] Chat interface for questions
- [ ] Validation error explanations

### **Phase 3: Advanced Features** (3-4 weeks)
- [ ] Batch operations with progress tracking
- [ ] Invoice & payment posting
- [ ] SKU management UI
- [ ] Zoho Items API integration
- [ ] Automated email notifications
- [ ] Dashboard embedding

### **Phase 4: Production Hardening** (2-3 weeks)
- [ ] User authentication & roles
- [ ] Audit logging to database
- [ ] Error recovery & retry logic
- [ ] Rate limit handling
- [ ] Backup & rollback features
- [ ] Deployment (Azure/AWS)

---

## 💡 KEY DECISIONS NEEDED

1. **Invoice Posting Strategy:**
   - Post all invoices immediately? Or journal-first, invoices later?
   - **Recommendation:** Journal-first (safer, faster)

2. **SKU Management:**
   - Pre-create all SKUs in Zoho manually?
   - Or build SKU auto-creation in app?
   - **Recommendation:** Bulk-create 18 SKUs now, then auto-create new ones

3. **LLM Provider:**
   - OpenAI (easier) vs Azure OpenAI (enterprise)
   - **Recommendation:** Start with OpenAI, migrate to Azure if needed

4. **Deployment:**
   - Local Streamlit vs cloud-hosted?
   - **Recommendation:** Start local, deploy to Azure App Service later

5. **Approval Workflow:**
   - Single approver vs multi-stage approval?
   - **Recommendation:** Single approver initially

---

## ✅ IMMEDIATE NEXT STEPS

1. **Sync Settlement 23874397121** (today)
   - 1 SKU to verify: SALTT15-ALLT
   - Journal balanced, all GL mapped
   - Post journal only for now

2. **Bulk-create 18 SKUs in Zoho** (today/tomorrow)
   - Use SKU list from validation report
   - LLM can generate import CSV

3. **Decide on Streamlit app** (this week)
   - Worth building? Or stick with command-line scripts?
   - **My recommendation:** Yes, build it - saves time long-term

4. **Sync remaining 4 settlements** (this week)
   - After SKUs created
   - Can do all at once or one-by-one

---

**Ready to proceed?** Which would you like to tackle first:
- A) Sync settlement 23874397121 now (test case)
- B) Design Streamlit app mockup
- C) Create SKU bulk import CSV
- D) Discuss LLM integration architecture
