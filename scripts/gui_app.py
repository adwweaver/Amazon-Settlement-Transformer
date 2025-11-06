#!/usr/bin/env python3
"""
Simple GUI Application for Amazon Settlement Processing

A user-friendly interface for non-technical users to:
- Process settlement files
- Post to Zoho Books
- View processing status
- Monitor the folder

Usage:
    python scripts/gui_app.py
"""

import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path
import threading
import subprocess
import queue
from datetime import datetime
import os

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class SettlementProcessorGUI:
    """Main GUI Application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Amazon Settlement Processor")
        self.root.geometry("800x600")
        
        # Project paths
        self.project_root = Path(__file__).parent.parent
        self.settlements_folder = self.project_root / 'raw_data' / 'settlements'
        self.outputs_folder = self.project_root / 'outputs'
        
        # Processing state
        self.is_processing = False
        self.watchdog_running = False
        self.observer = None
        
        # Create UI
        self._create_ui()
        
        # Check for existing files
        self._check_existing_files()
    
    def _create_ui(self):
        """Create the user interface"""
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Amazon Settlement Processor", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Folder selection
        ttk.Label(main_frame, text="Settlement Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.folder_label = ttk.Label(main_frame, text=str(self.settlements_folder), 
                                      foreground='blue')
        self.folder_label.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(main_frame, text="Browse", command=self._browse_folder).grid(row=1, column=2)
        
        # File list
        ttk.Label(main_frame, text="Settlement Files:").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=(10, 5))
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.file_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.file_listbox.yview)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.process_button = ttk.Button(button_frame, text="Process Files", 
                                         command=self._process_files)
        self.process_button.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = ttk.Button(button_frame, text="Refresh List", 
                                         command=self._refresh_file_list)
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        self.watchdog_button = ttk.Button(button_frame, text="Start Auto-Watch", 
                                          command=self._toggle_watchdog)
        self.watchdog_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Open Outputs", 
                  command=self._open_outputs).pack(side=tk.LEFT, padx=5)
        
        # Status/Log area
        ttk.Label(main_frame, text="Status & Logs:").grid(row=4, column=0, sticky=(tk.W, tk.N), pady=(10, 5))
        
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=4, column=1, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN)
        self.status_label.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Configure grid weights
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(4, weight=1)
    
    def _browse_folder(self):
        """Browse for settlement folder"""
        folder = filedialog.askdirectory(initialdir=str(self.settlements_folder))
        if folder:
            self.settlements_folder = Path(folder)
            self.folder_label.config(text=str(self.settlements_folder))
            self._refresh_file_list()
    
    def _check_existing_files(self):
        """Check for existing files on startup"""
        self._refresh_file_list()
        if self.file_listbox.size() > 0:
            self.log("Found existing settlement files. Click 'Process Files' to process them.")
    
    def _refresh_file_list(self):
        """Refresh the file list"""
        self.file_listbox.delete(0, tk.END)
        
        if not self.settlements_folder.exists():
            self.log(f"Folder not found: {self.settlements_folder}", level="error")
            return
        
        files = list(self.settlements_folder.glob('*.txt'))
        
        if files:
            for file_path in sorted(files):
                self.file_listbox.insert(tk.END, file_path.name)
            self.log(f"Found {len(files)} settlement file(s)")
        else:
            self.log("No settlement files found")
    
    def _process_files(self):
        """Process settlement files"""
        if self.is_processing:
            messagebox.showwarning("Processing", "Already processing files. Please wait.")
            return
        
        self.is_processing = True
        self.process_button.config(state='disabled')
        self.status_label.config(text="Processing...")
        
        # Run in separate thread
        thread = threading.Thread(target=self._run_processing)
        thread.daemon = True
        thread.start()
    
    def _run_processing(self):
        """Run the processing in background thread"""
        try:
            self.log("="*60)
            self.log(f"Starting ETL Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.log("="*60)
            
            # Run main.py
            result = subprocess.run(
                [sys.executable, str(self.project_root / 'scripts' / 'main.py')],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                self.log("Processing completed successfully!")
                self.log("Check the outputs/ folder for generated files.")
                
                # Show success message
                self.root.after(0, lambda: messagebox.showinfo(
                    "Success", 
                    "Processing completed successfully!\n\nCheck the outputs/ folder for generated files."
                ))
            else:
                self.log("Processing failed!", level="error")
                self.log(f"Error: {result.stderr}", level="error")
                
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Processing failed!\n\nCheck the logs for details.\n\nError: {result.stderr[:200]}"
                ))
        
        except subprocess.TimeoutExpired:
            self.log("Processing timed out (took longer than 10 minutes)", level="error")
            self.root.after(0, lambda: messagebox.showerror(
                "Timeout",
                "Processing took too long and was cancelled."
            ))
        except Exception as e:
            self.log(f"Error during processing: {e}", level="error")
            self.root.after(0, lambda: messagebox.showerror(
                "Error",
                f"An error occurred: {e}"
            ))
        finally:
            self.is_processing = False
            self.root.after(0, self._processing_complete)
    
    def _processing_complete(self):
        """Called when processing is complete"""
        self.process_button.config(state='normal')
        self.status_label.config(text="Ready")
        self._refresh_file_list()
    
    def _toggle_watchdog(self):
        """Toggle file watcher"""
        if not WATCHDOG_AVAILABLE:
            messagebox.showwarning(
                "Not Available",
                "File watching requires the 'watchdog' package.\n\n"
                "Install it with: pip install watchdog"
            )
            return
        
        if self.watchdog_running:
            self._stop_watchdog()
        else:
            self._start_watchdog()
    
    def _start_watchdog(self):
        """Start file watcher"""
        if not WATCHDOG_AVAILABLE:
            return
        
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class SimpleHandler(FileSystemEventHandler):
                def __init__(self, callback):
                    self.callback = callback
                
                def on_created(self, event):
                    if not event.is_directory and event.src_path.endswith('.txt'):
                        self.callback(event.src_path)
            
            self.observer = Observer()
            handler = SimpleHandler(self._on_file_created)
            self.observer.schedule(handler, str(self.settlements_folder), recursive=False)
            self.observer.start()
            
            self.watchdog_running = True
            self.watchdog_button.config(text="Stop Auto-Watch")
            self.log("Auto-watch started. New files will be processed automatically.")
            self.status_label.config(text="Auto-Watch: Active")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start file watcher: {e}")
    
    def _stop_watchdog(self):
        """Stop file watcher"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self.watchdog_running = False
        self.watchdog_button.config(text="Start Auto-Watch")
        self.log("Auto-watch stopped.")
        self.status_label.config(text="Auto-Watch: Stopped")
    
    def _on_file_created(self, file_path):
        """Called when a new file is detected"""
        self.log(f"New file detected: {Path(file_path).name}")
        self.root.after(0, self._refresh_file_list)
        
        # Auto-process if not already processing
        if not self.is_processing:
            self.root.after(0, self._process_files)
    
    def _open_outputs(self):
        """Open outputs folder"""
        if self.outputs_folder.exists():
            os.startfile(str(self.outputs_folder))
        else:
            messagebox.showwarning("Not Found", "Outputs folder not found.")
    
    def log(self, message, level="info"):
        """Add message to log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        
        # Color code by level
        if level == "error":
            self.log_text.tag_add("error", f"end-{len(formatted_message)}c", "end-1c")
            self.log_text.tag_config("error", foreground="red")
        elif level == "success":
            self.log_text.tag_add("success", f"end-{len(formatted_message)}c", "end-1c")
            self.log_text.tag_config("success", foreground="green")
    
    def on_closing(self):
        """Handle window closing"""
        if self.watchdog_running:
            self._stop_watchdog()
        self.root.destroy()


def main():
    """Main function"""
    root = tk.Tk()
    app = SettlementProcessorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()



