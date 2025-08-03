#!/usr/bin/env python3
"""
PDF File Watcher - Automatically copies PDF files to aftis-parser container
Monitors a directory for new PDF files and copies them to the container inbox

Usage: python watch-pdfs.py [watch_directory]
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class PDFHandler(FileSystemEventHandler):
    def __init__(self, container_name="aftis-parser", container_path="/srv/aftis/inbox/"):
        self.container_name = container_name
        self.container_path = container_path
        
    def is_container_running(self):
        """Check if the container is running"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            return self.container_name in result.stdout.split('\n')
        except subprocess.CalledProcessError:
            return False
    
    def copy_to_container(self, file_path):
        """Copy file to container"""
        try:
            filename = os.path.basename(file_path)
            target_path = f"{self.container_name}:{self.container_path}{filename}"
            
            subprocess.run(
                ["docker", "cp", file_path, target_path],
                check=True, capture_output=True
            )
            print(f"✓ Copied {filename} to container")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to copy {filename}: {e}")
            return False
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = event.src_path
        if not file_path.lower().endswith('.pdf'):
            return
            
        # Wait a moment to ensure file is fully written
        time.sleep(1)
        
        if not os.path.exists(file_path):
            return
            
        print(f"New PDF detected: {os.path.basename(file_path)}")
        
        if not self.is_container_running():
            print(f"✗ Container {self.container_name} is not running")
            return
            
        self.copy_to_container(file_path)
    
    def on_moved(self, event):
        """Handle file move events (treats as new file)"""
        if event.is_directory:
            return
            
        if event.dest_path.lower().endswith('.pdf'):
            # Treat moved PDF as new file
            event.src_path = event.dest_path
            self.on_created(event)

def main():
    watch_dir = sys.argv[1] if len(sys.argv) > 1 else "./statements"
    
    if not os.path.exists(watch_dir):
        print(f"Error: Directory '{watch_dir}' does not exist")
        sys.exit(1)
    
    print(f"Watching directory: {os.path.abspath(watch_dir)}")
    print("Monitoring for PDF files...")
    print("Press Ctrl+C to stop")
    
    event_handler = PDFHandler()
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=True)
    
    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping file watcher...")
        observer.stop()
    
    observer.join()
    print("File watcher stopped")

if __name__ == "__main__":
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("Error: watchdog library not installed")
        print("Install with: pip install watchdog")
        sys.exit(1)
    
    main()