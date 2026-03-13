#!/usr/bin/env node

import { program } from 'commander';
import { run } from '../src/watcher.js';

program
  .name('jswatch')
  .description('Monitor remote JavaScript files for changes')
  .version('2.0.0')
  .option('-d, --debug', 'verbose output', false)
  .option('-m, --monitors-dir <path>', 'monitors directory', './monitors')
  .option('-w, --watch', 'continuous monitoring mode', false)
  .option('-i, --interval <seconds>', 'watch interval in seconds', parseInt, 300)
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
