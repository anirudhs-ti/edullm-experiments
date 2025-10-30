#!/usr/bin/env python3
"""
Generate DI-style sequences for Grade 3 substandards with poor/no mappings.
Uses existing sequences as exemplars and follows DI principles.
"""

import os
import json
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

class SequenceItem(BaseModel):
    """Individual sequence item for a substandard."""
    sequence_number: int
    problem_type: str
    example_questions: List[str] = Field(..., min_items=2)
    visual_aids: Optional[List[str]] = None

class GeneratedSequenceResponse(BaseModel):
    """Response containing generated sequences for a substandard."""
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

def load_mappings_data(grade: int = 3):
    """Load existing mappings data."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mappings_path = os.path.join(
        project_root, 
        "..", 
        "Experiment - Find existing mappings",
        "outputs",
        "substandard_to_sequence_mappings.v3.json"
    )
    
    print(f"Loading mappings from: {mappings_path}")
    
    with open(mappings_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data

def load_di_formats():
    """Load DI formats with existing sequences."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    di_path = os.path.join(
        project_root,
        "..",
        "Experiment - Find existing mappings",
        "inputs",
        "di_formats_with_mappings.json"
    )
    
    print(f"Loading DI formats from: {di_path}")
    
    with open(di_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data

def get_substandards_needing_sequences(mappings_data, threshold: int = 2):
    """
    Get substandards that need new sequences (have few or poor matches).
    
    Args:
        mappings_data: Loaded mappings data
        threshold: Minimum number of good matches required
    
    Returns:
        List of substandards that need sequences
    """
    needs_sequences = []
    
    for mapping in mappings_data.get('mappings', []):
        num_matches = len(mapping.get('final_excellent_matches', []))
        
        if num_matches < threshold:
            needs_sequences.append({
                'substandard_id': mapping['substandard_id'],
                'grade': mapping['grade'],
                'substandard_description': mapping['substandard_description'],
                'assessment_boundary': mapping['assessment_boundary'],
                'current_matches': num_matches
            })
    
    return needs_sequences

def get_exemplar_sequences(di_data, grade: int = 3, skill: str = None):
    """
    Extract exemplar sequences from DI data.
    
    Args:
        di_data: Loaded DI formats data
        grade: Grade level to filter
        skill: Optional skill name to filter
    
    Returns:
        List of exemplar sequences
    """
    exemplars = []
    
    for skill_name, skill_data in di_data.get('skills', {}).items():
        if skill and skill_name != skill:
            continue
        
        for progression in skill_data.get('progression', []):
            if progression.get('grade') == grade:
                for seq in progression.get('sequence', []):
                    exemplars.append({
                        'skill': skill_name,
                        'grade': grade,
                        'sequence_number': seq.get('sequence_number'),
                        'problem_type': seq.get('problem_type'),
                        'example_questions': seq.get('example_questions', []),
                        'visual_aids': seq.get('visual_aids')
                    })
    
    return exemplars

def create_sequence_generation_prompt(
    substandard: dict,
    exemplars: list,
    template: str
) -> str:
    """Create prompt for sequence generation."""
    
    # Format exemplars for prompt
    exemplar_text = json.dumps(exemplars[:10], indent=2)  # Limit to 10 exemplars
    
    # Fill in template
    prompt = template.format(
        grade=substandard['grade'],
        substandard_id=substandard['substandard_id'],
        substandard_description=substandard['substandard_description'],
        assessment_boundary=substandard['assessment_boundary'],
        exemplar_sequences=exemplar_text
    )
    
    return prompt

def generate_sequences_for_substandard(
    substandard: dict,
    exemplars: list,
    template: str
) -> GeneratedSequenceResponse:
    """Generate sequences for a single substandard."""
    
    print(f"\n{'='*80}")
    print(f"Generating sequences for: {substandard['substandard_id']}")
    print(f"Description: {substandard['substandard_description'][:80]}...")
    print(f"{'='*80}")
    
    prompt = create_sequence_generation_prompt(substandard, exemplars, template)
    
    try:
        response = produce_structured_response_gemini(prompt, GeneratedSequenceResponse)
        print(f"✅ Generated {len(response.sequences)} sequences")
        return response
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        raise

def save_generated_sequences(results: list, output_filename: str = None):
    """Save generated sequences to JSON file."""
    
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"generated_sequences_{timestamp}.json"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    outputs_dir = os.path.join(os.path.dirname(script_dir), "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    
    output_path = os.path.join(outputs_dir, output_filename)
    
    output_data = {
        "metadata": {
            "generation_timestamp": datetime.now().isoformat(),
            "total_substandards_processed": len(results),
            "llm_model": "gemini-2.5-pro",
            "generation_version": "1.0"
        },
        "generated_sequences": results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved generated sequences to: {output_path}")
    return output_path

# ============================================================================
# Main Function
# ============================================================================

def main():
    """Main execution function."""
    
    print("="*80)
    print("DI SEQUENCE GENERATOR")
    print("="*80)
    
    # Check API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return
    
    # Load data
    print("\n📥 Loading data...")
    mappings_data = load_mappings_data()
    di_data = load_di_formats()
    
    # Get substandards needing sequences
    print("\n🔍 Identifying substandards needing sequences...")
    needs_sequences = get_substandards_needing_sequences(mappings_data, threshold=1)
    print(f"Found {len(needs_sequences)} substandards needing sequences (0 matches)")
    
    # Get exemplar sequences
    print("\n📚 Loading exemplar sequences...")
    exemplars = get_exemplar_sequences(di_data, grade=3)
    print(f"Loaded {len(exemplars)} exemplar sequences")
    
    # Load prompt template
    print("\n📝 Loading prompt template...")
    template = load_prompt_template("sequence_generation")
    
    # Generate sequences
    print("\n🔨 Generating sequences...")
    results = []
    
    # Process first 5 for testing (remove limit for full run)
    for i, substandard in enumerate(needs_sequences[:5], 1):
        print(f"\n[{i}/{min(5, len(needs_sequences))}]")
        
        try:
            response = generate_sequences_for_substandard(
                substandard,
                exemplars,
                template
            )
            
            result = {
                "substandard_id": substandard['substandard_id'],
                "grade": substandard['grade'],
                "substandard_description": substandard['substandard_description'],
                "assessment_boundary": substandard['assessment_boundary'],
                "generated_sequences": [seq.model_dump() for seq in response.sequences],
                "generation_reasoning": response.generation_reasoning,
                "generated_at": datetime.now().isoformat()
            }
            
            results.append(result)
            
            # Show generated sequences
            for seq in response.sequences:
                print(f"  - Seq #{seq.sequence_number}: {seq.problem_type}")
            
        except Exception as e:
            print(f"❌ Failed to generate for {substandard['substandard_id']}: {e}")
            continue
    
    # Save results
    if results:
        output_path = save_generated_sequences(results)
        
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Total substandards processed: {len(results)}")
        print(f"Total sequences generated: {sum(len(r['generated_sequences']) for r in results)}")
        print(f"Output: {output_path}")
    else:
        print("\n⚠️  No sequences were generated")

if __name__ == "__main__":
    main()

