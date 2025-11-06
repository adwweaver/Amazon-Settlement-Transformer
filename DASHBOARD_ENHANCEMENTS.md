# Dashboard Enhancements & Error Tracking

## ✅ Current Status
- **Multi-tab Dashboard** with 4 tabs successfully implemented:
  1. Current Settlements - Processing status with validation checks
  2. GL Account Summary - Financial view (30/60/90-day + YTD)
  3. Monthly Trends - 12-month GL account history
  4. Historical Log - Complete settlement processing records

- **GL Account Data** now populating correctly with timezone fixes applied

---

## 🎯 RECOMMENDED: Zoho Integration for Automated Tracking

### Concept
Automatically sync settlement processing data to Zoho Books/Analytics for reporting without manual intervention.

### Architecture Options

#### **Option A: Direct Zoho Books API Integration**
Push data directly to Zoho Books as journal entries are created.

**Flow:**
1. Python processes settlements → generates Journal/Invoice/Payment CSVs
2. During export generation, automatically POST to Zoho Books API
3. Zoho Books creates/updates:
   - Journal Entries (for GL transactions)
   - Bills/Invoices (for FBA fees, advertising charges)
   - Bank Deposits (for settlement amounts)
4. Zoho Books tracks status internally (Draft → Posted → Reconciled)
5. Users access Zoho Books reports for tracking (no separate Excel needed)

**API Endpoints:**
```python
# Zoho Books API v3
POST /api/v3/journalentries  # Create journal entry
POST /api/v3/bills  # Create bill for Amazon fees
POST /api/v3/bankaccounts/{account_id}/deposits  # Record bank deposit
GET /api/v3/journalentries  # Query status
```

**Benefits:**
- ✅ Single source of truth (Zoho Books)
- ✅ No Excel file distribution needed
- ✅ Built-in Zoho reporting/dashboards
- ✅ Audit trail automatically maintained
- ✅ Multi-user access with permissions
- ✅ Mobile access through Zoho app

**Challenges:**
- 🔧 Requires Zoho Books subscription & API access
- 🔧 Need to map Amazon data → Zoho chart of accounts
- 🔧 Authentication setup (OAuth 2.0)
- 🔧 Error handling for API failures

---

#### **Option B: Zoho Analytics Integration**
Push summary data to Zoho Analytics for custom dashboards and reporting.

**Flow:**
1. Python processes settlements
2. After generating Dashboard, upload data to Zoho Analytics workspace
3. Zoho Analytics creates interactive dashboards
4. Users access via Zoho Analytics web interface

**API Endpoints:**
```python
# Zoho Analytics API
POST /api/{workspace}/tables/{table}/data  # Bulk upload
POST /api/{workspace}/tables/{table}/rows  # Add single row
```

**Tables to Create:**
- `settlement_history` - One row per settlement processed
- `journal_entries` - All GL transactions
- `validation_errors` - Any processing errors
- `processing_log` - Timestamp, user, status for each run

**Benefits:**
- ✅ Separate from accounting system (cleaner)
- ✅ Custom dashboards/visualizations
- ✅ Scheduled reports via email
- ✅ Easier API (less complex than Books)
- ✅ Can combine with other data sources

**Challenges:**
- 🔧 Requires Zoho Analytics subscription
- 🔧 Separate from actual accounting data
- 🔧 Authentication setup

---

#### **Option C: Zoho Creator Custom App**
Build a custom Zoho Creator app specifically for Amazon settlement tracking.

**Flow:**
1. Python uploads processed data to Zoho Creator via API
2. Creator app provides:
   - Custom forms for manual entry (if needed)
   - Automated workflows (notifications, approvals)
   - Custom reports and dashboards
   - Mobile app automatically generated

**Benefits:**
- ✅ Fully customized to your workflow
- ✅ Can integrate with other Zoho apps (Books, CRM, etc.)
- ✅ Low-code/no-code interface for modifications
- ✅ Workflow automation (email alerts, approvals)
- ✅ Role-based access control

