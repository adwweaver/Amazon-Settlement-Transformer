# Invoice/Payment Mapping Reports - Location Guide

## ✅ 1:1 Mapping Report (NEW)

**Location**: `C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\invoice_payment_1to1_mapping.csv`

**Purpose**: Complete 1:1 mapping showing exactly what's local vs what's in Zoho, with gaps identified.

**Contents** (1,355 records):
- Every local invoice with status (MATCHED, NOT_IN_ZOHO)
- Every local payment with status (MATCHED, NOT_IN_ZOHO)  
- Every Zoho invoice/payment not in local files (IN_ZOHO_ONLY)
- Matching method (INVOICE_NUMBER, REFERENCE_NUMBER, AMOUNT_MATCH)
- Action needed (CREATE, UPDATE_TRACKING, VERIFY/DELETE)

**Columns**:
- `settlement_id` - Settlement ID
- `record_type` - INVOICE or PAYMENT
- `local_invoice_number` - Local invoice number (or blank if Zoho-only)
- `local_amount` - Amount in local file
- `local_date` - Date in local file
- `status` - MATCHED, NOT_IN_ZOHO, IN_ZOHO_ONLY
- `zoho_invoice_id` - Zoho invoice ID (if matched/found)
- `zoho_invoice_number` - Zoho invoice number (if matched/found)
- `match_method` - How it was matched (if matched)
- `action_needed` - CREATE, UPDATE_TRACKING, or VERIFY/DELETE

**Summary**:
- **CREATE**: 432 items (payments) need to be created
- **UPDATE_TRACKING**: 436 items (invoices) matched - need tracking updated
- **VERIFY/DELETE**: 487 items in Zoho but not in local files

---

## Other Comparison Files

### 1. `action_items.csv`
**Location**: `C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\action_items.csv`

**Purpose**: Action items breakdown - what needs CREATE/EDIT/DELETE

**Contents**: 1,348 action items
- Items to CREATE (with amounts and dates)
- Items to VERIFY/DELETE (with Zoho IDs)
- Detailed breakdown by settlement

---

### 2. `zoho_comparison.csv`
**Location**: `C:\Users\User\Documents\GitHub\zoho_comparison.csv`

**Purpose**: High-level settlement comparison

**Contents**: Summary by settlement showing:
- Journal status
- Invoice counts (local vs Zoho)
- Payment counts (local vs Zoho)
- Overall status

---

## How to Use the 1:1 Mapping

### Filter by Status

**Find Missing Items (Need to Create)**:
```python
import pandas as pd
df = pd.read_csv(r"C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\invoice_payment_1to1_mapping.csv")

# Items that need to be created
missing = df[df['action_needed'] == 'CREATE']
print(f"Items to CREATE: {len(missing)}")
print(missing[['settlement_id', 'record_type', 'local_invoice_number', 'local_amount']])
```

**Find Matched Items (Need Tracking Updated)**:
```python
matched = df[df['action_needed'] == 'UPDATE_TRACKING']
print(f"Items matched: {len(matched)}")
# These have zoho_invoice_id or zoho_payment_id populated
```

**Find Extra Items in Zoho (Need to Verify/Delete)**:
```python
extra = df[df['action_needed'] == 'VERIFY/DELETE']
print(f"Items in Zoho but not local: {len(extra)}")
# These may be duplicates or incorrect entries
```

### Filter by Settlement

```python
settlement_df = df[df['settlement_id'] == '24288684721']
print(f"Settlement 24288684721:")
print(f"  Total records: {len(settlement_df)}")
print(f"  Missing: {len(settlement_df[settlement_df['action_needed'] == 'CREATE'])}")
print(f"  Matched: {len(settlement_df[settlement_df['action_needed'] == 'UPDATE_TRACKING'])}")
```

---

## Quick Reference

**All mapping/review files are in**:
```
C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\
```

**Files**:
1. ✅ `invoice_payment_1to1_mapping.csv` - **1:1 detailed mapping (use this for gaps)**
2. `action_items.csv` - Action items summary
3. `zoho_tracking.csv` - Tracking with Zoho IDs
4. `settlement_history.csv` - Settlement-level tracking

---

## Next Steps

1. **Open `invoice_payment_1to1_mapping.csv`** in Excel
2. **Filter by `action_needed = 'CREATE'`** to see all missing items
3. **Sort by `settlement_id`** to group by settlement
4. **Use `local_invoice_number` and `local_amount`** to identify exactly what needs to be posted

The mapping shows exactly which invoices/payments are missing, which are matched (but need tracking), and which are in Zoho but shouldn't be.



