#!/usr/bin/env python3
"""
Utility functions for question generation.
Includes: data loading, misconceptions, LLM calls, Langfuse integration.
"""

import os
import json
import time
import random
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from litellm import completion
from dotenv import load_dotenv
from functools import wraps

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Try to import Langfuse
try:
    from langfuse import observe, Langfuse
    
    # Initialize Langfuse client
    langfuse_client = Langfuse()
    LANGFUSE_AVAILABLE = True
    print("✅ Langfuse tracing enabled")
except Exception as e:
    LANGFUSE_AVAILABLE = False
    print(f"⚠️  Langfuse not available: {e}")
    
    # Create dummy decorator if Langfuse not available
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])
    
    langfuse_client = None

# Set up API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    os.environ['GEMINI_API_KEY'] = GEMINI_API_KEY


# ============================================================================
# Data Loading
# ============================================================================

class SubstandardData:
    """Container for substandard data."""
    def __init__(self, substandard_id, substandard_description, assessment_boundary,
                 grade, sequence, format_data):
        self.substandard_id = substandard_id
        self.substandard_description = substandard_description
        self.assessment_boundary = assessment_boundary
        self.grade = grade
        self.sequence = sequence
        self.format_data = format_data


def load_substandards(json_path: str, num_substandards: int = 30, 
                     random_seed: int = None) -> List[SubstandardData]:
    """Load and prepare substandards for question generation."""
    if random_seed is not None:
        random.seed(random_seed)
    
    print(f"Loading data from: {json_path}")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    substandards = data.get('substandards', [])
    print(f"Loaded {len(substandards)} substandards")
    
    # Filter substandards with formats
    filtered = [s for s in substandards 
                if any(seq.get('format') for seq in s.get('sequences', []))]
    print(f"Filtered to {len(filtered)} substandards with formats")
    
    # Random selection
    if len(filtered) <= num_substandards:
        selected = filtered
    else:
        selected = random.sample(filtered, num_substandards)
    print(f"Selected {len(selected)} substandards")
    
    # Prepare data
    prepared = []
    for substandard in selected:
        sequences_with_formats = [
            seq for seq in substandard.get('sequences', [])
            if seq.get('format') is not None
        ]
        if not sequences_with_formats:
            continue
        
        # Randomly select one sequence
        sequence = random.choice(sequences_with_formats)
        
        prepared.append(SubstandardData(
            substandard_id=substandard.get('substandard_id'),
            substandard_description=substandard.get('substandard_description'),
            assessment_boundary=substandard.get('assessment_boundary'),
            grade=substandard.get('grade'),
            sequence=sequence,
            format_data=sequence.get('format')
        ))
    
    print(f"Prepared {len(prepared)} substandards for generation")
    return prepared


def load_misconceptions(csv_path: str) -> Dict[str, List[str]]:
    """Load misconceptions from CSV."""
    print(f"Loading misconceptions from: {csv_path}")
    df = pd.read_csv(csv_path, keep_default_na=False)
    
    misconception_cols = [
        "Common Misconception 1",
        "Common Misconception 2",
        "Common Misconception 3",
        "Common Misconception 4"
    ]
    
    misconceptions_map = {}
    for _, row in df.iterrows():
        substandard_id = str(row.get("Substandard ID", "")).strip()
        if not substandard_id or substandard_id == "nan":
            continue
        
        misconceptions = []
        for col in misconception_cols:
            if col in df.columns:
                value = str(row[col]).strip()
                if value and value != "nan" and value != "N/A":
                    misconceptions.append(value)
        
        if misconceptions:
            misconceptions_map[substandard_id] = misconceptions
    
    print(f"Loaded misconceptions for {len(misconceptions_map)} substandards")
    return misconceptions_map


# ============================================================================
# LLM Calls with Retry Logic
# ============================================================================

