#!/usr/bin/env python3
"""
Database module for tracking processed files and historical data.
"""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import logging


class ETLDatabase:
    """Handles all database operations for the ETL pipeline."""
    
    def __init__(self, db_path: str = "database/settlements.db"):
        """Initialize database connection and ensure schema exists."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self._init_schema()
    
    def _init_schema(self):
        """Create database schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Track processed files (prevent reprocessing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                settlement_id TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                archived_path TEXT,
                status TEXT CHECK(status IN ('success', 'failed', 'partial')) DEFAULT 'success',
                error_message TEXT,
                record_count INTEGER
            )
        """)
        
        # Settlement summary history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settlement_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                settlement_id TEXT NOT NULL,
                deposit_date DATE,
                date_from DATE,
                date_to DATE,
                bank_deposit_amount REAL,
                total_records INTEGER,
                journal_lines INTEGER,
                invoice_lines INTEGER,
                tax_lines INTEGER,
                split_lines INTEGER,
                linecount_check INTEGER,
                total_tax_amount REAL,
                balance_check TEXT,
                processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_id INTEGER,
                FOREIGN KEY (file_id) REFERENCES processed_files(file_id)
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_settlement_id 
            ON settlement_history(settlement_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_date 
            ON processed_files(processed_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_hash 
            ON processed_files(file_hash)
        """)
        
        conn.commit()
        conn.close()
        self.logger.info(f"Database initialized at {self.db_path}")
    
    @staticmethod
    def calculate_file_hash(filepath: Path) -> str:
        """Calculate SHA256 hash of file for duplicate detection."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def check_file_processed(self, filename: str, file_hash: str) -> Optional[Dict]:
        """
        Check if file has already been processed.
        
        Returns:
            Dict with file info if already processed, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM processed_files 
            WHERE filename = ? OR file_hash = ?
        """, (filename, file_hash))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def log_processed_file(self, filename: str, settlement_id: str, file_hash: str,
                          file_size: int, archived_path: str, status: str = 'success',
                          error_message: str = None, record_count: int = 0) -> int:
        """
        Log a processed file to the database.
        
        Returns:
            file_id of the inserted record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO processed_files 
            (filename, settlement_id, file_hash, file_size, archived_path, 
             status, error_message, record_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (filename, settlement_id, file_hash, file_size, archived_path, 
              status, error_message, record_count))
        
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.logger.info(f"Logged processed file: {filename} (ID: {file_id})")
        return file_id
    
    def log_settlement_summary(self, summary_data: Dict, file_id: int):
        """Log settlement summary data to history table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO settlement_history 
            (settlement_id, deposit_date, date_from, date_to, bank_deposit_amount,
             total_records, journal_lines, invoice_lines, tax_lines, split_lines,
             linecount_check, total_tax_amount, balance_check, file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary_data.get('settlement_id'),
            summary_data.get('deposit_date'),
            summary_data.get('date_from'),
            summary_data.get('date_to'),
            summary_data.get('bank_deposit_amount'),
            summary_data.get('total_records'),
            summary_data.get('journal_lines'),
            summary_data.get('invoice_lines'),
            summary_data.get('tax_lines'),
            summary_data.get('split_lines'),
            summary_data.get('linecount_check'),
            summary_data.get('total_tax_amount'),
            summary_data.get('balance_check'),
            file_id
        ))
        
        conn.commit()
        conn.close()
        self.logger.info(f"Logged settlement summary for {summary_data.get('settlement_id')}")
    
    def get_processing_history(self, limit: int = 50) -> List[Dict]:
        """Get recent processing history."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM processed_files 
            ORDER BY processed_date DESC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_settlement_history(self, settlement_id: str = None) -> List[Dict]:
        """Get settlement processing history, optionally filtered by settlement_id."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if settlement_id:
            cursor.execute("""
                SELECT * FROM settlement_history 
                WHERE settlement_id = ?
                ORDER BY processed_timestamp DESC
            """, (settlement_id,))
        else:
            cursor.execute("""
                SELECT * FROM settlement_history 
                ORDER BY processed_timestamp DESC
                LIMIT 100
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_statistics(self) -> Dict:
        """Get overall statistics about processed files."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total files processed
        cursor.execute("SELECT COUNT(*) FROM processed_files WHERE status = 'success'")
        stats['total_files_processed'] = cursor.fetchone()[0]
        
        # Total settlements
        cursor.execute("SELECT COUNT(DISTINCT settlement_id) FROM settlement_history")
        stats['total_settlements'] = cursor.fetchone()[0]
        
        # Total records processed
        cursor.execute("SELECT SUM(record_count) FROM processed_files WHERE status = 'success'")
        result = cursor.fetchone()[0]
        stats['total_records_processed'] = result if result else 0
        
        # Most recent processing date
        cursor.execute("SELECT MAX(processed_date) FROM processed_files")
        stats['last_processed'] = cursor.fetchone()[0]
        
        # Failed files count
        cursor.execute("SELECT COUNT(*) FROM processed_files WHERE status = 'failed'")
        stats['failed_files'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
