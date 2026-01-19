import yaml
import hashlib
import re
import requests
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
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
class StepConfig:
    """Configuration for a single step in the pipeline"""
    url: str
    extract_regex: Optional[str] = None
    url_template: Optional[str] = None
    validate_regex: Optional[str] = None

@dataclass
class StepContext:
    """Immutable context object that carries state between steps"""
    url: str
    content: Optional[str] = None
    extracted_values: Dict[str, str] = field(default_factory=dict)
    final_url: Optional[str] = None
    
    def with_content(self, content: str) -> 'StepContext':
        return StepContext(
            url=self.url, content=content,
            extracted_values=self.extracted_values.copy(),
            final_url=self.final_url or self.url
        )
    
    def with_extracted(self, key: str, value: str) -> 'StepContext':
        new_values = self.extracted_values.copy()
        new_values[key] = value
        return StepContext(
            url=self.url, content=self.content,
            extracted_values=new_values,
            final_url=self.final_url or self.url
        )
    
    def with_url(self, url: str) -> 'StepContext':
        return StepContext(
            url=url, content=self.content,
            extracted_values=self.extracted_values.copy(),
            final_url=url
        )

@dataclass
class StatConfig:
    """Configuration for statistics tracking"""
    name: str
    regex: str

@dataclass
class FileConfig:
    title: str
    steps: List[StepConfig]
    headers: Optional[Dict[str, str]] = None
    stats: Optional[List[StatConfig]] = None
    max_line_length: Optional[int] = 500

