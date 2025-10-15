# Educational LLM Experiments

This repository contains experiments for matching curriculum standards with direct instruction formats using various AI/ML approaches including LLM-based matching, TF-IDF similarity, and hybrid methods.

## Repository Structure

```
edullm-experiments/
├── data/                           # Data files (CSV, JSON)
│   ├── curriculum.csv              # Curriculum standards data
│   ├── di_formats.json            # Direct instruction formats
│   └── *.csv                      # Various extracted instruction files
├── docs/                          # Documentation
│   ├── README_LLM_MATCHING.md
│   └── LLM_MATCHING_SUMMARY.md
├── output/                        # Generated reports and results
│   └── hybrid_report.html
├── logs/                          # Log files (created during execution)
├── llm_match_curriculum.py        # Main LLM-based curriculum matching script
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Overview

This project implements LLM-based matching to connect curriculum standards with direct instruction formats:

### LLM-Based Matching
- Uses Google's Gemini 2.0 Flash Lite model
- Intelligent assessment of scaffolding quality
- Considers conceptual alignment, skill progression, cognitive load
- Produces detailed explanations for each match
- Processes curriculum standards in batches for efficiency

## Quick Start

### 1. Setup Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Set up Gemini API key (for LLM-based methods)
export GEMINI_API_KEY="your_api_key_here"
```

### 2. Run LLM Matching
```bash
python llm_match_curriculum.py
```

## Data Files

- **curriculum.csv**: Curriculum standards with grade levels and descriptions
- **di_formats.json**: Direct instruction formats with detailed sequences
- **all_formats_extracted.csv**: Flattened format data for analysis
- **hybrid-extracted-instructions-*.csv**: Results from hybrid matching by grade

## Key Features

- **Grade-specific analysis**: Focus on 3rd grade curriculum standards
- **LLM-based matching**: Intelligent assessment using Gemini 2.0 Flash Lite
- **Comprehensive logging**: Detailed progress tracking and error handling
- **Progress saving**: Prevents data loss during long runs
- **Batch processing**: Efficient handling of large datasets
- **Detailed explanations**: LLM provides reasoning for each match decision

## Documentation

- [LLM Matching Documentation](docs/README_LLM_MATCHING.md)
- [LLM Matching Summary](docs/LLM_MATCHING_SUMMARY.md)

## Output Files

Results are saved as CSV files with the following format:
- `grade`: Grade level
- `substandard_description`: Curriculum standard description
- `substandard_id`: Unique identifier
- `direct_instructions`: Matched instruction format
- `match_confidence`: Confidence level (High/Medium/Low/Very Low)
- `similarity_score`: Numeric score (0.0-1.0)
- `llm_explanation`: Detailed explanation (LLM methods only)

## Requirements

- Python 3.8+
- pandas, numpy, scikit-learn
- google-generativeai (for LLM methods)
- python-dotenv (for environment variables)

## Contributing

This repository focuses on LLM-based curriculum matching. The main script `llm_match_curriculum.py` contains the core functionality for matching curriculum standards with direct instruction formats using Google's Gemini model.