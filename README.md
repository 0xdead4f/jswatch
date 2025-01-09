![Logo](logo.png)

---

JSWatch is a lightweight and efficient JavaScript file monitoring tool that tracks changes in remote JavaScript files. It provides automatic diff generation in markdown format written to stdout.

Supports :

1. Static file path
2. Dynamic file path
3. Multiple Step dynamic file path

> But in practice , i personally used this tool not just for javascript file , but also for other remote static file.

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

There is two type of javascript that can be monitored, static and dynamic. The `is_static` attribute that indicate how the scanning approach. if Set to `True` it will need addition attribute value to proceed.

```javascript
[
  {
    // Identifier for the file, will be used as filename
    title: "Main Application JS",

    // True for direct URL to JS file or False for scan an webpage for dynamic js
    is_static: true,

    // Static file have 2 option , Multiple Step or not
    // Multiple step means, the value of the js file is inside another js file
    // so program need to scan 2 times
    // [DEV] the current version only support 2 step
    is_multiple_step: true,

    // URL of the webpage containing the script
    url: "https://example.com/static/app.js",

    // Pattern to find script tags
    regex_js: '<script.*?src="(/static/.*?\\.js)".*?>',

    // Base URL for completing relative paths
    url_to_append: "https://example.com",

    // Pattern to identify correct script content
    // this regex is used as getting value from javascript if
    // "is_multiple_step" set to True
    regex_attribute: "specific_function_name or Variable",

    // Custom header for the every request
    custom_header: {},

    // the Next_step is used when "is_multiple_step" is set to True
    next_step: {
      // this attribute is used to craft url from given regex value
      // user `{regex_attribute}` to format the result of the regex
      url_to_append: "https://example.com/_nuxt/{regex_attribute}.js",

      // Next regex to determine the current javascript is the right one
      regex_attribute: "SPECIFIC_FUNCTION_OR_STRING",
    },
  },
];
```

4. Run the app

```bash
python jswatch.py
```

## Configuration Types

### Static JavaScript File

Use this when you have a direct URL to the JavaScript file.

```json
[
  {
    "title": "Main Script",
    "is_static": true,
    "url": "https://example.com/main.js",
    "custom_header": {
      "Cookie": "session=admin"
    }
  }
]
```

### Dynamic JavaScript File

Use this when the JavaScript file needs to be found within a webpage.

```json
[
  {
    "title": "Dynamic Script",
    "is_static": false,
    "url": "https://example.com/page.html",
    "regex_js": "<script.*?src=\"(/static/.*?\\.js)\".*?>",
    "url_to_append": "https://example.com",
    "regex_attribute": "specific_content",
    "custom_header": {
      "Cookie": "session=admin"
    }
  }
]
```

### Multiple javascript configuration

Use this when you need to scan multiple pages or javascript file

```json
[
  {
    "title": "Dynamic Script",
    "is_static": false,
    "url": "https://example.com/page.html",
    "regex_js": "<script.*?src=\"(/static/.*?\\.js)\".*?>",
    "url_to_append": "https://example.com",
    "regex_attribute": "specific_content",
    "custom_header": {
      "Cookie": "session=admin"
    }
  },
  {
    "title": "Main Script",
    "is_static": true,
    "url": "https://example.com/main.js",
    "custom_header": {
      "Cookie": "session=admin"
    }
  }
]
```

### If multiple step needed to obtain target javascript url

This configuration is used if target javascript name or url need multiple step to obtain.

```json
[
  {
    "title": "Test multiple step",
    "is_static": false,
    "is_multiple_step": true,
    "url": "https://example.com/home/",
    "regex_js": "<script.*?src=\"(.*?\\.js)\".*?>",
    "url_to_append": "https://example.com",
    "regex_attribute": "REGEX_TO_OBTAIN_SOME_VALUE",
    "next_step": {
      "url_to_append": "https://example.com/_nuxt/{regex_attribute}.js",
      "regex_attribute": "SPECIFIC_CONTENT_OR_STRING"
    }
  }
]
```

## How It Works

1. First Run:

   - Creates ./js directory
   - Downloads initial versions of files
   - Saves them as baselines named base on `title` on the configuration on `./js` directory

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

```

## Tips

1. Testing Your Regex:

   - Use Python's regex tester to verify patterns
   - Test URL construction with url_to_append

2. Common Issues:

   - Verify URL accessibility
   - Confirm regex patterns match target scripts

3. Use `DEBUG` mode
   - set `DEBUG = True` on `jswatch.py` to make more verbose output like regex match

## Next development idea

1. Add multiple step request
2. Add handler if the file already not accesible

## Contributing 🤝

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
```
