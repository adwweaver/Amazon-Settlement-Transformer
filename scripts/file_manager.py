#!/usr/bin/env python3
"""
File management module for archiving and organizing processed files.
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import logging


class FileManager:
    """Handles file archiving and organization."""
    
    def __init__(self, base_path: str = "."):
        """Initialize file manager with base path."""
        self.base_path = Path(base_path)
        self.incoming_dir = self.base_path / "raw_data" / "settlements"
        self.archive_dir = self.base_path / "archive"
        self.outputs_dir = self.base_path / "outputs"
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
    
    def archive_file(self, source_path: Path, settlement_id: str = None) -> Path:
        """
        Archive a processed file with timestamp in organized folder structure.
        
        Args:
            source_path: Path to source file
            settlement_id: Optional settlement ID for better organization
            
        Returns:
            Path to archived file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        year_month = datetime.now().strftime('%Y-%m')
        
        # Create archive directory for this month
        archive_subdir = self.archive_dir / year_month
        archive_subdir.mkdir(parents=True, exist_ok=True)
        
        # Create new filename with timestamp
        filename = source_path.stem
        extension = source_path.suffix
        
        if settlement_id:
            new_name = f"{settlement_id}_{filename}_processed_{timestamp}{extension}"
        else:
            new_name = f"{filename}_processed_{timestamp}{extension}"
        
        archive_path = archive_subdir / new_name
        
        # Copy file to archive
        shutil.copy2(source_path, archive_path)
        self.logger.info(f"Archived file: {source_path.name} -> {archive_path}")
        
        return archive_path
    
    def archive_and_remove(self, source_path: Path, settlement_id: str = None) -> Path:
        """
        Archive file and remove from incoming directory.
        
        Args:
            source_path: Path to source file
            settlement_id: Optional settlement ID
            
        Returns:
            Path to archived file
        """
        archive_path = self.archive_file(source_path, settlement_id)
        
        # Remove from incoming
        source_path.unlink()
        self.logger.info(f"Removed original file: {source_path}")
        
        return archive_path
    
    def get_incoming_files(self, pattern: str = "*.txt") -> List[Path]:
        """
        Get list of unprocessed files in incoming directory.
        
        Args:
            pattern: File pattern to match (default: *.txt)
            
        Returns:
            List of file paths
        """
        files = sorted(self.incoming_dir.glob(pattern))
        self.logger.info(f"Found {len(files)} files in incoming directory")
        return files
    
    def archive_outputs(self, session_timestamp: str = None) -> Path:
        """
        Archive current output files to timestamped folder.
        
        Args:
            session_timestamp: Optional timestamp string for archive folder
            
        Returns:
            Path to archive folder
        """
        if session_timestamp is None:
            session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        outputs_archive_dir = self.outputs_dir / "archive" / session_timestamp
        outputs_archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy all CSV files from outputs to archive
        csv_files = list(self.outputs_dir.glob("*.csv"))
        
        for csv_file in csv_files:
            dest = outputs_archive_dir / csv_file.name
            shutil.copy2(csv_file, dest)
        
        self.logger.info(f"Archived {len(csv_files)} output files to {outputs_archive_dir}")
        return outputs_archive_dir
    
    def get_file_info(self, filepath: Path) -> dict:
        """
        Get metadata about a file.
        
        Args:
            filepath: Path to file
            
        Returns:
            Dictionary with file metadata
        """
        stat = filepath.stat()
        return {
            'filename': filepath.name,
            'size': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'created': datetime.fromtimestamp(stat.st_ctime),
            'extension': filepath.suffix
        }
    
    def clean_old_archives(self, days: int = 365) -> int:
        """
        Clean up archive files older than specified days.
        
        Args:
            days: Number of days to keep archives
            
        Returns:
            Number of files removed
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        for archive_file in self.archive_dir.rglob("*.*"):
            if archive_file.is_file():
                modified_time = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if modified_time < cutoff_date:
                    archive_file.unlink()
                    removed_count += 1
        
        self.logger.info(f"Cleaned up {removed_count} archive files older than {days} days")
        return removed_count