**Challenges:**
- 🔧 Initial setup time
- 🔧 Requires Zoho Creator subscription
- 🔧 Learning curve for Creator platform

---

### 🎯 Recommended Implementation: Zoho Books Direct Integration

**Why Books over Analytics:**
- Already your accounting system
- No duplicate data entry
- Financial reports already exist
- Bank reconciliation built-in
- Audit trail automatic

**Implementation Phases:**

#### **Phase 1: Setup & Authentication (Week 1)**
```python
# Install Zoho SDK
pip install zohobooks

# Configuration
ZOHO_CLIENT_ID = "your_client_id"
ZOHO_CLIENT_SECRET = "your_client_secret"
ZOHO_REDIRECT_URI = "http://localhost"
ZOHO_ORGANIZATION_ID = "your_org_id"

# OAuth 2.0 flow - one-time setup
# Generates refresh token for automated access
```

#### **Phase 2: Chart of Accounts Mapping (Week 1)**
```python
# Map Amazon GL accounts → Zoho Books accounts
GL_ACCOUNT_MAPPING = {
    "Amazon.ca Clearing": "1050",  # Zoho account ID
    "Amazon.ca Revenue": "4000",
    "Amazon FBA Fulfillment Fees": "6100",
    "Amazon Advertising Expense": "6200",
    # ... etc
}
```

#### **Phase 3: Journal Entry Sync (Week 2)**
```python
# New module: scripts/zoho_sync.py

def sync_journal_to_zoho(journal_df, settlement_id):
    """Push journal entries to Zoho Books"""
    
    # Group by GL account
    entries = []
    for _, row in journal_df.iterrows():
        entries.append({
            "account_id": GL_ACCOUNT_MAPPING[row['GL_Account']],
            "debit_or_credit": "debit" if row['Debit'] > 0 else "credit",
            "amount": row['Debit'] or row['Credit'],
            "description": f"Amazon Settlement {settlement_id} - {row['Description']}"
        })
    
    # Create journal entry in Zoho
    journal_entry = {
        "journal_date": row['Posted_Date'],
        "reference_number": settlement_id,
        "notes": f"Amazon Remittance - Auto-imported",
        "line_items": entries
    }
    
    response = zoho_books.journal_entries.create(journal_entry)
    return response['journal_entry']['journal_entry_id']
```

#### **Phase 4: Status Tracking (Week 2-3)**
```python
# After sync, record in settlement_history
settlement_data = {
    ...
    'zoho_journal_id': journal_entry_id,
    'zoho_sync_status': 'SUCCESS',
    'zoho_sync_timestamp': datetime.now()
}

# Later, can query Zoho to check if posted/reconciled
status = zoho_books.journal_entries.get(journal_entry_id)
# Update local records with Zoho status
```

#### **Phase 5: Error Handling & Retry Logic (Week 3)**
```python
def sync_with_retry(data, max_retries=3):
    for attempt in range(max_retries):
        try:
            return sync_journal_to_zoho(data)
        except ZohoAPIError as e:
            if e.code == 'RATE_LIMIT':
                time.sleep(60)  # Wait and retry
            elif e.code == 'INVALID_DATA':
                log_error_to_csv(e)  # Skip and continue
                break
            else:
                raise  # Fatal error
```

---

### 📊 Zoho Books Dashboard Reports (No Code Needed!)

Once data is in Zoho Books, users can access built-in reports:

1. **Journal Entry Report** - All Amazon transactions
2. **Trial Balance** - GL account totals
3. **Profit & Loss** - Revenue vs expenses (filtered by Amazon)
4. **Bank Reconciliation** - Match settlements to bank deposits
5. **Custom Reports** - Build in Zoho interface

**Plus:**
- 📧 Schedule reports to email automatically
- 📱 Access via Zoho Books mobile app
- 🔍 Search/filter by settlement ID, date range, GL account
- ✅ Multi-user collaboration with audit trail

