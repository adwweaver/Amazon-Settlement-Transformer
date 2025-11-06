# Migration Guide: Reorganizing Project to Amazon-Settlement-Transformer

**Date:** 2025-11-02  
**Purpose:** Move all project files to `Amazon-Settlement-Transformer` folder structure

---

## 📋 Overview

This guide helps you reorganize the Amazon Settlement ETL project from the root `GitHub` directory into a dedicated `Amazon-Settlement-Transformer` folder.

**Current Location:** `C:\Users\User\Documents\GitHub\` (root directory)  
**Target Location:** `C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer\`

---

## 📁 Files and Folders to Move

### Core Project Files (Must Move)

```
✅ scripts/              → Amazon-Settlement-Transformer/scripts/
✅ config/               → Amazon-Settlement-Transformer/config/
✅ docs/                 → Amazon-Settlement-Transformer/docs/
✅ raw_data/             → Amazon-Settlement-Transformer/raw_data/
✅ outputs/              → Amazon-Settlement-Transformer/outputs/
✅ logs/                 → Amazon-Settlement-Transformer/logs/
✅ database/             → Amazon-Settlement-Transformer/database/
✅ mCode/                → Amazon-Settlement-Transformer/mCode/
✅ requirements.txt      → Amazon-Settlement-Transformer/requirements.txt
✅ venv/                 → Amazon-Settlement-Transformer/venv/ (if exists)
```

### Documentation Files (Move to Root of Amazon-Settlement-Transformer)

```
✅ README.md             → Amazon-Settlement-Transformer/README.md (already updated)
✅ PROJECT_STATUS_AND_ROADMAP.md → Amazon-Settlement-Transformer/PROJECT_STATUS_AND_ROADMAP.md
✅ BUSINESS_LOGIC_RULES.md → Already in docs/
✅ TRACKING_FILES_LOCATION.md → Amazon-Settlement-Transformer/TRACKING_FILES_LOCATION.md
✅ INVOICE_PAYMENT_MAPPING_LOCATION.md → Amazon-Settlement-Transformer/INVOICE_PAYMENT_MAPPING_LOCATION.md
✅ VALIDATION_SYSTEM_DESIGN.md → Amazon-Settlement-Transformer/VALIDATION_SYSTEM_DESIGN.md
✅ DASHBOARD_ENHANCEMENTS.md → Amazon-Settlement-Transformer/DASHBOARD_ENHANCEMENTS.md
✅ DEPLOYMENT_M365.md → Amazon-Settlement-Transformer/DEPLOYMENT_M365.md
✅ AUTO_SYNC_GUIDE.md → Amazon-Settlement-Transformer/AUTO_SYNC_GUIDE.md
✅ ZOHO_SETUP_CHECKLIST.md → Amazon-Settlement-Transformer/ZOHO_SETUP_CHECKLIST.md
```

### Script Files (Move to Amazon-Settlement-Transformer/scripts/)

All `.py` files in root `scripts/` directory should already be in `Amazon-Settlement-Transformer/scripts/` after moving `scripts/` folder.

### Batch/PowerShell Files (Move to Root of Amazon-Settlement-Transformer)

```
✅ run_pipeline.bat      → Amazon-Settlement-Transformer/run_pipeline.bat
✅ run_tests.bat         → Amazon-Settlement-Transformer/run_tests.bat
✅ START_SYNC.bat        → Amazon-Settlement-Transformer/START_SYNC.bat
✅ deploy_to_production.ps1 → Amazon-Settlement-Transformer/deploy_to_production.ps1
✅ sync_to_production.ps1 → Amazon-Settlement-Transformer/sync_to_production.ps1
```

### Files to Keep in Root (Not Project-Specific)

```
❌ Amazon-Ads-Automator/ (separate project)
❌ Zoho Books Reporting/ (separate project)
❌ _archive/ (can be moved to Amazon-Settlement-Transformer/_archive/ if needed)
```

---

## 🔧 Step-by-Step Migration

### Step 1: Create Target Directory Structure

```powershell
# Navigate to GitHub directory
cd C:\Users\User\Documents\GitHub

