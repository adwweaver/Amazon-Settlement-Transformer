# 🚀 M365 Deployment Guide

## Option A: SharePoint + Power Automate (Recommended)

### **Architecture:**
```
External User → SharePoint Library (upload)
       ↓
Power Automate Flow (triggered on file upload)
       ↓
Azure Function (Python ETL processing)
       ↓
SharePoint Library (download processed files)
       ↓
Email notification to user
```

---

## 📋 Step-by-Step Setup

### **Step 1: Create SharePoint Site** (5 mins)

1. Go to SharePoint Admin Center
2. Create new site: "Amazon Settlement ETL"
3. Site URL: `https://brackishco.sharepoint.com/sites/amazon-etl`
4. Site type: Team site or Communication site

### **Step 2: Create Document Libraries** (5 mins)

Create 3 document libraries:

1. **Incoming** - Where external users upload files
   - Allow: .txt files only
   - Permissions: Anyone with link can upload
   
2. **Processed** - Where outputs go
   - Folders for each processing session
   - Permissions: Anyone with link can view/download
   
3. **Archive** - Historical storage
   - Auto-organized by date
   - Permissions: Internal only

### **Step 3: Configure External Sharing** (5 mins)

For "Incoming" library:
```
Settings → Permissions → Share
- ☑ Anyone with the link can upload
- ☑ Link expires in 90 days
- ☑ Require sign-in (optional)
```

For "Processed" library:
```
Settings → Permissions → Share
- ☑ Anyone with the link can view/download
- ☑ Link expires in 7 days
```

### **Step 4: Deploy Python ETL as Azure Function** (30 mins)

#### **Option A: Simple Azure Function**

Create `function_app.py`:
```python
import azure.functions as func
import logging
import sys
from pathlib import Path

# Import your ETL modules
sys.path.append(str(Path(__file__).parent / 'scripts'))
from transform import DataTransformer
from exports import DataExporter
from database import ETLDatabase
import yaml

app = func.FunctionApp()

@app.blob_trigger(arg_name="blob", path="incoming/{name}",
                  connection="AzureWebJobsStorage")
def process_settlement(blob: func.InputStream):
    logging.info(f"Processing: {blob.name}")
    
    try:
        # Save uploaded file
        file_content = blob.read()
        temp_path = Path(f"/tmp/{blob.name}")
        temp_path.write_bytes(file_content)
        
        # Load config
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize components
        db = ETLDatabase()
        transformer = DataTransformer(config)
        exporter = DataExporter(config)
        
        # Check if already processed
        file_hash = db.calculate_file_hash(temp_path)
        existing = db.check_file_processed(blob.name, file_hash)
        
        if existing:
            logging.warning(f"File already processed: {blob.name}")
            return
        
        # Process settlement
        settlement_data = transformer.process_settlements()
        
        if settlement_data is not None:
            final_data = transformer.merge_and_finalize(
                settlement_data, None, None
            )
            
            # Generate exports
            exporter.generate_all_exports(final_data)
            
            # Log to database
            settlement_id = settlement_data['settlement_id'].iloc[0]
            db.log_processed_file(
                filename=blob.name,
                settlement_id=settlement_id,
                file_hash=file_hash,
                file_size=len(file_content),
                archived_path=f"archive/{blob.name}",
                status='success',
                record_count=len(settlement_data)
            )
            
            logging.info(f"Successfully processed: {blob.name}")
            
    except Exception as e:
        logging.error(f"Error processing {blob.name}: {str(e)}")
        raise
```

Deploy to Azure:
```powershell
# Install Azure Functions Core Tools
npm install -g azure-functions-core-tools@4

# Create Function App
cd C:\Users\User\Documents\GitHub
func init --python

# Deploy
func azure functionapp publish amazon-etl-brackish
```

#### **Option B: Container Instance** (Simpler)

Deploy as Docker container that polls SharePoint:
```python
# monitor_sharepoint.py
import time
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential

def monitor_incoming_folder():
    # Connect to SharePoint
    site_url = "https://brackishco.sharepoint.com/sites/amazon-etl"
    ctx = ClientContext(site_url).with_credentials(
        UserCredential(username, password)
    )
    
    # Check for new files every 5 minutes
    while True:
        incoming = ctx.web.lists.get_by_title("Incoming")
        items = incoming.items.get().execute_query()
        
        for item in items:
            # Process file
            process_settlement_file(item)
            
        time.sleep(300)  # 5 minutes
```

### **Step 5: Create Power Automate Flow** (15 mins)

1. Go to Power Automate (flow.microsoft.com)
2. Create new automated flow

**Trigger:**
```
When a file is created (SharePoint)
- Site: /sites/amazon-etl
- Library: Incoming
```

**Actions:**

**Action 1: Get File Content**
```
Get file content using path
- Site: /sites/amazon-etl
- File: Trigger output (Full Path)
```

**Action 2: Call Azure Function** (or HTTP webhook)
```
HTTP Request
- Method: POST
- URI: https://amazon-etl-brackish.azurewebsites.net/api/process
- Body: @{outputs('Get_file_content')}
- Headers: 
  - filename: @{triggerOutputs()?['body/{Name}']}
```

**Action 3: Wait for Processing**
```
Delay
- Duration: 2 minutes
```