---

### 💡 Hybrid Approach (Best of Both Worlds)

**Keep Excel for initial validation** + **Use Zoho for final tracking**

**Workflow:**
1. Python processes settlements → generates CSVs + Dashboard.xlsx
2. User reviews Dashboard locally (quick validation)
3. If validation passes → Auto-sync to Zoho Books
4. Zoho Books becomes "system of record" for tracking status
5. Excel Dashboard archived to SharePoint for backup

**Benefits:**
- Excel Dashboard = Quick offline review
- Zoho Books = Long-term tracking and reporting
- Best of both worlds

---

### 🚀 Quick Start: Minimal Zoho Integration

**What You Need:**
1. Zoho Books subscription (or trial)
2. API access enabled (in Zoho Books settings)
3. Create Zoho API app to get credentials
4. Install Python SDK: `pip install zohobooks`

**Implementation Time:**
- Basic journal sync: 2-3 days
- Error handling + retry: 1-2 days
- Testing with real data: 2-3 days
- **Total: 1-2 weeks** for production-ready integration

---

### 🎯 Next Steps

**Decision Points:**
1. Do you already have Zoho Books? (or other Zoho apps?)
2. Who needs access to the tracking data? (accounting team, ops, management?)
3. Do you want real-time sync or batch processing (daily/weekly)?
4. Should validation errors block Zoho sync, or log and continue?

**I can help you:**
- Set up Zoho API authentication
- Build the `zoho_sync.py` module
- Create GL account mappings
- Implement error handling and retry logic
- Test with your actual settlement data

**Would you like me to start building the Zoho Books integration?**

---

## 📊 Option 1: Integrate Entry_Status.xlsx into Dashboard (Previous Option - Keep for Reference)

### Concept
Add a 5th tab to Dashboard_Summary.xlsx that shows the Entry_Status tracking information.

### Implementation
**Pros:**
- Single file for users to reference
- Consistent Excel experience
- Easy to distribute
- No additional infrastructure needed

**Cons:**
- Entry_Status.xlsx is currently in SharePoint root (different location than Dashboard)
- Would need to decide: merge into one file, or keep separate?
- Entry_Status has interactive dropdowns for status updates - these wouldn't work in a read-only Dashboard tab

### Code Changes Needed:
```python
# In exports.py generate_dashboard_summary():
# Load Entry_Status data
entry_status_file = Path("path/to/Entry_Status.xlsx")
if entry_status_file.exists():
    entry_status_df = pd.read_excel(entry_status_file)
    entry_status_df.to_excel(writer, index=False, sheet_name='Upload Tracker')
```

**Recommendation:** Create a **read-only view** of Entry_Status as "Upload Tracker" tab showing recent uploads with status, but keep the interactive Entry_Status.xlsx separate for data entry.

---

## 📊 Option 2: Enhanced Entry_Status with Error Tracking

### Concept
Expand Entry_Status.xlsx to include error logging columns.

### New Columns to Add:
- **Error_Count**: Number of validation errors encountered
- **Error_Type**: Category (Missing Data, Format Error, Balance Error, etc.)
- **Error_Details**: Specific error messages
- **Error_Timestamp**: When errors were detected
- **Resolution_Notes**: How errors were fixed
- **Assigned_To**: Person responsible for fixing

### Implementation:
```python
# In tracking.py EntryTracker class:
def record_error(self, settlement_id, error_type, error_details):
    """Record processing errors for a settlement"""
    # Update Entry_Status with error information
    # Increment error count
    # Log error timestamp
    pass

def mark_resolved(self, settlement_id, resolution_notes, resolved_by):
    """Mark errors as resolved"""
    # Clear error flags
    # Record resolution details
    pass
```

**Pros:**
- All tracking in one place
- Historical error patterns visible
- Can identify recurring issues
- Audit trail for error resolution

**Cons:**
- File becomes more complex
- Needs more user training
- Excel file can become large over time

