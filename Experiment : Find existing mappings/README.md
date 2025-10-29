# Experiment: Find Existing Mappings

**Purpose:** Generate complete Grade 3 substandard-to-sequence mappings using brute-force validation.

**Method:** Processes ALL Grade 3 substandards by evaluating all 38 sequences across all skills (no Phase 1 pre-filtering), eliminating false negatives from the original two-phase approach.

---

## Folder Structure

```
Experiment : Find existing mappings/
├── scripts/
│   └── generate_all_grade3_mappings.py    # Main brute-force mapping script
├── inputs/
│   ├── curricululm_with_assesment_boundary.csv     # Curriculum substandards (descriptions & boundaries)
│   ├── di_formats_with_mappings.json               # DI problem sequences (all skills)
│   └── substandard_to_sequence_mappings.json      # Old mappings (for preserving phase1_selected_skills)
└── outputs/
    ├── substandard_to_sequence_mappings.v3.json   # Final brute-force mappings
    ├── bruteforce_remap_report_all_grade3.md      # Summary report
    └── generate_all_grade3_mappings.log           # Processing log
```

---

## Files Description

### Scripts

- **`scripts/generate_all_grade3_mappings.py`**
  - Main script that performs brute-force evaluation
  - For each Grade 3 substandard, evaluates all 38 sequences using LLM (Gemini)
  - Rates sequences with metrics: match_quality, boundary_classification, grade_alignment, alignment_score
  - Filters and ranks eligible sequences, selects top 5
  - Uses relative paths to inputs/ and outputs/ folders

### Input Files

- **`inputs/curricululm_with_assesment_boundary.csv`**
  - Source: Curriculum CSV with Grade 3 substandards
  - Contains: substandard_id, grade, substandard_description, assessment_boundary

- **`inputs/di_formats_with_mappings.json`**
  - Source: DI formats JSON with all problem sequences
  - Contains: skills → progressions → sequences (by grade)
  - Each sequence includes: sequence_number, problem_type, example_questions, visual_aids

- **`inputs/substandard_to_sequence_mappings.json`**
  - Source: Previous mapping results
  - Used to preserve `phase1_selected_skills` field in output for backward compatibility

### Output Files

- **`outputs/substandard_to_sequence_mappings.v3.json`**
  - Final mapping results with metadata
  - Each mapping contains:
    - `substandard_id`, `grade`, `substandard_description`, `assessment_boundary`
    - `final_excellent_matches`: top 5 sequences (up to 5)
    - `bruteforce_metadata`: evaluation stats
    - `phase1_selected_skills`: preserved from old mapping (if available)

- **`outputs/bruteforce_remap_report_all_grade3.md`**
  - Summary report with statistics and findings

- **`outputs/generate_all_grade3_mappings.log`**
  - Processing log file

---

## Usage

```bash
cd "Experiment : Find existing mappings"
python scripts/generate_all_grade3_mappings.py
```

**Requirements:**
- GEMINI_API_KEY environment variable must be set
- Python packages: pandas, google-generativeai, pydantic, python-dotenv

---

## Results

- **Coverage:** 47.3% of Grade 3 CCSS standards (53/112 substandards) have good alignment
- **Improvement:** +26.8 percentage points from original 20.5% coverage
- **Method:** Pure brute-force eliminates Phase 1 skill pre-selection bottlenecks

