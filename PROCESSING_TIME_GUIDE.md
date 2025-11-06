# Processing Time Guide

**How long does it take to process a settlement file?**

---

## ⏱️ **Processing Time Estimates**

### **ETL Processing (File → CSV Exports)**

When you drop a settlement file and click "Process Files":

| File Size | Transactions | Processing Time | Notes |
|-----------|--------------|-----------------|-------|
| **Small** | < 100 transactions | **1-2 minutes** | Quick processing |
| **Medium** | 100-1,000 transactions | **2-5 minutes** | Typical settlement |
| **Large** | 1,000-5,000 transactions | **5-10 minutes** | Large settlement |
| **Very Large** | > 5,000 transactions | **10+ minutes** | May hit timeout |

**Timeout:** 10 minutes maximum (600 seconds)

---

## 📋 **What Happens During Processing**

### **Step 1: File Upload** (Instant)
- File is saved to `raw_data/settlements/`
- Takes: < 1 second

### **Step 2: ETL Pipeline** (Main Processing)
1. **File Detection** - Scans for `.txt` files
2. **Data Extraction** - Parses tab-delimited data
3. **Data Transformation** - Normalizes columns, applies business logic
4. **Export Generation** - Creates CSV files (Journal, Invoice, Payment)
5. **Validation** - Runs integrity checks
6. **Settlement History** - Records processing

**Takes:** 1-10 minutes depending on file size

### **Step 3: Output Files Created** (Instant)
- CSV files created in `outputs/{settlement_id}/`
- Summary Excel file generated
- Validation report created

**Takes:** < 1 second

---

## 🎯 **Typical Processing Times**

### **Small Settlement** (< 100 transactions)
- **Processing Time:** 1-2 minutes
- **Example:** Settlement with only 4 transactions
- **What Happens:** Fast processing, minimal data

### **Medium Settlement** (100-1,000 transactions)
- **Processing Time:** 2-5 minutes
- **Example:** Typical weekly settlement
- **What Happens:** Standard processing, normal data volume

### **Large Settlement** (1,000-5,000 transactions)
- **Processing Time:** 5-10 minutes
- **Example:** Monthly settlement with many orders
- **What Happens:** Longer processing, more data to transform

### **Very Large Settlement** (> 5,000 transactions)
- **Processing Time:** 10+ minutes (may hit timeout)
- **Example:** Large monthly settlement
- **What Happens:** May need to process in batches or increase timeout

---

## ⚠️ **Important Notes**

### **Timeout Limit:**
- **Current timeout:** 10 minutes (600 seconds)
- **If file is too large:** Processing will timeout
- **Solution:** Increase timeout or split large files

### **Processing is Synchronous:**
- The web app waits for processing to complete
- You'll see a spinner while processing
- The page will refresh when done

### **No Background Processing:**
- Processing happens in real-time
- You need to wait for it to complete
- Can't close the browser while processing

---

## 📊 **Processing Steps Breakdown**

### **Typical Medium Settlement (500 transactions):**

| Step | Time | Notes |
|------|------|-------|
| File Detection | < 1 sec | Instant |
| Data Extraction | 5-10 sec | Parsing text file |
| Data Transformation | 30-60 sec | Business logic, calculations |
| Export Generation | 20-30 sec | Creating CSV files |
| Validation | 5-10 sec | Running checks |
| Settlement History | < 1 sec | Recording |
| **Total** | **1-2 minutes** | Typical time |

---

## 🚀 **How to Check Processing Status**

### **In the Web App:**
1. **Status Indicator:** Shows "Processing..." spinner
2. **Logs Tab:** View processing logs
3. **Outputs Tab:** Check for generated files

### **Processing Complete When:**
- ✅ Status shows "Ready"
- ✅ Files appear in `outputs/{settlement_id}/`
- ✅ Success message appears
- ✅ File list updates

---

## ⏱️ **What to Expect**

### **When You Drop a File:**
1. **File Upload** - Instant (< 1 second)
2. **Click "Process Files"** - Starts processing
3. **Wait** - 1-10 minutes (depending on size)
4. **Done** - Files ready in `outputs/` folder

### **During Processing:**
- ✅ Spinner shows "Processing..."
- ✅ Status updates in real-time
- ✅ Logs show progress
- ⚠️ Don't close the browser!

### **After Processing:**
- ✅ Success message appears
- ✅ Output files available
- ✅ Can download files
- ✅ Can view processing logs

---

## 📝 **Tips for Faster Processing**

### **For Large Files:**
1. **Split files** if possible (if you have multiple settlements)
2. **Process separately** (one at a time)
3. **Check file size** before uploading (large files take longer)

### **For Better Experience:**
1. **Upload file** → Wait for upload to complete
2. **Click "Process Files"** → Wait for spinner
3. **Don't close browser** → Wait for completion
4. **Check outputs** → Download when ready

---

## 🔍 **Monitoring Processing**

### **Check Processing Status:**
- **Web App:** Status tab shows current state
- **Logs:** View processing logs in real-time
- **Outputs:** Check for generated files

### **If Processing Fails:**
- Check error message in web app
- Review logs in "Status & Logs" tab
- Check file format (must be `.txt`)
- Verify file isn't corrupted

---

## ⚠️ **Timeout Issues**

### **If Processing Times Out:**
- **Error:** "Processing timed out (took longer than 10 minutes)"
- **Cause:** File is too large
- **Solution:** 
  1. Split large files into smaller ones
  2. Or increase timeout in `web_app.py` (line 118)

### **To Increase Timeout:**
```python
timeout=600  # Change to 1200 for 20 minutes
```

---

## 📋 **Summary**

**Typical Processing Time:**
- **Small files:** 1-2 minutes
- **Medium files:** 2-5 minutes
- **Large files:** 5-10 minutes

**Current Timeout:** 10 minutes

**What to Do:**
1. Upload file
2. Click "Process Files"
3. Wait for processing (1-10 minutes)
4. Download outputs when done

---

**Last Updated:** November 4, 2025  
**Status:** ✅ Ready to Use



