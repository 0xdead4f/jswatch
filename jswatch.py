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
        """Create a new context with updated content"""
        return StepContext(
            url=self.url,
            content=content,
            extracted_values=self.extracted_values.copy(),
            final_url=self.final_url or self.url
        )
    
    def with_extracted(self, key: str, value: str) -> 'StepContext':
        """Create a new context with an extracted value"""
        new_values = self.extracted_values.copy()
        new_values[key] = value
        return StepContext(
            url=self.url,
            content=self.content,
            extracted_values=new_values,
            final_url=self.final_url or self.url
        )
    
    def with_url(self, url: str) -> 'StepContext':
        """Create a new context with updated URL"""
        return StepContext(
            url=url,
            content=self.content,
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
        self.js_dir = Path('./js')
        self.js_dir.mkdir(exist_ok=True)
        self.load_config()
        self.reports = []

    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                monitors = data.get('monitors', [])
                self.files = []
                for item in monitors:
                    steps = [StepConfig(**step) for step in item.get('steps', [])]
                    stats = None
                    if 'stats' in item:
                        stats = [StatConfig(**stat) for stat in item['stats']]
                    config = FileConfig(
                        title=item['title'],
                        steps=steps,
                        headers=item.get('headers'),
                        stats=stats,
                        max_line_length=item.get('max_line_length', 500)
                    )
                    self.files.append(config)
        except FileNotFoundError:
            print(f"[!] Error: Config file not found at {self.config_path}")
        except Exception as e:
            print(f"[!] Error loading config: {e}")

    def resolve_url(self, url_template: str, context: StepContext, step_index: int) -> str:
        """Resolve URL template by replacing placeholders with extracted values"""
        url = url_template
        
        # Replace {step0}, {step1}, etc. with extracted values from previous steps
        for i in range(step_index):
            step_key = f"step{i}"
            if step_key in context.extracted_values:
                url = url.replace(f"{{{step_key}}}", context.extracted_values[step_key])
        
        # Replace {extracted} with the most recent extracted value
        if 'extracted' in context.extracted_values:
            url = url.replace("{extracted}", context.extracted_values['extracted'])
        
        # Replace any remaining placeholders from extracted_values
        for key, value in context.extracted_values.items():
            url = url.replace(f"{{{key}}}", value)
        
        return url

    def fetch_content(self, url: str, headers: Optional[Dict[str, str]]) -> Optional[str]:
        """Fetch content from URL with optional custom headers"""
        try:
            if headers:
                response = requests.get(url, headers=headers)
            else:
                response = requests.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if DEBUG:
                print(f"[!] Error fetching {url}: {e}")
            return None

    def extract_value(self, content: str, regex: str) -> Optional[str]:
        """Extract a value from content using regex"""
        match = re.search(regex, content)
        if match:
            # Return first capture group if available, otherwise full match
            return match.group(1) if match.groups() else match.group(0)
        return None

    def validate_content(self, content: str, regex: str) -> bool:
        """Validate that content matches regex pattern"""
        return bool(re.search(regex, content))

    def execute_step(self, step: StepConfig, context: StepContext, headers: Optional[Dict[str, str]], step_index: int) -> Optional[StepContext]:
        """Execute a single step in the pipeline"""
        # Resolve URL
        url = step.url
        if '{' in url:
            url = self.resolve_url(url, context, step_index)
        
        if DEBUG:
            print(f"[+] Step {step_index}: Fetching {url}")
        
        # Fetch content
        content = self.fetch_content(url, headers)
        if content is None:
            return None
        
        new_context = context.with_url(url).with_content(content)
        
        # Extract value if extract_regex is provided
        if step.extract_regex:
            extracted = self.extract_value(content, step.extract_regex)
            if extracted is None:
                if DEBUG:
                    print(f"[!] Step {step_index}: Extract regex '{step.extract_regex}' did not match")
                return None
            
            if DEBUG:
                print(f"[+] Step {step_index}: Extracted value: {extracted}")
            
            # Store extracted value
            new_context = new_context.with_extracted('extracted', extracted)
            
            # If url_template is provided, resolve it and store the resolved URL
            if step.url_template:
                resolved_url = self.resolve_url(step.url_template, new_context, step_index)
                new_context = new_context.with_url(resolved_url)
                # Store resolved URL in step{i} so {step0} refers to the URL
                new_context = new_context.with_extracted(f'step{step_index}', resolved_url)
                if DEBUG:
                    print(f"[+] Step {step_index}: Resolved URL template to: {resolved_url}")
            else:
                # No url_template, so store extracted value in step{i}
                new_context = new_context.with_extracted(f'step{step_index}', extracted)
        
        # Validate content if validate_regex is provided
        if step.validate_regex:
            if not self.validate_content(content, step.validate_regex):
                if DEBUG:
                    print(f"[!] Step {step_index}: Validation regex '{step.validate_regex}' did not match")
                return None
            if DEBUG:
                print(f"[+] Step {step_index}: Content validated successfully")
        
        return new_context

    def get_file_content(self, config: FileConfig) -> Optional[Tuple[str, str]]:
        """Get file content using pipeline pattern. Returns (content, final_url) or None"""
        if not config.steps:
            return None
        
        # Initialize context with first step URL
        initial_url = config.steps[0].url
        context = StepContext(url=initial_url)
        
        # Execute each step in sequence
        for i, step in enumerate(config.steps):
            context = self.execute_step(step, context, config.headers, i)
            if context is None:
                return None
        
        if context.content is None:
            return None
        
        return (context.content, context.final_url or context.url)

    def calculate_hash(self, content: str) -> str:
        """Calculate MD5 hash of content"""
        return hashlib.md5(content.encode()).hexdigest()

    def check_stats(self, local_content: str, remote_content: str, config: FileConfig) -> str:
        """Check statistics differences between local and remote content"""
        if not config.stats:
            return "Stats Not Specified"
        
        stats_changes = []
        for stat in config.stats:
            local_matches = re.findall(stat.regex, local_content)
            remote_matches = re.findall(stat.regex, remote_content)
            if len(local_matches) != len(remote_matches):
                stats_changes.append(f"{stat.name}: {len(local_matches)} -> {len(remote_matches)}")
        
        if not stats_changes:
            return "No stats changes"
        
        return "\n".join(stats_changes)

    def format_diff(self, local_content: str, remote_content: str, max_length: int) -> List[str]:
        """Format diff between local and remote content"""
        local_lines = jsbeautifier.beautify(local_content).splitlines()
        remote_lines = jsbeautifier.beautify(remote_content).splitlines()
        diff = list(difflib.unified_diff(local_lines, remote_lines, n=5))
        
        # Filter changed lines and exclude lines longer than max_length
        changed_lines = [
            line for line in diff[2:]  # Skip the first two lines of unified diff output
            if (line.startswith('+') or line.startswith('-')) and len(line) <= max_length
        ]
        
        return changed_lines

    def generate_report(self, title: str, final_url: str, local_content: str, remote_content: str, config: FileConfig) -> str:
        """Generate markdown report for changes"""
        stats_report = self.check_stats(local_content, remote_content, config)
        changed_lines = self.format_diff(local_content, remote_content, config.max_line_length)
        
        report = f"""## JSwatch : new change for `{title}`
url : {final_url}
time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### Stats
{stats_report}

### Changes
```diff
{chr(10).join(f"{line[0]} {line[1:]}" for line in changed_lines)}
```\n"""
        
        return report

    def report(self, local_content: str, remote_content: str, title: str, final_url: str, config: FileConfig) -> None:
        """Generate and save report for changes"""
        report = self.generate_report(title, final_url, local_content, remote_content, config)
        self.reports.append(report)
        
        # Save to file
        report_path = self.js_dir / f"{title}_changes.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"\n{report}\n")

    def check_changes(self) -> None:
        """Check for changes in all monitored files"""
        for config in self.files:
            if DEBUG:
                print(f"[+] Processing target: {config.title}")
                if config.headers:
                    print(f"[+] Headers: {config.headers}")
            
            local_path = self.js_dir / f"{config.title}.js"
            result = self.get_file_content(config)
            
            if result is None:
                print(f"[!] Warning: Target file not found for {config.title}")
                continue
            
            remote_content, final_url = result
            
            # Create baseline if it doesn't exist
            if not local_path.exists():
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(remote_content)
                if DEBUG:
                    print(f"[+] Created baseline for {config.title}")
                continue

            # Read local content and compare
            with open(local_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            local_hash = self.calculate_hash(local_content)
            remote_hash = self.calculate_hash(remote_content)

            if local_hash != remote_hash:
                self.report(local_content, remote_content, config.title, final_url, config)
                # Update baseline
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(remote_content)
            else:
                if DEBUG:
                    print(f"[+] No changes detected for {config.title}\n")


def main():
    monitor = FileMonitor('monitor.yaml')
    monitor.check_changes()
    if len(monitor.reports) > 0:
        for report in monitor.reports:
            print(report)


if __name__ == "__main__":
    main()
