#!/usr/bin/env python3
"""
Generate DI-style formats for newly generated sequences.
Uses existing formats as exemplars and follows DI instructional design principles.
"""

import os
import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Pydantic Schemas (same as generate_formats.py)
# ============================================================================

class FormatStep(BaseModel):
    """Individual step in a format with teacher and student components."""
    step_number: int
    teacher_action: str
    student_response: Optional[str] = None
    notes: Optional[str] = None

class FormatPart(BaseModel):
    """A part within a format (e.g., Part A, Part B)."""
    part_name: str
    description: Optional[str] = None
    steps: List[FormatStep] = Field(..., min_items=1)

class GeneratedFormat(BaseModel):
    """Individual format for teaching a sequence."""
    format_number: str
    title: str
    parts: List[FormatPart] = Field(..., min_items=1)
    grade: int
    sequence_numbers: List[int]
    grade_assignment_reasoning: str

class GeneratedFormatResponse(BaseModel):
    """Response containing generated format for a sequence."""
    format: GeneratedFormat
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

def load_generated_sequences():
    """Load newly generated sequences."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    outputs_dir = os.path.join(os.path.dirname(script_dir), "outputs")
    
    # Find the most recent generated_sequences file
    generated_files = [f for f in os.listdir(outputs_dir) if f.startswith('generated_sequences_') and f.endswith('.json')]
    
    if not generated_files:
        print("❌ No generated sequences files found")
        return None
    
    # Sort by filename (timestamp) and get the latest
    generated_files.sort(reverse=True)
    latest_file = generated_files[0]
    
    file_path = os.path.join(outputs_dir, latest_file)
    print(f"📥 Loading generated sequences from: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data

def load_di_formats():
    """Load existing DI formats as exemplars."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    di_path = os.path.join(
        project_root,
        "..",
        "Experiment - Find existing mappings",
        "inputs",
        "di_formats_with_mappings.json"
    )
    
    print(f"📥 Loading DI formats from: {di_path}")
    
    with open(di_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data

def get_exemplar_formats(di_data, grade: int = 3, limit: int = 10):
    """Extract exemplar formats from DI data."""
    exemplars = []
    
    for skill_name, skill_data in di_data.get('skills', {}).items():
        for fmt in skill_data.get('formats', []):
            fmt_grade = fmt.get('grade') or fmt.get('assigned_grade')
            if fmt_grade == grade:
                exemplars.append({
                    'skill': skill_name,
                    'format_number': fmt.get('format_number'),
                    'title': fmt.get('title'),
                    'parts': fmt.get('parts', []),
                    'grade': fmt_grade,
                    'sequence_numbers': fmt.get('sequence_numbers', [])
                })
                
                if len(exemplars) >= limit:
                    break
        
        if len(exemplars) >= limit:
            break
    
    return exemplars

def create_format_generation_prompt(
    substandard_data: dict,
    sequence: dict,
    exemplars: list,
    template: str
) -> str:
    """Create prompt for format generation."""
    
    exemplar_text = json.dumps(exemplars[:5], indent=2)
    
    prompt = template.format(
        skill=f"Generated for {substandard_data['substandard_id']}",
        grade=substandard_data['grade'],
        sequence_number=sequence['sequence_number'],
        problem_type=sequence['problem_type'],
        example_questions=json.dumps(sequence.get('example_questions', []), indent=2),
        visual_aids=sequence.get('visual_aids') if sequence.get('visual_aids') else "None",
        exemplar_formats=exemplar_text
    )
    
    return prompt

def generate_format_for_sequence(
    substandard_data: dict,
    sequence: dict,
    exemplars: list,
    template: str,
    format_number: str
) -> GeneratedFormatResponse:
    """Generate a format for a single sequence."""
    
    print(f"\n{'='*80}")
    print(f"Generating format for: {substandard_data['substandard_id']}")
    print(f"Sequence #{sequence['sequence_number']}: {sequence['problem_type'][:60]}...")
    print(f"{'='*80}")
    
    prompt = create_format_generation_prompt(substandard_data, sequence, exemplars, template)
    
    try:
        response = produce_structured_response_gemini(prompt, GeneratedFormatResponse)
        response.format.format_number = format_number
        print(f"✅ Generated format: {response.format.title}")
        return response
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        raise

def save_generated_formats(results: list, output_filename: str = None):
    """Save generated formats to JSON file."""
    
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"generated_formats_new_sequences_{timestamp}.json"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    outputs_dir = os.path.join(os.path.dirname(script_dir), "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    
    output_path = os.path.join(outputs_dir, output_filename)
    
    output_data = {
        "metadata": {
            "generation_timestamp": datetime.now().isoformat(),
            "total_sequences_processed": len(results),
            "llm_model": "gemini-2.5-pro",
            "generation_version": "1.0",
            "source": "newly_generated_sequences"
        },
        "generated_formats": results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved generated formats to: {output_path}")
    return output_path

# ============================================================================
# Main Function
# ============================================================================

def main():
    """Main execution function."""
    
    print("="*80)
    print("DI FORMAT GENERATOR - NEW SEQUENCES")
    print("="*80)
    
    # Check API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return
    
    # Load data
    print("\n📥 Loading data...")
    generated_data = load_generated_sequences()
    if not generated_data:
        return
    
    di_data = load_di_formats()
    
    # Get exemplar formats
    print("\n📚 Loading exemplar formats...")
    exemplars = get_exemplar_formats(di_data, grade=3, limit=10)
    print(f"Loaded {len(exemplars)} exemplar formats")
    
    # Load prompt template
    print("\n📝 Loading prompt template...")
    template = load_prompt_template("format_generation")
    
    # Generate formats
    print("\n🔨 Generating formats for new sequences...")
    results = []
    format_counter = 1
    
    generated_sequences = generated_data.get('generated_sequences', [])
    
    # Process first 3 for testing (change to all for full run)
    for i, substandard_data in enumerate(generated_sequences, 1):
        print(f"\n[Substandard {i}/{len(generated_sequences)}] {substandard_data['substandard_id']}")
        
        for seq_idx, sequence in enumerate(substandard_data['generated_sequences'], 1):
            try:
                format_number = f"NEW.{format_counter}"
                
                response = generate_format_for_sequence(
                    substandard_data,
                    sequence,
                    exemplars,
                    template,
                    format_number
                )
                
                result = {
                    "substandard_id": substandard_data['substandard_id'],
                    "substandard_description": substandard_data['substandard_description'],
                    "grade": substandard_data['grade'],
                    "sequence_number": sequence['sequence_number'],
                    "problem_type": sequence['problem_type'],
                    "generated_format": response.format.model_dump(),
                    "generation_reasoning": response.generation_reasoning,
                    "generated_at": datetime.now().isoformat()
                }
                
                results.append(result)
                format_counter += 1
                
                print(f"  ✓ Seq #{seq_idx}/{len(substandard_data['generated_sequences'])} → Format {format_number}")
                
            except Exception as e:
                print(f"  ❌ Failed for sequence #{seq_idx}: {e}")
                continue
    
    # Save results
    if results:
        output_path = save_generated_formats(results)
        
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Substandards processed: {min(3, len(generated_sequences))}")
        print(f"Formats generated: {len(results)}")
        print(f"Output: {output_path}")
    else:
        print("\n⚠️  No formats were generated")

if __name__ == "__main__":
    main()

