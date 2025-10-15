# Educational LLM Experiments

This repository contains experiments for matching curriculum standards with direct instruction formats using various AI/ML approaches including LLM-based matching, TF-IDF similarity, and hybrid methods.

## Repository Structure

```
edullm-experiments/
├── data/                           # Data files (CSV, JSON)
│   ├── curriculum.csv              # Curriculum standards data
│   ├── di_formats.json            # Direct instruction formats
│   ├── format-based/              # Format-based analysis data
│   └── *.csv                      # Various extracted instruction files
├── scripts/                       # Python scripts organized by function
│   ├── matching/                  # Curriculum matching algorithms
│   │   ├── llm_match_curriculum.py
│   │   ├── llm_match_very_low.py
│   │   ├── match_curriculum_hybrid*.py
│   │   ├── match_curriculum_gemini*.py
│   │   └── tfidf_match_curriculum.py
│   ├── extraction/                # Data extraction scripts
│   │   ├── extract_all_formats.py
│   │   └── extract_grade3_progressions.py
│   └── utilities/                 # Utility and demo scripts
│       ├── demo_llm_matching.py
│       ├── test_llm_setup.py
│       └── generate_hybrid_report.py
├── docs/                          # Documentation
│   ├── README_LLM_MATCHING.md
│   └── LLM_MATCHING_SUMMARY.md
├── output/                        # Generated reports and results
│   └── hybrid_report.html
├── logs/                          # Log files (created during execution)
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Overview

This project implements multiple approaches to match curriculum standards with direct instruction formats:

### 1. LLM-Based Matching
- Uses Google's Gemini 2.0 Flash Lite model
- Intelligent assessment of scaffolding quality
- Considers conceptual alignment, skill progression, cognitive load
- Produces detailed explanations for each match

### 2. TF-IDF Similarity
- Vector-based text similarity using scikit-learn
- Fast keyword-based matching
- Good baseline for comparison

### 3. Hybrid Approach
- Combines TF-IDF with LLM validation
- Uses local TF-IDF for initial filtering
- Escalates borderline matches to LLM for final scoring
- Balances speed and accuracy

### 4. Vector-Based Matching
- Pure Python implementation using stdlib only
- No external API dependencies
- Useful for offline analysis

## Quick Start

### 1. Setup Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Set up Gemini API key (for LLM-based methods)
export GEMINI_API_KEY="your_api_key_here"
```

### 2. Test Setup
```bash
python scripts/utilities/test_llm_setup.py
```

### 3. Run Demo
```bash
python scripts/utilities/demo_llm_matching.py
```

### 4. Run Full Analysis
```bash
# LLM-based matching
python scripts/matching/llm_match_curriculum.py

# TF-IDF matching
python scripts/matching/tfidf_match_curriculum.py

# Hybrid matching
python scripts/matching/match_curriculum_hybrid.py
```

## Data Files

- **curriculum.csv**: Curriculum standards with grade levels and descriptions
- **di_formats.json**: Direct instruction formats with detailed sequences
- **all_formats_extracted.csv**: Flattened format data for analysis
- **hybrid-extracted-instructions-*.csv**: Results from hybrid matching by grade

## Key Features

- **Grade-specific analysis**: Focus on 3rd grade curriculum standards
- **Multiple matching algorithms**: LLM, TF-IDF, hybrid, and vector-based
- **Comprehensive logging**: Detailed progress tracking and error handling
- **Progress saving**: Prevents data loss during long runs
- **Batch processing**: Efficient handling of large datasets
- **Report generation**: HTML reports with visualizations

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

When adding new scripts:
- Place matching algorithms in `scripts/matching/`
- Place data extraction scripts in `scripts/extraction/`
- Place utility scripts in `scripts/utilities/`
- Update this README if adding new functionality