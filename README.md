# Amazon-Settlement-Transformer

A Python-based ETL (Extract, Transform, Load) pipeline for processing Amazon settlement, invoice, and payment data. This pipeline transforms Amazon remittance files into Zoho Books friendly import files and automatically posts them to Zoho Books API.

## 🚀 Features

- **Automated Data Processing**: Reads and processes `.txt` files from multiple data sources
- **Data Normalization**: Standardizes column names and cleans data values
- **Business Logic**: Applies transformation rules to replicate M Code behavior
- **Multiple Exports**: Generates Journal, Invoice, and Payment CSV exports
- **Zoho Books Integration**: Automatically posts journals, invoices, and payments to Zoho Books API
- **Custom Invoice Numbering**: Enforces `AMZN` + last 7 digits of `order_id` format
- **SKU Mapping**: Maps Amazon SKUs to Zoho Books Item IDs
- **Data Validation**: Built-in quality checks and validation reporting
- **Comprehensive Logging**: Detailed logging for monitoring and debugging
- **Configurable**: All settings managed through YAML configuration
- **Tracking System**: Comprehensive audit trail via `zoho_tracking.csv`

## 📁 Project Structure

```
Amazon-Settlement-Transformer/
├── raw_data/
│   ├── settlements/     # Input settlement .txt files
│   ├── invoices/        # Input invoice .txt files
│   └── payments/        # Input payment .txt files
├── outputs/             # Generated CSV exports (organized by settlement_id)
│   └── {settlement_id}/
│       ├── Invoice_{settlement_id}.csv
│       ├── Payment_{settlement_id}.csv
│       └── Journal_{settlement_id}.csv
├── scripts/             # Python ETL modules
│   ├── main.py         # Main orchestrator
│   ├── transform.py    # Data transformation logic
│   ├── exports.py      # Export generation
│   ├── validate_settlement.py  # Data validation
│   ├── sync_settlement.py  # Zoho Books posting logic
│   ├── zoho_sync.py    # Zoho Books API client
│   ├── paths.py        # Path configuration (SharePoint tracking files)
│   └── ...
├── config/
│   ├── config.yaml     # Main configuration
│   ├── sku_mapping.yaml  # SKU mapping (Amazon → Zoho)
│   ├── zoho_gl_mapping.yaml  # GL account mapping
│   └── zoho_credentials.yaml  # Zoho API credentials
├── docs/
│   ├── BUSINESS_LOGIC_RULES.md  # ⚠️ CRITICAL: Business logic documentation
│   ├── ZoHo API Ref/    # Zoho API reference documentation
│   └── ...
├── logs/               # Log files (auto-created)
├── database/           # Local database files (if any)
├── mCode/              # Original M Code reference (Power Query)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## 🛠️ Setup Instructions

### 1. Install Python Dependencies

```bash
# Navigate to project directory
cd C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer

# Create virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 2. Configure Settings

Edit `config/config.yaml` to customize:
- Input/output folder paths
- Export filenames
- Processing options
- Business rules

Edit `config/zoho_credentials.yaml` with your Zoho Books API credentials.

### 3. Prepare Data

Place your data files in the appropriate folders:
- Settlement files → `raw_data/settlements/`
- Invoice files → `raw_data/invoices/`
- Payment files → `raw_data/payments/`

## 🏃 Running the Pipeline

### Basic Usage

```bash
# Navigate to project directory
cd C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer

# Activate virtual environment
venv\Scripts\activate

# Run the complete ETL pipeline
python scripts/main.py
```

### Advanced Usage

```bash
# Post all settlements to Zoho Books
python scripts/post_all_settlements.py --confirm

# Sync single settlement to Zoho
python scripts/sync_settlement.py {settlement_id}

# Check current status (local vs Zoho)
python scripts/check_current_status.py
```

## 📊 Output Files

The pipeline generates the following outputs in the `outputs/{settlement_id}/` folder:

1. **Journal_{settlement_id}.csv** - General ledger transactions for accounting
2. **Invoice_{settlement_id}.csv** - Invoice-related data for billing
3. **Payment_{settlement_id}.csv** - Payment data for cash management
4. **Validation_Errors_{settlement_id}.csv** - Data quality assessment

## 🔌 Zoho Books Integration

### Current Status

- ✅ **Journals**: 129 posted successfully
- ✅ **Invoices**: 15,629 posted with correct AMZN format
- ⚠️ **Payments**: 200 posted, ~15,800 remaining (HTTP 400 errors being resolved)

### Features

- **Custom Invoice Numbers**: `AMZN` + last 7 digits of `order_id`
- **Multi-line Invoice Support**: Groups invoice line items correctly
- **Payment Alignment**: Links payments to invoices by invoice number
- **Settlement Tracking**: All records linked via `reference_number` (settlement_id)
- **Rate Limit Handling**: Built-in delays and retry logic

### Tracking Files

