"""
Zoho Books Integration Module
Syncs Amazon settlement data to Zoho Books with duplicate prevention
"""

import yaml
import requests
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ZohoBooks:
    """Interface for Zoho Books API with Canada data center support"""
    
    def __init__(self, config_file: str = None):
        """Initialize Zoho Books API client"""
        if config_file is None:
            config_file = Path(__file__).parent.parent / 'config' / 'zoho_credentials.yaml'
        
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Load GL account mapping
        mapping_file = Path(__file__).parent.parent / 'config' / 'zoho_gl_mapping.yaml'
        with open(mapping_file, 'r') as f:
            mapping_config = yaml.safe_load(f)
            self.gl_mapping = mapping_config['gl_account_mapping']
        
        self.access_token = None
        self.token_expiry = None
        
        # Initialize transaction log
        self._init_transaction_log()
        
        logger.info(f"Zoho Books client initialized for {self.config['data_center']} data center")
    
    def _init_transaction_log(self):
        """Initialize transaction log file with header if it doesn't exist"""
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / 'zoho_api_transactions.log'
        
        if not log_file.exists():
            header = "timestamp|method|type|endpoint|reference|amount|status|http_code|transaction_id\n"
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(header)
            logger.info("Created new Zoho API transaction log file")
    
    def _refresh_access_token(self) -> str:
        """Get a fresh access token using refresh token"""
        accounts_server = self.config.get('accounts_server', 'https://accounts.zoho.com')
        token_url = f"{accounts_server}/oauth/v2/token"
        
        token_params = {
            "refresh_token": self.config['refresh_token'],
            "client_id": self.config['client_id'],
            "client_secret": self.config['client_secret'],
            "grant_type": "refresh_token"
        }
        
        response = requests.post(token_url, data=token_params)
        token_data = response.json()
        
        if 'access_token' not in token_data:
            raise Exception(f"Token refresh failed: {token_data}")
        
        self.access_token = token_data['access_token']
        self.token_expiry = datetime.now().timestamp() + token_data['expires_in']
        
        logger.debug("Access token refreshed")
        return self.access_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers with fresh access token"""
        # Refresh token if expired or not set
        if not self.access_token or datetime.now().timestamp() >= self.token_expiry:
            self._refresh_access_token()
        
        return {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def _api_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make API request with error handling"""
        # Remove leading slash if present
        endpoint = endpoint.lstrip('/')
        
        url = f"{self.config['api_endpoint']}/{endpoint}"
        params = {"organization_id": self.config['organization_id']}
        
        logger.debug(f"API {method} request to: {url}")
        
        headers = self._get_headers()
        
        # Log transaction details to dedicated file
        self._log_transaction(method, endpoint, data)
        
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, params=params, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, params=params, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, params=params)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        try:
            result = response.json()
        except Exception:
            # If response is not JSON, create a basic error result
            result = {
                'code': response.status_code,
                'message': f'HTTP {response.status_code}: {response.text[:200]}'
            }
        
        logger.debug(f"API response: {json.dumps(result, indent=2)}")
        
        # Log response to transaction log
        self._log_transaction_response(method, endpoint, result, response.status_code)
        
        # For payment creation, we want to handle errors in the calling method
        # so we return the result even for non-200 status codes
        if response.status_code != 200 and response.status_code != 201:
            logger.warning(f"API request returned non-200 status: {response.status_code}")
            logger.warning(f"Response: {json.dumps(result, indent=2)}")
            # Don't raise exception - let caller handle based on result['code']
            # This allows us to check result.get('code') in create_payment()
        
        return result
    
    def _log_transaction(self, method: str, endpoint: str, data: Dict = None):
        """Log API transaction details to dedicated file"""
        import os
        from pathlib import Path
        
        # Create transaction log directory if it doesn't exist
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        # Transaction log file
        log_file = log_dir / 'zoho_api_transactions.log'
        
        timestamp = datetime.now().isoformat()
        
        # Extract key info from endpoint
        transaction_type = 'UNKNOWN'
        if 'journals' in endpoint:
            transaction_type = 'JOURNAL'
        elif 'invoices' in endpoint:
            transaction_type = 'INVOICE'
        elif 'customerpayments' in endpoint:
            transaction_type = 'PAYMENT'
        elif 'contacts' in endpoint:
            transaction_type = 'CONTACT'
        elif 'items' in endpoint:
            transaction_type = 'ITEM'
        
        # Extract settlement ID or reference from data if available
        reference = 'N/A'
        if data:
            if 'reference_number' in data:
                reference = data['reference_number']
            elif 'invoice_number' in data:
                reference = data['invoice_number']
            elif 'payment_number' in data:
                reference = data['payment_number']
        
        # Calculate amount if available
        amount = 'N/A'
        if data and 'line_items' in data:
            total = 0
            for item in data['line_items']:
                if item.get('debit_or_credit') == 'debit':
                    total += item.get('amount', 0)
                elif item.get('debit_or_credit') == 'credit':
                    total -= item.get('amount', 0)
            if total != 0:
                amount = f"${abs(total):.2f}"
        elif data and 'total' in data:
            amount = f"${data['total']:.2f}"
        
        log_entry = f"{timestamp}|{method}|{transaction_type}|{endpoint}|{reference}|{amount}"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    
    def _log_transaction_response(self, method: str, endpoint: str, result: Dict, status_code: int):
        """Log API response details"""
        import os
        from pathlib import Path
        
        log_dir = Path(__file__).parent.parent / 'logs'
        log_file = log_dir / 'zoho_api_transactions.log'
        
        # Extract transaction ID from response if successful
        transaction_id = 'N/A'
        if result.get('code') == 0:
            if 'journal' in result:
                transaction_id = result['journal'].get('journal_id', 'N/A')
            elif 'invoice' in result:
                transaction_id = result['invoice'].get('invoice_id', 'N/A')
            elif 'payment' in result:
                transaction_id = result['payment'].get('payment_id', 'N/A')
        
        success = 'SUCCESS' if status_code in [200, 201] else 'FAILED'
        
        # Append response to last log entry
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if lines:
                # Update last line with response info
                last_line = lines[-1].strip()
                updated_line = f"{last_line}|{success}|{status_code}|{transaction_id}"
                
                # Rewrite file with updated last line
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[:-1])
                    f.write(updated_line + '\n')
        except Exception as e:
            logger.warning(f"Failed to update transaction log: {e}")
    
    def _log_payment_error(self, payment_data: Dict, result: Dict, error_code: int, error_msg: str):
        """Log payment error details to a dedicated error log file"""
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        error_log_file = log_dir / 'payment_errors.log'
        
        timestamp = datetime.now().isoformat()
        error_entry = {
            'timestamp': timestamp,
            'error_code': error_code,
            'error_message': error_msg,
            'payment_data': payment_data,
            'zoho_response': result
        }
        
        try:
            with open(error_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(error_entry, indent=2) + '\n' + '='*80 + '\n')
        except Exception as e:
            logger.warning(f"Failed to write payment error log: {e}")
    
    def get_transaction_history(self, limit: int = 50) -> List[Dict]:
        """Get recent transaction history from log file"""
        log_dir = Path(__file__).parent.parent / 'logs'
        log_file = log_dir / 'zoho_api_transactions.log'
        
        if not log_file.exists():
            return []
        
        transactions = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Skip header
            for line in lines[1:][-limit:]:  # Get last 'limit' entries
                parts = line.strip().split('|')
                if len(parts) >= 9:
                    transaction = {
                        'timestamp': parts[0],
                        'method': parts[1],
                        'type': parts[2],
                        'endpoint': parts[3],
                        'reference': parts[4],
                        'amount': parts[5],
                        'status': parts[6],
                        'http_code': parts[7],
                        'transaction_id': parts[8]
                    }
                    transactions.append(transaction)
        except Exception as e:
            logger.error(f"Error reading transaction log: {e}")
        
        return transactions
    
    def check_existing_journal(self, settlement_id: str) -> Optional[str]:
        """Check if journal entry already exists for this settlement"""
        try:
            # Search by reference number with pagination
            page = 1
            per_page = 200
            
            while True:
                result = self._api_request('GET', f'journals?page={page}&per_page={per_page}')
                
                if result.get('code') == 0:
                    journals = result.get('journals', [])
                    
                    # Check this page for matching reference number
                    for journal in journals:
                        if journal.get('reference_number') == settlement_id:
                            journal_id = journal['journal_id']
                            logger.warning(f"Settlement {settlement_id} already exists in Zoho (ID: {journal_id})")
                            return journal_id
                    
                    # Check if there are more pages
                    page_context = result.get('page_context', {})
                    if not page_context.get('has_more_page', False):
                        break
                    
                    page += 1
                else:
                    logger.error(f"Failed to check journals: {result}")
                    break
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking existing journal: {e}")
            # Don't fail - just continue (better to try posting and catch duplicate error)
            return None
    
    def create_journal_entry(self, settlement_id: str, journal_data, 
                           dry_run: bool = True, individual_lines: bool = False,
                           reference_number: Optional[str] = None, force: bool = False) -> Optional[str]:
        """
        Create journal entry in Zoho Books
        
        Args:
            settlement_id: Amazon settlement ID
            journal_data: DataFrame OR Dict with journal entry details
            dry_run: If True, only log what would be posted (no actual API call)
            individual_lines: If True, post each DataFrame row separately
        
        Returns:
            Journal entry ID if successful, None if failed
        """
        # Check for duplicates first unless force
        if not force:
            existing_id = self.check_existing_journal(settlement_id)
            if existing_id:
                logger.info(f"Skipping duplicate settlement {settlement_id}")
                return existing_id
        
        # Build journal entry payload
        line_items = []
        
        # Check if journal_data is a DataFrame
        import pandas as pd
        if isinstance(journal_data, pd.DataFrame) and individual_lines:
            # Post each row as separate line item
            logger.debug(f"Processing {len(journal_data)} individual transactions")
            for idx, row in journal_data.iterrows():
                account_name = row['GL_Account']
                
                # Get Zoho account ID from mapping
                account_id = self.gl_mapping.get(account_name)
                if not account_id:
                    logger.warning(f"No mapping for account: {account_name}")
                    continue
                
                # Normalize debit/credit: ensure positive amounts on the correct side
                raw_debit = float(row.get('Debit', 0) or 0)
                raw_credit = float(row.get('Credit', 0) or 0)
                debit = 0.0
                credit = 0.0
                if raw_debit > 0 and raw_credit == 0:
                    debit = raw_debit
                elif raw_credit > 0 and raw_debit == 0:
                    credit = raw_credit
                elif raw_debit < 0 and raw_credit == 0:
                    credit = abs(raw_debit)
                elif raw_credit < 0 and raw_debit == 0:
                    debit = abs(raw_credit)
                elif raw_debit == 0 and raw_credit == 0:
                    # Skip zero line
                    continue
                else:
                    # If both have values (shouldn't), net them safely
                    net = raw_debit - raw_credit
                    if net > 0:
                        debit = net
                    elif net < 0:
                        credit = abs(net)
                    else:
                        continue
                
                # Create line item with description
                description = str(row.get('Description', ''))
                
                if debit > 0:
                    line_items.append({
                        "account_id": account_id,
                        "debit_or_credit": "debit",
                        "amount": debit,
                        "description": description
                    })
                if credit > 0:
                    line_items.append({
                        "account_id": account_id,
                        "debit_or_credit": "credit",
                        "amount": credit,
                        "description": description
                    })
            
            # Get date and notes
            journal_date = journal_data['Date'].iloc[0]
            notes = f"Amazon Settlement {settlement_id} - {len(journal_data)} transactions"
        
        else:
            # Aggregated mode - journal_data is a dict
            for account_name, amount in journal_data.items():
                if account_name in ['settlement_id', 'deposit_date', 'notes']:
                    continue
                
                # Get Zoho account ID from mapping
                account_id = self.gl_mapping.get(account_name)
                if not account_id:
                    logger.warning(f"No mapping found for GL account: {account_name}")
                    continue
                
                # Skip zero amounts
                if amount == 0:
                    continue
                
                # Determine debit/credit
                if amount > 0:
                    line_items.append({
                        "account_id": account_id,
                        "debit_or_credit": "debit",
                        "amount": abs(amount)
                    })
                else:
                    line_items.append({
                        "account_id": account_id,
                        "debit_or_credit": "credit",
                        "amount": abs(amount)
                    })
            
            journal_date = journal_data.get('deposit_date', datetime.now().strftime('%Y-%m-%d'))
            notes = journal_data.get('notes', f"Amazon Remittance - Auto-imported from settlement {settlement_id}")
        
        if not line_items:
            logger.error(f"No line items generated for settlement {settlement_id}")
            return None
        
        payload = {
            "journal_date": journal_date,
            "reference_number": reference_number or settlement_id,
            "notes": notes,
            "line_items": line_items
        }
        
        if dry_run:
            logger.info("=" * 70)
            logger.info("DRY RUN MODE - NO DATA POSTED")
            logger.info("=" * 70)
            logger.info(f"Settlement ID: {settlement_id}")
            logger.info(f"Journal Entry Payload:")
            logger.info(json.dumps(payload, indent=2))
            logger.info("=" * 70)
            return "DRY_RUN_ID"
        
        # Actually post to Zoho
        try:
            logger.info(f"Creating journal entry for settlement {settlement_id}")
            result = self._api_request('POST', 'journals', payload)
            
            if result.get('code') == 0:
                journal_id = result['journal']['journal_id']
                logger.info(f"[OK] Journal entry created: {journal_id}")
                return journal_id
            else:
                logger.error(f"Failed to create journal: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating journal entry: {e}")
            return None
    
    def get_journal_entry(self, journal_id: str) -> Optional[Dict]:
        """Retrieve journal entry details"""
        try:
            result = self._api_request('GET', f'journals/{journal_id}')
            if result.get('code') == 0:
                return result.get('journal')
            return None
        except Exception as e:
            logger.error(f"Error retrieving journal {journal_id}: {e}")
            return None
    
    def create_invoice(self, invoice_data: Dict, dry_run: bool = False) -> Optional[str]:
        """
        Create an invoice in Zoho Books
        
        Args:
            invoice_data: Dict with invoice details
            dry_run: If True, validate but don't post
        
        Returns:
            invoice_id or None
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would create invoice: {invoice_data.get('invoice_number')}")
            return "DRY_RUN_INVOICE_ID"
        
        try:
            # Add query parameter to ignore auto-number generation and use custom invoice_number
            result = self._api_request('POST', 'invoices?ignore_auto_number_generation=true', invoice_data)
            
            if result.get('code') == 0:
                invoice_id = result['invoice']['invoice_id']
                logger.info(f"[OK] Invoice created: {invoice_id} ({invoice_data.get('invoice_number')})")
                return invoice_id
            else:
                logger.error(f"Failed to create invoice: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating invoice: {e}")
            return None
    
    def create_payment(self, payment_data: Dict, dry_run: bool = False) -> Optional[str]:
        """
        Create a payment received in Zoho Books
        
        Args:
            payment_data: Dict with payment details
            dry_run: If True, validate but don't post
        
        Returns:
            payment_id or None
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would create payment: ${payment_data.get('amount')}")
            return "DRY_RUN_PAYMENT_ID"
        
        try:
            result = self._api_request('POST', 'customerpayments', payment_data)
            
            if result.get('code') == 0:
                payment_id = result['payment']['payment_id']
                logger.info(f"[OK] Payment created: {payment_id} (${payment_data.get('amount')})")
                return payment_id
            else:
                error_msg = result.get('message', 'Unknown error')
                error_code = result.get('code')
                logger.error(f"Failed to create payment (code={error_code}): {error_msg}")
                logger.error(f"Payment payload: {json.dumps(payment_data, indent=2)}")
                logger.error(f"Full Zoho response: {json.dumps(result, indent=2)}")
                # Log to transaction log file for detailed analysis
                self._log_payment_error(payment_data, result, error_code, error_msg)
                return None
                
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            logger.error(f"Payment payload: {json.dumps(payment_data, indent=2)}")
            # Log exception details
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            return None
    
    def delete_invoice(self, invoice_id: str) -> bool:
        """
        Delete an invoice in Zoho Books
        
        Args:
            invoice_id: The Zoho invoice ID to delete
        
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            result = self._api_request('DELETE', f'invoices/{invoice_id}')
            
            if result.get('code') == 0:
                logger.info(f"[OK] Invoice deleted: {invoice_id}")
                return True
            else:
                logger.error(f"Failed to delete invoice {invoice_id}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting invoice {invoice_id}: {e}")
            return False
    
    def delete_payment(self, payment_id: str) -> bool:
        """
        Delete a payment in Zoho Books
        
        Args:
            payment_id: The Zoho payment ID to delete
        
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            result = self._api_request('DELETE', f'customerpayments/{payment_id}')
            
            if result.get('code') == 0:
                logger.info(f"[OK] Payment deleted: {payment_id}")
                return True
            else:
                logger.error(f"Failed to delete payment {payment_id}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting payment {payment_id}: {e}")
            return False

    def delete_journal(self, journal_id: str) -> bool:
        """
        Delete a manual journal in Zoho Books
        """
        try:
            result = self._api_request('DELETE', f'journals/{journal_id}')
            if result.get('code') == 0:
                logger.info(f"[OK] Journal deleted: {journal_id}")
                return True
            else:
                logger.error(f"Failed to delete journal {journal_id}: {result}")
                return False
        except Exception as e:
            logger.error(f"Error deleting journal {journal_id}: {e}")
            return False
    
    def get_customer_id(self, customer_name: str) -> Optional[str]:
        """Get customer ID by name"""
        try:
            result = self._api_request('GET', f'contacts?contact_name={customer_name}')
            if result.get('code') == 0 and result.get('contacts'):
                return result['contacts'][0]['contact_id']
            return None
        except Exception as e:
            logger.error(f"Error getting customer: {e}")
            return None
    
    def get_item_id(self, sku: str) -> Optional[str]:
        """Get item ID by SKU"""
        try:
            # Try direct SKU lookup first
            result = self._api_request('GET', f'items?sku={sku}')
            if result.get('code') == 0 and result.get('items'):
                return result['items'][0]['item_id']

            # Fallback: use search_text in case SKU filter isn't supported or differs
            result2 = self._api_request('GET', f'items?search_text={sku}')
            if result2.get('code') == 0 and result2.get('items'):
                # Prefer exact SKU match if present in search results
                for it in result2.get('items', []):
                    if str(it.get('sku', '')).strip() == str(sku).strip():
                        return it.get('item_id')
                # Otherwise return first search hit
                return result2['items'][0].get('item_id')
            return None
        except Exception as e:
            logger.error(f"Error getting item for SKU {sku}: {e}")
            return None
    
    def get_invoice_details(self, invoice_id: str) -> Optional[Dict]:
        """
        Get invoice details including balance
        
        Args:
            invoice_id: Zoho invoice ID
            
        Returns:
            Invoice dict with balance_amount, total, etc. or None
        """
        try:
            result = self._api_request('GET', f'invoices/{invoice_id}')
            if result.get('code') == 0:
                return result.get('invoice')
            return None
        except Exception as e:
            logger.error(f"Error getting invoice details for {invoice_id}: {e}")
            return None
    
    def get_invoice_balance(self, invoice_id: str) -> Optional[float]:
        """
        Get remaining balance for an invoice
        
        Args:
            invoice_id: Zoho invoice ID
            
        Returns:
            Balance amount (float) or None if invoice not found
        """
        invoice = self.get_invoice_details(invoice_id)
        if invoice:
            # Balance is the unpaid amount - try multiple fields
            balance = invoice.get('balance', 0)
            if balance is None or balance == '':
                balance = invoice.get('balance_amount', 0)
            if balance is None or balance == '':
                # Calculate from total - payments
                total = float(invoice.get('total', 0) or 0)
                payments = float(invoice.get('payments', 0) or 0)
                balance = total - payments
            return float(balance) if balance else 0.0
        return None
    
    def is_invoice_paid(self, invoice_id: str) -> bool:
        """
        Check if invoice is fully paid
        
        Args:
            invoice_id: Zoho invoice ID
            
        Returns:
            True if invoice is fully paid, False otherwise
        """
        balance = self.get_invoice_balance(invoice_id)
        if balance is None:
            return False
        # Consider invoice paid if balance is <= 0.01 (allowing for rounding)
        return abs(balance) < 0.01