class FileMonitor:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.files: List[FileConfig] = []
        self.webhook_url: Optional[str] = None # Store webhook URL
        self.js_dir = Path('./js')
        self.js_dir.mkdir(exist_ok=True)
        self.load_config()
        self.reports = []

    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.webhook_url = data.get('discord_webhook') # Get webhook from root of YAML
                monitors = data.get('monitors', [])
                self.files = []
                for item in monitors:
                    steps = [StepConfig(**step) for step in item.get('steps', [])]
                    stats = [StatConfig(**stat) for stat in item.get('stats', [])] if 'stats' in item else None
                    config = FileConfig(
                        title=item['title'],
                        steps=steps,
                        headers=item.get('headers'),
                        stats=stats,
                        max_line_length=item.get('max_line_length', 500)
                    )
                    self.files.append(config)
        except Exception as e:
            print(f"[!] Error loading config: {e}")

    def send_discord_notification(self, report: str):
        """Send the report to Discord via Webhook"""
        if not self.webhook_url:
            if DEBUG: print("[!] No Discord webhook configured.")
            return

        # Discord has a 2000 character limit per message
        if len(report) > 1950:
            report = report[:1900] + "\n... [Diff truncated due to length] ...\n```"

        payload = {"content": report}
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            if DEBUG: print("[+] Discord notification sent.")
        except Exception as e:
            print(f"[!] Failed to send Discord notification: {e}")

    def resolve_url(self, url_template: str, context: StepContext, step_index: int) -> str:
        url = url_template
        for i in range(step_index):
            step_key = f"step{i}"
            if step_key in context.extracted_values:
                url = url.replace(f"{{{step_key}}}", context.extracted_values[step_key])
        if 'extracted' in context.extracted_values:
            url = url.replace("{extracted}", context.extracted_values['extracted'])
        for key, value in context.extracted_values.items():
            url = url.replace(f"{{{key}}}", value)
        return url

    def fetch_content(self, url: str, headers: Optional[Dict[str, str]]) -> Optional[str]:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if DEBUG: print(f"[!] Error fetching {url}: {e}")
            return None

    def extract_value(self, content: str, regex: str) -> Optional[str]:
        match = re.search(regex, content)
        if match:
            return match.group(1) if match.groups() else match.group(0)
        return None

    def validate_content(self, content: str, regex: str) -> bool:
        return bool(re.search(regex, content))

    def execute_step(self, step: StepConfig, context: StepContext, headers: Optional[Dict[str, str]], step_index: int) -> Optional[StepContext]:
        url = step.url
        if '{' in url:
            url = self.resolve_url(url, context, step_index)
        
        content = self.fetch_content(url, headers)
        if content is None: return None
        
        new_context = context.with_url(url).with_content(content)
        
        if step.extract_regex:
            extracted = self.extract_value(content, step.extract_regex)
            if extracted is None: return None
            new_context = new_context.with_extracted('extracted', extracted)
            
            if step.url_template:
                resolved_url = self.resolve_url(step.url_template, new_context, step_index)
                new_context = new_context.with_url(resolved_url)
                new_context = new_context.with_extracted(f'step{step_index}', resolved_url)
            else:
                new_context = new_context.with_extracted(f'step{step_index}', extracted)
        
        if step.validate_regex and not self.validate_content(content, step.validate_regex):
            return None
        
        return new_context

    def get_file_content(self, config: FileConfig) -> Optional[Tuple[str, str]]:
        if not config.steps: return None
        context = StepContext(url=config.steps[0].url)
        for i, step in enumerate(config.steps):
            context = self.execute_step(step, context, config.headers, i)
            if context is None: return None
        return (context.content, context.final_url or context.url)

    def calculate_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()

    def check_stats(self, local_content: str, remote_content: str, config: FileConfig) -> str:
        if not config.stats: return "Stats Not Specified"
        stats_changes = []
        for stat in config.stats:
            local_matches = re.findall(stat.regex, local_content)
            remote_matches = re.findall(stat.regex, remote_content)
            if len(local_matches) != len(remote_matches):
                stats_changes.append(f"{stat.name}: {len(local_matches)} -> {len(remote_matches)}")
        return "\n".join(stats_changes) if stats_changes else "No stats changes"

    def format_diff(self, local_content: str, remote_content: str, max_length: int) -> List[str]:
        local_lines = jsbeautifier.beautify(local_content).splitlines()
        remote_lines = jsbeautifier.beautify(remote_content).splitlines()
        diff = list(difflib.unified_diff(local_lines, remote_lines, n=3))
        changed_lines = [
            line for line in diff[2:] 
            if (line.startswith('+') or line.startswith('-')) and len(line) <= max_length
        ]
        return changed_lines

    def generate_report(self, title: str, final_url: str, local_content: str, remote_content: str, config: FileConfig) -> str:
        stats_report = self.check_stats(local_content, remote_content, config)
        changed_lines = self.format_diff(local_content, remote_content, config.max_line_length)
        
        diff_text = chr(10).join(f"{line[0]} {line[1:]}" for line in changed_lines)
        
        report = f"## JSwatch : new change for `{title}`\n"
        report += f"**URL**: {final_url}\n"
        report += f"**Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"### Stats\n{stats_report}\n\n"
        report += f"### Changes\n```diff\n{diff_text}\n```"
        return report

    def report(self, local_content: str, remote_content: str, title: str, final_url: str, config: FileConfig) -> None:
        report = self.generate_report(title, final_url, local_content, remote_content, config)
        self.reports.append(report)
        
        # 1. Save to local file
        report_path = self.js_dir / f"{title}_changes.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"\n{report}\n")

        # 2. Send to Discord
        self.send_discord_notification(report)

    def check_changes(self) -> None:
        for config in self.files:
            if DEBUG: print(f"[+] Processing: {config.title}")
            local_path = self.js_dir / f"{config.title}.js"
            result = self.get_file_content(config)
            
            if result is None:
                continue
            
            remote_content, final_url = result
            if not local_path.exists():
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(remote_content)
                continue

            with open(local_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            if self.calculate_hash(local_content) != self.calculate_hash(remote_content):
                self.report(local_content, remote_content, config.title, final_url, config)
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(remote_content)

def main():
    monitor = FileMonitor('monitor.yaml')
    monitor.check_changes()
    if not monitor.reports and DEBUG:
        print("[+] No changes found in any target.")

if __name__ == "__main__":
    main()
