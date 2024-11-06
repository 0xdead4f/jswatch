# utils/reporter.py
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
from utils.differ import DiffResult

@dataclass
class Report:
    timestamp: datetime
    url: str
    status: str
    changes: List[str]

class Reporter:
    def __init__(self, report_file: Path, format_type: str = 'markdown'):
        self.report_file = report_file
        self.format_type = format_type.lower()
        self.reports: List[Report] = []
        self.total_changes = 0
        self.last_update = None

    def generate_report(self, url: str, diff_result: Optional[DiffResult], status: str):
        self.last_update = datetime.now()
        report = Report(
            timestamp=self.last_update,
            url=url,
            status=status,
            changes=diff_result.changes if diff_result else []
        )
        self.reports.append(report)
        
        if status == "Changed":
            self.total_changes += 1
        
        self._write_report()

    def _format_diff_html(self, changes: List[str]) -> str:
        if not changes:
            return '<div class="no-changes">No changes detected</div>'
        
        formatted_lines = []
        for line in changes:
            css_class = ""
            if line.startswith('+'):
                css_class = "diff-add"
            elif line.startswith('-'):
                css_class = "diff-remove"
            else:
                css_class = "diff-context"
            
            formatted_lines.append(f'<div class="diff-line {css_class}">{line}</div>')
        
        return f'<div class="diff-container"><code class="diff">{"".join(formatted_lines)}</code></div>'

    def _write_report(self):
        if self.format_type == 'markdown':
            self._write_markdown_report()
        else:
            self._write_html_report()

    def _write_html_report(self):
        content = []
        unique_urls = len(set(r.url for r in self.reports))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_check = self.last_update.strftime("%H:%M:%S") if self.last_update else "N/A"

        # Generate report items
        for report in reversed(self.reports):
            status_class = {
                'Changed': 'changed',
                'Unchanged': 'unchanged',
                'Initial Download': 'initial'
            }.get(report.status, '')

            content.append(f'''
                <div class="report-item">
                    <div class="report-header">
                        <h3>{report.url}</h3>
                        <span class="badge badge-{status_class}">{report.status}</span>
                    </div>
                    <div class="report-time">
                        <span>{report.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</span>
                    </div>
                    {self._format_diff_html(report.changes)}
                </div>
            ''')

        # Construct the full HTML
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JSWatch Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #f8fafc;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            text-transform: uppercase;
            color: #64748b;
        }}
        .stat-card p {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: #1e293b;
        }}
        .report-item {{
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .report-header {{
            background: #f8fafc;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #e2e8f0;
        }}
        .report-header h3 {{
            margin: 0;
            font-size: 16px;
            color: #1e293b;
        }}
        .report-time {{
            padding: 10px 15px;
            color: #64748b;
            font-size: 14px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        .badge-changed {{
            background: #fff7ed;
            color: #c2410c;
        }}
        .badge-unchanged {{
            background: #f0fdf4;
            color: #15803d;
        }}
        .badge-initial {{
            background: #eff6ff;
            color: #1d4ed8;
        }}
        .diff-container {{
            padding: 15px;
            background: #f8fafc;
            overflow-x: auto;
        }}
        .diff {{
            font-family: monospace;
            white-space: pre;
            margin: 0;
            font-size: 14px;
        }}
        .diff-line {{
            padding: 2px 0;
        }}
        .diff-add {{
            background: #dcfce7;
            color: #166534;
        }}
        .diff-remove {{
            background: #fee2e2;
            color: #991b1b;
        }}
        .diff-context {{
            color: #64748b;
        }}
        .no-changes {{
            padding: 20px;
            text-align: center;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>JSWatch Report</h1>
            <p>Generated on: {timestamp}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>URLs Monitored</h3>
                <p>{unique_urls}</p>
            </div>
            <div class="stat-card">
                <h3>Changes Detected</h3>
                <p>{self.total_changes}</p>
            </div>
            <div class="stat-card">
                <h3>Last Check</h3>
                <p>{last_check}</p>
            </div>
        </div>

        <div class="reports">
            {"".join(content)}
        </div>
    </div>
</body>
</html>'''

        self.report_file.write_text(html)

    def _write_markdown_report(self):
        content = []
        for report in reversed(self.reports):
            content.append(f"## {report.url}")
            content.append(f"Status: {report.status}")
            content.append(f"Time: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if report.changes:
                content.append("\n```diff")
                content.extend(report.changes)
                content.append("```\n")
            
            content.append("---\n")

        md_report = f'''# JSWatch Report
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{"".join(content)}'''

        self.report_file.write_text(md_report)