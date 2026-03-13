import { fetchUrl } from './fetcher.js';

const SCAN_CONCURRENCY = 10;

/**
 * Execute a monitor's pipeline. Returns { content, finalUrl } or null.
 */
export async function executePipeline(config, options = {}) {
  const { debug = false } = options;
  let currentUrl = config.startUrl;
  let currentContent = null;

  if (debug) console.log(`  [>] start_url: ${currentUrl}`);

  // Fetch the start URL
  currentContent = await fetchUrl(currentUrl, config.headers, { debug });
  if (currentContent === null) return null;

  // No pipeline — the start_url content IS the target
  if (!config.pipeline) {
    return { content: currentContent, finalUrl: currentUrl };
  }

  // Walk through each pipeline step
  for (let i = 0; i < config.pipeline.length; i++) {
    const step = config.pipeline[i];
    if (debug) {
      console.log(`  [>] pipeline step ${i}: ${step.scan ? 'scan' : 'extract'}=${step.scan || step.extract} template=${step.template} validate=${step.validate}`);
    }

    // ── Scan: extract ALL matches, fetch in parallel, find first that validates ──
    if (step.scan) {
      const result = await executeScan(step, currentContent, currentUrl, config.headers, i, debug);
      if (result === null) return null;
      currentContent = result.content;
      currentUrl = result.url;
      continue;
    }

    // ── Extract: single match ──
    if (step.extract) {
      const regex = new RegExp(step.extract);
      const match = currentContent.match(regex);
      if (!match) {
        if (debug) console.log(`  [!] step ${i}: extract regex did not match`);
        return null;
      }

      const extracted = match[1] !== undefined ? match[1] : match[0];
      if (debug) console.log(`  [+] step ${i}: extracted = ${extracted}`);

      // Resolve the next URL
      let nextUrl;
      if (step.template) {
        nextUrl = step.template.replace('{extracted}', extracted);
      } else {
        // Auto-resolve relative URLs
        nextUrl = new URL(extracted, currentUrl).href;
      }

      if (debug) console.log(`  [+] step ${i}: resolved url = ${nextUrl}`);

      // Fetch the new content
      currentContent = await fetchUrl(nextUrl, config.headers, { debug });
      if (currentContent === null) return null;
      currentUrl = nextUrl;
    }

    // ── Validate ──
    if (step.validate && !step.scan) {
      if (!new RegExp(step.validate).test(currentContent)) {
        if (debug) console.log(`  [!] step ${i}: validation failed`);
        return null;
      }
      if (debug) console.log(`  [+] step ${i}: content validated`);
    }
  }

  return { content: currentContent, finalUrl: currentUrl };
}

/**
 * Scan step: extract ALL regex matches from current content, construct URLs,
 * fetch in parallel batches, return the first whose content matches validate.
 */
async function executeScan(step, content, baseUrl, headers, stepIndex, debug) {
  const regex = new RegExp(step.scan, 'g');
  const matches = [];
  let m;
  while ((m = regex.exec(content)) !== null) {
    const value = m[1] !== undefined ? m[1] : m[0];
    // Deduplicate
    if (!matches.includes(value)) matches.push(value);
  }

  if (matches.length === 0) {
    if (debug) console.log(`  [!] step ${stepIndex}: scan regex matched nothing`);
    return null;
  }

  if (debug) console.log(`  [+] step ${stepIndex}: scan found ${matches.length} unique matches`);

  // Build URLs
  const urls = matches.map(extracted => {
    if (step.template) return step.template.replace('{extracted}', extracted);
    return new URL(extracted, baseUrl).href;
  });

  const validateRegex = step.validate ? new RegExp(step.validate) : null;

  // Fetch in concurrent batches and return first match
  for (let batch = 0; batch < urls.length; batch += SCAN_CONCURRENCY) {
    const batchUrls = urls.slice(batch, batch + SCAN_CONCURRENCY);

    const results = await Promise.allSettled(
      batchUrls.map(async (url) => {
        const text = await fetchUrl(url, headers, { debug: false });
        if (text === null) return null;
        if (validateRegex && !validateRegex.test(text)) return null;
        return { content: text, url };
      })
    );

    for (const result of results) {
      if (result.status === 'fulfilled' && result.value !== null) {
        if (debug) console.log(`  [+] step ${stepIndex}: scan hit → ${result.value.url}`);
        return result.value;
      }
    }

    if (debug) console.log(`  [>] step ${stepIndex}: scanned batch ${batch / SCAN_CONCURRENCY + 1} (${batchUrls.length} URLs), no match yet...`);
  }

  if (debug) console.log(`  [!] step ${stepIndex}: scan exhausted all ${urls.length} URLs, no match`);
  return null;
}
