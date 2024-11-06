import asyncio
import logging
from pathlib import Path
from datetime import datetime
import sys
import signal
from typing import Set

from utils.downloader import JSDownloader
from utils.differ import JSDiffer
from utils.config import load_config
from utils.helpers import load_urls
from utils.reporter import Reporter

class JSWatch:
    def __init__(self):
        self.config = load_config(Path("config.conf"))
        self.setup_logging()
        
        self.urls = load_urls(Path("monitor.list"))
        self.storage_dir = Path(self.config.storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        self.downloader = JSDownloader(self.storage_dir)
        self.differ = JSDiffer() 
        self.reporter = Reporter(self.config.report_file, self.config.report_format)
        
        self.running = True
        self.processed_urls: Set[str] = set()

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("jswatch.log")
            ]
        )
        self.logger = logging.getLogger("jswatch")

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown on signals"""
        self.logger.info("Received shutdown signal, cleaning up...")
        self.running = False

    async def process_url(self, url: str) -> None:
        """Process a single URL"""
        try:
            self.logger.info(f"Checking {url}")
            old_content, new_content, is_new = await self.downloader.download(url)
            
            if is_new:
                self.logger.info(f"Initial download of {url}")
                self.reporter.generate_report(url, None, "Initial Download")
            elif old_content != new_content:
                diff_result = self.differ.compare(url, old_content, new_content)
                self.logger.info(f"Changes detected in {url}")
                self.reporter.generate_report(url, diff_result, "Changed")
            else:
                self.logger.debug(f"No changes in {url}")
                
            self.processed_urls.add(url)
            
        except Exception as e:
            self.logger.error(f"Error processing {url}: {e}")

    async def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Process all URLs
                for url in self.urls:
                    if not self.running:
                        break
                    await self.process_url(url)
                
                # Wait for next check interval
                if self.running:
                    self.logger.info(f"Waiting {self.config.check_interval} minutes until next check...")
                    await asyncio.sleep(self.config.check_interval * 60)
                
            except Exception as e:
                self.logger.error(f"Unexpected error in monitor loop: {e}")
                if self.running:
                    await asyncio.sleep(60)  # Wait before retry

    async def run(self):
        # Start the monitoring process
        self.logger.info("Starting JSWatch...")
        self.logger.info(f"Monitoring {len(self.urls)} URLs with {self.config.check_interval} minute intervals")
        
        try:
            await self.monitor_loop()
        finally:
            # Cleanup
            self.logger.info("JSWatch stopped")
            if self.processed_urls:
                self.logger.info(f"Processed {len(self.processed_urls)} URLs")

def main():
    """Entry point"""
    try:
        jswatch = JSWatch()
        asyncio.run(jswatch.run())
    except KeyboardInterrupt:
        print("\nJSWatch stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()