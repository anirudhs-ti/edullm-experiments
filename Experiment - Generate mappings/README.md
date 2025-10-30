# Experiment: Generate Mappings

**Purpose:** Generate custom DI-style sequences and formats for Grade 3 substandards that had poor or no matches in the existing DI materials.

---

## Overview

The "Find existing mappings" experiment showed that 47.3% of Grade 3 substandards have good alignments with existing DI sequences. This experiment generates new sequences for the remaining ~53% that need custom content.

## Approach

1. **Identify gaps**: Load substandards with poor/no matches (fewer than 2 good matches)
2. **Use exemplars**: Extract existing DI sequences as examples of good DI-style problems
3. **Generate sequences**: Use LLM to create new sequences following DI principles
4. **Respect constraints**: Strictly enforce assessment boundaries and grade alignment

## Folder Structure

```
Experiment - Generate mappings/
├── scripts/
│   ├── generate_sequences.py          # Main sequence generation script
│   └── prompts/
│       └── sequence_generation.txt    # Prompt template for sequence generation
└── outputs/
    └── generated_sequences_*.json     # Generated sequences with metadata
```

---

## Files Description

### Scripts

- **`scripts/generate_sequences.py`**
  - Loads substandards with poor/no matches from existing mappings
  - Extracts exemplar DI sequences as examples
  - Generates 2-5 new sequences per substandard using Gemini 2.5 Pro
  - Validates against assessment boundaries
  - Outputs structured JSON with generated sequences

- **`scripts/generate_formats.py`**
  - Finds sequences without teaching formats
  - Uses existing DI formats as exemplars
  - Generates complete teaching formats (teacher actions + student responses)
  - Follows DI instructional methodology
  - Outputs structured JSON with generated formats

- **`scripts/generate_formats_for_new_sequences.py`**
  - Generates formats specifically for newly generated sequences
  - Loads from latest `generated_sequences_*.json` file
  - Uses existing DI formats as exemplars
  - Outputs separate format file for new content

### Prompts

- **`scripts/prompts/sequence_generation.txt`**
  - Template for sequence generation prompt
  - Includes DI principles, exemplar format, and constraints
  - Ensures generated sequences follow DI methodology

- **`scripts/prompts/format_generation.txt`**
  - Template for format generation prompt
  - Includes DI teaching principles (Model-Test-Practice)
  - Ensures formats follow explicit instruction methodology
  - Converts classroom language to online equivalents

### Output Files

- **`outputs/generated_sequences_*.json`**
  - Contains generated sequences for each substandard
  - Includes metadata, reasoning, and timestamp
  - Structure:
    ```json
    {
      "metadata": {
        "generation_timestamp": "...",
        "total_substandards_processed": N,
        "llm_model": "gemini-2.5-pro"
      },
      "generated_sequences": [
        {
          "substandard_id": "...",
          "grade": 3,
          "substandard_description": "...",
          "assessment_boundary": "...",
          "generated_sequences": [
            {
              "sequence_number": 1,
              "problem_type": "...",
              "example_questions": [...],
              "visual_aids": [...]
            }
          ],
          "generation_reasoning": "..."
        }
      ]
    }
    ```

---

## Usage

### Step 1: Generate Sequences
```bash
cd "Experiment - Generate mappings"
python scripts/generate_sequences.py
```
Generates sequences for substandards with poor/no matches.

### Step 2: Generate Formats (Existing Sequences)
```bash
python scripts/generate_formats.py
```
Generates formats for existing sequences that lack them.

### Step 3: Generate Formats (New Sequences)
```bash
python scripts/generate_formats_for_new_sequences.py
```
Generates formats for newly created sequences.

**Requirements:**
- GEMINI_API_KEY environment variable must be set
- Python packages: google-generativeai, pydantic, python-dotenv

**Configuration:**
- `generate_sequences.py`: Processes all substandards needing sequences
- `generate_formats.py`: Processes first 3 existing sequences for testing
- `generate_formats_for_new_sequences.py`: Processes first 3 new sequences for testing
- Remove `[:3]` limits to process all

---

## DI Principles Applied

The generation follows Direct Instruction methodology:

1. **Spiral Curriculum**: Sequences progress from simple to complex
2. **Explicit Instruction**: Clear, unambiguous problem statements
3. **Mastery-Based**: Each sequence builds on previous understanding
4. **Minimal Cognitive Load**: One new concept per sequence
5. **Systematic Review**: Problems revisit and reinforce prior skills
6. **Example-Rich**: Multiple concrete examples per sequence type

---

## Next Steps

1. Generate sequences for all substandards needing them
2. Validate generated sequences against assessment boundaries
3. Create matching formats (teaching scripts) for each sequence
4. Re-run Grade 3 mapping with augmented sequence library
5. Human review of edge cases and boundary violations

