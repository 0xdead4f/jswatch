import crypto from 'crypto';
import jsBeautify from 'js-beautify';
const { js_beautify } = jsBeautify;
import { diffLines } from 'diff';

/**
 * Calculate MD5 hash of content string.
 */
export function calculateHash(content) {
  return crypto.createHash('md5').update(content).digest('hex');
}

/**
 * Generate a filtered diff of old vs new content.
 * Beautifies both sides, diffs, and returns only +/- lines within maxLineLength.
 */
export function formatDiff(oldContent, newContent, maxLineLength = 500) {
  const oldLines = js_beautify(oldContent).split('\n');
  const newLines = js_beautify(newContent).split('\n');

  const changes = diffLines(oldLines.join('\n'), newLines.join('\n'));

  const result = [];
  for (const part of changes) {
    if (!part.added && !part.removed) continue;

    const prefix = part.added ? '+' : '-';
    const lines = part.value.split('\n');
    for (const line of lines) {
      if (line === '') continue;
      const formatted = `${prefix} ${line}`;
      if (formatted.length <= maxLineLength) {
        result.push(formatted);
      }
    }
  }

  return result;
}

/**
 * Check regex-based stats between old and new content.
 * Returns a string report of stat changes.
 */
export function checkStats(oldContent, newContent, stats) {
  if (!stats) return 'Stats Not Specified';

  const changes = [];
  for (const stat of stats) {
    const oldCount = (oldContent.match(new RegExp(stat.regex, 'g')) || []).length;
    const newCount = (newContent.match(new RegExp(stat.regex, 'g')) || []).length;
    if (oldCount !== newCount) {
      changes.push(`${stat.name}: ${oldCount} -> ${newCount}`);
    }
  }

  return changes.length > 0 ? changes.join('\n') : 'No stats changes';
}
