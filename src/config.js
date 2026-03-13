import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, basename, extname } from 'path';
import yaml from 'js-yaml';

/**
 * Convert legacy steps-based config to new pipeline format.
 */
function convertLegacyMonitor(item) {
  if (!item.steps || item.start_url) return item;

  const steps = item.steps;
  delete item.steps;

  if (!steps || steps.length === 0) return item;

  // First step's url becomes start_url
  item.start_url = steps[0].url || '';

  // Rename title -> id if still using old key
  if (item.title && !item.id) {
    item.id = item.title;
    delete item.title;
  }

  const pipeline = [];
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const pipeStep = {};

    if (step.extract_regex) pipeStep.extract = step.extract_regex;
    if (step.url_template) pipeStep.template = step.url_template;
    if (step.validate_regex) pipeStep.validate = step.validate_regex;

    // Skip empty steps after the first
    if (i > 0 && Object.keys(pipeStep).length === 0) continue;
    if (Object.keys(pipeStep).length > 0) pipeline.push(pipeStep);
  }

  if (pipeline.length > 0) item.pipeline = pipeline;
  return item;
}

/**
 * Validate a monitor config object. Returns an array of error strings.
 */
function validateMonitor(item, filename) {
  const errors = [];

  if (!item.id) errors.push(`Missing 'id' in ${filename}`);
  if (!item.start_url) errors.push(`Missing 'start_url' for '${item.id || '?'}' in ${filename}`);

  if (item.pipeline) {
    for (let i = 0; i < item.pipeline.length; i++) {
      const step = item.pipeline[i];
      if (step.extract) {
        try { new RegExp(step.extract); }
        catch { errors.push(`Invalid extract regex in step ${i} of '${item.id}': ${step.extract}`); }
      }
      if (step.scan) {
        try { new RegExp(step.scan, 'g'); }
        catch { errors.push(`Invalid scan regex in step ${i} of '${item.id}': ${step.scan}`); }
        if (!step.validate) {
          errors.push(`Scan step ${i} of '${item.id}' requires a 'validate' regex`);
        }
      }
      if (step.validate) {
        try { new RegExp(step.validate); }
        catch { errors.push(`Invalid validate regex in step ${i} of '${item.id}': ${step.validate}`); }
      }
    }
  }

  if (item.stats) {
    for (const stat of item.stats) {
      if (!stat.name || !stat.regex) {
        errors.push(`Stats entry missing name/regex in '${item.id}'`);
        continue;
      }
      try { new RegExp(stat.regex); }
      catch { errors.push(`Invalid stats regex for '${stat.name}' in '${item.id}': ${stat.regex}`); }
    }
  }

  return errors;
}

/**
 * Load all YAML config files from the monitors directory.
 * Returns an array of { projectName, monitors[] } objects.
 */
export function loadConfigs(monitorsDir = 'monitors', debug = false) {
  const projects = [];
  let yamlFiles = [];

  if (existsSync(monitorsDir)) {
    const files = readdirSync(monitorsDir).sort();
    yamlFiles = files
      .filter(f => f.endsWith('.yaml') || f.endsWith('.yml'))
      .map(f => join(monitorsDir, f));
  } else {
    // Fallback: try monitor.yaml in current dir
    if (existsSync('monitor.yaml')) {
      yamlFiles = ['monitor.yaml'];
    } else {
      console.log('[!] No monitors/ directory and no monitor.yaml found.');
      return [];
    }
  }

  for (const yamlFile of yamlFiles) {
    const projectName = basename(yamlFile, extname(yamlFile));
    try {
      const raw = readFileSync(yamlFile, 'utf-8');
      const data = yaml.load(raw);

      if (!data || !data.monitors) {
        if (debug) console.log(`[!] Skipping ${yamlFile}: no 'monitors' key found`);
        continue;
      }

      const monitors = [];
      for (let item of data.monitors) {
        // Convert legacy format
        item = convertLegacyMonitor(item);

        // Rename title -> id
        if (item.title && !item.id) {
          item.id = item.title;
          delete item.title;
        }

        // Validate
        const errors = validateMonitor(item, yamlFile);
        if (errors.length > 0) {
          for (const err of errors) console.log(`[!] ${err}`);
          continue;
        }

        monitors.push({
          id: item.id,
          startUrl: item.start_url || '',
          pipeline: item.pipeline || null,
          headers: item.headers || null,
          stats: item.stats || null,
          maxLineLength: item.max_line_length ?? 500,
          diffMode: item.diff_mode || 'text',
        });
      }

      projects.push({ projectName, monitors });
      if (debug) console.log(`[+] Loaded ${yamlFile}: ${monitors.length} monitor(s)`);
    } catch (err) {
      if (err.code === 'ENOENT') {
        console.log(`[!] Config file not found: ${yamlFile}`);
      } else {
        console.log(`[!] Error loading ${yamlFile}: ${err.message}`);
      }
    }
  }

  return projects;
}
