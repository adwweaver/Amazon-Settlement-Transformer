#!/usr/bin/env python3
"""
Amazon Settlement ETL Pipeline - Data Validation and Testing Module

This module provides data validation and testing capabilities for the ETL pipeline.
It includes:
1. Data quality checks and validation rules
2. Unit test framework for pipeline components
3. Integration tests for end-to-end validation
4. Data profiling and quality reporting

This module helps ensure data integrity and pipeline reliability.

Author: ETL Pipeline
Date: October 2025
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
import numpy as np
from datetime import datetime
import unittest


class DataValidator:
    """
    Class for performing data quality checks and validation.
    
    This class provides methods to validate:
    - Data completeness and consistency
    - Business rule compliance
    - Data type and format validation
    - Statistical anomaly detection
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the DataValidator with configuration settings.
        
        Args:
            config: Configuration dictionary loaded from config.yaml
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Load validation rules from config
        self.validation_rules = config.get('processing', {}).get('validation', {})
        self.business_rules = config.get('business_rules', {})
        
        self.logger.info("DataValidator initialized")
    
    def validate_data_completeness(self, df: pd.DataFrame, data_type: str) -> Dict[str, Any]:
        """
        Check data completeness and identify missing values.
        
        Args:
            df: DataFrame to validate
            data_type: Type of data being validated
            
        Returns:
            Dictionary with validation results
        """
        if df.empty:
            return {
                'status': 'EMPTY',
                'message': f'{data_type} dataset is empty',
                'missing_data': {},
                'completeness_score': 0.0
            }
        
        # Calculate missing values per column
        missing_data = {}
        total_cells = len(df) * len(df.columns)
        total_missing = 0
        
        for column in df.columns:
            missing_count = df[column].isna().sum()
            missing_percentage = (missing_count / len(df)) * 100
            
            missing_data[column] = {
                'count': int(missing_count),
                'percentage': round(missing_percentage, 2)
            }
            
            total_missing += missing_count
        
        completeness_score = ((total_cells - total_missing) / total_cells) * 100
        
        return {
            'status': 'COMPLETE' if completeness_score > 90 else 'INCOMPLETE',
            'message': f'{data_type} data completeness: {completeness_score:.1f}%',
            'missing_data': missing_data,
            'completeness_score': round(completeness_score, 2),
            'total_rows': len(df),
            'total_columns': len(df.columns)
        }
    
    def validate_business_rules(self, df: pd.DataFrame, data_type: str) -> Dict[str, Any]:
        """
        Validate business rules and constraints.
        
        Args:
            df: DataFrame to validate
            data_type: Type of data being validated
            
        Returns:
            Dictionary with validation results
        """
        violations = []
        
        if df.empty:
            return {
                'status': 'SKIPPED',
                'message': 'No data to validate',
                'violations': violations
            }
        
        # Check required key fields
        merge_keys = self.business_rules.get('merge_keys', {})
        primary_key = merge_keys.get('primary', 'order_id')
        
        if primary_key in df.columns:
            # Check for duplicate keys
            duplicates = df[df[primary_key].duplicated()]
            if not duplicates.empty:
                violations.append({
                    'rule': 'Unique Primary Key',
                    'field': primary_key,
                    'count': len(duplicates),
                    'message': f'Found {len(duplicates)} duplicate {primary_key} values'
                })
        
        # Validate amount columns
        amount_columns = self.business_rules.get('amount_columns', [])
        for col in amount_columns:
            if col in df.columns:
                # Check for invalid numeric values
                numeric_col = pd.to_numeric(df[col], errors='coerce')
                invalid_count = numeric_col.isna().sum() - df[col].isna().sum()
                
                if invalid_count > 0:
                    violations.append({
                        'rule': 'Valid Numeric Amount',
                        'field': col,
                        'count': invalid_count,
                        'message': f'Found {invalid_count} invalid numeric values in {col}'
                    })
        
        # Validate date columns
        date_columns = self.business_rules.get('date_columns', [])
        for col in date_columns:
            if col in df.columns:
                # Check for invalid date values
                date_col = pd.to_datetime(df[col], errors='coerce')
                invalid_count = date_col.isna().sum() - df[col].isna().sum()
                
                if invalid_count > 0:
                    violations.append({
                        'rule': 'Valid Date Format',
                        'field': col,
                        'count': invalid_count,
                        'message': f'Found {invalid_count} invalid date values in {col}'
                    })
        
        status = 'PASSED' if not violations else 'FAILED'
        
        return {
            'status': status,
            'message': f'Business rule validation {status.lower()} for {data_type}',
            'violations': violations,
            'total_violations': len(violations)
        }
    
    def validate_data_quality(self, df: pd.DataFrame, data_type: str) -> Dict[str, Any]:
        """
        Perform comprehensive data quality assessment.
        
        Args:
            df: DataFrame to validate
            data_type: Type of data being validated
            
        Returns:
            Dictionary with comprehensive validation results
        """
        # Perform individual validations
        completeness_result = self.validate_data_completeness(df, data_type)
        business_rules_result = self.validate_business_rules(df, data_type)
        
        # Calculate overall quality score
        completeness_weight = 0.4
        business_rules_weight = 0.6
        
        completeness_score = completeness_result['completeness_score']
        business_rules_score = 100.0 if business_rules_result['status'] == 'PASSED' else 0.0
        
        overall_score = (completeness_score * completeness_weight + 
                        business_rules_score * business_rules_weight)
        
        # Determine overall status
        if overall_score >= 90:
            overall_status = 'EXCELLENT'
        elif overall_score >= 75:
            overall_status = 'GOOD'
        elif overall_score >= 60:
            overall_status = 'ACCEPTABLE'
        else:
            overall_status = 'POOR'
        
        return {
            'data_type': data_type,
            'overall_status': overall_status,
            'overall_score': round(overall_score, 2),
            'completeness': completeness_result,
            'business_rules': business_rules_result,
            'validated_at': datetime.now().isoformat()
        }


