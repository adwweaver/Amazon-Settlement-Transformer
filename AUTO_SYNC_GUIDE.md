# Auto-Sync Workflow - Keep Both Environments in Sync

## Overview

When you're actively developing and want both environments to stay synchronized, use the **Auto-Sync** feature.

## How It Works

The auto-sync script monitors your development files and automatically copies changes to production whenever you save a file.

### Files That Auto-Sync:
- All Python scripts in `scripts/` folder
- `config/config.yaml`
- `create_excel_tracking.py`

### What Doesn't Sync:
- Archive folder
- Test data
- Outputs
- Logs

---

## Usage

### Option 1: Run Auto-Sync While Developing (Recommended)

**Start the sync monitor:**
1. Double-click `START_SYNC.bat` in the GitHub folder
2. Leave the window open while you work
3. Edit files in VS Code
4. **Changes automatically sync to production!**
5. Press Ctrl+C to stop when done

**Or from PowerShell:**
```powershell
cd C:\Users\User\Documents\GitHub
.\sync_to_production.ps1
```

### Option 2: One-Time Sync

When you want to manually sync all changes once:
```powershell
cd C:\Users\User\Documents\GitHub
.\sync_to_production.ps1 -Once
```

### Option 3: Manual Deployment (Old Way)

For more control over what gets deployed:
```powershell
cd C:\Users\User\Documents\GitHub
.\deploy_to_production.ps1
```

---

## Typical Workflow

### During Active Development:

1. **Start Auto-Sync** (once at beginning of session)
   ```
   Double-click: START_SYNC.bat
   ```

2. **Develop in VS Code**
   - Edit `scripts/transform.py`
   - Save file (Ctrl+S)
   - ✅ Automatically copied to production!

3. **Test in Development**
   ```powershell
   cd C:\Users\User\Documents\GitHub
   python scripts/main.py
   ```

4. **Production Already Updated!**
   - No manual deployment needed
   - Both environments stay in sync

5. **Stop Sync** (when done for the day)
   - Press Ctrl+C in sync window
   - Or just close the window

---

## Example Session

```
=== MORNING ===
1. Open VS Code at C:\Users\User\Documents\GitHub
2. Double-click START_SYNC.bat
3. Start developing...

=== WHILE WORKING ===
Edit: scripts/exports.py
Save: Ctrl+S
Sync Window: "Synced: exports.py" ✓

Edit: scripts/transform.py
Save: Ctrl+S
Sync Window: "Synced: transform.py" ✓

=== TEST LOCALLY ===
Terminal: python scripts/main.py
Check outputs/

=== PRODUCTION IS ALREADY UPDATED! ===
No deployment needed - changes already in SharePoint etl/ folder

=== END OF DAY ===
Close sync window or press Ctrl+C
```

---

## Sync Script Options

### Basic Usage
```powershell
# Continuous monitoring (default)
.\sync_to_production.ps1

# One-time sync
.\sync_to_production.ps1 -Once

# Check every 2 seconds (faster response)
.\sync_to_production.ps1 -IntervalSeconds 2

# Check every 30 seconds (less frequent)
.\sync_to_production.ps1 -IntervalSeconds 30
```

---

## What Gets Synced?

### ✅ Always Synced
- `scripts/*.py` → Production `scripts/`
- `config/config.yaml` → Production `config/`
- `create_excel_tracking.py` → Production root

### ❌ Never Synced (Development Only)
- `_archive/` folder
- `outputs/` folder
- `logs/` folder
- `raw_data/` files
- `.git/` folder
- Virtual environments

---

## Benefits

**Before Auto-Sync:**
1. Edit file in development
2. Save file
3. Remember to deploy
4. Run deploy script
5. Confirm deployment
6. Test in production

**With Auto-Sync:**
1. Edit file in development
2. Save file
3. ✅ **Done! Production already updated**

---

## Safety Features

- **Only copies newer files** - Won't overwrite if production is newer
- **No data loss** - Doesn't delete anything
- **One-way sync** - Development → Production only
- **Selective sync** - Only syncs code files, not data/logs
- **Can be stopped anytime** - Ctrl+C to stop

---

## Comparison: Three Deployment Methods

| Method | Use Case | Speed | Control |
|--------|----------|-------|---------|
| **Auto-Sync** | Active development | Instant | Automatic |
| **One-Time Sync** | Quick update | Fast | Manual trigger |
| **Full Deploy** | Major releases | Slower | Full control |

---

## Tips

💡 **Keep sync window visible** - You'll see every file sync in real-time

💡 **Test locally first** - Auto-sync copies files, but test locally before users see changes

💡 **One sync window** - Don't run multiple sync scripts at once

💡 **Works with git** - Auto-sync doesn't interfere with git operations

💡 **Restart after config changes** - If you modify `sync_to_production.ps1`, restart it

---

## Troubleshooting

**Q: Sync window says "ERROR: Production path not found"**
A: Make sure the SharePoint folder is syncing and accessible

**Q: Files aren't syncing**
A: Check that you're editing files in the monitored folders (`scripts/`, `config/`)

**Q: Want to sync different files?**
A: Edit `sync_to_production.ps1` and modify the `$syncPaths` array

**Q: Accidentally synced bad code?**
A: Copy good version from production back to development, or use git to revert

---

## Advanced: Customize What Syncs

Edit `sync_to_production.ps1` line 23-27:

```powershell
$syncPaths = @(
    @{Pattern="scripts\*.py"; Dest="scripts\"},
    @{Pattern="config\config.yaml"; Dest="config\"},
    @{Pattern="create_excel_tracking.py"; Dest=""},
    # Add more patterns here
    @{Pattern="requirements.txt"; Dest=""}
)
```

---

## Summary

🚀 **Best for rapid development** - Edit, save, it's live!

⚡ **No manual deployment** - Saves time and prevents forgetting

🔄 **Both environments stay current** - Never out of sync

🎯 **Focus on coding** - Not on deployment logistics
