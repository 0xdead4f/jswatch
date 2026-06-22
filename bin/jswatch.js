#!/usr/bin/env node

import { program } from 'commander';
import { run } from '../src/watcher.js';

// Commander calls a coercion fn as fn(value, previous), where previous is the
// default (300). Passing bare parseInt makes it parseInt(value, 300) - 300 is
// read as the radix (invalid, must be 2..36) and returns NaN, so e.g. -i 86400
// silently becomes NaN and the watch loop never waits. Parse with base 10 and
// reject non-positive / non-numeric input.
function parseInterval(value) {
  const n = parseInt(value, 10);
  if (!Number.isFinite(n) || n <= 0) {
    console.error("[!] Invalid --interval '" + value + "'; falling back to 300s");
    return 300;
  }
  return n;
}

program
  .name('jswatch')
  .description('Monitor remote JavaScript files for changes')
  .version('2.0.0')
  .option('-d, --debug', 'verbose output', false)
  .option('-m, --monitors-dir <path>', 'monitors directory', './monitors')
  .option('-w, --watch', 'continuous monitoring mode', false)
  .option('-i, --interval <seconds>', 'watch interval in seconds', parseInterval, 300)
  .option('-f, --filter <pattern>', 'only run monitors matching id pattern')
  .option('--ast', 'enable AST-based structural diffing globally', false)
  .parse();

const opts = program.opts();

await run({
  monitorsDir: opts.monitorsDir,
  debug: opts.debug,
  watch: opts.watch,
  interval: opts.interval,
  filter: opts.filter,
  astMode: opts.ast,
});
