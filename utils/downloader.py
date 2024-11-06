# utils/downloader.py
from pathlib import Path
import httpx
import logging
from .helpers import get_url_hash, save_version_map, load_version_map, get_version_info

logger = logging.getLogger("jswatch")

class JSDownloader:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(exist_ok=True)
        self.version_map = load_version_map(storage_dir)
        self.current_content = {}  # Store current run content

    async def download(self, url: str) -> tuple[str, str, bool]:
        """
        Download JS file and return (old_content, new_content, is_new)
        old_content: Previous version content (or empty for new files)
        new_content: Current version content
        is_new: True if first time download
        """
        filename = get_url_hash(url)
        file_path = self.storage_dir / filename
        version_info = get_version_info(self.version_map, url)

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            new_content = response.text

            # First time seeing this URL
            if not version_info:
                logger.info(f"First time download for {url}")
                self.version_map.append({"url": url, "js": filename})
                save_version_map(self.storage_dir, self.version_map)
                file_path.write_text(new_content)
                return "", new_content, True

            # URL exists, load previous content
            try:
                old_content = file_path.read_text()
                if old_content != new_content:
                    file_path.write_text(new_content)
                    return old_content, new_content, False
                return old_content, new_content, False
            except FileNotFoundError:
                logger.warning(f"File missing for {url}, creating new one")
                file_path.write_text(new_content)
                return "", new_content, True