def sync_settlement_to_zoho(settlement_id: str, journal_df, dry_run: bool = True, 
                           aggregate: bool = False) -> Tuple[bool, str]:
    """
    Sync a single settlement to Zoho Books
    
    Args:
        settlement_id: Settlement ID
        journal_df: DataFrame with journal entries
        dry_run: Test mode (no actual posting)
        aggregate: If True, sum by GL account; if False, post each line separately
    
    Returns:
        (success: bool, journal_id: str or error_message: str)
    """
    try:
        zoho = ZohoBooks()
        
        if aggregate:
            # Aggregate by GL account
            gl_totals = {}
            for _, row in journal_df.iterrows():
                account = row['GL_Account']
                debit = row.get('Debit', 0) or 0
                credit = row.get('Credit', 0) or 0
                amount = debit - credit
                
                if account in gl_totals:
                    gl_totals[account] += amount
                else:
                    gl_totals[account] = amount
            
            # Add metadata
            gl_totals['settlement_id'] = settlement_id
            gl_totals['deposit_date'] = journal_df['Date'].iloc[0] if len(journal_df) > 0 else None
            gl_totals['notes'] = f"Amazon Settlement {settlement_id} - {len(journal_df)} transactions"
            
            # Post to Zoho
            journal_id = zoho.create_journal_entry(settlement_id, gl_totals, dry_run=dry_run, individual_lines=False)
        else:
            # Post individual transactions - pass DataFrame directly
            journal_id = zoho.create_journal_entry(settlement_id, journal_df, dry_run=dry_run, individual_lines=True)
        
        if journal_id:
            return True, journal_id
        else:
            return False, "Failed to create journal entry"
            
    except Exception as e:
        logger.error(f"Error syncing settlement {settlement_id}: {e}")
        return False, str(e)
