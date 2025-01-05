![Logo](logo.png)

---

JSWatch is a lightweight and efficient JavaScript file monitoring tool that tracks changes in remote JavaScript files. It provides automatic diff generation in markdown format written to stdout. 

> But in practice , i personally used this tool not just for javascript file , but also for other remote static file.

## Features

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

3. Configure the `monitor.json` file

There is two type of javascript that can be monitored, static and dynamic. The `is_static` attribute that indicate how the scanning approach. if Set to `True` it will need addition attribute value to proceed. But all attribute need to be provided.

```json
{
      // Static JavaScript file configuration
      "title": "Main Application JS",                    // Identifier for the file, will be used as filename
      "is_static": true,                                 // Direct URL to JS file
      "url": "https://example.com/static/app.js",

      // if is_static set to true, attribute below is not used but still must be provided
      "regex_attribute": null,
      "url_to_append": "",
      "regex_js": ""
    },
    {
      // Dynamic JavaScript file configuration
      "title": "Dynamic Module JS",                      // Identifier for monitoring
      "is_static": false,                                // File requires scraping from webpage
      "url": "https://example.com/index.html",          // URL of the webpage containing the script
      "regex_js": "<script.*?src=\"(/static/.*?\\.js)\".*?>",  // Pattern to find script tags
      "url_to_append": "https://example.com",           // Base URL for completing relative paths
      "regex_attribute": "specific_function_name or Variable"        // Pattern to identify correct script content
    }
```

4. Run the app

```bash
python jswatch.py
```

## Configuration Types

### Static JavaScript File

Use this when you have a direct URL to the JavaScript file.

```json
{
  "title": "Main Script",
  "is_static": true,
  "url": "https://example.com/main.js"
}
```

### Dynamic JavaScript File

Use this when the JavaScript file needs to be found within a webpage.

```json
{
  "title": "Dynamic Script",
  "is_static": false,
  "url": "https://example.com/page.html",
  "regex_js": "<script.*?src=\"(/static/.*?\\.js)\".*?>",
  "url_to_append": "https://example.com",
  "regex_attribute": "specific_content"
}
```

## How It Works

1. First Run:

   - Creates ./js directory
   - Downloads initial versions of files
   - Saves them as baselines named base on `title` on the configuration

2. Monitoring:

   - Checks files every time you run the program
   - Downloads current versions
   - Compares with baselines
   - Generates dif report for changes

3. Change Detection:
   - Formats report in Markdown
   - writen into stdout using `print()`
   - Saves report history on `./js/{title}.md`

## Reports

When changes are detected, you'll see reports like this:

````markdown
## JSwatch : new change for `script.js`

url : https://example.com/script.js
time : 2025-01-05 12:34:56

```diff
- old code
+ new code
```
````

## Tips

1. Testing Your Regex:

   - Use Python's regex tester to verify patterns
   - Test URL construction with url_to_append

2. Common Issues:

   - Verify URL accessibility
   - Confirm regex patterns match target scripts

3. Use `DEBUG` mode
   - set `DEBUG = True` on `jswatch.py` to make more verbose output like regex match

## Contributing 🤝

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
