# Automation Setup Guide

**For Non-Technical Users:** How to set up automatic processing of settlement files.

---

## 🎯 **Options for Automatic Processing**

You have three options, from simplest to most advanced:

1. **Simple GUI App** (Recommended for most users)
2. **File Watcher** (Background monitoring)
3. **Windows Scheduled Task** (Runs on a schedule)

---

## 📱 **Option 1: Simple GUI App (Easiest)**

### **What It Does:**
- Provides a simple graphical interface
- Click a button to process files
- Optional: Auto-watch folder for new files
- Shows processing status and logs

### **How to Use:**

1. **Double-click:** `run_gui_app.bat`
   - This opens a simple window

2. **Process Files:**
   - Click "Process Files" button
   - Wait for completion
   - Check status in the log area

3. **Auto-Watch (Optional):**
   - Click "Start Auto-Watch" button
   - Leave the window open
   - New files will be processed automatically

### **Screenshots of What You'll See:**
- File list showing all `.txt` files in the folder
- "Process Files" button
- "Start Auto-Watch" button (for automatic processing)
- Status log showing what's happening
- "Open Outputs" button to view results

### **Requirements:**
- Python installed (already set up)
- No additional packages needed (uses built-in tkinter)

---

## 👁️ **Option 2: File Watcher (Background Monitoring)**

### **What It Does:**
- Monitors the `raw_data/settlements/` folder in the background
- Automatically processes new `.txt` files when they're added
- Runs in a console window (can minimize)

### **How to Use:**

1. **Double-click:** `watch_and_process.bat`
   - A console window will open

2. **Leave It Running:**
   - Keep the window open (you can minimize it)
   - The watcher will check for new files every second

3. **Add Files:**
   - Just drop new `.txt` files into `raw_data/settlements/`
   - They'll be processed automatically

4. **Stop It:**
   - Press Ctrl+C or close the window

### **What You'll See:**
```
================================================
Amazon Settlement Auto-Processor
================================================

Watching folder: C:\...\raw_data\settlements\
Press Ctrl+C to stop
================================================

[2025-11-04 10:30:15] New settlement file detected: 50011020300.txt
[2025-11-04 10:30:15] Starting ETL pipeline for 50011020300.txt...
[2025-11-04 10:32:45] Successfully processed 50011020300.txt
```

### **Requirements:**
- Python installed
- `watchdog` package (installed automatically by the batch file)

---

## ⏰ **Option 3: Windows Scheduled Task (Advanced)**

### **What It Does:**
- Runs automatically on a schedule (e.g., daily at 9 AM)
- Processes all new files in the folder
- Runs in the background (no window needed)

### **How to Set Up:**

1. **Open Task Scheduler:**
   - Press `Win + R`
   - Type: `taskschd.msc`
   - Press Enter

2. **Create New Task:**
   - Click "Create Basic Task" (right side)
   - Name: "Amazon Settlement Processor"
   - Description: "Process new settlement files"

3. **Set Trigger:**
   - Choose "Daily" (or your preferred schedule)
   - Set time (e.g., 9:00 AM)

4. **Set Action:**
   - Action: "Start a program"
   - Program: `python`
   - Arguments: `C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer\scripts\main.py`
   - Start in: `C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer`

5. **Finish:**
   - Click "Finish"
   - Task will run automatically on schedule

### **Requirements:**
- Python in system PATH
- Windows Task Scheduler access

---

## 🚀 **Quick Start (Recommended)**

### **For Most Users:**

1. **Use the GUI App:**
   ```
   Double-click: run_gui_app.bat
   ```

2. **Click "Start Auto-Watch"**
   - Leave the window open
   - New files will be processed automatically

3. **That's It!**
   - Just drop files in `raw_data/settlements/`
   - They'll be processed automatically

### **For Background Processing:**

1. **Use File Watcher:**
   ```
   Double-click: watch_and_process.bat
   ```

2. **Minimize the window**
   - It runs in the background
   - Processes files automatically

---

## 📋 **What Happens When a File is Processed?**

1. **File Detected** (if auto-watch enabled)
   - System detects new `.txt` file

2. **Processing Starts**
   - ETL pipeline runs
   - Extracts settlement data
   - Generates CSV files

3. **Output Files Created:**
   ```
   outputs/{settlement_id}/
   ├── Journal_{settlement_id}.csv
   ├── Invoice_{settlement_id}.csv
   ├── Payment_{settlement_id}.csv
   └── Validation_Errors_{settlement_id}.csv
   ```

4. **Notification** (if enabled)
   - Windows notification appears
   - "Settlement Processed" message

5. **Logging**
   - All activity logged to `logs/watchdog.log`
   - Processing details in `logs/etl_pipeline.log`

---

## ⚙️ **Configuration**

### **Change Watch Folder:**
Edit `watch_and_process.bat` or `scripts/watchdog.py`:
```python
watch_folder = Path('raw_data/settlements')  # Change this path
```

### **Change Processing Behavior:**
Edit `scripts/watchdog.py`:
- Check interval (default: 1 second)
- Processing timeout (default: 10 minutes)
- Notification settings

---

## 🔧 **Troubleshooting**

### **GUI App Won't Start:**
- Check Python is installed: `python --version`
- Check you're in the correct directory
- Try running from command line: `python scripts/gui_app.py`

### **File Watcher Not Processing Files:**
- Check the console window for error messages
- Verify files are `.txt` format
- Check `logs/watchdog.log` for details
- Ensure files are fully copied (wait a few seconds after copying)

### **Files Processed Multiple Times:**
- The system tracks processed files
- If you want to re-process, delete the file from `database/watchdog_processed.json`
- Or just move the file out and back in

### **Processing Takes Too Long:**
- Large files (>1000 transactions) can take 5-10 minutes
- Check `logs/etl_pipeline.log` for progress
- Timeout is set to 10 minutes (configurable)

---

## 📊 **Monitoring**

### **Check Processing Status:**
- GUI App: Status shown in the log area
- File Watcher: Console output
- Logs: `logs/watchdog.log` and `logs/etl_pipeline.log`

### **Check Processed Files:**
- List stored in: `database/watchdog_processed.json`
- Shows which files have been processed
- Prevents duplicate processing

---

## 🎯 **Recommendation**

**For Most Users: Use the GUI App**
- Simple and user-friendly
- Shows what's happening
- Easy to start/stop
- Can enable auto-watch if desired

**For Background Processing: Use File Watcher**
- Runs in background
- Minimal resource usage
- Automatic processing
- Good for unattended operation

**For Scheduled Processing: Use Task Scheduler**
- Runs on a schedule
- No user interaction needed
- Good for routine processing

---

## 📝 **Next Steps**

1. **Choose your preferred method** (GUI App recommended)
2. **Test with a sample file** to ensure it works
3. **Set up auto-watch or scheduled task** if desired
4. **Monitor logs** to ensure everything works correctly

---

**Last Updated:** November 4, 2025  
**Status:** ✅ Ready to Use