# Create Amazon-Settlement-Transformer directory (if not exists)
New-Item -ItemType Directory -Path "Amazon-Settlement-Transformer" -Force

# Create subdirectories
cd Amazon-Settlement-Transformer
New-Item -ItemType Directory -Path "scripts" -Force
New-Item -ItemType Directory -Path "config" -Force
New-Item -ItemType Directory -Path "docs" -Force
New-Item -ItemType Directory -Path "raw_data" -Force
New-Item -ItemType Directory -Path "outputs" -Force
New-Item -ItemType Directory -Path "logs" -Force
New-Item -ItemType Directory -Path "database" -Force
New-Item -ItemType Directory -Path "mCode" -Force
```

### Step 2: Move Core Directories

```powershell
# From GitHub root directory
cd C:\Users\User\Documents\GitHub

# Move core directories
Move-Item -Path "scripts" -Destination "Amazon-Settlement-Transformer\scripts" -Force
Move-Item -Path "config" -Destination "Amazon-Settlement-Transformer\config" -Force
Move-Item -Path "docs" -Destination "Amazon-Settlement-Transformer\docs" -Force
Move-Item -Path "raw_data" -Destination "Amazon-Settlement-Transformer\raw_data" -Force
Move-Item -Path "outputs" -Destination "Amazon-Settlement-Transformer\outputs" -Force
Move-Item -Path "logs" -Destination "Amazon-Settlement-Transformer\logs" -Force
Move-Item -Path "database" -Destination "Amazon-Settlement-Transformer\database" -Force
Move-Item -Path "mCode" -Destination "Amazon-Settlement-Transformer\mCode" -Force
```

### Step 3: Move Root Files

```powershell
# Move root-level files
Move-Item -Path "requirements.txt" -Destination "Amazon-Settlement-Transformer\requirements.txt" -Force
Move-Item -Path "PROJECT_STATUS_AND_ROADMAP.md" -Destination "Amazon-Settlement-Transformer\PROJECT_STATUS_AND_ROADMAP.md" -Force
Move-Item -Path "TRACKING_FILES_LOCATION.md" -Destination "Amazon-Settlement-Transformer\TRACKING_FILES_LOCATION.md" -Force
Move-Item -Path "INVOICE_PAYMENT_MAPPING_LOCATION.md" -Destination "Amazon-Settlement-Transformer\INVOICE_PAYMENT_MAPPING_LOCATION.md" -Force
Move-Item -Path "VALIDATION_SYSTEM_DESIGN.md" -Destination "Amazon-Settlement-Transformer\VALIDATION_SYSTEM_DESIGN.md" -Force
Move-Item -Path "DASHBOARD_ENHANCEMENTS.md" -Destination "Amazon-Settlement-Transformer\DASHBOARD_ENHANCEMENTS.md" -Force
Move-Item -Path "DEPLOYMENT_M365.md" -Destination "Amazon-Settlement-Transformer\DEPLOYMENT_M365.md" -Force
Move-Item -Path "AUTO_SYNC_GUIDE.md" -Destination "Amazon-Settlement-Transformer\AUTO_SYNC_GUIDE.md" -Force
Move-Item -Path "ZOHO_SETUP_CHECKLIST.md" -Destination "Amazon-Settlement-Transformer\ZOHO_SETUP_CHECKLIST.md" -Force
```

### Step 4: Move Batch/PowerShell Scripts

```powershell
# Move batch and PowerShell files
Move-Item -Path "run_pipeline.bat" -Destination "Amazon-Settlement-Transformer\run_pipeline.bat" -Force
Move-Item -Path "run_tests.bat" -Destination "Amazon-Settlement-Transformer\run_tests.bat" -Force
Move-Item -Path "START_SYNC.bat" -Destination "Amazon-Settlement-Transformer\START_SYNC.bat" -Force
Move-Item -Path "deploy_to_production.ps1" -Destination "Amazon-Settlement-Transformer\deploy_to_production.ps1" -Force
Move-Item -Path "sync_to_production.ps1" -Destination "Amazon-Settlement-Transformer\sync_to_production.ps1" -Force
```

### Step 5: Move Virtual Environment (Optional)

```powershell
# If venv exists and is project-specific
Move-Item -Path "venv" -Destination "Amazon-Settlement-Transformer\venv" -Force
```

**Note:** If you move the venv, you'll need to recreate the activation paths. Consider recreating the venv after migration instead.

---

## ✅ Verification Steps

### Step 1: Verify Directory Structure

```powershell
cd C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer

