# SharePoint-Based Settlement Processing Workflow

**Goal:** Users upload files to SharePoint → Automatic processing → Status tracking → Email notifications

---

## 🎯 **Solution Options (Ranked by Complexity)**

### **Option 1: SharePoint Sync + Local Watchdog Service** ⭐ RECOMMENDED
**Best for:** Simple setup, reliable, no cloud dependencies

### **Option 2: SharePoint + Power Automate + Azure Function** 
**Best for:** Fully cloud-based, no local service needed

### **Option 3: SharePoint + Power Automate + HTTP Endpoint**
**Best for:** Hybrid approach, local processing with cloud trigger

### **Option 4: SharePoint List + Power Automate**
**Best for:** Simple tracking, manual processing trigger

---

## ✅ **Option 1: SharePoint Sync + Local Watchdog Service** (RECOMMENDED)

### **Architecture:**
```
User → SharePoint Library (upload file)
  ↓
SharePoint syncs to local folder (via OneDrive sync)
  ↓
Local Watchdog Service (monitors synced folder)
  ↓
Processes file → Creates outputs → Updates SharePoint List
  ↓
Email notification sent
```

### **Setup Steps:**

#### **Step 1: Create SharePoint Document Libraries**

1. **Create Site/Library for Incoming Files:**
   - Go to SharePoint
   - Create new Document Library: "Settlement Files - Incoming"
   - URL: `https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/Amazon-ETL-Incoming`
   - Permissions: Anyone with link can upload

2. **Create SharePoint List for Status Tracking:**
   - Go to SharePoint
   - Create new List: "Settlement Processing Status"
   - Columns:
     - `File Name` (Single line of text)
     - `Settlement ID` (Single line of text)
     - `Status` (Choice: Pending, Processing, Completed, Error)
     - `Upload Date` (Date/Time)
     - `Processed Date` (Date/Time)
     - `Zoho Sync Status` (Single line of text)
     - `Error Message` (Multiple lines of text)
     - `Output Files Link` (Hyperlink)

3. **Create Library for Outputs (Optional):**
   - Document Library: "Settlement Files - Processed"
   - For storing output CSV/Excel files

#### **Step 2: Sync SharePoint Folder Locally**

1. **Open SharePoint Library:**
   ```
   https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/Amazon-ETL-Incoming
   ```

2. **Click "Sync" button** (top toolbar)
   - This syncs to: `C:\Users\User\SharePoint\Amazon-ETL-Incoming`

3. **Verify sync location:**
   - Check File Explorer → SharePoint folder
   - Files uploaded to SharePoint will appear here automatically

#### **Step 3: Create Enhanced Watchdog Service**

Create `scripts/sharepoint_watchdog.py` that:
- Monitors synced SharePoint folder
- Processes files automatically
- Updates SharePoint List via REST API
- Sends email notifications
- Handles errors gracefully

#### **Step 4: Run Watchdog as Windows Service**

- Run as background service
- Starts automatically on boot
- Monitors SharePoint folder continuously
- Processes files as they arrive

### **User Experience:**

1. **User uploads file to SharePoint:**
   - Drag and drop or click "Upload" in SharePoint library
   - File appears in SharePoint library

2. **Automatic processing:**
   - File syncs to local folder (via OneDrive sync)
   - Watchdog detects new file
   - Processing starts automatically
   - Status updates in SharePoint List

3. **User checks status:**
   - Open SharePoint List: "Settlement Processing Status"
   - See status: Processing → Completed
   - Click link to download output files (if stored in SharePoint)

4. **Email notification:**
   - Receives email when processing completes
   - Includes status, errors (if any), links to outputs

### **Advantages:**
- ✅ Simple setup (just sync SharePoint folder)
- ✅ Reliable (local processing, no cloud dependencies)
- ✅ Real-time status in SharePoint List
- ✅ Email notifications
- ✅ Works offline (processes when connected)
- ✅ No additional infrastructure needed

### **Requirements:**
- OneDrive sync enabled
- Watchdog service running (can be Windows Service)
- SharePoint API access (for updating List)

---

## ✅ **Option 2: SharePoint + Power Automate + Azure Function**

### **Architecture:**
```
User → SharePoint Library (upload file)
  ↓
Power Automate Flow (triggered on file creation)
  ↓
Azure Function (Python ETL processing)
  ↓
Updates SharePoint List
  ↓
Uploads outputs to SharePoint Library
  ↓
Sends email notification
```

### **Setup Steps:**

#### **Step 1: Create SharePoint Libraries & List** (Same as Option 1)

#### **Step 2: Deploy Azure Function**

1. **Create Azure Function App:**
   - Portal: https://portal.azure.com
   - Create Function App (Python runtime)
   - Upload ETL code

2. **Create HTTP Trigger Function:**
   ```python
   import azure.functions as func
   import logging
   import json
   from pathlib import Path
   
   app = func.FunctionApp()
   
   @app.route(route="process_settlement", auth_level=func.AuthLevel.FUNCTION)
   def process_settlement(req: func.HttpRequest) -> func.HttpResponse:
       # Process settlement file
       # Returns status JSON
   ```

#### **Step 3: Create Power Automate Flow**

**Trigger:** When a file is created in SharePoint Library
**Actions:**
1. Get file content
2. Call Azure Function HTTP endpoint
3. Parse response
4. Create/Update item in SharePoint List
5. Upload output files to SharePoint Library
6. Send email notification

### **Advantages:**
- ✅ Fully cloud-based (no local service)
- ✅ Scalable (Azure Functions)
- ✅ Real-time processing
- ✅ SharePoint integration