---

## 🎫 Option 3: Simple Error Ticket System

### Concept
Create a separate **Error_Tickets.xlsx** workbook for tracking issues.

### Structure:
| Ticket_ID | Settlement_ID | Date_Reported | Error_Type | Description | Status | Assigned_To | Resolution | Date_Resolved |
|-----------|---------------|---------------|------------|-------------|--------|-------------|------------|---------------|
| ERR-001 | 24391894961 | 2025-10-26 | Balance Error | LineCount ≠ 0 | Open | John | | |
| ERR-002 | 24288684721 | 2025-10-25 | Missing Data | No invoice data | Resolved | Sarah | Re-uploaded | 2025-10-26 |

### Auto-Generation:
```python
# In validation functions, whenever an error is detected:
def log_error_ticket(settlement_id, error_type, description):
    """Automatically create error ticket when validation fails"""
    ticket_id = f"ERR-{datetime.now().strftime('%Y%m%d%H%M')}"
    # Append to Error_Tickets.xlsx
    pass
```

**Pros:**
- Dedicated error tracking
- Can assign tickets to team members
- Clear workflow: Open → In Progress → Resolved
- Easy to filter and report on errors
- Can export/email error reports

**Cons:**
- Another file to manage
- Requires process for checking tickets
- Needs integration with processing pipeline

---

## 🌐 Option 4: Web-Based Error Portal (Advanced)

### Concept
Create a simple web interface using **Streamlit** or **Flask** for error reporting and tracking.

### Features:
- View all settlements and their status
- Click to see detailed validation results
- Submit error tickets with descriptions
- Upload corrected files
- Email notifications when errors occur
- Dashboard showing error trends

### Tech Stack:
- **Streamlit**: Easy to build, Python-based, no HTML/CSS needed
- **SQLite**: Lightweight database for error tracking
- **Pandas**: Data processing
- **Plotly**: Interactive charts

### Sample Features:
```python
# Streamlit app structure:
# 1. Settlement Status Page
# 2. Error Ticket System
# 3. Upload Interface
# 4. Error Analytics Dashboard
```

**Pros:**
- Modern, user-friendly interface
- Real-time updates
- Email notifications possible
- Can run locally or on server
- Mobile-friendly
- Better for multiple users

**Cons:**
- Requires web server (can be localhost)
- More complex to set up
- Users need to access a web URL
- Requires maintenance

---

## 🎯 Recommended Approach

### **Phase 1: Quick Win** (Immediate)
1. **Add Upload Tracker tab to Dashboard** - Show Entry_Status data as read-only view
2. **Enhance Entry_Status.xlsx** - Add 3 columns:
   - **Validation_Status** (dropdown: Pass / Warning / Error)
   - **Error_Summary** (text field for brief description)
   - **Notes** (text field for any comments)

### **Phase 2: Error Logging** (Next Sprint)
1. **Auto-populate errors** from validation checks
2. **Create Error_Tickets.xlsx** for detailed tracking
3. **Add email alerts** when critical errors occur (optional)

### **Phase 3: Web Portal** (Future Enhancement)
1. Build Streamlit dashboard for interactive error management
2. Integrate with SharePoint for file uploads
3. Add user authentication if needed

---

## 💡 Implementation Priority

**High Priority (This Week):**
- ✅ Fix GL Account data display (DONE)
- 🔄 Add Upload Tracker tab to Dashboard
- 🔄 Enhance Entry_Status with error columns

**Medium Priority (Next Week):**
- Error ticket auto-generation
- Email notifications for critical errors
- Error reporting dashboard

**Low Priority (Future):**
- Web-based portal
- Advanced analytics
- Integration with other systems

---

## 📝 Next Steps

**Ready to implement:**
1. Add 5th tab "Upload Tracker" to Dashboard showing Entry_Status data
2. Add error tracking columns to Entry_Status.xlsx
3. Update pipeline to auto-populate validation results

**Which option would you like me to start with?**
