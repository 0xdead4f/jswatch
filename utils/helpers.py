# utils/helpers.py
from pathlib import Path
import json
import hashlib

def load_urls(urls_file: Path) -> list[str]:
    return [url.strip() for url in urls_file.read_text().splitlines() if url.strip()]

def get_url_hash(url: str) -> str:
    """Generate filename based on URL hash"""
    return f"{hashlib.md5(url.encode()).hexdigest()}.js"

def save_version_map(storage_dir: Path, version_map: list):
    """Save version mapping to a JSON file"""
    with (storage_dir / "versions.json").open("w") as f:
        json.dump(version_map, f, indent=2)

def load_version_map(storage_dir: Path) -> list:
    """Load version mapping from JSON file"""
    try:
        with (storage_dir / "versions.json").open("r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_version_info(version_map: list, url: str) -> dict | None:
    """Get version info for a URL"""
    return next((item for item in version_map if item["url"] == url), None)