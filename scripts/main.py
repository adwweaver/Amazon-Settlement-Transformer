#!/usr/bin/env python3
"""
Amazon Settlement ETL Pipeline - Main Orchestrator

This script is the main entry point for the Amazon settlement data processing pipeline.
It coordinates the entire ETL (Extract, Transform, Load) process by:
1. Loading configuration settings
2. Reading raw data files from settlements, invoices, and payments folders
3. Applying data transformations and cleaning
4. Generating the required export files

Usage: python main.py

Author: ETL Pipeline
Date: October 2025
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
import yaml
import pandas as pd
import shutil
import os

# Import our custom modules
from transform import DataTransformer
from exports import DataExporter
from tracking import EntryTracker
from validate_settlement import SettlementValidator
from notifications import send_email


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure logging for the ETL pipeline.
    
    Args:
        log_level: The logging level (INFO, DEBUG, WARNING, ERROR)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Clear any existing handlers and reconfigure
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    # Configure logging format
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "etl_pipeline.log", mode='w'),  # Overwrite file
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Force reconfiguration
    )


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load configuration settings from YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Dictionary containing configuration settings
        
    Raises:
        FileNotFoundError: If configuration file doesn't exist
        yaml.YAMLError: If configuration file is invalid
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            logging.info(f"Configuration loaded from: {config_path}")
            return config
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file: {e}")
        raise


def validate_paths(config: Dict[str, Any]) -> None:
    """
    Validate that required directories exist.
    
    Args:
        config: Configuration dictionary
        
    Raises:
        FileNotFoundError: If required directories don't exist
    """
    # Check raw data directory
    raw_data_path = Path(config['paths']['raw_data'])
    if not raw_data_path.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_data_path}")
    
    # Check input subdirectories
    for input_type in config['inputs'].values():
        input_path = raw_data_path / input_type
        if not input_path.exists():
            logging.warning(f"Input directory not found (will be skipped): {input_path}")
    
    # Create outputs directory if it doesn't exist
    output_path = Path(config['paths']['outputs'])
    output_path.mkdir(exist_ok=True)
    logging.info(f"Output directory ready: {output_path}")


def organize_outputs_by_settlement(settlements_data: pd.DataFrame, config: Dict[str, Any]) -> None:
    """
    Organize output files into settlement-specific folders.
    Creates folders named by settlement ID, with (2), (3) suffixes for duplicates.
    
    Args:
        settlements_data: DataFrame containing settlement data
        config: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    output_path = Path(config['paths']['outputs'])
    
    if settlements_data is None or settlements_data.empty:
        logger.warning("No settlements data available to organize outputs")
        return
    
    # Get unique settlement IDs (column name is 'settlement_id' with underscore)
    if 'settlement_id' not in settlements_data.columns:
        logger.error("settlement_id column not found in settlements data")
        return
    
    settlement_ids = settlements_data['settlement_id'].unique()
    
    for settlement_id in settlement_ids:
        # Find files for this settlement
        settlement_files = list(output_path.glob(f"*_{settlement_id}.*"))
        
        if not settlement_files:
            continue
        
        # Create settlement folder name
        base_folder_name = str(settlement_id)
        settlement_folder = output_path / base_folder_name
        
        # Remove existing folder if it exists (to avoid duplicates)
        if settlement_folder.exists():
            shutil.rmtree(settlement_folder, ignore_errors=True)
            logger.info(f"Removed existing folder: {settlement_folder.name}")
        
        # Create the folder
        settlement_folder.mkdir(exist_ok=True)
        logger.info(f"Created output folder: {settlement_folder.name}")
        
        # Move settlement-specific files to the folder
        for file in settlement_files:
            dest = settlement_folder / file.name
            shutil.move(str(file), str(dest))
            logger.info(f"  Moved {file.name} to {settlement_folder.name}/")
    
    # Dashboard stays in root outputs folder
    dashboard_file = output_path / "Dashboard_Summary.xlsx"
    if dashboard_file.exists():
        logger.info("Dashboard_Summary.xlsx remains in outputs root")


