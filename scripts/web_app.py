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

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from paths import get_sharepoint_base

# Page configuration
st.set_page_config(
    page_title="Amazon Settlement Processor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SETTLEMENTS_FOLDER = PROJECT_ROOT / 'raw_data' / 'settlements'
OUTPUTS_FOLDER = PROJECT_ROOT / 'outputs'
SHAREPOINT_BASE = get_sharepoint_base()

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
    """Process settlement files"""
    if st.session_state.processing:
        return
    
    st.session_state.processing = True
    
    try:
        # Run ETL pipeline
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / 'scripts' / 'main.py')],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode == 0:
            st.success("✅ Processing completed successfully!")
            return True
        else:
            st.error(f"❌ Processing failed: {result.stderr[:500]}")
            return False
    
    except subprocess.TimeoutExpired:
        st.error("⏱️ Processing timed out (took longer than 10 minutes)")
        return False
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
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
            st.dataframe(df, use_container_width=True, hide_index=True)
            
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

