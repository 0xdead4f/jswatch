import { writeFileSync, appendFileSync } from 'fs';
import { join } from 'path';
import chalk from 'chalk';
import { formatDiff, checkStats } from './diff.js';
import { astDiff } from './ast-diff.js';

/**
 * Generate a markdown report for a detected change.
 */
export function generateReport(monitorId, finalUrl, oldContent, newContent, config) {
  const timestamp = new Date().toISOString().replace('T', ' ').replace(/\.\d+Z$/, '');
  const statsReport = checkStats(oldContent, newContent, config.stats);
  const useAst = config.diffMode === 'ast';

  let changesSection;

  if (useAst) {
    const result = astDiff(oldContent, newContent, { maxAstSize: config.maxAstSize });

    if (result.success) {
      changesSection = buildAstSection(result);
    } else {
      // Fallback to text diff
      const textLines = formatDiff(oldContent, newContent, config.maxLineLength);
      changesSection = `> Note: ${result.fallbackReason}\n\n` + buildTextDiffSection(textLines);
    }
  } else {
    const textLines = formatDiff(oldContent, newContent, config.maxLineLength);
    changesSection = buildTextDiffSection(textLines);
  }

  return `## JSwatch : new change for \`${monitorId}\`
url : ${finalUrl}
time : ${timestamp}

### Stats
${statsReport}

${changesSection}
`;
}

function buildTextDiffSection(lines) {
  return `### Changes
\`\`\`diff
${lines.join('\n')}
\`\`\`
`;
}

function buildAstSection(result) {
  let out = '';

  if (result.summary.length > 0) {
    out += '### AST Summary\n';
    for (const line of result.summary) {
      out += `- ${line}\n`;
    }
    out += '\n';
  }

  out += '### Changes\n\n';

  for (const change of result.changes) {
    const kindLabel = change.kind.replace('export:', '');
    const displayName = change.name.replace(/^(call:|assign:|import:|export:named:)/, '');

    if (change.type === 'added') {
      out += `#### + ADDED ${kindLabel} \`${displayName}\` (line ${change.line})\n`;
      out += '```js\n' + change.source + '\n```\n\n';
    } else if (change.type === 'removed') {
      out += `#### - REMOVED ${kindLabel} \`${displayName}\` (line ${change.line})\n`;
      out += '```js\n' + change.source + '\n```\n\n';
    } else if (change.type === 'modified') {
      out += `#### ~ MODIFIED ${kindLabel} \`${displayName}\` (line ${change.line})\n`;
      out += '```diff\n' + change.diff + '\n```\n\n';
    }
  }

  return out;
}

/**
 * Save a report by appending it to changes.md in the output directory.
 */
export function saveReport(report, outputDir) {
  const reportPath = join(outputDir, 'changes.md');
  appendFileSync(reportPath, `\n${report}\n`, 'utf-8');
}

/**
 * Print a report to console with colors.
 */
export function printReport(report) {
  const lines = report.split('\n');
  for (const line of lines) {
    if (line.startsWith('## JSwatch')) {
      console.log(chalk.cyan.bold(line));
    } else if (line.startsWith('+ ') || line.startsWith('+')) {
      console.log(chalk.green(line));
    } else if (line.startsWith('- ') || line.startsWith('-')) {
      console.log(chalk.red(line));
    } else if (line.startsWith('### ') || line.startsWith('#### ')) {
      console.log(chalk.yellow(line));
    } else {
      console.log(line);
    }
  }
}
