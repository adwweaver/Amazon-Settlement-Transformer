# How to Process a New Remittance

**Quick Answer:** Place file in `raw_data/settlements/`, then run `python scripts/main.py` manually. Processing takes 1-5 minutes. Posting to Zoho takes 5-30 minutes depending on size.

---

## 📁 **Where to Put the File**

### **Location:**
```
raw_data/settlements/{filename}.txt
```

**Example:**
- Download settlement report from Amazon Seller Central
- Save it as: `raw_data/settlements/50011020300.txt`
- **File must be `.txt` format** (tab-delimited)

### **File Naming:**
- Any name is fine (e.g., `50011020300.txt`, `settlement_2025_11_04.txt`)
- The system extracts the settlement ID from the file content, not the filename

---

## ⚡ **What Happens (Manual Process)**

### **Current Status: NOT AUTOMATIC** 
The pipeline is **NOT automated** - you need to run it manually when you have a new file.

### **Step-by-Step Process:**

#### **STEP 1: Place the File** ✅
- Drop the `.txt` file in `raw_data/settlements/`
- That's it! Nothing happens automatically yet.

#### **STEP 2: Run the Pipeline** (Manual)
```bash
# Option 1: Run from command line
python scripts/main.py

# Option 2: Use batch file (Windows)
run_pipeline.bat
```

**What Happens:**
1. ✅ Scans `raw_data/settlements/` for `.txt` files
2. ✅ Extracts and processes settlement data
3. ✅ Generates CSV exports (Journal, Invoice, Payment)
4. ✅ Runs validation checks
5. ✅ Creates output files in `outputs/{settlement_id}/`

**Output Files Created:**
```
outputs/{settlement_id}/
├── Journal_{settlement_id}.csv       ← For accounting
├── Invoice_{settlement_id}.csv        ← For invoices
├── Payment_{settlement_id}.csv        ← For payments
├── Validation_Errors_{settlement_id}.csv  ← Quality check
└── Summary_{settlement_id}.xlsx      ← Summary report
```

#### **STEP 3: Review Validation** (Manual)
- Check `outputs/{settlement_id}/Validation_Errors_{settlement_id}.csv`
- Verify journal balances (Debits = Credits)
- Review for any blocking errors

#### **STEP 4: Post to Zoho** (Manual - Optional)
```bash
python scripts/sync_settlement.py {settlement_id}
```

**What Happens:**
1. ✅ Posts journal entry to Zoho Books
2. ✅ Posts invoices to Zoho Books
3. ✅ Posts payments to Zoho Books
4. ✅ Updates tracking files
5. ✅ Logs all operations

**Note:** This step is optional - you can review the CSV files first before posting to Zoho.

---

## ⏱️ **How Long Does It Take?**

### **ETL Processing (Step 2):**
- **Small settlement** (< 100 transactions): **1-2 minutes**
- **Medium settlement** (100-1,000 transactions): **2-5 minutes**
- **Large settlement** (> 1,000 transactions): **5-10 minutes**

### **Posting to Zoho (Step 4 - Optional):**
- **Journals:** ~5 seconds per settlement
- **Invoices:** ~0.5 seconds per invoice (with rate limiting)
  - 100 invoices = ~50 seconds
  - 500 invoices = ~4 minutes
- **Payments:** ~0.5 seconds per payment (with rate limiting)
  - 100 payments = ~50 seconds
  - 500 payments = ~4 minutes

**Total Time Estimate:**
- **Small settlement** (process + post): **3-5 minutes**
- **Medium settlement** (process + post): **10-15 minutes**
- **Large settlement** (process + post): **20-30 minutes**

### **Rate Limiting:**
The system includes automatic delays to respect Zoho API rate limits:
- 0.5 seconds between items
- 5 seconds between batches
- Automatic retry on rate limit errors

---

## 🔄 **Complete Workflow Example**

### **Scenario: New Settlement File Arrives**

1. **Download from Amazon** (1 minute)
   - Go to Amazon Seller Central
   - Download settlement report

2. **Place File** (30 seconds)
   ```
   → Save to: raw_data/settlements/50011020300.txt
   ```

3. **Run Pipeline** (2 minutes)
   ```bash
   python scripts/main.py
   ```
   - Wait for processing to complete
   - Check console output for success

4. **Review Outputs** (2 minutes)
   - Check `outputs/50011020300/Validation_Errors_50011020300.csv`
   - Verify journal balances
   - Review summary report

5. **Post to Zoho** (5 minutes - optional)
   ```bash
   python scripts/sync_settlement.py 50011020300
   ```
   - Wait for posting to complete
   - Check console output for success

6. **Verify** (1 minute)
   ```bash
   python scripts/check_current_status.py
   ```
   - Verify all records posted correctly

**Total Time: ~10-15 minutes** (mostly waiting for processing)

---

## ⚠️ **Important Notes**

### **What's NOT Automatic:**
- ❌ File watching (doesn't auto-detect new files)
- ❌ Auto-processing (doesn't run automatically)
- ❌ Auto-posting (doesn't post to Zoho automatically)

### **What IS Automatic:**
- ✅ Duplicate detection (won't process same file twice)
- ✅ Settlement ID extraction (from file content)
- ✅ Validation checks (during processing)
- ✅ Error handling (logs errors, continues processing)
- ✅ Rate limiting (respects Zoho API limits)

### **Safety Features:**
- ✅ **Duplicate Prevention:** Won't process same settlement twice
- ✅ **Balance Checks:** Won't post if journal out of balance
- ✅ **Invoice Balance Check:** Skips already-paid invoices
- ✅ **Payment Amount Adjustment:** Adjusts to match invoice balance
- ✅ **Comprehensive Logging:** All operations logged

---

## 🚀 **Future Automation (Not Yet Implemented)**

The project documentation mentions future automation options:
- **SharePoint Integration:** Upload files to SharePoint, auto-process
- **Azure Functions:** Automatic processing when files uploaded
- **Power Automate:** Email notifications when processing complete

**Current Status:** These are planned but not yet implemented. For now, manual processing is required.

---

## 📝 **Quick Reference Commands**

```bash
# Process new files
python scripts/main.py

# Post specific settlement to Zoho
python scripts/sync_settlement.py {settlement_id}

# Check current status (local vs Zoho)
python scripts/check_current_status.py

# Reconcile P&L totals
python scripts/reconcile_pl_totals.py

# Verify all balances
python scripts/verify_all_balances.py
```

---

## ❓ **FAQ**

**Q: Do I have to run the pipeline manually every time?**  
A: Yes, currently manual. Just place the file and run `python scripts/main.py`.

**Q: What if I put multiple files in the folder?**  
A: The pipeline processes ALL `.txt` files in `raw_data/settlements/` at once.

**Q: Will it process the same file twice?**  
A: No, it checks settlement history and skips already-processed files.

**Q: Do I have to post to Zoho immediately?**  
A: No, you can review the CSV files first, then post when ready.

**Q: What if processing fails?**  
A: Check `logs/etl_pipeline.log` for error details. Fix the issue and re-run.

**Q: Can I automate this?**  
A: Not yet - automation features are planned but not implemented. Manual processing is required for now.

---

**Last Updated:** November 4, 2025  
**Status:** ✅ Manual Process - Fully Functional



