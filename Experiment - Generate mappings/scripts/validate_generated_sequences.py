#!/usr/bin/env python3
"""
Validate generated sequences against intended lesson design using LLM.
Checks if generated sequences align with Tasks and Step By Step Explanation from curriculum.
"""

import os
import json
import csv
import sys
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Pydantic Schemas
# ============================================================================

class SingleSequenceValidation(BaseModel):
    """Validation result for a single sequence."""
    sequence_number: int
    alignment_score: float = Field(..., ge=0.0, le=1.0, description="Score between 0 and 1")
    reasoning: str = Field(..., description="Why this score was given")
    should_keep: bool = Field(..., description="Whether to keep this sequence")
    suggestions: str = Field(..., description="How to improve if not keeping")

class ValidationResponse(BaseModel):
    """Response containing validation for a single sequence."""
    validation: SingleSequenceValidation

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

def load_generated_sequences(json_path: str) -> list:
    """Load generated sequences from JSON file."""
    print(f"📥 Loading generated sequences from: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    sequences = data.get('generated_sequences', [])
    print(f"✅ Loaded {len(sequences)} generated sequence sets")
    return sequences

def create_validation_prompt(
    curriculum_entry: dict,
    sequence: dict,
    template: str
) -> str:
    """Create validation prompt for a single sequence."""
    
    # Format sequence for prompt
    sequence_text = json.dumps(sequence, indent=2)
    
    # Fill in template
    prompt = template.format(
        substandard_id=curriculum_entry['substandard_id'],
        substandard_description=curriculum_entry['substandard_description'],
        assessment_boundary=curriculum_entry['assessment_boundary'],
        tasks=curriculum_entry['tasks'],
        step_by_step_explanation=curriculum_entry['step_by_step_explanation'],
        lesson_title=curriculum_entry.get('lesson_title', 'N/A'),
        sequence=sequence_text,
        sequence_number=sequence.get('sequence_number', 0)
    )
    
    return prompt

def validate_single_sequence(
    curriculum_entry: dict,
    sequence: dict,
    template: str
) -> SingleSequenceValidation:
    """Validate a single sequence against curriculum intent."""
    
    prompt = create_validation_prompt(curriculum_entry, sequence, template)
    
    try:
        response = produce_structured_response_gemini(prompt, ValidationResponse)
        return response.validation
    except Exception as e:
        print(f"❌ Validation failed for sequence {sequence.get('sequence_number')}: {e}")
        raise

def save_validation_results(results: list, output_filename: str = None):
    """Save validation results to JSON file."""
    
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"sequence_validation_{timestamp}.json"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    outputs_dir = os.path.join(os.path.dirname(script_dir), "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    
    output_path = os.path.join(outputs_dir, output_filename)
    
    # Calculate summary statistics
    total_sequences_evaluated = sum(len(r['sequence_validations']) for r in results)
    all_sequences = [seq for r in results for seq in r['sequence_validations']]
    
    kept_sequences = sum(1 for seq in all_sequences if seq['should_keep'])
    rejected_sequences = total_sequences_evaluated - kept_sequences
    
    avg_score = sum(seq['alignment_score'] for seq in all_sequences) / len(all_sequences) if all_sequences else 0
    
    output_data = {
        "metadata": {
            "validation_timestamp": datetime.now().isoformat(),
            "total_lessons_processed": len(results),
            "total_sequences_evaluated": total_sequences_evaluated,
            "sequences_kept": kept_sequences,
            "sequences_rejected": rejected_sequences,
            "llm_model": "gemini-2.5-pro",
            "validation_version": "2.0"
        },
        "summary_statistics": {
            "average_alignment_score": round(avg_score, 3),
            "keep_rate": round(kept_sequences / total_sequences_evaluated, 3) if total_sequences_evaluated > 0 else 0,
            "reject_rate": round(rejected_sequences / total_sequences_evaluated, 3) if total_sequences_evaluated > 0 else 0
        },
        "validation_results": results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved validation results to: {output_path}")
    return output_path

# ============================================================================
# Main Function
# ============================================================================

def main():
    """Main execution function."""
    
    print("="*80)
    print("SEQUENCE VALIDATION AGAINST CURRICULUM INTENT")
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
    sequences_path = os.path.join(project_root, "outputs", "generated_sequences_20251030_113708.json")
    
    # Load data
    print("\n📥 Loading data...")
    curriculum = load_curriculum_data(csv_path)
    generated_sequences_data = load_generated_sequences(sequences_path)
    
    # Load prompt template
    print("\n📝 Loading prompt template...")
    template = load_prompt_template("sequence_validation")
    
    # Validate sequences
    print("\n🔍 Validating sequences...")
    results = []
    
    for i, seq_entry in enumerate(generated_sequences_data, 1):
        substandard_id = seq_entry.get('substandard_id')
        
        if not substandard_id:
            print(f"⚠️  Skipping entry {i}: No substandard_id")
            continue
        
        if substandard_id not in curriculum:
            print(f"⚠️  Skipping {substandard_id}: Not found in curriculum data")
            continue
        
        print(f"\n[{i}/{len(generated_sequences_data)}] {substandard_id}")
        print(f"{'='*80}")
        
        curriculum_entry = curriculum[substandard_id]
        generated_sequences = seq_entry.get('generated_sequences', [])
        
        print(f"Lesson: {curriculum_entry.get('lesson_title', 'N/A')}")
        print(f"Sequences to validate: {len(generated_sequences)}")
        
        sequence_validations = []
        
        for sequence in generated_sequences:
            seq_num = sequence.get('sequence_number', 0)
            print(f"\n  Validating Sequence #{seq_num}...", end=' ')
            
            try:
                validation = validate_single_sequence(
                    curriculum_entry,
                    sequence,
                    template
                )
                
                sequence_validations.append({
                    "sequence_number": validation.sequence_number,
                    "problem_type": sequence.get('problem_type', ''),
                    "alignment_score": validation.alignment_score,
                    "should_keep": validation.should_keep,
                    "reasoning": validation.reasoning,
                    "suggestions": validation.suggestions
                })
                
                # Display result
                if validation.should_keep:
                    print(f"🟢 KEEP (score: {validation.alignment_score:.2f})")
                else:
                    print(f"🔴 REJECT (score: {validation.alignment_score:.2f})")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
        
        result = {
            "substandard_id": substandard_id,
            "lesson_title": curriculum_entry.get('lesson_title', 'N/A'),
            "grade": curriculum_entry.get('grade', 'N/A'),
            "total_sequences": len(generated_sequences),
            "sequences_kept": sum(1 for v in sequence_validations if v['should_keep']),
            "sequences_rejected": sum(1 for v in sequence_validations if not v['should_keep']),
            "sequence_validations": sequence_validations,
            "validated_at": datetime.now().isoformat()
        }
        
        results.append(result)
        print(f"\n  Summary: {result['sequences_kept']} kept, {result['sequences_rejected']} rejected")
    
    # Save results
    if results:
        output_path = save_validation_results(results)
        
        print(f"\n{'='*80}")
        print("VALIDATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total lessons processed: {len(results)}")
        
        total_sequences = sum(r['total_sequences'] for r in results)
        total_kept = sum(r['sequences_kept'] for r in results)
        total_rejected = sum(r['sequences_rejected'] for r in results)
        
        print(f"Total sequences evaluated: {total_sequences}")
        print(f"  🟢 Kept: {total_kept} ({total_kept/total_sequences*100:.1f}%)")
        print(f"  🔴 Rejected: {total_rejected} ({total_rejected/total_sequences*100:.1f}%)")
        print(f"\nOutput: {output_path}")
    else:
        print("\n⚠️  No sequences were validated")

if __name__ == "__main__":
    main()