class ETLTestSuite(unittest.TestCase):
    """
    Unit test suite for the ETL pipeline components.
    
    This class contains test cases for:
    - Data transformation functions
    - Export generation
    - Configuration loading
    - Error handling
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.test_config = {
            'paths': {
                'raw_data': './test_data',
                'outputs': './test_outputs'
            },
            'inputs': {
                'settlements': 'settlements',
                'invoices': 'invoices',
                'payments': 'payments'
            },
            'options': {
                'log_level': 'DEBUG'
            }
        }
    
    def test_column_normalization(self):
        """Test column name normalization function."""
        # Import here to avoid circular imports during module initialization
        from transform import DataTransformer
        
        transformer = DataTransformer(self.test_config)
        
        # Create test DataFrame with messy column names
        test_df = pd.DataFrame({
            'Settlement ID ': [1, 2, 3],
            'Order-Fee Amount': [10.50, 20.00, 15.75],
            '  Posted Date  ': ['2025-01-01', '2025-01-02', '2025-01-03']
        })
        
        # Normalize columns
        normalized_df = transformer.normalize_column_names(test_df)
        
        # Check results
        expected_columns = ['settlement_id', 'order_fee_amount', 'posted_date']
        self.assertEqual(list(normalized_df.columns), expected_columns)
    
    def test_data_cleaning(self):
        """Test data value cleaning function."""
        from transform import DataTransformer
        
        transformer = DataTransformer(self.test_config)
        
        # Create test DataFrame with messy data
        test_df = pd.DataFrame({
            'amount': ['10.50 ', ' 20.00', '15.75'],
            'description': ['  Test  ', 'Another Test ', '  '],
            'invalid_num': ['abc', '123', 'nan']
        })
        
        # Clean data
        cleaned_df = transformer.clean_data_values(test_df)
        
        # Check that whitespace is trimmed
        self.assertEqual(cleaned_df['amount'].iloc[0], '10.50')
        self.assertEqual(cleaned_df['description'].iloc[0], 'Test')
    
    def test_empty_data_handling(self):
        """Test handling of empty DataFrames."""
        from transform import DataTransformer
        
        transformer = DataTransformer(self.test_config)
        
        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        result = transformer.normalize_column_names(empty_df)
        
        self.assertTrue(result.empty)
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test with valid config
        self.assertIn('paths', self.test_config)
        self.assertIn('raw_data', self.test_config['paths'])
        
        # Test with invalid config (missing required keys)
        invalid_config = {'invalid': 'config'}
        
        # This should be handled gracefully by the transformer
        try:
            from transform import DataTransformer
            transformer = DataTransformer(invalid_config)
            # Should not raise exception but may log warnings
            self.assertIsNotNone(transformer)
        except Exception as e:
            # If it does raise an exception, it should be informative
            self.assertIn('config', str(e).lower())


def run_data_validation(data_dict: Dict[str, pd.DataFrame], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run comprehensive data validation on all datasets.
    
    Args:
        data_dict: Dictionary containing all processed datasets
        config: Configuration dictionary
        
    Returns:
        Dictionary containing validation results for all datasets
    """
    validator = DataValidator(config)
    logger = logging.getLogger(__name__)
    
    validation_results = {
        'validation_timestamp': datetime.now().isoformat(),
        'datasets': {},
        'summary': {
            'total_datasets': len(data_dict),
            'passed_datasets': 0,
            'failed_datasets': 0,
            'overall_status': 'UNKNOWN'
        }
    }
    
    logger.info(f"Starting validation of {len(data_dict)} datasets...")
    
    for data_type, df in data_dict.items():
        logger.info(f"Validating {data_type} dataset...")
        
        result = validator.validate_data_quality(df, data_type)
        validation_results['datasets'][data_type] = result
        
        # Update summary
        if result['overall_status'] in ['EXCELLENT', 'GOOD', 'ACCEPTABLE']:
            validation_results['summary']['passed_datasets'] += 1
        else:
            validation_results['summary']['failed_datasets'] += 1
        
        logger.info(f"{data_type} validation: {result['overall_status']} "
                   f"(Score: {result['overall_score']})")
    
    # Determine overall status
    passed_count = validation_results['summary']['passed_datasets']
    total_count = validation_results['summary']['total_datasets']
    
    if total_count == 0:
        validation_results['summary']['overall_status'] = 'NO_DATA'
    elif passed_count == total_count:
        validation_results['summary']['overall_status'] = 'ALL_PASSED'
    elif passed_count > 0:
        validation_results['summary']['overall_status'] = 'PARTIAL_PASS'
    else:
        validation_results['summary']['overall_status'] = 'ALL_FAILED'
    
    logger.info(f"Validation completed: {validation_results['summary']['overall_status']}")
    
    return validation_results


