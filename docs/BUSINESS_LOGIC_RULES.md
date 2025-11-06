# Business Logic Rules & Assumptions

**Last Updated:** 2025-10-31  
**Purpose:** Document all business logic, assumptions, and rules for the Amazon Settlement ETL pipeline to prevent misunderstandings and ensure consistency.

---

## ⚠️ CRITICAL: Read This File Before Making Logic Changes

**Rule:** Always review this file before modifying business logic in:
- `scripts/exports.py` (data transformation)
- `scripts/sync_settlement.py` (Zoho posting logic)
- `scripts/validate_settlement.py` (validation rules)
- Any other files that implement business rules

---

## 📋 Invoice Numbering Rules

### Format
**Invoice numbers MUST be:** `AMZN` + last 7 digits of `order_id`

**Examples:**
- Order ID: `123-4567890-1234567` → Invoice: `AMZN1234567`
- Order ID: `9876543210` → Invoice: `AMZN7654321`

### Implementation
- **Location:** `scripts/exports.py` - `_generate_invoice_number()` method (line ~1095)
- **Logic:** 
  ```python
  suffix = order_id[-7:] if len(order_id) >= 7 else order_id
  return f"AMZN{suffix}"
  ```

### Special Cases
- **WAREHOUSE DAMAGE transactions:** Use `AMZN` + `YMMDDhh` format (year last digit + month + day + hour)
- **Non-order transactions (no order_id):** Use `AMZN` + `YMMDDhh` format

### Zoho Integration
- **MUST include `invoice_number` field in invoice payload** when posting to Zoho Books
- **MUST include query parameter `ignore_auto_number_generation=true`** in invoice POST request
- **Location:** `scripts/zoho_sync.py` - `create_invoice()` method
- **Payload field:** `"invoice_number": str(invoice_number)`
- **API endpoint:** `POST invoices?ignore_auto_number_generation=true`
- **Why:** Without this parameter, Zoho auto-generates invoice numbers (e.g., "INV-000003") even if invoice_number is provided, breaking payment matching

---

## 🏷️ SKU Mapping Rules

### Purpose
Map Amazon SKUs to Zoho Books Item IDs to ensure invoices post correctly.

### Configuration
- **File:** `config/sku_mapping.yaml`
- **Format:**
  ```yaml
  sku_mapping:
    "SALTT15-ALLT": "SALTT15-ULTA"
    "SALTT30-ALLT": "SALTT30-ULTA"
    "SALTT30-CRML": "SALTT30-VCHO"
  ```

### Mapping Logic
1. **Applied before:** Invoice posting and validation
2. **Location:** `scripts/sync_settlement.py` - `apply_sku_mapping()` function
3. **Behavior:**
   - Original SKU in invoice file is replaced with mapped SKU
   - Mapped SKU is then checked against Zoho Books Items
   - If mapped SKU doesn't exist in Zoho → Warning (non-blocking if override enabled)

### Current Mappings
| Amazon SKU | Zoho SKU | Reason |
|------------|----------|--------|
| SALTT15-ALLT | SALTT15-ULTA | Product name standardization |
| SALTT30-ALLT | SALTT30-ULTA | Product name standardization |
| SALTT30-CRML | SALTT30-VCHO | Product name standardization |

---

## 💰 Payment Alignment Rules

### Multi-Line Invoice Handling
**Rule:** Payments MUST align correctly with multi-line invoices.

### How It Works
1. **Invoice Grouping:** Invoices are grouped by `Invoice Number` (handles multi-line invoices)
2. **Payment Mapping:** Each payment links to ONE invoice via `Invoice Number`
3. **Payment Amount:** Payment amount matches the total of all line items for that invoice number

### Implementation
- **Location:** `scripts/sync_settlement.py` - payment posting section (~line 420+)
- **Invoice Map:** `invoice_number → zoho_invoice_id`
- **Payment Payload:**
  ```python
  "invoices": [{
      "invoice_id": zoho_invoice_id,  # Must be string, not scientific notation
      "amount_applied": float(row['Payment Amount'])
  }]
  ```

### Critical Issues Fixed
1. **Invoice ID Format:** Must be string (not float/scientific notation)
   - **Problem:** `7.39850000004934e+16` → **Solution:** `73985000000493400`
   - **Fix:** Convert to string when loading from tracking file and in payment payload

2. **Invoice Map Source:** 
   - **Priority 1:** Use tracking file (`zoho_tracking.csv`) - no API calls
   - **Priority 2:** Query Zoho API if tracking file incomplete
   - **Why:** Avoids rate limits when building invoice map

---

## 📊 Settlement Reference Number

### Format
**Reference Number = Settlement ID**

- **Example:** Settlement `23874397121` → Reference Number: `23874397121`
- **Purpose:** Links all journals, invoices, and payments to the original Amazon settlement

### Usage
- **Journals:** Reference number = settlement_id
- **Invoices:** Reference number = settlement_id (allows querying by settlement)
- **Payments:** Reference number = settlement_id

### Query Pattern
To find all records for a settlement:
```python
# Invoices
GET invoices?reference_number={settlement_id}

# Payments
GET customerpayments?reference_number={settlement_id}

# Journals
GET journals?reference_number={settlement_id}
```

---

## 🔄 Posting Order & Dependencies

### Critical Posting Order
**MUST follow this order:**

1. **Journals** (no dependencies)
2. **Invoices** (requires: journal exists OR can verify via Zoho)
3. **Payments** (requires: invoices exist AND invoice map available)

### Why This Order?
- **Payments can't exist without invoices:** Zoho won't allow payment creation without linked invoice
- **Invoices should exist before payments:** Ensures invoice map is available for payment linking
- **Journals are independent:** Can be posted anytime, but should exist before invoices/payments for completeness