def main():
    """
    Main execution function for the ETL pipeline.
    
    This function orchestrates the entire process:
    1. Load configuration and setup logging
    2. Validate required paths
    3. Initialize data transformer and processor
    4. Process each data source (settlements, invoices, payments)
    5. Generate export files
    """
    try:
        # Load configuration
        config = load_config()
        
        # Setup logging
        setup_logging(config['options']['log_level'])
        logger = logging.getLogger(__name__)
        
        logger.info("=== Amazon Settlement ETL Pipeline Started ===")
        # Avoid logging full configuration to prevent leaking sensitive info
        try:
            cfg_info = {
                'paths': list(config.get('paths', {}).keys()),
                'exports': list(config.get('exports', {}).keys()),
                'options': {k: config.get('options', {}).get(k) for k in ['log_level', 'overwrite']}
            }
            logger.info(f"Configuration keys loaded: {cfg_info}")
        except Exception:
            logger.info("Configuration loaded")
        
        # Validate paths
        validate_paths(config)
        
        # Initialize data transformer
        transformer = DataTransformer(config)
        
        # Process all data sources
        logger.info("Starting data extraction and transformation...")
        
        # Load and transform settlements data
        settlements_data = transformer.process_settlements()
        logger.info(f"Processed {len(settlements_data) if settlements_data is not None else 0} settlement records")
        
        # Load and transform invoices data
        invoices_data = transformer.process_invoices()
        logger.info(f"Processed {len(invoices_data) if invoices_data is not None else 0} invoice records")
        
        # Load and transform payments data
        payments_data = transformer.process_payments()
        logger.info(f"Processed {len(payments_data) if payments_data is not None else 0} payment records")
        
        # Perform data merging and final transformations
        logger.info("Merging and finalizing data transformations...")
        final_data = transformer.merge_and_finalize(
            settlements_data, 
            invoices_data, 
            payments_data
        )
        
        # Initialize data exporter
        exporter = DataExporter(config)
        
        # Pass price lookup data from transformer to exporter
        if hasattr(transformer, 'price_lookup_data'):
            exporter.price_lookup_data = transformer.price_lookup_data
        
        # Generate export files
        logger.info("Generating export files...")
        
        # Generate Journal Export
        journal_exported = exporter.generate_journal_export(final_data)
        if journal_exported:
            logger.info("Journal export generated successfully")
        
        # Generate Invoice Export
        invoice_exported = exporter.generate_invoice_export(final_data)
        if invoice_exported:
            logger.info("Invoice export generated successfully")
        
        # Generate Payment Export
        payment_exported = exporter.generate_payment_export(final_data)
        if payment_exported:
            logger.info("Payment export generated successfully")
        
        # Generate Dashboard Summary
        dashboard_generated = exporter.generate_dashboard_summary(final_data)
        if dashboard_generated:
            logger.info("Dashboard summary generated successfully")
        
        # Generate GL Mapping and Summary reports
        try:
            gl_reports = exporter.generate_gl_reports(final_data)
            if gl_reports:
                logger.info("GL reports generated successfully")
        except Exception as e:
            logger.warning(f"GL reports generation failed: {e}")
        
        # Record settlement history for trending and analysis
        try:
            tracker = EntryTracker()
            journal_data = final_data.get('journal', pd.DataFrame())
            logger.info(f"Journal data columns: {list(journal_data.columns[:5]) if not journal_data.empty else 'EMPTY'}")
            logger.info(f"Has settlement_id column: {'settlement_id' in journal_data.columns}")
            
            if settlements_data is not None and 'settlement_id' in journal_data.columns:
                logger.info("Starting settlement history recording...")
                
                for settlement_id in journal_data['settlement_id'].unique():
                    # Get journal rows for GL account totals
                    journal_rows = journal_data[journal_data['settlement_id'] == settlement_id]
                    
                    # Get original settlement rows for metadata (dates, amounts)
                    settlement_rows = settlements_data[settlements_data['settlement_id'] == settlement_id]
                    
                    # Get formatted journal to access GL accounts
                    formatted_journal = exporter._format_journal_data(journal_rows)
                    
                    # Calculate GL account totals
                    gl_totals = {}
                    if not formatted_journal.empty and 'GL_Account' in formatted_journal.columns:
                        for gl_account in formatted_journal['GL_Account'].unique():
                            gl_rows = formatted_journal[formatted_journal['GL_Account'] == gl_account]
                            total_debit = pd.to_numeric(gl_rows.get('Debit', 0), errors='coerce').sum()
                            total_credit = pd.to_numeric(gl_rows.get('Credit', 0), errors='coerce').sum()
                            net_amount = total_debit - total_credit
                            gl_totals[gl_account] = float(net_amount) if not pd.isna(net_amount) else 0.0
                    
                    # Get settlement metadata with proper date formatting
                    deposit_date = ''
                    date_from = ''
                    date_to = ''
                    bank_deposit = 0.0
                    tax_count = 0
                    
                    try:
                        if 'deposit_date' in settlement_rows.columns:
                            dd = settlement_rows['deposit_date'].iloc[0]
                            # Convert to datetime and strip timezone
                            dd_dt = pd.to_datetime(dd, errors='coerce', utc=True)
                            deposit_date = dd_dt.tz_localize(None).strftime('%Y-%m-%d') if pd.notna(dd_dt) else ''
                            logger.debug(f"  Settlement {settlement_id} deposit_date: {deposit_date}")
                    except Exception as e:
                        logger.debug(f"  Could not extract deposit_date: {e}")
                    
                    try:
                        if 'posted_date' in settlement_rows.columns:
                            # Convert to datetime and filter valid dates
                            dates = pd.to_datetime(settlement_rows['posted_date'], errors='coerce')
                            valid_dates = dates[dates.notna()]
                            if len(valid_dates) > 0:
                                date_from = str(valid_dates.min()).split(' ')[0]
                                date_to = str(valid_dates.max()).split(' ')[0]
                                logger.debug(f"  Settlement {settlement_id} date range: {date_from} to {date_to}")
                    except Exception as e:
                        logger.debug(f"  Could not extract date range: {e}")
                    
                    try:
                        if 'total_amount' in settlement_rows.columns:
                            # Simple sum, don't filter
                            amounts = pd.to_numeric(settlement_rows['total_amount'], errors='coerce').fillna(0)
                            bank_deposit = float(amounts.sum())
                    except:
                        bank_deposit = 0.0
                    
                    try:
                        if 'tax_amount' in settlement_rows.columns:
                            tax_amounts = pd.to_numeric(settlement_rows['tax_amount'], errors='coerce').fillna(0)
                            tax_count = int((tax_amounts != 0).sum())
                    except:
                        tax_count = 0
                    
                    # Record in history
                    logger.info(f"Recording history for settlement {settlement_id}")
                    success = tracker.record_settlement_history({
                        'settlement_id': str(settlement_id),
                        'deposit_date': deposit_date,
                        'date_from': date_from,
                        'date_to': date_to,
                        'bank_deposit_amount': float(bank_deposit) if not pd.isna(bank_deposit) else 0.0,
                        'total_records': len(settlement_rows),
                        'journal_line_count': len(formatted_journal) if not formatted_journal.empty else 0,
                        'invoice_line_count': 0,  # Will be calculated if needed
                        'tax_line_count': tax_count,
                        'gl_account_totals': gl_totals
                    })
                    logger.info(f"History recording result for {settlement_id}: {success}")
                
                logger.info("Settlement history recorded for trending analysis")
        except Exception as e:
            import traceback
            logger.warning(f"Could not record settlement history: {e}")
            logger.debug(traceback.format_exc())

        # Run validation per settlement and write validation error reports
        try:
            validator = SettlementValidator()
            journal_df = final_data.get('journal', pd.DataFrame())
            blocked_settlements = set()
            if journal_df is not None and not journal_df.empty and 'settlement_id' in journal_df.columns:
                for settlement_id in journal_df['settlement_id'].astype(str).unique():
                    res = validator.validate_settlement(settlement_id)
                    report_file = validator.write_error_report(settlement_id, res)
                    # If cannot proceed, send alert email and mark as blocked
                    if not res.get('can_proceed', False):
                        blocked_settlements.add(settlement_id)
                        jb = res.get('journal_balance', {})
                        diff = jb.get('difference')
                        err_lines = "\n".join(res.get('errors', []))
                        missing = ", ".join(res.get('missing_gl_accounts', []))
                        subject = f"Amazon ETL BLOCKED - Settlement {settlement_id}"
                        body = (
                            f"Settlement {settlement_id} is blocked.\n\n"
                            f"Journal balanced: {jb.get('balanced')}\n"
                            f"Debits: {jb.get('debits')}  Credits: {jb.get('credits')}  Difference: {diff}\n"
                            f"Unmapped GL: {missing if missing else 'None'}\n\n"
                            f"Errors:\n{err_lines if err_lines else 'None'}\n\n"
                            f"See attached Validation_Errors file."
                        )
                        try:
                            send_email(subject, body, attachments=[report_file])
                        except Exception as e:
                            logger.warning(f"Failed to send alert email: {e}")
        except Exception as e:
            logger.warning(f"Validation step failed: {e}")
        
        # Generate Individual Settlement Summaries
        summary_exported = exporter.generate_settlement_summaries(final_data, settlements_data)
        if summary_exported:
            logger.info("Individual settlement summaries generated successfully")
        
        # Track processed settlements in Entry_Status.csv
        try:
            tracker = EntryTracker()
            # Get unique settlement IDs from the settlements data
            if settlements_data is not None and 'settlement-id' in settlements_data.columns:
                settlement_ids = settlements_data['settlement-id'].unique()
                for settlement_id in settlement_ids:
                    # Get settlement-specific data
                    settlement_rows = settlements_data[settlements_data['settlement-id'] == settlement_id]
                    
                    # Extract deposit date (from deposit-date column, first non-null value)
                    deposit_date = ""
                    if 'deposit-date' in settlement_rows.columns:
                        deposit_dates = settlement_rows['deposit-date'].dropna()
                        if len(deposit_dates) > 0:
                            deposit_date = str(deposit_dates.iloc[0])
                    
                    # Extract deposit amount (sum of all amounts for this settlement)
                    deposit_amount = 0.0
                    if 'amount' in settlement_rows.columns:
                        # Sum all amounts for this settlement
                        amounts = pd.to_numeric(settlement_rows['amount'], errors='coerce')
                        deposit_amount = amounts.sum()
                    
                    tracker.record_processing(
                        str(settlement_id), 
                        deposit_date=deposit_date,
                        deposit_amount=float(deposit_amount),
                        processed_by="ETL Pipeline"
                    )
                logger.info(f"Tracked {len(settlement_ids)} settlement(s) in Entry_Status.csv")
        except Exception as e:
            logger.warning(f"Could not update entry tracking: {e}")
        
        # Organize outputs into settlement-specific folders
        logger.info("Organizing outputs by settlement...")
        organize_outputs_by_settlement(settlements_data, config)
        
        # Sync outputs to SharePoint production location (skip blocked settlements)
        try:
            sharepoint_path = Path("C:/Users/User/Touchstone Brands/BrackishCo - Documents/Sharepoint_Public/Amazon-ETL/2-Processed")
            if sharepoint_path.exists():
                output_path = Path(config['paths']['outputs'])
                logger.info(f"Syncing outputs to SharePoint: {sharepoint_path}")
                
                import shutil
                import time
                # Copy all settlement folders and Dashboard
                for item in output_path.iterdir():
                    dest = sharepoint_path / item.name
                    if item.is_dir():
                        # Skip blocked settlements
                        if 'blocked_settlements' in locals() and item.name in blocked_settlements:
                            logger.info(f"Skipping SharePoint sync for blocked settlement {item.name}")
                            continue
                        # Copy directory recursively, overwriting files (dirs_exist_ok for SharePoint)
                        try:
                            shutil.copytree(item, dest, dirs_exist_ok=True)
                            logger.info(f"  Synced folder: {item.name}")
                        except Exception as e:
                            logger.warning(f"  Could not sync folder {item.name}: {e}")
                    elif item.is_file() and item.suffix in ['.xlsx', '.csv']:
                        # Copy file
                        try:
                            shutil.copy2(item, dest)
                            logger.info(f"  Synced file: {item.name}")
                        except Exception as e:
                            logger.warning(f"  Could not sync file {item.name}: {e}")
                
                logger.info("SharePoint sync completed")
            else:
                logger.warning(f"SharePoint path not found, skipping sync: {sharepoint_path}")
        except Exception as e:
            logger.warning(f"Could not sync to SharePoint: {e}")
        
        logger.info("=== ETL Pipeline Completed Successfully ===")
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"ETL Pipeline failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()