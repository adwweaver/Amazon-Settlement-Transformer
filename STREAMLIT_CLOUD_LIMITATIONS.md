# Streamlit Cloud Limitations & Solutions

**Important:** Streamlit Cloud has restrictions that affect file processing.

---

## ⚠️ **Streamlit Cloud Limitations**

### **1. File System Access**
- ✅ **Read-only access** to files in the repository
- ✅ **Temporary files** can be created
- ❌ **Cannot write to** `/mount/src/` (repository files are read-only)
- ✅ **Can write to** `/tmp/` (temporary directory)

### **2. Subprocess Execution**
- ✅ **Can run Python scripts** via subprocess
- ✅ **Can run system commands** (limited)
- ⚠️ **File paths** must be correct for Streamlit Cloud structure

### **3. File Uploads**
- ✅ **Can upload files** via Streamlit file uploader
- ✅ **Files stored** in Streamlit's temporary directory
- ⚠️ **Files are temporary** - may be deleted after session

---

## 🚨 **Current Issue: File Processing**

### **Problem:**
The web app tries to run `main.py` via subprocess, but:
1. File paths may not match Streamlit Cloud structure
2. Output files may not be writable
3. Temporary files may be lost

### **Solution Options:**

#### **Option 1: Process Files Directly in Web App** (Recommended)
Instead of calling `main.py` via subprocess, process files directly in the web app using the same logic.

#### **Option 2: Use Streamlit Cloud's File System**
- Upload files to `/tmp/` directory
- Process files there
- Download outputs immediately

#### **Option 3: Use External Processing Service**
- Upload files to SharePoint/OneDrive
- Process via Azure Function or similar
- Download outputs

---

## 🔧 **Recommended Fix**

### **Process Files Directly in Web App**

Instead of:
```python
subprocess.run([sys.executable, str(main_py)])
```

Do:
```python
# Import and use the processing functions directly
from transform import DataTransformer
from exports import DataExporter
from validate_settlement import SettlementValidator

# Process files directly
transformer = DataTransformer(config)
settlements_data = transformer.process_settlements()
# ... continue processing
```

This avoids subprocess issues and works better on Streamlit Cloud.

---

## 📋 **Streamlit Cloud File Structure**

```
/mount/src/amazon-settlement-transformer/
├── scripts/
│   ├── web_app.py
│   ├── main.py
│   ├── transform.py
│   └── ...
├── config/
│   └── config.yaml
└── requirements.txt
```

**Note:** Files in `/mount/src/` are read-only. Use `/tmp/` for temporary files.

---

## ✅ **Best Practices for Streamlit Cloud**

1. **Process files directly** (don't use subprocess)
2. **Use temporary directories** for uploads/outputs
3. **Provide download links** for outputs
4. **Handle file paths** correctly for both local and cloud

---

**Last Updated:** November 4, 2025  
**Status:** ⚠️ Needs Fix

