# Question Generation System

Automated MCQ generation for Grade 3 mathematics using LLMs with Langfuse tracing.

## Quick Start

```bash
# 1. Activate Python 3.13 environment  
cd "/workspaces/github-com-anirudhs-ti-edullm-experiments/Question Generation"
source venv_py313/bin/activate

# 2. Run generation
cd scripts

# Test with 2 questions (~1 minute)
python generate_questions.py 2 42

# Full generation with 30 questions (~10-15 minutes)
python generate_questions.py 30 42

# Custom: N questions with seed S
python generate_questions.py N S
```

## What's New (Latest Version)

✅ **Langfuse v3 tracing enabled** - All LLM calls are now traced  
✅ **Consolidated to 2 files** - Simplified codebase (was 11 files, now 2!)  
✅ **Python 3.13** - Fixed compatibility issues  
✅ **@observe decorators** - Clean tracing with Langfuse v3 API

## File Structure

```
Question Generation/
├── scripts/
│   ├── generate_questions.py  # Main script (run this!)
│   ├── utils.py               # Helper functions
│   └── prompts/
│       ├── system_a_plan_generation.txt
│       └── system_b_question_generation.txt
├── data/
│   └── composed_substandards.json
├── outputs/
│   └── generated_questions_*.json
├── venv_py313/                 # Python 3.13 virtual environment
└── .env                        # API keys (Gemini, Langfuse)
```

## Output

Questions saved to: `outputs/generated_questions_TIMESTAMP.json`

Format:
```json
{
  "subject": "math",
  "grade": "3",
  "type": "mcq",
  "generated_questions": [
    {
      "id": "q1",
      "type": "mcq",
      "question": "...",
      "answer": "C",
      "answer_explanation": "...",
      "answer_options": {"A": "...", "B": "...", "C": "..."},
      "skill": {...}
    }
  ],
  "metadata": {...}
}
```

## Langfuse Tracing

✅ **Enabled** - View traces at https://cloud.langfuse.com

Traces include:
- `generate_question_for_substandard` - Overall question generation
- `format_to_scaffolding` - Format conversion  
- `generate_plan` - System A (plan generation)
- `generate_question` - System B (final question)

## Configuration

Edit `.env` file:
```
GEMINI_API_KEY=your_key_here
LANGFUSE_SECRET_KEY=your_key_here
LANGFUSE_PUBLIC_KEY=your_key_here
```

## System Architecture

```
Load Data → Get Misconceptions → For each substandard:
  │
  ├─> Convert Format to Scaffolding (LLM + @observe)
  ├─> Generate Plan with System A (LLM + @observe)  
  └─> Generate Question with System B (LLM + @observe)
       │
       └─> Save to JSON
```

## Notes

- ⏱️ **Rate Limits**: Gemini API has 10 requests/minute  
- 🔄 **Auto Retry**: Automatically retries on rate limits
- 📊 **Tracing**: All LLM calls logged to Langfuse
- ✅ **Tested**: 2/2 questions generated successfully

## When Done

```bash
deactivate
```

That's it! 🎉
