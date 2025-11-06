"""
Audit Trail System for Amazon Settlement Processing

Creates comprehensive records of:
1. Source files and data
2. Generated journals/invoices/payments
3. Zoho postings with IDs
4. Reconciliation between local and Zoho
5. Complete audit trail for compliance
"""

import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json

from zoho_sync import ZohoBooks


class AuditTrail:
    """Manages audit trail for settlement processing and Zoho sync"""
    
    def __init__(self, audit_db_path: str = 'database/audit_trail.db.csv'):
        self.audit_db_path = Path(audit_db_path)
        self.audit_db_path.parent.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Initialize audit database
        self._init_audit_db()
    
    def _init_audit_db(self):
        """Initialize or load audit trail database"""
        if self.audit_db_path.exists():
            self.audit_df = pd.read_csv(self.audit_db_path)
            self.logger.info(f"Loaded {len(self.audit_df)} audit records")
        else:
            # Create new audit database with comprehensive columns
            self.audit_df = pd.DataFrame(columns=[
                # Settlement identification
                'settlement_id',
                'settlement_date_start',
                'settlement_date_end',
                'deposit_date',
                'marketplace',
                'currency',
                
                # Source file tracking
                'source_file_name',
                'source_file_path',
                'source_file_hash',
                'source_file_row_count',
                'source_file_date_processed',
                
                # Generated local files
                'journal_csv_path',
                'journal_csv_hash',
                'journal_line_count',
                'journal_total_debits',
                'journal_total_credits',
                'journal_balanced',
                
                'invoice_csv_path',
                'invoice_csv_hash',
                'invoice_count',
                'invoice_line_count',
                'invoice_total_amount',
                
                'payment_csv_path',
                'payment_csv_hash',
                'payment_count',
                'payment_total_amount',
                
                # Zoho posting details
                'zoho_sync_date',
                'zoho_sync_user',
                'zoho_journal_id',
                'zoho_journal_number',
                'zoho_journal_date',
                'zoho_journal_status',
                
                'zoho_invoice_ids',  # JSON array
                'zoho_invoice_numbers',  # JSON array
                'zoho_invoice_count',
                'zoho_invoice_total',
                
                'zoho_payment_ids',  # JSON array
                'zoho_payment_numbers',  # JSON array
                'zoho_payment_count',
                'zoho_payment_total',
                
                # Reconciliation
                'reconciliation_status',  # 'matched', 'discrepancy', 'not_synced'
                'reconciliation_date',
                'reconciliation_notes',
                'local_vs_zoho_variance',
                
                # Audit metadata
                'created_date',
                'created_by',
                'last_modified_date',
                'last_modified_by',
                'audit_notes',
                'processing_version'
            ])
            self.logger.info("Initialized new audit trail database")
    
    def record_settlement_processing(self, settlement_id: str, 
                                     source_file: str,
                                     journal_data: Dict,
                                     invoice_data: Dict,
                                     payment_data: Dict) -> None:
        """
        Record complete settlement processing details
        
        Args:
            settlement_id: Settlement ID
            source_file: Path to source remittance file
            journal_data: Dict with journal file info and totals
            invoice_data: Dict with invoice file info and totals
            payment_data: Dict with payment file info and totals
        """
        import hashlib
        
        # Calculate file hash for source file
        source_hash = self._calculate_file_hash(source_file)
        
        # Prepare audit record
        audit_record = {
            'settlement_id': settlement_id,
            'settlement_date_start': journal_data.get('date_start'),
            'settlement_date_end': journal_data.get('date_end'),
            'deposit_date': journal_data.get('deposit_date'),
            'marketplace': 'Amazon.ca',
            'currency': 'CAD',
            
            # Source file
            'source_file_name': Path(source_file).name,
            'source_file_path': source_file,
            'source_file_hash': source_hash,
            'source_file_row_count': journal_data.get('source_row_count'),
            'source_file_date_processed': datetime.now().isoformat(),
            
            # Journal
            'journal_csv_path': journal_data.get('csv_path'),
            'journal_csv_hash': self._calculate_file_hash(journal_data.get('csv_path')),
            'journal_line_count': journal_data.get('line_count'),
            'journal_total_debits': journal_data.get('total_debits'),
            'journal_total_credits': journal_data.get('total_credits'),
            'journal_balanced': journal_data.get('balanced'),
            
            # Invoices
            'invoice_csv_path': invoice_data.get('csv_path'),
            'invoice_csv_hash': self._calculate_file_hash(invoice_data.get('csv_path')),
            'invoice_count': invoice_data.get('invoice_count'),
            'invoice_line_count': invoice_data.get('line_count'),
            'invoice_total_amount': invoice_data.get('total_amount'),
            
            # Payments
            'payment_csv_path': payment_data.get('csv_path'),
            'payment_csv_hash': self._calculate_file_hash(payment_data.get('csv_path')),
            'payment_count': payment_data.get('payment_count'),
            'payment_total_amount': payment_data.get('total_amount'),
            
            # Metadata
            'reconciliation_status': 'not_synced',
            'created_date': datetime.now().isoformat(),
            'created_by': 'ETL_Pipeline',
            'processing_version': '1.0'
        }
        
        # Add or update record
        self._upsert_record(settlement_id, audit_record)
        self.logger.info(f"Recorded processing audit for settlement {settlement_id}")
    
    def record_zoho_sync(self, settlement_id: str,
                        journal_result: Dict,
                        invoice_results: List[Dict],
                        payment_results: List[Dict]) -> None:
        """
        Record Zoho sync results
        
        Args:
            settlement_id: Settlement ID
            journal_result: Dict with journal_id, journal_number, etc.
            invoice_results: List of dicts with invoice details
            payment_results: List of dicts with payment details
        """
        # Get existing record
        existing = self.audit_df[self.audit_df['settlement_id'] == settlement_id]
        
        if existing.empty:
            self.logger.warning(f"No audit record found for {settlement_id}, creating new one")
            audit_record = {'settlement_id': settlement_id}
        else:
            audit_record = existing.iloc[0].to_dict()
        
        # Update with Zoho details
        audit_record.update({
            'zoho_sync_date': datetime.now().isoformat(),
            'zoho_sync_user': 'Automated_Sync',
            
            # Journal
            'zoho_journal_id': journal_result.get('journal_id'),
            'zoho_journal_number': journal_result.get('entry_number'),
            'zoho_journal_date': journal_result.get('journal_date'),
            'zoho_journal_status': journal_result.get('status', 'published'),
            
            # Invoices
            'zoho_invoice_ids': json.dumps([inv.get('invoice_id') for inv in invoice_results]),
            'zoho_invoice_numbers': json.dumps([inv.get('invoice_number') for inv in invoice_results]),
            'zoho_invoice_count': len(invoice_results),
            'zoho_invoice_total': sum(float(inv.get('total', 0)) for inv in invoice_results),
            
            # Payments
            'zoho_payment_ids': json.dumps([pmt.get('payment_id') for pmt in payment_results]),
            'zoho_payment_numbers': json.dumps([pmt.get('payment_number') for pmt in payment_results]),
            'zoho_payment_count': len(payment_results),
            'zoho_payment_total': sum(float(pmt.get('amount', 0)) for pmt in payment_results),
            
            'last_modified_date': datetime.now().isoformat(),
            'last_modified_by': 'Zoho_Sync'
        })
        
        self._upsert_record(settlement_id, audit_record)
        self.logger.info(f"Recorded Zoho sync audit for settlement {settlement_id}")
    
    def reconcile_settlement(self, settlement_id: str) -> Dict:
        """
        Reconcile local files against Zoho Books data
        
        Returns:
            Dict with reconciliation results
        """
        zoho = ZohoBooks()
        
        # Get audit record
        record = self.audit_df[self.audit_df['settlement_id'] == settlement_id]
        if record.empty:
            return {'status': 'error', 'message': 'Settlement not found in audit trail'}
        
        record = record.iloc[0]
        
        # Get Zoho data
        journal_id = record['zoho_journal_id']
        if pd.isna(journal_id):
            return {'status': 'not_synced', 'message': 'Settlement not synced to Zoho'}
        
        # Fetch journal from Zoho
        journal_zoho = zoho._api_request('GET', f'journals/{journal_id}')
        
        # Calculate totals from Zoho
        zoho_debits = sum(float(line.get('amount', 0)) 
                         for line in journal_zoho.get('journal', {}).get('line_items', [])
                         if line.get('debit_or_credit') == 'debit')
        zoho_credits = sum(float(line.get('amount', 0))
                          for line in journal_zoho.get('journal', {}).get('line_items', [])
                          if line.get('debit_or_credit') == 'credit')
        
        # Compare with local
        local_debits = float(record['journal_total_debits'])
        local_credits = float(record['journal_total_credits'])
        
        variance = abs((zoho_debits - local_debits) + (zoho_credits - local_credits))
        
        # Update reconciliation status
        if variance < 0.01:  # Within 1 cent
            status = 'matched'
            notes = f'Reconciled successfully. Variance: ${variance:.2f}'
        else:
            status = 'discrepancy'
            notes = f'Discrepancy found. Variance: ${variance:.2f}'
        
        # Update audit record
        idx = self.audit_df[self.audit_df['settlement_id'] == settlement_id].index[0]
        self.audit_df.at[idx, 'reconciliation_status'] = status
        self.audit_df.at[idx, 'reconciliation_date'] = datetime.now().isoformat()
        self.audit_df.at[idx, 'reconciliation_notes'] = notes
        self.audit_df.at[idx, 'local_vs_zoho_variance'] = variance
        
        self._save()
        
        return {
            'status': status,
            'variance': variance,
            'local_debits': local_debits,
            'local_credits': local_credits,
            'zoho_debits': zoho_debits,
            'zoho_credits': zoho_credits,
            'notes': notes
        }
    
    def generate_audit_report(self, settlement_id: Optional[str] = None,
                            output_path: Optional[str] = None) -> pd.DataFrame:
        """
        Generate comprehensive audit report
        
        Args:
            settlement_id: Optional specific settlement to report on
            output_path: Optional path to save Excel report
        
        Returns:
            DataFrame with audit report
        """
        if settlement_id:
            report_df = self.audit_df[self.audit_df['settlement_id'] == settlement_id].copy()
        else:
            report_df = self.audit_df.copy()
        
        # Add computed columns
        report_df['days_since_processing'] = (
            pd.to_datetime('now') - pd.to_datetime(report_df['created_date'])
        ).dt.days
        
        report_df['synced_to_zoho'] = ~report_df['zoho_journal_id'].isna()
        
        # Format for readability
        report_df = report_df.sort_values('deposit_date', ascending=False)
        
        if output_path:
            report_df.to_excel(output_path, index=False)
            self.logger.info(f"Audit report saved to {output_path}")
        
        return report_df
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file for integrity verification"""
        import hashlib
        
        if not file_path or pd.isna(file_path):
            return None
        
        path = Path(file_path)
        if not path.exists():
            return None
        
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def _upsert_record(self, settlement_id: str, record: Dict):
        """Insert or update audit record"""
        existing_idx = self.audit_df[self.audit_df['settlement_id'] == settlement_id].index
        
        if len(existing_idx) > 0:
            # Update existing
            for key, value in record.items():
                if key in self.audit_df.columns:
                    self.audit_df.at[existing_idx[0], key] = value
        else:
            # Insert new
            new_df = pd.DataFrame([record])
            self.audit_df = pd.concat([self.audit_df, new_df], ignore_index=True)
        
        self._save()
    
    def _save(self):
        """Save audit database to CSV"""
        self.audit_df.to_csv(self.audit_db_path, index=False)
        self.logger.debug(f"Audit trail saved: {len(self.audit_df)} records")


if __name__ == "__main__":
    # Test/demo
    logging.basicConfig(level=logging.INFO)
    audit = AuditTrail()
    
    print(f"Loaded {len(audit.audit_df)} audit records")
    
    # Generate report
    report = audit.generate_audit_report()
    print("\nAudit Trail Summary:")
    print(f"  Total Settlements: {len(report)}")
    print(f"  Synced to Zoho: {report['synced_to_zoho'].sum()}")
    print(f"  Reconciled: {(report['reconciliation_status'] == 'matched').sum()}")
