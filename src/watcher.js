import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import chalk from 'chalk';
import { loadConfigs } from './config.js';
import { executePipeline } from './pipeline.js';
import { calculateHash } from './diff.js';
import { generateReport, saveReport, printReport } from './reporter.js';

/**
 * Run a single monitor and return a report string or null.
 */
async function runMonitor(projectName, config, projectsDir, options) {
  const { debug, astMode } = options;

  if (debug) {
    console.log(`\n[+] Monitor: ${config.id}`);
    if (config.headers) console.log(`[+] Headers: ${JSON.stringify(config.headers)}`);
  }

  const outputDir = join(projectsDir, projectName, config.id);
  mkdirSync(outputDir, { recursive: true });
  const baselinePath = join(outputDir, 'baseline.js');

  // Execute pipeline
  const result = await executePipeline(config, { debug });
  if (result === null) {
    console.log(`[!] Warning: could not fetch target for ${projectName}/${config.id}`);
    return null;
  }

  const { content: remoteContent, finalUrl } = result;

  // First run — create baseline
  if (!existsSync(baselinePath)) {
    writeFileSync(baselinePath, remoteContent, 'utf-8');
    if (debug) console.log(`[+] Baseline created: ${baselinePath}`);
    return null;
  }

  // Compare
  const localContent = readFileSync(baselinePath, 'utf-8');
  if (calculateHash(localContent) === calculateHash(remoteContent)) {
    if (debug) console.log(`[+] No changes for ${config.id}`);
    return null;
  }

  // Use AST mode if enabled globally or per-monitor
  const effectiveConfig = { ...config };
  if (astMode && effectiveConfig.diffMode === 'text') {
    effectiveConfig.diffMode = 'ast';
  }

  const report = generateReport(config.id, finalUrl, localContent, remoteContent, effectiveConfig);
  saveReport(report, outputDir);

  // Update baseline
  writeFileSync(baselinePath, remoteContent, 'utf-8');

  return report;
}

/**
 * Run all monitors once. Returns exit code: 0 = no changes, 1 = changes detected.
 */
async function runOnce(options) {
  const { monitorsDir, debug, filter, astMode } = options;
  const projects = loadConfigs(monitorsDir, debug);

  if (projects.length === 0) {
    console.log('[!] No projects loaded.');
    return 0;
  }

  const reports = [];

  for (const project of projects) {
    if (debug) {
      console.log(`\n${'='.repeat(50)}`);
      console.log(`[+] Project: ${project.projectName}`);
      console.log('='.repeat(50));
    }

    // Filter monitors if pattern specified
    let monitors = project.monitors;
    if (filter) {
      const pattern = new RegExp(filter, 'i');
      monitors = monitors.filter(m => pattern.test(m.id));
      if (debug && monitors.length < project.monitors.length) {
        console.log(`[+] Filter '${filter}' matched ${monitors.length}/${project.monitors.length} monitor(s)`);
      }
    }

    // Run monitors concurrently within each project
    const results = await Promise.allSettled(
      monitors.map(config => runMonitor(project.projectName, config, './projects', { debug, astMode }))
    );

    for (const result of results) {
      if (result.status === 'fulfilled' && result.value) {
        reports.push(result.value);
      } else if (result.status === 'rejected') {
        console.log(`[!] Monitor error: ${result.reason?.message || result.reason}`);
      }
    }
  }

  // Print reports
  if (reports.length > 0) {
    console.log('');
    for (const report of reports) {
      printReport(report);
    }
    return 1;
  }

  if (debug) console.log('\n[+] No changes detected.');
  return 0;
}

/**
 * Main entry point. Supports single run and watch mode.
 */
export async function run(options) {
  const { watch = false, interval = 300 } = options;

  if (!watch) {
    const exitCode = await runOnce(options);
    process.exitCode = exitCode;
    return;
  }

  // Watch mode
  console.log(chalk.cyan(`[*] Watch mode started (interval: ${interval}s)`));
  console.log(chalk.cyan('[*] Press Ctrl+C to stop\n'));

  let running = true;

  const shutdown = () => {
    if (running) {
      running = false;
      console.log(chalk.yellow('\n[*] Shutting down...'));
    }
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  while (running) {
    await runOnce(options);

    // Wait for interval, but check for shutdown
    const endTime = Date.now() + interval * 1000;
    while (running && Date.now() < endTime) {
      await new Promise(r => setTimeout(r, 1000));
    }

    if (running) {
      console.log(chalk.cyan(`\n[*] Re-checking... (${new Date().toLocaleTimeString()})`));
    }
  }
}
