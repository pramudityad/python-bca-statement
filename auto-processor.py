#!/usr/bin/env python3
"""
AFTIS Auto-Processor
Monitors inbox directory and automatically processes PDF files
Deletes successfully processed files, moves failed files to failed/ directory
"""

import os
import time
import json
import logging
import requests
import shutil
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/srv/aftis/auto-processor.log')
    ]
)
logger = logging.getLogger(__name__)

class PDFProcessor(FileSystemEventHandler):
    def __init__(self):
        self.parser_url = os.getenv('PARSER_URL', "http://parser:8080")
        self.inbox_path = "/srv/aftis/inbox"
        self.failed_path = "/srv/aftis/failed"
        self.processing_files = set()  # Track files currently being processed
        
        # Ensure directories exist
        os.makedirs(self.failed_path, exist_ok=True)
        
        # Environment configuration
        self.auto_delete = os.getenv('AUTO_DELETE_PDFS', 'true').lower() == 'true'
        self.process_delay = int(os.getenv('PROCESS_DELAY_SECONDS', '2'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.scan_interval = int(os.getenv('SCAN_INTERVAL_SECONDS', '60'))  # Periodic scan every 60s
        
        logger.info(f"Auto-processor initialized:")
        logger.info(f"  - Auto delete: {self.auto_delete}")
        logger.info(f"  - Process delay: {self.process_delay}s")
        logger.info(f"  - Max retries: {self.max_retries}")
        logger.info(f"  - Scan interval: {self.scan_interval}s")
    
    def wait_for_file_stable(self, file_path, timeout=10):
        """Wait for file to be completely written"""
        initial_size = -1
        stable_count = 0
        
        for _ in range(timeout):
            try:
                current_size = os.path.getsize(file_path)
                if current_size == initial_size:
                    stable_count += 1
                    if stable_count >= 2:  # File size stable for 2 seconds
                        return True
                else:
                    stable_count = 0
                    initial_size = current_size
                time.sleep(1)
            except (OSError, FileNotFoundError):
                time.sleep(1)
                continue
        
        return False
    
    
    def process_pdf(self, file_path):
        """Process a PDF file through the parser API"""
        filename = os.path.basename(file_path)
        
        try:
            # Check if parser service is available before processing
            logger.debug(f"Checking parser health before processing {filename}")
            health_response = requests.get(f"{self.parser_url}/health", timeout=5)
            if health_response.status_code != 200:
                logger.error(f"Parser service unhealthy (status {health_response.status_code}), skipping {filename}")
                return False
            
            logger.debug(f"Parser healthy, processing {filename}")
            
            # Call parse-and-store endpoint
            payload = {"pdf_path": file_path}
            logger.debug(f"Calling {self.parser_url}/parse-and-store with payload: {payload}")
            
            response = requests.post(
                f"{self.parser_url}/parse-and-store",
                json=payload,
                timeout=30
            )
            
            logger.debug(f"Parse response: {response.status_code} - {response.text[:200]}...")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    parsed_count = result.get('parsed_count', 0)
                    db_stored = result.get('database_stored', False)
                    
                    logger.info(f"✓ Processed {filename}: {parsed_count} transactions" + 
                               (", stored in DB" if db_stored else ", DB storage failed"))
                    return True
                else:
                    logger.error(f"✗ Processing failed for {filename}: {result}")
                    return False
            else:
                logger.error(f"✗ API call failed for {filename}: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except requests.Timeout as e:
            logger.error(f"✗ Timeout error processing {filename}: {e}")
            return False
        except requests.ConnectionError as e:
            logger.error(f"✗ Connection error processing {filename}: {e}")
            return False
        except requests.RequestException as e:
            logger.error(f"✗ Network error processing {filename}: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error processing {filename}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def handle_successful_processing(self, file_path):
        """Handle successfully processed file"""
        filename = os.path.basename(file_path)
        
        if self.auto_delete:
            try:
                os.remove(file_path)
                logger.info(f"🗑️  Deleted processed file: {filename}")
            except OSError as e:
                logger.error(f"Failed to delete {filename}: {e}")
        else:
            logger.info(f"✓ Processing complete: {filename} (auto-delete disabled)")
    
    def handle_failed_processing(self, file_path):
        """Move failed file to failed directory"""
        filename = os.path.basename(file_path)
        failed_file_path = os.path.join(self.failed_path, filename)
        
        try:
            # Add timestamp to avoid conflicts
            if os.path.exists(failed_file_path):
                base, ext = os.path.splitext(filename)
                timestamp = int(time.time())
                failed_file_path = os.path.join(self.failed_path, f"{base}_{timestamp}{ext}")
            
            shutil.move(file_path, failed_file_path)
            logger.warning(f"📁 Moved failed file to: {failed_file_path}")
        except OSError as e:
            logger.error(f"Failed to move {filename} to failed directory: {e}")
    
    def process_file_with_retries(self, file_path):
        """Process file with retry logic"""
        filename = os.path.basename(file_path)
        
        if filename in self.processing_files:
            logger.debug(f"Already processing {filename}, skipping")
            return
        
        self.processing_files.add(filename)
        
        try:
            logger.info(f"🔄 Processing: {filename}")
            
            for attempt in range(1, self.max_retries + 1):
                if attempt > 1:
                    logger.info(f"Retry {attempt}/{self.max_retries} for {filename}")
                
                success = self.process_pdf(file_path)
                
                if success:
                    self.handle_successful_processing(file_path)
                    return
                
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            # All retries failed
            logger.error(f"All retries failed for {filename}")
            self.handle_failed_processing(file_path)
            
        finally:
            self.processing_files.discard(filename)
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if not file_path.lower().endswith('.pdf'):
            return
        
        filename = os.path.basename(file_path)
        logger.info(f"📄 New PDF detected: {filename}")
        
        # Wait for processing delay
        time.sleep(self.process_delay)
        
        # Wait for file to be stable (fully written)
        if not self.wait_for_file_stable(file_path):
            logger.warning(f"File {filename} may not be fully written, processing anyway")
        
        # Process the file
        self.process_file_with_retries(file_path)
    
    def scan_for_missed_files(self):
        """Periodic scan for files that might have been missed"""
        try:
            if not os.path.exists(self.inbox_path):
                return
            
            existing_files = [f for f in os.listdir(self.inbox_path) if f.lower().endswith('.pdf')]
            
            if existing_files:
                logger.info(f"🔍 Periodic scan found {len(existing_files)} unprocessed files")
                for filename in existing_files:
                    file_path = os.path.join(self.inbox_path, filename)
                    logger.info(f"📄 Processing missed file: {filename}")
                    self.process_file_with_retries(file_path)
        except Exception as e:
            logger.error(f"Error during periodic scan: {e}")
    
    def start_periodic_scanner(self):
        """Start periodic scanning in background thread"""
        def scanner_loop():
            while True:
                time.sleep(self.scan_interval)
                self.scan_for_missed_files()
        
        scanner_thread = threading.Thread(target=scanner_loop, daemon=True)
        scanner_thread.start()
        logger.info(f"📡 Started periodic scanner (every {self.scan_interval}s)")
    
    def on_moved(self, event):
        """Handle file move events (treat as new file)"""
        if event.is_directory:
            return
        
        if event.dest_path.lower().endswith('.pdf'):
            # Treat moved PDF as new file
            event.src_path = event.dest_path
            self.on_created(event)

def process_existing_files():
    """Process any existing files in inbox on startup"""
    inbox_path = "/srv/aftis/inbox"
    processor = PDFProcessor()
    
    if not os.path.exists(inbox_path):
        logger.info("Inbox directory does not exist, creating it")
        os.makedirs(inbox_path, exist_ok=True)
        return
    
    existing_files = [f for f in os.listdir(inbox_path) if f.lower().endswith('.pdf')]
    
    if existing_files:
        logger.info(f"Found {len(existing_files)} existing PDF files, processing...")
        for filename in existing_files:
            file_path = os.path.join(inbox_path, filename)
            processor.process_file_with_retries(file_path)
    else:
        logger.info("No existing PDF files found in inbox")

def main():
    """Main function to start the auto-processor"""
    logger.info("🚀 AFTIS Auto-Processor starting...")
    
    # Process any existing files
    process_existing_files()
    
    # Start watching for new files
    inbox_path = "/srv/aftis/inbox"
    event_handler = PDFProcessor()
    observer = Observer()
    observer.schedule(event_handler, inbox_path, recursive=False)
    
    try:
        observer.start()
        logger.info(f"👀 Watching {inbox_path} for new PDF files...")
        
        # Start periodic scanner for missed files
        event_handler.start_periodic_scanner()
        
        logger.info("Press Ctrl+C to stop")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping auto-processor...")
        observer.stop()
    
    observer.join()
    logger.info("✅ Auto-processor stopped")

if __name__ == "__main__":
    try:
        import requests
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError as e:
        logger.error(f"Missing required dependencies: {e}")
        logger.error("Install with: pip install requests watchdog")
        exit(1)
    
    main()