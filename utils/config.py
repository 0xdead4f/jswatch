from pathlib import Path
import tomli
from typing import NamedTuple

class Config(NamedTuple):
    storage_dir: Path
    check_interval: int
    log_level: str
    report_format: str  # 'html' or 'markdown'
    report_file: Path

def load_config(config_path: Path) -> Config:
    config_data = tomli.loads(config_path.read_text())
    return Config(
        storage_dir=Path(config_data["storage_dir"]),
        check_interval=config_data["check_interval_minutes"],
        log_level=config_data.get("log_level", "INFO"),
        report_format=config_data.get("report_format", "markdown"),
        report_file=Path(config_data.get("report_file", "output.md"))
    )