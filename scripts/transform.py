#!/usr/bin/env python3
"""
Amazon Settlement ETL Pipeline - Data Transformation Module

This module handles all data transformation operations including:
1. Reading raw data files from various sources
2. Cleaning and normalizing column names and data
3. Applying business logic transformations
4. Merging data from multiple sources
5. Preparing data for export

The transformations replicate the M Code behavior from Power Query
but use pandas for better performance and maintainability.

Author: ETL Pipeline
Date: October 2025
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np
from datetime import datetime


class DataTransformer:
    """
    Main class for handling all data transformation operations.
    
    This class encapsulates all the logic needed to:
    - Read raw data files
    - Clean and normalize data
    - Apply business transformations
    - Merge data from multiple sources
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the DataTransformer with configuration settings.
        
        Args:
            config: Configuration dictionary loaded from config.yaml
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Set up paths
        self.raw_data_path = Path(config['paths']['raw_data'])
        self.settlements_path = self.raw_data_path / config['inputs']['settlements']
        self.invoices_path = self.raw_data_path / config['inputs']['invoices']
        self.payments_path = self.raw_data_path / config['inputs']['payments']
        
        self.logger.info("DataTransformer initialized")
    
    def normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to follow consistent naming conventions.
        
        This function:
        1. Converts to lowercase
        2. Replaces spaces with underscores
        3. Removes special characters except underscores and hyphens
        4. Trims whitespace
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with normalized column names
        """
        if df.empty:
            return df
            
        # Create a copy to avoid modifying original
        normalized_df = df.copy()
        
        # Normalize column names
        new_columns = []
        for col in normalized_df.columns:
            # Convert to string and strip whitespace
            normalized_col = str(col).strip()
            
            # Convert to lowercase
            normalized_col = normalized_col.lower()
            
            # Replace spaces, hyphens, and special characters with underscores
            normalized_col = re.sub(r'[^\w]', '_', normalized_col)
            
            # Remove multiple consecutive underscores
            normalized_col = re.sub(r'_+', '_', normalized_col)
            
            # Remove leading/trailing underscores
            normalized_col = normalized_col.strip('_')
            
            new_columns.append(normalized_col)
        
        normalized_df.columns = new_columns
        
        self.logger.debug(f"Column names normalized: {dict(zip(df.columns, new_columns))}")
        return normalized_df
    
    def clean_data_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize data values in the DataFrame.
        
        This function:
        1. Trims whitespace from string columns
        2. Standardizes date formats
        3. Handles numeric data cleaning
        4. Removes or replaces invalid values
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with cleaned data values
        """
        if df.empty:
            return df
            
        cleaned_df = df.copy()
        
        # Clean string columns: trim whitespace
        string_columns = cleaned_df.select_dtypes(include=['object']).columns
        for col in string_columns:
            cleaned_df[col] = cleaned_df[col].astype(str).str.strip()
            # Replace 'nan' strings with actual NaN
            cleaned_df[col] = cleaned_df[col].replace('nan', np.nan)
        
        # Clean numeric columns: handle invalid values
        numeric_columns = cleaned_df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            # Replace inf and -inf with NaN
            cleaned_df[col] = cleaned_df[col].replace([np.inf, -np.inf], np.nan)
        
        self.logger.debug(f"Data values cleaned for {len(cleaned_df)} rows")
        return cleaned_df
    
    def read_data_files(self, folder_path: Path, file_pattern: str = "*.txt") -> Optional[pd.DataFrame]:
        """
        Read all data files from a specified folder and combine them.
        
        Args:
            folder_path: Path to the folder containing data files
            file_pattern: Pattern to match files (default: *.txt)
            
        Returns:
            Combined DataFrame or None if no files found
        """
        if not folder_path.exists():
            self.logger.warning(f"Folder not found: {folder_path}")
            return None
        
        # Find all matching files
        data_files = list(folder_path.glob(file_pattern))
        
        if not data_files:
            self.logger.warning(f"No {file_pattern} files found in {folder_path}")
            return None
        
        self.logger.info(f"Found {len(data_files)} files in {folder_path}")
        
        # Read and combine all files
        dataframes = []
        for file_path in data_files:
            try:
                self.logger.debug(f"Reading file: {file_path}")
                
                # Try to detect delimiter (tab or comma)
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                
                # Determine delimiter based on first line
                if '\t' in first_line:
                    delimiter = '\t'
                elif ',' in first_line:
                    delimiter = ','
                else:
                    delimiter = '\t'  # default to tab
                
                # Read the file
                df = pd.read_csv(file_path, delimiter=delimiter, dtype=str)
                
                # Add source file information
                df['source_file'] = file_path.name
                
                dataframes.append(df)
                self.logger.debug(f"Successfully read {len(df)} rows from {file_path.name}")
                
            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {str(e)}")
                continue
        
        if not dataframes:
            self.logger.warning("No data files could be read successfully")
            return None
        
        # Combine all dataframes
        combined_df = pd.concat(dataframes, ignore_index=True)
        self.logger.info(f"Combined {len(dataframes)} files into {len(combined_df)} total rows")
        
        return combined_df
    
    def process_settlements(self) -> Optional[pd.DataFrame]:
        """
        Process settlement data files.
        
        Returns:
            Processed settlements DataFrame or None if no data
        """
        self.logger.info("Processing settlement data...")
        
        # Read raw settlement files
        raw_data = self.read_data_files(self.settlements_path)
        
        if raw_data is None or raw_data.empty:
            self.logger.warning("No settlement data to process")
            return None
        
        # Apply transformations
        processed_data = self.normalize_column_names(raw_data)
        processed_data = self.clean_data_values(processed_data)
        
        # Add data source identifier
        processed_data['data_source'] = 'settlements'
        
        # Apply settlement-specific transformations
        processed_data = self._apply_settlement_transformations(processed_data)
        
        self.logger.info(f"Settlement processing completed: {len(processed_data)} records")
        return processed_data
    
    def process_invoices(self) -> Optional[pd.DataFrame]:
        """
        Process invoice data files.
        
        Returns:
            Processed invoices DataFrame or None if no data
        """
        self.logger.info("Processing invoice data...")
        
        # Read raw invoice files
        raw_data = self.read_data_files(self.invoices_path)
        
        if raw_data is None or raw_data.empty:
            self.logger.warning("No invoice data to process")
            return None
        
        # Apply transformations
        processed_data = self.normalize_column_names(raw_data)
        processed_data = self.clean_data_values(processed_data)
        
        # Add data source identifier
        processed_data['data_source'] = 'invoices'
        
        # Apply invoice-specific transformations
        processed_data = self._apply_invoice_transformations(processed_data)
        
        self.logger.info(f"Invoice processing completed: {len(processed_data)} records")
        return processed_data
    
    def process_payments(self) -> Optional[pd.DataFrame]:
        """
        Process payment data files.
        
        Returns:
            Processed payments DataFrame or None if no data
        """
        self.logger.info("Processing payment data...")
        
        # Read raw payment files
        raw_data = self.read_data_files(self.payments_path)
        
        if raw_data is None or raw_data.empty:
            self.logger.warning("No payment data to process")
            return None
        
        # Apply transformations
        processed_data = self.normalize_column_names(raw_data)
        processed_data = self.clean_data_values(processed_data)
        
        # Add data source identifier
        processed_data['data_source'] = 'payments'
        
        # Apply payment-specific transformations
        processed_data = self._apply_payment_transformations(processed_data)
        
        self.logger.info(f"Payment processing completed: {len(processed_data)} records")
        return processed_data
    
    def _apply_settlement_transformations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply settlement-specific business logic transformations.
        Based on SettlementSummary_Base.m logic.
        
        Args:
            df: Settlement DataFrame
            
        Returns:
            Transformed DataFrame with full business logic applied
        """
        if df.empty:
            return df
            
        self.logger.info("Applying SettlementSummary_Base transformations...")
        self.logger.debug(f"Available columns: {list(df.columns)}")
        transformed_df = df.copy()
        
        # Step 1: Add row_id index (like M Code line 35)
        transformed_df = transformed_df.reset_index(drop=True)
        transformed_df['row_id'] = transformed_df.index + 1
        
        # Step 1.5: Add line_count field (original line count before any journal splits)
        transformed_df['line_count'] = 1
        
        # Step 2: Add item_price_lookup key (like M Code lines 37-54)
        transformed_df['item_price_lookup'] = transformed_df.apply(
            self._create_item_price_lookup, axis=1
        )
        
        # Step 3: Convert financial columns using the M Code asNum logic
        financial_columns = [
            'total_amount', 'quantity_purchased', 'price_amount', 
            'shipment_fee_amount', 'order_fee_amount', 'item_related_fee_amount',
            'misc_fee_amount', 'other_fee_amount', 'direct_payment_amount', 
            'other_amount', 'promotion_amount'
        ]
        
        for col in financial_columns:
            if col in transformed_df.columns:
                transformed_df[col] = transformed_df[col].apply(self._parse_amount)
        
        # Step 4: Calculate MinRowID for each settlement_id (like M Code lines 163-171)
        if 'settlement_id' in transformed_df.columns:
            min_row_lookup = transformed_df.groupby('settlement_id')['row_id'].min().to_dict()
            transformed_df['MinRowID'] = transformed_df['settlement_id'].map(min_row_lookup)
        else:
            self.logger.warning("settlement_id column not found, using row_id as MinRowID")
            transformed_df['MinRowID'] = transformed_df['row_id']
        
        # Step 5: Calculate transaction_amount (like M Code lines 178-190)
        transformed_df['transaction_amount'] = transformed_df.apply(
            self._calculate_transaction_amount, axis=1
        )
        
        # Step 6: Add tax_amount (like M Code lines 193-198)
        transformed_df['tax_amount'] = transformed_df.apply(
            self._calculate_tax_amount, axis=1
        )
        
        # Step 7: Generate price lookup data (PriceLookup_CasePrice logic)
        self.price_lookup_data = self._create_price_lookup_table(transformed_df)
        
        self.logger.info(f"Settlement transformations completed: {len(transformed_df)} rows processed")
        return transformed_df
    
    def _create_price_lookup_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create price lookup table based on PriceLookup_CasePrice.m logic.
        
        Args:
            df: Settlement DataFrame
            
        Returns:
            Price lookup DataFrame with case_price_amount calculations
        """
        if df.empty:
            return pd.DataFrame()
            
        self.logger.info("Creating price lookup table...")
        
        # Step 1: Add price_amount_line (M Code lines 13-32)
        lookup_df = df.copy()
        lookup_df['price_amount_line'] = lookup_df.apply(self._calculate_price_amount_line, axis=1)
        
        # Step 2: Filter valid lookup rows (M Code lines 34-37)
        filtered_df = lookup_df[
            (lookup_df['item_price_lookup'] != '') & 
            (
                (lookup_df['price_amount_line'] != 0) | 
                ((lookup_df['quantity_purchased'].notna()) & (lookup_df['quantity_purchased'] != 0))
            )
        ]
        
        if filtered_df.empty:
            self.logger.warning("No valid price lookup data found")
            return pd.DataFrame()
        
        # Step 3: Group by item_price_lookup (M Code lines 39-43)
        grouped = filtered_df.groupby('item_price_lookup').agg({
            'price_amount_line': 'max',  # MAX(price_amount_line) 
            'quantity_purchased': 'max'  # MAX(quantity_purchased)
        }).reset_index()
        
        grouped.rename(columns={'price_amount_line': 'total_price_amount'}, inplace=True)
        
        # Step 4: Filter non-zero values (M Code lines 45-49)
        cleaned_lookup = grouped[
            (grouped['total_price_amount'] != 0) & 
            (grouped['quantity_purchased'].notna()) & 
            (grouped['quantity_purchased'] != 0)
        ].copy()
        
        # Step 5: Calculate case_price_amount (M Code lines 51-54)
        if not cleaned_lookup.empty:
            cleaned_lookup['case_price_amount'] = (
                cleaned_lookup['total_price_amount'] / cleaned_lookup['quantity_purchased']
            )
            
            self.logger.info(f"Price lookup table created: {len(cleaned_lookup)} entries")
            return cleaned_lookup[['item_price_lookup', 'total_price_amount', 'quantity_purchased', 'case_price_amount']]
        else:
            # Return empty DataFrame with expected columns
            self.logger.warning("No valid price lookup data found")
            return pd.DataFrame(columns=['item_price_lookup', 'total_price_amount', 'quantity_purchased', 'case_price_amount'])
    
    def _calculate_price_amount_line(self, row: pd.Series) -> float:
        """
        Calculate price_amount_line based on M Code logic (lines 13-32).
        """
        price_type = str(row.get('price_type', '')).lower().strip()
        txn_type = str(row.get('transaction_type', '')).upper().strip()
        original_qty = row.get('quantity_purchased', 0)
        
        # SCENARIO 1: Damages/Reversals where quantity is present
        if (txn_type in ['WAREHOUSE DAMAGE', 'REVERSAL_REIMBURSEMENT']) and original_qty > 0:
            return row.get('other_amount', 0)
        
        # SCENARIO 2: Principal sale price
        elif price_type == 'principal':
            return row.get('price_amount', 0)
        
        # SCENARIO 3: None of the above
        else:
            return 0.0
    
    def _create_item_price_lookup(self, row: pd.Series) -> str:
        """
        Create item_price_lookup key based on M Code logic.
        Create lookup keys for ALL rows that have the necessary data (order_id, sku, etc.)
        so that invoice rows can match to their corresponding principal pricing rows.
        """
        order_id = str(row.get('order_id', '')).strip()
        sku = str(row.get('sku', '')).strip()
        settlement_id = str(row.get('settlement_id', '')).strip()
        transaction_type = str(row.get('transaction_type', '')).strip().lower()
        
        # Skip rows that don't have enough data to create a meaningful lookup key
        if not sku or sku.lower() in ['', 'nan', 'null']:
            return ''
        
        # Parse posted_date to ddMMyyyy format
        try:
            posted_date = pd.to_datetime(row.get('posted_date'), errors='coerce')
            if pd.isna(posted_date):
                posted_date_str = '01011900'
            else:
                posted_date_str = posted_date.strftime('%d%m%Y')
        except:
            posted_date_str = '01011900'
        
        # Apply M Code conditional logic - same for all rows
        if order_id == '' or pd.isna(order_id) or order_id.lower() == 'nan':
            return f"{settlement_id}{posted_date_str}{transaction_type}"
        else:
            # Take last 7 characters of order_id + sku
            order_suffix = order_id[-7:] if len(order_id) >= 7 else order_id
            return f"{order_suffix}{sku}"
    
    def _parse_amount(self, value) -> float:
        """
        Parse amount values using M Code asNum logic.
        Handles various formats: "$1,234.56", "(123.45)", "1.234,56", etc.
        """
        if pd.isna(value) or value == "" or str(value).strip() == "":
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        try:
            # Convert to string and clean
            text = str(value).strip()
            
            # Remove commas
            text = text.replace(',', '')
            
            # Handle parentheses (negative numbers)
            if text.startswith('(') and text.endswith(')'):
                text = '-' + text[1:-1]
            
            # Remove currency symbols
            text = text.replace('$', '').replace('€', '').replace('£', '')
            
            # Try parsing as US format first, then German format
            try:
                return float(text)
            except ValueError:
                # Try German format (1.234,56 -> 1234.56)
                if '.' in text and ',' in text:
                    # Assume German format: thousands separator = ., decimal = ,
                    text = text.replace('.', '').replace(',', '.')
                elif ',' in text and text.count(',') == 1:
                    # Single comma might be decimal separator
                    text = text.replace(',', '.')
                return float(text)
                
        except (ValueError, TypeError):
            self.logger.warning(f"Failed to parse amount: {value}")
            return 0.0
    
    def _calculate_transaction_amount(self, row: pd.Series) -> float:
        """
        Calculate transaction_amount using M Code logic (lines 178-190).
        """
        # Sum of all fee components
        normal_sum = (
            row.get('price_amount', 0) +
            row.get('shipment_fee_amount', 0) +
            row.get('order_fee_amount', 0) +
            row.get('item_related_fee_amount', 0) +
            row.get('misc_fee_amount', 0) +
            row.get('other_fee_amount', 0) +
            row.get('direct_payment_amount', 0) +
            row.get('other_amount', 0) +
            row.get('promotion_amount', 0)
        )
        
        # Add total_amount adjustment only for first row of each settlement
        is_first_row = row.get('row_id') == row.get('MinRowID')
        total_amount_adj = -row.get('total_amount', 0) if is_first_row else 0
        
        return normal_sum + total_amount_adj
    
    def _calculate_tax_amount(self, row: pd.Series) -> float:
        """
        Calculate tax_amount using M Code logic (lines 193-198).
        """
        other_fee_reason = str(row.get('other_fee_reason_description', '')).lower().strip()
        
        if other_fee_reason == 'taxamount':
            return row.get('other_fee_amount', 0)
        else:
            return 0.0
    
    def _apply_invoice_transformations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply invoice-specific business logic transformations.
        
        Args:
            df: Invoice DataFrame
            
        Returns:
            Transformed DataFrame
        """
        if df.empty:
            return df
            
        transformed_df = df.copy()
        
        # Apply invoice-specific logic here
        # This is a placeholder for actual business logic
        
        self.logger.debug("Invoice-specific transformations applied")
        return transformed_df
    
    def _apply_payment_transformations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply payment-specific business logic transformations.
        
        Args:
            df: Payment DataFrame
            
        Returns:
            Transformed DataFrame
        """
        if df.empty:
            return df
            
        transformed_df = df.copy()
        
        # Apply payment-specific logic here
        # This is a placeholder for actual business logic
        
        self.logger.debug("Payment-specific transformations applied")
        return transformed_df
    
    def merge_and_finalize(
        self, 
        settlements: Optional[pd.DataFrame], 
        invoices: Optional[pd.DataFrame], 
        payments: Optional[pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        Merge data from multiple sources and prepare final datasets.
        
        Args:
            settlements: Processed settlements DataFrame
            invoices: Processed invoices DataFrame
            payments: Processed payments DataFrame
            
        Returns:
            Dictionary containing final datasets for each export type
        """
        self.logger.info("Merging and finalizing datasets...")
        
        final_data = {
            'journal': pd.DataFrame(),
            'invoice': pd.DataFrame(),
            'payment': pd.DataFrame()
        }
        
        # Start with settlements as the base dataset if available
        base_data = settlements if settlements is not None else pd.DataFrame()
        
        # Merge with invoices if available
        if invoices is not None and not invoices.empty:
            if not base_data.empty and 'order_id' in base_data.columns and 'order_id' in invoices.columns:
                base_data = base_data.merge(
                    invoices, 
                    on='order_id', 
                    how='outer', 
                    suffixes=('_settlement', '_invoice')
                )
                self.logger.info("Merged settlements with invoices")
            else:
                base_data = pd.concat([base_data, invoices], ignore_index=True)
                self.logger.info("Concatenated settlements and invoices")
        
        # Merge with payments if available
        if payments is not None and not payments.empty:
            if not base_data.empty and 'order_id' in base_data.columns and 'order_id' in payments.columns:
                base_data = base_data.merge(
                    payments, 
                    on='order_id', 
                    how='outer', 
                    suffixes=('', '_payment')
                )
                self.logger.info("Merged with payments")
            else:
                base_data = pd.concat([base_data, payments], ignore_index=True)
                self.logger.info("Concatenated with payments")
        
        # Prepare specific datasets for each export
        if not base_data.empty:
            # Journal Export: All financial transactions
            final_data['journal'] = self._prepare_journal_data(base_data)
            
            # Invoice Export: Invoice-related data
            final_data['invoice'] = self._prepare_invoice_data(base_data)
            
            # Payment Export: Payment-related data
            final_data['payment'] = self._prepare_payment_data(base_data)
        
        self.logger.info(f"Final datasets prepared - Journal: {len(final_data['journal'])}, "
                        f"Invoice: {len(final_data['invoice'])}, Payment: {len(final_data['payment'])}")
        
        return final_data
    
    def _prepare_journal_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data specifically for the Journal Export.
        
        Args:
            df: Combined DataFrame
            
        Returns:
            DataFrame formatted for journal export
        """
        if df.empty:
            return df
            
        journal_df = df.copy()
        
        # Select and rename columns for journal export (include all M Code calculated fields)
        journal_columns = [
            'settlement_id', 'order_id', 'merchant_order_id', 'transaction_type', 
            'posted_date', 'deposit_date', 'total_amount', 'currency',
            'transaction_amount', 'tax_amount', 'row_id', 'item_price_lookup',
            'shipment_fee_type', 'order_fee_type', 'item_related_fee_type',
            'other_fee_reason_description', 'promotion_type', 'price_type',
            'marketplace_name', 'sku', 'quantity_purchased', 'price_amount',
            'data_source', 'source_file'
        ]
        
        # Keep only columns that exist
        available_columns = [col for col in journal_columns if col in journal_df.columns]
        journal_df = journal_df[available_columns]
        
        # Sort by date if available
        if 'posted_date' in journal_df.columns:
            journal_df = journal_df.sort_values('posted_date')
        
        return journal_df
    
    def _prepare_invoice_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data specifically for the Invoice Export.
        
        NOTE: In the M Code, InvoiceExport uses SettlementSummary data,
        not separate invoice files. So we pass through all settlement data.
        
        Args:
            df: Combined DataFrame (SettlementSummary)
            
        Returns:
            DataFrame formatted for invoice export (all settlement data)
        """
        if df.empty:
            return df
            
        # InvoiceExport.m uses SettlementSummary data, so return settlement data
        invoice_df = df[df['data_source'] == 'settlements'].copy() if 'data_source' in df.columns else df.copy()
        
        return invoice_df
    
    def _prepare_payment_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data specifically for the Payment Export.
        
        NOTE: In the M Code, PaymentExport uses SettlementSummary data,
        not separate payment files. So we pass through all settlement data.
        
        Args:
            df: Combined DataFrame (SettlementSummary)
            
        Returns:
            DataFrame formatted for payment export (all settlement data)
        """
        if df.empty:
            return df
            
        # PaymentExport.m uses SettlementSummary data, so return settlement data
        payment_df = df[df['data_source'] == 'settlements'].copy() if 'data_source' in df.columns else df.copy()
        
        return payment_df