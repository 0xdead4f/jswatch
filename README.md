![Logo](logo.png)

---

JSWatch is a lightweight and efficient remote JavaScript & web page monitoring tool that tracks changes. It provides automatic diff generation in markdown format written to stdout.

Supports :

1. Static file path
2. Dynamic file path
3. Multiple Step dynamic file path (unlimited steps)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/0xdead4f/jswatch.git
cd jswatch
```

2. Install required dependencies:

```bash
pip install -r requirements.txt
```

3. Create `monitor.yaml` configuration file.

JSWatch uses a unified step-based configuration system. Each monitor entry defines a series of steps that are executed in sequence to fetch the target file. Steps can fetch URLs, extract values using regex, validate content, and construct URLs from previous step results.

```yaml
monitors:
  - title: "Main Application JS"
    headers:
      Cookie: "session=admin"
    steps:
      - url: "https://example.com/home/"
        extract_regex: '<script.*?src="(/static/.*?\\.js)".*?>'
        url_template: "https://example.com{extracted}"
      - url: "{step0}"
        validate_regex: "specific_function_name"
    stats:
      - name: "Urls"
        regex: "/api/v1/urls/.*"
    max_line_length: 500
```

4. Run the app

```bash
python jswatch.py
```

For debug output:

```bash
python jswatch.py --debug
```

## Configuration Types

### Static JavaScript File

Use this when you have a direct URL to the JavaScript file.

```yaml
monitors:
  - title: "Main Script"
    headers:
      Cookie: "session=admin"
    steps:
      - url: "https://example.com/main.js"
```

### Dynamic JavaScript File

Use this when the JavaScript file needs to be found within a webpage.

```yaml
monitors:
  - title: "Dynamic Script"
    headers:
      Cookie: "session=admin"
    steps:
      - url: "https://example.com/page.html"
        extract_regex: '<script.*?src="(/static/.*?\\.js)".*?>'
        url_template: "https://example.com{extracted}"
      - url: "{step0}"
        validate_regex: "specific_content"
```

### Multiple Step Configuration

Use this when you need multiple steps to obtain the target JavaScript URL. Steps are executed sequentially, and each step can reference results from previous steps using placeholders like `{step0}`, `{step1}`, etc.

```yaml
monitors:
  - title: "Multi-Step JS"
    steps:
      - url: "https://example.com/home/"
        extract_regex: '<script.*?src="(.*?\\.js)".*?>'
        url_template: "https://example.com{extracted}"
      - url: "{step0}"
        extract_regex: "REGEX_VALUE"
        url_template: "https://example.com/_nuxt/{extracted}.js"
      - url: "{step1}"
        validate_regex: "SPECIFIC_CONTENT_OR_STRING"
```

### Multiple Monitors

You can monitor multiple files by adding multiple entries to the `monitors` array:

```yaml
monitors:
  - title: "Dynamic Script"
    steps:
      - url: "https://example.com/page.html"
        extract_regex: '<script.*?src="(/static/.*?\\.js)".*?>'
        url_template: "https://example.com{extracted}"
      - url: "{step0}"
        validate_regex: "specific_content"

  - title: "Main Script"
    headers:
      Cookie: "session=admin"
    steps:
      - url: "https://example.com/main.js"
```

## Step Configuration Reference

Each step in the `steps` array supports the following options:

- **`url`** (required): The URL to fetch. Can contain placeholders like `{step0}`, `{step1}`, `{extracted}` that will be replaced with values from previous steps.

- **`extract_regex`** (optional): A regex pattern to extract a value from the fetched content. The first capture group (or full match if no groups) is stored and can be referenced in subsequent steps using `{extracted}` or `{stepN}`.

- **`url_template`** (optional): A URL template that uses extracted values. If provided, the URL will be resolved using this template after extraction. Placeholders like `{extracted}` or `{step0}` will be replaced.

- **`validate_regex`** (optional): A regex pattern to validate that the fetched content matches. If the content doesn't match, the step fails and the monitor is skipped.

## Monitor Configuration Reference

Each monitor entry supports:

- **`title`** (required): Identifier for the file, used as filename for baseline storage.

- **`steps`** (required): Array of step configurations executed in sequence.

- **`headers`** (optional): Custom HTTP headers to send with every request.

- **`stats`** (optional): Array of statistics to track. Each stat has:

  - `name`: Name of the statistic
  - `regex`: Regex pattern to count matches

- **`max_line_length`** (optional): Maximum line length in diff output (default: 500). Longer lines are excluded from the diff.

## How It Works

1. **First Run:**

   - Downloads initial versions of files by executing step pipelines
   - Saves them as baselines named based on `title` in the `./js` directory

2. **Monitoring:**

   - Checks files every time you run the program
   - Executes step pipelines to fetch current versions
   - Compares with baselines using MD5 hashing
   - Generates diff report for changes

3. **Change Detection:**
   - Formats report in Markdown
   - Written to stdout using `print()`
   - Checks statistics based on regex patterns
   - Saves report history to `./js/{title}_changes.md`

## Step Execution Flow

The step-based pipeline works as follows:

1. **Initialize**: Start with the first step's URL
2. **Fetch**: Download content from the current URL
3. **Extract** (if `extract_regex` provided): Extract value(s) using regex and store for next steps
4. **Resolve** (if `url_template` provided): Construct new URL using extracted values
5. **Validate** (if `validate_regex` provided): Verify content matches pattern
6. **Repeat**: Move to next step, using placeholders to reference previous results
7. **Return**: Final step's content is the target file

### Placeholder Reference

- `{step0}`: Value extracted from step 0
- `{step1}`: Value extracted from step 1
- `{stepN}`: Value extracted from step N
- `{extracted}`: Most recently extracted value

## Reports

When changes are detected, you'll see reports like this:

````markdown
## JSwatch : new change for `script.js`

url : https://example.com/script.js
time : 2025-01-05 12:34:56

### Stats

Urls: 5 -> 7

### Changes

```diff
- old code
+ new code
```
````

## Tips

1. **Testing Your Regex:**

   - Use Python's regex tester to verify patterns
   - Test URL construction with placeholders
   - Use `--debug` flag to see step-by-step execution

2. **Common Issues:**

   - Verify URL accessibility
   - Confirm regex patterns match target content
   - If monitoring packed JavaScript, make sure the identifier regex uses static strings (function names may change)
   - Check that placeholders match step indices correctly

3. **Debug Mode:**

   - Run with `--debug` flag: `python jswatch.py --debug`
   - Shows detailed output including regex matches, extracted values, and URL resolution

4. **Step Design:**
   - Start simple: one step for static files
   - Add extraction steps when URLs need to be discovered
   - Use validation steps to filter out unwanted matches
   - Test each step incrementally

## Contributing 🤝

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