### **Requirements:**
- Azure subscription
- Power Automate license
- SharePoint API access

---

## ✅ **Option 3: SharePoint + Power Automate + HTTP Endpoint (Local)**

### **Architecture:**
```
User → SharePoint Library (upload file)
  ↓
Power Automate Flow (triggered on file creation)
  ↓
HTTP Request to local service (via ngrok/public IP)
  ↓
Local service processes file
  ↓
Returns status to Power Automate
  ↓
Power Automate updates SharePoint List & sends email
```

### **Setup Steps:**

#### **Step 1: Create Local HTTP Service**

Create `scripts/sharepoint_http_service.py`:
- Flask/FastAPI server
- Endpoint: `POST /process_settlement`
- Receives file URL from SharePoint
- Downloads file via SharePoint API
- Processes file
- Returns JSON status

#### **Step 2: Expose Service Publicly**

**Option A: ngrok** (for testing)
```bash
ngrok http 5000
```

**Option B: Public IP/Port forwarding** (for production)
- Configure router/firewall
- Use static IP or domain

#### **Step 3: Create Power Automate Flow**

**Trigger:** File created in SharePoint
**Actions:**
1. Get file content/download URL
2. HTTP POST to local service endpoint
3. Wait for response
4. Update SharePoint List
5. Send email

### **Advantages:**
- ✅ Uses existing local infrastructure
- ✅ No cloud processing costs
- ✅ Full control over processing
- ✅ SharePoint integration

### **Requirements:**
- Public IP or ngrok
- Local service running
- Power Automate license

---

## ✅ **Option 4: SharePoint List + Power Automate (Simple)**

### **Architecture:**
```
User → SharePoint List (create new item with file)
  ↓
Power Automate Flow (triggered on item creation)
  ↓
Downloads file from attachment
  ↓
Calls Azure Function OR HTTP endpoint
  ↓
Updates List item with status
  ↓
Sends email notification
```

### **User Experience:**
1. User creates new item in SharePoint List
2. Attaches settlement file
3. Power Automate processes automatically
4. Status updates in same List item
5. Email notification sent

### **Advantages:**
- ✅ Very simple (just SharePoint List)
- ✅ All status in one place
- ✅ Easy to track multiple files

---

## 📋 **Recommended Implementation Plan**

### **Phase 1: Quick Win (Option 1 - SharePoint Sync + Watchdog)**

**Time:** 2-4 hours

1. **Create SharePoint Libraries & List** (30 mins)
2. **Sync SharePoint folder locally** (10 mins)
3. **Enhance watchdog to update SharePoint List** (2 hours)
4. **Add email notifications** (1 hour)
5. **Test end-to-end** (30 mins)

### **Phase 2: Enhanced Features**

1. **Add SharePoint List integration** (status updates)
2. **Add email notifications** (completion/errors)
3. **Upload outputs to SharePoint** (processed files library)
4. **Add error handling & retry logic**

---

## 🔧 **Implementation: Enhanced Watchdog with SharePoint Integration**

### **Key Features:**

1. **Monitors synced SharePoint folder**
2. **Processes files automatically**
3. **Updates SharePoint List via REST API:**
   - Status: Pending → Processing → Completed
   - Settlement ID
   - Processing date
   - Zoho sync status
   - Error messages (if any)

4. **Sends email notifications:**
   - Processing started
   - Processing completed (with summary)
   - Processing failed (with error details)

5. **Uploads outputs to SharePoint** (optional):
   - Processed CSV files
   - Summary Excel files
   - Validation reports

### **SharePoint List Structure:**

| Column Name | Type | Description |
|------------|------|-------------|
| File Name | Single line of text | Original filename |
| Settlement ID | Single line of text | Extracted settlement ID |
| Status | Choice | Pending, Processing, Completed, Error |
| Upload Date | Date/Time | When file was uploaded |
| Processed Date | Date/Time | When processing completed |
| Zoho Sync Status | Single line of text | Synced, Not Synced, Error |
| Journal ID | Single line of text | Zoho journal ID (if posted) |
| Invoice Count | Number | Number of invoices posted |
| Payment Count | Number | Number of payments posted |
| Error Message | Multiple lines | Error details (if failed) |
| Output Files Link | Hyperlink | Link to processed files |

---

## 📧 **Email Notification Template**

### **Processing Started:**
```
Subject: Settlement Processing Started - {filename}

File: {filename}
Settlement ID: {settlement_id}
Upload Date: {upload_date}

Processing has started. You will receive another email when processing completes.
```

### **Processing Completed:**
```
Subject: Settlement Processing Completed - {filename} ✅

File: {filename}
Settlement ID: {settlement_id}

Status: Success ✅

Processing Summary:
- Journal: Posted (ID: {journal_id})
- Invoices: {invoice_count} posted
- Payments: {payment_count} posted
- Output Files: [Download Link]

View Status: [SharePoint List Link]
```

### **Processing Failed:**
```
Subject: Settlement Processing Failed - {filename} ❌

File: {filename}
Settlement ID: {settlement_id}

Status: Error ❌

Error Details:
{error_message}

Please review the error and try again, or contact support.
```

---

## 🚀 **Next Steps**

Which option would you like me to implement? I recommend **Option 1** (SharePoint Sync + Local Watchdog) as it's:
- Simplest to set up
- Most reliable
- No additional infrastructure needed
- Easy to maintain

I can:
1. Create the enhanced watchdog service with SharePoint List integration
2. Set up email notification templates
3. Create setup instructions for SharePoint libraries/list
4. Test the complete workflow

Let me know which option you prefer, and I'll implement it!