### Dependency Checks
- **Invoices:** Check if journal exists in Zoho (can query or use tracking)
- **Payments:** Check if invoices exist (build invoice map from tracking file or Zoho API)

---

## 🛡️ Error Handling & Validation

### Validation Levels

#### Blocking Errors (Cannot Proceed)
- **Journal out of balance:** Debits ≠ Credits
- **Unmapped GL accounts:** Required GL account missing from mapping

#### Warnings (Can Override)
- **SKU not found in Zoho:** SKU doesn't exist but mapping available or override enabled
- **Clearing vs Invoices mismatch:** Minor rounding differences (non-blocking)
- **SKU mapping applied:** Informational only

### Override Flag
- **When to use:** For non-blocking warnings
- **Location:** `scripts/post_all_settlements.py` - `override` parameter
- **Default:** `False` (require manual confirmation)

---

## 📁 File Locations & Paths

### SharePoint Directory (Primary Location)
**Base Path:** `C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL`

**Key Files:**
- `settlement_history.csv` - Settlement processing status
- `zoho_tracking.csv` - 1:1 mapping of local records to Zoho IDs
- `action_items.csv` - Items requiring manual intervention

### Project Directory
**Base Path:** `C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer`

### Local Output Files
**Base Path:** `C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer\outputs\{settlement_id}\`

**Files per Settlement:**
- `Invoice_{settlement_id}.csv` - Invoice data
- `Payment_{settlement_id}.csv` - Payment data
- `Journal_{settlement_id}.csv` - Journal entry data
- `Validation_Errors_{settlement_id}.csv` - Validation report

### Path Management
- **Helper Module:** `scripts/paths.py`
- **Always use:** `from paths import get_*_path()` functions
- **Why:** Ensures consistent file locations across all scripts

---

## 🔌 Zoho Books API Rules

### Rate Limits
- **Issue:** Zoho has strict rate limits (varies by endpoint)
- **Symptom:** "You have made too many requests continuously"
- **Solutions:**
  - Use tracking file instead of API calls when possible
  - Add delays between batches (`time.sleep()`)
  - Batch size: Start with 10, reduce to 5 if rate limits hit

### Batch Posting Strategy
**For Payments:**
- **Batch Size:** 10 payments per batch (adjust if rate limits occur)
- **Delay Between Payments:** 0.5 seconds
- **Delay Between Batches:** 5 seconds
- **If Rate Limited:** Wait 30 seconds, reduce batch size

### Customer ID
- **Customer Name:** "Amazon.ca" (hardcoded in export logic)
- **Retrieval:** Query once per settlement, cache for invoices and payments
- **Fallback:** Extract from existing invoices if customer lookup fails

---

## 📝 Tracking & Audit Trail

### Tracking File Format
**File:** `zoho_tracking.csv`

**Columns:**
- `settlement_id` - Settlement identifier
- `record_type` - JOURNAL, INVOICE, or PAYMENT
- `local_identifier` - Local identifier (invoice number, settlement ID, etc.)
- `zoho_id` - Zoho Books ID (journal_id, invoice_id, payment_id)
- `zoho_number` - Zoho-generated number (if different from local)
- `reference_number` - Settlement ID reference
- `status` - POSTED, NOT_POSTED, etc.
- `created_date` - ISO timestamp

### Tracking Rules
1. **Save after posting:** Every successful post updates tracking file
2. **Invoice numbers tracked:** Local invoice number → Zoho invoice_id
3. **Use for payment mapping:** Build invoice map from tracking file (faster, no API calls)

---

## 🚨 Known Issues & Workarounds

### Issue 1: Invoice ID Scientific Notation
**Problem:** Pandas converts large integers to float/scientific notation  
**Example:** `73985000000493400` → `7.39850000004934e+16`  
**Solution:** Always convert to string: `str(zoho_id).strip()` or `f"{zoho_id:.0f}"` for floats

### Issue 2: Zoho Auto-Generated Invoice Numbers
**Problem:** Zoho may auto-generate invoice numbers if `invoice_number` not in payload  
**Solution:** Always include `"invoice_number"` field in invoice payload

### Issue 3: Rate Limits
**Problem:** Too many API calls trigger rate limits  
**Solution:** 
- Use tracking file first (no API calls)
- Batch operations with delays
- Wait for rate limits to reset (15-30 minutes)

---

## 📚 Related Documentation

- **API Reference:** `docs/amazon-sp-api-reference.md` (for Amazon SP-API)
- **Zoho API:** (TBD - user will provide)
- **SKU Mapping:** `config/sku_mapping.yaml`
- **GL Mapping:** `config/zoho_gl_mapping.yaml`

---

## 🔄 Change Log

### 2025-10-31
- ✅ Added `invoice_number` to invoice payload (was missing, causing Zoho auto-generation)
- ✅ Fixed invoice ID format conversion (scientific notation → string)
- ✅ Documented payment alignment for multi-line invoices
- ✅ Documented SKU mapping rules
- ✅ Created this file

---

## 📌 Quick Reference Checklist

Before modifying logic code, verify:

- [ ] Invoice numbers follow `AMZN` + last 7 digits format
- [ ] `invoice_number` field included in Zoho invoice payload
- [ ] SKU mappings applied before validation/posting
- [ ] Payment invoice IDs are strings (not float/scientific notation)
- [ ] Posting order: Journals → Invoices → Payments
- [ ] Tracking file used before API calls (when possible)
- [ ] Rate limit delays added for batch operations
- [ ] Customer ID retrieved/cached appropriately
- [ ] Multi-line invoices grouped correctly
- [ ] Error handling distinguishes blocking vs. warnings

---

**Remember:** When in doubt, check this file first! 🎯

