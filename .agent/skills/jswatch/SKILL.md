---
name: jswatch-monitor
description: >
  Create and manage JSWatch monitor configurations for tracking changes in
  remote JavaScript files. Use this skill when the user wants to: monitor a
  JavaScript file for changes, track a dynamic/bundled JS file, set up a
  multi-step pipeline to extract a JS URL from HTML or other JS files, scan
  webpack chunks to find specific code, create a new monitor config, add
  statistics tracking for API endpoints or patterns, or debug a failing
  JSWatch pipeline. Also trigger for: "monitor this JS", "track this script",
  "watch for JS changes", "set up jswatch", "create monitor config",
  "add a new target", "JS recon", "asset monitoring", "scan chunks",
  "find mutation in webpack", "module federation".
---

# JSWatch Monitor Skill

Create, run, and debug JSWatch monitor configurations for tracking remote JavaScript file changes.

---

## Quick Reference

### Folder Structure

```
jswatch/
├── bin/jswatch.js          # CLI entry point
├── src/                    # core modules
├── monitors/               # all configs go here
│   ├── target_name.yaml    # one yaml per target/project
│   └── another.yaml
└── projects/               # auto-generated output
    └── target_name/
        └── monitor_id/
            ├── baseline.js
            └── changes.md
```

### Config Format

Each YAML file in `monitors/` has a `monitors:` array. Each monitor has:

| Field | Required | Description |
|---|---|---|
| `id` | **Yes** | Unique identifier, becomes the output folder name |
| `start_url` | **Yes** | The initial URL to fetch |
| `pipeline` | No | Array of steps: `extract`, `template`, `validate`, `scan` |
| `headers` | No | Custom HTTP headers for all requests |
| `stats` | No | Array of `{name, regex}` to track pattern counts |
| `max_line_length` | No | Max diff line length (default: 500) |
| `diff_mode` | No | `"text"` (default) or `"ast"` for structural JS diffing |

### Pipeline Steps

Each step in `pipeline:` supports:

- **`extract`**: Regex to extract a value from the current content. First capture group is used.
- **`template`**: URL template using `{extracted}` placeholder. If omitted, the extracted value is auto-resolved as a relative URL.
- **`validate`**: Regex that must match the current content or the pipeline fails.
- **`scan`**: Like `extract` but matches ALL occurrences globally, fetches each URL in parallel (batches of 10), and returns the first whose content matches `validate`. Requires `validate`. Use for searching across webpack chunks.

Steps are implicit: each step's output (fetched content) automatically feeds the next step.

---

## Creating a Monitor

### Step 1 -- Determine the target type

1. **Static file**: You know the exact URL -- just use `start_url`, no pipeline.
2. **Dynamic file**: JS path is inside an HTML page -- one `extract` step.
3. **Multi-step**: JS path is buried across multiple files -- chain `extract` steps.
4. **Chunk search**: Target code is in one of many webpack chunks -- use `scan` step.

### Step 2 -- Write the config

Place a new `.yaml` file in `monitors/`:

```yaml
# monitors/target_name.yaml
monitors:
  - id: "main_bundle"
    start_url: "https://target.com/"
    pipeline:
      - extract: '<script.*?src="([^"]+\.js)"'
      - validate: "apiKey"
    diff_mode: "ast"
```

### Step 3 -- Test

```bash
node bin/jswatch.js --debug
```

Check the debug output for:
- `[+] start_url: ...` -- confirms the initial fetch
- `[+] step N: extracted = ...` -- confirms regex matched
- `[+] step N: resolved url = ...` -- confirms URL resolution
- `[+] step N: scan found N matches` -- confirms scan discovered URLs
- `[+] step N: scan hit -> ...` -- confirms scan found the target
- `[+] Baseline created: ...` -- confirms first-run baseline saved

### Step 4 -- Run again to detect changes

```bash
node bin/jswatch.js
```

If the remote JS changed since the baseline, a diff report is printed to stdout and saved to `projects/{project}/{id}/changes.md`.

---

## Common Patterns

### Static file with auth
```yaml
- id: "admin_panel_js"
  start_url: "https://target.com/admin/app.js"
  headers:
    Cookie: "session=abc123"
    Authorization: "Bearer token"
```

### Dynamic file (auto-resolve relative URL)
```yaml
- id: "app_bundle"
  start_url: "https://target.com/"
  pipeline:
    - extract: '<script.*?src="([^"]+\.js)"'
    # no template needed -- relative paths auto-resolved
```

### Multi-step Nuxt/Webpack chunk tracking
```yaml
- id: "nuxt_chunk"
  start_url: "https://target.com/"
  pipeline:
    - extract: '<script.*?src="(/_nuxt/[^"]+\.js)"'
    - extract: 'chunkId="([a-f0-9]+)"'
      template: "https://target.com/_nuxt/{extracted}.js"
    - validate: "targetFunctionName"
```

### Scan webpack module federation chunks
```yaml
- id: "federation_target"
  start_url: "https://target.com/admin"
  pipeline:
    # Extract federation host script
    - extract: 'src="([^"]*federation[^"]*index\.js)"'
    # Extract manifest path from federation host
    - extract: '(mfe-commerce/mf-manifest\.json)'
      template: "https://cdn.target.com/{extracted}"
    # Scan ALL chunk filenames, fetch each, find the one with the target
    - scan: '"(\d+\.[a-f0-9]+\.js)"'
      template: "https://cdn.target.com/mfe-commerce/{extracted}"
      validate: 'mutation DeleteCollection\('
  diff_mode: "ast"
  stats:
    - name: "GraphQL Mutations"
      regex: 'mutation [A-Z]\w+\('
```

### Track API endpoint count changes
```yaml
- id: "api_surface"
  start_url: "https://target.com/app.js"
  stats:
    - name: "REST Endpoints"
      regex: "/api/v[0-9]+/[^\"'\\s]+"
    - name: "GraphQL Queries"
      regex: 'query [A-Z]\w+\('
```

---

## CLI Reference

```bash
node bin/jswatch.js                           # normal run
node bin/jswatch.js --debug                   # verbose output
node bin/jswatch.js --ast                     # enable AST diff globally
node bin/jswatch.js --filter "api_tracker"    # run specific monitors
node bin/jswatch.js --watch --interval 60     # continuous mode
```

Exit codes: `0` = no changes, `1` = changes detected.

---

## Debugging Checklist

1. **Regex not matching?** -- Test your regex on the actual page source, not the rendered DOM.
2. **Wrong URL resolved?** -- Add `template:` to override auto-resolve with an explicit URL.
3. **Validation failing?** -- The string might be in a different chunk. Use `scan` instead of `extract`.
4. **Scan too slow?** -- Narrow the regex to match fewer chunk filenames from the manifest.
5. **AST diff empty but hash changed?** -- Cosmetic changes (whitespace/comments) don't produce structural diffs. This is expected.
6. **AST fell back to text?** -- The file couldn't be parsed (e.g. webpack runtime wrapper). Text diff is the correct fallback.
