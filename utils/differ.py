from pathlib import Path
from difflib import unified_diff
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class DiffResult:
    url: str
    changes: List[str]
    context_lines: List[Tuple[int, str]]

class JSDiffer:
    def compare(self, url: str, old_content: str, new_content: str) -> DiffResult | None:
        # Get the diff with context
        diff = list(unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile='previous',
            tofile='current',
            lineterm='',
            n=3  # Context of 3 lines
        ))
        
        # If there are changes, extract context lines
        if diff:
            # Extract context lines around changes
            context_lines = []
            change_lines = set()
            
            # Find changed lines
            for i, line in enumerate(diff):
                if line.startswith('+') or line.startswith('-'):
                    change_lines.add(i)
            
            # Get context (3 lines before and after changes)
            for i in change_lines:
                for j in range(max(0, i - 3), min(len(diff), i + 4)):
                    if not diff[j].startswith('---') and not diff[j].startswith('+++'):
                        context_lines.append((j, diff[j]))
            
            return DiffResult(
                url=url,
                changes=diff,
                context_lines=context_lines
            )
        
        return None