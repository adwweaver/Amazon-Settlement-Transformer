#!/usr/bin/env python3
"""
File Watcher for Automatic Settlement Processing

This script monitors the raw_data/settlements/ folder for new .txt files
and automatically processes them when detected.

Usage:
    python scripts/watchdog.py
    
Or run as Windows service:
    python scripts/watchdog.py --service
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


class SettlementFileHandler(FileSystemEventHandler):
    """Handler for settlement file events"""
    
    def __init__(self, processed_files_file: Path):
        self.processed_files_file = processed_files_file
        self.processed_files = self._load_processed_files()
        self.processing = set()  # Track files currently being processed
        
        # Setup logging
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'watchdog.log'),
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
    
    def _process_file(self, file_path: Path):
        """Process a settlement file"""
        if file_path in self.processing:
            self.logger.debug(f"File {file_path.name} already being processed")
            return
        
        if str(file_path) in self.processed_files:
            self.logger.info(f"File {file_path.name} already processed, skipping")
            return
        
        self.logger.info(f"New settlement file detected: {file_path.name}")
        self.processing.add(file_path)
        
        try:
            # Run the ETL pipeline
            self.logger.info(f"Starting ETL pipeline for {file_path.name}...")
            
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
                self.logger.info(f"Successfully processed {file_path.name}")
                self.processed_files.add(str(file_path))
                self._save_processed_files()
                
                # Show notification (Windows)
                try:
                    self._show_notification(
                        "Settlement Processed",
                        f"File {file_path.name} processed successfully"
                    )
                except Exception:
                    pass  # Notification is optional
            else:
                self.logger.error(f"Failed to process {file_path.name}")
                self.logger.error(f"Error output: {result.stderr}")
                
                # Show error notification
                try:
                    self._show_notification(
                        "Processing Failed",
                        f"File {file_path.name} failed to process. Check logs."
                    )
                except Exception:
                    pass
                    
        except subprocess.TimeoutExpired:
            self.logger.error(f"Processing {file_path.name} timed out")
        except Exception as e:
            self.logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)
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
    """Main function to start the file watcher"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor settlement folder for new files')
    parser.add_argument('--watch-folder', type=str, default=None,
                       help='Folder to watch (default: raw_data/settlements/)')
    parser.add_argument('--interval', type=int, default=1,
                       help='Check interval in seconds (default: 1)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress console output')
    
    args = parser.parse_args()
    
    # Setup paths
    project_root = Path(__file__).parent.parent
    watch_folder = project_root / (args.watch_folder or 'raw_data/settlements')
    processed_files_file = project_root / 'database' / 'watchdog_processed.json'
    
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
    logger.info("Settlement File Watcher Started")
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



