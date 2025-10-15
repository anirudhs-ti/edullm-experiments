# LLM-Based Curriculum Matching (Batched Approach)

This script uses Google's Gemini 2.5 Flash model to assess how well direct instruction formats serve as scaffolding for curriculum substandards. It processes formats in batches of 15 for improved efficiency and better comparative analysis.

## Setup

1. **Install dependencies:**
   ```bash
   pip install pandas numpy google-generativeai scikit-learn
   ```

2. **Set up Gemini API key:**
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```
   
   Or add it to your environment permanently.

3. **Verify setup:**
   ```bash
   python test_llm_setup.py
   ```

## Usage

Run the LLM matching process:
```bash
python llm_match_curriculum.py
```

## What it does

1. **Loads data:**
   - `curriculum.csv` - Curriculum substandards (filtered to 3rd grade only)
   - `all_formats_extracted.csv` - Direct instruction formats

2. **For each 3rd grade substandard:**
   - Compares against all 116 instruction formats in batches of 15
   - Uses Gemini 2.5 Flash to assess scaffolding quality
   - Ranks formats within each batch and selects the best overall match
   - Logs detailed progress for each batch comparison
   - Saves progress after each substandard

3. **Output:**
   - `llm-extracted-instructions.csv` - Results in same format as TF-IDF version
   - `llm_matching.log` - Detailed logging of the process

## Features

- **Detailed logging:** Shows which substandard is being processed, which format it's compared against, and the result
- **Progress saving:** Results are saved after each substandard to prevent data loss
- **Scaffolding assessment:** LLM evaluates conceptual alignment, skill progression, cognitive load, instructional approach, and content relevance
- **3rd grade focus:** Only processes 3rd grade curriculum substandards

## Output Format

The output CSV contains:
- `grade`: Grade level (3)
- `substandard_description`: Description of the curriculum substandard
- `substandard_id`: Unique identifier for the substandard
- `direct_instructions`: Best matching instruction format content
- `match_confidence`: High/Medium/Low/Very Low confidence rating
- `similarity_score`: Numeric score (0.0-1.0) from LLM assessment
- `llm_explanation`: Detailed explanation of the match quality

## Logging

The script provides excellent logging that shows:
- Current substandard being processed
- Each format comparison with confidence and score
- Best match found for each substandard
- Progress updates and error handling
- Final summary statistics

## Example Log Output

```
2024-01-15 10:30:15 - INFO - Processing substandard: CCSS.MATH.CONTENT.3.OA.A.1+1
2024-01-15 10:30:15 - INFO - Description: Write a multiplication equation that represents an equal sets of objects.
2024-01-15 10:30:16 - INFO -   Comparing against format 1/116: INTRODUCING NEW NUMBERS...
2024-01-15 10:30:17 - INFO -     Result: Low confidence, score: 0.25
2024-01-15 10:30:18 - INFO -   Comparing against format 2/116: RATIONAL COUNTING...
2024-01-15 10:30:19 - INFO -     Result: Medium confidence, score: 0.45
...
2024-01-15 10:35:20 - INFO -   Best match found: SINGLE DIGIT MULTIPLICATION (confidence: High, score: 0.85)
2024-01-15 10:35:21 - INFO - ✓ Successfully processed substandard 1
2024-01-15 10:35:21 - INFO - Progress saved: 1/112 substandards completed
```

## Error Handling

- Graceful handling of API errors
- Progress saving prevents data loss
- Detailed error logging for troubleshooting
- Fallback responses for failed assessments
