# SharePoint Settlement Processing Setup Guide

**Complete setup guide for SharePoint-based settlement file processing with automatic status tracking and email notifications.**

---

## 🎯 **Overview**

This solution allows users to:
1. **Upload files** to SharePoint Document Library
2. **Automatic processing** when files are detected
3. **Status tracking** in SharePoint List (real-time updates)
4. **Email notifications** for completion/errors
5. **View outputs** in SharePoint or download directly

---

## 📋 **Step-by-Step Setup**

### **Step 1: Create SharePoint Document Libraries** (15 minutes)

#### **1.1 Create "Settlement Files - Incoming" Library**

1. Go to your SharePoint site:
   ```
   https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo
   ```

2. Click **"New"** → **"Document Library"**

3. **Name:** `Settlement Files - Incoming`
4. **Description:** `Upload settlement files here. Files will be processed automatically.`

5. **Settings:**
   - **File versioning:** Enabled
   - **Content approval:** Disabled
   - **Allow external sharing:** Yes (if needed)

6. **Permissions:**
   - **Anyone with link can upload** (or your preferred access level)

7. **Click "Create"**

#### **1.2 Create "Settlement Processing Status" List**

1. Click **"New"** → **"List"** → **"Blank list"**

2. **Name:** `Settlement Processing Status`
3. **Description:** `Tracks processing status of settlement files`

4. **Add Columns:**
   
   | Column Name | Type | Required | Default Value |
   |------------|------|----------|---------------|
   | File Name | Single line of text | Yes | - |
   | Settlement ID | Single line of text | Yes | - |
   | Status | Choice | Yes | Pending |
   | Upload Date | Date/Time | Yes | Today |
   | Processed Date | Date/Time | No | - |
   | Zoho Sync Status | Single line of text | No | - |
   | Journal ID | Single line of text | No | - |
   | Invoice Count | Number | No | 0 |
   | Payment Count | Number | No | 0 |
   | Error Message | Multiple lines of text | No | - |
   | Output Files Link | Hyperlink | No | - |

5. **Status Column Choices:**
   - Pending
   - Processing
   - Completed
   - Error

6. **Click "Create"**

#### **1.3 Create "Processed Files" Library (Optional)**

1. Click **"New"** → **"Document Library"**
2. **Name:** `Settlement Files - Processed`
3. **Description:** `Processed settlement files and outputs`
4. **Click "Create"**

---

### **Step 2: Sync SharePoint Folder Locally** (5 minutes)

#### **2.1 Sync "Incoming" Library**

1. **Open SharePoint Library:**
   ```
   https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/Amazon-ETL-Incoming
   ```

2. **Click "Sync" button** (top toolbar)
   - This will sync to: `C:\Users\User\SharePoint\Amazon-ETL-Incoming`
   - Or: `C:\Users\User\OneDrive - Touchstone Brands\Amazon-ETL-Incoming`

3. **Verify sync location:**
   - Open File Explorer
   - Navigate to SharePoint or OneDrive folder
   - You should see the synced folder

4. **Note the exact path** - you'll need this for configuration

---

### **Step 3: Configure Email Notifications** (10 minutes)

#### **3.1 Update config.yaml**

Edit `config/config.yaml` and add:

```yaml
# SharePoint Configuration
sharepoint:
  site_url: "https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo"
  status_list_name: "Settlement Processing Status"
  incoming_library: "Settlement Files - Incoming"
  processed_library: "Settlement Files - Processed"

# Email Notifications
notifications:
  enabled: true
  email_enabled: true
  email_to:
    - your-email@example.com
    - accounting@example.com
  email_from: "etl-bot@example.com"
  smtp_server: "smtp.office365.com"
  smtp_port: 587
  username: "your-email@example.com"
  password: "your-app-password"  # Use app password, not regular password
```

#### **3.2 Get App Password (for Office 365)**

1. Go to: https://account.microsoft.com/security
2. Click **"Security"** → **"Advanced security options"**
3. Click **"App passwords"**
4. Generate new app password
5. Copy and paste into `config.yaml`

---

### **Step 4: Install & Run SharePoint Watchdog Service** (5 minutes)

#### **4.1 Install Dependencies**

```bash
pip install watchdog requests
```

#### **4.2 Test the Service**

