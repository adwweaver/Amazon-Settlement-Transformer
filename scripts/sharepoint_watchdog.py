#!/usr/bin/env python3
"""
SharePoint-Integrated Settlement File Watcher

Monitors synced SharePoint folder for new settlement files, processes them automatically,
and updates SharePoint List with status. Sends email notifications on completion/errors.

Usage:
    python scripts/sharepoint_watchdog.py
    
Or run as Windows service:
    python scripts/sharepoint_watchdog.py --service
"""

import sys
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import json
from datetime import datetime
import os

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from paths import get_settlement_history_path
from notifications import send_email
import yaml

# SharePoint List integration
try:
    import requests
    SHAREPOINT_API_AVAILABLE = True
except ImportError:
    SHAREPOINT_API_AVAILABLE = False
    logging.warning("requests package not available - SharePoint List updates disabled")


class SharePointStatusTracker:
    """Tracks processing status in SharePoint List"""
    
    def __init__(self, config_file: Path = None):
        """Initialize SharePoint status tracker"""
        if config_file is None:
            config_file = Path(__file__).parent.parent / 'config' / 'config.yaml'
        
        try:
            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        except:
            self.config = {}
        
        # SharePoint List configuration
        self.sharepoint_site = self.config.get('sharepoint', {}).get('site_url', '')
        self.list_name = self.config.get('sharepoint', {}).get('status_list_name', 'Settlement Processing Status')
        self.access_token = None
        
        # Email configuration
        self.email_enabled = self.config.get('notifications', {}).get('email_enabled', False)
        self.email_to = self.config.get('notifications', {}).get('email_to', [])
        self.email_from = self.config.get('notifications', {}).get('email_from', '')
    
    def update_status(self, file_name: str, settlement_id: str, status: str, 
                     zoho_sync_status: str = None, error_message: str = None,
                     journal_id: str = None, invoice_count: int = None, 
                     payment_count: int = None, output_files_link: str = None):
        """Update SharePoint List item with processing status"""
        if not SHAREPOINT_API_AVAILABLE or not self.sharepoint_site:
            logging.warning("SharePoint List updates not configured - skipping")
            return False
        
        try:
            # Find or create list item
            item_id = self._find_or_create_item(file_name, settlement_id)
            
            if not item_id:
                logging.warning(f"Could not find or create SharePoint List item for {file_name}")
                return False
            
            # Update item
            update_data = {
                'Status': status,
                'ProcessedDate': datetime.now().isoformat() if status in ['Completed', 'Error'] else None,
                'ZohoSyncStatus': zoho_sync_status or '',
                'JournalID': journal_id or '',
                'InvoiceCount': invoice_count or 0,
                'PaymentCount': payment_count or 0,
                'ErrorMessage': error_message or '',
                'OutputFilesLink': output_files_link or ''
            }
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            # Make API call to update SharePoint List item
            # This requires OAuth authentication - implementation depends on your SharePoint setup
            # For now, we'll log it and return success
            logging.info(f"Would update SharePoint List item {item_id} with: {update_data}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error updating SharePoint List: {e}")
            return False
    
    def _find_or_create_item(self, file_name: str, settlement_id: str) -> str:
        """Find existing list item or create new one"""
        # This would make SharePoint REST API calls to find/create item
        # Placeholder implementation - needs actual SharePoint API integration
        return None
    
    def send_notification(self, file_name: str, settlement_id: str, status: str,
                         message: str, error_message: str = None):
        """Send email notification"""
        if not self.email_enabled or not self.email_to:
            logging.debug("Email notifications not configured - skipping")
            return False
        
        try:
            if status == 'Completed':
                subject = f"Settlement Processing Completed - {file_name} ✅"
                body = f"""
File: {file_name}
Settlement ID: {settlement_id}

Status: Success ✅

{message}

View Status: {self.sharepoint_site}/Lists/{self.list_name}/AllItems.aspx
"""
            elif status == 'Error':
                subject = f"Settlement Processing Failed - {file_name} ❌"
                body = f"""
File: {file_name}
Settlement ID: {settlement_id}

Status: Error ❌

Error Details:
{error_message or 'Unknown error'}

Please review the error and try again, or contact support.
"""
            else:
                subject = f"Settlement Processing Started - {file_name}"
                body = f"""
File: {file_name}
Settlement ID: {settlement_id}

Processing has started. You will receive another email when processing completes.
"""
            
            # Send email
            send_email(
                subject=subject,
                body=body
            )
            
            logging.info(f"Email notification sent for {file_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error sending email notification: {e}")
            return False