All tracking files live in SharePoint:
- **Location**: `C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\`
- **Files**: `zoho_tracking.csv`, `settlement_history.csv`, `action_items.csv`

See `docs/BUSINESS_LOGIC_RULES.md` for complete integration details.

## ⚠️ CRITICAL: Business Logic Rules

**ALWAYS check `docs/BUSINESS_LOGIC_RULES.md` before:**
- Modifying business logic in `scripts/exports.py`
- Changing invoice numbering logic
- Updating SKU mapping behavior
- Adjusting payment posting logic
- Modifying validation rules
- Changing Zoho API payload structures

**Key Rules:**
1. Invoice numbers MUST be: `AMZN` + last 7 digits of `order_id`
2. `invoice_number` field MUST be included in invoice payload to Zoho
3. Use `ignore_auto_number_generation=true` query parameter when creating invoices
4. Invoice IDs must be strings (not float/scientific notation)
5. Posting order: Journals → Invoices → Payments
6. Use tracking file before API calls to avoid rate limits

## 🔧 Configuration Options

Key configuration settings in `config/config.yaml`:

```yaml
# Processing options
processing:
  file_patterns:
    settlements: "*.txt"
  column_normalization:
    lowercase: true
    replace_spaces_with_underscores: true

# Business rules
business_rules:
  merge_keys:
    primary: "order_id"
  date_columns:
    - "settlement_start_date"
    - "deposit_date"
```

## 🧪 Testing and Validation

### Data Quality Checks

The pipeline includes automatic validation for:
- ✅ Data completeness (missing values)
- ✅ Business rule compliance (unique keys, valid amounts)
- ✅ Date format validation
- ✅ Numeric value validation
- ✅ SKU mapping validation
- ✅ GL account mapping validation

### Running Tests

```bash
# Run validation tests
python scripts/validate_settlement.py

# Check current status
python scripts/check_current_status.py

# Verify invoice numbers in Zoho
python scripts/check_invoice_numbers.py
```

## 📝 Understanding the Code

### Main Components

1. **main.py** - Entry point that orchestrates the entire ETL process
2. **transform.py** - Contains `DataTransformer` class for data processing
3. **exports.py** - Contains `DataExporter` class for generating CSV files
4. **sync_settlement.py** - Handles Zoho Books posting (journals, invoices, payments)
5. **zoho_sync.py** - Zoho Books API client
6. **validate_settlement.py** - Contains validation and testing utilities

### Key Functions

```python
# Data transformation
transformer = DataTransformer(config)
settlements_data = transformer.process_settlements()

# Export generation
exporter = DataExporter(config)
exporter.generate_journal_export(final_data)

# Zoho Books posting
from sync_settlement import post_settlement_complete
result = post_settlement_complete(settlement_id, post_journal=True, post_invoices=True, post_payments=True)
```

## 🔍 Monitoring and Logging

### Log Files

Logs are automatically created in the `logs/` directory:
- `etl_pipeline.log` - Complete processing log
- `zoho_sync.log` - Zoho API transaction log
- `zoho_api_transactions.log` - Detailed API call log
- Console output - Real-time progress updates

### Log Levels

Set in `config.yaml`:
- `DEBUG` - Detailed technical information
- `INFO` - General progress updates (recommended)
- `WARNING` - Important notices
- `ERROR` - Error conditions only

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure all dependencies are installed
   pip install -r requirements.txt
   ```

2. **File Not Found Errors**
   ```bash
   # Check that data files exist in raw_data folders
   # Verify paths in config.yaml
   ```

3. **Zoho API Rate Limits**
   ```bash
   # The pipeline includes automatic rate limit handling
   # If issues persist, increase delays in sync_settlement.py
   ```

4. **Payment Posting Failures**
   ```bash
   # Check logs/etl_pipeline.log for detailed error messages
   # Verify invoice IDs exist in Zoho before posting payments
   # See docs/BUSINESS_LOGIC_RULES.md for payment posting requirements
   ```

### Getting Help

1. Check the log files in `logs/etl_pipeline.log`
2. Review `docs/BUSINESS_LOGIC_RULES.md` for business logic rules
3. Run validation tests: `python scripts/validate_settlement.py`
4. Check current status: `python scripts/check_current_status.py`

## 📚 Documentation

- **Business Logic Rules**: `docs/BUSINESS_LOGIC_RULES.md` ⚠️ **CRITICAL**
- **Project Status & Roadmap**: `PROJECT_STATUS_AND_ROADMAP.md`
- **Tracking Files Location**: `TRACKING_FILES_LOCATION.md`
- **Zoho API Reference**: `docs/ZoHo API Ref/`

## 🔄 Customization

### Adding New Data Sources

1. Add new folder to `raw_data/`
2. Update `config.yaml` inputs section
3. Add processing method in `transform.py`
4. Create export format in `exports.py`

### Modifying Business Logic

1. **ALWAYS check `docs/BUSINESS_LOGIC_RULES.md` first**
2. Edit transformation functions in `transform.py`
3. Update business rules in `config.yaml`
4. Add validation rules in `validate_settlement.py`
5. Test changes with `python scripts/validate_settlement.py`

## 📋 Maintenance

### Regular Tasks

- Monitor log files for warnings/errors
- Review data validation reports
- Update configuration as business rules change
- Run tests before deploying changes
- Check `zoho_tracking.csv` for posting status

### Performance Tips

- Process data in smaller batches if memory is limited
- Use DEBUG logging sparingly in production
- Clean up old log files periodically
- Monitor output file sizes

---

**Project Location**: `C:\Users\User\Documents\GitHub\Amazon-Settlement-Transformer`  
**Last Updated**: 2025-11-02  
**Status**: Payment posting issues being resolved (see `PROJECT_STATUS_AND_ROADMAP.md`)
