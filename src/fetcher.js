const MAX_RETRIES = 3;
const BASE_DELAY = 1000;

/**
 * Fetch a URL with retry logic and timeout.
 * Retries on network errors and 5xx responses with exponential backoff.
 * Returns response text or null on final failure.
 */
export async function fetchUrl(url, headers = null, options = {}) {
  const { debug = false, timeout = 15000 } = options;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const fetchOptions = {
        signal: AbortSignal.timeout(timeout),
      };
      if (headers) fetchOptions.headers = headers;

      const resp = await fetch(url, fetchOptions);

      // Don't retry client errors
      if (resp.status >= 400 && resp.status < 500) {
        if (debug) console.log(`[!] Fetch ${url}: HTTP ${resp.status} (not retrying)`);
        return null;
      }

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      return await resp.text();
    } catch (err) {
      if (debug) console.log(`[!] Fetch error ${url} (attempt ${attempt}/${MAX_RETRIES}): ${err.message}`);

      if (attempt < MAX_RETRIES) {
        const delay = BASE_DELAY * Math.pow(2, attempt - 1);
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }

  return null;
}
