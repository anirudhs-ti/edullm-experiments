# Evaluation Dashboard

A simple HTML dashboard for viewing question generation evaluation statistics.

## Quick Start

```bash
# Navigate to the evals directory
cd "/workspaces/github-com-anirudhs-ti-edullm-experiments/Question Generation/outputs/evals"

# Start the server
python serve_dashboard.py
```

The script will print the URL to access (e.g., `http://localhost:8000`)

## Features

### Summary Cards
- **Average Score**: Overall quality score across all questions
- **Pass Rate**: Percentage of questions that passed Reading QC
- **Acceptance Rate**: Percentage recommended for acceptance
- **Answer Correctness**: Percentage of verified correct answers

### Detailed Metrics Tabs
1. **Overview**: Score distribution histogram and summary statistics
2. **TI Question QA**: Individual metric scores (correctness, grade alignment, etc.)
3. **Answer Verification**: Correctness rate and confidence scores
4. **Reading QC**: Quality control scores and pass rates
5. **Math Content**: Overall ratings and pass/fail breakdown
6. **Questions Table**: Detailed breakdown of each question with expandable details

### File Selection
- Dropdown at the top to select which evaluation file to view
- Statistics are isolated per file (no mixing of data)
- Refresh button to reload the current file

## How It Works

1. **serve_dashboard.py**: Simple HTTP server that serves files from the evals directory
2. **index.html**: Self-contained dashboard with all logic in JavaScript
3. **Data Loading**: JavaScript fetches JSON files and calculates statistics client-side

## Accessing from Outside the Container

If you're SSH'd into a container:

### Option 1: Port Forwarding (Recommended)
```bash
# On your local machine, forward the port:
ssh -L 8000:localhost:8000 user@container-host

# Then access: http://localhost:8000
```

### Option 2: Direct Access
If your container has a network IP, the script will print it:
```
http://<container-ip>:8000
```

## Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

## Troubleshooting

**Port already in use?**
- The script automatically finds the next available port (8000, 8001, 8002, etc.)

**No files showing up?**
- Make sure you have JSON files with names starting with `results_` in the evals directory

**Charts not rendering?**
- The dashboard uses Chart.js from CDN - ensure you have internet access

## File Structure

```
evals/
├── serve_dashboard.py      # HTTP server script
├── index.html              # Dashboard UI
├── results_*.json          # Evaluation files (auto-detected)
└── README_DASHBOARD.md     # This file
```