```bash
python scripts/sharepoint_watchdog.py --watch-folder "C:\Users\User\SharePoint\Amazon-ETL-Incoming"
```

#### **4.3 Run as Windows Service (Optional)**

Create `sharepoint_watchdog_service.bat`:
```batch
@echo off
cd /d "C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer"
python scripts/sharepoint_watchdog.py --watch-folder "C:\Users\User\SharePoint\Amazon-ETL-Incoming"
pause
```

**Or use Windows Task Scheduler:**
1. Open Task Scheduler
2. Create new task
3. **Trigger:** "At log on" or "Daily at 9:00 AM"
4. **Action:** Start program
   - Program: `python`
   - Arguments: `scripts/sharepoint_watchdog.py --watch-folder "C:\Users\User\SharePoint\Amazon-ETL-Incoming"`
   - Start in: `C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer`

---

### **Step 5: Test End-to-End** (10 minutes)

1. **Upload a test file to SharePoint:**
   - Go to SharePoint "Settlement Files - Incoming" library
   - Upload a test `.txt` file

2. **Verify file syncs locally:**
   - Check synced folder in File Explorer
   - File should appear within 1-2 minutes

3. **Check processing:**
   - Watch console/logs for processing messages
   - Check SharePoint List for status updates
   - Wait for email notification

4. **Verify outputs:**
   - Check `outputs/{settlement_id}/` folder
   - Check SharePoint List for completion status
   - Verify Zoho sync status

---

## 🔧 **Configuration Options**

### **SharePoint List Updates**

The service updates SharePoint List via REST API. You may need to:
- Configure OAuth authentication (if required)
- Set up app permissions in SharePoint Admin Center
- Or use service account credentials

**For now, the service will log updates - actual API calls require SharePoint authentication setup.**

### **Email Notifications**

Email notifications use SMTP (Office 365, Gmail, etc.). Configure in `config.yaml`:
```yaml
notifications:
  enabled: true
  smtp_server: smtp.office365.com
  smtp_port: 587
  username: your-email@example.com
  password: app-password
  from: etl-bot@example.com
  to:
    - recipient1@example.com
    - recipient2@example.com
```

---

## 📊 **User Workflow**

### **For Users:**

1. **Upload File:**
   - Go to SharePoint "Settlement Files - Incoming" library
   - Click "Upload" or drag and drop `.txt` file
   - File appears in library

2. **Check Status:**
   - Go to SharePoint "Settlement Processing Status" list
   - Find your file by name or settlement ID
   - See status: Pending → Processing → Completed/Error

3. **Receive Email:**
   - Email sent when processing completes
   - Includes status, summary, and links

4. **Download Outputs:**
   - Click "Output Files Link" in SharePoint List
   - Or go to "Processed Files" library
   - Download CSV/Excel files

---

## 🚨 **Troubleshooting**

### **Files Not Processing:**

1. **Check SharePoint sync:**
   - Verify file appears in local synced folder
   - Check sync status in OneDrive

2. **Check watchdog service:**
   - Is service running?
   - Check `logs/sharepoint_watchdog.log` for errors

3. **Check file format:**
   - Must be `.txt` format
   - Must be valid settlement file

### **SharePoint List Not Updating:**

1. **Check authentication:**
   - Service may need SharePoint API permissions
   - Check logs for authentication errors

2. **Check site URL:**
   - Verify `sharepoint.site_url` in config.yaml is correct

### **Email Not Sending:**

1. **Check SMTP settings:**
   - Verify server, port, username, password
   - Use app password, not regular password

2. **Check email config:**
   - Verify `email_enabled: true` in config.yaml
   - Check recipient email addresses

---

## 📝 **Next Steps**

1. **Set up SharePoint libraries and list** (Step 1)
2. **Sync SharePoint folder locally** (Step 2)
3. **Configure email notifications** (Step 3)
4. **Test with a sample file** (Step 5)
5. **Set up as Windows Service** (Step 4.3) for automatic startup

---

## ✅ **Status Check**

After setup, verify:
- ✅ SharePoint libraries created
- ✅ SharePoint List created with all columns
- ✅ SharePoint folder synced locally
- ✅ Watchdog service running
- ✅ Email notifications working
- ✅ Test file processed successfully
- ✅ Status updates in SharePoint List
- ✅ Email notification received

---

**Last Updated:** 2025-11-05  
**Status:** Ready for Implementation

