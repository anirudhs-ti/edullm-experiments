# Direct Instruction Curriculum Viewer

A modern, human-readable web interface for viewing the Direct Instruction Mathematics curriculum data.

## Features

- 📊 **Metadata Display**: Shows version, source document, statistics, and last update time
- 🔍 **Search Functionality**: Search through skills by name
- 📚 **Skill Cards**: Collapsible cards showing each skill's progression
- 🎓 **Grade-Level Organization**: Each skill organized by grade level with sequences
- 💡 **Example Questions**: Shows example questions for each sequence
- 🎨 **Modern UI**: Beautiful gradient design with smooth animations

## How to Use

### Option 1: Python Server (Recommended)

1. Run the Python server:
   ```bash
   python3 serve.py
   ```

2. Open your browser to `http://localhost:8000`

The server will automatically open the page in your default browser.

**IMPORTANT:** You MUST use the server. Opening `index.html` directly (using `file://` protocol) will cause a CORS error and the JSON file won't load. The browser will show an error page. Always use `http://localhost:8000` instead.

### Option 2: Other Web Servers

You can use any web server that supports serving static files:

- **Node.js**: `npx http-server`
- **PHP**: `php -S localhost:8000`
- **VS Code**: Use the "Live Server" extension

Just open `index.html` in your browser after starting the server.

## File Structure

- `index.html` - Main HTML structure
- `styles.css` - Styling and layout
- `script.js` - Data loading and display logic
- `serve.py` - Simple Python HTTP server
- `data/di_formats_augmented.json` - The curriculum data

## Usage

1. Click on any skill card to expand/collapse and view its progression
2. Use the search bar to filter skills by name
3. Browse through different grade levels and sequences
4. View example questions and visual aids for each sequence

## Debugging

If you see an error page, here's how to debug:

1. **Open Developer Console**: Press F12 or right-click → Inspect → Console tab
2. **Check the logs**: You'll see detailed information about:
   - What file is being loaded
   - HTTP response status
   - JSON parsing status
   - Any error messages

3. **Common issues**:
   - **"Failed to fetch"**: Server is not running or file path is wrong
   - **"HTTP error! status: 404"**: JSON file not found at the expected path
   - **CORS error**: Opening HTML file directly instead of through the server

## Browser Compatibility

Works best in modern browsers (Chrome, Firefox, Safari, Edge).


