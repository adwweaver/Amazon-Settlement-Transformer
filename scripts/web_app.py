#!/usr/bin/env python3
"""
Streamlit Web Application for Amazon Settlement Processing

This web app can be embedded in SharePoint or accessed via a direct link.
It provides a user-friendly interface for processing settlement files.

Usage:
    streamlit run scripts/web_app.py
    
Or for SharePoint:
    streamlit run scripts/web_app.py --server.port 8501 --server.address 0.0.0.0
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import subprocess
import time
from datetime import datetime
import json
import os

# Add scripts directory to path - handle both local and Streamlit Cloud
scripts_dir = Path(__file__).parent
scripts_dir_str = str(scripts_dir)
if scripts_dir_str not in sys.path:
    sys.path.insert(0, scripts_dir_str)

# Also add project root to path for Streamlit Cloud
PROJECT_ROOT_TEMP = Path(__file__).parent.parent
if Path('/mount/src/amazon-settlement-transformer').exists():
    PROJECT_ROOT_TEMP = Path('/mount/src/amazon-settlement-transformer')
project_root_str = str(PROJECT_ROOT_TEMP)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
scripts_path_str = str(PROJECT_ROOT_TEMP / 'scripts')
if scripts_path_str not in sys.path:
    sys.path.insert(0, scripts_path_str)

# Try to import paths, but handle if it doesn't exist (for Streamlit Cloud)
try:
    from paths import get_sharepoint_base
except ImportError:
    # Fallback for Streamlit Cloud or if paths module not available
    def get_sharepoint_base():
        """Fallback SharePoint base path"""
        return Path.home() / 'sharepoint' / 'Amazon-ETL'

# Page configuration
st.set_page_config(
    page_title="Amazon Settlement Processor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Project paths - handle both local and Streamlit Cloud
# On Streamlit Cloud, try multiple possible paths
# Start with script location (most reliable)
script_dir = Path(__file__).resolve().parent  # Use absolute path
possible_roots = [
    script_dir.parent,  # Local: scripts/ -> project root
    Path('/mount/src/amazon-settlement-transformer'),  # Streamlit lowercase
    Path('/mount/src/Amazon-Settlement-Transformer'),  # Streamlit with capitals
]

# Find the actual project root by checking for scripts/transform.py
# Use absolute paths to avoid relative path issues
PROJECT_ROOT = None
for root in possible_roots:
    root = root.resolve() if root.is_absolute() else Path.cwd() / root
    test_file = root / 'scripts' / 'transform.py'
    if test_file.exists() and test_file.is_file():
        PROJECT_ROOT = root.resolve()
        break

# Fallback: try script parent with absolute path
if PROJECT_ROOT is None:
    candidate = script_dir.parent.resolve()
    test_file = candidate / 'scripts' / 'transform.py'
    if test_file.exists() and test_file.is_file():
        PROJECT_ROOT = candidate
    else:
        # Last resort: use script parent anyway
        PROJECT_ROOT = candidate

SETTLEMENTS_FOLDER = PROJECT_ROOT / 'raw_data' / 'settlements'
OUTPUTS_FOLDER = PROJECT_ROOT / 'outputs'

# Import processing modules at module level (better for Streamlit Cloud)
MODULES_LOADED = False
MODULE_ERROR = "Unknown error"

try:
    # First try: Direct import (should work if scripts_dir is in sys.path)
    from transform import DataTransformer
    from exports import DataExporter
    from validate_settlement import SettlementValidator
    import yaml
    MODULES_LOADED = True
except ImportError as e:
    # Second try: Use importlib with detected PROJECT_ROOT
    MODULE_ERROR = f"Primary import failed: {e}"
    try:
        import importlib.util
        
        # Try multiple possible locations
        transform_paths = [
            PROJECT_ROOT / 'scripts' / 'transform.py',
            script_dir / 'transform.py',  # In case we're already in scripts/
            Path('/mount/src/amazon-settlement-transformer') / 'scripts' / 'transform.py',
            Path('/mount/src/Amazon-Settlement-Transformer') / 'scripts' / 'transform.py',
        ]
        
        transform_path = None
        for path in transform_paths:
            if path.exists():
                transform_path = path
                break
        
        if transform_path and transform_path.exists():
            # Load transform module
            spec = importlib.util.spec_from_file_location("transform", transform_path)
            transform_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(transform_module)
            DataTransformer = transform_module.DataTransformer
            
            # Load exports module (in same directory as transform)
            exports_path = transform_path.parent / 'exports.py'
            if exports_path.exists():
                spec = importlib.util.spec_from_file_location("exports", exports_path)
                exports_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(exports_module)
                DataExporter = exports_module.DataExporter
            else:
                raise FileNotFoundError(f"Exports file not found at {exports_path}")
            
            # Load validate_settlement module
            validate_path = transform_path.parent / 'validate_settlement.py'
            if validate_path.exists():
                spec = importlib.util.spec_from_file_location("validate_settlement", validate_path)
                validate_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(validate_module)
                SettlementValidator = validate_module.SettlementValidator
            else:
                raise FileNotFoundError(f"Validate settlement file not found at {validate_path}")
            
            import yaml
            MODULES_LOADED = True
            MODULE_ERROR = None
        else:
            checked_paths = ', '.join([str(p) for p in transform_paths])
            MODULE_ERROR = f"Transform file not found in any of: {checked_paths}. Primary error: {e}"
    except Exception as e2:
        MODULE_ERROR = f"{MODULE_ERROR}. Secondary attempt failed: {e2}"

# SharePoint path - handle both local and Streamlit Cloud
try:
    SHAREPOINT_BASE = get_sharepoint_base()
except Exception:
    # Fallback for Streamlit Cloud
    SHAREPOINT_BASE = PROJECT_ROOT / 'sharepoint' / 'Amazon-ETL'

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = set()


def load_processed_files():
    """Load list of processed files"""
    processed_file = PROJECT_ROOT / 'database' / 'webapp_processed.json'
    if processed_file.exists():
        try:
            with open(processed_file, 'r') as f:
                data = json.load(f)
                return set(data.get('processed_files', []))
        except Exception:
            return set()
    return set()


def save_processed_file(filename):
    """Save processed file to tracking"""
    processed_file = PROJECT_ROOT / 'database' / 'webapp_processed.json'
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    
    processed_files = load_processed_files()
    processed_files.add(filename)
    
    data = {
        'processed_files': list(processed_files),
        'last_updated': datetime.now().isoformat()
    }
    
    with open(processed_file, 'w') as f:
        json.dump(data, f, indent=2)


def get_settlement_files():
    """Get list of settlement files"""
    if not SETTLEMENTS_FOLDER.exists():
        return []
    
    files = list(SETTLEMENTS_FOLDER.glob('*.txt'))
    return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)


def process_files():
    """Process settlement files - process directly instead of subprocess for Streamlit Cloud compatibility"""
    if st.session_state.processing:
        return
    
    st.session_state.processing = True
    
    try:
        # Check if modules were loaded successfully
        if not MODULES_LOADED:
            st.error(f"❌ Import error: Modules not loaded. {MODULE_ERROR}")
            st.error(f"📁 Project root: {PROJECT_ROOT} (absolute: {PROJECT_ROOT.resolve()})")
            st.error(f"📁 Script file location: {Path(__file__).resolve()}")
            st.error(f"📁 Current working directory: {Path.cwd()}")
            st.error(f"📁 Scripts directory: {PROJECT_ROOT / 'scripts'} (exists: {(PROJECT_ROOT / 'scripts').exists()})")
            transform_file = PROJECT_ROOT / 'scripts' / 'transform.py'
            st.error(f"📁 Transform file: {transform_file} (exists: {transform_file.exists()}, absolute: {transform_file.resolve() if transform_file.exists() else 'N/A'})")
            st.error(f"📁 Python path: {sys.path[:5]}")
            
            # Try to find transform.py in any location
            import os
            for root, dirs, files in os.walk('/mount/src'):
                if 'transform.py' in files:
                    st.info(f"🔍 Found transform.py at: {os.path.join(root, 'transform.py')}")
            
            st.session_state.processing = False
            return False
        
        # Load config
        config_file = PROJECT_ROOT / 'config' / 'config.yaml'
        if not config_file.exists():
            st.error(f"❌ Config file not found: {config_file}")
            st.session_state.processing = False
            return False
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Setup logging (simplified for web app)
        import logging
        log_dir = PROJECT_ROOT / 'logs'
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=getattr(logging, config.get('options', {}).get('log_level', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'etl_pipeline.log'),
                logging.StreamHandler()
            ]
        )
        
        # Initialize transformer
        transformer = DataTransformer(config)
        
        # Process settlements
        st.info("📊 Processing settlement files...")
        settlements_data = transformer.process_settlements()
        
        if settlements_data is None or settlements_data.empty:
            st.warning("⚠️ No settlement files found to process")
            st.session_state.processing = False
            return False
        
        st.info(f"✅ Processed {len(settlements_data)} settlement records")
        
        # Get list of processed file names from the settlements folder
        processed_file_names = set()
        settlement_files = list(SETTLEMENTS_FOLDER.glob('*.txt'))
        for file_path in settlement_files:
            # Extract settlement ID from filename (filename is like "50011020300.txt")
            # The settlement ID should match what's in the data
            processed_file_names.add(file_path.name)
        
        # Process invoices and payments (if needed)
        invoices_data = transformer.process_invoices()
        payments_data = transformer.process_payments()
        
        # Merge and finalize
        st.info("🔄 Merging and finalizing data...")
        final_data = transformer.merge_and_finalize(
            settlements_data,
            invoices_data,
            payments_data
        )
        
        # Initialize exporter
        exporter = DataExporter(config)
        if hasattr(transformer, 'price_lookup_data'):
            exporter.price_lookup_data = transformer.price_lookup_data
        
        # Generate exports
        st.info("📄 Generating export files...")
        exporter.generate_journal_export(final_data)
        exporter.generate_invoice_export(final_data)
        exporter.generate_payment_export(final_data)
        exporter.generate_dashboard_summary(final_data)
        
        # Run validation (optional but recommended)
        try:
            validator = SettlementValidator(config)
            validation_results = validator.validate_settlement(final_data)
            if validation_results:
                st.info("✅ Validation checks completed")
        except Exception as e:
            st.warning(f"⚠️ Validation skipped: {e}")
        
        # Mark all processed files as processed
        for file_name in processed_file_names:
            save_processed_file(file_name)
        
        st.success("✅ Processing completed successfully!")
        st.info(f"📝 Marked {len(processed_file_names)} file(s) as processed")
        return True
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"❌ Error: {str(e)}")
        with st.expander("See error details"):
            st.code(error_details)
        return False
    finally:
        st.session_state.processing = False


def main():
    """Main application"""
    
    # Title
    st.title("📊 Amazon Settlement Processor")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Navigation")
        
        page = st.radio(
            "Select Page",
            ["Process Files", "View Outputs", "Status & Logs", "Settings"],
            index=0
        )
        
        st.markdown("---")
        st.info("💡 **Tip:** Upload files to `raw_data/settlements/` folder, then click 'Process Files'")
    
    # Main content
    if page == "Process Files":
        st.header("🚀 Process Settlement Files")
        
        # File upload section
        st.subheader("📤 Upload New File")
        
        uploaded_file = st.file_uploader(
            "Choose a settlement file (.txt)",
            type=['txt'],
            help="Upload a .txt settlement file from Amazon"
        )
        
        if uploaded_file is not None:
            # Save uploaded file
            save_path = SETTLEMENTS_FOLDER / uploaded_file.name
            SETTLEMENTS_FOLDER.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            st.info(f"📁 Saved to: {save_path}")
        
        st.markdown("---")
        
        # Existing files section
        st.subheader("📋 Existing Settlement Files")
        
        files = get_settlement_files()
        processed_files = load_processed_files()
        
        if files:
            # File list
            file_data = []
            for file_path in files:
                file_stat = file_path.stat()
                file_data.append({
                    'File Name': file_path.name,
                    'Size': f"{file_stat.st_size / 1024:.1f} KB",
                    'Modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'Status': '✅ Processed' if file_path.name in processed_files else '⏳ Pending'
                })
            
            df = pd.DataFrame(file_data)
            
            # Configure column display to prevent overflow
            # Set proper widths and enable word wrapping
            column_config = {
                'File Name': st.column_config.TextColumn(
                    'File Name',
                    width='medium',
                    help='Settlement file name'
                ),
                'Size': st.column_config.TextColumn(
                    'Size',
                    width='small',
                    help='File size'
                ),
                'Modified': st.column_config.TextColumn(
                    'Modified',
                    width='medium',
                    help='Last modification date'
                ),
                'Status': st.column_config.TextColumn(
                    'Status',
                    width='small',
                    help='Processing status'
                )
            }
            
            # Display with proper formatting
            st.dataframe(
                df, 
                use_container_width=True, 
                hide_index=True,
                column_config=column_config,
                column_order=['File Name', 'Size', 'Modified', 'Status']
            )
            
            # Process button
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button("🔄 Process Files", disabled=st.session_state.processing):
                    with st.spinner("Processing files... This may take a few minutes."):
                        success = process_files()
                        if success:
                            # Refresh file list
                            time.sleep(1)
                            st.rerun()
            
            with col2:
                if st.button("🔄 Refresh List"):
                    st.rerun()
            
            with col3:
                st.info(f"📊 **{len(files)}** file(s) found")
        
        else:
            st.info("📭 No settlement files found. Upload a file above or place files in the `raw_data/settlements/` folder.")
    
    elif page == "View Outputs":
        st.header("📂 View Output Files")
        
        # Get output settlements
        if OUTPUTS_FOLDER.exists():
            settlements = [d for d in OUTPUTS_FOLDER.iterdir() if d.is_dir()]
            
            if settlements:
                st.subheader("Processed Settlements")
                
                # Settlement selector
                settlement_names = [f"{s.name} ({len(list(s.glob('*.csv')))} files)" for s in settlements]
                selected = st.selectbox("Select Settlement", settlement_names)
                
                if selected:
                    settlement_id = selected.split(' ')[0]
                    settlement_dir = OUTPUTS_FOLDER / settlement_id
                    
                    # Show files
                    files = list(settlement_dir.glob('*'))
                    
                    if files:
                        st.subheader(f"Files for Settlement {settlement_id}")
                        
                        for file_path in sorted(files):
                            file_name = file_path.name
                            file_size = file_path.stat().st_size
                            
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.text(file_name)
                            
                            with col2:
                                with open(file_path, 'rb') as f:
                                    st.download_button(
                                        label="📥 Download",
                                        data=f.read(),
                                        file_name=file_name,
                                        mime='text/csv' if file_path.suffix == '.csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                        key=file_name
                                    )
                    else:
                        st.info("No output files found for this settlement.")
            else:
                st.info("No processed settlements found. Process some files first.")
        else:
            st.warning("Outputs folder not found.")
    
    elif page == "Status & Logs":
        st.header("📊 Processing Status & Logs")
        
        # Processing status
        st.subheader("Current Status")
        
        if st.session_state.processing:
            st.warning("⚠️ Processing in progress...")
            st.progress(0.5)  # Placeholder progress
        else:
            st.success("✅ Ready - No processing in progress")
        
        st.markdown("---")
        
        # Recent logs
        st.subheader("Recent Logs")
        
        log_file = PROJECT_ROOT / 'logs' / 'etl_pipeline.log'
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Show last 50 lines
                recent_lines = lines[-50:] if len(lines) > 50 else lines
            
            st.code('\n'.join(recent_lines), language='text')
            
            if st.button("🔄 Refresh Logs"):
                st.rerun()
        else:
            st.info("No log file found. Logs will appear here after processing.")
    
    elif page == "Settings":
        st.header("⚙️ Settings")
        
        st.subheader("Folder Locations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Settlements Folder", value=str(SETTLEMENTS_FOLDER), disabled=True)
            st.text_input("Outputs Folder", value=str(OUTPUTS_FOLDER), disabled=True)
        
        with col2:
            st.text_input("SharePoint Base", value=str(SHAREPOINT_BASE), disabled=True)
            st.text_input("Project Root", value=str(PROJECT_ROOT), disabled=True)
        
        st.markdown("---")
        
        st.subheader("System Information")
        
        st.json({
            "Python Version": sys.version.split()[0],
            "Project Root": str(PROJECT_ROOT),
            "Settlements Folder": str(SETTLEMENTS_FOLDER),
            "Outputs Folder": str(OUTPUTS_FOLDER),
            "SharePoint Base": str(SHAREPOINT_BASE)
        })
        
        if st.button("🔄 Refresh Settings"):
            st.rerun()


if __name__ == "__main__":
    main()

