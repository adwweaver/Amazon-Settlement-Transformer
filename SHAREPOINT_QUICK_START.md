# SharePoint Settlement Processing - Quick Start Guide

**Get up and running in 5 minutes!**

---

## ✅ **Prerequisites**

1. SharePoint folder synced locally (OneDrive sync)
2. Python installed
3. Dependencies installed: `pip install watchdog requests pyyaml`

---

## 🚀 **Quick Setup (5 Steps)**

### **Step 1: Create SharePoint List** (2 minutes)

1. Go to SharePoint: `https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo`
2. Click **"New"** → **"List"** → **"Blank list"**
3. **Name:** `Settlement Processing Status`
4. **Add these columns:**
   - `File Name` (Single line of text)
   - `Settlement ID` (Single line of text)
   - `Status` (Choice: Pending, Processing, Completed, Error)
   - `Upload Date` (Date/Time)
   - `Processed Date` (Date/Time)
   - `Zoho Sync Status` (Single line of text)
   - `Journal ID` (Single line of text)
   - `Invoice Count` (Number)
   - `Payment Count` (Number)
   - `Error Message` (Multiple lines of text)
   - `Output Files Link` (Hyperlink)

5. Click **"Create"**

### **Step 2: Create SharePoint Libraries** (2 minutes)

1. **Create "Incoming" Library:**
   - Click **"New"** → **"Document Library"**
   - **Name:** `Settlement Files - Incoming`
   - Click **"Create"**

2. **Create "Processed" Library (Optional):**
   - Click **"New"** → **"Document Library"**
   - **Name:** `Settlement Files - Processed`
   - Click **"Create"**

### **Step 3: Sync SharePoint Folder** (1 minute)

1. Go to SharePoint "Settlement Files - Incoming" library
2. Click **"Sync"** button (top toolbar)
3. **Note the local path** (usually `C:\Users\User\SharePoint\Settlement Files - Incoming`)

### **Step 4: Update Configuration** (1 minute)

Edit `config/config.yaml` and set:
```yaml
sharepoint:
  site_url: "https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo"
  status_list_name: "Settlement Processing Status"
  incoming_library: "Settlement Files - Incoming"

notifications:
  enabled: true
  email_enabled: true
  smtp_server: smtp.office365.com
  smtp_port: 587
  username: "your-email@brackishco.ca"
  password: "your-app-password"
  from: etl-bot@brackishco.ca
  to:
    - andrew@brackishco.ca
```

### **Step 5: Start Watchdog Service** (1 minute)

**Option A: Run manually**
```bash
python scripts/sharepoint_watchdog.py --watch-folder "C:\Users\User\SharePoint\Settlement Files - Incoming"
```

**Option B: Use batch file**
```bash
run_sharepoint_watchdog.bat
```

**Option C: Run as Windows Service (for automatic startup)**
- Use Task Scheduler to run `run_sharepoint_watchdog.bat` at startup

---

## 🧪 **Test It!**

1. **Upload a test file** to SharePoint "Settlement Files - Incoming" library
2. **Wait 1-2 minutes** for file to sync locally
3. **Check logs:** `logs/sharepoint_watchdog.log`
4. **Check status:** `database/sharepoint_list_tracking.json`
5. **Check email** for completion notification

---

## 📊 **Status Tracking**

### **Local Tracking File:**
- Location: `database/sharepoint_list_tracking.json`
- Contains: All processing status for each file
- Format: JSON with file status, settlement ID, Zoho sync status, etc.

### **SharePoint List (Optional):**
- If SharePoint API is configured, status will also update in SharePoint List
- For now, status is tracked locally in JSON file

---

## 🔧 **Troubleshooting**

### **File Not Processing:**
- Check if file appears in local synced folder
- Check `logs/sharepoint_watchdog.log` for errors
- Verify file is `.txt` format

### **Email Not Sending:**
- Check SMTP settings in `config/config.yaml`
- Use app password (not regular password)
- Check `logs/sharepoint_watchdog.log` for email errors

### **Zoho Sync Failing:**
- Check Zoho credentials in `config/zoho_credentials.yaml`
- Check `logs/sharepoint_watchdog.log` for Zoho API errors
- Verify settlement ID matches in Zoho

---

## 📝 **Next Steps**

1. ✅ Set up SharePoint List and Libraries
2. ✅ Sync folder locally
3. ✅ Update configuration
4. ✅ Start watchdog service
5. ✅ Test with sample file
6. ✅ Configure Windows Service (optional, for auto-start)

---

**That's it! You're ready to process settlement files automatically!** 🎉