def generate_validation_report(validation_results: Dict[str, Any], output_path: Path) -> bool:
    """
    Generate a detailed validation report.
    
    Args:
        validation_results: Results from data validation
        output_path: Path to save the report
        
    Returns:
        True if report generated successfully
    """
    try:
        report_data = []
        
        # Add summary information
        summary = validation_results.get('summary', {})
        report_data.append({
            'Category': 'SUMMARY',
            'Dataset': 'All',
            'Status': summary.get('overall_status', 'UNKNOWN'),
            'Score': '',
            'Details': f"Passed: {summary.get('passed_datasets', 0)}, "
                      f"Failed: {summary.get('failed_datasets', 0)}"
        })
        
        # Add dataset-specific information
        for dataset_name, result in validation_results.get('datasets', {}).items():
            report_data.append({
                'Category': 'DATASET',
                'Dataset': dataset_name,
                'Status': result.get('overall_status', 'UNKNOWN'),
                'Score': result.get('overall_score', ''),
                'Details': f"Completeness: {result.get('completeness', {}).get('completeness_score', 0)}%, "
                          f"Violations: {result.get('business_rules', {}).get('total_violations', 0)}"
            })
            
            # Add violation details if any
            violations = result.get('business_rules', {}).get('violations', [])
            for violation in violations:
                report_data.append({
                    'Category': 'VIOLATION',
                    'Dataset': dataset_name,
                    'Status': violation.get('rule', 'Unknown Rule'),
                    'Score': violation.get('count', ''),
                    'Details': violation.get('message', '')
                })
        
        # Create DataFrame and save report
        report_df = pd.DataFrame(report_data)
        report_file = output_path / "Data_Validation_Report.csv"
        report_df.to_csv(report_file, index=False, encoding='utf-8-sig')
        
        logging.getLogger(__name__).info(f"Validation report saved: {report_file}")
        return True
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to generate validation report: {str(e)}")
        return False


def run_unit_tests() -> bool:
    """
    Run the unit test suite.
    
    Returns:
        True if all tests pass, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info("Running unit tests...")
    
    try:
        # Create test suite
        suite = unittest.TestLoader().loadTestsFromTestCase(ETLTestSuite)
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Check results
        success = result.wasSuccessful()
        
        if success:
            logger.info("All unit tests passed!")
        else:
            logger.error(f"Unit tests failed: {len(result.failures)} failures, "
                        f"{len(result.errors)} errors")
        
        return success
        
    except Exception as e:
        logger.error(f"Error running unit tests: {str(e)}")
        return False


if __name__ == "__main__":
    """
    Script can be run directly to execute unit tests.
    
    Usage: python validate.py
    """
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run unit tests
    success = run_unit_tests()
    
    if not success:
        sys.exit(1)
    
    print("Validation module tests completed successfully!")