#!/usr/bin/env python3
"""
Settlement Validation & Pre-Flight Checks
Validates settlements before Zoho sync and identifies issues requiring user intervention
"""

import pandas as pd
import yaml
from pathlib import Path
from typing import Dict, List, Tuple
from zoho_sync import ZohoBooks
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SettlementValidator:
    """Comprehensive validation for settlements before Zoho posting"""
    
    def __init__(self):
        self.config_dir = Path("config")
        self.output_dir = Path("outputs")
        self.load_config()
        self.sku_mapping = self._load_sku_mapping()
        
    def load_config(self):
        """Load GL mapping and credentials"""
        with open(self.config_dir / "zoho_gl_mapping.yaml") as f:
            config = yaml.safe_load(f)
            self.gl_mapping = config.get('gl_account_mapping', {})
    
    def validate_settlement(self, settlement_id: str) -> Dict:
        """
        Run all validation checks for a settlement
        
        Returns:
            {
                'valid': bool,
                'can_proceed': bool,
                'warnings': [],
                'errors': [],
                'journal_balance': {'debits': float, 'credits': float, 'balanced': bool},
                'missing_gl_accounts': [],
                'missing_skus': [],
                'file_status': {'journal': bool, 'invoice': bool, 'payment': bool}
            }
        """
        result = {
            'settlement_id': settlement_id,
            'valid': True,
            'can_proceed': True,
            'warnings': [],
            'errors': [],
            'journal_balance': {},
            'missing_gl_accounts': [],
            'missing_skus': [],
            'file_status': {}
        }
        
        settlement_dir = self.output_dir / settlement_id
        
        # 1. Check if output files exist
        logger.info(f"Validating settlement {settlement_id}...")
        result['file_status'] = self.check_files_exist(settlement_dir)
        
        if not result['file_status']['journal']:
            result['errors'].append(f"Journal file not found: {settlement_dir}/Journal_{settlement_id}.csv")
            result['valid'] = False
            result['can_proceed'] = False
            return result
        
        # 2. Validate journal balance
        journal_file = settlement_dir / f"Journal_{settlement_id}.csv"
        result['journal_balance'] = self.validate_journal_balance(journal_file)
        
        if not result['journal_balance']['balanced']:
            result['errors'].append(
                f"Journal out of balance! Debits: ${result['journal_balance']['debits']:.2f}, "
                f"Credits: ${result['journal_balance']['credits']:.2f}, "
                f"Difference: ${result['journal_balance']['difference']:.2f}"
            )
            result['valid'] = False
            result['can_proceed'] = False  # STOP - requires user override
        
        # 3. Check for unmapped GL accounts
        result['missing_gl_accounts'] = self.check_gl_mapping(journal_file)
        
        if result['missing_gl_accounts']:
            result['errors'].append(
                f"Unmapped GL accounts: {', '.join(result['missing_gl_accounts'])}"
            )
            result['valid'] = False
            result['can_proceed'] = False  # STOP - requires GL mapping
        
        # 4. Check for SKUs (if invoice exists)
        if result['file_status']['invoice']:
            invoice_file = settlement_dir / f"Invoice_{settlement_id}.csv"
            result['missing_skus'] = self.check_skus(invoice_file)
            
            if result['missing_skus']:
                result['warnings'].append(
                    f"SKUs in invoice but not verified in Zoho: {', '.join(result['missing_skus'])}"
                )
                # This is a WARNING, not an error - can still proceed with user confirmation
        
        # 5. Enforce clearing = invoices and payments = invoices
        try:
            clearing_total = 0.0
            invoices_total = 0.0
            payments_total = 0.0
            # Clearing debit from journal
            journal_file = settlement_dir / f"Journal_{settlement_id}.csv"
            if journal_file.exists():
                jdf = pd.read_csv(journal_file)
                jdf['Debit'] = pd.to_numeric(jdf.get('Debit', 0), errors='coerce').fillna(0)
                jdf['Credit'] = pd.to_numeric(jdf.get('Credit', 0), errors='coerce').fillna(0)
                mask = jdf.get('GL_Account', '').astype(str) == 'Amazon.ca Clearing'
                clearing_total = float(jdf.loc[mask, 'Debit'].sum() - jdf.loc[mask, 'Credit'].sum())
            # Invoices total
            inv_file = settlement_dir / f"Invoice_{settlement_id}.csv"
            if inv_file.exists():
                idf = pd.read_csv(inv_file)
                amt_col = None
                for c in ['Invoice Line Amount', 'amount', 'rate']:
                    if c in idf.columns:
                        amt_col = c; break
                if amt_col:
                    invoices_total = float(pd.to_numeric(idf[amt_col], errors='coerce').fillna(0).sum())
            # Payments total
            pay_file = settlement_dir / f"Payment_{settlement_id}.csv"
            if pay_file.exists():
                pdf = pd.read_csv(pay_file)
                pcol = 'Payment Amount' if 'Payment Amount' in pdf.columns else None
                if pcol:
                    payments_total = float(pd.to_numeric(pdf[pcol], errors='coerce').fillna(0).sum())
            # Compare with small tolerance
            tol = 0.01
            if abs(clearing_total - invoices_total) > tol:
                result['errors'].append(
                    f"Clearing vs Invoices mismatch: Clearing {clearing_total:.2f} != Invoices {invoices_total:.2f}"
                )
                result['valid'] = False
                result['can_proceed'] = False
            if invoices_total > 0 and abs(payments_total - invoices_total) > tol and result['file_status']['payment']:
                result['warnings'].append(
                    f"Payments vs Invoices mismatch: Payments {payments_total:.2f} != Invoices {invoices_total:.2f}"
                )
        except Exception as e:
            logger.warning(f"Could not compute clearing/invoice/payment reconciliation: {e}")
        
        # 5. Additional validations
        result = self.additional_checks(settlement_dir, result)
        
        return result

    def write_error_report(self, settlement_id: str, result: Dict) -> Path:
        """Write a validation errors/warnings report for the settlement.
        Returns path to the report (CSV). Creates an empty file with header if no issues.
        """
        out_dir = self.output_dir
        out_dir.mkdir(exist_ok=True)
        report_file = out_dir / f"Validation_Errors_{settlement_id}.csv"

        rows = []
        for err in result.get('errors', []):
            rows.append({'Type': 'ERROR', 'Message': err})
        for warn in result.get('warnings', []):
            rows.append({'Type': 'WARNING', 'Message': warn})
        # Include unmapped GL accounts as individual rows for clarity
        for account in result.get('missing_gl_accounts', []):
            rows.append({'Type': 'ERROR', 'Message': f"Unmapped GL account: {account}"})

        df = pd.DataFrame(rows if rows else [{'Type': 'INFO', 'Message': 'No issues detected'}])
        df.to_csv(report_file, index=False, encoding='utf-8-sig')
        logger.info(f"Validation report saved: {report_file}")
        return report_file
    
    def check_files_exist(self, settlement_dir: Path) -> Dict[str, bool]:
        """Check which output files exist"""
        settlement_id = settlement_dir.name
        return {
            'journal': (settlement_dir / f"Journal_{settlement_id}.csv").exists(),
            'invoice': (settlement_dir / f"Invoice_{settlement_id}.csv").exists(),
            'payment': (settlement_dir / f"Payment_{settlement_id}.csv").exists()
        }
    
    def validate_journal_balance(self, journal_file: Path) -> Dict:
        """Validate debits = credits"""
        df = pd.read_csv(journal_file)
        
        debits = df['Debit'].sum()
        credits = df['Credit'].sum()
        difference = abs(debits - credits)
        balanced = difference < 0.01  # Allow 1 cent rounding
        
        return {
            'debits': round(debits, 2),
            'credits': round(credits, 2),
            'difference': round(difference, 2),
            'balanced': balanced,
            'line_count': len(df)
        }
    
    def check_gl_mapping(self, journal_file: Path) -> List[str]:
        """Check for GL accounts without Zoho mapping"""
        df = pd.read_csv(journal_file)
        
        missing = []
        for account in df['GL_Account'].unique():
            if account not in self.gl_mapping:
                missing.append(account)
        
        return missing
    
    def check_skus(self, invoice_file: Path) -> List[str]:
        """Return SKUs that are not found in Zoho (after applying local mapping)."""
        df = pd.read_csv(invoice_file)
        if 'SKU' not in df.columns:
            return []

        # Normalize and de-duplicate
        skus = [str(s) for s in df['SKU'].dropna().unique().tolist()]

        # Apply local SKU mapping
        mapped_skus = [self.sku_mapping.get(sku, sku) for sku in skus]

        # Check existence in Zoho (unique only)
        zoho = ZohoBooks()
        missing: List[str] = []
        for sku in sorted(set(mapped_skus)):
            try:
                item_id = zoho.get_item_id(sku)
                if not item_id:
                    missing.append(sku)
            except Exception as e:
                logger.warning(f"SKU check failed for {sku}: {e}")
        return missing

    def _load_sku_mapping(self) -> Dict[str, str]:
        """Load SKU mapping from config; fall back to empty mapping on error."""
        mapping_file = self.config_dir / "sku_mapping.yaml"
        if not mapping_file.exists():
            return {}
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
                mapping = cfg.get('sku_mapping', {}) or {}
                return {str(k): str(v) for k, v in mapping.items()}
        except Exception as e:
            logger.warning(f"Failed to load SKU mapping from {mapping_file}: {e}")
            return {}
    
    def additional_checks(self, settlement_dir: Path, result: Dict) -> Dict:
        """Additional validation checks"""
        settlement_id = settlement_dir.name
        
        # Check for duplicate order IDs
        journal_file = settlement_dir / f"Journal_{settlement_id}.csv"
        if journal_file.exists():
            df = pd.read_csv(journal_file)
            if 'Notes' in df.columns:
                # Extract order IDs from notes
                order_ids = df['Notes'].str.extract(r'Order ID: (\d+-\d+-\d+)', expand=False).dropna()
                duplicates = order_ids[order_ids.duplicated()].unique()
                
                if len(duplicates) > 0:
                    result['warnings'].append(f"Duplicate order IDs found: {', '.join(duplicates)}")
        
        return result
    
    def print_validation_report(self, result: Dict):
        """Pretty print validation results"""
        print("\n" + "="*70)
        print(f"VALIDATION REPORT - Settlement {result['settlement_id']}")
        print("="*70)
        
        # Overall status
        status_icon = "✅" if result['valid'] else "❌"
        proceed_icon = "🟢" if result['can_proceed'] else "🔴"
        print(f"\n{status_icon} Valid: {result['valid']}")
        print(f"{proceed_icon} Can Proceed: {result['can_proceed']}")
        
        # Journal balance
        print(f"\n📊 JOURNAL BALANCE:")
        jb = result['journal_balance']
        if jb:
            balance_icon = "✅" if jb['balanced'] else "❌"
            print(f"  {balance_icon} Debits:  ${jb['debits']:,.2f}")
            print(f"  {balance_icon} Credits: ${jb['credits']:,.2f}")
            if not jb['balanced']:
                print(f"  ⚠️  Difference: ${jb['difference']:,.2f}")
            print(f"  📝 Line Count: {jb['line_count']}")
        
        # GL Accounts
        if result['missing_gl_accounts']:
            print(f"\n❌ MISSING GL MAPPINGS:")
            for account in result['missing_gl_accounts']:
                print(f"  - {account}")
        else:
            print(f"\n✅ All GL accounts mapped")
        
        # SKUs
        if result['missing_skus']:
            print(f"\n⚠️  SKUs TO VERIFY IN ZOHO:")
            for sku in result['missing_skus']:
                print(f"  - {sku}")
        
        # Files
        print(f"\n📁 FILES:")
        for file_type, exists in result['file_status'].items():
            icon = "✅" if exists else "❌"
            print(f"  {icon} {file_type.capitalize()}: {exists}")
        
        # Errors
        if result['errors']:
            print(f"\n❌ ERRORS:")
            for error in result['errors']:
                print(f"  - {error}")
        
        # Warnings
        if result['warnings']:
            print(f"\n⚠️  WARNINGS:")
            for warning in result['warnings']:
                print(f"  - {warning}")
        
        print("\n" + "="*70)
        
        # Action required
        if not result['can_proceed']:
            print("🛑 ACTION REQUIRED - Cannot proceed until issues are resolved")
            print("="*70)
        elif result['warnings']:
            print("⚠️  REVIEW WARNINGS - Proceed with caution")
            print("="*70)
        else:
            print("✅ READY TO SYNC - All validations passed")
            print("="*70)
        
        return result


def validate_all_pending_settlements():
    """Validate all settlements that haven't been synced to Zoho"""
    from paths import get_settlement_history_path
    history = pd.read_csv(get_settlement_history_path())
    pending = history[history['zoho_synced'] == False]
    
    validator = SettlementValidator()
    results = []
    
    for _, row in pending.iterrows():
        settlement_id = row['settlement_id']
        result = validator.validate_settlement(str(settlement_id))
        validator.print_validation_report(result)
        results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    total = len(results)
    ready = sum(1 for r in results if r['can_proceed'])
    blocked = sum(1 for r in results if not r['can_proceed'])
    warnings = sum(1 for r in results if r['warnings'])
    
    print(f"Total settlements: {total}")
    print(f"✅ Ready to sync: {ready}")
    print(f"⚠️  With warnings: {warnings}")
    print(f"🔴 Blocked: {blocked}")
    print("="*70)
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Validate specific settlement
        settlement_id = sys.argv[1]
        validator = SettlementValidator()
        result = validator.validate_settlement(settlement_id)
        validator.print_validation_report(result)
    else:
        # Validate all pending
        validate_all_pending_settlements()