**Action 4: Copy Outputs to Processed Library**
```
Create file (SharePoint)
- Site: /sites/amazon-etl
- Folder: /Processed/@{utcNow('yyyy-MM-dd')}
- File Name: Dashboard_Summary.csv
- Content: @{body('Call_Azure_Function')?['outputs']['dashboard']}
```

**Action 5: Send Email Notification**
```
Send an email (V2)
- To: @{triggerOutputs()?['body/{CreatedBy}/Email']}
- Subject: Settlement Processing Complete
- Body: Your files have been processed. Download at: [Link]
```

**Action 6: Move Source to Archive**
```
Move file (SharePoint)
- Site: /sites/amazon-etl
- Source: Trigger file
- Destination: /Archive/@{utcNow('yyyy-MM')}
```

---

## 🔐 Security Configuration

### **External User Access:**

1. **Time-Limited Links**
```powershell
# PowerShell to create expiring link
$ctx = Connect-PnPOnline -Url "https://brackishco.sharepoint.com/sites/amazon-etl" -ReturnConnection
$link = New-PnPSharingLink -Path "/sites/amazon-etl/Incoming" -Type AnonymousEdit -ExpiresInDays 90
```

2. **Email-Required Upload**
- Settings → External Sharing → Require people to sign in with email
- Tracks who uploaded what
- Prevents abuse

3. **Audit Logging**
```powershell
# View upload audit logs
Search-UnifiedAuditLog -StartDate (Get-Date).AddDays(-30) -EndDate (Get-Date) -RecordType SharePointFileOperation -Operations FileUploaded
```

### **Data Protection:**

1. **Sensitivity Labels** (if M365 E3/E5)
   - Mark library as "Confidential"
   - Prevent external download after 7 days

2. **Retention Policies**
   - Auto-delete from "Incoming" after 30 days
   - Keep "Archive" for 7 years

3. **DLP Policies**
   - Alert if sensitive data detected
   - Block upload of non-settlement files

---

## 📧 User Instructions Template

Send this to external users:

```
Subject: Amazon Settlement File Upload Access

Hi [Name],

You've been granted access to upload Amazon settlement files for processing.

UPLOAD FILES:
1. Click this link: [SharePoint Upload Link]
2. Drag and drop your settlement files (.txt)
3. You'll receive an email when processing completes (usually 2-5 minutes)

DOWNLOAD PROCESSED FILES:
1. Check your email for "Processing Complete" notification
2. Click the download link in the email
3. Get these files for import to Zoho:
   - Dashboard_Summary.csv
   - Journal_[ID].csv
   - Invoice_[ID].csv
   - Payment_[ID].csv

IMPORTANT:
- Link expires in 90 days
- Only .txt settlement files accepted
- Files automatically deleted after processing
- Check your spam folder for notifications

Questions? Reply to this email.

Thanks,
[Your Name]
```

---

## 💰 Cost Comparison

| Solution | Monthly Cost | Setup Time | External Access |
|----------|-------------|------------|-----------------|
| **SharePoint + Power Automate** | $0 (included) | 1 hour | ✅ Built-in |
| **Azure Function (Consumption)** | ~$1-5 | 2 hours | ✅ Via SharePoint |
| **Azure Web App (Basic)** | ~$13 | 1 hour | ✅ Custom domain |
| **Streamlit Cloud** | $0 (free tier) | 15 mins | ✅ Password protected |

---

## 🚀 Quick Start (Minimum Viable Product)

**30-Minute Setup - No Azure Functions:**

1. **Create SharePoint Libraries** (10 mins)
   - Incoming, Processed, Archive

2. **Local Processing Script** (10 mins)
   ```powershell
   # watch_sharepoint.ps1
   while($true) {
       # Download new files from SharePoint
       # Run: python scripts/main.py
       # Upload outputs to SharePoint
       Start-Sleep -Seconds 300
   }
   ```

3. **Power Automate for Notifications** (10 mins)
   - Trigger: File uploaded
   - Action: Send email to uploader
   - Action: Email you to run processing

4. **Manual Processing**
   - You get email notification
   - Run local script
   - Outputs auto-upload to SharePoint
   - User gets notification

**Later: Automate with Azure Function**

---

## 📊 Monitoring & Maintenance

### **Power Automate Dashboard:**
- View all processing runs
- Success/failure rates
- Processing times
- User activity

### **SharePoint Analytics:**
- File upload frequency
- Storage usage
- External user activity
- Most active partners

### **Database Reports:**
```python
# Generate weekly report
import sqlite3
conn = sqlite3.connect('database/settlements.db')
weekly_stats = pd.read_sql("""
    SELECT 
        DATE(processed_date) as date,
        COUNT(*) as files_processed,
        SUM(record_count) as total_records
    FROM processed_files
    WHERE processed_date >= date('now', '-7 days')
    GROUP BY DATE(processed_date)
""", conn)
```

---

## 🎯 Recommended Approach

**Start Simple, Scale Later:**

**Week 1:** SharePoint libraries + manual processing
**Week 2:** Add Power Automate notifications
**Week 3:** Deploy Azure Function for automation
**Week 4:** Add analytics dashboard

**Total Time Investment:** 4-6 hours
**Total Cost:** $0-5/month

---

**Need Help?**
- SharePoint: Microsoft 365 Admin Center → Support
- Power Automate: flow.microsoft.com → Help
- Azure: portal.azure.com → Support