class SettlementFileHandler(FileSystemEventHandler):
    """Handler for settlement file events with SharePoint integration"""
    
    def __init__(self, processed_files_file: Path):
        self.processed_files_file = processed_files_file
        self.processed_files = self._load_processed_files()
        self.processing = set()  # Track files currently being processed
        
        # Initialize SharePoint tracker
        self.sharepoint_tracker = SharePointStatusTracker()
        
        # Setup logging
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'sharepoint_watchdog.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _load_processed_files(self) -> set:
        """Load list of already processed files"""
        if not self.processed_files_file.exists():
            return set()
        
        try:
            with open(self.processed_files_file, 'r') as f:
                data = json.load(f)
                return set(data.get('processed_files', []))
        except Exception as e:
            logging.warning(f"Could not load processed files: {e}")
            return set()
    
    def _save_processed_files(self):
        """Save list of processed files"""
        try:
            data = {
                'processed_files': list(self.processed_files),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.processed_files_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Could not save processed files: {e}")
    
    def _is_settlement_file(self, file_path: Path) -> bool:
        """Check if file is a settlement file"""
        return file_path.suffix.lower() == '.txt' and file_path.is_file()
    
    def _extract_settlement_id(self, file_path: Path) -> str:
        """Extract settlement ID from file (try filename first, then file content)"""
        # Try filename (e.g., "50065020384.txt" -> "50065020384")
        settlement_id = file_path.stem
        if settlement_id.isdigit():
            return settlement_id
        
        # Try to read first line of file to get actual settlement ID
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if '\t' in first_line:
                    # Tab-delimited file
                    parts = first_line.split('\t')
                    if len(parts) > 0:
                        settlement_id_from_file = parts[0].strip()
                        if settlement_id_from_file.isdigit():
                            return settlement_id_from_file
        except:
            pass
        
        # Fallback to filename
        return file_path.stem
    
    def _process_file(self, file_path: Path):
        """Process a settlement file"""
        if file_path in self.processing:
            self.logger.debug(f"File {file_path.name} already being processed")
            return
        
        if str(file_path) in self.processed_files:
            self.logger.info(f"File {file_path.name} already processed, skipping")
            return
        
        file_name = file_path.name
        settlement_id = self._extract_settlement_id(file_path)
        
        self.logger.info(f"New settlement file detected: {file_name}")
        self.processing.add(file_path)
        
        # Update SharePoint List: Processing started
        self.sharepoint_tracker.update_status(
            file_name=file_name,
            settlement_id=settlement_id,
            status='Processing'
        )
        
        # Send notification: Processing started
        self.sharepoint_tracker.send_notification(
            file_name=file_name,
            settlement_id=settlement_id,
            status='Processing',
            message='Processing has started'
        )
        
        try:
            # Run the ETL pipeline
            self.logger.info(f"Starting ETL pipeline for {file_name}...")
            
            # Get the project root directory
            project_root = Path(__file__).parent.parent
            scripts_dir = project_root / 'scripts'
            
            # Run main.py
            result = subprocess.run(
                [sys.executable, str(scripts_dir / 'main.py')],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully processed {file_name}")
                
                # Try to sync to Zoho
                zoho_sync_status = 'Not Synced'
                journal_id = None
                invoice_count = None
                payment_count = None
                error_message = None
                
                try:
                    from sync_settlement import post_settlement_complete
                    
                    self.logger.info(f"Syncing settlement {settlement_id} to Zoho...")
                    sync_result = post_settlement_complete(
                        settlement_id=settlement_id,
                        post_journal=True,
                        post_invoices=True,
                        post_payments=True,
                        dry_run=False,
                        override=False
                    )
                    
                    if sync_result.get('journal', {}).get('posted', False):
                        journal_id = sync_result['journal'].get('id')
                        zoho_sync_status = 'Synced'
                    
                    if sync_result.get('invoices', {}).get('posted', False):
                        invoice_count = sync_result['invoices'].get('count', 0)
                    
                    if sync_result.get('payments', {}).get('posted', False):
                        payment_count = sync_result['payments'].get('count', 0)
                    
                    if not sync_result.get('journal', {}).get('posted', False):
                        error_message = sync_result.get('journal', {}).get('error', 'Unknown error')
                        zoho_sync_status = f"Error: {error_message}"
                    
                except Exception as e:
                    self.logger.error(f"Error syncing to Zoho: {e}")
                    error_message = str(e)
                    zoho_sync_status = f"Error: {error_message}"
                
                # Mark as processed
                self.processed_files.add(str(file_path))
                self._save_processed_files()
                
                # Update SharePoint List: Completed
                output_files_link = f"{self.sharepoint_tracker.sharepoint_site}/Lists/ProcessedFiles?settlement_id={settlement_id}"
                
                self.sharepoint_tracker.update_status(
                    file_name=file_name,
                    settlement_id=settlement_id,
                    status='Completed',
                    zoho_sync_status=zoho_sync_status,
                    error_message=error_message,
                    journal_id=journal_id,
                    invoice_count=invoice_count,
                    payment_count=payment_count,
                    output_files_link=output_files_link
                )
                
                # Send notification: Completed
                message = f"""
Processing Summary:
- Journal: {'Posted' if journal_id else 'Not posted'} ({journal_id or 'N/A'})
- Invoices: {invoice_count or 0} posted
- Payments: {payment_count or 0} posted
- Zoho Sync: {zoho_sync_status}
"""
                self.sharepoint_tracker.send_notification(
                    file_name=file_name,
                    settlement_id=settlement_id,
                    status='Completed',
                    message=message
                )
                
                # Show notification (Windows)
                try:
                    self._show_notification(
                        "Settlement Processed",
                        f"File {file_name} processed successfully"
                    )
                except Exception:
                    pass
            else:
                self.logger.error(f"Failed to process {file_name}")
                self.logger.error(f"Error output: {result.stderr}")
                
                error_message = result.stderr[:500] if result.stderr else "Unknown error"
                
                # Update SharePoint List: Error
                self.sharepoint_tracker.update_status(
                    file_name=file_name,
                    settlement_id=settlement_id,
                    status='Error',
                    error_message=error_message
                )
                
                # Send notification: Error
                self.sharepoint_tracker.send_notification(
                    file_name=file_name,
                    settlement_id=settlement_id,
                    status='Error',
                    message='',
                    error_message=error_message
                )
                
                # Show error notification
                try:
                    self._show_notification(
                        "Processing Failed",
                        f"File {file_name} failed to process. Check logs."
                    )
                except Exception:
                    pass
                    
        except subprocess.TimeoutExpired:
            self.logger.error(f"Processing {file_name} timed out")
            error_message = "Processing timed out after 10 minutes"
            
            # Update SharePoint List: Error
            self.sharepoint_tracker.update_status(
                file_name=file_name,
                settlement_id=settlement_id,
                status='Error',
                error_message=error_message
            )
            
            # Send notification: Error
            self.sharepoint_tracker.send_notification(
                file_name=file_name,
                settlement_id=settlement_id,
                status='Error',
                message='',
                error_message=error_message
            )
        except Exception as e:
            self.logger.error(f"Error processing {file_name}: {e}", exc_info=True)
            
            # Update SharePoint List: Error
            self.sharepoint_tracker.update_status(
                file_name=file_name,
                settlement_id=settlement_id,
                status='Error',
                error_message=str(e)
            )
            
            # Send notification: Error
            self.sharepoint_tracker.send_notification(
                file_name=file_name,
                settlement_id=settlement_id,
                status='Error',
                message='',
                error_message=str(e)
            )
        finally:
            self.processing.discard(file_path)
    
    def _show_notification(self, title: str, message: str):
        """Show Windows notification"""
        try:
            import win10toast
            toaster = win10toast.ToastNotifier()
            toaster.show_toast(title, message, duration=10)
        except ImportError:
            # win10toast not installed, skip notification
            pass
        except Exception as e:
            self.logger.debug(f"Could not show notification: {e}")
    
    def on_created(self, event):
        """Handle file creation event"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        if self._is_settlement_file(file_path):
            # Wait a moment to ensure file is fully written
            time.sleep(2)
            
            # Check if file is still being written (size changes)
            last_size = 0
            stable_count = 0
            for _ in range(10):  # Check for 5 seconds
                try:
                    current_size = file_path.stat().st_size
                    if current_size == last_size:
                        stable_count += 1
                        if stable_count >= 3:
                            break  # File is stable
                    else:
                        stable_count = 0
                        last_size = current_size
                    time.sleep(0.5)
                except Exception:
                    pass
            
            self._process_file(file_path)
    
    def on_moved(self, event):
        """Handle file move event (like a copy completing)"""
        if event.is_directory:
            return
        
        file_path = Path(event.dest_path)
        
        if self._is_settlement_file(file_path):
            time.sleep(2)
            self._process_file(file_path)


def main():
    """Main function to start the SharePoint-integrated file watcher"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor SharePoint-synced folder for new settlement files')
    parser.add_argument('--watch-folder', type=str, default=None,
                       help='Folder to watch (default: SharePoint synced folder)')
    parser.add_argument('--interval', type=int, default=1,
                       help='Check interval in seconds (default: 1)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress console output')
    
    args = parser.parse_args()
    
    # Setup paths
    project_root = Path(__file__).parent.parent
    
    # Default to SharePoint synced folder if available
    if args.watch_folder:
        watch_folder = Path(args.watch_folder)
    else:
        # Try to find SharePoint synced folder
        sharepoint_sync_paths = [
            Path(os.path.expanduser(r"~\SharePoint\Amazon-ETL-Incoming")),
            Path(os.path.expanduser(r"~\OneDrive - Touchstone Brands\Amazon-ETL-Incoming")),
            Path(os.path.expanduser(r"~\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL-Incoming")),
            project_root / 'raw_data' / 'settlements'  # Fallback to local folder
        ]
        
        watch_folder = None
        for path in sharepoint_sync_paths:
            if path.exists():
                watch_folder = path
                break
        
        if not watch_folder:
            watch_folder = project_root / 'raw_data' / 'settlements'
            logging.warning(f"SharePoint synced folder not found, using default: {watch_folder}")
    
    processed_files_file = project_root / 'database' / 'sharepoint_watchdog_processed.json'
    
    # Create directories
    watch_folder.mkdir(parents=True, exist_ok=True)
    processed_files_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    if not args.quiet:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    logger = logging.getLogger(__name__)
    
    logger.info("="*80)
    logger.info("SharePoint-Integrated Settlement File Watcher Started")
    logger.info("="*80)
    logger.info(f"Watching folder: {watch_folder}")
    logger.info(f"Processed files log: {processed_files_file}")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*80)
    
    # Create event handler
    event_handler = SettlementFileHandler(processed_files_file)
    
    # Create observer
    observer = Observer()
    observer.schedule(event_handler, str(watch_folder), recursive=False)
    observer.start()
    
    try:
        # Process any existing files
        logger.info("Checking for existing files...")
        for file_path in watch_folder.glob('*.txt'):
            if file_path.is_file():
                event_handler._process_file(file_path)
        
        # Keep running
        while True:
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Stopping file watcher...")
        observer.stop()
    
    observer.join()
    logger.info("File watcher stopped")


if __name__ == "__main__":
    main()

