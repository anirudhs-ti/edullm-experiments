# Curriculum to Sequence Mapping

## Overview

This script maps curriculum substandards to Direct Instruction (DI) format sequences using a two-phase LLM-based approach.

## Process

### Phase 1: Skill Selection
- For each substandard (description + assessment boundary)
- LLM evaluates all 15 skills with their grade-specific summaries
- Selects top 1-2 skills that best match the substandard

### Phase 2: Sequence Rating
- For each selected skill from Phase 1
- LLM rates all sequences for that grade using 4-tier system:
  - **EXCELLENT**: Perfect match - addresses substandard and respects all assessment constraints
  - **FAIR**: Partial match - addresses some aspects
  - **POOR**: Weak match - tangentially related
  - **NON-EXISTENT**: No meaningful connection
- Only **EXCELLENT** matches are kept in final output

## Files

### Input
- `/workspaces/github-com-anirudhs-ti-edullm-experiments/data/curricululm_with_assesment_boundary.csv` - Curriculum substandards
- `/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_with_mappings.json` - DI formats with sequences

### Output
- `/workspaces/github-com-anirudhs-ti-edullm-experiments/output/substandard_to_sequence_mappings.json` - Final mappings
- `/workspaces/github-com-anirudhs-ti-edullm-experiments/output/mapping_progress.json` - Progress tracker for resume capability
- `curriculum_sequence_mapping.log` - Detailed execution log

## Usage

### Full Run (Grade 3)
```bash
cd /workspaces/github-com-anirudhs-ti-edullm-experiments
python3 map_curriculum_to_sequences.py
```

### Resume After Interruption
The script automatically resumes from where it left off using `mapping_progress.json`.

### Test Run (First 2 substandards)
```bash
# Modify TARGET_GRADE in script or use Python:
python3 -c "
import pandas as pd
from map_curriculum_to_sequences import *

# ... test code ...
"
```

## Configuration

Edit these variables in `map_curriculum_to_sequences.py`:
- `TARGET_GRADE = 3` - Which grade to process (currently Grade 3 POC)
- `SAVE_INTERVAL = 5` - How often to save progress (every N substandards)

## API Requirements

- **Model**: Gemini 2.0 Flash Exp
- **API Key**: Set `GEMINI_API_KEY` in `.env` file
- **Rate Limiting**: 0.5 second delay between substandards

## Expected Runtime

For Grade 3 (112 substandards):
- ~2-3 LLM calls per substandard (1 for Phase 1, 1-2 for Phase 2)
- Total: ~250-350 API calls
- Estimated time: 10-15 minutes
- Estimated cost: $5-10

## Output Format

```json
{
  "metadata": {
    "source_csv": "...",
    "target_grade": 3,
    "processed_substandards": 112,
    "llm_model": "gemini-2.0-flash-exp"
  },
  "mappings": [
    {
      "substandard_id": "CCSS.MATH.CONTENT.3.OA.A.1+1",
      "grade": 3,
      "substandard_description": "Write a multiplication equation...",
      "assessment_boundary": "Factors limited to up to 5...",
      "phase1_selected_skills": ["Multiplication"],
      "phase2_results": [
        {
          "skill_name": "Multiplication",
          "excellent_sequences": [1, 2],
          "all_ratings": [...],
          "no_excellent_explanation": null
        }
      ],
      "final_excellent_matches": [
        {"skill": "Multiplication", "grade": 3, "sequence_number": 1},
        {"skill": "Multiplication", "grade": 3, "sequence_number": 2}
      ]
    }
  ]
}
```

## Logging

The script provides detailed logging at multiple levels:
- `INFO`: Progress updates, phase results
- `WARNING`: Skipped items, missing data
- `ERROR`: Failures, exceptions

Logs are written to both console and `curriculum_sequence_mapping.log`.

## Troubleshooting

### "No GEMINI_API_KEY found"
- Ensure `.env` file exists with `GEMINI_API_KEY=your_key_here`

### "No skills found with grade 3 summaries"
- Verify `di_formats_with_mappings.json` has `grade_based_summary.grade_3` for skills

### Script hangs
- Check API rate limits
- Monitor `curriculum_sequence_mapping.log` for errors
- Script auto-resumes, so you can safely Ctrl+C and restart

