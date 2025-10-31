#!/usr/bin/env python3
"""
Regenerate sequences for lessons where all sequences were rejected.
Uses validation feedback (failed sequences, reasoning, suggestions) to generate better sequences.
"""

import os
import json
import csv
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Pydantic Schemas
# ============================================================================

class SequenceItem(BaseModel):
    """Individual sequence item for a substandard."""
    sequence_number: int
    problem_type: str
    example_questions: List[str] = Field(..., min_items=2)
    visual_aids: Optional[List[str]] = None

class RegeneratedSequenceResponse(BaseModel):
    """Response containing regenerated sequences for a substandard."""
    substandard_id: str
    sequences: List[SequenceItem] = Field(..., min_items=1, max_items=5)
    generation_reasoning: str

# ============================================================================
# Helper Functions
# ============================================================================

def produce_structured_response_gemini(
    prompt: str,
    structure_model: type[BaseModel],
    llm_model: str = "gemini-2.5-pro",
) -> BaseModel:
    """Generate structured response using Gemini."""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": structure_model,
            },
        )
        json_text = response.candidates[0].content.parts[0].text
        return structure_model.model_validate_json(json_text)
    except Exception as e:
        print(f"❌ Gemini generation failed: {e}")
        raise

def load_prompt_template(template_name: str) -> str:
    """Load prompt template from prompts/ directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(script_dir, "prompts")
    template_path = os.path.join(prompts_dir, f"{template_name}.txt")
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()

def load_validation_results(json_path: str) -> dict:
    """Load validation results from JSON file."""
    print(f"📥 Loading validation results from: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ Loaded validation for {data['metadata']['total_lessons_processed']} lessons")
    return data

def load_original_sequences(json_path: str) -> dict:
    """Load original generated sequences from JSON file."""
    print(f"📥 Loading original sequences from: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Index by substandard_id for easy lookup
    sequences_by_id = {}
    for entry in data.get('generated_sequences', []):
        substandard_id = entry.get('substandard_id')
        if substandard_id:
            sequences_by_id[substandard_id] = entry
    
    print(f"✅ Loaded original sequences for {len(sequences_by_id)} lessons")
    return sequences_by_id

def load_curriculum_data(csv_path: str) -> dict:
    """Load curriculum data from CSV and index by substandard_id."""
    print(f"📥 Loading curriculum data from: {csv_path}")
    
    curriculum = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            substandard_id = row.get('Substandard ID', '').strip()
            if substandard_id:
                curriculum[substandard_id] = {
                    'substandard_id': substandard_id,
                    'substandard_description': row.get('Substandard Description', ''),
                    'assessment_boundary': row.get('Assessment Boundary', ''),
                    'tasks': row.get('Tasks', ''),
                    'step_by_step_explanation': row.get('Step By Step Explanation', ''),
                    'lesson_title': row.get('Lesson Title', ''),
                    'grade': row.get('Grade', '')
                }
    
    print(f"✅ Loaded {len(curriculum)} curriculum entries")
    return curriculum

def get_failed_lessons(validation_data: dict) -> list:
    """Get lessons where all sequences were rejected (sequences_kept = 0)."""
    failed_lessons = []
    
    for result in validation_data.get('validation_results', []):
        if result.get('sequences_kept', 0) == 0:
            failed_lessons.append(result)
    
    return failed_lessons

def create_regeneration_prompt(
    curriculum_entry: dict,
    original_sequences: list,
    validation_results: list,
    template: str
) -> str:
    """Create prompt for sequence regeneration with failure feedback."""
    
    # Format failed sequences with their feedback
    failed_sequences_text = json.dumps(validation_results, indent=2)
    original_sequences_text = json.dumps(original_sequences, indent=2)
    
    # Fill in template
    prompt = template.format(
        substandard_id=curriculum_entry['substandard_id'],
        grade=curriculum_entry.get('grade', '3.0'),
        substandard_description=curriculum_entry['substandard_description'],
        assessment_boundary=curriculum_entry['assessment_boundary'],
        tasks=curriculum_entry['tasks'],
        step_by_step_explanation=curriculum_entry['step_by_step_explanation'],
        lesson_title=curriculum_entry.get('lesson_title', 'N/A'),
        original_sequences=original_sequences_text,
        failed_validations=failed_sequences_text,
        num_failed=len(validation_results)
    )
    
    return prompt

def regenerate_sequences_for_lesson(
    curriculum_entry: dict,
    original_sequences: list,
    validation_results: list,
    template: str
) -> RegeneratedSequenceResponse:
    """Regenerate sequences for a lesson using failure feedback."""
    
    print(f"\n{'='*80}")
    print(f"Regenerating: {curriculum_entry['substandard_id']}")
    print(f"Lesson: {curriculum_entry.get('lesson_title', 'N/A')}")
    print(f"Failed sequences: {len(validation_results)}")
    print(f"{'='*80}")
    
    prompt = create_regeneration_prompt(
        curriculum_entry,
        original_sequences,
        validation_results,
        template
    )
    
    try:
        response = produce_structured_response_gemini(prompt, RegeneratedSequenceResponse)
        print(f"✅ Regenerated {len(response.sequences)} sequences")
        return response
    except Exception as e:
        print(f"❌ Regeneration failed: {e}")
        raise

def save_regenerated_sequences(results: list, output_filename: str = None):
    """Save regenerated sequences to JSON file."""
    
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"regenerated_sequences_{timestamp}.json"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    outputs_dir = os.path.join(os.path.dirname(script_dir), "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    
    output_path = os.path.join(outputs_dir, output_filename)
    
    output_data = {
        "metadata": {
            "generation_timestamp": datetime.now().isoformat(),
            "total_lessons_regenerated": len(results),
            "llm_model": "gemini-2.5-pro",
            "generation_version": "2.0_with_feedback",
            "based_on_validation": "sequence_validation_20251030_224655.json"
        },
        "regenerated_sequences": results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved regenerated sequences to: {output_path}")
    return output_path

# ============================================================================
# Main Function
# ============================================================================

def main():
    """Main execution function."""
    
    print("="*80)
    print("SEQUENCE REGENERATION WITH FAILURE FEEDBACK")
    print("="*80)
    
    # Check API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return
    
    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    csv_path = os.path.join(project_root, "data", "Copy of MATH DATA MODEL - 3rd Grade.csv")
    validation_path = os.path.join(project_root, "outputs", "filter", "sequence_validation_20251030_224655.json")
    original_sequences_path = os.path.join(project_root, "outputs", "generated_sequences_20251030_113708.json")
    
    # Load data
    print("\n📥 Loading data...")
    curriculum = load_curriculum_data(csv_path)
    validation_data = load_validation_results(validation_path)
    original_sequences_by_id = load_original_sequences(original_sequences_path)
    
    # Get lessons that failed completely
    print("\n🔍 Identifying lessons with 0 accepted sequences...")
    failed_lessons = get_failed_lessons(validation_data)
    print(f"Found {len(failed_lessons)} lessons needing regeneration")
    
    # Load prompt template
    print("\n📝 Loading prompt template...")
    template = load_prompt_template("sequence_regeneration")
    
    # Regenerate sequences
    print("\n🔨 Regenerating sequences with failure feedback...")
    results = []
    
    for i, failed_lesson in enumerate(failed_lessons, 1):
        substandard_id = failed_lesson.get('substandard_id')
        
        if not substandard_id:
            print(f"⚠️  Skipping entry {i}: No substandard_id")
            continue
        
        if substandard_id not in curriculum:
            print(f"⚠️  Skipping {substandard_id}: Not found in curriculum data")
            continue
        
        if substandard_id not in original_sequences_by_id:
            print(f"⚠️  Skipping {substandard_id}: Original sequences not found")
            continue
        
        print(f"\n[{i}/{len(failed_lessons)}]")
        
        try:
            curriculum_entry = curriculum[substandard_id]
            original_sequences = original_sequences_by_id[substandard_id].get('generated_sequences', [])
            validation_results = failed_lesson.get('sequence_validations', [])
            
            response = regenerate_sequences_for_lesson(
                curriculum_entry,
                original_sequences,
                validation_results,
                template
            )
            
            result = {
                "substandard_id": substandard_id,
                "lesson_title": curriculum_entry.get('lesson_title', 'N/A'),
                "grade": curriculum_entry.get('grade', 'N/A'),
                "substandard_description": curriculum_entry['substandard_description'],
                "assessment_boundary": curriculum_entry['assessment_boundary'],
                "tasks": curriculum_entry['tasks'],
                "step_by_step_explanation": curriculum_entry['step_by_step_explanation'],
                "original_sequences": original_sequences,
                "validation_feedback": validation_results,
                "regenerated_sequences": [seq.model_dump() for seq in response.sequences],
                "generation_reasoning": response.generation_reasoning,
                "regenerated_at": datetime.now().isoformat()
            }
            
            results.append(result)
            
            # Show regenerated sequences
            for seq in response.sequences:
                print(f"  ✨ Seq #{seq.sequence_number}: {seq.problem_type}")
            
        except Exception as e:
            print(f"❌ Failed to regenerate for {substandard_id}: {e}")
            continue
    
    # Save results
    if results:
        output_path = save_regenerated_sequences(results)
        
        print(f"\n{'='*80}")
        print("REGENERATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total lessons regenerated: {len(results)}")
        print(f"Total new sequences: {sum(len(r['regenerated_sequences']) for r in results)}")
        print(f"\nLessons regenerated:")
        for r in results:
            print(f"  • {r['substandard_id']}: {r['lesson_title']}")
        print(f"\nOutput: {output_path}")
        print(f"\n💡 Next step: Run validate_generated_sequences.py on the regenerated sequences")
    else:
        print("\n⚠️  No sequences were regenerated")

if __name__ == "__main__":
    main()

