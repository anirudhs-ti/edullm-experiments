# Grade 3 Substandard Mappings Viewer

Interactive web viewer for displaying brute-force mapping results from `substandard_to_sequence_mappings.v3.json`.

## Files

- **`mappings_viewer.html`** - Main HTML viewer
- **`data.json`** - Brute-force mapping results (copied from `Experiment : Find existing mappings/outputs/substandard_to_sequence_mappings.v3.json`)
- **`serve.py`** - Python HTTP server script

## Usage

### Start the Server

```bash
cd website
python3 serve.py
```

The server will start on `http://localhost:8000` and automatically open your browser.

### Manual Access

If the browser doesn't open automatically, navigate to:
```
http://localhost:8000/mappings_viewer.html
```

## Features

- **Search** - Search substandards by ID or description
- **Browse** - Browse all 112 Grade 3 substandards
- **View Matches** - See EXCELLENT and FAIR sequence matches for each substandard
- **Metadata** - View brute-force evaluation metadata (total sequences evaluated, timestamps)
- **Export** - Export individual substandard views as PNG or PDF

## Data Structure

The viewer displays:
- Substandard ID, description, and assessment boundary
- **final_excellent_matches** - Top matches (up to 5) with quality ratings (EXCELLENT/FAIR) and alignment scores
- **bruteforce_metadata** - Evaluation statistics (total sequences evaluated, top matches count)
- **phase1_selected_skills** - Original Phase 1 skill selections (preserved for compatibility)

## Stopping the Server

Press `Ctrl+C` in the terminal to stop the server.

