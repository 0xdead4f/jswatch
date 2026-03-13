

# JSWatch

**Monitor remote JavaScript files for changes. Trace through bundlers. Diff structurally.**

  [Node.js](https://nodejs.org/)
  [License: MIT](https://opensource.org/licenses/MIT)
  [PRs Welcome](https://github.com/0xdead4f/jswatch/pulls)
  [JavaScript](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)



  


JSWatch fetches remote JavaScript files, compares them against stored baselines, and generates detailed diff reports. It handles everything from simple static URLs to complex webpack module federation setups where the target file is buried behind multiple layers of indirection.

```
shop.html → federation-host/index.js → mf-manifest.json → scan 155 chunks → hit: 4767.e75f73df9a7c683d93bd.js
```

---

## What makes it different

**Pipeline engine** -- Chain fetch-extract-fetch steps to follow dynamic script references through HTML pages, manifests, and loaders. Each step feeds the next automatically.

**Scan step** -- Extract *all* regex matches from a manifest or entry point, fetch each URL in parallel, and find the one containing your target code. Designed for webpack/module federation chunk hunting.

**AST-based diffing** -- Parse JavaScript with [acorn](https://github.com/acornjs/acorn) and diff at the symbol level. Changes are grouped by function, variable, and class -- not just line numbers. Cosmetic changes (whitespace, comments) are ignored.

**Text diff fallback** -- For minified bundles or non-JS files that can't be parsed, falls back to beautified text diff with [js-beautify](https://github.com/beautifier/js-beautify).

**AI agent skill** -- Ships with a built-in [Claude Code](https://claude.ai) skill (`.agent/skills/jswatch/SKILL.md`) that lets AI agents create monitor configs, debug pipelines, and run JSWatch through natural language. Just describe what you want to monitor and the agent handles the YAML, regex, and pipeline setup.

---

## Install

```bash
git clone https://github.com/0xdead4f/jswatch.git
cd jswatch
npm install
```

Requires **Node.js 18+** (uses built-in `fetch`).

---

## New AI agent skill

JSWatch includes an agent skill at `.agent/skills/jswatch/SKILL.md` for use with [Claude Code](https://claude.ai) or any compatible AI coding agent. The skill gives the agent full context on JSWatch's config format, pipeline steps, common patterns, and debugging — so it can create and troubleshoot monitors on your behalf.

**What the agent can do:**

- Generate monitor YAML configs from a target URL or description
- Build multi-step pipelines (extract, scan, validate) with correct regex
- Choose the right diff mode (`text` vs `ast`) for your target
- Add stats tracking for API endpoints, GraphQL mutations, etc.
- Debug failing pipelines using the built-in checklist

**Example prompt:**

> "Monitor [https://target.com/admin](https://target.com/admin) for changes to the JS bundle that contains the DeleteItem mutation. It's behind a webpack federation setup."

The agent will create the full YAML config with the pipeline steps, scan logic, validation regex, and AST diffing enabled.

---

## Quick start

**1. Create a monitor config:**

```yaml
# monitors/target.yaml
monitors:
  - id: "main_bundle"
    start_url: "https://example.com/app.js"
    stats:
      - name: "API Endpoints"
        regex: "/api/v[0-9]+/.*"
```

**2. Run:**

```bash
node bin/jswatch.js           # normal run
node bin/jswatch.js --debug   # verbose output
node bin/jswatch.js --ast     # enable AST diffing globally
```

First run creates a baseline. Subsequent runs detect and report changes.

**3. Output:**

```
projects/
└── target/
    └── main_bundle/
        ├── baseline.js       # stored snapshot
        └── changes.md        # appended diff reports
```

---

## CLI options

```
Usage: jswatch [options]

Options:
  -d, --debug              verbose output
  -m, --monitors-dir <path> monitors directory (default: "./monitors")
  -w, --watch              continuous monitoring mode
  -i, --interval <seconds> watch interval (default: 300)
  -f, --filter <pattern>   only run monitors matching id pattern
  --ast                    enable AST diffing globally
  -V, --version            output the version number
  -h, --help               display help for command
```

Watch mode runs checks on a loop until interrupted:

```bash
node bin/jswatch.js --watch --interval 60 --filter "api_tracker"
```

Exit codes: `0` = no changes, `1` = changes detected. Useful for CI/cron.

---

## Configuration

Configs are YAML files in `monitors/`. Each file becomes a **project**, each monitor gets its own output directory.

### Monitor fields


| Field             | Required | Default  | Description                                                |
| ----------------- | -------- | -------- | ---------------------------------------------------------- |
| `id`              | yes      |          | Unique name. Becomes the output folder.                    |
| `start_url`       | yes      |          | Initial URL to fetch.                                      |
| `pipeline`        | no       |          | Array of steps: `extract`, `template`, `validate`, `scan`. |
| `headers`         | no       |          | Custom HTTP headers for all requests.                      |
| `stats`           | no       |          | Array of `{name, regex}` to track pattern counts.          |
| `max_line_length` | no       | `500`    | Max line length in text diffs.                             |
| `diff_mode`       | no       | `"text"` | `"text"` or `"ast"` for structural JS diffing.             |


### Pipeline steps


| Field      | Description                                                                                                 |
| ---------- | ----------------------------------------------------------------------------------------------------------- |
| `extract`  | Regex to extract a value. First capture group `()` is used.                                                 |
| `template` | URL template with `{extracted}` placeholder. Omit to auto-resolve relative URLs.                            |
| `validate` | Regex that must match the fetched content, or the step fails.                                               |
| `scan`     | Like `extract` but matches **all** occurrences, fetches each in parallel, returns first passing `validate`. |


### Examples

**Static file with auth**

```yaml
- id: "admin_js"
  start_url: "https://target.com/admin.js"
  headers:
    Cookie: "session=abc123"
    Authorization: "Bearer token"
```



**Dynamic extraction from HTML**

```yaml
- id: "app_bundle"
  start_url: "https://target.com/"
  pipeline:
    - extract: '<script.*?src="([^"]+\.js)"'
      template: "https://target.com{extracted}"
    - validate: "initApp"
```



**Multi-step pipeline (Nuxt/Webpack)**

```yaml
- id: "nuxt_chunk"
  start_url: "https://target.com/"
  pipeline:
    - extract: '<script.*?src="(/_nuxt/[^"]+\.js)"'
    - extract: 'buildId="([a-f0-9]+)"'
      template: "https://target.com/_nuxt/{extracted}.js"
    - validate: "targetFunction"
```



**Scan webpack federation chunks**

```yaml
- id: "federation_target"
  start_url: "https://target.com/admin"
  pipeline:
    - extract: 'src="([^"]*index\.js)"'
    - extract: '(mfe-app/mf-manifest\.json)'
      template: "https://cdn.target.com/{extracted}"
    - scan: '"(\d+\.[a-f0-9]+\.js)"'
      template: "https://cdn.target.com/mfe-app/{extracted}"
      validate: 'mutation DeleteItem\('
  diff_mode: "ast"
```



**Stats tracking**

```yaml
- id: "api_surface"
  start_url: "https://target.com/app.js"
  stats:
    - name: "REST Endpoints"
      regex: "/api/v[0-9]+/[^\"'\\s]+"
    - name: "GraphQL Mutations"
      regex: 'mutation [A-Z]\w+\('
```



---

## AST diff output

When `diff_mode: "ast"` is set (or `--ast` flag is used), changes are grouped by symbol:

```markdown
### Stats
API Endpoints: 2 -> 4

### AST Summary
- 2 variables modified
- 1 function modified
- 1 variable added
- 1 function added
- 1 function removed

### Changes

#### + ADDED function `authenticateUser` (line 13)
​```js
function authenticateUser(token) {
    return fetch('/api/v2/auth', {
        headers: { Authorization: token }
    });
}
​```

#### - REMOVED function `oldFeature` (line 11)
​```js
function oldFeature() {
    return "this will be removed";
}
​```

#### ~ MODIFIED function `initApp` (line 7)
​```diff
 function initApp() {
-    console.log("App v1 initialized");
+    console.log("App v2 initialized");
+    authenticateUser(SESSION_TOKEN);
 }
​```
```

Cosmetic changes (whitespace, comments) produce an empty Changes section -- the hash changes but no structural diff is reported.

For files that can't be parsed (minified webpack bundles, non-JS), it automatically falls back to text diff with a note.

---

## Architecture

```
bin/jswatch.js        CLI entry point (commander)
src/
  config.js           YAML loading, legacy conversion, validation
  fetcher.js          HTTP with retry (3 attempts, exponential backoff)
  pipeline.js         Pipeline engine: extract, scan, validate
  diff.js             MD5 hashing, text diff, regex stats
  ast-diff.js         Structural JS diffing with acorn
  reporter.js         Markdown report generation, colored console output
  watcher.js          Orchestrator, concurrent execution, watch mode
```

Monitors within each project run concurrently via `Promise.allSettled()`. Failed fetches retry 3 times with exponential backoff (1s, 2s, 4s). 4xx errors are not retried.

---

## License

MIT License - see [LICENSE](LICENSE) for details.