def retry_with_backoff(max_retries: int = 3, initial_delay: float = 30.0):
    """Decorator for retry logic with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    if ('rate' in error_str or '429' in error_str or 'quota' in error_str):
                        if attempt < max_retries:
                            print(f"   ⏳ Rate limit. Waiting {delay:.0f}s before retry {attempt + 1}/{max_retries}...")
                            time.sleep(delay)
                            delay *= 2
                            continue
                    raise e
            return None
        return wrapper
    return decorator


@observe(name="format_to_scaffolding")
@retry_with_backoff(max_retries=3, initial_delay=30.0)
def convert_format_to_scaffolding(format_data: Dict, model: str = "gemini/gemini-2.0-flash-exp") -> str:
    """Convert DI format to scaffolding using LLM."""
    time.sleep(2)  # Rate limiting
    
    format_title = format_data.get('title', '')
    parts = format_data.get('parts', [])
    
    # Build prompt
    steps_text = []
    for part in parts:
        steps_text.append(f"\n{part.get('part_name', '')}:")
        for step in part.get('steps', []):
            teacher_action = step.get('teacher_action', '')
            steps_text.append(f"- {teacher_action}")
    
    prompt = f"""Convert the following teaching format into a concise, student-friendly step-by-step explanation.

FORMAT TITLE: {format_title}

TEACHING STEPS:
{chr(10).join(steps_text)}

INSTRUCTIONS:
1. Distill into clear, sequential explanation
2. Write in second person ("you should...")
3. Keep concise (3-5 sentences)
4. Include key hints from the teaching steps

Generate a natural explanation:"""
    
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": "You are an educational content expert. Convert teaching formats into concise student explanations."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    scaffolding = response.choices[0].message.content.strip()
    return scaffolding


@observe(name="generate_plan")
@retry_with_backoff(max_retries=3, initial_delay=30.0)
def generate_plan(substandard_data: SubstandardData, misconceptions: List[str],
                 template: str, model: str = "gemini/gemini-2.0-flash-exp") -> str:
    """Generate question plan (System A)."""
    time.sleep(2)  # Rate limiting
    
    # Format data
    example_questions_text = "\n".join(
        f"- {q}" for q in substandard_data.sequence.get('example_questions', [])[:5]
    )
    misconceptions_text = "\n".join(f"- {m}" for m in misconceptions) if misconceptions else "None documented"
    
    # Fill template
    prompt = template.format(
        substandard_id=substandard_data.substandard_id,
        grade=substandard_data.grade,
        substandard_description=substandard_data.substandard_description,
        assessment_boundary=substandard_data.assessment_boundary,
        problem_type=substandard_data.sequence.get('problem_type', ''),
        example_questions=example_questions_text,
        misconceptions=misconceptions_text,
        format_number=substandard_data.format_data.get('format_number', ''),
        format_title=substandard_data.format_data.get('title', '')
    )
    
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert educational content planner."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    
    plan = response.choices[0].message.content.strip()
    return plan


@observe(name="generate_question")
@retry_with_backoff(max_retries=3, initial_delay=30.0)
def generate_question(plan: str, scaffolding: str, substandard_data: SubstandardData,
                     question_id: str, template: str, 
                     model: str = "gemini/gemini-2.0-flash-exp") -> Dict:
    """Generate final question JSON (System B)."""
    time.sleep(2)  # Rate limiting
    
    # Fill template
    prompt = template.format(
        plan=plan,
        scaffolding=scaffolding,
        format_number=substandard_data.format_data.get('format_number', ''),
        format_title=substandard_data.format_data.get('title', ''),
        substandard_id=substandard_data.substandard_id,
        grade=substandard_data.grade,
        substandard_description=substandard_data.substandard_description,
        question_id=question_id
    )
    
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert educational content creator. Generate complete MCQ questions. Respond with ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    
    question = json.loads(response.choices[0].message.content.strip())
    
    # Add metadata if missing
    if not question.get('additional_details'):
        from datetime import datetime
        question['additional_details'] = (
            f"Generated from {substandard_data.substandard_id}, "
            f"format {substandard_data.format_data.get('format_number')}, "
            f"at {datetime.now().isoformat()}"
        )
    
    return question


# ============================================================================
# Prompt Loading
# ============================================================================

def load_prompt(filename: str) -> str:
    """Load prompt template from file."""
    prompt_path = Path(__file__).parent / "prompts" / filename
    with open(prompt_path, 'r') as f:
        return f.read()