# Check structure
Get-ChildItem -Directory | Select-Object Name
# Should show: config, docs, logs, mCode, outputs, raw_data, scripts, venv (if moved)

Get-ChildItem -File | Select-Object Name
# Should show: README.md, requirements.txt, PROJECT_STATUS_AND_ROADMAP.md, etc.
```

### Step 2: Test Script Imports

```powershell
cd C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer

# Activate venv (if moved)
venv\Scripts\activate

# Test imports
python -c "import sys; sys.path.insert(0, 'scripts'); from zoho_sync import ZohoBooks; print('Import successful')"
```

### Step 3: Update Script Paths (If Needed)

Check if any scripts have hardcoded paths that need updating:

```powershell
# Search for hardcoded paths
cd C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer
Select-String -Path "scripts\*.py" -Pattern "C:\\Users\\User\\Documents\\GitHub[^\\]" -Recurse
```

Most scripts should use relative paths or `scripts/paths.py` which already handles SharePoint paths correctly.

---

## 🔄 Post-Migration Updates

### Update Batch Files

If batch files reference the old location, update them:

**run_pipeline.bat:**
```batch
@echo off
cd /d "%~dp0"
cd C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer
call venv\Scripts\activate.bat
python scripts\main.py
```

**START_SYNC.bat:**
```batch
@echo off
cd /d "%~dp0"
cd C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer
call venv\Scripts\activate.bat
python scripts\post_all_settlements.py --confirm
```

### Update PowerShell Scripts

**deploy_to_production.ps1:**
```powershell
$sourcePath = "C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer"
$prodPath = "C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\etl"
# ... rest of script
```

---

## 📝 Notes

### What Stays the Same

- **SharePoint paths**: No changes needed - `scripts/paths.py` already uses SharePoint paths for tracking files
- **Relative paths**: Scripts using relative paths (like `Path("outputs")`) will work automatically
- **Config files**: YAML configs use relative paths, so no changes needed

### What Needs Attention

- **Virtual environment**: If you move `venv/`, you may need to recreate it or update activation scripts
- **Hardcoded paths**: Search for any hardcoded `C:\Users\User\Documents\GitHub\` paths that don't include `Amazon-Settlement-Transformer`
- **Batch files**: Update batch files to reference the new location

---

## 🚨 Troubleshooting

### Issue: Scripts can't find modules

**Solution:** Make sure you're running scripts from the `Amazon-Settlement-Transformer` directory, or scripts use `sys.path.insert(0, 'scripts')` correctly.

### Issue: Config files not found

**Solution:** Ensure `config/` folder is in `Amazon-Settlement-Transformer/config/` and scripts use relative paths like `Path("config/config.yaml")`.

### Issue: Outputs not saving

**Solution:** Verify `outputs/` directory exists in `Amazon-Settlement-Transformer/outputs/` and scripts have write permissions.

---

## ✅ Completion Checklist

- [ ] All core directories moved to `Amazon-Settlement-Transformer/`
- [ ] All documentation files moved
- [ ] All batch/PowerShell scripts moved
- [ ] Virtual environment handled (moved or recreated)
- [ ] Batch files updated with new paths
- [ ] Script imports tested and working
- [ ] Config files accessible
- [ ] Outputs directory working
- [ ] Logs directory working
- [ ] README.md updated (already done)

---

**Migration Complete!** 🎉

All project files should now be organized under `C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer\`

