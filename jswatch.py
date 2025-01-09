import json
import hashlib
import re
import requests
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import difflib
import jsbeautifier
import sys

if "--debug" in sys.argv:
    DEBUG = True
else:
    DEBUG = False

@dataclass
class FileConfig:
    title: str
    is_static: bool
    url: str
    regex_js: Optional[str] = None
    url_to_append: Optional[str] = None
    regex_attribute: Optional[str] = None
    custom_header: Optional[dict[str]] = None
    is_multiple_step: Optional[bool] = False
    next_step: Optional['FileConfig'] = None
    

class FileMonitor:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.files: List[FileConfig] = []
        self.js_dir = Path('./js')
        self.js_dir.mkdir(exist_ok=True)
        self.load_config()
        self.current_js_url = ""
        self.reports = []

    def load_config(self) -> None:
        try:
            with open(self.config_path) as f:
                data = json.load(f)
                self.files = [FileConfig(**item) for item in data]
        except FileNotFoundError:
            print(f"[!] Error: Config file not found at {self.config_path}")

    def find_js_files(self, html_content: str, config: FileConfig) -> List[str]:
        matches = re.findall(config.regex_js, html_content)
        if DEBUG: print(f"[+] Found {len(matches)} matches for {config.title} : \n{'\n'.join(matches)}")
        return [config.url_to_append + match for match in matches]

    def check_js_content(self, js_url: str, regex_attr: str, custom_header: dict) -> Optional[str]:
        content = self.get_with_custom_headers(js_url, custom_header)
        if re.search(regex_attr, content):
            if DEBUG: print(f"[+] Found pattern '{regex_attr}' in {js_url}")
            self.current_js_url = js_url
            return content
        if DEBUG: print(f"[!] Pattern '{regex_attr}' not found in {js_url}")
        return None
    
    def get_with_custom_headers(self, url: str, header: dict[str]) -> str:
        if not header:
            return requests.get(url).text
        return requests.get(url, headers=header).text

    def get_file_content(self, config: FileConfig) -> str:

        ## check if the file is static
        if config.is_static:
            self.current_js_url = config.url
            return self.get_with_custom_headers(config.url, config.custom_header)
        
        if config.is_multiple_step:
            page = self.get_with_custom_headers(config.url, config.custom_header)
            js_urls = self.find_js_files(page, config)
            for js_url in js_urls:
                content = self.check_js_content(js_url, config.regex_attribute,config.custom_header)
                if content:
                    regex_value = re.search(config.regex_attribute, content)
                    if not regex_value:
                        if DEBUG: print(f"[!] Regex not found")
                        return ""
                    if DEBUG: print(f"[+] Found regex value : {regex_value.group(1)}")
                    regex_attribute = regex_value.group(1)
                    config.url = config.next_step["url_to_append"].format(regex_attribute=regex_attribute)
                    if DEBUG: print(f"[+] Get js on this url : {config.url}")
                    content = self.check_js_content(config.url, config.next_step["regex_attribute"],config.custom_header)
                    if content:
                        return content
                    return ""

        page = self.get_with_custom_headers(config.url, config.custom_header)
        js_urls = self.find_js_files(page, config)
        for js_url in js_urls:
            content = self.check_js_content(js_url, config.regex_attribute,config.custom_header)
            if content:
                return content
        return ""

    def calculate_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()

    def report(self, local_content: str, remote_content: str, title: str) -> None:

        local_lines = jsbeautifier.beautify(local_content).splitlines()
        remote_lines = jsbeautifier.beautify(remote_content).splitlines()
        diff = list(difflib.unified_diff(local_lines, remote_lines, n=5))
        
        changed_lines = []
        for line in diff[2:]:  # Skip the first two lines of unified diff output
            if line.startswith('+') or line.startswith('-'):
                changed_lines.extend([line])
        
        report = f"""## JSwatch : new change for `{title}`
url : {self.current_js_url}
time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

```diff
{'\n'.join(f"{line[0]} {line[1:]}" for line in changed_lines)}
```\n"""

        self.reports.append(report)

        # Optional: Save to file
        report_path = self.js_dir / f"{title}_changes.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"\n{report}\n")

    def check_changes(self) -> None:
        for file in self.files:
            if DEBUG : print(f"[+] Processing target    : {file.title}")
            if DEBUG : print(f"[+] url                  : {file.url}")
            if DEBUG : print(f"[+] custom header        : {file.custom_header}")
            local_path = self.js_dir / f"{file.title}.js"
            remote_content = self.get_file_content(file)
            
            if not remote_content:
                if DEBUG : print(f"[!] Warning: Target JS not found for {file.title}")
                continue

            if not local_path.exists():
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(remote_content)
                continue

            with open(local_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
                
            local_hash = self.calculate_hash(local_content)
            remote_hash = self.calculate_hash(remote_content)

            if local_hash != remote_hash:
                self.report(local_content, remote_content, file.title)
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(remote_content)
            else:
                if DEBUG : print(f"[!] No changes detected for {file.title}\n")


def main():
    monitor = FileMonitor('monitor.json')
    monitor.check_changes()
    if len(monitor.reports) > 0:
        for report in monitor.reports:
            print(report)

if __name__ == "__main__":
    main()